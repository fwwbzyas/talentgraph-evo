"""robots.txt 规则快照与警示(SPEC §4.10)。

快照来自 2026-08-13 实测:
- liepin: `Disallow: /*?*`(任何带查询串的 URL 均被禁止),`/job/*.shtml` 未被禁止。
- 51job: we.51job.com / www.51job.com 均未提供有效 robots.txt(返回 SPA 壳/跳转)。

本模块只做**警示**,不做强制阻断;CLI 对被判 disallowed 的目标要求
用户显式确认(`--i-understand-robots`)后才继续。
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class RobotsVerdict:
    allowed: bool
    rule: str
    note: str


def check(url: str) -> RobotsVerdict:
    p = urlparse(url)
    host = p.netloc.lower()
    if host.endswith("liepin.com"):
        if p.query:  # Disallow: /*?*
            return RobotsVerdict(
                False,
                "Disallow: /*?*",
                "猎聘 robots.txt 禁止抓取带查询串的 URL(含搜索页);"
                "详情页 /job/*.shtml 未带查询串时不在禁止之列。",
            )
        for prefix in ("/user/", "/hunter/", "/event/", "/image/randomcode/"):
            if p.path.startswith(prefix):
                return RobotsVerdict(False, f"Disallow: {prefix}", "猎聘 robots.txt 明确禁止该路径。")
        return RobotsVerdict(True, "", "猎聘 robots.txt 未禁止该路径。")
    if host.endswith("51job.com"):
        return RobotsVerdict(
            True,
            "",
            "51job 未提供有效 robots.txt(实测返回 SPA 壳);仍须遵守平台条款并控制频率。",
        )
    return RobotsVerdict(True, "", "未知站点,无内置快照。")
