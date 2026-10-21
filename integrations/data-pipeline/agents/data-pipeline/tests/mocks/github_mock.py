"""
GitHub 爬虫 mock 数据（模拟 GitHub Search API 响应）

提供 3 组数据：
  - normal: 正常搜索 "machine-learning" 的返回
  - boundary: 空结果
  - abnormal: 限速错误响应
"""

# ── 正常数据 — "machine-learning" 搜索结果中的 3 个仓库 ──

SEARCH_RESPONSE_NORMAL = {
    "total_count": 3,
    "incomplete_results": False,
    "items": [
        {
            "id": 83222441,
            "full_name": "tensorflow/tensorflow",
            "name": "tensorflow",
            "owner": {"login": "tensorflow"},
            "description": "An Open Source Machine Learning Framework for Everyone",
            "language": "C++",
            "topics": ["machine-learning", "deep-learning", "tensorflow"],
            "stargazers_count": 185000,
            "forks_count": 74000,
            "html_url": "https://github.com/tensorflow/tensorflow",
            "updated_at": "2024-01-15T10:30:00Z",
        },
        {
            "id": 65600975,
            "full_name": "pytorch/pytorch",
            "name": "pytorch",
            "owner": {"login": "pytorch"},
            "description": "Tensors and Dynamic neural networks in Python",
            "language": "Python",
            "topics": ["deep-learning", "machine-learning", "gpu"],
            "stargazers_count": 78000,
            "forks_count": 21000,
            "html_url": "https://github.com/pytorch/pytorch",
            "updated_at": "2024-01-14T08:00:00Z",
        },
        {
            "id": 19141425,
            "full_name": "scikit-learn/scikit-learn",
            "name": "scikit-learn",
            "owner": {"login": "scikit-learn"},
            "description": "Machine learning in Python",
            "language": "Python",
            "topics": ["machine-learning", "data-science", "python"],
            "stargazers_count": 59000,
            "forks_count": 25000,
            "html_url": "https://github.com/scikit-learn/scikit-learn",
            "updated_at": "2024-01-13T12:00:00Z",
        },
    ],
}

# ── 边界数据 — 空搜索结果 ──

SEARCH_RESPONSE_EMPTY = {
    "total_count": 0,
    "incomplete_results": False,
    "items": [],
}

# ── 异常数据 — 限速错误 ──

SEARCH_RESPONSE_RATE_LIMITED = {
    "message": "API rate limit exceeded for user 1.2.3.4. "
               "(But here's the good news: Authenticated requests get a higher rate limit. "
               "Check out the documentation for more details.)",
    "documentation_url": "https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting",
}

# ── HTTP 响应头（限速场景） ──

RATE_LIMIT_HEADERS = {
    "X-RateLimit-Limit": "60",
    "X-RateLimit-Remaining": "0",
    "X-RateLimit-Reset": str(1700000000),  # 未来时间戳
    "Retry-After": "30",
}
