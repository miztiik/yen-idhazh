"""Which committed listener belongs to each independently started scorer API?"""

from typing import Self, get_args

from pydantic import ConfigDict, model_validator

from summary_evaluator.serve_http.contracts.api_settings import (
    API_SETTINGS_SCHEMA_VERSION,
    ApiComponent,
    ApiSettingsVersion,
)
from summary_evaluator.shared.contracts.base import PositiveCount, RelativePath
from summary_evaluator.shared.contracts.server_contract import ServerContract
from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings


class ApiDeploymentSettings(ServerContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": API_SETTINGS_SCHEMA_VERSION,
            "readCompatibility": (
                "frozen two/three-listener or single-listener settings resolve "
                "with propagation disabled"
            ),
            "changelog": [
                {
                    "version": API_SETTINGS_SCHEMA_VERSION,
                    "change": "Configure actual API and worker trace propagation.",
                },
                {"version": "2026-11-07", "change": "Separate HHEM and UniEval listeners."},
            ],
        }
    )

    version: ApiSettingsVersion
    listeners: dict[ApiComponent, ListenerSettings]
    logging: LoggingSettings
    propagate_trace_context: bool
    log_directory: RelativePath
    shutdown_timeout_ms: PositiveCount

    @model_validator(mode="after")
    def require_distinct_declared_listeners(self) -> Self:
        if set(self.listeners) != set(get_args(ApiComponent)):
            raise ValueError("Every declared scorer requires its own listener")
        bindings = {(listener.host, listener.port) for listener in self.listeners.values()}
        if len(bindings) != len(self.listeners):
            raise ValueError("Scorer API listeners must not collide")
        return self
