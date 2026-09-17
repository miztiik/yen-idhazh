"""The built days and the knobs every placement module reads."""

from __future__ import annotations

from collections import Counter

from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.knobs.placement import PlacementConfig
from idhazh.placement import DeskBounds, place, refile, stream_order

#: The five desks the taxonomy declares today.
DESKS = ("india", "world", "ai", "energy", "business-economy")


#: The floor and the ceiling the Editor ruled on 2026-09-13, as
#: `config/taxonomy.json` carries them. Repeated here rather than read off the
#: file, so a test that fails says which of the two moved.
BOUNDS = {
    "ai": DeskBounds(floor=6, ceiling=0.35),
    "energy": DeskBounds(floor=6, ceiling=0.25),
    "business-economy": DeskBounds(floor=6, ceiling=0.25),
    "world": DeskBounds(floor=6, ceiling=0.4),
    "india": DeskBounds(floor=6, ceiling=0.4),
}


def story(
    item_id: str,
    *,
    vertical: str,
    source_id: str,
    rank_score: float | None,
    desk: str | None = None,
    secondary_desk: str | None = None,
    published_at: str | None = "2026-09-13T09:00:00Z",
    introduced_by_run: int = 1,
) -> DigestItem:
    """One published story, with every field the frame reads set explicitly."""
    return DigestItem(
        item_id=item_id,
        vertical=vertical,
        desk=desk,
        secondary_desk=secondary_desk,
        title="Something happened",
        source_url=f"https://example.test/{item_id}",
        source_id=source_id,
        source_name=source_id,
        summary="A summary.",
        key_points=["A point."],
        band=ConfidenceBand.HIGH,
        introduced_by_run=introduced_by_run,
        published_at=published_at,
        rank_score=rank_score,
    )


def desk_of(item: DigestItem) -> str:
    return item.desk or item.vertical


def lopsided_day() -> list[DigestItem]:
    """A day built to break the frame, which no committed day has ever been.

    The top twenty by score are eighteen `india` stories and two others, and the
    top ten are nine stories from one feed and one from a second. Every other
    desk then supplies eight stories from eight distinct feeds, so the frame has
    somewhere to go: without that supply the day could not fill a capped head and
    the test would be measuring the shortage instead of the cap.
    """
    items: list[DigestItem] = []
    score = 100.0

    for index in range(9):
        items.append(
            story(f"india-pti-{index:02d}", vertical="india", source_id="feed-pti", rank_score=score)
        )
        score -= 1.0
    for index in range(9):
        items.append(
            story(
                f"india-other-{index:02d}",
                vertical="india",
                source_id=f"feed-india-{index}",
                rank_score=score,
            )
        )
        score -= 1.0
    items.append(story("world-top-00", vertical="world", source_id="feed-reuters", rank_score=score))
    score -= 1.0
    items.append(story("ai-top-00", vertical="ai", source_id="feed-verge", rank_score=score))
    score -= 1.0

    for desk in ("world", "ai", "energy", "business-economy"):
        for index in range(8):
            items.append(
                story(
                    f"{desk}-{index:02d}",
                    vertical=desk,
                    source_id=f"feed-{desk}-{index}",
                    rank_score=score,
                )
            )
            score -= 1.0
    return items


def frame(**knobs: int) -> PlacementConfig:
    return PlacementConfig(**knobs)


def heavy_ai_day() -> list[DigestItem]:
    """Forty stories, every one of which reads AI, carried by five desks' feeds.

    The day a model-read desk makes possible and the archive has never produced: a
    model reads every article onto one desk while the feeds that carried them
    are spread across five. Without the ceiling this is a one-desk digest with
    four empty rails, on exactly the day a reader most needs the other four.
    """
    return [
        story(
            f"{DESKS[index % 5]}-heavy-{index:02d}",
            vertical=DESKS[index % 5],
            desk="ai",
            source_id=f"feed-{index}",
            rank_score=100.0 - index,
        )
        for index in range(40)
    ]


def gated_day() -> list[DigestItem]:
    """A day where two thin desks can only be filled from something refused.

    `world` is thin because this run found fewer live feeds than its floor, so
    it planned nothing and will render nothing - five stories its feeds carried
    on an earlier run are in the day, relabelled onto `ai`, and sending them back
    would publish under a name this day's own payload says planned nothing.
    `business-economy` is thin because what would have filled it was past
    `collect.max_age_hours`, so it never became a story at all and nothing in the
    day names that desk.

    The only lawful supply is the six `energy` stories relabelled onto `ai`. A
    naive rule that filled a floor from whatever was left would reach the five
    `world` stories first, because they outscore the day's tail.
    """
    day = [
        story(f"ai-bulk-{index:02d}", vertical="ai", desk="ai", source_id=f"feed-a{index}",
              rank_score=100.0 - index)
        for index in range(10)
    ]
    day += [
        story(f"energy-relabelled-{index:02d}", vertical="energy", desk="ai",
              source_id=f"feed-e{index}", rank_score=90.0 - index)
        for index in range(6)
    ]
    day += [
        story(f"world-relabelled-{index:02d}", vertical="world", desk="ai",
              source_id=f"feed-w{index}", rank_score=84.0 - index)
        for index in range(5)
    ]
    day.append(
        story("energy-own-00", vertical="energy", desk="energy", source_id="feed-e9",
              rank_score=79.0)
    )
    day += [
        story(f"business-economy-own-{index:02d}", vertical="business-economy",
              desk="business-economy", source_id=f"feed-b{index}", rank_score=78.0 - index)
        for index in range(2)
    ]
    return day


def filed(items: list[DigestItem]) -> Counter[str]:
    return Counter(desk_of(item) for item in items)


def placed(
    day: list[DigestItem],
    *,
    config: PlacementConfig,
    bounds: dict[str, DeskBounds] | None = None,
) -> list[DigestItem]:
    """`place`, with the four promises its own docstring makes checked every call.

    Call this rather than `place` directly. The promises hold whatever the config
    says and whatever the day looks like, so a test about the desk ceiling checks
    them as cheaply as a test about the head - and a test written next year for
    some other reason inherits every one of them without knowing they exist.

    That is the difference between a rule and a control. All four were written
    down before 2026-09-13 and the one about a later run was written in three
    places; what was missing was somewhere they went red.
    """
    out = place(day, config=config, bounds=bounds)

    assert len(out) == len(day), "a cap shortened the day, and a reader cannot see what is missing"
    assert {item.item_id for item in out} == {item.item_id for item in day}, (
        "the day came back holding stories it was not handed"
    )
    runs = [item.introduced_by_run for item in out]
    assert runs == sorted(runs), "a later run's story moved above one a reader had already read"
    assert filed(out) == filed(refile(stream_order(day), bounds=bounds or {})), (
        "the desk rules were applied to one run's block rather than to the day"
    )
    return out
