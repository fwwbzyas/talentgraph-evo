import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def job51_search_payload() -> dict:
    return json.loads((FIXTURES / "job51_search_response.json").read_text(encoding="utf-8"))


@pytest.fixture()
def job51_waf_html() -> str:
    return (FIXTURES / "job51_waf_challenge.html").read_text(encoding="utf-8")


@pytest.fixture()
def liepin_cards_html() -> str:
    return (FIXTURES / "liepin_search_cards.html").read_text(encoding="utf-8")


@pytest.fixture()
def liepin_detail_html() -> str:
    return (FIXTURES / "liepin_job_detail.html").read_text(encoding="utf-8")
