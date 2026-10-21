from io import BytesIO
import json
import sqlite3
from types import SimpleNamespace
from zipfile import ZipFile

from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfReader

from agents.assessment import resume_files
from agents.evolution.service import EvolutionAgent
from agents.match.report_export import export_match_report
from apps.api import main as api_main
from contracts import CandidateProfile, MatchReport
from core.store import AppStore


app = api_main.app


def test_market_evolution_uses_persisted_versions():
    jobs = [SimpleNamespace(source_platform="zhaopin")]
    versions = [
        {
            "job_id": "zhaopin:1",
            "version_number": 1,
            "changed_at": "2026-07-20T09:00:00+00:00",
            "changes": {"baseline": {"before": None, "after": True}},
            "snapshot": {
                "source_platform": "zhaopin",
                "title": "AI 工程师",
                "company": "测试企业",
                "job_status": "active",
                "skill_tags": ["Python", "RAG"],
            },
        },
        {
            "job_id": "zhaopin:1",
            "version_number": 2,
            "changed_at": "2026-07-23T09:00:00+00:00",
            "changes": {"skill_tags": {"before": ["Python", "RAG"], "after": ["Python", "RAG", "LangGraph"]}},
            "snapshot": {
                "source_platform": "zhaopin",
                "title": "AI 工程师",
                "company": "测试企业",
                "job_status": "active",
                "skill_tags": ["Python", "RAG", "LangGraph"],
            },
        },
    ]

    result = EvolutionAgent().analyze_market(jobs, versions)

    assert result["summary"]["changed_jobs"] == 1
    assert result["frames"][-1]["updated_jobs"] == 1
    assert any(change[0] == "LangGraph" and change[3] == "new" for change in result["frames"][-1]["changes"])


def test_market_evolution_excludes_new_baselines_from_period_comparison():
    jobs = [SimpleNamespace(source_platform="zhaopin") for _ in range(2)]
    versions = [
        {
            "job_id": "zhaopin:1", "version_number": 1,
            "changed_at": "2026-07-20T09:00:00+00:00",
            "changes": {"baseline": {"before": None, "after": True}},
            "snapshot": {
                "source_platform": "zhaopin", "title": "AI 工程师", "company": "甲公司",
                "job_status": "active", "skill_tags": ["Python"], "source_url": "https://example.com/1",
            },
        },
        {
            "job_id": "zhaopin:1", "version_number": 2,
            "changed_at": "2026-07-21T09:00:00+00:00",
            "changes": {"skill_tags": {"before": ["Python"], "after": ["Python", "RAG"]}},
            "snapshot": {
                "source_platform": "zhaopin", "title": "AI 工程师", "company": "甲公司",
                "job_status": "active", "skill_tags": ["Python", "RAG"], "source_url": "https://example.com/1",
            },
        },
        {
            "job_id": "zhaopin:2", "version_number": 1,
            "changed_at": "2026-07-21T10:00:00+00:00",
            "changes": {"baseline": {"before": None, "after": True}},
            "snapshot": {
                "source_platform": "zhaopin", "title": "算法工程师", "company": "乙公司",
                "job_status": "active", "skill_tags": ["C++"], "source_url": "https://example.com/2",
            },
        },
    ]

    result = EvolutionAgent().analyze_market(jobs, versions)
    frame = result["frames"][-1]
    rag = next(change for change in frame["changes"] if change[0] == "RAG")

    assert frame["comparison_job_count"] == 1
    assert rag[1:5] == [0.0, 100.0, "new", 1]
    assert rag[5]["denominator"] == 1
    assert rag[5]["added_evidence"][0]["source_url"] == "https://example.com/1"


