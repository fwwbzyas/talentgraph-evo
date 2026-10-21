"""Playwright 备用模式(SPEC §4.17)。

定位:httpx 路径被风控拦截时的**人工兜底通道**,合规形态与智联爬虫一致:

- **headed 真实浏览器**(强制非 headless),持久化用户数据目录,
  复用用户本人已通过的站点验证状态;
- 人机验证**由人完成**:检测到 WAF/验证码页时仅轮询等待其消失
  (默认最多 180s),绝不自动打码、绝不注入指纹伪装、不使用代理;
- 请求节奏沿用 `RateLimiter`(同一套限速/抖动),robots 护栏在 CLI 层
  与 httpx 路径完全一致;
- 解析复用 httpx 路径的成熟解析器,不维护第二套解析逻辑:
  - 51job:捕获浏览器自身发出的 `search-pc` API JSON 响应 → `parse_search`;
  - liepin:页面渲染后对 DOM 执行 `parse_search_cards`。

启用:`--browser`(直接用浏览器模式)/ `--browser-fallback`(httpx 被风控
停站后自动切换)。需要 `pip install playwright && playwright install chromium`。
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional
from urllib.parse import quote

from ..exceptions import RiskControlError
from ..models import JobPosting
from ..pipeline import Checkpoint
from ..ratelimit import RateLimiter
from .base import BaseSpider
from .job51 import CITY_CODES as JOB51_CITY_CODES, parse_search
from .liepin import LIEPIN_CITY_CODES, parse_search_cards

logger = logging.getLogger("jd_crawler.spiders.browser")

_VERIFY_MARKERS = ("safe.liepin.com", "验证", "captcha", "Security", "Verification")


class BrowserSession:
    """headed 持久化浏览器会话。禁止 headless(合规:不伪装、人工可见)。"""

    def __init__(
        self,
        user_data_dir: str,
        *,
        rate_limiter: Optional[RateLimiter] = None,
        verify_timeout: int = 180,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.user_data_dir = user_data_dir
        self.rl = rate_limiter or RateLimiter()
        self.verify_timeout = verify_timeout
        self._sleep = sleep
        self._pw = None
        self._context = None

    def __enter__(self) -> "BrowserSession":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "Playwright 备用模式需要: pip install playwright && "
                "playwright install chromium"
            ) from e
        self._pw = sync_playwright().start()
        # launch_persistent_context:复用用户数据目录中的验证状态;headed 可见
        self._context = self._pw.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        return self

    def __exit__(self, *exc) -> None:
        if self._context:
            self._context.close()
        if self._pw:
            self._pw.stop()

    @contextmanager
    def page(self) -> Iterator[Any]:
        page = self._context.new_page()
        try:
            yield page
        finally:
            page.close()

    def goto(self, page: Any, url: str) -> None:
        self.rl.wait()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        self._wait_verification(page, url)

    def _wait_verification(self, page: Any, url: str) -> None:
        """出现验证页时等人:轮询直到页面恢复正常或超时按风控停站。"""
        try:
            title = page.title() or ""
            cur = page.url or ""
        except Exception:
            return
        if not any(m in title or m in cur for m in _VERIFY_MARKERS):
            return
        logger.warning(
            "检测到人机验证页面(%s)。请在浏览器窗口中手动完成验证,"
            "最多等待 %d 秒……", cur, self.verify_timeout,
        )
        for _ in range(self.verify_timeout):
            self._sleep(2)
            try:
                title = page.title() or ""
                cur = page.url or ""
            except Exception:
                return
            if not any(m in title or m in cur for m in _VERIFY_MARKERS):
                logger.info("验证已通过,继续采集。")
                return
        raise RiskControlError("browser", url, "人机验证等待超时")


def fetch_51job_search(
    session: BrowserSession, keyword: str, city: str | None, page_num: int,
) -> tuple[list[JobPosting], int]:
    """浏览器模式抓 51job 列表:捕获页面自身发出的 search-pc API 响应。"""
    job_area = JOB51_CITY_CODES.get(city or "全国")
    if job_area is None:
        raise ValueError(f"未知城市: {city}")
    payloads: list[dict] = []
    with session.page() as page:
        url = (f"https://we.51job.com/pc/search?keyword={quote(keyword)}"
               f"&jobArea={job_area}&pageNum={page_num}")
        # search-pc 可能先后触发多次(预热空调用 + 真实结果),全部收集后取
        # joblist 最大的一份。注意:response 回调里只存对象、不调 .json()
        # (同步 API 在事件回调里会扰乱事件循环),统一在页面就绪后解析。
        responses: list[Any] = []
        page.on("response", lambda r: responses.append(r)
                if "/api/job/search-pc" in r.url else None)
        session.goto(page, url)
        # 轮询等待 search-pc 响应出现(页面骨架里就有 joblist-item 容器,
        # 不能等 selector;实测 API 在导航后 2~8s 才发出)
        for _ in range(40):  # 最多 ~20s
            if responses:
                break
            page.wait_for_timeout(500)
        page.wait_for_timeout(1500)  # 容许紧随的第二次数据响应
        for r in responses:
            try:
                payloads.append(r.json())
            except Exception:
                pass
        if not payloads and 'id="renderData"' in page.content():
            # WAF 挑战页在浏览器中也未能自动通过 ⇒ 按风控停站处理
            raise RiskControlError("browser", url, "WAF 挑战在浏览器模式下仍未通过")
    if not payloads:
        logger.warning("51job 浏览器模式未捕获到 search-pc 响应(第 %d 页)。", page_num)
        return [], 0
    best_jobs: list[JobPosting] = []
    best_total = 0
    for p in payloads:
        jobs, total = parse_search(p)
        if len(jobs) > len(best_jobs):
            best_jobs, best_total = jobs, total
    return best_jobs, best_total


def fetch_liepin_search(
    session: BrowserSession, keyword: str, city: str | None, cur_page: int,
) -> list[JobPosting]:
    """浏览器模式抓猎聘列表:渲染完成后复用 SSR 卡片解析器解析 DOM。"""
    url = f"https://www.liepin.com/zhaopin/?key={quote(keyword)}&curPage={cur_page}"
    if city and city in LIEPIN_CITY_CODES:
        url += f"&city={LIEPIN_CITY_CODES[city]}&dq={LIEPIN_CITY_CODES[city]}"
    with session.page() as page:
        session.goto(page, url)
        try:
            page.wait_for_selector("div.job-card-pc-container", timeout=10_000)
        except Exception:
            logger.warning("猎聘浏览器模式第 %d 页未出现职位卡片。", cur_page)
        html = page.content()
    return parse_search_cards(html)


_PROBE_URLS = {
    "51job": "https://we.51job.com/pc/search?keyword=python",
    "liepin": "https://www.liepin.com/zhaopin/?key=python",
}

# 登录页(登录模式预热用;扫码/账号登录由用户在弹出的浏览器中完成)
_LOGIN_URLS = {
    "51job": "https://login.51job.com/login.php",
    "liepin": "https://passport.liepin.com/login",
}
# 登录页 URL 标记:连续数次检查都不再包含这些标记 ⇒ 判定已登录跳转
_LOGIN_MARKERS = ("login", "passport")


def profile_dir(base: str | Path, login: bool = False) -> str:
    """浏览器 profile 目录:登录态与游客态分离,互不污染。"""
    from pathlib import Path as _P
    return str(_P(base) / ("browser_profile_login" if login else "browser_profile"))


def _looks_logged_out(url: str) -> bool:
    u = url.lower()
    return any(m in u for m in _LOGIN_MARKERS)


def login_warmup(
    user_data_dir: str,
    sites: tuple[str, ...] = ("51job", "liepin"),
    *,
    timeout: int = 300,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, str]:
    """登录模式预热:自动弹出各站点登录页(扫码/账号),轮询检测登录成功
    (URL 离开登录域)后自动继续下一站;登录态固化到 user_data_dir。
    返回 {site: "ok" | "timeout" | "unknown site"}。
    """
    results: dict[str, str] = {}
    with BrowserSession(user_data_dir, sleep=sleep) as session:
        for site in sites:
            url = _LOGIN_URLS.get(site)
            if not url:
                results[site] = "unknown site"
                continue
            with session.page() as page:
                logger.info("[登录预热] %s: 已打开登录页 %s,请扫码/登录……", site, url)
                session.rl.wait()
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                ok = False
                stable = 0
                for _ in range(timeout // 2):
                    sleep(2)
                    try:
                        cur = page.url or ""
                    except Exception:
                        break
                    if not _looks_logged_out(cur):
                        stable += 1
                        if stable >= 2:  # 连续两次离开登录域 ⇒ 登录成功
                            ok = True
                            break
                    else:
                        stable = 0
                results[site] = "ok" if ok else "timeout"
                if ok:
                    logger.info("[登录预热] %s 登录成功(%s),登录态已固化。", site,
                                page.url)
                else:
                    logger.warning("[登录预热] %s 等待登录超时(%ds),未固化登录态。",
                                   site, timeout)
    return results


def preflight(
    user_data_dir: str,
    sites: tuple[str, ...] = ("51job", "liepin"),
    *,
    verify_timeout: int = 180,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, str]:
    """浏览器预热:打开各站点搜索页,等待人工完成验证,固话验证状态到
    user_data_dir,供后续定时轮跑免干预复用。返回 {site: "ok" | "blocked: ..."}。
    """
    results: dict[str, str] = {}
    with BrowserSession(user_data_dir, verify_timeout=verify_timeout,
                        sleep=sleep) as session:
        for site in sites:
            url = _PROBE_URLS.get(site)
            if not url:
                results[site] = "unknown site"
                continue
            with session.page() as page:
                try:
                    session.goto(page, url)
                    results[site] = "ok"
                    logger.info("[预热] %s 可访问,验证状态已固化到 profile。", site)
                except RiskControlError as e:
                    results[site] = f"blocked: {e.evidence}"
                    logger.error("[预热] %s 未通过: %s", site, e.evidence)
    return results


class BrowserSpider(BaseSpider):
    """浏览器版 Spider:与 httpx 版同一接口,便于 BatchRunner 无感切换。"""

    def __init__(self, session: BrowserSession, site: str):
        super().__init__(http=None)  # 浏览器路径不使用 HttpClient
        self.session = session
        self.site = site

    def iter_jobs(self, keyword: str, city: str | None, max_pages: int,
                  checkpoint: Checkpoint) -> Iterator[JobPosting]:
        start = 1 if self.site == "51job" else 0
        for i in range(max_pages):
            page_num = start + i
            if checkpoint.is_page_done(self.site, keyword, city, page_num):
                continue
            if self.site == "51job":
                jobs, _total = fetch_51job_search(self.session, keyword, city, page_num)
            else:
                jobs = fetch_liepin_search(self.session, keyword, city, page_num)
            logger.info("[%s/浏览器] 第 %d 页: %d 条", self.site, page_num, len(jobs))
            for job in jobs:
                job = job.model_copy(update={"keyword": keyword, "search_city": city})
                if not checkpoint.is_job_done(job):
                    yield job
            checkpoint.mark_page(self.site, keyword, city, page_num)
            checkpoint.save()
            if not jobs:
                break
