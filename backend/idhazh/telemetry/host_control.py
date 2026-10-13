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
    if mode not in (None, "", "rust", "legacy", "off"):
        raise ValueError("IDHAZH_HOST_TELEMETRY_MODE must be rust, legacy or off")
    return observability.host_telemetry_enabled and mode != "off"
