"""What was the machine doing, at the two grains that ask - one sampler, two consumers.

A throughput number with no machine beside it is not a measurement (Guardrail
#10), and two readers of one machine fact are two answers nobody can reconcile.
So every host reading this project takes is taken here, once, and handed to both
things that write it down:

- **the item row**, through `Watch`, around one item. A shard figure cannot say
  whether one slow item met a noisy neighbour, which is the question a 4.2x
  between-runner spread raises.
- **`state/runtime-counters.csv`**, through `stage_counters`, at shard grain.
  That store is the independent check on the census's own timings, so it stays a
  separate store: a check folded into the thing it checks stops being a check.

The two grains are the point and they are not the same number. `cpu_busy_pct` on
an item row is that item's window; on the shard row it is the whole job,
including the cache restore and the weight load. What must never differ is a
fact that does not change inside a job - the processor, the runner label - and
those come from one `host_facts()` call.

**Every source is a local file read.** `/proc/stat`, `/proc/loadavg`,
`/proc/self/status`, `/proc/<server pid>/status` and the cgroup peak file - one
`open()` each, against a median 475,890 ms of model time. `psutil` would be a
dependency, its install time and its shipped bytes for arithmetic that is four
lines (Guardrail #8). What one reading costs is in
`docs/reference/measurements.md`.

**The arithmetic is not written twice.** `contracts.runtime_counters` already
differences two `/proc/stat` captures into a busy share, and this module calls
that rather than reproducing it (Guardrail #5). What is new here is the reading,
not the maths.

**A reading that cannot be taken records empty and never raises.** None of these
paths exists on the developer machines this project is written on, and a missing
instrument degrades the row rather than the run (CLAUDE.md section 1a).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh import assemble, ledger
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.runtime_counters import (
    WORK_JOB,
    RuntimeCountersRow,
    ServerJob,
    cpu_busy_pct_between,
)
from idhazh.fingerprint import host_cpu

LOG: Final = logging.getLogger("idhazh")

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

#: The key the shard job writes the kernel's peak under when it copies that file
#: into `memory-peak.txt`. The copy exists so the runtime artifact and the
#: operator get the number too. It is the same file, so it is read by the same
#: function rather than by a second parser somewhere else.
CGROUP_PEAK_KEY: Final = "cgroup_memory_peak_bytes"

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


def cgroup_peak_bytes(reported: str | None = None) -> int | None:
    """What the kernel counted against the job's memory limit, at its highest.

    One reader, and the one fact arrives in two shapes. The kernel writes a bare
    count. The shard job copies that count into `memory-peak.txt` as
    `cgroup_memory_peak_bytes=<count>`, and writes the word `unavailable` where
    the kernel file is not there - which is what a GitHub-hosted runner has
    measured every time. `reported` is that copy; with no copy in hand this opens
    the kernel file itself. Anything that is not a plain count reads as unknown,
    and unknown is not zero.
    """
    text = _text(CGROUP_PEAK) if reported is None else reported
    if not text:
        return None
    for line in text.splitlines():
        key, found, raw = line.strip().partition("=")
        value = raw.strip() if found and key.strip() == CGROUP_PEAK_KEY else line.strip()
        if value.isdigit():
            return int(value)
    return None


def cpu_model(reported: str | None = None) -> str | None:
    """The processor this job drew, in the host's own words.

    One reader, two callers. `reported` is what the shard job's first step read
    out of `/proc/cpuinfo` before a checkout existed; with nothing reported this
    reads the same file through `fingerprint.host_cpu`. Both answers are the same
    file on the same host, which is why the item row and the shard row cannot
    name two different processors.

    A probe that reported nothing and could read nothing records nothing: an
    empty cell means the reading was not taken, which is a different fact from a
    processor with no name.
    """
    named = (reported or "").strip() or host_cpu().strip()
    return named or None


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
class HostFacts:
    """Every host cell that both consumers name, taken in one call.

    The item row and `state/runtime-counters.csv` each carry a `cpu_model` and a
    `cgroup_peak_bytes` column, so a second reader on either side is two answers
    to one question and nothing to say which is right (Guardrail #10).
    """

    cpu_model: str | None
    runner_name: str | None
    cgroup_peak_bytes: int | None
    #: Which workflow job drew this machine. Not a reading - no file on the host
    #: says it - so it is handed in rather than probed for, and it travels here
    #: because it is one half of the key the item row joins the host record on.
    job: ServerJob | None = None

    def shard_cells(self) -> dict[str, str | None]:
        """The three a shard reads once and notes on every item it records.

        `job` is here rather than beside `shard` in the caller because the pair
        it forms is the join, and a key column filled in one place cannot drift
        from the machine cells filled in another.

        `cgroup_peak_bytes` is deliberately not here. It is a high-water mark
        that grows across a job, so an item row takes it again at the end of
        each item rather than once before the first one runs.
        """
        return {
            "cpu_model": self.cpu_model,
            "runner_name": self.runner_name,
            "job": None if self.job is None else self.job.value,
        }


def host_facts(
    *,
    reported_cpu_model: str | None = None,
    reported_cgroup_peak: str | None = None,
    environ: dict[str, str] | None = None,
    job: ServerJob | None = None,
) -> HostFacts:
    """One call, so that no two consumers disagree about what machine this was.

    Every argument is something the platform already handed a caller - the shard
    job reads the processor and copies the kernel peak in its own shell, before
    Python exists. Hand over nothing and nothing is assumed: each reading falls
    back to the file this module would have opened anyway.

    `job` is the one argument with no fallback, because there is nothing to fall
    back to: no file on the host names the workflow job, and a default would
    claim a machine for every row that never said which job it was.
    """
    return HostFacts(
        cpu_model=cpu_model(reported_cpu_model),
        runner_name=runner_name(environ),
        cgroup_peak_bytes=cgroup_peak_bytes(reported_cgroup_peak),
        job=job,
    )


@dataclass(frozen=True, slots=True)
class HostReading:
    """One instant, as this machine reported it."""

    #: The raw aggregate `cpu` line, kept rather than parsed: the busy share is
    #: a difference of two of these and a single one answers nothing.
    cpu_stat: str | None
    load_1m: float | None
    llama_rss_bytes: int | None
    llama_rss_peak_bytes: int | None
    python_rss_bytes: int | None


def read_now(*, server_pid: int | None = None) -> HostReading:
    """Every point-in-time reading, taken together so they describe one instant."""
    return HostReading(
        cpu_stat=_text(PROC_STAT),
        load_1m=load_1m(),
        llama_rss_bytes=_status_kb(server_pid, "VmRSS"),
        llama_rss_peak_bytes=_status_kb(server_pid, "VmHWM"),
        python_rss_bytes=_status_kb(os.getpid(), "VmRSS"),
    )


@dataclass(frozen=True, slots=True)
class HostCells:
    """What the machine did across one item, as cells the census row names.

    Not called a span. `telemetry.Span` is one node of the trace tree and lives
    two modules away, and two things called a span inside one package is how a
    reader loses ten minutes.
    """

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

    `facts` is the sampler call this watch shares with whatever else writes the
    same column names. A run hands over nothing and the watch reads the kernel
    peak itself at close, which is what a high-water mark wants - and it reads
    only that one file, because the processor cannot change inside a shard.
    """

    __slots__ = (
        "_busy",
        "_facts",
        "_first",
        "_interval",
        "_last",
        "_on_tick",
        "_pid",
        "_stop",
        "_thread",
    )

    def __init__(
        self,
        *,
        interval_s: float,
        server_pid: int | None = None,
        on_tick: Callable[[float], None] | None = None,
        facts: HostFacts | None = None,
    ) -> None:
        self._interval = interval_s
        self._pid = server_pid
        self._on_tick = on_tick
        self._facts = facts
        self._busy: list[float] = []
        self._first = read_now(server_pid=server_pid)
        self._last = self._first
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Watch:
        if self._interval > 0:
            self._thread = threading.Thread(target=self._sample, name="host-watch", daemon=True)
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

    def close(self) -> HostCells:
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
        # Only the kernel peak, never a whole `host_facts`. The processor cannot
        # change inside a shard, so reading it again here would be one extra
        # `/proc/cpuinfo` open on every item for an answer already on the row.
        peak = cgroup_peak_bytes() if self._facts is None else self._facts.cgroup_peak_bytes
        return HostCells(
            cpu_busy_pct=whole,
            cpu_busy_max=max(seen) if seen else None,
            cpu_busy_min=min(seen) if seen else None,
            load_1m=end.load_1m,
            llama_rss_bytes=end.llama_rss_bytes,
            llama_rss_peak_bytes=max(peaks) if peaks else None,
            python_rss_bytes=end.python_rss_bytes,
            cgroup_peak_bytes=peak,
        )


def stage_counters(
    plan: RunPlan,
    *,
    state_root: Path,
    metrics_path: Path,
    shard: int = 0,
    shards: int = 1,
    job: str = WORK_JOB,
    job_started_at: int | None = None,
    cpu_model_reported: str | None = None,
    cpu_stat_at_start: str | None = None,
    cpu_stat_at_end: str | None = None,
    rss_samples_path: Path | None = None,
    server_log_path: Path | None = None,
    memory_peak_path: Path | None = None,
    facts: HostFacts | None = None,
) -> RuntimeCountersRow:
    """Commit what this shard's model server counted, so the ledger can be checked.

    Every timing on the item-health ledger is a field the summarize stage copied
    out of one model reply. The server's own counters are the second instrument,
    and until now they reached only a job log that keeps them for two days - so
    the rates two published surfaces quote could not be reconciled with anything
    (Guardrail #10).

    Both counters are cumulative for the server process and a shard runs one
    server for its whole job, so this one read covers the shard entirely.

    The same row carries the job's own facts as well as the server's: the clock,
    the host, how busy that host was, the window one sequence got, three memory
    high points and what the weights cost to open. The server's counters and the
    job's clock arrive as files this stage opens. **The host's readings arrive
    from `host_facts`, which is the call the item row's `Watch` takes as well**,
    so the processor named on an item row and the processor named on that shard's
    row are one reading rather than two that happen to agree.

    A missing or empty body still writes a row, with every counter null. A shard
    whose server was already gone and a shard that never ran are different facts,
    and pooling a run needs to see the shard that contributed nothing.

    `job` is which of the two model-server jobs this is. It is on the row because
    the two serve different weights, so nothing downstream can pool them and
    nothing can tell them apart without it.
    """
    read = (
        host_facts(
            reported_cpu_model=cpu_model_reported,
            reported_cgroup_peak=_text_if_readable(memory_peak_path) or None,
        )
        if facts is None
        else facts
    )
    row = RuntimeCountersRow.from_metrics_text(
        _text_if_readable(metrics_path),
        date=plan.date,
        run_id=plan.run_id,
        shard=shard,
        shards=shards,
        scraped_at=assemble.utc_now(),
        job=job,
        job_started_at=job_started_at,
        cpu_model=read.cpu_model,
        cpu_stat_at_start=cpu_stat_at_start,
        cpu_stat_at_end=cpu_stat_at_end,
        rss_samples=_text_if_readable(rss_samples_path),
        server_log=_text_if_readable(server_log_path),
        cgroup_peak_bytes=read.cgroup_peak_bytes,
    )
    landed = ledger.append_runtime_counters(state_root, [row])
    LOG.info(
        "counted job=%s shard=%s/%s run=%s read_tokens=%s read_seconds=%s job_seconds=%s "
        "cpu=%s cpu_busy_pct=%s peak_rss_bytes=%s model_load_ms=%s n_ctx_configured=%s "
        "python_peak_rss_bytes=%s cgroup_peak_bytes=%s rows=%s",
        row.job,
        shard,
        shards,
        plan.run_id,
        row.prompt_tokens_total,
        row.prompt_seconds_total,
        row.job_seconds,
        row.cpu_model,
        row.cpu_busy_pct,
        row.peak_rss_bytes,
        row.model_load_ms,
        row.n_ctx_configured,
        row.python_peak_rss_bytes,
        row.cgroup_peak_bytes,
        landed,
    )
    return row


def _text_if_readable(path: Path | None) -> str:
    """A file the job may not have written is absent text, never a failed stage."""
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
