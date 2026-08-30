"""Keep the published site inside the ceiling that arrives first.

The 1 GB Pages cap is the earliest hard limit this project meets, and it is met
by images rather than by text. So this does two separate things, and they are
deliberately not the same thing:

- **The alarm** measures the built bundle - the tree the deploy uploads - and
  says when it is approaching the ceiling. It is on from the first run, long
  before anything is ever deleted, because measuring the ceiling is what turns a
  policy into a decision rather than a reaction.
- **The prune** removes rendered visuals older than a configured window. It
  ships disabled, in dry-run, behind a per-run delete fuse.

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

**A level is not a date, and only a date answers the ceiling question.** The
alarm used to print one megabyte figure and one headroom figure, and neither is
a rate, so neither says when. What says when is bytes per published item times
the items a day may publish, divided into the headroom. Three things follow from
that and they are the rest of this module: `by_directory`, so a directory that
grew can be named rather than inferred from one moving sum;
`bytes_per_published_item`, because a rate over whole days moves when the item
mix moves and a rate over items does not; and `days_to_alarm` and `days_to_cap`,
which are the answer the question was always asking for.

**The telemetry fold is the third thing here, and it deletes nothing a reader
can reach.** `state/item-health/` is the census, and it grew at a measured
211,742 bytes a published day on 2026-08-30 with nothing bounding it.
`observability.keep_months` is where a month stops being kept item by item: past
it the month is folded to one row per (date, stage) and the full-grain shard is
deleted. It is thirteen months because `console.max_window_days` is 366, so a
shard has to answer for a year and a month of it is still being written. The
aggregate is kept forever by default, because a downsampled year costs
kilobytes and deleting it would make a year-over-year comparison unanswerable -
`observability.hard_delete_after_months` is the escape hatch and is null.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.contracts.app_config import ObservabilityConfig, RetentionConfig
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow, percentile

BYTES_PER_MB: Final = 1024 * 1024
#: The platform's own hard ceiling. Not a knob: it is a property of the host,
#: and making it editable would invite raising it instead of shrinking the site.
PAGES_HARD_CAP_MB: Final = 1024

_VISUAL_SUFFIXES: Final[frozenset[str]] = frozenset({".png", ".webp", ".jpg", ".jpeg", ".svg"})

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


def measure(root: Path, *, published_items: int = 0) -> SiteSize:
    """Recorded every run from the first one, long before any policy exists."""
    if not root.exists():
        return SiteSize(0, 0)
    by_directory: dict[str, int] = {}
    files = 0
    for child in sorted(root.iterdir()):
        if child.is_file():
            by_directory[child.name] = child.stat().st_size
            files += 1
        elif child.is_dir():
            inside = [path for path in child.rglob("*") if path.is_file()]
            by_directory[child.name] = sum(path.stat().st_size for path in inside)
            files += len(inside)
    return SiteSize(sum(by_directory.values()), files, by_directory, published_items)


def count_published_items(root: Path) -> int:
    """Items across every day payload staged into the measured tree.

    Read from the built tree rather than from `frontend/public/digest/` or from a
    run manifest, because bytes and items have to come from one corpus. The two
    trees are eighteen times apart and a prune would move one before the other,
    so a rate taken across them divides a numerator by somebody else's
    denominator.
    """
    staged = root / _STAGED_DIGEST_DIRNAME
    if not staged.is_dir():
        return 0
    total = 0
    for payload in sorted(staged.rglob("digest.json")):
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
    """Past the platform's own ceiling, which is where reporting stops being enough.

    `cap_mb` is a parameter for the same reason `prune` takes `today`: a test has
    to be able to cross the line without building a one-gigabyte fixture. No
    caller passes it, and the CLI offers no flag for it.
    """
    return size.megabytes > cap_mb


def headroom_mb(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> float:
    return cap_mb - size.megabytes


def daily_growth_bytes(size: SiteSize, items_per_day: int) -> float:
    """What one more published day costs, at the item ceiling in force.

    `items_per_day` is `run.safety_ceiling_per_run` and not an average of the
    days on disk. A day that published 117 items is not evidence that the next
    one will; the ceiling is the most a day is allowed to cost, which is the
    figure a worst-case runway needs (Rule #10).
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


def budget_alarm(
    size: SiteSize, config: RetentionConfig, *, cap_mb: int = PAGES_HARD_CAP_MB
) -> str | None:
    """The alarm's words, or None when the built site is inside budget.

    Below the platform cap the alarm only reports - it fails no build and deletes
    nothing - so the run that meets it needs a line it can act on: the size, the
    alarm point it crossed, and the headroom left to the cap.
    """
    if not over_budget(size, config):
        return None
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
    still had room. Past the cap the site is outside what Rule #2 allows, and
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

    A day's `digest.json` and `run.json` are never candidates: they are the
    record that the day happened, and they are text.
    """
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _VISUAL_SUFFIXES:
            continue
        published = _date_of(path, root)
        if published is not None and published < limit:
            found.append(path)
    return found


def _date_of(path: Path, root: Path) -> date | None:
    parts = path.relative_to(root).parts
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime("-".join(parts[:3]), "%Y-%m-%d").replace(tzinfo=UTC).date()
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class PruneResult:
    considered: int
    deleted: int
    dry_run: bool
    fuse_tripped: bool


def prune(root: Path, config: RetentionConfig, today: date) -> PruneResult:
    """Delete nothing unless configured to, and never more than the fuse allows."""
    limit = cutoff(today, config.image_months)
    if limit is None:
        return PruneResult(0, 0, config.dry_run, False)

    candidates = visuals_older_than(root, limit)
    fuse_tripped = len(candidates) > config.max_deletes_per_run
    allowed = candidates[: config.max_deletes_per_run]
    if config.dry_run:
        return PruneResult(len(candidates), 0, True, fuse_tripped)

    for path in allowed:
        path.unlink(missing_ok=True)
    return PruneResult(len(candidates), len(allowed), False, fuse_tripped)


# --- The telemetry fold ------------------------------------------------------


def oldest_month_kept(today: date, months: int) -> str:
    """The oldest `YYYY-MM` stem that still stays at full grain.

    Counted in months rather than in thirty-day steps, because the thing being
    kept is a month file and a month is not thirty days. `months` counts the
    month being written as one of them, so 13 on any day of August 2026 keeps
    `2025-08` through `2026-08` - a whole year of complete months plus the
    partial one.
    """
    if months < 1:
        raise ValueError("keeping fewer than one month would delete the month being written")
    total = today.year * 12 + (today.month - 1) - (months - 1)
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def month_shards(directory: Path) -> list[Path]:
    """Every `<YYYY-MM>.csv` in a ledger directory, oldest first.

    Anything else in there is left alone. A directory this walks is one a prune
    deletes from, so it names what it recognises rather than deleting what it
    does not.
    """
    if not directory.is_dir():
        return []
    found = [path for path in directory.glob("*.csv") if _is_month_stem(path.stem)]
    return sorted(found, key=lambda path: path.stem)


def _is_month_stem(stem: str) -> bool:
    if len(stem) != 7 or stem[4] != "-":
        return False
    try:
        datetime.strptime(stem, "%Y-%m").replace(tzinfo=UTC)
    except ValueError:
        return False
    return True


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


def fold_month(rows: list[ItemHealthRow]) -> list[TelemetryAggregateRow]:
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
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.folded or self.hard_deleted)


def prune_telemetry(
    state_dir: Path,
    config: ObservabilityConfig,
    today: date,
    *,
    dry_run: bool = False,
) -> TelemetryPruneResult:
    """Fold every out-of-window item-health month, then delete the shard it came from.

    Order matters and it is the whole safety argument: the aggregate is written
    and read back before the full-grain shard is unlinked, so a fold that cannot
    be written leaves the shard exactly where it was. Nothing is deleted on the
    strength of a write nobody checked.

    `hard_delete_after_months` is applied last and defaults to null, which means
    an aggregate is kept forever. Set, it must sit above `keep_months`, which the
    config contract enforces - so a month is never deleted before it is folded.
    """
    keep_from = oldest_month_kept(today, config.keep_months)
    folded: list[str] = []
    rows_folded = 0
    aggregate_rows = 0

    for shard in month_shards(state_dir / ledger.ITEM_HEALTH_DIRNAME):
        if shard.stem >= keep_from:
            continue
        rows = ledger.load_item_health_shard(shard)
        summary = fold_month(rows)
        folded.append(shard.stem)
        rows_folded += len(rows)
        aggregate_rows += len(summary)
        if dry_run:
            continue
        target = ledger.telemetry_aggregate_path(state_dir, shard.stem)
        ledger.write_telemetry_aggregate(target, summary)
        # Read back before the shard goes. A fold nobody verified is a deletion
        # nobody can undo.
        if ledger.load_telemetry_aggregate(target) != summary:
            raise ValueError(
                f"{ledger.telemetry_aggregate_relpath(shard.stem)} did not read back as it "
                f"was written, so {shard.name} stays"
            )
        shard.unlink()

    hard_deleted: list[str] = []
    if config.hard_delete_after_months is not None:
        delete_from = oldest_month_kept(today, config.hard_delete_after_months)
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
        dry_run=dry_run,
    )


# --- The seen shards ---------------------------------------------------------


@dataclass(frozen=True)
class SeenPruneResult:
    """Which seen shards went, and what they weighed."""

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
    """Delete every seen shard the reader would no longer open.

    `ledger.load_seen` consults `shards_in_window(today, within_days)` and
    nothing else, so a shard outside that set is already invisible to the
    pipeline - it is bytes in the working tree answering no question. Without
    this the ledger grows for ever at a rate nothing bounds: measured
    2026-08-31, 356 KB a day after the address column came off, which is 32 MB
    over a 90-day window and no ceiling after that.

    The keep-set comes from the reader's own helper rather than from a second
    date calculation here. That is the safety argument: two calculations drift,
    and the day they drift this one deletes a shard the next plan wanted.

    There is no fuse and no `max_deletes_per_run`. A shard nobody reads is not
    the archive, and the picture pruner's fuse exists because a date-parse bug
    there eats published images - the worst case here is that the pipeline
    re-learns a first-sight date it had already forgotten.
    """
    keep = set(ledger.shards_in_window(today, within_days))
    deleted: list[str] = []
    kept: list[str] = []
    freed = 0

    for shard in month_shards(state_dir / ledger.SEEN_DIRNAME):
        if shard.stem in keep:
            kept.append(shard.stem)
            continue
        deleted.append(shard.stem)
        freed += shard.stat().st_size
        if not dry_run:
            shard.unlink()

    return SeenPruneResult(
        deleted=tuple(deleted),
        bytes_freed=freed,
        kept=tuple(kept),
        dry_run=dry_run,
    )
