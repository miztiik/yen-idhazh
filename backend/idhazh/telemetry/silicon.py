"""What silicon did this job draw, what can it do, and what did the job cost?

`host.py` answers what the machine is DOING and changes every second. This
answers what the machine IS and is fixed for the length of the job, so it is
read once rather than sampled.

Two steps write it, because two of its cells are only knowable at opposite ends
of a job: `stage_fingerprint` probes the machine before the heaviest step, and
`stage_job_clock` records the clock and the weight-load cost after the last item.
Both are filed through the ledger door and the settlement unites them: every
reader settles a day by key.

Every reading here degrades to nothing. None of these files or services exists
on a developer machine, and a missing instrument records an empty cell rather
than failing a run (CLAUDE.md section 1a).
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import statistics
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final

from idhazh import ledger, run_context
from idhazh.contracts.base import WORK_JOB, PipelineName, ServerJob, TaskName
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_fingerprint import (
    HOST_FINGERPRINT_VERSION,
    WATCHED_FLAGS,
    HostFingerprintRow,
    fingerprint_v2,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry.host import runner_name
from idhazh.telemetry.host_control import enabled as host_telemetry_enabled

if TYPE_CHECKING:  # pragma: no cover - a type, not a runtime dependency
    from idhazh import config

LOG: Final = logging.getLogger("idhazh")

#: The producer both halves of a job's host row file under. One name for the
#: probe and the clock is what makes the clock's whole row a later write of the
#: probe's work unit, so the door keeps the whole row and drops the half.
PRODUCER: Final = __name__.partition(".")[2]

#: The four cells only the end of a job can fill. The probe fills none of them.
CLOCK_CELLS: Final = (
    "model_load_ms",
    "job_seconds",
    "server_prompt_tokens",
    "server_prompt_seconds",
)

CPUINFO: Final = Path("/proc/cpuinfo")
UPTIME: Final = Path("/proc/uptime")
PROC: Final = Path("/proc")
CPU_ONLINE: Final = Path("/sys/devices/system/cpu/online")
CPU_ROOT: Final = Path("/sys/devices/system/cpu")
CGROUP_ROOT: Final = Path("/sys/fs/cgroup")
_PROC_READ_LIMIT_BYTES: Final = 1 << 20

#: The one spelling a payload timestamp leaves the process in, as `strptime`
#: reads it. `Timestamp` pins the same shape as a regex; this turns it back into
#: an instant so the job's own clock can be measured against its own scrape.
_SCRAPED_AT_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"

#: The two lines llama-server brackets its own model load with, on llama.cpp
#: `b10598`. Read from a real capture. A rename leaves the cell empty, which
#: reads as unknown - never as a load that took no time.
_LOAD_STARTED: Final = "load_model: loading model"
_LOAD_FINISHED: Final = "llama_server: model loaded"

#: How llama-server stamps a log line: minutes, seconds, milliseconds and
#: microseconds since its own process started. Decoded from a real capture
#: rather than from the source - the last field steps by 15 between two lines
#: printed back to back, which only works if it is microseconds.
_LOG_INSTANT: Final = re.compile(r"^(\d+)\.(\d{2})\.(\d{3})\.(\d{3}) ")

#: The Prometheus series each prompt cell is read from, on llama.cpp `b10598`.
#: The names are the wire format and the field names are ours, so a llama.cpp
#: rename is one edit here and shows up as an empty column rather than as a
#: wrong number. Read from a real capture, not from the upstream README.
_SERIES: Final[Mapping[str, str]] = {
    "llamacpp:prompt_tokens_total": "prompt_tokens_total",
    "llamacpp:prompt_seconds_total": "prompt_seconds_total",
}

#: The one of those two whose series is a whole count. A value that is not whole
#: is a rename or a format change, and it raises rather than truncate.
_WHOLE: Final = frozenset({"prompt_tokens_total"})

#: Every level of every cache the kernel publishes, one directory a level.
CACHE_ROOT: Final = Path("/sys/devices/system/cpu/cpu0/cache")

#: The link-local address every major cloud answers instance questions on. It is
#: a constant in this file and never built from anything fetched, so no reachable
#: input can point this at another host (Guardrail #11).
METADATA_URL: Final = "http://169.254.169.254/metadata/instance/compute?api-version=2021-02-01"
METADATA_HEADER: Final = {"Metadata": "true"}

#: Short, because the answer is a nicety and the job is not waiting on it.
METADATA_TIMEOUT_SECONDS: Final = 2.0

#: Three copies, and the middle one is the reading. One scheduler hiccup should
#: not decide what a machine's bandwidth was.
MEMCPY_REPEATS: Final = 3

_MIB: Final = 1024 * 1024
_GIB: Final = 1024 * 1024 * 1024


def _text(path: Path) -> str | None:
    try:
        with path.open("rb") as reading:
            raw = reading.read(_PROC_READ_LIMIT_BYTES + 1)
    except OSError:
        return None
    if len(raw) > _PROC_READ_LIMIT_BYTES:
        return None
    return raw.decode("utf-8", errors="replace")


def _cpuinfo_fields(text: str) -> tuple[dict[str, str], list[float]]:
    """The first processor's key-value lines, and every processor's clock."""
    first: dict[str, str] = {}
    clocks: list[float] = []
    for line in text.splitlines():
        key, found, raw = line.partition(":")
        if not found:
            continue
        name, value = key.strip(), raw.strip()
        if name == "cpu MHz":
            try:
                frequency = float(value)
            except ValueError:
                continue
            if math.isfinite(frequency) and frequency > 0:
                clocks.append(frequency)
        elif name not in first:
            first[name] = value
    return first, clocks


def _as_int(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_float(value: str | None) -> float | None:
    try:
        found = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return found if math.isfinite(found) and found > 0 else None


def _cpu_ids(text: str | None) -> tuple[int, ...] | None:
    """Parse Linux's online CPU list without treating sparse IDs as a count."""
    if not text:
        return None
    found: set[int] = set()
    for part in text.strip().split(","):
        low_text, separator, high_text = part.partition("-")
        if not low_text.isascii() or not low_text.isdigit():
            return None
        low = int(low_text)
        high = low
        if separator:
            if not high_text.isascii() or not high_text.isdigit():
                return None
            high = int(high_text)
            if high < low:
                return None
        ids = set(range(low, high + 1))
        if found.intersection(ids):
            return None
        found.update(ids)
    return tuple(sorted(found)) or None


