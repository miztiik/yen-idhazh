"""Prove native contract boundaries without serving HTTP or loading a model."""

import json
from collections.abc import Callable
from typing import get_args

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from hhem_evaluator.contracts.base import API_PREFIX, SCHEMA_VERSION, NativeContract
from hhem_evaluator.contracts.error_detail import (
    ERROR_POLICIES,
    ErrorCode,
    ErrorDetail,
    project_request_error,
)
from hhem_evaluator.contracts.evaluate_request import EffectiveSettings, EvaluateRequest
from hhem_evaluator.contracts.evaluation_event import EvaluationEvent, EventDetails
from hhem_evaluator.contracts.evaluation_progress import (
    EvaluationTimings,
    EvaluationWindows,
    WindowCounts,
    WindowDetail,
    WindowDetails,
)
from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from hhem_evaluator.contracts.model_identity import ModelIdentity
from hhem_evaluator.contracts.service_health import ServiceHealth
from hhem_evaluator.contracts.service_settings import ServiceSettings, StartupContext
from hhem_evaluator.contracts.worker_identity import WorkerIdentity
from hhem_evaluator.contracts.worker_message import (
    FrozenAssets,
    ScoreWindow,
    WindowOutcome,
    WorkerBootstrap,
    WorkerCommand,
    WorkerFailed,
    WorkerReady,
    WorkerReply,
    WorkerStarted,
    validate_window_reply,
)
from hhem_evaluator.load_settings import load_settings
from hhem_evaluator.resolve_ids import create_event_id

from .contract_examples import (
    EXECUTION_ID,
    SETTINGS_FILE,
    example_command,
    example_event,
    example_model,
    example_result,
    example_window_outcome,
    example_worker,
    read_contract,
)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_text", ""),
        ("source_text", " \t\n"),
        ("summary_text", ""),
        ("source_text", None),
        ("source_text", 42),
        ("summary_text", True),
        ("full_source_text", ""),
        ("full_source_text", " \n"),
        ("source_text", "\ud800"),
        ("summary_text", "\udfff"),
        ("hhem_full", "false"),
        ("hhem_full", 0),
        ("include_window_details", 1),
        ("chunk_words", "900"),
        ("chunk_words", 1.0),
        ("chunk_words", True),
        ("chunk_overlap_words", "100"),
        ("chunk_overlap_words", False),
        ("model", "request-selected"),
        ("destination", "https://invalid.example"),
    ],
)
def test_invalid_request_values_and_controls_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        read_contract(
            EvaluateRequest, {"source_text": "Source.", "summary_text": "Summary.", field: value}
        )


@pytest.mark.parametrize(
    "field",
    [
        "full_source_text",
        "hhem_full",
        "include_window_details",
        "chunk_words",
        "chunk_overlap_words",
        "request_id",
        "correlation_id",
    ],
)
def test_omittable_does_not_mean_nullable(field: str) -> None:
    minimal = {"source_text": " Source.\n", "summary_text": "\tSummary. "}
    request = read_contract(EvaluateRequest, minimal)
    assert request.model_dump(mode="json") == minimal
    with pytest.raises(ValidationError):
        read_contract(EvaluateRequest, {**minimal, field: None})


def test_fastapi_openapi_matches_native_omission_and_null_rules() -> None:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=f"{API_PREFIX}/openapi.json")

    def accept_native_request(request: EvaluateRequest) -> EvaluateRequest:
        return request

    app.add_api_route(
        f"{API_PREFIX}/evaluate", accept_native_request, methods=["POST"], response_model=None
    )
    schema = app.openapi()["components"]["schemas"]["EvaluateRequest"]
    native = EvaluateRequest.model_json_schema(mode="validation")
    assert schema["required"] == ["source_text", "summary_text"]
    assert schema["required"] == native["required"]
    assert schema["additionalProperties"] is False
    for field in EvaluateRequest.model_fields:
        assert schema["properties"][field] == native["properties"][field]
        assert "null" not in json.dumps(schema["properties"][field])
        assert "default" not in schema["properties"][field]
    assert "version" not in schema["properties"]
    assert schema["version"] == SCHEMA_VERSION


