"""Which private packets identify exactly one owned scorer API process?"""

from typing import Annotated, Final, Literal

from pydantic import ConfigDict, Field, RootModel, StrictBool
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.base import PositiveCount, RelativePath, Uuid4
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.worker_exit import WorkerExit

from .contracts import SourceCode, WorkflowContract
from .control import StartupPacket

SCORER_CONTROL_VERSION: Final = "2026-11-07"


class ScorerContract(WorkflowContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": SCORER_CONTROL_VERSION,
            "readCompatibility": "current_only; private owned scorer API controls",
            "changelog": [
                {"version": SCORER_CONTROL_VERSION, "change": "Identify one owned scorer API."}
            ],
        }
    )


class ScorerStartupPacket(ScorerContract):
    version: Literal["2026-11-07"]
    scorer: ApiComponent
    startup: StartupPacket

    @property
    def startup_id(self) -> str:
        return self.startup.startup_id

    @property
    def phase(self) -> Literal["generation", "evaluation"]:
        return self.startup.phase


class ScorerPacket(ScorerContract):
    version: Literal["2026-11-07"]
    service: Literal["api"]
    scorer: ApiComponent
    startup_id: Uuid4


class ScorerReply(ScorerPacket):
    process: ProcessIdentity

    @property
    def pid(self) -> int:
        return self.process.pid


class ScorerReady(ScorerReply):
    kind: Literal["ready"]
    service_instance_id: Uuid4
    log_file: RelativePath | None
    log_available: StrictBool


class ScorerStopped(ScorerReply):
    kind: Literal["stopped"]
    clean: StrictBool
    worker_exit: WorkerExit
    log_file: RelativePath | None
    log_available: StrictBool
    error_code: SourceCode | None = None
    cleanup_error_code: SourceCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)


class ScorerStartFailed(ScorerPacket):
    kind: Literal["failed"]
    pid: PositiveCount
    error_code: SourceCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)


class ScorerControl(
    RootModel[
        Annotated[
            ScorerReady | ScorerStopped | ScorerStartFailed, Field(discriminator="kind")
        ]
    ]
):
    pass
