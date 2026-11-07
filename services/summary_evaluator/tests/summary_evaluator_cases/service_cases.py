"""Compose the real ASGI lifespan, owned processes and explicit test handshakes."""

import asyncio
import io
import json
import multiprocessing
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import cast

import httpx
from fastapi import FastAPI
from starlette.types import Message, Scope
from summary_evaluator_cases.contract_examples import REPOSITORY, SETTINGS_FILE
from summary_evaluator_cases.replay_predictions import Scenario, run_recorded_worker

from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.maintain_worker import WorkerSupervisor
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent, ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ServerEvent
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.contracts.api_paths import EVALUATE_PATH
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.exchange_packets import ByteChannel
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.maintain_unieval_worker import UnievalSupervisor


def service_settings(**blocks: dict[str, object]) -> ServiceSettings:
    data = load_settings(SETTINGS_FILE).model_dump(mode="json")
    data["enabled"] = True
    data["worker"].update(
        {
            "startup_timeout_ms": 10000,
            "replacement_timeout_ms": 10000,
            "stop_grace_ms": 1000,
            "forced_stop_ms": 3000,
            "shutdown_timeout_ms": 6000,
        }
    )
    data["evaluation"]["timeout_ms"] = 5000
    data["queue"].update({"capacity": 2, "wait_timeout_ms": 10000})
    for name, changes in blocks.items():
        data[name].update(changes)
    return ServiceSettings.model_validate_json(json.dumps(data))


