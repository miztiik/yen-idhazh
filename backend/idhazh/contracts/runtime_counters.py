"""What llama-server itself counted during one `work` shard.

`state/runtime-counters.csv`. One row per shard per run, appended by the `work`
job just after it commits the rows its items earned.

**What one row covers.** Both `llamacpp:` figures are cumulative for the server
process, and a shard starts one llama-server and keeps it for the whole job. So
one scrape at job end is the whole shard, and there is nothing to subtract. A
per-request scrape would add requests to the thing it measures and still report
only the last one.

**Five cells are about the job rather than the server.** `job_seconds` is the
shard job's own clock, `cpu_model` is the processor it drew, `cpu_busy_pct` is
how much of that processor it actually used, `peak_rss_bytes` is the memory high
point it reached, and `model_load_ms` is what it paid before the first item. They
live here because one work job is one row, which is the grain all five facts
have; the run manifest is one row per run and a run draws up to eight hosts. The
truncation cap reverts on the slowest work job's wall-clock, and before these
cells the only place that number existed was the GitHub jobs API, which drops a
job record when the run ages out.

**Why this exists.** Every timing on the item-health ledger is a field the
summarize stage copied out of one model reply, and two documents publish rates
derived from it - `docs/architecture/summarize/throughput.md` and the console.
Nothing committed could check them, because the only place the server's own
counters landed was a job log with two days of retention. Rule #10 says an
unreconcilable number may not justify a design, so the second instrument had to
become a committed row.

**How rows compose into a run.** A run has one row per shard. The run figure is
the sum of the tokens over the sum of the seconds - never the mean of the
per-shard rates. A rate is a ratio, and averaging ratios weighs a shard that did
20 items the same as one that did 40
(`docs/reference/measurements.md`). Deliberately there is no per-row rate
property here: the pooling lives in `backend/utilities/reconcile_prefill.py`,
where it can only be done the one correct way.

**Why not a field on `RunManifest`.** Four reasons, and any one of them is
enough. The grain is wrong - a manifest run record is one run and this is one
shard, so the manifest would grow a variable-length list. The producer is wrong
- the manifest is written by `assemble`, in another job hours later, so these
numbers would have to travel inside the items artifact, which expires in a day
and is not uploaded at all when a job is cancelled. The audience is wrong -
`run.json` is a published payload a reader's browser fetches, and this is
measurement evidence that belongs under `state/`, which is never served. And the
timing is wrong - a concurrent branch was also opening `RunManifest`, and two
branches stamping one contract's changelog on the same day raise `TypeError` at
import (`docs/architecture/contracts/schemas.md`).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Timestamp,
)

#: The one spelling a payload timestamp leaves the process in, as `strptime`
#: reads it. `Timestamp` pins the same shape as a regex; this turns it back into
#: an instant so the row's own clock can be measured against its own scrape.
_SCRAPED_AT_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"

#: One line of printable ASCII. `state/runtime-counters.csv` is merged with the
#: union driver, which works line by line, so a cell that could hold a newline
#: could split one row across a merge.
CpuModel = Annotated[str, StringConstraints(pattern=r"^[ -~]+$", max_length=120)]

#: The Prometheus series each field is read from, on llama.cpp `b10598`. The
#: names are the wire format and the field names are ours, so a llama.cpp rename
#: is one edit here and shows up as a null column rather than as a wrong number.
#: Read from a real capture, not from the upstream README: the README at tag
#: b10598 lists neither `prompt_tokens_cached_total` nor the "excluding cached
#: tokens" wording that settles what `prompt_tokens_total` means.
SERIES: Final[dict[str, str]] = {
    "llamacpp:prompt_tokens_total": "prompt_tokens_total",
    "llamacpp:prompt_tokens_cached_total": "prompt_tokens_cached_total",
    "llamacpp:prompt_seconds_total": "prompt_seconds_total",
    "llamacpp:tokens_predicted_total": "tokens_predicted_total",
    "llamacpp:tokens_predicted_seconds_total": "tokens_predicted_seconds_total",
    "llamacpp:n_decode_total": "n_decode_total",
    "llamacpp:n_tokens_max": "n_tokens_max",
    "llamacpp:n_busy_slots_per_decode": "n_busy_slots_per_decode",
}

#: Fields whose series is a whole count. A value that is not whole is a rename
#: or a format change, and it raises rather than truncate.
_WHOLE: Final = frozenset(
    {
        "prompt_tokens_total",
        "prompt_tokens_cached_total",
        "tokens_predicted_total",
        "n_decode_total",
        "n_tokens_max",
    }
)

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

#: The column of `rss-samples.tsv` carrying llama-server's own high-water mark.
#: The sampler reads it out of `/proc/<pid>/status` every 15 seconds while the
#: server lives.
_RSS_PEAK_COLUMN: Final = "llama_vmhwm_kb"

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


class RuntimeCountersRow(Contract):
    """One `work` shard, one run, one row."""

    __schema_stem__: ClassVar[str] = "runtime-counters-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-30",
            change=(
                "Appended `cpu_busy_pct`, the share of every processor second the host "
                "spent busy over the job; `peak_rss_bytes`, llama-server's own high-water "
                "mark; and `model_load_ms`, the time the server took to open the weights."
            ),
            why=(
                "The row said what the server counted and how long the job took, and "
                "nothing about the machine that did it. Three questions had no committed "
                "answer. A shard that reads the prompt 2.30x slower than its sibling in "
                "the same run is either short of processor or waiting on something else, "
                "and only a busy figure separates those - the cgroup ran 3.99 of 4 "
                "processors when it was last measured by hand, so the reading is expected "
                "at or near 100 and a drop is the signal. Whether a candidate model fits "
                "the runner's 16 GB at `n_ctx` 8192 was answered by whether the run "
                "survived; a qualification proves a model is fast enough and faithful "
                "enough and proves nothing about what it holds. And model load is the "
                "fixed cost `run.shard_size` exists to amortise, which cannot be sized "
                "against a number nobody kept."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29",
            change=(
                "Appended `job_seconds`, the shard job's own clock up to this scrape, "
                "and `cpu_model`, the processor the host drew."
            ),
            why=(
                "The truncation cap reverts when the slowest work job passes 110 "
                "minutes on two of three scheduled runs, and no committed file carried "
                "a job's clock - only the GitHub jobs API did, and it drops a job "
                "record when the run ages out. A rollback rule that reads an instrument "
                "outside the repository is checked by hand or not at all. The CPU model "
                "lands in the same row because this project has measured a 3.1x swing "
                "in read throughput between hosts, so a clock without the part it was "
                "taken on cannot be compared with the next run's (Rule #10). Both are "
                "one fact about one work job, which is exactly this row's grain; the "
                "run manifest is one row per run and a run draws up to eight hosts."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27",
            change=(
                "Initial shape: the shard, and the llamacpp: counters its server "
                "reported at job end."
            ),
            why=(
                "The item-health ledger's prefill and decode timings are copied out of "
                "the model's own replies, one request at a time, and two published "
                "surfaces quote rates derived from them. Nothing committed could check "
                "either, because the server's own counters were scraped into a job log "
                "that keeps them for two days. A number that cannot be reconciled "
                "cannot justify a design (Rule #10), so the second instrument is now a "
                "committed row."
            ),
        ),
    )

    date: DateStamp = Field(
        description="The digest day, the same one the item-health row files under."
    )
    run_id: RunId
    shard: int = Field(ge=0, description="Which work shard this server served.")
    shards: int = Field(ge=1, description="How many shards the run split into. The denominator.")
    scraped_at: Timestamp = Field(
        description="When the counters were read. Job end, after the last item settled."
    )

    prompt_tokens_total: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the server actually read, cached ones excluded. The same "
            "quantity the ledger spells `input_tokens - cached_tokens`."
        ),
    )
    prompt_tokens_cached_total: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens reused from the cache instead of read. The ledger's `cached_tokens`."
        ),
    )
    prompt_seconds_total: float | None = Field(
        default=None, ge=0, description="Seconds spent reading prompts. The ledger's `prefill_ms`."
    )
    tokens_predicted_total: int | None = Field(
        default=None, ge=0, description="Tokens written. The ledger's `output_tokens`."
    )
    tokens_predicted_seconds_total: float | None = Field(
        default=None, ge=0, description="Seconds spent writing. The ledger's `decode_ms`."
    )
    n_decode_total: int | None = Field(
        default=None, ge=0, description="llama_decode() calls, speculative and multimodal excluded."
    )
    n_tokens_max: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The longest sequence the server saw, prompt plus generation. Says how "
            "close the day came to `n_ctx`."
        ),
    )
    n_busy_slots_per_decode: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Slots busy per decode call, averaged. Says whether batching happened at "
            "all, which is what separates 'more slots did not help' from 'more slots "
            "were never used'."
        ),
    )

    job_seconds: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Seconds from the shard job's first step to this scrape. It is a floor on "
            "the wall-clock the GitHub jobs API reports and never a ceiling: the steps "
            "after the scrape - the ledger push, two log summaries and the artifact "
            "uploads - are outside it."
        ),
    )
    cpu_model: CpuModel | None = Field(
        default=None,
        description=(
            "The `model name` line of the host's /proc/cpuinfo. `ubuntu-latest` is the "
            "label and this is the part, so a clock in this row can be read against "
            "another run's."
        ),
    )

    cpu_busy_pct: float | None = Field(
        default=None,
        ge=0,
        description=(
            "The share of every processor second the host spent busy between the job's "
            "first step and this scrape, from the aggregate `cpu` line of /proc/stat. "
            "The cgroup ran 3.99 of 4 processors the one time it was measured by hand, "
            "so the reading is expected at or near 100 and a DROP is the signal - it "
            "says the shard spent the job waiting rather than computing. Above 100 means "
            "the two readings disagree about the window, never that the host found a "
            "fifth processor."
        ),
    )
    peak_rss_bytes: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The highest `VmHWM` llama-server reached, over every sample this shard "
            "took. It answers what a qualification cannot: whether a candidate model can "
            "be SERVED on the runner's 16 GB at `n_ctx` 8192 with headroom left. Until "
            "this cell, a run either survived or the runner killed it."
        ),
    )
    model_load_ms: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds from llama-server saying it is loading the weights to saying "
            "they are loaded, read off its own log stamps. Model load is the fixed cost "
            "`run.shard_size` exists to amortise, so it is one figure per shard and "
            "never one per item."
        ),
    )

    @model_validator(mode="after")
    def _shard_fits_inside_the_run(self) -> Self:
        if self.shard >= self.shards:
            raise ValueError("a shard index must be below the shard count")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. A series this build does not publish is an empty cell.

        Empty is not zero. A server that never answered and a server that read no
        tokens are different facts, and one of them is a broken scrape.
        """
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never a zero."""
        payload: dict[str, Any] = {name: row[name] for name in cls.model_fields}
        for name in cls._absent_when_blank():
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

    @classmethod
    def _absent_when_blank(cls) -> tuple[str, ...]:
        """Every optional cell, derived rather than listed a second time.

        A field declared `default=None` is one this row can be missing. Reading
        that off the model means a column added later cannot be forgotten here
        and come back from the ledger as the string `""`.
        """
        return tuple(
            name for name, field in cls.model_fields.items() if field.default is None
        )

    @classmethod
    def from_metrics_text(
        cls,
        text: str,
        *,
        date: str,
        run_id: str,
        shard: int,
        shards: int,
        scraped_at: str,
        job_started_at: int | None = None,
        cpu_model: str | None = None,
        cpu_stat_at_start: str | None = None,
        cpu_stat_at_end: str | None = None,
        rss_samples: str | None = None,
        server_log: str | None = None,
    ) -> Self:
        """Read one row out of a `GET /metrics` body and the host readings beside it.

        A series this build does not publish is left null rather than defaulted,
        so a llama.cpp rename shows as a missing column instead of as a zero that
        a later reader would average. A series that is present but unreadable
        raises: the workflow step tolerates its own failure, so a broken scrape
        costs this row and never the shard.

        `job_started_at` is the epoch second the job's first step stamped, and
        the clock is worked out here against `scraped_at` rather than by the
        caller - so the two cells can never say different things about the same
        instant. No stamp leaves the cell empty. Empty is not zero: a job whose
        stamp went missing and a job that took no time are different facts.

        The last four arguments are raw text the host printed, not numbers a
        caller worked out: the `cpu` line of `/proc/stat` at each end of the job,
        the memory sampler's whole file, and llama-server's own log. Every
        derivation happens here, so the arithmetic behind three cells is in one
        testable place rather than spread across a shell script.
        """
        values: dict[str, Any] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, raw = line.partition(" ")
            field = SERIES.get(name)
            if field is None:
                continue
            values[field] = _number(name, field, raw.strip())
        return cls.model_validate(
            {
                "date": date,
                "run_id": run_id,
                "shard": shard,
                "shards": shards,
                "scraped_at": scraped_at,
                "job_seconds": _elapsed(scraped_at, job_started_at),
                "cpu_model": (cpu_model or "").strip() or None,
                "cpu_busy_pct": _cpu_busy_pct(cpu_stat_at_start, cpu_stat_at_end),
                "peak_rss_bytes": _peak_rss_bytes(rss_samples),
                "model_load_ms": _model_load_ms(server_log),
                **values,
            }
        )


def _cpu_ticks(text: str | None) -> dict[str, int] | None:
    """The aggregate `cpu` line of `/proc/stat`, by field name.

    Reads the line out of whatever it is handed - the workflow passes that one
    line, and a whole capture of the file is the same fact with the per-processor
    lines still attached. Anything else - an empty variable, a truncated read -
    is absent rather than a zero reading.
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


