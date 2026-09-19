"""Fold every waiting segment into its head, then delete the segment.

`state/segments/` is where a writer puts its rows when more than one job writes
one ledger. Two writers never share a filename there, so a lost push race cannot
stack two copies of a row and a re-run is told apart from the attempt it
replaces. This stage is what turns those files back into the one head every
reader opens.

Three properties are the contract, and each one is a test.

**It is safe to run twice.** A segment it folded is gone, so a second pass finds
nothing to do; and a segment folded twice settles against a row already holding
the same key at the same attempt, which keeps what is there.

**It never calls git.** The caller stages what changed, because a stage that
shells out to git is a stage nobody can drive from a fixture.

**It never reads the clock.** The head a row lands in is named by the row's own
date cell, so a segment a run left behind three days ago goes to that day rather
than to today - which is the whole of the recovery path for a day that died.
"""

from __future__ import annotations

import csv
import logging
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import assemble, ledger
from idhazh.ledger import CsvContract, SegmentLedger

LOG: Final = logging.getLogger("idhazh")

#: A row already in the head has no filename, so it has no attempt. Zero is
#: lower than every segment's, which is what lets any segment correct a head and
#: what makes the settlement below total rather than a list of cases.
HEAD_ATTEMPT: Final = 0

#: The cell that names the head a row belongs to, where the row has one. The
#: score index does not: it is a stamp and a digest, filed beside the rows it
#: describes, and `ledger.segment_dates_from_run` is what says so.
DATE_CELL: Final = "date"

#: The one non-key cell two rows may fill differently without disagreeing. It
#: stamps the shape the row was written under, so two generations of one record
#: differ here by construction and a rule that read it would call every pair
#: contested and let nothing ever join.
VERSION_CELL: Final = "version"


@dataclass(frozen=True, slots=True)
class CompactionReport:
    """What one pass folded. A return value, so it has no schema and no file."""

    segments_read: int
    rows_merged: int
    rows_superseded: int
    heads_written: tuple[str, ...]
    oldest_segment_date: str | None
    #: Rows folded, counted against the run date of the segment that carried
    #: them, oldest first. This pass never reads a clock, so a caller asking how
    #: many of these had been waiting brings its own run date to the two methods
    #: below rather than getting an answer measured against today.
    rows_by_run_date: tuple[tuple[str, int], ...] = ()
    #: The newest date a folded row landed under, which is how far the heads
    #: reach now. None when nothing waited.
    newest_row_date: str | None = None

    def lag_days(self, run_date: str) -> int:
        """Whole days between the oldest segment found waiting and this run."""
        if self.oldest_segment_date is None:
            return 0
        waited = date_type.fromisoformat(run_date) - date_type.fromisoformat(
            self.oldest_segment_date
        )
        return max(0, waited.days)

    def rows_waiting_before(self, run_date: str) -> int:
        """Rows folded in from segments an earlier run left behind."""
        return sum(rows for written_on, rows in self.rows_by_run_date if written_on < run_date)


@dataclass(slots=True)
class _Held:
    """One record on its way to a head, and the highest attempt that wrote it."""

    attempt: int
    cells: dict[str, str]


@dataclass(frozen=True, slots=True)
class _Folded:
    """What one ledger's fold did, before the pass adds its ledgers together."""

    heads: tuple[str, ...]
    merged: int
    superseded: int
    rows_by_run_date: tuple[tuple[str, int], ...]
    newest_row_date: str | None


@dataclass(frozen=True, slots=True)
class _Waiting:
    """One segment row, read, with enough provenance to name it in a refusal."""

    path: Path
    attempt: int
    lineno: int
    cells: dict[str, str]
    date: str
    #: The date the run that wrote this segment opened on, off the filename. The
    #: head a row lands in comes from `date` above; this says how long the row
    #: sat before anything folded it.
    run_date: str


