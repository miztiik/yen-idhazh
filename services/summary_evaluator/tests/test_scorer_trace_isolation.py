"""Do independent APIs retain real receiving, nested and worker contexts for concurrent callers?"""

import asyncio
import io
import logging
import multiprocessing
from dataclasses import dataclass, field

import httpx
from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_child_operation,
    create_root_operation,
    write_trace_context,
)
from starlette.types import ASGIApp, Receive, Scope, Send
from summary_evaluator_cases.contract_examples import (
    API_SETTINGS_FILE,
    CORRELATION_ID,
    REPOSITORY,
    REQUEST_ID,
)
from summary_evaluator_cases.replay_predictions import Scenario, read_recordings
from summary_evaluator_cases.service_cases import RecordedSupervisor, service_settings
from summary_evaluator_cases.unieval_cases import (
    RecordedUnievalSupervisor,
    UnievalScenario,
    read_unieval_recordings,
    recorded_unieval_request,
    run_recorded_unieval_worker,
    unieval_settings,
)

from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent
from summary_evaluator.hhem.contracts.worker_message import ScoreWindow, WindowOutcome
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData, ServerEvent
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.contracts.api_paths import EVALUATE_PATH
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.unieval.contracts.unieval_contract import DIMENSIONS
from summary_evaluator.unieval.contracts.unieval_worker_contract import UNIEVAL_WORKER_VERSION
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    RequestPacket,
    UnievalBootstrap,
    UnievalCommand,
    UnievalFinished,
    UnievalReady,
    UnievalReply,
    validate_request_reply,
)
from summary_evaluator.unieval.exchange_packets import command_byte_limit
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH


class ObservedEvents(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[ServerEvent, OperationMetadata]] = []

    def emit(self, record: logging.LogRecord) -> None:
        operation = getattr(record, "operation_metadata", None)
        assert isinstance(record.msg, ServerEvent)
        assert isinstance(operation, OperationMetadata)
        self.records.append((record.msg, operation))


@dataclass
class ObservedRequests:
    app: ASGIApp
    operations: dict[str, OperationMetadata] = field(default_factory=dict)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)
        operation = scope["state"]["operation_metadata"]
        assert isinstance(operation, OperationMetadata)
        self.operations[operation.trace_id] = operation


def test_owned_unieval_progress_returns_the_issued_evaluation_operation() -> None:
    _, settings = unieval_settings()
    inputs, _, _ = read_unieval_recordings()
    bootstrap = UnievalBootstrap(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=create_child_operation(create_root_operation()),
        settings=settings,
    )
    command = UnievalCommand(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=create_child_operation(create_root_operation(trace_state="test=worker")),
        execution_id=create_execution_id(),
        generation=1,
        request=recorded_unieval_request(inputs.cases[0].request),
    )
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    owner_read, owner_write = context.Pipe(duplex=False)
    process = context.Process(
        target=run_recorded_unieval_worker,
        args=(
            child,
            owner_read,
            REPOSITORY,
            1,
            command_byte_limit(settings, 1),
            UnievalScenario(),
        ),
        daemon=False,
    )
    try:
        process.start()
        child.close()
        owner_read.close()
        parent.send_bytes(bootstrap.model_dump_json().encode())
        assert parent.poll(settings.worker.startup_timeout_ms / 1000)
        ready = UnievalReply.model_validate_json(
            parent.recv_bytes(settings.worker.max_reply_bytes)
        ).root
        assert isinstance(ready, UnievalReady), ready
        assert ready.worker.pid == process.pid
        assert ready.operation_metadata == bootstrap.operation_metadata
        parent.send_bytes(command.model_dump_json().encode())
        while True:
            assert parent.poll(settings.evaluation.timeout_ms / 1000)
            reply = UnievalReply.model_validate_json(
                parent.recv_bytes(settings.worker.max_reply_bytes)
            ).root
            assert isinstance(reply, RequestPacket)
            validate_request_reply(command, reply)
            assert reply.operation_metadata == command.operation_metadata
            if isinstance(reply, UnievalFinished):
                break
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


