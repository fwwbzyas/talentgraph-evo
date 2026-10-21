from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from urllib.request import urlopen

import websocket


SESSION_CONFIG = {
    "boss": {
        "name": "BOSS直聘",
        "port": 9222,
        "domain": "zhipin.com",
        "profile": "data/browser_profiles/boss-v2",
        "url": "https://www.zhipin.com/?ka=header-home-logo",
    },
    "zhaopin": {
        "name": "智联招聘",
        "port": 9333,
        "dynamic_port": True,
        "domain": "zhaopin.com",
        "profile": "data/browser_profiles/zhaopin",
        "url": "https://sou.zhaopin.com/?kw=AI%20Agent%20%E5%B7%A5%E7%A8%8B%E5%B8%88&p=1",
    },
}


class BrowserSessionManager:
    """Owns the user-visible, persistent browser sessions used by protected sources."""

    def status(self, source_id: str, *, manage_visibility: bool = True) -> dict[str, Any]:
        config = self._config(source_id)
        port = self._active_port(config)
        pages = self._pages(port) if port else []
        page = next(
            (item for item in pages if item.get("type") == "page" and config["domain"] in item.get("url", "")),
            None,
        )
        title = str((page or {}).get("title") or "")
        url = str((page or {}).get("url") or "")
        page_state = self._inspect_page(page, port) if page and port else {}
        verification_marker = any(
            token in f"{title} {url} {page_state.get('text', '')}".lower()
            for token in ("security", "captcha", "安全校验", "完成验证", "滑动验证")
        )
        verification = verification_marker or "_security_check=" in url
        authenticated = bool(page_state.get("authenticated"))
        authentication = (
            "verification_required" if verification else
            "ready" if authenticated or page_state.get("cards") else
            "login_required" if page else "not_connected"
        )
        background_mode = False
        if manage_visibility and page and port and os.getenv("TALENTGRAPH_BROWSER_AUTO_HIDE", "1") != "0":
            if authentication == "ready":
                background_mode = self._set_visible(config, port, False)
            elif authentication == "verification_required":
                self._set_visible(config, port, True)
        return {
            "source_id": source_id,
            "name": config["name"],
            "requires_browser": True,
            "running": bool(pages),
            "connected": page is not None,
            "authentication": authentication,
            "background_mode": background_mode,
            "public_access": bool(page_state.get("cards")) and not authenticated,
            "page_title": title or None,
            "page_url": url or None,
            "job_cards": int(page_state.get("cards", 0)),
            "profile_path": str(Path(config["profile"]).resolve()),
            "debugger_port": port,
        }

    def start(self, source_id: str) -> dict[str, Any]:
        config = self._config(source_id)
        current = self.status(source_id, manage_visibility=False)
        if current["connected"]:
            pages = self._pages(int(current["debugger_port"]))
            page = next((item for item in pages if config["domain"] in item.get("url", "")), None)
            if page:
                self._set_visible(config, int(current["debugger_port"]), True)
                if current["authentication"] == "login_required" and current.get("page_url") != config["url"]:
                    self._navigate(page, int(current["debugger_port"]), config["url"])
                self._bring_to_front(page, int(current["debugger_port"]))
            return self.status(source_id, manage_visibility=False)
        chrome = self._chrome_path()
        profile = Path(config["profile"]).resolve()
        profile.mkdir(parents=True, exist_ok=True)
        command = [
            chrome,
            f"--remote-debugging-port={0 if config.get('dynamic_port') else config['port']}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            config["url"],
        ]
        process = self._launch_chrome(command)
        deadline = time.monotonic() + 10
        latest = current
        exit_code = None
        while time.monotonic() < deadline:
            exit_code = process.poll() if process else None
            time.sleep(0.25)
            latest = self.status(source_id, manage_visibility=False)
            if latest["running"]:
                return {**latest, "launch_requested": True}
        if exit_code is not None or os.name == "nt":
            raise RuntimeError(
                "Chrome authentication window did not connect; close residual BOSS browser processes and retry"
            )
        return {**latest, "launch_requested": True, "launch_pending": True}

    @staticmethod
    def _launch_chrome(command: list[str]) -> subprocess.Popen | None:
        if os.name == "nt":
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "open",
                command[0],
                subprocess.list2cmdline(command[1:]),
                str(Path(command[0]).parent),
                1,
            )
            if result <= 32:
                raise RuntimeError(f"Windows could not launch Chrome (ShellExecute code {result})")
            return None
        return subprocess.Popen(command, close_fds=True)

    def statuses(self) -> list[dict[str, Any]]:
        return [self.status(source_id) for source_id in SESSION_CONFIG]

    def ensure_ready(self, source_id: str, *, timeout_seconds: float = 15) -> dict[str, Any]:
        current = self.status(source_id)
        if not current["connected"]:
            self.start(source_id)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            current = self.status(source_id)
            if current["authentication"] in {"ready", "verification_required"}:
                return current
            time.sleep(0.5)
        return self.status(source_id)

    @staticmethod
    def _set_visible(config: dict[str, Any], port: int, visible: bool) -> bool:
        if os.name != "nt":
            return False
        titles = [
            str(item.get("title") or "")
            for item in BrowserSessionManager._pages(port)
            if item.get("type") == "page" and item.get("title")
        ]
        handles: list[int] = []
        user32 = ctypes.windll.user32
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            title_buffer = ctypes.create_unicode_buffer(length + 1)
            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buffer, length + 1)
            user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
            window_title = title_buffer.value
            title_matches = config["name"] in window_title or any(
                title in window_title for title in titles if len(title) >= 3
            )
            if class_buffer.value.startswith("Chrome_WidgetWin") and title_matches:
                handles.append(int(hwnd))
            return True

        user32.EnumWindows(enum_proc(callback), 0)
        command = 9 if visible else 0  # SW_RESTORE / SW_HIDE
        for handle in handles:
            user32.ShowWindow(handle, command)
        return bool(handles)

    @staticmethod
    def _bring_to_front(page: dict[str, Any], port: int) -> None:
        socket = None
        try:
            socket = websocket.create_connection(
                page["webSocketDebuggerUrl"], timeout=3, origin=f"http://127.0.0.1:{port}",
            )
            socket.send(json.dumps({"id": 1, "method": "Page.bringToFront"}))
            socket.recv()
        except Exception:
            return
        finally:
            if socket:
                socket.close()

    @staticmethod
    def _navigate(page: dict[str, Any], port: int, url: str) -> None:
        socket = None
        try:
            socket = websocket.create_connection(
                page["webSocketDebuggerUrl"], timeout=3, origin=f"http://127.0.0.1:{port}",
            )
            socket.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}}))
            socket.recv()
        except Exception:
            return
        finally:
            if socket:
                socket.close()

    @staticmethod
    def _inspect_page(page: dict[str, Any], port: int) -> dict[str, Any]:
        socket = None
        try:
            socket = websocket.create_connection(
                page["webSocketDebuggerUrl"], timeout=3, origin=f"http://127.0.0.1:{port}",
            )
            socket.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": """
                    (() => {
                      const host = location.hostname;
                      const cookieNames = document.cookie.split(';').map(item => item.split('=')[0].trim());
                      const linkTexts = [...document.querySelectorAll('a')].map(item => item.innerText.trim());
                      const authenticated = host.includes('zhipin.com')
                        ? cookieNames.includes('bst') && !!document.querySelector('.link-logout')
                        : host.includes('zhaopin.com')
                          ? cookieNames.includes('at') && cookieNames.includes('rt') && linkTexts.includes('\u9000\u51fa')
                          : false;
                      return {
                        cards: document.querySelectorAll('.job-card-box, div.joblist-box__item').length,
                        text: document.body.innerText.slice(0, 500),
                        authenticated
                      };
                    })()
                    """,
                    "returnByValue": True,
                },
            }))
            while True:
                response = json.loads(socket.recv())
                if response.get("id") == 1:
                    return response.get("result", {}).get("result", {}).get("value", {}) or {}
        except Exception:
            return {}
        finally:
            if socket:
                socket.close()

    @staticmethod
    def _pages(port: int) -> list[dict[str, Any]]:
        try:
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1.5) as response:
                value = json.load(response)
                return value if isinstance(value, list) else []
        except Exception:
            return []

    def _active_port(self, config: dict[str, Any]) -> int | None:
        preferred = int(config["port"])
        if self._pages(preferred):
            return preferred
        port_file = Path(config["profile"]) / "DevToolsActivePort"
        try:
            dynamic = int(port_file.read_text(encoding="utf-8").splitlines()[0])
            return dynamic if self._pages(dynamic) else None
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def _chrome_path() -> str:
        configured = os.getenv("TALENTGRAPH_CHROME_PATH", "").strip()
        candidates = [
            configured,
            shutil.which("google-chrome") or "",
            shutil.which("google-chrome-stable") or "",
            shutil.which("chromium") or "",
            shutil.which("chromium-browser") or "",
            shutil.which("chrome") or "",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        raise RuntimeError("Google Chrome was not found; set TALENTGRAPH_CHROME_PATH")

    @staticmethod
    def _config(source_id: str) -> dict[str, Any]:
        if source_id not in SESSION_CONFIG:
            raise ValueError(f"unsupported browser source: {source_id}")
        return SESSION_CONFIG[source_id]


browser_sessions = BrowserSessionManager()
