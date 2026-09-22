"""Keep the published site inside the ceiling that arrives first.

**The concept is adaptive pruning, and `docs/concepts/adaptive-pruning.md` is
where it is decided.** Adaptive because every store answers one question for
itself - what a reader loses when its oldest entry goes - and the answer picks
one of four policies: a ledger folds, a lookup deletes, an asset deletes, a
record is kept. That page carries the deciding rule, the five properties every
deletion below obeys, and the register naming every artefact this project writes
against its policy. What follows here is how each policy is built rather than
why it is the right one.

The 1 GB Pages cap is the earliest hard limit this project meets, and it is met
by images rather than by text. So this does two separate things, and they are
deliberately not the same thing:

- **The alarm** measures the built bundle - the tree the deploy uploads - and
  says when it is approaching the ceiling. It is on from the first run, long
  before anything is ever deleted, because measuring the ceiling is what turns a
  policy into a decision rather than a reaction.
- **The prune** removes rendered visuals older than a configured window. It
  ships disabled, in dry-run, behind a per-run delete fuse.

**The alarm and the cap are two instruments and they stay apart.**
`retention.site_budget_mb` is the alarm: it prints and stops nothing.
`retention.pages_hard_cap_mb` is the cap: past it the step fails, because past
it the bytes cannot be published at all. Merging them would leave one number
doing a job it can only do badly - a warning nobody can ignore, or a failure
that arrives with no notice. The cap is a knob in one direction only. Its field
is bounded by `PAGES_HARD_CAP_MB`, the platform's own ceiling, so a config edit
can make this gate stricter and can never make it looser (Guardrail #2).

**The alarm measures the built bundle and never the committed payload tree.**
Those are two different trees and they grow at different rates, so one cannot
stand in for the other. Measured 2026-08-27 on this checkout: the payload tree
under `frontend/public/digest/` was 7,027,075 bytes while the built site was
128,064,853 - eighteen times larger, and the eighteen was twenty-one the day
before. The alarm used to watch the payload tree, so it could not have fired
until the site was already six times past the cap. A green light on the wrong
tree is worse than no light, because a green light gets read as safety.

Three rules the prune obeys, each one a way this goes wrong otherwise:

- **Age only, never size.** A size-triggered prune deletes most on the day the
  site is largest, which is the day the reader has most to read.
- **Visuals only, never a day.** The digest payload is the record that a day
  happened. Deleting text to save bytes trades the whole archive for a rounding
  error.
- **A fuse.** An off-by-one in a date parse must not eat the archive, so no run
  may delete more than a configured number of files.
- **A record.** Every pass appends one row to `state/visual-prunes.csv`, and that
  row carries `skipped_by_fuse` beside `deleted`. The fuse caps `deleted`, so on
  its own it is the same number on a run that finished its backlog and on one
  that could not get near it. Only the pair says which, and the pass runs and
  reports on every run - including today's, where the policy is off and nothing
  is a candidate - so the day it starts working is visible in a committed file
  rather than in a job log.

**A level is not a date, and only a date answers the ceiling question.** The
alarm used to print one megabyte figure and one headroom figure, and neither is
a rate, so neither says when. What says when is bytes per published item times
the items a day may publish, divided into the headroom. Three things follow from
that and they are the rest of this module: `by_directory`, so a directory that
grew can be named rather than inferred from one moving sum;
`bytes_per_published_item`, because a rate over whole days moves when the item
mix moves and a rate over items does not; and `days_to_alarm` and `days_to_cap`,
which are the answer the question was always asking for.

**The telemetry fold is the third thing here, and it takes two files at once.**
`state/item-health/` is the census, and it grew at a measured 211,742 bytes a
published day on 2026-08-30 with nothing bounding it.
`observability.item_health_full_grain_months` is where a month stops being kept
item by item: past it the month is folded to one row per (date, stage), the
full-grain shard is deleted, and the browser's copy of that same month under
`frontend/public/telemetry/` goes with it. It is fourteen months because
`console.max_window_days` is 366, `ledger.shards_in_window` walks 367 inclusive
days, and those days can fall in fourteen calendar months - a window ending on
the first of a month starts on the last day of another. The aggregate is kept
forever by default, because a downsampled year costs kilobytes and deleting it
would make a year-over-year comparison unanswerable -
`observability.item_health_aggregate_keep_months` is the escape hatch and is
null. Those two names are what this module reads; the single age they replaced
was removed on 2026-09-03, once every reader had moved onto them.

**The private record and its browser copy go together, in that order.**
`frontend/public/telemetry/<YYYY-MM>.csv` is the projection a reader's browser
fetches, and `observability.public_telemetry_keep_months` is its own age - the
config refuses any value but the ledger's own, so the two can never come apart
by an edit. A copy that outlived its source would be a published rate nobody
could check against the rows behind it. The copy is named before anything is
deleted, so a dry run prints the file a live run removes rather than a list
assembled from what the deletion happened to reach; and a copy whose source an
earlier interrupted run already folded away is caught by the same pass, which is
why that pass walks the published tree rather than the shards it just folded.

**Feed health is deleted rather than folded, and that is the fourth thing.**
`state/feed-health/` is one row per feed per run. The quarantine reads 31 days
(`ledger.HEALTH_WINDOW_DAYS`) and the console reaches at most
`console.max_window_days`, so no summary of a month past
`observability.feed_health_keep_months` has a reader - and inventing one would
persist a shape nothing consumes, for ever. The ledger files by day and that
age is a month, so the prune takes a month's day files whole and names each one
it removed. `state/feed-retirements.csv` sits beside that directory and is never
a candidate: it carries no time window at all, and a run that forgot a retired
address would start asking a dead one again.

**The seen prune is the fifth thing, and it folds nothing on purpose.**
`state/seen/` is a lookup rather than a measurement: `ledger.load_seen` opens
the day files `day_partition.days_in_window(today, collect.seen_window_days)`
names and nothing else, so a day outside that set answers no question anybody
asks and its honest retention is deletion. A fold would be inventing a total
nobody reads. The keep-set is taken from the reader's own helper, and only days
*older* than it are deleted, so the retained set is a superset of the read set
whatever date the prune is handed. It is the one prune here whose boundary is a
day rather than a month, because it is the one whose knob is counted in days.

**The score archive is the sixth thing, and it is the only one that has to prove
itself twice.** `state/scores/` is the largest store here - 5,335 rows in
4,266,655 bytes on 2026-09-03 - and it is neither a lookup nor a set of timings:
it is the evidence behind every published quality claim, and it is what stops an
old measurement being scored again as if it were new. So a month past
`observability.scores_full_grain_months` is summarised into
`state/score-archive/<YYYY-MM>.json` (`idhazh.evals.archive`), the file is read
back through its contract, and the summary is reconciled field by field against
a second reading of the shard before the shard is unlinked. The telemetry fold
above checks that what it wrote reads back; this checks that as well, and then
checks that what reads back still describes the file it is about to delete.

**The visual fold is the seventh thing, and today it is the fold and not the
pass.** `state/visuals/` takes one row per attempt at a picture, and
`observability.visuals_full_grain_months` is where a month stops being readable
attempt by attempt. `fold_visual_month` is the arithmetic that replaces it: one
row per `(date, decision, none_reason, rejection_reason, potential_primary,
family, element_band, downgrade_depth)` group, carrying the counts a keep rate
needs and the spread of the two measured columns. What is deliberately absent is
a `prune_visuals` beside the six passes above, and the reason is that nothing
writes the store yet: a pass over a directory no run creates would walk an empty
tree on every run and report a policy working, which is a green light on the
wrong tree - the failure this module already learned once from the alarm. The
key is settled now because the fold deletes the shard and cannot be revised; the
pass lands with the writer.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Final, NamedTuple, NoReturn

from idhazh import assemble, day_partition, day_shards, ledger, month_partition, telemetry
from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.retention import PAGES_HARD_CAP_MB, RetentionConfig
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow, percentile
from idhazh.contracts.visual_decision import VisualState
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.contracts.visual_telemetry import VisualAggregateRow, VisualAttemptRow, band_of
from idhazh.evals import archive as score_archive
from idhazh.evals import writer as score_writer
from idhazh.telemetry.publish import public_telemetry

BYTES_PER_MB: Final = 1024 * 1024

#: Where the built tree keeps the day payloads, relative to the tree root.
_STAGED_DIGEST_DIRNAME: Final = "digest"


@dataclass(frozen=True, slots=True)
class SiteSize:
    bytes_used: int
    files: int
    #: Bytes under each top-level child of the measured tree, largest first when
    #: read back through `heaviest_directories`. One sum cannot say whether the
    #: visuals grew or the telemetry did; this can.
    by_directory: dict[str, int] = field(default_factory=dict)
    #: Items the same tree carries. Counted from the measured tree and never
    #: from a second one - that pairing is the whole lesson of this module.
    published_items: int = 0

    @property
    def megabytes(self) -> float:
        return self.bytes_used / BYTES_PER_MB

    @property
    def bytes_per_published_item(self) -> float:
        """The stable unit. A day rate moves when the item mix moves; this does not.

        Measured 2026-08-29 over seven mature days: 24,378 bytes an item, spread
        23,066 to 26,538, while the day rate moved by a factor of six across the
        same days because two of them published 117 and 212 items where the ones
        behind them published 731.

        It raises on nothing published rather than returning zero. Zero is the
        number that makes an empty tree read as a site that will never grow.
        """
        if self.published_items <= 0:
            raise ValueError(
                "no published items in the measured tree, so there is no rate and "
                "no runway. A rate of zero reads as a site that never grows"
            )
        return self.bytes_used / self.published_items

    def minus(self, root: Path, removed: Mapping[Path, int]) -> SiteSize:
        """This total once those files have left the tree. It reads no file.

        The maintained total (Guardrail #12). A pass that deletes already knows what it
        removed and how big each one was, so asking the whole tree again is a walk
        that grows with the archive to learn a number the caller is holding.

        Each entry names a file and the bytes it held. The caller reads the size
        while the file is still there, because a file that has gone cannot be
        asked, and passes only the files that really went - a total that subtracts
        a deletion which did not happen has nothing to disagree with it.

        `measure` stays the audit: run it and the two have to agree, which is what
        `test_a_retracted_deletion_equals_an_independent_walk` holds.
        """
        by_directory = dict(self.by_directory)
        files = self.files
        for path, size in removed.items():
            parts = path.relative_to(root).parts
            if len(parts) == 1:
                # A file directly under the root is its own entry, so the entry
                # goes with the file - which is what a fresh walk would report.
                by_directory.pop(parts[0], None)
            else:
                # `unlink` never removes the directory, so its entry survives at
                # whatever is left, down to zero.
                by_directory[parts[0]] = by_directory.get(parts[0], 0) - size
            files -= 1
        return SiteSize(sum(by_directory.values()), files, by_directory, self.published_items)


def measure(root: Path, *, published_items: int = 0) -> SiteSize:
    """Walk the whole tree and read every file's size. The audit, not the ordinary path.

    **This read grows with the tree, deliberately, and that is what it is for.**
    It is the independent reading a maintained total is checked against, and the
    only honest way to certify a tree this process did not write - the built
    bundle comes out of `npm run build`, so nothing here saw those bytes land and
    nothing here can carry a total forward across them. A pass that both writes
    and deletes inside one process carries its total with `SiteSize.minus`
    instead and calls this once.

    Measured 2026-09-07 on an Intel Core i7-1265U over `frontend/public/digest/`:
    443 files, 25,070,521 bytes, 276.8 ms best and 352.3 ms worst over five runs.

    It streams rather than listing every path first, so the walk costs one file's
    memory instead of the whole tree's.
    """
    if not root.exists():
        return SiteSize(0, 0)
    by_directory: dict[str, int] = {}
    files = 0
    for child in sorted(root.iterdir()):
        if child.is_file():
            by_directory[child.name] = child.stat().st_size
            files += 1
        elif child.is_dir():
            inside = 0
            counted = 0
            for path in child.rglob("*"):
                if path.is_file():
                    inside += path.stat().st_size
                    counted += 1
            by_directory[child.name] = inside
            files += counted
    return SiteSize(sum(by_directory.values()), files, by_directory, published_items)


def count_published_items(root: Path) -> int:
    """Items across every day payload staged into the measured tree.

    Read from the built tree rather than from `frontend/public/digest/` or from a
    run manifest, because bytes and items have to come from one corpus. The two
    trees are eighteen times apart and a prune would move one before the other,
    so a rate taken across them divides a numerator by somebody else's
    denominator.

    **This read grows with the archive**: one more published day is one more
    payload to open and parse. It stays that way for the same reason `measure`
    does - the tree is written by the site build rather than by this process, so
    there is no total to carry - and it runs once a build, in the step that has
    just spent minutes producing the tree it reads.
    """
    staged = root / _STAGED_DIGEST_DIRNAME
    if not staged.is_dir():
        return 0
    total = 0
    for payload in staged.rglob("digest.json"):
        day = json.loads(payload.read_text(encoding="utf-8"))
        items = day.get("items")
        if isinstance(items, list):
            total += len(items)
    return total


def heaviest_directories(size: SiteSize, limit: int = 0) -> list[tuple[str, int]]:
    """Top-level children largest first, so the line names what grew."""
    ordered = sorted(size.by_directory.items(), key=lambda entry: (-entry[1], entry[0]))
    return ordered if limit <= 0 else ordered[:limit]


def over_budget(size: SiteSize, config: RetentionConfig) -> bool:
    """The alarm fires below the platform's ceiling, so there is room to act."""
    return size.megabytes > config.site_budget_mb


def over_cap(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> bool:
    """Past the cap in force, which is where reporting stops being enough.

    `cap_mb` is a parameter for the same reason `prune` takes `today`: a test has
    to be able to cross the line without building a one-gigabyte fixture. The
    step passes `retention.pages_hard_cap_mb` down from config, and the default
    here is the platform's own ceiling, which is the most that knob may name.
    """
    return size.megabytes > cap_mb


def headroom_mb(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> float:
    return cap_mb - size.megabytes


def daily_growth_bytes(size: SiteSize, items_per_day: int) -> float:
    """What one more published day costs, at the item ceiling in force.

    `items_per_day` is `run.safety_ceiling_per_run` and not an average of the
    days on disk. A day that published 117 items is not evidence that the next
    one will; the ceiling is the most a day is allowed to cost, which is the
    figure a worst-case runway needs (Guardrail #10).
    """
    if items_per_day <= 0:
        raise ValueError("a day that may publish no items has no growth rate and no runway")
    return size.bytes_per_published_item * items_per_day


def days_to_alarm(size: SiteSize, config: RetentionConfig, items_per_day: int) -> float:
    """Published days from here to the alarm point. Negative once it is behind us."""
    left = (config.site_budget_mb - size.megabytes) * BYTES_PER_MB
    return left / daily_growth_bytes(size, items_per_day)


def days_to_cap(size: SiteSize, items_per_day: int, *, cap_mb: int = PAGES_HARD_CAP_MB) -> float:
    """Published days from here to the platform ceiling. The runway."""
    return headroom_mb(size, cap_mb=cap_mb) * BYTES_PER_MB / daily_growth_bytes(size, items_per_day)


def budget_alarm(size: SiteSize, config: RetentionConfig) -> str | None:
    """The alarm's words, or None when the built site is inside budget.

    Below the cap the alarm only reports - it fails no build and deletes nothing -
    so the run that meets it needs a line it can act on: the size, the alarm point
    it crossed, and the headroom left to the cap. Both numbers come from the same
    config, so an operator who lowers the cap sees the shorter headroom here too.
    """
    if not over_budget(size, config):
        return None
    cap_mb = config.pages_hard_cap_mb
    return (
        f"published site is {size.megabytes:.0f} MB, past the "
        f"{config.site_budget_mb} MB alarm point, with "
        f"{headroom_mb(size, cap_mb=cap_mb):.0f} MB left to the {cap_mb} MB Pages cap"
    )


def cap_breach(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> str | None:
    """The words for a site that can no longer be published, or None.

    This one fails the build, and the alarm above does not. The split is the
    whole point: 800 MB still deploys, so failing there would stop publishing
    weeks before it had to, and the reader loses a working site to a budget that
    still had room. Past the cap the site is outside what Guardrail #2 allows, and
    failing in the job that measured it names the cause - a deploy that refuses
    the bytes names nothing.
    """
    if not over_cap(size, cap_mb=cap_mb):
        return None
    return (
        f"built site is {size.megabytes:.0f} MB in {size.files} files, past the "
        f"{cap_mb} MB Pages cap. It cannot be published. Prune, or shrink what a "
        f"published day costs"
    )


def cutoff(today: date, months: int) -> date | None:
    """None means retention is off, which is what ships."""
    if months < 0:
        return None
    return today - timedelta(days=months * 30)


def visuals_older_than(root: Path, limit: date) -> list[Path]:
    """Rendered visuals under dated directories older than the cutoff.

    Ordered by path, the same order a sort over the whole tree would give,
    because `prune` hands the fuse the first `max_deletes_per_run` of this list.
    The order decides which files a capped run takes and which it leaves for the
    next one, so a reordering here would quietly change what a backlog run does.

    Only the expired days are opened. Measured on a built 400-day tree with
    3,600 files, 2026-09-07, Intel Core i7-1265U: 261 directory listings against
    417 for the sort-then-filter shape this replaced - and the 261 does not move
    when 140 more days and 3,080 more files are published inside the window,
    which is what the archive does every day nobody writes any code (Guardrail #12).
    """
    found: list[Path] = []
    for _, folder in _dated_days(root, before=limit):
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


def _dated_days(root: Path, *, before: date | None = None) -> Iterator[tuple[date, Path]]:
    """Published day directories, oldest first, read out of their names.

    The tree is `<YYYY>/<MM>/<DD>` (`assemble.day_dir`), so a day's date is in
    its path and a caller who wants a span of days can have it without opening a
    single one. That is the whole reason this exists. The scan above used to sort
    every path under the root and then filter, so selecting the handful of
    expired days cost a listing of all of them - a bill that arrived every run,
    larger each time, for an answer no code change had touched (Guardrail #12).
    `before` prunes by name at each level: a year whose January already sits at
    or past the cutoff, and a month whose first does, cannot hold an expired day
    and are never opened.

    **What this still reads, and how that grows.** The root once, then one
    listing per year and one per month that could hold a day older than `before`,
    then one per day it yields. So it grows with the BACKLOG - the days the
    policy has not caught up with - at one listing a month, and it shrinks as the
    prune works. A bounded input cannot answer the question: "every day older
    than the cutoff" has no lower bound but the archive's own first day, and the
    per-run fuse deliberately caps what a pass DELETES rather than what it
    counts, because the backlog left behind is what the committed row exists to
    report.

    **A name inside the dated tree that is not a date is a fault, not a skip.**
    Below a year directory the layout is ours, so a name this cannot read means
    something else is writing there, and a cleanup that passed over it quietly
    would leave files it can never account for. At the root the rule stops and
    nothing is refused: a root is allowed to hold things that are not the day
    tree at all, and one that does is left alone rather than pruned or rejected.
    """
    if not root.is_dir():
        return
    for year_dir in sorted(root.iterdir()):
        if not _stamped(year_dir.name, 4) or not year_dir.is_dir():
            continue
        year = int(year_dir.name)
        try:
            opens = date(year, 1, 1)
        except ValueError:
            continue
        if before is not None and opens >= before:
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not _stamped(month_dir.name, 2) or not month_dir.is_dir():
                _refuse(month_dir, root, "month")
            month = int(month_dir.name)
            if not 1 <= month <= 12:
                _refuse(month_dir, root, "month")
            if before is not None and date(year, month, 1) >= before:
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not _stamped(day_dir.name, 2) or not day_dir.is_dir():
                    _refuse(day_dir, root, "day")
                try:
                    published = date(year, month, int(day_dir.name))
                except ValueError:
                    _refuse(day_dir, root, "day")
                if before is None or published < before:
                    yield published, day_dir


def _visuals_in(folder: Path) -> list[Path]:
    """The published visuals in one day, by name.

    **A visual is a file named for an item**, which is the same rule
    `render.write.assets_in_day` uses and the same rule that decides where a
    writer puts one. It was a set of image suffixes until 2026-09-13, when the
    reader's browser took over the drawing and a visual stopped being an image -
    and adding `.json` to that set would have made `digest.json` and `run.json`
    candidates, which is the record that the day happened and the one thing this
    module may never delete.

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


def oldest_visual(root: Path) -> date | None:
    """The published day of the oldest rendered visual still on disk, or None.

    Read against the cutoff, this is what says whether the policy has caught up:
    while it is older than the cutoff there is backlog left, whatever one run's
    `deleted` says. None means the tree carries no visual at all, which is a
    different fact from "the oldest one is recent" and is spelled differently.

    This is the one that costs on every run that has ever shipped, and it did not
    stop costing when the window took a value. `image_months` is 13 from
    2026-09-13 and the oldest visual on disk is weeks old, so `visuals_older_than`
    returns nothing until 2027 - and `prune` still asks this on every path
    through it, including the early
    return. The answer is the first day that still holds a picture, so it stops
    at that day: 4 directory listings on a built 400-day tree against 417 for the
    shape it replaced, 2026-09-07, Intel Core i7-1265U.
    """
    for published, folder in _dated_days(root):
        if _visuals_in(folder):
            return published
    return None


@dataclass(frozen=True, slots=True)
class PruneResult:
    """What one cleanup pass found, took, and left behind.

    `skipped_by_fuse` was computable from the first day and thrown away every
    run. It is the difference between a run that finished its backlog and a run
    that could not get near it, and `deleted` cannot show it because the fuse
    caps `deleted` at the same number in both cases.

    It means the same thing on a dry run as on a live one - the candidates the
    fuse would not have let this run reach - so it is never inflated by the
    deletions a dry run declined to make. `dry_run` is the field that says
    nothing was deleted.
    """

    considered: int
    deleted: int
    dry_run: bool
    fuse_tripped: bool
    skipped_by_fuse: int
    bytes_reclaimed: int
    cutoff_date: date | None
    oldest_kept: date | None
    bytes_before: int
    bytes_after: int


def prune(
    root: Path, config: RetentionConfig, today: date, *, dry_run: bool = False
) -> PruneResult:
    """Delete nothing unless configured to, and never more than the fuse allows.

    `dry_run` is an override the caller adds on top of `retention.dry_run`, never
    one that cancels it: the step passes its own flag and either source is enough
    to make the pass report-only. There is no argument that turns deletion on.

    The tree is read once, at the top, and the after-total is that reading with
    the deleted files retracted from it (`SiteSize.minus`). It used to be two
    whole-tree readings, so learning the size of two pictures cost a second walk
    of everything ever published - the cost Guardrail #12 refuses, and it rose every
    time a day was added. The reason the old shape existed still holds and is
    kept: a total that subtracts what the pass *meant* to delete would still be
    written when an unlink did not happen, so a file is retracted only once it
    has actually gone. `bytes_reclaimed` is then what left the tree rather than
    what the loop intended, and `test_the_after_total_counts_only_the_files_that_actually_left`
    is that distinction.
    """
    pretend = dry_run or config.dry_run
    before = measure(root)
    limit = cutoff(today, config.image_months)
    if limit is None:
        return PruneResult(
            considered=0,
            deleted=0,
            dry_run=pretend,
            fuse_tripped=False,
            skipped_by_fuse=0,
            bytes_reclaimed=0,
            cutoff_date=None,
            oldest_kept=oldest_visual(root),
            bytes_before=before.bytes_used,
            bytes_after=before.bytes_used,
        )

    candidates = visuals_older_than(root, limit)
    allowed = candidates[: config.max_deletes_per_run]
    skipped = len(candidates) - len(allowed)
    if pretend:
        return PruneResult(
            considered=len(candidates),
            deleted=0,
            dry_run=True,
            fuse_tripped=skipped > 0,
            skipped_by_fuse=skipped,
            bytes_reclaimed=0,
            cutoff_date=limit,
            oldest_kept=oldest_visual(root),
            bytes_before=before.bytes_used,
            bytes_after=before.bytes_used,
        )

    # One reading of each file the fuse lets through, taken while it is still
    # there. The fuse bounds this, so it does not grow with the archive.
    gone: dict[Path, int] = {}
    for path in allowed:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        path.unlink(missing_ok=True)
        if not path.exists():
            gone[path] = size
    after = before.minus(root, gone)
    return PruneResult(
        considered=len(candidates),
        deleted=len(allowed),
        dry_run=False,
        fuse_tripped=skipped > 0,
        skipped_by_fuse=skipped,
        bytes_reclaimed=before.bytes_used - after.bytes_used,
        cutoff_date=limit,
        oldest_kept=oldest_visual(root),
        bytes_before=before.bytes_used,
        bytes_after=after.bytes_used,
    )


@dataclass(frozen=True, slots=True)
class FragmentPruneResult:
    """Which days' blocks went and what they weighed.

    There is no kept-count. Answering it means walking every day still on disk,
    which is the cost this pass exists to stop the tree charging (Guardrail
    #12), and the number it would print is the archive's own size rather than
    anything about this pass.
    """

    deleted: tuple[str, ...]
    bytes_freed: int
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.deleted)


def prune_digest_fragments(
    state_dir: Path, config: RetentionConfig, today: date, *, dry_run: bool = False
) -> FragmentPruneResult:
    """Delete the per-run blocks of every day past the window the day itself keeps.

    A block is what one run of a day published, and the published day is
    assembled out of every block of its date. Once the day is old enough that
    nothing will be added to it, the blocks are a second full copy of every
    story with no reader and no writer - an archive that grows one day at a time
    and answers nothing (Guardrail #12).

    The window is `retention.image_months`, which is the day's own: a date whose
    pictures may still be deleted is a date whose blocks may still be needed, and
    one rule for the day means the two can never disagree about when it closed.
    The published day itself is never deleted here or anywhere - it is the record
    that the day happened.

    `dry_run` is an override the caller adds on top of `retention.dry_run`,
    exactly as `prune` takes it, so either source is enough to make the pass
    report-only. `deleted` carries the committed POSIX relpath of each file, so a
    dry run names what a live run would take (section 2).

    Cover: the days already past the window, and not the archive. `_dated_days`
    prunes by name at the year and the month, so a date inside the window is
    never opened - the cost follows the backlog this pass has to clear and
    shrinks as it clears it.
    """
    root = state_dir / assemble.FRAGMENTS_DIRNAME
    limit = cutoff(today, config.image_months)
    if limit is None or not root.is_dir():
        return FragmentPruneResult((), 0, dry_run or config.dry_run)

    pretend = dry_run or config.dry_run
    deleted: list[str] = []
    freed = 0
    for _published, folder in _dated_days(root, before=limit):
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            deleted.append(f"{ledger.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}")
            freed += path.stat().st_size
            if not pretend:
                path.unlink()
        if not pretend:
            day_partition.drop_empty_day_dirs(folder)

    return FragmentPruneResult(deleted=tuple(deleted), bytes_freed=freed, dry_run=pretend)


def prune_row(
    result: PruneResult, config: RetentionConfig, *, date_stamp: str, run_id: str
) -> VisualPruneRow:
    """The committed account of one cleanup pass.

    Built here rather than in the caller so the row and the result can never
    describe two different runs, and so the contract's own arithmetic checks
    whatever this module produces.
    """
    return VisualPruneRow(
        version=VisualPruneRow.schema_version(),
        date=date_stamp,
        run_id=run_id,
        policy_months=config.image_months,
        max_deletes_per_run=config.max_deletes_per_run,
        dry_run=result.dry_run,
        cutoff_date=result.cutoff_date.isoformat() if result.cutoff_date else None,
        candidates_found=result.considered,
        deleted=result.deleted,
        skipped_by_fuse=result.skipped_by_fuse,
        fuse_tripped=result.fuse_tripped,
        bytes_reclaimed=result.bytes_reclaimed,
        oldest_kept=result.oldest_kept.isoformat() if result.oldest_kept else None,
        payload_bytes_before=result.bytes_before,
        payload_bytes_after=result.bytes_after,
    )


# --- The telemetry fold ------------------------------------------------------


def oldest_month_kept(today: date, months: int) -> str:
    """The oldest `YYYY-MM` stem that still stays at full grain.

    `month_partition` owns the arithmetic, because the published tree ages by
    the same boundary now and two copies of it is how one store deletes a month
    the other still serves. This name stays because every prune below reads by
    it and a rename would be a second change in the same commit.
    """
    return month_partition.oldest_month_kept(today, months)


def month_shards(directory: Path) -> list[Path]:
    """Every `<YYYY-MM>.csv` in a ledger directory, oldest first.

    Anything else in there is left alone. A directory this walks is one a prune
    deletes from, so it names what it recognises rather than deleting what it
    does not - and it recognises what `month_partition` recognises, which is the
    same thing `evals.writer` and `evals.archive` recognise. Those three used to
    hold three different answers, and `2025-13.csv` was left alone here and
    deleted there.
    """
    return month_partition.month_files(directory, ".csv")


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


def compact_month(rows: list[ItemHealthRow]) -> list[TelemetryAggregateRow]:
    """One month of full-grain rows, as one row per (date, stage).

    Ordered by date and then by the stage's own pipeline order, so the file a
    reader opens reads down the funnel rather than down the alphabet.
    """
    grouped: dict[tuple[str, ItemStage], list[ItemHealthRow]] = {}
    for row in rows:
        grouped.setdefault((row.date, row.stage), []).append(row)

    order = list(ItemStage)
    folded: list[TelemetryAggregateRow] = []
    for day, stage in sorted(grouped, key=lambda key: (key[0], order.index(key[1]))):
        members = grouped[(day, stage)]
        elapsed = sorted(
            value for value in (_elapsed_ms(member) for member in members) if value is not None
        )
        folded.append(
            TelemetryAggregateRow(
                version=TelemetryAggregateRow.schema_version(),
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


@dataclass(frozen=True, slots=True)
class TelemetryPruneResult:
    """What one fold did, in the words a log line needs."""

    folded: tuple[str, ...]
    rows_folded: int
    aggregate_rows: int
    hard_deleted: tuple[str, ...]
    #: Every `state/item-health/<YYYY>/<MM>/<DD>.csv` the fold took, POSIX and
    #: relative to the repository, oldest first. Carried rather than derived from
    #: `folded`, because a month is a directory of day files now: a caller that
    #: spelled `<month>-01` would name a file the ledger may never have held, and
    #: the list a dry run prints has to be the list a live run removes, file for
    #: file.
    days_removed: tuple[str, ...]
    #: Months whose browser copy under `frontend/public/telemetry/` went. Named
    #: apart from `folded` because the two sets come apart: a copy whose source
    #: month an earlier interrupted run already folded away is deleted here with
    #: nothing left to fold beside it.
    public_deleted: tuple[str, ...]
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.folded or self.hard_deleted or self.public_deleted)


def _expired_public_copies(public_root: Path | None, boundary: str) -> tuple[str, ...]:
    """Every published month below the boundary, named before anything is deleted.

    Read up front so the list a dry run prints is the list a live run removes,
    file for file. That list is what a person reads before turning the deletion
    on, so it may not be assembled from what the deletion happened to reach.

    It walks the published tree rather than the shards being folded, which is
    what catches a copy whose source is already gone. Only `<YYYY-MM>.csv` is
    recognised - a directory this deletes from names what it knows.
    """
    if public_root is None:
        return ()
    return tuple(copy.stem for copy in month_shards(public_root) if copy.stem < boundary)


def prune_telemetry(
    state_dir: Path,
    config: ObservabilityConfig,
    today: date,
    *,
    public_root: Path | None = None,
    dry_run: bool = False,
) -> TelemetryPruneResult:
    """Fold every out-of-window item-health month, then delete its days and its copy.

    The ledger files by day and the aggregate that replaces it files by month, so
    this is where the two grains meet: `day_partition.days_by_month` groups the
    day files, and a month is folded whole or not at all. A month's input is at
    most 31 files, so the fold stays a store-bounded read.

    Order matters and it is the whole safety argument: the aggregate is written
    and read back before a single day file is unlinked, and the browser's copy of
    that month is unlinked only after the days it copies. Nothing is deleted on
    the strength of a write nobody checked.

    `public_root` is `frontend/public/telemetry/`. None means there is no site
    beside this state tree, so there is no copy to consider - and it is the
    default because a caller that names its own state tree and forgets this one
    must get nothing rather than the committed one.

    `item_health_aggregate_keep_months` is applied last and defaults to null,
    which means an aggregate is kept forever. Set, it must sit above
    `item_health_full_grain_months`, which the config contract enforces - so a
    month is never deleted before it is folded.
    """
    keep_from = oldest_month_kept(today, config.item_health_full_grain_months)
    public_deleted = _expired_public_copies(
        public_root, oldest_month_kept(today, config.public_telemetry_keep_months)
    )
    folded: list[str] = []
    days_removed: list[str] = []
    rows_folded = 0
    aggregate_rows = 0

    by_month = day_partition.days_by_month(state_dir / ledger.ITEM_HEALTH_DIRNAME)
    for month in sorted(by_month):
        if month >= keep_from:
            continue
        days = by_month[month]
        rows = [row for day in days for row in ledger.load_item_health_shard(day)]
        summary = compact_month(rows)
        folded.append(month)
        # Named before anything is written, so the dry run prints the same list
        # the live run removes.
        days_removed += [ledger.item_health_relpath(f"{month}-{day.stem}") for day in days]
        rows_folded += len(rows)
        aggregate_rows += len(summary)
        if dry_run:
            continue
        target = ledger.telemetry_aggregate_path(state_dir, month)
        ledger.write_telemetry_aggregate(target, summary)
        # Read back before the days go. A fold nobody verified is a deletion
        # nobody can undo.
        if ledger.load_telemetry_aggregate(target) != summary:
            raise ValueError(
                f"{ledger.telemetry_aggregate_relpath(month)} did not read back as it "
                f"was written, so the {len(days)} day files of {month} stay"
            )
        for day in days:
            day.unlink()
            day_partition.drop_empty_day_dirs(day)
        # Only a copy below its own configured age, so the set deleted is exactly
        # the set named above and never a month the published tree still owes a
        # reader.
        if public_root is not None and month in public_deleted:
            public_telemetry.shard_path(public_root, month).unlink(missing_ok=True)

    # Whatever the loop above did not reach. On the scheduled path this is empty:
    # every copy below the boundary has a shard beside it, and the pair went
    # together. It is not empty after a run that stopped between the two.
    if public_root is not None and not dry_run:
        for stem in public_deleted:
            public_telemetry.shard_path(public_root, stem).unlink(missing_ok=True)

    hard_deleted: list[str] = []
    if config.item_health_aggregate_keep_months is not None:
        delete_from = oldest_month_kept(today, config.item_health_aggregate_keep_months)
        for aggregate in month_shards(state_dir / ledger.TELEMETRY_AGGREGATE_DIRNAME):
            if aggregate.stem >= delete_from:
                continue
            hard_deleted.append(aggregate.stem)
            if not dry_run:
                aggregate.unlink()

    return TelemetryPruneResult(
        folded=tuple(folded),
        rows_folded=rows_folded,
        aggregate_rows=aggregate_rows,
        hard_deleted=tuple(hard_deleted),
        days_removed=tuple(days_removed),
        public_deleted=public_deleted,
        dry_run=dry_run,
    )


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

    **It can only shrink the store.** Every group holds at least one attempt, so
    the row count never rises, and the folded row is narrower than the attempt
    row it replaces - it drops the run, the item and the join key and adds
    nothing per attempt. The pathological month in which every attempt lands in
    its own group folds to the same number of rows, each one smaller, which is
    the fold buying nothing rather than costing something.

    Ordered by the key, so a folded month reads down the days and then down the
    causes.
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


# --- The feed-health shards --------------------------------------------------


@dataclass(frozen=True, slots=True)
class FeedHealthPruneResult:
    """Which months of a day-filed ledger went, and what they weighed.

    Named for the first store that needed it, and shared by every prune whose
    knob is months and whose files are days - `prune_host_fingerprint` is the
    other one today.
    """

    deleted: tuple[str, ...]
    bytes_freed: int
    kept: tuple[str, ...]
    #: Every `<YYYY>/<MM>/<DD>.csv` this took, POSIX and relative to the
    #: repository, oldest first. Carried rather than derived from `deleted`,
    #: because a month is a directory of day files now: a caller that spelled
    #: `<month>-01` would name a file the ledger may never have held, and the
    #: list a dry run prints has to be the list a live run removes, file for
    #: file.
    days_removed: tuple[str, ...]
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.deleted)


def prune_feed_health(
    state_dir: Path,
    config: ObservabilityConfig,
    today: date,
    *,
    dry_run: bool = False,
) -> FeedHealthPruneResult:
    """Delete every feed-health month past its own age, and fold nothing.

    A row here is one feed's result on one run. The quarantine reads
    `ledger.HEALTH_WINDOW_DAYS` (31) and the console reaches at most
    `console.max_window_days`, so nothing asks a month older than
    `observability.feed_health_keep_months` for anything - and a summary of what
    a feed did fourteen months ago would be a shape nothing consumes, persisted
    for ever.

    The ledger files by day and this boundary is a month, so
    `day_partition.days_by_month` groups the day files and a month goes whole or
    not at all. That keeps the knob's unit the one it has always had while the
    files below it are days.

    **Older than the oldest month kept, never merely outside a window.** The
    boundary is a floor, so a run handed a date in the past deletes less rather
    than deleting the live day. That is the rule `prune_seen` states at length
    and it is the same rule here.

    `state/feed-retirements.csv` is not in this directory and is never a
    candidate. It carries no time window: one row is one address a server said
    was gone, and a run that forgot it would start asking a dead address again.
    """
    boundary = oldest_month_kept(today, config.feed_health_keep_months)
    deleted: list[str] = []
    days_removed: list[str] = []
    kept: list[str] = []
    freed = 0

    by_month = day_partition.days_by_month(state_dir / ledger.HEALTH_DIRNAME)
    for month in sorted(by_month):
        if month >= boundary:
            kept.append(month)
            continue
        deleted.append(month)
        for day in by_month[month]:
            # Named and weighed before anything is unlinked, so the dry run
            # prints the same list the live run removes.
            days_removed.append(ledger.health_relpath(f"{month}-{day.stem}"))
            freed += day.stat().st_size
            if not dry_run:
                day.unlink()
                day_partition.drop_empty_day_dirs(day)

    return FeedHealthPruneResult(
        deleted=tuple(deleted),
        bytes_freed=freed,
        kept=tuple(kept),
        days_removed=tuple(days_removed),
        dry_run=dry_run,
    )


# --- The host-fingerprint shards ---------------------------------------------


def prune_host_fingerprint(
    state_dir: Path,
    config: ObservabilityConfig,
    today: date,
    *,
    dry_run: bool = False,
) -> FeedHealthPruneResult:
    """Delete every host-fingerprint month past its own age, and fold nothing.

    A row here is one job's silicon on one run - the machine the platform handed
    us and what its model server counted. Ten jobs a run each write one, so the
    tree grows every run and nothing else bounds it (Guardrail #12).

    Deleted rather than folded, for the reason `prune_feed_health` gives: a total
    over a month fourteen months back names no machine, so the fold would be a
    shape nothing consumes, persisted for ever. The month that matters is already
    published under `frontend/public/machine/`.

    Reuses `FeedHealthPruneResult` rather than minting a shape with the same five
    fields and a different name, the way `prune_trial_state` reuses
    `TracePruneResult`. The month knob over a day tree is the same problem, so it
    is the same answer.

    `observability.host_fingerprint_keep_months` is null by default, and null
    means never: this then names no boundary and removes nothing. Set, it may not
    sit below `public_machine_keep_months`, which the contract refuses - the
    published shard is folded from this ledger.

    **Older than the oldest month kept, never merely outside a window.** The
    boundary is a floor, so a run handed a date in the past deletes less rather
    than deleting the live day. That is the rule `prune_seen` states at length
    and it is the same rule here.

    It walks the tree to find what to delete, so the walk is what bounds the
    collection and its cost falls as it works - a day it removes is a day no
    later pass opens. That is the argument `prune_counterfactual_scores` already
    makes for the same shape (`docs/concepts/growing-reads.md`, Guardrail #12).
    """
    if config.host_fingerprint_keep_months is None:
        return FeedHealthPruneResult((), 0, (), (), dry_run)

    boundary = oldest_month_kept(today, config.host_fingerprint_keep_months)
    deleted: list[str] = []
    days_removed: list[str] = []
    kept: list[str] = []
    freed = 0

    by_month = day_partition.days_by_month(state_dir / ledger.HOST_FINGERPRINT_DIRNAME)
    for month in sorted(by_month):
        if month >= boundary:
            kept.append(month)
            continue
        deleted.append(month)
        for day in by_month[month]:
            # Named and weighed before anything is unlinked, so the dry run
            # prints the same list the live run removes.
            days_removed.append(ledger.host_fingerprint_relpath(f"{month}-{day.stem}"))
            freed += day.stat().st_size
            if not dry_run:
                day.unlink()
                day_partition.drop_empty_day_dirs(day)

    return FeedHealthPruneResult(
        deleted=tuple(deleted),
        bytes_freed=freed,
        kept=tuple(kept),
        days_removed=tuple(days_removed),
        dry_run=dry_run,
    )


# --- The seen day files ------------------------------------------------------


@dataclass(frozen=True)
class SeenPruneResult:
    """Which seen day files went, and what they weighed.

    `deleted` and `kept` are both `state/seen/<YYYY>/<MM>/<DD>.csv`, POSIX and
    relative to the repository, oldest first. One unit rather than two, because
    this prune has no month in it at all: `collect.seen_window_days` is counted
    in days, so the boundary is a day and the file it names is the file it
    deletes. The two health prunes beside this one carry a second `days_removed`
    list precisely because their knobs are months and `deleted` has to stay a
    month to match.
    """

    deleted: tuple[str, ...]
    bytes_freed: int
    kept: tuple[str, ...]
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.deleted)


def prune_seen(
    state_dir: Path,
    *,
    today: str,
    within_days: int,
    dry_run: bool = False,
) -> SeenPruneResult:
    """Delete every seen day file the reader would no longer open.

    `ledger.load_seen` consults `day_partition.days_in_window(today, within_days)`
    and nothing else, so a day older than the oldest that names is already
    invisible to the pipeline - it is bytes in the working tree answering no
    question. Without this the ledger grows for ever at a rate nothing bounds:
    measured 2026-08-31, 356 KB a day after the address column came off, which
    is 32 MB over a 90-day window and no ceiling after that.

    The keep-set comes from the reader's own helper rather than from a second
    date calculation here. That is the safety argument: two calculations drift,
    and the day they drift this one deletes a file the next plan wanted.

    **The boundary is a day, and this is the one prune here where it is.** Every
    other store in this module is bounded by a knob counted in months, so its
    prune groups day files with `day_partition.days_by_month` and takes a month
    whole. `collect.seen_window_days` is counted in days, so there is no month to
    group by and the file the reader named is the file this keeps. The retained
    span is therefore exactly the window - where the month shards this replaced
    kept 90 to 120 days, because a whole shard survived if any of its days was in
    range.

    **Only what is older than that set goes, never what is newer.** The window
    is anchored on the date this is handed, and a run can be handed a date in
    the past - `--date` takes whatever it is given. Deleting everything outside
    the window would then delete the live day file, which is the one file every
    later plan opens. Deleting everything below the window's oldest day keeps
    the retained set a superset of the read set for every date rather than for
    today's, and it costs nothing: on the scheduled path the two sets are the
    same files.

    There is no fuse and no `max_deletes_per_run`. A day nobody reads is not
    the archive, and the picture pruner's fuse exists because a date-parse bug
    there eats published images - the worst case here is that the pipeline
    re-learns a first-sight date it had already forgotten.
    """
    # `days_in_window` always names the anchor's own day, so this is never the
    # minimum of an empty set.
    oldest_read = min(day_partition.days_in_window(today, within_days))
    deleted: list[str] = []
    kept: list[str] = []
    freed = 0

    for day in day_partition.day_files(state_dir / ledger.SEEN_DIRNAME):
        on = day_partition.date_of(day)
        if on >= oldest_read:
            kept.append(ledger.seen_relpath(on))
            continue
        # Named and weighed before anything is unlinked, so the dry run prints
        # the same list the live run removes.
        deleted.append(ledger.seen_relpath(on))
        freed += day.stat().st_size
        if not dry_run:
            day.unlink()
            day_partition.drop_empty_day_dirs(day)

    return SeenPruneResult(
        deleted=tuple(deleted),
        bytes_freed=freed,
        kept=tuple(kept),
        dry_run=dry_run,
    )


# --- The counterfactual score day files --------------------------------------


@dataclass(frozen=True)
class CounterfactualPruneResult:
    """Which counterfactual day files went, and what they weighed.

    The same shape as `SeenPruneResult` and for the same reason: this knob is
    counted in days too, so the boundary is a day and the file the reader named
    is the file this deletes. There is no month here to group by.
    """

    deleted: tuple[str, ...]
    bytes_freed: int
    kept: tuple[str, ...]
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.deleted)


def prune_counterfactual_scores(
    state_dir: Path,
    *,
    today: str,
    within_days: int,
    dry_run: bool = False,
) -> CounterfactualPruneResult:
    """Delete every counterfactual day file outside the window anyone reads.

    This ledger is appended to on every run and read only over a trailing window
    - `lens_weights.window_days` - so a day older than that window's oldest is
    bytes in the working tree answering no question. Without this prune it grows
    for ever at a rate nothing bounds, and the row that added it put the
    unbounded arithmetic in writing: about 180 rows a run and 900 a day, which
    is roughly 135 KB a day and 49 MB a year at 150 bytes a row (estimate; the
    measured width is in that row's pull request).

    The keep-set comes from `day_partition.days_in_window`, the same helper the
    reader consults, rather than from a second date calculation here. Two
    calculations drift, and the day they drift this one deletes a file a reader
    wanted.

    **Only what is older than that set goes, never what is newer**, for the
    reason `prune_seen` states at length: a run can be handed a date in the
    past, and deleting everything outside the window would then take the live
    day with it.

    There is no fuse. A day nobody reads is not the archive, and the worst case
    is that a later tuning pass has a shorter history to argue from - which is
    the same thing the window already decided.
    """
    oldest_read = min(day_partition.days_in_window(today, within_days))
    deleted: list[str] = []
    kept: list[str] = []
    freed = 0

    for day in day_partition.day_files(state_dir / ledger.COUNTERFACTUAL_SCORES_DIRNAME):
        on = day_partition.date_of(day)
        if on >= oldest_read:
            kept.append(ledger.counterfactual_scores_relpath(on))
            continue
        deleted.append(ledger.counterfactual_scores_relpath(on))
        freed += day.stat().st_size
        if not dry_run:
            day.unlink()
            day_partition.drop_empty_day_dirs(day)

    return CounterfactualPruneResult(
        deleted=tuple(deleted),
        bytes_freed=freed,
        kept=tuple(kept),
        dry_run=dry_run,
    )


# --- The trace tree ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TracePruneResult:
    """Which committed traces went, what they weighed, and how many stayed."""

    deleted: tuple[str, ...]
    bytes_freed: int
    kept: int
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.deleted)


def prune_traces(
    state_dir: Path,
    *,
    today: date,
    within_days: int,
    dry_run: bool = False,
) -> TracePruneResult:
    """Delete every committed trace older than the window, and fold nothing.

    A trace is a lookup an operator opens to walk one recent run step by step,
    not a measurement, so its honest retention is deletion: a fold would invent a
    total nobody reads (section 9.2, docs/concepts/telemetry.md). The record of a
    run is the span rollup beside it under `state/span-rollup/`; this is the
    evidence, kept only briefly.

    A file is kept while its published day is within `within_days` of `today` and
    goes once it is further back, so the last `within_days` days survive and
    everything older is removed. A file dated ahead of `today` - a back-dated run
    handed an older `--date` - is newer than the window and is kept, the same
    property `prune_seen` holds for the first-sight day files.

    There is no fuse and no max-per-run. A trace outside the window is not the
    archive, and the worst case is an operator losing a drill-down into a run
    that has already left the window - not a published byte, which is what the
    picture pruner's fuse exists to protect.

    `state/traces/` does not exist until `observability.tracing_enabled` is true,
    so on every run before that this returns at once having walked nothing.
    `deleted` carries the committed POSIX relpath of each file, so a dry run can
    name what a live run would remove (section 2); `kept` is a count, because a
    full window is many files and naming them all is noise.
    """
    root = state_dir / telemetry.TRACES_DIRNAME
    if not root.is_dir():
        return TracePruneResult((), 0, 0, dry_run)

    deleted: list[str] = []
    kept = 0
    freed = 0
    for path in sorted(root.rglob("*.jsonl")):
        published = telemetry.trace_date(path, root)
        if published is None:
            continue
        if (today - published).days < within_days:
            kept += 1
            continue
        deleted.append(f"{ledger.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}")
        freed += path.stat().st_size
        if not dry_run:
            path.unlink()

    return TracePruneResult(
        deleted=tuple(deleted),
        bytes_freed=freed,
        kept=kept,
        dry_run=dry_run,
    )


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
    boundary `prune_telemetry` holds for the months it folds.
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


def prune_trial_state(
    state_dir: Path,
    *,
    dirname: str,
    today: date,
    within_days: int,
    dry_run: bool = False,
) -> TracePruneResult:
    """Delete a trial run's files past their window, whatever ledger wrote them.

    A trial run exercises production's code path and writes every ledger it
    would write, under `state/<dirname>/` instead of `state/`. Nothing reads
    those rows - no published series, no gate, no console band - so the honest
    retention is deletion, and the window is about disk and about a reader who
    opens `state/` and wonders what a directory is.

    It takes the tree whole rather than one ledger at a time, and that is the
    difference from every prune above it. Those know which ledger they are
    pruning and what its knob is called; this one does not need to, because
    every file under here is the same kind of thing - a day of a run nobody
    reads - and a per-ledger version would have to be edited every time a ledger
    is added.

    **It walks to any depth, and that is what changed on 2026-09-22.** It used
    to hand each child of the root to `day_shards.shard_files`, which expects a
    day tree directly beneath it and raises on anything else. A trial run writes
    `segments/<ledger>/<run-id>-...csv` two levels down and `traces/<YYYY>/<MM>/
    <DD>-<ordinal>-<shard>.jsonl` under a name that is not a day file at all, so
    the moment this prune was pointed at a real trial root it raised instead of
    pruning. `trial_day` reads the date off the path instead.

    **A file whose path spells no date is kept and counted, not refused.** A day
    tree refuses a stray because a reader that skipped one would start missing
    rows; nothing reads a trial root, so what a refusal costs here is the whole
    nightly prune for a file nobody wanted (section 1a: degrade, do not fail).

    Reuses `TracePruneResult` rather than minting a shape with the same four
    fields and a different name.

    A file dated ahead of `today` is kept, the same property `prune_traces` and
    `prune_seen` hold: a run handed an older `--date` must not delete the day
    the next one appends to.
    """
    root = state_dir / dirname
    if not root.is_dir():
        return TracePruneResult((), 0, 0, dry_run)

    deleted: list[str] = []
    kept = 0
    freed = 0
    # Unbounded because the question is which of this run's days have aged out,
    # and a window would leave the oldest ones standing for ever.
    for path in sorted(entry for entry in root.rglob("*") if entry.is_file()):
        relative = path.relative_to(state_dir).as_posix()
        written = trial_day(path.relative_to(root).as_posix())
        if written is None or (today - written).days < within_days:
            kept += 1
            continue
        deleted.append(f"{ledger.STATE_DIRNAME}/{relative}")
        freed += path.stat().st_size
        if not dry_run:
            path.unlink()

    if not dry_run:
        _drop_empty_directories(root)

    return TracePruneResult(
        deleted=tuple(deleted),
        bytes_freed=freed,
        kept=kept,
        dry_run=dry_run,
    )


def _drop_empty_directories(root: Path) -> None:
    """Take the emptied trial tree away, root included.

    Without this the child count under `state/` only ever rises: a trial that
    ran once leaves a directory for ever, and a reader opening `state/` cannot
    tell an empty husk from a tree still being written (Guardrail #12).
    """
    for directory in sorted((entry for entry in root.rglob("*") if entry.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    if not any(root.iterdir()):
        root.rmdir()


# --- The score ledger --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScorePruneResult:
    """What one archiving pass did, in the words a log line and a measurement need."""

    archived: tuple[str, ...]
    rows_archived: int
    #: Every `state/scores/<YYYY>/<MM>/<DD>.csv` this took, POSIX and relative to
    #: the repository, oldest first. Carried rather than derived from `archived`,
    #: because a month is a directory of day files now: a caller that spelled
    #: `<month>-01` would name a file the ledger may never have held, and the
    #: list a dry run prints has to be the list a live run removes, file for file.
    days_removed: tuple[str, ...]
    #: Every `state/score-index/<YYYY>/<MM>/<DD>.csv` this took, on the same
    #: terms. The index is derived from the days above and answers only for
    #: them, so it is pruned to the same span in the same pass - an index that
    #: outlives its source is a lookup that misses for ever, and the archive
    #: beside it already carries those digests.
    index_days_removed: tuple[str, ...]
    #: Distinct measurements the archives now index. This is the number that
    #: keeps the dedupe exact after the rows are gone, so it is reported rather
    #: than left to be inferred from the row count - they differ whenever a
    #: month held a repeat the settlement had not yet dropped.
    observations_indexed: int
    #: What the archived day files weighed, and what their summaries weigh. Both
    #: are counted in a dry run too, because the ratio between them is the
    #: measurement this policy is justified by (Guardrail #10) and a person has to be
    #: able to read it before any deletion is switched on.
    source_bytes: int
    archive_bytes: int
    hard_deleted: tuple[str, ...]
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.archived or self.hard_deleted)


def prune_scores(
    state_dir: Path,
    config: ObservabilityConfig,
    today: date,
    *,
    dry_run: bool = False,
) -> ScorePruneResult:
    """Archive every out-of-window score month, prove the archive, then delete its days.

    Four steps per month and the order is the whole safety argument: summarise,
    write temp-then-rename, read the written file back through its contract, and
    reconcile it field by field against a second reading of the day files. Only
    then are they unlinked. An archive that will not reconcile leaves its days in
    place and stops the run, because the alternative is deleting a committed file
    on the strength of a summary nobody checked - and `prune.yml` force-pushes
    `main`, so that file does not come back.

    The ledger files by day and this boundary is a month, so
    `day_partition.days_by_month` groups the day files and a month goes whole or
    not at all. That keeps the knob's unit the one it has always had while the
    files below it are days, and it keeps the archive's own input at most 31
    files.

    **The index beside those days goes in the same pass.** It is derived from
    them and answers only for them, so an index month that outlived its rows is
    a lookup that misses for ever. `evals.writer.refresh_index` drops one too,
    but only on the next run that writes a score, and it never repairs a stale
    index - so nothing would notice in between. Both guard on the same fact:
    the month's archive is on disk, and the archive carries those digests, so
    nothing here can remove the last record of a measurement.

    A dry run does the first step and none of the others. It still counts the
    bytes both ways, so the log says what the archive would weigh against what
    the days weigh, which is the figure Guardrail #10 asks for beside this policy.

    `score_archive_keep_months` is applied last and defaults to null, which means
    an archive is kept for ever. Set, it must sit above
    `scores_full_grain_months`, which the config contract enforces - so a month
    is never deleted before it is archived.

    Re-running changes nothing. A month already archived has no day file left to
    find, and a month whose archive was written by a run that then failed to
    unlink is summarised again to the same bytes.
    """
    keep_from = oldest_month_kept(today, config.scores_full_grain_months)
    archived: list[str] = []
    days_removed: list[str] = []
    rows_archived = 0
    observations = 0
    source_bytes = 0
    archive_bytes = 0

    by_month = day_partition.days_by_month(state_dir / score_writer.LEDGER_DIRNAME)
    for month in sorted(by_month):
        if month >= keep_from:
            continue
        days = by_month[month]
        built = score_archive.summarise(
            days, month=month, observation_key=score_writer.OBSERVATION_KEY
        )
        archived.append(month)
        # Named and weighed before anything is written, so the dry run prints the
        # same list the live run removes.
        days_removed += [score_writer.ledger_relpath(f"{month}-{day.stem}") for day in days]
        rows_archived += built.source_rows
        observations += len(built.observation_digests)
        source_bytes += sum(day.stat().st_size for day in days)
        archive_bytes += len(built.to_json().encode("utf-8"))
        if dry_run:
            continue
        target = score_archive.archive_path(state_dir, month)
        score_archive.write(target, built)
        # Read back through the contract, then check the file that came back
        # still describes the days. The first catches a bad write; only the
        # second catches a summary of the wrong month.
        score_archive.reconcile(
            score_archive.read(target),
            days,
            month=month,
            observation_key=score_writer.OBSERVATION_KEY,
        )
        for day in days:
            day.unlink()
            day_partition.drop_empty_day_dirs(day)

    # The months whose digests an archive now carries, including the ones this
    # pass took - so a dry run names the same index files a live run removes.
    covered = {path.stem for path in score_archive.archive_files(state_dir)} | set(archived)
    index_days_removed: list[str] = []
    for shard in day_shards.shard_files(
        state_dir / score_writer.INDEX_DIRNAME, days=UNBOUNDED_WINDOW
    ):
        month = day_shards.date_of(shard)[:7]
        if month >= keep_from or month not in covered:
            continue
        index_days_removed.append(
            f"{ledger.STATE_DIRNAME}/{shard.relative_to(state_dir).as_posix()}"
        )
        if not dry_run:
            shard.unlink()
            day_partition.drop_empty_day_dirs(shard)

    hard_deleted: list[str] = []
    if config.score_archive_keep_months is not None:
        delete_from = oldest_month_kept(today, config.score_archive_keep_months)
        for summary in score_archive.archive_files(state_dir):
            if summary.stem >= delete_from:
                continue
            hard_deleted.append(summary.stem)
            if not dry_run:
                summary.unlink()

    return ScorePruneResult(
        archived=tuple(archived),
        rows_archived=rows_archived,
        days_removed=tuple(days_removed),
        index_days_removed=tuple(index_days_removed),
        observations_indexed=observations,
        source_bytes=source_bytes,
        archive_bytes=archive_bytes,
        hard_deleted=tuple(hard_deleted),
        dry_run=dry_run,
    )
