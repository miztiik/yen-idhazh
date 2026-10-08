"""How a caller puts rows into a ledger and gets them back out.

One verb per ledger. Each takes the state directory and the period its rows
describe, never a file name, and each takes contracts rather than dicts - so no
cell reaches a committed file without a model having read it.

Every writer here that records new rows asks `lifecycle.accepts_new_rows` first,
and writes nothing into a paused or retired family; `append_seen` and
`append_published` ask through `persist`, which asks for every pipeline write.
`write_item_health_summary` does not ask: it folds rows already recorded, and the
ageing step reads that fold back before it deletes anything.

Nine readers here read a ledger that lives under `state/raw/` and
`state/compact/` rather than in a CSV tree - `load_seen`, `load_published`,
`load_health`, `load_retirements`, `load_visual_prunes`, the two item-health
readers `load_settled_failures` and `load_source_counts`, and the judge's
`load_story_similarity_pairs` and `load_fitted_thresholds` - and all nine read it
through `ledger/ledger_files.py`, which reads the yearly files, then the monthly
files, then the daily files, then the raw days no compact index names, each date
from exactly one of them. Two of their writers are here, `append_seen` and
`append_published`, and both file through `persist`; every other producer hands
its rows to `persist` itself.
"""

from __future__ import annotations

import csv
from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Final

from idhazh import day_partition
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome
from idhazh.contracts.item_health_summary import ItemHealthSummaryRow
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.ledger import ledger_files, lifecycle, paths
from idhazh.ledger.csv_file import (
    _read_rows,
    extend_ledger_file,
)
from idhazh.ledger.keys import STORY_SIMILARITY_THRESHOLD_KEY
from idhazh.ledger.persist import persist
from idhazh.ledger.settle import drop_repeated_rows

#: How far back a health read looks, in days the ledger holds. Not a policy - just
#: enough history to reach into last month, so a quarantine decided on the first
#: of the month can still see the failures that caused it.
HEALTH_WINDOW_DAYS: Final = 31


def append_seen(
    state_dir: Path, date: str, rows: Iterable[SeenRow], *, identity: WriterIdentity
) -> int:
    """File first sights under the day the plan stage ran for. Returns how many it filed.

    A first sight carries no date of its own, so `date` is the day its rows are
    filed under, and the day a reader's window names to find them again.
    """
    recorded = list(rows)
    filed = persist(state_dir, recorded, ledger=LedgerName.SEEN, covers=date, identity=identity)
    return len(recorded) if filed else 0


def append_published(
    state_dir: Path, date: str, rows: Iterable[PublishedRow], *, identity: WriterIdentity
) -> int:
    """File what a committed digest actually carried, under that digest's day.

    The caller hands the date, so the caller decides which day the rows are filed
    under: a date inside a day that has already closed files a correction to that
    day (`docs/concepts/partitions.md`). Returns how many rows it filed.
    """
    recorded = list(rows)
    filed = persist(
        state_dir, recorded, ledger=LedgerName.PUBLISHED, covers=date, identity=identity
    )
    return len(recorded) if filed else 0


def load_seen(state_dir: Path, *, today: str, within_days: int) -> dict[str, str]:
    """Address -> the timestamp we first saw it, over the window only.

    Older days stay committed and stay readable; they are simply not consulted,
    because an address first seen four months ago is not evidence about today.
    The earliest sight wins when two days disagree, which is what "first" means.

    `day_partition.days_in_window` names both ends, so a cover of `n` days reads
    exactly `n + 1` days through the door's bounded reader, whatever the ledger
    holds beside them. A day with no row is not a fault: a run that met no new
    address that day filed nothing that day.
    """
    first_seen: dict[str, str] = {}
    days = day_partition.days_in_window(today, within_days)
    for row in ledger_files.load_days(state_dir, LedgerName.SEEN, days, model=SeenRow):
        if row.url_key not in first_seen or row.first_seen_at < first_seen[row.url_key]:
            first_seen[row.url_key] = row.first_seen_at
    return first_seen


