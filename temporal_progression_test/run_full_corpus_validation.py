from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import gzip
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from time import perf_counter
from typing import Any


SUITE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SUITE_DIR.parent
sys.path.insert(0, str(REPO_ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def patch_version_times(db_path: Path, observed_at_by_job: dict[str, str]) -> None:
    if not observed_at_by_job:
        return
    with sqlite3.connect(db_path) as connection:
        for job_id, observed_at in observed_at_by_job.items():
            row = connection.execute(
                "SELECT version_id, payload FROM job_versions WHERE job_id = ? ORDER BY version_number DESC LIMIT 1",
                (job_id,),
            ).fetchone()
            if not row:
                raise AssertionError(f"缺少岗位版本：{job_id}")
            version_id, payload_text = row
            payload = json.loads(payload_text)
            payload["changed_at"] = observed_at
            connection.execute(
                "UPDATE job_versions SET changed_at = ?, payload = ? WHERE version_id = ?",
                (observed_at, json.dumps(payload, ensure_ascii=False), version_id),
            )


def validate(dataset_dir: Path, work_dir: Path) -> dict[str, Any]:
    os.environ["TALENTGRAPH_DB_PATH"] = str(work_dir / "global-import-guard.db")
    os.environ["TALENTGRAPH_LLM_DISABLED"] = "1"
    from agents.data.service import DataAgent
    from agents.evolution.service import EvolutionAgent
    from agents.job_graph.knowledge_graph import KnowledgeGraphService
    from contracts import ImportRequest
    from core.store import AppStore

    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    truth_rows = read_jsonl(dataset_dir / "sentinel_ground_truth.jsonl")
    truth = {row["record_id"]: row for row in truth_rows}
    periods = manifest["periods"]
    test_db = work_dir / "full-corpus-validation.db"
    store = AppStore(str(test_db))
    agent = DataAgent()
    start = perf_counter()
    monthly_results = []
    rejected_examples = []
    sentinel_expected = Counter(row["expected_outcome"] for row in truth_rows)
    sentinel_actual = Counter()
    sentinel_misses = []
    sentinel_rejected = []
    rejections_by_role = Counter()
    rejection_reason_counts = Counter()
    unique_accepted_source_ids: set[str] = set()
    changed_field_checks = 0
    changed_field_misses = []
    skill_addition_misses = []
    skill_removal_misses = []
    total_records = 0
    total_accepted = 0
    total_rejected = 0

    for batch_info in manifest["monthly_batches"]:
        period = batch_info["period"]
        rows = read_jsonl(dataset_dir / batch_info["file"])
        total_records += len(rows)
        by_unprefixed = {str(row["raw_item"]["source_id"]): row for row in rows}
        clean_start = perf_counter()
        batch = agent.run(ImportRequest(
            batch_name=f"full_corpus_{period}",
            items=[row["raw_item"] for row in rows],
            min_quality=0,
            strict_scope=True,
        ))
        clean_seconds = perf_counter() - clean_start
        total_accepted += len(batch.items)
        rejected = len(rows) - len(batch.items)
        total_rejected += rejected
        rejection_reason_counts.update(batch.quality_summary.get("rejection_reasons") or {})
        rejected_examples.extend((batch.quality_summary.get("rejected_records") or [])[: max(0, 20 - len(rejected_examples))])
        accepted_source_ids = {item.source_id for item in batch.items}
        unique_accepted_source_ids.update(accepted_source_ids)
        for row in rows:
            raw_item = row["raw_item"]
            source_platform = str(raw_item.get("source_platform") or "unknown")
            raw_source_id = str(raw_item.get("source_id") or "")
            canonical_source_id = (
                raw_source_id
                if raw_source_id.startswith(f"{source_platform}:")
                else f"{source_platform}:{raw_source_id}"
            )
            if canonical_source_id in accepted_source_ids:
                continue
            role = str(row.get("feed_role") or (raw_item.get("metadata") or {}).get("feed_role") or "corpus")
            rejections_by_role[role] += 1
            expected_truth = truth.get(row["record_id"])
            if expected_truth:
                sentinel_actual["rejected"] += 1
                miss = {
                    "record_id": row["record_id"],
                    "expected": expected_truth["expected_outcome"],
                    "actual": "rejected",
                }
                sentinel_misses.append(miss)
                sentinel_rejected.append(miss)
        before_ids = set(store.jobs)
        ingest_start = perf_counter()
        result = store.ingest_live_batch(batch)
        ingest_seconds = perf_counter() - ingest_start
        event_by_job = {event["job_id"]: event for event in result["events"]}
        observed_at_by_job = {}

        for item in batch.items:
            unprefixed = item.source_id.split(":", 1)[-1]
            row = by_unprefixed.get(unprefixed)
            if not row:
                continue
            actual = "new" if item.source_id not in before_ids and item.source_id in store.jobs else "updated" if item.source_id in event_by_job else "unchanged"
            if actual in {"new", "updated"}:
                observed_at_by_job[item.source_id] = row["observed_at"]
            expected_truth = truth.get(row["record_id"])
            if not expected_truth:
                continue
            expected = expected_truth["expected_outcome"]
            sentinel_actual[actual] += 1
            if actual != expected:
                sentinel_misses.append({"record_id": row["record_id"], "expected": expected, "actual": actual})
                continue
            if expected != "updated":
                continue
            event = event_by_job[item.source_id]
            changes = event["changes"]
            required = set(expected_truth.get("expected_changed_fields") or [])
            changed_field_checks += len(required)
            absent = sorted(required - set(changes))
            if absent:
                changed_field_misses.append({"record_id": row["record_id"], "missing": absent, "actual": sorted(changes)})
            skill_change = changes.get("skill_tags") or {"before": [], "after": []}
            before_skills = set(skill_change.get("before") or [])
            after_skills = set(skill_change.get("after") or [])
            for skill in expected_truth.get("expected_added_skills") or []:
                if skill not in after_skills - before_skills:
                    skill_addition_misses.append({"record_id": row["record_id"], "skill": skill})
            for skill in expected_truth.get("expected_removed_skills") or []:
                if skill not in before_skills - after_skills:
                    skill_removal_misses.append({"record_id": row["record_id"], "skill": skill})

        patch_version_times(test_db, observed_at_by_job)
        monthly_results.append({
            "period": period,
            "input_records": len(rows),
            "introductions": batch_info["introductions"],
            "sentinel_observations": batch_info["sentinel_observations"],
            "accepted": len(batch.items), "rejected": rejected,
            "new": result["new"], "updated": result["updated"], "unchanged": result["unchanged"],
            "exact_duplicate": result["exact_duplicate"], "repost": result["repost"],
            "clean_seconds": round(clean_seconds, 3), "ingest_seconds": round(ingest_seconds, 3),
        })

    versions = store.list_all_job_versions(limit=50000)
    evolution_start = perf_counter()
    market = EvolutionAgent().analyze_market(store.jobs.values(), versions, max_frames=20)
    evolution_seconds = perf_counter() - evolution_start
    graph_start = perf_counter()
    graph = KnowledgeGraphService().build_career_galaxy(store.jobs.values(), max_nodes=1400, deep_relations=True)
    graph_seconds = perf_counter() - graph_start
    actual_frame_periods = [frame["time"][:7] for frame in market["frames"]]
    duration = perf_counter() - start
    report = {
        "dataset_version": manifest["dataset_version"],
        "executed_at": datetime.now(UTC).isoformat(),
        "is_isolated_test": True,
        "production_database_modified": False,
        "formal_real_job_count": manifest["formal_real_job_count"],
        "sentinel_count": manifest["sentinel_count"],
        "periods": periods,
        "total_feed_records": total_records,
        "normalization_accepted": total_accepted,
        "normalization_rejected": total_rejected,
        "normalization_acceptance_rate": round(total_accepted / max(1, total_records), 6),
        "unique_accepted_source_ids": len(unique_accepted_source_ids),
        "rejections_by_role": dict(rejections_by_role),
        "rejection_reason_counts": dict(rejection_reason_counts),
        "final_job_assets": len(store.jobs),
        "version_count": len(versions),
        "sentinel_expected": dict(sentinel_expected),
        "sentinel_actual": dict(sentinel_actual),
        "sentinel_total": len(truth_rows),
        "sentinel_rejected": len(sentinel_rejected),
        "sentinel_outcome_accuracy": round((len(truth_rows) - len(sentinel_misses)) / max(1, len(truth_rows)), 6),
        "changed_field_recall": round((changed_field_checks - sum(len(item["missing"]) for item in changed_field_misses)) / max(1, changed_field_checks), 6),
        "skill_addition_misses": len(skill_addition_misses),
        "skill_removal_misses": len(skill_removal_misses),
        "market_frame_periods": actual_frame_periods,
        "market_change_events": market["summary"]["change_events"],
        "graph_nodes": len(graph.get("nodes") or []),
        "graph_links": len(graph.get("links") or []),
        "evolution_seconds": round(evolution_seconds, 3),
        "graph_seconds": round(graph_seconds, 3),
        "duration_seconds": round(duration, 3),
        "monthly_results": monthly_results,
        "failures": {
            "rejected_examples": rejected_examples,
            "sentinel_outcome_misses": sentinel_misses[:20],
            "changed_field_misses": changed_field_misses[:20],
            "skill_addition_misses": skill_addition_misses[:20],
            "skill_removal_misses": skill_removal_misses[:20],
        },
    }
    report["passed"] = all((
        total_records == manifest["total_feed_records"],
        total_accepted + total_rejected == total_records,
        len(store.jobs) == len(unique_accepted_source_ids),
        report["sentinel_rejected"] == 0,
        report["sentinel_outcome_accuracy"] == 1.0,
        report["changed_field_recall"] == 1.0,
        report["skill_addition_misses"] == 0,
        report["skill_removal_misses"] == 0,
        actual_frame_periods == periods,
        report["graph_nodes"] > 0 and report["graph_links"] > 0,
    ))
    return report


def markdown(report: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {item['period']} | {item['input_records']} | {item['accepted']} | {item['rejected']} | {item['new']} | {item['updated']} | {item['unchanged']} | {item['clean_seconds']} | {item['ingest_seconds']} |"
        for item in report["monthly_results"]
    )
    return f"""# 9000+真实JD月度渐进投喂实测摘要

- 结论：**{'通过' if report['passed'] else '未通过'}**
- 正式真实岗位：{report['formal_real_job_count']} 条
- 时间范围：{report['periods'][0]} 至 {report['periods'][-1]}
- 投喂记录：{report['total_feed_records']} 条
- 清洗接受/拒绝：{report['normalization_accepted']} / {report['normalization_rejected']}（接受率 {report['normalization_acceptance_rate']:.2%}）
- 清洗拒绝分层：语料 {report['rejections_by_role'].get('corpus', 0)} / 哨兵 {report['rejections_by_role'].get('sentinel', 0)}
- 最终岗位资产：{report['final_job_assets']} 条
- 100条哨兵观测：{report['sentinel_total']} 条，清洗拒绝 {report['sentinel_rejected']} 条
- 100条哨兵变化分类准确率：{report['sentinel_outcome_accuracy']:.2%}
- 变化字段召回率：{report['changed_field_recall']:.2%}
- 版本快照：{report['version_count']} 条
- 演化帧：{len(report['market_frame_periods'])} 个
- 图谱：{report['graph_nodes']} 节点 / {report['graph_links']} 关系
- 总用时：{report['duration_seconds']} 秒

| 月份 | 输入 | 接受 | 拒绝 | 新增 | 更新 | 无变化 | 清洗秒 | 入库秒 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{rows}

> 模拟月份只用于验证时间演化检测，不代表真实市场趋势；全过程写入隔离测试库。
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=SUITE_DIR / "full_corpus_data")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--report-dir", type=Path, default=SUITE_DIR / "reports")
    args = parser.parse_args()
    temporary = None
    work_dir = args.work_dir
    if work_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="full-corpus-validation-")
        work_dir = Path(temporary.name)
    work_dir.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = validate(args.dataset.resolve(), work_dir.resolve())
    (args.report_dir / "full_corpus_latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.report_dir / "full_corpus_latest.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps({
        "passed": report["passed"],
        "formal_real_job_count": report["formal_real_job_count"],
        "total_feed_records": report["total_feed_records"],
        "normalization_accepted": report["normalization_accepted"],
        "normalization_rejected": report["normalization_rejected"],
        "sentinel_outcome_accuracy": report["sentinel_outcome_accuracy"],
        "changed_field_recall": report["changed_field_recall"],
        "graph_nodes": report["graph_nodes"],
        "graph_links": report["graph_links"],
        "duration_seconds": report["duration_seconds"],
        "report_json": str((args.report_dir / "full_corpus_latest.json").resolve()),
        "report_markdown": str((args.report_dir / "full_corpus_latest.md").resolve()),
    }, ensure_ascii=True, indent=2))
    if temporary:
        temporary.cleanup()
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
