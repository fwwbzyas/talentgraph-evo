from __future__ import annotations

import json
from pathlib import Path

from agents.data.collection import DataCollectionAgent
from agents.data.job51_browser import Job51BrowserSource, compute_sign, parse_job51_payload
from agents.data.liepin_browser import (
    LiepinBrowserSource,
    enrich_liepin_detail,
    liepin_public_topic_urls,
    parse_liepin_cards_html,
    parse_liepin_mobile_cards_html,
)
from agents.data.normalization import normalize_recruitment_item
from agents.data.source_policy import SUPPLEMENTAL_INTERVAL_MINUTES, SUPPLEMENTAL_ITEMS_PER_RUN
from agents.data.sources import default_sources, source_catalog
from agents.data.supplemental_recruitment import (
    CollectionRiskControlError,
    CollectionTransientSourceError,
    TARGET_CITIES,
    TARGET_JOB_QUERIES,
)
from agents.emerging_jobs.service import EmergingJobAgent
from agents.evolution.service import EvolutionAgent
from agents.job_graph.knowledge_graph import KnowledgeGraphService
from agents.job_graph.service import JobGraphAgent
from agents.match.service import MatchAgent
from contracts import CandidateProfile, CleanedDataBatch, CollectionStrategyRequest, DataCollectionRequest, EmergingJobDiscoveryRequest
from core.store import AppStore


ROOT = Path(__file__).resolve().parents[1]


class FixtureRecruitmentSource:
    source_category = "recruitment"
    access_mode = "test_fixture"
    enabled = True

    def __init__(self, source_id: str, items: list[dict]):
        self.source_id = source_id
        self.display_name = source_id
        self.items = items

    def fetch(self, *, max_items: int, lookback_hours: int):
        del lookback_hours
        return self.items[:max_items]


class RiskControlledRecruitmentSource(FixtureRecruitmentSource):
    def fetch(self, *, max_items: int, lookback_hours: int):
        del max_items, lookback_hours
        raise CollectionRiskControlError(self.source_id, "https://example.invalid/verification", "captcha")


class TransientRecruitmentSource(FixtureRecruitmentSource):
    last_fetch_stats = {"end_reason": "source_temporarily_unavailable", "pages_visited": 1}

    def fetch(self, *, max_items: int, lookback_hours: int):
        del max_items, lookback_hours
        raise CollectionTransientSourceError(self.source_id, "ERR_CONNECTION_CLOSED")


def _job51_raw() -> dict:
    payload = {
        "resultbody": {
            "job": {
                "totalCount": 1,
                "items": [{
                    "jobId": "job51-agent-1",
                    "jobName": "AI Agent 工程师",
                    "provideSalaryString": "20-35k·14薪",
                    "jobAreaString": "北京-海淀区",
                    "workYearString": "3-5年",
                    "degreeString": "本科",
                    "issueDateString": "2026-08-20T09:00:00+08:00",
                    "jobHref": "https://jobs.51job.com/beijing/job51-agent-1.html?tracking=x",
                    "fullCompanyName": "甲智能科技有限公司",
                    "companyIndustryType1Str": "人工智能",
                    "companySizeString": "500-1000人",
                    "jobDescribe": ("负责 AI Agent 平台研发，使用 Python、RAG、LangGraph、向量数据库和 Docker，"
                                    "建设工具调用、模型评测、可观测性与生产交付体系。" * 8)
                                   + " 联系邮箱 dev@example.com，手机 13800138000。",
                }],
            },
        },
    }
    rows, total = parse_job51_payload(payload, keyword="AI Agent 工程师", search_city="北京", search_page=1)
    assert total == 1
    return rows[0]


