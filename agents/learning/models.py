from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class JobSkill(BaseModel):
    name: str
    demand_count: int = 0
    demand_rate: float = 0


class JobProfile(BaseModel):
    job_key: str
    title: str
    domain: str
    job_count: int
    skills: list[JobSkill]


class CourseDocument(BaseModel):
    course_id: str
    source: str
    title: str
    url: str
    cover_url: str = ""
    summary: str = ""
    instructor: str = ""
    published_at: str | None = None
    duration_seconds: int | None = None
    view_count: int = 0
    quality_score: float = Field(default=50, ge=0, le=100)
    difficulty: Literal["入门", "进阶", "实战", "综合"] = "综合"
    language: str = "zh-CN"
    is_free: bool = True
    skills: list[str] = Field(default_factory=list)
    content: str = ""
    raw: dict = Field(default_factory=dict)


class CollectRequest(BaseModel):
    job_keys: list[str] = Field(default_factory=list)
    skills_per_job: int = Field(default=6, ge=1, le=15)
    courses_per_skill: int = Field(default=4, ge=1, le=10)


class RouteRequest(BaseModel):
    job_key: str
    weak_skills: list[str] = Field(min_length=1)
    current_level: Literal["零基础", "入门", "进阶"] = "入门"
    courses_per_skill: int = Field(default=3, ge=1, le=6)


class RouteCourse(BaseModel):
    course_id: str
    title: str
    url: str
    cover_url: str = ""
    source: str
    instructor: str = ""
    duration_text: str = "时长未公开"
    quality_score: float
    recommendation_score: float
    reason: str


class RouteStep(BaseModel):
    order: int
    phase: str
    skill: str
    demand_count: int = 0
    demand_rate: float = 0
    estimated_hours: int
    why: str
    learning_content: list[str]
    completion_criteria: list[str]
    courses: list[RouteCourse]


class LearningRoute(BaseModel):
    route_id: str = Field(default_factory=lambda: f"route_{uuid4().hex[:12]}")
    job_key: str
    job_title: str
    domain: str
    current_level: str
    weak_skills: list[str]
    total_estimated_hours: int
    steps: list[RouteStep]
    project: dict
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
