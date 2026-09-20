"""What was the machine doing, around one item - one sampler, one set of columns.

A throughput number with no machine beside it is not a measurement (Guardrail
#10), and two readers of one machine fact are two answers nobody can reconcile.
So every host reading this project takes is taken here, once, and handed to the
thing that writes it down: **the item row**, through `Watch`, around one item. A
shard figure cannot say whether one slow item met a noisy neighbour, which is
the question a 4.2x between-runner spread raises, so the item window is the
grain this module serves.

What must never differ between two items of one shard is a fact that does not
change inside a job - the processor, the runner label - so those come from one
`host_facts()` call taken before the first item runs.

**Every source is a local file read.** `/proc/stat`, `/proc/loadavg`,
`/proc/meminfo`, `/proc/self/status`, `/proc/<server pid>/status` and the cgroup
peak file - one `open()` each, against a median 475,890 ms of model time.
`psutil` would be a dependency, its install time and its shipped bytes for
arithmetic that is four lines (Guardrail #8). What one reading costs is in
`docs/reference/pipeline-cost.md`.

**The `/proc/stat` arithmetic lives here, beside the reading it differences.**
`cpu_ticks` and `cpu_busy_pct_between` are pure functions over text the caller
opened, so they stay testable without a Linux box, and there is one copy of them
rather than one per consumer (Guardrail #5).

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

from idhazh.contracts.base import ServerJob
from idhazh.fingerprint import host_cpu

#: The aggregate processor counters, since boot. Differenced, never read alone:
#: a single read is mostly the runner's idle boot.
PROC_STAT: Final = Path("/proc/stat")

#: The columns of the aggregate `cpu` line of `/proc/stat`, in the order the
#: kernel prints them. A kernel that publishes fewer is read as far as it goes.
#: `/proc/stat` rather than a cgroup file on purpose: this project has measured
#: `/sys/fs/cgroup/memory.peak` and `/sys/fs/cgroup/cpu.max` both absent on a
#: GitHub-hosted runner, and `/proc/stat` is on every Linux there is.
_CPU_FIELDS: Final = (
    "user",
    "nice",
    "system",
    "idle",
    "iowait",
    "irq",
    "softirq",
    "steal",
    "guest",
    "guest_nice",
)

#: Time the processors were available and took no work. Everything else is busy.
_CPU_IDLE: Final = frozenset({"idle", "iowait"})

#: The kernel counts guest time inside `user` and guest-nice inside `nice` as
#: well as reporting it again, so a plain sum of the line counts it twice.
_CPU_DOUBLE_COUNTED: Final = ("guest", "guest_nice")

#: One-minute load, first field.
LOADAVG: Final = Path("/proc/loadavg")

#: The whole machine's own account of its memory. Every other reading in this
#: module is about a PROCESS, and no sum of process marks answers what is left:
#: llama.cpp maps the weights with no `-lm`, so their resident pages are
#: file-backed and evictable in every RSS figure, and a page two processes share
#: is counted twice.
MEMINFO: Final = Path("/proc/meminfo")

#: The five `/proc/meminfo` lines this project reads, spelled the kernel's way.
#: One open answers all five, because five opens would describe five instants.
MEMINFO_KEYS: Final = ("MemTotal", "MemAvailable", "Cached", "SwapFree", "SwapTotal")

#: Where a process reports its own resident and peak-resident memory.
PROC: Final = Path("/proc")

#: The two `/proc/<pid>/status` lines this project reads, spelled the kernel's
#: way. `VmRSS` is what the process holds now. `VmHWM` is the larger of that and
#: a mark the kernel refreshes only when the process itself gives memory back -
#: so it is a whole-life figure that a reclaimed page can still pull DOWN, and
#: not a peak that only rises (`docs/reference/host-metrics.md`). One open
#: answers both, because two opens would describe two instants.
STATUS_KEYS: Final = ("VmRSS", "VmHWM")

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


def _kb_keys(text: str | None, keys: tuple[str, ...]) -> dict[str, int | None]:
    """`Key:<space><count> kB` lines, by key, in bytes.

    `/proc/meminfo` and `/proc/<pid>/status` both print that layout, so one
    parser serves both rather than one per reader (Guardrail #5). The kernel
    reports the counts in kilobytes, so the conversion happens here and not at
    each caller.

    A key the text does not carry stays unknown, and unknown is not zero
    (CLAUDE.md section 1a). The key has to match whole: `VmHWM` and `VmPeak` are
    two different facts that share a prefix.
    """
    found: dict[str, int | None] = dict.fromkeys(keys)
    if text is None:
        return found
    for line in text.splitlines():
        name, marked, rest = line.partition(":")
        key = name.strip()
        if not marked or key not in found:
            continue
        cells = rest.split()
        if cells and cells[0].isdigit():
            found[key] = int(cells[0]) * _KB
    return found


def status_bytes(pid: int | None) -> dict[str, int | None]:
    """What one process holds now and its high-water mark, from one open.

    Two lines of one file, read together because they have to describe one
    instant - the same reason `meminfo_bytes` below takes its five keys in one
    read.

    A pid nobody named, or a process this machine will not open, answers two
    unknowns and never raises. That is the ordinary path on every machine this
    project is written on.
    """
    if pid is None:
        return dict.fromkeys(STATUS_KEYS)
    return _kb_keys(_text(PROC / str(pid) / "status"), STATUS_KEYS)


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


def cpu_ticks(text: str | None) -> dict[str, int] | None:
    """The aggregate `cpu` line of `/proc/stat`, by field name.

    Reads the line out of whatever it is handed, so a whole capture of the file
    with the per-processor lines still attached is the same fact as the one line
    on its own. Anything else - an empty string, a truncated read - is absent
    rather than a zero reading.

    A pure function over text the caller opened, so the arithmetic below can be
    checked on a machine that has no `/proc` at all.
    """
    if not text:
        return None
    for line in text.splitlines():
        cells = line.split()
        if cells[:1] != ["cpu"] or len(cells) < 2:
            continue
        ticks: dict[str, int] = {}
        for name, raw in zip(_CPU_FIELDS, cells[1:], strict=False):
            if not raw.isdigit():
                return None
            ticks[name] = int(raw)
        return ticks
    return None


def cpu_busy_pct_between(at_start: str | None, at_end: str | None) -> float | None:
    """Busy processor time as a share of processor time available, between two reads.

    Differencing two reads is what makes this the window's number rather than
    the host's: `/proc/stat` counts since boot, and a runner boots minutes of
    mostly idle time before the job starts. The denominator is every processor's
    time, so nothing here needs to know how many there are.
    """
    start = cpu_ticks(at_start)
    end = cpu_ticks(at_end)
    if start is None or end is None:
        return None
    totals = []
    idles = []
    for ticks in (start, end):
        totals.append(sum(ticks.values()) - sum(ticks.get(n, 0) for n in _CPU_DOUBLE_COUNTED))
        idles.append(sum(ticks.get(n, 0) for n in _CPU_IDLE))
    available = totals[1] - totals[0]
    if available <= 0:
        return None
    busy = available - (idles[1] - idles[0])
    return round(100 * busy / available, 2)


def meminfo_bytes(reported: str | None = None) -> dict[str, int | None]:
    """The five `/proc/meminfo` lines this project reads, in bytes.

    One open for five readings, because they have to describe one instant.

    A machine with no `/proc/meminfo` answers five unknowns and never raises,
    which is what every machine this project is written on does. A key the file
    does not carry is unknown for the same reason, and unknown is not zero
    (CLAUDE.md section 1a) - a box with no swap writes a real `SwapTotal: 0`,
    and that is a different fact from a box that was never asked.
    """
    text = _text(MEMINFO) if reported is None else reported
    return _kb_keys(text, MEMINFO_KEYS)


def cgroup_peak_bytes() -> int | None:
    """What the kernel counted against the job's memory limit, at its highest.

    The kernel writes a bare count, so a file that holds anything else reads as
    unknown - and unknown is not zero. Absent is the reading a GitHub-hosted
    runner has given every time this project has probed one, which is why it
    degrades rather than raising.
    """
    text = _text(CGROUP_PEAK)
    if not text:
        return None
    value = text.strip()
    return int(value) if value.isdigit() else None


def cpu_model() -> str | None:
    """The processor this job drew, in the host's own words.

    Read through `fingerprint.host_cpu`, which opens `/proc/cpuinfo` on a runner
    and falls back to `platform.processor()` on a developer machine. One reader,
    so two rows of one shard cannot name two different processors.

    A probe that could read nothing records nothing: an empty cell means the
    reading was not taken, which is a different fact from a processor with no
    name.
    """
    return host_cpu().strip() or None


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
    """Every host cell that does not change inside a job, taken in one call.

    A shard reads these once and notes them on every item it records, so a
    second reader would be two answers to one question and nothing to say which
    is right (Guardrail #10).

    `runner_name` is the one field no consumer of this class takes any more -
    the item row retired the column on 2026-09-17. It stays because this is the
    one call that reads the environment, and the host record's own producer
    takes the same reading through `runner_name()` below: dropping it here would
    leave the label read in one place and nowhere to compare it against.
    """

    cpu_model: str | None
    runner_name: str | None
    cgroup_peak_bytes: int | None
    #: Which workflow job drew this machine. Not a reading - no file on the host
    #: says it - so it is handed in rather than probed for, and it travels here
    #: because it is one half of the key the item row joins the host record on.
    job: ServerJob | None = None

    def shard_cells(self) -> dict[str, str | None]:
        """The two a shard reads once and notes on every item it records.

        `job` is here rather than beside `shard` in the caller because the pair
        it forms is the join, and a key column filled in one place cannot drift
        from the machine cells filled in another.

        **`runner_name` left on 2026-09-17 and stays on this class.** The item
        row no longer has the column - the host record carries the label once a
        job, and `job` with `shard` is how an item reaches that record. What is
        still read here is the one call that takes it, so nothing else has to
        open the environment a second time.

        `cgroup_peak_bytes` is deliberately not here. It is a high-water mark
        that grows across a job, so an item row takes it again at the end of
        each item rather than once before the first one runs.
        """
        return {
            "cpu_model": self.cpu_model,
            "job": None if self.job is None else self.job.value,
        }


def host_facts(
    *,
    environ: dict[str, str] | None = None,
    job: ServerJob | None = None,
) -> HostFacts:
    """One call, so that no two items of one shard disagree about what machine this was.

    Every reading here opens a file or the environment, and every one of them
    degrades to empty on a machine that does not have it.

    `job` is the one argument, because there is nothing to fall back to: no file
    on the host names the workflow job, and a default would claim a machine for
    every row that never said which job it was.
    """
    return HostFacts(
        cpu_model=cpu_model(),
        runner_name=runner_name(environ),
        cgroup_peak_bytes=cgroup_peak_bytes(),
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
    #: What the MACHINE had at this instant, against the four process marks
    #: above. `mem_available_bytes` is the kernel's own estimate of what a new
    #: allocation could get, which is the question a headroom decision asks.
    mem_available_bytes: int | None
    mem_total_bytes: int | None
    mem_cached_bytes: int | None
    swap_free_bytes: int | None
    swap_total_bytes: int | None


def read_now(*, server_pid: int | None = None) -> HostReading:
    """Every point-in-time reading, taken together so they describe one instant."""
    machine = meminfo_bytes()
    server = status_bytes(server_pid)
    ours = status_bytes(os.getpid())
    return HostReading(
        cpu_stat=_text(PROC_STAT),
        load_1m=load_1m(),
        llama_rss_bytes=server["VmRSS"],
        llama_rss_peak_bytes=server["VmHWM"],
        python_rss_bytes=ours["VmRSS"],
        mem_available_bytes=machine["MemAvailable"],
        mem_total_bytes=machine["MemTotal"],
        mem_cached_bytes=machine["Cached"],
        swap_free_bytes=machine["SwapFree"],
        swap_total_bytes=machine["SwapTotal"],
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
    #: What the machine had, against the four process marks above. The last one
    #: is the only cell here taken over the window rather than at its end: the
    #: closest this item took the machine to running out.
    os_mem_available_bytes: int | None
    os_mem_total_bytes: int | None
    os_mem_cached_bytes: int | None
    os_swap_free_bytes: int | None
    os_swap_total_bytes: int | None
    os_mem_available_min_bytes: int | None

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
            "os_mem_available_bytes": self.os_mem_available_bytes,
            "os_mem_total_bytes": self.os_mem_total_bytes,
            "os_mem_cached_bytes": self.os_mem_cached_bytes,
            "os_swap_free_bytes": self.os_swap_free_bytes,
            "os_swap_total_bytes": self.os_swap_total_bytes,
            "os_mem_available_min_bytes": self.os_mem_available_min_bytes,
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
        "_headroom",
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
        self._headroom: list[int] = []
        self._first = read_now(server_pid=server_pid)
        self._note_headroom(self._first)
        self._last = self._first
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _note_headroom(self, reading: HostReading) -> None:
        """Keep what the kernel said was left, so the item's floor is this item's.

        The window matters more than the arithmetic. A shard's job is about nine
        times an item's model time and most items overlap, so a floor taken over
        the job would put one number on nearly every row.
        """
        if reading.mem_available_bytes is not None:
            self._headroom.append(reading.mem_available_bytes)

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
            self._note_headroom(now)
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
        self._note_headroom(end)
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
            os_mem_available_bytes=end.mem_available_bytes,
            os_mem_total_bytes=end.mem_total_bytes,
            os_mem_cached_bytes=end.mem_cached_bytes,
            os_swap_free_bytes=end.swap_free_bytes,
            os_swap_total_bytes=end.swap_total_bytes,
            os_mem_available_min_bytes=min(self._headroom) if self._headroom else None,
        )
