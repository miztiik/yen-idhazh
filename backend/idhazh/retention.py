"""How old is a file under a dated tree, and what does a month fold into before its files go?

The retention passes are gardener tasks, one module each under
`idhazh.gardener.tasks`, and each says what it owns and how long it keeps it in
its own declaration under `config/gardener/`. What they share lives here: the
walk that reads a published day's date out of its path, the rule for which file
in a day is a picture, the month stems a ledger files by, the day a trial file
records, and the two folds that replace a month of full-grain rows with the
rows a reader still needs. **The concept is adaptive pruning, and
`docs/concepts/adaptive-pruning.md` is where it is decided**: which policy each
artefact carries, and why.

Nothing here deletes a file but `drop_empty_directories`, and it deletes only
directories already emptied: every deletion goes through a task, so each one is
counted, capped and recorded in the gardener's own record.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Final, NamedTuple, NoReturn

from idhazh import month_partition
from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.item_health_summary import ItemHealthSummaryRow, percentile
from idhazh.contracts.visual_decision import VisualState
from idhazh.contracts.visual_telemetry import VisualAggregateRow, VisualAttemptRow, band_of


def visuals_older_than(root: Path, days: Iterable[date]) -> list[Path]:
    """Rendered visuals inside these named days, ordered for the delete ceiling."""
    found: list[Path] = []
    for _, folder in dated_days(root, days):
        found.extend(_visuals_in(folder))
    return found


def _stamped(name: str, width: int) -> bool:
    """Exactly `width` ASCII digits.

    `str.isdigit` on its own accepts another script's numerals, and a date parse
    would then read one as a day this tree never wrote.
    """
    return len(name) == width and name.isascii() and name.isdigit()


def _refuse(entry: Path, root: Path, expected: str) -> NoReturn:
    raise ValueError(
        f"{entry.relative_to(root).as_posix()} is not a {expected} of the published day "
        f"tree. Everything below a year directory here is written by assemble.day_dir, "
        f"so a name this pass cannot read as a date means something else is writing "
        f"there - and a cleanup that skipped it quietly would leave files nothing "
        f"accounts for"
    )


def dated_days(root: Path, days: Iterable[date]) -> Iterator[tuple[date, Path]]:
    """Existing published directories for these named days, oldest first.

    The caller supplies a fixed day window. This opens each named path directly,
    so neither an old backlog nor newer published days adds directory reads.
    """
    for published in sorted(set(days)):
        day_dir = root / f"{published:%Y}" / f"{published:%m}" / f"{published:%d}"
        if day_dir.is_dir():
            yield published, day_dir


def _visuals_in(folder: Path) -> list[Path]:
    """The published visuals in one day, by name.

    **A visual is a file named for an item**, which is the same rule
    `render.write.assets_in_day` uses and the same rule that decides where a
    writer puts one. It was a set of image suffixes until 2026-09-13, when the
    reader's browser took over the drawing and a visual stopped being an image -
    and adding `.json` to that set would have made `digest.json` and `run.json`
    candidates, which is the record that the day happened and the one thing a
    cleanup may never delete.

    Reading identity rather than extension is also what stops the list rotting.
    A suffix set holds the formats somebody remembered; an item id ends in a
    hyphen and a run of digits or sixteen base32 symbols, so no day-level payload
    can ever look like one whatever a later row files beside it.
    """
    return [
        path
        for path in sorted(folder.iterdir())
        if path.is_file() and re.match(ITEM_ID_PATTERN, path.stem)
    ]


def oldest_visual(root: Path, day: date) -> date | None:
    """The published day of the oldest rendered visual still on disk, or None.

    Read against the cutoff, this is what says whether the policy has caught up:
    while it is older than the cutoff there is backlog left, whatever one run's
    `deleted` says. None means the tree carries no visual at all, which is a
    different fact from "the oldest one is recent" and is spelled differently.

    The visual-prune task asks this on every pass, whatever it found, so it is
    the one read here that costs on every wake. The answer is the first day that
    still holds a picture, so it stops at that day: 4 directory listings on a
    built 400-day tree against 417 for the shape it replaced, 2026-09-07, Intel
    Core i7-1265U.
    """
    folder = root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    return day if folder.is_dir() and _visuals_in(folder) else None


def oldest_month_kept(today: date, months: int) -> str:
    """The oldest `YYYY-MM` stem that still stays at full grain.

    `month_partition` owns the arithmetic, because the published tree ages by
    the same boundary now and two copies of it is how one ledger deletes a month
    the other still serves. This name stays because the month tasks and their
    tests read by it.
    """
    return month_partition.oldest_month_kept(today, months)


def month_shards(directory: Path, months: Iterable[str]) -> list[Path]:
    """Every `<YYYY-MM>.csv` in a ledger directory, oldest first.

    Anything else in there is left alone. A directory this walks is one a task
    deletes from, so it names what it recognises rather than deleting what it
    does not - and it recognises what `month_partition` recognises. Three
    readers used to hold three different answers, and `2025-13.csv` was left
    alone here and deleted there.
    """
    return month_partition.month_files(directory, ".csv", months)


# --- The telemetry fold ------------------------------------------------------


def _elapsed_ms(row: ItemHealthRow) -> int | None:
    """What one item spent in the pipeline, or nothing if it was never timed.

    The three stage clocks added together rather than the one clock belonging to
    the row's terminal stage: an item that reached `publish` was fetched,
    extracted and summarized, and the figure a reader wants for it is what the
    whole item cost. An item that stopped at `fetch` has only the one clock, and
    adding it to nothing gives that clock back.
    """
    parts = [row.fetch_ms, row.extract_ms, row.summarize_ms]
    timed = [value for value in parts if value is not None]
    return sum(timed) if timed else None


def compact_month(rows: list[ItemHealthRow]) -> list[ItemHealthSummaryRow]:
    """One month of full-grain rows, as one row per (date, stage).

    Ordered by date and then by the stage's own pipeline order, so the file a
    reader opens reads down the funnel rather than down the alphabet.
    """
    grouped: dict[tuple[str, ItemStage], list[ItemHealthRow]] = {}
    for row in rows:
        grouped.setdefault((row.date, row.stage), []).append(row)

    order = list(ItemStage)
    folded: list[ItemHealthSummaryRow] = []
    for day, stage in sorted(grouped, key=lambda key: (key[0], order.index(key[1]))):
        members = grouped[(day, stage)]
        elapsed = sorted(
            value for value in (_elapsed_ms(member) for member in members) if value is not None
        )
        folded.append(
            ItemHealthSummaryRow(
                version=ItemHealthSummaryRow.schema_version(),
                date=day,
                stage=stage,
                items=len(members),
                failed=sum(1 for member in members if member.outcome is not ItemOutcome.OK),
                timed=len(elapsed),
                p50_ms=percentile(elapsed, 0.5) if elapsed else None,
                p90_ms=percentile(elapsed, 0.9) if elapsed else None,
                max_ms=elapsed[-1] if elapsed else None,
                sum_ms=sum(elapsed) if elapsed else None,
            )
        )
    return folded


# --- The visual fold ---------------------------------------------------------


class _Spread(NamedTuple):
    """One measured column of one group, as the six figures that survive the fold.

    Deliberately not a mean. A mean cannot be re-added across groups and, more to
    the point here, it hides a bimodal spread - which is the finding worth having
    when the question is whether a gate refuses two different populations for two
    different reasons.
    """

    n: int
    min: int | None
    p25: int | None
    p50: int | None
    p75: int | None
    max: int | None


def _spread(values: list[int]) -> _Spread:
    """The six figures over one group's readings of one column.

    Nearest-rank quartiles, so every figure is one an attempt really had and can
    be checked against the shard this replaced. An interpolated quartile is a
    number no attempt produced, and a fold that invents a value cannot be
    reconciled against the file it deletes.

    Empty in, empty out: a column nothing measured carries `n = 0` and no
    figures. Zero would say the attempts measured the column and found nothing.
    """
    if not values:
        return _Spread(n=0, min=None, p25=None, p50=None, p75=None, max=None)
    ordered = sorted(values)
    return _Spread(
        n=len(ordered),
        min=ordered[0],
        p25=percentile(ordered, 0.25),
        p50=percentile(ordered, 0.5),
        p75=percentile(ordered, 0.75),
        max=ordered[-1],
    )


def _visual_group(row: VisualAttemptRow) -> tuple[str, ...]:
    """This attempt's `FOLD_KEY` tuple, as sortable text.

    Text rather than the typed values because six of the eight terms are
    optional, and `sorted` cannot compare `None` with a member of an enum. An
    absent term sorts first as the empty string, which puts the groups nobody
    could classify at the top of their day rather than scattered through it. The
    depth is zero-padded so ten sorts after nine.
    """
    band = band_of(row.elements_found)
    return (
        row.date,
        row.decision.value,
        row.none_reason.value if row.none_reason is not None else "",
        row.rejection_reason.value if row.rejection_reason is not None else "",
        row.potential_primary.value if row.potential_primary is not None else "",
        row.family.value if row.family is not None else "",
        band.value if band is not None else "",
        "" if row.downgrade_depth is None else f"{row.downgrade_depth:03d}",
    )


def fold_visual_month(rows: Sequence[VisualAttemptRow]) -> list[VisualAggregateRow]:
    """One month of visual attempts, as one row per `FOLD_KEY` group.

    Cover: the rows of one month's shard, handed in rather than read here - the
    same shape `compact_month` above takes, and for the same reason. The cost
    follows the month being folded and never the months behind it
    (Guardrail #12), so a fold in year three costs what a fold in year one did.

    **It can only shrink the ledger.** Every group holds at least one attempt, so
    the row count never rises, and the folded row is narrower than the attempt
    row it replaces - it drops the run, the item and the join key and adds
    nothing per attempt. The pathological month in which every attempt lands in
    its own group folds to the same number of rows, each one smaller, which is
    the fold buying nothing rather than costing something.

    Ordered by the key, so a folded month reads down the days and then down the
    causes. Nothing calls it yet: `state/visuals/` has no writer, and the task
    that folds it lands with the writer.
    """
    grouped: dict[tuple[str, ...], list[VisualAttemptRow]] = {}
    for row in rows:
        grouped.setdefault(_visual_group(row), []).append(row)

    folded: list[VisualAggregateRow] = []
    for key in sorted(grouped):
        members = grouped[key]
        first = members[0]
        elements = _spread(
            [member.elements_found for member in members if member.elements_found is not None]
        )
        marks = _spread([member.marks for member in members if member.marks is not None])
        folded.append(
            VisualAggregateRow(
                version=VisualAggregateRow.schema_version(),
                date=first.date,
                decision=first.decision,
                none_reason=first.none_reason,
                rejection_reason=first.rejection_reason,
                potential_primary=first.potential_primary,
                family=first.family,
                element_band=band_of(first.elements_found),
                downgrade_depth=first.downgrade_depth,
                attempts=len(members),
                published=sum(1 for member in members if member.state is VisualState.RENDERED),
                elements_n=elements.n,
                elements_min=elements.min,
                elements_p25=elements.p25,
                elements_p50=elements.p50,
                elements_p75=elements.p75,
                elements_max=elements.max,
                marks_n=marks.n,
                marks_min=marks.min,
                marks_p25=marks.p25,
                marks_p50=marks.p50,
                marks_p75=marks.p75,
                marks_max=marks.max,
            )
        )
    return folded


# --- A trial run's ledgers ---------------------------------------------------


#: The day a file under a trial root belongs to, read off its path. A trial root
#: mirrors `state/`, so it carries every grammar the tree carries: a
#: `<YYYY>/<MM>/<DD>.csv` day file, a `<YYYY>/<MM>/<DD>-<ordinal>-<shard>.jsonl`
#: trace, a `<YYYY-MM-DD>-<execution>-<attempt>-<job>-<shard>.csv` segment, and a
#: `<YYYY-MM>.csv` month head. One expression reads all four, because the thing
#: they agree on is the date and the thing they disagree on is everything else.
_TRIAL_DAY: Final = re.compile(r"(?P<year>\d{4})[/-](?P<month>\d{2})(?:[/-](?P<day>\d{2}))?")


def trial_day(relpath: str) -> date | None:
    """Which day this trial file records, or `None` when its path spells none.

    A month head has no day of its own, so it takes the last day of its month:
    a month is inside the window while any day in it is, which is the same
    boundary the telemetry-aggregate task holds for the months it folds.
    """
    found = _TRIAL_DAY.search(relpath)
    if found is None:
        return None
    year = int(found["year"])
    month = int(found["month"])
    if found["day"] is None:
        last = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
        return last
    try:
        return date(year, month, int(found["day"]))
    except ValueError:
        return None


def drop_empty_directories(root: Path) -> None:
    """Take the emptied trial tree away, root included.

    Without this the child count under `state/` only ever rises: a trial that
    ran once leaves a directory for ever, and a reader opening `state/` cannot
    tell an empty husk from a tree still being written (Guardrail #12). A tree
    the checkout never downloaded has no folder here to take away.
    """
    if not root.is_dir():
        return
    for directory in sorted((entry for entry in root.rglob("*") if entry.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    if not any(root.iterdir()):
        root.rmdir()
