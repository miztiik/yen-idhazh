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

**The settlement is not here.** `day_shards` owns the three-case fold and the
row reader, because a day directory of writer-owned files settles to the same
answer this writes into a head. One fold, two callers.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import assemble, day_shards, ledger
from idhazh.day_shards import Held, Waiting, parsed, rows_of, settle
from idhazh.ledger import CsvContract, SegmentLedger

LOG: Final = logging.getLogger("idhazh")

#: A row already in the head has no filename, so it has no attempt. Zero is
#: lower than every segment's, which is what lets any segment correct a head and
#: what makes the settlement below total rather than a list of cases.
HEAD_ATTEMPT: Final = day_shards.SETTLED_ATTEMPT

#: The cell that names the head a row belongs to, where the row has one. The
#: score index does not: it is a stamp and a digest, filed beside the rows it
#: describes, and `ledger.segment_dates_from_run` is what says so.
DATE_CELL: Final = "date"


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


@dataclass(frozen=True, slots=True)
class _Folded:
    """What one ledger's fold did, before the pass adds its ledgers together."""

    heads: tuple[str, ...]
    merged: int
    superseded: int
    rows_by_run_date: tuple[tuple[str, int], ...]
    newest_row_date: str | None


def _waiting_rows(
    paths: list[Path], model: type[CsvContract], *, dates_from_run: bool
) -> list[Waiting]:
    """Every row of every segment of one ledger, in the order it is folded.

    Ascending attempt, so a correction always arrives after what it corrects and
    the settlement never has to look backwards. Ties break on the filename and
    then on the row, so two passes over the same files produce the same head.

    The date each row is filed under comes off the row, except for the one
    ledger whose rows carry no date at all - `ledger.segment_dates_from_run`
    says which, and there the segment's own run id supplies it.
    """
    waiting = [
        Waiting(
            path,
            name.attempt,
            lineno,
            cells,
            name.run_id[:10] if dates_from_run else cells[DATE_CELL],
            name.run_id[:10],
        )
        for path, name in ((path, ledger.parse_segment_name(path)) for path in paths)
        for lineno, cells in (
            (lineno, parsed(path, lineno, raw, model)) for lineno, raw in rows_of(path)
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
    grouped: dict[str, tuple[ledger.SegmentHead, list[Waiting]]] = {}
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
        held: dict[tuple[str, ...], Held] = {}
        if head.path.exists():
            # A head that came back from a union merge can carry two header
            # blocks, and a DictReader would read the second one as a row.
            _, complaints = ledger.settle_header(
                head.path, columns, ledger.refiler(head.model), carried=head.carried
            )
            for complaint in complaints:
                LOG.warning("compact: %s", complaint)
            for lineno, raw in rows_of(head.path):
                cells = parsed(head.path, lineno, raw, head.model)
                held[tuple(cells[name] for name in head.key)] = Held(HEAD_ATTEMPT, cells)
        for row in rows:
            merged += 1
            record = tuple(row.cells[name] for name in head.key)
            if record not in held:
                held[record] = Held(row.attempt, dict(row.cells))
            elif settle(held[record], row, head.key, prefers):
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
