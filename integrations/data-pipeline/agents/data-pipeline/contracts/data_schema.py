"""
数据采集与清洗流水线 — Schema 定义（Schema-First 原则）

本文件定义数据管线的全部输入/输出 Schema。
所有上下游模块通过此 Schema 对接，修改必须走 PR review。
版本: v1.0.0
"""

from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════

class Source(str, Enum):
    """数据来源枚举"""
    BOSS = "boss"
    ZHAOPIN = "zhaopin"
    LAGOU = "lagou"
    LIEPIN = "liepin"
    BILIBILI = "bilibili"
    ZHIHU = "zhihu"
    GITHUB = "github"
    ARXIV = "arxiv"


class QualityLevel(str, Enum):
    """质量等级"""
    HIGH = "high"        # ≥80 分
    MEDIUM = "medium"    # 50-79 分
    LOW = "low"          # <50 分
    REJECTED = "rejected"


# ═══════════════════════════════════════════
# 技能项
# ═══════════════════════════════════════════

class SkillItem(BaseModel):
    """单个技能项"""
    name: str = Field(..., description="技能名称，如 'Python'、'Spring Boot'")
    level: Optional[str] = Field(None, description="熟练度: beginner/intermediate/advanced/expert")
    category: Optional[str] = Field(None, description="技能分类: 编程语言/框架/工具/软技能")
    evidence: list[str] = Field(default_factory=list, description="该技能在JD中的原始文本证据")


# ═══════════════════════════════════════════
# 原始数据
# ═══════════════════════════════════════════

class RawJobDescription(BaseModel):
    """
    原始 JD 数据结构 — 爬虫产出

    对应功能技术说明文档 工程1（数据采集层）的要求：
    - 多源数据 ≥1000 条
    - 合规处理
    - 增量更新
    """
    source: Source = Field(..., description="数据来源")
    source_url: str = Field(..., description="原始页面 URL")
    title: str = Field(..., min_length=1, max_length=200, description="岗位名称")
    company: Optional[str] = Field(None, max_length=200, description="公司名称")
    description: str = Field(..., min_length=1, description="岗位描述原文")
    required_skills_raw: list[str] = Field(default_factory=list, description="页面提取的必备技能原文")
    optional_skills_raw: list[str] = Field(default_factory=list, description="页面提取的加分技能原文")
    salary_range: Optional[str] = Field(None, description="薪资范围，如 '15K-25K'")
    location: Optional[str] = Field(None, description="工作地点")
    experience: Optional[str] = Field(None, description="经验要求")
    education: Optional[str] = Field(None, description="学历要求")
    publish_date: Optional[str] = Field(None, description="发布日期")
    crawl_timestamp: datetime = Field(default_factory=datetime.now, description="采集时间戳")
    raw_html: Optional[str] = Field(None, description="原始HTML（可选，用于事后审计）")


# ═══════════════════════════════════════════
# 清洗后数据
# ═══════════════════════════════════════════

class CleaningTrace(BaseModel):
    """单条数据的清洗追溯记录"""
    dedup_passed: bool = True
    dedup_similarity: float = 0.0
    plagiarism_score: float = 0.0
    ai_generated_score: float = 0.0
    freshness_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    noise_rejected: bool = False
    noise_reason: Optional[str] = None


class CleanedJobDescription(BaseModel):
    """
    清洗后 JD 数据结构 — 清洗流水线产出

    对应功能技术说明文档 工程4（多源数据清洗流水线）的要求：
    - MinHash 去重
    - 模板抄袭检测
    - 时间衰减加权
    - AI生成内容识别
    - JD质量评分 0-100
    """
    raw_id: str = Field(..., description="关联 RawJobDescription 的唯一标识")
    source: Source
    title: str
    company: Optional[str] = None
    description_clean: str = Field(..., description="清洗后的岗位描述")
    skills: list[SkillItem] = Field(default_factory=list, description="结构化技能列表")
    quality_score: float = Field(ge=0.0, le=100.0, description="综合质量评分")
    quality_level: QualityLevel = Field(default=QualityLevel.MEDIUM)
    is_duplicate: bool = False
    is_plagiarized: bool = False
    is_ai_generated: bool = False
    freshness_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    cleaning_trace: CleaningTrace = Field(default_factory=CleaningTrace)
    cleaned_at: datetime = Field(default_factory=datetime.now)


# ═══════════════════════════════════════════
# 质量报告
# ═══════════════════════════════════════════

class QualityReport(BaseModel):
    """
    清洗质量报告 — 对应项目计划 P3 阶段"数据清洗质量报告"要求
    """
    total_raw: int = Field(..., description="原始数据总量")
    total_cleaned: int = Field(..., description="清洗后数据量")
    dedup_removed: int = Field(..., description="去重移除量")
    dedup_rate: float = Field(..., description="去重率")
    noise_removed: int = Field(..., description="噪声过滤量")
    avg_quality_score: float = Field(..., description="平均质量分")
    quality_distribution: dict[QualityLevel, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.now)


# ═══════════════════════════════════════════
# 爬虫配置
# ═══════════════════════════════════════════

class CrawlConfig(BaseModel):
    """爬虫运行时配置"""
    keywords: list[str] = Field(..., min_length=1, description="搜索关键词列表")
    max_pages: int = Field(default=3, ge=1, le=10, description="每个关键词最大翻页数")
    min_results: int = Field(default=15, description="最少采集条数")
    request_delay: float = Field(default=3.0, ge=1.0, description="请求间隔/秒")
    timeout: int = Field(default=30, ge=10, le=60, description="请求超时/秒")
    output_dir: str = Field(default="./output", description="结果输出目录")


# ═══════════════════════════════════════════
# GitHub 仓库数据 & 技能资源关联
# ═══════════════════════════════════════════

class GitHubRepo(BaseModel):
    """GitHub 仓库项目信息 — 对应职位关联技能推荐模块"""
    repo_id: int = Field(..., description="GitHub 仓库 ID")
    full_name: str = Field(..., description="完整仓库名 owner/repo")
    name: str = Field(..., description="仓库名")
    owner: str = Field(..., description="所有者")
    description: Optional[str] = Field(None, description="项目简介")
    language: Optional[str] = Field(None, description="主要编程语言")
    topics: list[str] = Field(default_factory=list, description="仓库主题标签(领域)")
    stargazers_count: int = Field(default=0, description="Star 数量")
    forks_count: int = Field(default=0, description="Fork 数量")
    html_url: str = Field(..., description="仓库页面 URL")
    updated_at: Optional[str] = Field(None, description="最近更新时间")
    matched_keyword: str = Field(default="", description="匹配的搜索关键词")
