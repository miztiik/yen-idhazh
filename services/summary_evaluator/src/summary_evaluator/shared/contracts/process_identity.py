"""Which actual API process is identified by a PID and an observed kernel start pin?"""

from typing import Self

from pydantic import model_validator

from summary_evaluator.shared.contracts.base import PositiveCount
from summary_evaluator.shared.contracts.server_contract import ServerContract
from summary_evaluator.shared.contracts.worker_identity import PinUnavailableReason, StartTicks


class ProcessIdentity(ServerContract):
    pid: PositiveCount
    start_ticks: StartTicks | None
    pin_unavailable_reason: PinUnavailableReason | None

    @model_validator(mode="after")
    def require_observation_or_reason(self) -> Self:
        if (self.start_ticks is None) != (self.pin_unavailable_reason is not None):
            raise ValueError("A process requires a pin or an unavailable reason, not both")
        return self
