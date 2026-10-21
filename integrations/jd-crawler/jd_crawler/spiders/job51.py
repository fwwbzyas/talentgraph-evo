"""51job(前程无忧)Spider(SPEC §4.7)。

实测要点(2026-08-13):
- 搜索 API `GET https://we.51job.com/api/job/search-pc`;
- `sign = HmacSHA256_hex(相对URL(含querystring), cupid_sign_key)`,
  算法与密钥均取自官方前端 JS(app-06837ae4 chunk, commonStore);
- 沙箱实测:即便 sign 正确,仍返回阿里云 WAF JS 挑战页 ⇒ 由 HttpClient
  的风控检测抛 RiskControlError 并停站(绝不执行/绕过 WAF JS)。
- API 响应结构按公开情报解析(resultbody.joblist),fixture 单测验证。

说明:详情页(jobs.51job.com/...)同样受 WAF 保护,本原型**只采列表
字段**,description 恒为空串;不实现详情抓取。
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid as uuidlib
from typing import Any, Iterator
from urllib.parse import quote, urlencode

from ..models import JobPosting
from ..pipeline import Checkpoint
from .base import BaseSpider

logger = logging.getLogger("jd_crawler.spiders.job51")

API_PATH = "/api/job/search-pc"
BASE_URL = "https://we.51job.com"

# 硬编码于官方前端 JS(commonStore.cupid_sign_key),2026-08-13 实测提取
CUPID_SIGN_KEY = "abfc8f9dcf8c3f3d8aa294ac5f2cf2cc7767e5592590f39c3f503271dd68562b"

# 常用城市码(jobArea),000000 为全国
CITY_CODES = {
    "全国": "000000", "北京": "010000", "上海": "020000",
    "广州": "030100", "深圳": "030200", "杭州": "080200",
    "南京": "070200", "成都": "090200", "武汉": "180200",
    "西安": "200200", "苏州": "070300", "天津": "050000",
    "重庆": "060000", "长沙": "190200", "郑州": "170200",
    "合肥": "150200",
}

# 与前端一致的固定参数位(空串占位,顺序即签名顺序)
SEARCH_PARAMS = [
    "keyword", "searchType", "function", "industry", "jobArea", "jobArea2",
    "landmark", "metro", "salary", "workYear", "degree", "companyType",
    "companySize", "jobType", "issueDate", "sortType", "pageNum",
    "requestId", "pageSize", "source", "accountId", "pageCode",
]

MAX_PAGE_SIZE = 50


def build_search_url(keyword: str, job_area: str, page_num: int,
                     page_size: int = 20, timestamp: int | None = None) -> str:
    """构造与前端完全一致的相对 URL(含 querystring),供签名与请求使用。"""
    ts = str(timestamp if timestamp is not None else int(time.time()))
    values = {
        "keyword": keyword, "searchType": "2", "function": "", "industry": "",
        "jobArea": job_area, "jobArea2": "", "landmark": "", "metro": "",
        "salary": "", "workYear": "", "degree": "", "companyType": "",
        "companySize": "", "jobType": "", "issueDate": "", "sortType": "0",
        "pageNum": str(page_num), "requestId": "", "pageSize": str(page_size),
        "source": "1", "accountId": "", "pageCode": "sou|sou|soulb",
    }
    qs = urlencode([(k, values[k]) for k in SEARCH_PARAMS])
    return f"{API_PATH}?api_key=51job&timestamp={ts}&{qs}"


def compute_sign(relative_url_with_query: str, sign_key: str = CUPID_SIGN_KEY) -> str:
    """sign = HmacSHA256_hex(url, key)(与前端 `HmacSHA256(url+(data||''), key)` 一致)。"""
    return hmac.new(
        sign_key.encode("utf-8"),
        relative_url_with_query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def parse_search(payload: dict[str, Any]) -> tuple[list[JobPosting], int]:
    """解析 search-pc 响应。返回 (职位列表, 总数)。

    兼容两种结构:
    - 现行真实 API(2026-08-13 浏览器实测):`resultbody.job.items` /
      `resultbody.job.totalCount`,字段为驼峰(jobId/jobName/provideSalaryString/
      jobAreaString/workYearString/degreeString/issueDateString/jobHref/jobDescribe);
    - 旧公开结构(httpx 路径 fixture):`resultbody.joblist` + 小写字段。
    """
    body = payload.get("resultbody") or {}
    job_node = body.get("job") if isinstance(body.get("job"), dict) else {}
    items = job_node.get("items") or body.get("joblist") or []
    total = int(job_node.get("totalCount") or job_node.get("totalcount")
                or body.get("totalcount") or 0)
    jobs: list[JobPosting] = []
    for item in items:
        job_id = str(item.get("jobId") or item.get("jobid") or "").strip()
        if not job_id:
            continue
        tags = [t for t in (item.get("companyIndustryType1Str") or item.get("companyindustrytype_text"),
                            item.get("companyTypeString"),
                            item.get("companySizeString") or item.get("companysize_text")) if t]
        href = item.get("jobHref") or item.get("jobhref") or ""
        jobs.append(JobPosting(
            source="51job",
            job_id=job_id,
            title=item.get("jobName") or item.get("jobname") or "",
            salary=item.get("provideSalaryString") or item.get("providesalarytext") or None,
            city=item.get("jobAreaString") or item.get("workareashow") or item.get("workarea") or None,
            company_name=item.get("fullCompanyName") or item.get("fullcompanyname")
                          or item.get("company_name") or None,
            experience=item.get("workYearString") or item.get("workyear") or None,
            education=item.get("degreeString") or item.get("degreefrom") or None,
            publish_date=item.get("issueDateString") or item.get("updatedate")
                         or item.get("issuedate") or item.get("updateDateTime") or None,
            # 仅浏览器模式能拿到 jobDescribe;httpx 路径恒为空串
            description=item.get("jobDescribe") or "",
            job_url=(href.split("?")[0] if href
                     else f"https://jobs.51job.com/job/{job_id}.html"),
            company_tags=tags,
        ))
    return jobs, total


class Job51Spider(BaseSpider):
    site = "51job"

    def __init__(self, http, sign_key: str = CUPID_SIGN_KEY):
        super().__init__(http)
        self.sign_key = sign_key

    def iter_jobs(self, keyword: str, city: str | None, max_pages: int,
                  checkpoint: Checkpoint) -> Iterator[JobPosting]:
        job_area = CITY_CODES.get(city or "全国")
        if job_area is None:
            raise ValueError(
                f"未知城市: {city};可选: {', '.join(CITY_CODES)}(或自行扩展 CITY_CODES)"
            )
        for page in range(1, max_pages + 1):
            if checkpoint.is_page_done(self.site, keyword, city, page):
                logger.info("跳过已完成页 %s/%s/%s 第 %d 页", self.site, keyword, city, page)
                continue
            rel = build_search_url(keyword, job_area, page)
            headers = {
                "sign": compute_sign(rel, self.sign_key),
                "uuid": uuidlib.uuid4().hex,
                "From-Domain": "51job_web",
                "account-id": "",
                "user-token": "",
                "partner": "",
                "property": "%7B%7D",
                "Referer": f"{BASE_URL}/pc/search?keyword={quote(keyword)}",
            }
            resp = self.http.get(BASE_URL + rel, headers=headers)
            payload = resp.json()  # WAF 页是 HTML,会在风控检测处先行拦截
            jobs, total = parse_search(payload)
            logger.info("51job 第 %d 页: %d 条(总 %d)", page, len(jobs), total)
            for job in jobs:
                if not checkpoint.is_job_done(job):
                    yield job.model_copy(update={"keyword": keyword, "search_city": city})
            checkpoint.mark_page(self.site, keyword, city, page)
            checkpoint.save()
            if not jobs or len(jobs) < 1:
                break
