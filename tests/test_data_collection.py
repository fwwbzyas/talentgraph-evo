from __future__ import annotations

from agents.data.collection import CollectionScheduler, DataCollectionAgent
from agents.data.normalization import normalize_recruitment_item
from contracts import CollectionStrategyRequest, DataCollectionRequest, DataQualityRejection, SourceCollectionStrategy
from core.store import AppStore


class FakeSource:
    def __init__(self, source_id: str, source_category: str, items: list[dict]):
        self.source_id = source_id
        self.source_category = source_category
        self.display_name = source_id
        self.access_mode = "test_fixture"
        self.items = items

    def fetch(self, *, max_items: int, lookback_hours: int):
        return self.items[:max_items]


def test_normalizer_enforces_new_information_technology_scope():
    engineering, _ = normalize_recruitment_item({
        "source_id": "ai-1",
        "source_platform": "fixture",
        "source_url": "https://example.com/jobs/ai-1",
        "title": "AI Agent Engineer",
        "company": "Example",
        "content": "Build production LLM, RAG and LangGraph systems with Python. " * 12,
        "collection_mode": "live",
    })
    sales, issues = normalize_recruitment_item({
        "source_id": "sales-1",
        "source_platform": "fixture",
        "title": "Sales Manager",
        "company": "Example",
        "content": "Sell artificial intelligence products. " * 12,
        "collection_mode": "live",
    })

    assert engineering and engineering["domain"] == "人工智能"
    assert {"Python", "RAG", "LangGraph", "LLM", "Agent"} <= set(engineering["skill_tags"])
    assert sales is None and "outside_target_scope" in issues


def test_normalizer_accepts_platform_architect_analyst_and_network_roles():
    examples = [
        (
            "AI平台工程师",
            "建设 AI 平台、模型服务、向量检索和 Python 后端工程能力。 " * 10,
            "人工智能",
        ),
        (
            "AI Agent工程师",
            "负责 AI Agent、LLM、RAG、工具调用和 LangGraph 工作流研发。 " * 10,
            "人工智能",
        ),
        (
            "AI解决方案架构师",
            "设计 AI 架构、大模型应用、RAG 知识库和企业级系统集成方案。 " * 10,
            "人工智能",
        ),
        (
            "数据分析师",
            "负责数据分析、SQL、BI 报表、指标体系和业务数据洞察。 " * 10,
            "大数据",
        ),
        (
            "计算机网络工程师5k+",
            "负责计算机网络、TCP/IP、Linux、网络设备运维和系统集成支持。 " * 10,
            "智能系统",
        ),
    ]

    for index, (title, content, expected_domain) in enumerate(examples):
        normalized, issues = normalize_recruitment_item({
            "source_id": f"tech-role-{index}",
            "source_platform": "fixture",
            "source_url": f"https://example.com/jobs/tech-role-{index}",
            "title": title,
            "company": "Example",
            "content": content,
            "collection_mode": "live",
        })

        assert normalized is not None, (title, issues)
        assert normalized["domain"] == expected_domain


def test_collection_separates_primary_jobs_and_auxiliary_community_signals(tmp_path):
    recruitment = FakeSource("jobs", "recruitment", [
        {
            "source_id": "job-1", "source_platform": "jobs", "source_url": "https://example.com/job-1",
            "title": "Senior Data Engineer", "company": "Data Co", "city": "Shanghai",
            "content": "Build real-time data platforms using Flink, Spark, Kafka and SQL. " * 12,
            "published_at": "2026-07-16T00:00:00Z", "collection_mode": "live",
        },
        {
            "source_id": "sales-1", "source_platform": "jobs", "source_url": "https://example.com/sales-1",
            "title": "Sales Manager", "company": "Data Co", "content": "Sell big data products. " * 12,
            "collection_mode": "live",
        },
    ])
    community = FakeSource("forum", "community_signal", [{
        "signal_id": "question-1", "source_platform": "forum", "source_type": "developer_community",
        "source_url": "https://example.com/questions/1", "title": "Flink checkpoint latency in production",
        "content": "How should a data platform tune Flink checkpoints and Kafka backpressure? " * 5,
        "tags": ["flink", "kafka", "big-data"], "domain_hint": "大数据",
        "published_at": "2026-07-16T00:00:00Z", "engagement": {"views": 80, "answers": 3},
    }])
    local_store = AppStore(str(tmp_path / "collection.db"))
    collector = DataCollectionAgent(sources={"jobs": recruitment, "forum": community}, app_store=local_store)

    run = collector.collect(DataCollectionRequest(source_ids=["jobs", "forum"], max_items_per_source=10))

    assert run.status == "completed"
    assert run.recruitment_fetched == 2 and run.recruitment_accepted == 1
    assert run.community_fetched == 1 and run.community_accepted == 1
    assert run.new_count == 1
    assert len(local_store.jobs) == 1
    assert len(local_store.community_signals) == 1
    assert next(iter(local_store.community_signals.values())).metadata["auxiliary_only"] is True
    assert run.quality_summary["evidence_policy"] == {"recruitment": "primary", "community_signal": "auxiliary"}


