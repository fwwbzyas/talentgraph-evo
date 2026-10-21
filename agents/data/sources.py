from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from time import perf_counter, sleep
from typing import Any, Protocol

import httpx

from agents.data.boss_browser import BossBrowserSource
from agents.data.job51_browser import Job51BrowserSource
from agents.data.liepin_browser import LiepinBrowserSource
from agents.data.zhaopin_browser import ZhaopinBrowserSource


USER_AGENT = "TalentGraphEvo/0.2 (+public-data-collection; contact=enterprise-admin)"


class DataSource(Protocol):
    source_id: str
    source_category: str
    display_name: str
    access_mode: str

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]: ...


class HttpDataSource:
    source_id = ""
    source_category = ""
    display_name = ""
    access_mode = "public_api"
    enabled = True

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=httpx.Timeout(25, connect=10),
            follow_redirects=True,
        )

    def _get_json(self, url: str, **kwargs) -> Any:
        response = self.client.get(url, **kwargs)
        response.raise_for_status()
        return response.json()


class RemoteOkSource(HttpDataSource):
    source_id = "remoteok"
    source_category = "community_signal"
    display_name = "Remote OK"

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]:
        data = self._get_json("https://remoteok.com/api")
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        items = []
        for raw in data if isinstance(data, list) else []:
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("position"):
                continue
            published = _as_datetime(raw.get("date") or raw.get("epoch"))
            if published and published < cutoff:
                continue
            items.append({
                "source_id": str(raw["id"]),
                "source_type": "developer_community",
                "source_platform": self.source_id,
                "source_url": raw.get("url") or f"https://remoteok.com/remote-jobs/{raw.get('slug', raw['id'])}",
                "title": raw.get("position"),
                "company": raw.get("company"),
                "content": raw.get("description"),
                "city": raw.get("location") or "Remote",
                "tags": raw.get("tags") or [],
                "salary_min": raw.get("salary_min"),
                "salary_max": raw.get("salary_max"),
                "salary_period": "annual",
                "currency": "USD",
                "published_at": published,
                "employment_type": "full_time",
                "remote": True,
                "collection_mode": "live",
                "metadata": {"source_logo": raw.get("company_logo"), "original_slug": raw.get("slug")},
            })
            if len(items) >= max_items:
                break
        return items


class ArbeitnowSource(HttpDataSource):
    source_id = "arbeitnow"
    source_category = "community_signal"
    display_name = "Arbeitnow"

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        output: list[dict[str, Any]] = []
        page = 1
        while len(output) < max_items and page <= 3:
            payload = self._get_json("https://www.arbeitnow.com/api/job-board-api", params={"page": page})
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            if not rows:
                break
            for raw in rows:
                published = _as_datetime(raw.get("created_at"))
                if published and published < cutoff:
                    continue
                output.append({
                    "source_id": raw.get("slug"),
                    "source_type": "developer_community",
                    "source_platform": self.source_id,
                    "source_url": raw.get("url"),
                    "title": raw.get("title"),
                    "company": raw.get("company_name"),
                    "content": raw.get("description"),
                    "city": raw.get("location"),
                    "tags": raw.get("tags") or [],
                    "published_at": published,
                    "employment_type": ", ".join(raw.get("job_types") or []) or "full_time",
                    "remote": bool(raw.get("remote")),
                    "collection_mode": "live",
                    "metadata": {"original_slug": raw.get("slug")},
                })
                if len(output) >= max_items:
                    break
            page += 1
        return output


class HackerNewsSource(HttpDataSource):
    source_id = "hackernews"
    source_category = "community_signal"
    display_name = "Hacker News"
    access_mode = "public_search_api"
    queries = {
        "人工智能": "AI engineer LLM agent",
        "大数据": "data engineering Flink Spark",
        "智能系统": "robotics autonomous systems",
        "物联网": "IoT embedded edge computing",
    }

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]:
        cutoff = int((datetime.now(UTC) - timedelta(hours=lookback_hours)).timestamp())
        each = max(2, max_items // len(self.queries))
        output: list[dict[str, Any]] = []
        for domain, query in self.queries.items():
            payload = self._get_json(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"query": query, "tags": "(story,comment)", "numericFilters": f"created_at_i>{cutoff}", "hitsPerPage": each},
            )
            for raw in payload.get("hits", []):
                object_id = raw.get("objectID")
                output.append({
                    "signal_id": object_id,
                    "source_platform": self.source_id,
                    "source_type": "forum",
                    "source_url": raw.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                    "title": raw.get("title") or raw.get("story_title") or f"Hacker News discussion {object_id}",
                    "content": raw.get("story_text") or raw.get("comment_text") or raw.get("title"),
                    "author": raw.get("author"),
                    "published_at": raw.get("created_at"),
                    "tags": [],
                    "domain_hint": domain,
                    "engagement": {"points": raw.get("points") or 0, "comments": raw.get("num_comments") or 0},
                    "metadata": {"story_id": raw.get("story_id"), "auxiliary_only": True},
                })
                if len(output) >= max_items:
                    return output
        return output