@pytest.mark.parametrize(
    "contract",
    [
        EvaluateRequest,
        EffectiveSettings,
        EvaluationResult,
        ErrorDetail,
        EvaluationEvent,
        EventDetails,
        WindowCounts,
        WindowDetail,
        WindowDetails,
        EvaluationTimings,
        EvaluationWindows,
        ModelIdentity,
        WorkerIdentity,
        ServiceHealth,
        ServiceSettings,
        StartupContext,
        WorkerBootstrap,
        WorkerStarted,
        WorkerReady,
        WorkerFailed,
        ScoreWindow,
        WindowOutcome,
    ],
)
def test_native_schemas_are_strict_versioned_and_change_logged(
    contract: type[NativeContract],
) -> None:
    schema = contract.model_json_schema()
    assert schema["version"] == SCHEMA_VERSION
    changes = schema["changelog"]
    assert 1 <= len(changes) <= 5
    assert changes[0]["version"] == SCHEMA_VERSION
    assert all(entry["change"] and "\n" not in entry["change"] for entry in changes)
    assert schema["additionalProperties"] is False
    if "version" in contract.model_fields:
        assert "version" in schema["required"]
        assert schema["properties"]["version"]["const"] == SCHEMA_VERSION


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("INVALID_JSON", 400),
        ("INVALID_REQUEST", 400),
        ("INPUT_TIMEOUT", 408),
        ("BODY_TOO_LARGE", 413),
        ("UNSUPPORTED_MEDIA", 415),
        ("ORIGIN_FORBIDDEN", 403),
        ("HOST_FORBIDDEN", 403),
        ("WINDOW_LIMIT_EXCEEDED", 400),
        ("QUEUE_FULL", 429),
        ("QUEUE_TIMEOUT", 503),
        ("SERVICE_DISABLED", 503),
        ("SERVICE_STOPPED", 503),
        ("WORKER_NOT_READY", 503),
        ("MODEL_LOAD_FAILED", 500),
        ("MODEL_IDENTITY_CHANGED", 500),
        ("MODEL_SCORING_FAILED", 500),
        ("INVALID_MODEL_OUTPUT", 500),
        ("WORKER_EXITED", 500),
        ("WORKER_PROTOCOL_FAILED", 500),
        ("WORKER_STOP_FAILED", 500),
        ("EVALUATION_TIMEOUT", 504),
        ("CLIENT_DISCONNECTED", None),
        ("LOGGING_FAILED", 500),
        ("INTERNAL_ERROR", 500),
    ],
)
def test_every_closed_error_has_fixed_safe_wording_and_status(
    code: ErrorCode,
    status: int | None,
) -> None:
    assert set(get_args(ErrorCode)) == set(ERROR_POLICIES)
    error = ErrorDetail.from_code(code, "request")
    assert ERROR_POLICIES[code].http_status == status
    assert read_contract(ErrorDetail, error.model_dump(mode="json")) == error
    with pytest.raises(ValidationError, match="message"):
        read_contract(ErrorDetail, {**error.model_dump(mode="json"), "message": "private canary"})
    with pytest.raises(ValidationError):
        read_contract(ErrorDetail, {**error.model_dump(mode="json"), "field": "private canary"})


@pytest.mark.parametrize(
    ("field", "value", "expected_field"),
    [
        ("private-property-canary", "private-value-canary", None),
        ("request_id", "private-id-canary", "request_id"),
        ("source_text", {"private-input-canary": "private-value-canary"}, "source_text"),
    ],
)
def test_validation_projection_discards_unknown_fields_and_input_echoes(
    field: str,
    value: object,
    expected_field: str | None,
) -> None:
    with pytest.raises(ValidationError) as failure:
        read_contract(
            EvaluateRequest, {"source_text": "Source.", "summary_text": "Summary.", field: value}
        )
    error = project_request_error(failure.value)
    assert error.code == "INVALID_REQUEST"
    assert error.field == expected_field
    assert "private" not in error.model_dump_json()


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf"), True, "0.5"])
def test_scores_must_be_finite_numbers_in_the_unit_interval(value: object) -> None:
    with pytest.raises(ValidationError):
        read_contract(EvaluationResult, {**example_result().model_dump(mode="json"), "hhem": value})
    with pytest.raises(ValidationError):
        read_contract(
            WindowOutcome, {**example_window_outcome().model_dump(mode="json"), "score": value}
        )


@pytest.mark.parametrize("score", [0.0, 1.0])
def test_score_boundaries_and_measured_zero_are_valid(score: float) -> None:
    payload = example_result().model_dump(mode="json")
    payload["hhem"] = score
    result = read_contract(EvaluationResult, payload)
    assert result.hhem == score
    assert result.timings_ms.primary_scoring == 0
    assert "window_details" not in result.model_dump(mode="json")
    assert EvaluationResult.model_validate_json(result.model_dump_json()) == result


