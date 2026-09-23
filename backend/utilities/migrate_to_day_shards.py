"""Move one committed ledger to a finer grain, and refuse a tree it cannot read back.

One utility for every ledger that changes grain, driven by the row that moves
it: `--directory` names the store, `--shape` names the move and `--date-column`
names the cell that says which day a row belongs to. Four copies of a split
would be four places for the read-back to stop being exact, and the read-back is
the only thing standing between a grain change and a silent delete (CLAUDE.md
Guardrail #5).

Four shapes, because a store arrives at the day directory from four places.
`month-to-day` splits `<YYYY-MM>.csv` into `<YYYY>/<MM>/<DD>.csv`.
`day-to-directory` turns each of those day files into a `<DD>/` directory
holding one `before-partition.csv`, which is the name a committed head takes
because it is many runs already merged and carries no writer identity to stamp.
`flat-to-day-directory` does both at once for a ledger that was one file for the
whole archive. `traces` splits a day prefix off a trace filename into a day
directory and leaves the rest of the name alone, because a trace line carries no
job and no attempt and those two elements cannot be invented.

**It refuses to write a tree it cannot read back.** The whole day tree is built
in a temporary directory beside the store, walked by `day_partition.day_files` -
the pipeline's own reader, not a second opinion - and compared row for row
against what came out of the month shards. Only then are the year directories
renamed into place and the month shards unlinked. A migration that writes an
empty tree and unlinks its source is a delete with exit 0.

**A row it cannot place stops the run before a byte is written.** An empty date
cell and a date cell that is not a date are what a real ledger eventually holds
- a run interrupted mid-append, a header migration half applied - and neither is
a row to skip: a skipped row is a measurement that stops having happened.

**Rows are copied, never rewritten.** The raw line goes across unchanged, cells,
order and bytes, so the `version` cell travels with the row it was written for
and a reader cannot tell which file a row came from. That is also what makes the
read-back exact: the comparison is over raw lines rather than over a parse that
could normalise a difference away.

**A directory holding a month shard and anything else is refused.** Not
tidiness: `day_files` refuses a name it cannot place, so a month shard sitting
beside a year directory stops every read of that store. A half-migrated
directory is therefore already unreadable by the pipeline, and the repair is
`git checkout` on the store rather than a second pass over it - a second pass
cannot know which rows the first one had already moved.

**Which cell names a day, and why `state/seen/` files by `first_seen_run`.** The
day is the first ten characters, and the cell is either exactly those ten or
continues with `-`. A run id is `<date>-<n>`, so filing by `first_seen_run`
reproduces `ledger.append_seen`'s own filing exactly. A wall-clock stamp is
`<date>T<time>Z`, and the `T` is refused here - `first_seen_at` crosses midnight
independently of the run the row belongs to, so a tree filed by it would
disagree with the writer that built it.

**Run it when no scheduled digest is in flight.** A migration moves every line of
every file it touches, so a run that appends while this is in review leaves the
trunk and the migrated tree disagreeing about every row of a shard rather than
about one appended line. Restore from the trunk and run this again.

This reads one whole ledger, which is the growing cost Guardrail #12 is about.
It is allowed here on the narrow ground the other one-shot utilities stand on:
an operator runs it once per store, it is never a step of any run, and every row
of the store is what it has to move.

Usage, from the root of a checkout:

    python backend/utilities/migrate_to_day_shards.py \
        --shape month-to-day --directory state/span-rollup --date-column date
    python backend/utilities/migrate_to_day_shards.py \
        --shape day-to-directory --directory state/item-health
    python backend/utilities/migrate_to_day_shards.py \
        --shape flat-to-day-directory --directory state/day-validations \
        --date-column date
    python backend/utilities/migrate_to_day_shards.py \
        --shape traces --directory state/traces

A flat ledger is named by the store it becomes: `--directory state/x` reads
`state/x.csv`, so every path this prints is still relative to one store.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import day_partition, day_shards, month_partition
from idhazh.assemble import write_atomic
from idhazh.day_partition import day_files
from idhazh.ledger import BEFORE_PARTITION_NAME
from idhazh.telemetry.traces import TRACE_SUFFIX, trace_date

#: `YYYY-MM-DD`. A cell is exactly this wide, or this wide and then a `-`.
DAY_WIDTH: Final = 10

#: Every ledger this moves is a CSV. Spelled once, used by both walks.
SUFFIX: Final = ".csv"


def day_of(cell: str) -> str:
    """The day this cell names, or a `ValueError` saying why it names none.

    Every clause refuses something the others let through. The suffix clause
    refuses a wall-clock stamp, whose eleventh character is `T`, and accepts a
    run id, whose eleventh character is `-`. The round-trip refuses `20260907`
    and `2026-W01-1`, which `date.fromisoformat` accepts and which name no
    `<YYYY>/<MM>/<DD>` path. An empty cell reaches the parser and is refused
    there.
    """
    if len(cell) > DAY_WIDTH and cell[DAY_WIDTH] != "-":
        raise ValueError(f"is dated {cell!r}, which is a stamp rather than a day")
    day = cell[:DAY_WIDTH]
    try:
        parsed = date_type.fromisoformat(day)
    except ValueError as error:
        raise ValueError(f"is dated {cell!r}, which names no day file") from error
    if parsed.isoformat() != day:
        raise ValueError(f"is dated {cell!r}, which names no day file")
    return day


def day_path(root: Path, day: str) -> Path:
    """The day file a row dated `day` belongs in, under `root`."""
    return root / day[:4] / day[5:7] / f"{day[8:10]}{SUFFIX}"


def day_relpath(day: str) -> str:
    """`<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a report line."""
    return f"{day[:4]}/{day[5:7]}/{day[8:10]}{SUFFIX}"


def day_dir_relpath(day: str) -> str:
    """`<YYYY>/<MM>/<DD>` - the day directory a partitioned store files under."""
    return f"{day[:4]}/{day[5:7]}/{day[8:10]}"


def _text(path: Path) -> str:
    """The file's bytes as text, with the line endings it really holds.

    Rows are copied verbatim, so nothing here may translate a newline on the way
    in - a reader that did would make a carriage return invisible to the check
    in `read_shards` that refuses one.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _cells(line: str, width: int, where: str) -> tuple[str, ...]:
    rows = list(csv.reader([line]))
    if len(rows) != 1 or len(rows[0]) != width:
        raise ValueError(f"{where} does not carry {width} cells")
    return tuple(rows[0])


@dataclass(frozen=True, slots=True)
class Shards:
    """What the month shards hold, read before a single byte is written."""

    #: The header line every shard carries, empty when there is no shard.
    header: str
    #: `<YYYY-MM>.csv` -> its exact bytes as text, so a failed install restores.
    texts: dict[str, str]
    #: Day -> the raw data lines that belong to it, in the order they were read.
    lines: dict[str, list[str]]

    @property
    def rows(self) -> Counter[str]:
        """Every data line that went in, counted - the read-back's other side."""
        return Counter(line for day in self.lines for line in self.lines[day])

    @property
    def rows_in(self) -> int:
        return sum(len(lines) for lines in self.lines.values())


def _refuse_mixed(directory: Path, shards: list[Path]) -> None:
    """A store holding a month shard may hold nothing else.

    `day_files` refuses a month shard at the root of a day tree, so a directory
    holding both grains is already unreadable. Refusing here rather than on the
    read-back is what keeps the failure free of a half-written tree.
    """
    known = set(shards)
    strays = [path.name for path in sorted(directory.iterdir()) if path not in known]
    if strays:
        raise ValueError(
            f"holds {len(shards)} month shards and {', '.join(strays)} beside them, "
            "which is a layout no reader can walk. Restore the directory from the "
            "trunk and run this once on the month shards alone"
        )


def read_shards(directory: Path, date_column: str) -> Shards:
    """Every month shard, grouped by the day each row's own cell names.

    A row nobody can place stops the whole read rather than being skipped, and
    nothing is written until this returns.
    """
    paths = month_partition.month_files(directory, SUFFIX)
    if not paths:
        return Shards(header="", texts={}, lines={})
    _refuse_mixed(directory, paths)

    header = ""
    index = -1
    width = 0
    texts: dict[str, str] = {}
    lines: dict[str, list[str]] = {}
    for path in paths:
        text = _text(path)
        if "\r" in text:
            raise ValueError(f"{path.name} holds a carriage return, and rows are copied verbatim")
        parts = text.split("\n")
        if parts == [""] or parts[-1] != "":
            raise ValueError(f"{path.name} is empty or does not end with a newline")
        shard_header, *rows = parts[:-1]
        if not header:
            header = shard_header
            parsed = list(csv.reader([header]))
            if len(parsed) != 1 or not parsed[0]:
                raise ValueError(f"{path.name} line 1 is not a header this can read")
            columns = tuple(parsed[0])
            if date_column not in columns:
                raise ValueError(
                    f"{path.name} carries no {date_column!r} column. "
                    f"Its columns are {', '.join(columns)}"
                )
            index = columns.index(date_column)
            width = len(columns)
        elif shard_header != header:
            raise ValueError(
                f"{path.name} carries a different header from {paths[0].name}, so a "
                "header migration is half applied and no one header fits both"
            )
        texts[path.name] = text
        for number, line in enumerate(rows, start=2):
            where = f"{path.name} line {number}"
            cells = _cells(line, width, where)
            try:
                day = day_of(cells[index])
            except ValueError as error:
                raise ValueError(f"{where} {error}") from error
            lines.setdefault(day, []).append(line)
    return Shards(header=header, texts=texts, lines=lines)


def _stage(root: Path, shards: Shards) -> None:
    """Write the whole day tree under `root`, one atomic file a day."""
    head = shards.header + "\n"
    for day in sorted(shards.lines):
        body = "".join(f"{line}\n" for line in shards.lines[day])
        write_atomic(day_path(root, day), head + body)


def _read_day_tree(root: Path, header: str) -> Counter[str]:
    """Every data line the pipeline's own day walk finds under `root`, counted."""
    found: Counter[str] = Counter()
    for path in day_files(root):
        parts = _text(path).split("\n")
        if parts[:1] != [header] or parts[-1] != "":
            raise ValueError(
                f"{path.relative_to(root).as_posix()} does not carry the header the "
                "month shards carried"
            )
        found.update(parts[1:-1])
    return found


def _refuse_unequal[T](found: Counter[T], expected: Counter[T], where: str) -> None:
    """The read-back. A row short or a row over stops the run before an unlink."""
    if found == expected:
        return
    missing = sum((expected - found).values())
    extra = sum((found - expected).values())
    raise ValueError(
        f"{where} holds {extra} rows the month shards did not and is missing "
        f"{missing} the month shards held, so no month shard was removed"
    )


def _install(staged: Path, directory: Path) -> list[str]:
    """Rename each staged year directory into the store, and say which moved."""
    installed: list[str] = []
    for year in sorted(staged.iterdir()):
        year.replace(directory / year.name)
        installed.append(year.name)
    return installed


def _restore(directory: Path, shards: Shards, installed: list[str]) -> None:
    """Put the store back exactly as it was read."""
    for name in installed:
        shutil.rmtree(directory / name, ignore_errors=True)
    for name, text in shards.texts.items():
        write_atomic(directory / name, text)


@dataclass(frozen=True, slots=True)
class Report:
    """What the migration did, for the person who has to believe it.

    Every path here is POSIX and relative to the store (CLAUDE.md section 2).
    """

    rows_in: int
    #: Counted off the installed day tree, so it is a second reading rather than
    #: `rows_in` printed twice.
    rows_out: int
    #: The `<YYYY-MM>.csv` names that were removed, oldest first.
    shards: list[str]
    #: The `<YYYY>/<MM>/<DD>.csv` names that were written, oldest first.
    paths: list[str]

    @property
    def days(self) -> int:
        return len(self.paths)


def run(directory: Path, date_column: str) -> Report:
    """Move the rows, read the tree back, and only then unlink a month shard.

    A store with no month shard has nothing to move and is told so, which is
    what makes a second run over a migrated tree change no byte.
    """
    shards = read_shards(directory, date_column)
    if not shards.texts:
        return Report(rows_in=0, rows_out=0, shards=[], paths=[])

    expected = shards.rows
    installed: list[str] = []
    found: Counter[str] = Counter()
    staged = Path(tempfile.mkdtemp(prefix=f".{directory.name}-day-shards-", dir=directory.parent))
    try:
        _stage(staged, shards)
        _refuse_unequal(_read_day_tree(staged, shards.header), expected, "the staged day tree")
        try:
            installed = _install(staged, directory)
            for name in shards.texts:
                (directory / name).unlink()
            found = _read_day_tree(directory, shards.header)
            _refuse_unequal(found, expected, "the day tree")
        except BaseException:
            _restore(directory, shards, installed)
            raise
    finally:
        shutil.rmtree(staged, ignore_errors=True)

    return Report(
        rows_in=shards.rows_in,
        rows_out=sum(found.values()),
        shards=sorted(shards.texts),
        paths=[day_relpath(day) for day in sorted(shards.lines)],
    )


def _nothing_moved() -> Report:
    """What a store already in the new shape reports, and it names no path."""
    return Report(rows_in=0, rows_out=0, shards=[], paths=[])


def _scratch(directory: Path, what: str) -> Path:
    """A working directory beside the store, so every rename stays on one volume."""
    return Path(tempfile.mkdtemp(prefix=f".{directory.name}-{what}-", dir=directory.parent))


def _years(directory: Path) -> list[Path]:
    """The `<YYYY>` directories of a store, oldest first.

    Only the year directories, so a store's own root-level file - `state/traces`
    keeps a `.gitkeep` - is neither staged nor parked and cannot be lost.
    """
    return [entry for entry in sorted(directory.iterdir()) if entry.is_dir()]


def _is_day_segment(year: str, month: str, day: str) -> bool:
    """Whether three path segments spell a real calendar date."""
    widths = (day_partition.YEAR_WIDTH, day_partition.SEGMENT_WIDTH, day_partition.SEGMENT_WIDTH)
    if not all(
        day_partition.is_segment(name, width)
        for name, width in zip((year, month, day), widths, strict=True)
    ):
        return False
    try:
        date_type.fromisoformat(f"{year}-{month}-{day}")
    except ValueError:
        return False
    return True


def _swap(directory: Path, staged: Path, parked: Path, check: Callable[[], None]) -> None:
    """Park the store's years, install the staged ones, and put them back on any fault.

    A rename rather than a copy, so the original tree is intact until the last
    moment and a rollback is the same operation backwards. `check` is called
    once the new tree is in place and raises if it does not read back.
    """
    installed: list[str] = []
    moved: list[str] = []
    try:
        for year in _years(directory):
            year.replace(parked / year.name)
            moved.append(year.name)
        for year in sorted(staged.iterdir()):
            year.replace(directory / year.name)
            installed.append(year.name)
        check()
    except BaseException:
        for name in installed:
            shutil.rmtree(directory / name, ignore_errors=True)
        for name in moved:
            (parked / name).replace(directory / name)
        raise


def _recorded_shards(root: Path) -> list[Path]:
    """Every file of every recorded day, in whichever of the two shapes holds it.

    This is the one module that has to see both, because it is what turns one
    into the other: the count before the move is taken over `<DD>.csv` day files
    and the count after it over `<DD>/` day directories. Every pipeline reader
    dropped the day-file branch once the last committed store had moved, so the
    walk cannot be borrowed from `day_shards` any more.

    A day directory is read through `day_shards.one_day`, so a stray inside one
    refuses here exactly as it does at every pipeline read. A name at the day
    level that is neither a day file nor a day directory refuses too: a stray
    carried through the move would land in a directory named after it.
    """
    found: list[Path] = []
    for year in _years(root):
        for month in sorted(year.iterdir()):
            for entry in sorted(month.iterdir()):
                if not day_partition.is_segment(entry.stem, day_partition.SEGMENT_WIDTH):
                    raise ValueError(
                        f"{root.name} holds {entry.relative_to(root).as_posix()}, which is "
                        "neither a <DD>.csv day file nor a <DD>/ day directory"
                    )
                if entry.is_dir():
                    found.extend(
                        day_shards.one_day(root, f"{year.name}-{month.name}-{entry.name}")
                    )
                else:
                    found.append(entry)
    return found


def _recorded_date(root: Path, shard: Path) -> str:
    """The `<YYYY-MM-DD>` a shard is filed under, whichever shape it is in.

    Three path segments is a day file and four is a writer's file inside a day
    directory, and the first two name the year and the month either way.
    """
    parts = shard.relative_to(root).parts
    return f"{parts[0]}-{parts[1]}-{parts[2][:2]}"


def _rows_by_day(root: Path) -> Counter[tuple[str, str]]:
    """Every data line of the store, keyed by the day it is filed under.

    Keyed rather than pooled, because a partition that filed every row under one
    day would pass a check over the lines alone.
    """
    found: Counter[tuple[str, str]] = Counter()
    for shard in _recorded_shards(root):
        where = shard.relative_to(root).as_posix()
        parts = _text(shard).split("\n")
        if parts == [""] or parts[-1] != "":
            raise ValueError(f"{where} is empty or does not end with a newline")
        recorded = _recorded_date(root, shard)
        found.update((recorded, line) for line in parts[1:-1])
    return found


def _day_file_paths(root: Path) -> list[Path]:
    """The `<YYYY>/<MM>/<DD>.csv` day files of a store, oldest first.

    Three path segments is a day file and four is a writer's file inside a day
    directory, which is the rule `telemetry.trace_date` reads a trace by. Taken
    off `_recorded_shards`, so a name no reader can place stops this here.
    """
    return [
        shard
        for shard in _recorded_shards(root)
        if len(shard.relative_to(root).parts) == 3
    ]


def _open_the_day_files(staged: Path) -> list[str]:
    """Turn every day file under `staged` into a day directory. Bytes are copied."""
    written: list[str] = []
    for day_file in _day_file_paths(staged):
        target = day_file.with_suffix("") / BEFORE_PARTITION_NAME
        text = _text(day_file)
        day_file.unlink()
        write_atomic(target, text)
        written.append(target.relative_to(staged).as_posix())
    return sorted(written)


def partition(directory: Path) -> Report:
    """Every `<DD>.csv` day file becomes `<DD>/before-partition.csv`.

    The bytes go across unchanged and only the path moves, so the `version` cell
    still travels with the row it was written for. A store already holding day
    directories has nothing to move and is told so, which is what makes a second
    run change no byte.
    """
    if not directory.is_dir():
        return _nothing_moved()
    expected = _rows_by_day(directory)
    removed = [path.relative_to(directory).as_posix() for path in _day_file_paths(directory)]
    if not removed:
        return _nothing_moved()

    staged = _scratch(directory, "day-directories")
    parked = _scratch(directory, "parked")
    try:
        for year in _years(directory):
            shutil.copytree(year, staged / year.name)
        written = _open_the_day_files(staged)
        _refuse_unequal(_rows_by_day(staged), expected, "the staged day tree")
        _swap(
            directory,
            staged,
            parked,
            lambda: _refuse_unequal(_rows_by_day(directory), expected, "the day tree"),
        )
    finally:
        shutil.rmtree(staged, ignore_errors=True)
        shutil.rmtree(parked, ignore_errors=True)

    return Report(
        rows_in=sum(expected.values()),
        rows_out=sum(_rows_by_day(directory).values()),
        shards=sorted(removed),
        paths=written,
    )


def _read_flat(path: Path, date_column: str) -> Shards:
    """One flat ledger, grouped by the day each row's own cell names.

    The same read `read_shards` makes of a month shard, over a store that was
    one file for the whole archive. A row nobody can place stops it here, before
    a byte is written.
    """
    text = _text(path)
    if "\r" in text:
        raise ValueError(f"{path.name} holds a carriage return, and rows are copied verbatim")
    parts = text.split("\n")
    if parts == [""] or parts[-1] != "":
        raise ValueError(f"{path.name} is empty or does not end with a newline")
    header, *rows = parts[:-1]
    parsed = list(csv.reader([header]))
    if len(parsed) != 1 or not parsed[0]:
        raise ValueError(f"{path.name} line 1 is not a header this can read")
    columns = tuple(parsed[0])
    if date_column not in columns:
        raise ValueError(
            f"{path.name} carries no {date_column!r} column. Its columns are {', '.join(columns)}"
        )
    index = columns.index(date_column)
    lines: dict[str, list[str]] = {}
    for number, line in enumerate(rows, start=2):
        where = f"{path.name} line {number}"
        cells = _cells(line, len(columns), where)
        try:
            day = day_of(cells[index])
        except ValueError as error:
            raise ValueError(f"{where} {error}") from error
        lines.setdefault(day, []).append(line)
    return Shards(header=header, texts={path.name: text}, lines=lines)


def split_flat(directory: Path, date_column: str) -> Report:
    """`<store>.csv` becomes `<store>/<YYYY>/<MM>/<DD>/before-partition.csv`.

    The flat file is named by the store it becomes, so one `--directory` still
    says where every printed path is relative to. A store that holds both is
    half migrated and is refused: a second pass cannot know which rows the first
    one had already moved, and the repair is a restore from the trunk.
    """
    flat = directory.with_name(f"{directory.name}{SUFFIX}")
    if not flat.is_file():
        return _nothing_moved()
    if directory.exists():
        raise ValueError(
            f"{flat.name} sits beside a {directory.name}/ directory, so a migration is "
            "half applied. Restore both from the trunk and run this once"
        )

    shards = _read_flat(flat, date_column)
    expected = Counter((day, line) for day in shards.lines for line in shards.lines[day])
    head = shards.header + "\n"
    staged = _scratch(directory, "day-directories")
    try:
        for day in sorted(shards.lines):
            body = "".join(f"{line}\n" for line in shards.lines[day])
            write_atomic(staged / day_dir_relpath(day) / BEFORE_PARTITION_NAME, head + body)
        _refuse_unequal(_rows_by_day(staged), expected, "the staged day tree")
        directory.mkdir(parents=True)
        try:
            for year in sorted(staged.iterdir()):
                year.replace(directory / year.name)
            flat.unlink()
            _refuse_unequal(_rows_by_day(directory), expected, "the day tree")
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            write_atomic(flat, shards.texts[flat.name])
            raise
    finally:
        shutil.rmtree(staged, ignore_errors=True)

    return Report(
        rows_in=shards.rows_in,
        rows_out=sum(_rows_by_day(directory).values()),
        shards=[flat.name],
        paths=[
            f"{day_dir_relpath(day)}/{BEFORE_PARTITION_NAME}" for day in sorted(shards.lines)
        ],
    )


def _trace_target(path: Path, root: Path) -> tuple[str, str] | None:
    """The day and the filename a legacy trace becomes, or None if it is not one.

    A legacy trace is `<YYYY>/<MM>/<DD>-<rest>.jsonl` and becomes
    `<YYYY>/<MM>/<DD>/<rest>.jsonl` - the day prefix turns into a directory and
    the rest of the name is left exactly as it was written, because a trace line
    carries no job and no attempt to rebuild a fuller name from.
    """
    rel = path.relative_to(root)
    if len(rel.parts) != 3:
        return None
    year, month, name = rel.parts
    stem, _, rest = name.partition("-")
    if not rest or not _is_day_segment(year, month, stem):
        return None
    return f"{year}-{month}-{stem}", rest


def _traces_now(root: Path) -> Counter[tuple[str, str, str]]:
    """Every committed trace, by the day, name and bytes it will have afterwards.

    The legacy path's day prefix is read off the name and the migrated path's
    off its directories, so the two sides of the read-back are comparable and a
    file that moved to the wrong day or lost a byte fails it.
    """
    found: Counter[tuple[str, str, str]] = Counter()
    for path in sorted(root.rglob(f"*{TRACE_SUFFIX}")):
        legacy = _trace_target(path, root)
        if legacy is not None:
            day, name = legacy
        else:
            recorded = trace_date(path, root)
            if recorded is None:
                raise ValueError(
                    f"{path.relative_to(root).as_posix()} is neither a "
                    "<YYYY>/<MM>/<DD>-<name> trace nor one a reader can place"
                )
            day, name = recorded.isoformat(), path.name
        found[(day, name, hashlib.sha256(path.read_bytes()).hexdigest())] += 1
    return found


def _traces_read_back(root: Path) -> Counter[tuple[str, str, str]]:
    """Every committed trace the pipeline's own reader can place, with its bytes."""
    found: Counter[tuple[str, str, str]] = Counter()
    for path in sorted(root.rglob(f"*{TRACE_SUFFIX}")):
        recorded = trace_date(path, root)
        if recorded is None:
            raise ValueError(
                f"{path.relative_to(root).as_posix()} is not a path the trace reader places"
            )
        found[
            (recorded.isoformat(), path.name, hashlib.sha256(path.read_bytes()).hexdigest())
        ] += 1
    return found


def _trace_lines(root: Path) -> int:
    """Every JSON line the trace tree holds - a trace's rows."""
    return sum(
        len(_text(path).splitlines()) for path in sorted(root.rglob(f"*{TRACE_SUFFIX}"))
    )


def split_traces(directory: Path) -> Report:
    """`<DD>-<name>.jsonl` becomes `<DD>/<name>.jsonl`, and nothing else moves.

    A pure path split: the bytes are copied and the filename keeps every
    character after the day prefix. A tree already in the new shape has nothing
    to move and is told so.
    """
    if not directory.is_dir():
        return _nothing_moved()
    expected = _traces_now(directory)
    legacy = [
        path
        for path in sorted(directory.rglob(f"*{TRACE_SUFFIX}"))
        if _trace_target(path, directory) is not None
    ]
    if not legacy:
        return _nothing_moved()
    rows_in = _trace_lines(directory)

    staged = _scratch(directory, "day-directories")
    parked = _scratch(directory, "parked")
    written: list[str] = []
    try:
        for year in _years(directory):
            shutil.copytree(year, staged / year.name)
        for path in sorted(staged.rglob(f"*{TRACE_SUFFIX}")):
            target = _trace_target(path, staged)
            if target is None:
                continue
            day, name = target
            moved = staged / day[:4] / day[5:7] / day[8:10] / name
            moved.parent.mkdir(parents=True, exist_ok=True)
            path.replace(moved)
            written.append(moved.relative_to(staged).as_posix())
        _refuse_unequal(_traces_read_back(staged), expected, "the staged trace tree")
        _swap(
            directory,
            staged,
            parked,
            lambda: _refuse_unequal(_traces_read_back(directory), expected, "the trace tree"),
        )
    finally:
        shutil.rmtree(staged, ignore_errors=True)
        shutil.rmtree(parked, ignore_errors=True)

    return Report(
        rows_in=rows_in,
        rows_out=_trace_lines(directory),
        shards=sorted(path.relative_to(directory).as_posix() for path in legacy),
        paths=sorted(written),
    )


#: Every move this makes, and the function that makes it. A closed vocabulary,
#: so a shape nobody wrote is refused by the parser rather than guessed at.
SHAPES: Final = ("month-to-day", "day-to-directory", "flat-to-day-directory", "traces")

#: The shapes that need a cell to read a day off. The other two read the day off
#: a path, so demanding a column there would be a flag nobody can answer.
NEEDS_A_DATE_COLUMN: Final = ("month-to-day", "flat-to-day-directory")


def migrate(shape: str, directory: Path, date_column: str) -> Report:
    """Run one shape over one store."""
    if shape == "month-to-day":
        return run(directory, date_column)
    if shape == "day-to-directory":
        return partition(directory)
    if shape == "flat-to-day-directory":
        return split_flat(directory, date_column)
    return split_traces(directory)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move one committed ledger to a finer grain, reading the result back first."
    )
    parser.add_argument(
        "--shape",
        choices=SHAPES,
        default="month-to-day",
        help="which move to make; see the module docstring for what each one writes",
    )
    parser.add_argument(
        "--directory",
        required=True,
        help="the ledger directory to rewrite, relative to the current directory",
    )
    parser.add_argument(
        "--date-column",
        default="",
        help="the column whose cell names the day a row belongs to",
    )
    args = parser.parse_args()

    directory = Path(args.directory)
    if directory.is_absolute():
        raise SystemExit(
            "--directory takes a path relative to the current directory, so that every "
            "path this prints is one too"
        )
    if args.shape in NEEDS_A_DATE_COLUMN and not args.date_column:
        raise SystemExit(f"--shape {args.shape} needs --date-column")
    where = directory.as_posix()
    try:
        report = migrate(args.shape, directory, args.date_column)
    except ValueError as error:
        raise SystemExit(f"{where}: {error}") from error

    if not report.shards:
        print(f"{where}: nothing to migrate")
        return
    print(f"{where}: {report.rows_in} rows in, {report.rows_out} rows out")
    print(f"{where}: {len(report.shards)} removed, {report.days} written")
    for name in report.shards:
        print(f"  - {name}")
    for relpath in report.paths:
        print(f"  + {relpath}")


if __name__ == "__main__":
    main()