def _liepin_raw() -> dict:
    cards = """
    <div class="job-card-pc-container">
      <a data-nick="job-detail-job-info" href="https://www.liepin.com/job/1974521297.shtml?track=x">
        <div class="job-title-box"><div>AI Agent 工程师</div></div>
        <div class="job-dq-box"><span>北京-朝阳区</span></div>
        <span class="job-salary">25-40k·15薪</span>
        <div class="job-labels-box"><span>3-5年</span><span>本科</span></div>
      </a>
      <div class="company-name">乙大模型科技有限公司</div>
      <div class="company-tags-box"><span>人工智能</span><span>100-499人</span></div>
    </div>
    """
    rows = parse_liepin_cards_html(cards, keyword="AI Agent 工程师", search_city="北京", search_page=0)
    detail = """
    <html><head><title>【北京 AI Agent 工程师招聘】-乙大模型科技有限公司招聘信息-猎聘</title></head>
    <body><section class="job-intro">负责大模型应用与 AI Agent 研发，使用 Python、RAG、LangGraph、
    FastAPI、Docker 和向量数据库，建设多 Agent 协作、工具调用、模型评测和稳定性监控。</section></body></html>
    """
    rows[0] = enrich_liepin_detail(detail * 6, rows[0])
    return rows[0]


def test_team_parsers_emit_existing_talentgraph_raw_contract_and_mask_contacts():
    raw = _job51_raw()
    normalized, issues = normalize_recruitment_item(raw)

    assert normalized is not None, issues
    assert normalized["source_id"] == "51job:job51-agent-1"
    assert normalized["source_platform"] == "51job"
    assert normalized["city"] == "北京" and normalized["district"] == "海淀区"
    assert normalized["salary_min_k"] == 20 and normalized["salary_max_k"] == 35
    assert raw["metadata"]["query"] == "AI Agent 工程师"
    assert "?" not in raw["source_url"]
    assert "[EMAIL]" in raw["content"] and "[PHONE]" in raw["content"]
    assert "dev@example.com" not in raw["content"] and "13800138000" not in raw["content"]


def test_liepin_parser_uses_canonical_url_and_rendered_public_jd():
    raw = _liepin_raw()
    normalized, issues = normalize_recruitment_item(raw)

    assert normalized is not None, issues
    assert normalized["source_id"] == "liepin:1974521297"
    assert normalized["source_platform"] == "liepin"
    assert normalized["city"] == "北京" and normalized["district"] == "朝阳区"
    assert "?" not in normalized["source_url"]
    assert {"Python", "RAG", "LangGraph"} <= set(normalized["skill_tags"])


def test_liepin_mobile_parser_emits_the_same_raw_jd_contract():
    mobile_html = """
    <a class="job-card" href="https://m.liepin.com/job/1985080761.shtml?track=mobile">
      <div class="job-title"><span>大模型应用工程师</span></div>
      <h3><small>25-45k·14薪</small></h3>
      <div class="job-card-company"><span>示例人工智能科技有限公司</span></div>
      <div class="job-card-labels">
        <label>北京-海淀区</label><label>3-5年经验</label><label>本科</label><label>人工智能</label>
      </div>
    </a>
    """
    rows = parse_liepin_mobile_cards_html(
        mobile_html,
        keyword="大模型应用工程师",
        search_city="北京",
        search_page=0,
    )

    assert len(rows) == 1
    raw = rows[0]
    assert raw["source_id"] == "1985080761"
    assert raw["source_platform"] == "liepin"
    assert raw["city"] == "北京" and raw["district"] == "海淀区"
    assert raw["salary_min_k"] == 25 and raw["salary_max_k"] == 45
    assert raw["experience_min_years"] == 3 and raw["experience_max_years"] == 5
    assert raw["education"] == "本科"
    assert raw["metadata"]["public_mobile_fallback"] is True