def full_result_payload(primary: float, full: float) -> dict[str, object]:
    result = example_result().model_dump(mode="json")
    result["effective_settings"]["hhem_full"] = True
    result["hhem"] = primary
    result["hhem_full"] = full
    result["hhem_delta"] = primary - full
    result["windows"]["full"] = {"planned": 1, "scored": 1}
    result["timings_ms"]["full_scoring"] = 0
    return result


@pytest.mark.parametrize(("primary", "full"), [(0.75, 0.25), (0.25, 0.75)])
def test_delta_is_primary_minus_full_in_either_direction(primary: float, full: float) -> None:
    payload = full_result_payload(primary, full)
    result = read_contract(EvaluationResult, payload)
    assert result.hhem_delta == primary - full
    with pytest.raises(ValidationError, match="hhem_delta"):
        read_contract(EvaluationResult, {**payload, "hhem_delta": full - primary})


def test_partial_retains_only_the_completed_primary_score() -> None:
    payload = example_result().model_dump(mode="json")
    payload["status"] = "partial"
    payload["effective_settings"]["hhem_full"] = True
    payload["windows"]["full"] = {"planned": 2, "scored": 1}
    payload["timings_ms"]["full_scoring"] = 7
    payload["errors"] = [
        ErrorDetail.from_code("EVALUATION_TIMEOUT", "full", window_index=1).model_dump(mode="json")
    ]
    partial = read_contract(EvaluationResult, payload)
    assert partial.hhem == 0.75
    assert partial.hhem_full is None
    assert partial.hhem_delta is None
    assert partial.windows.full == WindowCounts(planned=2, scored=1)
    payload["hhem_full"] = 0.5
    payload["hhem_delta"] = 0.25
    with pytest.raises(ValidationError, match="every planned window"):
        read_contract(EvaluationResult, payload)


