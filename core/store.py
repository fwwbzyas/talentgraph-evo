from __future__ import annotations

from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
import json
import os
import shutil
import sqlite3
from uuid import uuid4
from zipfile import ZipFile

from contracts import (
    AssessmentSession,
    CandidateProfile,
    CleanedDataBatch,
    CleanedDataItem,
    CommunitySignal,
    DataAuditRecord,
    DataCollectionRun,
    DataQualityRejection,
    EvolutionOutput,
    EmergingJobCandidate,
    JobGraph,
    MatchReport,
    ValidationRun,
)


class AppStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.batches: dict[str, CleanedDataBatch] = {}
        self.graphs: dict[str, JobGraph] = {}
        self.evolutions: dict[str, EvolutionOutput] = {}
        self.sessions: dict[str, AssessmentSession] = {}
        self.profiles: dict[str, CandidateProfile] = {}
        self.reports: dict[str, MatchReport] = {}
        self.report_profiles: dict[str, CandidateProfile] = {}
        self.report_access: dict[str, dict[str, str | None]] = {}
        self.emerging_jobs: dict[str, EmergingJobCandidate] = {}
        self.validation_runs: dict[str, ValidationRun] = {}
        self.community_signals: dict[str, CommunitySignal] = {}
        self.collection_runs: dict[str, DataCollectionRun] = {}
        self.quality_rejections: dict[str, DataQualityRejection] = {}
        self.data_audits: dict[str, DataAuditRecord] = {}
        self.jobs: dict[str, object] = {}
        self.settings: dict[str, dict] = {}
        self.db_path = db_path
        if db_path:
            database_path = Path(db_path)
            database_path.parent.mkdir(parents=True, exist_ok=True)
            archive_path = database_path.with_name("talentgraph-db.zip")
            if not database_path.exists() and archive_path.exists():
                with ZipFile(archive_path) as archive:
                    member = next(
                        (name for name in archive.namelist() if name.endswith(("talentgraph.db", "talentgraph.snapshot.db"))),
                        None,
                    )
                    if member:
                        with archive.open(member) as source, database_path.open("wb") as target:
                            shutil.copyfileobj(source, target)
            with sqlite3.connect(db_path) as connection:
                connection.execute("CREATE TABLE IF NOT EXISTS job_assets (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS assessment_sessions (session_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS assessment_session_access (session_id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, organization_id TEXT, candidate_id TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS assessment_records (record_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, payload TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS candidates (candidate_id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, organization_id TEXT, name TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS candidate_resumes (resume_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, payload TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS candidate_session_links (session_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS candidate_events (event_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, session_id TEXT, event_type TEXT NOT NULL, payload TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, created_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS candidate_report_links (report_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, created_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS resume_parse_jobs (candidate_id TEXT PRIMARY KEY, payload TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS candidate_profiles (candidate_id TEXT PRIMARY KEY, payload TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS emerging_jobs (candidate_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS validation_runs (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS community_signals (signal_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS collection_runs (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS app_settings (setting_key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS quality_rejections (rejection_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS data_audits (audit_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS match_reports (report_id TEXT PRIMARY KEY, payload TEXT NOT NULL, profile_payload TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS job_observations (observation_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, source_platform TEXT, source_id TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS job_versions (version_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, version_number INTEGER NOT NULL, changed_at TEXT NOT NULL, payload TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS audit_feedback (feedback_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS enterprise_jobs (job_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS recruitment_candidates (candidate_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS recruitment_feedback (feedback_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, organization_id TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS candidate_gap_analyses (analysis_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, scope TEXT NOT NULL, target_job_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_gap_candidate ON candidate_gap_analyses(candidate_id, created_at DESC)")
                connection.execute("CREATE TABLE IF NOT EXISTS candidate_learning_routes (route_id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, candidate_id TEXT NOT NULL, owner_user_id TEXT NOT NULL, organization_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
                job_rows = connection.execute("SELECT job_id, payload FROM job_assets").fetchall()
                session_rows = connection.execute("SELECT session_id, payload FROM assessment_sessions").fetchall()
                emerging_rows = connection.execute("SELECT candidate_id, payload FROM emerging_jobs").fetchall()
                validation_rows = connection.execute("SELECT run_id, payload FROM validation_runs").fetchall()
                signal_rows = connection.execute("SELECT signal_id, payload FROM community_signals").fetchall()
                collection_rows = connection.execute("SELECT run_id, payload FROM collection_runs").fetchall()
                setting_rows = connection.execute("SELECT setting_key, payload FROM app_settings").fetchall()
                rejection_rows = connection.execute("SELECT rejection_id, payload FROM quality_rejections").fetchall()
                audit_rows = connection.execute("SELECT audit_id, payload FROM data_audits").fetchall()
                report_rows = connection.execute(
                    "SELECT report_id, payload, profile_payload, owner_user_id, organization_id FROM match_reports"
                ).fetchall()
                profile_rows = connection.execute("SELECT candidate_id, payload FROM candidate_profiles").fetchall()
            self.jobs = {item_id: CleanedDataItem.model_validate_json(payload) for item_id, payload in job_rows}
            self.sessions = {item_id: AssessmentSession.model_validate_json(payload) for item_id, payload in session_rows}
            self.emerging_jobs = {item_id: EmergingJobCandidate.model_validate_json(payload) for item_id, payload in emerging_rows}
            self.validation_runs = {item_id: ValidationRun.model_validate_json(payload) for item_id, payload in validation_rows}
            self.community_signals = {item_id: CommunitySignal.model_validate_json(payload) for item_id, payload in signal_rows}
            self.collection_runs = {item_id: DataCollectionRun.model_validate_json(payload) for item_id, payload in collection_rows}
            self.settings = {item_id: json.loads(payload) for item_id, payload in setting_rows}
            self.quality_rejections = {item_id: DataQualityRejection.model_validate_json(payload) for item_id, payload in rejection_rows}
            self.data_audits = {item_id: DataAuditRecord.model_validate_json(payload) for item_id, payload in audit_rows}
            self.reports = {
                report_id: MatchReport.model_validate_json(payload)
                for report_id, payload, _, _, _ in report_rows
            }
            self.report_profiles = {
                report_id: CandidateProfile.model_validate_json(profile_payload)
                for report_id, _, profile_payload, _, _ in report_rows
            }
            self.report_access = {
                report_id: {"owner_user_id": owner_user_id, "organization_id": organization_id}
                for report_id, _, _, owner_user_id, organization_id in report_rows
            }
            self.profiles = {
                candidate_id: CandidateProfile.model_validate_json(payload)
                for candidate_id, payload in profile_rows
            }
            self._compact_quality_rejections()
            self._recover_interrupted_collection_runs()
            self._migrate_auxiliary_jobs()
            self._purge_orphaned_emerging_jobs()
            self._backfill_data_audits()
            self._migrate_normalized_job_fields()
            self._backfill_job_versions()

    def _recover_interrupted_collection_runs(self) -> None:
        for run in self.collection_runs.values():
            if run.status != "running":
                continue
            run.status = "partial" if run.source_results else "failed"
            run.completed_at = datetime.now(UTC)
            run.quality_summary = {**run.quality_summary, "interrupted": True, "reason": "service_restarted"}
            self._persist_model("collection_runs", "run_id", run.run_id, run.model_dump_json())

    def _migrate_auxiliary_jobs(self) -> None:
        auxiliary_sources = {"remoteok", "arbeitnow"}
        legacy = [job for job in self.jobs.values() if job.source_platform in auxiliary_sources]
        if not legacy:
            return
        for job in legacy:
            signal = CommunitySignal(
                signal_id=f"{job.source_platform}:{job.source_id}",
                source_type="developer_community",
                source_platform=job.source_platform,
                source_url=job.source_url or f"https://invalid.local/{job.source_platform}/{job.source_id}",
                domain=job.domain,
                title=job.title,
                content=job.raw_content or job.content,
                tags=job.skill_tags,
                published_at=job.published_at,
                collected_at=job.collected_at,
                quality_score=job.quality_score,
                dedup_hash=job.dedup_hash,
                metadata={**job.metadata, "auxiliary_only": True, "migrated_from_job_assets": True},
            )
            self.community_signals[signal.signal_id] = signal
            self._persist_model("community_signals", "signal_id", signal.signal_id, signal.model_dump_json())
            self.jobs.pop(job.source_id, None)
        if self.db_path:
            with sqlite3.connect(self.db_path) as connection:
                connection.executemany("DELETE FROM job_assets WHERE job_id = ?", [(job.source_id,) for job in legacy])

    def _purge_orphaned_emerging_jobs(self) -> None:
        """Remove legacy candidates whose claimed recruitment evidence no longer exists."""
        if not self.db_path or not self.emerging_jobs:
            return
        valid_job_ids = set(self.jobs)
        orphaned_ids = []
        for candidate_id, candidate in self.emerging_jobs.items():
            evidence_ids = {
                str(evidence.get("source_id", ""))
                for evidence in candidate.evidence
                if evidence.get("source_id")
            }
            if not evidence_ids or evidence_ids.isdisjoint(valid_job_ids):
                orphaned_ids.append(candidate_id)
        if not orphaned_ids:
            return
        for candidate_id in orphaned_ids:
            self.emerging_jobs.pop(candidate_id, None)
        with sqlite3.connect(self.db_path) as connection:
            connection.executemany(
                "DELETE FROM emerging_jobs WHERE candidate_id = ?",
                [(candidate_id,) for candidate_id in orphaned_ids],
            )

    def _backfill_job_versions(self) -> None:
        if not self.db_path or not self.jobs:
            return
        with sqlite3.connect(self.db_path) as connection:
            versioned = {
                row[0] for row in connection.execute("SELECT DISTINCT job_id FROM job_versions").fetchall()
            }
            rows = []
            for job_id, job in self.jobs.items():
                if job_id in versioned:
                    continue
                changed_at = (job.changed_at or job.collected_at or datetime.now(UTC)).isoformat()
                payload = {
                    "version_id": f"{job_id}:v1", "job_id": job_id, "version_number": 1,
                    "changed_at": changed_at,
                    "changes": {"baseline": {"before": None, "after": True}},
                    "snapshot": job.model_dump(mode="json"),
                }
                rows.append((f"{job_id}:v1", job_id, 1, changed_at, json.dumps(payload, ensure_ascii=False)))
            connection.executemany(
                "INSERT OR IGNORE INTO job_versions (version_id, job_id, version_number, changed_at, payload) VALUES (?, ?, ?, ?, ?)",
                rows,
            )

    def _backfill_data_audits(self) -> None:
        if not self.db_path or not self.jobs:
            return
        audited_sources = {
            (record.source_category, record.source_id)
            for record in self.data_audits.values()
        }
        records = []
        now = datetime.now(UTC)
        for job in self.jobs.values():
            if ("recruitment", job.source_id) in audited_sources:
                continue
            record = DataAuditRecord(
                audit_id=f"audit_legacy_{job.dedup_hash}_{job.source_id[-12:]}",
                source_category="recruitment",
                source_id=job.source_id,
                source_platform=job.source_platform,
                source_url=job.source_url,
                title=job.title,
                record_type="accepted",
                status="accepted",
                raw_item={
                    "source_id": job.source_id,
                    "title": job.title,
                    "company": job.company,
                    "content": job.raw_content or job.content,
                    "tags": job.skill_tags,
                    "source_url": job.source_url,
                    "source_platform": job.source_platform,
                },
                normalized_item=job.model_dump(mode="json"),
                rule_assessment={"version": "legacy-lineage-v1", "migration": True},
                final_confidence=round(job.quality_score / 100, 3),
                graph_publish_status="published",
                review_status="approved",
                created_at=job.collected_at,
                updated_at=now,
            )
            self.data_audits[record.audit_id] = record
            records.append((record.audit_id, record.model_dump_json(), now.isoformat()))
        with sqlite3.connect(self.db_path) as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO data_audits (audit_id, payload, updated_at) VALUES (?, ?, ?)",
                records,
            )

    def _migrate_normalized_job_fields(self) -> None:
        if (
            not self.db_path
            or not self.jobs
            or self.settings.get("normalization_migration_skills_v2", {}).get("completed")
        ):
            return
        from agents.data.normalization import extract_skills

        now = datetime.now(UTC)
        audits_by_source = {
            record.source_id: record for record in self.data_audits.values()
            if record.source_category == "recruitment"
        }
        job_rows = []
        audit_rows = []
        changed_count = 0
        for job_id, job in list(self.jobs.items()):
            cleaned_skills = extract_skills(
                f"{job.title}\n{job.content}",
                job.skill_tags,
            )
            if cleaned_skills == job.skill_tags:
                continue
            previous_skills = list(job.skill_tags)
            updated_job = job.model_copy(update={
                "skill_tags": cleaned_skills,
                "metadata": {
                    **job.metadata,
                    "normalization_version": "skills-v2",
                },
            })
            self.jobs[job_id] = updated_job
            job_rows.append((
                job_id,
                updated_job.model_dump_json(),
                now.isoformat(),
            ))
            audit = audits_by_source.get(job_id)
            if audit:
                updated_audit = audit.model_copy(update={
                    "record_type": "field_correction",
                    "reasons": list(dict.fromkeys([
                        *audit.reasons,
                        "non_skill_tags_removed",
                    ])),
                    "normalized_item": updated_job.model_dump(mode="json"),
                    "field_changes": {
                        **audit.field_changes,
                        "skill_tags": {
                            "before": previous_skills,
                            "after": cleaned_skills,
                        },
                    },
                    "rule_assessment": {
                        **audit.rule_assessment,
                        "skill_normalization": "skills-v2",
                    },
                    "updated_at": now,
                })
                self.data_audits[audit.audit_id] = updated_audit
                audit_rows.append((
                    audit.audit_id,
                    updated_audit.model_dump_json(),
                    now.isoformat(),
                ))
            changed_count += 1
        with sqlite3.connect(self.db_path) as connection:
            connection.executemany(
                "INSERT OR REPLACE INTO job_assets (job_id, payload, updated_at) VALUES (?, ?, ?)",
                job_rows,
            )
            connection.executemany(
                "INSERT OR REPLACE INTO data_audits (audit_id, payload, updated_at) VALUES (?, ?, ?)",
                audit_rows,
            )
        self.save_setting("normalization_migration_skills_v2", {
            "completed": True,
            "changed_records": changed_count,
            "completed_at": now.isoformat(),
        })

    def _persist_model(self, table: str, id_column: str, item_id: str, payload: str) -> None:
        if not self.db_path:
            return
        allowed = {
            ("assessment_sessions", "session_id"),
            ("emerging_jobs", "candidate_id"),
            ("validation_runs", "run_id"),
            ("community_signals", "signal_id"),
            ("collection_runs", "run_id"),
            ("quality_rejections", "rejection_id"),
            ("data_audits", "audit_id"),
        }
        if (table, id_column) not in allowed:
            raise ValueError("unsupported persistence target")
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                f"INSERT OR REPLACE INTO {table} ({id_column}, payload, updated_at) VALUES (?, ?, ?)",
                (item_id, payload, datetime.now(UTC).isoformat()),
            )

    def _persist_job(self, job) -> None:
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO job_assets (job_id, payload, updated_at) VALUES (?, ?, ?)",
                (job.source_id, job.model_dump_json(), datetime.now(UTC).isoformat()),
            )

    def _enterprise_rows(self, table: str, organization_id: str, *, item_id: str | None = None) -> list[dict]:
        allowed = {"enterprise_jobs", "recruitment_candidates", "recruitment_feedback"}
        if table not in allowed or not self.db_path:
            return []
        id_column = "feedback_id" if table == "recruitment_feedback" else "candidate_id" if table == "recruitment_candidates" else "job_id"
        query = f"SELECT payload FROM {table} WHERE organization_id = ?"
        values: tuple = (organization_id,)
        if item_id:
            query += f" AND {id_column} = ?"
            values += (item_id,)
        query += " ORDER BY updated_at DESC"
        with sqlite3.connect(self.db_path) as connection:
            return [json.loads(row[0]) for row in connection.execute(query, values).fetchall()]

    def save_enterprise_record(self, table: str, item_id: str, organization_id: str, payload: dict) -> dict:
        allowed = {"enterprise_jobs": "job_id", "recruitment_candidates": "candidate_id", "recruitment_feedback": "feedback_id"}
        if table not in allowed:
            raise ValueError("unsupported enterprise persistence target")
        if self.db_path:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    f"INSERT OR REPLACE INTO {table} ({allowed[table]}, organization_id, payload, updated_at) VALUES (?, ?, ?, ?)",
                    (item_id, organization_id, json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()),
                )
        return payload

    def index_batch(self, batch: CleanedDataBatch) -> None:
        for item in batch.items:
            if item.source_type == "jd":
                self.jobs[item.source_id] = item
                self._persist_job(item)

    def ingest_live_batch(self, batch: CleanedDataBatch) -> dict[str, Any]:
        counts: dict[str, Any] = {
            "new": 0, "updated": 0, "unchanged": 0,
            "exact_duplicate": 0, "repost": 0, "events": [],
        }
        now = datetime.now(UTC)
        hash_index = {job.dedup_hash: job for job in self.jobs.values()}
        identity_index = {
            job.metadata.get("identity_hash"): job for job in self.jobs.values()
            if job.metadata.get("identity_hash")
        }
        for item in batch.items:
            existing = self.jobs.get(item.source_id)
            if existing is None:
                exact = hash_index.get(item.dedup_hash)
                if exact is not None:
                    counts["exact_duplicate"] += 1
                    self.save_job_observation(exact.source_id, item, "exact_duplicate")
                    continue
                identity = item.metadata.get("identity_hash")
                related = identity_index.get(identity) if identity else None
                if related is not None:
                    similarity = SequenceMatcher(None, related.content, item.content).ratio()
                    if similarity >= 0.95:
                        counts["repost"] += 1
                        self.save_job_observation(related.source_id, item, "repost")
                        continue
                    changes = self._job_diff(related, item)
                    aliases = list(dict.fromkeys([*related.metadata.get("source_aliases", []), item.source_id]))
                    replacement = item.model_copy(update={
                        "source_id": related.source_id,
                        # A cross-source observation may refresh the canonical
                        # job content, but it must not erase the provenance of
                        # the already-persisted real job asset.
                        "source_platform": related.source_platform,
                        "source_url": related.source_url,
                        "change_type": "updated",
                        "changed_at": now,
                        "metadata": {
                            **related.metadata,
                            **item.metadata,
                            "source_aliases": aliases,
                            "updated_from_source_id": item.source_id,
                            "updated_from_source_platform": item.source_platform,
                            "updated_from_source_url": item.source_url,
                        },
                    })
                    self.jobs[related.source_id] = replacement
                    self._persist_job(replacement)
                    self.save_job_version(replacement, changes)
                    self.save_job_observation(related.source_id, item, "updated_alias")
                    counts["updated"] += 1
                    counts["events"].append({
                        "job_id": related.source_id,
                        "outcome": "updated_alias",
                        "before": related.model_dump(mode="json"),
                        "after": replacement.model_dump(mode="json"),
                        "changes": changes,
                    })
                    hash_index[replacement.dedup_hash] = replacement
                    continue
                item.change_type = "new"
                item.changed_at = now
                counts["new"] += 1
                self.jobs[item.source_id] = item
                self._persist_job(item)
                self.save_job_version(item, {"created": {"before": None, "after": True}})
                self.save_job_observation(item.source_id, item, "new")
                hash_index[item.dedup_hash] = item
                if item.metadata.get("identity_hash"):
                    identity_index[item.metadata["identity_hash"]] = item
                continue
            elif existing.dedup_hash != item.dedup_hash:
                item.change_type = "updated"
                item.changed_at = now
                counts["updated"] += 1
                changes = self._job_diff(existing, item)
                self.jobs[item.source_id] = item
                self._persist_job(item)
                self.save_job_version(item, changes)
                self.save_job_observation(item.source_id, item, "updated")
                counts["events"].append({
                    "job_id": item.source_id,
                    "outcome": "updated",
                    "before": existing.model_dump(mode="json"),
                    "after": item.model_dump(mode="json"),
                    "changes": changes,
                })
            else:
                item.change_type = "unchanged"
                item.changed_at = existing.changed_at
                counts["unchanged"] += 1
                self.jobs[item.source_id] = item
                self._persist_job(item)
                self.save_job_observation(item.source_id, item, "unchanged")
        return counts

    @staticmethod
    def _job_diff(before, after) -> dict:
        fields = (
            "title", "company", "city", "district", "salary_min_k", "salary_max_k", "salary_months",
            "experience_min_years", "experience_max_years", "education", "skill_tags",
            "responsibilities", "requirements", "job_status",
        )
        return {
            field: {"before": getattr(before, field), "after": getattr(after, field)}
            for field in fields if getattr(before, field) != getattr(after, field)
        }

    def save_job_observation(self, job_id: str, item, outcome: str) -> None:
        if not self.db_path:
            return
        observed_at = datetime.now(UTC)
        observation_id = f"obs_{uuid4().hex[:16]}"
        payload = {
            "observation_id": observation_id, "job_id": job_id, "source_id": item.source_id,
            "source_platform": item.source_platform, "observed_at": observed_at.isoformat(),
            "outcome": outcome, "dedup_hash": item.dedup_hash, "source_url": item.source_url,
            "quality_score": item.quality_score,
        }
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO job_observations (observation_id, job_id, source_platform, source_id, observed_at, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (observation_id, job_id, item.source_platform, item.source_id, observed_at.isoformat(), json.dumps(payload, ensure_ascii=False)),
            )

    def save_job_version(self, item, changes: dict) -> None:
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as connection:
            version_number = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM job_versions WHERE job_id = ?", (item.source_id,),
            ).fetchone()[0]
            version_id = f"{item.source_id}:v{version_number}"
            payload = {
                "version_id": version_id, "job_id": item.source_id, "version_number": version_number,
                "changed_at": datetime.now(UTC).isoformat(), "changes": changes,
                "snapshot": item.model_dump(mode="json"),
            }
            connection.execute(
                "INSERT OR REPLACE INTO job_versions (version_id, job_id, version_number, changed_at, payload) VALUES (?, ?, ?, ?, ?)",
                (version_id, item.source_id, version_number, payload["changed_at"], json.dumps(payload, ensure_ascii=False)),
            )

    def create_job(self, job):
        if not job.source_id:
            job.source_id = f"job_{uuid4().hex[:10]}"
        if job.source_id in self.jobs:
            raise ValueError("job already exists")
        self.jobs[job.source_id] = job
        self._persist_job(job)
        return job

    def save_job_asset(self, job):
        self.jobs[job.source_id] = job
        self._persist_job(job)
        return job

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def update_job(self, job_id: str, changes: dict):
        job = self.jobs.get(job_id)
        if job is None:
            return None
        changes = {key: value for key, value in changes.items() if value is not None}
        changes["changed_at"] = datetime.now(UTC)
        changes["change_type"] = "updated"
        updated = job.model_copy(update=changes)
        self.jobs[job_id] = updated
        self._persist_job(updated)
        self.save_job_version(updated, self._job_diff(job, updated))
        return updated

    def list_job_versions(self, job_id: str) -> list[dict]:
        if not self.db_path:
            return []
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM job_versions WHERE job_id = ? ORDER BY version_number DESC", (job_id,),
            ).fetchall()
        return [json.loads(payload) for (payload,) in rows]

    def compare_job_version(
        self,
        job_id: str,
        version_number: int,
        base_version_number: int | None = None,
    ) -> dict | None:
        versions = sorted(
            self.list_job_versions(job_id),
            key=lambda item: int(item.get("version_number") or 0),
        )
        current_index = next(
            (
                index
                for index, item in enumerate(versions)
                if int(item.get("version_number") or 0) == version_number
            ),
            None,
        )
        if current_index is None:
            return None

        current = versions[current_index]
        if base_version_number is None:
            previous = versions[current_index - 1] if current_index > 0 else None
        else:
            previous = next(
                (
                    item
                    for item in versions
                    if int(item.get("version_number") or 0) == base_version_number
                ),
                None,
            )
            if previous is None:
                return None

        current_version_number = int(current.get("version_number") or version_number)
        previous_version_number = int(previous.get("version_number") or 0) if previous else None
        after = current.get("snapshot") or {}
        before = (previous or {}).get("snapshot") or {}
        recorded_changes = current.get("changes") or {}
        snapshot_fields = (
            "title", "company", "city", "district", "salary_min_k", "salary_max_k", "salary_months",
            "experience_min_years", "experience_max_years", "education", "skill_tags",
            "responsibilities", "requirements", "job_status",
        )
        compare_snapshots = previous is not None and (
            base_version_number is not None
            or current_version_number - previous_version_number != 1
        )
        if compare_snapshots:
            field_diffs = [
                {"field": field, "before": before.get(field), "after": after.get(field)}
                for field in snapshot_fields
                if before.get(field) != after.get(field)
            ]
        else:
            field_names = list(recorded_changes)
            if previous is not None:
                field_names = list(dict.fromkeys([
                    *field_names,
                    *(field for field in snapshot_fields if before.get(field) != after.get(field)),
                ]))

            field_diffs = []
            for field in field_names:
                recorded = recorded_changes.get(field) or {}
                before_value = recorded.get("before", before.get(field))
                after_value = recorded.get("after", after.get(field))
                if field == "created" or before_value == after_value:
                    continue
                field_diffs.append({
                    "field": field,
                    "before": before_value,
                    "after": after_value,
                })

        before_skills = set(before.get("skill_tags") or [])
        after_skills = set(after.get("skill_tags") or [])
        return {
            "job_id": job_id,
            "version_number": current_version_number,
            "version_id": current.get("version_id"),
            "changed_at": current.get("changed_at"),
            "has_previous": previous is not None,
            "base_version_number": previous_version_number,
            "previous_version_number": previous_version_number,
            "before": before if previous is not None else None,
            "after": after,
            "field_diffs": field_diffs,
            "skill_diffs": {
                "added": sorted(after_skills - before_skills),
                "removed": sorted(before_skills - after_skills),
                "retained": sorted(before_skills & after_skills),
            },
            "source_url": after.get("source_url") or before.get("source_url"),
        }

    def list_all_job_versions(self, limit: int = 50000) -> list[dict]:
        if not self.db_path:
            return []
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM job_versions ORDER BY changed_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(payload) for (payload,) in rows]

    def list_job_versions_by_source(self, source_platform: str, limit: int = 50000) -> list[dict]:
        versions = self.list_all_job_versions(limit)
        return [
            version for version in versions
            if version.get("snapshot", {}).get("source_platform") == source_platform
        ]

    def list_job_observations(self, job_id: str, limit: int = 100) -> list[dict]:
        if not self.db_path:
            return []
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM job_observations WHERE job_id = ? ORDER BY observed_at DESC LIMIT ?",
                (job_id, limit),
            ).fetchall()
        return [json.loads(payload) for (payload,) in rows]

    def delete_job(self, job_id: str) -> bool:
        if job_id not in self.jobs:
            return False
        del self.jobs[job_id]
        if self.db_path:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute("DELETE FROM job_assets WHERE job_id = ?", (job_id,))
        self.graphs.pop(job_id, None)
        self.evolutions.pop(job_id, None)
        return True

    def list_jobs(self, *, city: str | None = None, keyword: str | None = None, active_only: bool = True):
        jobs = list(self.jobs.values())
        if active_only:
            jobs = [job for job in jobs if job.job_status == "active"]
        if city:
            jobs = [job for job in jobs if job.city == city]
        if keyword:
            needle = keyword.casefold()
            jobs = [job for job in jobs if needle in f"{job.title} {job.company} {' '.join(job.skill_tags)}".casefold()]
        return sorted(jobs, key=lambda job: job.published_at or job.collected_at, reverse=True)

    def today_changes(self):
        today = datetime.now(UTC).date()
        return [job for job in self.jobs.values() if job.change_type != "unchanged" and job.changed_at and job.changed_at.date() == today]

    def save_session(self, session: AssessmentSession) -> AssessmentSession:
        self.sessions[session.session_id] = session
        self._persist_model("assessment_sessions", "session_id", session.session_id, session.model_dump_json())
        return session

    def grant_session_access(self, session: AssessmentSession, user: dict) -> None:
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """INSERT OR REPLACE INTO assessment_session_access
                (session_id, owner_user_id, organization_id, candidate_id, updated_at)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    session.session_id,
                    user["user_id"],
                    user.get("organization_id"),
                    session.candidate_id,
                    datetime.now(UTC).isoformat(),
                ),
            )
        self.link_candidate_session(session, user)

    def _upsert_candidate(self, candidate_id: str, user: dict, name: str | None = None) -> None:
        if not self.db_path:
            return
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as connection:
            existing = connection.execute(
                "SELECT owner_user_id, organization_id, name FROM candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if existing:
                allowed = existing[0] == user["user_id"] or bool(
                    user.get("role") == "enterprise" and existing[1] and existing[1] == user.get("organization_id")
                )
                if not allowed:
                    raise PermissionError("candidate access denied")
                connection.execute(
                    "UPDATE candidates SET name = ?, updated_at = ? WHERE candidate_id = ?",
                    (name or existing[2], now, candidate_id),
                )
            else:
                connection.execute(
                    "INSERT INTO candidates (candidate_id, owner_user_id, organization_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (candidate_id, user["user_id"], user.get("organization_id"), name or "", now, now),
                )

    def link_candidate_session(self, session: AssessmentSession, user: dict) -> None:
        self._upsert_candidate(session.candidate_id, user)
        if not self.db_path:
            return
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO candidate_session_links (session_id, candidate_id, owner_user_id, organization_id, created_at, updated_at) VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM candidate_session_links WHERE session_id = ?), ?), ?)",
                (session.session_id, session.candidate_id, user["user_id"], user.get("organization_id"), session.session_id, now, now),
            )

    def save_candidate_event(self, candidate_id: str, user: dict, event_type: str, payload: dict, session_id: str | None = None) -> None:
        self._upsert_candidate(candidate_id, user)
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO candidate_events (event_id, candidate_id, session_id, event_type, payload, owner_user_id, organization_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid4().hex, candidate_id, session_id, event_type, json.dumps(payload, ensure_ascii=False), user["user_id"], user.get("organization_id"), datetime.now(UTC).isoformat()),
            )

    def save_gap_analysis(self, analysis: dict, user: dict) -> dict:
        candidate_id = str(analysis["candidate_id"])
        if not self.can_access_candidate(candidate_id, user):
            raise PermissionError("candidate access denied")
        now = datetime.now(UTC).isoformat()
        payload = {**analysis, "created_at": analysis.get("created_at") or now}
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO candidate_gap_analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (payload["analysis_id"], candidate_id, user["user_id"], user.get("organization_id"), payload["scope"], payload.get("target_job_id"), json.dumps(payload, ensure_ascii=False), payload["created_at"]),
            )
        self.save_candidate_event(candidate_id, user, "gap_analyzed", {"analysis_id": payload["analysis_id"], "scope": payload["scope"], "target_job_id": payload.get("target_job_id")})
        return payload

    def get_gap_analysis(self, analysis_id: str, user: dict) -> dict | None:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT payload, owner_user_id, organization_id FROM candidate_gap_analyses WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        if not row:
            return None
        allowed = row[1] == user["user_id"] or bool(user.get("role") == "enterprise" and row[2] and row[2] == user.get("organization_id"))
        if not allowed:
            raise PermissionError("gap analysis access denied")
        payload = json.loads(row[0])
        if payload.get("data_policy") != "real_recruitment_evidence_only":
            return None
        return payload

    def latest_gap_analysis(self, candidate_id: str, user: dict) -> dict | None:
        if not self.can_access_candidate(candidate_id, user):
            raise PermissionError("candidate access denied")
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM candidate_gap_analyses WHERE candidate_id = ? AND (owner_user_id = ? OR organization_id = ?) ORDER BY created_at DESC",
                (candidate_id, user["user_id"], user.get("organization_id")),
            ).fetchall()
        for row in rows:
            payload = json.loads(row[0])
            if payload.get("data_policy") == "real_recruitment_evidence_only":
                return payload
        return None

    def save_learning_route(self, route: dict, analysis_id: str, candidate_id: str, user: dict) -> dict:
        if not self.can_access_candidate(candidate_id, user):
            raise PermissionError("candidate access denied")
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO candidate_learning_routes VALUES (?, ?, ?, ?, ?, ?, ?)",
                (route["route_id"], analysis_id, candidate_id, user["user_id"], user.get("organization_id"), json.dumps(route, ensure_ascii=False), now),
            )
        self.save_candidate_event(candidate_id, user, "learning_route_generated", {"route_id": route["route_id"], "analysis_id": analysis_id})
        return route

    def latest_learning_route(self, analysis_id: str, user: dict) -> dict | None:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT payload, owner_user_id, organization_id FROM candidate_learning_routes WHERE analysis_id = ? ORDER BY created_at DESC LIMIT 1",
                (analysis_id,),
            ).fetchone()
        if not row:
            return None
        allowed = row[1] == user["user_id"] or bool(user.get("role") == "enterprise" and row[2] and row[2] == user.get("organization_id"))
        if not allowed:
            raise PermissionError("learning route access denied")
        return json.loads(row[0])

    def can_access_session(self, session_id: str, user: dict) -> bool:
        if not self.db_path:
            return False
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT owner_user_id, organization_id FROM assessment_session_access WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return False
        return row[0] == user["user_id"] or bool(
            user.get("role") == "enterprise"
            and row[1]
            and row[1] == user.get("organization_id")
        )

    def can_access_candidate(self, candidate_id: str, user: dict) -> bool:
        if not self.db_path:
            return False
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT owner_user_id, organization_id FROM assessment_session_access WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchall()
            profile_row = connection.execute(
                "SELECT owner_user_id, organization_id FROM candidate_profiles WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        if profile_row:
            rows.append(profile_row)
        return any(
            owner == user["user_id"]
            or bool(user.get("role") == "enterprise" and org and org == user.get("organization_id"))
            for owner, org in rows
        )

    def save_candidate_profile(self, profile: CandidateProfile, user: dict) -> CandidateProfile:
        self.profiles[profile.candidate_id] = profile
        self._upsert_candidate(profile.candidate_id, user, profile.name)
        if self.db_path:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    """INSERT OR REPLACE INTO candidate_profiles
                    (candidate_id, payload, owner_user_id, organization_id, updated_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (profile.candidate_id, profile.model_dump_json(), user["user_id"], user.get("organization_id"), datetime.now(UTC).isoformat()),
                )
        self.save_candidate_event(profile.candidate_id, user, "profile_generated", profile.model_dump(mode="json"))
        self.save_assessment_record(
            {
                "id": profile.candidate_id,
                "candidate_id": profile.candidate_id,
                "name": profile.name,
                "target_job_id": profile.target_job_id,
                "status": "已生成画像",
                "profile": profile.model_dump(mode="json"),
            },
            user,
        )
        return profile

    def save_resume_parse_job(self, candidate_id: str, payload: dict, user: dict) -> dict:
        parsed = payload.get("resume_parse") if isinstance(payload.get("resume_parse"), dict) else {}
        self._upsert_candidate(candidate_id, user, str(parsed.get("candidate_name") or ""))
        if self.db_path:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    """INSERT OR REPLACE INTO resume_parse_jobs
                    (candidate_id, payload, owner_user_id, organization_id, updated_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (candidate_id, json.dumps(payload, ensure_ascii=False), user["user_id"], user.get("organization_id"), datetime.now(UTC).isoformat()),
                )
                connection.execute(
                    "INSERT INTO candidate_resumes (resume_id, candidate_id, payload, owner_user_id, organization_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(resume_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                    (f"resume:{candidate_id}", candidate_id, json.dumps(payload, ensure_ascii=False), user["user_id"], user.get("organization_id"), datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()),
                )
        self.save_candidate_event(candidate_id, user, "resume_parsed", {"status": payload.get("status")})
        return payload

    def get_resume_parse_job(self, candidate_id: str, user: dict) -> dict | None:
        if not self.db_path:
            return None
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT payload, owner_user_id, organization_id FROM resume_parse_jobs WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        if not row:
            return None
        allowed = row[1] == user["user_id"] or bool(user.get("role") == "enterprise" and row[2] and row[2] == user.get("organization_id"))
        if not allowed:
            raise PermissionError("resume parse access denied")
        return json.loads(row[0])

    def list_assessment_records(self, user: dict) -> list[dict]:
        if not self.db_path:
            return []
        if user.get("role") == "enterprise" and user.get("organization_id"):
            query = "SELECT payload FROM assessment_records WHERE organization_id = ? ORDER BY updated_at DESC"
            params = (user["organization_id"],)
        else:
            query = "SELECT payload FROM assessment_records WHERE owner_user_id = ? ORDER BY updated_at DESC"
            params = (user["user_id"],)
        with sqlite3.connect(self.db_path) as connection:
            return [json.loads(payload) for (payload,) in connection.execute(query, params).fetchall()]

    def save_assessment_record(self, record: dict, user: dict) -> dict:
        record_id = str(record.get("id") or record.get("candidate_id") or uuid4().hex)
        candidate_id = str(record.get("candidate_id") or record_id)
        payload = {**record, "id": record_id, "candidate_id": candidate_id}
        self._upsert_candidate(candidate_id, user, str(payload.get("name") or ""))
        if self.db_path:
            with sqlite3.connect(self.db_path) as connection:
                existing = connection.execute(
                    "SELECT owner_user_id, organization_id FROM assessment_records WHERE record_id = ?",
                    (record_id,),
                ).fetchone()
                if existing:
                    allowed = existing[0] == user["user_id"] or bool(
                        user.get("role") == "enterprise" and existing[1] and existing[1] == user.get("organization_id")
                    )
                    if not allowed:
                        raise PermissionError("assessment record access denied")
                connection.execute(
                    """INSERT OR REPLACE INTO assessment_records
                    (record_id, candidate_id, payload, owner_user_id, organization_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        record_id,
                        candidate_id,
                        json.dumps(payload, ensure_ascii=False),
                        user["user_id"],
                        user.get("organization_id"),
                        datetime.now(UTC).isoformat(),
                    ),
                )
        return payload

    def delete_assessment_record(self, record_id: str, user: dict) -> bool:
        if not self.db_path:
            return False
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT owner_user_id, organization_id FROM assessment_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                return False
            allowed = row[0] == user["user_id"] or bool(
                user.get("role") == "enterprise" and row[1] == user.get("organization_id")
            )
            if not allowed:
                raise PermissionError("assessment record access denied")
            connection.execute("DELETE FROM assessment_records WHERE record_id = ?", (record_id,))
        return True

    def save_report(
        self,
        report: MatchReport,
        profile: CandidateProfile,
        *,
        owner_user_id: str,
        organization_id: str | None = None,
    ) -> MatchReport:
        self.reports[report.report_id] = report
        self.report_profiles[report.report_id] = profile
        self.report_access[report.report_id] = {
            "owner_user_id": owner_user_id,
            "organization_id": organization_id,
        }
        if self.db_path:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO match_reports (
                        report_id, payload, profile_payload, owner_user_id,
                        organization_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report.report_id,
                        report.model_dump_json(),
                        profile.model_dump_json(),
                        owner_user_id,
                        organization_id,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO candidate_report_links (report_id, candidate_id, owner_user_id, organization_id, created_at) VALUES (?, ?, ?, ?, ?)",
                    (report.report_id, report.candidate_id, owner_user_id, organization_id, datetime.now(UTC).isoformat()),
                )
        report_user = {"user_id": owner_user_id, "organization_id": organization_id, "role": "enterprise" if organization_id else "seeker"}
        self._upsert_candidate(report.candidate_id, report_user, profile.name)
        self.save_candidate_event(report.candidate_id, report_user, "report_generated", {"report_id": report.report_id, "score": report.score})
        self.save_assessment_record(
            {
                "id": report.candidate_id,
                "candidate_id": report.candidate_id,
                "name": profile.name,
                "target_job_id": report.target_job_id,
                "status": "已出报告",
                "score": report.score,
                "profile": {**profile.model_dump(mode="json"), "match_report": report.model_dump(mode="json")},
            },
            report_user,
        )
        return report

    def save_emerging_jobs(self, candidates: list[EmergingJobCandidate]) -> list[EmergingJobCandidate]:
        for candidate in candidates:
            self.emerging_jobs[candidate.candidate_id] = candidate
            self._persist_model("emerging_jobs", "candidate_id", candidate.candidate_id, candidate.model_dump_json())
        return candidates

    def replace_emerging_jobs(self, candidates: list[EmergingJobCandidate]) -> list[EmergingJobCandidate]:
        incoming_ids = {candidate.candidate_id for candidate in candidates}
        stale_ids = [
            candidate_id
            for candidate_id, existing in self.emerging_jobs.items()
            if candidate_id not in incoming_ids and existing.review_status != "approved"
        ]
        if self.db_path and stale_ids:
            with sqlite3.connect(self.db_path) as connection:
                connection.executemany(
                    "DELETE FROM emerging_jobs WHERE candidate_id = ?",
                    [(candidate_id,) for candidate_id in stale_ids],
                )
        for candidate_id in stale_ids:
            self.emerging_jobs.pop(candidate_id, None)

        reconciled = []
        for candidate in candidates:
            existing = self.emerging_jobs.get(candidate.candidate_id)
            if existing and existing.review_status != "pending":
                candidate = candidate.model_copy(update={
                    "review_status": existing.review_status,
                    "definition_version": existing.definition_version,
                })
            reconciled.append(candidate)
        return self.save_emerging_jobs(reconciled)

    def review_emerging_job(
        self,
        candidate_id: str,
        status: str,
        corrections: dict | None = None,
    ) -> EmergingJobCandidate | None:
        candidate = self.emerging_jobs.get(candidate_id)
        if candidate is None:
            return None
        allowed = {
            "name", "domain", "definition", "core_responsibilities", "required_skills",
            "bonus_skills", "application_scenarios", "source_family", "difference_summary",
        }
        changes = {key: value for key, value in (corrections or {}).items() if key in allowed}
        changes["review_status"] = status
        changes["definition_version"] = f"emerging-job-v{int(candidate.definition_version.rsplit('v', 1)[-1] or 1) + 1}"
        updated = candidate.model_copy(update=changes)
        self.emerging_jobs[candidate_id] = updated
        self._persist_model("emerging_jobs", "candidate_id", candidate_id, updated.model_dump_json())
        return updated

    def save_validation_run(self, run: ValidationRun) -> ValidationRun:
        self.validation_runs[run.run_id] = run
        self._persist_model("validation_runs", "run_id", run.run_id, run.model_dump_json())
        return run

    def save_community_signals(self, signals: list[CommunitySignal]) -> list[CommunitySignal]:
        for signal in signals:
            self.community_signals[signal.signal_id] = signal
            self._persist_model("community_signals", "signal_id", signal.signal_id, signal.model_dump_json())
        return signals

    def list_community_signals(self, *, domain: str | None = None, source_platform: str | None = None):
        signals = [signal for signal in self.community_signals.values() if signal.metadata.get("quality_status") != "quarantined"]
        if domain:
            signals = [signal for signal in signals if signal.domain == domain]
        if source_platform:
            signals = [signal for signal in signals if signal.source_platform == source_platform]
        return sorted(signals, key=lambda signal: signal.published_at or signal.collected_at, reverse=True)

    def save_collection_run(self, run: DataCollectionRun) -> DataCollectionRun:
        self.collection_runs[run.run_id] = run
        self._persist_model("collection_runs", "run_id", run.run_id, run.model_dump_json())
        return run

    def save_setting(self, key: str, value: dict) -> dict:
        self.settings[key] = value
        if self.db_path:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO app_settings (setting_key, payload, updated_at) VALUES (?, ?, ?)",
                    (key, json.dumps(value, ensure_ascii=False, default=str), datetime.now(UTC).isoformat()),
                )
        return value

    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)

    def save_quality_rejections(self, records: list[DataQualityRejection]) -> list[DataQualityRejection]:
        for record in records:
            if record.record_type == "duplicate":
                continue
            existing = next((item for item in self.quality_rejections.values() if (
                item.source_category == record.source_category
                and item.source_platform == record.source_platform
                and item.source_id == record.source_id
                and item.record_type == record.record_type
                and item.reasons == record.reasons
                and item.review_status == "pending"
            )), None)
            if existing:
                record = existing.model_copy(update={
                    "last_seen_at": datetime.now(UTC),
                    "occurrence_count": existing.occurrence_count + 1,
                    "collection_run_id": record.collection_run_id,
                    "raw_item": record.raw_item or existing.raw_item,
                })
            self.quality_rejections[record.rejection_id] = record
            self._persist_model("quality_rejections", "rejection_id", record.rejection_id, record.model_dump_json())
        return records

    def save_data_audits(self, records: list[DataAuditRecord]) -> list[DataAuditRecord]:
        for record in records:
            self.data_audits[record.audit_id] = record
            self._persist_model("data_audits", "audit_id", record.audit_id, record.model_dump_json())
        return records

    def review_data_audit(
        self,
        audit_id: str,
        status: str,
        note: str | None = None,
        decision: str | None = None,
        corrections: dict | None = None,
    ) -> DataAuditRecord | None:
        record = self.data_audits.get(audit_id)
        if record is None:
            return None
        approved = status == "approved"
        normalized = dict(record.normalized_item)
        normalized.update(corrections or {})
        updated = record.model_copy(update={
            "status": "accepted" if approved else "rejected",
            "review_status": status,
            "review_note": note,
            "review_decision": decision or ("accept" if approved else "reject"),
            "corrections": corrections or {},
            "normalized_item": normalized,
            "graph_publish_status": "published" if approved else "blocked",
            "reviewed_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        })
        self.data_audits[audit_id] = updated
        self._persist_model("data_audits", "audit_id", audit_id, updated.model_dump_json())
        return updated

    def review_quality_rejection(
        self, rejection_id: str, status: str, note: str | None = None,
        decision: str | None = None, corrections: dict | None = None,
    ):
        record = self.quality_rejections.get(rejection_id)
        if record is None:
            return None
        updated = record.model_copy(update={
            "review_status": status,
            "review_note": note,
            "reviewed_at": datetime.now(UTC),
            "review_decision": decision or ("accept" if status == "approved" else "reject"),
            "corrections": corrections or {},
        })
        self.quality_rejections[rejection_id] = updated
        self._persist_model("quality_rejections", "rejection_id", rejection_id, updated.model_dump_json())
        self._save_audit_feedback(updated)
        return updated

    def _save_audit_feedback(self, record: DataQualityRejection) -> None:
        if not self.db_path:
            return
        feedback_id = f"feedback_{uuid4().hex[:12]}"
        payload = {
            "feedback_id": feedback_id, "rejection_id": record.rejection_id,
            "source_id": record.source_id, "source_platform": record.source_platform,
            "title": record.title, "reasons": record.reasons, "decision": record.review_decision,
            "status": record.review_status, "corrections": record.corrections,
            "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        }
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO audit_feedback (feedback_id, payload, updated_at) VALUES (?, ?, ?)",
                (feedback_id, json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
        policy = self.get_setting("audit_learning_policy", {"version": 0, "feedback_count": 0, "accepted_titles": {}, "rejected_titles": {}})
        title = (record.corrections.get("title") or record.title or "").strip().casefold()
        bucket = "accepted_titles" if record.review_status == "approved" else "rejected_titles"
        if title:
            entry = dict(policy.get(bucket, {}).get(title, {}))
            entry["count"] = int(entry.get("count", 0)) + 1
            if record.corrections.get("domain"):
                entry["domain"] = record.corrections["domain"]
            policy.setdefault(bucket, {})[title] = entry
        policy["version"] = int(policy.get("version", 0)) + 1
        policy["feedback_count"] = int(policy.get("feedback_count", 0)) + 1
        policy["updated_at"] = datetime.now(UTC).isoformat()
        self.save_setting("audit_learning_policy", policy)

    def learn_data_audit(self, record: DataAuditRecord) -> None:
        """Persist one idempotent governance decision and update the rule-learning policy."""
        if not self.db_path or record.review_status not in {"approved", "rejected"}:
            return
        feedback_id = f"governance_{record.audit_id}"
        with sqlite3.connect(self.db_path) as connection:
            existed = connection.execute(
                "SELECT 1 FROM audit_feedback WHERE feedback_id = ?",
                (feedback_id,),
            ).fetchone()
            if existed:
                return
            payload = {
                "feedback_id": feedback_id,
                "audit_id": record.audit_id,
                "source_id": record.source_id,
                "source_platform": record.source_platform,
                "title": record.title,
                "reasons": record.reasons,
                "decision": record.review_decision,
                "status": record.review_status,
                "corrections": record.corrections,
                "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
            }
            connection.execute(
                "INSERT INTO audit_feedback (feedback_id, payload, updated_at) VALUES (?, ?, ?)",
                (feedback_id, json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
        policy = self.get_setting(
            "audit_learning_policy",
            {"version": 0, "feedback_count": 0, "accepted_titles": {}, "rejected_titles": {}},
        )
        title = (record.corrections.get("title") or record.title or "").strip().casefold()
        bucket = "accepted_titles" if record.review_status == "approved" else "rejected_titles"
        if title:
            entry = dict(policy.get(bucket, {}).get(title, {}))
            entry["count"] = int(entry.get("count", 0)) + 1
            if record.corrections.get("domain"):
                entry["domain"] = record.corrections["domain"]
            policy.setdefault(bucket, {})[title] = entry
        policy["version"] = int(policy.get("version", 0)) + 1
        policy["feedback_count"] = int(policy.get("feedback_count", 0)) + 1
        policy["updated_at"] = datetime.now(UTC).isoformat()
        self.save_setting("audit_learning_policy", policy)

    def audit_learning_status(self) -> dict:
        policy = self.get_setting("audit_learning_policy", {"version": 0, "feedback_count": 0, "accepted_titles": {}, "rejected_titles": {}})
        return {
            **policy,
            "active_accepted_titles": sum(item.get("count", 0) >= 1 for item in policy.get("accepted_titles", {}).values()),
            "active_rejected_titles": sum(item.get("count", 0) >= 2 for item in policy.get("rejected_titles", {}).values()),
            "activation_policy": "人工通过立即记忆精确标题；拒绝标题累计两次后生效；所有策略可按版本回滚",
        }

    def _compact_quality_rejections(self) -> None:
        if not self.db_path or not self.quality_rejections:
            return
        grouped: dict[tuple, DataQualityRejection] = {}
        for record in self.quality_rejections.values():
            if record.record_type == "duplicate":
                continue
            key = (record.source_category, record.source_platform, record.source_id, record.record_type, tuple(record.reasons))
            current = grouped.get(key)
            if current is None:
                grouped[key] = record.model_copy(update={
                    "first_seen_at": record.rejected_at,
                    "last_seen_at": record.rejected_at,
                    "occurrence_count": max(1, record.occurrence_count),
                })
                continue
            preferred = record if record.review_status != "pending" else current
            grouped[key] = preferred.model_copy(update={
                "first_seen_at": min(current.first_seen_at, record.rejected_at),
                "last_seen_at": max(current.last_seen_at, record.rejected_at),
                "occurrence_count": current.occurrence_count + max(1, record.occurrence_count),
            })
        if len(grouped) == len(self.quality_rejections):
            return
        self.quality_rejections = {record.rejection_id: record for record in grouped.values()}
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("DELETE FROM quality_rejections")
            connection.executemany(
                "INSERT INTO quality_rejections (rejection_id, payload, updated_at) VALUES (?, ?, ?)",
                [(record.rejection_id, record.model_dump_json(), datetime.now(UTC).isoformat()) for record in grouped.values()],
            )


store = AppStore(os.getenv("TALENTGRAPH_DB_PATH", "data/talentgraph.db"))
