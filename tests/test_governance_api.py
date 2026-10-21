from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)
login = client.post(
    "/api/auth/login",
    json={
        "email": "hr@talentgraph.cn",
        "password": "talentgraph2026",
        "role": "enterprise",
    },
)
ENTERPRISE_HEADERS = {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_governance_audit_api_exposes_process_and_summaries():
    response = client.get("/api/data/audits", params={"limit": 3}, headers=ENTERPRISE_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert {"total", "type_summary", "status_summary", "lane_summary", "items"} <= payload.keys()
    assert len(payload["items"]) <= 3
    assert set(payload["lane_summary"]) == {
        "pending", "rejected", "corrections", "copies", "changes",
    }


def test_governance_audit_api_pages_each_lane_independently():
    response = client.get(
        "/api/data/audits",
        params={"lane": "corrections", "limit": 5},
        headers=ENTERPRISE_HEADERS,
    )

    assert response.status_code == 200
    assert all(
        item["record_type"] == "field_correction"
        for item in response.json()["items"]
    )


def test_graph_hierarchy_api_is_progressive_and_evidence_backed():
    overview = client.get("/api/graph/overview")

    assert overview.status_code == 200
    payload = overview.json()
    assert payload["parent"] is None
    assert all(node["type"] == "domain" for node in payload["children"])
    if payload["children"]:
        child = client.get("/api/graph/children", params={"parent_id": payload["children"][0]["id"]})
        assert child.status_code == 200
        child_payload = child.json()
        assert child_payload["parent"]["id"] == payload["children"][0]["id"]
        assert child_payload["path"]


def test_trend_api_keeps_community_evidence_auxiliary():
    response = client.get("/api/signals/technology-trends", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_policy"]["community_signal"] == "auxiliary_only"
    assert all(
        item["can_publish_ability"] or item["evidence_role"] == "auxiliary_only"
        for item in payload["items"]
    )


def test_temporal_graph_marks_auxiliary_signals_as_non_publishable():
    response = client.get("/api/graph/temporal", params={"max_nodes": 100})

    assert response.status_code == 200
    signals = [node for node in response.json()["nodes"] if node["nodeType"] == "signal"]
    assert all(node["evidenceRole"] == "auxiliary_only" and not node["canPublishAbility"] for node in signals)
