"""The same-story pass: what it groups, what it refuses, and what it never loses.

Row #9's oracle is a hand-labelled day. Every group the pass forms on the
2026-08-30 payload was read from the published titles and summaries on
2026-09-01 and marked same-story or not; the labels are written out below and
the test holds the shipped threshold against them.  A group that is two stories
is a false merge, and a false merge is a story that never ran.

**The day is frozen under `tests/fixtures/`, not read from the published tree.**
A hand-labelled judgement is the most expensive artefact in this file and
retention would have deleted the payload it was read off, taking the labels'
meaning with it and turning three tests red on a date nobody chose. The fixture
keeps the four fields the pass actually reads - `item_id`, `source_id`,
`rank_score`, `introduced_by_run` - and every vector, which is 280.6 KB against
the day's 1,041.9 KB. It never grows.

Unit tier for the rules and integration tier for the oracle (CLAUDE.md section
13). Real quantised vectors through the encoder's own wire format throughout.
No mocks, no network.
"""

from __future__ import annotations

import json
import math
import re
from array import array
from base64 import b64decode
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh import config
from idhazh.assemble import (
    EarlierDay,
    collapse_same_story,
    cosine_int8,
    cross_source_pairs,
    numbers_agree,
    story_key,
)
from idhazh.contracts.digest_day import DigestDay, DigestEmbeddings, DigestItem
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.knobs.placement import AssembleConfig, SameStoryConfig
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, cosine, from_base64, to_base64

#: The day the labels below were read off. Closed, so its payload cannot move.
LABELLED_DATE: Final = "2026-08-30"

#: Hand-labelled 2026-09-01 from the published titles and summaries. Keeper ->
#: the items the default view stops drawing, and what the story is.
#:
#: - Nepal warns of fresh floods as the death toll reaches 734.
#: - One dead and five hurt in a shooting at a rave in Aarau.
#: - OpenAI stops supplying models to Cursor over its SpaceX ownership.
#: - A ferry capsizes off northern Cyprus, killing seven.
#: - Google Maps renames Lake Ontario to Lake America for US users.
LABELLED_GROUPS: Final = {
    "world-3280041570": ["world-7682627246"],
    "india-6614514195": ["world-3683931166"],
    "india-1300981688": ["india-3930315816"],
    "world-6544659615": ["world-6936460020"],
    "india-6661057661": ["world-2726893923"],
}

#: The highest-scoring pair on that day that a person marked as TWO stories:
#: Ontario's pushback against the renaming, and Google carrying the renaming
#: out. They score 0.9317 against each other, and the shipped threshold has to
#: sit above them or the pushback never ran.
LABELLED_FALSE_PAIR: Final = ("world-8617792855", "business-economy-2218216680")

#: The day the labels were read off, frozen the day the labels were taken.
#: Written by hand once from the then-committed payload; re-taking it means
#: re-taking the labels, which is the point of freezing it.
LABELLED_DAY_FIXTURE: Final = FIXTURES_DIR / "same-story" / "labelled-day.json"


def labelled_day() -> tuple[list[DigestItem], DigestEmbeddings]:
    """The oracle day: 431 stories over 64 sources, and every vector.

    Only the four fields `collapse_same_story` reads are stored, so `item()`
    fills the rest. A title or a summary in here would be article text in the
    repository for no reader - `corpus/` is the one place this project commits
    article text - and would not change one grouping.
    """
    payload = json.loads(read_text(LABELLED_DAY_FIXTURE))
    assert payload["date"] == LABELLED_DATE, "the fixture is not the day the labels were read off"
    items = [
        item(
            one["item_id"],
            source=one["source_id"],
            score=one["rank_score"],
            run=one["introduced_by_run"],
        )
        for one in payload["items"]
    ]
    return items, DigestEmbeddings.model_validate(payload["embeddings"])


def committed_threshold() -> float:
    """What `config/idhazh.json` ships, never a number written out again here."""
    return config.load(CONFIG_DIR).app.assemble.same_story.floor_min


def at(floor: float) -> SameStoryConfig:
    """The shipped weights with the floor moved, so a test names one number.

    Every test below is about what the pass groups rather than about how the
    terms are weighted, and the shipped weights put the whole score on the
    cosine - so a test that names a floor is naming the cosine it wants.
    """
    return SameStoryConfig(floor_min=floor)


