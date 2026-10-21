from __future__ import annotations

from pathlib import Path

import pytest

from agents.data.cookie_sessions import COOKIE_SESSION_CONFIG, RecruitmentCookieSessionStore


def test_cookie_session_is_persisted_without_exposing_values(tmp_path, monkeypatch):
    path = tmp_path / "liepin" / "cookies.json"
    monkeypatch.setitem(COOKIE_SESSION_CONFIG["liepin"], "path", str(path))
    store = RecruitmentCookieSessionStore()

    status = store.save("liepin", [{
        "name": "session",
        "value": "secret-value",
        "domain": ".liepin.com",
        "path": "/",
        "httpOnly": True,
        "sameSite": "no_restriction",
    }])

    assert status["configured"] is True and status["cookie_count"] == 1
    assert "secret-value" not in str(status)
    assert path.is_file()
    assert store.clear("liepin")["configured"] is False


def test_cookie_session_rejects_cross_site_cookie(tmp_path, monkeypatch):
    monkeypatch.setitem(COOKIE_SESSION_CONFIG["51job"], "path", str(tmp_path / "cookies.json"))
    store = RecruitmentCookieSessionStore()

    with pytest.raises(ValueError, match="51job.com"):
        store.save("51job", [{
            "name": "session",
            "value": "not-for-this-site",
            "domain": ".example.com",
            "path": "/",
        }])

    assert not Path(COOKIE_SESSION_CONFIG["51job"]["path"]).exists()
