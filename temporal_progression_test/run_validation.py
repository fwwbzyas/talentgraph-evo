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
os.environ.setdefault("TALENTGRAPH_LLM_DISABLED", "1")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def patch_latest_version_time(db_path: Path, job_id: str, observed_at: str) -> None:
    with sqlite3.connect(db_path) as connection:
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
    from agents.data.normalization import normalize_recruitment_item
    from agents.evolution.service import EvolutionAgent
    from agents.job_graph.knowledge_graph import KnowledgeGraphService
    from contracts import CleanedDataBatch, CleanedDataItem
    from core.store import AppStore

    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    observations = read_jsonl(dataset_dir / "temporal_raw_12_months.jsonl.gz")
    truths = {row["record_id"]: row for row in read_jsonl(dataset_dir / "ground_truth.jsonl")}
    periods = manifest["periods"]
    if len(observations) != 1200 or len(truths) != 1200:
        raise AssertionError("数据集必须包含100条基线 × 12个月 = 1200条观测")

    test_db = work_dir / "temporal-validation.db"
    store = AppStore(str(test_db))
    actual_outcomes = Counter()
    expected_outcomes = Counter()
    normalization_rejections: list[dict[str, Any]] = []
    missing_fields: list[dict[str, Any]] = []
    missing_skill_additions: list[dict[str, Any]] = []
    missing_skill_removals: list[dict[str, Any]] = []
    monthly_results: list[dict[str, Any]] = []
    start = perf_counter()

    grouped = {period: [] for period in periods}
    for row in observations:
        grouped[row["period"]].append(row)

    for period in periods:
        month_rows = grouped[period]
        cleaned_items = []
        expected_by_job: dict[str, dict[str, Any]] = {}
        for row in month_rows:
            normalized, issues = normalize_recruitment_item(row["raw_item"])
            if normalized is None:
                normalization_rejections.append({"record_id": row["record_id"], "issues": issues})
                continue
            item = CleanedDataItem.model_validate(normalized)
            cleaned_items.append(item)
            expected_by_job[item.source_id] = truths[row["record_id"]]
            expected_outcomes[truths[row["record_id"]]["expected_outcome"]] += 1
        if len(cleaned_items) != 100:
            raise AssertionError(f"{period} 清洗后应保留100条，实际{len(cleaned_items)}条")

        batch = CleanedDataBatch(batch_name=f"temporal_test_{period}", items=cleaned_items)
        result = store.ingest_live_batch(batch)
        event_by_job = {event["job_id"]: event for event in result["events"]}
        actual_outcomes.update({
            "new": result["new"],
            "updated": result["updated"],
            "unchanged": result["unchanged"],
        })
        monthly_results.append({
            "period": period,
            "new": result["new"],
            "updated": result["updated"],
            "unchanged": result["unchanged"],
            "exact_duplicate": result["exact_duplicate"],
            "repost": result["repost"],
        })

        for item in cleaned_items:
            truth = expected_by_job[item.source_id]
            expected = truth["expected_outcome"]
            if expected in {"new", "updated"}:
                patch_latest_version_time(test_db, item.source_id, truth["period"] + "-01T09:00:00+08:00")
            if expected != "updated":
                continue
            event = event_by_job.get(item.source_id)
            if not event:
                missing_fields.append({"record_id": truth["record_id"], "expected": truth["expected_changed_fields"], "actual": []})
                continue
            changes = event["changes"]
            required = set(truth["expected_changed_fields"])
            absent = sorted(required - set(changes))
            if absent:
                missing_fields.append({"record_id": truth["record_id"], "expected": sorted(required), "actual": sorted(changes), "missing": absent})
            skill_change = changes.get("skill_tags") or {"before": [], "after": []}
            before_skills = set(skill_change.get("before") or [])
            after_skills = set(skill_change.get("after") or [])
            for skill in truth["expected_added_skills"]:
                if skill not in after_skills - before_skills:
                    missing_skill_additions.append({"record_id": truth["record_id"], "skill": skill})
            for skill in truth["expected_removed_skills"]:
                if skill not in before_skills - after_skills:
                    missing_skill_removals.append({"record_id": truth["record_id"], "skill": skill})

    versions = store.list_all_job_versions(limit=10000)
    market = EvolutionAgent().analyze_market(store.jobs.values(), versions, max_frames=20)
    graph = KnowledgeGraphService().build_career_galaxy(store.jobs.values(), max_nodes=500, deep_relations=True)
    elapsed = perf_counter() - start
    expected_changed_periods = sorted({row["period"] for row in truths.values() if row["expected_outcome"] in {"new", "updated"}})
    actual_frame_periods = [frame["time"][:7] for frame in market["frames"]]

    outcome_total = sum(expected_outcomes.values())
    outcome_correct = sum(min(actual_outcomes[key], expected_outcomes[key]) for key in ("new", "updated", "unchanged"))
    updated_total = expected_outcomes["updated"]
    changed_field_checks = sum(len(row["expected_changed_fields"]) for row in truths.values() if row["expected_outcome"] == "updated")
    changed_field_misses = sum(len(row.get("missing") or row.get("expected") or []) for row in missing_fields)
    report = {
        "dataset_version": manifest["dataset_version"],
        "executed_at": datetime.now(UTC).isoformat(),
        "is_isolated_test": True,
        "production_database_modified": False,
        "test_database": str(test_db),
        "baseline_count": manifest["baseline_count"],
        "observation_count": len(observations),
        "normalization_accepted": len(observations) - len(normalization_rejections),
        "normalization_rejected": len(normalization_rejections),
        "expected_outcomes": dict(expected_outcomes),
        "actual_outcomes": dict(actual_outcomes),
        "outcome_accuracy": round(outcome_correct / max(1, outcome_total), 6),
        "changed_field_recall": round((changed_field_checks - changed_field_misses) / max(1, changed_field_checks), 6),
        "skill_addition_misses": len(missing_skill_additions),
        "skill_removal_misses": len(missing_skill_removals),
        "version_count": len(versions),
        "expected_changed_periods": expected_changed_periods,
        "market_frame_periods": actual_frame_periods,
        "market_change_events": market["summary"]["change_events"],
        "graph_nodes": len(graph.get("nodes") or []),
        "graph_links": len(graph.get("links") or []),
        "duration_seconds": round(elapsed, 3),
        "monthly_results": monthly_results,
        "failures": {
            "normalization_rejections": normalization_rejections[:20],
            "missing_changed_fields": missing_fields[:20],
            "missing_skill_additions": missing_skill_additions[:20],
            "missing_skill_removals": missing_skill_removals[:20],
        },
    }
    report["passed"] = all((
        report["normalization_rejected"] == 0,
        report["outcome_accuracy"] == 1.0,
        report["changed_field_recall"] == 1.0,
        report["skill_addition_misses"] == 0,
        report["skill_removal_misses"] == 0,
        actual_frame_periods == expected_changed_periods,
        report["graph_nodes"] > 0,
        report["graph_links"] > 0,
    ))
    return report


