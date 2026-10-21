from __future__ import annotations

from datetime import UTC, datetime

import httpx

from agents.data.sources import AuthorizedRecruitmentSource, default_sources, source_catalog
from agents.data.source_policy import (
    CORE_RECRUITMENT_SOURCE_IDS,
    RECRUITMENT_SOURCE_IDS,
    SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS,
)
from contracts import DataCollectionRequest


def test_authorized_source_is_disabled_without_feed_configuration(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_BOSS_FEED_URL", raising=False)
    source = AuthorizedRecruitmentSource("boss", "BOSS直聘")

    assert source.enabled is False
    assert source.access_mode == "authorization_required"


def test_authorized_source_maps_partner_feed_to_canonical_schema(monkeypatch):
    monkeypatch.setenv("TALENTGRAPH_ZHAOPIN_FEED_URL", "https://partner.example/jobs")
    monkeypatch.setenv("TALENTGRAPH_ZHAOPIN_FEED_TOKEN", "test-token")
    published = datetime.now(UTC).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.url.params["limit"] == "20"
        return httpx.Response(200, json={"data": {"records": [{
            "jobId": "zl-1001",
            "jobName": "大模型应用工程师",
            "companyName": "星云智能",
            "jobDescription": "负责 RAG、LLM Agent 与 Python 服务工程化落地。" * 12,
            "cityName": "北京",
            "districtName": "海淀区",
            "salaryMin": 25,
            "salaryMax": 45,
            "degreeName": "本科",
            "experienceName": "3-5年",
            "skillTags": ["Python", "RAG", "LLM"],
            "jobUrl": "https://partner.example/jobs/zl-1001",
            "publishTime": published,
        }]}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = AuthorizedRecruitmentSource("zhaopin", "智联招聘", client)
    rows = source.fetch(max_items=20, lookback_hours=24)

    assert source.enabled is True and source.access_mode == "authorized_feed"
    assert rows[0]["source_id"] == "zl-1001"
    assert rows[0]["source_platform"] == "zhaopin"
    assert rows[0]["title"] == "大模型应用工程师"
    assert rows[0]["company"] == "星云智能"
    assert rows[0]["tags"] == ["Python", "RAG", "LLM"]
    assert rows[0]["metadata"]["authorized_feed"] is True


def test_recruitment_catalog_includes_core_and_supplemental_sources(monkeypatch):
    for source_id in ("BOSS", "ZHAOPIN", "LIEPIN"):
        monkeypatch.delenv(f"TALENTGRAPH_{source_id}_FEED_URL", raising=False)
    catalog = {item["source_id"]: item for item in source_catalog(default_sources())}

    recruitment = {source_id for source_id, item in catalog.items() if item["source_category"] == "recruitment"}
    assert recruitment == set(RECRUITMENT_SOURCE_IDS)
    assert set(CORE_RECRUITMENT_SOURCE_IDS) == {"boss", "zhaopin"}
    assert set(SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS) == {"51job", "liepin"}


def test_supplemental_sources_do_not_change_current_ad_hoc_default_collection(monkeypatch):
    monkeypatch.setenv("TALENTGRAPH_LIEPIN_FEED_URL", "https://partner.example/liepin/jobs")

    assert not set(SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS) & set(DataCollectionRequest().source_ids)
