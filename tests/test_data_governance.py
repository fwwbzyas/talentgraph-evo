from __future__ import annotations

from datetime import UTC, datetime, timedelta
import sqlite3

from agents.data.collection import DataCollectionAgent
from agents.data.evidence import EvidenceIntelligenceService
from agents.data.governance import DataGovernanceAgent
from agents.data.normalization import normalize_recruitment_item
from contracts import CommunitySignal, DataCollectionRequest
from core.store import AppStore


class FakeSource:
    def __init__(self, source_id: str, source_category: str, items: list[dict]):
        self.source_id = source_id
        self.source_category = source_category
        self.display_name = source_id
        self.access_mode = "test_fixture"
        self.items = items

    def fetch(self, *, max_items: int, lookback_hours: int):
        del lookback_hours
        return self.items[:max_items]

    def configure(self, **kwargs):
        self.configuration = kwargs

    def seed_seen(self, source_ids):
        self.seeded = source_ids


def recruitment_item(source_id: str, platform: str = "boss", **changes):
    base = {
        "source_id": source_id,
        "source_platform": platform,
        "source_url": f"https://example.com/{source_id}",
        "title": "AI Agent 工程师",
        "company": "示例科技",
        "city": "北京",
        "content": (
            "岗位职责：负责 AI Agent、RAG 和 Python 应用的设计、开发与生产交付。"
            "任职要求：熟悉 LangGraph、向量数据库和模型评测，具备工程实践经验。"
        ) * 8,
        "tags": ["Python", "本科", "五险一金", "RAG"],
        "published_at": datetime.now(UTC).isoformat(),
        "collection_mode": "live",
    }
    return {**base, **changes}


def test_rule_governance_filters_polluted_tags_and_flags_title_content_mismatch():
    normalized, issues = normalize_recruitment_item(recruitment_item("clean-1"))
    assert normalized is not None, issues
    assert {"本科", "五险一金"}.isdisjoint(normalized["skill_tags"])

    mismatch = recruitment_item(
        "mismatch-1",
        title="Flink 实时计算工程师",
        content=(
            "岗位职责：负责 AI Agent Marketplace 产品规划、插件生态运营和客户方案交付。"
            "任职要求：熟悉大模型应用、RAG、提示词工程和智能体工作流。"
        ) * 8,
    )
    candidate, _ = normalize_recruitment_item(mismatch)
    assessment = DataGovernanceAgent().assess_recruitment(mismatch, candidate)

    assert "title_content_mismatch" in assessment.reasons
    assert assessment.status == "manual_review"
    assert assessment.evidence_snippets


def test_collection_persists_lineage_for_accepted_and_rejected_records(tmp_path):
    source = FakeSource("boss", "recruitment", [
        recruitment_item("accepted-1"),
        recruitment_item(
            "noise-1",
            title="人工智能课程销售",
            content="负责课程推广、电话销售、客户转化和招生运营。" * 20,
        ),
    ])
    local_store = AppStore(str(tmp_path / "governance.db"))
    collector = DataCollectionAgent(sources={"boss": source}, app_store=local_store)

    collector.collect(DataCollectionRequest(source_ids=["boss"], max_items_per_source=10))

    records = list(local_store.data_audits.values())
    assert len(records) == 2
    assert {record.status for record in records} == {"accepted", "rejected"}
    assert all(record.raw_item for record in records)
    assert all(record.rule_assessment for record in records)
    accepted = next(record for record in records if record.status == "accepted")
    assert accepted.normalized_item["source_id"].endswith("accepted-1")
    assert accepted.graph_publish_status == "published"


def test_copy_clusters_reduce_repeated_evidence_to_independent_companies(tmp_path):
    local_store = AppStore(str(tmp_path / "copies.db"))
    source = FakeSource("boss", "recruitment", [
        recruitment_item("copy-1", company="甲公司"),
        recruitment_item("copy-2", company="乙公司"),
        recruitment_item("different-1", company="丙公司", content=(
            "岗位职责：建设数据仓库与实时计算平台，负责 Flink 和 Kafka 任务开发。"
            "任职要求：熟悉 Java、SQL、数据治理和湖仓架构。"
        ) * 8, title="大数据开发工程师"),
    ])
    collector = DataCollectionAgent(sources={"boss": source}, app_store=local_store)
    collector.collect(DataCollectionRequest(source_ids=["boss"], max_items_per_source=10))

    clusters = EvidenceIntelligenceService().copy_clusters(local_store.jobs.values())

    assert len(clusters) == 1
    assert clusters[0]["record_count"] == 2
    assert clusters[0]["independent_company_count"] == 2
    assert set(clusters[0]["source_ids"]) == {"boss:copy-1", "boss:copy-2"}