def test_two_concurrent_carriers_reach_both_real_apis_and_their_independent_workers() -> None:
    async def check() -> None:
        hhem_api = load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
        hhem_settings = service_settings()
        unieval_api, selected_unieval = unieval_settings()
        hhem_worker = RecordedSupervisor(hhem_settings, (Scenario(),))
        unieval_worker = RecordedUnievalSupervisor(selected_unieval)
        writers = (
            EventWriter(hhem_api.logging, io.StringIO()),
            EventWriter(unieval_api.logging, io.StringIO()),
        )
        observed = (ObservedEvents(), ObservedEvents())
        for writer, observer in zip(writers, observed, strict=True):
            writer.logger.addHandler(observer)
        apps = (
            create_app(
                hhem_api,
                hhem_settings,
                REPOSITORY,
                writer=writers[0],
                supervisor=hhem_worker,
            ),
            create_app(
                unieval_api,
                None,
                REPOSITORY,
                writer=writers[1],
                unieval_settings=selected_unieval,
                unieval_supervisor=unieval_worker,
            ),
        )
        requests = (ObservedRequests(apps[0]), ObservedRequests(apps[1]))
        callers = (
            create_root_operation(trace_state="first=one,second=left"),
            create_root_operation(trace_state="first=two,second=right"),
        )
        hhem_inputs, predictions, _ = read_recordings(REPOSITORY)
        unieval_inputs, unieval_predictions, _ = read_unieval_recordings()
        try:
            async with (
                apps[0].router.lifespan_context(apps[0]),
                apps[1].router.lifespan_context(apps[1]),
            ):
                await apps[0].state.controller.loading_task
                await apps[1].state.unieval.loading_task
                async with (
                    httpx.AsyncClient(
                        transport=httpx.ASGITransport(requests[0]),
                        base_url=f"http://{hhem_api.listener.host}:{hhem_api.listener.port}",
                        trust_env=False,
                    ) as hhem,
                    httpx.AsyncClient(
                        transport=httpx.ASGITransport(requests[1]),
                        base_url=f"http://{unieval_api.listener.host}:{unieval_api.listener.port}",
                        trust_env=False,
                    ) as unieval,
                ):
                    responses = await asyncio.gather(
                        *[
                            client.post(
                                path,
                                headers=write_trace_context(caller),
                                json=body,
                            )
                            for client, path, bodies in (
                                (
                                    hhem,
                                    EVALUATE_PATH,
                                    [
                                        {
                                            "source_text": hhem_inputs.cases[0].source_text,
                                            "summary_text": hhem_inputs.cases[0].summary_text,
                                            "full_source_text": hhem_inputs.cases[0].source_text,
                                            "hhem_full": True,
                                            "request_id": REQUEST_ID.upper(),
                                            "correlation_id": CORRELATION_ID.upper(),
                                        }
                                    ]
                                    * 2,
                                ),
                                (
                                    unieval,
                                    UNIEVAL_PATH,
                                    [
                                        {
                                            **recorded_unieval_request(case.request).model_dump(),
                                            "request_id": REQUEST_ID.upper(),
                                            "correlation_id": CORRELATION_ID.upper(),
                                        }
                                        for case in unieval_inputs.cases[:2]
                                    ],
                                ),
                            )
                            for caller, body in zip(callers, bodies, strict=True)
                        ]
                    )
                assert all(response.status_code == 200 for response in responses)
                assert hhem_worker.worker is not None and unieval_worker.worker is not None
                assert hhem_worker.worker.pid != unieval_worker.worker.pid
                for index, response in enumerate(responses):
                    api_index, caller_index = divmod(index, 2)
                    caller = callers[caller_index]
                    receiving = requests[api_index].operations[caller.trace_id]
                    body = response.json()
                    assert receiving.parent_span_id == caller.span_id
                    assert receiving.trace_state == caller.trace_state
                    assert (
                        response.headers["traceparent"]
                        == (write_trace_context(receiving)["traceparent"])
                    )
                    assert response.headers["tracestate"] == caller.trace_state
                    assert body["request_id"] == REQUEST_ID.upper()
                    assert body["correlation_id"] == CORRELATION_ID.upper()
                    terminal = [
                        (event, operation)
                        for event, operation in observed[api_index].records
                        if event.data.execution_id == body["execution_id"]
                        and (
                            isinstance(event.data, EvaluationEvent)
                            and event.data.operation == "request"
                            and event.data.phase == "completed"
                            or isinstance(event.data, ApiDiagnosticData)
                            and event.data.action == "completed"
                        )
                    ]
                    assert len(terminal) == 1
                    assert terminal[0][1] == receiving
                    assert terminal[0][0].traceparent == response.headers["traceparent"]
                    if api_index == 0:
                        assert body["hhem"] == predictions.cases[0].score
                        assert body["hhem_full"] == body["hhem"]
                        assert body["windows"]["full_reused_primary"]
                    else:
                        recorded = unieval_predictions.cases[caller_index]
                        for dimension in DIMENSIONS:
                            values = [
                                comparison.score
                                for comparison in recorded.comparisons
                                if comparison.dimension == dimension
                            ]
                            if dimension == "consistency":
                                width = len(recorded.work.source_spans)
                                values = [
                                    max(values[start : start + width])
                                    for start in range(0, len(values), width)
                                ]
                            assert body["scores"][dimension] == sum(values) / len(values)
                commands = [
                    ScoreWindow.model_validate_json(encoded) for encoded in hhem_worker.commands
                ]
                assert len(commands) == 2
                for command in commands:
                    receiving = requests[0].operations[command.operation_metadata.trace_id]
                    primary = [
                        operation
                        for event, operation in observed[0].records
                        if isinstance(event.data, EvaluationEvent)
                        and event.data.execution_id == command.execution_id
                        and event.data.operation == "primary"
                        and event.data.phase == "started"
                    ][0]
                    assert primary.parent_span_id == receiving.span_id
                    assert command.operation_metadata.parent_span_id == primary.span_id
                for encoded in hhem_worker.replies:
                    reply = WindowOutcome.model_validate_json(encoded)
                    assert any(
                        reply.operation_metadata == command.operation_metadata
                        for command in commands
                    )
                unieval_commands = [
                    UnievalCommand.model_validate_json(encoded)
                    for encoded in unieval_worker.commands
                ]
                assert len(unieval_commands) == 2
                for unieval_command in unieval_commands:
                    receiving = requests[1].operations[unieval_command.operation_metadata.trace_id]
                    assert unieval_command.operation_metadata.parent_span_id == receiving.span_id
                for encoded in unieval_worker.replies:
                    unieval_reply = UnievalReply.model_validate_json(encoded).root
                    assert isinstance(unieval_reply, RequestPacket)
                    assert any(
                        unieval_reply.operation_metadata == item.operation_metadata
                        for item in unieval_commands
                    )
                assert hhem_worker.bootstrap is not None and unieval_worker.bootstrap is not None
                loads = (
                    hhem_worker.bootstrap.operation_metadata,
                    unieval_worker.bootstrap.operation_metadata,
                )
                for api_index, load in enumerate(loads):
                    assert load.trace_id == writers[api_index].service_operation.trace_id
                    assert load.trace_id not in {caller.trace_id for caller in callers}
        finally:
            hhem_worker.close_controls()
        assert hhem_worker.exit_confirmed and unieval_worker.exit_confirmed

    asyncio.run(check())
