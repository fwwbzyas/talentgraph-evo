from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from lxml import etree
from lxml import html as lxml_html


BASE_URL = "https://www.zhipin.com"
HARD_CHALLENGE_MARKERS = ("安全验证", "请完成验证", "访问异常", "滑动验证")
SECURITY_URL_MARKERS = ("/web/passport/zp/security.html", "/web/common/security-check")
LOGIN_MARKERS = ("账号登录", "登录后查看", "请先登录")
EMPTY_RESULT_MARKERS = ("暂无相关职位", "没有找到相关职位", "暂无职位")


@dataclass(frozen=True)
class BossSearchHit:
    source_url: str
    title: str
    company: str | None = None
    salary_range: str | None = None
    location: str | None = None
    experience: str | None = None
    education: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class BossJobRecord:
    source_url: str
    source_job_id: str | None
    title: str
    company: str | None
    description: str
    salary_range: str | None
    location: str | None
    experience: str | None
    education: str | None
    publish_date: str | None
    recruiter: str | None
    company_industry: str | None
    company_size: str | None
    company_stage: str | None
    benefits: list[str]
    search_city: str
    search_city_code: str
    search_keyword: str
    keyword_category: str
    detail_tags: list[str] = field(default_factory=list)

    def to_raw_item(self, *, search_page: int, known: bool) -> dict[str, Any]:
        city, district = _split_location(self.location, self.search_city)
        salary_min_k, salary_max_k, salary_months = _salary_parts(self.salary_range)
        experience_min, experience_max = _experience_parts(self.experience)
        return {
            "source_id": self.source_job_id or _source_job_id(self.source_url) or self.source_url,
            "source_platform": "boss",
            "source_url": self.source_url,
            "title": self.title,
            "company": self.company,
            "content": self.description,
            "raw_content": self.description,
            "city": city,
            "district": district,
            "salary_min_k": salary_min_k,
            "salary_max_k": salary_max_k,
            "salary_months": salary_months,
            "experience_min_years": experience_min,
            "experience_max_years": experience_max,
            "education": self.education,
            "benefits": self.benefits,
            "tags": list(dict.fromkeys([*self.detail_tags, *self.benefits])),
            "published_at": self.publish_date or datetime.now(UTC),
            "employment_type": "full_time",
            "collection_mode": "live",
            "change_type": "unchanged" if known else "new",
            "metadata": {
                "browser_assisted": True,
                "crawler_engine": "boss-job-crawler-playwright",
                "research_collection": True,
                "query": self.search_keyword,
                "keyword_category": self.keyword_category,
                "search_city": self.search_city,
                "search_city_code": self.search_city_code,
                "search_page": search_page,
                "salary_range_raw": self.salary_range,
                "experience_raw": self.experience,
                "recruiter": self.recruiter,
                "company_industry": self.company_industry,
                "company_size": self.company_size,
                "company_stage": self.company_stage,
            },
        }


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def is_challenge_page(html: str, url: str = "") -> bool:
    document = _document(html)
    haystack = f"{url}\n{clean_text(document.text_content()) or ''}"
    if (
        any(marker in haystack for marker in HARD_CHALLENGE_MARKERS)
        or any(marker in url for marker in SECURITY_URL_MARKERS)
        or "/web/user/" in url
    ):
        return True
    has_public_job_content = bool(
        document.xpath(
            "//*[contains(@class, 'job-card-wrapper') or contains(@class, 'job-card-box') "
            "or contains(@class, 'job-sec-text')]"
            " | //script[@type='application/ld+json' and contains(., 'JobPosting')]"
        )
    )
    return not has_public_job_content and any(marker in haystack for marker in LOGIN_MARKERS)


def is_explicit_empty_result(html: str) -> bool:
    text = clean_text(_document(html).text_content()) or ""
    return any(marker in text for marker in EMPTY_RESULT_MARKERS)


def parse_search_cards(html: str) -> list[BossSearchHit]:
    selector = _document(html)
    cards = selector.xpath(
        "//*[self::li or self::div][contains(concat(' ', normalize-space(@class), ' '), ' job-card-wrapper ') "
        "or contains(concat(' ', normalize-space(@class), ' '), ' job-card-box ') "
        "or (self::li and contains(concat(' ', normalize-space(@class), ' '), ' job-primary '))]"
    )
    results: list[BossSearchHit] = []
    seen: set[str] = set()
    for card in cards:
        href = _first(card, (
            ".//a[contains(concat(' ', normalize-space(@class), ' '), ' job-card-left ')]/@href",
            ".//a[contains(concat(' ', normalize-space(@class), ' '), ' job-name ')]/@href",
            ".//a[contains(@href, 'job_detail')]/@href",
        ))
        title = _first(card, (
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-name ')]/text()",
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-title ')]/text()",
            ".//a[@title]/@title",
        ))
        if not href or not title:
            continue
        source_url = urljoin(BASE_URL, href)
        if source_url in seen:
            continue
        seen.add(source_url)
        tags = _texts(card, (
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' tag-list ')]//li",
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-card-footer ')]//li",
        ))
        results.append(BossSearchHit(
            source_url=source_url,
            title=title,
            company=_first(card, (
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' company-name ')]//a/text()",
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' company-name ')]/text()",
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' boss-name ')]/text()",
            )),
            salary_range=_first(card, (
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' salary ')]/text()",
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-salary ')]/text()",
            )),
            location=_first(card, (
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-area ')]/text()",
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' job-area-wrapper ')]/text()",
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' company-location ')]/text()",
            )),
            experience=tags[0] if tags else None,
            education=tags[1] if len(tags) > 1 else None,
            tags=tags,
        ))
    return results


