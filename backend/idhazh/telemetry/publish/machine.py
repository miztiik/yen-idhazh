"""Publish what each work shard's machine did, a month at a time.

One row per `(date, run_id, shard)`, folded from the two ledgers that record it:
`state/item-health/<Y>/<M>/<DD>/` for what the items cost, and
`state/host-fingerprint/<Y>/<M>/<DD>/` for what the machine was and what the
model server itself counted. The shape is `MachineShardRow`, and it says in its
own module why both instruments ride on one row.

**An ordinary month-scoped producer.** Both sources file by day, so the month
boundary is inherited rather than drawn here, and the read is scoped by
`series.months_to_write` - a daily run reads the one month it appended to, and a
month whose published shard is missing as well, so a fresh clone and a first
backfill both land. The cover is `observability.public_machine_keep_months`,
fourteen months or about 426 days, which is what the published directory
promises a reader.

**Every COLUMN of the fold, but only the work job's rows.** `PUBLISHED_JOB`
names the one job this series is about. The plan and assemble jobs run one shard
each and serve different weights, so pooling them into a shard board would
answer about a matrix nobody dispatched.
"""

from __future__ import annotations

import csv
from collections.abc import Collection, Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import day_shards, ledger
from idhazh.contracts.base import WORK_JOB
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.machine_shard import MachineShardRow
from idhazh.ledger import CsvContract
from idhazh.telemetry.publish import series

PUBLIC_COLUMNS: Final[tuple[str, ...]] = MachineShardRow.csv_columns()
DIRNAME: Final = series.MACHINE_DIRNAME
SUFFIX: Final = ".csv"
#: The one job this series is about, for the reason in the module docstring.
PUBLISHED_JOB: Final = WORK_JOB

__all__ = [
    "DIRNAME",
    "PUBLIC_COLUMNS",
    "PUBLISHED_JOB",
    "SUFFIX",
    "fold_shards",
    "month_days",
    "publish",
    "read_shard",
    "shard_path",
    "shard_relpath",
]


def shard_path(digest_root: Path, month: str) -> Path:
    """The browser's copy of one month of machine rows."""
    return series.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/machine/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return series.relpath(DIRNAME, f"{month}{SUFFIX}")


def _figure(cell: str | None) -> float | None:
    """A cell as a number, or nothing. An empty cell is unknown and never zero."""
    if cell is None or cell.strip() == "":
        return None
    try:
        return float(cell)
    except ValueError:
        return None


def _whole(value: float | None) -> int | None:
    return None if value is None else round(value)


def _highest(carried: int | None, value: int | None) -> int | None:
    if value is None:
        return carried
    return value if carried is None else max(carried, value)


def month_days(root: Path, *, oldest_month: str) -> dict[str, list[str]]:
    """Each month at or above the boundary, to the dates its days recorded.

    One directory listing and no file opened, so this costs the day tree's shape
    rather than its contents. A month below the retention boundary is dropped
    here, because reading one would write a file the prune deletes on the same
    pass (Guardrail #12).

    Dates rather than files, because a day is a directory of writer-owned files
    and the caller settles it.
    """
    return {
        month: dates
        for month, dates in day_shards.dates_by_month(root, days=UNBOUNDED_WINDOW).items()
        if month >= oldest_month
    }


def _settled_month(
    root: Path,
    dates: Iterable[str],
    key: tuple[str, ...],
    model: type[CsvContract],
) -> list[dict[str, str]]:
    """Every row a month recorded, each of its days settled on its own.

    Settled rather than concatenated. A work shard and assemble each leave their
    own file in a day, and a re-run leaves a second attempt beside the first, so
    reading them all would add one measurement to the month twice.
    """
    return [row for date in dates for row in day_shards.settled_day(root, date, key, model)]


class _Fold:
    """One shard's cells while they are being added up."""

    def __init__(self) -> None:
        self.items = 0
        self.read_tokens: int | None = None
        self.read_ms: int | None = None
        self.cached_tokens: int | None = None
        self.written_tokens: int | None = None
        self.write_ms: int | None = None
        self.longest_sequence: int | None = None
        self.n_ctx_configured: int | None = None
        self.cpu_busy_pct: float | None = None
        self.llama_rss_peak_bytes: int | None = None
        self.python_rss_bytes: int | None = None
        self.cpu_model: str | None = None
        self.model_load_ms: float | None = None
        self.job_seconds: int | None = None
        self.server_prompt_tokens: int | None = None
        self.server_prompt_seconds: float | None = None

    def add_item(self, row: Mapping[str, str]) -> None:
        """One item row folded in. A missing cell contributes nothing, never a zero."""
        read_in = _figure(row.get("input_tokens"))
        cached = _figure(row.get("cached_tokens"))
        written = _figure(row.get("output_tokens"))
        if read_in is not None and cached is not None:
            self.items += 1
            self.read_tokens = (self.read_tokens or 0) + max(round(read_in - cached), 0)
            self.cached_tokens = (self.cached_tokens or 0) + round(cached)
            if written is not None:
                self.longest_sequence = _highest(
                    self.longest_sequence, round(read_in + written)
                )
        if written is not None:
            self.written_tokens = (self.written_tokens or 0) + round(written)
        prefill = _whole(_figure(row.get("prefill_ms")))
        if prefill is not None:
            self.read_ms = (self.read_ms or 0) + prefill
        decode = _whole(_figure(row.get("decode_ms")))
        if decode is not None:
            self.write_ms = (self.write_ms or 0) + decode
        self.n_ctx_configured = _highest(
            self.n_ctx_configured, _whole(_figure(row.get("n_ctx_configured")))
        )
        busy = _figure(row.get("cpu_busy_pct"))
        if busy is not None:
            self.cpu_busy_pct = (
                busy if self.cpu_busy_pct is None else min(self.cpu_busy_pct, busy)
            )
        self.llama_rss_peak_bytes = _highest(
            self.llama_rss_peak_bytes, _whole(_figure(row.get("llama_rss_peak_bytes")))
        )
        self.python_rss_bytes = _highest(
            self.python_rss_bytes, _whole(_figure(row.get("python_rss_bytes")))
        )

    def add_host(self, row: Mapping[str, str]) -> None:
        """The machine record's half. A job writes two rows, so a filled cell wins."""
        model = (row.get("cpu_model") or "").strip()
        if model:
            self.cpu_model = model
        load = _figure(row.get("model_load_ms"))
        if load is not None:
            self.model_load_ms = load
        for name in ("job_seconds", "server_prompt_tokens"):
            value = _whole(_figure(row.get(name)))
            if value is not None:
                setattr(self, name, value)
        seconds = _figure(row.get("server_prompt_seconds"))
        if seconds is not None:
            self.server_prompt_seconds = seconds

    def row(self, *, day: str, run_id: str, shard: int) -> MachineShardRow:
        return MachineShardRow(
            version=MachineShardRow.schema_version(),
            date=day,
            run_id=run_id,
            shard=shard,
            items=self.items,
            read_tokens=self.read_tokens,
            read_ms=self.read_ms,
            cached_tokens=self.cached_tokens,
            written_tokens=self.written_tokens,
            write_ms=self.write_ms,
            longest_sequence=self.longest_sequence,
            n_ctx_configured=self.n_ctx_configured,
            cpu_model=self.cpu_model,
            cpu_busy_pct=self.cpu_busy_pct,
            llama_rss_peak_bytes=self.llama_rss_peak_bytes,
            python_rss_bytes=self.python_rss_bytes,
            model_load_ms=self.model_load_ms,
            job_seconds=self.job_seconds,
            server_prompt_tokens=self.server_prompt_tokens,
            server_prompt_seconds=self.server_prompt_seconds,
        )