def test_job_version_comparison_returns_before_after_and_skill_diffs(tmp_path):
    local_store = AppStore(db_path=tmp_path / "versions.db")
    with sqlite3.connect(local_store.db_path) as connection:
        connection.execute(
            "INSERT INTO job_versions (version_id, job_id, version_number, changed_at, payload) VALUES (?, ?, ?, ?, ?)",
            (
                "job:1:v1", "job:1", 1, "2026-07-20T09:00:00+00:00",
                '{"version_id":"job:1:v1","job_id":"job:1","version_number":1,"changed_at":"2026-07-20T09:00:00+00:00","changes":{"created":{"before":null,"after":true}},"snapshot":{"title":"AI 工程师","company":"测试企业","skill_tags":["Python","RAG"],"responsibilities":["开发模型服务"],"source_url":"https://example.com/1"}}',
            ),
        )
        connection.execute(
            "INSERT INTO job_versions (version_id, job_id, version_number, changed_at, payload) VALUES (?, ?, ?, ?, ?)",
            (
                "job:1:v2", "job:1", 2, "2026-07-23T09:00:00+00:00",
                '{"version_id":"job:1:v2","job_id":"job:1","version_number":2,"changed_at":"2026-07-23T09:00:00+00:00","changes":{"skill_tags":{"before":["Python","RAG"],"after":["Python","LangGraph"]},"responsibilities":{"before":["开发模型服务"],"after":["开发 Agent 平台"]}},"snapshot":{"title":"AI 工程师","company":"测试企业","skill_tags":["Python","LangGraph"],"responsibilities":["开发 Agent 平台"],"source_url":"https://example.com/1"}}',
            ),
        )

    result = local_store.compare_job_version("job:1", 2)

    assert result is not None
    assert result["base_version_number"] == 1
    assert result["previous_version_number"] == 1
    assert result["before"]["responsibilities"] == ["开发模型服务"]
    assert result["after"]["responsibilities"] == ["开发 Agent 平台"]
    assert result["skill_diffs"]["added"] == ["LangGraph"]
    assert result["skill_diffs"]["removed"] == ["RAG"]
    assert {item["field"] for item in result["field_diffs"]} == {"skill_tags", "responsibilities"}


