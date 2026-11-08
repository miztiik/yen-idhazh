"""Verify private packet versions, exact reply operations and complete serialized byte bounds."""

import io
import json

import pytest
from local_api_host.propagate_trace_context import (
    OperationLink,
    create_child_operation,
    create_root_operation,
)
from pydantic import ValidationError
from summary_evaluator_cases.contract_examples import (
    EXAMPLE_OPERATION,
    REPOSITORY,
    example_command,
    example_window_outcome,
)
from summary_evaluator_cases.service_cases import service_settings

from summary_evaluator.hhem.contracts.base import SCHEMA_VERSION
from summary_evaluator.hhem.contracts.worker_contract import HHEM_WORKER_VERSION
from summary_evaluator.hhem.contracts.worker_message import (
    FrozenAssets,
    ScoreWindow,
    WindowOutcome,
    WorkerBootstrap,
    WorkerCommand,
    WorkerFailed,
    WorkerReady,
    WorkerStarted,
    validate_window_reply,
)
from summary_evaluator.hhem.exchange_packets import command_byte_limit, reply_byte_limit
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData, ServerEvent
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.shared.bound_operation_metadata import maximum_worker_operation_metadata
from summary_evaluator.shared.contracts.base import NativeContract
from summary_evaluator.shared.contracts.service_settings import LoggingSettings, StartupContext
from summary_evaluator.shared.exchange_packets import UUID4_EXAMPLE, encode_packet
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.unieval.contracts.unieval_contract import UNIEVAL_VERSION
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_worker_contract import UNIEVAL_WORKER_VERSION
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    UnievalBootstrap,
    UnievalCommand,
    UnievalFinished,
    UnievalPrediction,
    UnievalPrepared,
    UnievalReady,
    UnievalStartupFailed,
    validate_request_reply,
)
from summary_evaluator.unieval.exchange_packets import command_byte_limit as unieval_command_limit


@pytest.mark.parametrize(
    "contract",
    [
        WorkerBootstrap,
        WorkerStarted,
        WorkerReady,
        WorkerFailed,
        ScoreWindow,
        WindowOutcome,
        UnievalBootstrap,
        UnievalReady,
        UnievalStartupFailed,
        UnievalCommand,
        UnievalPrepared,
        UnievalPrediction,
        UnievalFinished,
    ],
)
def test_private_worker_dates_do_not_reversion_public_scores(
    contract: type[NativeContract],
) -> None:
    schema = contract.model_json_schema()
    assert schema["version"] == HHEM_WORKER_VERSION == UNIEVAL_WORKER_VERSION == "2026-11-08"
    assert schema["properties"]["version"]["const"] == schema["version"]
    assert "operation_metadata" in schema["required"]
    assert "replace old owned processes" in schema["readCompatibility"]
    assert schema["changelog"][0]["version"] == schema["version"]
    assert SCHEMA_VERSION == "2026-11-02" and UNIEVAL_VERSION == "2026-11-04"


def test_complete_escaped_metadata_and_record_newline_stay_inside_the_existing_event_bound() -> (
    None
):
    settings = service_settings()
    operation = maximum_worker_operation_metadata()
    event = ServerEvent.diagnostic(
        ApiDiagnosticData(component="api", action="failed", level="WARNING", code="X"),
        operation,
        propagate_trace_context=True,
    )
    initial_bytes = len((event.model_dump_json() + "\n").encode())
    event = event.model_copy(
        update={
            "data": event.data.model_copy(
                update={"code": "X" * (settings.logging.max_event_bytes - initial_bytes + 1)}
            )
        }
    )
    event = ServerEvent.model_validate_json(event.model_dump_json())
    encoded = (event.model_dump_json() + "\n").encode("utf-8")
    assert len(encoded) == settings.logging.max_event_bytes
    assert event.encode_json_line(len(encoded)) == encoded
    stream = io.StringIO()
    writer = EventWriter(
        LoggingSettings(level="INFO", max_event_bytes=len(encoded)),
        stream,
        service_operation=operation,
        propagate_trace_context=True,
    )
    writer.write_server_event(event, operation)
    assert stream.getvalue().encode() == encoded
    overflow = EventWriter(
        LoggingSettings(level="INFO", max_event_bytes=len(encoded) - 1),
        io.StringIO(),
        service_operation=operation,
        propagate_trace_context=True,
    )
    with pytest.raises(RuntimeFailure) as failure:
        overflow.write_server_event(event, operation)
    assert failure.value.code == "LOGGING_FAILED"


