from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
from typing import Any


def _payloads(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [json.loads(row[0]) for row in connection.execute(f"SELECT payload FROM {table}")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only summary of recruitment collection state.")
    parser.add_argument("--db", type=Path, default=Path("data/talentgraph.db"))
    parser.add_argument("--recent", type=int, default=12)
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.db.resolve()}?mode=ro", uri=True)
    try:
        jobs = _payloads(connection, "job_assets")
        runs = _payloads(connection, "collection_runs")
        settings = {
            key: json.loads(payload)
            for key, payload in connection.execute("SELECT setting_key, payload FROM app_settings")
        }
    finally:
        connection.close()

    recent = sorted(runs, key=lambda item: item.get("started_at", ""), reverse=True)[:max(1, args.recent)]
    output = {
        "database": str(args.db),
        "job_count": len(jobs),
        "jobs_by_source": dict(Counter(item.get("source_platform", "unknown") for item in jobs)),
        "schedule": settings.get("collection_schedule"),
        "strategy": settings.get("collection_strategy"),
        "recent_runs": [
            {
                "run_id": run.get("run_id"),
                "status": run.get("status"),
                "started_at": run.get("started_at"),
                "new_count": run.get("new_count", 0),
                "updated_count": run.get("updated_count", 0),
                "sources": [
                    {
                        "source_id": source.get("source_id"),
                        "status": source.get("status"),
                        "fetched": source.get("fetched", 0),
                        "accepted": source.get("accepted", 0),
                        "scanned": source.get("scanned", 0),
                        "error": source.get("error"),
                    }
                    for source in run.get("source_results", [])
                ],
            }
            for run in recent
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
