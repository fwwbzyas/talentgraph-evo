"""51job:sign 算法、URL 构造、搜索响应解析(fixture 为按公开结构重建)。"""

from jd_crawler.spiders.job51 import (
    CITY_CODES,
    CUPID_SIGN_KEY,
    MAX_PAGE_SIZE,
    build_search_url,
    compute_sign,
    parse_search,
)


def test_compute_sign_known_answer():
    """已知答案测试:期望值由独立 HmacSHA256 计算(与前端 CryptoJS 行为一致)。"""
    url = (
        "/api/job/search-pc?api_key=51job&timestamp=1700000000&keyword=Python"
        "&searchType=2&function=&industry=&jobArea=000000&jobArea2=&landmark="
        "&metro=&salary=&workYear=&degree=&companyType=&companySize=&jobType="
        "&issueDate=&sortType=0&pageNum=1&requestId=&pageSize=20&source=1"
        "&accountId=&pageCode=sou%7Csou%7Csoulb"
    )
    assert compute_sign(url) == (
        "38c25d37c9fda77b493c4afa95f95b38103a4439bdd7298b3b7525b5df544fc6"
    )


def test_build_search_url():
    url = build_search_url("Python", CITY_CODES["全国"], 1, timestamp=1700000000)
    assert url.startswith("/api/job/search-pc?api_key=51job&timestamp=1700000000&")
    assert "keyword=Python" in url
    assert "jobArea=000000" in url
    assert "pageNum=1" in url
    assert "pageSize=20" in url
    # pageCode 中 | 被 urlencode,与前端 qs.stringify 一致
    assert "pageCode=sou%7Csou%7Csoulb" in url


def test_parse_search(job51_search_payload):
    jobs, total = parse_search(job51_search_payload)
    assert total == 1234
    assert len(jobs) == 2
    j = jobs[0]
    assert j.source == "51job"
    assert j.job_id == "156789012"
    assert j.dedup_key == "51job:156789012"
    assert j.title == "Python开发工程师"
    assert j.salary == "1.5-2.5万/月"
    assert j.city == "上海-浦东新区"
    assert j.company_name == "示例科技（上海）有限公司"
    assert j.experience == "3-5年"
    assert j.education == "本科"
    assert j.publish_date == "2026-08-10 10:00:00"
    assert j.job_url == "https://jobs.51job.com/shanghai/156789012.html"
    assert "互联网/电子商务" in j.company_tags
    assert j.description == ""  # 详情受 WAF 保护,默认不采正文


def test_parse_search_empty():
    jobs, total = parse_search({"status": "1", "resultbody": {}})
    assert jobs == [] and total == 0
