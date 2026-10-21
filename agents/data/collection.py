from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
import logging
import os
import random
from threading import Event, Lock, Thread
from time import perf_counter
from typing import Any

from agents.data.normalization import normalize_community_signal
from agents.data.normalization import normalize_recruitment_item
from agents.data.evidence import EvidenceIntelligenceService
from agents.data.browser_sessions import browser_sessions
from agents.data.service import DataAgent
from agents.data.source_policy import (
    CORE_RECRUITMENT_SOURCE_IDS,
    RECRUITMENT_SOURCE_SET,
    SUPPLEMENTAL_INTERVAL_MINUTES,
    SUPPLEMENTAL_ITEMS_PER_RUN,
    SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS,
)
from agents.data.sources import DataSource, default_sources, source_catalog, timed_fetch
from agents.data.supplemental_recruitment import CollectionRiskControlError, CollectionTransientSourceError
from contracts import (
    CleanedDataBatch,
    CleanedDataItem,
    CollectionScheduleRequest,
    CollectionStrategyRequest,
    CommunitySignal,
    DataAuditRecord,
    DataCollectionRequest,
    DataCollectionRun,
    DataQualityRejection,
    ImportRequest,
    SourceCollectionResult,
    SourceCollectionStrategy,
)
from core.store import AppStore, store


logger = logging.getLogger(__name__)


