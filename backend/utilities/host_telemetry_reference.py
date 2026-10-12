"""How do unchanged Python decoders read bounded captures of this live workload?"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_events import (
    HostWindowCells,
    LegacyJobSample,
    LegacyProcessRollcall,
    ProcessTarget,
)
from idhazh.contracts.host_evidence import EVIDENCE_VERSION, ReferenceSample
from idhazh.contracts.host_fingerprint import (
    LEGACY_HOST_VERSIONS,
    HostFingerprintRow,
    normalize_host_row,
)
from idhazh.telemetry import host, silicon
from idhazh.telemetry.host_evidence_inputs import ComparisonSettings, NativeSettings, read_bytes
from utilities import memory_sampler

# Procfs stat's tail starts at field 3, after the final comm bracket.
START_TICKS_TAIL = 19
CPU_TICKS_TAIL = (11, 12)
KIB = 1024


def identity(pid: int, native: NativeSettings, proc: Path = Path("/proc")) -> ProcessTarget:
    text = read_bytes(proc / str(pid) / "stat", native.capture_limits.max_proc_text_bytes).decode()
    prefix, bracket, tail = text.rpartition(") ")
    if not bracket or int(prefix.partition(" ")[0]) != pid:
        raise ValueError("malformed process identity")
    return ProcessTarget(pid=pid, start_ticks=int(tail.split()[START_TICKS_TAIL]))


def process_cost(target: ProcessTarget, native: NativeSettings) -> tuple[float, int]:
    if identity(target.pid, native) != target:
        raise ValueError("monitor PID was reused")
    stat = (
        read_bytes(Path(f"/proc/{target.pid}/stat"), native.capture_limits.max_proc_text_bytes)
        .decode()
        .rpartition(") ")[2]
        .split()
    )
    status = read_bytes(
        Path(f"/proc/{target.pid}/status"), native.capture_limits.max_proc_text_bytes
    ).decode()
    ticks = sum(int(stat[index]) for index in CPU_TICKS_TAIL)
    rss = host._kb_keys(status, ("VmRSS",))["VmRSS"]
    if rss is None:
        raise ValueError("required monitor RSS is absent")
    if sys.platform == "linux":
        return ticks / os.sysconf("SC_CLK_TCK"), rss
    raise ValueError("process CPU clocks require Linux")


def snapshot_population(
    destination: Path,
    native: NativeSettings,
    compare: ComparisonSettings,
    *,
    proc: Path = Path("/proc"),
) -> tuple[ProcessTarget, ...]:
    """Copy one bounded real population; no replacement or dummy processes."""
    destination.mkdir(parents=True, exist_ok=False)
    cap = native.capture_limits.max_proc_text_bytes
    (destination / "meminfo").write_bytes(read_bytes(proc / "meminfo", cap))
    entries: list[int] = []
    with os.scandir(proc) as stream:
        for index, entry in enumerate(stream):
            if index >= compare.max_process_entries:
                raise ValueError("live process inventory exceeds its entry cap")
            if entry.name.isdecimal():
                entries.append(int(entry.name))
    if len(entries) > native.capture_limits.max_processes:
        raise ValueError("live process inventory exceeds its process cap")
    population: list[ProcessTarget] = []
    for pid in sorted(entries):
        source = proc / str(pid)
        try:
            before = identity(pid, native, proc)
            comm = read_bytes(source / "comm", cap)
            if not comm.strip().startswith(b"python"):
                continue
            status = read_bytes(source / "status", cap)
            try:
                cmdline = read_bytes(source / "cmdline", cap)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                cmdline = None
            if cmdline is not None:
                argv = [part for part in cmdline.split(b"\0") if part]
                cmdline = b"\0".join(argv[: memory_sampler.ARGV_FIELDS.stop])
            # Executable visibility does not decide the legacy memory population.
            try:
                executable = (source / "exe").readlink()
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                executable = None
            if identity(pid, native, proc) != before:
                raise ValueError("Python population PID changed during capture")
        except (FileNotFoundError, ProcessLookupError):
            continue
        target = destination / str(pid)
        target.mkdir()
        for name, raw in (("comm", comm), ("status", status)):
            (target / name).write_bytes(raw)
        if cmdline is not None:
            (target / "cmdline").write_bytes(cmdline)
        if executable is not None:
            (target / "exe").symlink_to(executable)
        population.append(before)
    return tuple(population)


def sample_population(
    destination: Path,
    native: NativeSettings,
    compare: ComparisonSettings,
    now: str,
    *,
    proc: Path = Path("/proc"),
) -> ReferenceSample:
    try:
        population = snapshot_population(destination, native, compare, proc=proc)
        cgroup = destination / "cgroup-current.txt"
        for source in memory_sampler.CGROUP_CURRENT_PATHS:
            try:
                cgroup.write_bytes(read_bytes(source, native.capture_limits.max_sysfs_text_bytes))
            except FileNotFoundError:
                continue
            break
        # Existing decoders see precisely the bounded capture, including the real sampler.
        sample, rollcall = memory_sampler.sample_once(
            0,
            proc_root=destination,
            cgroup_paths=(cgroup,),
            now=now,
        )
        return ReferenceSample(
            version=EVIDENCE_VERSION,
            record=LegacyJobSample.model_validate(sample),
            population=population,
            rollcall=tuple(LegacyProcessRollcall.model_validate(row) for row in rollcall),
        )
    finally:
        if destination.exists():
            with os.scandir(destination) as stream:
                for index, entry in enumerate(stream):
                    if index > native.capture_limits.max_processes + 2:
                        raise ValueError("generated process cleanup inventory exceeds its cap")
                    if entry.name.isdecimal():
                        link = Path(entry.path) / "exe"
                        if link.is_symlink():
                            link.unlink()


def endpoint(native: NativeSettings, destination: Path) -> tuple[str, float, dict[str, int | None]]:
    cap = native.capture_limits.max_proc_text_bytes
    destination.mkdir(parents=True, exist_ok=False)
    captured = {
        "stat": read_bytes(Path("/proc/stat"), cap),
        "loadavg": read_bytes(Path("/proc/loadavg"), cap),
        "meminfo": read_bytes(Path("/proc/meminfo"), cap),
        "status": read_bytes(Path(f"/proc/{os.getpid()}/status"), cap),
    }
    for name, raw in captured.items():
        (destination / name).write_bytes(raw)
    stat = captured["stat"].decode()
    load = float(captured["loadavg"].decode().split()[0])
    memory = host.meminfo_bytes(captured["meminfo"].decode())
    status = host._kb_keys(captured["status"].decode(), host.STATUS_KEYS)
    return (
        stat,
        load,
        {
            "python_rss_bytes": status["VmRSS"],
            "python_rss_anon_bytes": status["RssAnon"],
            "os_mem_available_bytes": memory["MemAvailable"],
            "os_mem_total_bytes": memory["MemTotal"],
            "os_mem_cached_bytes": memory["Cached"],
            "os_swap_free_bytes": memory["SwapFree"],
            "os_swap_total_bytes": memory["SwapTotal"],
        },
    )


def window_cells(
    opening: tuple[str, float, dict[str, int | None]],
    closing: tuple[str, float, dict[str, int | None]],
) -> HostWindowCells:
    shares = host.cpu_shares_between(opening[0], closing[0])
    if shares is None:
        raise ValueError("required live CPU endpoint counters are absent")
    available = [
        value
        for value in (opening[2]["os_mem_available_bytes"], closing[2]["os_mem_available_bytes"])
        if value is not None
    ]
    return HostWindowCells(
        cpu_busy_pct=shares.busy_pct,
        cpu_busy_min=shares.busy_pct,
        cpu_busy_max=shares.busy_pct,
        cpu_steal_pct=shares.steal_pct,
        load_1m=closing[1],
        os_mem_available_min_bytes=min(available) if available else None,
        **closing[2],
    )


def capture_cache(destination: Path, source: Path, native: NativeSettings) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with os.scandir(source) as stream:
        for index, entry in enumerate(stream):
            if index >= native.verification_limits.max_files:
                raise ValueError("cache inventory exceeds its cap")
            if not entry.name.startswith("index") or not entry.is_dir():
                continue
            target = destination / entry.name
            target.mkdir()
            for name in ("level", "size"):
                (target / name).write_bytes(
                    read_bytes(Path(entry.path) / name, native.capture_limits.max_sysfs_text_bytes)
                )


def host_row(
    root: Path, native: NativeSettings, *, day: str, run_id: str, now: str
) -> HostFingerprintRow:
    """Decode explicit baseline cells, never manufacture corrected CPU facts."""
    cap = native.capture_limits.max_proc_text_bytes
    cpu_raw = read_bytes(Path("/proc/cpuinfo"), cap)
    uptime = read_bytes(Path("/proc/uptime"), cap)
    cpuinfo = cpu_raw.decode()
    fields, clocks = silicon._cpuinfo_fields(cpuinfo)
    capture = root / "captures" / str(uuid4())
    cache = capture / "cache"
    capture_cache(cache, silicon.CACHE_ROOT, native)
    (capture / "cpuinfo").write_bytes(cpu_raw)
    (capture / "uptime").write_bytes(uptime)
    cells = {
        "cpu_model": fields.get("model name") or None,
        "cpu_vendor": fields.get("vendor_id") or None,
        "cpu_family": silicon._as_int(fields.get("cpu family")),
        "cpu_model_number": silicon._as_int(fields.get("model")),
        "cpu_stepping": silicon._as_int(fields.get("stepping")),
        "microcode": fields.get("microcode") or None,
        "cores": silicon._as_int(fields.get("cpu cores")),
        "threads": len(clocks) or None,
        "l3_cache_bytes": silicon.cache_bytes(root=cache),
        "flags": silicon.watched_flags(cpuinfo),
    }
    import statistics

    return normalize_host_row(
        {
            **cells,
            "date": day,
            "run_id": run_id,
            "job": ServerJob.WORK,
            "shard": 0,
            "version": LEGACY_HOST_VERSIONS[-1],
            "fingerprint": silicon.fingerprint_of(cells),
            "mhz_max": silicon._as_float(fields.get("cpu MHz")),
            "mhz_at_probe": statistics.mean(clocks) if clocks else None,
            "boot_seconds": silicon.boot_seconds(uptime.decode()),
            "memcpy_gib_s": None,
            "memcpy_probe_mib": 0,
            "runner_name": host.runner_name(),
            "measured_at": now,
        }
    )