class StackOverflowSource(HttpDataSource):
    source_id = "stackoverflow"
    source_category = "community_signal"
    display_name = "Stack Overflow"
    tags = {
        "人工智能": "artificial-intelligence",
        "大数据": "apache-flink",
        "智能系统": "robotics",
        "物联网": "iot",
    }

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]:
        cutoff = int((datetime.now(UTC) - timedelta(hours=lookback_hours)).timestamp())
        each = max(2, max_items // len(self.tags))
        output: list[dict[str, Any]] = []
        for domain, tag in self.tags.items():
            payload = self._get_json(
                "https://api.stackexchange.com/2.3/questions",
                params={
                    "site": "stackoverflow", "tagged": tag, "fromdate": cutoff, "sort": "activity",
                    "order": "desc", "pagesize": each, "filter": "withbody",
                },
            )
            for raw in payload.get("items", []):
                output.append({
                    "signal_id": raw.get("question_id"),
                    "source_platform": self.source_id,
                    "source_type": "developer_community",
                    "source_url": raw.get("link"),
                    "title": raw.get("title"),
                    "content": raw.get("body"),
                    "author": (raw.get("owner") or {}).get("display_name"),
                    "published_at": raw.get("creation_date"),
                    "tags": raw.get("tags") or [tag],
                    "domain_hint": domain,
                    "engagement": {
                        "score": raw.get("score") or 0,
                        "answers": raw.get("answer_count") or 0,
                        "views": raw.get("view_count") or 0,
                    },
                    "metadata": {"is_answered": raw.get("is_answered", False), "auxiliary_only": True},
                })
                if len(output) >= max_items:
                    return output
        return output


class GitHubSource(HttpDataSource):
    source_id = "github"
    source_category = "community_signal"
    display_name = "GitHub"
    access_mode = "public_search_api"
    queries = {
        "人工智能": "llm agent rag stars:>50",
        "大数据": "flink spark data-platform stars:>50",
        "智能系统": "robotics autonomous-system cloud-native stars:>50",
        "物联网": "iot embedded edge-computing mqtt stars:>50",
    }

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        each = max(2, min(30, max_items // len(self.queries) + 2))
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for domain, query in self.queries.items():
            payload = None
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    payload = self._get_json(
                        "https://api.github.com/search/repositories",
                        headers=headers,
                        params={"q": query, "sort": "updated", "order": "desc", "per_page": each, "page": 1},
                    )
                    break
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    if attempt < 2:
                        sleep(1.5 * (attempt + 1))
            if payload is None:
                if not output:
                    raise RuntimeError("GitHub API unavailable after 3 attempts") from last_error
                continue
            for raw in payload.get("items", []):
                repo_id = str(raw.get("id") or "")
                updated_at = _as_datetime(raw.get("updated_at"))
                if not repo_id or repo_id in seen or raw.get("archived") or raw.get("fork"):
                    continue
                if updated_at and updated_at < cutoff:
                    continue
                seen.add(repo_id)
                topics = [str(topic) for topic in raw.get("topics") or []]
                language = str(raw.get("language") or "").strip()
                description = str(raw.get("description") or "").strip()
                output.append({
                    "signal_id": repo_id,
                    "source_platform": self.source_id,
                    "source_type": "developer_community",
                    "source_url": raw.get("html_url"),
                    "title": raw.get("full_name") or raw.get("name"),
                    "content": "\n".join(part for part in (
                        description,
                        f"Primary language: {language}" if language else "",
                        f"Topics: {', '.join(topics)}" if topics else "",
                    ) if part),
                    "author": (raw.get("owner") or {}).get("login"),
                    "published_at": updated_at,
                    "tags": list(dict.fromkeys(([language] if language else []) + topics))[:30],
                    "domain_hint": domain,
                    "engagement": {
                        "stars": raw.get("stargazers_count") or 0,
                        "forks": raw.get("forks_count") or 0,
                        "watchers": raw.get("watchers_count") or 0,
                        "open_issues": raw.get("open_issues_count") or 0,
                    },
                    "metadata": {
                        "auxiliary_only": True,
                        "evidence_role": "auxiliary",
                        "evidence_weight": 0.25,
                        "signal_kind": "github_repository",
                        "matched_query": query,
                        "license": (raw.get("license") or {}).get("spdx_id"),
                        "default_branch": raw.get("default_branch"),
                    },
                })
                if len(output) >= max_items:
                    return output
        return output


class AuthorizedRecruitmentSource(HttpDataSource):
    source_category = "recruitment"
    access_mode = "authorization_required"

    def __init__(
        self,
        source_id: str,
        display_name: str,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(client)
        self.source_id = source_id
        self.display_name = display_name
        prefix = f"TALENTGRAPH_{source_id.upper()}"
        self.feed_url = os.getenv(f"{prefix}_FEED_URL", "").strip()
        self.token = os.getenv(f"{prefix}_FEED_TOKEN", "").strip()
        self.token_header = os.getenv(f"{prefix}_TOKEN_HEADER", "Authorization").strip()
        self.enabled = bool(self.feed_url)
        self.access_mode = "authorized_feed" if self.enabled else "authorization_required"

    def fetch(self, *, max_items: int, lookback_hours: int) -> list[dict[str, Any]]:
        if not self.enabled:
            raise RuntimeError(
                f"{self.display_name} requires an authorized API/feed agreement; "
                f"configure TALENTGRAPH_{self.source_id.upper()}_FEED_URL"
            )
        headers = {"Accept": "application/json"}
        if self.token:
            headers[self.token_header] = (
                f"Bearer {self.token}" if self.token_header.lower() == "authorization" else self.token
            )
        payload = self._get_json(
            self.feed_url,
            headers=headers,
            params={"limit": max_items, "lookback_hours": lookback_hours},
        )
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        output: list[dict[str, Any]] = []
        for raw in _extract_feed_rows(payload):
            published = _as_datetime(_pick(raw, "published_at", "publishTime", "updateTime", "date"))
            if published and published < cutoff:
                continue
            normalized = self._normalize(raw, published)
            if normalized["source_id"] and normalized["title"]:
                output.append(normalized)
            if len(output) >= max_items:
                break
        return output

    def _normalize(self, raw: dict[str, Any], published: datetime | None) -> dict[str, Any]:
        source_id = _pick(raw, "source_id", "jobId", "job_id", "positionId", "position_id", "id")
        url = _pick(raw, "source_url", "jobUrl", "job_url", "positionUrl", "url", "link")
        company = _pick(raw, "company", "companyName", "company_name", "brandName", "brand_name")
        if isinstance(company, dict):
            company = _pick(company, "name", "companyName", "shortName")
        content = _pick(raw, "content", "jobDescription", "job_description", "description", "detail", "jobDetail")
        responsibilities = _pick(raw, "responsibilities", "jobResponsibilities", "job_responsibilities", default=[])
        requirements = _pick(raw, "requirements", "jobRequirements", "job_requirements", default=[])
        if not content:
            content = "\n".join(_as_text(value) for value in (responsibilities, requirements) if value)
        salary = _pick(raw, "salary", "salaryDesc", "salary_desc")
        return {
            "source_id": str(source_id or ""),
            "source_platform": self.source_id,
            "source_url": str(url or ""),
            "title": _pick(raw, "title", "jobName", "job_name", "positionName", "position_name"),
            "company": company,
            "content": _as_text(content),
            "city": _pick(raw, "city", "cityName", "city_name", "workCity", "work_city"),
            "district": _pick(raw, "district", "districtName", "area", "businessDistrict"),
            "address": _pick(raw, "address", "workAddress", "work_address"),
            "tags": _as_list(_pick(raw, "tags", "skills", "skillTags", "jobLabels", default=[])),
            "salary": salary,
            "salary_min": _pick(raw, "salary_min", "salaryMin", "minSalary"),
            "salary_max": _pick(raw, "salary_max", "salaryMax", "maxSalary"),
            "salary_period": _pick(raw, "salary_period", "salaryPeriod", default="monthly"),
            "currency": _pick(raw, "currency", default="CNY"),
            "experience": _pick(raw, "experience", "experienceName", "workExperience"),
            "education": _pick(raw, "education", "degreeName", "degree", "educationName"),
            "published_at": published,
            "employment_type": _pick(raw, "employment_type", "jobType", "job_type", default="full_time"),
            "collection_mode": "live",
            "metadata": {
                "authorized_feed": True,
                "source_record_keys": sorted(str(key) for key in raw.keys())[:80],
            },
        }


def default_sources(client: httpx.Client | None = None) -> dict[str, DataSource]:
    sources = [
        RemoteOkSource(client), ArbeitnowSource(client), HackerNewsSource(client), StackOverflowSource(client), GitHubSource(client),
        BossBrowserSource(),
        ZhaopinBrowserSource(),
        Job51BrowserSource(),
        LiepinBrowserSource(),
    ]
    return {source.source_id: source for source in sources}


def source_catalog(sources: dict[str, DataSource]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": source.source_id,
            "name": source.display_name,
            "source_category": source.source_category,
            "access_mode": source.access_mode,
            "enabled": getattr(source, "enabled", True),
            "configuration": getattr(
                source,
                "configuration",
                "ready" if getattr(source, "enabled", True)
                else f"set TALENTGRAPH_{source.source_id.upper()}_FEED_URL after authorization",
            ),
        }
        for source in sources.values()
    ]


def timed_fetch(source: DataSource, *, max_items: int, lookback_hours: int) -> tuple[list[dict[str, Any]], int]:
    started = perf_counter()
    items = source.fetch(max_items=max_items, lookback_hours=lookback_hours)
    return items, round((perf_counter() - started) * 1000)


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, UTC)
        except (ValueError, OSError):
            return None
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _extract_feed_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "jobs", "results", "records", "list", "rows"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return _extract_feed_rows(data)
    return []


def _pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return default


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return "\n".join(str(item) for item in value.values() if item)
    return str(value or "")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return []
