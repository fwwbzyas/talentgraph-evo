from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import UTC, datetime
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any

from generate_dataset import (
    DATASET_VERSION as SENTINEL_DATASET_VERSION,
    REAL_SOURCES,
    SCENARIO_COUNTS,
    SEED,
    anonymized_baseline,
    apply_event,
    assign_scenarios,
    digest,
    event_due,
    iso_time,
    month_id,
    open_database,
    select_baseline,
    write_jsonl,
)


DATASET_VERSION = "temporal-jd-full-corpus-v3.0"
# Fixed 12-month replay window required by the competition demo.
PERIODS = [month_id(2025, 9, offset) for offset in range(12)]


def load_real_jobs(source: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    db_path, temporary = open_database(source)
    try:
        connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            rows = connection.execute("SELECT job_id, payload FROM job_assets").fetchall()
        finally:
            connection.close()
    finally:
        if temporary:
            temporary.cleanup()

    excluded = Counter()
    jobs = []
    seen_ids = set()
    for job_id, payload in rows:
        item = json.loads(payload)
        platform = str(item.get("source_platform") or "")
        metadata = item.get("metadata") or {}
        if platform not in REAL_SOURCES:
            excluded["non_formal_or_simulated_source"] += 1
            continue
        if metadata.get("synthetic") or metadata.get("is_simulated") or metadata.get("synthetic_temporal_test"):
            excluded["simulation_flag"] += 1
            continue
        identity = str(item.get("source_id") or job_id)
        if identity in seen_ids:
            excluded["duplicate_source_id"] += 1
            continue
        seen_ids.add(identity)
        jobs.append(item)
    return jobs, {
        "database_job_count": len(rows),
        "formal_real_job_count": len(jobs),
        "excluded_counts": dict(excluded),
    }


def sentinel_candidates(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = []
    seen_hashes: set[str] = set()
    for item in jobs:
        if not (
            item.get("domain") in {"人工智能", "大数据", "智能系统", "物联网"}
            and item.get("job_status", "active") == "active"
            and len(item.get("content") or "") >= 300
            and len(item.get("skill_tags") or []) >= 3
            and item.get("company") and item.get("source_url")
        ):
            continue
        fingerprint = str(item.get("dedup_hash") or digest(json.dumps(item, sort_keys=True, ensure_ascii=False)))
        if fingerprint in seen_hashes:
            continue
        seen_hashes.add(fingerprint)
        eligible.append(item)
    return select_baseline(eligible, SEED)


def assign_introduction_months(jobs: list[dict[str, Any]], sentinel_ids: set[str]) -> dict[str, int]:
    assignments = {source_id: 0 for source_id in sentinel_ids}
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in jobs:
        source_id = str(item["source_id"])
        if source_id not in sentinel_ids:
            buckets[(str(item.get("domain") or "未知"), str(item.get("source_platform") or "unknown"))].append(item)
    month_loads = Counter({index: sum(value == index for value in assignments.values()) for index in range(12)})
    for key in sorted(buckets):
        bucket = sorted(buckets[key], key=lambda item: digest(f"bucket|{SEED}|{item.get('source_id')}", 64))
        for item in bucket:
            lightest = min(range(12), key=lambda index: (month_loads[index], index))
            assignments[str(item["source_id"])] = lightest
            month_loads[lightest] += 1
    return assignments


def sha256_file(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate(source: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    batches_dir = output / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    jobs, source_stats = load_real_jobs(source)
    sentinels = sentinel_candidates(jobs)
    sentinel_ids = {str(item["source_id"]) for item in sentinels}
    scenarios = assign_scenarios(sentinels)
    introductions = assign_introduction_months(jobs, sentinel_ids)
    monthly: dict[str, list[dict[str, Any]]] = {period: [] for period in PERIODS}
    truth: list[dict[str, Any]] = []

    for item in jobs:
        original_id = str(item["source_id"])
        month_index = introductions[original_id]
        period = PERIODS[month_index]
        raw = anonymized_baseline(item, SEED)
        raw["raw_content"] = raw["content"]
        raw["published_at"] = iso_time(period)
        raw["changed_at"] = iso_time(period)
        raw["metadata"] = {
            **raw["metadata"],
            "full_corpus_dataset_version": DATASET_VERSION,
            "feed_role": "sentinel" if original_id in sentinel_ids else "corpus",
            "introduction_period": period,
        }
        monthly[period].append({
            "record_id": f"{raw['source_id']}:{period}:intro",
            "dataset_version": DATASET_VERSION,
            "period": period,
            "observed_at": iso_time(period),
            "feed_role": "sentinel" if original_id in sentinel_ids else "corpus",
            "expected_outcome": "new_or_deduplicated",
            "raw_item": raw,
        })

    for source_item in sentinels:
        original_id = str(source_item["source_id"])
        state = anonymized_baseline(source_item, SEED)
        scenario = scenarios[original_id]
        phase = int(digest(f"phase|{SEED}|{original_id}", 8), 16)
        event_number = 0
        normalized_source_id = f"{state['source_platform']}:{state['source_id']}"
        truth.append({
            "record_id": f"{state['source_id']}:{PERIODS[0]}:intro",
            "period": PERIODS[0], "source_id": normalized_source_id, "scenario": scenario,
            "expected_outcome": "new", "expected_changed_fields": [],
            "expected_added_skills": [], "expected_removed_skills": [],
        })
        for month_index, period in enumerate(PERIODS[1:], start=1):
            expectation = {
                "event_type": "unchanged", "expected_changed_fields": [],
                "expected_added_skills": [], "expected_removed_skills": [], "month_index": month_index,
            }
            if event_due(scenario, month_index, phase):
                event_number += 1
                expectation = apply_event(state, scenario, month_index, event_number)
            outcome = "updated" if expectation["expected_changed_fields"] else "unchanged"
            raw = deepcopy(state)
            raw["raw_content"] = raw["content"]
            raw["published_at"] = iso_time(PERIODS[0])
            raw["changed_at"] = iso_time(period) if outcome == "updated" else None
            raw["metadata"] = {
                **raw["metadata"], "full_corpus_dataset_version": DATASET_VERSION,
                "feed_role": "sentinel", "introduction_period": PERIODS[0], "observation_period": period,
            }
            record_id = f"{raw['source_id']}:{period}:monitor"
            monthly[period].append({
                "record_id": record_id, "dataset_version": DATASET_VERSION, "period": period,
                "observed_at": iso_time(period), "feed_role": "sentinel", "scenario": scenario,
                "expected_outcome": outcome, "raw_item": raw,
            })
            truth.append({
                "record_id": record_id, "period": period, "source_id": normalized_source_id,
                "scenario": scenario, "expected_outcome": outcome, **expectation,
            })

    batch_manifest = []
    for period in PERIODS:
        records = sorted(monthly[period], key=lambda row: (row["feed_role"] != "sentinel", row["record_id"]))
        path = batches_dir / f"{period}.jsonl.gz"
        write_jsonl(path, records, compressed=True)
        batch_manifest.append({
            "period": period,
            "file": f"batches/{path.name}",
            "records": len(records),
            "introductions": sum(row["record_id"].endswith(":intro") for row in records),
            "sentinel_observations": sum(row["feed_role"] == "sentinel" and row["record_id"].endswith(":monitor") for row in records),
            "sha256": sha256_file(path),
            "compressed_bytes": path.stat().st_size,
        })
    write_jsonl(output / "sentinel_ground_truth.jsonl", truth)
    manifest = {
        "dataset_version": DATASET_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "seed": SEED,
        "purpose": "现有全部正式真实JD按12个月逐步投喂，并以100条哨兵验证变化捕捉",
        "is_synthetic_temporal_test": True,
        "production_write_forbidden": True,
        "source_database": source.name,
        "source_database_sha256": sha256_file(source),
        "periods": PERIODS,
        "formal_real_job_count": len(jobs),
        "sentinel_count": len(sentinels),
        "total_feed_records": sum(item["records"] for item in batch_manifest),
        "domain_counts": dict(Counter(str(item.get("domain") or "未知") for item in jobs)),
        "source_counts": dict(Counter(str(item.get("source_platform") or "unknown") for item in jobs)),
        "scenario_counts": SCENARIO_COUNTS,
        "monthly_batches": batch_manifest,
        "source_stats": source_stats,
        "design": {
            "all_real_jobs_introduced_once": True,
            "stratified_by": ["domain", "source_platform"],
            "monthly_load_balancing": True,
            "sentinels_introduced_in_first_month": True,
            "sentinels_reobserved_monthly": True,
            "sentinel_basis": SENTINEL_DATASET_VERSION,
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="将现有9000+真实JD生成12个月逐步投喂数据集")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "full_corpus_data")
    args = parser.parse_args()
    manifest = generate(args.source.resolve(), args.output.resolve())
    print(json.dumps({
        "dataset_version": manifest["dataset_version"],
        "formal_real_job_count": manifest["formal_real_job_count"],
        "sentinel_count": manifest["sentinel_count"],
        "total_feed_records": manifest["total_feed_records"],
        "monthly_counts": [item["records"] for item in manifest["monthly_batches"]],
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
