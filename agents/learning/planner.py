from __future__ import annotations

from .db import CourseStore
from .learning_content import DEPENDENCIES, content_for
from .models import LearningRoute, RouteRequest, RouteStep
from .retriever import CourseRetriever


def _ordered_skills(weak_skills: list[str]) -> list[tuple[str, str]]:
    weak = list(dict.fromkeys(skill.strip() for skill in weak_skills if skill.strip()))
    ordered: list[tuple[str, str]] = []
    seen = set()

    def add(skill: str, phase: str) -> None:
        if skill in seen:
            return
        for dependency in DEPENDENCIES.get(skill, []):
            if dependency in weak:
                add(dependency, "基础补齐")
        seen.add(skill)
        ordered.append((skill, phase))

    for skill in weak:
        add(skill, "基础补齐" if not DEPENDENCIES.get(skill) else "核心能力")
    return ordered


class RoutePlanner:
    def __init__(self, store: CourseStore):
        self.store = store
        self.retriever = CourseRetriever(store)

    def generate(self, request: RouteRequest) -> LearningRoute:
        job = self.store.get_job(request.job_key)
        if not job:
            raise KeyError(f"unknown job: {request.job_key}")
        demand = {item.name.lower(): item for item in job.skills}
        steps = []
        for index, (skill, phase) in enumerate(_ordered_skills(request.weak_skills), start=1):
            content, criteria = content_for(skill)
            signal = demand.get(skill.lower())
            hours = 10 if request.current_level == "进阶" else 16
            if phase == "核心能力":
                hours += 6
            steps.append(RouteStep(
                order=index, phase=phase, skill=skill,
                demand_count=signal.demand_count if signal else 0,
                demand_rate=signal.demand_rate if signal else 0,
                estimated_hours=hours,
                why=(f"该技能在{job.title}样本岗位中出现{signal.demand_count}次，覆盖率{signal.demand_rate}%。" if signal else f"该技能来自你的{job.title}能力差距结果。"),
                learning_content=content, completion_criteria=criteria,
                courses=self.retriever.search(skill, request.current_level, request.courses_per_skill),
            ))
        route = LearningRoute(
            job_key=job.job_key, job_title=job.title, domain=job.domain,
            current_level=request.current_level, weak_skills=request.weak_skills,
            total_estimated_hours=sum(step.estimated_hours for step in steps), steps=steps,
            project={
                "title": f"{job.title}岗位综合实践",
                "description": f"围绕{'、'.join(request.weak_skills)}完成一个可运行、可测试、可复盘的岗位项目。",
                "deliverables": ["可运行项目与源代码", "README和架构说明", "自动化测试或评测结果", "能力证据复盘记录"],
            },
        )
        self.store.save_route(route)
        return route