def _cpu_busy_pct(at_start: str | None, at_end: str | None) -> float | None:
    """Busy processor time as a share of processor time available, between two reads.

    Differencing two reads is what makes this the job's number rather than the
    host's: `/proc/stat` counts since boot, and a runner boots minutes of mostly
    idle time before the job starts. The denominator is every processor's time,
    so nothing here needs to know how many there are.
    """
    start = _cpu_ticks(at_start)
    end = _cpu_ticks(at_end)
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


def _peak_rss_bytes(text: str | None) -> int | None:
    """The highest `VmHWM` the memory sampler saw, in bytes.

    The column is found by name off the sampler's own header rather than by
    position, so a column added to the left of it cannot silently shift which
    number this reads. `/proc` reports kilobytes and this row reports bytes.
    """
    if not text:
        return None
    lines = text.splitlines()
    if not lines:
        return None
    header = lines[0].split("\t")
    if _RSS_PEAK_COLUMN not in header:
        return None
    column = header.index(_RSS_PEAK_COLUMN)
    peaks = [
        int(cells[column])
        for cells in (line.split("\t") for line in lines[1:])
        if len(cells) > column and cells[column].strip().isdigit()
    ]
    return max(peaks) * 1024 if peaks else None


def _log_microseconds(line: str) -> int | None:
    """A llama-server log stamp, in microseconds since its process started."""
    found = _LOG_INSTANT.match(line)
    if found is None:
        return None
    minutes, seconds, milliseconds, microseconds = (int(part) for part in found.groups())
    return (((minutes * 60) + seconds) * 1000 + milliseconds) * 1000 + microseconds


def _model_load_ms(text: str | None) -> float | None:
    """Milliseconds between the two lines llama-server brackets its load with.

    Both ends have to be present and stamped. A build that renames either line,
    or one that logs without timestamps, leaves the cell empty - which reads as
    unknown, and is the failure `SERIES` is written for as well.
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


def _elapsed(scraped_at: str, job_started_at: int | None) -> int | None:
    """Job start to scrape, in seconds. A stamp in the future fails `ge=0` loudly."""
    if job_started_at is None:
        return None
    scraped = datetime.strptime(scraped_at, _SCRAPED_AT_FORMAT).replace(tzinfo=UTC)
    return int(scraped.timestamp()) - job_started_at


def _number(series: str, field: str, raw: str) -> float | int:
    value = float(raw)
    if field not in _WHOLE:
        return value
    if not value.is_integer():
        raise ValueError(f"{series} is a count and reported {raw!r}")
    return int(value)
