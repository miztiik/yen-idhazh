"""Which private packets identify exactly one owned scorer API process?"""

from typing import Annotated, Final, Literal, Self

from local_api_host.propagate_trace_context import OperationMetadata
from pydantic import ConfigDict, Field, RootModel, StrictBool, model_validator
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.base import PositiveCount, RelativePath, Uuid4
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.worker_exit import WorkerExit

from .contracts import SourceCode, WorkflowContract
from .control import StartupPacket
from .previous_scorer_control import PreviousScorerControl, PreviousScorerStartupPacket

SCORER_CONTROL_VERSION: Final = "2026-11-08"


class ScorerContract(WorkflowContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": SCORER_CONTROL_VERSION,
            "readCompatibility": "read 2026-11-07 controls without adding trace metadata",
            "changelog": [
                {
                    "version": SCORER_CONTROL_VERSION,
                    "change": "Bind owned scorer launch and observed service operations.",
                },
                {"version": "2026-11-07", "change": "Identify one owned scorer API."},
            ],
        }
    )


class ScorerStartupPacket(ScorerContract):
    version: Literal["2026-11-08"]
    scorer: ApiComponent
    startup: StartupPacket
    operation_metadata: OperationMetadata

    @property
    def startup_id(self) -> str:
        return self.startup.startup_id

    @property
    def phase(self) -> Literal["generation", "evaluation"]:
        return self.startup.phase


class ScorerStartup(
    RootModel[
        Annotated[
            ScorerStartupPacket | PreviousScorerStartupPacket, Field(discriminator="version")
        ]
    ]
):
    model_config = ConfigDict(json_schema_extra=ScorerContract.model_config["json_schema_extra"])


class ScorerPacket(ScorerContract):
    version: Literal["2026-11-08"]
    service: Literal["api"]
    scorer: ApiComponent
    startup_id: Uuid4
    launch_operation_metadata: OperationMetadata
    operation_metadata: OperationMetadata

    @model_validator(mode="after")
    def require_launched_service_operation(self) -> Self:
        launch, service = self.launch_operation_metadata, self.operation_metadata
        if (
            service.trace_id != launch.trace_id
            or service.parent_span_id != launch.span_id
            or service.trace_state != launch.trace_state
            or service.links
        ):
            raise ValueError("The service operation must be a child of the issued launch")
        return self


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


type CurrentScorerControl = Annotated[
    ScorerReady | ScorerStopped | ScorerStartFailed, Field(discriminator="kind")
]


class ScorerControl(RootModel[
    Annotated[CurrentScorerControl | PreviousScorerControl, Field(discriminator="version")]
]):
    model_config = ConfigDict(json_schema_extra=ScorerContract.model_config["json_schema_extra"])
