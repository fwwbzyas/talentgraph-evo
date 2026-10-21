from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from .models import JobProfile, JobSkill


JOB_FAMILIES = [
    ("ai-agent", "AI Agent工程师", "人工智能", ("agent", "智能体")),
    ("llm-app", "大模型应用工程师", "人工智能", ("大模型", "llm", "rag")),
    ("algorithm", "算法工程师", "人工智能", ("算法工程师", "机器学习", "深度学习", "视觉算法", "nlp")),
    ("data-engineering", "大数据开发工程师", "大数据", ("大数据开发", "hadoop", "spark", "flink")),
    ("data-warehouse", "数据仓库工程师", "大数据", ("数据仓库", "数仓")),
    ("data-analysis", "数据分析师", "大数据", ("数据分析师", "数据挖掘")),
    ("java-backend", "Java后端工程师", "智能系统", ("java后端", "java开发", "后端开发")),
    ("cloud-devops", "云原生与DevOps工程师", "智能系统", ("云原生", "devops", "运维开发", "sre")),
    ("test-development", "测试开发工程师", "智能系统", ("测试开发", "自动化测试")),
    ("embedded", "嵌入式工程师", "物联网", ("嵌入式",)),
    ("iot", "物联网工程师", "物联网", ("物联网", "iot", "设备接入")),
    ("intelligent-system", "智能系统工程师", "智能系统", ("智能系统", "机器人", "自动驾驶")),
]

NOISE_PATTERNS = re.compile(
    r"^(本科|硕士|博士|大专|不限|应届|\d+-\d+年|五险一金|年终奖|餐补|房补|交通补助|补充医疗保险|股票期权)$",
    re.I,
)


def _clean_skills(skills: list[str]) -> list[str]:
    result = []
    for raw in skills:
        skill = str(raw).strip()
        if not skill or len(skill) > 32 or NOISE_PATTERNS.search(skill):
            continue
        result.append(skill)
    return result


def load_job_profiles(source_db: Path, skills_per_job: int = 12) -> list[JobProfile]:
    if not source_db.exists():
        raise FileNotFoundError(f"TalentGraph database not found: {source_db}")
    with sqlite3.connect(source_db) as connection:
        rows = [json.loads(row[0]) for row in connection.execute("SELECT payload FROM job_assets")]

    profiles: list[JobProfile] = []
    for job_key, title, domain, keywords in JOB_FAMILIES:
        matched = [
            item for item in rows
            if item.get("job_status", "active") == "active"
            and any(keyword in str(item.get("title") or "").lower() for keyword in keywords)
        ]
        counts = Counter(skill for item in matched for skill in _clean_skills(item.get("skill_tags") or []))
        denominator = max(1, len(matched))
        skills = [
            JobSkill(name=name, demand_count=count, demand_rate=round(count / denominator * 100, 1))
            for name, count in counts.most_common(skills_per_job)
        ]
        if matched and skills:
            profiles.append(JobProfile(job_key=job_key, title=title, domain=domain, job_count=len(matched), skills=skills))
    return profiles

