from __future__ import annotations

import math
from datetime import UTC, datetime

from .db import CourseStore
from .models import RouteCourse


def _duration_text(seconds: int | None) -> str:
    if not seconds:
        return "时长未公开"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours}小时{minutes}分钟" if hours else f"{minutes}分钟"


def _freshness(published_at: str | None) -> float:
    if not published_at:
        return 0.55
    try:
        years = max(0, (datetime.now(UTC) - datetime.fromisoformat(published_at)).days / 365)
        return max(0.15, 1 - years * 0.16)
    except ValueError:
        return 0.55


class CourseRetriever:
    def __init__(self, store: CourseStore):
        self.store = store

    def search(self, skill: str, current_level: str = "入门", limit: int = 3) -> list[RouteCourse]:
        rows = self.store.courses_for_skill(skill, limit=30)
        ranked = []
        for row in rows:
            difficulty = row["difficulty"]
            level_fit = 1.0 if difficulty in ({"零基础": {"入门", "综合"}, "入门": {"入门", "实战", "综合"}, "进阶": {"进阶", "实战", "综合"}}[current_level]) else 0.55
            quality = float(row["quality_score"]) / 100
            popularity = min(1, math.log10(max(1, int(row["view_count"]))) / 7)
            source_trust = 1.0 if row["source"] == "官方免费课程" else 0.82
            score = 0.4 + quality * 0.25 + level_fit * 0.15 + _freshness(row["published_at"]) * 0.1 + popularity * 0.05 + source_trust * 0.05
            reason = f"覆盖{skill}，难度为{difficulty}"
            if row["source"] == "官方免费课程":
                reason += "，来源权威且可免费访问"
            elif int(row["view_count"]):
                reason += f"，已有{int(row['view_count']):,}次播放"
            ranked.append((score, RouteCourse(
                course_id=row["course_id"], title=row["title"], url=row["url"], source=row["source"],
                cover_url=row.get("cover_url", ""),
                instructor=row["instructor"], duration_text=_duration_text(row["duration_seconds"]),
                quality_score=round(float(row["quality_score"]), 1), recommendation_score=round(score * 100, 1), reason=reason,
            )))
        ranked.sort(key=lambda item: (item[0], item[1].quality_score), reverse=True)
        selected = []
        source_seen = set()
        for _, course in ranked:
            if course.source in source_seen and len(ranked) > limit:
                continue
            selected.append(course)
            source_seen.add(course.source)
            if len(selected) >= limit:
                break
        if len(selected) < limit:
            selected_ids = {course.course_id for course in selected}
            remaining = [course for _, course in ranked if course.course_id not in selected_ids]
            selected.extend(remaining[:limit - len(selected)])
        return selected[:limit]
