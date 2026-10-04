"""Which raw files hold one ledger's current rows, and what those rows are.

A raw ledger is many small files under `state/raw/<ledger>/<YYYY>/<MM>/<DD>/`,
one per writer per day, each written once by the door in `ledger/persist.py`.
Two attempts at one work unit leave two files carrying one `unit_id`, and only
the higher attempt is current: GitHub re-runs a failed job into the same run id,
so the re-run replaces its first try rather than adding to it. The door writes
both files and removes neither, and it says that choosing between them is a
reader's job. This module is that job, done once, so no reader invents its own
version of it: `settle_rows` keeps one file's rows per unit - the last file of
its highest attempt - and then the first row per key, and both the ledger's
reader and the compaction call it.

**Oldest first, and the order is written down rather than inherited.** Files
sort by the day they cover, then by the instant they were written, then by
their `file_id`, all read from each file's own envelope. A directory listing
happens to agree today, because a `file_id` starts with its clock; a reader that
leaned on that would change its answer the day the name grammar did.

**A reader names the days it wants, or reads every day a ledger has a folder
for (Guardrail #12).** `ledger/ledger_files.py` reads the days no compact index
names and nothing else, and the compaction reads one day at a time. What an
unbounded read costs grows with the files: one per writer per day that has not
been compacted yet, and a parquet file's envelope is read from its footer
without its rows. `docs/concepts/growing-reads.md` lists the reads.

**A reader skips a file this build cannot read, with one warning that names it;
the compaction stops that day instead.** A file under a newer row shape, a row
today's model refuses, a file that is not a ledger file at all, or one filed in
the wrong folder is a `ValueError`. A reader that stopped on it would cost the
run its day to protect one row. The compaction must never delete a file it
could not read, so `read_day_files` raises rather than skips. Only `ValueError`
is caught. A missing parquet engine raises `ImportError`, and that must stop the
run: skipping every file for it would read as a ledger with no history.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import NamedTuple, cast

from idhazh import day_partition
from idhazh.contracts.base import Contract
from idhazh.contracts.file_envelope import FileEnvelope, Tier
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths
from idhazh.ledger.keys import preference_for
from idhazh.ledger.persist import StoredRow, load_stored, read_envelope

logger = logging.getLogger(__name__)


class RawFile(NamedTuple):
    """One raw file, and the envelope that says what it holds."""

    path: Path
    envelope: FileEnvelope


def _shown(state_dir: Path, path: Path) -> str:
    """A path as it may leave the process: under `state/`, POSIX (CLAUDE.md section 2)."""
    return f"{paths.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}"


def _skip(state_dir: Path, path: Path, reason: object) -> None:
    """Say which file a read left out, and why, in the one line a person will look for."""
    logger.warning("skipped a raw file path=%s reason=%s", _shown(state_dir, path), reason)


def _day_folders(state_dir: Path, root: Path) -> list[tuple[str, Path]]:
    """Every `<YYYY>/<MM>/<DD>` folder under one ledger's raw root, with the day it names.

    The index listings sit beside the years, in `index/`, and are not rows, so
    that one name is passed over in silence. Anything else that is not a day
    folder is named in a warning and left alone.
    """
    if not root.is_dir():
        return []
    found: list[tuple[str, Path]] = []
    for year in sorted(root.iterdir()):
        if year.name == paths.INDEX_DIRNAME and year.is_dir():
            continue
        if not (year.is_dir() and day_partition.is_segment(year.name, day_partition.YEAR_WIDTH)):
            _skip(state_dir, year, "not a YYYY folder")
            continue
        for month in sorted(year.iterdir()):
            if not (
                month.is_dir()
                and day_partition.is_segment(month.name, day_partition.SEGMENT_WIDTH)
            ):
                _skip(state_dir, month, "not an MM folder")
                continue
            for day in sorted(month.iterdir()):
                if not (
                    day.is_dir() and day_partition.is_segment(day.name, day_partition.SEGMENT_WIDTH)
                ):
                    _skip(state_dir, day, "not a DD folder")
                    continue
                found.append((f"{year.name}-{month.name}-{day.name}", day))
    return found


def _order(held: RawFile) -> tuple[str, int, str]:
    """Oldest first: the day covered, then the write instant, then the file's own id."""
    return (held.envelope.covers, held.envelope.written_at_ms, str(held.envelope.file_id))