def _physical_cores(
    online_ids: tuple[int, ...] | None, *, cpu_root: Path
) -> int | None:
    """Count complete package/core pairs for every online logical CPU."""
    if online_ids is None:
        return None
    topology: set[tuple[int, int]] = set()
    for cpu_id in online_ids:
        root = cpu_root / f"cpu{cpu_id}" / "topology"
        package = _as_int(_text(root / "physical_package_id"))
        core = _as_int(_text(root / "core_id"))
        if package is None or core is None or package < 0 or core < 0:
            return None
        topology.add((package, core))
    return len(topology) if 0 < len(topology) <= len(online_ids) else None


def _reported_max_mhz(online_ids: tuple[int, ...] | None, *, cpu_root: Path) -> float | None:
    """Read a maximum only when every online CPU reports a valid policy value."""
    if online_ids is None:
        return None
    values: list[float] = []
    for cpu_id in online_ids:
        raw = _text(cpu_root / f"cpu{cpu_id}" / "cpufreq" / "cpuinfo_max_freq")
        value = _as_float(raw)
        if value is None:
            return None
        values.append(value / 1000)
    return max(values) if values else None


def _cpu_quota(
    pid: int, *, proc_root: Path, cgroup_root: Path
) -> tuple[float | None, str]:
    """Read quota at the target's cgroup and each visible ancestor."""
    groups = _text(proc_root / str(pid) / "cgroup")
    if groups is None:
        return None, "unavailable"
    location: PurePosixPath | None = None
    version_two = False
    for line in groups.splitlines():
        hierarchy, separator, rest = line.partition(":")
        controllers, separator2, path = rest.partition(":")
        if not separator or not separator2:
            continue
        if hierarchy == "0" and not controllers:
            location, version_two = PurePosixPath(path), True
            break
        if "cpu" in controllers.split(","):
            location = PurePosixPath(path)
            break
    if location is None or not location.is_absolute() or ".." in location.parts:
        return None, "unavailable"
    base = cgroup_root if version_two else cgroup_root / "cpu"
    node = base.joinpath(*location.parts[1:])
    finite: list[float] = []
    states: list[str] = []
    while True:
        if version_two:
            raw = _text(node / "cpu.max")
            cells = raw.split() if raw is not None else []
            if len(cells) != 2 or not cells[1].isascii() or not cells[1].isdigit():
                states.append("unavailable")
            else:
                period = int(cells[1])
                if period <= 0:
                    states.append("unavailable")
                elif cells[0] == "max":
                    states.append("unlimited")
                elif cells[0].isascii() and cells[0].isdigit() and int(cells[0]) > 0:
                    finite.append(int(cells[0]) / period)
                    states.append("finite")
                else:
                    states.append("unavailable")
        else:
            quota_text = _text(node / "cpu.cfs_quota_us")
            period_text = _text(node / "cpu.cfs_period_us")
            try:
                quota = int(quota_text.strip()) if quota_text is not None else 0
                period = int(period_text.strip()) if period_text is not None else 0
            except ValueError:
                states.append("unavailable")
            else:
                if period <= 0:
                    states.append("unavailable")
                elif quota == -1:
                    states.append("unlimited")
                elif quota > 0:
                    finite.append(quota / period)
                    states.append("finite")
                else:
                    states.append("unavailable")
        if node == base:
            break
        node = node.parent
        if base not in node.parents and node != base:
            return None, "unavailable"
    if "unavailable" in states or not states:
        return None, "unavailable"
    if finite:
        return min(finite), "finite"
    return None, "unlimited"


