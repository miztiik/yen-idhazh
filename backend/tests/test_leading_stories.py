"""The day's leading stories: what leads, what a cap costs, and what the block says.

Unit and integration tier (CLAUDE.md section 13). Nothing here is mocked, no
test touches the network, and nothing reads the committed archive: every case is
built in the test, including cases no published day has produced (Guardrail #12).

The one thing every test here is defending is the promise in
`docs/concepts/digest.md`: the block adds a way into the day and removes
nothing. Every story a rule turns away is still in `items`, in the published
order, marked exactly as it was.
"""

from __future__ import annotations

import json
import logging

import pytest

from idhazh.assemble import leading_stories, subject_clusters
from idhazh.config import load
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.item_health import TimeSource
from idhazh.contracts.knobs.placement import PlacementConfig
from idhazh.contracts.knobs.ui import UiConfig
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import SourceKind, Taxonomy, VerticalDef
from idhazh.contracts.watchlist import EntityDef, Watchlist
from idhazh.discover import Candidate
from idhazh.rank import plan_vertical

#: The hour the block is chosen at. An hour after the default story appeared,
#: so every story a test does not date itself sits inside the freshness
#: shoulder and scores 1.0 - the age curve moves nothing a test did not ask it
#: to move.
NOW = "2026-08-31T10:00:00Z"

DESKS = {
    "ai": "AI",
    "energy": "Energy",
    "world": "World",
    "india": "India",
    "business-economy": "Business",
}


def watchlist(*entries: tuple[str, str, list[str]]) -> Watchlist:
    return Watchlist(
        version=Watchlist.schema_version(),
        entities=[
            EntityDef(id=slug, display_name=name, aliases=aliases)
            for slug, name, aliases in entries
        ],
    )


REGISTRY = watchlist(
    ("nvidia", "Nvidia", ["nvidia"]),
    ("openai", "OpenAI", ["openai"]),
    ("apple", "Apple", ["apple"]),
)

EMPTY = watchlist()


def story(
    item_id: str,
    *,
    vertical: str = "ai",
    source_id: str = "feed-a",
    title: str = "Something happened",
    rank_score: float | None = 1.0,
    carried_by: int | None = 1,
    band: ConfidenceBand = ConfidenceBand.HIGH,
    truncated: bool = False,
    published_at: str | None = "2026-08-31T09:00:00Z",
    time_source: TimeSource | None = TimeSource.FEED,
    source_kind: SourceKind = "reporting",
) -> DigestItem:
    """One published story, with every field the block reads set explicitly."""
    return DigestItem(
        item_id=item_id,
        vertical=vertical,
        title=title,
        source_url=f"https://example.test/{item_id}",
        source_id=source_id,
        source_name=source_id,
        source_kind=source_kind,
        published_at=published_at,
        time_source=time_source,
        summary="A summary.",
        band=band,
        truncated=truncated,
        introduced_by_run=1,
        carried_by=carried_by,
        rank_score=rank_score,
    )


def five_desks(**overrides: object) -> list[DigestItem]:
    """One eligible story on each of five desks, descending by score.

    Every one of them is the lead story of its own desk, so every one carries
    the desk sentence and the block fills without any subject at all.
    """
    return [
        story(
            f"{desk}-{index:010d}",
            vertical=desk,
            source_id=f"feed-{desk}",
            title=f"A story on {desk}",
            rank_score=2.0 - index / 10,
            **overrides,  # type: ignore[arg-type]
        )
        for index, desk in enumerate(DESKS)
    ]


def choose(
    items: list[DigestItem],
    *,
    wl: Watchlist = EMPTY,
    now: str = NOW,
    placement: PlacementConfig | None = None,
    taxonomy: Taxonomy | None = None,
    **knobs: object,
) -> list[str]:
    leads = leading_stories(
        items,
        date="2026-08-31",
        watchlist=wl,
        taxonomy=taxonomy or load().taxonomy,
        ui=UiConfig(**knobs),  # type: ignore[arg-type]
        placement=placement or PlacementConfig(),
        now=now,
        desk_names=DESKS,
    )
    return [lead.item_id for lead in leads]


def reasons(items: list[DigestItem], *, wl: Watchlist = EMPTY, **knobs: object) -> dict[str, str]:
    leads = leading_stories(
        items,
        date="2026-08-31",
        watchlist=wl,
        taxonomy=load().taxonomy,
        ui=UiConfig(**knobs),  # type: ignore[arg-type]
        placement=PlacementConfig(),
        now=NOW,
        desk_names=DESKS,
    )
    return {lead.item_id: lead.reason for lead in leads}


