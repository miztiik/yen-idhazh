"""Does isolated host evidence refuse missing, drifting or unsafe inputs?"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from idhazh.contracts.host_evidence import WorkloadRequest

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("mode", ["reference", "native_only", "stop"])
def test_workload_request_round_trip_has_a_versioned_contract(mode: str) -> None:
    request = WorkloadRequest.model_validate({"sequence": 1, "mode": mode})
    assert WorkloadRequest.model_validate_json(request.model_dump_json()) == request
    assert request.version == WorkloadRequest.schema_version()


@pytest.mark.parametrize(
    "payload",
    [
        {"sequence": True, "mode": "reference"},
        {"sequence": 0, "mode": "reference"},
        {"sequence": 1, "mode": "model"},
        {"sequence": 1, "mode": "reference", "url": "https://example.org"},
    ],
)
def test_workload_request_refuses_nonlocal_or_unbounded_commands(payload: object) -> None:
    with pytest.raises(ValidationError):
        WorkloadRequest.model_validate(payload)
