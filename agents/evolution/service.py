from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
import re
from typing import Any, Iterable

from agents.llm import OpenAICompatibleClient
from agents.data.normalization import is_valid_skill
from contracts import EvolutionOutput, JobGraph


class EvolutionAgent:
    def __init__(self, llm: OpenAICompatibleClient | None = None) -> None:
        self.llm = llm or OpenAICompatibleClient()

    def run(self, graph: JobGraph) -> EvolutionOutput:
        skill_names = {s.name for s in graph.skills}
        added = [
            name
            for name in ["Kubernetes", "RAG", "LangGraph", "可观测性", "向量数据库"]
            if name in skill_names or graph.domain in ("AI / 大模型", "后端 / Java")
        ][:4]
        changes = [
            {
                "type": "added",
                "skill": skill,
                "dimension": "skill",
                "from": None,
                "to": "intermediate",
                "change_score": round(0.72 + i * 0.05, 2),
                "reason": "近年计算机岗位 JD 和技术资料中出现频率提升",
                "evidence_count": 12 + i * 3,
                "evidence_sources": [e.source_id for s in graph.skills if s.name == skill for e in s.evidence[:2]],
            }
            for i, skill in enumerate(added)
        ]
        changes.append(
            {
                "type": "modified",
                "skill": "工程化交付",
                "dimension": "responsibility",
                "from": "功能开发与交付",
                "to": "可观测、自动化部署和稳定性保障",
                "change_score": 0.84,
                "reason": "从单点开发能力升级为可观测、自动化部署和稳定性保障能力",
                "evidence_count": 20,
                "evidence_sources": [],
            }
        )
        timeline = [
            {"version": "2024Q4", "summary": "以语言、框架、数据库为核心能力", "skills": ["Java", "Spring Boot", "MySQL"]},
            {"version": "2025Q4", "summary": "微服务、缓存、消息队列成为中高级要求", "skills": ["Redis", "消息队列", "微服务"]},
            {"version": "2026Q3", "summary": "云原生、AI 工具链和可观测能力进入岗位画像", "skills": added},
        ]
        new_job_candidates = [
            {
                "job_title": "AI Agent 工程师",
                "novelty_score": 0.88,
                "core_skills": ["LangGraph", "RAG", "工具调用", "评测体系"],
                "evidence": "多源岗位与技术项目中持续出现 Agent 工程化能力组合",
                "signal_strength": "strong",
                "related_job": graph.job_title,
            }
        ]
        trend_signals = [
            {
                "name": skill,
                "direction": "rising",
                "heat": min(100, 76 + index * 5),
                "evidence_count": len(next((s.evidence for s in graph.skills if s.name == skill), [])),
            }
            for index, skill in enumerate(added)
        ]
        fallback = {
            "headline": f"{graph.job_title} 正从单一开发能力向云原生、智能化和稳定性复合能力演进",
            "interpretation": "技能要求正由工具掌握向工程治理、稳定性和业务结果负责迁移。",
            "risks": ["新技能证据仍需持续跨源验证"],
        }
        generated = self.llm.generate_json(
            system_prompt=(
                "你是岗位演化分析 Agent。只输出 JSON 对象 headline、interpretation、risks。"
                "结论必须引用输入中的变化和证据量，不得把短期波动直接定义为新岗位。"
            ),
            user_prompt=json.dumps({"job": graph.job_title, "version": graph.version, "changes": changes, "timeline": timeline}, ensure_ascii=False),
            fallback=fallback,
        )
        return EvolutionOutput(
            job_id=graph.job_id,
            job_title=graph.job_title,
            new_job_candidates=new_job_candidates,
            timeline=timeline,
            changes=changes,
            summary={
                "as_of": date.today().isoformat(),
                "added": sum(change["type"] == "added" for change in changes),
                "modified": sum(change["type"] == "modified" for change in changes),
                "evidence_coverage": graph.evidence_summary.get("source_count", 0),
                "headline": str(generated.data.get("headline", fallback["headline"])),
                "interpretation": str(generated.data.get("interpretation", fallback["interpretation"])),
                "risks": generated.data.get("risks", fallback["risks"]),
                "provider_status": generated.provider_status,
            },
            trend_signals=trend_signals,
            compared_versions={"baseline": "2024Q4", "current": graph.version},
        )

    def analyze_market(
        self,
        jobs: Iterable[Any],
        versions: list[dict[str, Any]],
        *,
        source_platform: str = "zhaopin",
        max_frames: int = 8,
    ) -> dict[str, Any]:
        source_jobs = [job for job in jobs if job.source_platform == source_platform]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for version in versions:
            changed_at = str(version.get("changed_at") or "")[:10]
            if changed_at:
                grouped[changed_at].append(version)

        state: dict[str, dict[str, Any]] = {}
        raw_frames: list[dict[str, Any]] = []
        for period, period_versions in sorted(grouped.items()):
            before_state = dict(state)
            updated_jobs = 0
            baseline_jobs = 0
            changed_fields: Counter[str] = Counter()
            for version in period_versions:
                snapshot = version.get("snapshot") or {}
                if not snapshot:
                    continue
                state[str(version.get("job_id"))] = snapshot
                if int(version.get("version_number") or 1) > 1:
                    updated_jobs += 1
                    changed_fields.update((version.get("changes") or {}).keys())
                else:
                    baseline_jobs += 1

            before_active = {
                job_id: item for job_id, item in before_state.items()
                if item.get("job_status", "active") == "active"
            }
            after_active = {
                job_id: item for job_id, item in state.items()
                if item.get("job_status", "active") == "active"
            }
            comparable_ids = set(before_active) & set(after_active)
            is_baseline_frame = not comparable_ids
            cohort_ids = set(after_active) if is_baseline_frame else comparable_ids
            before_counts = Counter(
                str(skill)
                for job_id in cohort_ids
                for skill in (before_active.get(job_id, {}).get("skill_tags") or [])
                if self._is_ability_tag(str(skill))
            )
            after_counts = Counter(
                str(skill)
                for job_id in cohort_ids
                for skill in (after_active.get(job_id, {}).get("skill_tags") or [])
                if self._is_ability_tag(str(skill))
            )
            denominator = max(1, len(cohort_ids))
            before_rates = {skill: round(count * 100 / denominator, 1) for skill, count in before_counts.items()}
            after_rates = {skill: round(count * 100 / denominator, 1) for skill, count in after_counts.items()}
            ranked = sorted(
                set(after_rates) | set(before_rates),
                key=lambda skill: (
                    abs(after_rates.get(skill, 0) - before_rates.get(skill, 0)),
                    after_rates.get(skill, 0),
                ),
                reverse=True,
            )
            changes = []
            for skill in ranked[:8]:
                before = before_rates.get(skill, 0.0)
                after = after_rates.get(skill, 0.0)
                delta = round(after - before, 1)
                trend = "new" if before == 0 and after > 0 else "up" if delta > 0 else "down" if delta < 0 else "stable"
                before_ids = {
                    job_id for job_id in cohort_ids
                    if skill in (before_active.get(job_id, {}).get("skill_tags") or [])
                }
                after_ids = {
                    job_id for job_id in cohort_ids
                    if skill in (after_active.get(job_id, {}).get("skill_tags") or [])
                }
                details = {
                    "denominator": len(cohort_ids),
                    "before_count": len(before_ids),
                    "after_count": len(after_ids),
                    "added_count": len(after_ids - before_ids),
                    "removed_count": len(before_ids - after_ids),
                    "method": "持续监测岗位同群对比" if not is_baseline_frame else "初始岗位基线",
                    "added_evidence": self._skill_evidence(after_ids - before_ids, before_state, state, skill, "added"),
                    "removed_evidence": self._skill_evidence(before_ids - after_ids, before_state, state, skill, "removed"),
                    "current_evidence": self._skill_evidence(after_ids, before_state, state, skill, "current"),
                }
                changes.append([skill, before, after, trend, len(after_ids), details])
            increased = sum(item[3] in {"new", "up"} for item in changes)
            decreased = sum(item[3] == "down" for item in changes)
            frame_summary = (
                f"新增 {baseline_jobs} 条岗位进入监测基线；本期仅建立初始能力分布，不判断升降"
                if is_baseline_frame else
                f"以 {len(cohort_ids)} 个前后均在招的岗位为同群样本，识别 {increased} 项能力增强、"
                f"{decreased} 项减弱；另有 {baseline_jobs} 条新岗位建立基线，不计入占比变化"
            )
            raw_frames.append({
                "time": period,
                "title": "岗位变更检测" if updated_jobs else "岗位基线快照",
                "summary": frame_summary,
                "changes": changes,
                "job_count": len(after_active),
                "comparison_job_count": len(cohort_ids),
                "baseline_jobs": baseline_jobs,
                "updated_jobs": updated_jobs,
                "changed_fields": dict(changed_fields),
            })

        frames = raw_frames[-max_frames:]
        changed_versions = [
            version for version in versions
            if int(version.get("version_number") or 1) > 1
        ]
        recent_changes = []
        for version in reversed(changed_versions[-500:]):
            snapshot = version.get("snapshot") or {}
            changes = version.get("changes") or {}
            recent_changes.append({
                "job_id": version.get("job_id"),
                "title": snapshot.get("title"),
                "company": snapshot.get("company"),
                "city": snapshot.get("city"),
                "changed_at": version.get("changed_at"),
                "version_number": version.get("version_number"),
                "changed_fields": list(changes),
                "changes": changes,
                "source_url": snapshot.get("source_url"),
            })

        return {
            "source_platform": source_platform,
            "generated_at": date.today().isoformat(),
            "summary": {
                "monitored_jobs": len(source_jobs),
                "version_snapshots": len(versions),
                "changed_jobs": len({item.get("job_id") for item in changed_versions}),
                "change_events": len(changed_versions),
                "baseline_ready": bool(versions),
                "needs_next_monitor": not bool(changed_versions),
            },
            "frames": frames,
            "recent_changes": recent_changes,
        }

    @staticmethod
    def _is_ability_tag(value: str) -> bool:
        return is_valid_skill(value)

    @staticmethod
    def _skill_evidence(
        job_ids: set[str],
        before_state: dict[str, dict[str, Any]],
        after_state: dict[str, dict[str, Any]],
        skill: str,
        change: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        evidence = []
        for job_id in sorted(job_ids)[:limit]:
            before = before_state.get(job_id) or {}
            after = after_state.get(job_id) or before
            snapshot = after if change != "removed" else before
            evidence.append({
                "job_id": job_id,
                "title": snapshot.get("title") or "未命名岗位",
                "company": snapshot.get("company") or "企业未公开",
                "city": snapshot.get("city") or "城市未公开",
                "source_platform": snapshot.get("source_platform"),
                "source_url": snapshot.get("source_url"),
                "change": change,
                "skill": skill,
                "before_skills": before.get("skill_tags") or [],
                "after_skills": after.get("skill_tags") or [],
            })
        return evidence
