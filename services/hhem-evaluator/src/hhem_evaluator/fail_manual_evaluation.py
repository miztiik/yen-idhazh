"""How are caller failures projected without input or exception text?"""

from typing import Literal

from .contracts.workflow_report import (
    FAILURE_MESSAGES,
    FailureCode,
    FailurePhase,
    WorkflowError,
)


class WorkflowFailure(Exception):
    def __init__(
        self,
        code: FailureCode,
        phase: FailurePhase,
        service: Literal["hhem", "host", "caller"] = "caller",
        http_status: int | None = None,
    ) -> None:
        self.error = WorkflowError(
            code=code,
            phase=phase,
            service=service,
            http_status=http_status,
            message=FAILURE_MESSAGES[code],
        )
        super().__init__(self.error.message)