def test_job_version_comparison_supports_explicit_historical_base(tmp_path, monkeypatch):
    local_store = AppStore(db_path=tmp_path / "historical-versions.db")
    snapshots = {
        1: {
            "title": "AI 工程师",
            "company": "测试企业",
            "salary_min_k": 20,
            "skill_tags": ["Python", "RAG"],
            "responsibilities": ["开发模型服务"],
        },
        2: {
            "title": "AI 工程师",
            "company": "测试企业",
            "salary_min_k": 25,
            "skill_tags": ["Python", "RAG", "LangGraph"],
            "responsibilities": ["开发 Agent 平台"],
        },
        3: {
            "title": "AI Agent 工程师",
            "company": "新测试企业",
            "salary_min_k": 30,
            "skill_tags": ["Python", "LangGraph"],
            "responsibilities": ["开发 Agent 平台", "建设评测体系"],
        },
    }
    changes = {
        1: {"created": {"before": None, "after": True}},
        2: {
            "salary_min_k": {"before": 20, "after": 25},
            "skill_tags": {"before": ["Python", "RAG"], "after": ["Python", "RAG", "LangGraph"]},
            "responsibilities": {"before": ["开发模型服务"], "after": ["开发 Agent 平台"]},
        },
        3: {
            "title": {"before": "AI 工程师", "after": "AI Agent 工程师"},
            "company": {"before": "测试企业", "after": "新测试企业"},
            "salary_min_k": {"before": 25, "after": 30},
            "skill_tags": {"before": ["Python", "RAG", "LangGraph"], "after": ["Python", "LangGraph"]},
            "responsibilities": {"before": ["开发 Agent 平台"], "after": ["开发 Agent 平台", "建设评测体系"]},
        },
    }
    with sqlite3.connect(local_store.db_path) as connection:
        for version_number in (1, 2, 3):
            payload = {
                "version_id": f"job:1:v{version_number}",
                "job_id": "job:1",
                "version_number": version_number,
                "changed_at": f"2026-07-{20 + version_number:02d}T09:00:00+00:00",
                "changes": changes[version_number],
                "snapshot": snapshots[version_number],
            }
            connection.execute(
                "INSERT INTO job_versions (version_id, job_id, version_number, changed_at, payload) VALUES (?, ?, ?, ?, ?)",
                (payload["version_id"], "job:1", version_number, payload["changed_at"], json.dumps(payload, ensure_ascii=False)),
            )

    result = local_store.compare_job_version("job:1", 3, base_version_number=1)

    assert result is not None
    assert result["base_version_number"] == 1
    assert result["previous_version_number"] == 1
    assert result["before"] == snapshots[1]
    assert result["after"] == snapshots[3]
    assert result["skill_diffs"] == {
        "added": ["LangGraph"],
        "removed": ["RAG"],
        "retained": ["Python"],
    }
    field_diffs = {item["field"]: item for item in result["field_diffs"]}
    assert set(field_diffs) == {"title", "company", "salary_min_k", "skill_tags", "responsibilities"}
    assert field_diffs["salary_min_k"] == {"field": "salary_min_k", "before": 20, "after": 30}
    assert field_diffs["skill_tags"]["before"] == ["Python", "RAG"]
    assert field_diffs["responsibilities"]["before"] == ["开发模型服务"]

    monkeypatch.setattr(api_main, "store", local_store)
    client = TestClient(app)
    default_response = client.get("/api/jobs/job:1/versions/3/compare")
    assert default_response.status_code == 200
    assert default_response.json()["base_version_number"] == 2
    assert default_response.json()["before"] == snapshots[2]

    response = client.get(
        "/api/jobs/job:1/versions/3/compare?base_version_number=1",
    )
    assert response.status_code == 200
    assert response.json()["base_version_number"] == 1
    assert client.get(
        "/api/jobs/job:1/versions/3/compare?base_version_number=4",
    ).status_code == 404
    assert client.get(
        "/api/jobs/job:1/versions/4/compare?base_version_number=1",
    ).status_code == 404


def test_text_pdf_skips_expensive_page_render(monkeypatch):
    rendered = False

    monkeypatch.setattr(resume_files, "_extract_pdf_text", lambda _: "Python 工程师，五年开发经验。" * 10)

    def render(_):
        nonlocal rendered
        rendered = True
        return []

    monkeypatch.setattr(resume_files, "_render_pdf_images", render)
    result = resume_files.extract_resume_text("resume.pdf", b"fake pdf")

    assert result["text_length"] > 80
    assert result["image_count"] == 0
    assert rendered is False


def test_match_report_exports_pdf_and_word():
    report = SimpleNamespace(
        candidate_id="candidate_test",
        target_job_id="job_ai",
        score=86,
        level="high",
        gaps=[{"skill": "LangGraph", "suggestion": "补充生产实践"}],
        strengths=[{"skill": "Python", "summary": "R&D <Agent> 项目证据充分"}],
        risks=["大型系统经验仍需核验"],
        follow_up_questions=["请说明一次生产故障复盘。"],
        learning_path=[{"step": "第一阶段", "action": "完成 Agent 工程实践"}],
        executive_summary="候选人与 AI <Agent> 平台岗位整体匹配。",
        evidence_coverage=0.82,
        interview_recommendation="建议进入终面",
        job_snapshot={"job_title": "AI Agent 工程师"},
    )
    profile = SimpleNamespace(
        archetype_title="系统型架构者",
        archetype_code="SRA",
        archetype_narrative="擅长结构化拆解复杂问题。",
        summary="",
        competency_dimensions=[{"name": "工程深度", "score": 88}],
    )

    pdf, pdf_type, _ = export_match_report(report, profile, "pdf")
    docx, docx_type, _ = export_match_report(report, profile, "docx")

    assert pdf.startswith(b"%PDF")
    assert pdf_type == "application/pdf"
    assert docx.startswith(b"PK")
    assert "wordprocessingml" in docx_type

    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    word_text = "\n".join(paragraph.text for paragraph in Document(BytesIO(docx)).paragraphs)
    assert "企业招聘匹配报告" in pdf_text
    assert "AI <Agent> 平台岗位" in pdf_text
    assert "企业招聘匹配报告" in word_text
    assert "R&D <Agent> 项目证据充分" in word_text
    assert b"/FontFile2" in pdf or b"/FontFile3" in pdf

    with ZipFile(BytesIO(docx)) as archive:
        styles_xml = archive.read("word/styles.xml").decode("utf-8")
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert 'w:eastAsia="Microsoft YaHei"' in styles_xml
    assert 'w:fill="EAF2FF"' in document_xml
    assert 'w:color="2F6DF4"' in document_xml


