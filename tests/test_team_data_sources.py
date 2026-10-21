from datetime import UTC, datetime

import httpx

from agents.data.normalization import normalize_community_signal
from agents.data.sources import GitHubSource, default_sources, source_catalog
from agents.data.zhaopin_browser import _canonical_job_url, _job_id, _parse_salary
from contracts import DataCollectionRequest


def test_github_repository_is_mapped_as_auxiliary_signal():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/repositories"
        return httpx.Response(200, json={"items": [{
            "id": 101,
            "full_name": "example/agent-platform",
            "name": "agent-platform",
            "description": "Production LLM agent and RAG evaluation platform for AI engineers.",
            "html_url": "https://github.com/example/agent-platform",
            "language": "Python",
            "topics": ["llm", "rag", "ai-agent"],
            "stargazers_count": 1200,
            "forks_count": 120,
            "watchers_count": 1200,
            "open_issues_count": 8,
            "updated_at": datetime.now(UTC).isoformat(),
            "archived": False,
            "fork": False,
            "owner": {"login": "example"},
            "license": {"spdx_id": "Apache-2.0"},
            "default_branch": "main",
        }]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rows = GitHubSource(client).fetch(max_items=1, lookback_hours=24 * 7)
    normalized, issues = normalize_community_signal(rows[0])

    assert issues == []
    assert normalized is not None
    assert normalized["source_platform"] == "github"
    assert normalized["source_type"] == "developer_community"
    assert normalized["metadata"]["auxiliary_only"] is True
    assert normalized["metadata"]["evidence_role"] == "auxiliary"
    assert normalized["metadata"]["evidence_weight"] == 0.25


def test_zhaopin_helpers_map_stable_source_identity_and_salary():
    url = _canonical_job_url(
        "http://www.zhaopin.com/jobdetail/CC529523026J90250037000.htm?refcode=4019"
    )

    assert url == "https://www.zhaopin.com/jobdetail/CC529523026J90250037000.htm"
    assert _job_id(url) == "CC529523026J90250037000"
    assert _parse_salary("1.5-2万·13薪") == (2, 2, 13)
    assert _parse_salary("6000-8000元") == (6, 8, 12)


def test_team_sources_join_default_catalog_without_changing_evidence_roles(monkeypatch):
    monkeypatch.setenv("TALENTGRAPH_ZHAOPIN_BROWSER_ENABLED", "1")
    catalog = {item["source_id"]: item for item in source_catalog(default_sources())}
    request = DataCollectionRequest()

    assert catalog["zhaopin"]["source_category"] == "recruitment"
    assert catalog["github"]["source_category"] == "community_signal"
    assert catalog["remoteok"]["source_category"] == "community_signal"
    assert catalog["arbeitnow"]["source_category"] == "community_signal"
    assert {"zhaopin", "github"} <= set(request.source_ids)
