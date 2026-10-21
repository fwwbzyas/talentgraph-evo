from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from agents.assessment.service import AssessmentAgent
from agents.data.service import DataAgent
from agents.data.normalization import classify_domain
from agents.job_graph.service import JobGraphAgent
from agents.match.service import MatchAgent
from contracts import (
    CandidateProfile,
    ImportRequest,
    ValidationFailure,
    ValidationRun,
    ValidationRunRequest,
)
from core.sample_data import generate_demo_jds


DEFAULT_RESUME_CASES = [
    {
        "sample_id": "resume_java_01",
        "text": "本科，4年开发经验。负责Java订单系统，使用Spring Boot、MySQL、Redis、Docker和Kubernetes。",
        "expected": {"skills": ["Java", "Spring Boot", "MySQL", "Redis", "Docker", "Kubernetes"], "experience_years": 4.0, "education": "本科"},
    },
    {
        "sample_id": "resume_ai_01",
        "text": "硕士，3年Python开发经验，建设RAG检索服务，采用LangGraph编排并负责模型评测。",
        "expected": {"skills": ["Python", "RAG", "LangGraph"], "experience_years": 3.0, "education": "硕士"},
    },
    {
        "sample_id": "resume_iot_01",
        "text": "本科，5年物联网平台经验，使用MQTT接入设备，熟悉Python和Docker。",
        "expected": {"skills": ["MQTT", "Python", "Docker"], "experience_years": 5.0, "education": "本科"},
    },
]


