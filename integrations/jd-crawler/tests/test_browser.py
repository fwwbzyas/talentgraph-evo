"""Playwright 备用模式的解析胶水层(假 page/session,不需要真实浏览器)。"""

import json

from jd_crawler.spiders.browser import (
    BrowserSpider, fetch_51job_search, fetch_liepin_search, profile_dir,
)
from jd_crawler.pipeline import Checkpoint


def test_profile_dir_login_separation():
    assert profile_dir("/tmp/x", login=False).endswith("browser_profile")
    assert profile_dir("/tmp/x", login=True).endswith("browser_profile_login")
    assert profile_dir("/tmp/x").endswith("browser_profile")  # 默认游客态


class _FakeResponse:
    def __init__(self, url, payload):
        self.url = url
        self._payload = payload

    def json(self):
        return self._payload


class _FakePage:
    def __init__(self, *, payload=None, html=""):
        self._payload = payload
        self._html = html
        self._handlers = []
        self.url = "https://example.com/search"

    def on(self, event, handler):
        self._handlers.append(handler)

    def goto(self, url, **kw):
        if self._payload is not None:
            for h in self._handlers:
                h(_FakeResponse(
                    "https://we.51job.com/api/job/search-pc?api_key=51job",
                    self._payload,
                ))

    def wait_for_timeout(self, ms):
        pass

    def expect_response(self, predicate, **kw):
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            class _Info:
                value = None
            info = _Info()
            yield info
            if self._payload is not None:
                info.value = _FakeResponse(
                    "https://we.51job.com/api/job/search-pc?api_key=51job",
                    self._payload,
                )

        return _ctx()

    def wait_for_selector(self, sel, **kw):
        pass

    def title(self):
        return "正常页面"

    def content(self):
        return self._html

    def close(self):
        pass


class _FakeSession:
    def __init__(self, page):
        self._page = page
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            yield self._page

        self._ctx = _ctx

    def page(self):
        return self._ctx()

    def goto(self, page, url):
        page.goto(url)


def test_fetch_51job_search_captures_api_payload(job51_search_payload):
    session = _FakeSession(_FakePage(payload=job51_search_payload))
    jobs, total = fetch_51job_search(session, "算法工程师", "北京", 1)
    assert len(jobs) > 0
    assert total >= len(jobs)


def test_fetch_51job_search_no_payload_returns_empty():
    session = _FakeSession(_FakePage(payload=None))
    jobs, total = fetch_51job_search(session, "算法工程师", "北京", 1)
    assert jobs == [] and total == 0


def test_fetch_liepin_search_parses_rendered_dom(liepin_cards_html):
    session = _FakeSession(_FakePage(html=liepin_cards_html))
    jobs = fetch_liepin_search(session, "算法工程师", "北京", 0)
    assert len(jobs) == 3


def test_browser_spider_iter_jobs_and_checkpoint(tmp_path, liepin_cards_html):
    session = _FakeSession(_FakePage(html=liepin_cards_html))
    cp = Checkpoint(tmp_path / "checkpoint.json")
    spider = BrowserSpider(session, "liepin")
    jobs = list(spider.iter_jobs("算法工程师", "北京", 1, cp))
    assert len(jobs) == 3
    assert jobs[0].keyword == "算法工程师"
    assert jobs[0].search_city == "北京"
    assert cp.is_page_done("liepin", "算法工程师", "北京", 0)