def test_report_export_endpoint_uses_persisted_authorized_snapshot(tmp_path, monkeypatch):
    report = {
        "report_id": "report_client_only",
        "candidate_id": "candidate/client_only",
        "target_job_id": "job_ai",
        "score": 86,
        "level": "high",
        "gaps": [],
        "strengths": [{"skill": "Python", "summary": "项目证据充分"}],
        "risks": [],
        "follow_up_questions": ["请说明一次生产故障复盘。"],
        "learning_path": [],
        "executive_summary": "候选人与目标岗位整体匹配。",
        "evidence_coverage": 0.82,
        "interview_recommendation": "建议进入终面",
        "job_snapshot": {"job_title": "AI Agent 工程师"},
    }
    profile = {
        "candidate_id": "candidate/client_only",
        "target_job_id": "job_ai",
        "name": "陈明",
        "skills": [],
        "confidence": 0.9,
        "archetype_title": "系统型架构者",
        "archetype_code": "SRA",
        "competency_dimensions": [{"name": "工程深度", "score": 88}],
    }
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={
            "email": "hr@talentgraph.cn",
            "password": "talentgraph2026",
            "role": "enterprise",
        },
    )
    login_payload = login.json()
    headers = {"Authorization": f"Bearer {login_payload['access_token']}"}
    report_store_path = tmp_path / "reports.db"
    local_store = AppStore(str(report_store_path))
    local_store.save_report(
        MatchReport.model_validate(report),
        CandidateProfile.model_validate(profile),
        owner_user_id=login_payload["user"]["user_id"],
        organization_id=login_payload["user"]["organization_id"],
    )
    monkeypatch.setattr(api_main, "store", AppStore(str(report_store_path)))

    unauthorized = client.post(
        "/api/reports/export?format=pdf",
        json={"report_id": report["report_id"]},
    )
    assert unauthorized.status_code == 401

    seeker_login = client.post(
        "/api/auth/login",
        json={
            "email": "candidate@talentgraph.cn",
            "password": "talentgraph2026",
            "role": "seeker",
        },
    )
    forbidden = client.post(
        "/api/reports/export?format=pdf",
        headers={"Authorization": f"Bearer {seeker_login.json()['access_token']}"},
        json={"report_id": report["report_id"]},
    )
    assert forbidden.status_code == 403

    legacy_unauthorized = client.get(
        f"/api/reports/{report['report_id']}/download?format=pdf"
    )
    assert legacy_unauthorized.status_code == 401

    for output_format, signature, media_type in (
        ("pdf", b"%PDF", "application/pdf"),
        ("docx", b"PK", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ):
        response = client.post(
            f"/api/reports/export?format={output_format}",
            headers=headers,
            json={"report_id": report["report_id"]},
        )

        assert response.status_code == 200
        assert response.content.startswith(signature)
        assert response.headers["content-type"] == media_type
        assert "filename*=UTF-8''" in response.headers["content-disposition"]
        assert "%2F" in response.headers["content-disposition"]
