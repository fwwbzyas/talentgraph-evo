from __future__ import annotations

from collections import defaultdict

from .db import CourseStore
from .models import CourseDocument
from .sources import BilibiliSource, OfficialLearningSource


class CourseCollector:
    def __init__(self, store: CourseStore, timeout: float = 15):
        self.store = store
        self.timeout = timeout

    def collect(self, skills: list[str], per_skill: int = 4) -> dict:
        unique_skills = list(dict.fromkeys(skill.strip() for skill in skills if skill.strip()))
        source_counts = defaultdict(int)
        errors = []
        saved_ids = set()
        official = OfficialLearningSource()
        bilibili = BilibiliSource(timeout=self.timeout)
        try:
            for skill in unique_skills:
                documents: list[CourseDocument] = official.search(skill, limit=2)
                try:
                    documents.extend(bilibili.search(skill, limit=per_skill))
                except Exception as exc:
                    errors.append({"skill": skill, "source": "Bilibili", "error": str(exc)[:240]})
                for document in documents:
                    existing_skills = list(document.skills)
                    if skill not in existing_skills:
                        document.skills.append(skill)
                    self.store.upsert_course(document)
                    saved_ids.add(document.course_id)
                    source_counts[document.source] += 1
        finally:
            bilibili.close()
        return {
            "skills": unique_skills,
            "saved_courses": len(saved_ids),
            "source_records": dict(source_counts),
            "errors": errors,
        }

