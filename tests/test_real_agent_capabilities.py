from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from agents.assessment.service import AssessmentAgent
from agents.emerging_jobs.service import EmergingJobAgent
from agents.llm import OpenAICompatibleClient
from agents.validation.service import ValidationAgent
from apps.api.main import app
from contracts import (
    AssessmentAnswer,
    EmergingJobDiscoveryRequest,
    GameResultInput,
    ImportRequest,
    ValidationRunRequest,
)
from agents.data.service import DataAgent
from core.store import AppStore
from core.sample_data import generate_demo_jds


def test_llm_client_has_explicit_offline_fallback(monkeypatch):
    for name in ("TALENTGRAPH_LLM_BASE_URL", "TALENTGRAPH_LLM_API_KEY", "TALENTGRAPH_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    result = OpenAICompatibleClient().generate_json(
        system_prompt="json", user_prompt="question", fallback={"content": "offline"}
    )

    assert result.data == {"content": "offline"}
    assert result.provider_status["fallback"] is True
    assert result.provider_status["reason"] == "missing_environment_configuration"


def test_llm_client_calls_openai_compatible_json_endpoint(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_DISABLED", raising=False)
    monkeypatch.setenv("TALENTGRAPH_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("TALENTGRAPH_LLM_API_KEY", "test-only")
    monkeypatch.setenv("TALENTGRAPH_LLM_MODEL", "model-json")

    def fake_post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, request=request, json={"choices": [{"message": {"content": '{"content":"remote"}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = OpenAICompatibleClient().generate_json(system_prompt="json", user_prompt="question", fallback={"content": "offline"})

    assert result.data["content"] == "remote"
    assert result.provider_status["provider"] == "openai-compatible"
    assert result.provider_status["configured"] is True
    assert result.provider_status["model"] == "model-json"
    assert result.provider_status["mode"] == "remote"
    assert result.provider_status["ok"] is True
    assert result.provider_status["fallback"] is False
    assert result.provider_status["duration_ms"] >= 0


def test_assessment_is_staged_evidence_driven_and_persistable(tmp_path, monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    agent = AssessmentAgent(OpenAICompatibleClient())
    session = agent.start("candidate_state", "job_ai", "本科，4年Python开发，负责RAG平台，使用LangGraph。")

    assert session.current_stage == "skill_deep_question" and session.stage_progress == 0.2
    assert session.evidence[0]["stage"] == "resume_parse"
    answers = (
        "我负责RAG检索链路，召回率提升12%，有压测报告。",
        "先基于trace和监控定位，比较方案边界并压测。",
        "先确认影响面和指标，止损后回滚，并同步业务。",
    )
    for index in range(len(session.candidate_profile["dialogue_skill_plan"])):
        answer = answers[index % len(answers)]
        session = agent.answer(session, AssessmentAnswer(session_id=session.session_id, answer=answer))
        assert session.next_action is not None
    assert session.current_stage == "interactive_game"
    session = agent.game_result(
        session,
        GameResultInput(session_id=session.session_id, events=[{"type": "allocate", "value": "observability"}, {"type": "action", "value": "rollback"}]),
    )
    assert session.current_stage == "finalize_profile" and session.stage_progress == 1
    assert any(item["stage"] == "interactive_game" for item in session.evidence)

    first_store = AppStore(str(tmp_path / "state.db"))
    first_store.save_session(session)
    reloaded = AppStore(str(tmp_path / "state.db"))
    assert reloaded.sessions[session.session_id].history == session.history


def test_emerging_job_discovery_uses_observed_sources_and_growth():
    batch = DataAgent().run(ImportRequest(batch_name="discovery", items=generate_demo_jds()))
    candidates = EmergingJobAgent().discover(
        [batch], [], EmergingJobDiscoveryRequest(minimum_source_count=3, minimum_confidence=0.45)
    )

    assert candidates
    agent_job = next(item for item in candidates if item.name == "AI Agent 工程师")
    assert {"LangGraph", "工具调用", "多 Agent 协作"} <= set(agent_job.required_skills)
    assert agent_job.source_count == len({item["source_id"] for item in agent_job.evidence}) or agent_job.source_count > len(agent_job.evidence)
    assert agent_job.evidence and agent_job.maturity_status in {"signal", "forming", "established"}
    assert agent_job.source_family == "大模型应用岗位族"
    assert "Java 后端工程师" not in {item.name for item in candidates}


def test_validation_run_executes_agents_and_returns_field_failures():
    run = ValidationAgent().run(
        ValidationRunRequest(
            jd_limit=16,
            resume_cases=[{
                "sample_id": "known_failure",
                "text": "本科，2年Java开发经验。",
                "expected": {"skills": ["Java", "Kubernetes"], "experience_years": 2.0, "education": "本科"},
            }],
        )
    )

    assert run.status == "completed" and run.stage_progress == 1
    assert run.metrics["evaluated_samples"] == {"jd": 16, "resume": 1, "match": 3}
    assert any(failure.sample_id == "known_failure" and failure.field == "skills" for failure in run.failures)
    assert {result["stage"] for result in run.stage_results} == {"jd", "resume", "match"}


def test_emerging_and_validation_api_expose_runs_and_details():
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={
            "email": "hr@talentgraph.cn",
            "password": "talentgraph2026",
            "role": "enterprise",
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    imported = client.post(
        "/api/data/import", json={"batch_name": "real_api", "items": generate_demo_jds()}, headers=headers
    ).json()
    discovery = client.post("/api/emerging-jobs/discover", json={"batch_ids": [imported["batch_id"]]}, headers=headers)
    assert discovery.status_code == 200 and discovery.json()["items"]
    assert client.get("/api/emerging-jobs", params={"minimum_confidence": 0.5}, headers=headers).status_code == 200

    created = client.post("/api/validation/runs", json={"jd_limit": 12}, headers=headers)
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    assert client.get("/api/validation/runs", headers=headers).status_code == 200
    detail = client.get(f"/api/validation/runs/{run_id}", headers=headers)
    assert detail.status_code == 200 and detail.json()["stage_results"]
