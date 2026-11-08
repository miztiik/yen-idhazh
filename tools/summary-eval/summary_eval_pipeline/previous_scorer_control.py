"""Which untraced scorer controls remain readable with their original shape and version?"""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StrictBool
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.base import PositiveCount, RelativePath, Uuid4
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.worker_exit import WorkerExit

from .contracts import SourceCode, WorkflowContract
from .control import StartupPacket


class PreviousScorerContract(WorkflowContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-07",
            "readCompatibility": "read_only; retain genuinely untraced scorer controls",
            "changelog": [
                {"version": "2026-11-07", "change": "Identify one owned scorer API."}
            ],
        }
    )


class PreviousScorerStartupPacket(PreviousScorerContract):
    version: Literal["2026-11-07"]
    scorer: ApiComponent
    startup: StartupPacket

    @property
    def startup_id(self) -> str:
        return self.startup.startup_id

    @property
    def phase(self) -> Literal["generation", "evaluation"]:
        return self.startup.phase


class PreviousScorerPacket(PreviousScorerContract):
    version: Literal["2026-11-07"]
    service: Literal["api"]
    scorer: ApiComponent
    startup_id: Uuid4


class PreviousScorerReply(PreviousScorerPacket):
    process: ProcessIdentity

    @property
    def pid(self) -> int:
        return self.process.pid


class PreviousScorerReady(PreviousScorerReply):
    kind: Literal["ready"]
    service_instance_id: Uuid4
    log_file: RelativePath | None
    log_available: StrictBool


class PreviousScorerStopped(PreviousScorerReply):
    kind: Literal["stopped"]
    clean: StrictBool
    worker_exit: WorkerExit
    log_file: RelativePath | None
    log_available: StrictBool
    error_code: SourceCode | None = None
    cleanup_error_code: SourceCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)


class PreviousScorerStartFailed(PreviousScorerPacket):
    kind: Literal["failed"]
    pid: PositiveCount
    error_code: SourceCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)


type PreviousScorerControl = Annotated[
    PreviousScorerReady | PreviousScorerStopped | PreviousScorerStartFailed,
    Field(discriminator="kind"),
]