def _target_capacity(
    pid: int,
    online_ids: tuple[int, ...] | None,
    *,
    proc_root: Path,
    cgroup_root: Path,
) -> tuple[int | None, float | None, str]:
    """Measure the logical CPUs and quota available to one process."""
    allowed: int | None = None
    get_affinity = getattr(os, "sched_getaffinity", None)
    if online_ids is not None and get_affinity is not None:
        try:
            mask = get_affinity(pid)
        except (OSError, ValueError):
            pass
        else:
            count = len(set(online_ids).intersection(mask))
            allowed = count or None
    quota, state = _cpu_quota(pid, proc_root=proc_root, cgroup_root=cgroup_root)
    return allowed, quota, state


def watched_flags(text: str | None) -> str:
    """The flags worth reading back, sorted, from a `flags` line."""
    if text is None:
        return ""
    fields, _ = _cpuinfo_fields(text)
    present = set(fields.get("flags", "").split())
    return " ".join(flag for flag in WATCHED_FLAGS if flag in present)


def host_cpu_model(text: str | None = None) -> str | None:
    """This host's `model name`, for a caller that wants the label and nothing else."""
    raw = _text(CPUINFO) if text is None else text
    fields, _ = _cpuinfo_fields(raw or "")
    return fields.get("model name") or None


def cache_bytes(level: int = 3, root: Path | None = None) -> int | None:
    """One cache level in bytes, from the kernel rather than from a product page."""
    base = CACHE_ROOT if root is None else root
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return None
    for entry in entries:
        if _as_int(_text(entry / "level")) != level:
            continue
        size = (_text(entry / "size") or "").strip()
        if size.endswith("K"):
            found = _as_int(size[:-1])
            return None if found is None else found * 1024
        if size.endswith("M"):
            found = _as_int(size[:-1])
            return None if found is None else found * _MIB
        return _as_int(size)
    return None


def boot_seconds(text: str | None = None) -> float | None:
    """How long this machine had been up when the probe ran."""
    raw = _text(UPTIME) if text is None else text
    if not raw:
        return None
    cells = raw.split()
    return _as_float(cells[0]) if cells else None