def test_current_commands_bound_every_metadata_byte_and_reject_one_byte_over() -> None:
    settings = service_settings()
    operation = maximum_worker_operation_metadata()
    bootstrap = WorkerBootstrap(
        version=HHEM_WORKER_VERSION,
        operation_metadata=operation,
        kind="bootstrap",
        settings=settings,
        assets=FrozenAssets(model=settings.hhem.model, foundation=settings.hhem.foundation),
        context=StartupContext(),
    )
    command = example_command().model_copy(update={"operation_metadata": operation})
    outcome = example_window_outcome().model_copy(update={"operation_metadata": operation})
    for packet in (bootstrap, command, outcome):
        encoded = packet.model_dump_json().encode("utf-8")
        assert encode_packet(packet, len(encoded)) == encoded
        with pytest.raises(ValueError, match="byte limit"):
            encode_packet(packet, len(encoded) - 1)
    maximum = ScoreWindow(
        version=HHEM_WORKER_VERSION,
        operation_metadata=operation,
        kind="score_window",
        execution_id=UUID4_EXAMPLE,
        generation=1,
        comparison="primary",
        window_index=settings.listener.max_body_bytes,
        start_word=settings.listener.max_body_bytes,
        end_word=settings.listener.max_body_bytes + 1,
        source_text="\x00" * (settings.listener.max_body_bytes - 1) + "xxxxx",
        summary_text="x",
    )
    command_limit = command_byte_limit(bootstrap, 1)
    assert len(encode_packet(maximum, command_limit)) == command_limit
    one_over = maximum.model_copy(update={"source_text": maximum.source_text + "x"})
    with pytest.raises(ValueError, match="byte limit"):
        encode_packet(one_over, command_limit)
    assert len(encode_packet(outcome, reply_byte_limit(bootstrap, 1))) <= (
        reply_byte_limit(bootstrap, 1)
    )
    api = load_scorer_api_settings(REPOSITORY / "config" / "summary-evals" / "api.json", "unieval")
    selected = load_unieval_settings(REPOSITORY, api)
    unieval = UnievalCommand(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=operation,
        execution_id=UUID4_EXAMPLE,
        generation=1,
        request=UnievalRequest(source_text="x", summary_text="y", reference_summary_text="z"),
    )
    encoded = unieval.model_dump_json().encode()
    assert encode_packet(unieval, len(encoded)) == encoded
    with pytest.raises(ValueError, match="byte limit"):
        encode_packet(unieval, len(encoded) - 1)
    assert len(encode_packet(unieval, unieval_command_limit(selected, 1))) <= (
        unieval_command_limit(selected, 1)
    )
    finished = UnievalFinished(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=operation,
        execution_id=unieval.execution_id,
        generation=1,
    )
    reply_limit = len(finished.model_dump_json().encode())
    selected = type(selected).model_validate_json(
        selected.model_copy(
            update={"worker": selected.worker.model_copy(update={"max_reply_bytes": reply_limit})}
        ).model_dump_json()
    )
    assert len(encode_packet(finished, selected.worker.max_reply_bytes)) == reply_limit
    with pytest.raises(ValueError, match="byte limit"):
        encode_packet(
            finished.model_copy(update={"generation": 10}), selected.worker.max_reply_bytes
        )


@pytest.mark.parametrize("mutation", ["context", "state", "generation", "window", "version"])
def test_real_window_validator_rejects_crossed_or_stale_replies(mutation: str) -> None:
    command = example_command()
    payload = example_window_outcome().model_dump(mode="json")
    if mutation == "context":
        payload["operation_metadata"] = create_child_operation(create_root_operation()).model_dump(
            mode="json"
        )
    elif mutation == "state":
        payload["operation_metadata"]["traceState"] = "changed=value"
    elif mutation == "generation":
        payload["generation"] += 1
    elif mutation == "window":
        payload["window_index"] += 1
    else:
        payload["version"] = SCHEMA_VERSION
    with pytest.raises((ValidationError, ValueError)):
        outcome = WindowOutcome.model_validate_json(json.dumps(payload))
        validate_window_reply(command, outcome)


def test_real_unieval_validator_rejects_a_previous_operation_even_with_equal_caller_identity() -> (
    None
):
    command = UnievalCommand(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=EXAMPLE_OPERATION,
        execution_id=UUID4_EXAMPLE,
        generation=1,
        request=UnievalRequest(source_text="x", summary_text="y", reference_summary_text="z"),
    )
    finished = UnievalFinished(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=command.operation_metadata,
        execution_id=command.execution_id,
        generation=command.generation,
    )
    validate_request_reply(command, finished)
    next_command = command.model_copy(
        update={"operation_metadata": create_child_operation(command.operation_metadata)}
    )
    with pytest.raises(ValueError, match="outstanding command"):
        validate_request_reply(next_command, finished)
    stale = finished.model_copy(update={"generation": 2})
    with pytest.raises(ValueError, match="outstanding command"):
        validate_request_reply(command, stale)


def test_private_packet_reader_requires_metadata_and_its_bounded_recovery_link() -> None:
    payload = example_command().model_dump(mode="json")
    del payload["operation_metadata"]
    with pytest.raises(ValidationError):
        WorkerCommand.model_validate_json(json.dumps(payload))
    operation = create_root_operation(
        links=(
            OperationLink(trace_id="1" * 32, span_id="2" * 16),
            OperationLink(trace_id="3" * 32, span_id="4" * 16),
        )
    )
    payload["operation_metadata"] = operation.model_dump(mode="json")
    with pytest.raises(ValidationError, match="failed active attempt"):
        WorkerCommand.model_validate_json(json.dumps(payload))


def test_live_emission_cannot_use_reader_optionality_or_another_operation() -> None:
    operation = create_root_operation()
    data = ApiDiagnosticData(component="api", action="started", level="INFO")
    event = ServerEvent.diagnostic(data)
    writer = EventWriter(
        LoggingSettings(level="INFO", max_event_bytes=4096),
        io.StringIO(),
        service_operation=operation,
        propagate_trace_context=True,
    )
    with pytest.raises(RuntimeFailure) as failure:
        writer.write_server_event(event, operation)
    assert failure.value.code == "LOGGING_FAILED"
    event = ServerEvent.diagnostic(
        data,
        create_child_operation(operation),
        propagate_trace_context=True,
    )
    with pytest.raises(RuntimeFailure):
        writer.write_server_event(event, operation)
