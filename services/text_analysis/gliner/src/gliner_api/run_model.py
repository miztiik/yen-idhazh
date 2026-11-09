"""How does one application retain and safely use one local GLiNER2 model?"""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from starlette.concurrency import run_in_threadpool

from gliner_api.configure_native_diagnostics import NativeDiagnosticError, native_operation
from gliner_api.declare_api_contracts import (
    ErrorCode,
    ErrorDetail,
    GlinerHealth,
    HealthStatus,
    ResultValidationError,
)
from gliner_api.load_model import ModelLoadError, NativeModel, load_model
from gliner_api.load_settings import GlinerSettings


class OperationError(RuntimeError):
    """Carry only one safe API failure code across the native inference boundary."""

    def __init__(self, code: ErrorCode) -> None:
        super().__init__("The native GLiNER operation failed.")
        self.code = code


class ModelRuntime:
    """Own native calls and diagnostics independently of their HTTP waiters."""

    def __init__(self, settings: GlinerSettings, root: Path, shutdown_timeout_ms: int) -> None:
        self.settings = settings
        self.root = root
        self.shutdown_timeout_ms = shutdown_timeout_ms
        self.model: NativeModel | None = None
        self.status: HealthStatus = "loading" if settings.enabled else "disabled"
        self.error_code: ErrorCode = (
            "MODEL_UNAVAILABLE" if settings.enabled else "SERVICE_DISABLED"
        )
        self.lock = asyncio.Lock()
        self._owned_tasks: set[asyncio.Task[object]] = set()
        self._startup_task: asyncio.Task[None] | None = None
        self._stopping = False

    def mark_failed(self, code: ErrorCode) -> None:
        if not self.settings.enabled:
            return
        self.status = "failed"
        self.error_code = code

    async def start(self) -> None:
        if not self.settings.enabled:
            return
        if self._startup_task is None:
            self._startup_task = self._retain(asyncio.create_task(self._load_model()))
        await asyncio.shield(self._startup_task)

    async def _load_model(self) -> None:
        async with self.lock:
            try:
                self.model = await run_in_threadpool(load_model, self.settings, self.root)
            except ModelLoadError:
                self.mark_failed("MODEL_UNAVAILABLE")
                return
            if not self._stopping:
                self.status = "ready"

    def _retain[ResultT](self, task: asyncio.Task[ResultT]) -> asyncio.Task[ResultT]:
        owned = cast(asyncio.Task[object], task)
        self._owned_tasks.add(owned)
        owned.add_done_callback(self._release)
        return task

    def _release(self, task: asyncio.Task[object]) -> None:
        self._owned_tasks.discard(task)
        if task.cancelled() or (
            (failure := task.exception()) is not None
            and not isinstance(failure, OperationError)
        ):
            self.mark_failed("ANALYSIS_FAILED")

    def observe_health(self) -> GlinerHealth:
        return GlinerHealth(
            enabled=self.settings.enabled,
            status=self.status,
            error=None if self.status == "ready" else ErrorDetail.from_code(self.error_code),
        )

    async def execute[ResultT](
        self,
        operation: Callable[[NativeModel], ResultT],
        *,
        terminal: Callable[[ResultT | OperationError], Awaitable[None]] | None = None,
    ) -> ResultT:
        if self._stopping or self.status != "ready" or self.model is None:
            error = OperationError(self.error_code)
            if terminal is not None:
                await terminal(error)
            raise error
        completion = self._retain(asyncio.create_task(self._complete(operation, terminal)))
        return await asyncio.shield(completion)

    async def _complete[ResultT](
        self,
        operation: Callable[[NativeModel], ResultT],
        terminal: Callable[[ResultT | OperationError], Awaitable[None]] | None,
    ) -> ResultT:
        async with self.lock:
            outcome: ResultT | OperationError
            try:
                outcome = await self._run_native(operation)
            except OperationError as error:
                outcome = error
            if terminal is not None:
                try:
                    await terminal(outcome)
                except Exception:
                    self.mark_failed("LOGGING_FAILED")
                    raise OperationError("LOGGING_FAILED") from None
            if isinstance(outcome, OperationError):
                raise outcome
            return outcome

    async def _run_native[ResultT](self, operation: Callable[[NativeModel], ResultT]) -> ResultT:
        model = self.model
        if self.status not in ("ready", "stopping") or model is None:
            raise OperationError(self.error_code)

        def perform() -> ResultT:
            with native_operation():
                return operation(model)

        try:
            return await run_in_threadpool(perform)
        except NativeDiagnosticError as error:
            if error.code == "ANALYSIS_FAILED":
                self.mark_failed(error.code)
            raise OperationError(error.code) from None
        except ResultValidationError:
            self.mark_failed("INVALID_RESULT")
            raise OperationError("INVALID_RESULT") from None
        except (Warning, ValueError, TypeError, OverflowError):
            raise OperationError("INPUT_UNSUPPORTED") from None
        except Exception:
            self.mark_failed("ANALYSIS_FAILED")
            raise OperationError("ANALYSIS_FAILED") from None

    async def shutdown(self) -> None:
        if not self.settings.enabled:
            return
        self._stopping = True
        if self.status != "failed":
            self.status = "stopping"
            self.error_code = "MODEL_UNAVAILABLE"
        deadline = asyncio.get_running_loop().time() + self.shutdown_timeout_ms / 1000
        try:
            async with asyncio.timeout_at(deadline):
                if self._owned_tasks:
                    await asyncio.wait(tuple(self._owned_tasks))
                async with self.lock:
                    self.model = None
        except TimeoutError:
            self.mark_failed("ANALYSIS_FAILED")
            raise RuntimeError(
                "The GLiNER model did not finish within its shutdown bound."
            ) from None
