"""Read every live feed, rank the pool, and write down what it saw. No model.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import assemble, config, discover, fetch, ledger, rank, tag
from idhazh.contracts.base import fit_field
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.feed_health import (
    FeedHealthRow,
    FetchOutcome,
    derive_endpoint_key,
)
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.run_plan import PlannedItem, PublishedAgeBand, RunPlan, VerticalPlan
from idhazh.contracts.seen import SeenRow
from idhazh.contracts.sources import FeedDef
from idhazh.contracts.taxonomy import LifecycleStatus
from idhazh.embed import Embedder
from idhazh.stages import common
from idhazh.stages.common import LOG, Fetcher, _load_day, _load_manifest
from idhazh.telemetry import source_health

#: Why a feed was not asked, in the one cell a later reader has. A rest ends on
#: its own and a retirement does not, so the two sentences are different.
RESTING_DETAIL: Final = "resting after repeated failures"


RETIRED_DETAIL: Final = "address retired after repeated 410 Gone"


#: Outcomes that never sent a request to the feed address itself: permission was
#: refused or unknown, the feed was resting, or the address was one we refuse to
#: dial. Only the rows outside this set are evidence about the feed.
_NEVER_ASKED: Final[frozenset[FetchOutcome]] = frozenset(
    {FetchOutcome.ROBOTS_DENIED, FetchOutcome.SKIPPED, FetchOutcome.BLOCKED}
)

#: What a failure detail that folded away to nothing records. Never an empty
#: string: the outcome column already says the fetch failed, so a blank detail
#: beside it reads as a fetch nobody could describe rather than one nobody did.
_UNSTATED: Final = "detail could not be printed"


Clock = Callable[[], str]


def stage_plan(
    date: str,
    *,
    settings: config.Settings,
    fetcher: Fetcher | None = None,
    now: Clock | None = None,
    execution: int | None = None,
    state_dir: Path | None = None,
    cap: int | None = None,
) -> RunPlan:
    """Read every live feed, rank the pool, and write down what it saw. No model.

    Four committed ledgers bound the day. The seen store gives an article whose
    feed carried no date a real age - first sight is the only honest one there
    is. The published store is what stops a repeat, which a freshness rule
    cannot do on its own: an article published at 23:00 is seven hours old at
    06:00 the next morning. The item-health store stops the *other* repeat: an
    address that failed today behind a paywall or a 404 is not planned again
    today, because that answer will not change before tomorrow. The feed-health
    store records what every feed did, so a source that has gone quiet can be
    quarantined from evidence instead of from somebody's memory. Quarantine only
    ever holds a feed back for a few runs; it never edits `config/sources.json`,
    because retiring a source is a person's decision.

    Nothing is dropped for being old. `run.safety_ceiling_per_run` is a crash
    guard against a mis-parsed feed, not a reading budget.

    The item-health store answers a second question as well: how much of today
    each feed has already put in front of a reader. `collect.max_per_source`
    bounds a feed inside one desk in one run, and a feed sits on one desk, so
    its ceiling for a whole day is that count times the runs the day had - a
    fixed number whose share of the day moves with the day's size.
    `collect.max_source_share_per_day` is the share.

    `cap` takes the best `cap` stories of each vertical and is for a validation
    run that must not plan a whole day. It is a different knob from the crash
    guard: it works per vertical, before the day is deduplicated, and a run that
    does not ask for it plans exactly what it planned before.
    """
    read_url = fetcher or common.live_fetcher(settings)
    clock = now or assemble.utc_now
    state = state_dir if state_dir is not None else common.STATE_ROOT
    collect = settings.app.collect
    generated_at = clock()
    # Named by the execution that made it, not by a count of what is committed.
    # See `_next_run_n` for what the count could not do.
    run_id = _run_id(date, execution)

    candidates: list[discover.Candidate] = []
    health: list[FeedHealthRow] = []
    history = ledger.load_health(state, today=date, within_days=ledger.HEALTH_WINDOW_DAYS)
    asleep = discover.resting(history, after_failures=collect.availability_strikes_before_rest)
    # Retirement outranks rest, so it is decided first and from its own evidence:
    # five distinct runs reading `410 Gone` from one address. The ledger is read
    # before the row is filed and the two are joined, so the run that decides is
    # also the first run that does not ask.
    endpoints = source_health.endpoint_records(history)
    gone = {row.endpoint_key for row in ledger.load_retirements(state)}
    filed = source_health.retirements(
        settings.sources.feeds,
        records=endpoints,
        already=gone,
        after_runs=collect.feed_http_410_runs_before_retirement,
        date=date,
        run_id=run_id,
    )
    if filed:
        ledger.append_retirements(state, filed)
        gone |= {row.endpoint_key for row in filed}
        for row in filed:
            LOG.warning(
                "feed endpoint retired id=%s cause=%s runs=%s file=%s",
                row.feed_id,
                row.cause.value,
                len(row.evidence_run_ids),
                ledger.feed_retirements_relpath(),
            )
    retired = source_health.retired(settings.sources.feeds, gone)
    read = failed = skipped = 0
    for feed in settings.sources.feeds:
        if feed.id in retired:
            skipped += 1
            LOG.info("feed endpoint retired, not asked id=%s", feed.id)
            health.append(_rest_row(feed, at=generated_at, run_id=run_id, why=RETIRED_DETAIL))
            continue
        if feed.id in asleep:
            skipped += 1
            LOG.info("feed resting id=%s", feed.id)
            health.append(_rest_row(feed, at=generated_at, run_id=run_id, why=RESTING_DETAIL))
            continue
        result = read_url(feed.url)
        found = discover.candidates_from_feed(feed, result.body) if result.ok else []
        health.append(_health_row(feed, result, found=len(found), at=generated_at, run_id=run_id))
        if not result.ok:
            failed += 1
            LOG.warning("feed unavailable id=%s reason=%s", feed.id, result.detail)
            continue
        read += 1
        # What the feed offered is the health row's business; what we accept is
        # the pool's. A promotional page a healthy feed syndicated is not the
        # feed failing, so the two counts stay apart.
        kept, blocked = discover.split_blocked(found, markers=collect.blocked_url_markers)
        for candidate in blocked:
            LOG.info(
                "candidate blocked feed=%s reason=address_marker url=%s",
                feed.id,
                candidate.canonical_url,
            )
        candidates.extend(kept)

    front_page: set[str] = set()
    for salience in settings.sources.salience:
        result = read_url(salience.url)
        if result.ok:
            front_page |= discover.salience_urls(result.body)

    first_seen = ledger.load_seen(state, today=date, within_days=collect.seen_window_days)
    landed = ledger.append_seen(
        state, date, _first_sights(candidates, first_seen, generated_at, run_id)
    )
    ledger.append_health(state, date, health)
    published_on = ledger.load_published(
        state, today=date, within_days=collect.published_window_days
    )
    already_published = frozenset(published_on)
    settled_today = frozenset(
        ledger.load_settled_failures(state, date, codes=collect.settled_failure_codes)
    )
    # What the guard refused this run, and how old it was. The ledger's own size
    # says nothing about either: it counts every address the cover holds, and all
    # but a handful of those were never offered again. Only the overlap with what
    # the feeds offered today is the guard firing.
    #
    # The ages travel with the count because the count alone cannot answer the
    # question the width of the cover turns on - whether a narrower one would
    # have let any of these through. `collect.published_window_days` ships at -1,
    # so the read is still whole and these ages are the evidence a narrower cover
    # would have to be argued from. Both land on the plan payload, so a later run
    # can read what this one refused; this log line is stderr and nothing commits
    # stderr.
    planned_desks = {vertical.id for vertical in settings.taxonomy.verticals}
    offered = {item.url_key for item in candidates if item.vertical in planned_desks}
    run_day = date_type.fromisoformat(date)
    refused_ages = sorted(
        max(0, (run_day - date_type.fromisoformat(published_on[url_key])).days)
        for url_key in offered & already_published
    )
    LOG.info(
        "already-published guard refused=%s of offered=%s oldest_days=%s ledger=%s "
        "settled_today=%s",
        len(refused_ages),
        len(offered),
        refused_ages[-1] if refused_ages else "none",
        len(already_published),
        len(settled_today),
    )

    # The bonus is decided on the feed title, because that is all a plan has: the
    # page has not been fetched yet. An article whose body names an entity its
    # title does not still earns the published tag at Extract - the tag says what
    # the item is about, the bonus says what we were already watching for.
    entity_terms = settings.watchlist.entity_terms()
    watchlist_keys = frozenset(
        candidate.url_key for candidate in candidates if tag.tags(entity_terms, candidate.title)
    )
    LOG.info(
        "watchlist matched candidates=%s of %s entities=%s",
        len(watchlist_keys),
        len(candidates),
        len(entity_terms),
    )
    # A theme is read from the headline for the same reason, and only the lenses
    # config gives a weight to are asked. One story takes the largest weight it
    # earned: two themes in one headline is not twice the story. The lens's NAME
    # is kept beside its weight because the counterfactual ledger records which
    # lens a row is about, and a row that only carried the number could not be
    # counted per lens by anything reading it later.
    lens_weights = settings.taxonomy.lens_weights()
    lens_terms = settings.taxonomy.lens_terms()
    asked = {name: lens_terms[name] for name in lens_weights}
    lens_hits: dict[str, tuple[str, float]] = {}
    for candidate in candidates:
        matched = tag.tags(asked, candidate.title)
        if not matched:
            continue
        # The tie is broken on the name so two lenses of equal weight always
        # name the same winner. It cannot move a score: the weight is the same
        # either way, and only the name this row records changes.
        best_lens = max(matched, key=lambda lens: (lens_weights[lens], lens))
        if lens_weights[best_lens]:
            lens_hits[candidate.url_key] = (best_lens, lens_weights[best_lens])
    lens_bonuses = {key: weight for key, (_, weight) in lens_hits.items()}
    # The same weights multiplied, which is the only question this run asks and
    # the only thing it does with the answer is write it down.
    lens_multiplier = settings.app.lens_weights.counterfactual_multiplier
    counterfactual_bonuses = {key: weight * lens_multiplier for key, weight in lens_bonuses.items()}
    LOG.info(
        "themes matched candidates=%s of %s lenses=%s",
        len(lens_bonuses),
        len(candidates),
        sorted(lens_weights),
    )
    day_carried = ledger.load_source_counts(state, date)
    # A feed that has published badly over the trailing window - failed reads, or
    # reads that parsed to nothing - scores below a dependable feed of the same
    # tier. The factor is built once here off the committed health record and read
    # inside rank.authority; a feed with no evidence in the window reads 1.0.
    reliability_by_feed = ledger.reliability(
        state,
        today=date,
        within_days=collect.reliability_window_days,
        floor=collect.reliability_floor,
    )
    # The day's own encoder, built once and loaded only if the duplicate pass
    # finds work. Each story's lead is joined by address so the pass reads the
    # same headline-and-lead the design embeds; the first non-empty lead wins,
    # because feeds carrying one story carry one story's lead.
    embedder = Embedder(config.REPO_ROOT, settings.app.assist)
    leads: dict[str, str] = {}
    for candidate in candidates:
        if candidate.lead is not None and candidate.url_key not in leads:
            leads[candidate.url_key] = candidate.lead
    verticals, items, pools = _plan_desks(
        settings,
        candidates,
        now=generated_at,
        first_seen=first_seen,
        already_published=already_published,
        settled_today=settled_today,
        watchlist_keys=watchlist_keys,
        front_page_keys=frozenset(front_page),
        lens_bonuses=lens_bonuses,
        counterfactual_bonuses=counterfactual_bonuses,
        cap=cap,
        retired_keys=gone,
        endpoints=endpoints,
        reliability=reliability_by_feed,
    )

    items = _dedupe_planned_items(items)
    items = _record_plan_duplicates(items, embedder=embedder, leads=leads, collect=collect)
    items = _within_ceiling(items, ceiling=settings.app.run.safety_ceiling_per_run)

    # How much of the day one feed may hold is a share, and a share needs the
    # day's size. The day is what earlier runs published plus what this run is
    # about to plan, and the second half is only knowable once the desks have
    # been planned - so they are planned once to size the day, and again only
    # when the ceiling that size gives can actually bind on somebody.
    per_source = rank.day_source_ceiling(
        collect.max_source_share_per_day,
        sum(day_carried.values()) + len(items),
        max_per_source=collect.max_per_source,
    )
    crowding = sorted(
        source_id
        for source_id, held in day_carried.items()
        if per_source - held < collect.max_per_source
    )
    if crowding:
        LOG.info(
            "day source ceiling binds ceiling=%s carried=%s planning=%s feeds=%s",
            per_source,
            sum(day_carried.values()),
            len(items),
            crowding,
        )
        verticals, capped, pools = _plan_desks(
            settings,
            candidates,
            now=generated_at,
            first_seen=first_seen,
            already_published=already_published,
            settled_today=settled_today,
            watchlist_keys=watchlist_keys,
            front_page_keys=frozenset(front_page),
            lens_bonuses=lens_bonuses,
            counterfactual_bonuses=counterfactual_bonuses,
            cap=cap,
            retired_keys=gone,
            endpoints=endpoints,
            day_ceiling=rank.DayCeiling(per_source=per_source, carried=dict(day_carried)),
            reliability=reliability_by_feed,
        )
        capped = _dedupe_planned_items(capped)
        capped = _record_plan_duplicates(capped, embedder=embedder, leads=leads, collect=collect)
        capped = _within_ceiling(capped, ceiling=settings.app.run.safety_ceiling_per_run)
        if len(capped) < len(items):
            LOG.warning(
                "day source ceiling cost the day a story short=%s planned=%s ceiling=%s",
                len(items) - len(capped),
                len(items),
                per_source,
            )
        items = capped

    scored = sum(len(pool) for pool in pools.values())
    LOG.info("desks scored candidates=%s planned=%s", scored, len(items))
    recorded = ledger.append_counterfactual_scores(
        state,
        date,
        _counterfactual_rows(
            pools,
            items,
            date=date,
            run_id=run_id,
            lens_hits=lens_hits,
            multiplier=lens_multiplier,
            refused_per_desk=settings.app.lens_weights.counterfactual_refused_per_desk,
        ),
    )
    LOG.info(
        "counterfactual scores recorded rows=%s of %s scored file=%s",
        recorded,
        scored,
        ledger.counterfactual_scores_relpath(date),
    )
    counts = Counter(item.vertical for item in items)
    verticals = [
        summary.model_copy(update={"planned": counts.get(summary.id, 0)}) for summary in verticals
    ]
    LOG.info("first sights recorded new=%s file=%s", landed, ledger.seen_relpath(date))

    return RunPlan(
        version=RunPlan.schema_version(),
        date=date,
        run_id=run_id,
        generated_at=generated_at,
        feeds_read=read,
        feeds_failed=failed,
        feeds_skipped=skipped,
        dropped_published=len(refused_ages),
        dropped_published_ages=PublishedAgeBand.histogram(refused_ages),
        verticals=verticals,
        items=items,
    )


def _plan_desks(
    settings: config.Settings,
    candidates: list[discover.Candidate],
    *,
    now: str,
    first_seen: dict[str, str],
    already_published: frozenset[str],
    settled_today: frozenset[str],
    watchlist_keys: frozenset[str],
    front_page_keys: frozenset[str],
    lens_bonuses: dict[str, float],
    cap: int | None,
    retired_keys: set[str],
    endpoints: dict[str, source_health.EndpointRecord],
    counterfactual_bonuses: dict[str, float] | None = None,
    day_ceiling: rank.DayCeiling | None = None,
    reliability: dict[str, float] | None = None,
) -> tuple[list[VerticalPlan], list[PlannedItem], dict[str, list[rank.Ranked]]]:
    """Rank every desk once and return what they offered, desk by desk.

    Each desk is planned on its own: a vertical's candidates never compete with
    another's, which is what stops a busy desk emptying a quiet one. What comes
    back is still per-desk, so the caller deduplicates the day and applies the
    run's own ceiling.

    `day_ceiling` is the one limit that crosses a desk boundary, so it is the
    one thing this loop carries forward: each desk's take is added to the count
    before the next desk is planned. A feed sits on one desk, so in practice
    only that desk ever sees the count move - but a day ceiling that only
    counted one desk would be a per-desk rule wearing a day's name.

    The third thing returned is each desk's whole scored pool, refused
    candidates included, keyed by desk. It is returned rather than accumulated
    into something the caller passes in because this runs twice on a day whose
    source ceiling binds, and only the second pass scored against the ceiling
    the day actually applied. A returned value is replaced by the rebinding
    that is already there; an accumulator would hold both passes.
    """
    summaries: list[VerticalPlan] = []
    items: list[PlannedItem] = []
    pools: dict[str, list[rank.Ranked]] = {}
    for vertical in settings.taxonomy.verticals:
        askable = source_health.eligible(
            settings.sources.feeds,
            vertical.id,
            retired_keys=retired_keys,
            records=endpoints,
        )
        summary, planned, pool = rank.plan_vertical(
            vertical,
            [c for c in candidates if c.vertical == vertical.id],
            config=settings.app.collect,
            eligible_feeds=len(askable),
            now=now,
            first_seen=first_seen,
            already_published=already_published,
            settled_today=settled_today,
            watchlist_keys=watchlist_keys,
            front_page_keys=front_page_keys,
            lens_bonuses=lens_bonuses,
            counterfactual_lens_bonuses=counterfactual_bonuses,
            day_ceiling=day_ceiling,
            reliability=reliability,
        )
        summaries.append(summary)
        pools[vertical.id] = pool
        # A desk under its floor plans nothing and raises nothing, so without this
        # line the run succeeds, the digest publishes, and one section is absent.
        if summary.below_feed_floor and vertical.status is LifecycleStatus.ACTIVE:
            LOG.warning(
                "desk silent on its feed floor vertical=%s askable=%s floor=%s",
                vertical.id,
                summary.eligible_feeds,
                summary.feed_floor,
            )
        if cap is not None and len(planned) > cap:
            LOG.info("cap applied vertical=%s planned=%s cap=%s", vertical.id, len(planned), cap)
            planned = planned[:cap]
        if day_ceiling is not None:
            for item in planned:
                day_ceiling.record(item.source_id)
        items.extend(planned)
    return summaries, items, pools


def _counterfactual_rows(
    pools: Mapping[str, Sequence[rank.Ranked]],
    items: Sequence[PlannedItem],
    *,
    date: str,
    run_id: str,
    lens_hits: Mapping[str, tuple[str, float]],
    multiplier: float,
    refused_per_desk: int,
) -> list[CounterfactualScoreRow]:
    """The bounded pool of candidates this run writes both scores for.

    Everything the run took, plus the highest-scoring refused candidates on each
    desk. The pool arrives in the order the take read it, so the refused ones a
    desk keeps are simply the first it meets - the band around the cut, where a
    bonus decides. A candidate far below the cut would not cross it under any
    weight the probe asks about, so its row would be bytes with no question in
    them.

    The bound is per run rather than per day or per archive, so this costs a
    five-year-old repository exactly what it costs a fresh clone (CLAUDE.md
    Guardrail #12). What the ledger holds in total is bounded at the other end,
    by the retention pass keeping `lens_weights.window_days`.

    `taken` is read against the run's FINAL items rather than against what each
    desk took, so a story the day-wide duplicate fold or the run's safety
    ceiling removed after ranking reads as refused. That is what happened to it.

    **It is read per desk AND address, never per address alone.** One address
    can be carried by feeds on two desks, and then it is scored twice - once on
    each - while the day plans it once. Matching on the address alone marks both
    rows taken, and the ledger says the run took more stories than it did:
    measured on 2026-09-14, 87 rows claimed a day of 80 items.
    """
    taken = {(item.vertical, item.url_key) for item in items}
    rows: list[CounterfactualScoreRow] = []
    for vertical, pool in pools.items():
        refused = 0
        for ranked in pool:
            if ranked.score_counterfactual is None:
                continue
            key = ranked.candidate.url_key
            was_taken = (vertical, key) in taken
            if not was_taken:
                if refused >= refused_per_desk:
                    continue
                refused += 1
            lens_id, _ = lens_hits.get(key, ("", 0.0))
            rows.append(
                CounterfactualScoreRow(
                    version=CounterfactualScoreRow.schema_version(),
                    date=date,
                    run_id=run_id,
                    vertical=vertical,
                    url_key=key,
                    taken=was_taken,
                    lens_id=lens_id,
                    lens_bonus=ranked.lens_bonus,
                    lens_multiplier=multiplier,
                    score_committed=ranked.score,
                    score_counterfactual=ranked.score_counterfactual,
                )
            )
    return rows


def _rest_row(feed: FeedDef, *, at: str, run_id: str, why: str) -> FeedHealthRow:
    """The row a feed we chose not to ask gets. A record, not a measurement.

    Written rather than omitted so a rest can end: a run that left no trace
    would leave the old failures as the newest thing on record forever, and the
    feed would never be tried again. A retired address gets one for a different
    reason - the ledger has to stay one row per feed per run, or the console's
    denominator counts a desk it never asked.

    `why` is the difference between the two, because a rest lifts itself and a
    retirement does not.
    """
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=run_id,
        date=at[:10],
        feed_id=feed.id,
        checked_at=at,
        outcome=FetchOutcome.SKIPPED,
        items=0,
        detail=why,
        endpoint_key=derive_endpoint_key(feed.url),
        target_attempted=False,
    )


def _health_row(
    feed: FeedDef,
    result: fetch.FetchResult,
    *,
    found: int,
    at: str,
    run_id: str,
) -> FeedHealthRow:
    """This run's verdict on one feed, and on the address it was configured with.

    `detail` is our own sentence about the failure - a status name or an
    exception class - and never the response body. A feed is a stranger's text
    and this row lands on a published page (Guardrail #11).

    `endpoint_key` is what makes a later retirement possible at all: `feed_id`
    names a line of curated config, so an address that changed and an address
    that died read identically without it.

    `target_attempted` separates evidence about the feed from evidence about
    permission. A robots refusal, a rest and an address we refused to dial each
    left the feed itself un-asked, and only the rows that did ask say anything
    about whether it still works.
    """
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=run_id,
        date=at[:10],
        feed_id=feed.id,
        checked_at=at,
        outcome=result.outcome,
        status=result.status,
        items=found,
        detail=(
            fit_field(result.detail, model=FeedHealthRow, field="detail", absent=_UNSTATED)
            if result.detail
            else None
        ),
        endpoint_key=derive_endpoint_key(feed.url),
        robots_outcome=result.robots,
        target_attempted=result.outcome not in _NEVER_ASKED,
    )


def _first_sights(
    candidates: Iterable[discover.Candidate],
    known: dict[str, str],
    at: str,
    run_id: str,
) -> list[SeenRow]:
    """The addresses this run met for the first time, in address order.

    Recorded before anything is ranked, so an article that never made the day
    still has an age the next run can use. `known` is updated in place, which
    is what lets the ranking read this run's own sightings without a re-read.
    """
    fresh: dict[str, SeenRow] = {}
    for candidate in candidates:
        if candidate.url_key in known or candidate.url_key in fresh:
            continue
        fresh[candidate.url_key] = SeenRow(
            version=SeenRow.schema_version(),
            url_key=candidate.url_key,
            first_seen_at=at,
            first_seen_run=run_id,
        )
    known.update({url_key: row.first_seen_at for url_key, row in fresh.items()})
    return [fresh[url_key] for url_key in sorted(fresh)]


def _within_ceiling(items: list[PlannedItem], *, ceiling: int) -> list[PlannedItem]:
    """What sizes a run. Measured 2026-08-25 and since, it fires on every one.

    It drops the lowest-scoring stories across every vertical rather than
    truncating the list, so a mis-parsed feed costs the weakest items and not
    whichever vertical happened to sort last.

    It was written as a crash guard and supply overtook it: `items_planned` has
    equalled the ceiling on every run since, first at 200 and now at 160. It is
    the cap whatever it is called, and
    `docs/architecture/sources/freshness.md` says so rather than leaving the
    name to imply otherwise.
    """
    if len(items) <= ceiling:
        return items
    ranked = sorted(items, key=lambda item: (-item.rank_score, item.item_id))[:ceiling]
    keep = {item.item_id for item in ranked}
    LOG.warning("safety ceiling reached planned=%s ceiling=%s", len(items), ceiling)
    return [item for item in items if item.item_id in keep]


def _record_plan_duplicates(
    items: list[PlannedItem],
    *,
    embedder: Embedder,
    leads: Mapping[str, str],
    collect: CollectConfig,
) -> list[PlannedItem]:
    """Write down the day's same-story repeats, and cut them only when enforcing.

    Record-only by default (`collect.dedup_enforce` is false): the pass computes
    what it WOULD collapse - a story an earlier, stronger telling already
    covers - logs each one against what it matched, and removes nothing. Turning
    the flag on cuts the weaker telling before the safety ceiling and changes
    nothing else, so enforcing is a config edit rather than a code change.

    A record pass never stops a run (`degrade, do not fail`): an encoder that
    will not load costs the run its duplicate record, never its plan.
    """
    if len(items) < 2 or not embedder.available:
        return items
    try:
        embedder.load()
        ids: list[str] = []
        texts: list[str] = []
        for item in items:
            text = rank.dedup_text(item.title, leads.get(item.url_key))
            if text is None:
                continue
            ids.append(item.item_id)
            texts.append(text)
        if len(ids) < 2:
            return items
        vectors = dict(zip(ids, embedder.encode(texts), strict=True))
        findings = rank.duplicates_within_plan(
            items, vectors, similarity_min=collect.dedup_similarity_min
        )
    except Exception as error:  # degrade, do not fail: a record pass never stops a run
        LOG.warning("plan dedup skipped reason=%s: %s", type(error).__name__, error)
        return items
    for finding in findings:
        LOG.info(
            "plan duplicate would-collapse item=%s vertical=%s source=%s of=%s "
            "matched_source=%s similarity=%.4f enforce=%s",
            finding.item.item_id,
            finding.item.vertical,
            finding.item.source_id,
            finding.duplicate_of.item_id,
            finding.duplicate_of.source_id,
            finding.similarity,
            collect.dedup_enforce,
        )
    LOG.info(
        "plan duplicates recorded count=%s enforce=%s",
        len(findings),
        collect.dedup_enforce,
    )
    if not collect.dedup_enforce:
        return items
    cut = {finding.item.item_id for finding in findings}
    return [item for item in items if item.item_id not in cut]


def _dedupe_planned_items(items: list[PlannedItem]) -> list[PlannedItem]:
    """Keep one planned item per address before the crash guard counts slots."""
    by_key: dict[str, list[PlannedItem]] = {}
    for item in items:
        by_key.setdefault(item.url_key, []).append(item)

    duplicate_keys = [url_key for url_key, carried in by_key.items() if len(carried) > 1]
    if not duplicate_keys:
        return items

    winners = {
        url_key: min(
            carried,
            key=lambda item: (-item.rank_score, item.vertical, item.item_id, item.source_id),
        )
        for url_key, carried in by_key.items()
    }
    dropped = [item for item in items if winners[item.url_key] is not item]
    LOG.info(
        "plan duplicates dropped count=%s url_keys=%s source_ids=%s",
        len(dropped),
        ",".join(sorted(duplicate_keys)),
        ",".join(sorted({item.source_id for item in dropped})),
    )
    return [item for item in items if winners[item.url_key] is item]


def _next_run_n(date: str) -> int:
    """A run id for a machine with no CI run to name it. Local and test use only.

    Reading the count off the last committed manifest cannot make an identifier
    two executions are unable to share, and on 2026-08-29 two of them did share
    one. `actions/checkout` pins a job to the commit its run was triggered at, so
    the manifest a second run reads is the manifest as it stood before the first
    run published - and both count the same number. Runs 33270983446 (dispatched
    19:29) and 33274853468 (scheduled 20:58) both derived `2026-08-29-3`, and the
    ledgers keyed on it then held six counter rows for four shards.

    CI passes `--execution ${{ github.run_id }}` instead. GitHub allocates that
    number, it is unique across every run of every workflow in the repository,
    and nothing a second execution can read will reproduce it. This is what is
    left: a developer machine has no such number, and a laptop cannot race
    itself.
    """
    target = assemble.day_dir(common.PUBLIC_ROOT, date)
    manifest = _load_manifest(target / "run.json", day=_load_day(target / "digest.json"))
    return manifest.runs[-1].n + 1 if manifest else 1


def _run_id(date: str, execution: int | None) -> str:
    """The run address every ledger row of this execution is filed under.

    Written once because two stages now need it - the plan, which opens the run,
    and the cleanup, which closes it - and a second spelling of it would file
    one run's rows under two names.
    """
    return f"{date}-{execution if execution is not None else _next_run_n(date)}"
