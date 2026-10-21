from agents.data import browser_sessions as browser_sessions_module
from agents.data.browser_sessions import BrowserSessionManager


def test_browser_session_status_reports_connected_page(monkeypatch):
    manager = BrowserSessionManager()
    monkeypatch.setattr(manager, "_set_visible", lambda config, port, visible: False)
    monkeypatch.setattr(manager, "_pages", lambda port: [{
        "type": "page",
        "title": "北京招聘 - BOSS直聘",
        "url": "https://www.zhipin.com/web/geek/jobs",
    }] if port == 9222 else [])
    monkeypatch.setattr(manager, "_inspect_page", lambda page, port: {
        "authenticated": True,
        "cards": 20,
        "text": "职位列表",
    })

    boss = manager.status("boss")
    zhaopin = manager.status("zhaopin")

    assert boss["connected"] is True and boss["authentication"] == "ready"
    assert zhaopin["connected"] is False and zhaopin["authentication"] == "not_connected"


def test_public_boss_cards_are_collectable_without_login_cookie(monkeypatch):
    manager = BrowserSessionManager()
    monkeypatch.setattr(manager, "_set_visible", lambda config, port, visible: False)
    monkeypatch.setattr(manager, "_pages", lambda port: [{
        "type": "page",
        "title": "北京招聘 - BOSS直聘",
        "url": "https://www.zhipin.com/web/geek/jobs",
    }] if port == 9222 else [])
    monkeypatch.setattr(manager, "_inspect_page", lambda page, port: {
        "authenticated": False,
        "cards": 20,
        "text": "职位列表",
    })

    status = manager.status("boss")

    assert status["authentication"] == "ready"
    assert status["public_access"] is True


def test_start_opens_visible_window_and_waits_until_ready(monkeypatch, tmp_path):
    manager = BrowserSessionManager()
    states = iter([
        {"connected": False, "running": False},
        {"connected": True, "running": True, "authentication": "ready"},
    ])
    captured = {}

    class FakeProcess:
        @staticmethod
        def poll():
            # Chrome's launcher may hand off to an existing browser process and exit.
            return 0

    monkeypatch.setattr(manager, "status", lambda source_id, **kwargs: next(states))
    monkeypatch.setattr(manager, "_chrome_path", lambda: "chrome.exe")
    monkeypatch.setattr(manager, "_config", lambda source_id: {
        "name": "BOSS直聘",
        "port": 9222,
        "domain": "zhipin.com",
        "profile": str(tmp_path / "boss"),
        "url": "https://www.zhipin.com/web/geek/jobs",
    })
    monkeypatch.setattr(browser_sessions_module.time, "sleep", lambda seconds: None)

    def fake_launch(args):
        captured["args"] = args
        return FakeProcess()

    monkeypatch.setattr(manager, "_launch_chrome", fake_launch)

    result = manager.start("boss")

    assert result["running"] is True
    assert result["launch_requested"] is True
    assert "--new-window" in captured["args"]
