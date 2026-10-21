from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def resolve_path(value: str, default: str) -> Path:
    raw = Path(os.getenv(value, default))
    return raw if raw.is_absolute() else (ROOT / raw).resolve()


COURSE_DB = resolve_path("COURSE_RAG_DB", "data/talentgraph.db")
TALENTGRAPH_DB = resolve_path("TALENTGRAPH_DB", "data/talentgraph.db")
HTTP_TIMEOUT = float(os.getenv("COURSE_HTTP_TIMEOUT", "15"))
