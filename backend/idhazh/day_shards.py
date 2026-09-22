"""What does a day directory of writer-owned files read back as?

`state/<ledger>/<YYYY>/<MM>/<DD>/` is where a writer leaves its rows when more
than one job writes one ledger and there is no head file to fold them into. Two
writers never share a filename there - `ledger.segment_path` spells the identity
`<run_id>-<attempt>-<job>-<shard>` - so the directory is the ledger, and the
settlement is something a reader does rather than something a writer leaves
behind.

**The walk reads both shapes.** A `<DD>.csv` day file and a `<DD>/` day
directory are each one recorded day, so a caller that moves here reads exactly
what it read before until something writes a directory. Nothing writes one yet.

**The fold is the compaction's, moved rather than copied.** `settle` runs the
identical three cases `stages.compact` ran into a head - join, supersede, repeat
- and `stages.compact` calls this one now. Six ledgers with six read-side folds
would be six answers to one question, and a reader that forgot to call one would
read double-counted rows.

**`settled.csv` is the one name here that is not a writer's.** It is what a
closed-day fold leaves behind, and it sorts below every writer file: a writer's
attempt is the run's own `GITHUB_RUN_ATTEMPT` and that starts at 1, so attempt 0
is a place no writer can take. It is also the right place - every row in it has
already won its settlement, and a straggler beside it is later.

**The sort key is the path relative to the ledger root, never the bare
filename.** `settled.csv` has the same basename in every day directory, so a
reader spanning two days would have no total order without it - and only two
keys carry a preference rule, so a non-total order here is a silently wrong
answer rather than a flake.

**Nothing inside a day tree is skipped**, for the reason `day_partition` gives:
a name the reader cannot place would sit in a state directory unread and
unmentioned, which is how a reader starts missing rows with nobody noticing. A
day directory holding no readable file is refused on the same ground. A writer
that made the directory and wrote nothing into it is a defect, and an empty
answer would read as a day nothing ran on.

`day_partition.day_files` is not touched and keeps refusing a directory loudly.
It has callers over `state/published/` and `state/visual-prunes/`, which are not
moving, and its refusal is the tripwire that catches a twelfth tree arriving
without a plan.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path
from typing import Final, NoReturn

from idhazh import day_partition, ledger
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.ledger import CsvContract

#: What a closed-day fold leaves beside the writer files it read.
SETTLED_NAME: Final = "settled.csv"

#: Where `settled.csv` reads in. Lower than every writer file, because a run's
#: `GITHUB_RUN_ATTEMPT` starts at 1 and attempt 0 is a place no writer can take.
SETTLED_ATTEMPT: Final = 0

#: Every shard here is a CSV. Spelled once, used by both shapes of the walk.
SUFFIX: Final = ".csv"

#: The one non-key cell two rows may fill differently without disagreeing. It
#: stamps the shape the row was written under, so two generations of one record
#: differ here by construction and a rule that read it would call every pair
#: contested and let nothing ever join.
VERSION_CELL: Final = "version"


@dataclass(slots=True)
class Held:
    """One record on its way to an answer, and the highest attempt that wrote it."""

    attempt: int
    cells: dict[str, str]


@dataclass(frozen=True, slots=True)
class Waiting:
    """One shard row, read, with enough provenance to name it in a refusal.

    `date` and `run_date` belong to a caller that routes rows into heads.
    `stages.compact` fills both; a read-time settlement routes nothing and
    leaves them empty, and `settle` reads neither.
    """

    path: Path
    attempt: int
    lineno: int
    cells: dict[str, str]
    date: str = ""
    run_date: str = field(default="")


def _refuse_stray(entry: Path, root: Path) -> NoReturn:
    """Nothing inside a day tree may be ignored, so an odd name stops the read."""
    raise ValueError(
        f"{root.parent.name}/{root.name} holds "
        f"{entry.relative_to(root).as_posix()}, which is neither a YYYY/MM/DD day "
        "file nor a writer's file inside a YYYY/MM/DD day directory. A file the "
        "reader cannot place is how it starts missing rows, so it refuses the "
        "read rather than skipping the file."
    )


def _is_day(year: str, month: str, day: str) -> bool:
    """Whether three path segments spell a real calendar date."""
    if not (
        day_partition.is_segment(year, day_partition.YEAR_WIDTH)
        and day_partition.is_segment(month, day_partition.SEGMENT_WIDTH)
        and day_partition.is_segment(day, day_partition.SEGMENT_WIDTH)
    ):
        return False
    try:
        date_type.fromisoformat(f"{year}-{month}-{day}")
    except ValueError:
        return False
    return True


def _one_day(entry: Path, root: Path, year: str, month: str) -> list[Path]:
    """Every shard of one recorded day, whichever of the two shapes it is in.

    A day file is one shard. A day directory is every `.csv` inside it, in name
    order, and a directory holding none of them is refused rather than read as a
    day that recorded nothing.
    """
    if entry.is_file():
        if entry.suffix != SUFFIX or not _is_day(year, month, entry.stem):
            _refuse_stray(entry, root)
        return [entry]
    if not (entry.is_dir() and _is_day(year, month, entry.name)):
        _refuse_stray(entry, root)
    shards = []
    for candidate in sorted(entry.iterdir()):
        if not (candidate.is_file() and candidate.suffix == SUFFIX):
            _refuse_stray(candidate, root)
        shards.append(candidate)
    if not shards:
        _refuse_stray(entry, root)
    return shards


def shard_files(root: Path, *, days: int) -> Iterator[Path]:
    """Every shard of the newest `days` recorded days of one ledger, oldest first.

    `days` has no default, so every caller states its own cover where a reader
    can see it (Guardrail #12, `docs/concepts/growing-reads.md`). Pass
    `UNBOUNDED_WINDOW` for a pass that has to read the whole store, and say
    beside the call why.

    The newest `days` RECORDED days, not the newest `days` calendar days. A day
    nothing ran on has no entry, so counting entries never starves a caller of a
    day it should have read.

    Walked rather than globbed, so every entry is accounted for and the ones this
    cannot place are refused rather than passed over. A missing directory yields
    nothing, because a clone with no history is what a fresh checkout has and not
    a fault.
    """
    if not root.is_dir():
        return
    recorded: list[list[Path]] = []
    for year in sorted(root.iterdir()):
        if not (year.is_dir() and day_partition.is_segment(year.name, day_partition.YEAR_WIDTH)):
            _refuse_stray(year, root)
        for month in sorted(year.iterdir()):
            if not (
                month.is_dir()
                and day_partition.is_segment(month.name, day_partition.SEGMENT_WIDTH)
            ):
                _refuse_stray(month, root)
            for entry in sorted(month.iterdir()):
                recorded.append(_one_day(entry, root, year.name, month.name))
    kept = recorded if days == UNBOUNDED_WINDOW else recorded[max(0, len(recorded) - days) :]
    for shards in kept:
        yield from shards


def _is_day_file(shard: Path) -> bool:
    """Whether a shard is a `<DD>.csv` day file rather than a writer's file.

    Read off the path and never the name: the grandparent of a day file is its
    year and four digits wide, and the grandparent of a writer's file is its
    month and two.
    """
    return day_partition.is_segment(shard.parent.parent.name, day_partition.YEAR_WIDTH)


def date_of(shard: Path) -> str:
    """The `<YYYY-MM-DD>` a shard is filed under, read off its own path.

    The peer of `day_partition.date_of`, and it answers for both shapes.
    Nothing here opens the file.
    """
    if _is_day_file(shard):
        return f"{shard.parent.parent.name}-{shard.parent.name}-{shard.stem}"
    day = shard.parent
    return f"{day.parent.parent.name}-{day.parent.name}-{day.name}"


def _order(shard: Path, root: Path) -> tuple[int, str]:
    """Reading order inside one ledger: ascending attempt, then relative path.

    Ascending attempt, so a correction always arrives after what it corrects and
    the settlement never has to look backwards. `settled.csv` takes attempt 0,
    which is the place no writer can take and the place its rows belong.

    A `<DD>.csv` day file carries no identity either, so it takes the same
    place: its rows are a fold somebody already settled. `parse_segment_name` is
    what reads every other name, and it is not touched - it keeps raising on a
    name that is neither a writer's nor one of these two.
    """
    where = shard.relative_to(root).as_posix()
    if shard.name == SETTLED_NAME or _is_day_file(shard):
        return (SETTLED_ATTEMPT, where)
    return (ledger.parse_segment_name(shard).attempt, where)


def rows_of(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """Every row of a ledger file with the line number a person would count to.

    Row 1 is the header, so the first record is row 2 - which is what an editor
    shows and what a refusal has to name to be worth reading.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from enumerate(csv.DictReader(handle), start=2)


def parsed(
    path: Path,
    lineno: int,
    raw: dict[str, str],
    model: type[CsvContract],
) -> dict[str, str]:
    """One row read through its contract, or a refusal naming the row.

    This is the one place a ledger read does not degrade, and it is deliberate.
    A shard is written by our own code from a validated model one step earlier,
    so a row that will not parse means the writer and the reader disagree about
    the shape - and folding past that is how a ledger quietly loses a column.
    """
    try:
        return model.from_csv_row(raw).csv_row()
    except Exception as error:
        raise ValueError(
            f"{path.name} row {lineno} does not read as a {model.__name__}: {error}. "
            "A segment holds the head's own rows, so a row the head's contract "
            "cannot place means the writer and this reader disagree."
        ) from error


def contested(kept: dict[str, str], arriving: dict[str, str], key: tuple[str, ...]) -> bool:
    """Whether the two rows both fill a cell that is neither key nor version.

    Key cells are equal by construction - that is what made these two the same
    record - so a test that read them would find every pair in disagreement and
    let nothing ever join.
    """
    return any(
        value and kept.get(name)
        for name, value in arriving.items()
        if name not in key and name != VERSION_CELL
    )


def settle(
    held: Held,
    arriving: Waiting,
    key: tuple[str, ...],
    prefers: ledger.Preference | None,
) -> bool:
    """Fold an arriving row into the record already held. Says whether it lost.

    Three cases and exactly three.

    **Join** - nothing is filled in both, so the two rows describe different
    halves of one record and the answer is the union. Every ledger writing
    shards today has at least one required non-key cell, so this branch is what
    a ledger reaches when its non-key cells are all optional rather than one any
    of them reaches now.

    **Supersede** - something is filled in both and the attempts differ. The
    higher attempt wins each contested cell, because attempt 2 exists precisely
    because attempt 1 did not finish. A cell only the lower attempt filled is
    kept: a longer-lived first attempt can have recorded something the second
    never reached.

    **Repeat** - something is filled in both at the same attempt. The incumbent
    keeps every cell it filled and the arriving row keeps every cell the
    incumbent left empty, unless the key declares a preference. That per-cell
    answer is what lets two steps of one job write one record, and it is what
    makes a second settlement free.
    """
    if not contested(held.cells, arriving.cells, key):
        held.attempt = max(held.attempt, arriving.attempt)
        for name, value in arriving.cells.items():
            if value and not held.cells.get(name):
                held.cells[name] = value
        return False
    if arriving.attempt == held.attempt:
        arriving_wins = prefers is not None and prefers(arriving.cells, held.cells)
    else:
        arriving_wins = arriving.attempt > held.attempt
    winner, loser = (arriving.cells, held.cells) if arriving_wins else (held.cells, arriving.cells)
    merged = dict(loser)
    merged.update({name: value for name, value in winner.items() if value})
    held.attempt = max(held.attempt, arriving.attempt)
    held.cells = merged
    return True


def one_day(root: Path, date: str) -> list[Path]:
    """Every shard of one named day, in reading order. Nothing else is opened.

    The peer of `shard_files` for a caller that already knows which day it is
    asking about. It costs one directory listing whatever the ledger has
    accumulated, so it needs no cover to declare (Guardrail #12).

    A day nothing recorded has no entry and yields nothing, which is not a
    fault: a run that planned nothing that day wrote nothing that day.
    """
    month = root / date[:4] / date[5:7]
    if not month.is_dir():
        return []
    entry = month / date[8:10]
    if entry.is_dir():
        return _one_day(entry, root, date[:4], date[5:7])
    day_file = month / f"{date[8:10]}{SUFFIX}"
    return [day_file] if day_file.is_file() else []


def settled_day(
    root: Path,
    date: str,
    key: tuple[str, ...],
    model: type[CsvContract],
) -> list[dict[str, str]]:
    """One row per record one named day holds, settled, first seen first.

    `settled_rows` for a caller that names its day instead of a cover. Same
    settlement, same order, one directory listing.
    """
    return _settled(root, one_day(root, date), key, model)


def _settled(
    root: Path,
    shards: Iterable[Path],
    key: tuple[str, ...],
    model: type[CsvContract],
) -> list[dict[str, str]]:
    """The settlement itself, over shards somebody else chose."""
    arriving: list[tuple[tuple[int, str], int, Waiting]] = []
    for shard in shards:
        attempt, where = _order(shard, root)
        for lineno, raw in rows_of(shard):
            cells = parsed(shard, lineno, raw, model)
            arriving.append(((attempt, where), lineno, Waiting(shard, attempt, lineno, cells)))
    arriving.sort(key=lambda entry: (entry[0], entry[1]))
    prefers = ledger.preference_for(key)
    held: dict[tuple[str, ...], Held] = {}
    for _, _, row in arriving:
        record = tuple(row.cells[name] for name in key)
        if record not in held:
            held[record] = Held(row.attempt, dict(row.cells))
        else:
            settle(held[record], row, key, prefers)
    return [entry.cells for entry in held.values()]


def settled_rows(
    root: Path,
    key: tuple[str, ...],
    model: type[CsvContract],
    *,
    days: int,
) -> list[dict[str, str]]:
    """One row per record the ledger holds, settled, in the order they were first seen.

    The same answer a fold writes into `settled.csv`, taken at read time
    instead. A caller gets rows it can hand straight to `ledger.render_file` or
    to a contract, with no repeat and no half-written record.

    `days` has no default for the reason `shard_files` gives.
    """
    return _settled(root, shard_files(root, days=days), key, model)
