"""Which shared listener and explicit route groups can one API process use?"""

from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from summary_evaluator.shared.contracts.base import PositiveCount, RelativePath
from summary_evaluator.shared.contracts.server_contract import ServerContract, ServerSchemaVersion
from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings

ApiComponent = Literal["hhem", "unieval"]


class ApiSettings(ServerContract):
    """Freeze the single listener and the components enabled for this invocation."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-07",
            "readCompatibility": (
                "previous single-listener settings resolve only to a maintained scorer"
            ),
            "changelog": [
                {"version": "2026-11-07", "change": "Retain HHEM and native UniEval selection."}
            ],
        }
    )

    version: ServerSchemaVersion
    listener: ListenerSettings
    enabled_routes: tuple[ApiComponent, ...] = Field(
        description="Enabled API components for this invocation; phases may select a subset."
    )
    logging: LoggingSettings
    log_directory: RelativePath
    shutdown_timeout_ms: PositiveCount

    @model_validator(mode="after")
    def require_distinct_routes(self) -> Self:
        if len(set(self.enabled_routes)) != len(self.enabled_routes):
            raise ValueError("enabled_routes must contain distinct component names")
        return self