def load_published(state_dir: Path, *, today: str | None, within_days: int) -> dict[str, str]:
    """Address -> the digest date it ran on, over the cover the config sets.

    `within_days` is `collect.published_window_days`. The committed config sets
    it to `UNBOUNDED_WINDOW`, so the shipping answer is every address ever
    published - the guarantee the guard has always given. Two paths, because the
    two questions are not the same question:

    - **Unbounded.** Every month the ledger holds, read one month at a time and
      folded into the answer before the next month is read. `today` is not read
      on this path, and a caller with no cover passes `None` to say so.
    - **Finite.** The days in range and no others. A day outside the cover is
      never read, so an address only that day holds is forgotten and can be
      planned again. That is the point of a cover, and it is why
      `CollectConfig` refuses a value that is not wider than
      `collect.seen_window_days`.

    A month at a time, because this is the read over the ledger with no natural
    bound, and the history is what grows: the peak is one month's rows and the
    answer, never the whole ledger. The months come from the ledger's indexes
    and its raw folder names, so no data file is opened to find them. A day with
    no row is not a fault - a run that published nothing that day filed nothing.
    """
    published: dict[str, str] = {}
    if within_days == UNBOUNDED_WINDOW:
        for month in ledger_files.held_months(state_dir, LedgerName.PUBLISHED):
            _keep_the_earliest(
                published,
                ledger_files.load_days(
                    state_dir,
                    LedgerName.PUBLISHED,
                    ledger_files.month_days(month),
                    model=PublishedRow,
                ),
            )
        return published
    if today is None:
        raise ValueError(
            f"a published cover of {within_days} days needs the day it is anchored on. "
            f"Pass today, or {UNBOUNDED_WINDOW} to read every day."
        )
    days = day_partition.days_in_window(today, within_days)
    _keep_the_earliest(
        published,
        ledger_files.load_days(state_dir, LedgerName.PUBLISHED, days, model=PublishedRow),
    )
    return published


def _keep_the_earliest(published: dict[str, str], rows: Iterable[PublishedRow]) -> None:
    """Fold rows into the answer, keeping each address's earliest digest date."""
    for row in rows:
        if row.url_key not in published or row.published_on < published[row.url_key]:
            published[row.url_key] = row.published_on


def load_settled_failures(state_dir: Path, date: str, *, codes: Collection[str]) -> set[str]:
    """Addresses that failed today for a reason today cannot change.

    The published ledger stops a repeat of a *success*. It cannot stop a repeat
    of a failure, because a failure is never published - so every later run of
    the same day planned the same paywall again and got the same paywall.
    Measured over 2026-08-24 to 2026-08-29, 403 such repeats bought 2 items.

    Only `date` is read, and only the codes the caller names. A rate limit or a
    reset connection is a different answer at 18:20 than it was at 02:20, so
    those codes are left out of the config list and their addresses come back.

    An empty `codes` returns nothing, which is exactly the behaviour this
    replaced - a run configured that way plans a failed address again.
    """
    if not codes:
        return set()
    wanted = set(codes)
    return {
        row.url_key
        for row in ledger_files.load_days(
            state_dir, LedgerName.ITEM_HEALTH, [date], model=ItemHealthRow
        )
        if row.date == date
        and row.outcome != ItemOutcome.OK
        and row.code is not None
        and row.code in wanted
    }


def load_source_counts(state_dir: Path, date: str) -> dict[str, int]:
    """Feed -> how many of today's items it has already put in front of a reader.

    The count a day-wide source ceiling reads. Only rows that reached the
    digest are counted: a feed whose page was behind a paywall spent a slot,
    but it did not fill any of the day, and the ceiling is about what a reader
    sees.

    Keyed on the address rather than the row, because one item settles once but
    can be written by more than one job, and a re-run of the same day writes it
    again. Counting rows would charge a feed twice for one story.
    """
    carried: dict[str, str] = {}
    for row in ledger_files.load_days(
        state_dir, LedgerName.ITEM_HEALTH, [date], model=ItemHealthRow
    ):
        if row.date != date or row.outcome != ItemOutcome.OK:
            continue
        carried[row.url_key] = row.source_id
    counts: dict[str, int] = {}
    for source_id in carried.values():
        counts[source_id] = counts.get(source_id, 0) + 1
    return counts


