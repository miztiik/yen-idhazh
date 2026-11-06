"""Which enabled components and diagnostic file are actually available?"""

from typing import Literal, Self

from pydantic import StrictBool, model_validator

from summary_evaluator.hhem.contracts.service_health import ServiceHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.base import RelativePath, Uuid4
from summary_evaluator.shared.contracts.server_contract import ServerContract, ServerSchemaVersion
from summary_evaluator.unieval.contracts.unieval_result import UnievalHealth


class DisabledEvaluatorHealth(ServerContract):
    """Report a disabled scorer without loading or inventing its settings."""

    status: Literal["disabled"] = "disabled"
    worker: None = None
    model: None = None


class ApiHealth(ServerContract):
    """Keep component observations separate from aggregate server readiness."""

    version: ServerSchemaVersion
    service_instance_id: Uuid4
    enabled_routes: tuple[ApiComponent, ...]
    status: Literal["disabled", "loading", "ready", "failed", "stopping"]
    hhem: ServiceHealth | DisabledEvaluatorHealth
    unieval: UnievalHealth | DisabledEvaluatorHealth
    log_file: RelativePath | None
    log_available: StrictBool

    @model_validator(mode="after")
    def require_enabled_readiness(self) -> Self:
        components = {"hhem": self.hhem, "unieval": self.unieval}
        states = [components[component].status for component in self.enabled_routes]
        if self.status == "ready" and (not states or any(state != "ready" for state in states)):
            raise ValueError("Ready requires every enabled component to be ready")
        if self.status == "disabled" and self.enabled_routes:
            raise ValueError("Disabled requires an empty component selection")
        if self.log_available and self.log_file is None:
            raise ValueError("An available log requires its filename")
        return self

    @property
    def http_status(self) -> int:
        return 200 if self.status == "ready" else 503