# --- the block's shape ------------------------------------------------------


def test_the_block_holds_the_configured_count_and_never_more() -> None:
    """Ten eligible stories, two on each of five desks, and five leads."""
    items = [
        story(
            f"{desk}-{index * 10 + rank:010d}",
            vertical=desk,
            source_id=f"feed-{desk}-{rank}",
            rank_score=2.0 - index / 10 - rank / 100,
            carried_by=2,
        )
        for index, desk in enumerate(DESKS)
        for rank in range(2)
    ]
    assert len(choose(items)) == UiConfig().leading_stories
    assert len(choose(items, leading_stories=3)) == 3


def test_the_block_takes_the_strongest_stories_and_not_the_head_of_the_order() -> None:
    """Finding 1: the published order opens on whichever desk sorted first.

    The list handed in is deliberately in the worst order the payload can be
    in - the weakest desk first - and the block still opens on the strongest
    story.
    """
    items = list(reversed(five_desks()))
    assert choose(items)[0] == "ai-0000000000"


def test_below_the_minimum_the_block_does_not_render() -> None:
    """Four real leads beat five with one filler, and two beat three."""
    assert choose(five_desks()[:2]) == []
    assert len(choose(five_desks()[:3])) == 3


def test_a_desk_may_not_hold_more_than_its_share() -> None:
    items = [
        story(
            f"ai-{index:010d}",
            source_id=f"feed-{index}",
            rank_score=2.0 - index / 10,
            carried_by=2,
        )
        for index in range(4)
    ] + five_desks()[1:]
    chosen = choose(items)
    assert sum(1 for item_id in chosen if item_id.startswith("ai-")) == UiConfig().leading_per_desk
    capped = choose(items, leading_per_desk=1)
    assert sum(1 for item_id in capped if item_id.startswith("ai-")) == 1


def test_one_publication_may_hold_one_lead() -> None:
    """Otherwise a busy newsroom is the whole first screen."""
    items = five_desks()
    items[0] = items[0].model_copy(update={"source_id": "one-newsroom"})
    items[1] = items[1].model_copy(update={"source_id": "one-newsroom"})

    chosen = choose(items)

    assert len(chosen) == len(DESKS) - 1
    assert sum(item_id in {items[0].item_id, items[1].item_id} for item_id in chosen) == 1


def test_one_subject_may_hold_one_lead_however_many_desks_it_crosses() -> None:
    """The fourth cap, and the reason it is a cap rather than a decay.

    A running story crosses desks and sources, so the first three caps do not
    bound it: three of five would clear all of them.
    """
    items = five_desks()
    items[0] = items[0].model_copy(update={"title": "Nvidia does something"})
    items[1] = items[1].model_copy(update={"title": "Nvidia reports a change"})

    chosen = choose(items, wl=REGISTRY)

    assert len({items[0].item_id, items[1].item_id} & set(chosen)) == 1


def test_a_second_story_dated_yesterday_is_refused() -> None:
    """One late arrival is a catch-up; a second is beyond today's allowance."""
    items = [
        story(
            f"{desk}-{index:010d}",
            vertical=desk,
            source_id=f"feed-{index}",
            rank_score=2.0 - index / 10,
            published_at=(
                "2026-08-30T09:00:00Z" if index < 2 else "2026-08-31T09:00:00Z"
            ),
        )
        for index, desk in enumerate(DESKS)
    ]
    chosen = choose(items)
    yesterday = {
        item.item_id for item in items if item.published_at == "2026-08-30T09:00:00Z"
    }
    assert len(set(chosen) & yesterday) == 1
    assert len(choose(items, lead_max_yesterday=5)) == UiConfig().leading_stories


def test_every_lead_names_a_story_the_day_holds() -> None:
    items = five_desks()
    chosen = set(choose(items))
    assert chosen <= {item.item_id for item in items}


def test_two_builds_of_one_day_choose_the_same_five() -> None:
    """The tie-break is the item id, which is derived from the address."""
    items = five_desks()
    items[1] = items[1].model_copy(update={"rank_score": items[0].rank_score})

    forward = choose(items)
    backward = choose(list(reversed(items)))

    assert forward == backward
    assert forward.index(items[0].item_id) < forward.index(items[1].item_id)


# --- age, read at the hour the block is chosen ------------------------------


