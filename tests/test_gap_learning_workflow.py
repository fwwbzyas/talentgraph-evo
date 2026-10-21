from fastapi.testclient import TestClient

from agents.data.service import DataAgent
from agents.data.normalization import extract_skills
from agents.learning.models import CourseDocument
from agents.learning.service import CourseRagService
from apps.api import main as api_main
from contracts import CandidateProfile, ImportRequest
from core.auth import AuthService
from core.sample_data import generate_demo_jds
from core.store import AppStore


def _login(client: TestClient, role: str) -> tuple[dict, dict]:
    email = "hr@talentgraph.cn" if role == "enterprise" else "candidate@talentgraph.cn"
    response = client.post("/api/auth/login", json={"email": email, "password": "talentgraph2026", "role": role})
    assert response.status_code == 200
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]


def _profile(candidate_id: str) -> CandidateProfile:
    return CandidateProfile(
        candidate_id=candidate_id,
        target_job_id="",
        name="测试候选人",
        skills=[{"name": "Python", "level": "intermediate", "confidence": 0.9, "evidence": "项目中使用 Python"}],
        projects=[{"name": "智能问答", "description": "Python 服务开发"}],
        evidence=[{"type": "resume", "content": "Python 项目", "confidence": 0.9}],
        confidence=0.85,
        provider_status={"mode": "llm_resume_understanding", "fallback": False},
    )


def test_gap_analysis_and_course_route_are_persisted(tmp_path, monkeypatch):
    database = tmp_path / "talentgraph.db"
    local_store = AppStore(str(database))
    local_store.index_batch(DataAgent().run(ImportRequest(batch_name="gap", items=generate_demo_jds())))
    learning = CourseRagService(database)
    learning.sync_jobs()
    learning.store.upsert_course(CourseDocument(
        course_id="course_python", source="官方免费课程", title="Python 入门", url="https://docs.python.org/zh-cn/3/tutorial/",
        summary="Python 官方教程", instructor="Python", quality_score=95, difficulty="入门", skills=["Python"], content="Python 基础",
    ))
    monkeypatch.setattr(api_main, "store", local_store)
    monkeypatch.setattr(api_main, "auth_service", AuthService(str(database)))
    monkeypatch.setattr(api_main, "learning_service", learning)
    client = TestClient(api_main.app)

    seeker_headers, seeker = _login(client, "seeker")
    local_store.save_candidate_profile(_profile("candidate_gap_test"), seeker)
    target = next(
        job for job in local_store.jobs.values()
        if job.job_status == "active" and len(extract_skills(job.content, job.skill_tags)) >= 3
    )
    target_result = client.post("/api/gap-analysis", headers=seeker_headers, json={"candidate_id": "candidate_gap_test", "target_job_id": target.source_id})
    assert target_result.status_code == 200
    assert target_result.json()["results"][0]["job_id"] == target.source_id
    result = target_result.json()["results"][0]
    assert result["source_url"] == target.source_url
    assert result["job_evidence"]["source_id"] == target.source_id
    assert target_result.json()["data_policy"] == "real_recruitment_evidence_only"

    all_result = client.post("/api/gap-analysis", headers=seeker_headers, json={"candidate_id": "candidate_gap_test", "analyze_all": True})
    assert all_result.status_code == 200
    assert len(all_result.json()["top_matches"]) <= 5
    assert all_result.json()["evaluated_job_count"] >= len(all_result.json()["top_matches"])

    analysis = all_result.json()
    selected_jobs = [item for item in analysis["results"] if item["gaps"]]
    assert len(selected_jobs) >= 2
    selected = selected_jobs[1]
    route = client.post("/api/learning/routes", headers=seeker_headers, json={"analysis_id": analysis["analysis_id"], "job_id": selected["job_id"]})
    assert route.status_code == 200
    assert route.json()["steps"]
    assert route.json()["job_id"] == str(selected["job_id"])
    assert route.json()["job_title"] == selected["title"]
    restored = client.get(f"/api/learning/routes/latest/{analysis['analysis_id']}", headers=seeker_headers)
    assert restored.status_code == 200
    assert restored.json()["route_id"] == route.json()["route_id"]

    unknown = client.post(
        "/api/learning/routes",
        headers=seeker_headers,
        json={"analysis_id": analysis["analysis_id"], "job_id": "unknown-job-id"},
    )
    assert unknown.status_code == 422
    assert "不存在岗位 ID" in unknown.json()["detail"]


