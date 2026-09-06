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
from array import array
from base64 import b64decode
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh import config
from idhazh.assemble import collapse_same_story, cosine_int8
from idhazh.contracts.digest_day import DigestDay, DigestEmbeddings, DigestItem
from idhazh.contracts.eval_row import ConfidenceBand
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
    repository for no reader (`CLAUDE.md` section 0a) and would not change one
    grouping.
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
    return config.load(CONFIG_DIR).app.assemble.duplicate_similarity_min


def groups_of(items: list[DigestItem]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for item in items:
        if item.same_story_as is not None:
            found.setdefault(item.same_story_as, []).append(item.item_id)
    return found


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


def item(item_id: str, *, source: str, score: float | None = 1.0, run: int = 1) -> DigestItem:
    return DigestItem(
        item_id=item_id,
        vertical=item_id.rsplit("-", 1)[0],
        title=f"Story {item_id}",
        source_url=f"https://example.test/{item_id}",
        source_id=source,
        source_name=source.title(),
        summary="A summary long enough to be a summary.",
        key_points=["One point."],
        band=ConfidenceBand.HIGH,
        rank_score=score,
        introduced_by_run=run,
    )


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
        items, block({"world-01": unit(0), "world-02": unit(0)}), similarity_min=0.9
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
        items, block({one.item_id: unit(0) for one in items}), similarity_min=0.9
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
        items, block({"world-01": unit(0), "world-02": unit(0)}), similarity_min=0.9
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
    stamped = collapse_same_story(items, block(vectors), similarity_min=0.93)

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
        similarity_min=0.9,
    )

    assert groups_of(stamped) == {"world-01": ["world-02", "world-03"]}
    assert [one.also_covered_by for one in stamped] == [1, 1, 1]


# --- what the pass refuses to guess ----------------------------------------


def test_a_day_with_no_vectors_says_it_does_not_know() -> None:
    """Null, never 0. A day whose encoder never ran carried no claim either way."""
    items = [item("world-01", source="wire"), item("world-02", source="paper")]
    stamped = collapse_same_story(items, None, similarity_min=0.9)

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
        items, block({"world-01": unit(0), "world-02": unit(0)}), similarity_min=0.9
    )

    assert [one.also_covered_by for one in stamped] == [1, 1, None]
    assert stamped[2].same_story_as is None


def test_a_vector_of_the_wrong_width_is_not_grouped() -> None:
    """A short vector would score against a prefix of its rival and mean nothing."""
    items = [item("world-01", source="wire", score=9.0), item("world-02", source="paper")]
    vectors = {"world-01": unit(0), "world-02": to_base64([1.0] + [0.0] * (DIMENSIONS - 1))[:8]}
    stamped = collapse_same_story(items, block(vectors), similarity_min=0.9)

    assert [one.also_covered_by for one in stamped] == [0, None]


# --- the oracle: a hand-labelled day ---------------------------------------


def test_the_oracle_every_group_on_the_labelled_day_is_one_story() -> None:
    """Row #9's acceptance gate, at the threshold `config/idhazh.json` ships.

    The labels are the fixed thing here and the threshold answers to them. If
    this fails with a group the labels do not carry, that group is a false merge
    and ESCALATE trigger (b) has fired - read the two items before touching the
    number.
    """
    items, embeddings = labelled_day()
    stamped = collapse_same_story(items, embeddings, similarity_min=committed_threshold())

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
    stamped = collapse_same_story(items, embeddings, similarity_min=committed_threshold())

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
