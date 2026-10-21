from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ImportRequest(BaseModel):
    batch_name: str = "manual_import"
    items: list[dict[str, Any]] | None = None
    min_quality: float = Field(default=0, ge=0, le=100)
    strict_scope: bool = True


class CleanedDataItem(BaseModel):
    source_id: str
    source_type: Literal["jd", "resume", "article", "course", "repo", "paper"] = "jd"
    domain: str
    title: str
    content: str
    raw_content: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    quality_score: float = Field(ge=0, le=100)
    dedup_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_category: Literal["recruitment"] = "recruitment"
    company: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    salary_min_k: int | None = Field(default=None, ge=0)
    salary_max_k: int | None = Field(default=None, ge=0)
    salary_months: int = Field(default=12, ge=1, le=24)
    currency: str = "CNY"
    city: str | None = None
    district: str | None = None
    experience_min_years: int | None = Field(default=None, ge=0)
    experience_max_years: int | None = Field(default=None, ge=0)
    education: str | None = None
    employment_type: str = "full_time"
    skill_tags: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    evidence_segments: list[dict[str, Any]] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    changed_at: datetime | None = None
    source_platform: str | None = None
    source_url: str | None = None
    job_status: Literal["active", "offline"] = "active"
    change_type: Literal["new", "updated", "unchanged", "offline"] = "unchanged"


class CleanedDataBatch(BaseModel):
    batch_id: str = Field(default_factory=lambda: f"batch_{uuid4().hex[:8]}")
    batch_name: str
    items: list[CleanedDataItem]
    quality_summary: dict[str, Any] = Field(default_factory=dict)


class CommunitySignal(BaseModel):
    signal_id: str
    source_category: Literal["community_signal"] = "community_signal"
    source_type: Literal["forum", "social_media", "developer_community"]
    source_platform: str
    source_url: str
    domain: Literal["人工智能", "大数据", "智能系统", "物联网"]
    title: str
    content: str
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    engagement: dict[str, int] = Field(default_factory=dict)
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    quality_score: float = Field(ge=0, le=100)
    dedup_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataQualityRejection(BaseModel):
    rejection_id: str = Field(default_factory=lambda: f"reject_{uuid4().hex[:10]}")
    source_category: Literal["recruitment", "community_signal"]
    source_id: str
    source_platform: str | None = None
    title: str | None = None
    reasons: list[str] = Field(default_factory=list)
    quality_score: float | None = None
    collection_run_id: str | None = None
    record_type: Literal["quality_rejection", "change_review", "duplicate"] = "quality_rejection"
    source_url: str | None = None
    raw_item: dict[str, Any] = Field(default_factory=dict)
    matched_source_id: str | None = None
    review_status: Literal["pending", "approved", "rejected"] = "pending"
    review_note: str | None = None
    reviewed_at: datetime | None = None
    rejected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    occurrence_count: int = Field(default=1, ge=1)
    review_decision: str | None = None
    corrections: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataAuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"audit_{uuid4().hex[:12]}")
    source_category: Literal["recruitment", "community_signal"]
    source_id: str
    source_platform: str | None = None
    source_url: str | None = None
    title: str | None = None
    record_type: Literal[
        "accepted", "pending_review", "quality_rejection", "field_correction",
        "copy_cluster", "job_change",
    ] = "accepted"
    status: Literal["accepted", "pending_semantic_review", "manual_review", "rejected", "quarantined"]
    reasons: list[str] = Field(default_factory=list)
    raw_item: dict[str, Any] = Field(default_factory=dict)
    normalized_item: dict[str, Any] = Field(default_factory=dict)
    field_changes: dict[str, dict[str, Any]] = Field(default_factory=dict)
    evidence_snippets: list[dict[str, Any]] = Field(default_factory=list)
    rule_assessment: dict[str, Any] = Field(default_factory=dict)
    llm_assessment: dict[str, Any] = Field(default_factory=dict)
    cross_source_assessment: dict[str, Any] = Field(default_factory=dict)
    final_confidence: float = Field(default=0, ge=0, le=1)
    graph_publish_status: Literal["published", "blocked", "pending", "auxiliary_only"] = "blocked"
    review_status: Literal["pending", "approved", "rejected"] = "pending"
    review_note: str | None = None
    review_decision: str | None = None
    corrections: dict[str, Any] = Field(default_factory=dict)
    collection_run_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reviewed_at: datetime | None = None


def _default_collection_source_ids() -> list[str]:
    return ["boss", "zhaopin", "remoteok", "arbeitnow", "hackernews", "stackoverflow", "github"]