def test_enterprise_gap_analysis_is_limited_to_its_active_jobs(tmp_path, monkeypatch):
    database = tmp_path / "enterprise.db"
    local_store = AppStore(str(database))
    monkeypatch.setattr(api_main, "store", local_store)
    monkeypatch.setattr(api_main, "auth_service", AuthService(str(database)))
    monkeypatch.setattr(api_main, "learning_service", CourseRagService(database))
    client = TestClient(api_main.app)
    headers, user = _login(client, "enterprise")
    created = client.post("/api/enterprise-jobs", headers=headers, json={
        "title": "AI应用工程师", "domain": "人工智能", "city": "杭州", "headcount": 2,
        "responsibilities": ["负责企业RAG应用开发与评测"],
        "required_skills": ["Python", "RAG", "FastAPI"], "preferred_skills": ["Docker"], "status": "active",
    })
    assert created.status_code == 201
    jobs = client.get("/api/enterprise-jobs", headers=headers).json()["items"]
    local_store.save_candidate_profile(_profile("candidate_enterprise_test"), user)

    response = client.post("/api/gap-analysis", headers=headers, json={"candidate_id": "candidate_enterprise_test", "analyze_all": True})
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "enterprise_all_active"
    assert body["evaluated_job_count"] == len([job for job in jobs if job["status"] == "active"])
    assert all(item["source"] == "enterprise" for item in body["results"])
    assert body["results"][0]["interview_questions"]


def test_gap_analysis_rejects_local_resume_fallback(tmp_path, monkeypatch):
    database = tmp_path / "fallback.db"
    local_store = AppStore(str(database))
    local_store.index_batch(DataAgent().run(ImportRequest(batch_name="gap", items=generate_demo_jds())))
    monkeypatch.setattr(api_main, "store", local_store)
    monkeypatch.setattr(api_main, "auth_service", AuthService(str(database)))
    client = TestClient(api_main.app)
    headers, user = _login(client, "seeker")
    profile = _profile("candidate_fallback")
    profile.provider_status = {"mode": "deterministic_fallback", "fallback": True}
    local_store.save_candidate_profile(profile, user)
    target = next(job for job in local_store.jobs.values() if job.job_status == "active")

    response = client.post(
        "/api/gap-analysis",
        headers=headers,
        json={"candidate_id": profile.candidate_id, "target_job_id": target.source_id},
    )

    assert response.status_code == 409
    assert "大模型语义解析" in response.json()["detail"]


def test_gap_analysis_allows_completed_assessment_record_for_local_profile(tmp_path, monkeypatch):
    database = tmp_path / "completed-assessment.db"
    local_store = AppStore(str(database))
    local_store.index_batch(DataAgent().run(ImportRequest(batch_name="gap", items=generate_demo_jds())))
    monkeypatch.setattr(api_main, "store", local_store)
    monkeypatch.setattr(api_main, "auth_service", AuthService(str(database)))
    client = TestClient(api_main.app)
    headers, user = _login(client, "seeker")
    target = next(job for job in local_store.jobs.values() if job.job_status == "active")

    profile = _profile("candidate_completed_assessment")
    profile.provider_status = {"mode": "local_evidence_fallback", "fallback": True}
    local_store.save_candidate_profile(profile, user)
    local_store.save_assessment_record(
        {
            "id": "record_completed_assessment",
            "candidate_id": profile.candidate_id,
            "status": "已出报告",
            "profile": {"candidate_id": profile.candidate_id, "match_report": {"report_id": "report_1"}},
        },
        user,
    )

    response = client.post(
        "/api/gap-analysis",
        headers=headers,
        json={"candidate_id": profile.candidate_id, "target_job_id": target.source_id},
    )

    assert response.status_code == 200

    assessed_profile = _profile("candidate_completed_personal_assessment")
    assessed_profile.provider_status = {"mode": "local_evidence_fallback", "fallback": True}
    local_store.save_candidate_profile(assessed_profile, user)
    local_store.save_assessment_record(
        {
            "id": "record_personal_assessment",
            "candidate_id": assessed_profile.candidate_id,
            "status": "已生成画像",
            "profile": {
                "candidate_id": assessed_profile.candidate_id,
                "competency_dimensions": [{"name": "工程实践", "score": 82}],
            },
        },
        user,
    )
    assessed_response = client.post(
        "/api/gap-analysis",
        headers=headers,
        json={"candidate_id": assessed_profile.candidate_id, "target_job_id": target.source_id},
    )

    assert assessed_response.status_code == 200

    status_only_profile = _profile("candidate_status_only")
    status_only_profile.provider_status = {"mode": "local_evidence_fallback", "fallback": True}
    local_store.save_candidate_profile(status_only_profile, user)
    local_store.save_assessment_record(
        {
            "id": "record_status_only",
            "candidate_id": status_only_profile.candidate_id,
            "status": "已出报告",
            "profile": {"candidate_id": status_only_profile.candidate_id},
        },
        user,
    )
    status_only_response = client.post(
        "/api/gap-analysis",
        headers=headers,
        json={"candidate_id": status_only_profile.candidate_id, "target_job_id": target.source_id},
    )

    assert status_only_response.status_code == 409
