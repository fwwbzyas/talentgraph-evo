"""猎聘 Spider(SPEC §4.8)。

实测要点(2026-08-13):
- 游客搜索页 `/zhaopin/?key=...` 可达,但职位列表为 **CSR**;其数据 API
  (api-c.liepin.com/...pc-search-job)需要 security.min.js 计算的风控
  token,实测返回 {"flag":0} ⇒ 本爬虫**不请求该 API**,只解析 SSR 卡片
  (SSR 卡片存在时;真实站点在部分 UA/路径下会 SSR 职位卡片,DOM 与详情页
  推荐卡片同构,fixture 取自真实页面)。
- 详情页 `/job/<id>.shtml` 为 SSR:TDK(title/meta description)含岗位名、
  公司、城市、薪资、学历、经验;主体 JD 为 CSR,SSR 正文块存在时才提取。
- 连续请求可能 302 → safe.liepin.com 验证码 ⇒ HttpClient 风控检测停站。
- 合规:猎聘 robots.txt `Disallow: /*?*`,搜索 URL 带查询串 ⇒ CLI 默认
  要求 `--i-understand-robots` 显式确认(见 robots.py)。
"""

from __future__ import annotations

import logging
import re
from typing import Iterator, Optional
from urllib.parse import quote, urlparse

from parsel import Selector

from ..models import JobPosting
from ..pipeline import Checkpoint
from .base import BaseSpider

logger = logging.getLogger("jd_crawler.spiders.liepin")

BASE = "https://www.liepin.com"

# 猎聘城市 dq 码(公开常用值;未列出的城市可留空)
LIEPIN_CITY_CODES = {
    "北京": "010", "上海": "020", "天津": "030", "重庆": "040",
    "广州": "050020", "深圳": "050090", "南京": "060020",
    "苏州": "060080", "杭州": "070020", "合肥": "080020",
    "武汉": "170020", "长沙": "180020", "西安": "270020",
    "成都": "280020",
}

_EDU_WORDS = (
    "统招本科", "统招硕士", "统招大专", "本科", "硕士", "博士", "MBA", "EMBA",
    "大专", "学历不限", "中专/中技", "高中", "初中及以下",
)

_TITLE_RE = re.compile(r"【(?P<city>\S+?)\s+(?P<title>.+?)招聘】-(?P<company>.+?)招聘信息-猎聘")
_SALARY_RE = re.compile(r"薪资(?P<salary>[^,,，]+)")
_EXP_RE = re.compile(r"(?P<exp>\d+\s*-\s*\d+年|\d+年以上|经验不限|\d+年)(?:相关)?经验")
_DESC_SCALE_RE = re.compile(r"公司规模(?P<scale>[^,,，]+)")


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_job_url(href: str) -> tuple[str, str]:
    """去掉跟踪参数,返回 (规范URL, job_id)。无法识别时 job_id 为空串。"""
    p = urlparse(href)
    m = re.search(r"/(?:job|a)/(\d+)\.shtml", p.path)
    clean_url = f"{p.scheme}://{p.netloc}{p.path}" if p.scheme else href.split("?")[0]
    return clean_url, (m.group(1) if m else "")


def parse_search_cards(html: str) -> list[JobPosting]:
    """解析搜索页(或任何含同构卡片的页面)中的职位卡片。"""
    sel = Selector(html)
    jobs: list[JobPosting] = []
    for card in sel.css("div.job-card-pc-container"):
        a = card.css('a[data-nick="job-detail-job-info"]')
        href = a.attrib.get("href", "")
        if not href:
            continue
        url, job_id = normalize_job_url(href)
        if not job_id:
            job_id = a.attrib.get("data-jobid", "")
        if not job_id:
            continue
        title = _clean(card.css(".job-title-box div::text").get())
        city = _clean(card.css(".job-dq-box span.ellipsis-1::text").get())
        labels = [_clean(t) for t in card.css(".job-labels-box span::text").getall()]
        labels = [t for t in labels if t]
        experience = labels[0] if labels else None
        education = labels[1] if len(labels) > 1 else None
        jobs.append(JobPosting(
            source="liepin",
            job_id=job_id,
            title=title,
            salary=_clean(card.css(".job-salary::text").get()) or None,
            city=city or None,
            company_name=_clean(card.css(".company-name::text").get()) or None,
            experience=experience,
            education=education,
            publish_date=None,
            description="",
            job_url=url,
            company_tags=[_clean(t) for t in
                          card.css(".company-tags-box span::text").getall() if _clean(t)],
        ))
    return jobs