class DataCollectionAgent:
    def __init__(
        self,
        *,
        data_agent: DataAgent | None = None,
        sources: dict[str, DataSource] | None = None,
        app_store: AppStore | None = None,
    ) -> None:
        self.data_agent = data_agent or DataAgent()
        self.sources = sources or default_sources()
        self.store = app_store or store
        self.evidence_service = EvidenceIntelligenceService()
        self._semantic_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="semantic-governance")
        self._progress_lock = Lock()
        boss = self.sources.get("boss")
        self.available_cities = list(getattr(boss, "available_cities", {"全国": "100010000"}))
        self.available_queries = list(getattr(boss, "available_queries", getattr(boss, "queries", ())))
        self.source_strategies: dict[str, dict[str, Any]] = {}
        stored_strategy = self.store.get_setting("collection_strategy")
        if stored_strategy:
            self.apply_strategy(CollectionStrategyRequest.model_validate(stored_strategy), persist=False)

    def catalog(self) -> list[dict[str, Any]]:
        return source_catalog(self.sources)

    def apply_strategy(self, strategy: CollectionStrategyRequest, *, persist: bool = True) -> dict[str, Any]:
        configured: dict[str, dict[str, Any]] = {}
        for source_id, source in self.sources.items():
            source_config = strategy.sources.get(source_id)
            if source_config is None:
                is_primary = source_id in CORE_RECRUITMENT_SOURCE_IDS
                is_supplemental = source_id in SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS
                baseline = strategy.sources.get("zhaopin") or strategy.sources.get("boss")
                default_cities = baseline.cities if is_supplemental and baseline else strategy.cities
                default_queries = baseline.job_queries if is_supplemental and baseline else strategy.job_queries
                source_config = SourceCollectionStrategy(
                    enabled=strategy.enabled and bool(getattr(source, "enabled", True)),
                    mode="hybrid" if is_primary else "discovery",
                    min_interval_minutes=(
                        strategy.min_interval_minutes if is_primary else
                        SUPPLEMENTAL_INTERVAL_MINUTES if is_supplemental else 1440
                    ),
                    max_interval_minutes=(
                        strategy.max_interval_minutes if is_primary else
                        SUPPLEMENTAL_INTERVAL_MINUTES if is_supplemental else 2880
                    ),
                    items_per_run=SUPPLEMENTAL_ITEMS_PER_RUN if is_supplemental else strategy.items_per_source,
                    cities=default_cities,
                    job_queries=default_queries,
                    discovery_ratio=(0.6 if source_id == "boss" else 0.5) if is_primary else 1,
                    revisit_after_hours=(
                        12 if source_id == "boss" else
                        7 * 24 if is_supplemental else 24
                    ),
                )
            else:
                source_config = source_config.model_copy(update={
                    "enabled": source_config.enabled and bool(getattr(source, "enabled", True)),
                })
            available_cities = list(getattr(source, "available_cities", ()))
            available_queries = list(getattr(source, "available_queries", getattr(source, "queries", ())))
            cities = [city for city in source_config.cities if city in available_cities] or (["全国"] if available_cities else [])
            queries = [query for query in source_config.job_queries if query in available_queries] or available_queries
            source_config = source_config.model_copy(update={"cities": cities, "job_queries": queries})
            configured[source_id] = source_config.model_dump(mode="json")
            if hasattr(source, "configure"):
                source.configure(
                    cities=cities, queries=queries, items_per_run=source_config.items_per_run,
                    mode=source_config.mode, discovery_ratio=source_config.discovery_ratio,
                    revisit_after_hours=source_config.revisit_after_hours,
                )
        self.source_strategies = configured
        normalized = strategy.model_copy(update={"sources": {key: SourceCollectionStrategy.model_validate(value) for key, value in configured.items()}})
        if persist:
            self.store.save_setting("collection_strategy", normalized.model_dump(mode="json"))
        return {"enabled": any(item["enabled"] for item in configured.values()), "sources": configured}

    def collect(self, request: DataCollectionRequest, *, run: DataCollectionRun | None = None) -> DataCollectionRun:
        run = run or self.prepare_run(request)
        self.data_agent.learning_policy = self.store.get_setting("audit_learning_policy", {})
        all_jobs = []
        all_signals: list[CommunitySignal] = []
        seen_signal_hashes: set[str] = set()
        rejection_reasons: Counter[str] = Counter()
        quality_rejections: list[DataQualityRejection] = []
        data_audits: list[DataAuditRecord] = []
        refresh_evidence_cache = False

        known_sources = [(source_id, self.sources[source_id]) for source_id in request.source_ids if source_id in self.sources]
        now = datetime.now(UTC)
        run.source_results = [
            item.model_copy(update={"status": "running", "phase": "fetching", "started_at": now})
            if item.source_id in self.sources else item
            for item in run.source_results
        ]
        self.store.save_collection_run(run)
        workers = max(1, min(len(known_sources), int(os.getenv("TALENTGRAPH_COLLECTION_WORKERS", "4"))))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="source-collector") as executor:
            futures = {
                executor.submit(self._collect_source, run.run_id, source_id, source, request): source_id
                for source_id, source in known_sources
            }
            for future in as_completed(futures):
                source_id = futures[future]
                payload = future.result()
                result = payload["result"]
                run.source_results = [result if item.source_id == source_id else item for item in run.source_results]
                rejection_reasons.update(payload["rejection_reasons"])
                quality_rejections.extend(payload["quality_rejections"])
                data_audits.extend(payload["data_audits"])
                run.duplicate_count += payload["duplicates"]
                run.rejected_count += result.rejected
                if result.source_category == "recruitment":
                    run.recruitment_fetched += result.fetched
                    for item in payload["jobs"]:
                        all_jobs.append(item)
                        run.recruitment_accepted += 1
                else:
                    run.community_fetched += result.fetched
                    for signal in payload["signals"]:
                        if signal.dedup_hash in seen_signal_hashes:
                            run.duplicate_count += 1
                            continue
                        seen_signal_hashes.add(signal.dedup_hash)
                        all_signals.append(signal)
                        run.community_accepted += 1
                self.store.save_collection_run(run)

        final_batch = CleanedDataBatch(
            batch_name=f"live_collection_{run.started_at:%Y%m%d_%H%M%S}",
            items=all_jobs,
            quality_summary={
                "fetched": run.recruitment_fetched,
                "accepted": len(all_jobs),
                "avg_quality": round(sum(item.quality_score for item in all_jobs) / max(1, len(all_jobs)), 2),
                "domains": dict(Counter(item.domain for item in all_jobs)),
                "sources": dict(Counter(item.source_platform for item in all_jobs)),
                "rejection_reasons": dict(rejection_reasons),
                "primary_evidence_only": True,
            },
        )
        run.batch_id = final_batch.batch_id
        if request.persist:
            self.store.batches[final_batch.batch_id] = final_batch
            changes = self.store.ingest_live_batch(final_batch)
            self.store.save_community_signals(all_signals)
            self.store.save_quality_rejections(quality_rejections)
            self._apply_cross_source_evidence(data_audits, all_jobs)
            data_audits.extend(self._job_change_audits(changes.get("events", []), run.run_id))
            self.store.save_data_audits(data_audits)
            if all_jobs or all_signals:
                # The graph reads the new jobs directly. Expensive whole-corpus
                # copy/trend indexes are refreshed off the request path so a
                # small incremental crawl does not wait on ~10k historical JDs.
                refresh_evidence_cache = True
            gray_records = [record for record in data_audits if record.status == "manual_review"]
            if gray_records and self.data_agent.llm.configured:
                self._semantic_executor.submit(self.data_agent.review_gray_audits, gray_records, self.store)
            run.new_count = changes["new"]
            run.updated_count = changes["updated"]
            run.unchanged_count = changes["unchanged"]
            run.exact_duplicate_count = changes["exact_duplicate"]
            run.repost_count = changes["repost"]
        run.quality_summary = {
            **final_batch.quality_summary,
            "community_signals": len(all_signals),
            "community_domains": dict(Counter(item.domain for item in all_signals)),
            "community_sources": dict(Counter(item.source_platform for item in all_signals)),
            "evidence_policy": {"recruitment": "primary", "community_signal": "auxiliary"},
        }
        failures = sum(result.status == "failed" for result in run.source_results)
        run.status = "failed" if failures == len(run.source_results) else "partial" if failures else "completed"
        run.completed_at = datetime.now(UTC)
        saved_run = self.store.save_collection_run(run)
        if refresh_evidence_cache:
            self._semantic_executor.submit(self._refresh_evidence_cache_safe)
        return saved_run

    def _refresh_evidence_cache_safe(self) -> None:
        try:
            self.rebuild_evidence_intelligence()
        except Exception:
            logger.exception("background evidence cache refresh failed")

    def prepare_run(self, request: DataCollectionRequest) -> DataCollectionRun:
        run = DataCollectionRun(source_results=[
            SourceCollectionResult(
                source_id=source_id,
                source_category=getattr(self.sources.get(source_id), "source_category", "recruitment"),
                status="queued" if source_id in self.sources else "failed",
                phase="queued" if source_id in self.sources else "failed",
                error=None if source_id in self.sources else "unknown source",
            )
            for source_id in request.source_ids
        ])
        return self.store.save_collection_run(run)

    def _collect_source(self, run_id: str, source_id: str, source: DataSource, request: DataCollectionRequest) -> dict[str, Any]:
        started_at = datetime.now(UTC)
        started = perf_counter()
        stage_durations: dict[str, int] = {}
        jobs = []
        signals: list[CommunitySignal] = []
        rejections: list[DataQualityRejection] = []
        data_audits: list[DataAuditRecord] = []
        reasons: Counter[str] = Counter()
        duplicates = 0
        try:
            if source_id in RECRUITMENT_SOURCE_SET and hasattr(source, "configure"):
                if source_id in CORE_RECRUITMENT_SOURCE_IDS and getattr(source, "access_mode", "") == "browser_assisted_research":
                    session = browser_sessions.ensure_ready(source_id)
                    if session["authentication"] != "ready":
                        state = "安全验证" if session["authentication"] == "verification_required" else "账号登录"
                        raise RuntimeError(f"{source_id} 后台采集会话需要完成{state}")
                settings = self.source_strategies.get(source_id, {})
                queries = request.query_overrides.get(source_id) or settings.get("job_queries") or list(getattr(source, "queries", ()))
                cities = request.city_overrides.get(source_id) or settings.get("cities") or ["全国"]
                mode = request.collection_mode_override or settings.get("mode", "hybrid")
                source.configure(
                    cities=cities,
                    queries=queries,
                    items_per_run=request.max_items_per_source if request.full_scan_chunk else int(settings.get("items_per_run", request.max_items_per_source)),
                    mode=mode,
                    discovery_ratio=float(settings.get("discovery_ratio", 0.5)),
                    revisit_after_hours=0 if request.full_scan_chunk else float(settings.get("revisit_after_hours", 24)),
                    stop_at_end=request.full_scan_chunk,
                )
                if request.reset_scan_cursor and queries:
                    source.reset_cursor(queries[0], cities[0])
            if hasattr(source, "seed_seen"):
                source.seed_seen([
                    job.source_id for job in self.store.jobs.values() if job.source_platform == source_id
                ])
            fetch_started = perf_counter()
            source_limit = request.max_items_per_source if request.full_scan_chunk else min(
                request.max_items_per_source,
                int(self.source_strategies.get(source_id, {}).get("items_per_run", request.max_items_per_source)),
            )
            raw_items, _ = timed_fetch(source, max_items=source_limit, lookback_hours=request.lookback_hours)
            stage_durations["fetch"] = round((perf_counter() - fetch_started) * 1000)
            self._update_source_progress(run_id, source_id, "normalizing", fetched=len(raw_items), stage_durations=stage_durations)
            normalize_started = perf_counter()
            if source.source_category == "recruitment":
                batch = self.data_agent.run(ImportRequest(
                    batch_name=f"{run_id}_{source_id}", items=raw_items,
                    min_quality=request.min_job_quality, strict_scope=True,
                ))
                jobs = batch.items
                data_audits = [
                    DataAuditRecord.model_validate({
                        **record,
                        "collection_run_id": run_id,
                    })
                    for record in batch.quality_summary.get("audit_records", [])
                ]
                reasons.update(batch.quality_summary.get("rejection_reasons", {}))
                duplicates = batch.quality_summary.get("duplicates", 0)
                for record_type, records in (
                    ("quality_rejection", batch.quality_summary.get("rejected_records", [])),
                    ("duplicate", batch.quality_summary.get("duplicate_records", [])),
                ):
                    rejections.extend(DataQualityRejection(
                        source_category="recruitment", source_id=str(record.get("source_id", "unknown")),
                        source_platform=record.get("source_platform") or source_id, title=record.get("title"),
                        reasons=record.get("reasons") or ["rejected"], quality_score=record.get("quality_score"),
                        collection_run_id=run_id, record_type=record_type, source_url=record.get("source_url"),
                        raw_item=record.get("raw_item") or {}, matched_source_id=record.get("matched_source_id"),
                    ) for record in records)
                rejected = batch.quality_summary.get("rejected", 0)
            else:
                rejected = 0
                seen: set[str] = set()
                for raw in raw_items:
                    normalized, issues = normalize_community_signal(raw)
                    if normalized is None or normalized["quality_score"] < request.min_signal_quality:
                        issue_list = issues or ["below_signal_quality_threshold"]
                        reasons.update(issue_list)
                        rejected += 1
                        rejections.append(DataQualityRejection(
                            source_category="community_signal",
                            source_id=str(raw.get("signal_id") or raw.get("source_id") or "unknown"),
                            source_platform=source_id, title=raw.get("title"), reasons=issue_list,
                            quality_score=normalized.get("quality_score") if normalized else None,
                            collection_run_id=run_id, source_url=raw.get("source_url"), raw_item=raw,
                        ))
                        data_audits.append(DataAuditRecord(
                            source_category="community_signal",
                            source_id=str(raw.get("signal_id") or raw.get("source_id") or "unknown"),
                            source_platform=source_id,
                            source_url=raw.get("source_url"),
                            title=raw.get("title"),
                            record_type="quality_rejection",
                            status="rejected",
                            reasons=issue_list,
                            raw_item=raw,
                            rule_assessment={"version": "community-rules-v1", "issues": issue_list},
                            final_confidence=0.2,
                            graph_publish_status="blocked",
                            collection_run_id=run_id,
                        ))
                        continue
                    if normalized["dedup_hash"] in seen:
                        duplicates += 1
                        continue
                    seen.add(normalized["dedup_hash"])
                    signals.append(CommunitySignal.model_validate(normalized))
                    data_audits.append(DataAuditRecord(
                        source_category="community_signal",
                        source_id=normalized["signal_id"],
                        source_platform=source_id,
                        source_url=normalized["source_url"],
                        title=normalized["title"],
                        record_type="accepted",
                        status="accepted",
                        raw_item=raw,
                        normalized_item=normalized,
                        rule_assessment={
                            "version": "community-rules-v1",
                            "evidence_role": "auxiliary",
                            "can_publish_job_fact": False,
                        },
                        final_confidence=min(1, normalized["quality_score"] / 100),
                        graph_publish_status="auxiliary_only",
                        review_status="approved",
                        collection_run_id=run_id,
                    ))
            stage_durations["normalize"] = round((perf_counter() - normalize_started) * 1000)
            completed_at = datetime.now(UTC)
            result = SourceCollectionResult(
                source_id=source_id, source_category=source.source_category, status="success", phase="completed",
                fetched=len(raw_items), accepted=len(jobs) + len(signals), rejected=rejected,
                scanned=int(getattr(source, "last_fetch_stats", {}).get("scanned", len(raw_items))),
                discovery_candidates=int(getattr(source, "last_fetch_stats", {}).get("discovery_candidates", len(raw_items))),
                monitor_candidates=int(getattr(source, "last_fetch_stats", {}).get("monitor_candidates", 0)),
                reached_end=bool(getattr(source, "last_fetch_stats", {}).get("reached_end", False)),
                end_reason=getattr(source, "last_fetch_stats", {}).get("end_reason"),
                duration_ms=round((perf_counter() - started) * 1000), stage_durations_ms=stage_durations,
                started_at=started_at, completed_at=completed_at,
            )
        except (CollectionRiskControlError, CollectionTransientSourceError) as exc:
            # Verification/WAF and bounded network outages are isolated to this
            # supplemental source. Keep the operator panel quiet while retaining
            # an auditable server log and a machine-readable end reason.
            logger.warning(
                "supplemental source paused: source=%s reason=%s evidence=%s url=%s",
                exc.source_id,
                type(exc).__name__,
                exc.evidence,
                getattr(exc, "url", ""),
            )
            fetch_stats = getattr(source, "last_fetch_stats", {})
            result = SourceCollectionResult(
                source_id=source_id,
                source_category=source.source_category,
                status="success",
                phase="completed",
                scanned=int(fetch_stats.get("scanned", 0)),
                discovery_candidates=int(fetch_stats.get("discovery_candidates", 0)),
                monitor_candidates=int(fetch_stats.get("monitor_candidates", 0)),
                reached_end=False,
                end_reason=fetch_stats.get("end_reason"),
                duration_ms=round((perf_counter() - started) * 1000),
                stage_durations_ms=stage_durations,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
        except Exception as exc:
            fetch_stats = getattr(source, "last_fetch_stats", {})
            result = SourceCollectionResult(
                source_id=source_id, source_category=source.source_category, status="failed", phase="failed",
                scanned=int(fetch_stats.get("scanned", 0)),
                discovery_candidates=int(fetch_stats.get("discovery_candidates", 0)),
                monitor_candidates=int(fetch_stats.get("monitor_candidates", 0)),
                reached_end=bool(fetch_stats.get("reached_end", False)),
                duration_ms=round((perf_counter() - started) * 1000), stage_durations_ms=stage_durations,
                started_at=started_at, completed_at=datetime.now(UTC),
                error=f"{type(exc).__name__}: {str(exc)[:240]}",
            )
        return {
            "result": result, "jobs": jobs, "signals": signals, "quality_rejections": rejections,
            "data_audits": data_audits, "rejection_reasons": reasons, "duplicates": duplicates,
        }

    def _apply_cross_source_evidence(
        self,
        records: list[DataAuditRecord],
        new_jobs: list,
    ) -> None:
        jobs_by_id = {job.source_id: job for job in [*self.store.jobs.values(), *new_jobs]}
        all_jobs = list(jobs_by_id.values())
        for index, record in enumerate(records):
            if record.source_category != "recruitment" or record.status != "accepted":
                continue
            job = jobs_by_id.get(record.source_id)
            if job is None:
                continue
            cross_source = self.evidence_service.job_cross_source_assessment(job, all_jobs)
            records[index] = record.model_copy(update={
                "cross_source_assessment": cross_source,
                "final_confidence": round(min(1.0, (record.final_confidence + cross_source["cross_source_confidence"]) / 2), 3),
            })

    @staticmethod
    def _copy_cluster_audits(clusters: list[dict[str, Any]], run_id: str) -> list[DataAuditRecord]:
        return [
            DataAuditRecord(
                audit_id=f"audit_{cluster['cluster_id']}",
                source_category="recruitment",
                source_id=cluster["cluster_id"],
                source_platform="cross_source",
                title=f"疑似抄袭簇 · {cluster['record_count']} 条",
                record_type="copy_cluster",
                status="manual_review",
                reasons=["copied_jd"],
                raw_item=cluster,
                normalized_item={"source_ids": cluster["source_ids"]},
                rule_assessment={
                    "version": "copy-cluster-v1",
                    "evidence_weight": cluster["evidence_weight"],
                    "independent_company_count": cluster["independent_company_count"],
                },
                final_confidence=0.86,
                graph_publish_status="blocked",
                collection_run_id=run_id,
            )
            for cluster in clusters[:200]
        ]

    @staticmethod
    def _job_change_audits(events: list[dict[str, Any]], run_id: str) -> list[DataAuditRecord]:
        return [
            DataAuditRecord(
                audit_id=f"audit_change_{run_id}_{event['job_id']}",
                source_category="recruitment",
                source_id=event["job_id"],
                source_platform=event["after"].get("source_platform", "unknown"),
                source_url=event["after"].get("source_url"),
                title=event["after"].get("title"),
                record_type="job_change",
                status="accepted",
                reasons=["job_content_changed"],
                raw_item=event["before"],
                normalized_item=event["after"],
                field_changes=event["changes"],
                evidence_snippets=[
                    {
                        "field": field,
                        "text": f"{change.get('before')} -> {change.get('after')}",
                        "rule": "persistent_job_identity_changed",
                    }
                    for field, change in event["changes"].items()
                ][:12],
                rule_assessment={
                    "version": "job-change-v1",
                    "outcome": event["outcome"],
                    "changed_fields": list(event["changes"]),
                },
                final_confidence=0.96,
                graph_publish_status="published",
                review_status="approved",
                collection_run_id=run_id,
            )
            for event in events
        ]

    def _update_source_progress(
        self, run_id: str, source_id: str, phase: str, *, fetched: int = 0,
        stage_durations: dict[str, int] | None = None,
    ) -> None:
        with self._progress_lock:
            run = self.store.collection_runs.get(run_id)
            if run is None or run.status != "running":
                return
            run.source_results = [
                item.model_copy(update={
                    "status": "running", "phase": phase, "fetched": fetched,
                    "stage_durations_ms": dict(stage_durations or {}),
                }) if item.source_id == source_id else item
                for item in run.source_results
            ]
            self.store.save_collection_run(run)

    def revalidate_existing_jobs(self, min_quality: float = 65, min_signal_quality: float = 55) -> dict[str, Any]:
        checked = quarantined = refreshed = 0
        signals_checked = signals_quarantined = signals_refreshed = 0
        records: list[DataQualityRejection] = []
        audit_records: list[DataAuditRecord] = []
        for job in list(self.store.jobs.values()):
            if job.source_platform not in self.sources or job.metadata.get("collection_mode") != "live":
                continue
            checked += 1
            raw = job.model_dump()
            raw["content"] = job.raw_content or job.content
            raw["raw_content"] = job.raw_content or job.content
            for derived_field in ("skill_tags", "responsibilities", "requirements", "evidence_segments"):
                raw.pop(derived_field, None)
            raw["domain"] = job.metadata.get("raw_domain")
            normalized, issues = normalize_recruitment_item(raw)
            assessment = self.data_agent.governance.assess_recruitment(raw, normalized, issues)
            if normalized is not None and normalized["quality_score"] < min_quality:
                assessment.status = "rejected"
                assessment.reasons = list(dict.fromkeys([
                    *assessment.reasons,
                    "below_quality_threshold",
                ]))
                assessment.confidence = min(assessment.confidence, 0.35)
            if normalized is None or assessment.status != "accepted":
                reasons = assessment.reasons or ["below_quality_threshold"]
                job.job_status = "offline"
                job.change_type = "offline"
                job.changed_at = datetime.now(UTC)
                job.metadata = {**job.metadata, "quality_status": "quarantined", "quality_issues": reasons}
                self.store.save_job_asset(job)
                audit_record = self.data_agent.governance.audit_record(
                    raw,
                    normalized,
                    assessment,
                    source_category="recruitment",
                ).model_copy(update={
                    "audit_id": f"audit_revalidation_{job.source_id}",
                })
                audit_records.append(audit_record)
                records.append(DataQualityRejection(
                    source_category="recruitment", source_id=job.source_id, source_platform=job.source_platform,
                    title=job.title, reasons=reasons, quality_score=job.quality_score,
                    source_url=job.source_url,
                    raw_item=raw,
                    metadata={"revalidation": True},
                ))
                quarantined += 1
                continue
            was_quarantined = job.metadata.get("quality_status") == "quarantined"
            normalized["metadata"].pop("quality_status", None)
            normalized["metadata"]["quality_issues"] = normalized["metadata"].get("quality_issues", [])
            if was_quarantined:
                normalized["job_status"] = "active"
            refreshed_job = type(job).model_validate(normalized)
            refreshed_job.change_type = "updated" if was_quarantined else job.change_type
            refreshed_job.changed_at = datetime.now(UTC) if was_quarantined else job.changed_at
            self.store.save_job_asset(refreshed_job)
            refreshed += 1
        for signal in list(self.store.community_signals.values()):
            signals_checked += 1
            raw = signal.model_dump()
            if signal.source_platform == "hackernews":
                raw["tags"] = []
                raw["source_url"] = f"https://news.ycombinator.com/item?id={signal.signal_id.rsplit(':', 1)[-1]}"
            normalized, issues = normalize_community_signal(raw)
            if normalized is None or normalized["quality_score"] < min_signal_quality:
                reasons = issues or ["below_signal_quality_threshold"]
                signal.metadata = {**signal.metadata, "quality_status": "quarantined", "quality_issues": reasons}
                self.store.save_community_signals([signal])
                records.append(DataQualityRejection(
                    source_category="community_signal", source_id=signal.signal_id, source_platform=signal.source_platform,
                    title=signal.title, reasons=reasons, quality_score=signal.quality_score,
                    metadata={"revalidation": True},
                ))
                signals_quarantined += 1
                continue
            normalized["metadata"].pop("quality_status", None)
            self.store.save_community_signals([CommunitySignal.model_validate(normalized)])
            signals_refreshed += 1
        self.store.save_quality_rejections(records)
        self.store.save_data_audits(audit_records)
        return {
            "jobs": {"checked": checked, "refreshed": refreshed, "quarantined": quarantined, "minimum_quality": min_quality},
            "community_signals": {
                "checked": signals_checked, "refreshed": signals_refreshed,
                "quarantined": signals_quarantined, "minimum_quality": min_signal_quality,
            },
        }

    def rebuild_evidence_intelligence(self) -> dict[str, Any]:
        active_jobs = self.store.list_jobs()
        active_signals = self.store.list_community_signals()
        copy_clusters = self.evidence_service.copy_clusters(active_jobs)
        technology_trends = self.evidence_service.technology_trends(
            active_jobs,
            active_signals,
        )
        updated_at = datetime.now(UTC).isoformat()
        self.store.save_setting(
            "copy_clusters",
            {"items": copy_clusters, "updated_at": updated_at},
        )
        self.store.save_setting(
            "technology_trends",
            {"items": technology_trends, "updated_at": updated_at},
        )
        self.store.save_data_audits(
            self._copy_cluster_audits(copy_clusters, f"evidence_{datetime.now(UTC):%Y%m%d%H%M%S}")
        )
        return {
            "active_jobs": len(active_jobs),
            "active_signals": len(active_signals),
            "copy_clusters": len(copy_clusters),
            "technology_trends": len(technology_trends),
            "updated_at": updated_at,
        }

    def reprocess_reviewed_record(self, record: DataQualityRejection) -> dict[str, Any]:
        if record.review_status != "approved":
            return {"status": "not_applicable", "message": "拒绝结论已用于后续规则学习"}
        raw = {**record.raw_item, **record.corrections}
        self.data_agent.learning_policy = self.store.get_setting("audit_learning_policy", {})
        if record.source_category == "recruitment":
            batch = self.data_agent.run(ImportRequest(
                batch_name=f"audit_reprocess_{record.rejection_id}",
                items=[raw], min_quality=0, strict_scope=True,
            ))
            if not batch.items:
                return {
                    "status": "needs_correction",
                    "message": "人工结论已学习，但当前记录仍缺少可入库字段",
                    "reasons": batch.quality_summary.get("rejection_reasons", {}),
                }
            changes = self.store.ingest_live_batch(batch)
            return {"status": "persisted", "job_id": batch.items[0].source_id, "changes": changes}
        normalized, issues = normalize_community_signal(raw)
        if normalized is None:
            return {"status": "needs_correction", "message": "辅助信号仍缺少必要字段", "reasons": issues}
        signal = CommunitySignal.model_validate(normalized)
        self.store.save_community_signals([signal])
        return {"status": "persisted", "signal_id": signal.signal_id}

    def reprocess_data_audit(self, record: DataAuditRecord) -> dict[str, Any]:
        self.store.learn_data_audit(record)
        if record.record_type == "copy_cluster":
            return {
                "status": record.review_decision or "reviewed",
                "source_id": record.source_id,
            }
        if record.review_status != "approved":
            job = self.store.jobs.get(record.source_id)
            if job is not None:
                job.job_status = "offline"
                job.metadata = {
                    **job.metadata,
                    "quality_status": "quarantined",
                    "audit_id": record.audit_id,
                }
                self.store.save_job_asset(job)
            return {"status": "blocked", "source_id": record.source_id}
        normalized = dict(record.normalized_item)
        if not normalized:
            raw = {**record.raw_item, **record.corrections}
            normalized, issues = normalize_recruitment_item(
                raw, self.store.get_setting("audit_learning_policy", {}),
            )
            if normalized is None:
                return {"status": "failed", "source_id": record.source_id, "reasons": issues}
        else:
            normalized.update(record.corrections)
        normalized["metadata"] = {
            **dict(normalized.get("metadata") or {}),
            "quality_status": "human_approved",
            "audit_id": record.audit_id,
        }
        normalized["job_status"] = "active"
        job = CleanedDataItem.model_validate(normalized)
        existing = self.store.jobs.get(job.source_id)
        if existing is None:
            self.store.create_job(job)
        else:
            self.store.save_job_asset(job)
            changes = self.store._job_diff(existing, job)
            if changes:
                self.store.save_job_version(job, changes)
        return {"status": "published", "source_id": job.source_id}


class CollectionScheduler:
    def __init__(self, collector: DataCollectionAgent) -> None:
        self.collector = collector
        self._lock = Lock()
        self._active_lock = Lock()
        self._active_sources: set[str] = set()
        self._next_runs: dict[str, datetime] = {}
        self._stop = Event()
        self._thread: Thread | None = None
        default_interval = float(os.getenv("TALENTGRAPH_COLLECTION_INTERVAL_MINUTES", "0") or 0)
        stored = collector.store.get_setting("collection_schedule")
        self._config = CollectionScheduleRequest.model_validate(stored) if stored else CollectionScheduleRequest(
            enabled=default_interval >= 5, interval_minutes=max(5, default_interval or 1440)
        )
        if not self.collector.source_strategies:
            self.collector.apply_strategy(CollectionStrategyRequest(enabled=self._config.enabled))
        self._initialize_next_runs()
        if any(item["enabled"] for item in self.collector.source_strategies.values()):
            self._start_thread()

    def configure(self, config: CollectionScheduleRequest) -> dict[str, Any]:
        existing = self.collector.source_strategies
        minimum = max(5, config.interval_minutes - config.jitter_minutes)
        maximum = max(minimum, config.interval_minutes + config.jitter_minutes)
        sources = {
            source_id: SourceCollectionStrategy.model_validate(settings).model_copy(update={
                "enabled": config.enabled,
                "min_interval_minutes": SUPPLEMENTAL_INTERVAL_MINUTES if source_id in SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS else minimum,
                "max_interval_minutes": SUPPLEMENTAL_INTERVAL_MINUTES if source_id in SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS else maximum,
                "items_per_run": min(config.request.max_items_per_source, SUPPLEMENTAL_ITEMS_PER_RUN)
                if source_id in SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS else config.request.max_items_per_source,
            })
            for source_id, settings in existing.items()
        }
        self._config = config
        self.collector.store.save_setting("collection_schedule", config.model_dump(mode="json"))
        self.configure_strategy(CollectionStrategyRequest(enabled=config.enabled, sources=sources))
        return self.status()

    def status(self) -> dict[str, Any]:
        enabled = [key for key, value in self.collector.source_strategies.items() if value["enabled"]]
        intervals = [
            (value["min_interval_minutes"], value["max_interval_minutes"])
            for value in self.collector.source_strategies.values() if value["enabled"]
        ]
        minimum = min((item[0] for item in intervals), default=self._config.interval_minutes)
        maximum = max((item[1] for item in intervals), default=self._config.interval_minutes)
        request = self._config.request.model_copy(update={
            "source_ids": enabled,
            "max_items_per_source": max(
                (value["items_per_run"] for value in self.collector.source_strategies.values() if value["enabled"]),
                default=self._config.request.max_items_per_source,
            ),
        })
        return {
            "enabled": bool(enabled),
            "interval_minutes": (minimum + maximum) / 2,
            "jitter_minutes": (maximum - minimum) / 2,
            "request": request.model_dump(mode="json"),
            "running": bool(self._thread and self._thread.is_alive()),
            "storage_policy": {"recruitment": "job_assets", "community_signal": "community_signals"},
        }

    def strategy_status(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        sources = {}
        for source_id, settings in self.collector.source_strategies.items():
            source = self.collector.sources[source_id]
            next_run = self._next_runs.get(source_id)
            sources[source_id] = {
                **settings,
                "name": getattr(source, "display_name", source_id),
                "source_category": getattr(source, "source_category", "recruitment"),
                "running": source_id in self._active_sources,
                "next_run_at": next_run.isoformat() if settings["enabled"] and next_run else None,
                "due_in_seconds": max(0, round((next_run - now).total_seconds())) if settings["enabled"] and next_run else None,
                "options": {
                    "cities": list(getattr(source, "available_cities", ())),
                    "job_queries": list(getattr(source, "available_queries", getattr(source, "queries", ()))),
                },
            }
        return {
            "enabled": any(item["enabled"] for item in sources.values()),
            "sources": sources,
            "scheduler": "independent_per_source",
        }

    def configure_strategy(self, strategy: CollectionStrategyRequest) -> dict[str, Any]:
        self.collector.apply_strategy(strategy)
        with self._lock:
            self._stop.set()
            self._thread = None
            self._stop = Event()
            self._initialize_next_runs()
            if any(item["enabled"] for item in self.collector.source_strategies.values()):
                self._start_thread()
        return self.strategy_status()

    def _initialize_next_runs(self) -> None:
        now = datetime.now(UTC)
        self._next_runs = {}
        for source_id, settings in self.collector.source_strategies.items():
            if not settings["enabled"]:
                continue
            interval = timedelta(minutes=random.uniform(settings["min_interval_minutes"], settings["max_interval_minutes"]))
            if source_id not in SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS:
                self._next_runs[source_id] = now + interval
                continue
            last_completed = self._latest_source_completion(source_id)
            due_at = last_completed + interval if last_completed else now
            try:
                startup_max_age = timedelta(
                    hours=max(1.0, float(os.getenv("TALENTGRAPH_SUPPLEMENTAL_STARTUP_MAX_AGE_HOURS", "6")))
                )
            except (TypeError, ValueError):
                startup_max_age = timedelta(hours=6)
            if due_at <= now or last_completed is None or last_completed <= now - startup_max_age:
                bounds = os.getenv("TALENTGRAPH_SUPPLEMENTAL_INITIAL_DELAY_SECONDS", "20,60").split(",")
                try:
                    low, high = float(bounds[0]), float(bounds[-1])
                except (TypeError, ValueError):
                    low, high = 20.0, 60.0
                due_at = now + timedelta(seconds=random.uniform(min(low, high), max(low, high)))
            self._next_runs[source_id] = due_at

    def _latest_source_completion(self, source_id: str) -> datetime | None:
        completed = [
            result.completed_at or run.completed_at
            for run in self.collector.store.collection_runs.values()
            for result in run.source_results
            if result.source_id == source_id and (result.completed_at or run.completed_at)
        ]
        return max(completed, default=None)

    def _schedule_next(self, source_id: str) -> None:
        settings = self.collector.source_strategies[source_id]
        self._next_runs[source_id] = datetime.now(UTC) + timedelta(
            minutes=random.uniform(settings["min_interval_minutes"], settings["max_interval_minutes"])
        )

    def _start_thread(self) -> None:
        stop_event = self._stop
        self._thread = Thread(target=self._loop, args=(stop_event,), name="talentgraph-data-collector", daemon=True)
        self._thread.start()

    def _loop(self, stop_event: Event) -> None:
        while not stop_event.wait(10):
            now = datetime.now(UTC)
            for source_id, settings in list(self.collector.source_strategies.items()):
                if not settings["enabled"] or self._next_runs.get(source_id, now) > now:
                    continue
                with self._active_lock:
                    if source_id in self._active_sources:
                        continue
                    self._active_sources.add(source_id)
                self._schedule_next(source_id)
                Thread(
                    target=self._run_source,
                    args=(source_id,),
                    name=f"talentgraph-collector-{source_id}",
                    daemon=True,
                ).start()

    def _run_source(self, source_id: str) -> None:
        settings = self.collector.source_strategies[source_id]
        try:
            request = self._config.request.model_copy(update={
                "source_ids": [source_id],
                "max_items_per_source": settings["items_per_run"],
            })
            self.collector.collect(request)
        finally:
            with self._active_lock:
                self._active_sources.discard(source_id)
