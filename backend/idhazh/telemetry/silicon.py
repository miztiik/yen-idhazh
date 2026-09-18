"""What silicon did this job draw, and what can it do?

`host.py` answers what the machine is DOING and changes every second. This
answers what the machine IS and is fixed for the length of the job, so it is
read once rather than sampled.

Every reading here degrades to nothing. None of these files or services exists
on a developer machine, and a missing instrument records an empty cell rather
than failing a run (CLAUDE.md section 1a).
"""

from __future__ import annotations

import hashlib
import json
import logging
import statistics
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from idhazh import ledger, run_context
from idhazh.contracts.host_fingerprint import WATCHED_FLAGS, HostFingerprintRow
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.runtime_counters import WORK_JOB, ServerJob
from idhazh.telemetry.host import runner_name

if TYPE_CHECKING:  # pragma: no cover - a type, not a runtime dependency
    from idhazh import config

LOG: Final = logging.getLogger("idhazh")

CPUINFO: Final = Path("/proc/cpuinfo")
UPTIME: Final = Path("/proc/uptime")

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
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


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
                clocks.append(float(value))
            except ValueError:
                continue
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
    return found if found > 0 else None


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


def memcpy_gib_s(probe_mib: int) -> float | None:
    """Large-block copy bandwidth, or nothing where the probe is switched off.

    A `bytearray` slice assignment is a `memmove` of the whole buffer, so this
    times the C library rather than the interpreter. Bytes moved counts the read
    and the write, which is how STREAM counts a copy.

    The caller decides the size and the size decides what is measured: a buffer
    smaller than L3 measures cache. `HostFingerprintRow` records both so nobody
    can read one for the other.
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


def fingerprint_of(row: Mapping[str, object]) -> str:
    """A digest over the cells that cannot change inside one job.

    Deliberately not over the whole row. Bandwidth, clock and uptime move
    between two jobs on identical machines, so including them would give every
    job its own value and the column would count nothing.
    """
    fixed = (
        "cpu_vendor",
        "cpu_family",
        "cpu_model_number",
        "cpu_stepping",
        "cpu_model",
        "cores",
        "threads",
        "l3_cache_bytes",
        "flags",
    )
    canonical = json.dumps(
        {key: row.get(key) for key in fixed}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def read_row(
    *,
    date: str,
    run_id: str,
    job: ServerJob,
    shard: int,
    probe_mib: int,
    ask_placement: bool = True,
    cpuinfo: str | None = None,
) -> HostFingerprintRow:
    """Everything this machine will say about itself, taken once."""
    text = _text(CPUINFO) if cpuinfo is None else cpuinfo
    fields, clocks = _cpuinfo_fields(text or "")
    where = placement() if ask_placement else Placement()
    cells: dict[str, object] = {
        "cpu_model": fields.get("model name") or None,
        "cpu_vendor": fields.get("vendor_id") or None,
        "cpu_family": _as_int(fields.get("cpu family")),
        "cpu_model_number": _as_int(fields.get("model")),
        "cpu_stepping": _as_int(fields.get("stepping")),
        "microcode": fields.get("microcode") or None,
        "cores": _as_int(fields.get("cpu cores")),
        "threads": len(clocks) or None,
        "l3_cache_bytes": cache_bytes(),
        "flags": watched_flags(text),
    }
    return HostFingerprintRow(
        date=date,
        run_id=run_id,
        job=job,
        shard=shard,
        fingerprint=fingerprint_of(cells),
        mhz_max=_as_float(fields.get("cpu MHz")),
        mhz_at_probe=statistics.mean(clocks) if clocks else None,
        boot_seconds=boot_seconds(),
        memcpy_gib_s=memcpy_gib_s(probe_mib),
        memcpy_probe_mib=probe_mib,
        vm_size=where.vm_size,
        vm_location=where.location,
        vm_zone=where.zone,
        vm_fault_domain=where.fault_domain,
        runner_name=runner_name(),
        measured_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **cells,  # type: ignore[arg-type]
    )


def stage_fingerprint(
    plan: RunPlan,
    *,
    settings: config.Settings,
    state_root: Path,
    shard: int = 0,
    job: ServerJob = WORK_JOB,
) -> HostFingerprintRow | None:
    """Record what machine this job drew, before anything else competes for it.

    Runs early on purpose. The bandwidth probe needs a gigabyte and an idle
    machine, and a job that has already started its heaviest step has neither -
    the model server in `work`, the embeddings and the site build in `assemble`.
    A probe taken at the end of a job would measure that step rather than the
    host.

    The row goes to this job's own segment, never to the day file. Ten jobs of
    one run each draw a machine and each record it, so ten runners would be
    appending to one path at once; on 2026-09-16 that race left the day
    header-only. `assemble` folds the segments into the head, and the attempt is
    in the name so a re-run corrects its first try rather than colliding with it.
    """
    knobs = settings.app.observability
    if not knobs.host_fingerprint:
        LOG.info("fingerprint off job=%s shard=%s run=%s", job, shard, plan.run_id)
        return None
    row = read_row(
        date=plan.date,
        run_id=plan.run_id,
        job=job,
        shard=shard,
        probe_mib=knobs.host_fingerprint_bandwidth_mib,
    )
    attempt = run_context.run_attempt()
    landed = ledger.write_segment(
        state_root,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        [row],
        run_id=plan.run_id,
        attempt=attempt,
        job=job,
        shard=shard,
    )
    LOG.info(
        "fingerprint job=%s shard=%s run=%s id=%s cpu=%s family=%s model=%s stepping=%s "
        "flags=%s l3_bytes=%s memcpy_gib_s=%s probe_mib=%s vm_size=%s zone=%s "
        "boot_seconds=%s mhz=%s rows=%s segment=%s",
        job,
        shard,
        plan.run_id,
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
        landed,
        ledger.segment_relpath(
            ledger.SegmentLedger.HOST_FINGERPRINT,
            run_id=plan.run_id,
            attempt=attempt,
            job=job,
            shard=shard,
        ),
    )
    return row