def report_markdown(report: dict[str, Any]) -> str:
    status = "通过" if report["passed"] else "未通过"
    monthly = "\n".join(
        f"| {row['period']} | {row['new']} | {row['updated']} | {row['unchanged']} | {row['exact_duplicate']} | {row['repost']} |"
        for row in report["monthly_results"]
    )
    return f"""# 时间渐进性自动化测试结果

- 结论：**{status}**
- 数据集：`{report['dataset_version']}`
- 基线岗位：{report['baseline_count']} 条
- 月度观测：{report['observation_count']} 条（12 个时间点）
- 生产数据库写入：否
- 变化分类准确率：{report['outcome_accuracy']:.2%}
- 变化字段召回率：{report['changed_field_recall']:.2%}
- 技能新增漏检：{report['skill_addition_misses']}
- 技能移除漏检：{report['skill_removal_misses']}
- 版本快照：{report['version_count']} 条
- 演化帧：{len(report['market_frame_periods'])} 个
- 图谱：{report['graph_nodes']} 节点 / {report['graph_links']} 关系
- 用时：{report['duration_seconds']} 秒

## 月度流水线结果

| 月份 | 新增 | 更新 | 无变化 | 完全重复 | 重发 |
|---|---:|---:|---:|---:|---:|
{monthly}

## 口径说明

本报告验证“清洗 → 去重/身份识别 → 观察结果 → 岗位版本 → 市场演化帧 → 三维图谱数据构建”工程链路。模拟数据仅用于时间渐进性测试，不能作为真实市场趋势证据，也不能替代需人工双人标注与仲裁的正式 JD 金标集。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="在隔离SQLite库中执行时间渐进性数据集验证")
    parser.add_argument("--dataset", type=Path, default=SUITE_DIR / "data")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--report-dir", type=Path, default=SUITE_DIR / "reports")
    args = parser.parse_args()
    temporary = None
    work_dir = args.work_dir
    if work_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="temporal-validation-")
        work_dir = Path(temporary.name)
    work_dir.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = validate(args.dataset.resolve(), work_dir.resolve())
    (args.report_dir / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.report_dir / "latest.md").write_text(report_markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if temporary:
        temporary.cleanup()
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
