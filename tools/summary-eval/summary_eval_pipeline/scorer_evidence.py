"""Which actual API process, readiness and exit observations belong to one scorer?"""

from typing import Final, Self

from pydantic import ConfigDict, model_validator
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.serve_http.read_api_health import ReadableApiHealth
from summary_evaluator.shared.contracts.base import Uuid4
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.service_settings import ListenerSettings
from summary_evaluator.shared.contracts.worker_exit import WorkerExit

from .contracts import PipelineError, ServerOutcome, WorkflowContract

EVIDENCE_VERSION: Final = "2026-11-07"


class EvidenceContract(WorkflowContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": EVIDENCE_VERSION,
            "readCompatibility": (
                "read frozen shared evidence and disabled-coverage health "
                "without inventing identity"
            ),
            "changelog": [
                {"version": EVIDENCE_VERSION, "change": "Keep independent maintained scorer APIs."}
            ],
        }
    )


class ScorerApiEvidence(EvidenceContract):
    scorer: ApiComponent
    listener: ListenerSettings
    process: ProcessIdentity | None
    service_instance_id: Uuid4 | None
    health: ReadableApiHealth | None
    worker_exit: WorkerExit
    outcome: ServerOutcome
    errors: tuple[PipelineError, ...]

    @model_validator(mode="after")
    def require_owned_observations(self) -> Self:
        if self.outcome.server_name != "fastapi-server":
            raise ValueError("Scorer evidence requires its own API outcome")
        if self.service_instance_id is not None and self.process is None:
            raise ValueError("An application identity requires its actual API process")
        if any(error.service not in ("api", self.scorer) for error in self.errors):
            raise ValueError("API errors must belong to their declared scorer")
        if self.outcome.log_available and self.outcome.log_filename is None:
            raise ValueError("An available API log requires its observed filename")
        if self.process is not None and self.worker_exit.pid == self.process.pid:
            raise ValueError("The API process is not its model worker")
        if self.health is not None:
            if (
                self.process is None
                or self.service_instance_id != self.health.service_instance_id
                or self.health.enabled_routes != (self.scorer,)
            ):
                raise ValueError("Health must identify the actual selected API process")
            for name in ("hhem", "unieval"):
                observed = getattr(self.health, name)
                if name != self.scorer and observed.status != "disabled":
                    raise ValueError("An independent API must not enable another scorer")
                if name == self.scorer and observed.status == "ready":
                    if observed.service_instance_id != self.service_instance_id:
                        raise ValueError("The scorer must identify its owned API")
                    if observed.worker is None or observed.worker.pid == self.process.pid:
                        raise ValueError("The scorer requires its independently owned model worker")
        if self.outcome.startup == "ready" and (
            self.health is None or self.health.status != "ready"
        ):
            raise ValueError("Ready API evidence requires observed model readiness")
        if self.outcome.shutdown == "stopped" and (
            self.process is None
            or self.outcome.exit_code != 0
            or self.worker_exit.confirmed is False
        ):
            raise ValueError("Stopped API evidence requires the actual successful process exit")
        if self.outcome.startup == "not_started" and (
            self.process is not None or self.health is not None
        ):
            raise ValueError("An unstarted API cannot claim process or readiness observations")
        return self
