from __future__ import annotations

from pathlib import Path


# Formal recruitment evidence accepted by governance, graph, evolution and matching.
# Keep this policy in one place so adding a source cannot silently stop at ingestion.
RECRUITMENT_SOURCE_IDS = ("boss", "zhaopin", "51job", "liepin")
RECRUITMENT_SOURCE_SET = frozenset(RECRUITMENT_SOURCE_IDS)

# BOSS and Zhaopin retain their existing collection behaviour. The two new sources
# are deliberately sampled at a moderate daily cadence because the repository already
# contains a large recruitment evidence base.
CORE_RECRUITMENT_SOURCE_IDS = ("boss", "zhaopin")
SUPPLEMENTAL_RECRUITMENT_SOURCE_IDS = ("51job", "liepin")
SUPPLEMENTAL_ITEMS_PER_RUN = 36
SUPPLEMENTAL_INTERVAL_MINUTES = 24 * 60

SOURCE_DISPLAY_NAMES = {
    "boss": "BOSS直聘",
    "zhaopin": "智联招聘",
    "51job": "前程无忧",
    "liepin": "猎聘",
}

SOURCE_STATE_PATHS = {
    "boss": Path("data/boss_collection_state.json"),
    "zhaopin": Path("data/zhaopin_collection_state.json"),
    "51job": Path("data/51job_collection_state.json"),
    "liepin": Path("data/liepin_collection_state.json"),
}


def is_recruitment_source(source_id: str | None) -> bool:
    return bool(source_id and source_id in RECRUITMENT_SOURCE_SET)
