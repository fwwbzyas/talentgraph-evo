from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="只读审计 TalentGraph 中可证明为模拟数据的岗位")
    parser.add_argument("--db", default="data/talentgraph.db")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    )]
    source_counts: dict[str, int] = {}
    synthetic = []
    for row in connection.execute("SELECT job_id, payload FROM job_assets ORDER BY job_id"):
        payload = json.loads(row["payload"])
        source_platform = str(payload.get("source_platform") or "")
        source_url = str(payload.get("source_url") or "")
        source_id = str(payload.get("source_id") or row["job_id"])
        source_counts[source_platform] = source_counts.get(source_platform, 0) + 1
        if (
            source_platform == "结构化模拟样本"
            or source_url.startswith("https://demo.talentgraph.local/")
            or source_id.startswith("demo_")
        ):
            synthetic.append({
                "job_id": row["job_id"],
                "source_id": source_id,
                "source_platform": source_platform,
                "title": payload.get("title"),
                "source_url": source_url,
                "active": payload.get("active"),
            })
    print(json.dumps({
        "database": str(db_path),
        "tables": tables,
        "source_counts": dict(sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))),
        "synthetic_count": len(synthetic),
        "synthetic_candidates": synthetic,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
