"""Which native host facts and item cells does Python carry without collecting them?"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.contracts.base import ServerJob

PROC: Final = Path("/proc")


def runner_name(environ: dict[str, str] | None = None) -> str | None:
    """Read the platform's runner label, or leave it unknown on a developer machine."""
    env = os.environ if environ is None else environ
    return env.get("RUNNER_NAME", "").strip() or None


def llama_server_pid(comm: str = "llama-server") -> int | None:
    """Find the selected server in the bounded process table, without reading its resources."""
    try:
        entries = sorted(PROC.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / "comm").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if name.strip() == comm:
            return int(entry.name)
    return None


@dataclass(frozen=True, slots=True)
class HostFacts:
    """Stable native facts and the caller's job identity, shared by every item in a shard."""

    cpu_model: str | None
    runner_name: str | None
    job: ServerJob | None = None

    def shard_cells(self) -> dict[str, str | None]:
        """Carry the processor label and the job half of the host-record join key."""
        return {
            "cpu_model": self.cpu_model,
            "machine_job": None if self.job is None else self.job.value,
        }


@dataclass(frozen=True, slots=True)
class HostCells:
    """Native item-window measurements; an unmeasured window leaves every value unknown."""

    cpu_busy_pct: float | None = None
    cpu_busy_max: float | None = None
    cpu_busy_min: float | None = None
    cpu_steal_pct: float | None = None
    load_1m: float | None = None
    llama_rss_bytes: int | None = None
    llama_rss_anon_bytes: int | None = None
    llama_rss_peak_bytes: int | None = None
    llama_major_faults: int | None = None
    python_rss_bytes: int | None = None
    python_rss_anon_bytes: int | None = None
    os_mem_available_bytes: int | None = None
    os_mem_total_bytes: int | None = None
    os_mem_cached_bytes: int | None = None
    os_swap_free_bytes: int | None = None
    os_swap_total_bytes: int | None = None
    os_mem_available_min_bytes: int | None = None

    def cells(self) -> dict[str, float | int | None]:
        """Serialize every reading with its item-health column name."""
        return {
            "cpu_busy_pct": self.cpu_busy_pct,
            "cpu_busy_max": self.cpu_busy_max,
            "cpu_busy_min": self.cpu_busy_min,
            "cpu_steal_pct": self.cpu_steal_pct,
            "load_1m": self.load_1m,
            "llama_rss_bytes": self.llama_rss_bytes,
            "llama_rss_anon_bytes": self.llama_rss_anon_bytes,
            "llama_rss_peak_bytes": self.llama_rss_peak_bytes,
            "llama_major_faults": self.llama_major_faults,
            "python_rss_bytes": self.python_rss_bytes,
            "python_rss_anon_bytes": self.python_rss_anon_bytes,
            "os_mem_available_bytes": self.os_mem_available_bytes,
            "os_mem_total_bytes": self.os_mem_total_bytes,
            "os_mem_cached_bytes": self.os_mem_cached_bytes,
            "os_swap_free_bytes": self.os_swap_free_bytes,
            "os_swap_total_bytes": self.os_swap_total_bytes,
            "os_mem_available_min_bytes": self.os_mem_available_min_bytes,
        }
