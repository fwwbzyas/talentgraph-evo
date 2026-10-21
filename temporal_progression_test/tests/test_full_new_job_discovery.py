from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


PLAYBACK_DB = Path(os.environ.get("TALENTGRAPH_FULL_PLAYBACK_DB", ""))
PLAYBACK_REPORT = Path(os.environ.get("TALENTGRAPH_FULL_PLAYBACK_REPORT", ""))
HAS_FULL_PLAYBACK = bool(str(PLAYBACK_DB)) and PLAYBACK_DB.is_file() and PLAYBACK_REPORT.is_file()


@pytest.mark.skipif(not HAS_FULL_PLAYBACK, reason="full monthly playback artifacts were not supplied")
def test_monthly_playback_detects_new_jobs_and_preserves_first_seen_semantics():
    report = json.loads(PLAYBACK_REPORT.read_text(encoding="utf-8"))
    monthly = report["monthly_results"]

    assert [item["period"] for item in monthly] == report["periods"]
    assert all(item["new"] > 0 for item in monthly)
    assert sum(item["new"] for item in monthly) == report["final_job_assets"]
    assert report["sentinel_actual"]["new"] == report["sentinel_expected"]["new"]
    assert report["sentinel_outcome_accuracy"] == 1.0


@pytest.mark.skipif(not HAS_FULL_PLAYBACK, reason="full monthly playback artifacts were not supplied")
def test_frontend_new_job_discovery_finds_evidence_backed_candidates(monkeypatch):
    monkeypatch.setenv("TALENTGRAPH_LLM_DISABLED", "1")

    from agents.emerging_jobs.service import EmergingJobAgent
    from contracts import EmergingJobDiscoveryRequest
    from core.store import AppStore

    store = AppStore(str(PLAYBACK_DB))
    candidates = EmergingJobAgent().discover(
        [],
        [],
        EmergingJobDiscoveryRequest(minimum_source_count=2, minimum_confidence=0.45),
        persisted_jobs=store.list_jobs(),
    )

    assert candidates
    assert all(item.source_count >= 2 for item in candidates)
    assert all(item.confidence >= 0.45 for item in candidates)
    assert all(item.evidence for item in candidates)
    assert all(
        evidence["source_id"] in store.jobs
        for candidate in candidates
        for evidence in candidate.evidence
    )
    assert [item.confidence for item in candidates] == sorted(
        (item.confidence for item in candidates), reverse=True
    )
