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
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import urlopen

import websocket

from agents.data.city_catalog import recruitment_city_catalog


class ZhaopinBrowserSource:
    """Browser-backed Zhaopin collector adapted from the team data pipeline."""

    source_id = "zhaopin"
    source_category = "recruitment"
    display_name = "智联招聘"
    access_mode = "browser_assisted_research"

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
    exclude_pattern = re.compile(r"(销售|客服|招生|课程顾问|运营|市场|兼职)")
    search_url = "https://sou.zhaopin.com/"
    available_cities = ("全国", "北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉", "西安", "合肥", "苏州", "长沙")

    def __init__(self) -> None:
        self.available_cities = ("全国", *recruitment_city_catalog().keys())
        self.enabled = os.getenv("TALENTGRAPH_ZHAOPIN_BROWSER_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
        self.cdp_url = os.getenv("TALENTGRAPH_ZHAOPIN_CDP_URL", "http://127.0.0.1:9333").rstrip("/")
        self.headless = os.getenv("TALENTGRAPH_ZHAOPIN_HEADLESS", "1").strip().lower() not in {"0", "false", "no"}
        self.login_wait_seconds = int(os.getenv("TALENTGRAPH_ZHAOPIN_LOGIN_WAIT_SECONDS", "120"))
        self.browser_channel = os.getenv("TALENTGRAPH_ZHAOPIN_BROWSER_CHANNEL", "chrome").strip()
        self.profile_path = Path(os.getenv("TALENTGRAPH_ZHAOPIN_PROFILE_PATH", "data/browser_profiles/zhaopin"))
        self.cookie_path = Path(os.getenv(
            "TALENTGRAPH_ZHAOPIN_COOKIE_PATH",
            "integrations/data-pipeline/agents/data-pipeline/cookies/zhaopin.json",
        ))
        self.state_path = Path(os.getenv("TALENTGRAPH_ZHAOPIN_STATE_PATH", "data/zhaopin_collection_state.json"))
        self.min_per_run = int(os.getenv("TALENTGRAPH_ZHAOPIN_MIN_PER_RUN", "50"))
        self.max_per_run = int(os.getenv("TALENTGRAPH_ZHAOPIN_MAX_PER_RUN", "50"))
        self.page_delay_range = _float_range("TALENTGRAPH_ZHAOPIN_PAGE_DELAY_SECONDS", (0.5, 0.9))
        self.detail_delay_range = _float_range("TALENTGRAPH_ZHAOPIN_DETAIL_DELAY_SECONDS", (0.05, 0.15))
        self.detail_batch_size = int(os.getenv("TALENTGRAPH_ZHAOPIN_DETAIL_BATCH_SIZE", "16"))
        self.max_pages_per_run = int(os.getenv("TALENTGRAPH_ZHAOPIN_MAX_PAGES_PER_RUN", "24"))
        self.seen_cooldown_days = int(os.getenv("TALENTGRAPH_ZHAOPIN_SEEN_COOLDOWN_DAYS", "7"))
        self.mode = "hybrid"
        self.discovery_ratio = 0.5
        self.revisit_after_hours = 24.0
        self.last_fetch_stats: dict[str, Any] = {}
        self.stop_at_end = False
        self._lock = Lock()
        self.cities = ("全国",)

    def configure(
        self, *, cities: list[str], queries: list[str], items_per_run: int,
        mode: str = "hybrid", discovery_ratio: float = 0.5, revisit_after_hours: float = 24,
        stop_at_end: bool = False,
    ) -> None:
        selected = [city for city in cities if city in self.available_cities]
        self.cities = ("全国",) if "全国" in selected or not selected else tuple(selected)
        selected_queries = [query for query in queries if query in self.available_queries]
        self.queries = tuple(selected_queries or self.available_queries)
        self.min_per_run = items_per_run
        self.max_per_run = items_per_run
        self.mode = mode
        self.discovery_ratio = discovery_ratio
        self.revisit_after_hours = revisit_after_hours
        self.stop_at_end = stop_at_end

    def reset_cursor(self, query: str, city: str) -> None:
        state = self._load_state()
        key = f"{city}|{query}"
        state.setdefault("page_cursors", {})[key] = 1
        state.setdefault("page_signatures", {}).pop(key, None)
        state["combo_index"] = 0
        self._save_state(state)

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]:
        del lookback_hours
        if not self.enabled:
            raise RuntimeError("Zhaopin browser collection is disabled")
        with self._lock:
            return self._fetch_locked(max_items)

    def seed_seen(self, source_ids: list[str]) -> None:
        with self._lock:
            state = self._load_state()
            now = datetime.now(UTC).isoformat()
            for source_id in source_ids:
                native_id = source_id.removeprefix(f"{self.source_id}:")
                state["seen"].setdefault(native_id, now)
            self._save_state(state)

    def _fetch_locked(self, max_items: int) -> list[dict[str, Any]]:
        cdp_page = self._find_cdp_page()
        if cdp_page:
            return self._fetch_via_cdp(cdp_page, max_items)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("install Playwright before enabling Zhaopin collection") from exc

        state = self._load_state()
        self._prune_seen(state)
        upper = min(max_items, self.max_per_run)
        lower = min(self.min_per_run, upper)
        limit = random.randint(lower, upper)
        output: list[dict[str, Any]] = []
        run_seen: set[str] = set()
        scanned = discovery_candidates = monitor_candidates = 0
        discovery_quota = limit if self.mode == "discovery" else 0 if self.mode == "monitor" else round(limit * self.discovery_ratio)
        monitor_quota = limit - discovery_quota
        if self.stop_at_end and self.mode == "hybrid":
            discovery_quota = monitor_quota = limit

        self.profile_path.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {
                "user_data_dir": str(self.profile_path.resolve()),
                "headless": self.headless,
                "locale": "zh-CN",
                "viewport": {"width": 1440, "height": 900},
                "args": ["--disable-blink-features=AutomationControlled"],
            }
            if self.browser_channel:
                launch_options["channel"] = self.browser_channel
            context = playwright.chromium.launch_persistent_context(**launch_options)
            try:
                self._inject_team_cookies(context)
                search_page = context.pages[0] if context.pages else context.new_page()
                detail_page = context.new_page()
                empty_pages = 0
                pages_visited = 0
                reached_end = False
                while len(output) < limit and pages_visited < self.max_pages_per_run and empty_pages < 6:
                    pages_visited += 1
                    keyword, city, page_number = self._next_combo(state)
                    city_param = "" if city == "全国" else f"&jl={quote(city)}"
                    url = f"{self.search_url}?kw={quote(keyword)}{city_param}&p={page_number}"
                    search_page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    _random_sleep(self.page_delay_range)
                    if self._is_verification_page(search_page) and not self._wait_for_verification(search_page):
                        raise RuntimeError("Zhaopin browser session requires login or security verification")
                    search_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    search_page.wait_for_timeout(800)
                    cards = search_page.locator("div.joblist-box__item")
                    card_count = cards.count()
                    scanned += card_count
                    if not card_count:
                        self._reset_combo_cursor(state, keyword, city)
                        empty_pages += 1
                        reached_end = True
                        if self.stop_at_end:
                            break
                        continue
                    empty_pages = 0
                    card_values = [cards.nth(index).evaluate(_CARD_EXPRESSION) for index in range(card_count)]
                    signature = "|".join(_job_id(_canonical_job_url(card.get("href"))) for card in card_values[:8])
                    combo_key = f"{city}|{keyword}"
                    signatures = state.setdefault("page_signatures", {}).setdefault(combo_key, [])
                    if self.stop_at_end and signature and signature in signatures:
                        self._reset_combo_cursor(state, keyword, city)
                        reached_end = True
                        break
                    if signature:
                        signatures.append(signature)
                    for card in card_values:
                        title = str(card.get("title") or "").strip()
                        source_url = _canonical_job_url(card.get("href"))
                        source_id = _job_id(source_url)
                        if not source_id or source_id in run_seen or not self.include_pattern.search(title) or self.exclude_pattern.search(title):
                            continue
                        known = source_id in state["seen"]
                        if known and (self.mode == "discovery" or monitor_candidates >= monitor_quota or not self._due_for_revisit(state["seen"][source_id])):
                            continue
                        if not known and (self.mode == "monitor" or discovery_candidates >= discovery_quota):
                            continue
                        run_seen.add(source_id)
                        detail = self._fetch_detail(detail_page, source_url)
                        if len(detail["content"]) < 80:
                            continue
                        state["seen"][source_id] = datetime.now(UTC).isoformat()
                        if known:
                            monitor_candidates += 1
                        else:
                            discovery_candidates += 1
                        location_parts = [part.strip() for part in str(card.get("location") or "").split("·") if part.strip()]
                        salary_min, salary_max, salary_months = _parse_salary(str(card.get("salary") or ""))
                        output.append({
                            "source_id": source_id,
                            "source_platform": self.source_id,
                            "source_url": source_url,
                            "title": detail.get("title") or title,
                            "company": card.get("company"),
                            "content": detail["content"],
                            "raw_content": detail["content"],
                            "city": location_parts[0] if location_parts else None,
                            "district": location_parts[1] if len(location_parts) > 1 else None,
                            "experience": card.get("experience"),
                            "education": card.get("education"),
                            "tags": list(dict.fromkeys((card.get("tags") or []) + detail.get("tags", []))),
                            "salary_min_k": salary_min,
                            "salary_max_k": salary_max,
                            "salary_months": salary_months,
                            "published_at": datetime.now(UTC),
                            "employment_type": "full_time",
                            "collection_mode": "live",
                            "metadata": {
                                "browser_assisted": True,
                                "research_collection": True,
                                "team_pipeline_adapter": True,
                                "query": keyword,
                                "search_city": city,
                                "search_page": page_number,
                                "salary_raw": card.get("salary"),
                            },
                        })
                        if len(output) >= limit:
                            break
                        _random_sleep(self.detail_delay_range)
                    self._save_state(state)
            finally:
                self.last_fetch_stats = {"scanned": scanned, "discovery_candidates": discovery_candidates, "monitor_candidates": monitor_candidates, "reached_end": reached_end}
                self._save_state(state)
                context.close()
        return output

    def _fetch_via_cdp(self, page: dict[str, Any], max_items: int) -> list[dict[str, Any]]:
        debugger_port = urlsplit(page["webSocketDebuggerUrl"]).port or 9333
        socket = websocket.create_connection(
            page["webSocketDebuggerUrl"], timeout=30, origin=f"http://127.0.0.1:{debugger_port}"
        )
        client = _CdpClient(socket)
        authenticated = client.evaluate(
            "document.cookie.split(';').some(item=>item.trim().startsWith('at='))"
            "&&document.cookie.split(';').some(item=>item.trim().startsWith('rt='))"
        )
        if not authenticated:
            socket.close()
            raise RuntimeError("Zhaopin dedicated Chrome requires account login")
        state = self._load_state()
        self._prune_seen(state)
        upper = min(max_items, self.max_per_run)
        lower = min(self.min_per_run, upper)
        limit = random.randint(lower, upper)
        output: list[dict[str, Any]] = []
        run_seen: set[str] = set()
        scanned = discovery_candidates = monitor_candidates = 0
        discovery_quota = limit if self.mode == "discovery" else 0 if self.mode == "monitor" else round(limit * self.discovery_ratio)
        monitor_quota = limit - discovery_quota
        if self.stop_at_end and self.mode == "hybrid":
            discovery_quota = monitor_quota = limit
        empty_pages = 0
        pages_visited = 0
        reached_end = False
        end_reason: str | None = None
        repeated_page_confirmations = 0
        try:
            while len(output) < limit and pages_visited < self.max_pages_per_run and empty_pages < 6:
                pages_visited += 1
                keyword, city, page_number = self._next_combo(state)
                combo_key = f"{city}|{keyword}"
                city_param = "" if city == "全国" else f"&jl={quote(city)}"
                url = f"{self.search_url}?kw={quote(keyword)}{city_param}&p={page_number}"
                client.call("Page.navigate", {"url": url})
                _random_sleep(self.page_delay_range)
                page_state = _wait_for_cards(client, "div.joblist-box__item")
                page_marker = f"{page_state.get('title', '')} {page_state.get('url', '')}".lower()
                if any(token in page_marker for token in ("security", "verification", "captcha", "验证")) and not page_state.get("cards"):
                    raise RuntimeError("Zhaopin dedicated Chrome requires security verification")
                if not page_state.get("cards"):
                    empty_pages += 1
                    if self.stop_at_end:
                        if empty_pages < 2:
                            state.setdefault("page_cursors", {})[combo_key] = page_number
                            continue
                        self._reset_combo_cursor(state, keyword, city)
                        reached_end = True
                        end_reason = "empty_page_confirmed"
                        break
                    continue
                cards = client.evaluate(_CDP_CARD_EXPRESSION) or []
                empty_pages = 0
                signature = "|".join(_job_id(_canonical_job_url(card.get("href"))) for card in cards[:8])
                signatures = state.setdefault("page_signatures", {}).setdefault(combo_key, [])
                if self.stop_at_end and signature and signature in signatures:
                    repeated_page_confirmations += 1
                    if repeated_page_confirmations < 2:
                        state.setdefault("page_cursors", {})[combo_key] = page_number
                        continue
                    self._reset_combo_cursor(state, keyword, city)
                    reached_end = True
                    end_reason = "repeated_page_confirmed"
                    break
                repeated_page_confirmations = 0
                if signature:
                    signatures.append(signature)
                scanned += len(cards)
                selected: list[tuple[dict[str, Any], str, str, bool]] = []
                selected_discovery = selected_monitor = 0
                for card in cards:
                    title = str(card.get("title") or "").strip()
                    source_url = _canonical_job_url(card.get("href"))
                    source_id = _job_id(source_url)
                    if not source_id or source_id in run_seen or not self.include_pattern.search(title) or self.exclude_pattern.search(title):
                        continue
                    known = source_id in state["seen"]
                    if known and (self.mode == "discovery" or monitor_candidates + selected_monitor >= monitor_quota or not self._due_for_revisit(state["seen"][source_id])):
                        continue
                    if not known and (self.mode == "monitor" or discovery_candidates + selected_discovery >= discovery_quota):
                        continue
                    run_seen.add(source_id)
                    selected.append((card, source_url, source_id, known))
                    selected_monitor += int(known)
                    selected_discovery += int(not known)
                details: dict[str, dict[str, Any]] = {}
                for offset in range(0, len(selected), self.detail_batch_size):
                    urls = [item[1] for item in selected[offset:offset + self.detail_batch_size]]
                    for detail in client.evaluate(_details_expression(urls), await_promise=True) or []:
                        details[str(detail.get("url") or "")] = detail
                    _random_sleep(self.detail_delay_range)
                for card, source_url, source_id, known in selected:
                    detail = details.get(source_url, {})
                    content = str(detail.get("content") or "").strip()
                    if len(content) < 80:
                        continue
                    state["seen"][source_id] = datetime.now(UTC).isoformat()
                    if known:
                        monitor_candidates += 1
                    else:
                        discovery_candidates += 1
                    location_parts = [part.strip() for part in str(card.get("location") or "").split("·") if part.strip()]
                    salary_min, salary_max, salary_months = _parse_salary(str(card.get("salary") or ""))
                    output.append({
                        "source_id": source_id, "source_platform": self.source_id, "source_url": source_url,
                        "title": detail.get("title") or title, "company": card.get("company"),
                        "content": content, "raw_content": content,
                        "city": location_parts[0] if location_parts else None,
                        "district": location_parts[1] if len(location_parts) > 1 else None,
                        "experience": card.get("experience"), "education": card.get("education"),
                        "tags": list(dict.fromkeys((card.get("tags") or []) + (detail.get("tags") or []))),
                        "salary_min_k": salary_min, "salary_max_k": salary_max, "salary_months": salary_months,
                        "published_at": datetime.now(UTC), "employment_type": "full_time", "collection_mode": "live",
                        "metadata": {
                            "browser_assisted": True, "research_collection": True,
                            "team_pipeline_adapter": True, "cdp_session": True,
                            "query": keyword, "search_city": city, "search_page": page_number, "salary_raw": card.get("salary"),
                        },
                    })
                    if len(output) >= limit:
                        break
                    _random_sleep(self.detail_delay_range)
                self._save_state(state)
        finally:
            self.last_fetch_stats = {
                "scanned": scanned, "discovery_candidates": discovery_candidates,
                "monitor_candidates": monitor_candidates, "reached_end": reached_end,
                "end_reason": end_reason,
            }
            self._save_state(state)
            socket.close()
        return output

    def _find_cdp_page(self) -> dict[str, Any] | None:
        urls = [self.cdp_url]
        try:
            port = int((self.profile_path / "DevToolsActivePort").read_text(encoding="utf-8").splitlines()[0])
            urls.append(f"http://127.0.0.1:{port}")
        except (OSError, ValueError, IndexError):
            pass
        for base_url in dict.fromkeys(urls):
            try:
                with urlopen(f"{base_url}/json/list", timeout=2) as response:
                    pages = json.load(response)
            except Exception:
                continue
            page = next(
                (item for item in pages if item.get("type") == "page" and "zhaopin.com" in item.get("url", "")),
                None,
            )
            if page:
                return page
        return None

    def _fetch_detail(self, page, source_url: str) -> dict[str, Any]:
        page.goto(source_url, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(900)
        if self._is_verification_page(page):
            return {"title": "", "content": "", "tags": []}
        values = page.locator(
            ".describtion-card__detail-content, .describtion__detail-content, .job-detail, .job-detail-content, "
            "[class*='job-detail'], [class*='describtion__detail']"
        ).all_inner_texts()
        content = max((value.strip() for value in values if value.strip()), key=len, default="")
        if len(content) < 80:
            body_text = page.locator("body").inner_text().strip()
            content = body_text if len(body_text) < 12_000 else body_text[:12_000]
        tags = page.locator("[class*='job'] [class*='tag'] span, [class*='job'] [class*='tag'] li").all_inner_texts()
        title_values = page.locator("h1").all_inner_texts()
        return {
            "title": next((value.strip() for value in title_values if value.strip()), ""),
            "content": content,
            "tags": [value.strip() for value in tags if 1 < len(value.strip()) <= 40][:30],
        }

    def _inject_team_cookies(self, context) -> None:
        if not self.cookie_path.exists():
            return
        try:
            payload = json.loads(self.cookie_path.read_text(encoding="utf-8"))
            raw_cookies = payload.get("cookies", payload)
            if isinstance(raw_cookies, dict):
                cookies = [
                    {"name": str(name), "value": str(value), "domain": ".zhaopin.com", "path": "/"}
                    for name, value in raw_cookies.items() if value
                ]
            elif isinstance(raw_cookies, list):
                cookies = raw_cookies
            else:
                cookies = []
            if cookies:
                context.add_cookies(cookies)
        except (OSError, ValueError, TypeError):
            return

    @staticmethod
    def _is_verification_page(page) -> bool:
        title = page.title().lower()
        url = page.url.lower()
        return any(token in f"{title} {url}" for token in ("captcha", "verification", "security", "验证"))

    def _wait_for_verification(self, page) -> bool:
        if self.headless:
            return False
        deadline = time.monotonic() + self.login_wait_seconds
        while time.monotonic() < deadline:
            page.wait_for_timeout(2_000)
            if not self._is_verification_page(page):
                return True
        return False

    def _load_state(self) -> dict[str, Any]:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        state.setdefault("queue", [])
        state.setdefault("seen", {})
        if int(state.get("schema_version", 0)) < 2:
            state["schema_version"] = 2
            state["seen"] = {}
            state["page_cursors"] = {}
            state["combo_index"] = 0
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
        page = max(1, int(cursors.get(key, 1)))
        cursors[key] = page + 1
        state["cycle_started_at"] = state.get("cycle_started_at") or datetime.now(UTC).isoformat()
        return str(query), str(city), page

    def _due_for_revisit(self, timestamp: str) -> bool:
        return _timestamp(timestamp) <= datetime.now(UTC).timestamp() - self.revisit_after_hours * 3600

    @staticmethod
    def _reset_combo_cursor(state: dict[str, Any], query: str, city: str) -> None:
        state.setdefault("page_cursors", {})[f"{city}|{query}"] = 1

    def _prune_seen(self, state: dict[str, Any]) -> None:
        cutoff = datetime.now(UTC).timestamp() - self.seen_cooldown_days * 86400
        state["seen"] = {
            source_id: timestamp for source_id, timestamp in state["seen"].items()
            if _timestamp(timestamp) >= cutoff
        }


_CARD_EXPRESSION = r"""
(card) => {
  const text = (selector) => card.querySelector(selector)?.innerText?.trim() || '';
  const lines = (card.querySelector('div.jobinfo')?.innerText || '').split('\n').map(x => x.trim()).filter(Boolean);
  const isSalary = x => /\d/.test(x) && /(万|千|元|K|k|薪|[-~－])/.test(x);
  const isLocation = x => /[·•．]/.test(x) && !isSalary(x) && x.length < 50;
  return {
    title: text('a.jobinfo__name'),
    href: card.querySelector('a.jobinfo__name')?.href || '',
    salary: text('p.jobinfo__salary'),
    company: text('a.companyinfo__name'),
    location: lines.find(isLocation) || '',
    experience: lines.find(x => /\d+[-~]\d+年|\d+年以[上下]|经验不限|应届|在校/.test(x)) || '',
    education: lines.find(x => /本科|硕士|博士|大专|中专|高中|学历不限/.test(x)) || '',
    tags: [...card.querySelectorAll('div.jobinfo__tag span, div.jobinfo__tag')]
      .map(x => x.innerText.trim()).filter(x => x && x.length <= 40)
  };
}
"""

_CDP_CARD_EXPRESSION = r"""
[...document.querySelectorAll('div.joblist-box__item')].map(card => {
  const text = selector => card.querySelector(selector)?.innerText?.trim() || '';
  const lines = (card.querySelector('div.jobinfo')?.innerText || '').split('\n').map(x => x.trim()).filter(Boolean);
  const isSalary = x => /\d/.test(x) && /(万|千|元|K|k|薪|[-~－])/.test(x);
  const isLocation = x => /[·•．]/.test(x) && !isSalary(x) && x.length < 50;
  return {
    title: text('a.jobinfo__name'), href: card.querySelector('a.jobinfo__name')?.href || '',
    salary: text('p.jobinfo__salary'), company: text('a.companyinfo__name'),
    location: lines.find(isLocation) || '',
    experience: lines.find(x => /\d+[-~]\d+年|\d+年以[上下]|经验不限|应届|在校/.test(x)) || '',
    education: lines.find(x => /本科|硕士|博士|大专|中专|高中|学历不限/.test(x)) || '',
    tags: [...card.querySelectorAll('div.jobinfo__tag span, div.jobinfo__tag')]
      .map(x => x.innerText.trim()).filter(x => x && x.length <= 40)
  };
})
"""


def _details_expression(urls: list[str]) -> str:
    return f"""
Promise.all({json.dumps(urls)}.map(async url => {{
  try {{
    const response = await fetch(url, {{credentials:'include'}});
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const candidates = [...doc.querySelectorAll(
      ".describtion-card__detail-content, .describtion__detail-content, .job-detail, .job-detail-content, [class*='job-detail'], [class*='describtion__detail']"
    )].map(node => node.innerText.trim()).filter(Boolean).sort((a,b) => b.length-a.length);
    return {{
      url,
      status: response.status,
      title: doc.querySelector('h1')?.innerText?.trim() || '',
      content: candidates[0] || '',
      tags: [...doc.querySelectorAll("[class*='job'] [class*='tag'] span, [class*='job'] [class*='tag'] li")]
        .map(node => node.innerText.trim()).filter(text => text && text.length <= 40).slice(0,30)
    }};
  }} catch (error) {{
    return {{url, status: 0, title: '', content: '', tags: [], error: String(error)}};
  }}
}}))
"""


class _CdpClient:
    def __init__(self, socket) -> None:
        self.socket = socket
        self.sequence = 0

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.sequence += 1
        request_id = self.sequence
        self.socket.send(json.dumps({"id": request_id, "method": method, "params": params}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"].get("message", "CDP request failed"))
                return message.get("result", {})

    def evaluate(self, expression: str, *, await_promise: bool = False) -> Any:
        response = self.call("Runtime.evaluate", {
            "expression": expression, "awaitPromise": await_promise, "returnByValue": True,
        })
        if response.get("exceptionDetails"):
            description = response.get("result", {}).get("description") or response["exceptionDetails"].get("text")
            raise RuntimeError(f"Zhaopin page evaluation failed: {description}")
        return response.get("result", {}).get("value")


def _canonical_job_url(value: Any) -> str:
    url = str(value or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = "https://www.zhaopin.com" + url
    if not url.startswith(("http://", "https://")):
        return ""
    parts = urlsplit(url)
    return urlunsplit(("https", parts.netloc.lower(), parts.path, "", ""))


def _job_id(url: str) -> str:
    match = re.search(r"/jobdetail/([^/.?]+)", url, re.IGNORECASE)
    return match.group(1) if match else ""


def _parse_salary(value: str) -> tuple[int | None, int | None, int]:
    text = value.replace(" ", "")
    numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", text)[:2]]
    if not numbers:
        return None, None, 12
    multiplier = 1 if "万" in text else 0.001 if "元" in text else 1
    if "/年" in text or "年薪" in text:
        multiplier /= 12
    values = [max(0, round(number * multiplier)) for number in numbers]
    months_match = re.search(r"(\d+)薪", text)
    months = int(months_match.group(1)) if months_match else 12
    return values[0], values[-1], months


def _float_range(name: str, default: tuple[float, float]) -> tuple[float, float]:
    try:
        values = [float(value.strip()) for value in os.getenv(name, "").split(",") if value.strip()]
        return (values[0], values[-1]) if values else default
    except ValueError:
        return default


def _random_sleep(bounds: tuple[float, float]) -> None:
    time.sleep(random.uniform(min(bounds), max(bounds)))


def _wait_for_cards(client: _CdpClient, selector: str, timeout: float = 8.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        state = client.evaluate(
            f"({{title:document.title,url:location.href,cards:document.querySelectorAll({json.dumps(selector)}).length,"
            "authenticated:document.cookie.split(';').some(item=>item.trim().startsWith('at='))"
            "&&document.cookie.split(';').some(item=>item.trim().startsWith('rt='))})"
        ) or {}
        if state.get("cards"):
            return state
        time.sleep(0.2)
    return state


def _timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0
