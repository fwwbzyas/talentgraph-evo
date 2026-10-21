"""风控检测:WAF 挑战页 / safe.liepin 302 / 正常响应。全程 MockTransport。"""

import httpx
import pytest

from jd_crawler.exceptions import RiskControlError
from jd_crawler.http import HttpClient
from jd_crawler.ratelimit import RateLimiter


def make_client(handler) -> HttpClient:
    transport = httpx.MockTransport(handler)
    return HttpClient(
        "test",
        RateLimiter(interval=0, jitter=(0, 0)),  # 测试不限速
        transport=transport,
    )


def test_waf_challenge_raises(job51_waf_html):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=job51_waf_html)

    with make_client(handler) as c:
        with pytest.raises(RiskControlError) as ei:
            c.get("https://we.51job.com/api/job/search-pc?api_key=51job")
    assert "WAF" in ei.value.evidence


def test_liepin_captcha_redirect_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://safe.liepin.com/intercept/ip/captcha/dispatch?sourceUrl=xx"},
        )

    with make_client(handler) as c:
        with pytest.raises(RiskControlError):
            c.get("https://www.liepin.com/zhaopin/?key=Python&curPage=0")


def test_normal_response_passes():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"status": "1", "resultbody": {"joblist": []}})

    with make_client(handler) as c:
        resp = c.get("https://example.com/api")
        assert resp.json()["status"] == "1"
    # UA 带联系信息占位
    assert "contact:" in seen[0].headers["user-agent"]
