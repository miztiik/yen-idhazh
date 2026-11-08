"""Prove actual receiving and owned-worker carriers without substituting scorer logic."""

import io
import json
import multiprocessing
from collections.abc import Coroutine
from typing import Any

import pytest
from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_child_operation,
    create_root_operation,
    write_trace_context,
)
from starlette.requests import Request
from starlette.types import Message, Scope
from summary_evaluator_cases.contract_examples import API_SETTINGS_FILE, REPOSITORY
from summary_evaluator_cases.replay_predictions import (
    Scenario,
    read_recordings,
    run_recorded_worker,
)
from summary_evaluator_cases.service_cases import service_settings

from summary_evaluator.hhem.contracts.worker_contract import HHEM_WORKER_VERSION
from summary_evaluator.hhem.contracts.worker_message import (
    FrozenAssets,
    ScoreWindow,
    WindowOutcome,
    WorkerBootstrap,
    WorkerReply,
    validate_window_reply,
)
from summary_evaluator.hhem.dispatch_evaluation import dispatch_evaluation
from summary_evaluator.hhem.exchange_packets import command_byte_limit, reply_byte_limit
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData, ServerEvent
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.contracts.api_paths import (
    API_HEALTH_PATH,
    API_SCHEMA_PATH,
    EVALUATE_PATH,
)
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH

CALLER = OperationMetadata(
    trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    span_id="00f067aa0ba902b7",
    links=(),
    trace_state="first=value,second=other",
)


def finish_inline(coroutine: Coroutine[Any, Any, object]) -> None:
    """Drive ASGI refusal paths that require no event loop or background work."""
    try:
        coroutine.send(None)
    except StopIteration:
        return
    finally:
        coroutine.close()
    raise AssertionError("The body-free refusal unexpectedly required asynchronous work")


def call_api_inline(
    scorer: ApiComponent,
    carrier: dict[str, str],
    *,
    method: str = "POST",
    path: str | None = None,
    enabled: bool | None = None,
    stream: io.StringIO | None = None,
) -> tuple[list[Message], list[ServerEvent], OperationMetadata | None]:
    api = load_scorer_api_settings(API_SETTINGS_FILE, scorer)
    if enabled is not None:
        api = type(api).model_validate_json(
            api.model_copy(update={"propagate_trace_context": enabled}).model_dump_json()
        )
    stream = stream if stream is not None else io.StringIO()
    app = create_app(
        api,
        service_settings() if scorer == "hhem" else None,
        REPOSITORY,
        writer=EventWriter(
            api.logging, stream, propagate_trace_context=api.propagate_trace_context
        ),
        unieval_settings=load_unieval_settings(REPOSITORY, api) if scorer == "unieval" else None,
    )
    selected_path = path or (EVALUATE_PATH if scorer == "hhem" else UNIEVAL_PATH)
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": selected_path,
        "raw_path": selected_path.encode(),
        "query_string": b"",
        "headers": [
            (b"host", f"{api.listener.host}:{api.listener.port}".encode()),
            *[(key.encode(), value.encode()) for key, value in carrier.items()],
        ],
        "client": ("127.0.0.1", 1),
        "server": (api.listener.host, api.listener.port),
    }
    messages: list[Message] = []

    async def receive() -> Message:
        raise AssertionError("An unready scorer must refuse before reading the body")

    async def send(message: Message) -> None:
        messages.append(message)

    try:
        finish_inline(app(scope, receive, send))
        operation = scope["state"]["operation_metadata"]
        assert operation is None or isinstance(operation, OperationMetadata)
        assert isinstance(scope["state"]["request_started_at"], float)
        events = [ServerEvent.model_validate_json(line) for line in stream.getvalue().splitlines()]
        return messages, events, operation
    finally:
        app.state.events.close()


@pytest.mark.parametrize("scorer", ["hhem", "unieval"])
def test_receiving_operation_reaches_native_refusal_and_actual_response(
    scorer: ApiComponent,
) -> None:
    messages, events, operation = call_api_inline(scorer, write_trace_context(CALLER))
    assert messages[0]["status"] == 503
    headers = {key.decode(): value.decode() for key, value in messages[0]["headers"]}
    assert "traceparent" in headers
    assert isinstance(operation, OperationMetadata)
    assert operation.trace_id == CALLER.trace_id
    assert operation.parent_span_id == CALLER.span_id
    assert operation.span_id != CALLER.span_id
    assert operation.trace_state == CALLER.trace_state
    assert {key: headers[key] for key in write_trace_context(operation)} == (
        write_trace_context(operation)
    )
    assert events
    terminal = events[-1]
    assert terminal.traceparent == headers["traceparent"]
    assert terminal.tracestate == headers["tracestate"]


