"""Which exit was actually observed for the selected scorer's owned model process?"""

from typing import Self

from pydantic import StrictBool, model_validator

from summary_evaluator.shared.contracts.base import PositiveCount
from summary_evaluator.shared.contracts.server_contract import ServerContract


class WorkerExit(ServerContract):
    pid: PositiveCount | None
    exit_code: int | None
    confirmed: StrictBool | None

    @model_validator(mode="after")
    def require_actual_exit(self) -> Self:
        if self.confirmed is None and (self.pid is not None or self.exit_code is not None):
            raise ValueError("An unstarted worker has no exit observation")
        if self.confirmed is True and (self.pid is None or self.exit_code is None):
            raise ValueError("Confirmed worker exit requires its actual PID and exit code")
        return self
