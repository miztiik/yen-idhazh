"""How does one application retain and safely use one local GLiNER2 model?"""

import asyncio
from collections.abc import Callable
from pathlib import Path

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
    """Serialize native calls without replicas or changes to CPU tensor threading."""

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

    def mark_failed(self, code: ErrorCode) -> None:
        if not self.settings.enabled:
            return
        self.status = "failed"
        self.error_code = code

    async def start(self) -> None:
        if not self.settings.enabled:
            return
        async with self.lock:
            try:
                self.model = await run_in_threadpool(load_model, self.settings, self.root)
            except ModelLoadError:
                self.mark_failed("MODEL_UNAVAILABLE")
                return
            self.status = "ready"

    def observe_health(self) -> GlinerHealth:
        return GlinerHealth(
            enabled=self.settings.enabled,
            status=self.status,
            error=None if self.status == "ready" else ErrorDetail.from_code(self.error_code),
        )

    async def execute[ResultT](self, operation: Callable[[NativeModel], ResultT]) -> ResultT:
        async with self.lock:
            model = self.model
            if self.status != "ready" or model is None:
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
        self.status = "stopping"
        self.error_code = "MODEL_UNAVAILABLE"
        try:
            async with asyncio.timeout(self.shutdown_timeout_ms / 1000), self.lock:
                self.model = None
        except TimeoutError:
            self.mark_failed("ANALYSIS_FAILED")
            raise RuntimeError(
                "The GLiNER model did not finish within its shutdown bound."
            ) from None
