"""
数据采集与清洗流水线 — 单元测试

对应 多Agent协作开发规范 7.1: 测试覆盖率 ≥60%
运行: pytest tests/ -v --cov
"""

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.data_schema import (
    RawJobDescription,
    CleanedJobDescription,
    QualityReport,
    CrawlConfig,
    Source,
    QualityLevel,
)
from pipeline.dedup import DedupAgent, tokenize_jd
from pipeline.quality import QualityScorer


# ═══════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════

MOCK_DIR = Path(__file__).parent / "mocks"


def _load_mock(filename: str) -> list[RawJobDescription]:
    with open(MOCK_DIR / filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [RawJobDescription(**item) for item in data["data"]]


@pytest.fixture
def normal_jds() -> list[RawJobDescription]:
    return _load_mock("sample_normal.json")


@pytest.fixture
def boundary_jds() -> list[RawJobDescription]:
    return _load_mock("sample_boundary.json")


@pytest.fixture
def error_jds() -> list[RawJobDescription]:
    return _load_mock("sample_error.json")


@pytest.fixture
def dedup() -> DedupAgent:
    return DedupAgent(threshold=0.85)


@pytest.fixture
def scorer() -> QualityScorer:
    return QualityScorer()


# ═══════════════════════════════════════════════
# Schema 校验测试
# ═══════════════════════════════════════════════

class TestSchema:

    def test_raw_jd_minimal(self):
        jd = RawJobDescription(
            source=Source.ZHAOPIN,
            source_url="https://example.com/jd/1",
            title="测试岗位",
            description="这是岗位描述",
        )
        assert jd.source == Source.ZHAOPIN

    def test_raw_jd_full(self):
        jd = RawJobDescription(
            source=Source.ZHAOPIN,
            source_url="https://example.com/jd/1",
            title="Python工程师",
            company="测试公司",
            description="详细的岗位描述" * 10,
            required_skills_raw=["Python", "Django"],
            optional_skills_raw=["Docker"],
            salary_range="15K-25K",
            location="北京",
            experience="3-5年",
            education="本科",
            publish_date="2026-06-20",
        )
        assert len(jd.required_skills_raw) == 2

    def test_raw_jd_title_empty_raises_error(self):
        """空 title 应当被 Pydantic 校验拒绝"""
        with pytest.raises(Exception):
            RawJobDescription(
                source=Source.ZHAOPIN,
                source_url="https://example.com",
                title="",
                description="desc",
            )

    def test_crawl_config_defaults(self):
        config = CrawlConfig(keywords=["Python", "Java"], max_pages=3)
        assert config.min_results == 15
        assert config.request_delay == 3.0

    def test_quality_report_creation(self):
        report = QualityReport(
            total_raw=100,
            total_cleaned=85,
            dedup_removed=15,
            dedup_rate=0.15,
            noise_removed=0,
            avg_quality_score=72.5,
        )
        assert report.dedup_rate == 0.15

    def test_load_mock_normal(self, normal_jds):
        assert len(normal_jds) == 3
        assert normal_jds[0].source == Source.ZHAOPIN

    def test_load_mock_boundary(self, boundary_jds):
        """边界数据第二条使用与 normal 第一条相同的 source_url"""
        assert len(boundary_jds) == 2

    def test_load_mock_error(self, error_jds):
        """异常数据使用最小有效值通过 Schema 校验"""
        assert len(error_jds) == 2


# ═══════════════════════════════════════════════
# 去重测试（基于 datasketch）
# ═══════════════════════════════════════════════

class TestDedup:

    def test_tokenize_jd_output(self):
        tokens = tokenize_jd("Python工程师岗位")
        assert len(tokens) > 0
        # 含有 3-gram token
        has_3gram = any(len(t) == 3 for t in tokens)
        assert has_3gram

    def test_dedup_identical_text(self, dedup):
        """两条完全相同描述的 JD 应被去重"""
        jd1 = RawJobDescription(
            source=Source.ZHAOPIN,
            source_url="https://example.com/a",
            title="Python工程师",
            description="负责后端开发，使用Python Django框架，熟悉MySQL和Redis",
        )
        jd2 = RawJobDescription(
            source=Source.ZHAOPIN,
            source_url="https://example.com/b",
            title="Python工程师",
            description="负责后端开发，使用Python Django框架，熟悉MySQL和Redis",
        )
        result = dedup.deduplicate([jd1, jd2])
        assert len(result) == 1  # 第二条被移除

    def test_dedup_different_text(self, dedup):
        """不同描述的 JD 应都保留"""
        jd1 = RawJobDescription(
            source=Source.ZHAOPIN,
            source_url="https://example.com/a",
            title="Python工程师",
            description="Python Django MySQL Redis Linux Docker 后端开发",
        )
        jd2 = RawJobDescription(
            source=Source.ZHAOPIN,
            source_url="https://example.com/b",
            title="Java工程师",
            description="Java Spring Boot MyBatis Hibernate JPA Maven 后端开发",
        )
        result = dedup.deduplicate([jd1, jd2])
        assert len(result) == 2  # 技术栈不同，都应保留

    def test_dedup_normal_jds(self, dedup, normal_jds):
        result = dedup.deduplicate(normal_jds)
        assert 1 <= len(result) <= len(normal_jds)

    def test_dedup_empty_list(self, dedup):
        assert dedup.deduplicate([]) == []


# ═══════════════════════════════════════════════
# 质量评分测试
# ═══════════════════════════════════════════════

class TestQualityScorer:

    def test_score_normal_jd(self, scorer, normal_jds):
        cleaned = scorer.score(normal_jds[0])
        assert isinstance(cleaned, CleanedJobDescription)
        assert 0 <= cleaned.quality_score <= 100

    def test_score_low_quality(self, scorer, boundary_jds):
        """字段稀疏的 JD 应得低分"""
        cleaned = scorer.score(boundary_jds[0])  # title="实习", desc="招人。"
        assert cleaned.quality_score < 60

    def test_score_minimal_description(self, scorer, error_jds):
        cleaned = scorer.score(error_jds[0])
        assert cleaned.quality_score < 45

    def test_batch_score(self, scorer, normal_jds):
        results = scorer.score_batch(normal_jds)
        assert len(results) == len(normal_jds)
        assert all(isinstance(r, CleanedJobDescription) for r in results)

    def test_ai_detection_in_range(self, scorer, normal_jds):
        cleaned = scorer.score(normal_jds[0])
        assert 0 <= cleaned.cleaning_trace.ai_generated_score <= 1


# ═══════════════════════════════════════════════
# 端到端集成测试
# ═══════════════════════════════════════════════

class TestEndToEnd:

    def test_full_pipeline_with_mocks(self, normal_jds):
        # Stage 2a: 去重
        dedup = DedupAgent(threshold=0.85)
        unique = dedup.deduplicate(normal_jds)
        dedup_removed = len(normal_jds) - len(unique)

        # Stage 2b: 评分
        scorer = QualityScorer()
        cleaned = scorer.score_batch(unique)
        avg = sum(j.quality_score for j in cleaned) / len(cleaned)

        # Stage P: 报告
        report = QualityReport(
            total_raw=len(normal_jds),
            total_cleaned=len(cleaned),
            dedup_removed=dedup_removed,
            dedup_rate=round(dedup_removed / max(len(normal_jds), 1), 3),
            noise_removed=0,
            avg_quality_score=round(avg, 1),
        )

        assert report.total_raw == 3
        assert report.total_cleaned >= 1
        assert report.avg_quality_score > 0
