import json

import pytest
from fastapi import HTTPException

from apps.api.main import _parse_target_job_ids


def test_parse_target_job_ids_supports_multi_job_and_keeps_primary_first():
    selected = _parse_target_job_ids(
        "job_primary",
        json.dumps(["job_secondary", "job_primary", "job_third"]),
    )

    assert selected == ["job_primary", "job_secondary", "job_third"]


def test_parse_target_job_ids_requires_at_least_one_job():
    with pytest.raises(HTTPException) as error:
        _parse_target_job_ids(None, json.dumps([]))

    assert error.value.status_code == 422


def test_parse_target_job_ids_rejects_non_array_payload():
    with pytest.raises(HTTPException) as error:
        _parse_target_job_ids(None, json.dumps({"job_id": "job_primary"}))

    assert error.value.status_code == 422
