"""Does changing a desk floor or ceiling change the filing with no source edit?"""

from __future__ import annotations

from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy, VerticalDef
from idhazh.placement import DeskBounds, desk_bounds, refile, stream_order

from ._days import (
    BOUNDS,
    filed,
    gated_day,
    heavy_ai_day,
)


def test_changing_a_ceiling_changes_the_filing_with_no_source_edit() -> None:
    """Guardrail #6's substitution test, run on the desk ceiling."""
    day = heavy_ai_day()
    ruled = filed(refile(stream_order(day), bounds=BOUNDS))
    tighter = filed(
        refile(stream_order(day), bounds={**BOUNDS, "ai": DeskBounds(floor=6, ceiling=0.2)})
    )

    assert ruled["ai"] == 14
    assert tighter["ai"] == 8
    assert sum(ruled.values()) == sum(tighter.values()) == 40


def test_changing_a_floor_changes_the_filing_with_no_source_edit() -> None:
    day = gated_day()
    ruled = filed(refile(stream_order(day), bounds=BOUNDS, closed=frozenset({"world"})))
    raised = filed(
        refile(
            stream_order(day),
            bounds={**BOUNDS, "energy": DeskBounds(floor=3, ceiling=0.25)},
            closed=frozenset({"world"}),
        )
    )

    assert ruled["energy"] == 6
    assert raised["energy"] == 6, "the ceiling still admits six, and a lower floor asks for fewer"
    assert sum(ruled.values()) == sum(raised.values()) == 24


def test_a_desk_with_no_rule_may_hold_the_whole_day() -> None:
    """An absent rule is no rule, so the defaults are the two identity values."""
    default = VerticalDef(id="ai", display_name="AI", definition="A desk.", min_feeds=21)

    assert (default.floor, default.ceiling) == (0, 1.0)

    day = heavy_ai_day()
    out = refile(stream_order(day), bounds={})

    assert filed(out) == {"ai": 40}


def test_the_bounds_come_off_the_taxonomy_including_a_retired_desk() -> None:
    """A day published last month can still hold a desk this file has retired.

    Leaving it out would hand that desk no rule rather than the rule it had,
    which on a heavy day is the difference between a ceiling and none.
    """
    taxonomy = Taxonomy(
        version=Taxonomy.schema_version(),
        verticals=[
            VerticalDef(id="ai", display_name="AI", definition="A desk.", min_feeds=21,
                        floor=6, ceiling=0.35),
            VerticalDef(id="legacy", display_name="Legacy", min_feeds=21, floor=4, ceiling=0.1,
                        status=LifecycleStatus.RETIRED, retired_on="2026-04-12"),
        ],
        lenses=[],
        events=[],
    )

    assert desk_bounds(taxonomy) == {
        "ai": DeskBounds(floor=6, ceiling=0.35),
        "legacy": DeskBounds(floor=4, ceiling=0.1),
    }
