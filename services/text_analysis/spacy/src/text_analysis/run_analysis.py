"""How is validated analysis admitted to two standard spawned executor processes?"""

import asyncio
import multiprocessing
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import TextIOBase
from pathlib import Path
from typing import Literal

import anyio
from pydantic import ValidationError

from text_analysis.declare_api_contracts import (
    AnalysisCommand,
    AnalysisOutcome,
    ErrorDetail,
)
from text_analysis.declare_service_settings import ServiceSettings
from text_analysis.extract_features import extract_feature_results
from text_analysis.load_service_settings import load_service_settings
from text_analysis.manage_models import (
    ModelUnavailableError,
    load_selected_model,
    verify_spacy_runtime,
)

AdmissionFailureCode = Literal["SERVICE_DISABLED", "BUSY", "ANALYSIS_FAILED"]


class RuntimeAdmissionError(RuntimeError):
    """Refuse one request without adding an executor backlog."""

    def __init__(self, code: AdmissionFailureCode) -> None:
        super().__init__(code)
        self.code = code


class _DiscardText(TextIOBase):
    """Prevent third-party worker output from bypassing validated parent events."""

    def write(self, value: str) -> int:
        return len(value)


def _execute_analysis(command_json: str) -> str:
    command = AnalysisCommand.model_validate_json(command_json)
    settings = load_service_settings(Path.cwd())
    load_started_at = time.monotonic()
    try:
        loaded, model_load_ms = load_selected_model(
            settings,
            command.language,
            command.profile,
        )
    except ModelUnavailableError:
        return AnalysisOutcome(
            model=None,
            features=(),
            model_load_ms=(time.monotonic() - load_started_at) * 1000,
            analysis_ms=0.0,
            error=ErrorDetail.from_code("MODEL_UNAVAILABLE"),
        ).model_dump_json()

    analysis_started_at = time.monotonic()
    try:
        doc = loaded.nlp(command.text)
    except Exception:
        return AnalysisOutcome(
            model=None,
            features=(),
            model_load_ms=model_load_ms,
            analysis_ms=(time.monotonic() - analysis_started_at) * 1000,
            error=ErrorDetail.from_code("ANALYSIS_FAILED"),
        ).model_dump_json()
    features = extract_feature_results(doc, command, loaded, settings)
    return AnalysisOutcome(
        model=loaded.identity,
        features=features,
        model_load_ms=model_load_ms,
        analysis_ms=(time.monotonic() - analysis_started_at) * 1000,
        error=None,
    ).model_dump_json()


def execute_analysis(command_json: str) -> str:
    """Run one strict command without allowing worker output onto service stderr."""
    discard = _DiscardText()
    with redirect_stdout(discard), redirect_stderr(discard):
        return _execute_analysis(command_json)


@dataclass(frozen=True, slots=True)
class ActiveAnalysis:
    """Retain one admitted future and its shielded event-loop completion task."""

    process_future: Future[str]
    completion_task: asyncio.Task[AnalysisOutcome]


