"""Which owned process identity can be reported without inventing a pin?"""

from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from .base import NativeContract, PositiveCount

PinUnavailableReason = Literal[
    "unsupported_platform",
    "process_not_found",
    "process_read_failed",
    "process_identity_invalid",
    "process_identity_too_large",
]
StartTicks = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9]+$")]


class WorkerIdentity(NativeContract):
    """Pair a positive worker generation and PID with an observed pin or reason."""

    generation: PositiveCount
    pid: PositiveCount
    start_ticks: StartTicks | None
    pin_unavailable_reason: PinUnavailableReason | None

    @model_validator(mode="after")
    def require_observation_or_reason(self) -> Self:
        if (self.start_ticks is None) != (self.pin_unavailable_reason is not None):
            raise ValueError("start_ticks requires a pin or an unavailable reason, not both")
        return self
