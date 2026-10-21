from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import random
import re
from threading import Lock
import time
from typing import Any

from agents.data.source_policy import SOURCE_STATE_PATHS, SUPPLEMENTAL_INTERVAL_MINUTES, SUPPLEMENTAL_ITEMS_PER_RUN


TARGET_JOB_QUERIES = (
    "AI Agent 工程师", "大模型应用工程师", "RAG 工程师", "机器学习工程师",
    "算法工程师", "多模态工程师", "模型评测工程师", "AI 平台工程师",
    "大数据开发工程师", "实时计算工程师", "Flink 工程师", "数据平台工程师",
    "数据治理工程师", "数据仓库工程师", "湖仓架构师",
    "智能系统工程师", "机器人软件工程师", "边缘智能工程师", "自动驾驶系统工程师",
    "物联网平台工程师", "物联网嵌入式工程师", "IoT 工程师", "边缘网关工程师", "固件工程师",
)
TARGET_CITIES = ("北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "武汉", "西安", "合肥", "长沙")

_INCLUDE_TITLE = re.compile(r"(工程师|开发|研发|算法|架构|测试|数据|嵌入式|智能体|Agent)", re.IGNORECASE)
_EXCLUDE_TITLE = re.compile(r"(销售|客服|班主任|课程|招生|运营|市场|合伙人|兼职)")
_PHONE_RE = re.compile(r"(?<!\d)(?:1[3-9]\d{9}|1[3-9]\d[ -]\d{4}[ -]\d{4})(?!\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_WECHAT_RE = re.compile(r"(?:微信|微信号|wechat|weixin|wx)\s*[:：]?\s*[A-Za-z][A-Za-z0-9_-]{5,19}", re.IGNORECASE)
_QQ_RE = re.compile(r"(?:QQ|qq)\s*[:：]?\s*[1-9]\d{4,10}(?!\d)")
_VERIFY_MARKERS = ("safe.", "captcha", "verification", "security", "安全校验", "完成验证", "滑动验证", "验证码")
_TRANSIENT_BROWSER_MARKERS = (
    "err_connection_closed", "err_connection_reset", "err_timed_out", "err_name_not_resolved",
    "navigation timeout", "timeout exceeded", "target page, context or browser has been closed",
)


class CollectionRiskControlError(RuntimeError):
    """A hard stop: verification/WAF is recorded and never retried automatically."""

    def __init__(self, source_id: str, url: str, evidence: str) -> None:
        super().__init__(f"[{source_id}] 检测到安全验证，已停止本次采集：{evidence} ({url})")
        self.source_id = source_id
        self.url = url
        self.evidence = evidence


class CollectionTransientSourceError(RuntimeError):
    """A bounded, retry-later stop for temporary browser or network unavailability."""

    def __init__(self, source_id: str, evidence: str) -> None:
        super().__init__(f"[{source_id}] 来源暂时不可用，本轮已结束：{evidence}")
        self.source_id = source_id
        self.evidence = evidence


def mask_contacts(value: Any) -> str:
    text = str(value or "")
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _WECHAT_RE.sub("[WECHAT]", text)
    return _QQ_RE.sub("[QQ]", text).strip()


def split_location(value: Any) -> tuple[str | None, str | None]:
    parts = [part.strip() for part in re.split(r"[-·•．]", str(value or ""), maxsplit=1) if part.strip()]
    return (parts[0] if parts else None, parts[1] if len(parts) > 1 else None)


def parse_experience(value: Any) -> tuple[int | None, int | None]:
    text = str(value or "")
    match = re.search(r"(\d+)\s*[-~—至]\s*(\d+)\s*年", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d+)\s*年(?:以上)?", text)
    return (int(match.group(1)), int(match.group(1))) if match else (None, None)


def parse_monthly_salary(value: Any) -> tuple[int | None, int | None, int]:
    """Normalize common Chinese salary strings to integer k/month without dropping raw text."""
    text = str(value or "").replace(" ", "").replace("－", "-")
    numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", text)[:2]]
    if not numbers:
        return None, None, 12
    if "万" in text:
        multiplier = 10.0
    elif "千" in text or re.search(r"[Kk]", text):
        multiplier = 1.0
    elif "元" in text:
        multiplier = 0.001
    else:
        multiplier = 1.0
    if "/年" in text or "年薪" in text:
        multiplier /= 12
    values = [max(0, round(number * multiplier)) for number in numbers]
    months_match = re.search(r"(\d+)薪", text)
    months = int(months_match.group(1)) if months_match else 12
    return values[0], values[-1], months


class SupplementalBrowserSource(ABC):
    """Low-volume browser source that emits TalentGraph's existing raw JD contract."""

    source_id = ""
    source_category = "recruitment"
    display_name = ""
    access_mode = "browser_assisted_research"
    first_page = 1
    recommended_items_per_run = SUPPLEMENTAL_ITEMS_PER_RUN
    recommended_min_interval_minutes = SUPPLEMENTAL_INTERVAL_MINUTES
    recommended_max_interval_minutes = SUPPLEMENTAL_INTERVAL_MINUTES
    include_pattern = _INCLUDE_TITLE
    exclude_pattern = _EXCLUDE_TITLE
    available_queries = TARGET_JOB_QUERIES
    available_cities = ("全国", *TARGET_CITIES)

    def __init__(self) -> None:
        prefix = f"TALENTGRAPH_{self.source_id.upper()}"
        self.available_cities = ("全国", *TARGET_CITIES)
        self.enabled = _env_bool(f"{prefix}_BROWSER_ENABLED", True)
        self.headless = _env_bool(f"{prefix}_HEADLESS", False)
        self.profile_path = Path(os.getenv(f"{prefix}_PROFILE_PATH", f"data/browser_profiles/{self.source_id}"))
        self.cookie_path = Path(os.getenv(
            f"{prefix}_COOKIE_PATH",
            str(self.profile_path / "cookies.json"),
        ))
        self.state_path = Path(os.getenv(f"{prefix}_STATE_PATH", str(SOURCE_STATE_PATHS[self.source_id])))
        self.browser_channel = os.getenv(f"{prefix}_BROWSER_CHANNEL", "").strip()
        self.verify_timeout_seconds = int(os.getenv(f"{prefix}_VERIFY_TIMEOUT_SECONDS", "180"))
        self.navigation_timeout_ms = int(os.getenv(f"{prefix}_NAVIGATION_TIMEOUT_SECONDS", "20")) * 1000
        self.selector_timeout_ms = int(os.getenv(f"{prefix}_SELECTOR_TIMEOUT_SECONDS", "5")) * 1000
        self.max_pages_per_run = int(os.getenv(f"{prefix}_MAX_PAGES_PER_RUN", "4"))
        self.delay_range = _float_range(f"{prefix}_REQUEST_DELAY_SECONDS", (2.0, 3.5))
        self.min_per_run = self.recommended_items_per_run
        self.max_per_run = self.recommended_items_per_run
        self.mode = "discovery"
        self.discovery_ratio = 1.0
        self.revisit_after_hours = 7 * 24.0
        self.stop_at_end = False
        self.cities = TARGET_CITIES
        self.queries = TARGET_JOB_QUERIES
        self.last_fetch_stats: dict[str, Any] = {}
        self.configuration = "ready" if self.enabled else f"set {prefix}_BROWSER_ENABLED=1"
        self._lock = Lock()

    def configure(
        self,
        *,
        cities: list[str],
        queries: list[str],
        items_per_run: int,
        mode: str = "discovery",
        discovery_ratio: float = 1.0,
        revisit_after_hours: float = 7 * 24,
        stop_at_end: bool = False,
    ) -> None:
        selected_cities = [city for city in cities if city in self.available_cities]
        self.cities = tuple(selected_cities or TARGET_CITIES)
        selected_queries = [query for query in queries if query in self.available_queries]
        self.queries = tuple(selected_queries or self.available_queries)
        self.min_per_run = max(1, items_per_run)
        self.max_per_run = max(1, items_per_run)
        self.mode = mode
        self.discovery_ratio = discovery_ratio
        self.revisit_after_hours = revisit_after_hours
        self.stop_at_end = stop_at_end

    def reset_cursor(self, query: str, city: str) -> None:
        state = self._load_state()
        state.setdefault("page_cursors", {})[f"{city}|{query}"] = self.first_page
        state["combo_index"] = 0
        self._save_state(state)

    def seed_seen(self, source_ids: list[str]) -> None:
        with self._lock:
            state = self._load_state()
            now = datetime.now(UTC).isoformat()
            for source_id in source_ids:
                native_id = source_id.removeprefix(f"{self.source_id}:")
                state["seen"].setdefault(native_id, now)
            self._save_state(state)

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]:
        del lookback_hours
        if not self.enabled:
            raise RuntimeError(f"{self.display_name}采集器未启用：{self.configuration}")
        with self._lock:
            return self._fetch_locked(max_items)

    def _fetch_locked(self, max_items: int) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - dependency is present in project images
            raise RuntimeError(f"启用{self.display_name}采集前需安装 Playwright Chromium") from exc

        state = self._load_state()
        self._prune_seen(state)
        limit = max(1, min(max_items, self.max_per_run))
        discovery_quota = limit if self.mode == "discovery" else 0 if self.mode == "monitor" else round(limit * self.discovery_ratio)
        monitor_quota = limit - discovery_quota
        if self.stop_at_end and self.mode == "hybrid":
            discovery_quota = monitor_quota = limit
        output: list[dict[str, Any]] = []
        run_seen: set[str] = set()
        scanned = discovery_candidates = monitor_candidates = pages_visited = 0
        reached_end = False
        end_reason: str | None = None

        self.profile_path.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as playwright:
                options: dict[str, Any] = {
                    "user_data_dir": str(self.profile_path.resolve()),
                    "headless": self.headless,
                    "locale": "zh-CN",
                    "viewport": {"width": 1440, "height": 900},
                }
                if self.browser_channel:
                    options["channel"] = self.browser_channel
                context = playwright.chromium.launch_persistent_context(**options)
                try:
                    self._inject_configured_cookies(context)
                    while len(output) < limit and pages_visited < self.max_pages_per_run:
                        keyword, city, page_number = self._next_combo(state)
                        pages_visited += 1
                        _polite_wait(self.delay_range)
                        rows = self._fetch_page(context, keyword, city, page_number, limit - len(output))
                        scanned += len(rows)
                        if not rows:
                            self._reset_combo_cursor(state, keyword, city)
                            reached_end = True
                            end_reason = "empty_page"
                            if self.stop_at_end:
                                break
                            continue
                        for row in rows:
                            native_id = str(row.get("source_id") or "").strip()
                            title = str(row.get("title") or "").strip()
                            if not native_id or native_id in run_seen:
                                continue
                            if not self.include_pattern.search(title) or self.exclude_pattern.search(title):
                                continue
                            known = native_id in state["seen"]
                            if known and (self.mode == "discovery" or monitor_candidates >= monitor_quota or not self._due_for_revisit(state["seen"][native_id])):
                                continue
                            if not known and (self.mode == "monitor" or discovery_candidates >= discovery_quota):
                                continue
                            run_seen.add(native_id)
                            state["seen"][native_id] = datetime.now(UTC).isoformat()
                            monitor_candidates += int(known)
                            discovery_candidates += int(not known)
                            output.append(row)
                            if len(output) >= limit:
                                break
                        self._save_state(state)
                finally:
                    context.close()
        except CollectionRiskControlError:
            end_reason = "risk_control"
            self._record_fetch_stats(scanned, discovery_candidates, monitor_candidates, pages_visited, end_reason)
            self._save_state(state)
            raise
        except Exception as exc:
            if not _is_transient_browser_error(exc):
                raise
            end_reason = "source_temporarily_unavailable"
            self._record_fetch_stats(scanned, discovery_candidates, monitor_candidates, pages_visited, end_reason)
            self._save_state(state)
            raise CollectionTransientSourceError(self.source_id, str(exc)[:180]) from exc
        self.last_fetch_stats = {
            "scanned": scanned,
            "discovery_candidates": discovery_candidates,
            "monitor_candidates": monitor_candidates,
            "reached_end": reached_end,
            "end_reason": end_reason,
            "pages_visited": pages_visited,
            "sampling_policy": "supplemental_low_volume",
        }
        self._save_state(state)
        return output

    def _record_fetch_stats(
        self,
        scanned: int,
        discovery_candidates: int,
        monitor_candidates: int,
        pages_visited: int,
        end_reason: str,
    ) -> None:
        self.last_fetch_stats = {
            "scanned": scanned,
            "discovery_candidates": discovery_candidates,
            "monitor_candidates": monitor_candidates,
            "reached_end": False,
            "end_reason": end_reason,
            "pages_visited": pages_visited,
            "sampling_policy": "supplemental_low_volume",
        }

    def _inject_configured_cookies(self, context: Any) -> None:
        """Load an optional user-provided login session without logging secret values."""
        if not self.cookie_path.is_file():
            return
        try:
            payload = json.loads(self.cookie_path.read_text(encoding="utf-8"))
            cookies = payload.get("cookies", payload) if isinstance(payload, dict) else payload
            if not isinstance(cookies, list):
                return
            allowed = {
                "name", "value", "url", "domain", "path", "expires",
                "httpOnly", "secure", "sameSite",
            }
            normalized = [
                {key: value for key, value in item.items() if key in allowed}
                for item in cookies
                if isinstance(item, dict) and item.get("name") and item.get("value")
            ]
            if normalized:
                context.add_cookies(normalized)
        except (OSError, ValueError, TypeError):
            # An expired or malformed optional session must never stop scheduled runs.
            return

    @abstractmethod
    def _fetch_page(self, context: Any, keyword: str, city: str, page_number: int, remaining: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _wait_for_verification(self, page: Any) -> None:
        if not self._is_verification_page(page):
            return
        if self.headless:
            raise CollectionRiskControlError(self.source_id, str(page.url or ""), "headless 模式无法人工完成验证")
        deadline = time.monotonic() + self.verify_timeout_seconds
        while time.monotonic() < deadline:
            page.wait_for_timeout(2_000)
            if not self._is_verification_page(page):
                return
        raise CollectionRiskControlError(self.source_id, str(page.url or ""), "等待人工验证超时")

    @staticmethod
    def _is_verification_page(page: Any) -> bool:
        try:
            marker = f"{page.title()} {page.url}".casefold()
        except Exception:
            return False
        return any(token.casefold() in marker for token in _VERIFY_MARKERS)

    def _load_state(self) -> dict[str, Any]:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        state.setdefault("schema_version", 1)
        state.setdefault("seen", {})
        state.setdefault("page_cursors", {})
        state.setdefault("combo_index", 0)
        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def _next_combo(self, state: dict[str, Any]) -> tuple[str, str, int]:
        combos = [(query, city) for city in self.cities for query in self.queries]
        index = int(state.get("combo_index", 0)) % max(1, len(combos))
        query, city = combos[index]
        state["combo_index"] = (index + 1) % len(combos)
        key = f"{city}|{query}"
        cursors = state.setdefault("page_cursors", {})
        page = max(self.first_page, int(cursors.get(key, self.first_page)))
        cursors[key] = page + 1
        state["cycle_started_at"] = state.get("cycle_started_at") or datetime.now(UTC).isoformat()
        return str(query), str(city), page

    def _reset_combo_cursor(self, state: dict[str, Any], query: str, city: str) -> None:
        state.setdefault("page_cursors", {})[f"{city}|{query}"] = self.first_page

    def _due_for_revisit(self, timestamp: str) -> bool:
        return _timestamp(timestamp) <= datetime.now(UTC).timestamp() - self.revisit_after_hours * 3600

    def _prune_seen(self, state: dict[str, Any]) -> None:
        cutoff = datetime.now(UTC).timestamp() - 30 * 86400
        state["seen"] = {
            source_id: timestamp
            for source_id, timestamp in state["seen"].items()
            if _timestamp(timestamp) >= cutoff
        }


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() not in {"0", "false", "no", "off"}


def _float_range(name: str, default: tuple[float, float]) -> tuple[float, float]:
    try:
        values = [float(item.strip()) for item in os.getenv(name, "").split(",") if item.strip()]
        return (values[0], values[-1]) if values else default
    except ValueError:
        return default


def _polite_wait(bounds: tuple[float, float]) -> None:
    time.sleep(random.uniform(min(bounds), max(bounds)))


def _timestamp(value: Any) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0


def _is_transient_browser_error(exc: Exception) -> bool:
    marker = f"{type(exc).__name__}: {exc}".casefold()
    return any(token in marker for token in _TRANSIENT_BROWSER_MARKERS)
