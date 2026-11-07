"""Who owns coverage admission, independent readiness and all-or-error process cleanup?"""

import asyncio
from collections.abc import Callable
from pathlib import Path

from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.shared.queue_evaluations import EvaluationQueue, Reservation
from summary_evaluator.source_coverage.contracts.base import COVERAGE_VERSION
from summary_evaluator.source_coverage.contracts.evaluate_request import CoverageRequest
from summary_evaluator.source_coverage.contracts.evaluation_result import CoverageMetrics
from summary_evaluator.source_coverage.contracts.service_health import CoverageHealth
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings
from summary_evaluator.source_coverage.contracts.worker_message import (
    CoverageCommand,
    CoverageCompleted,
    CoverageFailed,
)
from summary_evaluator.source_coverage.fail_evaluation import CoverageFailure
from summary_evaluator.source_coverage.maintain_worker import CoverageSupervisor


class CoverageController:
    def __init__(
        self,
        settings: CoverageSettings,
        root: Path,
        writer: Callable[[LifecycleFields], None],
        service_instance_id: str,
        *,
        supervisor: CoverageSupervisor | None = None,
    ) -> None:
        self.settings, self.diagnostic = settings, writer
        self.worker = supervisor or CoverageSupervisor(settings, root)
        self.queue = EvaluationQueue(settings.queue)
        self.instance_id = service_instance_id
        self.status = "loading"
        self.failure_code: ErrorCode | None = None
        self.loading_task: asyncio.Task[None] | None = None
        self.active_task: asyncio.Task[CoverageMetrics] | None = None
        self.stop_task: asyncio.Task[None] | None = None
        self.stopping = False

    async def health(self) -> CoverageHealth:
        await self._observe_worker_exit()
        return CoverageHealth.model_validate(
            {
                "version": COVERAGE_VERSION,
                "service_instance_id": self.instance_id,
                "status": self.status,
                "model": self.worker.model,
                "worker": self.worker.worker,
                "queue_depth": self.queue.depth,
                "queue_capacity": self.settings.queue.capacity,
                "failure_code": self.failure_code,
            }
        )

    async def start(self) -> None:
        self.diagnostic(LifecycleFields(action="started", level="INFO"))
        self.loading_task = asyncio.create_task(self._load())

    async def _load(self) -> None:
        try:
            await self.worker.start()
            self.status, self.queue.ready = "ready", True
            self.queue.promote()
            self.diagnostic(LifecycleFields(action="ready", level="INFO"))
        except (CoverageFailure, RuntimeFailure) as failure:
            self.queue.ready = False
            self.failure_code, self.status = failure.code, "failed"
            self._record_failure(failure.code)
            try:
                await self._stop_worker()
            except CoverageFailure as cleanup:
                self.failure_code = cleanup.code
                self._record_failure(cleanup.code)

    def _record_failure(self, code: ErrorCode | None) -> None:
        try:
            self.diagnostic(LifecycleFields(action="failed", level="ERROR", code=code))
        except RuntimeFailure:
            self.failure_code = "LOGGING_FAILED"

    async def reserve(self, execution_id: str) -> Reservation:
        await self._observe_worker_exit()
        if self.stopping:
            raise CoverageFailure("SERVICE_STOPPED")
        if self.status != "ready":
            if self.failure_code in ("WORKER_EXITED", "WORKER_STOP_FAILED"):
                raise CoverageFailure(self.failure_code)
            raise CoverageFailure("WORKER_NOT_READY")
        try:
            return self.queue.reserve(execution_id)
        except RuntimeFailure as failure:
            raise CoverageFailure(failure.code) from None

    async def _observe_worker_exit(self) -> None:
        if self.status != "ready":
            if self.stop_task is not None:
                try:
                    await asyncio.shield(self.stop_task)
                except CoverageFailure as failure:
                    self.failure_code = failure.code
            return
        if self.worker.is_alive:
            return
        try:
            await self.fail_worker("WORKER_EXITED")
        except CoverageFailure as failure:
            self.failure_code = failure.code
        self._record_failure(self.failure_code)

    async def _stop_worker(self) -> None:
        if (
            self.stop_task is None
            or self.stop_task.cancelled()
            or (self.stop_task.done() and not self.worker.exit_confirmed)
        ):
            self.stop_task = asyncio.create_task(self.worker.stop())
        await asyncio.shield(self.stop_task)

    async def process(
        self, request: CoverageRequest, execution_id: str, reservation: Reservation
    ) -> CoverageMetrics:
        try:
            await self.queue.wait(reservation)
        except RuntimeFailure as failure:
            raise CoverageFailure(failure.code) from None
        self.active_task = asyncio.current_task()
        try:
            async with asyncio.timeout(self.settings.evaluation.timeout_ms / 1000):
                await self.worker.send(
                    CoverageCommand(
                        version=COVERAGE_VERSION,
                        execution_id=execution_id,
                        generation=self.worker.generation,
                        request=request,
                    )
                )
                reply = (await self.worker.receive()).root
                if (
                    not isinstance(reply, (CoverageCompleted, CoverageFailed))
                    or reply.execution_id != execution_id
                    or reply.generation != self.worker.generation
                ):
                    raise CoverageFailure("WORKER_PROTOCOL_FAILED")
                for warning in reply.warnings:
                    self.diagnostic(
                        LifecycleFields(
                            action="unavailable",
                            level="WARNING",
                            execution_id=execution_id,
                            code=warning,
                        )
                    )
                if isinstance(reply, CoverageFailed):
                    raise CoverageFailure(reply.code)
                return reply.metrics
        except TimeoutError:
            raise await self.stop_failed_request("EVALUATION_TIMEOUT") from None
        except (CoverageFailure, RuntimeFailure) as failure:
            raise await self.stop_failed_request(failure.code) from None
        except asyncio.CancelledError:
            await self.stop_failed_request("CLIENT_DISCONNECTED")
            raise
        finally:
            self.active_task = None

    async def stop_failed_request(self, code: ErrorCode) -> CoverageFailure:
        try:
            await self.fail_worker(code)
        except CoverageFailure as cleanup:
            return CoverageFailure(code, cleanup.code)
        return CoverageFailure(code)

    async def fail_worker(self, code: ErrorCode = "WORKER_NOT_READY") -> None:
        self.queue.ready = False
        self.status, self.failure_code = "stopping" if self.stopping else "failed", code
        for reservation in tuple(self.queue.reservations.values()):
            if reservation.owner is not None:
                reservation.owner.cancel()
        try:
            await self._stop_worker()
        except CoverageFailure:
            self.failure_code = "WORKER_STOP_FAILED"
            raise

    async def shutdown(self) -> None:
        self.stopping, self.status = True, "stopping"
        self.queue.close()
        tasks = [task for task in (self.loading_task, self.active_task) if task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        async with asyncio.timeout(self.settings.worker.shutdown_timeout_ms / 1000):
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await self._stop_worker()
        self.diagnostic(LifecycleFields(action="stopped", level="INFO"))
