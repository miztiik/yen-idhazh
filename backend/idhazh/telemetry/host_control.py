"""Does this invocation collect host readings, independently of its memory sub-control?"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal

from idhazh.contracts.knobs.observability import ObservabilityConfig

HostTelemetryMode = Literal["typescript", "off"]
MODE_ENV = "IDHAZH_HOST_TELEMETRY_MODE"
DEFAULT_MODE: HostTelemetryMode = "typescript"
HOST_TELEMETRY_MODES = (DEFAULT_MODE, "off")


def mode(
    observability: ObservabilityConfig, environ: Mapping[str, str] | None = None
) -> HostTelemetryMode:
    environment = os.environ if environ is None else environ
    requested = environment.get(MODE_ENV) or DEFAULT_MODE
    if requested != DEFAULT_MODE and requested != "off":
        raise ValueError(f"{MODE_ENV} must be typescript or off")
    if not observability.host_telemetry_enabled or requested == "off":
        return "off"
    return DEFAULT_MODE


def enabled(
    observability: ObservabilityConfig, environ: Mapping[str, str] | None = None
) -> bool:
    return mode(observability, environ) != "off"


def memory_override(environ: Mapping[str, str] | None = None) -> bool | None:
    """Resolve the workflow memory choice without accepting truthy strings."""
    environment = os.environ if environ is None else environ
    request = environment.get("MEMORY_PROFILING", "inherit")
    if request == "inherit":
        return None
    if request == "on":
        return True
    if request == "off":
        return False
    raise ValueError("MEMORY_PROFILING must be inherit, on or off")