def one_running_one_fresh() -> list[DigestItem]:
    """Two stories alike in every signal but when they appeared.

    The older one scores slightly higher, which is what makes the pair worth
    testing: with no clock the block takes it every time, whatever the hour.
    Three more desks come with them because the block does not render below its
    minimum.
    """
    return [
        story(
            "ai-0000000001",
            source_id="feed-running",
            title="A story that has been running",
            rank_score=2.05,
            published_at="2026-08-29T10:00:00Z",
        ),
        story(
            "energy-0000000002",
            vertical="energy",
            source_id="feed-fresh",
            title="A story that broke this morning",
            rank_score=2.0,
            published_at="2026-08-31T09:00:00Z",
        ),
        *five_desks()[2:],
    ]


def test_a_story_that_has_been_running_ranks_below_one_that_broke_today() -> None:
    """Two days old against an hour old, and the older one scores higher.

    `rank_score` is fixed at the run that planned the item, so the two-day-old
    story still carries the freshness bonus it earned two days ago. Reading the
    clock here is what takes it back.
    """
    chosen = choose(one_running_one_fresh())
    assert chosen.index("energy-0000000002") < chosen.index("ai-0000000001")


def test_the_same_pair_with_the_decay_switched_off_is_ordered_as_it_was() -> None:
    """The revert half: `freshness_decay_at_scale` of 1.0 restores the old order.

    One edit to one line puts the higher stored score back on top, which is
    what this block did before the curve existed.
    """
    off = PlacementConfig(freshness_decay_at_scale=1.0)
    chosen = choose(one_running_one_fresh(), placement=off)
    assert chosen.index("ai-0000000001") < chosen.index("energy-0000000002")


def test_two_stories_of_one_age_keep_their_order_whatever_that_age_is() -> None:
    """Why the curve multiplies rather than adding, as a check and not a comment.

    Two stories of the same age are multiplied by the same number, so their
    order cannot change however old they both are. A freshness term that added
    would close the gap between a strong story and a weak one instead, and at
    some age it would close it entirely.
    """
    for when in ("2026-08-31T09:00:00Z", "2026-08-29T10:00:00Z"):
        items = one_running_one_fresh()
        items[0] = items[0].model_copy(update={"published_at": when})
        items[1] = items[1].model_copy(update={"published_at": when})
        chosen = choose(items)
        assert chosen.index("ai-0000000001") < chosen.index("energy-0000000002")


def test_freshness_multiplies_the_rank_score() -> None:
    placement = PlacementConfig(
        freshness_offset_hours=0,
        freshness_scale_hours=24,
        freshness_decay_at_scale=0.5,
    )
    items = [
        story(
            "ai-0000000001",
            source_id="feed-ai",
            rank_score=3.0,
            published_at="2026-08-30T10:00:00Z",
        ),
        story(
            "energy-0000000002",
            vertical="energy",
            source_id="feed-energy",
            rank_score=2.0,
            published_at=NOW,
        ),
        story("world-0000000003", vertical="world", source_id="feed-world", rank_score=1.0),
        story("india-0000000004", vertical="india", source_id="feed-india", rank_score=0.9),
        story(
            "business-economy-0000000005",
            vertical="business-economy",
            source_id="feed-business",
            rank_score=0.8,
        ),
    ]
    old_age_hours = 24.0
    past_shoulder = max(0.0, old_age_hours - placement.freshness_offset_hours)
    old_multiplier = placement.freshness_decay_at_scale ** (
        (past_shoulder / placement.freshness_scale_hours) ** 2
    )
    assert 3.0 * old_multiplier < 2.0

    chosen = choose(items, placement=placement)

    assert chosen.index(items[1].item_id) < chosen.index(items[0].item_id)


def test_the_evening_run_of_a_day_does_not_lead_on_the_morning_story() -> None:
    """The defect this closes, in the shape the row described it.

    A story planned at 02:20 held the freshness it earned at 02:20 for the rest
    of the day, so at the evening run it still outranked something that broke an
    hour before. Same day, same stories, chosen twice: the early run opens on
    the story that was fresh then, and the evening run opens on the one that is
    fresh now.
    """
    items = one_running_one_fresh()
    items[0] = items[0].model_copy(update={"published_at": "2026-08-31T02:20:00Z"})
    items[1] = items[1].model_copy(update={"published_at": "2026-08-31T18:30:00Z"})
    assert choose(items, now="2026-08-31T03:00:00Z")[0] == "ai-0000000001"
    assert choose(items, now="2026-08-31T19:00:00Z")[0] == "energy-0000000002"


