"""What the machine was doing while one item ran.

A throughput number with no machine beside it is not a measurement
(Guardrail #10), and until now the only machine readings this project took were
at shard grain, in `state/runtime-counters.csv`, written from shell captures the
workflow handed to `stages.counters`. A shard figure cannot say whether one slow
item met a noisy neighbour, which is the question a 4.2x between-runner spread
raises. So the same readings are taken here, around one item.

**Every source is a local file read.** `/proc/stat`, `/proc/loadavg`,
`/proc/self/status`, `/proc/<server pid>/status` and the cgroup peak file - one
`open()` each, a few milliseconds against a median 475,890 ms of model time.
`psutil` would be a dependency, its install time and its shipped bytes for
arithmetic that is four lines (Guardrail #8).

**The arithmetic is not written twice.** `contracts.runtime_counters` already
differences two `/proc/stat` captures into a busy share, and this module calls
that rather than reproducing it (Guardrail #5). What is new here is the reading,
not the maths: nothing in the pipeline had ever opened these files in-process.

**A reading that cannot be taken records empty and never raises.** None of these
paths exists on the developer machines this project is written on, and a missing
instrument degrades the row rather than the run (CLAUDE.md section 1a).
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.contracts.runtime_counters import cpu_busy_pct_between

#: The aggregate processor counters, since boot. Differenced, never read alone:
#: a single read is mostly the runner's idle boot.
PROC_STAT: Final = Path("/proc/stat")

#: One-minute load, first field.
LOADAVG: Final = Path("/proc/loadavg")

#: Where a process reports its own resident and peak-resident memory.
PROC: Final = Path("/proc")

#: The kernel's own high-water mark for the whole job. Measured absent on every
#: GitHub-hosted runner this project has probed, which is why it degrades rather
#: than failing - and why it is worth reading anyway: it is the number the runner
#: would kill the job over (Guardrail #2).
CGROUP_PEAK: Final = Path("/sys/fs/cgroup/memory.peak")

#: `/proc` reports these in kilobytes.
_KB: Final = 1024


def _text(path: Path) -> str | None:
    """A file this machine may not have. Absent text, never a failed run."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _status_kb(pid: int | None, key: str) -> int | None:
    """One `VmRSS:`- or `VmHWM:`-shaped line of `/proc/<pid>/status`, in bytes."""
    if pid is None:
        return None
    text = _text(PROC / str(pid) / "status")
    if text is None:
        return None
    for line in text.splitlines():
        name, found, rest = line.partition(":")
        if found and name.strip() == key:
            cells = rest.split()
            if cells and cells[0].isdigit():
                return int(cells[0]) * _KB
    return None


def load_1m() -> float | None:
    """The one-minute load average, or nothing where the file is absent."""
    text = _text(LOADAVG)
    if text is None:
        return None
    cells = text.split()
    if not cells:
        return None
    try:
        return float(cells[0])
    except ValueError:
        return None


def cgroup_peak_bytes() -> int | None:
    """What the kernel counted against the job's memory limit, at its highest."""
    text = _text(CGROUP_PEAK)
    if text is None or not text.strip().isdigit():
        return None
    return int(text.strip())


def runner_name(environ: dict[str, str] | None = None) -> str | None:
    """The runner label this job drew, in the platform's own words.

    GitHub Actions publishes it. A developer machine publishes nothing and says
    so with an empty cell rather than with a name nobody can look up.
    """
    env = os.environ if environ is None else environ
    return env.get("RUNNER_NAME", "").strip() or None


