"""Does this invocation collect host readings, independently of its memory sub-control?"""

from __future__ import annotations

import os
from collections.abc import Mapping

from idhazh.contracts.knobs.observability import ObservabilityConfig


def enabled(
    observability: ObservabilityConfig, environ: Mapping[str, str] | None = None
) -> bool:
    environment = os.environ if environ is None else environ
    mode = environment.get("IDHAZH_HOST_TELEMETRY_MODE")
    if mode not in (None, "", "python", "off"):
        raise ValueError("IDHAZH_HOST_TELEMETRY_MODE must be python or off")
    return observability.host_telemetry_enabled and mode != "off"


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
