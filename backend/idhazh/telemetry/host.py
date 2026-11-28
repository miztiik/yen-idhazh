"""Which native host facts reach an item, and how is its target process pinned?"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from idhazh.contracts.base import ServerJob

PROC: Final = Path("/proc")
_PROC_READ_LIMIT_BYTES: Final = 1 << 20
# Linux stat field 22, counted from the state after the parenthesized name.
_PROC_START_TIME_AFTER_COMM: Final = 19


def process_start_ticks(pid: int | None) -> int | None:
    """Pin only the named process; a missing or unverified identity stays unknown."""
    if pid is None or pid <= 0:
        return None
    try:
        with (PROC / str(pid) / "stat").open("rb") as reading:
            raw = reading.read(_PROC_READ_LIMIT_BYTES + 1)
    except (FileNotFoundError, ProcessLookupError, PermissionError, NotADirectoryError):
        return None
    if len(raw) > _PROC_READ_LIMIT_BYTES:
        return None
    pid_text, _, stat = raw.partition(b" (")
    _, closing, tail = stat.rpartition(b")")
    if pid_text != str(pid).encode("ascii") or not closing:
        return None
    cells = tail.split()
    if len(cells) <= _PROC_START_TIME_AFTER_COMM:
        return None
    ticks = cells[_PROC_START_TIME_AFTER_COMM]
    return int(ticks) if ticks.isdigit() else None


@dataclass(frozen=True)
class HostFacts:
    """Opening host facts shared by the items of one shard."""

    cpu_model: str | None
    runner_name: str | None
    job: ServerJob | None = None
    pipeline_name: str | None = None
    task_name: str | None = None

    def shard_cells(self) -> dict[str, str | None]:
        return {
            "cpu_model": self.cpu_model,
            "machine_job": None if self.job is None else self.job.value,
            **({
                "machine_pipeline_name": self.pipeline_name,
                "machine_task_name": self.task_name,
            } if self.pipeline_name is not None else {}),
        }


@dataclass(frozen=True)
class HostCells:
    """Native readings projected onto the item-health row."""

    cpu_busy_pct: float | None
    cpu_busy_max: float | None
    cpu_busy_min: float | None
    cpu_steal_pct: float | None
    load_1m: float | None
    llama_rss_bytes: int | None
    llama_rss_anon_bytes: int | None
    llama_rss_peak_bytes: int | None
    llama_major_faults: int | None
    python_rss_bytes: int | None
    python_rss_anon_bytes: int | None
    os_mem_available_bytes: int | None
    os_mem_total_bytes: int | None
    os_mem_cached_bytes: int | None
    os_swap_free_bytes: int | None
    os_swap_total_bytes: int | None
    os_mem_available_min_bytes: int | None

    def cells(self) -> dict[str, float | int | None]:
        return asdict(self)