def llama_server_pid(comm: str = "llama-server") -> int | None:
    """The inference server's process id, found by asking the kernel rather than being told.

    The server is started by the workflow shell and the pipeline never learns
    its pid, so the alternative is a new environment variable set in one place
    and read in another - a contract between a shell script and a stage, with
    nothing to check it (Guardrail #3).

    **The scan is bounded by the process table and not by anything the
    repository accumulates** (Guardrail #12): a runner holds a few hundred
    entries, each one a short file read, and the answer is taken once per shard.
    Nothing here is retried and nothing raises - a machine with no `/proc`
    returns nothing and the two RSS cells record empty, which is what a
    developer box already does.
    """
    try:
        entries = sorted(PROC.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        name = _text(entry / "comm")
        if name is not None and name.strip() == comm:
            return int(entry.name)
    return None


@dataclass(frozen=True, slots=True)
class Reading:
    """One instant, as this machine reported it."""

    #: The raw aggregate `cpu` line, kept rather than parsed: the busy share is
    #: a difference of two of these and a single one answers nothing.
    cpu_stat: str | None
    load_1m: float | None
    llama_rss_bytes: int | None
    llama_rss_peak_bytes: int | None
    python_rss_bytes: int | None


def read_now(*, server_pid: int | None = None) -> Reading:
    """Every point-in-time reading, taken together so they describe one instant."""
    return Reading(
        cpu_stat=_text(PROC_STAT),
        load_1m=load_1m(),
        llama_rss_bytes=_status_kb(server_pid, "VmRSS"),
        llama_rss_peak_bytes=_status_kb(server_pid, "VmHWM"),
        python_rss_bytes=_status_kb(os.getpid(), "VmRSS"),
    )


@dataclass(frozen=True, slots=True)
class Span:
    """What the machine did across one item, as cells the census row names."""

    cpu_busy_pct: float | None
    cpu_busy_max: float | None
    cpu_busy_min: float | None
    load_1m: float | None
    llama_rss_bytes: int | None
    llama_rss_peak_bytes: int | None
    python_rss_bytes: int | None
    cgroup_peak_bytes: int | None

    def cells(self) -> dict[str, float | int | None]:
        """The cells by the names `ItemHealthRow` gives them."""
        return {
            "cpu_busy_pct": self.cpu_busy_pct,
            "cpu_busy_max": self.cpu_busy_max,
            "cpu_busy_min": self.cpu_busy_min,
            "load_1m": self.load_1m,
            "llama_rss_bytes": self.llama_rss_bytes,
            "llama_rss_peak_bytes": self.llama_rss_peak_bytes,
            "python_rss_bytes": self.python_rss_bytes,
            "cgroup_peak_bytes": self.cgroup_peak_bytes,
        }


class Watch:
    """One thread, sampling the machine and ticking the caller, for one item.

    **It is one thread and not two on purpose.** The heartbeat that says a model
    call is still in flight and the sampler that takes the maximum and the
    minimum want the same interval and the same lifetime, and a second timer for
    the same readings is a second thing to start, stop and leak (Carmack,
    2026-09-14).

    `on_tick` receives the seconds elapsed since the watch opened. It is called
    from the sampling thread, so an emitter handed to it has to be safe there -
    `logging` is, which is the only one this project hands over.

    A zero or negative interval samples the two ends and never ticks, which is
    how `logging.waiting_heartbeat_seconds = 0` turns the heartbeat off without
    also turning the maximum and the minimum off.
    """

    __slots__ = ("_busy", "_first", "_interval", "_last", "_on_tick", "_pid", "_stop", "_thread")

    def __init__(
        self,
        *,
        interval_s: float,
        server_pid: int | None = None,
        on_tick: Callable[[float], None] | None = None,
    ) -> None:
        self._interval = interval_s
        self._pid = server_pid
        self._on_tick = on_tick
        self._busy: list[float] = []
        self._first = read_now(server_pid=server_pid)
        self._last = self._first
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Watch:
        if self._interval > 0:
            self._thread = threading.Thread(target=self._sample, name="machine-watch", daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _sample(self) -> None:
        opened = time.monotonic()
        previous = self._first
        while not self._stop.wait(self._interval):
            now = read_now(server_pid=self._pid)
            share = cpu_busy_pct_between(previous.cpu_stat, now.cpu_stat)
            if share is not None:
                self._busy.append(share)
            self._last = now
            previous = now
            if self._on_tick is not None:
                self._on_tick(round(time.monotonic() - opened, 1))

    def close(self) -> Span:
        """Stop sampling and return what the machine did, as cells.

        The mean is the whole-item difference rather than the mean of the
        samples, because that is the figure a reader can add up: it is busy
        ticks over available ticks across the item, and a mean of ratios taken
        over uneven intervals is not.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self._interval * 2, 1.0))
            self._thread = None
        end = read_now(server_pid=self._pid)
        self._last = end
        whole = cpu_busy_pct_between(self._first.cpu_stat, end.cpu_stat)
        seen = [*self._busy, *([] if whole is None else [whole])]
        peaks = [
            value
            for value in (self._first.llama_rss_peak_bytes, end.llama_rss_peak_bytes)
            if value is not None
        ]
        return Span(
            cpu_busy_pct=whole,
            cpu_busy_max=max(seen) if seen else None,
            cpu_busy_min=min(seen) if seen else None,
            load_1m=end.load_1m,
            llama_rss_bytes=end.llama_rss_bytes,
            llama_rss_peak_bytes=max(peaks) if peaks else None,
            python_rss_bytes=end.python_rss_bytes,
            cgroup_peak_bytes=cgroup_peak_bytes(),
        )
