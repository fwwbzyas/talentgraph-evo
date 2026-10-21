from jd_crawler import robots


def test_liepin_search_disallowed():
    v = robots.check("https://www.liepin.com/zhaopin/?key=Python&curPage=0")
    assert not v.allowed
    assert "/*?*" in v.rule


def test_liepin_detail_allowed():
    assert robots.check("https://www.liepin.com/job/1978715521.shtml").allowed


def test_liepin_hunter_disallowed():
    assert not robots.check("https://www.liepin.com/hunter/xyz").allowed


def test_job51_no_valid_robots():
    v = robots.check("https://we.51job.com/api/job/search-pc?api_key=51job")
    assert v.allowed and "未提供有效" in v.note