class DataCollectionRequest(BaseModel):
    source_ids: list[str] = Field(
        default_factory=_default_collection_source_ids
    )
    max_items_per_source: int = Field(default=50, ge=1, le=200)
    lookback_hours: int = Field(default=24 * 7, ge=1, le=24 * 90)
    min_job_quality: float = Field(default=65, ge=0, le=100)
    min_signal_quality: float = Field(default=55, ge=0, le=100)
    persist: bool = True
    query_overrides: dict[str, list[str]] = Field(default_factory=dict)
    city_overrides: dict[str, list[str]] = Field(default_factory=dict)
    collection_mode_override: Literal["discovery", "monitor", "hybrid"] | None = None
    full_scan_chunk: bool = False
    reset_scan_cursor: bool = False


class SourceCollectionResult(BaseModel):
    source_id: str
    source_category: Literal["recruitment", "community_signal"]
    status: Literal["queued", "running", "success", "partial", "failed"]
    phase: Literal["queued", "fetching", "normalizing", "persisting", "completed", "failed"] = "queued"
    fetched: int = 0
    scanned: int = 0
    discovery_candidates: int = 0
    monitor_candidates: int = 0
    reached_end: bool = False
    end_reason: str | None = None
    accepted: int = 0
    rejected: int = 0
    duration_ms: int = 0
    stage_durations_ms: dict[str, int] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class DataCollectionRun(BaseModel):
    run_id: str = Field(default_factory=lambda: f"collect_{uuid4().hex[:10]}")
    status: Literal["running", "completed", "partial", "failed"] = "running"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    source_results: list[SourceCollectionResult] = Field(default_factory=list)
    batch_id: str | None = None
    recruitment_fetched: int = 0
    recruitment_accepted: int = 0
    community_fetched: int = 0
    community_accepted: int = 0
    rejected_count: int = 0
    duplicate_count: int = 0
    exact_duplicate_count: int = 0
    repost_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    quality_summary: dict[str, Any] = Field(default_factory=dict)


class CollectionScheduleRequest(BaseModel):
    enabled: bool = True
    interval_minutes: float = Field(default=1440, ge=5, le=10080)
    jitter_minutes: float = Field(default=0, ge=0, le=1440)
    request: DataCollectionRequest = Field(default_factory=DataCollectionRequest)


class SourceCollectionStrategy(BaseModel):
    enabled: bool = True
    mode: Literal["discovery", "monitor", "hybrid"] = "hybrid"
    min_interval_minutes: float = Field(default=5, ge=5, le=10080)
    max_interval_minutes: float = Field(default=10, ge=5, le=10080)
    items_per_run: int = Field(default=50, ge=1, le=200)
    discovery_ratio: float = Field(default=0.6, ge=0, le=1)
    revisit_after_hours: float = Field(default=12, ge=1, le=24 * 30)
    cities: list[str] = Field(default_factory=lambda: ["全国"])
    job_queries: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_range(self):
        if self.min_interval_minutes > self.max_interval_minutes:
            raise ValueError("min_interval_minutes must not exceed max_interval_minutes")
        return self


class CollectionStrategyRequest(BaseModel):
    enabled: bool = True
    min_interval_minutes: float = Field(default=5, ge=5, le=10080)
    max_interval_minutes: float = Field(default=10, ge=5, le=10080)
    items_per_source: int = Field(default=50, ge=1, le=200)
    cities: list[str] = Field(default_factory=lambda: ["全国"])
    job_queries: list[str] = Field(default_factory=list)
    sources: dict[str, SourceCollectionStrategy] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range(self):
        if self.min_interval_minutes > self.max_interval_minutes:
            raise ValueError("min_interval_minutes must not exceed max_interval_minutes")
        return self


class SkillEvidence(BaseModel):
    source_id: str
    source_type: str = "jd"
    snippet: str
    confidence: float = Field(ge=0, le=1)


class SkillRequirement(BaseModel):
    skill_id: str
    name: str
    category: str
    required_level: Literal["basic", "intermediate", "advanced", "expert"]
    importance: Literal["required", "preferred", "emerging"]
    evidence: list[SkillEvidence] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class JobGraph(BaseModel):
    job_id: str
    job_title: str
    domain: str
    responsibilities: list[str]
    skills: list[SkillRequirement]
    scenarios: list[str]
    capability_domains: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    version: str = "2026Q3"
    graph_nodes: list[dict[str, Any]] = Field(default_factory=list)
    graph_edges: list[dict[str, Any]] = Field(default_factory=list)


class JobGraphBuildRequest(BaseModel):
    batch_id: str
    target_job_title: str = "Java 后端工程师"


