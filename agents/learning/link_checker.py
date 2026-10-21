from __future__ import annotations

import httpx

from .db import CourseStore


class CourseLinkChecker:
    def __init__(self, store: CourseStore, timeout: float = 12):
        self.store = store
        self.timeout = timeout

    def run(self, limit: int = 200) -> dict:
        summary = {"checked": 0, "healthy": 0, "unknown": 0, "broken": 0}
        with httpx.Client(
            timeout=self.timeout, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"},
        ) as client:
            for item in self.store.list_course_links(limit):
                http_status = None
                try:
                    response = client.get(item["url"])
                    http_status = response.status_code
                    if http_status in {404, 410}:
                        status = "broken"
                    elif http_status < 400:
                        status = "healthy"
                    else:
                        status = "unknown"
                except httpx.HTTPError:
                    status = "unknown"
                self.store.save_link_health(item["course_id"], status, http_status)
                summary["checked"] += 1
                summary[status] += 1
        return summary
