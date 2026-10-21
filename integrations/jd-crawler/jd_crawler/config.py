"""批量抓取矩阵配置:12 城市 × 24 关键词(SPEC §4.12)。

默认矩阵:每平台 12 × 24 = 288 组「城市+关键词」搜索组合。
可用 JSON 配置文件覆盖(见 load_matrix_config),例如:

    {
      "cities": ["北京", "上海"],
      "keyword_groups": {"人工智能": ["算法工程师"]},
      "keywords": ["额外关键词"],
      "sites": ["51job", "liepin"],
      "pages": 2
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# 目标城市(12 个)
CITIES: list[str] = [
    "北京", "上海", "广州", "深圳", "杭州", "南京",
    "苏州", "成都", "武汉", "西安", "合肥", "长沙",
]

# 目标关键词(24 个,按 4 大类分组)
KEYWORD_GROUPS: dict[str, list[str]] = {
    "人工智能": [
        "AI Agent 工程师", "大模型应用工程师", "RAG 工程师", "机器学习工程师",
        "算法工程师", "多模态工程师", "模型评测工程师", "AI 平台工程师",
    ],
    "大数据": [
        "大数据开发工程师", "实时计算工程师", "Flink 工程师", "数据平台工程师",
        "数据治理工程师", "数据仓库工程师", "湖仓架构师",
    ],
    "智能系统": [
        "智能系统工程师", "机器人软件工程师", "边缘智能工程师", "自动驾驶系统工程师",
    ],
    "物联网": [
        "物联网平台工程师", "物联网嵌入式工程师", "IoT 工程师",
        "边缘网关工程师", "固件工程师",
    ],
}

SITES: list[str] = ["51job", "liepin"]


def flatten_keywords(groups: dict[str, list[str]] | None = None) -> list[str]:
    """按组顺序展开关键词,去重保序。"""
    out: list[str] = []
    for kws in (groups or KEYWORD_GROUPS).values():
        for kw in kws:
            if kw not in out:
                out.append(kw)
    return out


def keyword_category(keyword: str, groups: dict[str, list[str]] | None = None) -> str:
    for cat, kws in (groups or KEYWORD_GROUPS).items():
        if keyword in kws:
            return cat
    return ""


@dataclass
class MatrixConfig:
    """一轮批量抓取的完整矩阵描述。"""

    cities: list[str] = field(default_factory=lambda: list(CITIES))
    keywords: list[str] = field(default_factory=flatten_keywords)
    sites: list[str] = field(default_factory=lambda: list(SITES))
    pages: int = 2

    def combos(self) -> Iterator[tuple[str, str, str]]:
        """产出 (site, city, keyword) 组合流。"""
        for site in self.sites:
            for city in self.cities:
                for kw in self.keywords:
                    yield site, city, kw

    def combo_count(self) -> int:
        return len(self.sites) * len(self.cities) * len(self.keywords)


def load_matrix_config(path: str | Path | None = None) -> MatrixConfig:
    """从 JSON 文件加载矩阵配置;path 为 None 时返回默认 12×24 全矩阵。"""
    if path is None:
        return MatrixConfig()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = MatrixConfig()
    if "cities" in data:
        cfg.cities = list(data["cities"])
    if "keyword_groups" in data:
        cfg.keywords = flatten_keywords(data["keyword_groups"])
    if "keywords" in data:  # 追加/独立指定
        for kw in data["keywords"]:
            if kw not in cfg.keywords:
                cfg.keywords.append(kw)
    if "sites" in data:
        sites = list(data["sites"])
        for s in sites:
            if s not in SITES:
                raise ValueError(f"未知站点: {s};可选: {', '.join(SITES)}")
        cfg.sites = sites
    if "pages" in data:
        cfg.pages = int(data["pages"])
    return cfg
