"""How a caller puts rows into a ledger and gets them back out.

One verb per ledger. Each takes the state directory and the period its rows
describe, never a file name, and each takes contracts rather than dicts - so no
cell reaches a committed file without a model having read it.

`day_shards` is imported inside the function bodies that need it, and that is
deliberate. It imports names back out of this package at its own module top, so
a module-scope import here would close a load-time cycle: importing the package
runs `__init__`, which imports this module, which re-enters a half-built package.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path
from typing import Final

from idhazh import day_partition
from idhazh.contracts.base import ServerJob
from idhazh.contracts.council_shard_outcome import CouncilShardOutcome
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.ledger import paths
from idhazh.ledger.csv_file import (
    CsvRecord,
    _read_rows,
    _stream_rows,
    extend_ledger_file,
    render_file,
)
from idhazh.ledger.filenames import segment_name
from idhazh.ledger.keys import (
    _TREE_SHAPES,
    COUNCIL_SHARD_OUTCOME_KEY,
    DATE_CELL,
    FEED_HEALTH_KEY,
    FEED_RETIREMENT_KEY,
    ITEM_HEALTH_KEY,
    SPAN_ROLLUP_KEY,
    STORY_SIMILARITY_PAIR_KEY,
    STORY_SIMILARITY_THRESHOLD_KEY,
    VISUAL_PRUNE_KEY,
    _refuse_outside_day_trees,
)
from idhazh.ledger.settle import drop_repeated_rows

#: How far back a health read looks. Not a policy - just enough history to reach
#: into last month's shard, so a quarantine decided on the first of the month can
#: still see the failures that caused it.
HEALTH_WINDOW_DAYS: Final = 31


def append_seen(state_dir: Path, date: str, rows: Iterable[SeenRow]) -> int:
    """Append first sights. Returns how many landed, so a caller can log the count."""
    return extend_ledger_file(
        paths.path(state_dir, LedgerName.SEEN, date), SeenRow.csv_columns(), list(rows)
    )


def append_published(state_dir: Path, date: str, rows: Iterable[PublishedRow]) -> int:
    """Append what a committed digest actually carried, into that day's own file.

    The caller hands the date, so the caller decides: a date inside a day that
    has already closed performs a correction to that day, which is the one
    rewrite the freeze rule permits and the same choice `append_seen` gives its
    caller. See `docs/concepts/partitions.md`.
    """
    return extend_ledger_file(
        paths.path(state_dir, LedgerName.PUBLISHED, date), PublishedRow.csv_columns(), list(rows)
    )


def load_seen(state_dir: Path, *, today: str, within_days: int) -> dict[str, str]:
    """Address -> the timestamp we first saw it, over the window only.

    Older days stay committed and stay readable; they are simply not consulted,
    because an address first seen four months ago is not evidence about today.
    The earliest sight wins when two days disagree, which is what "first" means.

    `day_partition.days_in_window` names both ends, so a cover of `n` days opens
    at most `n + 1` files and reads exactly those days - where the month shards
    it replaced could hold up to 120 days of rows behind a 90-day cover. A day
    the ledger never recorded has no file, which is not a fault: a run that met
    no new address that day wrote nothing that day.
    """
    first_seen: dict[str, str] = {}
    for day in day_partition.days_in_window(today, within_days):
        for row in _read_rows(paths.path(state_dir, LedgerName.SEEN, day)):
            url_key, at = row["url_key"], row["first_seen_at"]
            if url_key not in first_seen or at < first_seen[url_key]:
                first_seen[url_key] = at
    return first_seen


def load_published(state_dir: Path, *, today: str | None, within_days: int) -> dict[str, str]:
    """Address -> the digest date it ran on, over the cover the config sets.

    `within_days` is `collect.published_window_days`. The committed config sets
    it to `UNBOUNDED_WINDOW`, so the shipping answer is every address ever
    published - the guarantee the guard has always given. Two paths, because the
    two questions are not the same question:

    - **Unbounded.** Walk `state/published/`, naming every entry it meets and
      refusing one it cannot place. `today` is not read on this path, and a
      caller with no cover passes `None` to say so.
    - **Finite.** Ask for the dates in range and open those files and no others.
      A day outside the cover is never opened, so an address only that day holds
      is forgotten and can be planned again. That is the point of a cover, and
      it is why `CollectConfig` refuses a value that is not wider than
      `collect.seen_window_days`.

    Neither path globs. The unbounded one has to account for every file it
    finds, and the bounded one only opens files it named itself. A named day
    with nothing published has no file, which is not a fault - a run that
    published nothing that day wrote nothing that day.

    Streamed rather than materialised, because this is the read over the ledger
    with no natural bound - so its peak would otherwise be the whole tree, and
    the tree is what grows. Only the day paths are listed, and a day is a file
    rather than a row.
    """
    if within_days == UNBOUNDED_WINDOW:
        files: Iterable[Path] = day_partition.day_files(
            paths.tree_root(state_dir, LedgerName.PUBLISHED)
        )
    elif today is None:
        raise ValueError(
            f"a published cover of {within_days} days needs the day it is anchored on. "
            f"Pass today, or {UNBOUNDED_WINDOW} to read every day file."
        )
    else:
        files = (
            paths.path(state_dir, LedgerName.PUBLISHED, on)
            for on in day_partition.days_in_window(today, within_days)
        )

    published: dict[str, str] = {}
    for file in files:
        for row in _stream_rows(file):
            url_key, on = row["url_key"], row["published_on"]
            if url_key not in published or on < published[url_key]:
                published[url_key] = on
    return published


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
    from idhazh import day_shards

    wanted = set(codes)
    return {
        row["url_key"]
        for row in day_shards.settled_day(
            paths.tree_root(state_dir, LedgerName.ITEM_HEALTH), date, ITEM_HEALTH_KEY, ItemHealthRow
        )
        if row["date"] == date and row["outcome"] != ItemOutcome.OK and row["code"] in wanted
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
    from idhazh import day_shards

    carried: dict[str, str] = {}
    for row in day_shards.settled_day(
        paths.tree_root(state_dir, LedgerName.ITEM_HEALTH), date, ITEM_HEALTH_KEY, ItemHealthRow
    ):
        if row["date"] != date or row["outcome"] != ItemOutcome.OK:
            continue
        carried[row["url_key"]] = row["source_id"]
    counts: dict[str, int] = {}
    for source_id in carried.values():
        counts[source_id] = counts.get(source_id, 0) + 1
    return counts


def _header_and_keys(
    path: Path, key: tuple[str, ...]
) -> tuple[tuple[str, ...], set[tuple[str, ...]]]:
    """The file's own header and every record it already holds, in one pass.

    One `csv.reader` rather than a `DictReader`, and one open rather than two.
    `DictReader` builds a dict of every column for each row, which is 119 keys on
    an item-health shard to read three cells; the positions are taken off the
    header once and the cells are read by index after that.

    A file with no header, or one that does not name every cell of `key`, holds
    no record this key can match - which is what a day with no history has.
    """
    if not path.exists():
        return (), set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = tuple(next(reader, []))
        if any(name not in header for name in key):
            return header, set()
        at = [header.index(name) for name in key]
        widest = max(at)
        return header, {
            tuple(cells[index] for index in at) for cells in reader if len(cells) > widest
        }


def recorded_item_health(path: Path) -> set[tuple[str, ...]]:
    """Every planned item this day's file already has a verdict for.

    A missing file is a day with no history, which is what the first run of a
    day has.
    """
    return _header_and_keys(path, ITEM_HEALTH_KEY)[1]


def append_retirements(state_dir: Path, rows: Iterable[FeedRetirementRow]) -> int:
    """Append the addresses this run decided are permanently gone.

    Settled against `FEED_RETIREMENT_KEY` straight after the write, because the
    two runs that can write one address are two
    stale checkouts rather than two decisions: each reads the same five `410`
    results and each files the same row. The settle catches the repeat inside one
    checkout; a second attempt that races its own first stops at the rebase
    rather than landing a second line. The
    first row wins - there is nothing for a preference rule to choose between,
    because a retirement is permanent and a second row for one address says
    nothing the first did not.

    Returns how many rows the file gained, so a caller can log the count. A row
    that only repeated one already on record is not a gain.
    """
    file = paths.path(state_dir, LedgerName.FEED_RETIREMENTS)
    landed = extend_ledger_file(file, FeedRetirementRow.csv_columns(), list(rows))
    return landed - drop_repeated_rows(file, FEED_RETIREMENT_KEY)


def load_retirements(state_dir: Path) -> list[FeedRetirementRow]:
    """Every retired address, in file order. Never windowed: retirement is forever.

    A row that no longer parses is skipped rather than fatal, and the direction
    of that failure is the safe one: an unreadable retirement costs one request
    to an address that is probably still gone, and the next run reads the same
    evidence and files it again. Refusing to start would cost the reader the day.

    Cover: -1, unbounded on purpose. A retirement is permanent, so any cover in
    days would forget the oldest ones and the run would ask a dead server again.
    """
    rows: list[FeedRetirementRow] = []
    for raw in _read_rows(paths.path(state_dir, LedgerName.FEED_RETIREMENTS)):
        try:
            rows.append(FeedRetirementRow.from_csv_row(raw))
        except (KeyError, ValueError):
            continue
    return rows


def recorded_span_rollup(path: Path) -> set[tuple[str, ...]]:
    """Every (date, run, shard, span) one span-rollup file already carries a fold for.

    A reader and no longer half of a writer. A work shard folds its spans into
    its own file in the day directory and nothing else opens that path, so the
    question this answers is what a settled file already holds rather than what
    an append is about to skip.
    """
    return {tuple(row[name] for name in SPAN_ROLLUP_KEY) for row in _read_rows(path)}


def append_visual_prunes(state_dir: Path, date: str, rows: Iterable[VisualPruneRow]) -> int:
    """Append what each cleanup pass found and took, into that day's own file.

    The caller hands the date, the way `append_published` takes one and for the
    same reason: the caller decides which day a pass belongs to, and a pass run
    against a date that has already closed writes its row there.

    Settled against `VISUAL_PRUNE_KEY` straight after the write, the way
    `append_retirements` is, because the two writers that can produce one key are
    two attempts at one execution rather than two cleanups. Each walks the same
    tree and reports the same counts, so the first row wins and there is nothing
    to choose between them. Settling the day file is enough: the key opens with
    `date`, so a repeat can only ever be inside the one day's file.

    Returns how many rows the file gained, so a caller can log the count.
    """
    file = paths.path(state_dir, LedgerName.VISUAL_PRUNES, date)
    landed = extend_ledger_file(file, VisualPruneRow.csv_columns(), list(rows))
    return landed - drop_repeated_rows(file, VISUAL_PRUNE_KEY)


def append_story_similarity_pairs(
    state_dir: Path, date: str, rows: Iterable[StorySimilarityPair]
) -> int:
    """Append a day's judged pairs into that day's own file.

    Settled against `STORY_SIMILARITY_PAIR_KEY` straight after the write, the
    way `append_visual_prunes` is. The key carries `run_id`, so a second
    RUN of one date keeps its own rows and only a second attempt at one
    execution is collapsed - both attempts judged the same pair under the same
    prompt against the same day, so the first row wins and there is nothing to
    choose between them. Which of two runs the record counts is decided over the
    whole day when the day is folded, never line by line here.

    **The day file is created even when the day judged nothing.** The commit step
    names this directory,
    `git add` runs under `set -euo pipefail`, and a path missing from the working
    tree aborts the step and costs the ledgers staged beside it.

    Returns how many rows the file gained, so a caller can log the count.
    """
    file = paths.path(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS, date)
    columns = StorySimilarityPair.csv_columns()
    if not file.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(",".join(columns) + "\n", encoding="utf-8", newline="")
    landed = extend_ledger_file(file, columns, list(rows))
    return landed - drop_repeated_rows(file, STORY_SIMILARITY_PAIR_KEY)


def load_story_similarity_pairs(state_dir: Path, date: str) -> list[StorySimilarityPair]:
    """One named day's judged pairs, and never a second file.

    **Guardrail #12 declaration, and it is the whole point of this ledger's
    shape.** The fold counts one date into the record and the record is then the
    only thing the fit reads, so this opens the file the date names and stops.
    It costs the same on the thousandth day as on the third whatever the tree
    holds beside it.

    A row that no longer parses stops the read rather than being skipped. A
    report may drop a day it cannot read; this is evidence being counted into a
    record that is rewritten whole, and a silently short count is a record that
    cannot be told from a quiet day.
    """
    pairs = paths.path(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS, date)
    return [StorySimilarityPair.from_csv_row(raw) for raw in _read_rows(pairs)]


def append_fitted_thresholds(
    state_dir: Path, date: str, rows: Iterable[FittedSimilarityThreshold]
) -> int:
    """Append a run's fitted row into that day's own file.

    Settled against `STORY_SIMILARITY_THRESHOLD_KEY` straight after the write,
    the way `append_story_similarity_pairs` is. The key is date and run, so a
    second RUN of one date keeps its own row - two runs fitted two records and
    both are facts - and only a second attempt at one execution is collapsed.

    **The day file is created even when the fit was held**, and a held day writes
    a row like any other: a line that moves itself has to leave a record on the
    days it stayed put, or a reader cannot tell a held day from a day nothing
    ran. The empty-file half is the same reason `append_story_similarity_pairs`
    gives - the commit step names this directory and a missing path aborts it
    under `set -euo pipefail`.

    Returns how many rows the file gained, so a caller can log the count.
    """
    file = paths.path(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS, date)
    columns = FittedSimilarityThreshold.csv_columns()
    if not file.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(",".join(columns) + "\n", encoding="utf-8", newline="")
    landed = extend_ledger_file(file, columns, list(rows))
    return landed - drop_repeated_rows(file, STORY_SIMILARITY_THRESHOLD_KEY)


def append_council_shard_outcomes(
    state_dir: Path, date: str, rows: Iterable[CouncilShardOutcome]
) -> int:
    """Append a night's recorded units of council work into that date's own file.

    Settled against `COUNCIL_SHARD_OUTCOME_KEY` straight after the write, the
    way `append_fitted_thresholds` is. A repeat under all four cells is a second
    attempt at one unit, which ran the same work under the same clock, so the
    first row wins and there is nothing to choose between them.

    **A night with no unit to record writes no file**, which is the one place
    this writer differs from the three above it. A header with no rows under it
    is a real day file to the partition walker, so an empty write here would put
    a permanent day in the prune target and the day inventory that no council
    run ever had. The ledger's directory is kept in the checkout by its own
    `.gitkeep`, so the staged path is there whether or not tonight wrote to it.

    Returns how many rows the file gained, so a caller can log the count.
    """
    recorded = list(rows)
    if not recorded:
        return 0
    file = paths.path(state_dir, LedgerName.LLM_COUNCIL_SHARD_OUTCOMES, date)
    landed = extend_ledger_file(file, CouncilShardOutcome.csv_columns(), recorded)
    return landed - drop_repeated_rows(file, COUNCIL_SHARD_OUTCOME_KEY)


def load_fitted_thresholds(
    state_dir: Path, *, today: str, within_days: int
) -> list[FittedSimilarityThreshold]:
    """Every fitted row in the window, oldest day first.

    **Guardrail #12 declaration.** `day_partition.days_in_window` names both
    ends, so a cover of `n` days opens at most `n + 1` files and reads exactly
    those days. The tree is never walked, so the read costs the same on the
    thousandth day as on the third.

    **The window is in days and the guard's median is in rows, and the caller is
    what reconciles them.** One missed run leaves thirteen rows inside a
    fourteen-day cover, the median returns nothing, and a guard that silently
    never fires is worse than one that fires too readily. The fit therefore asks
    for `max(settled_window_days, step_change_window_rows * 2)` days and takes the
    newest rows it finds - a bound set by two knobs rather than by the archive.

    A day the fit never ran has no file, which is not a fault. A row that no
    longer parses stops the read rather than being skipped: the guard takes a
    median over these rows, and a silently short list moves that median instead
    of costing a decision some evidence.
    """
    rows: list[FittedSimilarityThreshold] = []
    for day in reversed(day_partition.days_in_window(today, within_days)):
        fitted = paths.path(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS, day)
        rows.extend(FittedSimilarityThreshold.from_csv_row(raw) for raw in _read_rows(fitted))
    return rows


def load_visual_prunes(state_dir: Path) -> list[VisualPruneRow]:
    """Every cleanup pass on record, oldest day first. Never windowed.

    The question is whether the backlog is shrinking, which is about the whole
    series - so this opens every day file the tree holds and the layout saves it
    nothing. That is the trade `docs/architecture/contracts/state-ledgers.md`
    states for this ledger.

    A row that no longer parses is skipped rather than fatal, for the reason
    `load_retirements` gives: this ledger is a report, and refusing to start
    because an old report cannot be read would cost a reader the day. A file the
    walk cannot place is a different thing and still stops the read - a report
    that quietly drops a day is a report of the wrong series.
    """
    rows: list[VisualPruneRow] = []
    for file in day_partition.day_files(paths.tree_root(state_dir, LedgerName.VISUAL_PRUNES)):
        for raw in _read_rows(file):
            try:
                rows.append(VisualPruneRow.from_csv_row(raw))
            except (KeyError, ValueError):
                continue
    return rows


def day_shard_path(
    state_dir: Path,
    ledger: LedgerName,
    *,
    date: str,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> Path:
    """Where this writer puts this date's rows. Nobody else writes this path.

    `state/<tree>/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv`. The
    date supplies the three directory segments, the way every sibling helper in
    this module takes one; the four identity elements are what make the file
    this writer's own. Two jobs of one run cannot collide, and neither can two
    attempts - which is the difference between a lost push race costing a merge
    and costing the rows.

    The day comes off the row rather than off the clock, so rows a run left
    behind three days ago land under that day rather than under today.
    """
    _refuse_outside_day_trees(ledger)
    name = segment_name(run_id=run_id, attempt=attempt, job=job, shard=shard)
    return paths.path(state_dir, ledger, date) / name


def day_shard_relpath(
    ledger: LedgerName,
    *,
    date: str,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> str:
    """The POSIX form of `day_shard_path`, for a log line (CLAUDE.md section 2)."""
    _refuse_outside_day_trees(ledger)
    name = segment_name(run_id=run_id, attempt=attempt, job=job, shard=shard)
    return f"{paths.relpath(ledger, date)}/{name}"


def _dated_rows(
    ledger: LedgerName, rows: Sequence[CsvRecord], date: str | None
) -> dict[str, list[dict[str, str]]]:
    """This writer's rows, grouped by the day each one belongs under.

    `date` is for the one tree whose rows carry no date cell. The score index is
    a stamp and a digest - the record of what the rows beside it are - so it is
    filed beside them rather than dated itself, and its writer already knows the
    day because it is the first ten characters of the run id. Every other tree
    routes each row by its own `date` cell, so a writer holding two days' rows
    writes two files.
    """
    columns = _TREE_SHAPES[ledger].model.csv_columns()
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        cells = row.csv_row()
        day = date if date is not None else cells[DATE_CELL]
        grouped.setdefault(day, []).append({name: cells.get(name, "") for name in columns})
    return grouped


def write_segment(
    state_dir: Path,
    ledger: LedgerName,
    rows: Sequence[CsvRecord],
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
    date: str | None = None,
) -> int:
    """This writer's slice of one ledger, written whole. Nobody else writes these paths.

    Whole rather than appended, because each file is this writer's alone: there
    is no earlier row in it to keep and no header to agree with. That is what the
    day directory buys - two jobs of one run, and two attempts at one job, never
    open one file, so a lost push race costs a merge rather than the rows.

    One file a day. The rows carry the tree's own columns and the tree's own
    contract; a writer file gets no shape of its own, because a second shape for
    the same rows is the thing that drifts.

    Written through a temp file and a rename, so a writer killed mid-write leaves
    nothing rather than half a row for a reader to refuse. The temp file sits at
    the tree's own top rather than inside the day directory, which every reader
    walks and refuses a name it cannot place.

    Returns how many rows it wrote, so a caller can log the count.
    """
    _refuse_outside_day_trees(ledger)
    if not rows:
        return 0
    columns = _TREE_SHAPES[ledger].model.csv_columns()
    written = 0
    for day, cells in _dated_rows(ledger, rows, date).items():
        path = day_shard_path(
            state_dir, ledger, date=day, run_id=run_id, attempt=attempt, job=job, shard=shard
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        scratch = paths.tree_root(state_dir, ledger) / f"{path.stem}.{day}.{os.getpid()}.tmp"
        scratch.write_text(render_file(columns, cells), encoding="utf-8", newline="")
        scratch.replace(path)
        written += len(cells)
    return written


def extend_segment(
    state_dir: Path,
    ledger: LedgerName,
    rows: Sequence[CsvRecord],
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
    date: str | None = None,
) -> int:
    """Add rows to this writer's own files, keeping the ones it wrote earlier.

    `write_segment` is for a step that has everything its job will ever say. This
    is for a job that learns something later: the machine probe runs before the
    heaviest step because the bandwidth reading wants an idle host, and the job's
    own clock is only known once the job is over. Two steps, one writer, one file
    a day - the grammar in `day_shard_path` names the job and not the step, so a
    second file is not something this tree can express.

    The earlier rows are read and written back unchanged. Nothing is edited and
    nothing is settled here: the arriving row carries the cells it has, the
    earlier row keeps the cells it had, and `day_shards.settled_rows` is the one
    place that decides what two rows of one key mean.

    Returns how many rows it added, so a caller can log the count.
    """
    _refuse_outside_day_trees(ledger)
    if not rows:
        return 0
    columns = _TREE_SHAPES[ledger].model.csv_columns()
    added = 0
    for day, cells in _dated_rows(ledger, rows, date).items():
        path = day_shard_path(
            state_dir, ledger, date=day, run_id=run_id, attempt=attempt, job=job, shard=shard
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        held = [{name: row.get(name, "") for name in columns} for row in _read_rows(path)]
        scratch = paths.tree_root(state_dir, ledger) / f"{path.stem}.{day}.{os.getpid()}.tmp"
        scratch.write_text(render_file(columns, held + cells), encoding="utf-8", newline="")
        scratch.replace(path)
        added += len(cells)
    return added


def load_item_health_shard(path: Path) -> list[ItemHealthRow]:
    """Every row of one full-grain partition. Empty for a day never written."""
    return [ItemHealthRow.from_csv_row(row) for row in _read_rows(path)]


def load_host_fingerprint_shard(path: Path) -> list[HostFingerprintRow]:
    """Every row of one day's host records. Empty for a day never written.

    A day and not a window, because the key opens with `date` and a run id
    already names its date - so a caller asking about one run opens one file
    however long the ledger gets (Guardrail #12).
    """
    return [HostFingerprintRow.from_csv_row(row) for row in _read_rows(path)]


def load_span_rollup_shard(path: Path) -> list[SpanRollupRow]:
    """Every row of one month's span rollup. Empty for a month never written.

    A month rather than a day, because that is the grain the rollup is sharded
    at. A caller asking about one date filters on `date` after reading.
    """
    return [SpanRollupRow.from_csv_row(row) for row in _read_rows(path)]


def load_item_health(state_dir: Path, *, today: str, within_days: int) -> list[ItemHealthRow]:
    """Every item-health row in the window, oldest day first.

    Bounded for the same reason `load_health` is (Guardrail #12): this is the
    fastest-growing ledger in the repository and twenty work shards file into it
    every day, so a reader that walked every day would cost more every run for
    an answer about the last few weeks. `day_shards.settled_rows` names both the
    cover and the settlement, so a cover of `n` days reads the newest `n`
    RECORDED days and returns one row per planned item per run.

    A day the ledger never recorded has no entry, which is not a fault: a run
    that planned nothing that day wrote nothing that day.

    A row that no longer parses stops the read, which is what every day-shard
    read does: a census divides by these rows, so a silently dropped one moves a
    ratio instead of costing a decision some evidence.
    """
    from idhazh import day_shards

    return [
        ItemHealthRow.from_csv_row(row)
        for row in day_shards.settled_rows(
            paths.tree_root(state_dir, LedgerName.ITEM_HEALTH),
            ITEM_HEALTH_KEY,
            ItemHealthRow,
            days=within_days,
        )
    ]


def write_telemetry_aggregate(path: Path, rows: list[TelemetryAggregateRow]) -> int:
    """Write one month's folded summary whole, replacing whatever was there.

    The only writer here that rewrites rather than appends, and the reason is
    that this file is derived: every row is a function of the shard it was folded
    from, so writing it twice writes the same bytes twice. Appending would double
    a month whenever the fold ran again over a shard a lost race had restored.

    Returns how many rows landed, so a caller can log the count.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = TelemetryAggregateRow.csv_columns()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.csv_row())
    return len(rows)


def load_telemetry_aggregate(path: Path) -> list[TelemetryAggregateRow]:
    """Every folded row of one month. Empty for a month never folded."""
    return [TelemetryAggregateRow.from_csv_row(row) for row in _read_rows(path)]


def load_health(state_dir: Path, *, today: str, within_days: int) -> list[FeedHealthRow]:
    """Every health row in the window, oldest run first.

    Sorted by run rather than by file order so a caller can talk about "the last
    N runs" without knowing that the file is append-ordered - which it is today,
    and which a rebased CI push could stop being tomorrow.

    A row that no longer parses stops the read rather than being skipped. Each
    file is written whole by one writer from the contract's own columns, so a
    row that will not read means the writer and this reader disagree about the
    shape - `day_shards.parsed` says at length why that is the one ledger read
    that does not degrade.

    `day_shards.settled_rows` names both the cover and the settlement, so a
    cover of `n` days reads the newest `n` RECORDED days and returns one row per
    feed per run rather than one per write. A day the ledger never recorded has
    no entry, which is not a fault.
    """
    from idhazh import day_shards

    rows = [
        FeedHealthRow.from_csv_row(raw)
        for raw in day_shards.settled_rows(
            paths.tree_root(state_dir, LedgerName.FEED_HEALTH),
            FEED_HEALTH_KEY,
            FeedHealthRow,
            days=within_days,
        )
    ]
    rows.sort(key=lambda row: (row.date, _run_n(row.run_id)))
    return rows


def _run_n(run_id: str) -> int:
    """The execution number out of `<date>-<execution>`, so a later run sorts last.

    The trailing field is the GitHub run id on anything CI produced and a small
    ordinal on anything a developer machine did, and both increase with time, so
    the sort is chronological across the change and on either side of it.
    """
    return int(run_id.rsplit("-", 1)[1])
