from __future__ import annotations

import json
import os
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from agents.llm import OpenAICompatibleClient
from agents.data.governance import DataGovernanceAgent
from agents.data.normalization import normalize_recruitment_item
from contracts import CleanedDataBatch, CleanedDataItem, DataAuditRecord, ImportRequest


class DataAgent:
    computer_domains = ("AI", "大模型", "后端", "Java", "大数据", "IoT", "智能系统", "云原生", "测试")

    def __init__(self, llm: OpenAICompatibleClient | None = None) -> None:
        self.llm = llm or OpenAICompatibleClient()
        self.governance = DataGovernanceAgent()
        self.learning_policy: dict = {}

    def run(self, request: ImportRequest) -> CleanedDataBatch:
        raw_items = [dict(item) for item in (request.items or [])]
        provider_status = {
            **self.llm.status(),
            "normalization_mode": "deterministic_first_pass",
            "llm_deferred": True,
            "gray_zone_only": True,
        }
        cleaned: list[CleanedDataItem] = []
        rejection_reasons: Counter[str] = Counter()
        rejected_records: list[dict] = []
        audit_records: list[DataAuditRecord] = []
        for item in raw_items:
            normalized, issues = normalize_recruitment_item(item, self.learning_policy)
            assessment = self.governance.assess_recruitment(item, normalized, issues)
            if normalized is not None and normalized["quality_score"] < request.min_quality:
                assessment.reasons = list(dict.fromkeys([*assessment.reasons, "below_quality_threshold"]))
                assessment.status = "rejected"
                assessment.confidence = min(assessment.confidence, 0.35)
            audit_record = self.governance.audit_record(
                item,
                normalized,
                assessment,
                source_category="recruitment",
            )
            audit_records.append(audit_record)
            if normalized is None or assessment.status != "accepted":
                rejection_reasons.update(assessment.reasons or ["normalization_failed"])
                rejected_records.append({
                    "source_id": audit_record.source_id,
                    "source_platform": item.get("source_platform"),
                    "title": item.get("title") or item.get("position"),
                    "reasons": assessment.reasons or ["normalization_failed"],
                    "quality_score": normalized.get("quality_score") if normalized else None,
                    "source_url": audit_record.source_url,
                    "raw_item": item,
                    "audit_id": audit_record.audit_id,
                    "record_type": audit_record.record_type,
                })
                continue
            cleaned.append(CleanedDataItem.model_validate(normalized))
        avg = round(sum(i.quality_score for i in cleaned) / max(len(cleaned), 1), 2)
        return CleanedDataBatch(
            batch_name=request.batch_name,
            items=cleaned,
            quality_summary={
                "total": len(cleaned),
                "fetched": len(raw_items),
                "accepted": len(cleaned),
                "rejected": len(raw_items) - len(cleaned),
                "duplicates": 0,
                "rejection_reasons": dict(rejection_reasons),
                "rejected_records": rejected_records[:200],
                "audit_records": [record.model_dump(mode="json") for record in audit_records],
                "duplicate_records": [],
                "avg_quality": avg,
                "computer_scope": True,
                "computer_scope_items": sum(1 for item in cleaned if item.quality_score >= 60),
                "companies": len({item.company for item in cleaned if item.company}),
                "cities": len({item.city for item in cleaned if item.city}),
                "active_jobs": sum(item.job_status == "active" for item in cleaned),
                "today_changes": {
                    kind: sum(item.change_type == kind for item in cleaned)
                    for kind in ("new", "updated", "offline")
                },
                "salary_range_k": {
                    "min": min((item.salary_min_k for item in cleaned if item.salary_min_k is not None), default=None),
                    "max": max((item.salary_max_k for item in cleaned if item.salary_max_k is not None), default=None),
                },
                "provider_status": provider_status,
            },
        )

    def _normalize_with_llm(self, items: list[dict]) -> tuple[list[dict], dict]:
        if not self.llm.configured or not items:
            return items, self.llm.status()
        live_collection = all(item.get("collection_mode") == "live" for item in items)
        live_llm_enabled = os.getenv("TALENTGRAPH_LLM_LIVE_NORMALIZATION", "0").strip().lower() in {"1", "true", "yes"}
        if live_collection and not live_llm_enabled:
            return [dict(item) for item in items], {
                **self.llm.status(),
                "normalization_mode": "deterministic_realtime",
                "llm_deferred": True,
            }
        enriched = [dict(item) for item in items]
        status = self.llm.status()
        for offset in range(0, len(enriched), 30):
            chunk = enriched[offset : offset + 30]
            payload = [
                {"source_id": item.get("source_id"), "title": item.get("title"), "content": str(item.get("content", ""))[:1800]}
                for item in chunk
            ]
            result = self.llm.generate_json(
                system_prompt=(
                    "你是招聘数据治理 Agent。只输出 JSON 对象 {items:[...]}。"
                    "每项必须保留 source_id，并从原文抽取 title、domain、company、city、education、"
                    "experience_min_years、experience_max_years、salary_min_k、salary_max_k、skill_tags、responsibilities。"
                    "skill_tags 和 responsibilities 必须是数组，不得编造原文不存在的企业或薪资。"
                ),
                user_prompt=json.dumps({"items": payload}, ensure_ascii=False),
                fallback={"items": []},
            )
            status = result.provider_status
            by_id = {str(item.get("source_id")): item for item in result.data.get("items", []) if isinstance(item, dict)}
            for raw in chunk:
                normalized = by_id.get(str(raw.get("source_id")))
                if not normalized:
                    continue
                for key, value in normalized.items():
                    if key != "source_id" and value not in (None, "", []):
                        raw[key] = value
        return enriched, status

    def review_gray_audits(self, records: list[DataAuditRecord], app_store: Any) -> None:
        """Review a bounded gray-zone batch without blocking collection or auto-publishing facts."""
        if not self.llm.configured or not records:
            return
        max_items = max(1, int(os.getenv("TALENTGRAPH_LLM_GOVERNANCE_MAX_PER_RUN", "24")))
        ratio = min(0.2, max(0.1, float(os.getenv("TALENTGRAPH_LLM_GOVERNANCE_RATIO", "0.15"))))
        selected = records[: min(max_items, max(1, round(len(records) * ratio)))]
        for offset in range(0, len(selected), 10):
            chunk = selected[offset: offset + 10]
            payload = [{
                "audit_id": record.audit_id,
                "title": record.title,
                "content": str(record.raw_item.get("content") or record.raw_item.get("description") or "")[:1200],
                "rule_reasons": record.reasons,
                "skills": record.normalized_item.get("skill_tags", []),
            } for record in chunk]
            result = self.llm.generate_json(
                system_prompt=(
                    "你是招聘数据语义复核 Agent。只输出 JSON 对象 {items:[...]}。"
                    "每项包含 audit_id、verdict(accept/reject/manual)、confidence、reasons、evidence。"
                    "仅依据给定标题和正文判断标题正文一致性、是否为真实技术岗位、是否技能通胀。"
                    "不得补充输入中不存在的事实，也不得自动发布岗位或能力。"
                ),
                user_prompt=json.dumps({"items": payload}, ensure_ascii=False),
                fallback={"items": []},
            )
            by_id = {
                str(item.get("audit_id")): item
                for item in result.data.get("items", [])
                if isinstance(item, dict) and item.get("audit_id")
            }
            updates = []
            for record in chunk:
                reviewed = by_id.get(record.audit_id)
                if not reviewed:
                    continue
                llm_confidence = _bounded_float(reviewed.get("confidence"), 0.5)
                updates.append(record.model_copy(update={
                    "llm_assessment": {
                        "verdict": reviewed.get("verdict", "manual"),
                        "confidence": llm_confidence,
                        "reasons": reviewed.get("reasons", []),
                        "evidence": reviewed.get("evidence", []),
                        "provider_status": result.provider_status,
                    },
                    "final_confidence": round((record.final_confidence * 0.65) + (llm_confidence * 0.35), 3),
                    "updated_at": datetime.now(UTC),
                }))
            app_store.save_data_audits(updates)


def _bounded_float(value: Any, default: float) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default
