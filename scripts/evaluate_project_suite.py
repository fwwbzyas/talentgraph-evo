"""Run the project evidence suite through production parsing, data, graph and match code.

The runner is intentionally local and read-only with respect to the production database.
It writes only the report files below ``data/evaluation/project_suite``.
"""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import statistics
import subprocess
import sys
import time
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:  # pragma: no cover - dotenv is optional for local fallback mode
    pass

from agents.assessment.resume_files import extract_resume_text
from agents.assessment.resume_parser import ResumeParsingAgent
from agents.data.normalization import classify_domain, is_valid_skill
from agents.data.service import DataAgent
from agents.job_graph.service import JobGraphAgent
from agents.learning.job_catalog import load_job_profiles
from agents.match.service import ALIASES, MatchAgent
from contracts import (
    CandidateProfile,
    CleanedDataBatch,
    ImportRequest,
    JobGraph,
    SkillEvidence,
    SkillRequirement,
)
from core.sample_data import generate_demo_jds
from scripts.evaluate_resume_gold_100 import score_record


DEFAULT_DB = ROOT / "data" / "talentgraph.db"
DEFAULT_RESUME_DATA = ROOT / "data" / "evaluation" / "resume_gold_100"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "project_suite"
VOLATILE_KEYS = {
    "audit_id",
    "batch_id",
    "changed_at",
    "collected_at",
    "completed_at",
    "created_at",
    "discovered_at",
    "duration_ms",
    "generated_at",
    "observation_id",
    "report_id",
    "run_id",
    "session_id",
    "updated_at",
    "version_id",
}
JD_FIELDS = ("title", "domain", "skill_tags", "responsibilities", "city", "education")
DB_FIELDS = ("title", "domain", "skill_tags", "responsibilities", "city", "education", "company")


