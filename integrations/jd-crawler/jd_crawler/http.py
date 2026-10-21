"""HTTP 客户端:统一 UA、限速、重试、风控检测(SPEC §4.4/§4.5)。

合规要点:
- 使用正常 UA 并带联系信息占位,**不伪装搜索引擎爬虫**;
- 不带任何登录态(token/Cookie 仅由目标站自行 Set-Cookie);
- 检测到风控(阿里云 WAF / safe.liepin 验证码 / 滑块特征)立即抛
  `RiskControlError`,由上层停止该站点;绝不执行 WAF JS、绝不绕过。
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import httpx

from .exceptions import FetchError, RiskControlError
from .ratelimit import RateLimiter, with_retry

logger = logging.getLogger("jd_crawler.http")

DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# 风控特征(命中即停站)
_WAF_MARKERS = ("aliyun_waf", 'id="renderData"', "acw_sc__v2")
_CAPTCHA_MARKERS = (
    "safe.liepin.com",
    "captcha",
    "滑块",
    "验证中心",
    "punish-loc",
)


def default_risk_checker(site: str, response: httpx.Response, body: str) -> None:
    """通用风控检测:WAF 挑战页、验证码跳转、滑块特征。"""
    # 1) 30x 跳转到验证码域(httpx 默认不自动跟随我们配置为 False,由这里判定)
    if response.status_code in (301, 302, 303, 307, 308):
        loc = response.headers.get("location", "")
        if any(m in loc for m in ("safe.liepin.com", "captcha")):
            raise RiskControlError(site, str(response.url), f"302 -> {loc}")
    # 2) 响应头/正文特征
    if "punish-loc" in response.headers:
        raise RiskControlError(site, str(response.url), "punish-loc 响应头")
    head = body[:5000]
    for m in _WAF_MARKERS:
        if m in head:
            raise RiskControlError(site, str(response.url), f"阿里云 WAF 特征: {m}")
    for m in _CAPTCHA_MARKERS:
        if m in head:
            raise RiskControlError(site, str(response.url), f"验证码特征: {m}")


RiskChecker = Callable[[str, httpx.Response, str], None]


class HttpClient:
    def __init__(
        self,
        site_name: str,
        rate_limiter: Optional[RateLimiter] = None,
        *,
        contact: str = "YOUR-EMAIL-PLACEHOLDER",
        timeout: float = 20.0,
        risk_checker: RiskChecker = default_risk_checker,
        transport: httpx.BaseTransport | None = None,
    ):
        self.site_name = site_name
        self.rl = rate_limiter or RateLimiter()
        self.risk_checker = risk_checker
        ua = f"{DEFAULT_BROWSER_UA} jd-crawler/0.1 (+research; contact: {contact})"
        self._client = httpx.Client(
            headers={
                "User-Agent": ua,
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=timeout,
            follow_redirects=False,  # 302 由风控检测自行判定,绝不盲目跟随
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _request(self, method: str, url: str, **kw) -> httpx.Response:
        self.rl.wait()

        def _do() -> httpx.Response:
            try:
                resp = self._client.request(method, url, **kw)
            except httpx.HTTPError as e:
                raise FetchError(f"{method} {url} 失败: {e}", url=url) from e
            if resp.status_code >= 500:
                raise FetchError(f"HTTP {resp.status_code}", url=url, status=resp.status_code)
            return resp

        resp = with_retry(_do, max_retries=3, base_delay=2.0, retryable=(FetchError,))
        body = resp.text
        self.risk_checker(self.site_name, resp, body)
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code}", url=url, status=resp.status_code)
        return resp

    def get(self, url: str, **kw) -> httpx.Response:
        return self._request("GET", url, **kw)

    def post(self, url: str, **kw) -> httpx.Response:
        return self._request("POST", url, **kw)
