"""清洗层:内置清洗器、管道批处理、格式化输出到 cleaned 目录。"""

import json

from jd_crawler.cleaning import (
    CrossSourceDedupCleaner, SalaryNormCleaner, WhitespaceCleaner,
    run_cleaning,
)


def _rec(**kw):
    base = {
        "dedup_key": "51job:1", "source": "51job", "job_id": "1",
        "title": "算法工程师", "salary": "2.5-4万/月", "city": "北京",
        "company_name": "某某科技有限公司", "keyword": "算法工程师",
        "search_city": "北京",
    }
    base.update(kw)
    return base


def test_whitespace_cleaner():
    rec = WhitespaceCleaner().clean(_rec(title="  算法\n  工程师  "))
    assert rec["title"] == "算法 工程师"


def test_salary_norm_cleaner():
    assert SalaryNormCleaner().clean(_rec())["salary_norm"] == "25-40k/月"
    assert SalaryNormCleaner().clean(_rec(salary="20-30k·14薪"))["salary_norm"] == "20-30k/月"
    assert SalaryNormCleaner().clean(_rec(salary="100-150万/年"))["salary_norm"].endswith("/月")
    assert SalaryNormCleaner().clean(_rec(salary="面议"))["salary_norm"] == ""


def test_cross_source_dedup_marks_not_deletes():
    c = CrossSourceDedupCleaner()
    a = c.clean(_rec(dedup_key="51job:1"))
    assert "dup_of" not in a
    # 同标题/公司(带后缀)/同城市 → 打标不删除
    b = c.clean(_rec(dedup_key="liepin:9", source="liepin",
                     company_name="某某科技"))
    assert b["dup_of"] == "51job:1"
    # 不同城市 → 新记录
    d = c.clean(_rec(dedup_key="liepin:10", source="liepin", search_city="上海"))
    assert "dup_of" not in d


def test_run_cleaning_end_to_end(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "51job_a.jsonl").write_text(
        "\n".join(json.dumps(_rec(job_id=str(i), dedup_key=f"51job:{i}",
                                  title=f"算法工程师 {i}"))
                  for i in range(3)),
        encoding="utf-8",
    )
    cleaned = tmp_path / "cleaned"
    report = run_cleaning(raw, cleaned)
    assert report["51job_a.jsonl"]["in"] == 3
    assert report["51job_a.jsonl"]["out"] == 3
    out = json.loads((cleaned / "51job_a.cleaned.json").read_text(encoding="utf-8"))
    assert len(out) == 3
    assert out[0]["salary_norm"] == "25-40k/月"
    assert (cleaned / "clean_report.json").exists()


def test_run_cleaning_empty_dir(tmp_path):
    assert run_cleaning(tmp_path / "raw", tmp_path / "cleaned") == {}
