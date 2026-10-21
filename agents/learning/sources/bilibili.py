from __future__ import annotations

import hashlib
import html
import math
import re
from datetime import UTC, datetime

import httpx

from ..learning_content import aliases_for
from ..models import CourseDocument


TAG_RE = re.compile(r"<[^>]+>")
PROMOTION_RE = re.compile(r"加微信|领资料|培训班|保就业|包就业|七天.*大神|速成大神|破解版", re.I)
COURSE_RE = re.compile(r"教程|课程|入门|实战|公开课|从零|零基础|系统学习|项目", re.I)


def _duration_seconds(value: str | int | None) -> int | None:
    if isinstance(value, int):
        return value
    pieces = [int(part) for part in str(value or "").split(":") if part.isdigit()]
    if not pieces:
        return None
    total = 0
    for part in pieces:
        total = total * 60 + part
    return total


def _difficulty(title: str) -> str:
    if re.search(r"零基础|入门|基础|小白|从零", title, re.I):
        return "入门"
    if re.search(r"项目|实战|企业级|完整项目", title, re.I):
        return "实战"
    if re.search(r"进阶|原理|源码|高级|性能", title, re.I):
        return "进阶"
    return "综合"


def _cover_url(value: str | None) -> str:
    url = str(value or "").strip()
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://"):
        return f"https://{url[7:]}"
    return url


def _quality(item: dict, title: str, duration: int | None) -> float:
    score = 42.0
    views = int(item.get("play") or 0)
    favorites = int(item.get("favorites") or 0)
    if COURSE_RE.search(title):
        score += 14
    score += min(18, math.log10(max(1, views)) * 3)
    score += min(10, math.log10(max(1, favorites)) * 2)
    if duration and duration >= 20 * 60:
        score += 8
    if PROMOTION_RE.search(title + " " + str(item.get("description") or "")):
        score -= 25
    return round(max(0, min(100, score)), 1)


class BilibiliSource:
    source_name = "Bilibili"

    def __init__(self, timeout: float = 15):
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                "Referer": "https://search.bilibili.com/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )

    def close(self) -> None:
        self.client.close()

    def search(self, skill: str, limit: int = 5) -> list[CourseDocument]:
        query = f"{aliases_for(skill)[0]} 系统教程"
        warmup = self.client.get("https://search.bilibili.com/all", params={"keyword": query})
        warmup.raise_for_status()
        response = self.client.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params={"search_type": "video", "keyword": query, "page": 1, "order": "totalrank"},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Bilibili search failed: {payload.get('message') or payload.get('code')}")
        documents = []
        for item in payload.get("data", {}).get("result") or []:
            title = html.unescape(TAG_RE.sub("", str(item.get("title") or ""))).strip()
            description = html.unescape(TAG_RE.sub("", str(item.get("description") or ""))).strip()
            tags = [tag.strip() for tag in str(item.get("tag") or "").split(",") if tag.strip()]
            searchable = " ".join([title, description, *tags]).lower()
            if not any(alias.lower() in searchable for alias in aliases_for(skill)):
                continue
            duration = _duration_seconds(item.get("duration"))
            quality = _quality(item, title, duration)
            if quality < 48:
                continue
            bvid = str(item.get("bvid") or "").strip()
            if not bvid:
                continue
            published = item.get("pubdate")
            published_at = datetime.fromtimestamp(published, UTC).isoformat() if published else None
            documents.append(CourseDocument(
                course_id=f"bili:{bvid}", source=self.source_name, title=title,
                url=f"https://www.bilibili.com/video/{bvid}", cover_url=_cover_url(item.get("pic")), summary=description[:500],
                instructor=str(item.get("author") or ""), published_at=published_at,
                duration_seconds=duration, view_count=int(item.get("play") or 0),
                quality_score=quality, difficulty=_difficulty(title), skills=[skill],
                content="\n".join([title, description, "标签：" + "、".join(tags)]), raw={"bvid": bvid, "tags": tags, "cover_url": _cover_url(item.get("pic"))},
            ))
            if len(documents) >= limit:
                break
        return documents
