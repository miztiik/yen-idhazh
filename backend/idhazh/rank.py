"""Decide the day, with arithmetic rather than a model.

A story carried by three independent feeds is the day's story. That is the
whole idea, and it needs no weights, no classifier and no judgement at run
time - which means the plan job finishes in seconds and produces the same
answer on every re-run.

The score is: how far the source is trusted, times how widely the story is
carried, plus a bonus for the watchlist, for an aggregator's vote, and for
being new. Nothing is ever dropped for being old. A cutoff cannot tell a strong
old story from a weak fresh one; a bonus lets the rest of the score answer that.

Nothing bounds how many items a vertical contributes except supply, the score,
and `max_per_source`. Ties break on the canonical URL, so two runs over the same
feeds cannot disagree about the order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, NamedTuple

from idhazh.contracts.app_config import CollectConfig
from idhazh.contracts.run_plan import PlannedItem, TimeSource, VerticalPlan
from idhazh.contracts.taxonomy import SourceTier, VerticalDef
from idhazh.discover import Candidate

#: Bumped when the scoring shape changes. A published order that moved for a
#: reason nobody recorded is a published order nobody can defend.
RANK_VERSION: Final = "idhazh-rank-2"

#: Decimal digits of the address hash that make up an item id. Ten is short
#: enough to read in a link and wide enough that two addresses in one vertical
#: colliding is a once-in-many-years event rather than a weekly one.
ITEM_ID_DIGITS: Final = 10

_STAMP: Final = "%Y-%m-%dT%H:%M:%SZ"


def _at(stamp: str) -> datetime:
    return datetime.strptime(stamp, _STAMP).replace(tzinfo=UTC)


def _hours(later: str, earlier: str) -> float:
    return (_at(later) - _at(earlier)).total_seconds() / 3600.0


# --- identity ----------------------------------------------------------------


def item_id(vertical: str, url_key: str) -> str:
    """`<vertical>-<ten digits>`, derived from the address and nothing else.

    The id used to be the rank position, so run 2 of a day renumbered every
    story: the same article came back under a different id, the digest
    deduplicated on that id, and anything that moved one place published twice.
    Deriving it from the address means a later run of the same day recognises
    the work the earlier one already did.
    """
    number = int(url_key[:16], 16) % 10**ITEM_ID_DIGITS
    return f"{vertical}-{number:0{ITEM_ID_DIGITS}d}"


def assign_ids(vertical: str, url_keys: Iterable[str]) -> dict[str, str]:
    """One id per address, distinct within the vertical.

    Two addresses landing on the same ten digits is rare, but a repeated id is
    a contract failure that stops the run, so the second one steps forward
    until it is free. Resolved in address order, so the answer depends on the
    pool and never on the ranking.
    """
    assigned: dict[str, str] = {}
    taken: set[str] = set()
    for url_key in sorted(url_keys):
        chosen = item_id(vertical, url_key)
        while chosen in taken:
            number = (int(chosen.rsplit("-", 1)[1]) + 1) % 10**ITEM_ID_DIGITS
            chosen = f"{vertical}-{number:0{ITEM_ID_DIGITS}d}"
        taken.add(chosen)
        assigned[url_key] = chosen
    return assigned


# --- when a story appeared ---------------------------------------------------


class Appearance(NamedTuple):
    """When a story appeared, and which clock said so."""

    at: str | None
    source: TimeSource


def appeared_at(
    published_at: str | None,
    *,
    first_seen_at: str | None,
    now: str,
    max_future_hours: float,
) -> Appearance:
    """When to treat a story as having appeared, and whose clock that is.

    The feed's own date wins, unless it claims a future too far ahead to be
    true: a feed that stamps tomorrow would otherwise hold the top slot every
    single day. First sight is the fallback, and for an article carrying no
    date at all it is the only age anybody has.

    The label leaves with the value rather than being worked out again further
    down, because the fallback is silent: once the two clocks are in one field
    nothing can tell them apart, and a page that prints the time cannot say
    whose it is.
    """
    if published_at is not None and _hours(published_at, now) <= max_future_hours:
        return Appearance(published_at, TimeSource.FEED)
    if first_seen_at is not None:
        return Appearance(first_seen_at, TimeSource.FIRST_SEEN)
    return Appearance(None, TimeSource.UNKNOWN)


def too_old(at: str | None, *, now: str, config: CollectConfig) -> bool:
    """Past the age at which a story stops being news.

    A story we could not date at all is never too old: first sight is the only
    age it has, so it gets the run that found it and ages out from there.
    """
    if at is None:
        return False
    return _hours(now, at) > config.max_age_hours


def recency_bonus(at: str | None, *, now: str, config: CollectConfig) -> float:
    """A bonus that halves every `recency_half_life_hours`. Orders, never admits.

    `too_old` decides what may be added; this decides the order of what passed.
    A day-old item at the edge of the window still scores below an hour-old one.
    """
    if at is None:
        return 0.0
    hours = max(0.0, _hours(now, at))
    decay: float = 0.5 ** (hours / config.recency_half_life_hours)
    return config.recency_weight * decay


# --- scoring -----------------------------------------------------------------


def tier_weight(tier: SourceTier, config: CollectConfig) -> float:
    weights = config.tier_weights
    return {
        SourceTier.INSTITUTION: weights.institution,
        SourceTier.TRADE_PRESS: weights.trade_press,
        SourceTier.COMMUNITY: weights.community,
    }[tier]


def authority(candidate: Candidate, config: CollectConfig) -> float:
    """The source's tier score, scaled by that feed's own weight.

    Weight is soft retirement: drop a feed to 0.5, watch what it costs, then
    decide. Multiplying rather than adding keeps a weighted-down institution
    below a full-weight one of the same tier, which is the point.
    """
    return tier_weight(candidate.tier, config) * candidate.weight


def merge(candidates: Iterable[Candidate]) -> dict[str, list[Candidate]]:
    """Group by canonical URL. The group size is the cross-source repetition."""
    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.url_key, []).append(candidate)
    return grouped


def score(
    carried: Sequence[Candidate],
    *,
    config: CollectConfig,
    watchlist_hit: bool,
    on_front_page: bool,
    lens_bonus: float = 0.0,
    appeared: str | None,
    now: str,
) -> float:
    """Authority times reach, plus the bonuses.

    Authority is the best-trusted source that carried the story, not the
    average: one institution saying it makes it true regardless of how many
    aggregators repeated it.

    A lens bonus is the weight of one lens, never the sum of several. Two
    themes in one headline is not twice the story, and summing would let a
    keyword list outweigh the fact that three independent feeds carried it.
    """
    best = max(authority(candidate, config) for candidate in carried)
    reach = 1.0 + config.repetition_weight * (len(carried) - 1)
    total = best * reach
    if watchlist_hit:
        total += config.watchlist_bonus
    if on_front_page:
        total += config.front_page_bonus
    total += lens_bonus
    total += recency_bonus(appeared, now=now, config=config)
    return round(total, 6)


@dataclass(frozen=True, slots=True)
class Ranked:
    """One story after scoring, before anything decides whether to take it."""

    score: float
    candidate: Candidate
    appeared_at: str | None
    time_source: TimeSource
    carried_by: int
    watchlist_hit: bool
    on_front_page: bool
    lens_bonus: float = 0.0


def _ordered(scored: list[Ranked]) -> list[Ranked]:
    """Score first, then when it appeared, then the address.

    The tie-break matters more than it looks. On a day when no story is carried
    twice the scores sit close together, and an alphabetical tie-break silently
    hands the day to whichever host sorts first. Sorts are stable, so these
    compose least-significant first.
    """
    ordered = sorted(scored, key=lambda item: item.candidate.canonical_url)
    ordered.sort(key=lambda item: item.appeared_at or "", reverse=True)
    ordered.sort(key=lambda item: item.score, reverse=True)
    return ordered


def _take(ordered: list[Ranked], *, max_per_source: int) -> list[Ranked]:
    """Everything the feeds offered, except that no one feed becomes the vertical."""
    taken: list[Ranked] = []
    per_source: dict[str, int] = {}
    for item in ordered:
        source_id = item.candidate.source_id
        if per_source.get(source_id, 0) >= max_per_source:
            continue
        per_source[source_id] = per_source.get(source_id, 0) + 1
        taken.append(item)
    return taken


def plan_vertical(
    vertical: VerticalDef,
    candidates: Sequence[Candidate],
    *,
    config: CollectConfig,
    live_feeds: int,
    now: str,
    first_seen: Mapping[str, str] | None = None,
    already_published: frozenset[str] = frozenset(),
    settled_today: frozenset[str] = frozenset(),
    watchlist_keys: frozenset[str] = frozenset(),
    front_page_keys: frozenset[str] = frozenset(),
    lens_bonuses: Mapping[str, float] | None = None,
) -> tuple[VerticalPlan, list[PlannedItem]]:
    """Rank one vertical's candidates and take what its feeds actually offered.

    Supply, the score and `max_per_source` set the size. A vertical below its
    feed floor is still counted - it is being built in the open - but it plans
    nothing, so an under-sourced desk never reaches a reader.

    An address that reached a committed digest is dropped before anything is
    counted. A freshness rule cannot do that job on its own: an article
    published at 23:00 is seven hours old at 06:00 the next morning.

    An address that already failed today for a reason today cannot change is
    dropped the same way. `already_published` cannot cover it, because a failure
    is never published - so run 2 used to re-plan run 1's paywalls and get the
    same paywalls. The two sets are kept apart rather than merged: they are
    different facts, and `considered` has to be able to say which one cost a
    slot.

    A story past `max_age_hours` is dropped after it is counted, not before, so
    `considered` still says what the feeds offered and `too_old` says how much
    of it was a back catalogue.

    `lens_bonuses` is a theme's weight per address, matched on the headline
    before this is called - the body has not been fetched yet. One story takes
    the largest weight it earned and never the sum: two themes in one headline
    is not twice the story.

    `published_at` on the planned item is the time we believe, not the time the
    feed claimed. A date rejected as impossible must not reach a reader either,
    and `time_source` says which of the two clocks answered.
    """
    sightings = first_seen or {}
    themes = lens_bonuses or {}
    dropped = already_published | settled_today
    grouped = {
        url_key: carried
        for url_key, carried in merge(candidates).items()
        if url_key not in dropped
    }
    below_floor = live_feeds < vertical.min_feeds
    summary = VerticalPlan(
        id=vertical.id,
        considered=len(grouped),
        planned=0,
        live_feeds=live_feeds,
        below_feed_floor=below_floor,
    )
    if below_floor:
        return summary, []

    scored: list[Ranked] = []
    stale = 0
    for url_key, carried in grouped.items():
        best = min(carried, key=lambda item: (-authority(item, config), item.source_id))
        watchlist_hit = url_key in watchlist_keys
        on_front_page = best.canonical_url in front_page_keys
        appeared = appeared_at(
            best.published_at,
            first_seen_at=sightings.get(url_key),
            now=now,
            max_future_hours=config.max_future_hours,
        )
        if too_old(appeared.at, now=now, config=config):
            stale += 1
            continue
        theme = themes.get(url_key, 0.0)
        scored.append(
            Ranked(
                score=score(
                    carried,
                    config=config,
                    watchlist_hit=watchlist_hit,
                    on_front_page=on_front_page,
                    lens_bonus=theme,
                    appeared=appeared.at,
                    now=now,
                ),
                candidate=best,
                appeared_at=appeared.at,
                time_source=appeared.source,
                carried_by=len(carried),
                watchlist_hit=watchlist_hit,
                on_front_page=on_front_page,
                lens_bonus=theme,
            )
        )

    taken = _take(_ordered(scored), max_per_source=config.max_per_source)
    ids = assign_ids(vertical.id, (item.candidate.url_key for item in taken))
    items = [
        PlannedItem(
            item_id=ids[item.candidate.url_key],
            url_key=item.candidate.url_key,
            source_url=item.candidate.source_url,
            canonical_url=item.candidate.canonical_url,
            source_id=item.candidate.source_id,
            tier=item.candidate.tier,
            source_form=item.candidate.source_form,
            vertical=vertical.id,
            title=item.candidate.title,
            published_at=item.appeared_at,
            time_source=item.time_source,
            carried_by=item.carried_by,
            watchlist_hit=item.watchlist_hit,
            on_front_page=item.on_front_page,
            rank_score=item.score,
        )
        for item in taken
    ]
    return summary.model_copy(update={"planned": len(items), "too_old": stale}), items
