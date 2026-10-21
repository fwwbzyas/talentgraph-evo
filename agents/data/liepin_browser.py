from __future__ import annotations

import os
import random
import re
import time
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from lxml import html as lxml_html

from agents.data.supplemental_recruitment import (
    CollectionRiskControlError,
    SupplementalBrowserSource,
    mask_contacts,
    parse_experience,
    parse_monthly_salary,
    split_location,
)


BASE_URL = "https://www.liepin.com"
MOBILE_BASE_URL = "https://m.liepin.com"
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
)
LIEPIN_CITY_CODES = {
    "北京": "010", "上海": "020", "广州": "050020", "深圳": "050090",
    "南京": "060020", "苏州": "060080", "杭州": "070020", "合肥": "080020",
    "武汉": "170020", "长沙": "180020", "西安": "270020", "成都": "280020",
}
LIEPIN_MOBILE_CITY_SLUGS = {
    "北京": "bj", "上海": "sh", "广州": "gz", "深圳": "sz",
    "南京": "nj", "苏州": "suzhou", "杭州": "hz", "合肥": "hefei",
    "武汉": "wuhan", "长沙": "changsha", "西安": "xian", "成都": "cd",
}
# Public, server-rendered Liepin topic pages are the bounded fallback when the
# mobile keyword route returns only its client-side application shell.  They
# contain normal public job-card links; every row still passes the same title,
# city and governance filters as the keyword route.
LIEPIN_PUBLIC_TOPIC_URLS = (
    "https://m.liepin.com/zpzndhsfgcs3nv2/",  # intelligent-dialogue algorithms
    "https://m.liepin.com/zpgjslamgcs1f6o/",  # SLAM / robotics algorithms
    "https://m.liepin.com/zpyfjsgcs5x4h/",  # computing R&D
    "https://m.liepin.com/zpjfgwsfj5b2/",  # algorithm-oriented roles
)
_TITLE_RE = re.compile(r"【(?P<city>\S+?)\s+(?P<title>.+?)招聘】-(?P<company>.+?)招聘信息-猎聘")
_SALARY_RE = re.compile(r"薪资(?P<salary>[^,,，]+)")
_EXPERIENCE_RE = re.compile(r"(?P<experience>\d+\s*-\s*\d+年|\d+年以上|经验不限|\d+年)(?:相关)?经验")
_SCALE_RE = re.compile(r"公司规模(?P<scale>[^,,，]+)")
_EDUCATION_WORDS = ("统招本科", "统招硕士", "统招大专", "本科", "硕士", "博士", "MBA", "EMBA", "大专", "学历不限", "中专/中技", "高中")


def canonical_liepin_url(value: Any) -> tuple[str, str]:
    url = str(value or "").strip()
    if url.startswith("/"):
        url = BASE_URL + url
    parts = urlsplit(url)
    match = re.search(r"/(?:job|a)/(\d+)\.shtml", parts.path)
    canonical = urlunsplit(("https", parts.netloc.lower(), parts.path, "", "")) if parts.netloc else url.split("?", 1)[0]
    return canonical, match.group(1) if match else ""


def liepin_public_topic_urls(keyword: str, page_number: int) -> tuple[str, ...]:
    """Return a deterministic, query-aware order for official topic pages."""
    marker = str(keyword or "").casefold()
    if any(token in marker for token in ("数据", "计算", "flink", "云", "数据库", "iot", "边缘", "固件")):
        order = (2, 3, 0, 1)
    elif any(token in marker for token in ("自动驾驶", "机器人", "slam", "嵌入式")):
        order = (1, 0, 3, 2)
    else:
        order = (0, 3, 1, 2)
    page = max(0, int(page_number))
    suffix = f"?curPage={page}" if page else ""
    return tuple(f"{LIEPIN_PUBLIC_TOPIC_URLS[index]}{suffix}" for index in order)


