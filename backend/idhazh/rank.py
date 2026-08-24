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
from typing import Final

from idhazh.contracts.app_config import CollectConfig
from idhazh.contracts.run_plan import PlannedItem, VerticalPlan
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


def appeared_at(
    published_at: str | None,
    *,
    first_seen_at: str | None,
    now: str,
    max_future_hours: float,
) -> str | None:
    """When to treat a story as having appeared.

    The feed's own date wins, unless it claims a future too far ahead to be
    true: a feed that stamps tomorrow would otherwise hold the top slot every
    single day. First sight is the fallback, and for an article carrying no
    date at all it is the only age anybody has.
    """
    if published_at is not None and _hours(published_at, now) <= max_future_hours:
        return published_at
    return first_seen_at


def recency_bonus(at: str | None, *, now: str, config: CollectConfig) -> float:
    """A bonus that halves every `recency_half_life_hours`. Never a filter.

    Nothing is dropped for age. A hard cutoff throws away a strong story to
    keep a weak fresh one, and it has no answer at all for an article whose
    feed gave no date.
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
    appeared: str | None,
    now: str,
) -> float:
    """Authority times reach, plus the three bonuses.

    Authority is the best-trusted source that carried the story, not the
    average: one institution saying it makes it true regardless of how many
    aggregators repeated it.
    """
    best = max(authority(candidate, config) for candidate in carried)
    reach = 1.0 + config.repetition_weight * (len(carried) - 1)
    total = best * reach
    if watchlist_hit:
        total += config.watchlist_bonus
    if on_front_page:
        total += config.front_page_bonus
    total += recency_bonus(appeared, now=now, config=config)
    return round(total, 6)


@dataclass(frozen=True, slots=True)
class Ranked:
    """One story after scoring, before anything decides whether to take it."""

    score: float
    candidate: Candidate
    appeared_at: str | None
    carried_by: int
    watchlist_hit: bool
    on_front_page: bool


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
    watchlist_keys: frozenset[str] = frozenset(),
    front_page_keys: frozenset[str] = frozenset(),
) -> tuple[VerticalPlan, list[PlannedItem]]:
    """Rank one vertical's candidates and take what its feeds actually offered.

    Supply, the score and `max_per_source` set the size. A vertical below its
    feed floor is still counted - it is being built in the open - but it plans
    nothing, so an under-sourced desk never reaches a reader.

    An address that reached a committed digest is dropped before anything is
    counted. A freshness rule cannot do that job on its own: an article
    published at 23:00 is seven hours old at 06:00 the next morning.

    `published_at` on the planned item is the time we believe, not the time the
    feed claimed. A date rejected as impossible must not reach a reader either.
    """
    sightings = first_seen or {}
    grouped = {
        url_key: carried
        for url_key, carried in merge(candidates).items()
        if url_key not in already_published
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
        scored.append(
            Ranked(
                score=score(
                    carried,
                    config=config,
                    watchlist_hit=watchlist_hit,
                    on_front_page=on_front_page,
                    appeared=appeared,
                    now=now,
                ),
                candidate=best,
                appeared_at=appeared,
                carried_by=len(carried),
                watchlist_hit=watchlist_hit,
                on_front_page=on_front_page,
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
            carried_by=item.carried_by,
            watchlist_hit=item.watchlist_hit,
            on_front_page=item.on_front_page,
            rank_score=item.score,
        )
        for item in taken
    ]
    return summary.model_copy(update={"planned": len(items)}), items
