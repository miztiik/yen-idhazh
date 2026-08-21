"""Decide the day, with arithmetic rather than a model.

A story carried by three independent feeds is the day's story. That is the
whole idea, and it needs no weights, no classifier and no judgement at run
time - which means the plan job finishes in seconds and produces the same
answer on every re-run.

The score is: how authoritative the source is, times how widely the story is
carried, plus a bonus if it names something on the watchlist, plus a bonus if a
link aggregator voted for it. Ties break on the canonical URL, so two runs over
the same feeds cannot disagree about the order.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

from idhazh.contracts.app_config import CollectConfig
from idhazh.contracts.run_plan import PlannedItem, VerticalPlan
from idhazh.contracts.taxonomy import SourceTier, VerticalDef
from idhazh.discover import Candidate

#: Bumped when the scoring shape changes. A published order that moved for a
#: reason nobody recorded is a published order nobody can defend.
RANK_VERSION: Final = "idhazh-rank-1"


def tier_weight(tier: SourceTier, config: CollectConfig) -> float:
    weights = config.tier_weights
    return {
        SourceTier.INSTITUTION: weights.institution,
        SourceTier.TRADE_PRESS: weights.trade_press,
        SourceTier.COMMUNITY: weights.community,
    }[tier]


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
) -> float:
    """Authority times reach, plus the two bonuses.

    Authority is the best tier that carried the story, not the average: one
    institutional source saying it makes it true regardless of how many
    aggregators repeated it.
    """
    best_tier = min(candidate.tier for candidate in carried)
    reach = 1.0 + config.repetition_weight * (len(carried) - 1)
    total = tier_weight(best_tier, config) * reach
    if watchlist_hit:
        total += config.watchlist_bonus
    if on_front_page:
        total += config.front_page_bonus
    return round(total, 6)


def _sort_key(item: tuple[float, Candidate]) -> tuple[float, str]:
    ranked, candidate = item
    return (-ranked, candidate.canonical_url)


def plan_vertical(
    vertical: VerticalDef,
    candidates: Sequence[Candidate],
    *,
    config: CollectConfig,
    live_feeds: int,
    watchlist_keys: frozenset[str] = frozenset(),
    front_page_keys: frozenset[str] = frozenset(),
) -> tuple[VerticalPlan, list[PlannedItem]]:
    """Rank one vertical's candidates and take its daily cap.

    A vertical below its feed floor is still counted - it is being built in the
    open - but it plans nothing, so an under-sourced desk never reaches a
    reader.
    """
    grouped = merge(candidates)
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

    scored: list[tuple[float, Candidate]] = []
    flags: dict[str, tuple[bool, bool]] = {}
    for url_key, carried in grouped.items():
        first = min(carried, key=lambda candidate: (candidate.tier, candidate.source_id))
        watchlist_hit = url_key in watchlist_keys
        on_front_page = first.canonical_url in front_page_keys
        flags[url_key] = (watchlist_hit, on_front_page)
        scored.append(
            (
                score(
                    carried,
                    config=config,
                    watchlist_hit=watchlist_hit,
                    on_front_page=on_front_page,
                ),
                first,
            )
        )

    items: list[PlannedItem] = []
    ordered = sorted(scored, key=_sort_key)[: vertical.daily_cap]
    for ordinal, (ranked, first) in enumerate(ordered, 1):
        watchlist_hit, on_front_page = flags[first.url_key]
        items.append(
            PlannedItem(
                item_id=f"{vertical.id}-{ordinal:02d}",
                url_key=first.url_key,
                source_url=first.source_url,
                canonical_url=first.canonical_url,
                source_id=first.source_id,
                tier=first.tier,
                vertical=vertical.id,
                title=first.title,
                published_at=first.published_at,
                carried_by=len(grouped[first.url_key]),
                watchlist_hit=watchlist_hit,
                on_front_page=on_front_page,
                rank_score=ranked,
            )
        )
    return summary.model_copy(update={"planned": len(items)}), items