class AnalysisRuntime:
    """Own immediate capacity admission, the process pool and exact shutdown."""

    def __init__(
        self,
        settings: ServiceSettings,
        on_pool_failure: Callable[[], Awaitable[None]],
    ) -> None:
        self.settings = settings
        self.on_pool_failure = on_pool_failure
        self.status: Literal["disabled", "ready", "failed", "stopping"] = (
            "disabled" if not settings.enabled else "stopping"
        )
        self.admission_enabled = False
        self.executor: ProcessPoolExecutor | None = None
        self.limiter: anyio.CapacityLimiter | None = None
        self.active: dict[object, ActiveAnalysis] = {}
        self.pool_exited = not settings.enabled
        self.failure_reported = False
        self.logging_failed = False
        self.background_tasks: set[asyncio.Task[None]] = set()

    @property
    def active_requests(self) -> int:
        return len(self.active)

    @property
    def pool_ready(self) -> bool:
        return (
            self.status == "ready"
            and self.admission_enabled
            and self.executor is not None
            and not self.pool_exited
        )

    def mark_logging_failed(self) -> None:
        """Stop admission after stderr can no longer carry validated events."""
        self.logging_failed = True
        self.admission_enabled = False
        self.status = "failed"

    def _latch_pool_failure(self) -> bool:
        first = not self.failure_reported
        self.failure_reported = True
        self.admission_enabled = False
        self.status = "failed"
        return first

    async def _report_pool_failure(self) -> None:
        if self._latch_pool_failure():
            await self.on_pool_failure()

    def _schedule_pool_failure(self) -> None:
        task = asyncio.create_task(self.on_pool_failure())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def start(self) -> None:
        if not self.settings.enabled:
            self.status = "disabled"
            return
        if self.logging_failed:
            self.status = "failed"
            return
        try:
            verify_spacy_runtime(self.settings)
        except ModelUnavailableError:
            self._latch_pool_failure()
            raise RuntimeError("Configured spaCy runtime is unavailable") from None
        self.limiter = anyio.CapacityLimiter(
            self.settings.max_concurrent_requests
        )
        try:
            self.executor = ProcessPoolExecutor(
                max_workers=self.settings.max_concurrent_requests,
                mp_context=multiprocessing.get_context("spawn"),
            )
        except Exception:
            self._latch_pool_failure()
            raise
        self.pool_exited = False
        self.admission_enabled = True
        self.status = "ready"

    def submit(self, command: AnalysisCommand) -> asyncio.Task[AnalysisOutcome]:
        """Acquire one unique lease and submit without awaiting or queueing."""
        if not self.settings.enabled:
            raise RuntimeAdmissionError("SERVICE_DISABLED")
        if not self.pool_ready or self.executor is None or self.limiter is None:
            raise RuntimeAdmissionError("ANALYSIS_FAILED")

        lease = object()
        try:
            self.limiter.acquire_on_behalf_of_nowait(lease)
        except anyio.WouldBlock:
            raise RuntimeAdmissionError("BUSY") from None

        try:
            process_future = self.executor.submit(
                execute_analysis,
                command.model_dump_json(),
            )
        except (BrokenProcessPool, OSError, RuntimeError):
            self.limiter.release_on_behalf_of(lease)
            self._latch_pool_failure()
            self._schedule_pool_failure()
            raise RuntimeAdmissionError("ANALYSIS_FAILED") from None

        completion_task = asyncio.create_task(
            self._complete(lease, process_future)
        )
        self.active[lease] = ActiveAnalysis(
            process_future=process_future,
            completion_task=completion_task,
        )
        return completion_task

    async def _complete(
        self,
        lease: object,
        process_future: Future[str],
    ) -> AnalysisOutcome:
        wrapped = asyncio.wrap_future(process_future)
        try:
            try:
                payload = await wrapped
            except BrokenProcessPool:
                await self._report_pool_failure()
                return AnalysisOutcome(
                    model=None,
                    features=(),
                    model_load_ms=0.0,
                    analysis_ms=0.0,
                    error=ErrorDetail.from_code("ANALYSIS_FAILED"),
                )
            except asyncio.CancelledError:
                if not process_future.done():
                    try:
                        await asyncio.shield(asyncio.wrap_future(process_future))
                    except BaseException:
                        pass
                if self.status != "stopping":
                    await self._report_pool_failure()
                return AnalysisOutcome(
                    model=None,
                    features=(),
                    model_load_ms=0.0,
                    analysis_ms=0.0,
                    error=ErrorDetail.from_code("ANALYSIS_FAILED"),
                )
            except Exception:
                await self._report_pool_failure()
                return AnalysisOutcome(
                    model=None,
                    features=(),
                    model_load_ms=0.0,
                    analysis_ms=0.0,
                    error=ErrorDetail.from_code("ANALYSIS_FAILED"),
                )
            try:
                return AnalysisOutcome.model_validate_json(payload)
            except (ValidationError, TypeError):
                await self._report_pool_failure()
                return AnalysisOutcome(
                    model=None,
                    features=(),
                    model_load_ms=0.0,
                    analysis_ms=0.0,
                    error=ErrorDetail.from_code("ANALYSIS_FAILED"),
                )
        finally:
            if process_future.done():
                self.active.pop(lease, None)
                if self.limiter is not None:
                    self.limiter.release_on_behalf_of(lease)

    async def shutdown(self) -> None:
        """Close the pool and completion tasks under one absolute deadline."""
        self.admission_enabled = False
        if self.executor is None:
            if self.background_tasks:
                await asyncio.gather(
                    *(asyncio.shield(task) for task in tuple(self.background_tasks))
                )
            if self.settings.enabled and self.status != "failed":
                self.status = "stopping"
            return
        self.status = "stopping"
        active = tuple(self.active.values())
        for record in active:
            record.process_future.cancel()
        executor = self.executor
        deadline = (
            asyncio.get_running_loop().time()
            + self.settings.listener.shutdown_timeout_ms / 1000
        )
        try:
            async with asyncio.timeout_at(deadline):
                await asyncio.to_thread(
                    executor.shutdown,
                    wait=True,
                    cancel_futures=True,
                )
                if active:
                    await asyncio.gather(
                        *(
                            asyncio.shield(record.completion_task)
                            for record in active
                        )
                    )
                if self.background_tasks:
                    await asyncio.gather(
                        *(asyncio.shield(task) for task in tuple(self.background_tasks))
                    )
        except BaseException:
            self._latch_pool_failure()
            raise
        if self.active:
            self._latch_pool_failure()
            raise RuntimeError("Executor stopped before completion tasks settled")
        self.executor = None
        self.pool_exited = True