def test_liepin_mobile_detail_falls_back_to_visible_job_intro():
    raw = parse_liepin_mobile_cards_html(
        """
        <a class="job-card" href="https://m.liepin.com/job/1985080762.shtml">
          <div class="job-title"><span>大模型应用工程师</span></div>
          <div class="job-card-company"><span>示例人工智能科技有限公司</span></div>
        </a>
        """,
        keyword="大模型应用工程师",
        search_city="北京",
        search_page=0,
    )[0]
    visible_text = """
    登录
    大模型应用工程师
    职位介绍
    岗位职责：负责大模型应用与 AI Agent 平台研发，使用 Python、RAG、LangGraph、FastAPI 和 Docker 建设生产系统。
    任职要求：熟悉向量数据库、模型评测、工具调用和多 Agent 协作，具备三年以上后端开发经验。
    查看全部
    公司信息
    示例人工智能科技有限公司
    """

    enriched = enrich_liepin_detail("<html><body><div class='hashed-class'>职位介绍</div></body></html>", raw, visible_text)
    normalized, issues = normalize_recruitment_item(enriched)

    assert "大模型应用" in enriched["content"]
    assert "公司信息" not in enriched["content"]
    assert normalized is not None, issues
    assert {"Python", "RAG", "LangGraph"} <= set(normalized["skill_tags"])
    assert "?" not in raw["source_url"]


def test_liepin_public_topic_fallback_is_query_aware_and_bounded():
    ai_urls = liepin_public_topic_urls("AI Agent 工程师", 0)
    data_urls = liepin_public_topic_urls("大数据开发工程师", 2)

    assert len(ai_urls) == len(data_urls) == 4
    assert len(set(ai_urls)) == 4 and len(set(data_urls)) == 4
    assert ai_urls[0].startswith("https://m.liepin.com/zpzndhsfgcs3nv2/")
    assert data_urls[0].startswith("https://m.liepin.com/zpyfjsgcs5x4h/")
    assert all(url.endswith("?curPage=2") for url in data_urls)


def test_new_sources_share_zhaopin_scope_and_have_low_volume_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("TALENTGRAPH_LIEPIN_ROBOTS_ACKNOWLEDGED", "1")
    monkeypatch.setenv("TALENTGRAPH_51JOB_STATE_PATH", str(tmp_path / "51job.json"))
    monkeypatch.setenv("TALENTGRAPH_LIEPIN_STATE_PATH", str(tmp_path / "liepin.json"))
    sources = default_sources()
    catalog = {item["source_id"]: item for item in source_catalog(sources)}
    local_store = AppStore(str(tmp_path / "strategy.db"))
    collector = DataCollectionAgent(sources=sources, app_store=local_store)
    status = collector.apply_strategy(CollectionStrategyRequest(
        cities=list(TARGET_CITIES),
        job_queries=list(TARGET_JOB_QUERIES),
    ), persist=False)

    assert {"51job", "liepin"} <= set(catalog)
    assert catalog["51job"]["source_category"] == catalog["liepin"]["source_category"] == "recruitment"
    assert tuple(sources["51job"].available_queries) == tuple(sources["zhaopin"].available_queries)
    assert tuple(city for city in sources["51job"].available_cities if city != "全国") == TARGET_CITIES
    for source_id in ("51job", "liepin"):
        config = status["sources"][source_id]
        assert config["items_per_run"] == SUPPLEMENTAL_ITEMS_PER_RUN
        assert config["min_interval_minutes"] == config["max_interval_minutes"] == SUPPLEMENTAL_INTERVAL_MINUTES
        assert tuple(config["cities"]) == TARGET_CITIES
        assert tuple(config["job_queries"]) == TARGET_JOB_QUERIES


