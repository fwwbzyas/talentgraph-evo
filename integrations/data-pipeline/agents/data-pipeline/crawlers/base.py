"""
爬虫基类 — 所有数据源爬虫的抽象基类

对应 多Agent协作开发规范 1.1 Schema 先行原则：
- 输入: CrawlConfig
- 输出: list[RawJobDescription]
"""

from abc import ABC, abstractmethod
from pathlib import Path

from contracts.data_schema import RawJobDescription, CrawlConfig


class BaseCrawler(ABC):
    """爬虫抽象基类 — 所有招聘/社区数据源爬虫必须实现此接口"""

    def __init__(self, config: CrawlConfig):
        self.config = config
        self._session = None

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源标识，对应 Source 枚举"""

    @abstractmethod
    def search(self, keyword: str) -> list[RawJobDescription]:
        """
        按关键词搜索并返回原始 JD 列表。

        Args:
            keyword: 搜索关键词（如 "Python工程师"）

        Returns:
            RawJobDescription 列表
        """

    @abstractmethod
    def get_detail(self, url: str) -> RawJobDescription:
        """
        获取单个 JD 详情页。

        Args:
            url: 详情页 URL

        Returns:
            完整的 RawJobDescription
        """

    def collect(self) -> list[RawJobDescription]:
        """
        按配置批量采集 — 所有子类可共用此编排逻辑。

        采集流程:
          对每个关键词 → 调用 search() → 去重（按 source_url）→ 返回结果
        """
        all_results: list[RawJobDescription] = []
        seen_urls: set[str] = set()

        for keyword in self.config.keywords:
            print(f"\n{'='*60}")
            print(f"  [采集] 关键词: {keyword}")
            print(f"{'='*60}")

            try:
                results = self.search(keyword)
                new_count = 0
                for jd in results:
                    if jd.source_url not in seen_urls:
                        seen_urls.add(jd.source_url)
                        all_results.append(jd)
                        new_count += 1
                print(f"  -> 新增 {new_count} 条（去重后），累计 {len(all_results)} 条")

                if len(all_results) >= self.config.min_results:
                    print(f"  -> 已达到最低采集量 {self.config.min_results}，停止")
                    break

            except Exception as e:
                print(f"  [警告] 关键词 '{keyword}' 采集异常: {e}")
                continue

        return all_results