# --- the weighted score -----------------------------------------------------


def test_the_weights_bind_and_the_top_story_is_not_the_top_rank_score() -> None:
    """The whole point of a composite: another signal can change the answer.

    The weaker story was carried by four other sources. At the shipped weight
    of zero that buys it nothing; at a weight a person could set it takes the
    first slot off a story that scored higher at plan time.
    """
    items = five_desks()
    items[1] = items[1].model_copy(update={"also_covered_by": 4})
    assert choose(items)[0] == items[0].item_id
    assert choose(items, lead_also_covered_weight=0.1)[0] == items[1].item_id


def test_rank_carriage_outranks_a_qualifying_shared_subject_in_the_block() -> None:
    """The committed carriage step beats a smaller subject term in the real path."""
    configured = load()
    app = configured.app
    ui = app.ui

    def planned_story(
        item_id: str,
        *,
        vertical: str,
        url: str,
        title: str,
        source_ids: list[str],
        feed_weight: float,
    ) -> tuple[DigestItem, PlannedItem]:
        candidates = [
            Candidate(
                canonical_url=url,
                source_url=url,
                url_key=derive_url_key(url),
                source_id=source_id,
                vertical=vertical,
                tier=1,
                source_form=SourceForm.ARTICLE,
                title=title,
                published_at=NOW,
                weight=feed_weight,
            )
            for source_id in source_ids
        ]
        planned = plan_vertical(
            VerticalDef(id=vertical, display_name=DESKS[vertical], min_feeds=1),
            candidates,
            config=app.collect,
            eligible_feeds=len(source_ids),
            now=NOW,
        ).items
        assert len(planned) == 1
        ranked = planned[0]
        assert ranked.carried_by == len(source_ids)
        return (
            story(
                item_id,
                vertical=vertical,
                source_id=ranked.source_id,
                title=ranked.title or title,
                rank_score=ranked.rank_score,
                carried_by=ranked.carried_by,
                published_at=ranked.published_at,
            ),
            ranked,
        )

    extra, extra_ranked = planned_story(
        "ai-0000000000",
        vertical="ai",
        url="https://extra.example.test/report",
        title="A new chip order",
        source_ids=["extra-feed-a", "extra-feed-b"],
        feed_weight=0.9,
    )
    subject_entries = [
        planned_story(
            f"world-{index + 1:010d}",
            vertical="world",
            url=f"https://subject.example.test/report-{index}",
            title=f"Nvidia reports an update {index}",
            source_ids=[f"subject-feed-{index}"],
            feed_weight=0.9,
        )
        for index in range(ui.lead_cluster_floor)
    ]
    subjects = [item for item, _ in subject_entries]
    subject_ranks = [ranked for _, ranked in subject_entries]
    neutral, neutral_ranked = planned_story(
        "business-economy-0000000000",
        vertical="business-economy",
        url="https://neutral.example.test/report",
        title="A report on business conditions",
        source_ids=["neutral-feed"],
        feed_weight=1.0,
    )
    items = [extra, *subjects, neutral]

    def selected_ids(weights: UiConfig) -> list[str]:
        return [
            item.item_id
            for item in leading_stories(
                items,
                date="2026-08-31",
                watchlist=REGISTRY,
                taxonomy=configured.taxonomy,
                ui=weights,
                placement=app.placement,
                now=NOW,
                desk_names=DESKS,
            )
        ]

    selected = selected_ids(ui)
    selected_without_subject_weight = selected_ids(
        ui.model_copy(update={"lead_shared_subject_weight": 0.0})
    )
    subject_ids = {item.item_id for item in subjects}
    assert selected[0] == extra.item_id
    assert min(selected.index(item_id) for item_id in subject_ids if item_id in selected) < (
        selected.index(neutral.item_id)
    )
    assert selected_without_subject_weight.index(neutral.item_id) < min(
        selected_without_subject_weight.index(item_id)
        for item_id in subject_ids
        if item_id in selected_without_subject_weight
    )

    assert extra_ranked.carriage_step == app.collect.carriage_step
    assert all(ranked.carriage_step == 0.0 for ranked in subject_ranks)
    equal_terms = (
        "authority_score",
        "tier_score",
        "feed_weight",
        "feed_reliability",
        "watchlist_bonus",
        "lens_bonus",
        "recency_bonus",
    )
    assert all(
        getattr(extra_ranked, term) == getattr(subject_ranks[0], term)
        for term in equal_terms
    )
    assert all(ranked.rank_score == subject_ranks[0].rank_score for ranked in subject_ranks)
    assert all(neutral_ranked.rank_score > ranked.rank_score for ranked in subject_ranks)

    cluster = next(
        entry
        for entry in subject_clusters(items, REGISTRY, taxonomy=configured.taxonomy)
        if entry.entity == "nvidia"
    )
    assert cluster.qualifies(ui.lead_cluster_floor)
    assert cluster.sources == {item.source_id for item in subjects}
    assert ui.lead_shared_subject_weight > 0.0