def test_early_failure_keeps_unknown_values_null() -> None:
    payload = example_result().model_dump(mode="json")
    payload.update(
        {
            "status": "failed",
            "request_id": None,
            "correlation_id": None,
            "hhem": None,
            "effective_settings": None,
            "model": None,
            "worker": None,
            "windows": {"primary": None, "full": None, "full_reused_primary": False},
            "timings_ms": {
                "queue_wait": None,
                "primary_scoring": None,
                "full_scoring": None,
                "total": 0,
            },
            "errors": [ErrorDetail.from_code("INVALID_JSON", "request").model_dump(mode="json")],
        }
    )
    failed = read_contract(EvaluationResult, payload)
    assert failed.windows.primary is None
    assert failed.model is None
    assert failed.timings_ms.queue_wait is None
    assert failed.terminal_event_id is not None
    payload["errors"] = []
    with pytest.raises(ValidationError, match="require errors"):
        read_contract(EvaluationResult, payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "partial"),
        ("status", "failed"),
        ("hhem", None),
        ("errors", [ErrorDetail.from_code("INTERNAL_ERROR", "request").model_dump(mode="json")]),
        ("terminal_event_id", None),
        ("hhem_full", 0.5),
        ("hhem_delta", 0.25),
        ("effective_settings", None),
        ("request_id", None),
        ("correlation_id", None),
        ("model", None),
        ("worker", None),
        ("window_details", None),
        ("version", "2026-11-03"),
        ("source_text", "private-response-canary"),
    ],
)
def test_inconsistent_or_text_bearing_complete_results_are_rejected(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        read_contract(EvaluationResult, {**example_result().model_dump(mode="json"), field: value})


def test_logging_failure_has_no_fictional_terminal_event_link() -> None:
    payload = example_result().model_dump(mode="json")
    payload.update(
        {
            "status": "partial",
            "terminal_event_id": None,
            "errors": [ErrorDetail.from_code("LOGGING_FAILED", "request").model_dump(mode="json")],
        }
    )
    assert read_contract(EvaluationResult, payload).hhem == 0.75
    payload["terminal_event_id"] = create_event_id(EXECUTION_ID, 4)
    with pytest.raises(ValidationError, match="terminal_event_id"):
        read_contract(EvaluationResult, payload)
    payload["errors"] = [
        ErrorDetail.from_code("CLIENT_DISCONNECTED", "request").model_dump(mode="json")
    ]
    with pytest.raises(ValidationError, match="terminal event"):
        read_contract(EvaluationResult, payload)


def test_requested_full_comparison_must_finish_before_complete() -> None:
    payload = example_result().model_dump(mode="json")
    payload["effective_settings"]["hhem_full"] = True
    with pytest.raises(ValidationError, match="requested full"):
        read_contract(EvaluationResult, payload)


def test_full_reuse_reports_logical_windows_without_additional_work() -> None:
    payload = example_result().model_dump(mode="json")
    payload["effective_settings"]["hhem_full"] = True
    payload["effective_settings"]["include_window_details"] = True
    payload["hhem_full"] = payload["hhem"]
    payload["hhem_delta"] = 0
    payload["windows"]["full"] = {"planned": 1, "scored": 0}
    payload["windows"]["full_reused_primary"] = True
    detail = {"index": 0, "start_word": 0, "end_word": 4, "score": payload["hhem"]}
    payload["window_details"] = {"primary": [detail], "full": [detail]}
    result = read_contract(EvaluationResult, payload)
    assert result.timings_ms.full_scoring is None
    assert result.window_details is not None
    assert result.window_details.primary == result.window_details.full
    for change in ({"planned": 2, "scored": 0}, {"planned": 1, "scored": 1}):
        invalid = json.loads(json.dumps(payload))
        invalid["windows"]["full"] = change
        with pytest.raises(ValidationError, match="Full reuse"):
            read_contract(EvaluationResult, invalid)
    payload["window_details"]["full"] = []
    with pytest.raises(ValidationError, match="mirror"):
        read_contract(EvaluationResult, payload)


@pytest.mark.parametrize(
    ("counts", "details"),
    [
        ({"planned": 1, "scored": 2}, []),
        ({"planned": 0, "scored": 0}, []),
        ({"planned": 1, "scored": 1}, []),
        (
            {"planned": 1, "scored": 1},
            [{"index": 1, "start_word": 0, "end_word": 4, "score": 0.75}],
        ),
        (
            {"planned": 1, "scored": 1},
            [{"index": 0, "start_word": 4, "end_word": 4, "score": 0.75}],
        ),
    ],
)
def test_details_and_counts_describe_only_completed_valid_windows(
    counts: object,
    details: object,
) -> None:
    payload = example_result().model_dump(mode="json")
    payload["effective_settings"]["include_window_details"] = True
    payload["windows"]["primary"] = counts
    payload["window_details"] = {"primary": details, "full": None}
    with pytest.raises(ValidationError):
        read_contract(EvaluationResult, payload)


@pytest.mark.parametrize(
    "field", ["loaded_weights_sha256", "loaded_config_sha256", "service_config_sha256"]
)
def test_runtime_model_identity_does_not_accept_removed_fingerprints(field: str) -> None:
    payload = example_model().model_dump(mode="json")
    assert field not in payload
    assert field not in ModelIdentity.model_json_schema()["properties"]
    payload[field] = "f" * 64
    with pytest.raises(ValidationError):
        read_contract(ModelIdentity, payload)


@pytest.mark.parametrize(
    ("ticks", "reason"), [(None, None), ("123", "process_not_found"), (123, None), ("-1", None)]
)
def test_worker_pin_does_not_invent_missing_observations(ticks: object, reason: object) -> None:
    with pytest.raises(ValidationError):
        read_contract(
            WorkerIdentity,
            {"generation": 1, "pid": 1234, "start_ticks": ticks, "pin_unavailable_reason": reason},
        )


@pytest.mark.parametrize(
    "status", ["disabled", "loading", "ready", "replacing", "stopping", "failed"]
)
def test_health_status_matches_observed_readiness(status: str) -> None:
    payload: dict[str, object] = {
        "version": SCHEMA_VERSION,
        "service_instance_id": EXECUTION_ID,
        "status": status,
        "worker": None,
        "model": None,
        "queue_depth": 0,
        "queue_capacity": 8,
        "failure_code": None,
    }
    if status == "ready":
        with pytest.raises(ValidationError, match="Ready"):
            read_contract(ServiceHealth, payload)
        payload["worker"] = example_worker().model_dump(mode="json")
        payload["model"] = example_model().model_dump(mode="json")
    elif status == "failed":
        payload["failure_code"] = "MODEL_LOAD_FAILED"
    health = read_contract(ServiceHealth, payload)
    assert health.http_status == (200 if status == "ready" else 503)
    payload["queue_depth"] = 9
    with pytest.raises(ValidationError, match="queue_depth"):
        read_contract(ServiceHealth, payload)


def test_native_events_round_trip_with_utc_and_bounded_json_lines() -> None:
    event = example_event()
    assert EvaluationEvent.model_validate_json(event.model_dump_json()) == event
    encoded = event.encode_json_line(load_settings(SETTINGS_FILE).logging.max_event_bytes)
    assert encoded.endswith(b"\n")
    assert json.loads(encoded)["details"] == {}
    assert event.encode_json_line(len(encoded)) == encoded
    with pytest.raises(ValueError, match="max_event_bytes"):
        event.encode_json_line(len(encoded) - 1)


def test_measured_event_errors_and_result_details_survive_native_json_reading() -> None:
    error = ErrorDetail.from_code("MODEL_SCORING_FAILED", "primary", window_index=0)
    details = EventDetails(
        window_index=0, window_count=1, scored_window_count=0, duration_ms=0, errors=(error,)
    )
    assert EventDetails.model_validate_json(details.model_dump_json()) == details
    payload = example_result().model_dump(mode="json")
    payload["effective_settings"]["include_window_details"] = True
    payload["window_details"] = {
        "primary": [{"index": 0, "start_word": 0, "end_word": 4, "score": payload["hhem"]}],
        "full": None,
    }
    result = read_contract(EvaluationResult, payload)
    assert result.window_details is not None
    assert EvaluationResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", create_event_id(EXECUTION_ID, 2)),
        ("sequence", 0),
        ("sequence", True),
        ("sequence", "1"),
        ("sequence", 1.0),
        ("operation_id", "not-a-uuid"),
        ("operation", "inference"),
        ("phase", "ready"),
        ("occurred_at", "2026-11-02T09:00:00+01:00"),
        ("occurred_at", "2026-11-02T08:00:00"),
        ("source_text", "private-event-canary"),
        ("details", {"exception": "private-exception-canary"}),
        ("details", {"private-property-canary": 1}),
        ("details", {"score": None}),
        ("details", {"score": "0.5"}),
        ("details", {"duration_ms": -1}),
        ("details", {"window_count": 1, "scored_window_count": 2}),
        ("details", {"window_count": 1, "window_index": 1}),
        ("details", {"errors": []}),
        ("run_id", "private\ncontext"),
        ("version", "2026-11-03"),
    ],
)
def test_invalid_event_identities_details_and_text_are_rejected(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        read_contract(EvaluationEvent, {**example_event().model_dump(mode="json"), field: value})


def test_root_starts_and_comparison_causes_are_distinct() -> None:
    payload = example_event().model_dump(mode="json")
    payload["caused_by_event_id"] = create_event_id(EXECUTION_ID, 2)
    with pytest.raises(ValidationError, match="Root"):
        read_contract(EvaluationEvent, payload)
    payload["operation"] = "primary"
    payload["event_id"] = create_event_id(EXECUTION_ID, 3)
    payload["sequence"] = 3
    assert read_contract(EvaluationEvent, payload).caused_by_event_id is not None
    payload["caused_by_event_id"] = None
    with pytest.raises(ValidationError, match="initiating cause"):
        read_contract(EvaluationEvent, payload)


def test_bootstrap_freezes_settings_assets_and_private_context() -> None:
    settings = load_settings(SETTINGS_FILE)
    bootstrap = WorkerBootstrap(
        version=SCHEMA_VERSION,
        kind="bootstrap",
        settings=settings,
        assets=FrozenAssets(model=settings.hhem.model, foundation=settings.hhem.foundation),
        context=StartupContext(run_id="12345", pipeline_name="hhem-test", task_name="score"),
    )
    assert WorkerCommand.model_validate_json(bootstrap.model_dump_json()).root == bootstrap
    payload = bootstrap.model_dump(mode="json")
    payload["assets"]["model"]["revision"] = "0" * 40
    with pytest.raises(ValidationError, match="frozen startup settings"):
        read_contract(WorkerBootstrap, payload)
    payload = bootstrap.model_dump(mode="json")
    payload["source_text"] = "private-bootstrap-canary"
    with pytest.raises(ValidationError):
        read_contract(WorkerBootstrap, payload)


def test_worker_identity_readiness_and_failure_are_separate_native_packets() -> None:
    worker = example_worker()
    started = WorkerStarted(version=SCHEMA_VERSION, kind="worker_started", worker=worker)
    ready = WorkerReady(version=SCHEMA_VERSION, kind="ready", worker=worker, model=example_model())
    failed = WorkerFailed(
        version=SCHEMA_VERSION,
        kind="worker_failed",
        worker=worker,
        error=ErrorDetail.from_code("MODEL_LOAD_FAILED", "worker"),
    )
    for packet in (started, ready, failed):
        assert WorkerReply.model_validate_json(packet.model_dump_json()).root == packet
    payload = ready.model_dump(mode="json")
    payload["model"] = None
    with pytest.raises(ValidationError):
        WorkerReply.model_validate_json(json.dumps(payload))
    payload = failed.model_dump(mode="json")
    payload["error"] = ErrorDetail.from_code(
        "MODEL_LOAD_FAILED", "primary", window_index=0
    ).model_dump(mode="json")
    with pytest.raises(ValidationError, match="worker phase"):
        read_contract(WorkerFailed, payload)


def test_private_command_is_the_only_text_bearing_outbound_packet() -> None:
    command = example_command()
    outcome = example_window_outcome()
    assert WorkerCommand.model_validate_json(command.model_dump_json()).root == command
    assert WorkerReply.model_validate_json(outcome.model_dump_json()).root == outcome
    assert "source canary" in command.model_dump_json()
    for packet in (outcome, example_result(), example_event()):
        assert "source canary" not in packet.model_dump_json()
        assert "summary canary" not in packet.model_dump_json()
    validate_window_reply(command, outcome)


@pytest.mark.parametrize(
    ("reader", "example"),
    [(WorkerCommand, example_command), (WorkerReply, example_window_outcome)],
)
def test_packet_readers_preserve_the_envelope_and_reject_unknown_protocol_values(
    reader: type[WorkerCommand] | type[WorkerReply],
    example: Callable[[], NativeContract],
) -> None:
    packet = example()
    decoded = reader.model_validate_json(packet.model_dump_json())
    assert decoded.root == packet
    assert json.loads(decoded.model_dump_json()) == json.loads(packet.model_dump_json())
    schema = reader.model_json_schema()
    assert schema["version"] == SCHEMA_VERSION
    assert schema["changelog"] == NativeContract.model_json_schema()["changelog"]
    for field, value in (
        ("kind", "unknown_packet"),
        ("version", "2026-11-03"),
        ("private-unknown-property", "private-value-canary"),
    ):
        with pytest.raises(ValidationError):
            reader.model_validate_json(json.dumps({**packet.model_dump(mode="json"), field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "window_failed"),
        ("score", None),
        ("score", -1),
        ("scoring_ms", -1),
        (
            "error",
            ErrorDetail.from_code("MODEL_SCORING_FAILED", "primary", window_index=0).model_dump(
                mode="json"
            ),
        ),
        ("source_text", "private-packet-canary"),
        ("version", "2026-11-03"),
        ("end_word", 0),
    ],
)
def test_inconsistent_window_outcomes_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        read_contract(
            WindowOutcome, {**example_window_outcome().model_dump(mode="json"), field: value}
        )


def test_failed_window_has_no_score_and_matches_its_error_identity() -> None:
    payload = example_window_outcome().model_dump(mode="json")
    payload.update(
        {
            "kind": "window_failed",
            "score": None,
            "error": ErrorDetail.from_code(
                "MODEL_SCORING_FAILED", "primary", window_index=0
            ).model_dump(mode="json"),
        }
    )
    assert read_contract(WindowOutcome, payload).score is None
    payload["error"]["window_index"] = 1
    with pytest.raises(ValidationError, match="window identity"):
        read_contract(WindowOutcome, payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_id", "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"),
        ("generation", 2),
        ("comparison", "full"),
        ("window_index", 1),
        ("start_word", 1),
        ("end_word", 5),
    ],
)
def test_reply_must_match_every_part_of_the_outstanding_command(
    field: str,
    value: object,
) -> None:
    payload = example_window_outcome().model_dump(mode="json")
    payload[field] = value
    outcome = read_contract(WindowOutcome, payload)
    with pytest.raises(ValueError, match="outstanding command"):
        validate_window_reply(example_command(), outcome)


def test_valid_body_free_native_examples_have_no_input_fields() -> None:
    examples: tuple[Callable[[], NativeContract], ...] = (
        example_result,
        example_event,
        example_model,
        example_worker,
        example_window_outcome,
    )
    for example in examples:
        payload = example().model_dump_json()
        assert "source_text" not in payload
        assert "summary_text" not in payload
        assert "full_source_text" not in payload
