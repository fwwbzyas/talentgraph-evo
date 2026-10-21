from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


COOKIE_SESSION_CONFIG = {
    "51job": {
        "name": "前程无忧",
        "domain": "51job.com",
        "login_url": "https://login.51job.com/login.php",
        "path": "data/browser_profiles/51job/cookies.json",
    },
    "liepin": {
        "name": "猎聘",
        "domain": "liepin.com",
        "login_url": "https://passport.liepin.com/login",
        "path": "data/browser_profiles/liepin/cookies.json",
    },
}


class RecruitmentCookieSessionStore:
    """Persist user-exported site cookies without ever returning their values."""

    def statuses(self) -> list[dict[str, Any]]:
        return [self.status(source_id) for source_id in COOKIE_SESSION_CONFIG]

    def status(self, source_id: str) -> dict[str, Any]:
        config = self._config(source_id)
        path = Path(config["path"])
        count = 0
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                cookies = payload.get("cookies", []) if isinstance(payload, dict) else []
                count = len(cookies) if isinstance(cookies, list) else 0
            except (OSError, ValueError, TypeError):
                count = 0
        updated_at = (
            datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
            if path.is_file() else None
        )
        return {
            "source_id": source_id,
            "name": config["name"],
            "configured": count > 0,
            "cookie_count": count,
            "updated_at": updated_at,
            "login_url": config["login_url"],
        }

    def save(self, source_id: str, raw_cookies: Any) -> dict[str, Any]:
        config = self._config(source_id)
        cookies = raw_cookies.get("cookies", raw_cookies) if isinstance(raw_cookies, dict) else raw_cookies
        if not isinstance(cookies, list) or not cookies:
            raise ValueError("Cookie 文件必须是非空数组或包含 cookies 数组的 JSON")
        if len(cookies) > 200:
            raise ValueError("Cookie 数量超过 200 条限制")
        normalized = [self._normalize_cookie(item, config["domain"]) for item in cookies]
        encoded = json.dumps({"cookies": normalized}, ensure_ascii=False, indent=2)
        if len(encoded.encode("utf-8")) > 128 * 1024:
            raise ValueError("Cookie 文件超过 128KB 限制")

        path = Path(config["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(path)
        return self.status(source_id)

    def clear(self, source_id: str) -> dict[str, Any]:
        path = Path(self._config(source_id)["path"])
        if path.is_file():
            path.unlink()
        return self.status(source_id)

    @staticmethod
    def _normalize_cookie(item: Any, allowed_domain: str) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise ValueError("Cookie 条目必须是 JSON 对象")
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "")
        domain = str(item.get("domain") or "").strip().lstrip(".").casefold()
        url = str(item.get("url") or "").strip()
        url_domain = (urlsplit(url).hostname or "").casefold()
        cookie_domain = domain or url_domain
        if not name or not value:
            raise ValueError("Cookie 条目缺少 name 或 value")
        if cookie_domain != allowed_domain and not cookie_domain.endswith(f".{allowed_domain}"):
            raise ValueError(f"Cookie 域名必须属于 {allowed_domain}")

        output: dict[str, Any] = {"name": name, "value": value}
        if domain:
            output.update({"domain": str(item.get("domain")), "path": str(item.get("path") or "/")})
        else:
            output["url"] = url
        for key in ("expires", "httpOnly", "secure"):
            if key in item:
                output[key] = item[key]
        same_site = str(item.get("sameSite") or "").capitalize()
        if same_site in {"Strict", "Lax", "None"}:
            output["sameSite"] = same_site
        return output

    @staticmethod
    def _config(source_id: str) -> dict[str, Any]:
        if source_id not in COOKIE_SESSION_CONFIG:
            raise ValueError(f"不支持该登录态来源：{source_id}")
        return COOKIE_SESSION_CONFIG[source_id]


cookie_sessions = RecruitmentCookieSessionStore()
