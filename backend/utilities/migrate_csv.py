"""Move the two CSV ledgers onto the ledger door, once, and prove every row came across.

Removal condition: delete this module once `--check` exits 0 on `main` and no
run that checked out the CSV layout can still push, because then no CSV of
either ledger is left for it to move.

`state/feed-retirements.csv` and every `state/visual-prunes/<YYYY>/<MM>/<DD>.csv`
become files under `state/raw/<ledger>/<YYYY>/<MM>/<DD>/`, written through
`ledger.persist`, one file per day. A retirement has no date field of its own,
so it is filed under the day it was retired, which is where
`telemetry.source_health.file_retirements` files a new one.

    python backend/utilities/migrate_csv.py --state-dir state --run-id <YYYY-MM-DD-NNNN>
        --git-sha <sha> [--ledger feed-retirements|visual-prunes] [--check]

| Exit | Meaning |
| --- | --- |
| 0 | Every source CSV migrated, or there was none. A second run exits 0 and writes nothing |
| 1 | A row did not read back, or `--check` found a CSV left. No CSV was deleted |
| 2 | A file for the same work unit exists and holds other rows than this run would write |

A malformed `--run-id` or `--git-sha` is refused by the argument parser with its
own usage message, before anything is read.

**Nothing is deleted until everything is proven.** Every day of every ledger
asked for is written, read back field for field and cell for cell against the
CSV row it came from, and only then are the CSV files removed. A row that does
not read back removes the files this run wrote and leaves every CSV where it
was.

**Running it twice is safe by construction.** Every file carries
`WriterIdentity(run_id, attempt=1, job=migrate, shard=0, producer=utilities.migrate_csv,
git_sha)`, so a second run with the same `--run-id` mints the same `unit_id` for
each day and the same `content_sha256` for its rows. A file for that unit that
matches is left alone, and a CSV still beside it is deleted. **Run it again with
the first `--run-id`**: a new run id is a new work unit for every day, so the
check that would have caught a disagreement never fires and every day is
written twice. `--git-sha` may differ, because it is in neither identifier.

**Two migrations that disagree are both kept.** Overwriting a committed file is a
one-way write, so a unit whose file holds other rows exits 2 and names the day
and the file, and a person decides.

**The CSV addresses are spelled here, and nowhere else.** The registry
describes where each ledger sits now, so it no longer names where it sat, and a
path builder in the ledger for a layout nothing writes would outlive this file.
They are history: `<ledger>.csv` at the top of the state tree, and
`<ledger>/<YYYY>/<MM>/<DD>.csv` below it.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import tempfile
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from idhazh import day_partition, ledger
from idhazh.contracts.base import COMMIT_SHA_PATTERN, RUN_ID_PATTERN, ServerJob
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.file_envelope import FileEnvelope, WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow

#: The name every file this writes carries as its producer.
PRODUCER: Final = "utilities.migrate_csv"

#: A person runs this once, so it is the first and only attempt, as one shard.
ATTEMPT: Final = 1
SHARD: Final = 0

#: The suffix both CSV layouts used, a format literal of the layout being retired.
CSV_SUFFIX: Final = ".csv"

EXIT_MIGRATED: Final = 0
EXIT_NOT_PROVEN: Final = 1
EXIT_DISAGREES: Final = 2

type Row = FeedRetirementRow | VisualPruneRow

#: Each ledger this moves, the contract its rows are, and the cell that names the
#: day a row is filed under.
LEDGERS: Final[dict[LedgerName, tuple[type[FeedRetirementRow] | type[VisualPruneRow], str]]] = {
    LedgerName.FEED_RETIREMENTS: (FeedRetirementRow, "retired_on"),
    LedgerName.VISUAL_PRUNES: (VisualPruneRow, "date"),
}


class NotProvenError(Exception):
    """A row did not come across whole, so nothing is deleted. Exit 1."""


class DisagreesError(Exception):
    """A committed file for one work unit holds other rows than this run would write. Exit 2."""


def _shown(state_dir: Path, path: Path) -> str:
    """A path as it may leave the process: relative, POSIX (CLAUDE.md section 2)."""
    return f"{ledger.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}"


def csv_files(state_dir: Path, which: LedgerName) -> list[Path]:
    """Every CSV file this ledger was committed as, oldest first.

    A day tree that holds a name it cannot place stops the read, through
    `day_partition.day_files`, rather than leaving a file unmoved and unmentioned.
    """
    if which is LedgerName.FEED_RETIREMENTS:
        flat = state_dir / f"{which.value}{CSV_SUFFIX}"
        return [flat] if flat.is_file() else []
    return list(day_partition.day_files(state_dir / which.value))


@dataclass(slots=True)
class _Day:
    """One day of one ledger: the rows the CSV held, each beside the cells it was read from."""

    rows: list[Row] = field(default_factory=list)
    cells: list[dict[str, str]] = field(default_factory=list)


def _read(state_dir: Path, path: Path, which: LedgerName) -> dict[str, _Day]:
    """One CSV file's rows, grouped by the day each is filed under, or a refusal naming the line."""
    model, day_cell = LEDGERS[which]
    days: dict[str, _Day] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for number, raw in enumerate(csv.DictReader(handle), start=2):
            try:
                row = model.from_csv_row(raw)
            except (KeyError, ValueError) as error:
                raise NotProvenError(
                    f"{_shown(state_dir, path)}:{number} does not read as a {model.__name__}: "
                    f"{error}"
                ) from error
            held = days.setdefault(str(getattr(row, day_cell)), _Day())
            held.rows.append(row)
            held.cells.append(raw)
    return days