def test_every_weight_but_the_rank_score_at_zero_is_todays_order() -> None:
    """The revert half, and it is what makes the composite safe to land.

    With the two other terms weighted zero the score is the plan-time number,
    which is exactly what this block sorted on before it was a sum.
    """
    items = five_desks()
    items[1] = items[1].model_copy(update={"also_covered_by": 4})
    plain = choose(items, lead_also_covered_weight=0.0, lead_shared_subject_weight=0.0)
    assert plain == [item.item_id for item in items[: UiConfig().leading_stories]]


def test_the_rank_weight_is_a_knob_and_not_a_literal() -> None:
    """Guardrail #6, as a check: change the config and the order changes.

    At a rank weight of zero the plan-time score stops speaking, and the story
    several sources carried leads a block it came fourth in.
    """
    items = five_desks()
    items[3] = items[3].model_copy(update={"also_covered_by": 4})
    assert choose(items, lead_rank_weight=0.0, lead_also_covered_weight=0.1)[0] == (
        items[3].item_id
    )


def test_a_story_the_pass_could_not_read_scores_no_corroboration() -> None:
    """Null is not zero anywhere else in the payload, and it is not a count here.

    Null says the pass could not tell - the day carries no vectors, or this item
    has none. Weighting it as a count would credit a story for corroboration
    nobody found.
    """
    items = five_desks()
    items[1] = items[1].model_copy(update={"also_covered_by": None, "rank_score": 1.85})
    items[2] = items[2].model_copy(update={"also_covered_by": 0, "rank_score": 1.9})
    weighted = choose(items, lead_also_covered_weight=0.1)
    assert weighted == [
        items[0].item_id,
        items[2].item_id,
        items[1].item_id,
        items[3].item_id,
        items[4].item_id,
    ]


# --- eligibility ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("band", ConfidenceBand.LOW),
        ("truncated", True),
        ("time_source", TimeSource.FIRST_SEEN),
    ],
)
def test_an_ineligible_story_never_leads_however_it_ranks(field: str, value: object) -> None:
    """Each rule excludes regardless of rank, and the story still publishes."""
    items = five_desks()
    strongest = items[0].model_copy(update={field: value, "rank_score": 99.0})
    items[0] = strongest
    assert strongest.item_id not in choose(items)


def test_a_story_with_no_time_at_all_cannot_lead() -> None:
    """`time_source` and `published_at` move together in the contract."""
    items = five_desks()
    items[0] = items[0].model_copy(
        update={"published_at": None, "time_source": TimeSource.UNKNOWN, "rank_score": 99.0}
    )
    assert items[0].item_id not in choose(items)


def test_an_announcement_leads_only_where_somebody_reported_the_same_subject() -> None:
    items = five_desks()
    items[0] = items[0].model_copy(update={"source_kind": "announcement", "rank_score": 99.0})
    assert items[0].item_id not in choose(items)

    corroborated = items[0].model_copy(update={"title": "Nvidia ships a chip"})
    reporter = story(
        "world-0000000099",
        vertical="world",
        source_id="a-newsroom",
        title="Nvidia ships a chip, say analysts",
        rank_score=0.1,
    )
    assert corroborated.item_id in choose([corroborated, *items[1:], reporter], wl=REGISTRY)


