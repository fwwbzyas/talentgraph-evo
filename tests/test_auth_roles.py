import pytest

from core.auth import AuthError, AuthService
from core.store import AppStore


def test_role_login_rejects_wrong_portal(tmp_path):
    service = AuthService(str(tmp_path / "auth.db"))

    with pytest.raises(AuthError, match="当前登录入口"):
        service.login(
            email="candidate@talentgraph.cn",
            password="talentgraph2026",
            role="enterprise",
        )

    session = service.login(
        email="candidate@talentgraph.cn",
        password="talentgraph2026",
        role="seeker",
    )
    assert session["user"]["role"] == "seeker"
    assert service.resolve_token(session["access_token"])["user_id"] == session["user"]["user_id"]


def test_seeker_applications_are_owner_scoped(tmp_path):
    service = AuthService(str(tmp_path / "applications.db"))
    first = service.register(
        email="first@example.com",
        password="password-123",
        role="seeker",
        display_name="第一位求职者",
    )
    second = service.register(
        email="second@example.com",
        password="password-123",
        role="seeker",
        display_name="第二位求职者",
    )

    created = service.create_application(
        user=first,
        job_id="job_ai_agent",
        job_title="AI Agent 工程师",
        company="星云科技",
        source_url="https://example.com/jobs/ai-agent",
        match_score=86,
    )

    assert service.list_applications(first)[0]["application_id"] == created["application_id"]
    assert service.list_applications(second) == []
    with pytest.raises(AuthError, match="无权修改"):
        service.update_application(created["application_id"], "withdrawn", second)


def test_enterprise_and_seeker_permissions_are_distinct(tmp_path):
    service = AuthService(str(tmp_path / "roles.db"))
    enterprise = service.login(
        email="hr@talentgraph.cn",
        password="talentgraph2026",
        role="enterprise",
    )["user"]
    seeker = service.login(
        email="candidate@talentgraph.cn",
        password="talentgraph2026",
        role="seeker",
    )["user"]

    assert enterprise["organization_id"]
    assert seeker["organization_id"] is None
    with pytest.raises(AuthError, match="只有求职者"):
        service.create_application(
            user=enterprise,
            job_id="job_1",
            job_title="大数据工程师",
            company="测试企业",
            source_url=None,
            match_score=None,
        )


def test_assessment_records_are_owner_scoped(tmp_path):
    auth = AuthService(str(tmp_path / "assessment-auth.db"))
    enterprise = auth.login(
        email="hr@talentgraph.cn", password="talentgraph2026", role="enterprise",
    )["user"]
    seeker = auth.login(
        email="candidate@talentgraph.cn", password="talentgraph2026", role="seeker",
    )["user"]
    store = AppStore(str(tmp_path / "assessment-store.db"))

    record = store.save_assessment_record(
        {"id": "record_1", "candidate_id": "candidate_1", "name": "候选人甲"},
        enterprise,
    )

    assert store.list_assessment_records(enterprise) == [record]
    assert store.list_assessment_records(seeker) == []
    with pytest.raises(PermissionError, match="access denied"):
        store.save_assessment_record(
            {"id": "record_1", "candidate_id": "candidate_1", "name": "越权修改"},
            seeker,
        )