def probe_buffer_mib(floor_mib: int, l3_cache_bytes: int | None, cache_multiple: int) -> int:
    """How large each side of the copy has to be on THIS machine, in MiB.

    The size decides what the probe measures, so it cannot be a constant. The
    reported L3 across the machines this project draws spans 32 MiB to 480 MiB,
    and a buffer that does not clear the cache reads as memory bandwidth while
    measuring something else. The configured value is the floor and the machine's
    own report raises it, so a part with more cache than anybody has drawn cannot
    quietly turn the reading into a cache reading.

    `cache_multiple` is the margin, and the console grades a committed row by the
    same value: a row whose buffer did not clear the cache by it has its copy
    speed withheld rather than drawn.

    A floor of zero stays zero: that is the caller saying do not probe at all. A
    machine that reports no cache keeps the floor, because an unknown cache is
    not a small one and there is nothing else to derive from.
    """
    if floor_mib <= 0 or l3_cache_bytes is None or l3_cache_bytes <= 0:
        return floor_mib
    whole_mib = -(-l3_cache_bytes // _MIB)  # round up, so the result clears the cache
    return max(floor_mib, cache_multiple * whole_mib)


def memcpy_gib_s(probe_mib: int) -> float | None:
    """Large-block copy bandwidth, or nothing where the probe is switched off.

    A `bytearray` slice assignment is a `memmove` of the whole buffer, so this
    times the C library rather than the interpreter. Bytes moved counts the read
    and the write, which is how STREAM counts a copy.

    The caller decides the size and the size decides what is measured: a buffer
    smaller than L3 measures cache. `probe_buffer_mib` is where that size comes
    from, and `HostFingerprintRow` records it beside the rate so nobody can read
    one for the other.
    """
    if probe_mib <= 0:
        return None
    size = probe_mib * _MIB
    try:
        source = bytearray(size)
        target = bytearray(size)
    except MemoryError:
        LOG.warning("silicon probe could not allocate %d MiB, bandwidth unrecorded", probe_mib)
        return None
    rates: list[float] = []
    for _ in range(MEMCPY_REPEATS):
        start = time.perf_counter()
        target[:] = source
        elapsed = time.perf_counter() - start
        if elapsed > 0:
            rates.append((2 * size / _GIB) / elapsed)
    return statistics.median(rates) if rates else None


@dataclass(frozen=True, slots=True)
class Placement:
    """What the platform says about where it put this job."""

    vm_size: str | None = None
    location: str | None = None
    zone: str | None = None
    fault_domain: str | None = None


def placement(url: str = METADATA_URL, timeout: float = METADATA_TIMEOUT_SECONDS) -> Placement:
    """Ask the host metadata service where this job landed.

    A link-local address that only answers inside the platform, so a developer
    machine gets a refused connection and an empty `Placement`. This runs at
    build time in CI and never from a published page.
    """
    request = urllib.request.Request(url, headers=METADATA_HEADER)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            payload = json.loads(reply.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return Placement()
    if not isinstance(payload, dict):
        return Placement()
    return Placement(
        vm_size=str(payload.get("vmSize") or "") or None,
        location=str(payload.get("location") or "") or None,
        zone=str(payload.get("zone") or "") or None,
        fault_domain=str(payload.get("platformFaultDomain") or "") or None,
    )


def read_row(
    *,
    date: str,
    run_id: str,
    job: ServerJob | TaskName | None,
    shard: int,
    pipeline_name: PipelineName | None = None,
    task_name: TaskName | None = None,
    frequency_enabled: bool = False,
    probe_floor_mib: int,
    probe_cache_multiple: int,
    ask_placement: bool = True,
    cpuinfo: str | None = None,
    cache_root: Path | None = None,
    online_cpu_list: str | None = None,
    cpu_root: Path | None = None,
    proc_root: Path | None = None,
    cgroup_root: Path | None = None,
    target_pid: int | None = None,
) -> HostFingerprintRow:
    """Everything this machine will say about itself, taken once."""
    text = _text(CPUINFO) if cpuinfo is None else cpuinfo
    fields, clocks = _cpuinfo_fields(text or "")
    online_ids = _cpu_ids(
        _text(CPU_ONLINE) if online_cpu_list is None else online_cpu_list
    )
    logical_processors = len(online_ids) if online_ids is not None else None
    visible_cpu_root = CPU_ROOT if cpu_root is None else cpu_root
    physical_cores = _physical_cores(
        online_ids, cpu_root=visible_cpu_root
    )
    reported_max_mhz = (
        _reported_max_mhz(online_ids, cpu_root=visible_cpu_root) if frequency_enabled else None
    )
    where = placement() if ask_placement else Placement()
    l3_cache_bytes = cache_bytes(root=cache_root)
    measured_at = datetime.now(UTC).strftime(_SCRAPED_AT_FORMAT)
    pid = os.getpid() if target_pid is None else target_pid
    allowed, quota, quota_state = _target_capacity(
        pid,
        online_ids,
        proc_root=PROC if proc_root is None else proc_root,
        cgroup_root=CGROUP_ROOT if cgroup_root is None else cgroup_root,
    )
    cells: dict[str, object] = {
        "cpu_model": fields.get("model name") or None,
        "cpu_vendor": fields.get("vendor_id") or None,
        "cpu_family": _as_int(fields.get("cpu family")),
        "cpu_model_number": _as_int(fields.get("model")),
        "cpu_stepping": _as_int(fields.get("stepping")),
        "microcode": fields.get("microcode") or None,
        "cpu_physical_cores": physical_cores,
        "cpu_logical_processors": logical_processors,
        "cpu_allowed_processors": allowed if logical_processors is not None else None,
        "cpu_quota_cores": quota,
        "cpu_quota_state": quota_state,
        "cpu_target_measured_at": measured_at,
        "l3_cache_bytes": l3_cache_bytes,
        "cpu_observed_mhz": statistics.mean(clocks) if frequency_enabled and clocks else None,
        "cpu_reported_max_mhz": reported_max_mhz,
        "flags": watched_flags(text),
    }
    # The recorded size is the derived one, never the configured floor, so the
    # column says what was probed rather than what somebody asked for.
    probe_mib = probe_buffer_mib(probe_floor_mib, l3_cache_bytes, probe_cache_multiple)
    row = HostFingerprintRow.model_validate(
        {
            "version": HOST_FINGERPRINT_VERSION,
            "date": date,
            "run_id": run_id,
            "job": job,
            "pipeline_name": pipeline_name,
            "task_name": task_name,
            "shard": shard,
            "fingerprint": None,
            "fingerprint_version": None,
            "boot_seconds": boot_seconds(),
            "memcpy_gib_s": memcpy_gib_s(probe_mib),
            "memcpy_probe_mib": probe_mib,
            "vm_size": where.vm_size,
            "vm_location": where.location,
            "vm_zone": where.zone,
            "vm_fault_domain": where.fault_domain,
            "runner_name": runner_name(),
            "measured_at": measured_at,
            **cells,
        }
    )
    identity = fingerprint_v2(row)
    return HostFingerprintRow.model_validate(
        row.model_dump()
        | {
            "fingerprint": identity,
            "fingerprint_version": 2 if identity is not None else None,
        }
    )


def _writer(
    run_id: str,
    *,
    commit_sha: str,
    job: ServerJob | TaskName | None,
    shard: int,
    attempt: int | None = None,
    pipeline_name: PipelineName | None = None,
    task_name: TaskName | None = None,
) -> WriterIdentity:
    """Build either a legacy job identity or a reusable pipeline/task identity."""
    chosen_attempt = run_context.run_attempt() if attempt is None else attempt
    if (pipeline_name is None) != (task_name is None):
        raise ValueError("pipeline_name and task_name must be present together")
    if pipeline_name is not None and task_name is not None:
        return WriterIdentity.for_pipeline_task(
            run_id=run_id,
            attempt=chosen_attempt,
            pipeline_name=pipeline_name,
            task_name=task_name,
            shard=shard,
            producer=PRODUCER,
            git_sha=commit_sha,
        )
    if job is None:
        raise ValueError("legacy writer identity requires a job")
    return WriterIdentity(
        run_id=run_id,
        attempt=chosen_attempt,
        job=job,
        shard=shard,
        producer=PRODUCER,
        git_sha=commit_sha,
    )


def _shown_files(state_root: Path, paths: list[Path]) -> str:
    """Where a write landed, as it may leave the process: relative and POSIX."""
    return ",".join(ledger.paths.shown(state_root, path) for path in paths) or "nothing"


def file_machine_row(
    *,
    date: str,
    run_id: str,
    settings: config.Settings | config.GardenerSettings,
    state_root: Path,
    commit_sha: str,
    shard: int = 0,
    job: ServerJob | TaskName | None = None,
    pipeline_name: PipelineName | None = None,
    task_name: TaskName | None = None,
    attempt: int | None = None,
) -> tuple[HostFingerprintRow | None, list[Path]]:
    """Record what machine this job drew, and say where the row landed.

    `stage_fingerprint` is this for a caller that only wants the row. A caller
    that has to name its own writes needs the paths as well: the gardener's shard
    declares every file it wrote so its publisher can refuse one it did not, and
    a row the shard filed but never named is a row that dies with the runner.
    """
    knobs = settings.app.observability
    if (pipeline_name is None) != (task_name is None):
        raise ValueError("pipeline_name and task_name must be present together")
    legacy_job = None if pipeline_name is not None else job or WORK_JOB
    task_label = task_name if task_name is not None else legacy_job
    if not host_telemetry_enabled(knobs) or not knobs.host_fingerprint:
        LOG.info("fingerprint off task=%s shard=%s run=%s", task_label, shard, run_id)
        return None, []
    reads_bandwidth = task_label in knobs.host_fingerprint_bandwidth_jobs
    row = read_row(
        date=date,
        run_id=run_id,
        job=legacy_job,
        pipeline_name=pipeline_name,
        task_name=task_name,
        frequency_enabled=knobs.host_fingerprint_frequency_enabled,
        shard=shard,
        probe_floor_mib=knobs.host_fingerprint_bandwidth_floor_mib if reads_bandwidth else 0,
        probe_cache_multiple=knobs.host_fingerprint_bandwidth_cache_multiple,
    )
    landed = ledger.persist(
        state_root,
        [row],
        ledger=LedgerName.HOST_FINGERPRINT,
        covers=date,
        identity=_writer(
            run_id,
            commit_sha=commit_sha,
            job=legacy_job,
            shard=shard,
            attempt=attempt,
            pipeline_name=pipeline_name,
            task_name=task_name,
        ),
    )
    LOG.info(
        "fingerprint task=%s shard=%s run=%s id=%s cpu=%s family=%s model=%s stepping=%s "
        "flags=%s l3_bytes=%s memcpy_gib_s=%s probe_mib=%s vm_size=%s zone=%s "
        "boot_seconds=%s mhz=%s file=%s",
        task_label,
        shard,
        run_id,
        row.fingerprint,
        row.cpu_model,
        row.cpu_family,
        row.cpu_model_number,
        row.cpu_stepping,
        row.flags or "none",
        row.l3_cache_bytes,
        row.memcpy_gib_s,
        row.memcpy_probe_mib,
        row.vm_size,
        row.vm_zone,
        row.boot_seconds,
        row.mhz_at_probe,
        _shown_files(state_root, landed),
    )
    return row, landed


def stage_fingerprint(
    *,
    date: str,
    run_id: str,
    settings: config.Settings,
    state_root: Path,
    commit_sha: str,
    shard: int = 0,
    job: ServerJob | TaskName | None = None,
    pipeline_name: PipelineName | None = None,
    task_name: TaskName | None = None,
) -> HostFingerprintRow | None:
    """Record what machine this job drew, before anything else competes for it.

    Runs early on purpose. The bandwidth probe needs a gigabyte or two and an
    idle machine, and a job that has already started its heaviest step has
    neither - the model server in `work`, the embeddings and the site build in
    `assemble`. A probe taken at the end of a job would measure that step rather
    than the host. How much it needs depends on the cache the machine reports:
    `probe_buffer_mib` sizes each of the two buffers against it.

    The row goes to this job's own raw file through the ledger door. Ten jobs of
    one run each draw a machine and each record it, and the door names each file
    for its writer, so no two jobs share a path; the attempt is in the writer's
    identity, so a re-run replaces its first try rather than colliding with it.

    **The day and the run address are what this needs, and it asks for both.**
    A machine reading is about a job rather than about the work that job did, so
    a job that plans nothing can still take one. Reading a run plan to recover
    two strings the caller already holds would make this probe refuse every
    workflow that does not plan - the gardener's wakes and the council's nights
    among them - for a payload it never opens.
    **The bandwidth reading is taken only by the jobs config names.** It wants a
    gigabyte and an idle machine, so a job that takes it anywhere but the bench
    measures its own run rather than the host. A job outside the list is handed a
    floor of zero, which is the caller saying do not probe, and the row carries
    `memcpy_probe_mib` of zero beside an empty rate - the reading was not taken,
    rather than a machine that could not copy.
    """
    row, _ = file_machine_row(
        date=date,
        run_id=run_id,
        settings=settings,
        state_root=state_root,
        commit_sha=commit_sha,
        shard=shard,
        job=job,
        pipeline_name=pipeline_name,
        task_name=task_name,
    )
    return row


def _own_probe(state_root: Path, date: str, identity: WriterIdentity) -> HostFingerprintRow | None:
    """The row this job's probe filed at its start, read back from its raw file.

    The newest file of this writer's own work unit and attempt, so a clock step
    that ran twice reads the whole row it wrote last, and never a sibling job's
    or an earlier attempt's. None when the probe was off or never ran.
    """
    unit = ledger.unit_id(
        ledger=LedgerName.HOST_FINGERPRINT,
        covers=date,
        run_id=identity.run_id,
        job=identity.job if identity.pipeline_name is None else None,
        pipeline_name=identity.pipeline_name,
        task_name=identity.task_name,
        shard=identity.shard,
        producer=identity.producer,
    )
    mine = [
        held
        for held in ledger.list_raw_files(state_root, LedgerName.HOST_FINGERPRINT, days={date})
        if held.envelope.unit_id == unit and held.envelope.identity.attempt == identity.attempt
    ]
    if not mine:
        return None
    rows = ledger.load([mine[-1].path], model=HostFingerprintRow)
    return rows[0] if rows else None


def _with_clock(probe: HostFingerprintRow, clock: HostFingerprintRow) -> HostFingerprintRow:
    """The probe's row with the four job-end cells filled from the clock's reading.

    The probe fills none of those four, so a probe that did is named in a
    warning: the clock's reading replaces it, and a person should know the two
    disagreed about who measures what.
    """
    cells = probe.model_dump()
    for name in CLOCK_CELLS:
        if cells[name] is not None:
            LOG.warning(
                "the probe filled a clock cell, and the clock's reading replaces it "
                "key=%s,%s,%s,%s cell=%s",
                probe.date,
                probe.run_id,
                probe.job,
                probe.shard,
                name,
            )
        cells[name] = getattr(clock, name)
    return HostFingerprintRow.model_validate(cells)


def file_job_clock(
    *,
    date: str,
    run_id: str,
    settings: config.Settings | config.GardenerSettings,
    state_root: Path,
    commit_sha: str,
    shard: int = 0,
    job: ServerJob | TaskName | None = None,
    pipeline_name: PipelineName | None = None,
    task_name: TaskName | None = None,
    job_started_at: int | None = None,
    server_log_path: Path | None = None,
    metrics_path: Path | None = None,
    attempt: int | None = None,
    finished_at: str | None = None,
) -> tuple[HostFingerprintRow | None, list[Path]]:
    """What the job cost, recorded onto the host row the probe opened.

    The other end of `stage_fingerprint`. Four cells of that row are only knowable
    once the job is over - the wall clock it spent, what opening the weights cost
    before the first item, and the two prompt counters the model server itself
    kept - and moving the probe to job end to collect them would destroy
    `mhz_at_probe` and `boot_seconds`, which want an idle machine.

    So this reads back the row this attempt's probe filed, fills the four cells,
    and files the whole row again under the same writer. That is a later write of
    the probe's own work unit, which the door keeps in place of the half-row, so
    a settled day holds one row a job and never one row naming two machines.

    The two prompt cells are the second instrument. The item ledger answers the
    same question by arithmetic over its own rows, which cannot check those rows;
    the server's own counters can disagree with them, and twice they have.

    A job that dies between the probe and this step leaves a usable half-row with
    four empty cells, which is the degrade path rather than a failure. So is a
    probe that never ran, which leaves this row alone, and a stamp that never
    arrived, or a scrape the server was already gone for: an empty cell says the
    reading was not taken, where a zero would claim a job that took no time and
    read no tokens.
    """
    knobs = settings.app.observability
    if (pipeline_name is None) != (task_name is None):
        raise ValueError("pipeline_name and task_name must be present together")
    legacy_job = None if pipeline_name is not None else job or WORK_JOB
    task_label = task_name if task_name is not None else legacy_job
    if not host_telemetry_enabled(knobs) or not knobs.host_fingerprint:
        LOG.info("job clock off task=%s shard=%s run=%s", task_label, shard, run_id)
        return None, []
    scraped_at = finished_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    prompt_tokens, prompt_seconds = server_prompt_totals(_text_if_readable(metrics_path))
    row = HostFingerprintRow(
        version=HostFingerprintRow.schema_version(),
        date=date,
        run_id=run_id,
        job=legacy_job,
        pipeline_name=pipeline_name,
        task_name=task_name,
        shard=shard,
        model_load_ms=model_load_ms(_text_if_readable(server_log_path)),
        job_seconds=job_seconds(scraped_at, job_started_at),
        server_prompt_tokens=prompt_tokens,
        server_prompt_seconds=prompt_seconds,
    )
    identity = _writer(
        run_id,
        commit_sha=commit_sha,
        job=legacy_job,
        shard=shard,
        attempt=attempt,
        pipeline_name=pipeline_name,
        task_name=task_name,
    )
    probe = _own_probe(state_root, date, identity)
    whole = _with_clock(probe, row) if probe is not None else row
    landed = ledger.persist(
        state_root,
        [whole],
        ledger=LedgerName.HOST_FINGERPRINT,
        covers=date,
        identity=identity,
    )
    LOG.info(
        "job clock task=%s shard=%s run=%s job_seconds=%s model_load_ms=%s "
        "server_prompt_tokens=%s server_prompt_seconds=%s probe=%s file=%s",
        task_label,
        shard,
        run_id,
        row.job_seconds,
        row.model_load_ms,
        row.server_prompt_tokens,
        row.server_prompt_seconds,
        "found" if probe is not None else "absent",
        _shown_files(state_root, landed),
    )
    return whole, landed


def stage_job_clock(
    *,
    date: str,
    run_id: str,
    settings: config.Settings,
    state_root: Path,
    commit_sha: str,
    shard: int = 0,
    job: ServerJob | TaskName | None = None,
    pipeline_name: PipelineName | None = None,
    task_name: TaskName | None = None,
    job_started_at: int | None = None,
    server_log_path: Path | None = None,
    metrics_path: Path | None = None,
) -> HostFingerprintRow | None:
    """Close the machine row when the caller does not need its written paths."""
    whole, _ = file_job_clock(
        date=date,
        run_id=run_id,
        settings=settings,
        state_root=state_root,
        commit_sha=commit_sha,
        shard=shard,
        job=job,
        pipeline_name=pipeline_name,
        task_name=task_name,
        job_started_at=job_started_at,
        server_log_path=server_log_path,
        metrics_path=metrics_path,
    )
    return whole


def _text_if_readable(path: Path | None) -> str | None:
    """A log the job may never have written is absent text, never a failed stage."""
    if path is None:
        return None
    return _text(path)


def _log_microseconds(line: str) -> int | None:
    """A llama-server log stamp, in microseconds since its process started."""
    found = _LOG_INSTANT.match(line)
    if found is None:
        return None
    minutes, seconds, milliseconds, microseconds = (int(part) for part in found.groups())
    return (((minutes * 60) + seconds) * 1000 + milliseconds) * 1000 + microseconds


def model_load_ms(text: str | None) -> float | None:
    """Milliseconds between the two lines llama-server brackets its load with.

    Both ends have to be present and stamped. A build that renames either line,
    or one that logs without timestamps, leaves the cell empty - which reads as
    unknown, and is the same failure `_SERIES` is written for.
    """
    if not text:
        return None
    instants: dict[str, int] = {}
    for line in text.splitlines():
        for marker in (_LOAD_STARTED, _LOAD_FINISHED):
            if marker in line and marker not in instants:
                stamped = _log_microseconds(line)
                if stamped is not None:
                    instants[marker] = stamped
    if len(instants) != 2:
        return None
    return (instants[_LOAD_FINISHED] - instants[_LOAD_STARTED]) / 1000


def job_seconds(scraped_at: str, job_started_at: int | None) -> int | None:
    """Job start to scrape, in seconds. A stamp in the future fails `ge=0` loudly."""
    if job_started_at is None:
        return None
    scraped = datetime.strptime(scraped_at, _SCRAPED_AT_FORMAT).replace(tzinfo=UTC)
    return int(scraped.timestamp()) - job_started_at


def server_prompt_totals(text: str | None) -> tuple[int | None, float | None]:
    """The two prompt counters the server itself kept, as (tokens, seconds).

    These two are the second instrument. The item ledger's own answer to the same
    question is arithmetic over that ledger, and arithmetic over a ledger cannot
    check it, so the only reading that can disagree is the server's own.

    A llama.cpp rename leaves both cells empty rather than inventing a zero, and
    a count that arrives fractional raises instead of being truncated into a
    number a later reader would average. Text nobody could read is two empty
    cells, which says the reading was not taken.
    """
    if not text:
        return None, None
    found: dict[str, float | int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, raw = line.partition(" ")
        field = _SERIES.get(name)
        if field is not None:
            found[field] = _number(name, field, raw.strip())
    tokens = found.get("prompt_tokens_total")
    seconds = found.get("prompt_seconds_total")
    return (None if tokens is None else int(tokens)), (None if seconds is None else float(seconds))


def _number(series: str, field: str, raw: str) -> float | int:
    value = float(raw)
    if field not in _WHOLE:
        return value
    if not value.is_integer():
        raise ValueError(f"{series} is a count and reported {raw!r}")
    return int(value)
