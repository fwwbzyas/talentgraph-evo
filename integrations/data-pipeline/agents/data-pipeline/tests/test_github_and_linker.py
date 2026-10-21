"""
GitHub 爬虫 & 技能关联模块 单元测试

覆盖:
  - GitHubRepo 模型校验
  - GitHubCrawler._parse_item 数据解析
  - GitHubCrawler._is_rate_limited 限速检测
  - SkillLinker.get_queries 关键词映射
  - SkillLinker.format_repo_summary 格式化输出
"""

import sys
from pathlib import Path

# 确保能找到项目包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.data_schema import GitHubRepo
from crawlers.github import GitHubCrawler
from crawlers.skill_linker import get_queries, format_repo_summary, JOB_TO_GITHUB_QUERIES
from .mocks.github_mock import (
    SEARCH_RESPONSE_NORMAL,
    SEARCH_RESPONSE_EMPTY,
    RATE_LIMIT_HEADERS,
)


# ═══════════════════════════════════════════
# GitHubRepo Schema
# ═══════════════════════════════════════════

class TestGitHubRepoSchema:
    """验证 GitHubRepo 数据模型"""

    def test_valid_repo(self):
        """正常数据能通过 Pydantic 校验"""
        repo = GitHubRepo(
            repo_id=12345,
            full_name="octocat/Hello-World",
            name="Hello-World",
            owner="octocat",
            description="A test repository",
            language="Python",
            topics=["testing", "demo"],
            stargazers_count=100,
            forks_count=20,
            html_url="https://github.com/octocat/Hello-World",
            updated_at="2024-01-01T00:00:00Z",
            matched_keyword="testing",
        )
        assert repo.repo_id == 12345
        assert repo.full_name == "octocat/Hello-World"
        assert repo.language == "Python"

    def test_minimal_repo(self):
        """最少字段 — 只有必填字段也能通过"""
        repo = GitHubRepo(
            repo_id=1,
            full_name="a/b",
            name="b",
            owner="a",
            html_url="https://github.com/a/b",
        )
        assert repo.description is None
        assert repo.language is None
        assert repo.topics == []

    def test_description_none_ok(self):
        """description 为 None 是合法的"""
        repo = GitHubRepo(
            repo_id=1,
            full_name="a/b",
            name="b",
            owner="a",
            description=None,
            html_url="https://github.com/a/b",
        )
        assert repo.description is None


# ═══════════════════════════════════════════
# GitHubCrawler
# ═══════════════════════════════════════════

class TestGitHubCrawler:
    """测试 GitHub 爬虫内部逻辑"""

    def setup_method(self):
        self.crawler = GitHubCrawler(token="")

    def test_parse_item(self):
        """解析 API 响应中的单个仓库为 GitHubRepo"""
        item = SEARCH_RESPONSE_NORMAL["items"][0]
        repo = self.crawler._parse_item(item, "machine-learning")

        assert repo.repo_id == 83222441
        assert repo.full_name == "tensorflow/tensorflow"
        assert repo.language == "C++"
        assert "machine-learning" in repo.topics
        assert repo.stargazers_count == 185000
        assert repo.matched_keyword == "machine-learning"

    def test_is_rate_limited_403(self):
        """HTTP 403 + rate limit body → 识别为限速"""
        resp = _FakeResponse(
            status_code=403,
            body='{"message": "API rate limit exceeded"}',
            headers={},
        )
        assert self.crawler._is_rate_limited(resp) is True

    def test_is_rate_limited_zero_remaining(self):
        """X-RateLimit-Remaining 为 0 → 预防性限速"""
        resp = _FakeResponse(
            status_code=200,
            body="{}",
            headers={"X-RateLimit-Remaining": "0"},
        )
        assert self.crawler._is_rate_limited(resp) is True

    def test_is_not_rate_limited(self):
        """正常请求不应误判为限速"""
        resp = _FakeResponse(
            status_code=200,
            body="{}",
            headers={"X-RateLimit-Remaining": "59"},
        )
        assert self.crawler._is_rate_limited(resp) is False

    def test_rate_limit_wait_retry_after(self):
        """优先使用 Retry-After 头"""
        resp = _FakeResponse(
            status_code=403,
            body="{}",
            headers={"Retry-After": "42"},
        )
        assert self.crawler._rate_limit_wait(resp) == 42

    def test_rate_limit_wait_exponential(self):
        """无 Retry-After 头时使用指数退避"""
        resp = _FakeResponse(status_code=403, body="{}", headers={})
        w0 = self.crawler._rate_limit_wait(resp, retry_count=0)
        w1 = self.crawler._rate_limit_wait(resp, retry_count=1)
        w3 = self.crawler._rate_limit_wait(resp, retry_count=3)

        assert w0 == 60   # 2^0 * 60
        assert w1 == 120  # 2^1 * 60
        assert w3 == 480  # 2^3 * 60


# ═══════════════════════════════════════════
# SkillLinker
# ═══════════════════════════════════════════

class TestGetQueries:
    """测试关键词 → GitHub 查询映射"""

    def test_exact_match(self):
        """精确命中映射表"""
        queries = get_queries("大数据开发工程师")
        assert len(queries) >= 2
        assert any("big-data" in q for q in queries)

    def test_fuzzy_match(self):
        """模糊匹配 — 部分关键词命中"""
        queries = get_queries("高级Java开发工程师")
        assert len(queries) >= 1
        # 应该匹配到 "Java开发工程师" 或 "Java工程师"
        assert any("spring-boot" in q for q in queries)

    def test_no_match_fallback(self):
        """没有匹配时返回原始关键词"""
        queries = get_queries("未知奇怪的岗位名XYZ")
        assert len(queries) == 1
        assert "未知奇怪的岗位名XYZ" in queries[0]

    def test_all_keys_have_queries(self):
        """确保映射表中所有关键词都有对应的查询"""
        for key, queries in JOB_TO_GITHUB_QUERIES.items():
            assert len(queries) >= 1, f"{key} 没有配置查询词"
            assert all(isinstance(q, str) and len(q) > 0 for q in queries)


class TestFormatRepoSummary:
    """测试仓库摘要格式化"""

    def test_empty(self):
        assert "未找到" in format_repo_summary([])

    def test_normal_output(self):
        """正常仓库列表应包含关键信息"""
        repos = [
            GitHubRepo(
                repo_id=1,
                full_name="spark/apache-spark",
                name="spark",
                owner="apache",
                description="Apache Spark - A unified analytics engine",
                language="Scala",
                topics=["big-data"],
                stargazers_count=39000,
                forks_count=28000,
                html_url="https://github.com/apache/spark",
                matched_keyword="big-data",
            ),
        ]
        text = format_repo_summary(repos)
        assert "spark/apache-spark" in text
        assert "39000" in text
        assert "Scala" in text

    def test_long_description_truncated(self):
        """超长描述应截断到 80 字符"""
        repos = [
            GitHubRepo(
                repo_id=1,
                full_name="a/b",
                name="b",
                owner="a",
                description="A" * 100,
                html_url="https://github.com/a/b",
            ),
        ]
        text = format_repo_summary(repos)
        # 找出截断后的描述（带 ... 结尾）
        assert "..." in text


# ═══════════════════════════════════════════
# 测试辅助
# ═══════════════════════════════════════════

class _FakeResponse:
    """模拟 requests.Response，只包含爬虫用到的属性"""
    def __init__(self, status_code, body, headers):
        self.status_code = status_code
        self._body = body
        self.headers = headers

    def json(self):
        import json
        return json.loads(self._body)

    @property
    def text(self):
        return self._body
