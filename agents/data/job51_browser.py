from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from agents.data.supplemental_recruitment import (
    CollectionRiskControlError,
    SupplementalBrowserSource,
    mask_contacts,
    parse_experience,
    parse_monthly_salary,
    split_location,
)


BASE_URL = "https://we.51job.com"
API_PATH = "/api/job/search-pc"
CUPID_SIGN_KEY = "abfc8f9dcf8c3f3d8aa294ac5f2cf2cc7767e5592590f39c3f503271dd68562b"
CITY_CODES = {
    "全国": "000000", "北京": "010000", "上海": "020000", "广州": "030100",
    "深圳": "030200", "杭州": "080200", "南京": "070200", "苏州": "070300",
    "成都": "090200", "武汉": "180200", "西安": "200200", "合肥": "150200",
    "长沙": "190200",
}
SEARCH_PARAMS = (
    "keyword", "searchType", "function", "industry", "jobArea", "jobArea2",
    "landmark", "metro", "salary", "workYear", "degree", "companyType",
    "companySize", "jobType", "issueDate", "sortType", "pageNum",
    "requestId", "pageSize", "source", "accountId", "pageCode",
)


def build_search_api_url(
    keyword: str,
    job_area: str,
    page_num: int,
    *,
    page_size: int = 20,
    timestamp: int | None = None,
) -> str:
    values = {
        "keyword": keyword, "searchType": "2", "function": "", "industry": "",
        "jobArea": job_area, "jobArea2": "", "landmark": "", "metro": "",
        "salary": "", "workYear": "", "degree": "", "companyType": "",
        "companySize": "", "jobType": "", "issueDate": "", "sortType": "0",
        "pageNum": str(page_num), "requestId": "", "pageSize": str(page_size),
        "source": "1", "accountId": "", "pageCode": "sou|sou|soulb",
    }
    query = urlencode([(key, values[key]) for key in SEARCH_PARAMS])
    moment = timestamp if timestamp is not None else int(time.time())
    return f"{API_PATH}?api_key=51job&timestamp={moment}&{query}"


def compute_sign(relative_url_with_query: str, sign_key: str = CUPID_SIGN_KEY) -> str:
    return hmac.new(
        sign_key.encode("utf-8"),
        relative_url_with_query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def canonical_job51_url(value: Any, job_id: str) -> str:
    url = str(value or "").strip()
    if not url:
        return f"https://jobs.51job.com/job/{job_id}.html"
    if url.startswith("//"):
        url = "https:" + url
    parts = urlsplit(url)
    return urlunsplit(("https", parts.netloc.lower(), parts.path, "", ""))


def parse_job51_payload(
    payload: dict[str, Any],
    *,
    keyword: str,
    search_city: str,
    search_page: int,
) -> tuple[list[dict[str, Any]], int]:
    """Map both known 51job API shapes directly to TalentGraph's raw JD contract."""
    body = payload.get("resultbody") or {}
    job_node = body.get("job") if isinstance(body.get("job"), dict) else {}
    rows = job_node.get("items") or body.get("joblist") or []
    total = int(job_node.get("totalCount") or job_node.get("totalcount") or body.get("totalcount") or 0)
    output: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("jobId") or row.get("jobid") or "").strip()
        title = mask_contacts(row.get("jobName") or row.get("jobname"))
        if not source_id or not title:
            continue
        salary_raw = mask_contacts(row.get("provideSalaryString") or row.get("providesalarytext"))
        location_raw = row.get("jobAreaString") or row.get("workareashow") or row.get("workarea")
        city, district = split_location(location_raw)
        experience = mask_contacts(row.get("workYearString") or row.get("workyear"))
        experience_min, experience_max = parse_experience(experience)
        salary_min, salary_max, salary_months = parse_monthly_salary(salary_raw)
        content = mask_contacts(row.get("jobDescribe") or row.get("jobdescribe"))
        industry = mask_contacts(row.get("companyIndustryType1Str") or row.get("companyindustrytype_text"))
        company_size = mask_contacts(row.get("companySizeString") or row.get("companysize_text"))
        company_type = mask_contacts(row.get("companyTypeString") or row.get("companytype_text"))
        tags = list(dict.fromkeys(item for item in (industry, company_type, company_size) if item))
        output.append({
            "source_id": source_id,
            "source_platform": "51job",
            "source_url": canonical_job51_url(row.get("jobHref") or row.get("jobhref"), source_id),
            "title": title,
            "company": mask_contacts(
                row.get("fullCompanyName") or row.get("fullcompanyname") or row.get("company_name")
            ) or None,
            "content": content,
            "raw_content": content,
            "city": city,
            "district": district,
            "experience": experience or None,
            "experience_min_years": experience_min,
            "experience_max_years": experience_max,
            "education": mask_contacts(row.get("degreeString") or row.get("degreefrom")) or None,
            "tags": tags,
            "company_industry": industry or None,
            "company_size": company_size or None,
            "salary": salary_raw or None,
            "salary_min_k": salary_min,
            "salary_max_k": salary_max,
            "salary_months": salary_months,
            "salary_period": "monthly",
            "currency": "CNY",
            "published_at": row.get("issueDateString") or row.get("updatedate")
                            or row.get("issuedate") or row.get("updateDateTime"),
            "employment_type": "full_time",
            "collection_mode": "live",
            "metadata": {
                "browser_assisted": True,
                "research_collection": True,
                "team_jd_crawler_adapter": True,
                "crawler_engine": "jd-crawler-51job-browser-response",
                "query": keyword,
                "search_city": search_city,
                "search_page": search_page,
                "salary_raw": salary_raw,
            },
        })
    return output, total


class Job51BrowserSource(SupplementalBrowserSource):
    """Low-volume 51job adapter based on the team jd-crawler response parser."""

    source_id = "51job"
    display_name = "前程无忧"

    def _fetch_page(self, context: Any, keyword: str, city: str, page_number: int, remaining: int) -> list[dict[str, Any]]:
        del remaining
        job_area = CITY_CODES.get(city)
        if job_area is None:
            raise ValueError(f"前程无忧不支持城市：{city}")
        page = context.new_page()
        responses: list[Any] = []
        page.on("response", lambda response: responses.append(response) if API_PATH in response.url else None)
        url = f"{BASE_URL}/pc/search?keyword={quote(keyword)}&jobArea={job_area}&pageNum={page_number}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
            self._wait_for_verification(page)
            for _ in range(max(8, self.selector_timeout_ms // 500)):
                if responses:
                    break
                page.wait_for_timeout(500)
            page.wait_for_timeout(1_500)
            html = page.content()
            if not responses and ('id="renderData"' in html or "punish-loc" in str(page.url)):
                raise CollectionRiskControlError(self.source_id, str(page.url), "51job WAF challenge")
            candidates: list[tuple[list[dict[str, Any]], int]] = []
            for response in responses:
                try:
                    candidates.append(parse_job51_payload(
                        response.json(), keyword=keyword, search_city=city, search_page=page_number,
                    ))
                except Exception:
                    continue
            return max(candidates, key=lambda item: len(item[0]), default=([], 0))[0]
        finally:
            page.close()