def _rows_of(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """Every row of a ledger file with the line number a person would count to.

    Row 1 is the header, so the first record is row 2 - which is what an editor
    shows and what a refusal has to name to be worth reading.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from enumerate(csv.DictReader(handle), start=2)


def _parsed(
    path: Path,
    lineno: int,
    raw: dict[str, str],
    model: type[CsvContract],
) -> dict[str, str]:
    """One row read through its contract, or a refusal naming the row.

    This is the one place the compaction does not degrade, and it is deliberate.
    A segment is written by our own code from a validated model one step earlier,
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


def _contested(kept: dict[str, str], arriving: dict[str, str], key: tuple[str, ...]) -> bool:
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


def _settle(
    held: _Held,
    arriving: _Waiting,
    key: tuple[str, ...],
    prefers: ledger.Preference | None,
) -> bool:
    """Fold an arriving row into the record already held. Says whether it lost.

    Three cases and exactly three.

    **Join** - nothing is filled in both, so the two rows describe different
    halves of one record and the answer is the union. Every ledger writing
    segments today has at least one required non-key cell, so this branch is
    what a ledger reaches when its non-key cells are all optional rather than
    one any of them reaches now.

    **Supersede** - something is filled in both and the attempts differ. The
    higher attempt wins each contested cell, because attempt 2 exists precisely
    because attempt 1 did not finish. A cell only the lower attempt filled is
    kept: a longer-lived first attempt can have recorded something the second
    never reached.

    **Repeat** - something is filled in both at the same attempt. The incumbent
    keeps every cell it filled and the arriving row keeps every cell the
    incumbent left empty, unless the key declares a preference. That per-cell
    answer is what lets two steps of one job write one record, and it is what
    makes a second compaction free.
    """
    if not _contested(held.cells, arriving.cells, key):
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


def _waiting_rows(
    paths: list[Path], model: type[CsvContract], *, dates_from_run: bool
) -> list[_Waiting]:
    """Every row of every segment of one ledger, in the order it is folded.

    Ascending attempt, so a correction always arrives after what it corrects and
    the settlement never has to look backwards. Ties break on the filename and
    then on the row, so two passes over the same files produce the same head.

    The date each row is filed under comes off the row, except for the one
    ledger whose rows carry no date at all - `ledger.segment_dates_from_run`
    says which, and there the segment's own run id supplies it.
    """
    waiting = [
        _Waiting(
            path,
            name.attempt,
            lineno,
            cells,
            name.run_id[:10] if dates_from_run else cells[DATE_CELL],
            name.run_id[:10],
        )
        for path, name in ((path, ledger.parse_segment_name(path)) for path in paths)
        for lineno, cells in (
            (lineno, _parsed(path, lineno, raw, model)) for lineno, raw in _rows_of(path)
        )
    ]
    waiting.sort(key=lambda row: (row.attempt, row.path.name, row.lineno))
    return waiting


def _compact_ledger(
    state_dir: Path, which: SegmentLedger, paths: list[Path]
) -> _Folded:
    """Fold one ledger's segments into every head their own rows name.

    Grouped by the head each row's date names rather than by the date itself,
    because the two stopped being the same thing when the span fold started
    writing segments: a month head takes every date of its month, so grouping by
    date would read and rewrite one file once per day in it and report the same
    path that many times. The routing rule is unchanged - the date comes off the
    row and the head comes off the date.
    """
    grouped: dict[str, tuple[ledger.SegmentHead, list[_Waiting]]] = {}
    rows_waiting = _waiting_rows(
        paths,
        ledger.segment_contract(which),
        dates_from_run=ledger.segment_dates_from_run(which),
    )
    by_run_date: Counter[str] = Counter()
    for row in rows_waiting:
        head = ledger.segment_head(state_dir, which, row.date)
        grouped.setdefault(head.relpath, (head, []))[1].append(row)
        by_run_date[row.run_date] += 1
    written: list[str] = []
    merged = 0
    superseded = 0
    for _, (head, rows) in sorted(grouped.items()):
        columns = head.model.csv_columns()
        prefers = ledger.preference_for(head.key)
        held: dict[tuple[str, ...], _Held] = {}
        if head.path.exists():
            # A head that came back from a union merge can carry two header
            # blocks, and a DictReader would read the second one as a row.
            _, complaints = ledger.settle_header(
                head.path, columns, ledger.refiler(head.model), carried=head.carried
            )
            for complaint in complaints:
                LOG.warning("compact: %s", complaint)
            for lineno, raw in _rows_of(head.path):
                cells = _parsed(head.path, lineno, raw, head.model)
                held[tuple(cells[name] for name in head.key)] = _Held(HEAD_ATTEMPT, cells)
        for row in rows:
            merged += 1
            record = tuple(row.cells[name] for name in head.key)
            if record not in held:
                held[record] = _Held(row.attempt, dict(row.cells))
            elif _settle(held[record], row, head.key, prefers):
                superseded += 1
        assemble.write_atomic(
            head.path, ledger.render_file(columns, [entry.cells for entry in held.values()])
        )
        written.append(head.relpath)
    return _Folded(
        heads=tuple(written),
        merged=merged,
        superseded=superseded,
        rows_by_run_date=tuple(sorted(by_run_date.items())),
        newest_row_date=max((row.date for row in rows_waiting), default=None),
    )


def stage_compact(state_dir: Path) -> CompactionReport:
    """Merge every segment into its head and remove the segment. Safe to run twice."""
    waiting = ledger.segment_files(state_dir)
    if not waiting:
        LOG.info("compact: nothing waiting")
        return CompactionReport(0, 0, 0, (), None)
    by_ledger: dict[SegmentLedger, list[Path]] = {}
    for path in waiting:
        by_ledger.setdefault(SegmentLedger(path.parent.name), []).append(path)
    written: list[str] = []
    merged = 0
    superseded = 0
    by_run_date: Counter[str] = Counter()
    newest_row_date: str | None = None
    for which, paths in sorted(by_ledger.items()):
        folded = _compact_ledger(state_dir, which, paths)
        written.extend(folded.heads)
        merged += folded.merged
        superseded += folded.superseded
        by_run_date.update(dict(folded.rows_by_run_date))
        if folded.newest_row_date is not None:
            newest_row_date = max(newest_row_date or "", folded.newest_row_date)
    # Last, and never per head: one segment's rows can land in two heads, and a
    # pass that died between them leaves the file in place to be folded again.
    for path in waiting:
        path.unlink()
    report = CompactionReport(
        segments_read=len(waiting),
        rows_merged=merged,
        rows_superseded=superseded,
        heads_written=tuple(sorted(written)),
        oldest_segment_date=min(ledger.parse_segment_name(path).run_id[:10] for path in waiting),
        rows_by_run_date=tuple(sorted(by_run_date.items())),
        newest_row_date=newest_row_date,
    )
    LOG.info(
        "compact: %d segment(s), %d row(s) merged, %d superseded, %d head(s) written, "
        "oldest written on %s",
        report.segments_read,
        report.rows_merged,
        report.rows_superseded,
        len(report.heads_written),
        report.oldest_segment_date,
    )
    return report
