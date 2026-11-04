"""Who owns UniEval admission, independent readiness and bounded process shutdown?"""

import asyncio
import time
from pathlib import Path

from .contracts.server_event import ApiDiagnosticData
from .contracts.unieval_contract import UNIEVAL_VERSION
from .contracts.unieval_error import UnievalError, UnievalErrorCode
from .contracts.unieval_result import UnievalHealth
from .contracts.unieval_settings import UnievalSettings
from .contracts.unieval_worker_message import (
    UnievalCommand,
    UnievalFinished,
    UnievalPrediction,
    UnievalPrepared,
)
from .emit_events import EventWriter
from .fail_evaluation import EvaluationFailure
from .fail_unieval import UnievalFailure
from .maintain_unieval_worker import UnievalSupervisor
from .queue_evaluations import EvaluationQueue, Reservation
from .reduce_unieval import UnievalState


class UnievalController:
    def __init__(
        self,
        settings: UnievalSettings,
        root: Path,
        writer: EventWriter,
        service_instance_id: str,
        *,
        supervisor: UnievalSupervisor | None = None,
    ) -> None:
        self.settings, self.writer = settings, writer
        self.worker = supervisor or UnievalSupervisor(settings, root)
        self.queue = EvaluationQueue(settings.queue)
        self.instance_id = service_instance_id
        self.status = "loading"
        self.failure_code: UnievalErrorCode | None = None
        self.loading_task: asyncio.Task[None] | None = None
        self.active_task: asyncio.Task[None] | None = None
        self.stopping = False

    def health(self) -> UnievalHealth:
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
        self.writer.diagnostic(
            ApiDiagnosticData(component="unieval", action="started", level="INFO")
        )
        self.loading_task = asyncio.create_task(self._load())

    async def _load(self) -> None:
        try:
            await self.worker.start()
            self.status = "ready"
            self.queue.ready = True
            self.queue.promote()
            self.writer.diagnostic(
                ApiDiagnosticData(component="unieval", action="ready", level="INFO")
            )
        except (UnievalFailure, EvaluationFailure) as failure:
            self.queue.ready = False
            self.failure_code, self.status = failure.error.code, "failed"
            try:
                self.writer.diagnostic(
                    ApiDiagnosticData(
                        component="unieval",
                        action="failed",
                        level="ERROR",
                        code=failure.error.code,
                    )
                )
            except EvaluationFailure:
                self.failure_code = "LOGGING_FAILED"
            try:
                await self.worker.stop()
            except UnievalFailure as cleanup:
                self.failure_code = cleanup.error.code
                try:
                    self.writer.diagnostic(
                        ApiDiagnosticData(
                            component="unieval",
                            action="failed",
                            level="ERROR",
                            code=cleanup.error.code,
                        )
                    )
                except EvaluationFailure:
                    self.failure_code = "LOGGING_FAILED"

    def reserve(self, state: UnievalState) -> Reservation:
        if self.stopping:
            raise UnievalFailure(UnievalError.from_code("SERVICE_STOPPED"))
        if self.status != "ready":
            raise UnievalFailure(UnievalError.from_code("WORKER_NOT_READY"))
        return self.queue.reserve(state.execution_id)

    async def process(self, state: UnievalState, reservation: Reservation) -> None:
        await self.queue.wait(reservation)
        if state.request is None or reservation.promoted_at is None:
            raise UnievalFailure(UnievalError.from_code("INTERNAL_ERROR"))
        self.active_task = asyncio.current_task()
        state.model, state.worker = self.worker.model, self.worker.worker
        state.queue_ms = (reservation.promoted_at - reservation.reserved_at) * 1000
        started = time.monotonic()
        try:
            async with asyncio.timeout(self.settings.evaluation.timeout_ms / 1000):
                await self.worker.send(
                    UnievalCommand(
                        version=UNIEVAL_VERSION,
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
            await asyncio.shield(self.worker.stop())
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
            await self.worker.stop()
        self.writer.diagnostic(
            ApiDiagnosticData(component="unieval", action="stopped", level="INFO")
        )
