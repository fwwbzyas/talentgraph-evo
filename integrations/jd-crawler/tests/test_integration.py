"""端到端(mock 传输):猎聘列表+详情抓取流程、CLI robots 护栏。"""

import json

import httpx

from jd_crawler.cli import main
from jd_crawler.http import HttpClient
from jd_crawler.pipeline import Checkpoint
from jd_crawler.ratelimit import RateLimiter
from jd_crawler.spiders.liepin import LiepinSpider


def test_liepin_spider_end_to_end(tmp_path, liepin_cards_html, liepin_detail_html):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/zhaopin/":
            return httpx.Response(200, text=liepin_cards_html)
        if request.url.path.endswith(".shtml"):
            return httpx.Response(200, text=liepin_detail_html)
        return httpx.Response(404, text="not found")

    http = HttpClient("liepin", RateLimiter(interval=0, jitter=(0, 0)),
                      transport=httpx.MockTransport(handler))
    spider = LiepinSpider(http, fetch_details=True)
    cp = Checkpoint(tmp_path / "checkpoint.json")
    jobs = list(spider.iter_jobs("Python", None, max_pages=1, checkpoint=cp))
    http.close()

    assert len(jobs) == 3
    # 详情页 TDK 已补全(所有卡片指向不同 URL 但 mock 都返回同一详情 fixture)
    assert jobs[0].education == "本科"
    assert jobs[0].salary == "20-40k"  # 列表卡片已有薪资时,详情不回退覆盖
    assert cp.is_page_done("liepin", "Python", None, 0)

    # 断点续爬:同一 checkpoint 再爬一页应被跳过
    http2 = HttpClient("liepin", RateLimiter(interval=0, jitter=(0, 0)),
                       transport=httpx.MockTransport(handler))
    jobs2 = list(LiepinSpider(http2).iter_jobs("Python", None, 1, cp))
    http2.close()
    assert jobs2 == []


def test_cli_blocks_on_robots_without_flag(tmp_path, caplog):
    rc = main(["--site", "liepin", "--keyword", "Python", "--pages", "1",
               "--output", str(tmp_path)])
    assert rc == 2  # robots 禁止且未确认 ⇒ 拒绝执行
    # 不应产生任何输出数据文件
    assert not list(tmp_path.glob("*.jsonl"))


def test_cli_delay_clamped_to_minimum(tmp_path):
    """--delay < 1.0 时被 clamp 到 1.0 并告警(合规限速下限保护)。"""
    rc = main(["--site", "liepin", "--keyword", "Python", "--pages", "1",
               "--output", str(tmp_path), "--delay", "0.1"])
    assert rc == 2  # 仍未加 --i-understand-robots ⇒ robots 拦截
    log_text = (tmp_path / "crawl.log").read_text(encoding="utf-8")
    assert "低于下限 1.0s" in log_text


def test_cli_robots_flag_allows_but_risk_stops(tmp_path, job51_waf_html):
    """51job:robots 无禁止,但真实网络中 WAF ⇒ CLI 捕获 RiskControlError 返回 2。
    这里通过 monkeypatch 让 HttpClient 返回真实抓取的 WAF 页。"""
    from jd_crawler import cli as cli_mod

    def fake_client(site, rl, contact):
        def handler(request):
            return httpx.Response(200, text=job51_waf_html)
        return HttpClient(site, rl, contact=contact,
                          transport=httpx.MockTransport(handler))

    orig = cli_mod.HttpClient
    cli_mod.HttpClient = fake_client
    try:
        rc = main(["--site", "51job", "--keyword", "Python", "--pages", "1",
                   "--output", str(tmp_path), "--httpx"])
    finally:
        cli_mod.HttpClient = orig
    assert rc == 2  # 风控停站
    log_text = (tmp_path / "crawl.log").read_text(encoding="utf-8")
    assert "风控停止" in log_text
    # checkpoint 已保存(无完成页)
    assert json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))["done_pages"] == {}