def test_registry_properties_not_kind_names_control_lead_safety() -> None:
    taxonomy = load().taxonomy
    reporting = taxonomy.source_kind("reporting")
    announcement = taxonomy.source_kind("announcement")
    assert reporting is not None and announcement is not None
    taxonomy = taxonomy.model_copy(
        update={
            "source_kinds": [
                *taxonomy.source_kinds,
                reporting.model_copy(update={"id": "independent-review"}),
                announcement.model_copy(update={"id": "publisher-statement"}),
            ]
        }
    )
    items = five_desks()
    statement = items[0].model_copy(
        update={
            "source_kind": "publisher-statement",
            "rank_score": 99.0,
            "title": "Nvidia ships a chip",
        }
    )
    assert statement.item_id not in choose([statement, *items[1:]], taxonomy=taxonomy)
    reporter = story(
        "world-0000000099",
        vertical="world",
        source_id="independent",
        title="Nvidia ships a chip, say analysts",
        source_kind="independent-review",
        rank_score=0.1,
    )
    assert statement.item_id in choose(
        [statement, *items[1:], reporter], wl=REGISTRY, taxonomy=taxonomy
    )
    no_reporting = taxonomy.model_copy(
        update={
            "source_kinds": [
                entry.model_copy(update={"counts_as_reporting": False})
                for entry in taxonomy.source_kinds
            ]
        }
    )
    assert statement.item_id not in choose(
        [statement, *items[1:], reporter], wl=REGISTRY, taxonomy=no_reporting
    )


def test_an_excluded_story_is_still_in_the_day() -> None:
    """ESCALATE trigger (a): nothing may be dropped, hidden or unpublished.

    The block is a list of ids over a list the day already holds, so this is
    what the whole design rests on - a rule here can only decide what is at the
    top, never what exists.
    """
    items = five_desks()
    items[0] = items[0].model_copy(update={"band": ConfidenceBand.LOW})
    before = [
        (item, item.model_dump(mode="python"))
        for item in items
    ]
    leads = leading_stories(
        items,
        date="2026-08-31",
        watchlist=EMPTY,
        taxonomy=load().taxonomy,
        ui=UiConfig(),
        placement=PlacementConfig(),
        now=NOW,
        desk_names=DESKS,
    )
    assert items == [item for item, _ in before]
    assert [item.model_dump(mode="python") for item in items] == [
        values for _, values in before
    ]
    day = DigestDay(
        version=DigestDay.schema_version(),
        date="2026-08-31",
        generated_at="2026-08-31T10:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at="2026-08-31T10:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(id=desk, display_name=name, count=1) for desk, name in DESKS.items()
        ],
        items=items,
        leads=leads,
    )
    assert items[0].item_id in {item.item_id for item in day.items}
    assert items[0].item_id not in {lead.item_id for lead in day.leads}


# --- the shared-subject term ------------------------------------------------


def carriers(entity: str, count: int, *, kind: SourceKind = "reporting") -> list[DigestItem]:
    return [
        story(
            f"world-{900 + index:010d}",
            vertical="world",
            source_id=f"carrier-{index}",
            title=f"{entity} in the news",
            rank_score=0.5,
            source_kind=kind,
        )
        for index in range(count)
    ]


def test_a_subject_under_the_floor_earns_nothing() -> None:
    below = subject_clusters(carriers("Nvidia", 2), REGISTRY, taxonomy=load().taxonomy)
    assert [cluster.qualifies(3) for cluster in below] == [False]
    at_floor = subject_clusters(carriers("Nvidia", 3), REGISTRY, taxonomy=load().taxonomy)
    assert [cluster.qualifies(3) for cluster in at_floor] == [True]

    items = [
        story(
            "ai-0000000000",
            title="Nvidia reports a change",
            rank_score=1.0,
            source_id="feed-ai",
        ),
        story(
            "energy-0000000001",
            vertical="energy",
            title="Nvidia announces a plan",
            rank_score=0.9,
            source_id="feed-energy",
        ),
        story(
            "world-0000000002",
            vertical="world",
            title="A reactor is ordered",
            rank_score=1.1,
            source_id="feed-world",
        ),
        story(
            "india-0000000003",
            vertical="india",
            title="A court hears a case",
            rank_score=0.8,
            source_id="feed-india",
        ),
        story(
            "business-economy-0000000004",
            vertical="business-economy",
            title="A company reports results",
            rank_score=0.7,
            source_id="feed-business",
        ),
    ]
    assert choose(
        items,
        wl=REGISTRY,
        lead_cluster_floor=3,
        lead_shared_subject_weight=0.2,
    )[0] == items[2].item_id


def test_one_source_filing_four_pieces_is_one_source() -> None:
    """Decision 2: one item per source per entity."""
    filed = [
        story(
            f"world-{index:010d}",
            vertical="world",
            source_id="one-newsroom",
            title="Nvidia in the news",
        )
        for index in range(4)
    ]
    cluster = subject_clusters(filed, REGISTRY, taxonomy=load().taxonomy)[0]
    assert len(cluster.sources) == 1
    assert len(cluster.item_ids) == 4
    assert cluster.qualifies(3) is False