def groups_of(items: list[DigestItem]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for item in items:
        if item.same_story_as is not None:
            found.setdefault(item.same_story_as, []).append(item.item_id)
    return found


#: Digits spelled as letters, so a built item's default headline carries no
#: figure. `Story world-01` and `Story world-02` reduce to the same words around
#: two different numbers, which is exactly what `_numbers_clash` refuses - so
#: without this every pair of built items is vetoed and this module cannot test
#: grouping at all. The ids stay distinct, so the headlines do too.
_NO_FIGURES: Final = str.maketrans("0123456789", "abcdefghij")


def unit(degrees: float) -> str:
    """A real quantised vector at a chosen angle, through the wire format.

    Two components carry the whole vector, so the angle between two of these is
    the angle between their arguments and a test can name the similarity it
    wants instead of discovering it.
    """
    radians = math.radians(degrees)
    return to_base64([math.cos(radians), math.sin(radians)] + [0.0] * (DIMENSIONS - 2))


def block(vectors: dict[str, str]) -> DigestEmbeddings:
    return DigestEmbeddings(
        model_id=EMBEDDER_ID, dimensions=DIMENSIONS, dtype=DTYPE, vectors=vectors
    )


def item(
    item_id: str,
    *,
    source: str,
    score: float | None = 1.0,
    run: int = 1,
    title: str | None = None,
    outlet: str | None = None,
    when: str | None = None,
) -> DigestItem:
    return DigestItem(
        item_id=item_id,
        vertical=item_id.rsplit("-", 1)[0],
        title=title if title is not None else f"Story {item_id.translate(_NO_FIGURES)}",
        source_url=f"https://example.test/{item_id}",
        source_id=source,
        source_name=outlet if outlet is not None else source.title(),
        summary="A summary long enough to be a summary.",
        band=ConfidenceBand.HIGH,
        rank_score=score,
        introduced_by_run=run,
        published_at=when,
    )


# --- the window past midnight ----------------------------------------------


def one_story_two_days(
    *, broke: str, picked_up: str
) -> tuple[list[DigestItem], DigestEmbeddings, list[EarlierDay]]:
    """One story, two outlets, two published days, at two times a test chooses.

    Built rather than read off the archive: the pair this row exists for is a
    story that broke late and was picked up the next morning, and the committed
    days cannot be made to hold one at a chosen number of hours apart.
    """
    yesterday = item("world-01", source="wire", score=9.0, when=broke)
    today = item("world-02", source="paper", score=1.0, when=picked_up)
    return (
        [today],
        block({"world-02": unit(0)}),
        [
            EarlierDay(
                date="2026-08-30",
                items=[yesterday],
                embeddings=block({"world-01": unit(0)}),
            )
        ],
    )


def test_a_story_picked_up_inside_the_window_names_the_outlet_that_broke_it() -> None:
    """Thirty hours apart, so an evening break and the next morning's pick-up."""
    items, vectors, earlier = one_story_two_days(
        broke="2026-08-30T22:00:00Z", picked_up="2026-08-31T04:00:00Z"
    )
    stamped = collapse_same_story(
        items, vectors, same_story=at(0.9), window_hours=36.0, earlier=earlier
    )

    assert [one.item_id for one in stamped] == ["world-02"], "nothing is dropped or added"
    assert stamped[0].same_story_as is None, "today's story keeps its own card"
    ran = stamped[0].also_ran_earlier
    assert [(one.date, one.item_id, one.source_name) for one in ran] == [
        ("2026-08-30", "world-01", "Wire")
    ]


def test_a_story_outside_the_window_is_its_own_story() -> None:
    """Forty hours apart, which is a follow-up rather than a pick-up."""
    items, vectors, earlier = one_story_two_days(
        broke="2026-08-29T12:00:00Z", picked_up="2026-08-31T04:00:00Z"
    )
    stamped = collapse_same_story(
        items, vectors, same_story=at(0.9), window_hours=36.0, earlier=earlier
    )

    assert stamped[0].also_ran_earlier == ()
    assert stamped[0].also_covered_by == 0, "no other source of THIS day carried it"


def test_a_window_of_zero_reads_no_earlier_day_at_all() -> None:
    """The revert, and it has to be exact rather than approximate.

    The earlier day is handed in and still reaches nothing, so an operator who
    sets the window to 0 gets the same-day pass this had before the window
    existed - whatever the caller passes.
    """
    items, vectors, earlier = one_story_two_days(
        broke="2026-08-30T22:00:00Z", picked_up="2026-08-31T04:00:00Z"
    )
    stamped = collapse_same_story(
        items, vectors, same_story=at(0.9), window_hours=0.0, earlier=earlier
    )

    assert stamped[0].also_ran_earlier == ()
    assert stamped[0].also_covered_by == 0


def test_the_earlier_day_comes_back_exactly_as_it_went_in() -> None:
    """A published day is finished, so the pass may read it and never write it."""
    items, vectors, earlier = one_story_two_days(
        broke="2026-08-30T22:00:00Z", picked_up="2026-08-31T04:00:00Z"
    )
    before = [one.model_dump_json() for one in earlier[0].items]
    collapse_same_story(items, vectors, same_story=at(0.9), window_hours=36.0, earlier=earlier)

    assert [one.model_dump_json() for one in earlier[0].items] == before


def test_one_outlet_picking_up_its_own_story_is_not_a_group() -> None:
    """The across-outlets rule holds across days too, and it has to.

    One desk running one story on two days is a follow-up slot, which is the
    shape this pass is least able to tell from a recurrence.
    """
    yesterday = item("world-01", source="wire", score=9.0, when="2026-08-30T22:00:00Z")
    today = item("world-02", source="wire", score=1.0, when="2026-08-31T04:00:00Z")
    stamped = collapse_same_story(
        [today],
        block({"world-02": unit(0)}),
        same_story=at(0.9),
        window_hours=36.0,
        earlier=[
            EarlierDay(
                date="2026-08-30", items=[yesterday], embeddings=block({"world-01": unit(0)})
            )
        ],
    )

    assert stamped[0].also_ran_earlier == ()


def test_a_story_nothing_dated_never_reaches_across_a_day() -> None:
    """An undated story cannot be placed in time, so it is refused rather than guessed."""
    yesterday = item("world-01", source="wire", score=9.0, when="2026-08-30T22:00:00Z")
    today = item("world-02", source="paper", score=1.0)
    stamped = collapse_same_story(
        [today],
        block({"world-02": unit(0)}),
        same_story=at(0.9),
        window_hours=36.0,
        earlier=[
            EarlierDay(
                date="2026-08-30", items=[yesterday], embeddings=block({"world-01": unit(0)})
            )
        ],
    )

    assert stamped[0].also_ran_earlier == ()


def test_today_still_groups_with_today_while_the_window_is_open() -> None:
    """The window adds a way in and takes none away."""
    items = [
        item("world-02", source="paper", score=1.0, when="2026-08-31T04:00:00Z"),
        item("world-03", source="desk", score=5.0, when="2026-08-31T05:00:00Z"),
    ]
    stamped = collapse_same_story(
        items,
        block({"world-02": unit(0), "world-03": unit(0)}),
        same_story=at(0.9),
        window_hours=36.0,
        earlier=[
            EarlierDay(
                date="2026-08-30",
                items=[item("world-01", source="wire", score=9.0, when="2026-08-30T22:00:00Z")],
                embeddings=block({"world-01": unit(0)}),
            )
        ],
    )

    assert groups_of(stamped) == {"world-03": ["world-02"]}, "the day's own anchor still wins"
    assert [one.source_name for one in stamped[0].also_ran_earlier] == ["Wire"]
    assert [one.source_name for one in stamped[1].also_ran_earlier] == ["Wire"]


def test_the_count_stays_a_count_of_this_days_sources() -> None:
    """`also_covered_by` is what the card's remainder is worked out from.

    It counts this day's other outlets and nothing else, so the sentence beside
    the names stays true. The earlier outlet is a name in the stack rather than
    a number in the count.
    """
    items = [
        item("world-02", source="paper", score=1.0, when="2026-08-31T04:00:00Z"),
        item("world-03", source="desk", score=5.0, when="2026-08-31T05:00:00Z"),
    ]
    stamped = collapse_same_story(
        items,
        block({"world-02": unit(0), "world-03": unit(0)}),
        same_story=at(0.9),
        window_hours=36.0,
        earlier=[
            EarlierDay(
                date="2026-08-30",
                items=[item("world-01", source="wire", score=9.0, when="2026-08-30T22:00:00Z")],
                embeddings=block({"world-01": unit(0)}),
            )
        ],
    )

    assert [one.also_covered_by for one in stamped] == [1, 1]


# --- the arithmetic --------------------------------------------------------


def test_the_stored_vectors_score_the_same_as_the_decoded_ones() -> None:
    """The pass never decodes a vector, so the shortcut has to be exact.

    `dequantise` divides by the quantisation scale and then normalises, which
    cancels the scale - so the angle between two int8 vectors is the angle
    between the unit vectors they decode to. Computed here through the two
    genuinely separate paths rather than restated.
    """
    for left_angle, right_angle in ((0.0, 18.0), (0.0, 36.0), (12.0, 12.0), (0.0, 90.0)):
        left, right = unit(left_angle), unit(right_angle)
        raw_left, raw_right = array("b", b64decode(left)), array("b", b64decode(right))
        shortcut = cosine_int8(
            raw_left,
            raw_right,
            left_norm=math.sqrt(sum(value * value for value in raw_left)),
            right_norm=math.sqrt(sum(value * value for value in raw_right)),
        )
        decoded = cosine(from_base64(left), from_base64(right))
        assert shortcut == pytest.approx(decoded, abs=1e-9), f"{left_angle} vs {right_angle}"


# --- what the pass does and does not group ---------------------------------


def test_two_sources_carrying_one_story_leave_the_strongest_drawn() -> None:
    items = [
        item("world-01", source="wire", score=1.0),
        item("world-02", source="paper", score=9.0),
    ]
    stamped = collapse_same_story(
        items, block({"world-01": unit(0), "world-02": unit(0)}), same_story=at(0.9)
    )

    assert groups_of(stamped) == {"world-02": ["world-01"]}, "the higher rank_score is kept"
    assert [one.also_covered_by for one in stamped] == [1, 1], (
        "every item of a group carries the count, so the sentence is true whichever is drawn"
    )


def test_nothing_is_unpublished() -> None:
    """ESCALATE trigger (a), as an assertion.

    The pass returns the same items in the same order. It marks; it never drops,
    reorders or rewrites anything a reader can reach.
    """
    items = [item(f"world-0{n}", source="wire" if n % 2 else "paper") for n in range(1, 7)]
    stamped = collapse_same_story(
        items, block({one.item_id: unit(0) for one in items}), same_story=at(0.9)
    )

    assert [one.item_id for one in stamped] == [one.item_id for one in items]
    assert [one.title for one in stamped] == [one.title for one in items]
    assert len([one for one in stamped if one.same_story_as is None]) == 1


def test_one_outlet_publishing_twice_is_not_a_group() -> None:
    """A group is across sources, because the sentence on it is about sources.

    Grouping one outlet's second piece would buy the reader nothing - the
    survivor's sentence is the one it already had - and still cost a story. It
    is also where the encoder is least trustworthy: the Federal Reserve's June
    minutes and its July minutes score 0.9867 against each other on the
    committed 2026-08-25 day and are two different documents.
    """
    items = [item("world-01", source="wire", score=1.0), item("world-02", source="wire", score=9.0)]
    stamped = collapse_same_story(
        items, block({"world-01": unit(0), "world-02": unit(0)}), same_story=at(0.9)
    )

    assert groups_of(stamped) == {}
    assert [one.also_covered_by for one in stamped] == [0, 0]
    assert [one.same_story_as for one in stamped] == [None, None]


def test_a_group_never_chains_through_its_middle() -> None:
    """Every pair inside a group clears the threshold, not only each new joiner.

    A is the same story as B and B as C, while A and C are two different
    stories. Single-link grouping puts all three together and loses A or C; this
    one keeps C drawn.
    """
    items = [
        item("world-01", source="wire", score=9.0),
        item("world-02", source="paper", score=5.0),
        item("world-03", source="agency", score=1.0),
    ]
    vectors = {"world-01": unit(0), "world-02": unit(18), "world-03": unit(36)}
    # 0.9518, 0.9501 and 0.8084 for the three pairs, in that order.
    stamped = collapse_same_story(items, block(vectors), same_story=at(0.93))

    assert groups_of(stamped) == {"world-01": ["world-02"]}
    assert [one.also_covered_by for one in stamped] == [1, 1, 0]


def test_the_count_is_of_other_sources_and_not_of_other_items() -> None:
    """Three items, two sources: each one has exactly one other source."""
    items = [
        item("world-01", source="wire", score=9.0),
        item("world-02", source="paper", score=5.0),
        item("world-03", source="paper", score=1.0),
    ]
    stamped = collapse_same_story(
        items,
        block({one.item_id: unit(0) for one in items}),
        same_story=at(0.9),
    )

    assert groups_of(stamped) == {"world-01": ["world-02", "world-03"]}
    assert [one.also_covered_by for one in stamped] == [1, 1, 1]


# --- one headline, two outlets ---------------------------------------------
#
# The cosine is taken over `title. summary`, and the summary is our own prose
# about ONE article and is 87 percent of what the encoder reads - a median 16
# tokens of headline in a median 121 - so two honest tellings of one
# story are pulled apart by the part that is guaranteed to differ. Measured
# 2026-09-14 over the twenty-five committed days: the fifty-three cross-source
# pairs that share a headline have a median cosine of 0.9177, and the pair
# above is two stories at 0.9317. The populations overlap, so the two cases
# below hold the threshold still and change one thing - the headline.

#: Far enough apart that no threshold this project would ship groups them. The
#: assertion in each case proves it rather than trusting this comment.
_APART: Final = 30.0
#: Close enough that the cosine alone forms a group, for the chaining guard.
_TOGETHER: Final = 45.0


def test_two_sources_with_one_headline_are_one_story_below_the_threshold() -> None:
    """The joined case. Two outlets, one headline, a cosine that never clears."""
    items = [
        item("world-01", source="wire", score=1.0, title="Ferry capsizes off Cyprus, killing seven"),
        item("world-02", source="paper", score=9.0, title="Ferry capsizes off Cyprus killing seven"),
    ]
    vectors = {"world-01": unit(0), "world-02": unit(_APART)}
    assert cosine(from_base64(vectors["world-01"]), from_base64(vectors["world-02"])) < (
        committed_threshold()
    ), "the case is only a test of the headline if the vectors cannot form this group"

    stamped = collapse_same_story(items, block(vectors), same_story=at(committed_threshold()))

    assert groups_of(stamped) == {"world-02": ["world-01"]}, "the higher rank_score is kept"
    assert [one.also_covered_by for one in stamped] == [1, 1]


def test_a_headline_one_word_apart_is_not_a_story_below_the_threshold() -> None:
    """The control case. Everything above, with one word of one headline changed.

    Both cases run at the threshold `config/idhazh.json` ships and both pairs
    carry the same two vectors, so this is the case that goes red if somebody
    answers the defect by lowering `duplicate_similarity_min` instead: a floor
    low enough to group the case above groups this one too.
    """
    items = [
        item("world-01", source="wire", score=1.0, title="Ferry capsizes off Cyprus, killing seven"),
        item("world-02", source="paper", score=9.0, title="Ferry capsizes off Crete killing seven"),
    ]
    stamped = collapse_same_story(
        items,
        block({"world-01": unit(0), "world-02": unit(_APART)}),
        same_story=at(committed_threshold()),
    )

    assert groups_of(stamped) == {}
    assert [one.also_covered_by for one in stamped] == [0, 0]
    assert [one.same_story_as for one in stamped] == [None, None]


def test_a_headline_does_not_chain_a_group_through_its_middle() -> None:
    """Andre's warning, 2026-09-14, as an assertion.

    A shared headline is transitive on its own and a cosine is not, so their
    union is not either. A and B share a headline, B and C clear the cosine, and
    A and C clear neither. Single-link over the union puts all three together
    and loses A or C; every pair inside a group has to clear one of the two.
    """
    items = [
        item("world-01", source="wire", score=9.0, title="Ferry capsizes off Cyprus"),
        item("world-02", source="paper", score=5.0, title="Ferry capsizes off Cyprus."),
        item("world-03", source="agency", score=1.0, title="Rescuers search the Cyprus strait"),
    ]
    vectors = {"world-01": unit(0), "world-02": unit(_APART), "world-03": unit(_TOGETHER)}
    assert cosine(from_base64(vectors["world-02"]), from_base64(vectors["world-03"])) > 0.94
    assert cosine(from_base64(vectors["world-01"]), from_base64(vectors["world-03"])) < 0.94

    stamped = collapse_same_story(items, block(vectors), same_story=at(0.94))

    assert groups_of(stamped) == {"world-01": ["world-02"]}
    assert [one.also_covered_by for one in stamped] == [1, 1, 0]


def test_one_outlet_running_one_headline_twice_is_still_not_a_group() -> None:
    """The across-sources rule holds over the new way in as well.

    One desk running one title on two days is a recurring slot, not a story
    covered twice. Over the twenty-five committed days, twelve of the 9,333
    (source, headline) pairs repeat across days, and two of them are an
    extraction failure the summariser titled.
    """
    items = [
        item("world-01", source="wire", score=1.0, title="Markets wrap"),
        item("world-02", source="wire", score=9.0, title="Markets wrap"),
    ]
    stamped = collapse_same_story(
        items,
        block({"world-01": unit(0), "world-02": unit(_APART)}),
        same_story=at(0.94),
    )

    assert groups_of(stamped) == {}
    assert [one.also_covered_by for one in stamped] == [0, 0]


def test_two_desks_rounding_one_price_are_one_group() -> None:
    """The owner's ruling, 2026-09-14, end to end rather than on the key alone.

    Two decimal places are not a reason to print the same acquisition twice.
    This is the 2026-09-03 Nvidia pair, at vectors that cannot form the group.
    """
    items = [
        item(
            "business-01",
            source="wire",
            score=1.0,
            title="Nvidia agrees to acquire Hugging Face for $12.9 billion",
        ),
        item(
            "business-02",
            source="paper",
            score=9.0,
            title="Nvidia agrees to acquire Hugging Face for $12.93 billion",
        ),
    ]
    vectors = {"business-01": unit(0), "business-02": unit(_APART)}
    assert cosine(from_base64(vectors["business-01"]), from_base64(vectors["business-02"])) < (
        committed_threshold()
    ), "the case is only a test of the headline if the vectors cannot form this group"

    stamped = collapse_same_story(items, block(vectors), same_story=at(committed_threshold()))

    assert groups_of(stamped) == {"business-02": ["business-01"]}
    assert [one.also_covered_by for one in stamped] == [1, 1]


def test_two_desks_printing_different_figures_are_two_groups() -> None:
    """The control for the case above. One word of one headline, one digit apart."""
    items = [
        item("business-01", source="wire", score=1.0, title="Tariff raised to 25 percent"),
        item("business-02", source="paper", score=9.0, title="Tariff raised to 50 percent"),
    ]
    stamped = collapse_same_story(
        items,
        block({"business-01": unit(0), "business-02": unit(_APART)}),
        same_story=at(committed_threshold()),
    )

    assert groups_of(stamped) == {}
    assert [one.also_covered_by for one in stamped] == [0, 0]


def test_one_outlet_on_two_of_its_own_feeds_is_not_a_group() -> None:
    """A feed is not a source. Measured defect, 2026-09-14.

    Four of our feeds are CGTN and two are The Straits Times. The rule used to
    compare `source_id`, which is the feed, so one newsroom counted as two
    sources and the card printed a corroboration the reader did not have: 3 of
    the 43 groups on the committed days were CGTN grouped with CGTN. The
    headlines here are identical, so only the outlet rule can refuse this.
    """
    items = [
        item(
            "world-01",
            source="cgtn-tech",
            score=1.0,
            title="Ferry capsizes off Cyprus",
            outlet="China Global Television Network",
        ),
        item(
            "world-02",
            source="cgtn-china",
            score=9.0,
            title="Ferry capsizes off Cyprus",
            outlet="China Global Television Network",
        ),
    ]
    stamped = collapse_same_story(
        items,
        block({"world-01": unit(0), "world-02": unit(_APART)}),
        same_story=at(committed_threshold()),
    )

    assert groups_of(stamped) == {}
    assert [one.also_covered_by for one in stamped] == [0, 0]


def test_two_mastheads_of_one_owner_are_two_sources() -> None:
    """The rule folds a feed into its masthead and stops there.

    The Hindu and The Hindu BusinessLine are different papers with different
    desks. A reader who sees both has two newsrooms, and folding them would
    cost a group that is genuinely corroborated.
    """
    items = [
        item(
            "world-01",
            source="thehindu-all",
            score=1.0,
            title="Ferry capsizes off Cyprus",
            outlet="The Hindu",
        ),
        item(
            "world-02",
            source="thehindu-biz",
            score=9.0,
            title="Ferry capsizes off Cyprus",
            outlet="The Hindu BusinessLine",
        ),
    ]
    stamped = collapse_same_story(
        items,
        block({"world-01": unit(0), "world-02": unit(_APART)}),
        same_story=at(committed_threshold()),
    )

    assert groups_of(stamped) == {"world-02": ["world-01"]}
    assert [one.also_covered_by for one in stamped] == [1, 1]


def test_turning_the_joiner_off_restores_the_vector_only_rule() -> None:
    """Guardrail #6's substitution test: change the config, change the behaviour."""
    items = [
        item("world-01", source="wire", score=1.0, title="Ferry capsizes off Cyprus"),
        item("world-02", source="paper", score=9.0, title="Ferry capsizes off Cyprus"),
    ]
    vectors = block({"world-01": unit(0), "world-02": unit(_APART)})

    assert groups_of(collapse_same_story(items, vectors, same_story=at(0.94))) != {}
    assert (
        groups_of(
            collapse_same_story(
                items, vectors, same_story=at(0.94), group_identical_titles=False
            )
        )
        == {}
    )


# --- what the pass refuses to guess ----------------------------------------


def test_a_day_with_no_vectors_says_it_does_not_know() -> None:
    """Null, never 0. A day whose encoder never ran carried no claim either way."""
    items = [item("world-01", source="wire"), item("world-02", source="paper")]
    stamped = collapse_same_story(items, None, same_story=at(0.9))

    assert [one.also_covered_by for one in stamped] == [None, None]
    assert [one.same_story_as for one in stamped] == [None, None]


def test_an_item_without_a_vector_says_it_does_not_know() -> None:
    """The rest of the day is still grouped; the item that cannot be is left alone."""
    items = [
        item("world-01", source="wire", score=9.0),
        item("world-02", source="paper", score=5.0),
        item("world-03", source="agency", score=1.0),
    ]
    stamped = collapse_same_story(
        items, block({"world-01": unit(0), "world-02": unit(0)}), same_story=at(0.9)
    )

    assert [one.also_covered_by for one in stamped] == [1, 1, None]
    assert stamped[2].same_story_as is None


def test_a_vector_of_the_wrong_width_is_not_grouped() -> None:
    """A short vector would score against a prefix of its rival and mean nothing."""
    items = [item("world-01", source="wire", score=9.0), item("world-02", source="paper")]
    vectors = {"world-01": unit(0), "world-02": to_base64([1.0] + [0.0] * (DIMENSIONS - 1))[:8]}
    stamped = collapse_same_story(items, block(vectors), same_story=at(0.9))

    assert [one.also_covered_by for one in stamped] == [0, None]


def test_an_item_without_a_vector_is_not_grouped_by_its_headline_either() -> None:
    """A published null that became a number would be a wider claim than this pass makes.

    `also_covered_by` says null when the day could not tell. A matching headline
    does not lift that, because the field's own description promises the null
    means the item carries no vector, and an item nobody encoded is one the pass
    cannot check the rest of the group against.
    """
    items = [
        item("world-01", source="wire", score=9.0, title="Ferry capsizes off Cyprus"),
        item("world-02", source="paper", score=1.0, title="Ferry capsizes off Cyprus"),
    ]
    stamped = collapse_same_story(items, block({"world-01": unit(0)}), same_story=at(0.94))

    assert [one.also_covered_by for one in stamped] == [0, None]
    assert [one.same_story_as for one in stamped] == [None, None]


def test_two_items_nobody_could_title_are_not_one_story() -> None:
    """`Untitled item` is the fallback two sources can both land on.

    It is a headline that names no event, so two of them are evidence of two
    extraction failures and never of one story.
    """
    items = [
        item("world-01", source="wire", score=9.0, title="Untitled item"),
        item("world-02", source="paper", score=1.0, title="Untitled item"),
    ]
    stamped = collapse_same_story(
        items,
        block({"world-01": unit(0), "world-02": unit(_APART)}),
        same_story=at(0.94),
    )

    assert groups_of(stamped) == {}
    assert [one.also_covered_by for one in stamped] == [0, 0]


# --- the headline, reduced -------------------------------------------------


def test_the_reduction_folds_case_and_punctuation() -> None:
    """The three differences two desks make to one headline, and nothing else."""
    one = "Nvidia Agrees to Acquire Hugging Face for $12.93 Billion"
    for other in (
        "nvidia agrees to acquire hugging face for $12.93 billion",
        "NVIDIA agrees to acquire Hugging Face for $12.93 billion",
        "Nvidia agrees to acquire Hugging Face for $12.93 billion.",
        "Nvidia agrees to acquire Hugging Face for \u201c$12.93 billion\u201d",
    ):
        assert story_key(one) == story_key(other), other


def test_the_reduction_keeps_a_script_it_cannot_fold() -> None:
    """Latin is not the rule. Two headlines that share no letter are not one key."""
    assert story_key("\u0938\u092e\u093e\u091a\u093e\u0930 \u090f\u0915") is not None
    assert story_key("\u0938\u092e\u093e\u091a\u093e\u0930 \u090f\u0915") != story_key(
        "\u0938\u092e\u093e\u091a\u093e\u0930 \u0926\u094b"
    )


def test_a_headline_that_reduces_to_nothing_is_not_a_key() -> None:
    """Two headlines of pure punctuation are two failures, not one story."""
    assert story_key("") is None
    assert story_key("   ") is None
    assert story_key("--- ... ---") is None
    assert story_key("Untitled item") is None
    assert story_key("untitled  ITEM.") is None


# --- the numbers in a headline ----------------------------------------------
#
# The words have to match exactly; a number only has to agree to the coarser of
# the two precisions it was written with. Owner ruling, 2026-09-14: two desks
# rounding one figure differently are still reporting one story, and a rule
# that split them would cost the reader a group for two decimal places.
# Measured the same day over the twenty-five committed days, the rule admits
# twelve cross-source pairs the exact-digit rule refused and every one of them
# is the same acquisition - no false merge.


def one_headline(left: str, right: str) -> bool:
    """Would the pass read these two headlines as one story?"""
    first, second = story_key(left), story_key(right)
    if first is None or second is None or first.shape != second.shape:
        return False
    return numbers_agree(first.numbers, second.numbers)


@pytest.mark.parametrize(
    ("left", "right", "why"),
    [
        (
            "Quake kills 2 million",
            "Quake kills 2,000,035",
            "a desk that writes 2 million does not claim the next six digits",
        ),
        (
            "Nvidia agrees to acquire Hugging Face for $12.9 billion",
            "Nvidia agrees to acquire Hugging Face for $13 billion",
            "two digits of precision against three, and they agree at two",
        ),
        (
            "Nvidia agrees to acquire Hugging Face for $12.93 billion",
            "Nvidia agrees to acquire Hugging Face for $12.9 billion",
            "the pair that ran five times on 2026-09-03",
        ),
        (
            "Nvidia agrees to acquire Hugging Face for $12.9bn",
            "Nvidia agrees to acquire Hugging Face for $12.9 billion",
            "the scale word is read into the value, not left in the words",
        ),
    ],
)
def test_two_desks_rounding_one_figure_are_one_story(left: str, right: str, why: str) -> None:
    assert one_headline(left, right), why


@pytest.mark.parametrize(
    ("left", "right", "why"),
    [
        (
            "Tariff raised to 25 percent",
            "Tariff raised to 50 percent",
            "both written to two digits and different inside them",
        ),
        (
            "Budget 2025 lands",
            "Budget 2026 lands",
            "the period label the Editor named as the watch class",
        ),
        (
            "Quake kills 2 million",
            "Quake kills 3 million",
            "one digit each, and one digit is enough to tell these apart",
        ),
        (
            "Ferry sinks, 7 dead",
            "Ferry sinks, 70 dead",
            "rounding is not magnitude-blind",
        ),
        (
            "Toll rises to 104",
            "Toll rises to 100",
            "a trailing zero is a written digit, so 100 claims three of them",
        ),
        (
            "Nvidia acquires Hugging Face for $12.9 billion",
            "Nvidia acquires Hugging Face for $12.9 million",
            "the scale word is part of the value it multiplies",
        ),
    ],
)
def test_two_desks_printing_different_figures_are_two_stories(
    left: str, right: str, why: str
) -> None:
    assert not one_headline(left, right), why


def test_a_headline_with_one_number_is_never_one_with_two() -> None:
    """Counting the numbers is part of matching them.

    A headline that carries a figure the other does not is not the same
    sentence, whatever the figures say.
    """
    assert not one_headline("Deal worth $5 billion agreed", "Deal worth $5 billion agreed by 3")


# --- the composite score ----------------------------------------------------


def test_every_term_runs_zero_to_one() -> None:
    """The one term sits on the floor's scale, or the floor means nothing.

    The cosine is bounded by construction, so this reads it off real pairs
    rather than asserting the construction back at itself.
    """
    items = [
        item("world-01", source="wire"),
        item("india-02", source="paper"),
        item("tech-03", source="feed"),
    ]
    vectors = block({"world-01": unit(0), "india-02": unit(18), "tech-03": unit(90)})
    scored = list(cross_source_pairs(items, vectors))
    assert scored, "three outlets make three cross-source pairs"
    for pair in scored:
        assert 0.0 <= pair.cosine <= 1.0
        assert 0.0 <= pair.score <= 1.0


@pytest.mark.parametrize("cosine_weight", [0.5, 0.0, 0.7, 0.99])
def test_a_cosine_weight_that_is_not_one_is_refused(cosine_weight: float) -> None:
    """A score off 0 to 1 cannot be compared against a floor on 0 to 1.

    The failure this refuses is silent rather than loud: a weight of 0.5 pushes
    every pair down, the floor stops meaning what the labels measured, and the
    day splits a story nobody chose to split. The cosine is the only term, so
    the rule that used to say the weights sum to 1.0 now says this.
    """
    with pytest.raises(ValueError, match=re.escape("the whole same_story score")):
        SameStoryConfig(cosine_weight=cosine_weight)


def test_the_shipped_weight_puts_the_whole_score_on_the_cosine() -> None:
    """The committed config scores exactly what the single floor scored.

    The block's own claim, as an assertion. A pair groups at its cosine alone,
    so no published day can move until a person moves the floor.
    """
    shipped = config.load(CONFIG_DIR).app.assemble.same_story
    assert shipped.cosine_weight == 1.0

    items = [
        item("world-01", source="wire"),
        item("india-02", source="paper"),
    ]
    vectors = block({"world-01": unit(0), "india-02": unit(18)})

    assert groups_of(collapse_same_story(items, vectors, same_story=at(0.94))) != {}
    assert groups_of(collapse_same_story(items, vectors, same_story=at(0.96))) == {}


@pytest.mark.parametrize(
    ("left_title", "right_title", "floor", "grouped", "why"),
    [
        (
            "Union Budget 2025 clears the house",
            "Union Budget 2026 clears the house",
            0.9,
            False,
            "a clash of figures refuses a pair the vectors score above the floor",
        ),
        (
            "Ash closes the airport",
            "Ash closes the airport",
            0.99,
            True,
            "one headline joins a pair the score would leave apart",
        ),
        (
            "Ash closes the airport",
            "Smoke shuts the runway",
            0.99,
            False,
            "everything else is scored, and this pair does not reach the floor",
        ),
    ],
)
def test_the_three_steps_run_in_the_order_the_rule_states(
    left_title: str, right_title: str, floor: float, grouped: bool, why: str
) -> None:
    """Veto, then headline, then score - and each outranks the one below it.

    One pair of vectors throughout, scoring 0.9511, so the only thing that
    moves between the three rows is the headline. The veto has to beat a score
    above the floor, and the headline has to beat a score below it; nothing
    else in this module states both halves against the same evidence.
    """
    items = [
        item("india-01", source="wire", title=left_title),
        item("world-02", source="paper", title=right_title),
    ]
    vectors = block({"india-01": unit(0), "world-02": unit(18)})

    assert bool(groups_of(collapse_same_story(items, vectors, same_story=at(floor)))) is grouped, why


def test_one_headline_carrying_a_figure_the_other_omits_is_scored_not_refused() -> None:
    """Two desks choosing differently about a headline are not two facts.

    On 2026-09-06 the BBC ran `Anak Krakatau eruption suspends flights at
    Jakarta airport` and Mint ran the same words with `300 flights` in them.
    A veto on any unmatched figure refuses that pair, and it is one story - the
    single group over the twenty-six committed days that the broader rule would
    have broken, measured 2026-09-16. So the pair is neither refused nor joined
    at 1.0. It is scored, which is what it was before the veto existed, and the
    second floor below is what proves the difference.
    """
    bare = "Anak Krakatau eruption suspends flights at Jakarta airport"
    figure = "Anak Krakatau eruption suspends 300 flights at Jakarta airport"
    items = [
        item("world-01", source="wire", title=bare),
        item("india-02", source="paper", title=figure),
    ]
    vectors = block({"world-01": unit(0), "india-02": unit(18)})

    assert groups_of(collapse_same_story(items, vectors, same_story=at(0.94))) != {}
    assert groups_of(collapse_same_story(items, vectors, same_story=at(0.96))) == {}


def test_the_veto_reads_the_headline_and_goes_when_the_headline_rule_goes() -> None:
    """Turning the joiner off restores the vector-only rule, veto included.

    The clash is read off the same reduced headline the joiner is, so an
    operator who switches the joiner off gets the pass exactly as it scored
    before either existed. Asserted rather than left to be noticed, because a
    revert path that quietly keeps half of what it reverts is worse than none.
    """
    items = [
        item("india-01", source="wire", title="Union Budget 2025 clears the house"),
        item("world-02", source="paper", title="Union Budget 2026 clears the house"),
    ]
    vectors = block({"india-01": unit(0), "world-02": unit(0)})

    assert groups_of(collapse_same_story(items, vectors, same_story=at(0.9))) == {}
    assert (
        groups_of(
            collapse_same_story(
                items, vectors, same_story=at(0.9), group_identical_titles=False
            )
        )
        != {}
    )


def test_the_floor_is_what_decides_a_group_the_cosine_nearly_made() -> None:
    """The score reaches the arithmetic, not only the log line.

    One pair scoring 0.9511 on the vectors: a floor at 0.96 leaves them apart
    and a floor at 0.95 joins them. The key-point term used to be the thing
    this test moved; with the cosine as the whole score, the floor is.
    """
    items = [
        item("world-01", source="wire"),
        item("india-02", source="paper"),
    ]
    vectors = block({"world-01": unit(0), "india-02": unit(18)})

    assert groups_of(collapse_same_story(items, vectors, same_story=SameStoryConfig(floor_min=0.96))) == {}
    assert groups_of(collapse_same_story(items, vectors, same_story=SameStoryConfig(floor_min=0.95))) != {}


def test_a_config_still_spelling_the_old_floor_is_refused_by_name() -> None:
    """0.94 of a cosine and 0.94 of a composite are not the same quantity.

    So the old knob is refused rather than aliased: a silent alias carries a
    number somebody measured against one rule forward into another, and the
    operator never finds out.
    """
    with pytest.raises(ValueError, match=re.escape("assemble.same_story.floor_min")):
        AssembleConfig.model_validate({"duplicate_similarity_min": 0.94})


# --- the oracle: a hand-labelled day ---------------------------------------


def test_the_oracle_every_group_on_the_labelled_day_is_one_story() -> None:
    """Row #9's acceptance gate, at the threshold `config/idhazh.json` ships.

    The labels are the fixed thing here and the threshold answers to them. If
    this fails with a group the labels do not carry, that group is a false merge
    and ESCALATE trigger (b) has fired - read the two items before touching the
    number.
    """
    items, embeddings = labelled_day()
    stamped = collapse_same_story(items, embeddings, same_story=at(committed_threshold()))

    assert groups_of(stamped) == LABELLED_GROUPS


def test_the_threshold_sits_above_the_labelled_false_pair() -> None:
    """The one measurement that chose the number, as an assertion.

    Ontario's pushback against the lake renaming and Google carrying it out are
    two stories, and they score 0.9317. A threshold at or below that merges
    them.
    """
    _, embeddings = labelled_day()
    left_id, right_id = LABELLED_FALSE_PAIR
    left = array("b", b64decode(embeddings.vectors[left_id]))
    right = array("b", b64decode(embeddings.vectors[right_id]))
    score = cosine_int8(
        left,
        right,
        left_norm=math.sqrt(sum(value * value for value in left)),
        right_norm=math.sqrt(sum(value * value for value in right)),
    )

    assert score == pytest.approx(0.9317, abs=5e-5), "the labelled pair moved"
    assert score < committed_threshold(), "the shipped threshold merges two different stories"


def test_the_labelled_day_keeps_every_item_it_published() -> None:
    """Nothing is unpublished, counted on the oracle day rather than argued."""
    items, embeddings = labelled_day()
    stamped = collapse_same_story(items, embeddings, same_story=at(committed_threshold()))

    assert len(stamped) == len(items)
    assert [one.item_id for one in stamped] == [one.item_id for one in items]


# --- the read side ---------------------------------------------------------


def a_day() -> dict[str, Any]:
    """A three-story day, mutable, for the rules the day-level validator holds.

    Three is what these need: one item folded onto a second folded onto a third
    is the chain that must be refused.
    """
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    )
    return payload


