from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import re
from typing import Any

from agents.data.normalization import (
    DOMAIN_KEYWORDS,
    classify_domain,
    clean_text,
    extract_skills,
    parse_datetime,
)
from contracts import DataAuditRecord


POLLUTED_TAG_PATTERN = re.compile(
    r"(本科|硕士|博士|大专|学历|经验|应届|五险|一金|双休|年终奖|带薪|团建|餐补|房补|"
    r"节日福利|定期体检|弹性工作|股票期权|招聘|急聘|\d+[年以上])",
    re.IGNORECASE,
)
NON_JOB_PATTERN = re.compile(
    r"(课程推广|电话销售|招生|学员转化|加盟|招商|引流|带货|保险代理|高薪兼职)",
    re.IGNORECASE,
)
JOB_EVIDENCE_PATTERN = re.compile(
    r"(岗位职责|工作职责|任职要求|职位要求|负责|开发|设计|建设|维护|熟悉|掌握|经验|"
    r"responsibilit|requirement|qualif|develop|build|design)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class GovernanceAssessment:
    status: str
    reasons: list[str] = field(default_factory=list)
    confidence: float = 1.0
    evidence_snippets: list[dict[str, Any]] = field(default_factory=list)
    field_changes: dict[str, dict[str, Any]] = field(default_factory=dict)
    rule_assessment: dict[str, Any] = field(default_factory=dict)


class DataGovernanceAgent:
    """Deterministic first-pass governance with an explicit gray-zone contract."""

    def assess_recruitment(
        self,
        raw: dict[str, Any],
        normalized: dict[str, Any] | None,
        normalization_issues: list[str] | None = None,
    ) -> GovernanceAssessment:
        reasons = list(dict.fromkeys(normalization_issues or []))
        title = clean_text(raw.get("title") or raw.get("position") or raw.get("name"))
        content = clean_text(raw.get("raw_content") or raw.get("content") or raw.get("description"))
        supplied_tags = raw.get("skill_tags") or raw.get("tags") or []
        supplied_tags = supplied_tags if isinstance(supplied_tags, list) else []
        snippets: list[dict[str, Any]] = []

        polluted = [clean_text(tag) for tag in supplied_tags if POLLUTED_TAG_PATTERN.search(clean_text(tag))]
        if polluted:
            reasons.append("skill_tag_pollution")
            snippets.append({"field": "tags", "text": "、".join(polluted[:8]), "rule": "non_skill_tag"})

        title_skills = set(extract_skills(title))
        content_skills = set(extract_skills(content))
        title_domain = classify_domain(title)
        content_domain = classify_domain(content)
        unsupported_title_skills = sorted(title_skills - content_skills)
        domain_conflict = bool(title_domain and content_domain and title_domain != content_domain)
        if title_skills and not title_skills.intersection(content_skills) and (domain_conflict or unsupported_title_skills):
            reasons.append("title_content_mismatch")
            snippets.append({
                "field": "title",
                "text": title,
                "rule": "title_skill_not_supported",
                "unsupported_skills": unsupported_title_skills[:8],
                "content_domain": content_domain,
            })

        if NON_JOB_PATTERN.search(content) or (content and not JOB_EVIDENCE_PATTERN.search(content)):
            reasons.append("non_job_content")
            snippets.append({"field": "content", "text": content[:260], "rule": "missing_job_structure"})

        normalized_skills = list((normalized or {}).get("skill_tags") or [])
        domain_hits = sum(
            any(term.casefold() in content.casefold() for term in terms)
            for terms in DOMAIN_KEYWORDS.values()
        )
        if len(normalized_skills) >= 18 or (len(normalized_skills) >= 12 and domain_hits >= 3):
            reasons.append("skill_inflation")
            snippets.append({
                "field": "skill_tags",
                "text": "、".join(normalized_skills[:20]),
                "rule": "excessive_cross_domain_skills",
            })

        salary_min = _number(raw.get("salary_min_k"))
        salary_max = _number(raw.get("salary_max_k"))
        if (
            salary_min is not None and salary_max is not None and salary_min > salary_max
        ) or max(salary_min or 0, salary_max or 0) > 500:
            reasons.append("salary_anomaly")
            snippets.append({
                "field": "salary",
                "text": f"{salary_min}-{salary_max}K",
                "rule": "invalid_salary_range",
            })

        published_at = parse_datetime(raw.get("published_at") or raw.get("date"))
        if published_at and published_at < datetime.now(UTC) - timedelta(days=365):
            reasons.append("stale_evidence")

        field_changes = self._field_changes(raw, normalized or {})
        reasons = list(dict.fromkeys(reasons))
        hard_reject = normalized is None or "outside_target_scope" in reasons or "non_job_content" in reasons
        gray = any(reason in reasons for reason in ("title_content_mismatch", "skill_inflation", "salary_anomaly"))
        status = "rejected" if hard_reject else "manual_review" if gray else "accepted"
        penalty = {
            "skill_tag_pollution": 0.06,
            "title_content_mismatch": 0.32,
            "non_job_content": 0.55,
            "skill_inflation": 0.2,
            "salary_anomaly": 0.14,
            "stale_evidence": 0.1,
            "outside_target_scope": 0.65,
        }
        confidence = max(0.0, min(1.0, 0.98 - sum(penalty.get(reason, 0.08) for reason in reasons)))
        return GovernanceAssessment(
            status=status,
            reasons=reasons,
            confidence=round(confidence, 3),
            evidence_snippets=snippets,
            field_changes=field_changes,
            rule_assessment={
                "version": "governance-rules-v1",
                "title_domain": title_domain,
                "content_domain": content_domain,
                "title_skills": sorted(title_skills),
                "content_skill_count": len(content_skills),
                "polluted_tags": polluted,
                "requires_llm": gray,
            },
        )

    def audit_record(
        self,
        raw: dict[str, Any],
        normalized: dict[str, Any] | None,
        assessment: GovernanceAssessment,
        *,
        source_category: str,
        collection_run_id: str | None = None,
    ) -> DataAuditRecord:
        source_platform = str(raw.get("source_platform") or "unknown")
        raw_source_id = str(raw.get("source_id") or raw.get("signal_id") or raw.get("id") or "unknown")
        source_id = str((normalized or {}).get("source_id") or raw_source_id)
        record_type = (
            "quality_rejection" if assessment.status == "rejected"
            else "pending_review" if assessment.status == "manual_review"
            else "field_correction" if assessment.field_changes or assessment.reasons
            else "accepted"
        )
        return DataAuditRecord(
            source_category=source_category,
            source_id=source_id,
            source_platform=source_platform,
            source_url=(normalized or {}).get("source_url") or raw.get("source_url") or raw.get("url"),
            title=(normalized or {}).get("title") or raw.get("title") or raw.get("position"),
            record_type=record_type,
            status=assessment.status,
            reasons=assessment.reasons,
            raw_item=raw,
            normalized_item=normalized or {},
            field_changes=assessment.field_changes,
            evidence_snippets=assessment.evidence_snippets,
            rule_assessment=assessment.rule_assessment,
            final_confidence=assessment.confidence,
            graph_publish_status="published" if assessment.status == "accepted" else "blocked",
            review_status="approved" if assessment.status == "accepted" else "pending",
            collection_run_id=collection_run_id,
        )

    @staticmethod
    def _field_changes(raw: dict[str, Any], normalized: dict[str, Any]) -> dict[str, dict[str, Any]]:
        aliases = {
            "title": raw.get("title") or raw.get("position"),
            "company": raw.get("company") or raw.get("company_name"),
            "city": raw.get("city") or raw.get("location"),
            "education": raw.get("education"),
            "skill_tags": raw.get("skill_tags") or raw.get("tags") or [],
        }
        output: dict[str, dict[str, Any]] = {}
        for field_name, before in aliases.items():
            after = normalized.get(field_name)
            if _comparable(before) != _comparable(after):
                output[field_name] = {"before": before, "after": after}
        return output


def _comparable(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(clean_text(item).casefold() for item in value if clean_text(item))
    return clean_text(value).casefold() if value is not None else None


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
