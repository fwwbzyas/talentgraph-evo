from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sqlite3


SYNTHETIC_ID = re.compile(r"^jd_\d{3}$")
SYNTHETIC_URL_PREFIX = "https://demo.talentgraph.local/synthetic/"
SYNTHETIC_PLATFORM = "结构化模拟样本"


def _synthetic_jobs(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    for job_id, raw_payload in connection.execute("SELECT job_id, payload FROM job_assets"):
        payload = json.loads(raw_payload)
        source_id = str(payload.get("source_id") or job_id)
        markers = (
            bool(SYNTHETIC_ID.fullmatch(source_id)),
            str(payload.get("source_url") or "").startswith(SYNTHETIC_URL_PREFIX),
            str(payload.get("source_platform") or "") == SYNTHETIC_PLATFORM,
        )
        # Require multiple independent markers so a real job can never match by accident.
        if sum(markers) >= 2:
            matches.append((str(job_id), source_id))
    return sorted(matches)


def _payload_references_synthetic(raw_payload: str, source_ids: set[str]) -> bool:
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError):
        return False
    serialized = json.dumps(payload, ensure_ascii=False)
    return (
        SYNTHETIC_URL_PREFIX in serialized
        and any(source_id in serialized for source_id in source_ids)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="精确清除 TalentGraph 的结构化模拟岗位；默认仅预览")
    parser.add_argument("--db", default="data/talentgraph.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    connection = sqlite3.connect(db_path)
    matches = _synthetic_jobs(connection)
    job_ids = {item[0] for item in matches}
    source_ids = {item[1] for item in matches}
    before_total = connection.execute("SELECT COUNT(*) FROM job_assets").fetchone()[0]
    related: dict[str, list[str]] = {
        "job_versions": [row[0] for row in connection.execute(
            "SELECT version_id FROM job_versions WHERE job_id IN (%s)" % ",".join("?" * len(job_ids)),
            tuple(job_ids),
        )] if job_ids else [],
        "job_observations": [row[0] for row in connection.execute(
            "SELECT observation_id FROM job_observations WHERE job_id IN (%s)" % ",".join("?" * len(job_ids)),
            tuple(job_ids),
        )] if job_ids else [],
    }
    for table, id_column in (("data_audits", "audit_id"), ("quality_rejections", "rejection_id")):
        related[table] = [
            row_id for row_id, payload in connection.execute(f"SELECT {id_column}, payload FROM {table}")
            if _payload_references_synthetic(payload, source_ids)
        ]

    report = {
        "database": str(db_path),
        "mode": "apply" if args.apply else "dry-run",
        "before_job_count": before_total,
        "synthetic_job_count": len(matches),
        "synthetic_job_ids": sorted(job_ids),
        "related_counts": {table: len(ids) for table, ids in related.items()},
    }
    if not args.apply:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        connection.close()
        return
    if len(matches) != 100:
        connection.close()
        raise SystemExit(f"安全中止：预期精确匹配 100 条模拟岗位，实际匹配 {len(matches)} 条")

    backup_path = db_path.with_name(f"{db_path.stem}.before-synthetic-purge-{datetime.now():%Y%m%d-%H%M%S}{db_path.suffix}")
    connection.execute("PRAGMA wal_checkpoint(FULL)")
    connection.close()
    shutil.copy2(db_path, backup_path)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for table, id_column in (
            ("job_versions", "version_id"),
            ("job_observations", "observation_id"),
            ("data_audits", "audit_id"),
            ("quality_rejections", "rejection_id"),
        ):
            ids = related[table]
            if ids:
                connection.executemany(f"DELETE FROM {table} WHERE {id_column} = ?", [(item,) for item in ids])
        connection.executemany("DELETE FROM job_assets WHERE job_id = ?", [(item,) for item in job_ids])
        remaining_synthetic = len(_synthetic_jobs(connection))
        after_total = connection.execute("SELECT COUNT(*) FROM job_assets").fetchone()[0]
        if remaining_synthetic or before_total - after_total != 100:
            raise RuntimeError("删除后安全校验失败，事务已回滚")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    report.update({
        "backup": str(backup_path),
        "after_job_count": after_total,
        "removed_job_count": before_total - after_total,
        "remaining_synthetic_count": remaining_synthetic,
    })
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