def fold_shards(
    health: Iterable[Mapping[str, str]], hosts: Iterable[Mapping[str, str]]
) -> list[MachineShardRow]:
    """One row per work shard, from the raw cells of the two ledgers.

    Pure, so a test drives it from two lists and the caller is the only thing
    that knows where the day files are. Rows leave ordered by date, then run,
    then shard index, so a re-derived month carries identical bytes and
    `series.write_if_changed` can skip the write.

    A shard the machine record reached and the item ledger did not still gets a
    row: the clock, the weights load and the server's own counters are what that
    row is for, and dropping it would hide a shard whose every item failed. A
    shard only the item ledger reached gets one too, with the machine cells
    empty.
    """
    folds: dict[tuple[str, str, int], _Fold] = {}

    def at(day: str, run_id: str, shard: float | None) -> _Fold | None:
        if shard is None or not run_id or not day:
            return None
        key = (day, run_id, int(shard))
        found = folds.get(key)
        if found is None:
            found = _Fold()
            folds[key] = found
        return found

    for row in health:
        fold = at(
            (row.get("date") or "").strip(),
            (row.get("run_id") or "").strip(),
            _figure(row.get("shard")),
        )
        if fold is not None:
            fold.add_item(row)

    for row in hosts:
        if (row.get("job") or PUBLISHED_JOB) != PUBLISHED_JOB:
            continue
        fold = at(
            (row.get("date") or "").strip(),
            (row.get("run_id") or "").strip(),
            _figure(row.get("shard")),
        )
        if fold is not None:
            fold.add_host(row)

    return [
        folds[key].row(day=key[0], run_id=key[1], shard=key[2]) for key in sorted(folds)
    ]


def read_shard(path: Path) -> list[MachineShardRow]:
    """Load a published shard back through the contract that wrote it."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != PUBLIC_COLUMNS:
            raise ValueError(
                f"{path.as_posix()} header is {list(header)}, the contract writes "
                f"{list(PUBLIC_COLUMNS)}"
            )
        return [MachineShardRow.from_csv_row(row) for row in reader]


def publish(
    *,
    state_root: Path,
    digest_root: Path,
    keep_months: int,
    today: date,
    months: Collection[str] | None = None,
    ensure_month: str | None = None,
) -> list[Path]:
    """Write a published machine shard for each month that changed."""
    oldest = series.oldest_month_kept(today, keep_months)
    health_root = state_root / ledger.ITEM_HEALTH_DIRNAME
    host_root = state_root / ledger.HOST_FINGERPRINT_DIRNAME
    health_days = month_days(health_root, oldest_month=oldest)
    host_days = month_days(host_root, oldest_month=oldest)
    available = sorted({*health_days, *host_days})

    # Only the months this run has to read are opened. A month outside the set
    # keeps the shard it was published with, which is what holds the daily cost
    # at one month rather than the whole cover (Guardrail #12, decision 1).
    wanted = series.months_to_write(
        available,
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        months=months,
        oldest_kept=oldest,
    )
    folded: dict[str, list[MachineShardRow]] = {}
    for month in wanted:
        folded[month] = fold_shards(
            _settled_month(
                health_root, health_days.get(month, []), ledger.ITEM_HEALTH_KEY, ItemHealthRow
            ),
            _settled_month(
                host_root,
                host_days.get(month, []),
                ledger.HOST_FINGERPRINT_KEY,
                HostFingerprintRow,
            ),
        )

    def encode(month: str) -> bytes:
        return series.encode_csv(
            PUBLIC_COLUMNS, (row.csv_row() for row in folded.get(month, []))
        )

    return series.publish_series(
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        available=available,
        encode=encode,
        keep_months=keep_months,
        today=today,
        months=months,
        ensure_month=ensure_month,
    )