def parse_liepin_cards_html(
    html: str,
    *,
    keyword: str,
    search_city: str,
    search_page: int,
) -> list[dict[str, Any]]:
    try:
        root = lxml_html.fromstring(html)
    except (TypeError, ValueError):
        return []
    output: list[dict[str, Any]] = []
    cards = root.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' job-card-pc-container ')]")
    for card in cards:
        anchors = card.xpath(".//a[@data-nick='job-detail-job-info']")
        if not anchors:
            continue
        anchor = anchors[0]
        source_url, source_id = canonical_liepin_url(anchor.get("href"))
        source_id = source_id or str(anchor.get("data-jobid") or "").strip()
        if not source_id or not source_url:
            continue
        title = _node_text(card, ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-title-box ')]//div[1]")
        city_raw = _node_text(card, ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-dq-box ')]//span[1]")
        city, district = split_location(city_raw)
        labels = _node_texts(card, ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-labels-box ')]//span")
        experience = labels[0] if labels else ""
        experience_min, experience_max = parse_experience(experience)
        salary_raw = _node_text(card, ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-salary ')]")
        salary_min, salary_max, salary_months = parse_monthly_salary(salary_raw)
        tags = _node_texts(card, ".//*[contains(concat(' ', normalize-space(@class), ' '), ' company-tags-box ')]//span")
        output.append({
            "source_id": source_id,
            "source_platform": "liepin",
            "source_url": source_url,
            "title": mask_contacts(title),
            "company": mask_contacts(_node_text(card, ".//*[contains(concat(' ', normalize-space(@class), ' '), ' company-name ')]")) or None,
            "content": "",
            "raw_content": "",
            "city": city,
            "district": district,
            "experience": mask_contacts(experience) or None,
            "experience_min_years": experience_min,
            "experience_max_years": experience_max,
            "education": mask_contacts(labels[1]) if len(labels) > 1 else None,
            "tags": tags,
            "salary": salary_raw or None,
            "salary_min_k": salary_min,
            "salary_max_k": salary_max,
            "salary_months": salary_months,
            "salary_period": "monthly",
            "currency": "CNY",
            "published_at": None,
            "employment_type": "full_time",
            "collection_mode": "live",
            "metadata": {
                "browser_assisted": True,
                "research_collection": True,
                "team_jd_crawler_adapter": True,
                "crawler_engine": "jd-crawler-liepin-rendered-dom",
                "query": keyword,
                "search_city": search_city,
                "search_page": search_page,
                "salary_raw": salary_raw,
            },
        })
    return output


def parse_liepin_mobile_cards_html(
    html: str,
    *,
    keyword: str,
    search_city: str,
    search_page: int,
) -> list[dict[str, Any]]:
    """Map the public mobile job-card DOM to the same raw JD contract as Zhaopin."""
    try:
        root = lxml_html.fromstring(html)
    except (TypeError, ValueError):
        return []
    output: list[dict[str, Any]] = []
    cards = root.xpath(
        "//a[contains(concat(' ', normalize-space(@class), ' '), ' job-card ')]"
    )
    for card in cards:
        href = str(card.get("href") or "").strip()
        if href.startswith("/"):
            href = MOBILE_BASE_URL + href
        source_url, source_id = canonical_liepin_url(href)
        title = _node_text(
            card,
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-title ')]//span[1]",
        ) or _node_text(card, ".//h2[1]")
        if not source_id or not source_url or not title:
            continue
        salary_raw = _node_text(card, ".//h3[1]//small[1]") or _node_text(card, ".//h3[1]")
        salary_min, salary_max, salary_months = parse_monthly_salary(salary_raw)
        labels = _node_texts(
            card,
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-card-labels ')]//label",
        )
        location_raw = next((item for item in labels if search_city in item or "-" in item), search_city)
        city, district = split_location(location_raw)
        experience = next((item for item in labels if "经验" in item or "应届" in item), "")
        experience_min, experience_max = parse_experience(experience)
        education = next((item for item in labels if any(word in item for word in _EDUCATION_WORDS)), None)
        company = _node_text(
            card,
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-card-company ')]//span[1]",
        )
        output.append({
            "source_id": source_id,
            "source_platform": "liepin",
            "source_url": source_url,
            "title": mask_contacts(title),
            "company": mask_contacts(company) or None,
            "content": "",
            "raw_content": "",
            "city": city or search_city,
            "district": district,
            "experience": mask_contacts(experience) or None,
            "experience_min_years": experience_min,
            "experience_max_years": experience_max,
            "education": mask_contacts(education) if education else None,
            "tags": [item for item in labels if item not in {location_raw, experience, education}],
            "salary": salary_raw or None,
            "salary_min_k": salary_min,
            "salary_max_k": salary_max,
            "salary_months": salary_months,
            "salary_period": "monthly",
            "currency": "CNY",
            "published_at": None,
            "employment_type": "full_time",
            "collection_mode": "live",
            "metadata": {
                "browser_assisted": True,
                "research_collection": True,
                "team_jd_crawler_adapter": True,
                "crawler_engine": "jd-crawler-liepin-mobile-rendered-dom",
                "query": keyword,
                "search_city": search_city,
                "search_page": search_page,
                "salary_raw": salary_raw,
                "public_mobile_fallback": True,
            },
        })
    return output


def enrich_liepin_detail(html: str, job: dict[str, Any], visible_text: str = "") -> dict[str, Any]:
    try:
        root = lxml_html.fromstring(html)
    except (TypeError, ValueError):
        return job
    candidates = []
    for node in root.xpath(
        "//*[contains(@class,'job-intro') or contains(@class,'content-word') "
        "or contains(@class,'job-detail-content') or contains(@class,'job-detail-box')]"
    ):
        text = _compact(" ".join(node.itertext()))
        if text:
            candidates.append(text)
    content = mask_contacts(max(candidates, key=len, default=""))
    if not content:
        content = mask_contacts(_extract_visible_job_intro(visible_text))
    if content:
        job["content"] = content[:20_000]
        job["raw_content"] = content[:20_000]

    title_tag = _compact(" ".join(root.xpath("//title/text()")))
    title_match = _TITLE_RE.search(title_tag)
    if title_match:
        job["title"] = job.get("title") or mask_contacts(title_match.group("title"))
        job["city"] = job.get("city") or title_match.group("city")
        company = title_match.group("company")
        if company.endswith(title_match.group("city")):
            company = company[:-len(title_match.group("city"))]
        job["company"] = job.get("company") or mask_contacts(company)

    meta_values = root.xpath("//meta[translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='description']/@content")
    meta = _compact(meta_values[0] if meta_values else "")
    if meta:
        salary_match = _SALARY_RE.search(meta)
        if not job.get("salary") and salary_match:
            salary_raw = salary_match.group("salary")
            salary_min, salary_max, salary_months = parse_monthly_salary(salary_raw)
            job.update({"salary": salary_raw, "salary_min_k": salary_min, "salary_max_k": salary_max, "salary_months": salary_months})
        if not job.get("education"):
            job["education"] = next((word for word in _EDUCATION_WORDS if word in meta), None)
        if not job.get("experience"):
            experience_match = _EXPERIENCE_RE.search(meta)
            if experience_match:
                experience = experience_match.group("experience").replace(" ", "")
                low, high = parse_experience(experience)
                job.update({"experience": experience, "experience_min_years": low, "experience_max_years": high})
        if not job.get("tags"):
            scale_match = _SCALE_RE.search(meta)
            if scale_match:
                job["tags"] = [scale_match.group("scale")]
    return job


def _extract_visible_job_intro(value: str) -> str:
    """Extract the JD section from mobile pages whose CSS classes are hashed."""
    lines = [_compact(line) for line in str(value or "").replace("\r", "\n").split("\n")]
    lines = [line for line in lines if line]
    start = next((index + 1 for index, line in enumerate(lines) if line in {"职位介绍", "职位描述", "岗位介绍"}), None)
    if start is None:
        return ""
    end_markers = {"查看全部", "公司信息", "工作地点", "猎聘温馨提示", "相关推荐", "职位推荐"}
    end = next((index for index in range(start, len(lines)) if lines[index] in end_markers), len(lines))
    content_lines = lines[start:end]
    content = "\n".join(content_lines).strip()
    return content if len(content) >= 80 else ""


class LiepinBrowserSource(SupplementalBrowserSource):
    """Low-volume Liepin adapter; search collection requires explicit robots acknowledgement."""

    source_id = "liepin"
    display_name = "猎聘"
    first_page = 0

    def __init__(self) -> None:
        super().__init__()
        self.robots_acknowledged = os.getenv("TALENTGRAPH_LIEPIN_ROBOTS_ACKNOWLEDGED", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.enabled = self.enabled and self.robots_acknowledged
        if not self.robots_acknowledged:
            self.configuration = "set TALENTGRAPH_LIEPIN_ROBOTS_ACKNOWLEDGED=1 after reviewing robots.txt and platform terms"

    @staticmethod
    def search_url(keyword: str, city: str, page_number: int) -> str:
        url = f"{BASE_URL}/zhaopin/?key={quote(keyword)}&curPage={page_number}"
        code = LIEPIN_CITY_CODES.get(city)
        if code:
            url += f"&city={code}&dq={code}"
        return url

    @staticmethod
    def mobile_search_url(keyword: str, city: str, page_number: int) -> str:
        slug = LIEPIN_MOBILE_CITY_SLUGS.get(city)
        prefix = f"{MOBILE_BASE_URL}/city-{slug}" if slug else MOBILE_BASE_URL
        return f"{prefix}/zhaopin/?keyword={quote(keyword)}&curPage={max(0, page_number)}"

    @staticmethod
    def mobile_city_url(city: str) -> str:
        slug = LIEPIN_MOBILE_CITY_SLUGS.get(city)
        return f"{MOBILE_BASE_URL}/city-{slug}/" if slug else f"{MOBILE_BASE_URL}/"

    def _fetch_page(self, context: Any, keyword: str, city: str, page_number: int, remaining: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        desktop_risk: CollectionRiskControlError | None = None
        desktop_error: Exception | None = None
        login_session_configured = self.cookie_path.is_file()

        # A user-provided session gets the normal desktop experience first. Anonymous
        # jobs use the public mobile surface first so a desktop captcha does not pollute
        # the shared .liepin.com persistent context before the fallback is attempted.
        if login_session_configured:
            try:
                rows = self._fetch_desktop_rows(context, keyword, city, page_number)
            except CollectionRiskControlError as exc:
                desktop_risk = exc
            except Exception as exc:
                desktop_error = exc
        if not rows:
            rows = self._fetch_mobile_rows(context, keyword, city, page_number)
        if not rows and not login_session_configured:
            try:
                rows = self._fetch_desktop_rows(context, keyword, city, page_number)
            except CollectionRiskControlError as exc:
                desktop_risk = exc
            except Exception as exc:
                desktop_error = exc
        if not rows and desktop_risk:
            raise desktop_risk
        if not rows and desktop_error:
            raise desktop_error

        detail_page = context.new_page()
        try:
            if rows and rows[0].get("metadata", {}).get("public_mobile_fallback"):
                detail_page.set_extra_http_headers({"User-Agent": MOBILE_USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
                detail_page.set_viewport_size({"width": 412, "height": 915})
            eligible_rows = [
                row for row in rows
                if self.include_pattern.search(str(row.get("title") or ""))
                and not self.exclude_pattern.search(str(row.get("title") or ""))
            ]
            for row in eligible_rows[:max(1, remaining)]:
                time.sleep(random.uniform(2.0, 3.5))
                try:
                    detail_page.goto(row["source_url"], wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
                    self._wait_for_verification(detail_page)
                    try:
                        detail_page.wait_for_timeout(min(1_200, self.selector_timeout_ms))
                        visible_text = detail_page.locator("body").inner_text(timeout=self.selector_timeout_ms)
                    except Exception:
                        visible_text = ""
                    enrich_liepin_detail(detail_page.content(), row, visible_text)
                except CollectionRiskControlError:
                    raise
                except Exception:
                    if self._is_verification_page(detail_page):
                        self._wait_for_verification(detail_page)
                    # A single detail failure remains a quality rejection, not a site retry loop.
                    continue
        finally:
            detail_page.close()
        return rows

    def _fetch_desktop_rows(self, context: Any, keyword: str, city: str, page_number: int) -> list[dict[str, Any]]:
        page = context.new_page()
        try:
            page.goto(self.search_url(keyword, city, page_number), wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
            self._wait_for_verification(page)
            try:
                page.wait_for_selector("div.job-card-pc-container", timeout=self.selector_timeout_ms)
            except Exception:
                pass
            return parse_liepin_cards_html(
                page.content(), keyword=keyword, search_city=city, search_page=page_number,
            )
        finally:
            page.close()

    def _fetch_mobile_rows(self, context: Any, keyword: str, city: str, page_number: int) -> list[dict[str, Any]]:
        page = context.new_page()
        try:
            page.set_extra_http_headers({"User-Agent": MOBILE_USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
            page.set_viewport_size({"width": 412, "height": 915})
            keyword_url = self.mobile_search_url(keyword, city, page_number)
            topic_urls = liepin_public_topic_urls(keyword, page_number)
            urls = (keyword_url, *topic_urls, self.mobile_city_url(city))
            for url in urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
                except Exception:
                    continue
                self._wait_for_verification(page)
                try:
                    page.wait_for_selector("a.job-card", timeout=self.selector_timeout_ms)
                except Exception:
                    pass
                rows = parse_liepin_mobile_cards_html(
                    page.content(), keyword=keyword, search_city=city, search_page=page_number,
                )
                if rows and url in topic_urls:
                    allowed_cities = set(self.cities)
                    rows = [row for row in rows if not row.get("city") or row.get("city") in allowed_cities]
                    for row in rows:
                        row["metadata"].update({
                            "public_topic_fallback": True,
                            "listing_url": url,
                        })
                if rows:
                    return rows
            return []
        finally:
            page.close()


def _node_text(root: Any, xpath: str) -> str:
    values = root.xpath(xpath)
    if not values:
        return ""
    node = values[0]
    return mask_contacts(_compact(" ".join(node.itertext()) if hasattr(node, "itertext") else str(node)))


def _node_texts(root: Any, xpath: str) -> list[str]:
    output = []
    for node in root.xpath(xpath):
        text = mask_contacts(_compact(" ".join(node.itertext()) if hasattr(node, "itertext") else str(node)))
        if text and text not in output:
            output.append(text)
    return output


def _compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
