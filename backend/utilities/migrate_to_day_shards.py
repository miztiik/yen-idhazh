"""Rewrite one month-sharded ledger directory into `<YYYY>/<MM>/<DD>.csv`.

One utility for every ledger that changes grain, driven by the row that moves
it: `--directory` names the store and `--date-column` names the cell that says
which day a row belongs to. Four copies of a split would be four places for the
read-back to stop being exact, and the read-back is the only thing standing
between a grain change and a silent delete (CLAUDE.md Guardrail #5).

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

**Run it when no scheduled digest is in flight.** `state/**/*.csv` is
`merge=union` in `.gitattributes`. Union merge keeps every line from both sides,
which is right for an append and wrong for a file whose every line moved - and
it has no conflict state, so a merge over a migrated tree exits 0 and leaves a
directory holding both grains. Restore from the trunk and run this again.

This reads one whole ledger, which is the growing cost Guardrail #12 is about.
It is allowed here on the narrow ground the other one-shot utilities stand on:
an operator runs it once per store, it is never a step of any run, and every row
of the store is what it has to move.

Usage, from the root of a checkout:

    python backend/utilities/migrate_to_day_shards.py \
        --directory state/item-health --date-column date
"""

from __future__ import annotations

import argparse
import csv
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import month_partition
from idhazh.assemble import write_atomic
from idhazh.day_partition import day_files

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


def _refuse_unequal(found: Counter[str], expected: Counter[str], where: str) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rewrite a month-sharded ledger directory into <YYYY>/<MM>/<DD>.csv day files."
    )
    parser.add_argument(
        "--directory",
        required=True,
        help="the ledger directory to rewrite, relative to the current directory",
    )
    parser.add_argument(
        "--date-column",
        required=True,
        help="the column whose cell names the day a row belongs to",
    )
    args = parser.parse_args()

    directory = Path(args.directory)
    if directory.is_absolute():
        raise SystemExit(
            "--directory takes a path relative to the current directory, so that every "
            "path this prints is one too"
        )
    where = directory.as_posix()
    try:
        report = run(directory, args.date_column)
    except ValueError as error:
        raise SystemExit(f"{where}: {error}") from error

    if not report.shards:
        print(f"{where}: no month shard to migrate")
        return
    print(f"{where}: {report.rows_in} rows in, {report.rows_out} rows out")
    print(f"{where}: {len(report.shards)} month shards removed, {report.days} day files written")
    for name in report.shards:
        print(f"  - {name}")
    for relpath in report.paths:
        print(f"  + {relpath}")


if __name__ == "__main__":
    main()