def load_retirements(state_dir: Path) -> list[FeedRetirementRow]:
    """Every retired address, oldest first, one row each. Never windowed: retirement is forever.

    Two runs reading the same five `410` answers from two stale checkouts each
    file the same address, and only the first row is kept - a retirement is
    permanent, so a second row for one address says nothing the first did not.
    A file this build cannot read is skipped with a warning, and the direction of
    that failure is the safe one: it costs one request to an address that is
    probably still gone, and the next run reads the same evidence and files it
    again. Refusing to start would cost the reader the day.

    Cover: -1, unbounded on purpose. A retirement is permanent, so any cover in
    days would forget the oldest ones and the run would ask a dead server again.
    What bounds it is the compaction: a retirement older than the `monthly_window`
    `config/gardener/compact-feed-retirements.json` declares is deleted with its
    month, and its feed is fetched again.
    """
    return ledger_files.load_ledger_rows(
        state_dir, LedgerName.FEED_RETIREMENTS, model=FeedRetirementRow
    )


def load_story_similarity_pairs(state_dir: Path, date: str) -> list[StorySimilarityPair]:
    """One named day's judged pairs, read through the ledger door, and never a second day.

    **Guardrail #12 declaration, and it is the whole point of this ledger's
    shape.** The fold counts one date into the record and the record is then the
    only thing the fit reads, so this asks the door for the day the date names
    and stops: the three compact indexes, the one file that serves the day, and
    that day's raw files. It costs the same on the thousandth day as on the third
    whatever the ledger holds beside it.

    A file this build cannot read is skipped with a warning naming it, the way
    the door reads every ledger, so a short day is said in the log rather than
    silently counted as a quiet one.
    """
    return ledger_files.load_days(
        state_dir,
        LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS,
        [date],
        model=StorySimilarityPair,
    )


def append_fitted_thresholds(
    state_dir: Path, date: str, rows: Iterable[FittedSimilarityThreshold]
) -> int:
    """Append a run's fitted row into that day's own file.

    Settled against `STORY_SIMILARITY_THRESHOLD_KEY` straight after the write.
    The key is date and run, so a second RUN of one date keeps its own row - two
    runs fitted two records and both are facts - and only a second attempt at
    one execution is collapsed: both attempts fitted the same record, so the
    first row wins and there is nothing to choose between them.

    **The day file is created even when the fit was held**, and a held day writes
    a row like any other: a line that moves itself has to leave a record on the
    days it stayed put, or a reader cannot tell a held day from a day nothing
    ran. The commit step names this directory, `git add` runs under
    `set -euo pipefail`, and a path missing from the working tree aborts the
    step and costs the ledgers staged beside it.

    Returns how many rows the file gained, so a caller can log the count.
    """
    recorded = list(rows)
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS
    if not lifecycle.accepts_new_rows(which, len(recorded)):
        return 0
    file = paths.path(state_dir, which, date)
    columns = FittedSimilarityThreshold.csv_columns()
    if not file.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(",".join(columns) + "\n", encoding="utf-8", newline="")
    landed = extend_ledger_file(file, columns, recorded)
    return landed - drop_repeated_rows(file, STORY_SIMILARITY_THRESHOLD_KEY)