def raw_days(state_dir: Path, ledger: LedgerName) -> list[str]:
    """Every UTC day this ledger has a raw folder with something in it for, oldest first.

    Folder names only: one entry is read from each day folder to see that it
    is not empty, and no file is opened. A day the compaction has emptied keeps
    no folder on a runner, because git keeps no empty folder, and the
    compaction removes the one it emptied on a developer's machine.
    """
    return [
        day
        for day, folder in _day_folders(state_dir, paths.raw_root(state_dir, ledger))
        if next(folder.iterdir(), None) is not None
    ]


def listed_days(state_dir: Path, ledger: LedgerName) -> list[str]:
    """Every UTC day a raw listing of this ledger sits under `index/` for, oldest first.

    No reader opens a listing in state/, and the compaction no longer writes one.
    An older listing records which raw files a day held before packing. A
    name that is not a `<YYYY-MM-DD>.json` listing is left out with a warning.
    """
    folder = paths.raw_root(state_dir, ledger) / paths.INDEX_DIRNAME
    if not folder.is_dir():
        return []
    found: list[str] = []
    for path in sorted(folder.iterdir()):
        try:
            if path.suffix != ".json" or paths.raw_index_path(state_dir, ledger, path.stem) != path:
                raise ValueError("not a day's listing")
        except ValueError as refusal:
            _skip(state_dir, path, refusal)
            continue
        found.append(path.stem)
    return found


def _held(ledger: LedgerName, covers: str, path: Path) -> RawFile:
    """One raw file and its envelope, or a `ValueError` saying why it is not one of this day's."""
    if not path.is_file():
        raise ValueError("not a file")
    envelope = read_envelope(path)
    if (envelope.ledger, envelope.tier, envelope.covers) != (ledger, Tier.RAW, covers):
        raise ValueError(
            f"its envelope says {envelope.tier.value} {envelope.ledger.value} "
            f"{envelope.covers}, and it sits in the raw {ledger.value} folder for {covers}"
        )
    return RawFile(path, envelope)


def list_raw_files(
    state_dir: Path, ledger: LedgerName, *, days: Collection[str] | None = None
) -> list[RawFile]:
    """Every raw file of this ledger whose envelope this build can read, oldest first.

    `days` bounds the read to the days named; `None` reads every day folder.
    Every file in a day folder is read, whatever its suffix, because
    `ledger.format` may be JSON lines as well as parquet. A file whose envelope
    names another ledger, another tier or another day than the folder it sits in
    was filed by something other than the door, and is skipped as unreadable.
    """
    found: list[RawFile] = []
    for covers, folder in _day_folders(state_dir, paths.raw_root(state_dir, ledger)):
        if days is not None and covers not in days:
            continue
        for path in sorted(folder.iterdir()):
            try:
                found.append(_held(ledger, covers, path))
            except ValueError as refusal:
                _skip(state_dir, path, refusal)
    return sorted(found, key=_order)


def read_day_files(state_dir: Path, ledger: LedgerName, day: str) -> list[RawFile]:
    """One day's raw files, oldest first, or a refusal naming the first one that cannot be read.

    For the compaction, which deletes what it read and so may not skip a file:
    a file it cannot read would be deleted unread. A day with no folder holds
    nothing, which is an empty list.
    """
    folder = paths.raw_root(state_dir, ledger).joinpath(day[:4], day[5:7], day[8:10])
    if not folder.is_dir():
        return []
    found: list[RawFile] = []
    for path in sorted(folder.iterdir()):
        try:
            found.append(_held(ledger, day, path))
        except ValueError as refusal:
            raise ValueError(f"{_shown(state_dir, path)} cannot be read: {refusal}") from refusal
    return sorted(found, key=_order)


