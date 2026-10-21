from __future__ import annotations

from agents.data.boss_browser import BossBrowserSource
from agents.data.boss_parser import is_challenge_page, parse_job_detail, parse_search_cards


SEARCH_HTML = """
<html><body><ul>
  <li class="job-card-wrapper job-card-box">
    <a class="job-card-left job-name" href="/job_detail/abc123.html">AI Agent 工程师</a>
    <span class="job-salary">30-60K·14薪</span>
    <span class="job-area">北京·海淀区</span>
    <div class="company-name"><a>示例科技</a></div>
    <ul class="tag-list"><li>3-5年</li><li>本科</li></ul>
  </li>
</ul></body></html>
"""

DETAIL_HTML = """
<html><head><script type="application/ld+json">
{"@type":"JobPosting","datePosted":"2026-08-08"}
</script></head><body>
  <div class="job-banner"><div class="name"><h1>AI Agent 工程师</h1></div><span class="salary">30-60K·14薪</span>
    <ul class="tag-list"><li>3-5年</li><li>本科</li></ul>
  </div>
  <div class="job-detail-section"><div class="job-sec-text">负责Python、RAG和大模型智能体平台研发，完成系统设计、开发、测试、部署和性能优化。</div></div>
  <div class="location-address">北京·海淀区</div>
  <div class="job-tags"><span>五险一金</span><span>双休</span></div>
  <div class="sider-company"><div class="company-info"><a>互联网</a><a>C轮</a><a>100-499人</a></div></div>
</body></html>
"""


def test_demo_parser_extracts_search_and_detail_contract():
    hits = parse_search_cards(SEARCH_HTML)
    assert len(hits) == 1
    job = parse_job_detail(
        DETAIL_HTML,
        hits[0].source_url,
        hits[0],
        search_city="北京",
        search_city_code="101010100",
        search_keyword="AI Agent 工程师",
        keyword_category="人工智能",
    )
    raw = job.to_raw_item(search_page=1, known=False)
    assert raw["source_id"] == "abc123"
    assert raw["salary_min_k"] == 30 and raw["salary_max_k"] == 60
    assert raw["salary_months"] == 14
    assert raw["experience_min_years"] == 3 and raw["experience_max_years"] == 5
    assert raw["metadata"]["crawler_engine"] == "boss-job-crawler-playwright"
    assert "RAG" in raw["content"]


def test_demo_parser_distinguishes_login_copy_from_public_jobs():
    assert is_challenge_page("<html><body>请先登录</body></html>")
    assert not is_challenge_page(SEARCH_HTML.replace("<body>", "<body><div>登录后查看完整信息</div>"))


def test_source_configuration_keeps_main_project_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("TALENTGRAPH_BOSS_STATE_PATH", str(tmp_path / "boss-state.json"))
    source = BossBrowserSource()
    source.configure(
        cities=["北京", "上海"],
        queries=["AI Agent 工程师"],
        items_per_run=20,
        mode="discovery",
        discovery_ratio=1,
        revisit_after_hours=12,
    )
    assert source.cities == {"北京": "101010100", "上海": "101020100"}
    assert source.queries == ("AI Agent 工程师",)
    assert source.max_per_run == 20
    source.reset_cursor("AI Agent 工程师", "北京")
    state = source._load_state()
    assert state["page_cursors"]["101010100|AI Agent 工程师"] == 1


def test_source_fetch_runs_search_and_detail_through_playwright(monkeypatch, tmp_path):
    class Response:
        status = 200

    class Page:
        def __init__(self, url="about:blank"):
            self.url = url
            self.html = SEARCH_HTML if "zhipin.com" in url else "<html></html>"
            self.closed = False

        def goto(self, url, **kwargs):
            self.url = url
            self.html = DETAIL_HTML if "job_detail" in url else SEARCH_HTML
            return Response()

        def content(self):
            return self.html

        def close(self):
            self.closed = True

    class Context:
        def __init__(self):
            self.pages = [Page("https://www.zhipin.com/web/geek/jobs")]

        def new_page(self):
            page = Page()
            self.pages.append(page)
            return page

    class Browser:
        def __init__(self):
            self.contexts = [Context()]

    class Chromium:
        def __init__(self):
            self.browser = Browser()

        def connect_over_cdp(self, *args, **kwargs):
            return self.browser

    class Playwright:
        def __init__(self):
            self.chromium = Chromium()

    class Manager:
        def __init__(self):
            self.playwright = Playwright()

        def __enter__(self):
            return self.playwright

        def __exit__(self, *args):
            return False

    monkeypatch.setenv("TALENTGRAPH_BOSS_STATE_PATH", str(tmp_path / "boss-state.json"))
    monkeypatch.setattr("agents.data.boss_browser.sync_playwright", Manager)
    monkeypatch.setattr("agents.data.boss_browser._random_sleep", lambda bounds: None)
    source = BossBrowserSource()
    source.request_delay_seconds = 0
    source.detail_delay_range = (0, 0)
    source.configure(
        cities=["北京"],
        queries=["AI Agent 工程师"],
        items_per_run=1,
        mode="discovery",
        discovery_ratio=1,
        revisit_after_hours=12,
    )

    items = source.fetch(max_items=1, lookback_hours=24)

    assert len(items) == 1
    assert items[0]["source_id"] == "abc123"
    assert items[0]["metadata"]["search_city"] == "北京"
    assert source.last_fetch_stats["scanned"] == 1
    assert source.last_fetch_stats["details_visited"] == 1
