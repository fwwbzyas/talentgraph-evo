from __future__ import annotations

from pathlib import Path

from .collector import CourseCollector
from .config import COURSE_DB, HTTP_TIMEOUT, TALENTGRAPH_DB
from .db import CourseStore
from .job_catalog import load_job_profiles
from .models import CollectRequest, RouteRequest
from .planner import RoutePlanner


class CourseRagService:
    def __init__(self, database_path=None):
        self.database_path = Path(database_path or COURSE_DB)
        self.store = CourseStore(self.database_path)

    def sync_jobs(self, skills_per_job: int = 12):
        jobs = load_job_profiles(self.database_path or TALENTGRAPH_DB, skills_per_job)
        self.store.replace_jobs(jobs)
        return jobs

    def collect(self, request: CollectRequest) -> dict:
        jobs = self.store.list_jobs() or self.sync_jobs()
        selected = [job for job in jobs if not request.job_keys or job.job_key in request.job_keys]
        skills = [skill.name for job in selected for skill in job.skills[:request.skills_per_job]]
        return CourseCollector(self.store, HTTP_TIMEOUT).collect(skills, request.courses_per_skill)

    def route(self, request: RouteRequest):
        if not self.store.list_jobs():
            self.sync_jobs()
        return RoutePlanner(self.store).generate(request)
