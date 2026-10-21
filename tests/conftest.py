import os

import pytest


os.environ["TALENTGRAPH_LLM_DISABLED"] = "1"


@pytest.fixture(autouse=True)
def disable_live_llm_calls(monkeypatch):
    """Unit tests must never spend quota or depend on the live model service."""
    monkeypatch.setenv("TALENTGRAPH_LLM_DISABLED", "1")
