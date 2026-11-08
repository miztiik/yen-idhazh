"""Compose separate native ASGI apps for caller tests without claiming API process isolation."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from local_api_host.propagate_trace_context import OperationMetadata
from starlette.types import ASGIApp, Receive, Scope, Send
from summary_eval_pipeline.evaluation import read_owned_health
from summary_eval_pipeline.phase_services import ScorerService
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.serve_http.contracts.server_event import ServerEvent
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.replay_predictions import Scenario
from summary_evaluator_cases.service_cases import ServiceCase, running_service, service_settings
from summary_evaluator_cases.unieval_cases import (
    RecordedUnievalSupervisor,
    UnievalScenario,
    unieval_settings,
)


class ObservedTraceRecords(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[ServerEvent, OperationMetadata]] = []

    def emit(self, record: logging.LogRecord) -> None:
        operation = getattr(record, "operation_metadata", None)
        assert isinstance(record.msg, ServerEvent)
        assert isinstance(operation, OperationMetadata)
        self.records.append((record.msg, operation))


@dataclass
class ObservedScorerApp:
    app: ASGIApp
    operations: list[OperationMetadata]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)
        operation = scope["state"]["operation_metadata"]
        if operation is not None:
            assert isinstance(operation, OperationMetadata)
            self.operations.append(operation)


@dataclass
class NativeResponseObservation:
    request: httpx.Request
    status: int
    headers: httpx.Headers
    body: bytearray


class ObservedResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream: httpx.AsyncByteStream, body: bytearray) -> None:
        self.stream, self.body = stream, body

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self.stream:
            self.body.extend(chunk)
            yield chunk

    async def aclose(self) -> None:
        await self.stream.aclose()


class ScorerTransport(httpx.AsyncBaseTransport):
    """Send each authored origin only to its real native ASGI app, never to a network."""

    def __init__(self, hhem: ServiceCase, unieval: ServiceCase) -> None:
        self.receiving: list[OperationMetadata] = []
        self.transports = {
            (case.app.state.api_settings.listener.host, case.app.state.api_settings.listener.port):
            httpx.ASGITransport(ObservedScorerApp(case.app, self.receiving))
            for case in (hhem, unieval)
        }
        if len(self.transports) != 2:
            raise ValueError("Caller tests require separately selected scorer listeners")
        self.requests: list[httpx.Request] = []
        self.responses: list[NativeResponseObservation] = []
        self.trace_faults: dict[str, str] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        key = (request.url.host, request.url.port)
        if request.url.scheme != "http" or key not in self.transports:
            raise AssertionError("The caller selected an origin outside its authored scorers")
        self.requests.append(request)
        response = await self.transports[key].handle_async_request(request)
        observed = NativeResponseObservation(
            request, response.status_code, httpx.Headers(response.headers), bytearray()
        )
        self.responses.append(observed)
        assert isinstance(response.stream, httpx.AsyncByteStream)
        response.stream = ObservedResponseStream(response.stream, observed.body)
        fault = self.trace_faults.get(request.url.path)
        if fault == "missing":
            del response.headers["traceparent"]
            if "tracestate" in response.headers:
                del response.headers["tracestate"]
        elif fault == "invalid":
            response.headers["traceparent"] = "PrivateResponseTraceCanary"
        elif fault == "state":
            response.headers["tracestate"] = "PrivateResponseTraceCanary"
        return response

    async def aclose(self) -> None:
        for transport in self.transports.values():
            await transport.aclose()


@dataclass
class ScorerCallerCase:
    hhem: ServiceCase
    unieval: ServiceCase
    unieval_worker: RecordedUnievalSupervisor
    apis: tuple[ScorerService, ScorerService]
    client: httpx.AsyncClient
    transport: ScorerTransport
    traces: tuple[ObservedTraceRecords, ObservedTraceRecords]


@asynccontextmanager
async def running_scorers(
    settings: ServiceSettings | None = None,
    scenarios: tuple[Scenario, ...] = (Scenario(),),
    *,
    selected_unieval: UnievalSettings | None = None,
    unieval_scenario: UnievalScenario | None = None,
    unieval_supervisor: RecordedUnievalSupervisor | None = None,
    wait_ready: bool = True,
) -> AsyncIterator[ScorerCallerCase]:
    selected_hhem = settings or service_settings()
    if selected_unieval is None:
        _, selected_unieval = unieval_settings()
    worker = unieval_supervisor or RecordedUnievalSupervisor(selected_unieval, unieval_scenario)
    async with (
        running_service(selected_hhem, scenarios, routes=("hhem",), wait_ready=wait_ready) as hhem,
        running_service(
            selected_hhem,
            routes=("unieval",),
            unieval_settings=selected_unieval,
            unieval_supervisor=worker,
            wait_ready=wait_ready,
        ) as unieval,
    ):
        apis = (
            ScorerService("hhem", hhem.app.state.api_settings, selected_hhem.worker),
            ScorerService("unieval", unieval.app.state.api_settings, selected_unieval.worker),
        )
        transport = ScorerTransport(hhem, unieval)
        traces = (ObservedTraceRecords(), ObservedTraceRecords())
        for case, observer in zip((hhem, unieval), traces, strict=True):
            case.app.state.events.logger.addHandler(observer)
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False,
        ) as client:
            if wait_ready:
                for api, case in zip(apis, (hhem, unieval), strict=True):
                    api.health = await read_owned_health(
                        client, api.origin, case.app.state.service_instance_id,
                        api.worker_settings, load_pipeline_settings(REPOSITORY), api.scorer,
                    )
            yield ScorerCallerCase(hhem, unieval, worker, apis, client, transport, traces)
