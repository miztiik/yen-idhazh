"""Fold a closed day's writer files into one settled file.

Every day tree under `state/` is written once per writer: a job files its own
rows at `state/<tree>/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` and
nothing else ever opens that path. That is what makes a lost push race cost a
merge rather than the rows, and it is why nothing here touches a day a run is
still writing.

What it costs is files. Twenty work shards and five runs leave a hundred small
files in one day, and a day nobody will write again keeps them for ever. So once
a day is closed - `run.settled_fold_after_days` behind the run's own date - this
reads that day through the same settlement a reader uses, writes the answer as
`settled.csv`, and deletes the writer files it read.

The fold changes no answer. `day_shards.settled_rows` gives one row per record
whether it reads a hundred writer files or one settled file, so a folded day and
an unfolded day read identically. That is what makes the fold safe to skip, safe
to repeat and safe to run on only some of the days.

Nothing here resolves a conflict. A fold that comes back from a merge carrying
two headers is refused and named, because taking either side leaves this job's
deletion of a writer file standing over the other side's rows - git does not
call a deletion a conflict - and those rows would then exist in no file, at exit
zero.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from idhazh import day_partition, day_shards, ledger
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW

LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CompactionReport:
    """What one fold did, in the terms a log line and a caller both need."""

    days_folded: int
    files_replaced: int
    rows_kept: int
    trees_touched: tuple[str, ...]
    oldest_day_folded: str | None
    newest_day_folded: str | None = None


def _open_from(date: str, after_days: int) -> str:
    """The oldest day still open. Every earlier day may be folded.

    Counted back from the run's own date and never from the clock, so a run that
    crosses midnight folds the same days its rows were written against.

    `days_in_window` answers newest first and names both ends, so the oldest day
    it names is the minimum. That is the idiom `retention.prune_seen` and
    `ledger.load_seen` already read a cover with, and reading it any other way
    turns a cover of seven days into a cover of none.
    """
    return min(day_partition.days_in_window(date, after_days))


def _fold_day(
    root: Path, date: str, key: tuple[str, ...], model: type[ledger.CsvContract]
) -> int:
    """Fold one closed day of one tree. Returns how many files it replaced.

    A day already holding nothing but its settled file is left alone, so a
    second fold of a folded day writes nothing and makes no diff - which is what
    lets this run over every closed day on every run.
    """
    shards = day_shards.one_day(root, date)
    if not shards or all(shard.name == day_shards.SETTLED_NAME for shard in shards):
        return 0
    rows = day_shards.settled_day(root, date, key, model)
    day_dir = root / date[:4] / date[5:7] / date[8:10]
    day_dir.mkdir(parents=True, exist_ok=True)
    settled = day_dir / day_shards.SETTLED_NAME
    settled.write_text(ledger.render_file(model.csv_columns(), rows), encoding="utf-8", newline="")
    replaced = 0
    for shard in shards:
        if shard == settled:
            continue
        shard.unlink()
        replaced += 1
    return replaced


def recorded_days(root: Path) -> list[str]:
    """Every day one tree has an entry for, oldest first.

    Read off the paths, so no file is opened. This is the one read here whose
    cost rises with what the repository has accumulated, and it has to: the
    question is which days exist, and a bounded input cannot answer it
    (Guardrail #12, `docs/concepts/growing-reads.md`). What it reads is
    directory names - three levels of them - and never a row.
    """
    if not root.is_dir():
        return []
    days = {
        day_shards.date_of(shard)
        for shard in day_shards.shard_files(root, days=UNBOUNDED_WINDOW)
    }
    return sorted(days)


def stage_compact(state_dir: Path, *, date: str, after_days: int) -> CompactionReport:
    """Fold every closed day of every day tree. Says what it did.

    `date` is the run's own date and `after_days` is how far behind it a day has
    to be before it counts as closed. Both are arguments rather than readings,
    so a bench run and an operator pass fold exactly the days they name.
    """
    folded: set[str] = set()
    trees: list[str] = []
    replaced = 0
    kept = 0
    open_from = _open_from(date, after_days)
    for tree in ledger.SegmentLedger:
        root = state_dir / tree.value
        key = ledger.segment_key(tree)
        model = ledger.segment_contract(tree)
        touched = False
        for day in recorded_days(root):
            if day >= open_from:
                continue
            moved = _fold_day(root, day, key, model)
            if not moved:
                continue
            replaced += moved
            kept += len(day_shards.settled_day(root, day, key, model))
            folded.add(day)
            touched = True
        if touched:
            trees.append(tree.value)
    report = CompactionReport(
        days_folded=len(folded),
        files_replaced=replaced,
        rows_kept=kept,
        trees_touched=tuple(sorted(trees)),
        oldest_day_folded=min(folded) if folded else None,
        newest_day_folded=max(folded) if folded else None,
    )
    LOG.info(
        "compact days=%s files_replaced=%s rows_kept=%s trees=%s oldest=%s open_from=%s",
        report.days_folded,
        report.files_replaced,
        report.rows_kept,
        ",".join(report.trees_touched) or "none",
        report.oldest_day_folded,
        open_from,
    )
    return report
