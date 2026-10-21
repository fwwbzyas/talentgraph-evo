from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agents.emerging_jobs.service import EmergingJobAgent
from contracts import CleanedDataBatch, CleanedDataItem, EmergingJobDiscoveryRequest


ANCHOR = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _item(index: int, published_at: datetime) -> CleanedDataItem:
    content = "负责 AI Agent 平台研发，要求掌握 RAG、LangGraph 和工具调用。"
    return CleanedDataItem(
        source_id=f"emerging-{index}",
        domain="人工智能",
        title="AI Agent 工程师",
        content=content,
        raw_content=content,
        collected_at=published_at,
        quality_score=95,
        dedup_hash=f"emerging-hash-{index}",
        company=f"企业{index}",
        city="北京",
        skill_tags=["RAG", "LangGraph", "工具调用"],
        responsibilities=["负责平台研发"],
        published_at=published_at,
        source_platform="fixture",
    )


def _market_item(index: int, published_at: datetime) -> CleanedDataItem:
    content = "负责 Java 后端平台研发，要求掌握 Java 和 Kubernetes。"
    return CleanedDataItem(
        source_id=f"market-{index}",
        domain="智能系统",
        title="Java 后端工程师",
        content=content,
        raw_content=content,
        collected_at=published_at,
        quality_score=95,
        dedup_hash=f"market-hash-{index}",
        company=f"市场企业{index}",
        city="北京",
        skill_tags=["Java", "Kubernetes"],
        responsibilities=["负责后端研发"],
        published_at=published_at,
        source_platform="fixture",
    )


def _discover(monkeypatch, candidate_days: list[int], market_days: list[int] | None = None):
    agent = EmergingJobAgent()
    monkeypatch.setattr(agent, "_now", lambda: ANCHOR)
    candidate_items = [
        _item(index, ANCHOR - timedelta(days=days))
        for index, days in enumerate(candidate_days)
    ]
    market_items = [
        _market_item(index, ANCHOR - timedelta(days=days))
        for index, days in enumerate(market_days or [])
    ]
    batch = CleanedDataBatch(batch_name="emerging-jobs-test", items=[*candidate_items, *market_items])
    candidates = agent.discover(
        [batch],
        [],
        EmergingJobDiscoveryRequest(minimum_source_count=1, minimum_confidence=0),
    )
    assert len(candidates) == 1
    return candidates[0]


def test_growth_rate_uses_demand_share_when_market_volume_changes(monkeypatch):
    candidate = _discover(
        monkeypatch,
        [5, 20, 25, 35, 45, 50, 55],
        [10] * 27 + [40] * 96,
    )

    assert candidate.trend_series[-2]["count"] == 4
    assert candidate.trend_series[-2]["market_count"] == 100
    assert candidate.trend_series[-2]["demand_share"] == 0.04
    assert candidate.trend_series[-1]["count"] == 3
    assert candidate.trend_series[-1]["market_count"] == 30
    assert candidate.trend_series[-1]["demand_share"] == 0.1
    assert candidate.growth_rate == 1.5
    assert candidate.trend_series[-1]["count"] < candidate.trend_series[-2]["count"]


def test_growth_rate_reports_real_demand_share_decline(monkeypatch):
    candidate = _discover(monkeypatch, [5, 25, 35, 45, 55, 58], [10, 15])

    assert candidate.trend_series[-2]["count"] == 4
    assert candidate.trend_series[-2]["market_count"] == 4
    assert candidate.trend_series[-2]["demand_share"] == 1.0
    assert candidate.trend_series[-1]["count"] == 2
    assert candidate.trend_series[-1]["market_count"] == 4
    assert candidate.trend_series[-1]["demand_share"] == 0.5
    assert candidate.growth_rate == -0.5


def test_growth_rate_handles_no_previous_demand_share(monkeypatch):
    candidate = _discover(monkeypatch, [5, 18, 29], [35])

    assert candidate.trend_series[-2]["count"] == 0
    assert candidate.trend_series[-2]["market_count"] == 1
    assert candidate.trend_series[-2]["demand_share"] == 0.0
    assert candidate.trend_series[-1]["count"] == 3
    assert candidate.trend_series[-1]["market_count"] == 3
    assert candidate.trend_series[-1]["demand_share"] == 1.0
    assert candidate.growth_rate == 1.0


def test_trend_intervals_are_contiguous_and_do_not_double_count_boundaries(monkeypatch):
    candidate = _discover(monkeypatch, [30, 60])
    trend_series = candidate.trend_series
    periods = [datetime.fromisoformat(item["period"]).date() for item in trend_series]

    assert len(trend_series) == 6
    assert all(right - left == timedelta(days=30) for left, right in zip(periods, periods[1:]))
    assert [period["count"] for period in trend_series] == [0, 0, 0, 0, 1, 1]
    assert [period["market_count"] for period in trend_series] == [0, 0, 0, 0, 1, 1]
    assert [period["demand_share"] for period in trend_series] == [0.0, 0.0, 0.0, 0.0, 1.0, 1.0]
    assert sum(period["count"] for period in trend_series) == 2
    assert sum(period["market_count"] for period in trend_series) == 2
    assert candidate.growth_rate == 0.0
