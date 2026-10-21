from __future__ import annotations

import re
from typing import Any

from agents.llm import OpenAICompatibleClient
from contracts import CandidateProfile, JobGraph, MatchReport, SkillRequirement


LEVEL_SCORE = {"basic": 55, "intermediate": 72, "advanced": 88, "expert": 96}
LEVEL_ORDER = {"basic": 1, "intermediate": 2, "advanced": 3, "expert": 4}
LEVEL_LABEL = {"basic": "基础", "intermediate": "中级", "advanced": "高级", "expert": "专家"}
IMPORTANCE_LABEL = {"required": "必备", "preferred": "加分", "emerging": "趋势"}

ALIASES = {
    "springboot": "spring boot",
    "springcloud": "spring cloud",
    "k8s": "kubernetes",
    "mq": "消息队列",
    "messagequeue": "消息队列",
    "mysql": "mysql",
    "redis": "redis",
    "rag": "rag",
    "llm": "大语言模型",
    "agent": "agent",
    "aiagent": "agent",
    "langchain": "langchain",
    "langgraph": "langgraph",
    "vector database": "向量数据库",
    "vectorstore": "向量数据库",
    "prometheus": "prometheus",
    "cicd": "ci/cd",
}


class MatchAgent:
    def __init__(self, llm: OpenAICompatibleClient | None = None) -> None:
        self.llm = llm or OpenAICompatibleClient()

    def run(self, graph: JobGraph, profile: CandidateProfile) -> MatchReport:
        job_skills = {skill.name: skill for skill in graph.skills}
        candidate_skills = [skill for skill in profile.skills if isinstance(skill, dict)]
        candidate_index = self._candidate_index(candidate_skills)
        matches, gaps = self._evaluate_skills(graph.skills, candidate_index, profile)
        matched = [item["skill"] for item in matches]
        missing = [item["skill"] for item in gaps]
        required = {name for name, skill in job_skills.items() if skill.importance == "required"}
        preferred = {name for name, skill in job_skills.items() if skill.importance != "required"}

        required_score = self._coverage_score(matches, required, required=True)
        preferred_score = self._coverage_score(matches, preferred, required=False) if preferred else required_score
        evidence_score = self._evidence_score(matches, profile)
        behavior_score = round(
            sum(int(d.get("score", 60)) for d in profile.competency_dimensions)
            / max(len(profile.competency_dimensions), 1)
        )
        score_breakdown = {
            "required_skills": required_score,
            "preferred_skills": preferred_score,
            "evidence_quality": evidence_score,
            "behavior_competency": behavior_score,
        }
        score = int(
            min(
                96,
                round(
                    required_score * 0.5
                    + preferred_score * 0.2
                    + evidence_score * 0.2
                    + behavior_score * 0.1
                ),
            )
        )
        level = "high" if score >= 80 else "medium" if score >= 60 else "low"
        strengths = self._strengths(matches)
        risks = self._risks(gaps, matches, profile, score)
        follow_up_questions = self._follow_up_questions(gaps, matches, risks, graph)
        learning_path = self._learning_path(gaps, graph)
        evidence_coverage = round(
            sum(1 for item in matches if item["evidence_count"] > 0) / max(len(graph.skills), 1),
            2,
        )
        executive_summary = self._summary(
            graph=graph,
            profile=profile,
            score=score,
            level=level,
            matches=matches,
            gaps=gaps,
            evidence_coverage=evidence_coverage,
        )
        interview_recommendation = self._interview_recommendation(level, gaps, risks)

        return MatchReport(
            candidate_id=profile.candidate_id,
            target_job_id=graph.job_id,
            score=score,
            level=level,
            gaps=gaps[:8],
            strengths=strengths,
            risks=risks,
            follow_up_questions=follow_up_questions,
            learning_path=learning_path,
            executive_summary=executive_summary,
            score_breakdown=score_breakdown,
            matched_skills=matched,
            missing_required_skills=sorted(required - set(matched)),
            evidence_coverage=evidence_coverage,
            interview_recommendation=interview_recommendation,
            job_snapshot={
                "job_title": graph.job_title,
                "domain": graph.domain,
                "required_skill_count": len(required),
                "preferred_skill_count": len(preferred),
                "matched_skill_count": len(matched),
                "missing_skill_count": len(missing),
                "scenario_count": len(graph.scenarios),
                "graph_version": graph.version,
                "evidence_summary": {
                    "profile_evidence_count": len(profile.evidence),
                    "project_count": len(profile.projects),
                    "evidence_backed_match_count": sum(1 for item in matches if item["evidence_count"] > 0),
                    **graph.evidence_summary,
                },
                "provider_status": {"provider": "local", "status": "deterministic_report"},
            },
        )

    def _candidate_index(self, skills: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for skill in skills:
            name = str(skill.get("name", "")).strip()
            if not name:
                continue
            indexed.setdefault(self._normalize(name), skill)
        return indexed

    def _evaluate_skills(
        self,
        job_skills: list[SkillRequirement],
        candidate_index: dict[str, dict[str, Any]],
        profile: CandidateProfile,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        matches: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        for job_skill in job_skills:
            candidate_skill, matched_by = self._find_candidate_skill(job_skill, candidate_index)
            if candidate_skill:
                level = str(candidate_skill.get("level") or "intermediate")
                required_rank = LEVEL_ORDER.get(job_skill.required_level, 2)
                candidate_rank = LEVEL_ORDER.get(level, 2)
                evidence = str(candidate_skill.get("evidence") or self._best_evidence(job_skill.name, profile))
                evidence_count = self._evidence_count(job_skill.name, evidence, profile)
                level_fit = min(1.0, candidate_rank / max(required_rank, 1))
                confidence = float(candidate_skill.get("confidence") or 0.72)
                matches.append(
                    {
                        "skill": job_skill.name,
                        "status": "matched" if level_fit >= 1 else "partial",
                        "candidate_skill": candidate_skill.get("name", job_skill.name),
                        "matched_by": matched_by,
                        "category": job_skill.category,
                        "importance": job_skill.importance,
                        "importance_label": IMPORTANCE_LABEL.get(job_skill.importance, job_skill.importance),
                        "required_level": job_skill.required_level,
                        "candidate_level": level,
                        "level_gap": max(0, required_rank - candidate_rank),
                        "score": round((LEVEL_SCORE.get(level, 72) * level_fit * 0.85) + min(confidence, 1) * 15),
                        "evidence": evidence or "候选人评估中识别到该能力，但仍需面试补充具体案例。",
                        "evidence_count": evidence_count,
                        "confidence": round(min(0.96, confidence), 2),
                    }
                )
                continue
            gaps.append(
                {
                    "skill": job_skill.name,
                    "status": "missing",
                    "category": job_skill.category,
                    "importance": job_skill.importance,
                    "importance_label": IMPORTANCE_LABEL.get(job_skill.importance, job_skill.importance),
                    "required_level": job_skill.required_level,
                    "required_level_label": LEVEL_LABEL.get(job_skill.required_level, job_skill.required_level),
                    "evidence_count": len(job_skill.evidence),
                    "suggestion": self._gap_suggestion(job_skill),
                    "recommended_action": self._recommended_action(job_skill),
                    "job_evidence": [item.snippet for item in job_skill.evidence[:2]],
                }
            )
        matches.sort(key=lambda item: (item["importance"] != "required", -item["score"], item["skill"]))
        gaps.sort(key=lambda item: (item["importance"] != "required", item["skill"]))
        return matches, gaps

    def _find_candidate_skill(
        self,
        job_skill: SkillRequirement,
        candidate_index: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, str]:
        normalized = self._normalize(job_skill.name)
        if normalized in candidate_index:
            return candidate_index[normalized], "exact"
        compact = self._compact(normalized)
        for key, skill in candidate_index.items():
            if self._compact(key) == compact:
                return skill, "normalized"
        for key, skill in candidate_index.items():
            if len(compact) >= 4 and (compact in self._compact(key) or self._compact(key) in compact):
                return skill, "related_name"
        return None, ""

    def _coverage_score(self, matches: list[dict[str, Any]], skill_names: set[str], *, required: bool) -> int:
        if not skill_names:
            return 100
        score = 0.0
        for name in skill_names:
            match = next((item for item in matches if item["skill"] == name), None)
            if not match:
                continue
            weight = 1.0 if match["status"] == "matched" else 0.65
            if required:
                weight *= 0.8 + min(match["evidence_count"], 2) * 0.1
            score += weight
        return round(100 * score / len(skill_names))

    def _evidence_score(self, matches: list[dict[str, Any]], profile: CandidateProfile) -> int:
        if not matches:
            return 35 if profile.evidence else 20
        backed = sum(1 for item in matches if item["evidence_count"] > 0)
        density = min(1.0, len(profile.evidence) / max(len(matches), 1))
        project_bonus = min(0.16, len(profile.projects) * 0.04)
        return round(min(100, (backed / len(matches)) * 64 + density * 24 + project_bonus * 100))

    def _strengths(self, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        strengths = []
        for item in matches[:6]:
            strengths.append(
                {
                    "skill": item["skill"],
                    "status": item["status"],
                    "evidence": item["evidence"],
                    "score": item["score"],
                    "importance": item["importance"],
                    "candidate_level": item["candidate_level"],
                    "evidence_count": item["evidence_count"],
                    "confidence": item["confidence"],
                    "summary": f"{item['skill']} 已达到 {LEVEL_LABEL.get(item['candidate_level'], item['candidate_level'])} 水平，证据数 {item['evidence_count']} 条。",
                }
            )
        return strengths

    def _risks(
        self,
        gaps: list[dict[str, Any]],
        matches: list[dict[str, Any]],
        profile: CandidateProfile,
        score: int,
    ) -> list[str]:
        risks: list[str] = []
        required_gaps = [item["skill"] for item in gaps if item["importance"] == "required"]
        if required_gaps:
            risks.append(f"必备能力仍有缺口：{self._join(required_gaps[:3])}，需要在终面用情景题验证可补足程度。")
        weak_evidence = [item["skill"] for item in matches if item["evidence_count"] == 0]
        if weak_evidence:
            risks.append(f"{self._join(weak_evidence[:3])} 已被识别为匹配项，但缺少可追溯项目证据。")
        partial = [item["skill"] for item in matches if item["status"] == "partial"]
        if partial:
            risks.append(f"{self._join(partial[:3])} 的候选人水平低于岗位要求，需要确认是否能独立承担。")
        if not profile.projects:
            risks.append("候选人画像缺少项目记录，报告结论需要依赖后续面试补充事实材料。")
        if not profile.behavior_signals:
            risks.append("行为与协作信号不足，建议补充一次场景化决策或团队协作追问。")
        if score < 60 and not risks:
            risks.append("综合匹配低于录用阈值，建议先补充岗位关键能力后再进入下一轮。")
        return risks[:4]

    def _follow_up_questions(
        self,
        gaps: list[dict[str, Any]],
        matches: list[dict[str, Any]],
        risks: list[str],
        graph: JobGraph,
    ) -> list[str]:
        questions: list[str] = []
        for gap in gaps[:3]:
            questions.append(
                f"请结合一个真实项目说明你如何补足或迁移到 {gap['skill']}，包括输入、关键决策和最终结果。"
            )
        for item in [match for match in matches if match["evidence_count"] <= 1][:2]:
            questions.append(f"你在 {item['skill']} 上最能证明能力的一次实践是什么？请说明规模、难点和可验证指标。")
        if graph.scenarios:
            questions.append(f"如果面对“{graph.scenarios[0]}”场景，你会如何拆解任务并控制风险？")
        if risks and not questions:
            questions.append("请补充一个能直接回应当前风险点的项目案例，并说明你的具体角色。")
        return list(dict.fromkeys(questions))[:5]

    def _learning_path(self, gaps: list[dict[str, Any]], graph: JobGraph) -> list[dict[str, Any]]:
        path = []
        for index, gap in enumerate(gaps[:4], start=1):
            scenario = graph.scenarios[(index - 1) % len(graph.scenarios)] if graph.scenarios else "岗位核心业务场景"
            path.append(
                {
                    "step": index,
                    "topic": gap["skill"],
                    "action": gap["suggestion"],
                    "resource": "课程学习 + 项目 Demo + 复盘材料",
                    "scenario": scenario,
                    "expected_output": f"形成一份 {gap['skill']} 小型实践说明或可运行样例。",
                }
            )
        return path

    def _summary(
        self,
        *,
        graph: JobGraph,
        profile: CandidateProfile,
        score: int,
        level: str,
        matches: list[dict[str, Any]],
        gaps: list[dict[str, Any]],
        evidence_coverage: float,
    ) -> str:
        level_text = {"high": "高匹配", "medium": "中等匹配", "low": "低匹配"}[level]
        top_strengths = self._join([item["skill"] for item in matches[:3]]) or "暂无明确优势技能"
        required_gap_count = sum(1 for item in gaps if item["importance"] == "required")
        return (
            f"候选人与 {graph.job_title} 的综合匹配为 {score} 分，属于{level_text}。"
            f"已匹配 {len(matches)} 项岗位能力，主要优势集中在 {top_strengths}；"
            f"仍有 {required_gap_count} 项必备能力缺口。"
            f"评估共形成 {len(profile.evidence)} 条候选人证据，匹配项证据覆盖率为 {round(evidence_coverage * 100)}%。"
        )

    def _interview_recommendation(self, level: str, gaps: list[dict[str, Any]], risks: list[str]) -> str:
        required_gap_count = sum(1 for item in gaps if item["importance"] == "required")
        if level == "high" and required_gap_count == 0:
            return "建议进入终面，可重点确认入职后负责模块与成长路径。"
        if level in {"high", "medium"}:
            return "建议进入技术面试，围绕必备能力缺口和证据薄弱项做定向追问。"
        if risks:
            return "暂不建议直接推进录用，建议先补充关键项目证据后再复评。"
        return "建议补充评估材料后再判断是否进入下一轮。"

    def _gap_suggestion(self, skill: SkillRequirement) -> str:
        level = LEVEL_LABEL.get(skill.required_level, skill.required_level)
        importance = IMPORTANCE_LABEL.get(skill.importance, skill.importance)
        return f"补充 {skill.name} 的{level}实践，最好提供与岗位{importance}要求对应的项目结果、指标或代码样例。"

    def _recommended_action(self, skill: SkillRequirement) -> str:
        if skill.importance == "required":
            return f"终面设置 {skill.name} 情景题，确认候选人能否独立完成关键任务。"
        return f"作为培养项纳入 30-90 天学习计划，观察 {skill.name} 的迁移速度。"

    def _best_evidence(self, skill_name: str, profile: CandidateProfile) -> str:
        normalized = self._normalize(skill_name)
        for evidence in reversed(profile.evidence):
            text = " ".join(str(value) for value in evidence.values())
            if normalized in self._normalize(text):
                return str(evidence.get("snippet") or evidence.get("answer") or evidence.get("summary") or text[:120])
        for project in profile.projects:
            text = " ".join(str(value) for value in project.values())
            if normalized in self._normalize(text):
                return str(project.get("evidence") or text[:120])
        return ""

    def _evidence_count(self, skill_name: str, skill_evidence: str, profile: CandidateProfile) -> int:
        normalized = self._normalize(skill_name)
        count = 1 if skill_evidence else 0
        for evidence in profile.evidence:
            if normalized in self._normalize(" ".join(str(value) for value in evidence.values())):
                count += 1
        for project in profile.projects:
            if normalized in self._normalize(" ".join(str(value) for value in project.values())):
                count += 1
        return count

    def _normalize(self, value: str) -> str:
        text = re.sub(r"[\s_\-（）()]+", "", value.strip().lower())
        return ALIASES.get(text, text)

    def _compact(self, value: str) -> str:
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())

    def _join(self, items: list[str]) -> str:
        return "、".join([item for item in items if item])