def _cells(row: Contract) -> dict[str, str]:
    """A row's cells as a CSV line spells them, which is what a preference rule reads."""
    spelled = getattr(row, "csv_row", None)
    if callable(spelled):
        return cast("dict[str, str]", spelled())
    return {
        name: "" if value is None else str(value)
        for name, value in row.model_dump(mode="json").items()
    }


def _say_what_was_dropped(
    record: tuple[str, ...], kept: Contract, dropped: Contract
) -> None:
    """Name each cell the dropped row filled and the kept row left empty.

    A settlement keeps whole rows, so a cell only the dropped row carried goes
    with it. That is the rule, and saying so is what lets a person see it.
    """
    held, gone = _cells(kept), _cells(dropped)
    for name, value in gone.items():
        if value and not held.get(name):
            logger.warning(
                "a settled row dropped a cell the kept row lacks key=%s cell=%s",
                ",".join(record),
                name,
            )


def settle_rows[C: Contract](
    files: Sequence[Sequence[StoredRow[C]]], key: tuple[str, ...]
) -> list[StoredRow[C]]:
    """The current rows of a union of files, in the order given: one file per unit, then key.

    `files` holds each file's rows, oldest file first. For each work unit the
    rows of one file are kept - the last file holding that unit's highest
    attempt - and every other row of the unit goes. A re-run replaces its first
    try rather than adding to it, even when it filed fewer rows; and one attempt
    that wrote a unit twice is its later write, so a union has one answer on
    every read. A compact file is passed before the raw files of its day: its
    rows were written before any raw file that arrived after it.

    Of the rows left, one whole row of each `key` is kept. Two writers that are
    not attempts at one unit - two runs reading the same evidence from two stale
    checkouts, or a work shard and assemble filing one item - can each file a
    row for one key. The first one filed wins, which is the rule `ledger/keys.py`
    gives a key that declares no preference of its own; a key that declares one
    keeps the later row wherever its preference says so. Either way a row is
    kept or dropped whole, and a cell only the dropped row filled is named in a
    warning.
    """
    prefers = preference_for(key)
    current: dict[str, tuple[int, int]] = {}
    for position, rows in enumerate(files):
        for held in rows:
            rank = (held.identity.attempt, position)
            current[held.identity.unit_id] = max(current.get(held.identity.unit_id, rank), rank)
    kept: dict[tuple[str, ...], StoredRow[C]] = {}
    for position, rows in enumerate(files):
        for held in rows:
            if current[held.identity.unit_id] != (held.identity.attempt, position):
                continue
            record = tuple(str(getattr(held.row, name)) for name in key)
            incumbent = kept.get(record)
            if incumbent is None:
                kept[record] = held
                continue
            later_wins = prefers is not None and prefers(_cells(held.row), _cells(incumbent.row))
            winner, loser = (held, incumbent) if later_wins else (incumbent, held)
            kept[record] = winner
            _say_what_was_dropped(record, winner.row, loser.row)
    return list(kept.values())


def load_current_rows[C: Contract](
    state_dir: Path,
    ledger: LedgerName,
    *,
    model: type[C],
    key: tuple[str, ...],
    days: Collection[str] | None = None,
) -> list[C]:
    """This ledger's current raw rows, oldest first, settled by `settle_rows`.

    `days` bounds the read to the days named, as `list_raw_files` does. Each
    file is read on its own, so one file this build cannot read costs the rows
    in it and never the rows in the files beside it.
    """
    stored: list[list[StoredRow[C]]] = []
    for held in list_raw_files(state_dir, ledger, days=days):
        try:
            stored.append(load_stored([held.path], model=model))
        except ValueError as refusal:
            _skip(state_dir, held.path, refusal)
    return [held.row for held in settle_rows(stored, key)]