def test_live_collection_detects_updates_by_stable_source_id(tmp_path):
    source = FakeSource("jobs", "recruitment", [{
        "source_id": "iot-1", "source_platform": "jobs", "source_url": "https://example.com/iot-1",
        "title": "IoT Platform Engineer", "company": "Device Co", "content": "Build MQTT device access and edge gateway systems. " * 12,
        "collection_mode": "live",
    }])
    local_store = AppStore(str(tmp_path / "updates.db"))
    collector = DataCollectionAgent(sources={"jobs": source}, app_store=local_store)

    first = collector.collect(DataCollectionRequest(source_ids=["jobs"]))
    second = collector.collect(DataCollectionRequest(source_ids=["jobs"]))
    source.items[0]["content"] += " Add RTOS firmware OTA operations."
    third = collector.collect(DataCollectionRequest(source_ids=["jobs"]))

    assert first.new_count == 1
    assert second.unchanged_count == 1
    assert third.updated_count == 1


def test_exact_duplicates_skip_review_queue_but_quality_failures_keep_evidence(tmp_path):
    duplicate = {
        "source_id": "data-1", "source_platform": "jobs", "source_url": "https://example.com/data-1",
        "title": "Senior Data Engineer", "company": "Data Co",
        "content": "Build real-time data platforms using Flink, Spark, Kafka and SQL. " * 12,
        "collection_mode": "live",
    }
    source = FakeSource("jobs", "recruitment", [
        duplicate,
        {**duplicate, "source_id": "data-copy", "source_url": "https://example.com/data-copy"},
        {
            "source_id": "sales-2", "source_platform": "jobs", "source_url": "https://example.com/sales-2",
            "title": "Sales Manager", "company": "Data Co", "content": "Sell software products. " * 12,
            "collection_mode": "live",
        },
    ])
    local_store = AppStore(str(tmp_path / "audit.db"))
    collector = DataCollectionAgent(sources={"jobs": source}, app_store=local_store)

    run = collector.collect(DataCollectionRequest(source_ids=["jobs"], max_items_per_source=10))

    records = list(local_store.quality_rejections.values())
    assert {record.record_type for record in records} == {"quality_rejection"}
    assert all(record.raw_item for record in records)
    assert all(record.source_url for record in records)
    assert all(record.review_status == "pending" for record in records)
    assert run.exact_duplicate_count == 1


def test_collection_strategy_updates_scheduler_and_both_domestic_sources(tmp_path):
    class ConfigurableSource(FakeSource):
        available_cities = {"全国": "all", "北京": "beijing", "上海": "shanghai"}
        queries = ("AI Agent 工程师", "大数据开发工程师")

        def configure(self, **kwargs):
            self.configuration = kwargs

    boss = ConfigurableSource("boss", "recruitment", [])
    zhaopin = ConfigurableSource("zhaopin", "recruitment", [])
    local_store = AppStore(str(tmp_path / "strategy.db"))
    collector = DataCollectionAgent(sources={"boss": boss, "zhaopin": zhaopin}, app_store=local_store)
    scheduler = CollectionScheduler(collector)

    result = scheduler.configure_strategy(CollectionStrategyRequest(
        sources={
            "boss": SourceCollectionStrategy(
                enabled=False, min_interval_minutes=5, max_interval_minutes=10,
                items_per_run=50, cities=["北京", "上海"], job_queries=["AI Agent 工程师"],
            ),
            "zhaopin": SourceCollectionStrategy(
                enabled=False, min_interval_minutes=15, max_interval_minutes=20,
                items_per_run=80, cities=["全国"], job_queries=["大数据开发工程师"],
            ),
        },
    ))

    assert result["sources"]["boss"]["items_per_run"] == 50
    assert result["sources"]["zhaopin"]["items_per_run"] == 80
    assert boss.configuration != zhaopin.configuration
    assert boss.configuration["items_per_run"] == 50
    assert zhaopin.configuration["items_per_run"] == 80
    assert scheduler.status()["enabled"] is False


