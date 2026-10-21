import pytest
from fastapi.testclient import TestClient

from agents.assessment.service import AssessmentAgent
from agents.assessment.resume_files import ResumeFileError
from agents.assessment.resume_parser import ResumeParseError
from agents.data.service import DataAgent
from agents.evolution.service import EvolutionAgent
from agents.job_graph.service import JobGraphAgent
from agents.match.service import MatchAgent
from apps.api import main as api_main
from apps.api.main import app
from contracts import AssessmentAnswer, ImportRequest
from core.auth import AuthService
from core.store import AppStore
from core.sample_data import generate_demo_jds


def enterprise_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={
            "email": "hr@talentgraph.cn",
            "password": "talentgraph2026",
            "role": "enterprise",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_demo_jobs_have_recruitment_site_fields_and_daily_changes():
    batch = DataAgent().run(ImportRequest(batch_name="rich_jobs", items=generate_demo_jds()))
    job = batch.items[0]

    assert job.company and job.company_industry and job.company_size
    assert job.salary_min_k < job.salary_max_k
    assert job.city and job.district
    assert job.experience_min_years <= job.experience_max_years
    assert len(job.skill_tags) >= 6
    assert len(job.responsibilities) >= 3
    assert len(job.benefits) >= 5
    assert job.published_at and job.source_url.startswith("https://")
    assert batch.quality_summary["today_changes"] == {"new": 6, "updated": 6, "offline": 6}


def test_store_filters_jobs_and_exposes_changes():
    batch = DataAgent().run(ImportRequest(batch_name="index", items=generate_demo_jds()))
    local_store = AppStore()
    local_store.index_batch(batch)

    beijing_java = local_store.list_jobs(city="北京", keyword="Java")
    assert beijing_java
    assert all(job.city == "北京" and "Java" in job.title for job in beijing_java)
    assert len(local_store.today_changes()) == 18


def test_graph_contains_complete_semantic_layers_and_evolution_diff():
    batch = DataAgent().run(ImportRequest(batch_name="graph", items=generate_demo_jds()))
    graph = JobGraphAgent().run(batch, "Java 后端工程师")
    evolution = EvolutionAgent().run(graph)

    node_types = {node["type"] for node in graph.graph_nodes}
    assert {"job", "capability_domain", "skill", "tool", "responsibility", "scenario", "evidence"} <= node_types
    assert graph.capability_domains and graph.tools
    assert graph.evidence_summary["source_count"] > 0
    assert any(edge["label"] == "enables" for edge in graph.graph_edges)
    assert any(edge["label"] == "validated_by" for edge in graph.graph_edges)
    assert evolution.compared_versions == {"baseline": "2024Q4", "current": "2026Q3"}
    assert all("change_score" in change and "from" in change and "to" in change for change in evolution.changes)
    assert evolution.summary["headline"]


def test_candidate_profile_and_match_report_are_explainable():
    batch = DataAgent().run(ImportRequest(batch_name="match", items=generate_demo_jds()))
    graph = JobGraphAgent().run(batch, "Java 后端工程师")
    assessment = AssessmentAgent()
    resume = """
    陈工，计算机科学本科，3 年 Java 后端开发经验。
    熟悉 Java、Spring Boot、MySQL、Redis、Kafka 和 Docker。
    项目经历：负责电商订单服务的微服务拆分、慢 SQL 优化与线上故障排查。
    """
    session = assessment.start("candidate_rich", graph.job_id, resume)
    for answer in ("负责订单服务", "先看监控、日志和慢 SQL", "先止损再回滚"):
        session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer=answer))
    profile = assessment.finalize(session).candidate_profile
    report = MatchAgent().run(graph, profile)

    assert profile.experience_years == 3
    assert profile.skill_scores["Java"] >= 45
    assert {item["name"] for item in profile.competency_dimensions} == {"专业技术", "工程实践", "问题解决", "行为素质"}
    assert set(report.score_breakdown) == {"required_skills", "preferred_skills", "evidence_quality", "behavior_competency"}
    assert report.matched_skills and 0 <= report.evidence_coverage <= 1
    assert report.interview_recommendation


def test_jobs_api_keeps_import_compatible_and_adds_queries():
    client = TestClient(app)
    headers = enterprise_headers(client)
    imported = client.post("/api/data/import", json={"batch_name": "api_rich", "items": generate_demo_jds()}, headers=headers)
    assert imported.status_code == 200
    assert len(imported.json()["items"]) == 100

    jobs = client.get("/api/jobs", params={"city": "北京", "limit": 5})
    changes = client.get("/api/jobs/changes/today")
    assert jobs.status_code == 200 and jobs.json()["items"]
    assert all(item["city"] == "北京" for item in jobs.json()["items"])
    assert changes.status_code == 200
    assert all(changes.json()["summary"][kind] >= 6 for kind in ("new", "updated", "offline"))