class EvolutionOutput(BaseModel):
    job_id: str
    job_title: str
    new_job_candidates: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    changes: list[dict[str, Any]]
    summary: dict[str, Any] = Field(default_factory=dict)
    trend_signals: list[dict[str, Any]] = Field(default_factory=list)
    compared_versions: dict[str, str] = Field(default_factory=dict)


class AssessmentAction(BaseModel):
    type: Literal["question", "scenario_task", "interactive_game", "finish"]
    content: str
    options: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssessmentSession(BaseModel):
    session_id: str = Field(default_factory=lambda: f"session_{uuid4().hex[:8]}")
    candidate_id: str
    target_job_id: str
    current_stage: str = "resume_parse"
    status: Literal["running", "finished"] = "running"
    next_action: AssessmentAction | None = None
    candidate_profile: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    stage_progress: float = Field(default=0, ge=0, le=1)
    completed_stages: list[str] = Field(default_factory=list)
    provider_status: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AssessmentAnswer(BaseModel):
    session_id: str
    answer: str


class GameResultInput(BaseModel):
    session_id: str
    game_id: str = "incident_response"
    events: list[dict[str, Any]]


class CandidateProfile(BaseModel):
    candidate_id: str
    target_job_id: str
    name: str = ""
    skills: list[dict[str, Any]]
    projects: list[dict[str, Any]] = Field(default_factory=list)
    behavior_signals: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    summary: str = ""
    experience_years: float | None = Field(default=None, ge=0)
    education: str | None = None
    skill_scores: dict[str, int] = Field(default_factory=dict)
    competency_dimensions: list[dict[str, Any]] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    expected_salary_k: list[int] = Field(default_factory=list)
    archetype_code: str = ""
    archetype_title: str = ""
    archetype_narrative: str = ""
    traits: list[str] = Field(default_factory=list)
    provider_status: dict[str, Any] = Field(default_factory=dict)
    profile_timing: dict[str, Any] = Field(default_factory=dict)
    resume_analysis: dict[str, Any] = Field(default_factory=dict)


class AssessmentFinalizeOutput(BaseModel):
    session_id: str
    candidate_profile: CandidateProfile


class EmergingJobCandidate(BaseModel):
    candidate_id: str
    name: str
    domain: str
    core_responsibilities: list[str]
    required_skills: list[str]
    bonus_skills: list[str] = Field(default_factory=list)
    application_scenarios: list[str] = Field(default_factory=list)
    source_family: str = ""
    difference_summary: str = ""
    auxiliary_evidence: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]]
    confidence: float = Field(ge=0, le=1)
    maturity_status: Literal["signal", "forming", "established"]
    source_count: int = Field(ge=0)
    growth_rate: float
    definition: str = ""
    trend_series: list[dict[str, Any]] = Field(default_factory=list)
    source_diversity: dict[str, Any] = Field(default_factory=dict)
    cooccurrence_signals: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    provider_status: dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    definition_version: str = "emerging-job-v1"
    review_status: Literal["pending", "watching", "approved", "rejected"] = "pending"


class EmergingJobDiscoveryRequest(BaseModel):
    batch_ids: list[str] = Field(default_factory=list)
    minimum_source_count: int = Field(default=2, ge=1)
    minimum_confidence: float = Field(default=0.45, ge=0, le=1)


class ValidationRunRequest(BaseModel):
    jd_limit: int = Field(default=100, ge=1, le=500)
    resume_cases: list[dict[str, Any]] = Field(default_factory=list)
    match_cases: list[dict[str, Any]] = Field(default_factory=list)


class ValidationFailure(BaseModel):
    stage: Literal["jd", "resume", "match"]
    sample_id: str
    field: str
    expected: Any = None
    actual: Any = None
    message: str


class ValidationRun(BaseModel):
    run_id: str = Field(default_factory=lambda: f"validation_{uuid4().hex[:10]}")
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    stage: str = "queued"
    stage_progress: float = Field(default=0, ge=0, le=1)
    metrics: dict[str, Any] = Field(default_factory=dict)
    failures: list[ValidationFailure] = Field(default_factory=list)
    stage_results: list[dict[str, Any]] = Field(default_factory=list)
    duration_ms: int = 0
    version: str = "validation-v1"
    provider_status: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class MatchReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"report_{uuid4().hex[:8]}")
    candidate_id: str
    target_job_id: str
    score: int = Field(ge=0, le=100)
    level: Literal["high", "medium", "low"]
    gaps: list[dict[str, Any]]
    strengths: list[dict[str, Any]]
    risks: list[str]
    follow_up_questions: list[str]
    learning_path: list[dict[str, Any]]
    executive_summary: str
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    matched_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    evidence_coverage: float = Field(default=0, ge=0, le=1)
    interview_recommendation: str = ""
    job_snapshot: dict[str, Any] = Field(default_factory=dict)