class EventLog(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[EvaluationEvent] = []
        self.envelopes: list[ServerEvent] = []
        self.waiters: list[tuple[str, str, str | None, asyncio.Future[EvaluationEvent]]] = []
        self.fail_terminal = False

    def write(self, text: str) -> int:
        if text == "\n":
            return super().write(text)
        envelope = ServerEvent.model_validate_json(text)
        self.envelopes.append(envelope)
        if not isinstance(envelope.data, EvaluationEvent):
            return super().write(text)
        event = envelope.data
        if (
            self.fail_terminal
            and event.operation == "request"
            and event.phase in ("completed", "failed", "cancelled")
        ):
            raise OSError("PrivateLoggingFailureCanary")
        self.events.append(event)
        for operation, phase, request_id, future in self.waiters:
            if (
                not future.done()
                and event.operation == operation
                and event.phase == phase
                and (request_id is None or event.request_id == request_id)
            ):
                future.set_result(event)
        return super().write(text)

    async def wait(
        self, operation: str, phase: str, request_id: str | None = None
    ) -> EvaluationEvent:
        for event in self.events:
            if (
                event.operation == operation
                and event.phase == phase
                and (request_id is None or event.request_id == request_id)
            ):
                return event
        future: asyncio.Future[EvaluationEvent] = asyncio.get_running_loop().create_future()
        self.waiters.append((operation, phase, request_id, future))
        async with asyncio.timeout(15):
            return await future


class RecordedSupervisor(WorkerSupervisor):
    def __init__(self, settings: ServiceSettings, scenarios: tuple[Scenario, ...]) -> None:
        super().__init__(settings, StartupContext(), REPOSITORY)
        self.scenarios = scenarios
        self.controls: dict[int, ByteChannel] = {}
        self.spawn_events = {index + 1: asyncio.Event() for index in range(len(scenarios))}
        self.child_controls: list[ByteChannel] = []
        self.confirmed_before_spawn: list[tuple[int, int]] = []

    def _create_process(
        self, channel: ByteChannel, lifetime: ByteChannel, generation: int, max_bytes: int
    ) -> BaseProcess:
        if generation > len(self.scenarios):
            raise AssertionError("The bounded test did not declare another worker generation.")
        if generation > 1:
            assert self.exit_confirmed and self.last_exit is not None
            self.confirmed_before_spawn.append(self.last_exit)
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        self.controls[generation] = parent
        self.child_controls.append(child)
        self.spawn_events[generation].set()
        return context.Process(
            target=run_recorded_worker,
            args=(
                channel,
                lifetime,
                self.root,
                generation,
                max_bytes,
                child,
                self.scenarios[generation - 1],
            ),
            daemon=False,
        )

    async def start(self) -> None:
        try:
            await super().start()
        finally:
            for child in self.child_controls:
                child.close()
            self.child_controls.clear()

    async def handshake(self, generation: int = 1) -> dict[str, object]:
        async with asyncio.timeout(15):
            await self.spawn_events[generation].wait()
            encoded = await asyncio.to_thread(self.controls[generation].recv_bytes, 1024)
        return cast(dict[str, object], json.loads(encoded))

    async def release_prediction(self, generation: int = 1) -> None:
        await asyncio.to_thread(self.controls[generation].send_bytes, b"1")

    def close_controls(self) -> None:
        for control in self.controls.values():
            control.close()


@dataclass
class ServiceCase:
    app: FastAPI
    client: httpx.AsyncClient
    worker: RecordedSupervisor
    log: EventLog


@asynccontextmanager
async def running_service(
    settings: ServiceSettings | None = None,
    scenarios: tuple[Scenario, ...] = (Scenario(),),
    *,
    wait_ready: bool = True,
    routes: tuple[ApiComponent, ...] | None = None,
    root: Path = REPOSITORY,
    log_directory: Path | None = None,
    unieval_settings: UnievalSettings | None = None,
    unieval_supervisor: UnievalSupervisor | None = None,
) -> AsyncIterator[ServiceCase]:
    selected = settings or service_settings()
    if routes is not None:
        selected = ServiceSettings.model_validate_json(
            selected.model_copy(update={"enabled": "hhem" in routes}).model_dump_json()
        )
    worker = RecordedSupervisor(selected, scenarios)
    log = EventLog()
    shared = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json",
        routes[0] if routes is not None and len(routes) == 1 else "hhem",
    )
    api = ApiSettings.model_validate_json(
        shared.model_copy(
            update={
                "enabled_routes": routes
                if routes is not None
                else (("hhem",) if selected.enabled else ()),
                "listener": (
                    unieval_settings.listener
                    if routes == ("unieval",) and unieval_settings is not None
                    else shared.listener if routes == ("unieval",)
                    else selected.listener
                ),
                "logging": selected.logging,
            }
        ).model_dump_json()
    )
    app = create_app(
        api,
        selected,
        root,
        supervisor=worker,
        writer=EventWriter(selected.logging, log, directory=log_directory),
        unieval_settings=unieval_settings,
        unieval_supervisor=unieval_supervisor,
    )
    try:
        async with app.router.lifespan_context(app):
            if wait_ready and selected.enabled:
                await app.state.controller.loading_task
                assert app.state.controller.health().status == "ready"
            if wait_ready and unieval_supervisor is not None:
                await app.state.unieval.loading_task
                assert (await app.state.unieval.health()).status == "ready"
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url=httpx.URL(
                    scheme="http", host=api.listener.host, port=api.listener.port,
                ),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                yield ServiceCase(app, client, worker, log)
    finally:
        worker.close_controls()


@dataclass
class DirectRequest:
    body: bytes
    path: str = EVALUATE_PATH
    headers: tuple[tuple[bytes, bytes], ...] = ()
    disconnected: asyncio.Event = field(default_factory=asyncio.Event)
    messages: list[Message] = field(default_factory=list)
    body_reads: int = 0

    async def receive(self) -> Message:
        if not self.body_reads:
            self.body_reads += 1
            return {"type": "http.request", "body": self.body, "more_body": False}
        await self.disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(self, message: Message) -> None:
        self.messages.append(message)

    async def run(self, app: FastAPI) -> None:
        listener = app.state.api_settings.listener
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": self.path,
            "raw_path": self.path.encode(),
            "query_string": b"",
            "root_path": "",
            "client": ("127.0.0.1", 1),
            "server": (listener.host, listener.port),
            "headers": [
                (b"host", f"{listener.host}:{listener.port}".encode()),
                (b"content-type", b"application/json"),
                *self.headers,
            ],
        }
        await app(scope, self.receive, self.send)