@dataclass(slots=True)
class _Plan:
    """What one ledger's migration will do, decided before anything is written."""

    which: LedgerName
    files: list[Path]
    days: dict[str, _Day]
    expected: dict[str, FileEnvelope]
    already: dict[str, Path]

    @property
    def rows(self) -> int:
        return sum(len(day.rows) for day in self.days.values())


def _identity(run_id: str, git_sha: str) -> WriterIdentity:
    return WriterIdentity(
        run_id=run_id,
        attempt=ATTEMPT,
        job=ServerJob.MIGRATE,
        shard=SHARD,
        producer=PRODUCER,
        git_sha=git_sha,
    )


def _plan(state_dir: Path, which: LedgerName, identity: WriterIdentity) -> _Plan:
    """Read the CSV, work out each day's file in a scratch tree, and find what is already there.

    The scratch write is the door's own answer to what each day's file holds, so
    the comparison below needs no second description of the envelope.
    """
    files = csv_files(state_dir, which)
    days: dict[str, _Day] = {}
    for path in files:
        for covers, read in _read(state_dir, path, which).items():
            held = days.setdefault(covers, _Day())
            held.rows += read.rows
            held.cells += read.cells
    expected: dict[str, FileEnvelope] = {}
    with tempfile.TemporaryDirectory() as scratch:
        for covers, held in sorted(days.items()):
            written = ledger.persist(
                Path(scratch), held.rows, ledger=which, covers=covers, identity=identity
            )
            if len(written) != 1:
                raise NotProvenError(
                    f"{which.value} {covers}: the door wrote {len(written)} files for one day"
                )
            expected[covers] = ledger.read_envelope(written[0])
    on_disk: dict[uuid.UUID, list[ledger.RawFile]] = {}
    for held_file in ledger.list_raw_files(state_dir, which):
        on_disk.setdefault(held_file.envelope.unit_id, []).append(held_file)
    already: dict[str, Path] = {}
    for covers, envelope in sorted(expected.items()):
        found = on_disk.get(envelope.unit_id, [])
        for other in found:
            if other.envelope.content_sha256 != envelope.content_sha256:
                raise DisagreesError(
                    f"{_shown(state_dir, other.path)} is this run's work unit for {which.value} "
                    f"{covers} and holds other rows than the CSV does. Neither is discarded: "
                    "compare the two and remove the one that is wrong"
                )
        if found:
            already[covers] = found[0].path
    return _Plan(which=which, files=files, days=days, expected=expected, already=already)


def _prove(state_dir: Path, path: Path, which: LedgerName, day: _Day) -> None:
    """The file reads back as exactly the CSV's rows: field for field, then cell for cell."""
    model, _ = LEDGERS[which]
    back: Sequence[Row] = ledger.load([path], model=model)
    shown = _shown(state_dir, path)
    if len(back) != len(day.rows):
        raise NotProvenError(
            f"{shown} reads back {len(back)} rows where the CSV held {len(day.rows)}"
        )
    for number, (read, wrote, cells) in enumerate(zip(back, day.rows, day.cells, strict=True)):
        if read != wrote:
            raise NotProvenError(f"{shown} row {number} does not read back as it was written")
        rendered = read.csv_row()
        for column, cell in cells.items():
            if rendered.get(column) != cell:
                raise NotProvenError(
                    f"{shown} row {number} reads back {column}={rendered.get(column)!r} where "
                    f"the CSV held {cell!r}"
                )