def test_a_cluster_of_announcements_is_a_press_schedule_and_not_a_story() -> None:
    announced = subject_clusters(
        carriers("Nvidia", 4, kind="announcement"), REGISTRY, taxonomy=load().taxonomy
    )
    assert [cluster.qualifies(3) for cluster in announced] == [False]


def test_a_story_naming_two_subjects_takes_the_larger_weight_and_never_the_sum() -> None:
    """The rule the lens bonus already follows.

    Two of the day's subjects in one title is not twice the story. The check is
    that one weight is all it can buy: a rival scoring one weight plus a whisker
    higher still leads, which it could not if the two subjects were summed.
    """
    weight = 0.2
    both = story(
        "ai-0000000000",
        title="Nvidia and OpenAI announce a deal",
        rank_score=1.0,
        source_id="lead-feed",
    )
    rival = story(
        "energy-0000000000",
        vertical="energy",
        title="A reactor is ordered",
        rank_score=1.0 + weight + 0.01,
        source_id="rival-feed",
        carried_by=2,
    )
    openai_carriers = [
        entry.model_copy(update={"item_id": f"india-{index:010d}", "vertical": "india"})
        for index, entry in enumerate(carriers("OpenAI", 3))
    ]
    chosen = choose(
        [both, rival, *carriers("Nvidia", 3), *openai_carriers],
        wl=REGISTRY,
        leading_min=1,
        lead_shared_subject_weight=weight,
    )
    assert chosen[0] == rival.item_id, (
        "a story naming two running subjects outranked a rival worth one weight "
        "more, so the term is being summed rather than taken at its ceiling"
    )
    assert both.item_id in chosen


# --- the why-line -----------------------------------------------------------


def test_the_strongest_true_sentence_wins() -> None:
    """The order Editor set, checked one preference at a time."""
    subject = story(
        "ai-0000000000", title="Nvidia ships a chip", rank_score=3.0, source_id="lead-feed"
    )
    told = reasons([subject, *carriers("Nvidia", 3), *five_desks()[1:]], wl=REGISTRY)
    assert told[subject.item_id] == "Four of today's stories are about Nvidia."


def test_a_watchlist_name_is_the_sentence_when_the_subject_is_not_running() -> None:
    named = story(
        "ai-0000000000", title="Apple does something", rank_score=3.0, source_id="lead-feed"
    )
    told = reasons([named, *five_desks()[1:]], wl=REGISTRY)
    assert told[named.item_id] == "Apple is on our watchlist."


def test_a_carried_address_says_how_it_reached_us_and_never_who_covered_it() -> None:
    """`carried_by` counts syndication of one address, so the sentence says so."""
    carried = story("ai-0000000000", rank_score=3.0, carried_by=3, source_id="lead-feed")
    told = reasons([carried, *five_desks()[1:]])
    assert told[carried.item_id] == "The same report reached us through three of our feeds."


def test_the_desk_sentence_is_only_true_of_the_desks_own_lead() -> None:
    """It is the fallback, and it still has to be true.

    A story that is not the strongest on its desk cannot say it is, so it
    carries no sentence - and a lead with nothing true to say is not a lead.
    """
    strongest = story("ai-0000000000", rank_score=3.0, source_id="feed-one")
    second = story("ai-0000000001", rank_score=2.5, source_id="feed-two")
    told = reasons([strongest, second, *five_desks()[1:]], leading_stories=6)
    assert told[strongest.item_id] == "The lead story on our AI desk."
    assert second.item_id not in told


def test_a_lead_that_cannot_say_anything_true_is_not_a_lead() -> None:
    weak = story("ai-0000000009", rank_score=0.1, source_id="feed-nine")
    chosen = choose([*five_desks()[:4], weak], leading_per_desk=2)
    assert len(chosen) == 4
    assert weak.item_id not in chosen


@pytest.mark.parametrize(
    ("story_count", "expected"),
    [
        (12, "Twelve of today's stories are about OpenAI."),
        (13, "13 of today's stories are about OpenAI."),
    ],
)
def test_a_count_switches_from_a_word_to_a_numeral_at_thirteen(
    story_count: int, expected: str
) -> None:
    subject = story(
        "ai-0000000000", title="OpenAI does something", rank_score=3.0, source_id="lead-feed"
    )
    many = [
        entry.model_copy(update={"item_id": f"india-{100 + index:010d}", "vertical": "india"})
        for index, entry in enumerate(carriers("OpenAI", story_count - 1))
    ]
    told = reasons([subject, *many, *five_desks()[1:]], wl=REGISTRY)
    assert told[subject.item_id] == expected


