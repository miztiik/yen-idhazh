"""How are finite body reservations promoted in validation-completion order?"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass

from .contracts.error_detail import ErrorDetail
from .contracts.service_settings import QueueSettings
from .fail_evaluation import EvaluationFailure


@dataclass
class Reservation:
    execution_id: str
    reserved_at: float
    deadline: float
    promoted: asyncio.Future[None]
    owner: asyncio.Task[object] | None
    promoted_at: float | None = None


class EvaluationQueue:
    """Count reading and queued work separately from the one active request."""

    def __init__(self, settings: QueueSettings) -> None:
        self.settings = settings
        self.reservations: dict[str, Reservation] = {}
        self.validated: deque[str] = deque()
        self.active: Reservation | None = None
        self.ready = False
        self.closed = False

    @property
    def depth(self) -> int:
        return len(self.reservations)

    def reserve(self, execution_id: str) -> Reservation:
        if self.closed:
            raise EvaluationFailure(ErrorDetail.from_code("SERVICE_STOPPED", "queue"))
        if self.depth >= self.settings.capacity:
            raise EvaluationFailure(ErrorDetail.from_code("QUEUE_FULL", "queue"))
        now = time.monotonic()
        reservation = Reservation(
            execution_id=execution_id,
            reserved_at=now,
            deadline=now + self.settings.wait_timeout_ms / 1000,
            promoted=asyncio.get_running_loop().create_future(),
            owner=asyncio.current_task(),
        )
        self.reservations[execution_id] = reservation
        return reservation

    async def wait(self, reservation: Reservation) -> None:
        self.validated.append(reservation.execution_id)
        self.promote()
        try:
            async with asyncio.timeout_at(reservation.deadline):
                await asyncio.shield(reservation.promoted)
        except TimeoutError:
            if self.active is reservation:
                return
            self.release(reservation)
            raise EvaluationFailure(ErrorDetail.from_code("QUEUE_TIMEOUT", "queue")) from None

    def promote(self) -> None:
        if not self.ready or self.closed or self.active is not None:
            return
        while self.validated:
            identity = self.validated.popleft()
            reservation = self.reservations.get(identity)
            if reservation is None:
                continue
            if time.monotonic() >= reservation.deadline:
                del self.reservations[identity]
                reservation.promoted.set_exception(
                    EvaluationFailure(ErrorDetail.from_code("QUEUE_TIMEOUT", "queue"))
                )
                continue
            del self.reservations[identity]
            self.active = reservation
            reservation.promoted_at = time.monotonic()
            reservation.promoted.set_result(None)
            return

    def release(self, reservation: Reservation) -> None:
        self.reservations.pop(reservation.execution_id, None)
        if reservation.execution_id in self.validated:
            self.validated.remove(reservation.execution_id)
        if not reservation.promoted.done():
            reservation.promoted.cancel()
        if self.active is reservation:
            self.active = None
        self.promote()

    def close(self) -> None:
        self.closed = True
        self.ready = False
        reservations = list(self.reservations.values())
        if self.active is not None:
            reservations.append(self.active)
        for reservation in reservations:
            if reservation.owner is not None:
                reservation.owner.cancel()