def test_a_committed_day_reads_an_absent_duplicate_field_as_unknown() -> None:
    """The read-side migration (CLAUDE.md section 11).

    A day written before the pass existed omits both fields, and each must come
    back as `None`. `0` for `also_covered_by` would claim no other source
    carried the story, which is a fact nobody measured.

    Driven from the fixture with both keys removed. Walking the committed tree
    cost one parse per published day, and it counted the items that still LACK
    the fields and failed at zero - so it went red on the day the last
    unmigrated day aged out of retention, which is a date on the calendar rather
    than a change anybody made.
    """
    payload = a_day()
    for item_payload in payload["items"]:
        item_payload.pop("also_covered_by", None)
        item_payload.pop("same_story_as", None)
    assert payload["items"], "the fixture holds no story, so removing the fields proved nothing"

    day = DigestDay.model_validate(payload)
    for one in day.items:
        assert one.also_covered_by is None, f"{one.item_id}: also_covered_by invented"
        assert one.same_story_as is None, f"{one.item_id}: same_story_as invented"


def test_a_day_may_not_collapse_onto_an_item_it_also_collapses() -> None:
    """One link, never a chain.

    Two stories folded onto an item that is itself folded away would leave the
    survivor drawing a count from somewhere else, and the reader with no way
    back to either.
    """
    payload = a_day()
    first, second, third = (one["item_id"] for one in payload["items"][:3])
    for one in payload["items"]:
        if one["item_id"] == first:
            one["same_story_as"], one["also_covered_by"] = second, 1
        if one["item_id"] == second:
            one["same_story_as"], one["also_covered_by"] = third, 1

    with pytest.raises(ValueError, match="which this day does not keep"):
        DigestDay.model_validate(payload)


def test_a_day_may_not_collapse_onto_an_item_it_does_not_hold() -> None:
    payload = a_day()
    payload["items"][0]["same_story_as"] = "world-9999999999"
    payload["items"][0]["also_covered_by"] = 1

    with pytest.raises(ValueError, match="which this day does not keep"):
        DigestDay.model_validate(payload)


def test_an_item_cannot_be_the_same_story_as_itself() -> None:
    payload = a_day()
    payload["items"][0]["same_story_as"] = payload["items"][0]["item_id"]
    payload["items"][0]["also_covered_by"] = 1

    with pytest.raises(ValueError, match="the same story as itself"):
        DigestDay.model_validate(payload)


def test_a_collapsed_item_carries_the_count_the_sentence_needs() -> None:
    payload = a_day()
    payload["items"][1]["same_story_as"] = payload["items"][0]["item_id"]

    with pytest.raises(ValueError, match="how many sources covered it"):
        DigestDay.model_validate(payload)
