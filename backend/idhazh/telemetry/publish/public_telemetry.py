"""Publish the browser-safe telemetry projection.

The source is the item-health ledger (`state/raw/item-health/`), and it carries
fields the browser must never receive. This module writes a narrow monthly
projection under `frontend/public/telemetry/`, which is the only item-health data
the console fetches at runtime.

**The two grains differ on purpose.** The ledger files by day, because a run
writes one day and a removal takes one day. The mirror files by month, because
its grain follows what a browser fetches and the console prices a window in month
files. So a month here is folded from that month's days - at most 31 of them -
and `docs/concepts/partitions.md` owns both rules.

The projection's shape is `PublicTelemetryRow`, not a list of names here. This
module owns *when* a shard is written and *from what*; the contract owns which
cells may cross and what each one may hold (Guardrail #3).

It owns *where* a shard sits too, through `shard_path`. The gardener's
`telemetry-aggregate` task deletes a copy once it is past that task's
public-copy series, and it finds the copy by the `<YYYY-MM>.csv` name
`shard_path` spells, through `retention.month_shards`, rather than by a spelling
of its own.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
from collections.abc import Collection
from pathlib import Path
from typing import Final

from idhazh import config, ledger, month_partition
from idhazh.atomic_write import write_atomic_bytes
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.public_telemetry import FORBIDDEN_COLUMNS, PublicTelemetryRow

PUBLIC_COLUMNS: Final[tuple[str, ...]] = PublicTelemetryRow.csv_columns()
#: Where the browser's copy sits under `frontend/public/`.
PUBLIC_TELEMETRY_DIRNAME: Final = "telemetry"
DEFAULT_PUBLIC_ROOT: Final = config.REPO_ROOT / "frontend" / "public" / PUBLIC_TELEMETRY_DIRNAME

__all__ = [
    "DEFAULT_PUBLIC_ROOT",
    "FORBIDDEN_COLUMNS",
    "PUBLIC_COLUMNS",
    "PUBLIC_TELEMETRY_DIRNAME",
    "migrate",
    "publish",
    "read_shard",
    "shard_path",
    "shard_relpath",
]


def shard_path(public_root: Path, month: str) -> Path:
    """The browser's copy of one item-health month.

    Spelled here and nowhere else, because the step that writes a copy and the
    step that deletes one have to name the same file. Two spellings of
    `<month>.csv` would delete a mirror nobody published and leave the one that
    was published behind.
    """
    return public_root / f"{month}.csv"


def shard_relpath(month: str) -> str:
    """`frontend/public/telemetry/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return f"frontend/public/{PUBLIC_TELEMETRY_DIRNAME}/{month}.csv"


def _settled_days(state_root: Path, days: list[str]) -> list[PublicTelemetryRow]:
    """These days of the census, settled, as the rows a reader is allowed to see.

    Read through the ledger door as `ItemHealthRow`s, each day settled on its
    own, and projected to the public shape here.
    """
    return [
        PublicTelemetryRow.from_csv_row(row.csv_row())
        for row in ledger.load_days(state_root, LedgerName.ITEM_HEALTH, days, model=ItemHealthRow)
    ]


def read_shard(path: Path) -> list[PublicTelemetryRow]:
    """Load a published shard back through the contract that wrote it.

    A published shard is the one artifact here nobody can re-derive once its
    source month has been folded away, so reading it back is what says it still
    loads rather than merely still parses.

    **The header is checked as a prefix, the way the browser checks it.** The
    projection grows by appending, so a shard published before the last widening
    is the current header cut short - and refusing it would make every widening a
    release blocker for exactly the file this function exists to prove still
    loads (`CLAUDE.md` section 11). The cells behind the cut come back null,
    which is what `from_csv_row` already does with an empty one. A header that
    disagrees inside the prefix is still refused: that is a shard from a
    different shape, not an older one.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != PUBLIC_COLUMNS[: len(header)]:
            raise ValueError(
                f"{path.as_posix()} header is {list(header)}, the contract writes "
                f"{list(PUBLIC_COLUMNS)}"
            )
        return [PublicTelemetryRow.from_csv_row(row) for row in reader]


def _encode(rows: list[PublicTelemetryRow]) -> bytes:
    """The exact bytes a shard holds, so a write can be skipped when they match."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=PUBLIC_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(row.csv_row() for row in rows)
    return buffer.getvalue().encode("utf-8")


def _write(path: Path, rows: list[PublicTelemetryRow]) -> int:
    write_atomic_bytes(path, _encode(rows))
    return len(rows)


def _write_if_changed(path: Path, rows: list[PublicTelemetryRow]) -> bool:
    """Write the shard only when its bytes would change; report whether they did.

    The freeze rule binds a closed month; this binds an unchanged one. The
    comparison is the shard's own bytes - a timestamp says when a file was
    written, never whether its content moved.
    """
    payload = _encode(rows)
    if path.exists() and path.read_bytes() == payload:
        return False
    write_atomic_bytes(path, payload)
    return True


def publish(
    *,
    state_root: Path = config.REPO_ROOT / ledger.STATE_DIRNAME,
    public_root: Path = DEFAULT_PUBLIC_ROOT,
    ensure_month: str | None = None,
    months: Collection[str] | None = None,
) -> list[Path]:
    """Write only caller-named item-health months.

    A month is written only when its projected bytes differ from the shard
    already on disk. An empty month list reads nothing; historical rebuilding
    must name its month range explicitly.

    `months` names the months a caller believes changed. A month outside it is
    skipped without being read, even when its shard is missing. A fresh clone
    or historical repair names the months to rebuild rather than discovering
    them by scanning the ledger.

    Two freezes compose. The month filter keeps a closed month from being read
    at all; the byte comparison keeps a re-derived month from being rewritten
    when nothing moved. The first is the freeze rule of
    `docs/concepts/partitions.md`; the second is how it decides "only when
    a correction targets it" - a correction changes the bytes, an ordinary
    re-run does not.

    **The ledger files by day and this mirror files by month**, so a month is
    read as that month's days through `ledger.load_days`, each day settled on
    its own.
    Settled rather than concatenated, because a day holds every writer's rows: a
    re-run's second attempt sits beside the first, and publishing both would show
    a reader one item twice. Its input is one month, so a named month reads at
    most 31 days.

    The daily caller passes the one month it appended to, so an ordinary run
    reads one month's days whatever the ledger holds. Historical rebuilding is
    explicit and does not run as a side effect of daily publication.
    """
    public_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for month in sorted(set(months or ())):
        target = shard_path(public_root, month)
        rows = _settled_days(state_root, ledger.month_days(month))
        if (rows or target.exists()) and _write_if_changed(target, rows):
            written.append(target)
    if ensure_month is not None and all(path.stem != ensure_month for path in written):
        target = shard_path(public_root, ensure_month)
        if not target.exists():
            _write(target, [])
        written.append(target)
    return written


def migrate(
    public_root: Path = DEFAULT_PUBLIC_ROOT, *, months: Collection[str] = ()
) -> list[tuple[Path, int, bool]]:
    """Rewrite named committed shards through the contract, and read them back.

    The publisher's own round trip rather than a utility of its own, because the
    pair that has to hold is the writer and the reader a run already uses. It
    never reads `state/`: a shard whose source month has been folded away still
    has to load.

    An empty month list does no work. The operator names the range to migrate.
    """
    results: list[tuple[Path, int, bool]] = []
    for path in (shard_path(public_root, month) for month in sorted(set(months))):
        if not path.is_file():
            continue
        before = path.read_bytes()
        rows = read_shard(path)
        _write(path, rows)
        if read_shard(path) != rows:
            raise ValueError(f"{path.as_posix()} did not read back as it was written")
        results.append((path, len(rows), path.read_bytes() == before))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=config.REPO_ROOT / ledger.STATE_DIRNAME)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC_ROOT)
    parser.add_argument("--from-month", required=True, help="First YYYY-MM month to read.")
    parser.add_argument("--through-month", required=True, help="Last YYYY-MM month to read.")
    parser.add_argument("--ensure-month", help="Write an empty shard when this month has no rows.")
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Rewrite the committed shards through the contract instead of publishing.",
    )
    args = parser.parse_args()
    months = month_partition.months_between(args.from_month, args.through_month)
    if args.migrate:
        for path, rows, unchanged in migrate(args.public, months=months):
            state = "unchanged" if unchanged else "REWRITTEN"
            name = path.relative_to(config.REPO_ROOT).as_posix()
            print(f"{name} {rows} rows {path.stat().st_size} bytes {state}")
        return
    for path in publish(
        state_root=args.state,
        public_root=args.public,
        ensure_month=args.ensure_month,
        months=months,
    ):
        size = path.stat().st_size
        gzipped = len(gzip.compress(path.read_bytes()))
        print(f"{path.relative_to(config.REPO_ROOT).as_posix()} {size} bytes {gzipped} gzip bytes")


if __name__ == "__main__":
    main()