def load_fitted_thresholds(
    state_dir: Path, *, today: str, within_days: int
) -> list[FittedSimilarityThreshold]:
    """Every fitted row in the window, read through the ledger door, oldest day first.

    **Guardrail #12 declaration.** `day_partition.days_in_window` names both
    ends, so a cover of `n` days asks the door for exactly `n + 1` days: the
    three compact indexes, the one file that serves each day, and the raw files
    of the days no index names. The ledger is never walked, so the read costs the
    same on the thousandth day as on the third.

    **The window is in days and the guard's median is in rows, and the caller is
    what reconciles them.** One missed run leaves thirteen rows inside a
    fourteen-day cover, the median returns nothing, and a guard that silently
    never fires is worse than one that fires too readily. The fit therefore asks
    for `max(settled_window_days, step_change_window_rows * 2)` days and takes the
    newest rows it finds - a bound set by two knobs rather than by the archive.

    A day the fit never ran has no row, which is not a fault. Two runs of one
    date both keep their row, the later run's last, because the door keeps the
    order its writers filed in. A file this build cannot read is skipped with a
    warning naming it, the way the door reads every ledger, so a short window is
    said in the log rather than silently read as a quiet one.
    """
    return ledger_files.load_days(
        state_dir,
        LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS,
        day_partition.days_in_window(today, within_days),
        model=FittedSimilarityThreshold,
    )


def load_visual_prunes(state_dir: Path) -> list[VisualPruneRow]:
    """Every cleanup pass on record, oldest day first, one row per run. Never windowed.

    The question is whether the backlog is shrinking, which is about the whole
    series - so this reads every day the raw ledger holds and no window saves it
    anything. That is the trade `docs/architecture/contracts/state-ledgers.md`
    states for this ledger.

    One row per `(date, run_id)`: a second attempt at one run replaces the first
    through the work unit, and a second row for one run from anywhere else walked
    the same tree and reported the same counts, so the first is kept. A file this
    build cannot read is skipped with a warning, for the reason `load_retirements`
    gives: this ledger is a report, and refusing to start because an old report
    cannot be read would cost a reader the day.
    """
    return ledger_files.load_ledger_rows(
        state_dir, LedgerName.VISUAL_PRUNES, model=VisualPruneRow
    )


def write_item_health_summary(path: Path, rows: list[ItemHealthSummaryRow]) -> int:
    """Write one month's folded summary whole, replacing whatever was there.

    The only writer here that rewrites rather than appends, and the reason is
    that this file is derived: every row is a function of the shard it was folded
    from, so writing it twice writes the same bytes twice. Appending would double
    a month whenever the fold ran again over a shard a lost race had restored.

    Returns how many rows landed, so a caller can log the count.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ItemHealthSummaryRow.csv_columns()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.csv_row())
    return len(rows)


def load_item_health_summary(path: Path) -> list[ItemHealthSummaryRow]:
    """Every folded row of one month. Empty for a month never folded."""
    return [ItemHealthSummaryRow.from_csv_row(row) for row in _read_rows(path)]


def load_health(state_dir: Path, *, today: str, within_days: int) -> list[FeedHealthRow]:
    """Every health row of the newest `within_days` days the ledger holds, oldest run first.

    Sorted by run rather than by file order so a caller can talk about "the last
    N runs" without knowing which file a row came from.

    The cover counts the days the ledger holds a row for, read from its indexes
    and its raw folder names alone (`ledger_files.held_days`), so a cover of `n`
    days reads the newest `n` RECORDED days and a day nothing ran on is never
    counted. `UNBOUNDED_WINDOW` reads every day it holds. `today` is not read: a
    count back from a date would answer nothing for a ledger whose last run was
    a week ago.

    Each day is read through the door's bounded reader and settled on its own:
    one writer's file per work unit, the highest attempt's, then one row per
    feed per run by `FEED_HEALTH_KEY` and its preference. A file this build
    cannot read is skipped with a warning naming it, as every door read is.
    """
    held = ledger_files.held_days(state_dir, LedgerName.FEED_HEALTH)
    days = held if within_days == UNBOUNDED_WINDOW else held[max(0, len(held) - within_days) :]
    rows = ledger_files.load_days(state_dir, LedgerName.FEED_HEALTH, days, model=FeedHealthRow)
    rows.sort(key=lambda row: (row.date, _run_n(row.run_id)))
    return rows


def _run_n(run_id: str) -> int:
    """The execution number out of `<date>-<execution>`, so a later run sorts last.

    The trailing field is the GitHub run id on anything CI produced and a small
    ordinal on anything a developer machine did, and both increase with time, so
    the sort is chronological across the change and on either side of it.
    """
    return int(run_id.rsplit("-", 1)[1])
