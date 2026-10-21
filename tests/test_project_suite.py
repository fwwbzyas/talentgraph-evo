from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agents.data.service import DataAgent
from contracts import ImportRequest
from core.sample_data import generate_demo_jds
from scripts.evaluate_project_suite import (
    JD_FIELDS,
    _record_projection,
    f1_score,
    json_hash,
    load_db_sample,
    run_controlled_jd,
)


def test_controlled_jd_schema_and_dataagent_repeatability():
    first, _, first_batch = run_controlled_jd(4)
    second, _, second_batch = run_controlled_jd(4)

    assert first["sample_count"] == 4
    assert first["label_source"] and first["limitations"]
    assert set(first["field_metrics"]) == set(JD_FIELDS)
    assert first["input_stable_sha256"] == second["input_stable_sha256"]
    assert json_hash([_record_projection(item, JD_FIELDS) for item in first_batch.items]) == json_hash(
        [_record_projection(item, JD_FIELDS) for item in second_batch.items]
    )


def test_lightweight_scoring_contract():
    assert f1_score(["Python", "SQL"], ["Python"]) == 0.666667
    assert f1_score("本科", "本科") == 1.0
    assert f1_score("本科", "硕士") == 0.0


def test_db_sample_is_sorted_and_read_only(tmp_path: Path):
    db_path = tmp_path / "sample.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table job_assets (job_id text primary key, payload text not null)")
        for job_id in ("job_b", "job_a"):
            connection.execute(
                "insert into job_assets values (?, ?)",
                (
                    job_id,
                    json.dumps({
                        "source_id": job_id,
                        "source_type": "jd",
                        "title": "Python 工程师",
                        "content": "负责 Python 服务开发和测试。",
                        "domain": "智能系统",
                        "source_platform": "fixture",
                    }, ensure_ascii=False),
                ),
            )

    sample, meta = load_db_sample(db_path, 2)
    assert [item["source_id"] for item in sample] == ["job_a", "job_b"]
    assert meta["source_table"] == "job_assets"
    assert sqlite3.connect(db_path).execute("select count(*) from job_assets").fetchone()[0] == 2


def test_generated_fixture_hash_ignores_runtime_timestamps():
    first = generate_demo_jds(2)
    second = generate_demo_jds(2)
    assert json_hash(first) == json_hash(second)