def test_enterprise_job_template_is_public():
    response = TestClient(app).get("/api/enterprise-jobs/template")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "enterprise-job-template.xlsx" in response.headers["content-disposition"]


def test_candidate_profile_api_returns_404_for_unknown_candidate():
    response = TestClient(app).get("/api/candidates/not_found/profile")
    assert response.status_code == 404
    assert response.json()["detail"] == "candidate profile not found"


def test_job_asset_crud_and_domain_guard():
    client = TestClient(app)
    headers = enterprise_headers(client)
    payload = {
        "source_id": "crud_iot_architect",
        "title": "物联网解决方案架构师",
        "domain": "物联网",
        "company": "星云科技",
        "city": "上海",
        "salary_min_k": 35,
        "salary_max_k": 55,
        "skill_tags": ["MQTT", "边缘计算", "设备安全"],
        "responsibilities": ["设计端云协同架构", "建设设备接入与安全体系"],
    }

    created = client.post("/api/jobs", json=payload, headers=headers)
    assert created.status_code == 201
    assert client.get("/api/jobs/crud_iot_architect").json()["domain"] == "物联网"

    updated = client.patch(
        "/api/jobs/crud_iot_architect",
        json={"salary_max_k": 60, "job_status": "offline"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["salary_max_k"] == 60
    assert updated.json()["job_status"] == "offline"
    assert updated.json()["change_type"] == "updated"

    invalid = client.post("/api/jobs", json={**payload, "source_id": "invalid_domain", "domain": "金融"}, headers=headers)
    assert invalid.status_code == 422

    deleted = client.delete("/api/jobs/crud_iot_architect", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/jobs/crud_iot_architect").status_code == 404


def test_resume_remote_parse_retries_local_evidence_with_provider_metadata(monkeypatch):
    parser = api_main.orchestrator.assessment_agent.resume_parser
    calls = []

    def parse(_resume_text, **kwargs):
        calls.append(kwargs)
        if kwargs["use_remote"]:
            raise ResumeParseError("HTTPStatusError: 403 Forbidden from provider\n" + "x" * 400)
        return {"provider_status": {"mode": "deterministic_fallback"}, "skills": []}

    monkeypatch.setattr(parser, "parse", parse)

    result = api_main._parse_resume_with_local_fallback(
        "Skills: Python",
        candidate_id="candidate_fallback_api",
        source_name="resume.txt",
    )

    assert len(calls) == 2
    assert calls[0]["require_remote"] is True and calls[0]["use_remote"] is True
    assert calls[1]["require_remote"] is False and calls[1]["use_remote"] is False
    assert result["provider_status"]["fallback"] is True
    assert result["provider_status"]["mode"] == "local_evidence_fallback"
    assert "403 Forbidden" in result["provider_status"]["remote_error"]
    assert len(result["provider_status"]["remote_error"]) <= 240


def test_resume_fallback_does_not_swallow_non_parse_errors(monkeypatch):
    parser = api_main.orchestrator.assessment_agent.resume_parser

    def parse(_resume_text, **kwargs):
        raise ValueError("unexpected parser failure")

    monkeypatch.setattr(parser, "parse", parse)

    with pytest.raises(ValueError, match="unexpected parser failure"):
        api_main._parse_resume_with_local_fallback("Skills: Python")


def test_recruitment_candidate_upload_uses_local_fallback_after_remote_403(tmp_path, monkeypatch):
    database = tmp_path / "recruitment.db"
    monkeypatch.setattr(api_main, "store", AppStore(str(database)))
    monkeypatch.setattr(api_main, "auth_service", AuthService(str(database)))
    client = TestClient(api_main.app)
    headers = enterprise_headers(client)

    job = client.post(
        "/api/enterprise-jobs",
        headers=headers,
        json={
            "title": "AI 应用工程师",
            "domain": "人工智能",
            "city": "杭州",
            "required_skills": ["Python", "FastAPI"],
            "responsibilities": ["负责企业应用开发"],
        },
    )
    assert job.status_code == 201

    parser = api_main.orchestrator.assessment_agent.resume_parser
    real_parse = parser.parse
    calls = []

    def fail_remote_then_parse_locally(resume_text, **kwargs):
        calls.append(kwargs)
        if kwargs["use_remote"]:
            raise ResumeParseError("HTTPStatusError: 403 Forbidden")
        return real_parse(resume_text, **kwargs)

    monkeypatch.setattr(parser, "parse", fail_remote_then_parse_locally)
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((80, 80), "Skills: Python, FastAPI")
    page.insert_text((80, 110), "Project: Enterprise platform")
    page.insert_text((80, 140), "Experience: 3 years, Education: Bachelor")
    response = client.post(
        "/api/recruitment/candidates/upload",
        headers=headers,
        data={"target_job_id": job.json()["job_id"]},
        files={
            "files": (
                "陆赞_个人简历.pdf",
                pdf.tobytes(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["errors"] == []
    assert body["items"][0]["name"] == "陆赞"
    assert body["items"][0]["profile"]["name"] == "陆赞"
    assert api_main.store.profiles[body["items"][0]["candidate_id"]].name == "陆赞"
    status = body["items"][0]["resume_parse"]["provider_status"]
    assert status["fallback"] is True
    assert status["mode"] == "local_evidence_fallback"
    assert "403" in status["remote_error"]
    assert len(calls) == 2


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("陈艾琳.pdf", "陈艾琳"),
        ("陆赞_个人简历.pdf", "陆赞"),
        ("王强-简历.pdf", "王强"),
        ("resume.pdf", None),
        ("candidate.pdf", None),
        ("简历.pdf", None),
        ("2026.pdf", None),
    ],
)
def test_resume_filename_display_name_is_conservative(filename, expected):
    assert api_main._resume_filename_display_name(filename) == expected


def test_assessment_upload_keeps_file_extraction_errors_as_422(tmp_path, monkeypatch):
    database = tmp_path / "resume-file-error.db"
    monkeypatch.setattr(api_main, "store", AppStore(str(database)))
    monkeypatch.setattr(api_main, "auth_service", AuthService(str(database)))

    def fail_extraction(_filename, _content):
        raise ResumeFileError("invalid resume file")

    monkeypatch.setattr(api_main, "extract_resume_text", fail_extraction)
    client = TestClient(api_main.app)
    headers = enterprise_headers(client)
    response = client.post(
        "/api/assessment/upload-resume",
        headers=headers,
        files={"file": ("resume.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid resume file"


def test_enterprise_job_put_preserves_identity_and_scopes_organization(tmp_path, monkeypatch):
    database = tmp_path / "enterprise-jobs.db"
    monkeypatch.setattr(api_main, "store", AppStore(str(database)))
    auth = AuthService(str(database))
    monkeypatch.setattr(api_main, "auth_service", auth)
    client = TestClient(api_main.app)
    headers = enterprise_headers(client)

    created = client.post(
        "/api/enterprise-jobs",
        headers=headers,
        json={
            "title": "AI 应用工程师",
            "domain": "人工智能",
            "city": "杭州",
            "headcount": 2,
            "required_skills": ["Python"],
            "status": "active",
        },
    )
    assert created.status_code == 201
    original = created.json()
    update_payload = {
        "title": "高级 AI 应用工程师",
        "domain": "智能系统",
        "city": "上海",
        "headcount": 3,
        "required_skills": ["Python", "RAG"],
        "preferred_skills": ["Docker"],
        "status": "paused",
    }

    updated = client.put(
        f"/api/enterprise-jobs/{original['job_id']}",
        headers=headers,
        json=update_payload,
    )

    assert updated.status_code == 200
    assert updated.json()["job_id"] == original["job_id"]
    assert updated.json()["organization_id"] == original["organization_id"]
    assert updated.json()["title"] == update_payload["title"]
    assert updated.json()["status"] == "paused"

    assert client.put(
        f"/api/enterprise-jobs/{original['job_id']}",
        headers=headers,
        json={**update_payload, "domain": "金融"},
    ).status_code == 422
    assert client.put(
        f"/api/enterprise-jobs/{original['job_id']}",
        headers=headers,
        json={**update_payload, "status": "draft"},
    ).status_code == 422
    assert client.put(
        "/api/enterprise-jobs/missing-job",
        headers=headers,
        json=update_payload,
    ).status_code == 404

    auth.register(
        email="other-enterprise@example.com",
        password="password-123",
        role="enterprise",
        display_name="另一家企业",
    )
    other_login = client.post(
        "/api/auth/login",
        json={
            "email": "other-enterprise@example.com",
            "password": "password-123",
            "role": "enterprise",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    cross_org = client.put(
        f"/api/enterprise-jobs/{original['job_id']}",
        headers=other_headers,
        json=update_payload,
    )
    assert cross_org.status_code == 404

    seeker_login = client.post(
        "/api/auth/login",
        json={
            "email": "candidate@talentgraph.cn",
            "password": "talentgraph2026",
            "role": "seeker",
        },
    )
    seeker_response = client.put(
        f"/api/enterprise-jobs/{original['job_id']}",
        headers={"Authorization": f"Bearer {seeker_login.json()['access_token']}"},
        json=update_payload,
    )
    assert seeker_response.status_code == 403
