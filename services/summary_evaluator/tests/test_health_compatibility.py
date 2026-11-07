"""Can saved disabled-coverage health be read without changing native observations?"""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.serve_http.contracts.previous_api_health import PreviousApiHealth
from summary_evaluator.serve_http.read_api_health import ReadableApiHealth


def current_health() -> dict[str, object]:
    return {
        "version": "2026-11-07",
        "service_instance_id": "11111111-2222-4333-8444-555555555555",
        "enabled_routes": [],
        "status": "disabled",
        "hhem": {"status": "disabled", "worker": None, "model": None},
        "unieval": {"status": "disabled", "worker": None, "model": None},
        "log_file": None,
        "log_available": False,
    }


def test_current_live_health_has_no_retired_slot() -> None:
    payload = current_health()
    observed = ApiHealth.model_validate_json(json.dumps(payload))
    assert observed.model_dump(mode="json") == payload
    assert set(ApiHealth.model_fields) == set(payload)
    assert TypeAdapter(ReadableApiHealth).validate_json(json.dumps(payload)) == observed
    with pytest.raises(ValidationError):
        ApiHealth.model_validate_json(json.dumps({**payload, "coverage": payload["hhem"]}))


def test_saved_previous_health_projects_only_its_disabled_slot() -> None:
    payload = current_health()
    previous = {**payload, "coverage": payload["hhem"]}
    observed = TypeAdapter(ReadableApiHealth).validate_json(json.dumps(previous))
    assert observed.model_dump(mode="json") == payload
    assert observed.service_instance_id == previous["service_instance_id"]
    assert observed.hhem.worker is observed.unieval.worker is None
    assert "coverage" in previous
    python_input = {**previous, "enabled_routes": ()}
    assert TypeAdapter(ReadableApiHealth).validate_python(python_input) == observed
    previous_model = PreviousApiHealth.model_validate(python_input)
    projected = TypeAdapter(ReadableApiHealth).validate_python(previous_model)
    assert type(projected) is ApiHealth and projected == observed


@pytest.mark.parametrize(
    "change",
    [
        {"coverage": {"status": "ready", "worker": None, "model": None}},
        {"coverage": {"status": "disabled", "worker": None, "model": None, "extra": True}},
        {"coverage": None},
        {"enabled_routes": ["coverage"]},
        {"version": "2026-11-08"},
        {"other": {"status": "disabled"}},
        {"log_available": True},
    ],
)
def test_previous_health_never_accepts_active_coverage_or_invalid_evidence(
    change: dict[str, object],
) -> None:
    payload = current_health()
    with pytest.raises(ValidationError):
        TypeAdapter(ReadableApiHealth).validate_json(
            json.dumps({**payload, "coverage": payload["hhem"], **change})
        )