def test_no_sentence_is_offered_for_recency() -> None:
    """The rail already prints the time; being newer is not a reason to lead."""
    lead = story("ai-0000000000", rank_score=3.0, source_id="feed-one")
    newer = story(
        "ai-0000000001",
        rank_score=2.9,
        source_id="feed-two",
        published_at="2026-08-31T23:00:00Z",
    )
    told = reasons([lead, newer, *five_desks()[1:]])
    assert told[lead.item_id] == "The lead story on our AI desk."
    assert newer.item_id not in told


def test_a_weighted_signal_does_not_replace_a_true_desk_reason() -> None:
    weighted = story(
        "ai-0000000000",
        rank_score=1.0,
        source_id="feed-one",
        carried_by=1,
    ).model_copy(update={"also_covered_by": 4})
    rival = story(
        "energy-0000000001",
        vertical="energy",
        rank_score=1.1,
        source_id="feed-two",
    )
    told = reasons(
        [weighted, rival, *five_desks()[2:]],
        lead_also_covered_weight=0.1,
    )
    assert told[weighted.item_id] == "The lead story on our AI desk."


def test_the_front_page_vote_is_not_a_sentence() -> None:
    """Measured 2026-09-01: `on_front_page` is false on all 490 committed
    stories that record it and absent on the other 3,596.

    It also cannot name its own source. The flag says a salience feed voted,
    and the two active ones are `Hacker News front page` and `Hacker News
    best` - so a sentence naming the front page is false whenever the other
    one voted, which is the falsity the row's own rejected alternative 4 rules
    out. What a reader loses is a line on about one story in 160; the sentence
    below it in the order takes its place.
    """
    voted = story("ai-0000000000", rank_score=3.0, source_id="feed-one")
    told = reasons([voted.model_copy(update={"on_front_page": True}), *five_desks()[1:]])
    assert told[voted.item_id] == "The lead story on our AI desk."


# --- the counters -----------------------------------------------------------


def test_the_block_records_its_line_coverage(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="idhazh"):
        choose(five_desks())
    assert any("coverage=" in record.getMessage() for record in caplog.records)


def test_a_notable_story_left_out_says_which_rule_left_it_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Decision 15's omission log.

    No story a reader could see the case for is absent from the block without
    the build log naming the rule.
    """
    notable = story(
        "world-0000000099",
        vertical="world",
        source_id="carrier-0",
        title="Nvidia in the news",
        rank_score=0.01,
        carried_by=4,
    )
    with caplog.at_level(logging.INFO, logger="idhazh"):
        choose([notable, *carriers("Nvidia", 3), *five_desks()], wl=REGISTRY)
    said = " ".join(record.getMessage() for record in caplog.records)
    assert f"omitted item={notable.item_id} because=" in said


# --- a real day is not read here -------------------------------------------
#
# Two questions used to open every committed day. One is gone and one is built.
# "Does a real day supply enough eligible stories to fill the block?" is about
# the news, not the code, so it is not a pytest (Guardrail #12); the code property -
# the block fills to its cap when the supply is there - is
# `test_the_block_holds_the_configured_count_and_never_more` above, and the
# data-supply signal, if wanted, is an operator surface under `backend/utilities/`.
# The other question is below, driven from a built payload rather than from
# whatever old day still sits in the tree.


def test_a_day_written_before_the_block_existed_reads_as_no_block() -> None:
    """A payload with no `leads` key reads as an empty block, never as a broken one.

    Driven from a payload with the key removed rather than by looking for an old
    day in the tree. Whether such a day is still inside the retention window is a
    fact about the calendar, and looking costs one parse per published day.
    """
    items = five_desks()
    payload = json.loads(
        DigestDay(
            version=DigestDay.schema_version(),
            date="2026-08-31",
            generated_at="2026-08-31T10:00:00Z",
            partial=False,
            items_planned=len(items),
            items_failed=0,
            runs=[DigestRunRef(n=1, at="2026-08-31T10:00:00Z", items_added=len(items))],
            verticals=[
                DigestVerticalRef(id=desk, display_name=name, count=1)
                for desk, name in DESKS.items()
            ],
            items=items,
            leads=[],
        ).to_json()
    )
    del payload["leads"]
    assert DigestDay.model_validate(payload).leads == []
