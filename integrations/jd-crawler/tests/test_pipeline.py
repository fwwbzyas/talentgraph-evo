import json
import sqlite3

from jd_crawler.models import JobPosting
from jd_crawler.pipeline import Checkpoint, DedupPipeline, JsonlWriter, SQLiteWriter


def make_job(job_id="1", source="51job"):
    return JobPosting(
        source=source, job_id=job_id, title="测试岗位",
        job_url=f"https://example.com/{source}/{job_id}",
    )


def test_dedup_pipeline(tmp_path):
    jl = JsonlWriter(tmp_path / "out.jsonl")
    sq = SQLiteWriter(tmp_path / "t.sqlite3")
    pipe = DedupPipeline(jl, sq)
    assert pipe.process(make_job("1")) is True
    assert pipe.process(make_job("1")) is False  # 内存去重
    assert pipe.process(make_job("2")) is True
    pipe.close()

    lines = (tmp_path / "out.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["title"] == "测试岗位"

    # 跨进程(SQLite 层面)去重
    sq2 = SQLiteWriter(tmp_path / "t.sqlite3")
    assert sq2.write(make_job("1")) is False
    sq2.close()
    conn = sqlite3.connect(tmp_path / "t.sqlite3")
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2
    conn.close()


def test_checkpoint_roundtrip(tmp_path):
    cp = Checkpoint(tmp_path / "checkpoint.json")
    cp.mark_page("51job", "Python", None, 1)
    cp.mark_page("51job", "Python", None, 2)
    cp.mark_job(make_job("99"))
    cp.save()

    cp2 = Checkpoint(tmp_path / "checkpoint.json")
    assert cp2.is_page_done("51job", "Python", None, 1)
    assert cp2.is_page_done("51job", "Python", None, 2)
    assert not cp2.is_page_done("51job", "Python", None, 3)
    assert not cp2.is_page_done("liepin", "Python", None, 1)
    assert cp2.is_job_done(make_job("99"))
