"""How are phase failures projected without input or exception text?"""

from .contracts import (
    FAILURE_MESSAGES,
    FailureCode,
    FailurePhase,
    PipelineError,
    ServiceName,
)


class WorkflowError(Exception):
    def __init__(
        self,
        code: FailureCode,
        phase: FailurePhase,
        service: ServiceName = "caller",
        http_status: int | None = None,
        *,
        source_code: str | None = None,
    ) -> None:
        self.error = PipelineError(
            code=code,
            phase=phase,
            service=service,
            http_status=http_status,
            message=FAILURE_MESSAGES[code],
            source_code=source_code,
        )
        super().__init__(self.error.message)
