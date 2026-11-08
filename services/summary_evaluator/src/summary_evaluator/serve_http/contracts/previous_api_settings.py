"""Which exact previous listener shapes may resolve to a maintained scorer?"""

from typing import Literal, Self, get_args

from pydantic import ConfigDict, model_validator

from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.base import PositiveCount, RelativePath
from summary_evaluator.shared.contracts.server_contract import ServerContract
from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings

PreviousApiComponent = Literal["hhem", "unieval", "coverage"]


class PreviousApiSettings(ServerContract):
    """Validate the frozen single-listener input, never a live route selection."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-07",
            "readCompatibility": "read_only; select one maintained scorer before use",
            "changelog": [
                {"version": "2026-11-07", "change": "Freeze previous single-listener settings."}
            ],
        }
    )

    version: Literal["2026-11-07"]
    listener: ListenerSettings
    enabled_routes: tuple[PreviousApiComponent, ...]
    logging: LoggingSettings
    log_directory: RelativePath
    shutdown_timeout_ms: PositiveCount

    @model_validator(mode="after")
    def require_distinct_routes(self) -> Self:
        if len(set(self.enabled_routes)) != len(self.enabled_routes):
            raise ValueError("enabled_routes must contain distinct component names")
        return self


class PreviousApiDeploymentSettings(ServerContract):
    """Validate all three authored bindings without enabling the retired scorer."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-07",
            "readCompatibility": "read_only; resolve only the selected maintained listener",
            "changelog": [
                {"version": "2026-11-07", "change": "Freeze previous three-listener settings."}
            ],
        }
    )

    version: Literal["2026-11-07"]
    listeners: dict[PreviousApiComponent, ListenerSettings]
    logging: LoggingSettings
    log_directory: RelativePath
    shutdown_timeout_ms: PositiveCount

    @model_validator(mode="after")
    def require_distinct_declared_listeners(self) -> Self:
        if set(self.listeners) != set(get_args(PreviousApiComponent)):
            raise ValueError("Every previous scorer requires its authored listener")
        bindings = {(listener.host, listener.port) for listener in self.listeners.values()}
        if len(bindings) != len(self.listeners):
            raise ValueError("Scorer API listeners must not collide")
        return self


class PreviousTwoListenerApiDeploymentSettings(ServerContract):
    """Read the delivered two-listener shape without accepting new propagation fields."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-07",
            "readCompatibility": (
                "read_only; resolve a maintained listener with propagation disabled"
            ),
            "changelog": [
                {"version": "2026-11-07", "change": "Freeze previous two-listener settings."}
            ],
        }
    )

    version: Literal["2026-11-07"]
    listeners: dict[ApiComponent, ListenerSettings]
    logging: LoggingSettings
    log_directory: RelativePath
    shutdown_timeout_ms: PositiveCount

    @model_validator(mode="after")
    def require_distinct_declared_listeners(self) -> Self:
        if set(self.listeners) != set(get_args(ApiComponent)):
            raise ValueError("Every maintained scorer requires its authored listener")
        bindings = {(listener.host, listener.port) for listener in self.listeners.values()}
        if len(bindings) != len(self.listeners):
            raise ValueError("Scorer API listeners must not collide")
        return self
