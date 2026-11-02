"""How are caller failures projected without input or exception text?"""

from typing import Literal

from .contracts import (
    FAILURE_MESSAGES,
    FailureCode,
    FailurePhase,
    PipelineError,
)


class WorkflowError(Exception):
    def __init__(
        self,
        code: FailureCode,
        phase: FailurePhase,
        service: Literal["hhem", "host", "caller"] = "caller",
        http_status: int | None = None,
    ) -> None:
        self.error = PipelineError(
            code=code,
            phase=phase,
            service=service,
            http_status=http_status,
            message=FAILURE_MESSAGES[code],
        )
        super().__init__(self.error.message)
