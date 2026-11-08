"""Who owns UniEval admission, independent readiness and bounded process shutdown?"""

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_child_operation,
    create_root_operation,
)

from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.shared.queue_evaluations import EvaluationQueue, Reservation
from summary_evaluator.unieval.contracts.unieval_contract import UNIEVAL_VERSION
from summary_evaluator.unieval.contracts.unieval_error import UnievalError, UnievalErrorCode
from summary_evaluator.unieval.contracts.unieval_result import UnievalHealth
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.contracts.unieval_worker_contract import UNIEVAL_WORKER_VERSION
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    UnievalCommand,
    UnievalFinished,
    UnievalPrediction,
    UnievalPrepared,
)
from summary_evaluator.unieval.fail_unieval import UnievalFailure
from summary_evaluator.unieval.maintain_unieval_worker import UnievalSupervisor
from summary_evaluator.unieval.reduce_unieval import UnievalState


class UnievalController:
    def __init__(
        self,
        settings: UnievalSettings,
        root: Path,
        writer: Callable[[LifecycleFields, OperationMetadata], None],
        service_instance_id: str,
        *,
        supervisor: UnievalSupervisor | None = None,
        service_operation: OperationMetadata | None = None,
        propagate_trace_context: bool = False,
    ) -> None:
        self.settings, self.writer = settings, writer
        self.service_operation = service_operation or create_root_operation()
        self.propagate_trace_context = propagate_trace_context
        self.load_operation = create_child_operation(self.service_operation)
        self.worker = supervisor or UnievalSupervisor(settings, root)
        self.queue = EvaluationQueue(settings.queue)
        self.instance_id = service_instance_id
        self.status = "loading"
        self.failure_code: UnievalErrorCode | None = None
        self.loading_task: asyncio.Task[None] | None = None
        self.active_task: asyncio.Task[None] | None = None
        self.stop_task: asyncio.Task[None] | None = None
        self.stopping = False

    def diagnostic(
        self, data: LifecycleFields, operation_metadata: OperationMetadata | None = None
    ) -> None:
        self.writer(data, operation_metadata or self.service_operation)

    async def health(self) -> UnievalHealth:
        await self._observe_worker_exit()
        return UnievalHealth.model_validate(
            {
                "version": UNIEVAL_VERSION,
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
            self.worker.issue_load(self.load_operation)
            await self.worker.start()
            self.status = "ready"
            self.queue.ready = True
            self.queue.promote()
            self.diagnostic(LifecycleFields(action="ready", level="INFO"), self.load_operation)
        except (UnievalFailure, RuntimeFailure) as failure:
            self.queue.ready = False
            code = failure.error.code if isinstance(failure, UnievalFailure) else failure.code
            self.failure_code, self.status = code, "failed"
            try:
                self.diagnostic(
                    LifecycleFields(
                        action="failed",
                        level="ERROR",
                        code=code,
                    ),
                    self.load_operation,
                )
            except RuntimeFailure:
                self.failure_code = "LOGGING_FAILED"
            try:
                await self._stop_worker()
            except UnievalFailure as cleanup:
                self.failure_code = cleanup.error.code
                try:
                    self.diagnostic(
                        LifecycleFields(
                            action="failed",
                            level="ERROR",
                            code=cleanup.error.code,
                        ),
                        self.load_operation,
                    )
                except RuntimeFailure:
                    self.failure_code = "LOGGING_FAILED"

    async def reserve(self, state: UnievalState) -> Reservation:
        await self._observe_worker_exit()
        if self.stopping:
            raise UnievalFailure(UnievalError.from_code("SERVICE_STOPPED"))
        if self.status != "ready":
            if self.failure_code in ("WORKER_EXITED", "WORKER_STOP_FAILED"):
                raise UnievalFailure(UnievalError.from_code(self.failure_code))
            raise UnievalFailure(UnievalError.from_code("WORKER_NOT_READY"))
        try:
            return self.queue.reserve(state.execution_id)
        except RuntimeFailure as failure:
            raise UnievalFailure(UnievalError.from_code(failure.code)) from None

    async def _observe_worker_exit(self) -> None:
        if self.status != "ready":
            if self.stop_task is not None:
                try:
                    await asyncio.shield(self.stop_task)
                except UnievalFailure as failure:
                    self.failure_code = failure.error.code
            return
        if self.worker.is_alive:
            return
        try:
            await self.fail_worker("WORKER_EXITED")
        except UnievalFailure as failure:
            self.failure_code = failure.error.code
        try:
            self.diagnostic(LifecycleFields(action="failed", level="ERROR", code=self.failure_code))
        except RuntimeFailure:
            self.failure_code = "LOGGING_FAILED"

    async def _stop_worker(self) -> None:
        if (
            self.stop_task is None
            or self.stop_task.cancelled()
            or (self.stop_task.done() and not self.worker.exit_confirmed)
        ):
            self.stop_task = asyncio.create_task(self.worker.stop())
        await asyncio.shield(self.stop_task)

    async def process(self, state: UnievalState, reservation: Reservation) -> None:
        state.queue_operation = create_child_operation(state.operation_metadata)
        try:
            await self.queue.wait(reservation)
        except RuntimeFailure as failure:
            raise UnievalFailure(UnievalError.from_code(failure.code)) from None
        if state.request is None or reservation.promoted_at is None:
            raise UnievalFailure(UnievalError.from_code("INTERNAL_ERROR"))
        self.active_task = asyncio.current_task()
        state.model, state.worker = self.worker.model, self.worker.worker
        state.queue_ms = (reservation.promoted_at - reservation.reserved_at) * 1000
        started = time.monotonic()
        state.evaluation_operation = create_child_operation(state.operation_metadata)
        try:
            async with asyncio.timeout(self.settings.evaluation.timeout_ms / 1000):
                await self.worker.send(
                    UnievalCommand(
                        version=UNIEVAL_WORKER_VERSION,
                        operation_metadata=state.evaluation_operation,
                        execution_id=state.execution_id,
                        generation=self.worker.generation,
                        request=state.request,
                    )
                )
                while True:
                    reply = (await self.worker.receive()).root
                    if not isinstance(reply, (UnievalPrepared, UnievalPrediction, UnievalFinished)):
                        raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
                    if (
                        reply.execution_id != state.execution_id
                        or reply.generation != self.worker.generation
                    ):
                        raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
                    if isinstance(reply, UnievalPrepared):
                        state.accept_plan(reply, self.settings)
                    elif isinstance(reply, UnievalPrediction):
                        state.accept_prediction(reply)
                    else:
                        state.require_finished()
                        break
        except TimeoutError:
            await self.stop_failed_request(state, UnievalError.from_code("EVALUATION_TIMEOUT"))
        except UnievalFailure as failure:
            await self.stop_failed_request(state, failure.error)
        except asyncio.CancelledError:
            try:
                await self.fail_worker("CLIENT_DISCONNECTED")
            except UnievalFailure as cleanup:
                state.errors.append(cleanup.error)
            raise
        finally:
            state.scoring_ms = (time.monotonic() - started) * 1000
            self.active_task = None

    async def stop_failed_request(self, state: UnievalState, error: UnievalError) -> None:
        state.errors.append(error)
        try:
            await self.fail_worker(error.code)
        except UnievalFailure as cleanup:
            state.errors.append(cleanup.error)

    async def fail_worker(self, code: UnievalErrorCode = "WORKER_NOT_READY") -> None:
        self.queue.ready = False
        self.status, self.failure_code = "stopping" if self.stopping else "failed", code
        for reservation in tuple(self.queue.reservations.values()):
            if reservation.owner is not None:
                reservation.owner.cancel()
        try:
            await self._stop_worker()
        except UnievalFailure:
            self.failure_code = "WORKER_STOP_FAILED"
            raise

    async def shutdown(self) -> None:
        self.stopping = True
        self.status = "stopping"
        self.queue.close()
        tasks = [task for task in (self.loading_task, self.active_task) if task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        async with asyncio.timeout(self.settings.worker.shutdown_timeout_ms / 1000):
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await self._stop_worker()
        self.diagnostic(
            LifecycleFields(action="stopped", level="INFO"),
            create_child_operation(self.service_operation),
        )