def test_store_tracks_exact_duplicates_observations_and_job_versions(tmp_path):
    source = FakeSource("jobs", "recruitment", [{
        "source_id": "agent-1", "source_platform": "jobs", "source_url": "https://example.com/agent-1",
        "title": "AI Agent Engineer", "company": "Agent Co", "city": "北京",
        "content": "Build production AI Agent, LLM, RAG and Python systems. " * 12,
        "collection_mode": "live",
    }])
    local_store = AppStore(str(tmp_path / "history.db"))
    collector = DataCollectionAgent(sources={"jobs": source}, app_store=local_store)

    first = collector.collect(DataCollectionRequest(source_ids=["jobs"])).new_count
    second = collector.collect(DataCollectionRequest(source_ids=["jobs"])).unchanged_count
    source.items[0]["content"] += "Add LangGraph workflow observability and model evaluation."
    third = collector.collect(DataCollectionRequest(source_ids=["jobs"])).updated_count

    assert (first, second, third) == (1, 1, 1)
    job_id = next(iter(local_store.jobs))
    assert len(local_store.list_job_versions(job_id)) == 2
    assert [item["outcome"] for item in local_store.list_job_observations(job_id)] == ["updated", "unchanged", "new"]
    change_audits = [item for item in local_store.data_audits.values() if item.record_type == "job_change"]
    assert len(change_audits) == 1
    assert change_audits[0].field_changes
    assert change_audits[0].graph_publish_status == "published"


def test_cross_source_update_preserves_canonical_job_provenance(tmp_path):
    primary = FakeSource("zhaopin", "recruitment", [{
        "source_id": "primary-1", "source_platform": "zhaopin",
        "source_url": "https://example.com/zhaopin/primary-1",
        "title": "Data Platform Engineer", "company": "Data Co", "city": "北京",
        "content": "Build Flink, Spark, Kafka and Python data platform services. " * 12,
        "collection_mode": "live",
    }])
    alias = FakeSource("51job", "recruitment", [{
        "source_id": "alias-1", "source_platform": "51job",
        "source_url": "https://example.com/51job/alias-1",
        "title": "Data Platform Engineer", "company": "Data Co", "city": "北京",
        "content": "Develop Hadoop, Elasticsearch, Java and SQL warehouse systems. " * 12,
        "collection_mode": "live",
    }])
    local_store = AppStore(str(tmp_path / "cross-source-provenance.db"))
    collector = DataCollectionAgent(
        sources={"zhaopin": primary, "51job": alias}, app_store=local_store,
    )

    assert collector.collect(DataCollectionRequest(source_ids=["zhaopin"])).new_count == 1
    assert collector.collect(DataCollectionRequest(source_ids=["51job"])).updated_count == 1

    job = next(iter(local_store.jobs.values()))
    assert job.source_id == "zhaopin:primary-1"
    assert job.source_platform == "zhaopin"
    assert job.source_url == "https://example.com/zhaopin/primary-1"
    assert job.metadata["source_aliases"] == ["51job:alias-1"]
    assert job.metadata["updated_from_source_platform"] == "51job"


def test_human_review_creates_versioned_normalization_policy(tmp_path):
    local_store = AppStore(str(tmp_path / "learning.db"))
    record = DataQualityRejection(
        source_category="recruitment", source_id="future-1", source_platform="jobs",
        title="数字孪生调优师", reasons=["outside_target_scope"],
        raw_item={"title": "数字孪生调优师"},
    )
    local_store.save_quality_rejections([record])

    local_store.review_quality_rejection(
        record.rejection_id, "approved", decision="accept_scope", corrections={"domain": "智能系统"},
    )
    policy = local_store.audit_learning_status()
    normalized, issues = normalize_recruitment_item({
        "source_id": "future-1", "source_platform": "jobs", "title": "数字孪生调优师",
        "company": "Future Co", "source_url": "https://example.com/future-1",
        "content": "负责工业数字孪生系统的生产部署、性能调优、故障诊断与交付。" * 12,
        "collection_mode": "live",
    }, policy)

    assert policy["version"] == 1 and policy["feedback_count"] == 1
    assert normalized is not None, issues
    assert normalized["domain"] == "智能系统"
