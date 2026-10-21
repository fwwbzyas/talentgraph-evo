"""
GitHub 仓库信息采集 — 调用 GitHub REST API 搜索指定领域的开源项目

用作"职位关联技能推荐模块"的数据源：
  搜索某个岗位关键词后，自动推荐相关的 GitHub 开源仓库，
  帮助求职者找到可学习的实际项目代码。

与招聘爬虫模块（zhaopin.py）完全独立，无互相依赖。

API 说明:
  GitHub Search API 无需认证即可调用，但未认证限速 60 次/小时。
  设置 GITHUB_TOKEN 环境变量可提升至 5000 次/小时。
  搜索端点: GET https://api.github.com/search/repositories

用法:
    crawler = GitHubCrawler()
    repos = crawler.search("big-data spark", per_page=10)
    for r in repos:
        print(r.full_name, r.stargazers_count)
"""

import os
import time
from datetime import datetime
from typing import Optional

import requests

from contracts.data_schema import GitHubRepo


class GitHubCrawler:
    """GitHub 仓库搜索与信息采集。

    通过 GitHub REST API 的 /search/repositories 端点搜索仓库，
    返回结构化的 GitHubRepo 数据。
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        # token 优先从参数读取，其次读环境变量 GITHUB_TOKEN
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": "job-skill-graph/1.0",
        })
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"

    # ── 公开方法 ──────────────────────────────

    def search(self, keyword: str, per_page: int = 10, max_results: int = 20) -> list[GitHubRepo]:
        """按关键词搜索仓库，返回 GitHubRepo 列表。

        Args:
            keyword: 搜索关键词，GitHub 搜索语法支持 + 组合，例如 "spark+big-data"
            per_page: 每页数量（最大 100）
            max_results: 总共最多返回条数（超过会自动翻页）
        """
        results: list[GitHubRepo] = []
        page = 1
        retries = 0  # 连续限速重试次数，用于指数退避

        while len(results) < max_results:
            url = f"{self.BASE_URL}/search/repositories"
            params = {
                "q": keyword,
                "sort": "stars",
                "order": "desc",
                "per_page": min(per_page, 100),
                "page": page,
            }

            resp = self._session.get(url, params=params, timeout=30)

            # 限速处理（403 + rate limit message 或 x-ratelimit-remaining 为 0）
            if self._is_rate_limited(resp):
                wait = self._rate_limit_wait(resp, retries)
                print(f"  [限速] 等待 {wait}s ...")
                time.sleep(wait)
                retries += 1
                continue

            retries = 0  # 成功请求后重置退避计数

            if resp.status_code == 422:
                # 搜索语法错误或结果超限（GitHub 只返回前 1000 条）
                break

            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])

            if not items:
                break

            for item in items:
                results.append(self._parse_item(item, keyword))

            # GitHub total_count 可能很大，但只允许翻到第 1000 条
            if len(items) < per_page or len(results) >= int(data.get("total_count", 0)):
                break

            page += 1

        return results[:max_results]

    def search_by_topic(self, topic: str, per_page: int = 10) -> list[GitHubRepo]:
        """按 GitHub topic 标签搜索——比关键词搜索更精准。

        例如 topic="machine-learning" 只匹配明确标了该主题的仓库。
        """
        return self.search(f"topic:{topic}", per_page=per_page, max_results=per_page)

    # ── 响应解析 ──────────────────────────────

    def _parse_item(self, item: dict, keyword: str) -> GitHubRepo:
        """把 API 返回的单个仓库 dict 转成 GitHubRepo"""
        return GitHubRepo(
            repo_id=item["id"],
            full_name=item["full_name"],
            name=item["name"],
            owner=item["owner"]["login"],
            description=item.get("description"),
            language=item.get("language"),
            topics=item.get("topics", []),
            stargazers_count=item["stargazers_count"],
            forks_count=item["forks_count"],
            html_url=item["html_url"],
            updated_at=item.get("updated_at"),
            matched_keyword=keyword,
        )

    # ── 限速处理 ──────────────────────────────

    def _is_rate_limited(self, resp) -> bool:
        """检查是否触发了速率限制。

        两种情况会触发：
        1. 返回 403 且 body 中提到 rate limit
        2. x-ratelimit-remaining 头为 0（预防性检测）
        """
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            return True
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            return True
        return False

    def _rate_limit_wait(self, resp, retry_count: int = 0) -> int:
        """根据 GitHub 最佳实践计算限速等待时间。

        优先级:
        1. retry-after 头 — GitHub 明确告知的等待秒数
        2. x-ratelimit-reset 头 — 配额重置的 Unix 时间戳
        3. 指数退避 — 连续重试时逐步增加等待时间（避免触发次级速率限制）
        """
        # 优先使用 retry-after 头
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            return int(retry_after)

        # 其次用 x-ratelimit-reset 计算
        reset_at = resp.headers.get("X-RateLimit-Reset")
        if reset_at:
            return max(1, int(reset_at) - int(time.time()) + 1)

        # 兜底: 指数退避 (1min → 2min → 4min → ...，最多 10min)
        return min(60 * (2 ** retry_count), 600)