class ValidationAgent:
    def __init__(self) -> None:
        self.data_agent = DataAgent()
        self.graph_agent = JobGraphAgent()
        self.assessment_agent = AssessmentAgent()
        self.match_agent = MatchAgent()

    def run(self, request: ValidationRunRequest, run: ValidationRun | None = None) -> ValidationRun:
        run = run or ValidationRun()
        started = perf_counter()
        run.status = "running"
        try:
            raw_jds = generate_demo_jds(request.jd_limit)
            stage_started = perf_counter()
            jd_result = self._evaluate_jds(raw_jds)
            jd_result["duration_ms"] = round((perf_counter() - stage_started) * 1000)
            run.stage = "jd_completed"
            run.stage_progress = 0.4
            run.stage_results.append(jd_result)
            run.failures.extend(jd_result.pop("failures"))

            resume_cases = request.resume_cases or DEFAULT_RESUME_CASES
            stage_started = perf_counter()
            resume_result = self._evaluate_resumes(resume_cases)
            resume_result["duration_ms"] = round((perf_counter() - stage_started) * 1000)
            run.stage = "resume_completed"
            run.stage_progress = 0.7
            run.stage_results.append(resume_result)
            run.failures.extend(resume_result.pop("failures"))

            stage_started = perf_counter()
            match_result = self._evaluate_match(raw_jds, request.match_cases)
            match_result["duration_ms"] = round((perf_counter() - stage_started) * 1000)
            run.stage = "match_completed"
            run.stage_progress = 0.95
            run.stage_results.append(match_result)
            run.failures.extend(match_result.pop("failures"))

            run.metrics = {
                "jd_field_macro_f1": jd_result["macro_f1"],
                "resume_field_macro_f1": resume_result["macro_f1"],
                "match_level_accuracy": match_result["accuracy"],
                "evaluated_samples": {
                    "jd": jd_result["sample_count"],
                    "resume": resume_result["sample_count"],
                    "match": match_result["sample_count"],
                },
                "failure_count": len(run.failures),
            }
            run.provider_status = self.assessment_agent.llm.status()
            run.status = "completed"
            run.stage = "completed"
            run.stage_progress = 1.0
        except Exception as exc:
            run.status = "failed"
            run.stage = "failed"
            run.failures.append(ValidationFailure(stage="jd", sample_id="run", field="execution", message=f"{type(exc).__name__}: {str(exc)[:240]}"))
        run.duration_ms = round((perf_counter() - started) * 1000)
        run.completed_at = datetime.now(UTC)
        return run

    def _evaluate_jds(self, raw_items: list[dict[str, Any]]) -> dict[str, Any]:
        batch = self.data_agent.run(ImportRequest(batch_name="validation_jd", items=raw_items))
        actual_by_id = {item.source_id: item for item in batch.items}
        fields = ("title", "domain", "skill_tags", "responsibilities", "city", "education")
        scores: dict[str, list[float]] = {field: [] for field in fields}
        failures: list[ValidationFailure] = []
        for raw in raw_items:
            sample_id = str(raw["source_id"])
            actual = actual_by_id.get(sample_id)
            if actual is None:
                failures.append(ValidationFailure(stage="jd", sample_id=sample_id, field="record", expected="present", actual=None, message="清洗后样本缺失"))
                for field in fields:
                    scores[field].append(0.0)
                continue
            for field in fields:
                expected = raw.get(field, raw.get("metadata", {}).get(field))
                if field == "domain":
                    expected = classify_domain(
                        f"{raw.get('title', '')} {raw.get('domain', '')} {raw.get('content', '')}"
                    )
                observed = getattr(actual, field)
                score = self._field_score(expected, observed)
                scores[field].append(score)
                if score < 1.0:
                    failures.append(ValidationFailure(stage="jd", sample_id=sample_id, field=field, expected=expected, actual=observed, message="字段提取结果与金标不一致"))
        field_scores = {field: round(sum(values) / max(len(values), 1), 4) for field, values in scores.items()}
        return {"stage": "jd", "sample_count": len(raw_items), "field_scores": field_scores, "macro_f1": round(sum(field_scores.values()) / max(len(field_scores), 1), 4), "failures": failures}

    def _evaluate_resumes(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        fields = ("skills", "experience_years", "education")
        scores: dict[str, list[float]] = {field: [] for field in fields}
        failures: list[ValidationFailure] = []
        for index, case in enumerate(cases):
            sample_id = str(case.get("sample_id", f"resume_{index + 1}"))
            session = self.assessment_agent.start(sample_id, "validation_job", str(case.get("text", "")))
            profile = session.candidate_profile
            expected = case.get("expected", {})
            actual = {
                "skills": [item["name"] for item in profile.get("skills", [])],
                "experience_years": self.assessment_agent._experience_years(profile.get("resume_text", "")),
                "education": self.assessment_agent._education(profile.get("resume_text", "")),
            }
            for field in fields:
                score = self._field_score(expected.get(field), actual.get(field))
                scores[field].append(score)
                if score < 1.0:
                    failures.append(ValidationFailure(stage="resume", sample_id=sample_id, field=field, expected=expected.get(field), actual=actual.get(field), message="档案解析字段与金标不一致"))
        field_scores = {field: round(sum(values) / max(len(values), 1), 4) for field, values in scores.items()}
        return {"stage": "resume", "sample_count": len(cases), "field_scores": field_scores, "macro_f1": round(sum(field_scores.values()) / max(len(field_scores), 1), 4), "failures": failures}

    def _evaluate_match(self, raw_jds: list[dict[str, Any]], custom_cases: list[dict[str, Any]]) -> dict[str, Any]:
        batch = self.data_agent.run(ImportRequest(batch_name="validation_match", items=raw_jds))
        graph = self.graph_agent.run(batch, "Java 后端工程师")
        required = [skill.name for skill in graph.skills if skill.importance == "required"]
        preferred = [skill.name for skill in graph.skills if skill.importance != "required"]
        all_skills = [skill.name for skill in graph.skills]
        cases = custom_cases or [
            {
                "sample_id": "match_high", "skills": all_skills, "skill_level": "advanced",
                "expected_level": "high", "evidence_count": max(12, len(all_skills)), "competency_score": 90,
            },
            {
                "sample_id": "match_medium",
                "skills": [*required, *preferred[: max(1, len(preferred) // 2)]],
                "skill_level": "intermediate", "expected_level": "medium",
                "evidence_count": 6, "competency_score": 72,
            },
            {
                "sample_id": "match_low", "skills": [], "skill_level": "basic",
                "expected_level": "low", "evidence_count": 0, "competency_score": 55,
            },
        ]
        failures: list[ValidationFailure] = []
        correct = 0
        results = []
        for case in cases:
            skills = [
                {"name": name, "level": case.get("skill_level", "intermediate"), "evidence": "验证金标"}
                for name in case.get("skills", [])
            ]
            evidence = [{"type": "validation", "content": f"evidence-{index}"} for index in range(int(case.get("evidence_count", len(skills))))]
            profile = CandidateProfile(
                candidate_id=str(case.get("sample_id")), target_job_id=graph.job_id, skills=skills, evidence=evidence,
                confidence=0.9,
                competency_dimensions=[{
                    "name": "专业技术",
                    "score": int(case.get("competency_score", 75)),
                    "evidence_count": len(skills),
                }],
            )
            report = self.match_agent.run(graph, profile)
            expected = str(case.get("expected_level"))
            is_correct = report.level == expected
            correct += int(is_correct)
            results.append({"sample_id": case.get("sample_id"), "expected": expected, "actual": report.level, "score": report.score})
            if not is_correct:
                failures.append(ValidationFailure(stage="match", sample_id=str(case.get("sample_id")), field="level", expected=expected, actual=report.level, message="匹配等级与金标不一致"))
        return {"stage": "match", "sample_count": len(cases), "accuracy": round(correct / max(len(cases), 1), 4), "cases": results, "failures": failures}

    def _field_score(self, expected: Any, actual: Any) -> float:
        if isinstance(expected, list) or isinstance(actual, list):
            expected_set = {str(item).casefold() for item in (expected or [])}
            actual_set = {str(item).casefold() for item in (actual or [])}
            if not expected_set and not actual_set:
                return 1.0
            precision = len(expected_set & actual_set) / max(len(actual_set), 1)
            recall = len(expected_set & actual_set) / max(len(expected_set), 1)
            return 2 * precision * recall / max(precision + recall, 1e-9)
        return 1.0 if expected == actual else 0.0