def test_new_source_jobs_flow_through_governance_graph_evolution_emerging_and_match(tmp_path):
    sources = {
        "51job": FixtureRecruitmentSource("51job", [_job51_raw()]),
        "liepin": FixtureRecruitmentSource("liepin", [_liepin_raw()]),
    }
    local_store = AppStore(str(tmp_path / "compatibility.db"))
    collector = DataCollectionAgent(sources=sources, app_store=local_store)
    run = collector.collect(DataCollectionRequest(
        source_ids=["51job", "liepin"], max_items_per_source=5, min_job_quality=60,
    ))

    jobs = list(local_store.jobs.values())
    assert run.status == "completed" and run.recruitment_accepted == 2
    assert {job.source_platform for job in jobs} == {"51job", "liepin"}
    assert all(job.source_id.startswith(f"{job.source_platform}:") for job in jobs)
    assert all(record.graph_publish_status == "published" for record in local_store.data_audits.values() if record.status == "accepted")

    graph_payload = KnowledgeGraphService().build(jobs, max_evidence=20)
    assert graph_payload["stats"]["source_jobs"] == 2
    assert set(graph_payload["stats"]["sources"]) == {"51job", "liepin"}

    batch = CleanedDataBatch(batch_name="supplemental_compatibility", items=jobs)
    graph = JobGraphAgent().run(batch, "AI Agent 工程师")
    evidence_ids = {evidence.source_id for skill in graph.skills for evidence in skill.evidence}
    assert {job.source_id for job in jobs} <= evidence_ids
    evolution = EvolutionAgent().run(graph)
    assert evolution.job_id == graph.job_id and evolution.changes

    candidates = EmergingJobAgent().discover(
        [batch], [graph], EmergingJobDiscoveryRequest(minimum_source_count=1, minimum_confidence=0), jobs,
    )
    assert candidates and {item["source_platform"] for item in candidates[0].evidence} == {"51job", "liepin"}

    profile = CandidateProfile(
        candidate_id="candidate-supplemental",
        target_job_id=graph.job_id,
        skills=[{"name": "Python", "level": "advanced"}, {"name": "RAG", "level": "advanced"}, {"name": "LangGraph", "level": "intermediate"}],
        evidence=[{"type": "project", "content": "生产级 AI Agent 与 RAG 项目"}],
        confidence=0.9,
    )
    report = MatchAgent().run(graph, profile)
    assert report.target_job_id == graph.job_id
    assert report.job_snapshot["evidence_summary"]["source_count"] >= 2


def test_supplemental_risk_control_is_silent_and_does_not_fail_the_run(tmp_path):
    local_store = AppStore(str(tmp_path / "risk-control.db"))
    collector = DataCollectionAgent(
        sources={"51job": RiskControlledRecruitmentSource("51job", [])},
        app_store=local_store,
    )

    run = collector.collect(DataCollectionRequest(source_ids=["51job"], max_items_per_source=5))

    assert run.status == "completed"
    assert run.source_results[0].status == "success"
    assert run.source_results[0].phase == "completed"
    assert run.source_results[0].error is None
    assert run.source_results[0].end_reason is None


def test_supplemental_network_outage_is_bounded_and_silent(tmp_path):
    local_store = AppStore(str(tmp_path / "transient-source.db"))
    collector = DataCollectionAgent(
        sources={"liepin": TransientRecruitmentSource("liepin", [])},
        app_store=local_store,
    )

    run = collector.collect(DataCollectionRequest(source_ids=["liepin"], max_items_per_source=5))

    assert run.status == "completed"
    assert run.source_results[0].status == "success"
    assert run.source_results[0].error is None
    assert run.source_results[0].end_reason == "source_temporarily_unavailable"


def test_51job_sign_algorithm_remains_compatible_with_team_crawler():
    relative_url = (
        "/api/job/search-pc?api_key=51job&timestamp=1700000000&keyword=Python"
        "&searchType=2&function=&industry=&jobArea=000000&jobArea2=&landmark="
        "&metro=&salary=&workYear=&degree=&companyType=&companySize=&jobType="
        "&issueDate=&sortType=0&pageNum=1&requestId=&pageSize=20&source=1"
        "&accountId=&pageCode=sou%7Csou%7Csoulb"
    )
    assert compute_sign(relative_url) == "38c25d37c9fda77b493c4afa95f95b38103a4439bdd7298b3b7525b5df544fc6"


def test_original_team_fixture_is_still_parseable_without_live_requests():
    payload = json.loads((ROOT / "integrations/jd-crawler/tests/fixtures/job51_search_response.json").read_text(encoding="utf-8"))
    rows, total = parse_job51_payload(payload, keyword="Python", search_city="上海", search_page=1)
    assert total == 1234 and len(rows) == 2
    assert rows[0]["source_id"] == "156789012"
