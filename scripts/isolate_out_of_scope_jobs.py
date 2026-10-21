from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3


DEFAULT_CITIES = ("北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "武汉", "西安", "合肥", "长沙")


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive and isolate job assets outside selected cities.")
    parser.add_argument("--database", type=Path, default=Path("data/talentgraph.db"))
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--cities", nargs="+", default=list(DEFAULT_CITIES))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    selected = set(args.cities)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = args.archive_root / f"out_of_scope_jobs_{stamp}"
    archive.mkdir(parents=True, exist_ok=False)

    connection = sqlite3.connect(args.database)
    rows = connection.execute("SELECT job_id, payload, updated_at FROM job_assets").fetchall()
    isolated = []
    retained = []
    for job_id, payload, updated_at in rows:
        value = json.loads(payload)
        record = {"job_id": job_id, "updated_at": updated_at, "payload": value}
        (retained if value.get("city") in selected else isolated).append(record)

    jsonl_path = archive / "jobs.jsonl"
    digest = hashlib.sha256()
    with jsonl_path.open("wb") as stream:
        for record in isolated:
            line = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            stream.write(line)
            digest.update(line)

    backup_path = archive / "talentgraph_before_isolation.db"
    backup = sqlite3.connect(backup_path)
    connection.backup(backup)
    backup.close()

    manifest = {
        "created_at": datetime.now().isoformat(),
        "source_database": str(args.database.resolve()),
        "selected_cities": sorted(selected),
        "total_before": len(rows),
        "retained_count": len(retained),
        "isolated_count": len(isolated),
        "isolated_sha256": digest.hexdigest(),
        "isolated_by_source": dict(Counter(item["payload"].get("source_platform") or "unknown" for item in isolated)),
        "isolated_by_city": dict(Counter(item["payload"].get("city") or "(empty)" for item in isolated)),
        "dry_run": args.dry_run,
    }
    (archive / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.dry_run and isolated:
        with connection:
            connection.executemany("DELETE FROM job_assets WHERE job_id = ?", [(item["job_id"],) for item in isolated])
    connection.close()
    print(json.dumps({**manifest, "archive": str(archive.resolve())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
