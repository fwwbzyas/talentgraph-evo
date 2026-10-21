from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import random
import re
from threading import Lock
import time
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from agents.data.boss_parser import (
    BossSearchHit,
    is_challenge_page,
    is_explicit_empty_result,
    parse_job_detail,
    parse_search_cards,
)
from agents.data.city_catalog import recruitment_city_catalog


RESTRICTED_HTTP_STATUSES = {401, 403, 412, 429}


class BossBrowserSource:
    """BOSS source using the boss-job-crawler Playwright and parser workflow."""

    source_id = "boss"
    source_category = "recruitment"
    display_name = "BOSS直聘"
    access_mode = "browser_assisted_research"
    enabled = True

    queries = (
        "AI Agent 工程师", "大模型应用工程师", "RAG 工程师", "机器学习工程师",
        "算法工程师", "多模态工程师", "模型评测工程师", "AI 平台工程师",
        "大数据开发工程师", "实时计算工程师", "Flink 工程师", "数据平台工程师",
        "数据治理工程师", "数据仓库工程师", "湖仓架构师",
        "智能系统工程师", "机器人软件工程师", "边缘智能工程师", "自动驾驶系统工程师",
        "物联网平台工程师", "物联网嵌入式工程师", "IoT 工程师", "边缘网关工程师", "固件工程师",
    )
    available_queries = queries
    include_pattern = re.compile(r"(工程师|开发|研发|算法|架构|测试|数据|嵌入式|智能体|Agent)", re.IGNORECASE)
    exclude_pattern = re.compile(r"(销售|客服|班主任|课程|招生|运营|市场|合伙人|兼职)")

    def __init__(self) -> None:
        self.available_cities = {"全国": "100010000", **recruitment_city_catalog()}
        self.cities = {"全国": "100010000"}
        self.cdp_url = os.getenv("TALENTGRAPH_BOSS_CDP_URL", "http://127.0.0.1:9222").rstrip("/")
        self.min_per_run = int(os.getenv("TALENTGRAPH_BOSS_MIN_PER_RUN", "50"))
        self.max_per_run = int(os.getenv("TALENTGRAPH_BOSS_MAX_PER_RUN", "50"))
        self.render_wait_seconds = float(os.getenv("TALENTGRAPH_BOSS_RENDER_WAIT_SECONDS", "20"))
        legacy_delay = os.getenv("TALENTGRAPH_BOSS_PAGE_DELAY_SECONDS", "6").split(",", 1)[0].strip()
        self.request_delay_seconds = float(os.getenv("TALENTGRAPH_BOSS_REQUEST_DELAY_SECONDS", legacy_delay))
        self.max_requests_per_hour = int(os.getenv("TALENTGRAPH_BOSS_MAX_REQUESTS_PER_HOUR", "80"))
        self.max_requests_per_day = int(os.getenv("TALENTGRAPH_BOSS_MAX_REQUESTS_PER_DAY", "400"))
        self.detail_delay_range = _float_range("TALENTGRAPH_BOSS_DETAIL_DELAY_SECONDS", (4.0, 8.0))
        self.max_details_per_run = int(os.getenv("TALENTGRAPH_BOSS_MAX_DETAILS_PER_RUN", "12"))
        self.max_pages_per_run = int(os.getenv("TALENTGRAPH_BOSS_MAX_PAGES_PER_RUN", "24"))
        self.seen_cooldown_days = int(os.getenv("TALENTGRAPH_BOSS_SEEN_COOLDOWN_DAYS", "7"))
        self.block_cooldown_seconds = int(os.getenv("TALENTGRAPH_BOSS_BLOCK_COOLDOWN_SECONDS", "300"))
        self.navigation_timeout_ms = int(os.getenv("TALENTGRAPH_BOSS_NAVIGATION_TIMEOUT_SECONDS", "30")) * 1000
        self.mode = "hybrid"
        self.discovery_ratio = 0.6
        self.revisit_after_hours = 12.0
        self.last_fetch_stats: dict[str, Any] = {}
        self.stop_at_end = False
        self.state_path = Path(os.getenv("TALENTGRAPH_BOSS_STATE_PATH", "data/boss_collection_state.json"))
        self._lock = Lock()

    def configure(
        self,
        *,
        cities: list[str],
        queries: list[str],
        items_per_run: int,
        mode: str = "hybrid",
        discovery_ratio: float = 0.6,
        revisit_after_hours: float = 12,
        stop_at_end: bool = False,
    ) -> None:
        selected = [city for city in cities if city in self.available_cities]
        if "全国" in selected or not selected:
            selected = ["全国"]
        self.cities = {city: self.available_cities[city] for city in selected}
        selected_queries = [query for query in queries if query in self.available_queries]
        self.queries = tuple(selected_queries or self.available_queries)
        self.min_per_run = max(1, items_per_run)
        self.max_per_run = max(1, items_per_run)
        self.mode = mode
        self.discovery_ratio = discovery_ratio
        self.revisit_after_hours = revisit_after_hours
        self.stop_at_end = stop_at_end

    def reset_cursor(self, query: str, city: str) -> None:
        city_code = self.available_cities.get(city, self.available_cities["全国"])
        state = self._load_state()
        key = f"{city_code}|{query}"
        state.setdefault("page_cursors", {})[key] = 1
        state.setdefault("page_signatures", {}).pop(key, None)
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
        with self._lock:
            return self._fetch_locked(max_items)

    def _fetch_locked(self, max_items: int) -> list[dict[str, Any]]:
        state = self._load_state()
        self._prune_seen(state)
        self._assert_not_blocked(state)
        limit = min(max(1, max_items), self.max_per_run)
        output: list[dict[str, Any]] = []
        run_seen: set[str] = set()
        scanned = discovery_candidates = monitor_candidates = 0
        pages_visited = details_visited = parse_failures = 0
        reached_end = False
        end_reason: str | None = None
        search_page = None
        security_paused = False
        discovery_quota = limit if self.mode == "discovery" else 0 if self.mode == "monitor" else round(limit * self.discovery_ratio)
        monitor_quota = limit - discovery_quota
        if self.stop_at_end and self.mode == "hybrid":
            discovery_quota = monitor_quota = limit

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(self.cdp_url, timeout=self.navigation_timeout_ms)
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                # Keep the user's login tab untouched. BOSS may still be redirecting it
                # after authentication, which can interrupt crawler navigation.
                search_page = context.new_page()
                while (
                    len(output) < limit
                    and pages_visited < self.max_pages_per_run
                    and details_visited < self.max_details_per_run
                ):
                    query, city_name, city_code, page_number = self._next_combo(state)
                    combo_key = f"{city_code}|{query}"
                    pages_visited += 1
                    self._reserve_request_slot(state, f"search:{city_code}:{query}:{page_number}")
                    response = self._goto_with_retry(search_page, _search_url(query, city_code, page_number))
                    self._raise_for_status(response.status if response else None, state)
                    html = self._wait_for_render(search_page, "search")
                    if is_challenge_page(html, search_page.url):
                        self._activate_block(state, "BOSS页面要求登录或安全验证")
                        raise RuntimeError("BOSS browser session requires security verification")
                    hits = parse_search_cards(html)
                    if not hits:
                        if is_explicit_empty_result(html):
                            self._reset_combo_cursor(state, query, city_code)
                            reached_end = True
                            end_reason = "explicit_empty_result"
                            if self.stop_at_end:
                                break
                            continue
                        raise RuntimeError("BOSS search page returned no job cards; page structure may have changed")

                    scanned += len(hits)
                    signature = "|".join((_native_id(hit.source_url) or hit.source_url) for hit in hits[:8])
                    signatures = state.setdefault("page_signatures", {}).setdefault(combo_key, [])
                    if self.stop_at_end and signature in signatures:
                        self._reset_combo_cursor(state, query, city_code)
                        reached_end = True
                        end_reason = "repeated_page"
                        break
                    if signature:
                        signatures.append(signature)
                        del signatures[:-3]

                    selected = self._select_hits(
                        hits,
                        state,
                        run_seen,
                        discovery_quota - discovery_candidates,
                        monitor_quota - monitor_candidates,
                    )
                    for hit, source_id, known in selected:
                        if len(output) >= limit:
                            break
                        detail_page = context.new_page()
                        try:
                            self._reserve_request_slot(state, f"detail:{source_id}")
                            response = self._goto_with_retry(detail_page, hit.source_url)
                            details_visited += 1
                            self._raise_for_status(response.status if response else None, state)
                            detail_html = self._wait_for_render(detail_page, "detail")
                            if is_challenge_page(detail_html, detail_page.url):
                                self._activate_block(state, "BOSS详情页要求登录或安全验证")
                                if output:
                                    security_paused = True
                                    reached_end = True
                                    end_reason = "security_pause_after_partial_results"
                                    break
                                raise RuntimeError("BOSS browser session requires security verification")
                            job = parse_job_detail(
                                detail_html,
                                detail_page.url or hit.source_url,
                                hit,
                                search_city=city_name,
                                search_city_code=city_code,
                                search_keyword=query,
                                keyword_category=_keyword_category(query),
                            )
                            output.append(job.to_raw_item(search_page=page_number, known=known))
                            state["seen"][source_id] = datetime.now(UTC).isoformat()
                            discovery_candidates += int(not known)
                            monitor_candidates += int(known)
                        except ValueError:
                            parse_failures += 1
                        finally:
                            detail_page.close()
                        _random_sleep(self.detail_delay_range)
                    if security_paused:
                        break
                    if details_visited >= self.max_details_per_run:
                        reached_end = True
                        end_reason = "detail_batch_limit"
                        break
                    self._save_state(state)
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            raise RuntimeError(f"BOSS Playwright collection failed: {exc}") from exc
        finally:
            if search_page is not None:
                try:
                    search_page.close()
                except PlaywrightError:
                    pass
            self.last_fetch_stats = {
                "scanned": scanned,
                "discovery_candidates": discovery_candidates,
                "monitor_candidates": monitor_candidates,
                "pages_visited": pages_visited,
                "details_visited": details_visited,
                "parse_failures": parse_failures,
                "reached_end": reached_end,
                "end_reason": end_reason,
                "crawler_engine": "boss-job-crawler-playwright",
            }
            self._save_state(state)
        return output

    def _select_hits(
        self,
        hits: list[BossSearchHit],
        state: dict[str, Any],
        run_seen: set[str],
        discovery_remaining: int,
        monitor_remaining: int,
    ) -> list[tuple[BossSearchHit, str, bool]]:
        selected: list[tuple[BossSearchHit, str, bool]] = []
        discovery_selected = monitor_selected = 0
        for hit in hits:
            source_id = _native_id(hit.source_url)
            if (
                not source_id
                or source_id in run_seen
                or not self.include_pattern.search(hit.title)
                or self.exclude_pattern.search(hit.title)
            ):
                continue
            known = source_id in state["seen"]
            if known:
                if self.mode == "discovery" or monitor_selected >= max(0, monitor_remaining):
                    continue
                if not self._due_for_revisit(state["seen"][source_id]):
                    continue
                monitor_selected += 1
            else:
                if self.mode == "monitor" or discovery_selected >= max(0, discovery_remaining):
                    continue
                discovery_selected += 1
            run_seen.add(source_id)
            selected.append((hit, source_id, known))
        return selected

    def _wait_for_render(self, page, expect: str) -> str:
        deadline = time.monotonic() + self.render_wait_seconds
        latest_html = self._read_content_when_stable(page, deadline)
        while time.monotonic() < deadline:
            if is_challenge_page(latest_html, page.url):
                return latest_html
            if expect == "search":
                if parse_search_cards(latest_html) or is_explicit_empty_result(latest_html):
                    return latest_html
            elif "job-sec-text" in latest_html or '"JobPosting"' in latest_html:
                return latest_html
            time.sleep(0.5)
            latest_html = self._read_content_when_stable(page, deadline)
        return latest_html

    def _goto_with_retry(self, page, url: str):
        for attempt in range(3):
            try:
                return page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.navigation_timeout_ms,
                )
            except PlaywrightError as exc:
                message = str(exc).casefold()
                transient = any(token in message for token in (
                    "interrupted by another navigation",
                    "navigation is interrupted",
                    "net::err_aborted",
                ))
                if not transient or attempt == 2:
                    raise
                time.sleep(0.75 * (attempt + 1))
        return None

    @staticmethod
    def _read_content_when_stable(page, deadline: float) -> str:
        while True:
            try:
                return page.content()
            except PlaywrightError as exc:
                message = str(exc).casefold()
                if "page is navigating" not in message and "changing the content" not in message:
                    raise
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)

    def _reserve_request_slot(self, state: dict[str, Any], label: str) -> None:
        while True:
            now = time.time()
            events = [float(item) for item in state.get("request_events", []) if float(item) >= now - 86400]
            waits: list[float] = []
            if events:
                waits.append(events[-1] + self.request_delay_seconds - now)
            hourly = [item for item in events if item >= now - 3600]
            if len(hourly) >= self.max_requests_per_hour:
                waits.append(hourly[0] + 3600 - now)
            if len(events) >= self.max_requests_per_day:
                waits.append(events[0] + 86400 - now)
            wait_seconds = max(waits, default=0.0)
            if wait_seconds <= 0:
                events.append(now)
                state["request_events"] = events
                state["last_request_label"] = label
                self._save_state(state)
                return
            time.sleep(min(wait_seconds, 30.0))

    def _raise_for_status(self, status: int | None, state: dict[str, Any]) -> None:
        if status in RESTRICTED_HTTP_STATUSES:
            self._activate_block(state, f"HTTP {status}")
            raise RuntimeError(f"BOSS access restricted with HTTP {status}")

    def _assert_not_blocked(self, state: dict[str, Any]) -> None:
        remaining = float(state.get("blocked_until", 0)) - time.time()
        if remaining > 0:
            reason = state.get("block_reason") or "access guard"
            raise RuntimeError(f"BOSS crawler paused for {remaining:.0f}s: {reason}")

    def _activate_block(self, state: dict[str, Any], reason: str) -> None:
        state["blocked_until"] = max(float(state.get("blocked_until", 0)), time.time() + self.block_cooldown_seconds)
        state["block_reason"] = reason
        self._save_state(state)

    def _load_state(self) -> dict[str, Any]:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        state.setdefault("seen", {})
        state.setdefault("page_cursors", {})
        state.setdefault("page_signatures", {})
        state.setdefault("combo_index", 0)
        state.setdefault("request_events", [])
        state.setdefault("schema_version", 3)
        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def _next_combo(self, state: dict[str, Any]) -> tuple[str, str, str, int]:
        combos = [(query, city_name, city_code) for city_name, city_code in self.cities.items() for query in self.queries]
        index = int(state.get("combo_index", 0)) % max(1, len(combos))
        query, city_name, city_code = combos[index]
        state["combo_index"] = (index + 1) % len(combos)
        key = f"{city_code}|{query}"
        cursors = state.setdefault("page_cursors", {})
        page_number = max(1, int(cursors.get(key, 1)))
        cursors[key] = page_number + 1
        return query, city_name, city_code, page_number

    def _due_for_revisit(self, timestamp: str) -> bool:
        return _timestamp(timestamp) <= time.time() - self.revisit_after_hours * 3600

    @staticmethod
    def _reset_combo_cursor(state: dict[str, Any], query: str, city_code: str) -> None:
        state.setdefault("page_cursors", {})[f"{city_code}|{query}"] = 1

    def _prune_seen(self, state: dict[str, Any]) -> None:
        cutoff = time.time() - self.seen_cooldown_days * 86400
        state["seen"] = {
            source_id: timestamp
            for source_id, timestamp in state["seen"].items()
            if _timestamp(timestamp) >= cutoff
        }


def _search_url(query: str, city_code: str, page: int) -> str:
    return "https://www.zhipin.com/web/geek/jobs?" + urlencode({
        "query": query,
        "city": city_code,
        "industry": "",
        "position": "",
        "page": page,
    })


def _native_id(url: str) -> str | None:
    match = re.search(r"/job_detail/([^/?#]+?)(?:\.html)?(?:[?#]|$)", url)
    return match.group(1) if match else None


def _keyword_category(query: str) -> str:
    if any(token in query.lower() for token in ("大数据", "flink", "数据平台", "数据治理", "数据仓库", "湖仓", "实时计算")):
        return "大数据"
    if any(token in query.lower() for token in ("物联网", "iot", "嵌入式", "网关", "固件")):
        return "物联网"
    if any(token in query for token in ("智能系统", "机器人", "边缘智能", "自动驾驶")):
        return "智能系统"
    return "人工智能"


def _float_range(name: str, default: tuple[float, float]) -> tuple[float, float]:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        values = tuple(float(value.strip()) for value in raw.split(",", 1))
        return values[0], values[-1]
    except ValueError:
        return default


def _random_sleep(bounds: tuple[float, float]) -> None:
    time.sleep(random.uniform(min(bounds), max(bounds)))


def _timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0
