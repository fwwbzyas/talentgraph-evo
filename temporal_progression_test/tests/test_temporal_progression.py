from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


SUITE_DIR = Path(__file__).resolve().parents[1]


def test_100_real_jd_baseline_progresses_through_12_month_pipeline(tmp_path):
    report_dir = tmp_path / "reports"
    environment = {
        **os.environ,
        "TALENTGRAPH_DB_PATH": str(tmp_path / "global-import-guard.db"),
        "TALENTGRAPH_LLM_DISABLED": "1",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(SUITE_DIR / "run_validation.py"),
            "--dataset", str(SUITE_DIR / "data"),
            "--work-dir", str(tmp_path / "work"),
            "--report-dir", str(report_dir),
        ],
        cwd=SUITE_DIR.parent,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    report = json.loads((report_dir / "latest.json").read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["baseline_count"] == 100
    assert report["observation_count"] == 1200
    assert report["production_database_modified"] is False