def test_copy_clusters_detect_segment_level_copy_with_local_edits(tmp_path):
    original = recruitment_item("copy-segment-1", company="甲公司")
    edited = recruitment_item(
        "copy-segment-2",
        company="乙公司",
        content=original["content"].replace(
            "具备工程实践经验",
            "具备三年以上工程实践经验，薪资范围面议",
            1,
        ),
    )
    source = FakeSource("zhaopin", "recruitment", [original, edited])
    local_store = AppStore(str(tmp_path / "segment_copies.db"))
    collector = DataCollectionAgent(sources={"zhaopin": source}, app_store=local_store)

    collector.collect(DataCollectionRequest(source_ids=["zhaopin"], max_items_per_source=10))
    clusters = EvidenceIntelligenceService().copy_clusters(local_store.jobs.values())

    assert len(clusters) == 1
    assert clusters[0]["similarity"] >= 0.28
    assert "分段指纹" in clusters[0]["reason"]


def test_technology_trends_keep_community_as_auxiliary_evidence():
    normalized, _ = normalize_recruitment_item(recruitment_item("job-1"))
    signal = CommunitySignal(
        signal_id="github:agent-runtime",
        source_type="developer_community",
        source_platform="github",
        source_url="https://github.com/example/agent-runtime",
        domain="人工智能",
        title="Agent runtime with LangGraph and tool calling",
        content="A fast growing Agent runtime built with LangGraph, RAG and tool calling.",
        tags=["LangGraph", "Agent", "RAG"],
        engagement={"stars": 850},
        published_at=datetime.now(UTC) - timedelta(days=2),
        quality_score=92,
        dedup_hash="signal-1",
    )

    trends = EvidenceIntelligenceService().technology_trends(
        [type("Job", (), normalized)()],
        [signal],
    )
    langgraph = next(item for item in trends if item["technology"] == "LangGraph")

    assert langgraph["auxiliary_evidence_count"] == 1
    assert langgraph["recruitment_evidence_count"] == 1
    assert langgraph["evidence_role"] == "auxiliary_plus_recruitment"
    assert langgraph["can_publish_ability"] is True


def test_human_audit_feedback_learns_once_and_republishes_in_background(tmp_path):
    mismatch = recruitment_item(
        "human-review-1",
        title="Flink 实时计算工程师",
        content=(
            "岗位职责：负责 AI Agent 与 RAG 平台的研发和生产交付。"
            "任职要求：熟悉 Python、LangGraph、模型评测和智能体工作流。"
        ) * 8,
    )
    local_store = AppStore(str(tmp_path / "learning.db"))
    collector = DataCollectionAgent(
        sources={"boss": FakeSource("boss", "recruitment", [mismatch])},
        app_store=local_store,
    )
    collector.collect(DataCollectionRequest(source_ids=["boss"], max_items_per_source=10))
    audit = next(record for record in local_store.data_audits.values() if record.source_id.endswith("human-review-1"))
    reviewed = local_store.review_data_audit(
        audit.audit_id,
        "approved",
        corrections={"title": "AI Agent 工程师", "domain": "人工智能"},
    )

    collector.reprocess_data_audit(reviewed)
    collector.reprocess_data_audit(reviewed)

    policy = local_store.get_setting("audit_learning_policy")
    assert policy["feedback_count"] == 1
    assert policy["accepted_titles"]["ai agent 工程师"]["domain"] == "人工智能"
    assert any(job.metadata.get("quality_status") == "human_approved" for job in local_store.jobs.values())


def test_legacy_audit_backfill_repairs_missing_lineage_incrementally(tmp_path):
    db_path = tmp_path / "partial_lineage.db"
    collector = DataCollectionAgent(
        sources={
            "boss": FakeSource(
                "boss",
                "recruitment",
                [
                    recruitment_item("legacy-1"),
                    recruitment_item(
                        "legacy-2",
                        company="乙公司",
                        title="大数据开发工程师",
                        content=(
                            "岗位职责：建设实时数据平台并治理数据质量。"
                            "任职要求：熟悉 Flink、Kafka、Spark、SQL 和数据仓库。"
                        ) * 10,
                    ),
                ],
            )
        },
        app_store=AppStore(str(db_path)),
    )
    collector.collect(DataCollectionRequest(source_ids=["boss"], max_items_per_source=10))

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "DELETE FROM data_audits WHERE audit_id IN "
            "(SELECT audit_id FROM data_audits LIMIT 1)"
        )

    reloaded = AppStore(str(db_path))

    assert len(reloaded.jobs) == 2
    assert {
        record.source_id for record in reloaded.data_audits.values()
        if record.source_category == "recruitment"
    } == {"boss:legacy-1", "boss:legacy-2"}
