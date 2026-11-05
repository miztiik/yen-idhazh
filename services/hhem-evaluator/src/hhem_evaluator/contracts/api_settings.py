"""Which shared listener and explicit route groups can one API process use?"""

from typing import Literal, Self

from pydantic import Field, model_validator

from .base import PositiveCount, RelativePath
from .server_contract import ServerContract, ServerSchemaVersion
from .service_settings import ListenerSettings, LoggingSettings

ApiComponent = Literal["hhem", "llama", "unieval"]


class LlamaTransportSettings(ServerContract):
    """Bound forwarding without selecting weights or a native destination."""

    connect_timeout_ms: PositiveCount
    health_timeout_ms: PositiveCount
    max_response_bytes: PositiveCount
    max_inflight_requests: PositiveCount


class ApiSettings(ServerContract):
    """Freeze the single listener and the components enabled for this invocation."""

    version: ServerSchemaVersion
    listener: ListenerSettings
    enabled_routes: tuple[ApiComponent, ...] = Field(
        description="Enabled API components for this invocation; phases may select a subset."
    )
    logging: LoggingSettings
    log_directory: RelativePath
    shutdown_timeout_ms: PositiveCount
    llama: LlamaTransportSettings

    @model_validator(mode="after")
    def require_distinct_routes(self) -> Self:
        if len(set(self.enabled_routes)) != len(self.enabled_routes):
            raise ValueError("enabled_routes must contain distinct component names")
        return self
