"""Who owns admission, readiness, active cancellation and replacement?"""

import asyncio
import time
from pathlib import Path

from .contracts.base import SCHEMA_VERSION, ServiceStatus
from .contracts.error_detail import ErrorCode, ErrorDetail
from .contracts.evaluation_event import EventDetails
from .contracts.service_health import ServiceHealth
from .contracts.service_settings import ServiceSettings, StartupContext
from .emit_events import EventEmitter, EventPhase, EventWriter
from .fail_evaluation import EvaluationFailure
from .maintain_worker import WorkerSupervisor
from .queue_evaluations import EvaluationQueue, Reservation
from .resolve_ids import create_execution_id
from .score_windows import EvaluationState, score_windows


class EvaluationController:
    """Serialize lifecycle changes while keeping HTTP health independent."""

    def __init__(
        self,
        settings: ServiceSettings,
        context: StartupContext,
        root: Path,
        *,
        supervisor: WorkerSupervisor | None = None,
        writer: EventWriter | None = None,
    ) -> None:
        self.settings = settings
        self.context = context
        self.worker = supervisor or WorkerSupervisor(settings, context, root)
        self.writer = writer or EventWriter(settings.logging)
        self.queue = EvaluationQueue(settings.queue)
        self.instance_id = create_execution_id()
        self.status: ServiceStatus = "loading" if settings.enabled else "disabled"
        self.failure_code: ErrorCode | None = None
        self.lifecycle = EventEmitter(self.writer, context)
        self.maintenance_lock = asyncio.Lock()
        self.loading_task: asyncio.Task[None] | None = None
        self.active_task: asyncio.Task[object] | None = None
        self.recovery_task: asyncio.Task[None] | None = None
        self.stopping = False

    def health(self) -> ServiceHealth:
        return ServiceHealth(
            version=SCHEMA_VERSION,
            service_instance_id=self.instance_id,
            status=self.status,
            worker=self.worker.worker,
            model=self.worker.model,
            queue_depth=self.queue.depth,
            queue_capacity=self.settings.queue.capacity,
            failure_code=self.failure_code,
        )

    async def start(self) -> None:
        try:
            self.lifecycle.emit("service", "started", EventDetails(status=self.status))
        except EvaluationFailure:
            self.status, self.failure_code = "failed", "LOGGING_FAILED"
            return
        if self.settings.enabled:
            self.loading_task = asyncio.create_task(self._load())

    async def _load(self) -> None:
        async with self.maintenance_lock:
            try:
                cause = self.lifecycle.emit(
                    "worker",
                    "started",
                    EventDetails(status=self.status),
                    cause=self.lifecycle.last_event_id,
                )
                await self.worker.start()
                if self.worker.worker is None or self.worker.model is None:
                    raise EvaluationFailure(ErrorDetail.from_code("WORKER_NOT_READY", "worker"))
                self.lifecycle.emit(
                    "worker",
                    "completed",
                    EventDetails(worker=self.worker.worker, model=self.worker.model),
                    cause=cause,
                )
                self.status, self.failure_code = "ready", None
                self.queue.ready = True
                self.queue.promote()
            except EvaluationFailure as failure:
                await self._fail_loading(failure.error)

    async def _fail_loading(self, error: ErrorDetail) -> None:
        self.queue.ready = False
        self.status, self.failure_code = "failed", error.code
        errors = [error]
        try:
            await self.worker.stop()
        except EvaluationFailure as cleanup:
            errors.append(cleanup.error)
            self.failure_code = cleanup.error.code
        try:
            self.lifecycle.emit(
                "worker",
                "failed",
                EventDetails(status="failed", errors=tuple(errors)),
                cause=self.lifecycle.last_event_id,
            )
        except EvaluationFailure:
            self.failure_code = "LOGGING_FAILED"

    def reserve(self, state: EvaluationState) -> Reservation:
        code: ErrorCode | None = None
        if self.stopping:
            code = "SERVICE_STOPPED"
        elif not self.settings.enabled:
            code = "SERVICE_DISABLED"
        elif self.status != "ready":
            code = "WORKER_NOT_READY"
        if code is not None:
            raise EvaluationFailure(ErrorDetail.from_code(code, "request"))
        return self.queue.reserve(state.emitter.execution_id)

    async def process(self, state: EvaluationState, reservation: Reservation) -> None:
        cause = state.emitter.emit(
            "queue",
            "started",
            EventDetails(queue_depth=self.queue.depth),
            cause=state.emitter.last_event_id,
        )
        try:
            await self.queue.wait(reservation)
        except EvaluationFailure as failure:
            state.emitter.emit(
                "queue", "failed", EventDetails(errors=(failure.error,)), cause=cause
            )
            raise
        except asyncio.CancelledError:
            state.emitter.emit("queue", "cancelled", EventDetails(), cause=cause)
            raise
        if reservation.promoted_at is None:
            raise EvaluationFailure(ErrorDetail.from_code("INTERNAL_ERROR", "queue"))
        state.queue_wait_ms = (reservation.promoted_at - reservation.reserved_at) * 1000
        state.model, state.worker = self.worker.model, self.worker.worker
        state.deadline = reservation.promoted_at + self.settings.evaluation.timeout_ms / 1000
        self.active_task = asyncio.current_task()
        try:
            state.emitter.emit(
                "queue",
                "completed",
                EventDetails(duration_ms=state.queue_wait_ms, queue_depth=self.queue.depth),
                cause=cause,
            )
            async with asyncio.timeout_at(state.deadline):
                await score_windows(state, self.worker)
        except TimeoutError:
            error = ErrorDetail.from_code(
                "EVALUATION_TIMEOUT", "full" if state.primary_score is not None else "primary"
            )
            await self.fail_active(state, error)
        except EvaluationFailure as failure:
            await self.fail_active(state, failure.error)
        except asyncio.CancelledError:
            if not state.recovery_started:
                try:
                    state.emitter.emit(
                        "full" if state.primary_score is not None else "primary",
                        "cancelled",
                        EventDetails(),
                        cause=state.emitter.last_event_id,
                    )
                except EvaluationFailure as failure:
                    state.errors.append(failure.error)
            await self.recover(state)
            raise
        finally:
            if self.active_task is asyncio.current_task():
                self.active_task = None

    async def fail_active(self, state: EvaluationState, error: ErrorDetail) -> None:
        state.errors.append(error)
        try:
            state.emitter.emit(
                error.phase,
                "failed",
                EventDetails(errors=(error,)),
                cause=state.emitter.last_event_id,
            )
        except EvaluationFailure as logging:
            if not any(item.code == "LOGGING_FAILED" for item in state.errors):
                state.errors.append(logging.error)
        await self.recover(state)

    async def recover(self, state: EvaluationState) -> None:
        """Join before loading again; queued reservations retain their deadlines."""
        if state.recovery_task is not None and not state.recovery_task.done():
            await asyncio.shield(state.recovery_task)
            return
        if state.recovery_started and not state.emitter.logging_failed:
            return
        state.recovery_started = True
        self.queue.ready = False
        self.status = "stopping" if self.stopping else "replacing"
        task = asyncio.create_task(self._recover_worker(state))
        state.recovery_task = self.recovery_task = task
        await asyncio.shield(task)

    async def _recover_worker(self, state: EvaluationState) -> None:
        if (
            state.emitter.logging_failed
            and self.loading_task is not None
            and not self.loading_task.done()
        ):
            self.loading_task.cancel()
            await asyncio.gather(self.loading_task, return_exceptions=True)
        async with self.maintenance_lock:
            try:
                await self.worker.stop()
            except EvaluationFailure as failure:
                state.errors.append(failure.error)
                self.status, self.failure_code = "failed", failure.error.code
                return
            if self.stopping:
                return
            if state.emitter.logging_failed:
                self.status, self.failure_code = "failed", "LOGGING_FAILED"
                return
        # The failed caller waits for confirmed exit, not a replacement model load.
        self.loading_task = asyncio.create_task(self._load())

    def terminal(self, state: EvaluationState, *, disconnected: bool = False) -> str | None:
        phase: EventPhase
        if disconnected:
            errors = (
                ErrorDetail.from_code("CLIENT_DISCONNECTED", "request"),
                *state.errors,
            )
            phase = "cancelled"
        else:
            errors = tuple(state.errors)
            phase = "failed" if errors else "completed"
        elapsed = (time.monotonic() - state.received_at) * 1000
        details = (
            EventDetails(duration_ms=elapsed, errors=errors)
            if errors
            else EventDetails(duration_ms=elapsed)
        )
        try:
            return state.emitter.emit(
                "request",
                phase,
                details,
                cause=state.emitter.last_event_id,
            )
        except EvaluationFailure as failure:
            if not any(error.code == "LOGGING_FAILED" for error in state.errors):
                state.errors.append(failure.error)
            return None

    async def shutdown(self) -> None:
        self.stopping, self.status = True, "stopping"
        self.queue.close()
        try:
            async with asyncio.timeout(self.settings.worker.shutdown_timeout_ms / 1000):
                if self.loading_task is not None and not self.loading_task.done():
                    self.loading_task.cancel()
                    await asyncio.gather(self.loading_task, return_exceptions=True)
                owners = [
                    reservation.owner
                    for reservation in self.queue.reservations.values()
                    if reservation.owner is not None
                ]
                if self.queue.active is not None and self.queue.active.owner is not None:
                    owners.append(self.queue.active.owner)
                if self.active_task is not None and not self.active_task.done():
                    owners.append(self.active_task)
                if owners:
                    await asyncio.gather(*owners, return_exceptions=True)
                if self.recovery_task is not None and not self.recovery_task.done():
                    await asyncio.shield(self.recovery_task)
                async with self.maintenance_lock:
                    await self.worker.stop()
                self.lifecycle.emit(
                    "service",
                    "completed",
                    EventDetails(status="stopping"),
                    cause=self.lifecycle.last_event_id,
                )
        except TimeoutError:
            self.status, self.failure_code = "failed", "WORKER_STOP_FAILED"
            raise EvaluationFailure(
                ErrorDetail.from_code("WORKER_STOP_FAILED", "service")
            ) from None
        except EvaluationFailure as failure:
            self.status, self.failure_code = "failed", failure.error.code
            raise