@dataclass(frozen=True, slots=True)
class Moved:
    """What one ledger's migration did, in the numbers a reviewer asks for."""

    which: LedgerName
    csv_files: int
    rows: int
    written: int
    already: int


def migrate(
    state_dir: Path, which: Sequence[LedgerName], *, run_id: str, git_sha: str
) -> list[Moved]:
    """Move these ledgers' CSV rows onto the door, prove them, then delete the CSV.

    Raises `DisagreesError` before anything is written, and `NotProvenError`
    after removing whatever this call wrote. Either way no CSV is deleted.
    """
    identity = _identity(run_id, git_sha)
    plans = [_plan(state_dir, name, identity) for name in which]
    wrote: list[Path] = []
    try:
        for plan in plans:
            for covers, held in sorted(plan.days.items()):
                target = plan.already.get(covers)
                if target is None:
                    written = ledger.persist(
                        state_dir, held.rows, ledger=plan.which, covers=covers, identity=identity
                    )
                    wrote += written
                    target = written[0]
                    envelope = ledger.read_envelope(target)
                    wanted = plan.expected[covers]
                    if (envelope.unit_id, envelope.content_sha256) != (
                        wanted.unit_id,
                        wanted.content_sha256,
                    ):
                        raise NotProvenError(
                            f"{_shown(state_dir, target)} is not the file the scratch write made"
                        )
                _prove(state_dir, target, plan.which, held)
    except NotProvenError:
        for path in wrote:
            path.unlink()
            day_partition.drop_empty_day_dirs(path)
        raise
    for plan in plans:
        for path in plan.files:
            path.unlink()
            day_partition.drop_empty_day_dirs(path)
        root = state_dir / plan.which.value
        if root.is_dir() and not any(root.iterdir()):
            root.rmdir()
    return [
        Moved(
            which=plan.which,
            csv_files=len(plan.files),
            rows=plan.rows,
            written=len(plan.days) - len(plan.already),
            already=len(plan.already),
        )
        for plan in plans
    ]


def _pattern(pattern: str, what: str) -> Callable[[str], str]:
    """An argument type that takes only a value matching this pattern."""

    def take(value: str) -> str:
        if re.fullmatch(pattern, value) is None:
            raise argparse.ArgumentTypeError(f"{value!r} is not {what}")
        return value

    return take


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--state-dir", required=True, type=Path, help="The tree to migrate.")
    parser.add_argument(
        "--run-id",
        required=True,
        type=_pattern(RUN_ID_PATTERN, "a run id, <YYYY-MM-DD>-<number>"),
        help="The run every file names. Use the same one on a second run.",
    )
    parser.add_argument(
        "--git-sha",
        required=True,
        type=_pattern(COMMIT_SHA_PATTERN, "the forty hex digits of a commit"),
        help="The commit this checkout is at, which every file names: git rev-parse HEAD.",
    )
    parser.add_argument(
        "--ledger",
        choices=[name.value for name in LEDGERS],
        default=None,
        help="One ledger to migrate. Both when absent.",
    )
    parser.add_argument(
        "--check", action="store_true", help="Write nothing. Exit 1 if any source CSV remains."
    )
    args = parser.parse_args(argv)
    state_dir: Path = args.state_dir
    which = [LedgerName(args.ledger)] if args.ledger else list(LEDGERS)

    if args.check:
        left = [path for name in which for path in csv_files(state_dir, name)]
        for path in left:
            print(f"{_shown(state_dir, path)} is still a CSV")
        print(f"{len(left)} source CSV file(s) left")
        return EXIT_NOT_PROVEN if left else EXIT_MIGRATED

    try:
        moved = migrate(state_dir, which, run_id=args.run_id, git_sha=args.git_sha)
    except DisagreesError as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return EXIT_DISAGREES
    except NotProvenError as refusal:
        print(f"not proven, nothing deleted: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
    for each in moved:
        print(
            f"{each.which.value}: {each.rows} rows from {each.csv_files} CSV file(s); "
            f"{each.written} file(s) written, {each.already} already there; "
            f"{each.csv_files} CSV file(s) deleted"
        )
    return EXIT_MIGRATED


if __name__ == "__main__":
    raise SystemExit(main())