@pytest.mark.parametrize("scorer", ["hhem", "unieval"])
@pytest.mark.parametrize("invalid", ["parent", "state", "orphan", "long-state"])
def test_invalid_optional_carriers_keep_native_refusals_and_never_log_raw_text(
    scorer: ApiComponent, invalid: str, caplog: pytest.LogCaptureFixture
) -> None:
    canary = "PrivateInvalidTraceStateCanary"
    carrier = write_trace_context(CALLER)
    if invalid == "parent":
        carrier["traceparent"] = canary
    elif invalid == "state":
        carrier["tracestate"] = canary
    elif invalid == "orphan":
        del carrier["traceparent"]
        carrier["tracestate"] = canary
    else:
        carrier["tracestate"] = "a=" + "x" * 256 + ",b=" + "y" * 256
    messages, events, operation = call_api_inline(scorer, carrier)
    assert messages[0]["status"] == 503
    assert isinstance(operation, OperationMetadata)
    assert operation.trace_state is None
    if invalid in ("state", "long-state"):
        assert operation.trace_id == CALLER.trace_id
        assert operation.parent_span_id == CALLER.span_id
    else:
        assert operation.parent_span_id is None and operation.trace_id != CALLER.trace_id
    headers = {key.decode(): value.decode() for key, value in messages[0]["headers"]}
    assert headers["traceparent"] == write_trace_context(operation)["traceparent"]
    assert "tracestate" not in headers
    warnings = [
        event
        for event in events
        if isinstance(event.data, ApiDiagnosticData) and event.data.code == "INVALID_TRACE_CONTEXT"
    ]
    assert len(warnings) == 1
    assert warnings[0].traceparent == headers["traceparent"]
    assert canary not in caplog.text
    assert all(canary not in event.model_dump_json() for event in events)


@pytest.mark.parametrize("enabled", [False, True])
def test_the_same_config_flag_changes_actual_http_and_event_carriers(enabled: bool) -> None:
    messages, events, operation = call_api_inline(
        "hhem", write_trace_context(CALLER), enabled=enabled
    )
    headers = {key.decode(): value.decode() for key, value in messages[0]["headers"]}
    assert messages[0]["status"] == 503
    assert ("traceparent" in headers) is enabled
    assert all((event.traceparent is not None) is enabled for event in events)
    assert (operation is not None) is enabled


@pytest.mark.parametrize("path", [API_HEALTH_PATH, API_SCHEMA_PATH, "/unknown"])
def test_read_and_unknown_routes_have_actual_receiving_carriers_without_scoring_events(
    path: str,
) -> None:
    messages, events, operation = call_api_inline(
        "hhem", write_trace_context(CALLER), method="GET", path=path
    )
    assert isinstance(operation, OperationMetadata)
    headers = {key.decode(): value.decode() for key, value in messages[0]["headers"]}
    assert headers["traceparent"] == write_trace_context(operation)["traceparent"]
    assert headers["tracestate"] == CALLER.trace_state
    assert not events


def test_native_allow_and_guard_refusals_keep_their_receiving_operations() -> None:
    messages, events, operation = call_api_inline("hhem", write_trace_context(CALLER), method="GET")
    headers = {key.decode(): value.decode() for key, value in messages[0]["headers"]}
    assert messages[0]["status"] == 405 and headers["allow"] == "POST"
    assert isinstance(operation, OperationMetadata)
    assert headers["traceparent"] == write_trace_context(operation)["traceparent"]
    assert not events
    messages, events, operation = call_api_inline(
        "hhem", {**write_trace_context(CALLER), "origin": "https://example.test"}
    )
    assert messages[0]["status"] == 403
    assert isinstance(operation, OperationMetadata)
    assert events[-1].traceparent == write_trace_context(operation)["traceparent"]


