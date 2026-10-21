"""猎聘:真实 fixture 的卡片与详情页解析。"""

from jd_crawler.models import JobPosting
from jd_crawler.spiders.liepin import (
    LiepinSpider,
    normalize_job_url,
    parse_detail,
    parse_search_cards,
)


def test_normalize_job_url_strips_tracking():
    url, job_id = normalize_job_url(
        "https://www.liepin.com/job/1974521297.shtml?d_sfrom=recom_jd&pgRef=abc"
    )
    assert url == "https://www.liepin.com/job/1974521297.shtml"
    assert job_id == "1974521297"


def test_parse_search_cards(liepin_cards_html):
    jobs = parse_search_cards(liepin_cards_html)
    assert len(jobs) == 3
    j = jobs[0]
    assert j.source == "liepin"
    assert j.job_id == "1974521297"  # 取 URL 中的规范 ID
    assert j.title == "格力新能源-节能技术经理/总监"
    assert j.city == "杭州-钱塘区"
    assert j.salary == "20-40k"
    assert j.company_name == "格力新能源"
    assert "电力/热力/燃气/水务" in j.company_tags
    assert "?" not in j.job_url  # 跟踪参数已剥离(亦规避 robots /*?*)
    # 所有卡片均应有规范 ID 与链接
    for job in jobs:
        assert job.job_url.startswith("https://www.liepin.com/job/")
        assert job.job_id.isdigit()


def test_parse_detail_from_tdk(liepin_detail_html):
    """详情 fixture 为真实页面(大华技术 ESG 岗),主体 CSR ⇒ 走 TDK 回退。"""
    job = JobPosting(
        source="liepin",
        job_id="1978715521",
        title="",
        job_url="https://www.liepin.com/job/1978715521.shtml",
    )
    job = parse_detail(liepin_detail_html, job)
    assert job.title == "ESG运营经理/专家"
    assert job.city == "杭州"
    assert job.company_name == "大华技术"
    assert job.salary == "10-20k"
    assert job.education == "本科"
    assert job.experience == "3-10年"


def test_search_url():
    spider = LiepinSpider.__new__(LiepinSpider)  # 仅测纯函数,不触发网络
    url = LiepinSpider.search_url(spider, "Python", "杭州", 0)
    assert url.startswith("https://www.liepin.com/zhaopin/?key=Python&curPage=0")
    assert "city=070020" in url
    url2 = LiepinSpider.search_url(spider, "数据分析", None, 3)
    assert "curPage=3" in url2 and "city=" not in url2


def test_parse_search_cards_empty_for_csr_shell():
    """游客 CSR 空壳页:无卡片时返回空列表而非报错。"""
    html = "<html><head><title>【招聘信息_人才网招聘信息】-猎聘</title></head><body></body></html>"
    assert parse_search_cards(html) == []
