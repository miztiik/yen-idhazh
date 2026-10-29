"""Validate live source references and apply the registry's configured defaults."""

from __future__ import annotations

from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.contracts.watchlist import Watchlist


def bind_source_classification(
    *, taxonomy: Taxonomy, sources: Sources, watchlist: Watchlist, collect: CollectConfig
) -> None:
    """Refuse broken references before a run can fetch or rank a source."""
    kinds = {entry.id: entry for entry in taxonomy.source_kinds}
    tiers = {entry.id: entry for entry in taxonomy.source_tiers}
    default_kind = taxonomy.source_kind_default()
    default_tier = taxonomy.entity_tier_default()
    if default_kind not in kinds:
        raise ValueError("taxonomy.default_source_kind must name a registered source kind")
    if default_tier not in tiers:
        raise ValueError("taxonomy.default_entity_tier must name a registered source tier")
    if kinds[default_kind].status is not LifecycleStatus.ACTIVE:
        raise ValueError("taxonomy.default_source_kind must name an active source kind")
    if tiers[default_tier].status is not LifecycleStatus.ACTIVE:
        raise ValueError("taxonomy.default_entity_tier must name an active source tier")
    verticals = {entry.id: entry for entry in taxonomy.verticals}
    for feed in sources.known_feeds():
        if "kind" not in feed.model_fields_set:
            feed.kind = default_kind
        live = feed.status is not LifecycleStatus.RETIRED
        if live and (
            feed.kind not in kinds or kinds[feed.kind].status is not LifecycleStatus.ACTIVE
        ):
            raise ValueError(f"source {feed.id} kind {feed.kind} is not active and registered")
        if live and (
            feed.tier not in tiers or tiers[feed.tier].status is not LifecycleStatus.ACTIVE
        ):
            raise ValueError(f"source {feed.id} tier {feed.tier} is not active and registered")
        if live and feed.vertical not in verticals:
            raise ValueError(f"source {feed.id} vertical {feed.vertical} is not registered")
        if (
            live
            and feed.vertical in verticals
            and verticals[feed.vertical].status is not LifecycleStatus.ACTIVE
        ):
            raise ValueError(f"source {feed.id} vertical {feed.vertical} is not active")
    for vertical_id in collect.vertical_feed_floors:
        if vertical_id not in verticals:
            raise ValueError(
                f"collect.vertical_feed_floors names unknown vertical {vertical_id}"
            )
    active_feed_verticals = {
        feed.vertical for feed in sources.feeds if feed.status is LifecycleStatus.ACTIVE
    }
    for vertical_id in active_feed_verticals:
        if collect.vertical_feed_floor(vertical_id) is None:
            raise ValueError(
                f"collect.vertical_feed_floors is missing active vertical {vertical_id}"
            )
    for entity in watchlist.entities:
        for entity_feed in entity.feeds:
            if "tier" not in entity_feed.model_fields_set:
                entity_feed.tier = default_tier
            if (
                entity.status is not LifecycleStatus.RETIRED
                and entity_feed.status is not LifecycleStatus.RETIRED
                and (
                    entity_feed.tier not in tiers
                    or tiers[entity_feed.tier].status is not LifecycleStatus.ACTIVE
                )
            ):
                raise ValueError(
                    f"entity {entity.id} feed {entity_feed.id} tier {entity_feed.tier} "
                    "is not active and registered"
                )
    collect.bind_source_tiers(taxonomy.source_tiers)
