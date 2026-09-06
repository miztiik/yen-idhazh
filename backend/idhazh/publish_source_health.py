"""Write the browser-safe source-health view once per run.

Four private stores answer four different questions about one address, and
until this module existed the console could re-derive two of them in TypeScript
and simply could not see the other two. This folds all four into
`SourceHealthView` and writes it to `frontend/public/source-health.json`.

**Nothing reads it back.** Collect keeps deriving every decision from the
private ledgers, so this file is a replaceable projection and never control
state: delete it and the console loses a section while the run behaves exactly
as it did.

**It runs the existing reducers rather than restating them.**
`discover.settled`, `discover.streak` and `discover.resting` decide
availability, `source_health.endpoint_records` decides permission, and the
retirement ledger decides retirement. A second reduction over one file is how a
page starts disagreeing with the run that produced it.

**The publishing record is counted over complete UTC dates only.** A date the
run is still working on has opportunities nobody has attempted yet, so counting
it would report every source as having failed the day's work it has not reached.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.contracts.app_config import CollectConfig
from idhazh.contracts.feed_health import FeedHealthRow, RobotsOutcome, derive_endpoint_key
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome
from idhazh.contracts.source_health_view import (
    SourceAvailability,
    SourceHealthRow,
    SourceHealthView,
    SourcePermission,
)
from idhazh.contracts.sources import FeedDef, Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.discover import live, resting, settled, streak
from idhazh.source_health import endpoint_records

#: Where the view sits under `frontend/public/`. Beside the day payloads rather
#: than inside them: it is a projection of `state/`, not of a published day.
PUBLIC_FILENAME: Final = "source-health.json"
DEFAULT_PUBLIC_PATH: Final = config.REPO_ROOT / "frontend" / "public" / PUBLIC_FILENAME

#: What `RobotsOutcome` means to a page. The fourth state has no ledger member
#: because it is the absence of one, and absence is the state every row written
#: before 2026-09-02 is in.
_PERMISSION: Final[dict[RobotsOutcome, SourcePermission]] = {
    RobotsOutcome.ALLOWED: SourcePermission.ALLOWED,
    RobotsOutcome.DENIED: SourcePermission.DENIED,
    RobotsOutcome.UNREACHABLE: SourcePermission.UNREACHABLE,
}

__all__ = [
    "DEFAULT_PUBLIC_PATH",
    "PUBLIC_FILENAME",
    "active_feeds",
    "build",
    "public_relpath",
    "publish",
]


def public_relpath() -> str:
    """`frontend/public/source-health.json` - the POSIX form, for a log line."""
    return f"frontend/public/{PUBLIC_FILENAME}"


def active_feeds(sources: Sources, verticals: Iterable[str]) -> list[FeedDef]:
    """Every address a curator left active, in the order a page will read them.

    Per desk through `discover.live`, which is the same filter the plan loops,
    so this counts exactly the addresses a run would ask. A feed naming a desk
    the taxonomy does not declare is unreachable by the plan and is therefore
    not an address we may ask - which is why the desk list is an argument rather
    than something derived from the feeds themselves.
    """
    found: list[FeedDef] = []
    for vertical in verticals:
        found.extend(live(list(sources.feeds), vertical))
    return sorted(found, key=lambda feed: feed.id)


def _availability(
    rows: Sequence[FeedHealthRow], *, resting_ids: frozenset[str], feed_id: str
) -> SourceAvailability:
    """What the committed record says about this address now.

    The rest is asked first because it outranks everything else: a resting feed
    has a run of failures behind it, and reporting it as failing would name the
    symptom over the decision an operator can act on.

    A robots answer and a rest are both absent from `read`, and that is the
    defect this row exists to fix. Neither one asked the feed whether it still
    works, so a source whose every result is a polite refusal has never been
    read - and until 2026-09-03 the console reported it as one that had never
    failed. `preserves` is the same predicate the strike rule uses, so the two
    cannot drift into two definitions of an ask.
    """
    if feed_id in resting_ids:
        return SourceAvailability.RESTING
    ordered = _chronological(rows)
    if not [row for row in ordered if not row.preserves]:
        return SourceAvailability.NEVER_ASKED
    return SourceAvailability.FAILING if streak(ordered) > 0 else SourceAvailability.ANSWERING


def _chronological(rows: Sequence[FeedHealthRow]) -> list[FeedHealthRow]:
    """Oldest run first, which is the order the strike rule reads in.

    Arrival order is run order in a file one run appends to, and it is not run
    order once two shards are concatenated or a second attempt lands. A date
    alone does not order five runs of one day, so the run id breaks the tie -
    the same two keys `chronological` in `frontend/src/lib/feed-health.ts` sorts
    on, because the page and the run have to read the record the same way round.
    """
    return sorted(rows, key=lambda row: (row.date, row.run_id))


def _complete_dates(rows: Iterable[ItemHealthRow], *, today: str, keep: int) -> list[str]:
    """The newest `keep` dates the census may read, oldest first.

    Dates the ledger holds rather than calendar days, and strictly before
    `today`. A day the pipeline never ran has no opportunities to divide by, so
    counting it as a complete date would dilute every source's record with a
    denominator nobody offered.
    """
    dates = sorted({row.date for row in rows if row.date < today})
    return dates[-keep:] if keep > 0 else []


class _Census:
    """Opportunities, publications and source-owned losses, per source.

    The unit is one distinct address on one complete date - not one row.
    A date runs up to five times and a retried address writes a row each time,
    so counting rows would inflate both sides of the ratio by however often the
    schedule fired (`docs/architecture/sources/health.md`).
    """

    def __init__(self) -> None:
        self._published: dict[str, set[tuple[str, str]]] = defaultdict(set)
        self._planned: dict[str, set[tuple[str, str]]] = defaultdict(set)
        self._lost: dict[str, set[tuple[str, str]]] = defaultdict(set)

    def add(self, row: ItemHealthRow) -> None:
        address = (row.date, row.url_key)
        self._planned[row.source_id].add(address)
        if row.outcome is ItemOutcome.OK:
            self._published[row.source_id].add(address)
        elif row.counts_against_source:
            self._lost[row.source_id].add(address)

    def of(self, source_id: str) -> tuple[int, int, int]:
        """Opportunities, publications and source-owned losses for one source.

        A loss is reported beside the ratio and never subtracted from it, so an
        address that both failed and later published on the same date counts
        once on each side rather than being removed from either. Losses are
        therefore capped at the opportunity count rather than added to the
        publications - the two sets overlap by design.
        """
        planned = self._planned.get(source_id, set())
        published = self._published.get(source_id, set())
        lost = self._lost.get(source_id, set()) - published
        return len(planned), len(published), len(lost)


def build(
    *,
    feeds: Sequence[FeedDef],
    collect: CollectConfig,
    health: Sequence[FeedHealthRow],
    items: Sequence[ItemHealthRow],
    retired_on: Mapping[str, str],
    date: str,
    run_id: str,
    generated_at: str,
) -> SourceHealthView:
    """Fold the committed record into the shape a page may read.

    Pure: every argument is already-loaded evidence, so the whole view is
    testable against rows a test made up and nothing here opens a socket, reads
    a clock or touches `config/sources.json` on disk. `feeds` is what
    `active_feeds` returned and `retired_on` maps an endpoint key to the day its
    retirement was filed, which is the retirement ledger with nothing else of it
    carried.
    """
    settled_rows = settled(health)
    by_feed: dict[str, list[FeedHealthRow]] = defaultdict(list)
    for row in settled_rows:
        by_feed[row.feed_id].append(row)
    resting_ids = resting(settled_rows, after_failures=collect.availability_strikes_before_rest)
    records = endpoint_records(settled_rows)

    keep = collect.source_yield_min_complete_days
    dates = _complete_dates(items, today=date, keep=keep)
    inside = set(dates)
    census = _Census()
    for item in items:
        if item.date in inside:
            census.add(item)

    rows: list[SourceHealthRow] = []
    for feed in sorted(feeds, key=lambda entry: entry.id):
        key = derive_endpoint_key(feed.url)
        record = records.get(key)
        permission = (
            SourcePermission.UNRECORDED
            if record is None or record.permission is None
            else _PERMISSION[record.permission]
        )
        opportunities, publications, lost = census.of(feed.id)
        rows.append(
            SourceHealthRow(
                source_id=feed.id,
                title=feed.title,
                vertical=feed.vertical,
                permission=permission,
                availability=_availability(
                    by_feed.get(feed.id, []), resting_ids=resting_ids, feed_id=feed.id
                ),
                retired=key in retired_on,
                retired_on=retired_on.get(key),
                opportunities=opportunities,
                publications=publications,
                source_failures=lost,
            )
        )

    return SourceHealthView(
        version=SourceHealthView.schema_version(),
        generated_at=generated_at,
        run_id=run_id,
        min_complete_days=keep,
        complete_dates=len(dates),
        yield_readable=len(dates) >= keep,
        first_date=dates[0] if dates else None,
        last_date=dates[-1] if dates else None,
        sources=rows,
    )


def publish(
    *,
    sources: Sources,
    taxonomy: Taxonomy,
    collect: CollectConfig,
    date: str,
    run_id: str,
    generated_at: str,
    state_root: Path = config.REPO_ROOT / ledger.STATE_DIRNAME,
    path: Path = DEFAULT_PUBLIC_PATH,
) -> SourceHealthView:
    """Read the committed record, fold it, write the view, and hand it back.

    The health read is the one the quarantine reads - `HEALTH_WINDOW_DAYS`
    anchored on this run's date - because this file publishes the run's decision
    rather than a second opinion about it. The item read is bounded by the same
    number of days the census keeps, so nothing is opened that `_complete_dates`
    would throw away.

    Returns the view rather than the path because `yield_alarm` reads it and the
    caller already holds the path it passed in.
    """
    health = ledger.load_health(state_root, today=date, within_days=ledger.HEALTH_WINDOW_DAYS)
    view = build(
        feeds=active_feeds(sources, [vertical.id for vertical in taxonomy.verticals]),
        collect=collect,
        health=health,
        items=ledger.load_item_health(
            state_root, today=date, within_days=collect.source_yield_min_complete_days
        ),
        retired_on={
            row.endpoint_key: row.retired_on for row in ledger.load_retirements(state_root)
        },
        date=date,
        run_id=run_id,
        generated_at=generated_at,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(view.to_json(), encoding="utf-8", newline="\n")
    return view


def yield_alarm(
    view: SourceHealthView, *, alarm_point: float, min_decisions: int
) -> str | None:
    """Name the sources that answer cleanly and return almost nothing.

    The gap this closes: every other signal asks whether we could ask, and none
    asks whether asking was worth it. `scmp-news` held permission `allowed`,
    availability `answering` and HTTP 200 with fifty dated entries every run for
    a fortnight while 123 of its 127 items failed extraction as `paywalled`. The
    ratio was already on this view and already on the console, and nobody was
    told (`docs/architecture/sources/discovery.md`, 2026-09-06).

    The denominator is the addresses the source itself decided - its
    publications plus its own losses - never `opportunities`. A model that would
    not answer, a rate limit and a robots refusal are ours or nobody's, and
    charging a publisher for our outage is how a true signal earns a false
    positive. Measured 2026-09-06 over the committed view: `aljazeera-economy`
    is 78 of 115 offered and 78 of 79 owned, so the wide denominator calls a
    99 percent source a 68 percent one.

    Reports rather than decides. Nothing here rests a feed, scales its rank or
    edits `config/sources.json` - feed health is recorded, not configured
    (`docs/architecture/sources/health.md`). A low yield is a claim about slots
    we spent, not about whether the writing was any good, and only a person can
    tell those apart.
    """
    named = [
        row
        for row in view.sources
        if not row.retired
        and row.permission is SourcePermission.ALLOWED
        and row.availability is SourceAvailability.ANSWERING
        and row.decisions >= min_decisions
        and row.source_yield is not None
        and row.source_yield < alarm_point
    ]
    if not named:
        return None
    worst = sorted(named, key=lambda row: (row.source_yield or 0.0, row.source_id))
    listed = ", ".join(
        f"{row.source_id} {row.publications}/{row.decisions} ({(row.source_yield or 0.0):.0%})"
        for row in worst
    )
    return (
        f"{len(worst)} source(s) answer but do not read, over {view.complete_dates} "
        f"complete day(s): {listed}. The bar is {alarm_point:.0%} of the addresses a "
        f"source owns, over at least {min_decisions} of them. Probe one with "
        f"'python backend/utilities/probe_feeds.py --from-config feeds --id <id> "
        f"--articles 5', then retire it in config/sources.json or leave it."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=config.REPO_ROOT / ledger.STATE_DIRNAME)
    parser.add_argument("--out", type=Path, default=DEFAULT_PUBLIC_PATH)
    parser.add_argument("--date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--generated-at",
        help="UTC stamp for the view. Defaults to now, which is what a run writes.",
    )
    args = parser.parse_args()
    settings = config.load()
    publish(
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        collect=settings.app.collect,
        date=args.date,
        run_id=args.run_id,
        generated_at=args.generated_at
        or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        state_root=args.state,
        path=args.out,
    )
    print(args.out.relative_to(config.REPO_ROOT).as_posix())


if __name__ == "__main__":
    main()
