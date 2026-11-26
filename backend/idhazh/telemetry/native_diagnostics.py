"""How do local utilities read native benchmark observations without another listener?"""

from __future__ import annotations

import os
import subprocess
from typing import Literal

from pydantic import TypeAdapter

from idhazh import config
from idhazh.telemetry import machine_api
from idhazh.telemetry.host import process_start_ticks

_COMMAND = "services/host-probes/src/diagnostics/read-utility-host.ts"
_MODEL: TypeAdapter[str | None] = TypeAdapter(str | None)
_PEAK: TypeAdapter[int | None] = TypeAdapter(int | None)
_CGROUP: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])


def _read[T](
    schema: TypeAdapter[T], operation: Literal["cpu-model", "rss-peak", "cgroup"], *args: str,
) -> T | None:
    try:
        result = subprocess.run(
            ["bun", "run", "--no-install", _COMMAND, operation, *args],
            cwd=config.REPO_ROOT, stdout=subprocess.PIPE, check=False,
        )
        if result.returncode:
            raise machine_api.MachineApiError("native diagnostic command failed")
        return schema.validate_json(result.stdout, strict=True)
    except (OSError, ValueError, machine_api.MachineApiError) as error:
        machine_api.unavailable(operation, "native diagnostic", error)
        return None


def cpu_model() -> str | None:
    return _read(_MODEL, "cpu-model")


def peak_memory_gib() -> float | None:
    pid = os.getpid()
    ticks = process_start_ticks(pid)
    if ticks is None:
        return None
    peak = _read(_PEAK, "rss-peak", str(pid), str(ticks))
    return None if peak is None else round(peak / (1024 * 1024), 2)


def cgroup_snapshot(*, memory_profiling_enabled: bool) -> dict[str, object] | None:
    return _read(_CGROUP, "cgroup", "on" if memory_profiling_enabled else "off")