class UnwritableStream(io.StringIO):
    def write(self, text: str) -> int:
        raise OSError("PrivateStderrFailureCanary")


@pytest.mark.parametrize("scorer", ["hhem", "unieval"])
def test_required_warning_delivery_failure_keeps_native_errors_and_actual_response_carrier(
    scorer: ApiComponent,
) -> None:
    messages, _, operation = call_api_inline(
        scorer,
        {"traceparent": write_trace_context(CALLER)["traceparent"], "tracestate": "invalid"},
        stream=UnwritableStream(),
    )
    assert messages[0]["status"] == 500
    headers = {key.decode(): value.decode() for key, value in messages[0]["headers"]}
    assert isinstance(operation, OperationMetadata)
    assert headers["traceparent"] == write_trace_context(operation)["traceparent"]
    body = json.loads(b"".join(message.get("body", b"") for message in messages[1:]))
    assert body["status"] == "failed"
    assert body["errors"][0]["code"] == "LOGGING_FAILED"
    assert "PrivateStderrFailureCanary" not in json.dumps(body)


def test_enabled_dispatcher_does_not_allocate_a_replacement_for_missing_host_state() -> None:
    api = load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
    writer = EventWriter(api.logging, io.StringIO())
    app = create_app(api, service_settings(), REPOSITORY, writer=writer)
    request = Request({"type": "http", "headers": [], "state": {}})
    with pytest.raises(RuntimeError, match="host receiving operation"):
        finish_inline(dispatch_evaluation(request, app.state.controller))
    writer.close()


def test_owned_hhem_worker_returns_issued_operation_on_real_byte_pipes() -> None:
    settings = service_settings()
    inputs, predictions, _ = read_recordings(REPOSITORY)
    case = inputs.cases[0]
    bootstrap = WorkerBootstrap(
        version=HHEM_WORKER_VERSION,
        operation_metadata=create_child_operation(create_root_operation()),
        kind="bootstrap",
        settings=settings,
        assets=FrozenAssets(model=settings.hhem.model, foundation=settings.hhem.foundation),
        context=StartupContext(),
    )
    command = ScoreWindow(
        version=HHEM_WORKER_VERSION,
        operation_metadata=create_child_operation(create_child_operation(CALLER)),
        kind="score_window",
        execution_id=create_execution_id(),
        generation=1,
        comparison="primary",
        window_index=0,
        start_word=0,
        end_word=len(case.source_text.split()),
        source_text=case.source_text,
        summary_text=case.summary_text,
    )
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    owner_read, owner_write = context.Pipe(duplex=False)
    control, child_control = context.Pipe(duplex=True)
    process = context.Process(
        target=run_recorded_worker,
        args=(
            child,
            owner_read,
            REPOSITORY,
            1,
            command_byte_limit(bootstrap, 1),
            child_control,
            Scenario(),
        ),
        daemon=False,
    )
    try:
        process.start()
        child.close()
        owner_read.close()
        child_control.close()
        parent.send_bytes(bootstrap.model_dump_json().encode())
        for _ in range(2):
            assert parent.poll(15), "The owned worker did not report startup"
            reply = WorkerReply.model_validate_json(
                parent.recv_bytes(reply_byte_limit(bootstrap, 1))
            ).root
            assert reply.operation_metadata == bootstrap.operation_metadata
        assert control.poll(15)
        assert json.loads(control.recv_bytes())["phase"] == "loading"
        parent.send_bytes(command.model_dump_json().encode())
        assert parent.poll(15), "The actual model boundary did not return a recorded score"
        encoded = parent.recv_bytes(reply_byte_limit(bootstrap, 1))
        outcome = WorkerReply.model_validate_json(encoded).root
        assert isinstance(outcome, WindowOutcome)
        assert outcome.score == predictions.cases[0].score
        assert "operation_metadata" in json.loads(encoded)
        assert outcome.operation_metadata == command.operation_metadata
        validate_window_reply(command, outcome)
    finally:
        owner_write.close()
        if process.pid is not None:
            process.join(settings.worker.shutdown_timeout_ms / 1000)
            if process.is_alive():
                process.kill()
                process.join(settings.worker.forced_stop_ms / 1000)
            assert not process.is_alive()
        process.close()
        parent.close()
        child.close()
        owner_read.close()
        control.close()
        child_control.close()