def _stable(value: Any) -> Any:
    """Remove run timestamps and ids before hashing an otherwise structured value."""
    if isinstance(value, dict):
        return {
            str(key): _stable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_stable(item) for item in value]
    if isinstance(value, tuple):
        return [_stable(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(_stable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def json_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def f1_score(expected: Any, actual: Any) -> float:
    if isinstance(expected, list) or isinstance(actual, list):
        left = {_text(item) for item in (expected or []) if _text(item)}
        right = {_text(item) for item in (actual or []) if _text(item)}
        if not left and not right:
            return 1.0
        overlap = len(left & right)
        precision = overlap / len(right) if right else 0.0
        recall = overlap / len(left) if left else 1.0
        return round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0
    return 1.0 if _text(expected) == _text(actual) else 0.0


def _mean(values: list[float]) -> float:
    return round(statistics.mean(values), 4) if values else 0.0


def _model_dump(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)


def _record_projection(value: Any, fields: tuple[str, ...] | None = None) -> dict[str, Any]:
    payload = _model_dump(value)
    if fields is not None:
        payload = {field: payload.get(field) for field in fields}
    return _stable(payload)


@contextmanager
def local_only() -> Iterator[None]:
    """Prevent an accidental configured LLM endpoint from changing this benchmark."""
    previous = os.environ.get("TALENTGRAPH_LLM_DISABLED")
    os.environ["TALENTGRAPH_LLM_DISABLED"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TALENTGRAPH_LLM_DISABLED", None)
        else:
            os.environ["TALENTGRAPH_LLM_DISABLED"] = previous


def run_controlled_jd(count: int = 100) -> tuple[dict[str, Any], list[dict[str, Any]], CleanedDataBatch]:
    raw_items = generate_demo_jds(count)
    batch = DataAgent().run(ImportRequest(batch_name="project_suite_controlled_jd", items=raw_items))
    actual_by_id = {item.source_id: item for item in batch.items}
    field_values = {field: [] for field in JD_FIELDS}
    rows: list[dict[str, Any]] = []
    failures = 0
    for raw in raw_items:
        source_id = str(raw["source_id"])
        actual = actual_by_id.get(source_id)
        expected_domain = classify_domain(f"{raw.get('title', '')} {raw.get('domain', '')} {raw.get('content', '')}")
        expected_values = {**raw, "domain": expected_domain}
        scores = {}
        for field in JD_FIELDS:
            observed = getattr(actual, field) if actual is not None else None
            score = f1_score(expected_values.get(field), observed)
            field_values[field].append(score)
            scores[field] = score
        if actual is None or any(score < 1 for score in scores.values()):
            failures += 1
        rows.append({"sample_id": source_id, "accepted": actual is not None, "field_f1": scores})
    field_metrics = {field: _mean(values) for field, values in field_values.items()}
    section = {
        "status": "completed",
        "label_type": "controlled",
        "label_source": "core.sample_data.generate_demo_jds controlled fields + production DataAgent.run",
        "limitations": [
            "Generated fixtures are controlled synthetic records, not market-distributed human labels.",
            "The generator timestamps are excluded from determinism hashes.",
        ],
        "production_api": ["core.sample_data.generate_demo_jds", "agents.data.service.DataAgent.run"],
        "sample_count": len(raw_items),
        "accepted_count": len(batch.items),
        "rejected_count": len(raw_items) - len(batch.items),
        "field_metrics": field_metrics,
        "macro_f1": _mean(list(field_metrics.values())),
        "failure_record_count": failures,
        "input_stable_sha256": json_hash(raw_items),
        "normalized_stable_sha256": json_hash([_record_projection(item, JD_FIELDS) for item in batch.items]),
        "quality_summary": {
            key: value
            for key, value in batch.quality_summary.items()
            if key in {"total", "fetched", "accepted", "rejected", "avg_quality", "companies", "cities", "active_jobs"}
        },
    }
    return section, rows, batch


def _resume_one(item: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    resume_path = data_dir / "files" / item["filename"]
    try:
        extracted = extract_resume_text(item["filename"], resume_path.read_bytes())
        parsed = ResumeParsingAgent().parse(
            str(extracted.get("text", "")),
            candidate_id=item["id"],
            source_name=item["filename"],
            images=extracted.get("images") or [],
            require_remote=False,
            use_remote=False,
        )
        gold = json.loads((data_dir / item["gold_file"]).read_text(encoding="utf-8"))
        scored = score_record(gold, parsed)
        return {
            "id": item["id"],
            "status": "ok",
            "processing_success": True,
            "usable_parse": sum(bool(parsed.get(key)) for key in ("job_intent", "skills", "projects")) >= 2,
            "format": item.get("format"),
            "domain": item.get("domain"),
            "difficulty": item.get("difficulty"),
            "split": item.get("split"),
            "macro_f1": round(float(scored["macro_f1"]), 6),
            "fields": scored["fields"],
            "provider_mode": "production_parser_deterministic_local",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:  # Keep all 100 inputs represented in the report.
        return {
            "id": item["id"],
            "status": "failed",
            "processing_success": False,
            "usable_parse": False,
            "format": item.get("format"),
            "domain": item.get("domain"),
            "difficulty": item.get("difficulty"),
            "split": item.get("split"),
            "macro_f1": 0.0,
            "fields": {},
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }


def run_resume_gold(data_dir: Path = DEFAULT_RESUME_DATA, workers: int = 4) -> dict[str, Any]:
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = sorted(manifest.get("records", []), key=lambda item: item.get("id", ""))
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_resume_one, item, data_dir) for item in records]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda item: item["id"])
    good = [row for row in rows if row["processing_success"]]
    field_names = ("job_intent", "skills", "projects", "experience_years", "education", "certifications", "preferred_locations", "expected_salary_k", "work_history")
    field_metrics = {
        field: {metric: _mean([row["fields"][field][metric] for row in good if field in row["fields"]]) for metric in ("precision", "recall", "f1")}
        for field in field_names
        if any(field in row["fields"] for row in good)
    }
    durations = [float(row["duration_ms"]) for row in rows]
    section = {
        "status": "completed",
        "label_type": "synthetic_gold",
        "label_source": "resume_gold_100 manifest/gold JSON + production extract_resume_text and ResumeParsingAgent.parse on 100 PDFs",
        "limitations": [
            "Gold profiles are fictional generated resumes and do not represent a human-annotated population.",
            "This run intentionally uses local deterministic parser mode; it does not measure remote LLM or vision quality.",
            "Matching is evaluated separately with gold profile fields, so this section does not measure parser-to-match error propagation.",
        ],
        "production_api": ["agents.assessment.resume_files.extract_resume_text", "agents.assessment.resume_parser.ResumeParsingAgent.parse"],
        "dataset": manifest.get("dataset", "resume_gold_100"),
        "requested_count": len(records),
        "pdf_count": sum(str(item.get("filename", "")).lower().endswith(".pdf") for item in records),
        "gold_count": sum(bool(item.get("gold_file")) for item in records),
        "processing_success_rate": round(len(good) / len(rows), 4) if rows else 0.0,
        "usable_parse_rate": round(sum(row["usable_parse"] for row in rows) / len(rows), 4) if rows else 0.0,
        "macro_f1": _mean([row["macro_f1"] for row in good]),
        "field_metrics": field_metrics,
        "provider_stats": {"remote_used": 0, "local_parser_rows": len(good), "failures": len(rows) - len(good)},
        "timing_ms": {
            "mean": round(statistics.mean(durations), 2) if durations else 0.0,
            "p50": round(statistics.median(durations), 2) if durations else 0.0,
            "max": round(max(durations), 2) if durations else 0.0,
        },
        "rows": rows,
    }
    return section


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return bool(connection.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone())


def _db_payload(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if isinstance(payload, dict) and isinstance(payload.get("snapshot"), dict):
        return payload["snapshot"]
    return payload


def load_db_sample(db_path: Path, limit: int = 100) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not db_path.exists():
        raise FileNotFoundError(f"database not found: {db_path}")
    uri = f"file:{db_path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        tables = [row[0] for row in connection.execute("select name from sqlite_master where type='table'")]
        table = "job_assets" if "job_assets" in tables else "job_versions" if "job_versions" in tables else ""
        candidates: list[dict[str, Any]] = []
        if table == "job_assets":
            raw_rows = connection.execute("select job_id, payload from job_assets order by job_id").fetchall()
            for job_id, value in raw_rows:
                try:
                    payload = _db_payload(value)
                except (TypeError, json.JSONDecodeError):
                    continue
                if isinstance(payload, dict):
                    payload.setdefault("source_id", job_id)
                    candidates.append(payload)
        elif table == "job_versions":
            raw_rows = connection.execute("select job_id, version_number, version_id, payload from job_versions order by job_id, version_number desc, version_id desc").fetchall()
            seen: set[str] = set()
            for job_id, _version_number, _version_id, value in raw_rows:
                if job_id in seen:
                    continue
                seen.add(job_id)
                try:
                    payload = _db_payload(value)
                except (TypeError, json.JSONDecodeError):
                    continue
                if isinstance(payload, dict):
                    payload.setdefault("source_id", job_id)
                    candidates.append(payload)
        technical = [
            item for item in candidates
            if item.get("title") and item.get("content")
            and str(item.get("source_platform") or "") not in {"结构化模拟样本", "synthetic"}
        ]
        selected = sorted(technical or candidates, key=lambda item: str(item.get("source_id", "")))[:limit]
        counts = {
            table_name: connection.execute(f"select count(*) from \"{table_name}\"").fetchone()[0]
            for table_name in ("job_assets", "job_versions", "job_profiles", "enterprise_jobs")
            if table_name in tables
        }
    return selected, {"source_table": table, "candidate_count": len(candidates), "technical_candidate_count": len(technical), "table_counts": counts}


def run_db_silver(db_path: Path, limit: int = 100) -> tuple[dict[str, Any], CleanedDataBatch, list[dict[str, Any]]]:
    raw_items, selection = load_db_sample(db_path, limit)
    first = DataAgent().run(ImportRequest(batch_name="project_suite_db_silver", items=raw_items))
    second = DataAgent().run(ImportRequest(batch_name="project_suite_db_silver_repeat", items=raw_items))
    first_by_id = {item.source_id: item for item in first.items}
    second_by_id = {item.source_id: item for item in second.items}
    field_values = {field: [] for field in DB_FIELDS}
    rows = []
    for raw in raw_items:
        source_id = str(raw.get("source_id"))
        actual = first_by_id.get(source_id)
        scores = {field: f1_score(raw.get(field), getattr(actual, field) if actual else None) for field in DB_FIELDS}
        for field, score in scores.items():
            field_values[field].append(score)
        rows.append({"sample_id": source_id, "accepted": actual is not None, "repeat_accepted": source_id in second_by_id, "field_f1": scores})
    stable_first = [_record_projection(first_by_id[key], DB_FIELDS) if key in first_by_id else {"source_id": key, "accepted": False} for key in sorted({str(item.get("source_id")) for item in raw_items})]
    stable_second = [_record_projection(second_by_id[key], DB_FIELDS) if key in second_by_id else {"source_id": key, "accepted": False} for key in sorted({str(item.get("source_id")) for item in raw_items})]
    section = {
        "status": "completed",
        "label_type": "silver",
        "label_source": "read-only production DB sample (job_assets/job_versions) re-run through DataAgent; no human gold labels",
        "limitations": [
            "Silver agreement is a deterministic re-normalization check, not an accuracy score against ground truth.",
            "The sample is sorted by persisted source_id and excludes synthetic DB rows when enough real rows exist.",
            "DB contents can change outside this process; the recorded DB SHA256 identifies this run's input snapshot.",
        ],
        "production_api": ["agents.data.service.DataAgent.run"],
        "sample_count": len(raw_items),
        "accepted_count": len(first.items),
        "rejected_count": len(raw_items) - len(first.items),
        "repeat_accepted_count": len(second.items),
        "field_metrics": {field: _mean(values) for field, values in field_values.items()},
        "db_field_macro_f1": _mean([_mean(values) for values in field_values.values()]),
        "deterministic_record_consistency": round(sum(left == right for left, right in zip(stable_first, stable_second)) / len(stable_first), 4) if stable_first else 0.0,
        "first_normalized_stable_sha256": json_hash(stable_first),
        "repeat_normalized_stable_sha256": json_hash(stable_second),
        "selection": selection,
        "rows": rows,
    }
    return section, first, raw_items


def _enterprise_graph(job: dict[str, Any]) -> JobGraph:
    job_id = str(job["job_id"])
    evidence = [SkillEvidence(source_id=job_id, source_type="enterprise_job", snippet=str(text), confidence=0.95) for text in (job.get("responsibilities") or [job.get("title", "")])]
    skills = [
        SkillRequirement(
            skill_id=f"{job_id}:{name}",
            name=str(name),
            category="core",
            required_level="intermediate",
            importance="required",
            evidence=evidence[:2],
            confidence=0.95,
        )
        for name in job.get("required_skills", [])
        if is_valid_skill(name)
    ]
    skills.extend(
        SkillRequirement(
            skill_id=f"{job_id}:{name}",
            name=str(name),
            category="plus",
            required_level="basic",
            importance="preferred",
            evidence=evidence[:1],
            confidence=0.82,
        )
        for name in job.get("preferred_skills", [])
        if is_valid_skill(name)
    )
    return JobGraph(
        job_id=job_id,
        job_title=str(job.get("title", job_id)),
        domain=str(job.get("domain", "")),
        responsibilities=[str(item) for item in job.get("responsibilities", [])],
        skills=skills,
        scenarios=[str(item) for item in job.get("responsibilities", [])],
        evidence_summary={"source": "enterprise_job", "job_id": job_id},
    )


def _profile_from_gold(gold: dict[str, Any], target_job_id: str) -> CandidateProfile:
    candidate = gold.get("candidate_profile") or {}
    level = {"初级": "basic", "中级": "intermediate", "高级": "advanced"}.get(candidate.get("level"), "intermediate")
    evidence_by_skill = {str(item.get("skill")): str(item.get("evidence", "")) for item in gold.get("skill_evidence", []) if isinstance(item, dict)}
    skills = [{"name": str(name), "level": level, "evidence": evidence_by_skill.get(str(name), "gold profile skill"), "confidence": 0.95} for name in gold.get("skills", [])]
    base = {"初级": 66, "中级": 78, "高级": 90}.get(candidate.get("level"), 72)
    dimensions = [{"name": name, "score": base, "evidence_count": len(gold.get("projects", []))} for name in ("专业技术", "工程实践", "问题解决", "行为素质")]
    evidence = [{"type": "gold_skill_evidence", "skill": item.get("skill"), "content": item.get("evidence", "")} for item in gold.get("skill_evidence", []) if isinstance(item, dict)]
    return CandidateProfile(
        candidate_id=str(candidate.get("candidate_id") or gold.get("id")),
        target_job_id=target_job_id,
        name=str(candidate.get("name", "")),
        skills=skills,
        projects=gold.get("projects", []) or [],
        behavior_signals=[{"type": "gold_strength", "content": item} for item in gold.get("strengths", [])],
        evidence=evidence,
        confidence=0.95,
        summary=str(gold.get("summary", "")),
        experience_years=candidate.get("experience_years"),
        education=gold.get("education"),
        preferred_locations=candidate.get("preferred_locations", []) or [],
        expected_salary_k=gold.get("expected_salary_k", []) or [],
        competency_dimensions=dimensions,
    )


def _rule_skill(value: Any) -> str:
    normalized = re.sub(r"[\s_\-（）()]+", "", str(value or "").strip().lower())
    return ALIASES.get(normalized, normalized)


def _rule_score(profile: CandidateProfile, job: dict[str, Any]) -> tuple[int, int, int, int]:
    profile_skills = {_rule_skill(item.get("name")) for item in profile.skills}
    required = {_rule_skill(item) for item in job.get("required_skills", [])}
    preferred = {_rule_skill(item) for item in job.get("preferred_skills", [])}
    required_overlap = len(profile_skills & required)
    preferred_overlap = len(profile_skills & preferred)
    domain_match = int(bool(profile.resume_analysis.get("domain") == job.get("domain")))
    return (required_overlap * 3 + preferred_overlap + domain_match * 2, required_overlap, preferred_overlap, domain_match)


def run_match_benchmark(resume_data: Path, db_path: Path, job_limit: int = 5) -> dict[str, Any]:
    manifest = json.loads((resume_data / "manifest.json").read_text(encoding="utf-8"))
    golds = []
    for item in sorted(manifest.get("records", []), key=lambda row: row.get("id", ""))[:100]:
        gold = json.loads((resume_data / item["gold_file"]).read_text(encoding="utf-8"))
        candidate = gold.get("candidate_profile") or {}
        gold["id"] = item.get("id")
        gold["candidate_profile"] = {**candidate, "domain": candidate.get("domain") or gold.get("domain")}
        golds.append(gold)
    uri = f"file:{db_path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        jobs = []
        for job_id, value in connection.execute("select job_id, payload from enterprise_jobs order by job_id"):
            try:
                payload = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                payload.setdefault("job_id", job_id)
                jobs.append(payload)
    jobs = jobs[:job_limit]
    graphs = {str(job["job_id"]): _enterprise_graph(job) for job in jobs}
    matcher = MatchAgent()
    ranking_rows = []
    for gold in golds:
        candidate_domain = (gold.get("candidate_profile") or {}).get("domain")
        profile_by_job = {}
        rule_values = {str(job["job_id"]): _rule_score(_profile_from_gold(gold, str(job["job_id"])), job) for job in jobs}
        max_rule = max(rule_values.values()) if rule_values else (0, 0, 0, 0)
        relevant = sorted(job_id for job_id, value in rule_values.items() if value == max_rule)
        for job in jobs:
            job_id = str(job["job_id"])
            profile = _profile_from_gold(gold, job_id)
            profile.resume_analysis = {"domain": candidate_domain}
            report = matcher.run(graphs[job_id], profile)
            profile_by_job[job_id] = {"score": report.score, "level": report.level, "matched_skill_count": len(report.matched_skills)}
        ranking = sorted(profile_by_job, key=lambda job_id: (-profile_by_job[job_id]["score"], job_id))
        ranks = {job_id: index + 1 for index, job_id in enumerate(ranking)}
        relevant_ranks = [ranks[job_id] for job_id in relevant if job_id in ranks]
        ranking_rows.append({
            "candidate_id": str(gold.get("id")),
            "rule_silver_relevant_job_ids": relevant,
            "rule_silver_primary_job_id": relevant[0] if relevant else None,
            "predicted_top1_job_id": ranking[0] if ranking else None,
            "predicted_ranking": [{"job_id": job_id, **profile_by_job[job_id], "rank": ranks[job_id]} for job_id in ranking],
            "top1_hit": bool(ranking and ranking[0] in relevant),
            "top3_hit": bool(any(rank <= 3 for rank in relevant_ranks)),
            "reciprocal_rank": round(1 / min(relevant_ranks), 6) if relevant_ranks else 0.0,
        })
    pair_count = len(golds) * len(jobs)
    section = {
        "status": "completed",
        "label_type": "rule_silver",
        "label_source": "100 resume_gold_100 gold profile JSON x 5 persisted enterprise_jobs; relevance is deterministic rule-silver skill/domain overlap",
        "limitations": [
            "Rule-silver relevance is a reproducible proxy, not human recruiter judgment or hiring outcome.",
            "Gold profile fields bypass resume parsing in this section; parser quality is reported separately.",
            "Five enterprise jobs are a small snapshot and ties are retained as a relevant set.",
        ],
        "production_api": ["agents.match.service.MatchAgent.run"],
        "gold_profile_count": len(golds),
        "enterprise_job_count": len(jobs),
        "pair_count": pair_count,
        "metrics": {
            "top1": _mean([float(row["top1_hit"]) for row in ranking_rows]),
            "top3": _mean([float(row["top3_hit"]) for row in ranking_rows]),
            "mrr": _mean([row["reciprocal_rank"] for row in ranking_rows]),
            "primary_rule_silver_top1": _mean([float(row["predicted_top1_job_id"] == row["rule_silver_primary_job_id"]) for row in ranking_rows]),
        },
        "jobs": [{key: job.get(key) for key in ("job_id", "organization_id", "title", "domain", "required_skills", "preferred_skills")} for job in jobs],
        "rows": ranking_rows,
    }
    return section


def run_graph_case(db_batch: CleanedDataBatch) -> dict[str, Any]:
    target = ""
    if db_batch.items:
        # JobGraphAgent groups evidence by the first four target-title characters.
        # Pick the densest real prefix so this case exercises more than one JD when possible.
        candidates = []
        for item in db_batch.items:
            prefix = item.title[:4]
            evidence_count = sum(prefix in other.title for other in db_batch.items)
            ai_bias = int(bool(re.search(r"agent|智能体|大模型|人工智能", item.title, re.I)))
            candidates.append((-evidence_count, -ai_bias, item.title, item.source_id))
        target = min(candidates)[2]
    if not db_batch.items:
        return {
            "status": "unavailable",
            "label_type": "evidence_backed",
            "label_source": "production DB sample after DataAgent",
            "limitations": ["No accepted DB JD was available to build the graph."],
            "target_job_title": target,
        }
    graph = JobGraphAgent().run(db_batch, target)
    payload = _model_dump(graph)
    return {
        "status": "completed",
        "label_type": "evidence_backed",
        "label_source": "production DB JD sample -> DataAgent -> JobGraphAgent",
        "limitations": [
            "This is one graph case from a bounded DB sample, not a graph-wide quality evaluation.",
            "Graph semantics are evidence-backed by persisted JDs but are not human adjudicated here.",
        ],
        "production_api": ["agents.job_graph.service.JobGraphAgent.run"],
        "target_job_title": graph.job_title,
        "target_job_id": graph.job_id,
        "source_count": graph.evidence_summary.get("source_count", 0),
        "skill_count": len(graph.skills),
        "node_count": len(graph.graph_nodes),
        "edge_count": len(graph.graph_edges),
        "node_types": sorted({node.get("type") for node in graph.graph_nodes}),
        "edge_labels": sorted({edge.get("label") for edge in graph.graph_edges}),
        "graph": payload,
    }


def run_ai_agent_db_case(db_path: Path) -> dict[str, Any]:
    uri = f"file:{db_path.resolve()}?mode=ro"
    persisted = None
    with sqlite3.connect(uri, uri=True) as connection:
        row = connection.execute("select job_key, title, domain, job_count, payload from job_profiles where job_key = 'ai-agent'").fetchone()
        if row:
            persisted = {"job_key": row[0], "title": row[1], "domain": row[2], "job_count": row[3], "payload": json.loads(row[4])}
    recomputed = None
    try:
        recomputed = next((_model_dump(item) for item in load_job_profiles(db_path) if item.job_key == "ai-agent"), None)
    except Exception as exc:
        recomputed = {"error": f"{type(exc).__name__}: {str(exc)[:240]}"}
    return {
        "status": "completed" if persisted else "missing",
        "label_type": "db_fact",
        "label_source": "persisted production DB job_profiles row for job_key=ai-agent",
        "limitations": [
            "This section reports a DB catalog fact and does not claim the catalog is a human gold label.",
            "Persisted and recomputed catalog values can differ when the DB has been refreshed; both are shown when available.",
        ],
        "production_api": ["agents.learning.job_catalog.load_job_profiles"],
        "job_key": "ai-agent",
        "persisted_profile": persisted,
        "recomputed_profile": recomputed,
    }


def _git_snapshot() -> dict[str, Any]:
    def command(*args: str) -> str | None:
        try:
            result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
        except OSError:
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    status = command("status", "--porcelain", "--untracked-files=no") or ""
    return {
        "head": command("rev-parse", "HEAD"),
        "branch": command("branch", "--show-current"),
        "dirty_tracked_files": bool(status),
        "tracked_status_entry_count": len([line for line in status.splitlines() if line.strip()]),
        "tracked_status_sha256": hashlib.sha256(status.encode()).hexdigest(),
    }


def _db_snapshot(db_path: Path) -> dict[str, Any]:
    info = {"path": str(db_path.resolve()), "exists": db_path.exists(), "read_only": True}
    if not db_path.exists():
        return info
    info.update({"bytes": db_path.stat().st_size, "sha256": file_hash(db_path)})
    try:
        _items, selection = load_db_sample(db_path, 1)
        info["table_counts"] = selection.get("table_counts", {})
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
    return info


def build_manifest(db_path: Path, resume_data: Path) -> dict[str, Any]:
    resume_manifest = resume_data / "manifest.json"
    payload = json.loads(resume_manifest.read_text(encoding="utf-8"))
    artifact_digest_input = [
        {"id": item.get("id"), "file_hashes": item.get("file_hashes", {}), "gold_file": item.get("gold_file")}
        for item in sorted(payload.get("records", []), key=lambda row: row.get("id", ""))
    ]
    return {
        "status": "completed",
        "label_type": "provenance",
        "label_source": "local filesystem, read-only DB inspection, git subprocess and Python platform metadata",
        "limitations": [
            "Git status intentionally reports tracked dirtiness only; untracked artifacts are not expanded in this compact report.",
            "Platform metadata describes the runner host and is not a reproducibility guarantee across hosts.",
        ],
        "runner": {"path": str(Path(__file__).resolve()), "sha256": file_hash(Path(__file__))},
        "resume_manifest": {
            "path": str(resume_manifest.resolve()),
            "sha256": file_hash(resume_manifest),
            "dataset": payload.get("dataset"),
            "record_count": len(payload.get("records", [])),
            "artifact_hashes_sha256": json_hash(artifact_digest_input),
        },
        "git": _git_snapshot(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "db": _db_snapshot(db_path),
    }


def _section_rows(section_name: str, section: dict[str, Any]) -> list[dict[str, Any]]:
    limitations = " | ".join(section.get("limitations", []))
    label_source = section.get("label_source", "")
    rows: list[dict[str, Any]] = []

    def add(metric: str, value: Any, sample_id: str = "summary") -> None:
        if isinstance(value, (str, int, float, bool)) or value is None:
            rows.append({"section": section_name, "sample_id": sample_id, "metric": metric, "value": value, "label_source": label_source, "limitations": limitations})

    for key in ("sample_count", "accepted_count", "rejected_count", "pair_count", "pdf_count", "gold_count", "processing_success_rate", "usable_parse_rate", "macro_f1", "db_field_macro_f1", "deterministic_record_consistency", "node_count", "edge_count", "source_count", "skill_count"):
        if key in section:
            add(key, section[key])
    for key, value in (section.get("field_metrics") or {}).items():
        if isinstance(value, dict):
            for metric, metric_value in value.items():
                add(f"{key}.{metric}", metric_value)
        else:
            add(key, value)
    for key, value in (section.get("metrics") or {}).items():
        add(key, value)
    for row in section.get("rows", [])[:1000]:
        sample_id = str(row.get("id") or row.get("sample_id") or row.get("candidate_id") or "row")
        for key in ("macro_f1", "top1_hit", "top3_hit", "reciprocal_rank", "accepted", "repeat_accepted"):
            if key in row:
                add(key, row[key], sample_id)
        for field, value in (row.get("field_f1") or {}).items():
            add(f"field_f1.{field}", value, sample_id)
    return rows


def write_csv(report: dict[str, Any], path: Path) -> None:
    columns = ["section", "sample_id", "metric", "value", "label_source", "limitations"]
    rows: list[dict[str, Any]] = []
    for name, section in report.get("sections", {}).items():
        rows.extend(_section_rows(name, section))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


METHODOLOGY = {
    "schema_version": "project-suite-v1",
    "label_source": "This file documents the executable local evidence suite.",
    "limitations": [
        "Controlled generated JD and resume gold data are synthetic.",
        "DB JD and rule-silver match labels are reproducible proxies, not human gold labels.",
        "Remote LLM calls are disabled for deterministic local execution.",
    ],
    "sections": {
        "controlled_generated_jd": "generate_demo_jds(100) -> DataAgent.run; compare controlled fields.",
        "resume_gold_pdf": "Parse all 100 existing manifest PDFs with extract_resume_text and ResumeParsingAgent.parse; score against gold JSON using the existing evaluator scorer.",
        "db_jd_silver": "Select sorted non-synthetic persisted DB JDs, run DataAgent twice, report DB field agreement and repeat consistency.",
        "match_benchmark": "Build enterprise JobGraph objects, call MatchAgent for 100 gold profiles x 5 jobs, rank by report score; compare against deterministic required/preferred skill plus domain rule-silver labels using top1/top3/MRR.",
        "actual_graph_case": "Run JobGraphAgent on the accepted DB sample and preserve the produced graph payload.",
        "ai_agent_engineer_db_case": "Read persisted job_profiles row ai-agent and compare with load_job_profiles recomputation when available.",
    },
}


def build_report(db_path: Path = DEFAULT_DB, resume_data: Path = DEFAULT_RESUME_DATA, resume_workers: int = 4) -> dict[str, Any]:
    with local_only():
        controlled, _controlled_rows, _controlled_batch = run_controlled_jd(100)
        resume = run_resume_gold(resume_data, workers=resume_workers)
        db_silver, db_batch, _db_raw = run_db_silver(db_path, 100)
        match = run_match_benchmark(resume_data, db_path, 5)
        graph = run_graph_case(db_batch)
        ai_db = run_ai_agent_db_case(db_path)
    manifest = build_manifest(db_path, resume_data)
    sections = {
        "controlled_generated_jd": controlled,
        "resume_gold_pdf": resume,
        "db_jd_silver": db_silver,
        "match_benchmark": match,
        "actual_graph_case": graph,
        "ai_agent_engineer_db_case": ai_db,
    }
    summary = {
        "status": "completed",
        "label_type": "summary",
        "label_source": "aggregated from the six executable project-suite sections",
        "limitations": ["Summary metrics inherit each section's labels and limitations; see section details."],
        "controlled_jd_macro_f1": controlled.get("macro_f1", 0.0),
        "resume_pdf_count": resume.get("pdf_count", 0),
        "resume_processing_success_rate": resume.get("processing_success_rate", 0.0),
        "resume_macro_f1": resume.get("macro_f1", 0.0),
        "db_jd_sample_count": db_silver.get("sample_count", 0),
        "db_jd_silver_consistency": db_silver.get("deterministic_record_consistency", 0.0),
        "match_pair_count": match.get("pair_count", 0),
        "match_top1": match.get("metrics", {}).get("top1", 0.0),
        "match_top3": match.get("metrics", {}).get("top3", 0.0),
        "match_mrr": match.get("metrics", {}).get("mrr", 0.0),
        "graph_node_count": graph.get("node_count", 0),
        "graph_edge_count": graph.get("edge_count", 0),
        "ai_agent_db_status": ai_db.get("status"),
    }
    return {
        "schema_version": "project-suite-v1",
        "suite": "talentgraph_project_suite",
        "manifest": manifest,
        "sections": sections,
        "summary": summary,
    }


def run_suite(db_path: Path = DEFAULT_DB, resume_data: Path = DEFAULT_RESUME_DATA, output_dir: Path = DEFAULT_OUTPUT, resume_workers: int = 4) -> dict[str, Any]:
    report = build_report(db_path, resume_data, resume_workers)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    methodology_path = output_dir / "methodology.json"
    csv_path = output_dir / "metrics.csv"
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    methodology_path.write_text(json.dumps(METHODOLOGY, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(report, csv_path)
    report["outputs"] = {"summary_json": str(summary_path.resolve()), "methodology_json": str(methodology_path.resolve()), "metrics_csv": str(csv_path.resolve())}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--resume-data", type=Path, default=DEFAULT_RESUME_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume-workers", type=int, default=4)
    args = parser.parse_args()
    report = run_suite(args.db, args.resume_data, args.output_dir, args.resume_workers)
    print(json.dumps({"summary": report["summary"], "outputs": report["outputs"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
