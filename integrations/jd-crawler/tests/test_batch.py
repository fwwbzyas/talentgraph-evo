"""BatchRunner(mock 传输):矩阵遍历、组合容错、风控停站、fresh_pages、双格式输出。"""

import json

import httpx

from jd_crawler.batch import BatchRunner
from jd_crawler.config import MatrixConfig
from jd_crawler.http import HttpClient
from jd_crawler.pipeline import SQLiteWriter
from jd_crawler.ratelimit import RateLimiter


def _factory(handler):
    def make(site, rl, contact):
        return HttpClient(site, RateLimiter(interval=0, jitter=(0, 0)),
                          contact=contact, transport=httpx.MockTransport(handler))
    return make


def _cfg(**kw):
    base = dict(sites=["liepin"], cities=["北京"], keywords=["算法工程师"], pages=1)
    base.update(kw)
    return MatrixConfig(**base)


def test_batch_runner_happy_path(tmp_path, liepin_cards_html):
    def handler(request):
        return httpx.Response(200, text=liepin_cards_html)

    runner = BatchRunner(
        _cfg(), tmp_path, fetch_details=False, robots_ack=True,
        http_factory=_factory(handler), sleep=lambda s: None,
    )
    summary = runner.run()
    assert summary.new_jobs == 3
    assert summary.failed == 0
    assert summary.risk_stopped_sites == []
    combo = summary.combos[0]
    assert (combo.site, combo.city, combo.keyword, combo.status) == \
        ("liepin", "北京", "算法工程师", "ok")
    # 双格式输出:JSONL + 格式化 JSON
    jsonl = list(tmp_path.glob("liepin_matrix_*.jsonl"))
    jarr = list(tmp_path.glob("liepin_matrix_*.json"))
    assert len(jsonl) == 1 and len(jarr) == 1
    arr = json.loads(jarr[0].read_text(encoding="utf-8"))
    assert len(arr) == 3
    assert arr[0]["keyword"] == "算法工程师"
    assert arr[0]["search_city"] == "北京"
    # 运行摘要落盘
    rs = list(tmp_path.glob("run_summary_*.json"))
    assert len(rs) == 1
    # SQLite 含 keyword/search_city 列
    w = SQLiteWriter(tmp_path / "jd_crawler.sqlite3")
    stats = w.stats()
    w.close()
    assert stats["total"] == 3
    assert dict(stats["by_search_city"]) == {"北京": 3}


def test_batch_runner_multi_combo_and_fresh_pages(tmp_path, liepin_cards_html):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, text=liepin_cards_html)

    cfg = _cfg(cities=["北京", "上海"], keywords=["算法工程师", "RAG 工程师"])
    runner = BatchRunner(cfg, tmp_path, robots_ack=True,
                         http_factory=_factory(handler), sleep=lambda s: None)
    s1 = runner.run()
    assert len(s1.combos) == 4
    n_after_first = calls["n"]
    assert n_after_first == 4  # 每组合 1 页

    # fresh_pages:第二轮重新抓页面,但 done_jobs 去重 ⇒ 新增 0
    runner2 = BatchRunner(cfg, tmp_path, robots_ack=True,
                          http_factory=_factory(handler), sleep=lambda s: None)
    s2 = runner2.run()
    assert calls["n"] == 8
    assert s2.new_jobs == 0
    w = SQLiteWriter(tmp_path / "jd_crawler.sqlite3")
    assert w.stats()["total"] == 3  # 同一份 fixture,跨组合去重后仍只有 3 条
    w.close()


def test_batch_runner_failed_combo_isolated(tmp_path, liepin_cards_html):
    def handler(request):
        if "RAG" in str(request.url):
            return httpx.Response(404, text="not found")  # 非 5xx:不重试
        return httpx.Response(200, text=liepin_cards_html)

    cfg = _cfg(keywords=["算法工程师", "RAG 工程师"])
    runner = BatchRunner(cfg, tmp_path, robots_ack=True,
                         http_factory=_factory(handler), sleep=lambda s: None)
    summary = runner.run()
    by_kw = {c.keyword: c for c in summary.combos}
    assert by_kw["RAG 工程师"].status == "failed"
    assert by_kw["算法工程师"].status == "ok"
    assert summary.failed == 1


def test_batch_runner_risk_stops_site(tmp_path, job51_waf_html):
    def handler(request):
        return httpx.Response(200, text=job51_waf_html)  # WAF 挑战页

    cfg = _cfg(sites=["51job"], cities=["北京", "上海"],
               keywords=["算法工程师", "RAG 工程师"])
    runner = BatchRunner(cfg, tmp_path, http_factory=_factory(handler),
                         sleep=lambda s: None)
    summary = runner.run()
    assert summary.risk_stopped_sites == ["51job"]
    # 4 个组合全部标记 risk_stopped(第一个真实请求触发,其余不再发请求)
    assert all(c.status == "risk_stopped" for c in summary.combos)
    assert len(summary.combos) == 4


def test_batch_runner_robots_skip(tmp_path):
    def handler(request):  # pragma: no cover - 不应被调用
        raise AssertionError("robots 未确认时不应发起任何请求")

    cfg = _cfg()  # liepin 搜索 URL 被 robots 禁止
    runner = BatchRunner(cfg, tmp_path, robots_ack=False,
                         http_factory=_factory(handler), sleep=lambda s: None)
    summary = runner.run()
    assert summary.combos[0].status == "skipped_robots"
