"""What silicon did this job draw, what can it do, and what did the job cost?

`host.py` answers what the machine is DOING and changes every second. This
answers what the machine IS and is fixed for the length of the job, so it is
read once rather than sampled.

Two steps write it, because two of its cells are only knowable at opposite ends
of a job: `stage_fingerprint` probes the machine before the heaviest step, and
`stage_job_clock` records the clock and the weight-load cost after the last item.
Both go to the job's own segment and `stages.compact` unites them.

Every reading here degrades to nothing. None of these files or services exists
on a developer machine, and a missing instrument records an empty cell rather
than failing a run (CLAUDE.md section 1a).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import statistics
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

from idhazh import ledger, run_context
from idhazh.contracts.base import WORK_JOB, ServerJob
from idhazh.contracts.host_fingerprint import WATCHED_FLAGS, HostFingerprintRow
from idhazh.contracts.run_plan import RunPlan
from idhazh.telemetry.host import runner_name

if TYPE_CHECKING:  # pragma: no cover - a type, not a runtime dependency
    from idhazh import config

LOG: Final = logging.getLogger("idhazh")

CPUINFO: Final = Path("/proc/cpuinfo")
UPTIME: Final = Path("/proc/uptime")

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
    probe_floor_mib: int,
    probe_cache_multiple: int,
    ask_placement: bool = True,
    cpuinfo: str | None = None,
    cache_root: Path | None = None,
) -> HostFingerprintRow:
    """Everything this machine will say about itself, taken once."""
    text = _text(CPUINFO) if cpuinfo is None else cpuinfo
    fields, clocks = _cpuinfo_fields(text or "")
    where = placement() if ask_placement else Placement()
    l3_cache_bytes = cache_bytes(root=cache_root)
    cells: dict[str, object] = {
        "cpu_model": fields.get("model name") or None,
        "cpu_vendor": fields.get("vendor_id") or None,
        "cpu_family": _as_int(fields.get("cpu family")),
        "cpu_model_number": _as_int(fields.get("model")),
        "cpu_stepping": _as_int(fields.get("stepping")),
        "microcode": fields.get("microcode") or None,
        "cores": _as_int(fields.get("cpu cores")),
        "threads": len(clocks) or None,
        "l3_cache_bytes": l3_cache_bytes,
        "flags": watched_flags(text),
    }
    # The recorded size is the derived one, never the configured floor, so the
    # column says what was probed rather than what somebody asked for.
    probe_mib = probe_buffer_mib(probe_floor_mib, l3_cache_bytes, probe_cache_multiple)
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

    Runs early on purpose. The bandwidth probe needs a gigabyte or two and an
    idle machine, and a job that has already started its heaviest step has
    neither - the model server in `work`, the embeddings and the site build in
    `assemble`. A probe taken at the end of a job would measure that step rather
    than the host. How much it needs depends on the cache the machine reports:
    `probe_buffer_mib` sizes each of the two buffers against it.

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
        probe_floor_mib=knobs.host_fingerprint_bandwidth_floor_mib,
        probe_cache_multiple=knobs.host_fingerprint_bandwidth_cache_multiple,
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
        ledger.day_shard_relpath(
            ledger.SegmentLedger.HOST_FINGERPRINT,
            date=plan.date,
            run_id=plan.run_id,
            attempt=attempt,
            job=job,
            shard=shard,
        ),
    )
    return row


def stage_job_clock(
    plan: RunPlan,
    *,
    settings: config.Settings,
    state_root: Path,
    shard: int = 0,
    job: ServerJob = WORK_JOB,
    job_started_at: int | None = None,
    server_log_path: Path | None = None,
    metrics_path: Path | None = None,
) -> HostFingerprintRow | None:
    """What the job cost, recorded onto the host row the probe opened.

    The other end of `stage_fingerprint`. Four cells of that row are only knowable
    once the job is over - the wall clock it spent, what opening the weights cost
    before the first item, and the two prompt counters the model server itself
    kept - and moving the probe to job end to collect them would destroy
    `mhz_at_probe` and `boot_seconds`, which want an idle machine. So this writes
    them as a second row of the same key, into the same segment, filling nothing
    the probe already filled.

    `stages.compact` is what unites the two. Neither row is ever edited: the
    probe's cells and these four are disjoint, so the fold takes the union and the
    day file holds one row a job.

    The two prompt cells are the second instrument. The item ledger answers the
    same question by arithmetic over its own rows, which cannot check those rows;
    the server's own counters can disagree with them, and twice they have.

    A job that dies between the probe and this step leaves a usable half-row with
    four empty cells, which is the degrade path rather than a failure. So is a
    stamp that never arrived, or a scrape the server was already gone for: an
    empty cell says the reading was not taken, where a zero would claim a job that
    took no time and read no tokens.
    """
    knobs = settings.app.observability
    if not knobs.host_fingerprint:
        LOG.info("job clock off job=%s shard=%s run=%s", job, shard, plan.run_id)
        return None
    scraped_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    prompt_tokens, prompt_seconds = server_prompt_totals(_text_if_readable(metrics_path))
    row = HostFingerprintRow(
        version=HostFingerprintRow.schema_version(),
        date=plan.date,
        run_id=plan.run_id,
        job=job,
        shard=shard,
        model_load_ms=model_load_ms(_text_if_readable(server_log_path)),
        job_seconds=job_seconds(scraped_at, job_started_at),
        server_prompt_tokens=prompt_tokens,
        server_prompt_seconds=prompt_seconds,
    )
    attempt = run_context.run_attempt()
    landed = ledger.extend_segment(
        state_root,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        [row],
        run_id=plan.run_id,
        attempt=attempt,
        job=job,
        shard=shard,
    )
    LOG.info(
        "job clock job=%s shard=%s run=%s job_seconds=%s model_load_ms=%s "
        "server_prompt_tokens=%s server_prompt_seconds=%s rows=%s segment=%s",
        job,
        shard,
        plan.run_id,
        row.job_seconds,
        row.model_load_ms,
        row.server_prompt_tokens,
        row.server_prompt_seconds,
        landed,
        ledger.day_shard_relpath(
            ledger.SegmentLedger.HOST_FINGERPRINT,
            date=plan.date,
            run_id=plan.run_id,
            attempt=attempt,
            job=job,
            shard=shard,
        ),
    )
    return row


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
    return (None if tokens is None else int(tokens)), (
        None if seconds is None else float(seconds)
    )


def _number(series: str, field: str, raw: str) -> float | int:
    value = float(raw)
    if field not in _WHOLE:
        return value
    if not value.is_integer():
        raise ValueError(f"{series} is a count and reported {raw!r}")
    return int(value)
