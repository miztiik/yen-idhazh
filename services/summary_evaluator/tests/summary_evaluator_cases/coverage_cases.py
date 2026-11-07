"""Compose the actual coverage worker and API with genuine recorded model-call boundaries."""

import asyncio
import io
import json
import multiprocessing
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Protocol

import httpx
from fastapi import FastAPI
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.coverage_recordings import (
    RecordedCoverageBackend,
    coverage_settings,
    read_coverage_recordings,
)

from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.exchange_packets import ByteChannel
from summary_evaluator.source_coverage.contracts.model_call import ConvertInput
from summary_evaluator.source_coverage.contracts.model_identity import CoverageModelIdentity
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings
from summary_evaluator.source_coverage.maintain_worker import CoverageSupervisor
from summary_evaluator.source_coverage.run_worker import run_worker


class PollableChannel(ByteChannel, Protocol):
    def poll(self, timeout: float) -> bool: ...


@dataclass(frozen=True)
class CoverageScenario:
    block_dimension: str | None = None
    hold_dimension: str | None = None
    crash_dimension: str | None = None
    invalid_dimension: str | None = None
    invalid_kind: str = "missing_dimension"
    load_failure: bool = False
    block_loading: bool = False


class ReplayCoverageBackend:
    def __init__(
        self,
        settings: CoverageSettings,
        root: Path,
        scenario: CoverageScenario,
        control: ByteChannel,
    ) -> None:
        inputs, recording = read_coverage_recordings()
        provenance = recording.provenance
        assert provenance.loaded_model_revision == settings.assets.model.revision
        assert provenance.code_revision == settings.assets.code.revision
        self.identity = CoverageModelIdentity(
            reference=provenance.model_reference,
            configured_revision=provenance.configured_model_revision,
            loaded_revision=provenance.loaded_model_revision,
            tokenizer_revision=provenance.tokenizer_revision,
            code_revision=provenance.code_revision,
            runtime_versions=provenance.runtime_versions,
        )
        self.cases = [
            RecordedCoverageBackend(case, settings, root)
            for case in recording.cases
        ]
        assert len(self.cases) == len(inputs.cases)
        self.convert_input: ConvertInput = self.cases[0].convert_input
        self.selected: RecordedCoverageBackend | None = None
        self.scenario, self.control = scenario, control

    def evaluate_dimension(
        self, data: list[dict[str, str]], dimension: str
    ) -> list[dict[str, float]]:
        self.control.send_bytes(json.dumps({"phase": "call", "dimension": dimension}).encode())
        if self.scenario.hold_dimension == dimension:
            self.control.recv_bytes(1)
        if self.scenario.block_dimension == dimension:
            threading.Event().wait()
        if self.scenario.crash_dimension == dimension:
            os._exit(17)
        if dimension == "fluency":
            self.selected = next(
                (case for case in self.cases if case.recorded.calls[0].inputs == tuple(data)), None
            )
            if self.selected is None:
                raise AssertionError("This exact coverage input has no genuine recording")
            self.selected.calls = 0
        if self.selected is None:
            raise AssertionError("The coverage dimension order has no genuine recording")
        result = self.selected.evaluate_dimension(data, dimension)
        if self.scenario.invalid_dimension == dimension:
            if self.scenario.invalid_kind == "missing_batch":
                return []
            if self.scenario.invalid_kind == "nonfinite":
                result[0][dimension] = float("nan")
            elif self.scenario.invalid_kind == "extra_batch":
                result.append(result[0].copy())
            else:
                result[0].pop(dimension)
        return result


@dataclass(frozen=True)
class RecordedCoverageLoader:
    scenario: CoverageScenario
    control: ByteChannel

    def __call__(self, settings: CoverageSettings, root: Path) -> ReplayCoverageBackend:
        self.control.send_bytes(b'{"phase":"loading"}')
        if self.scenario.block_loading:
            threading.Event().wait()
        if self.scenario.load_failure:
            raise ValueError("PrivateCoverageLoadFailureCanary")
        return ReplayCoverageBackend(settings, root, self.scenario, self.control)


def run_recorded_coverage_worker(
    channel: ByteChannel,
    lifetime: ByteChannel,
    root: Path,
    generation: int,
    command_limit: int,
    scenario: CoverageScenario,
    control: ByteChannel,
) -> None:
    try:
        run_worker(
            channel,
            lifetime,
            root,
            generation,
            command_limit,
            loader=RecordedCoverageLoader(scenario, control),
        )
    finally:
        control.close()


class RecordedCoverageSupervisor(CoverageSupervisor):
    def __init__(
        self, settings: CoverageSettings, scenario: CoverageScenario | None = None
    ) -> None:
        super().__init__(settings, REPOSITORY)
        self.scenario = scenario or CoverageScenario()
        self.control: PollableChannel | None = None
        self.child_control: PollableChannel | None = None

    def _create_process(
        self, channel: ByteChannel, lifetime: ByteChannel, generation: int
    ) -> BaseProcess:
        parent, child = multiprocessing.get_context("spawn").Pipe(duplex=True)
        self.control, self.child_control = parent, child
        return multiprocessing.get_context("spawn").Process(
            target=run_recorded_coverage_worker,
            args=(
                channel, lifetime, self.root, generation, self.command_limit, self.scenario, child
            ),
            daemon=False,
        )

    async def start(self) -> None:
        try:
            await super().start()
        finally:
            if self.child_control is not None:
                self.child_control.close()
                self.child_control = None

    async def handshake(self) -> dict[str, str]:
        assert self.control is not None
        ready = await asyncio.to_thread(self.control.poll, 30)
        assert ready, "The real coverage boundary did not reach its named phase"
        payload = await asyncio.to_thread(self.control.recv_bytes, 1024)
        value: dict[str, str] = json.loads(payload)
        return value

    async def release(self) -> None:
        assert self.control is not None
        await asyncio.to_thread(self.control.send_bytes, b"1")

    def close_controls(self) -> None:
        if self.control is not None:
            self.control.close()
            self.control = None
        if self.child_control is not None:
            self.child_control.close()
            self.child_control = None


@asynccontextmanager
async def running_coverage(
    *,
    settings: CoverageSettings | None = None,
    scenario: CoverageScenario | None = None,
    log_directory: Path | None = None,
    wait_ready: bool = True,
) -> AsyncIterator[tuple[httpx.AsyncClient, RecordedCoverageSupervisor, io.StringIO, FastAPI]]:
    api = load_api_settings(REPOSITORY / "config" / "summary-evals" / "api.json")
    api = api.model_copy(update={"enabled_routes": ("coverage",)})
    selected = settings or coverage_settings()
    api = api.model_copy(update={"listener": selected.listener, "logging": selected.logging})
    worker = RecordedCoverageSupervisor(selected, scenario)
    stream = io.StringIO()
    writer = EventWriter(api.logging, stream, directory=log_directory)
    app = create_app(
        api, None, REPOSITORY, writer=writer,
        coverage_settings=selected, coverage_supervisor=worker,
    )
    try:
        async with app.router.lifespan_context(app):
            if wait_ready:
                await app.state.coverage.loading_task
                assert (await app.state.coverage.health()).status == "ready", stream.getvalue()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app),
                base_url=f"http://{api.listener.host}:{api.listener.port}",
                trust_env=False,
            ) as client:
                yield client, worker, stream, app
    finally:
        worker.close_controls()
    assert worker.exit_confirmed