def parse_job_detail(
    html: str,
    url: str,
    hit: BossSearchHit,
    *,
    search_city: str,
    search_city_code: str,
    search_keyword: str,
    keyword_category: str,
) -> BossJobRecord:
    selector = _document(html)
    structured = _json_ld(selector)
    description = _first(selector, (
        "//*[contains(@class, 'job-detail-section')]//*[contains(@class, 'job-sec-text')]",
        "//*[contains(@class, 'job-detail')]//*[contains(@class, 'job-sec-text')]",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' job-sec-text ')]",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' job-detail-section ')]",
    ))
    if not description and structured.get("description"):
        description = clean_text(_document(str(structured["description"])).text_content())
    if not description:
        raise ValueError("详情页缺少岗位描述，页面结构可能变化或内容受限")

    detail_tags = _texts(selector, (
        "//*[contains(@class, 'job-banner')]//*[contains(@class, 'tag-list')]//li",
        "//*[contains(@class, 'job-primary')]//*[contains(@class, 'tag-list')]//li",
    ))
    company_tags = _texts(selector, (
        "//*[contains(@class, 'sider-company')]//*[contains(@class, 'company-info')]//a",
        "//*[contains(@class, 'company-info')]//li",
    ))
    benefits = _texts(selector, (
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' job-tags ')]//span",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' job-tags ')]"
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' tag-item ')]",
    ))
    return BossJobRecord(
        source_url=url,
        source_job_id=_source_job_id(url),
        title=_first(selector, (
            "//*[contains(@class, 'job-banner')]//*[contains(@class, 'name')]//h1/text()",
            "//h1/text()",
        )) or hit.title,
        company=_first(selector, (
            "//*[contains(@class, 'sider-company')]//*[contains(@class, 'company-info')]//a/text()",
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' company-name ')]/text()",
        )) or hit.company,
        description=description,
        salary_range=_first(selector, (
            "//*[contains(@class, 'job-banner')]//*[contains(@class, 'salary')]/text()",
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' salary ')]/text()",
        )) or hit.salary_range,
        location=_first(selector, (
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' location-address ')]/text()",
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' job-address ')]/text()",
        )) or hit.location,
        experience=detail_tags[0] if detail_tags else hit.experience,
        education=detail_tags[1] if len(detail_tags) > 1 else hit.education,
        publish_date=structured.get("datePosted"),
        recruiter=_first(selector, (
            "//*[contains(@class, 'boss-info-attr')]//*[contains(@class, 'name')]/text()",
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' boss-name ')]/text()",
        )),
        company_industry=company_tags[0] if company_tags else None,
        company_stage=company_tags[1] if len(company_tags) > 1 else None,
        company_size=company_tags[2] if len(company_tags) > 2 else None,
        benefits=benefits,
        search_city=search_city,
        search_city_code=search_city_code,
        search_keyword=search_keyword,
        keyword_category=keyword_category,
        detail_tags=detail_tags,
    )


def _document(html: str):
    return lxml_html.fromstring(html or "<html></html>")


def _first(selector, expressions: tuple[str, ...]) -> str | None:
    for expression in expressions:
        values = selector.xpath(expression)
        if not values:
            continue
        value = values[0]
        if isinstance(value, etree._Element):
            value = value.text_content()
        cleaned = clean_text(str(value))
        if cleaned:
            return cleaned
    return None


def _texts(selector, expressions: tuple[str, ...]) -> list[str]:
    for expression in expressions:
        values = selector.xpath(expression)
        values = [value.text_content() if isinstance(value, etree._Element) else str(value) for value in values]
        cleaned = [clean_text(value) for value in values]
        result = [value for value in cleaned if value]
        if result:
            return list(dict.fromkeys(result))
    return []


def _json_ld(selector) -> dict[str, Any]:
    for raw in selector.xpath("//script[@type='application/ld+json']/text()"):
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def _source_job_id(url: str) -> str | None:
    match = re.search(r"/job_detail/([^/?#]+?)(?:\.html)?(?:[?#]|$)", urlparse(url).path)
    return match.group(1) if match else None


def _split_location(value: str | None, fallback: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in re.split(r"[·•]", value or "") if part.strip()]
    return (parts[0] if parts else fallback, parts[1] if len(parts) > 1 else None)


def _salary_parts(value: str | None) -> tuple[int | None, int | None, int]:
    text = value or ""
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-~—至]\s*(\d+(?:\.\d+)?)\s*([Kk千万元]?)", text)
    months = re.search(r"(\d{2})\s*薪", text)
    if not match:
        return None, None, int(months.group(1)) if months else 12
    scale = 10 if match.group(3) == "万" else 1
    return round(float(match.group(1)) * scale), round(float(match.group(2)) * scale), int(months.group(1)) if months else 12


def _experience_parts(value: str | None) -> tuple[int | None, int | None]:
    match = re.search(r"(\d+)\s*[-~—至]\s*(\d+)\s*年", value or "")
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d+)\s*年", value or "")
    return (int(match.group(1)), int(match.group(1))) if match else (None, None)
