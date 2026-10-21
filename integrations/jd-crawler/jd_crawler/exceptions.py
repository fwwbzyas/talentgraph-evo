"""异常定义。"""

from __future__ import annotations


class FetchError(Exception):
    """网络或 HTTP 层错误(可重试)。"""

    def __init__(self, message: str, *, url: str = "", status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


class RiskControlError(Exception):
    """检测到验证码 / 滑块 / WAF / 风控跳转。

    按合规护栏:一旦抛出,必须**立即停止该站点的全部抓取**并记录,
    绝不重试、绝不打码、绝不绕过。
    """

    def __init__(self, site: str, url: str, evidence: str):
        super().__init__(f"[{site}] 触发风控/验证码,已停止该站点: {url} ({evidence})")
        self.site = site
        self.url = url
        self.evidence = evidence
