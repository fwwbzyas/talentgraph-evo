from datetime import date, timedelta
from types import SimpleNamespace

from agents.evolution.service import EvolutionAgent


def test_market_evolution_keeps_older_changes_and_orders_latest_first():
    jobs = [SimpleNamespace(source_platform="zhaopin")]
    versions = [
        {
            "job_id": "zhaopin:ai-agent",
            "version_number": 1,
            "changed_at": "2026-07-20T09:00:00+00:00",
            "changes": {"baseline": {"before": None, "after": True}},
            "snapshot": {
                "source_platform": "zhaopin",
                "title": "AI Agent 应用开发工程师",
                "company": "测试企业",
                "job_status": "active",
            },
        },
    ]
    for version_number in range(2, 53):
        versions.append(
            {
                "job_id": "zhaopin:ai-agent",
                "version_number": version_number,
                "changed_at": (
                    date(2026, 7, 21) + timedelta(days=version_number - 2)
                ).isoformat() + "T09:00:00+00:00",
                "changes": {"job_status": {"before": "active", "after": "offline"}},
                "snapshot": {
                    "source_platform": "zhaopin",
                    "title": "AI Agent 应用开发工程师",
                    "company": "测试企业",
                    "job_status": "offline" if version_number % 2 == 0 else "active",
                },
            }
        )

    result = EvolutionAgent().analyze_market(jobs, versions)
    recent_changes = result["recent_changes"]

    assert len(recent_changes) == 51
    assert recent_changes[0]["version_number"] == 52
    assert recent_changes[-1]["version_number"] == 2
    assert recent_changes[-1]["changed_at"] == "2026-07-21T09:00:00+00:00"
    assert recent_changes[-1]["title"] == "AI Agent 应用开发工程师"