def parse_detail(html: str, job: JobPosting) -> JobPosting:
    """补全详情页字段:优先 SSR 正文块,缺失时回退 TDK 解析。"""
    sel = Selector(html)

    # 1) SSR 正文块(历史结构,存在时才用)
    desc_parts = sel.css(
        ".job-intro ::text, .content-word ::text, .job-detail-content ::text"
    ).getall()
    desc = _clean(" ".join(desc_parts))
    if desc:
        job.description = desc

    # 2) TDK 回退
    title_tag = _clean(sel.css("title::text").get())
    m = _TITLE_RE.search(title_tag)
    if m:
        job.title = job.title or _clean(m.group("title"))
        job.city = job.city or m.group("city")
        company = m.group("company")
        if company.endswith(m.group("city")):
            company = company[: -len(m.group("city"))]
        job.company_name = job.company_name or _clean(company)

    meta_desc = sel.css('meta[name="description"]::attr(content)').get() or ""
    if meta_desc:
        if not job.salary:
            sm = _SALARY_RE.search(meta_desc)
            if sm:
                job.salary = sm.group("salary")
        if not job.education:
            for w in _EDU_WORDS:
                if w in meta_desc:
                    job.education = w
                    break
        if not job.experience:
            em = _EXP_RE.search(meta_desc)
            if em:
                job.experience = em.group("exp").replace(" ", "")
        if not job.company_tags:
            sc = _DESC_SCALE_RE.search(meta_desc)
            if sc:
                job.company_tags = [sc.group("scale")]
    # 重新触发脱敏(直接改字段绕过不了 model_post_init,这里手动过一遍)
    from ..sanitize import mask_contacts
    job.description = mask_contacts(job.description)
    return job


class LiepinSpider(BaseSpider):
    site = "liepin"

    def __init__(self, http, fetch_details: bool = True):
        super().__init__(http)
        self.fetch_details = fetch_details

    def search_url(self, keyword: str, city: Optional[str], cur_page: int) -> str:
        url = f"{BASE}/zhaopin/?key={quote(keyword)}&curPage={cur_page}"
        if city and city in LIEPIN_CITY_CODES:
            url += f"&city={LIEPIN_CITY_CODES[city]}&dq={LIEPIN_CITY_CODES[city]}"
        return url

    def iter_jobs(self, keyword: str, city: str | None, max_pages: int,
                  checkpoint: Checkpoint) -> Iterator[JobPosting]:
        for page in range(0, max_pages):
            if checkpoint.is_page_done(self.site, keyword, city, page):
                logger.info("跳过已完成页 %s/%s/%s 第 %d 页", self.site, keyword, city, page)
                continue
            resp = self.http.get(self.search_url(keyword, city, page))
            jobs = parse_search_cards(resp.text)
            if not jobs:
                logger.warning(
                    "猎聘第 %d 页未解析到 SSR 职位卡片(游客模式列表为 CSR,"
                    "属预期行为;不会改请求风控 API)。", page,
                )
            logger.info("liepin 第 %d 页: %d 条", page, len(jobs))
            for job in jobs:
                job = job.model_copy(update={"keyword": keyword, "search_city": city})
                if checkpoint.is_job_done(job):
                    continue
                if self.fetch_details:
                    try:
                        dresp = self.http.get(job.job_url)
                        job = parse_detail(dresp.text, job)
                    except Exception as e:
                        # 详情失败不致命:列表字段照出,正文留空;
                        # 但风控异常必须继续向上抛(停站)
                        from ..exceptions import RiskControlError
                        if isinstance(e, RiskControlError):
                            raise
                        logger.warning("详情页抓取失败 %s: %s", job.job_url, e)
                yield job
            checkpoint.mark_page(self.site, keyword, city, page)
            checkpoint.save()
            if not jobs:
                break
