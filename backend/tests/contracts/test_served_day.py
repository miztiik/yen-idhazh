"""Is the served day a narrowing of the published one, and what can it never carry?"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts.base import paragraphs_of
from idhazh.contracts.digest_day import DigestItem, DigestVisual
from idhazh.contracts.digest_view import (
    COVERAGE_NAMES_MAX,
    DigestView,
    DigestViewItem,
    DigestViewVisual,
)

from ._fixtures import (
    RANKING_SIGNAL,
    a_day_missing,
)

pytestmark = pytest.mark.contract


#: The projector that writes the served file. It runs in node at build time, so
#: the shape lives here and the behaviour lives there - and these tests are what
#: stop the two halves of one payload drifting across two languages.
PROJECT_TS = REPO_ROOT / "frontend" / "src" / "lib" / "payload" / "project.ts"


def projector_array(name: str) -> list[str]:
    match = re.search(
        rf"export const {name}: readonly string\[\] = \[(.*?)\];", read_text(PROJECT_TS), re.DOTALL
    )
    assert match, f"{name} is no longer a string array in project.ts"
    return re.findall(r"'([a-z_]+)'", match.group(1))


def projector_version() -> str:
    match = re.search(r"export const VIEW_VERSION = '([^']+)';", read_text(PROJECT_TS))
    assert match, "VIEW_VERSION is no longer a string literal in project.ts"
    return match.group(1)


def projector_number(name: str) -> int:
    match = re.search(rf"export const {name} = (\d+);", read_text(PROJECT_TS))
    assert match, f"{name} is no longer a number literal in project.ts"
    return int(match.group(1))


def a_group(
    *members: tuple[str, str, float | None],
    anchor: str | None = None,
) -> list[dict[str, Any]]:
    """A day of stories, some of them one story, built rather than looked for.

    The committed archive holds groups, and every one of them is an accident of
    what the sources ran that morning: none of them is four outlets on one story
    with one outlet running it twice, which is the case the rules below are for.
    Built here, the awkward shape is the point (`CLAUDE.md` section 13).

    Each member is `(item_id, source_name, rank_score)`. The first is the anchor
    unless `anchor` names another, and every other member points at it.
    """
    keeper = anchor if anchor is not None else members[0][0]
    return [
        {
            "item_id": item_id,
            "vertical": item_id.split("-")[0],
            "title": f"Story {item_id}",
            "summary": f"A summary of {item_id}.",
            "band": "high",
            "truncated": False,
            "source_name": source_name,
            "source_id": source_name.lower(),
            "source_kind": "reporting",
            "source_url": f"https://{source_name.lower()}.test/{item_id}",
            "rank_score": rank,
            "introduced_by_run": 1,
            "lenses": [],
            "key_points": [f"{item_id} happened."],
            "same_story_as": None if item_id == keeper else keeper,
            "also_covered_by": None,
        }
        for item_id, source_name, rank in members
    ]


def stacks(items: list[dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    """Every story's publisher stack, as `(outlet, item id)` pairs."""
    view = DigestView.project({"items": items})
    return {
        item.item_id: [(one.source_name, one.item_id) for one in item.covered_by]
        for item in view.items
    }


def without_description(shape: dict[str, Any]) -> dict[str, Any]:
    """The same field, minus the prose.

    The served item says what an absent value means to a reader; the published
    item says what the run recorded. Different sentences, same field.
    """
    return {key: value for key, value in shape.items() if key != "description"}


def test_the_projector_writes_exactly_the_shape_the_contract_names() -> None:
    """Guardrail #3, across a language boundary.

    The file a browser fetches is written by node and described by a Pydantic
    model. Nothing else connects them, so a name added on one side and not the
    other ships a payload that does not match its own schema.
    """
    assert projector_version() == DigestView.schema_version()
    assert set(projector_array("ITEM_FIELDS")) == set(DigestViewItem.model_fields)
    assert set(projector_array("VISUAL_FIELDS")) == set(DigestViewVisual.model_fields)
    assert set(projector_array("DAY_FIELDS")) | {"version"} == set(DigestView.model_fields)
    # The one number on the served item rather than a name on it. A cap the two
    # languages disagreed about would write a payload longer than its own schema
    # allows, which the contract refuses at read time on the reader's device.
    assert projector_number("COVERAGE_NAMES_MAX") == COVERAGE_NAMES_MAX


def test_a_folded_story_is_named_by_the_card_that_folds_it() -> None:
    """The fold's whole recovery path: the anchor says who else ran the story.

    One entry per OTHER OUTLET, strongest first, and every entry carries that
    outlet's own item id - which is the address the page links to, so a reader who
    wanted that newsroom's telling reaches it in one click.
    """
    day = a_group(("ai-01", "Alpha", 0.9), ("ai-02", "Beta", 0.7), ("ai-03", "Gamma", 0.8))
    found = stacks(day)

    assert found["ai-01"] == [("Gamma", "ai-03"), ("Beta", "ai-02")]
    # And it is true from every member's point of view, because a card is drawn
    # for a member whenever the fold is off or the reader's own address named it.
    assert found["ai-02"] == [("Alpha", "ai-01"), ("Gamma", "ai-03")]
    assert found["ai-03"] == [("Alpha", "ai-01"), ("Beta", "ai-02")]


def test_a_story_no_group_holds_is_named_by_nobody() -> None:
    day = [
        *a_group(("ai-01", "Alpha", 0.9), ("ai-02", "Beta", 0.7)),
        *a_group(("world-01", "Alpha", 0.5)),
    ]
    assert stacks(day)["world-01"] == []


def test_a_story_naming_an_anchor_this_day_does_not_hold_is_named_by_nobody() -> None:
    """The page cannot draw a card that is not here, so neither may the stack.

    It is reachable: a run appends, so a day can carry a story whose anchor was
    published under a retention window that has since dropped it.
    """
    day = a_group(("ai-02", "Beta", 0.7), ("ai-03", "Gamma", 0.8), anchor="ai-99")
    assert stacks(day) == {"ai-02": [], "ai-03": []}


def test_one_outlet_running_a_story_twice_is_named_once() -> None:
    """The names and the count have to agree, or the card contradicts itself.

    `also_covered_by` counts mastheads. A stack naming pieces would print three
    newsrooms under a sentence saying two, and the strongest of an outlet's two
    pieces is the one a reader should be sent to.
    """
    day = a_group(
        ("ai-01", "Alpha", 0.9),
        ("ai-02", "Beta", 0.4),
        ("ai-03", "Beta", 0.8),
    )
    assert stacks(day)["ai-01"] == [("Beta", "ai-03")]


def test_the_stack_stops_at_the_cap_and_the_count_carries_the_rest() -> None:
    day = a_group(
        ("ai-01", "Alpha", 0.9),
        ("ai-02", "Beta", 0.8),
        ("ai-03", "Gamma", 0.7),
        ("ai-04", "Delta", 0.6),
        ("ai-05", "Epsilon", 0.5),
    )
    named = stacks(day)["ai-01"]
    assert len(named) == COVERAGE_NAMES_MAX
    assert named == [("Beta", "ai-02"), ("Gamma", "ai-03"), ("Delta", "ai-04")]


def test_an_unscored_story_is_named_last_rather_than_named_first() -> None:
    """Null is unknown, never 0, and never the top of the stack either."""
    day = a_group(("ai-01", "Alpha", 0.9), ("ai-02", "Beta", None), ("ai-03", "Gamma", 0.1))
    assert stacks(day)["ai-01"] == [("Gamma", "ai-03"), ("Beta", "ai-02")]


def test_two_stories_tying_on_score_are_ordered_by_address() -> None:
    """A total order, so the projector in the other language sorts the same day
    the same way - and two builds of one day agree."""
    day = a_group(("ai-01", "Alpha", 0.5), ("ai-03", "Gamma", 0.5), ("ai-02", "Beta", 0.5))
    assert stacks(day)["ai-01"] == [("Beta", "ai-02"), ("Gamma", "ai-03")]


def test_the_block_this_projection_exists_to_drop_can_never_be_served() -> None:
    forbidden = set(projector_array("FORBIDDEN_FIELDS"))
    assert "embeddings" in forbidden, "the vector block is why this projection exists"
    kept = set(DigestViewItem.model_fields) | set(DigestView.model_fields)
    assert forbidden.isdisjoint(kept), f"served and forbidden at once: {sorted(forbidden & kept)}"


def test_a_served_day_written_before_the_day_facts_still_reads() -> None:
    """The widening of 2026-09-09 is additive, and this is what says so.

    A service worker keeps day payloads, so a shell built today can be handed a
    file written under `2026-09-01T09:00` - which carries the items and nothing
    else. It has to validate, and every name added since has to read as unknown
    rather than as a value. A default here would be a false claim about a day:
    `false` for `partial` says the run lost nothing, `0` for `items_failed` says
    the same, and an empty `verticals` says the day had no desk.

    Built here rather than read off a committed day, because the archive is
    re-staged on every build and carries no payload at the older stamp any more
    (`CLAUDE.md` section 13).
    """
    day = DigestView.project(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    )
    older = {"version": "2026-09-01T09:00", "items": json.loads(day.to_json())["items"]}

    read = DigestView.model_validate(older)

    assert read.version == "2026-09-01T09:00"
    assert read.items, "an older payload still carries its stories"
    unknown = {name for name in DigestView.model_fields if name not in {"version", "items"}}
    assert unknown, "the day facts are what this test is about"
    for name in sorted(unknown):
        assert getattr(read, name) is None, f"{name} must read as unknown on an older payload"


def test_the_served_item_is_a_narrowing_of_the_published_one() -> None:
    """A field means one thing, whichever file it is in.

    The served day is a projection, not a second vocabulary. Every name on it is
    a name the published item already has, with the same type and the same
    bounds - so a page reading the fetched file and a page reading the committed
    one cannot disagree about what they read.

    **`covered_by` is the one name the projector derives rather than copies**, and
    it is named here rather than excused in a comment: it is the day's grouping
    read back as publisher names, so there is nothing on the committed item for it
    to narrow. Every other name still has to be a copy, which is what keeps the
    exception one name wide instead of a door.
    """
    published = DigestItem.model_json_schema()["properties"]
    served = DigestViewItem.model_json_schema()["properties"]
    derived = {"covered_by"}

    assert derived < set(served), "the derived name is no longer on the served item"
    assert not (derived & set(published)), (
        "covered_by is on the committed item now, so the projector should copy it"
    )
    assert set(served) - derived < set(published), (
        "the served item names a field the published one does not"
    )
    for name, shape in served.items():
        if name == "visual" or name in derived:
            continue
        assert without_description(shape) == without_description(published[name]), name

    # The visual is the one field that is itself narrowed: `kind` is read at
    # build time for the console's chart count and no browser needs it.
    assert set(DigestViewVisual.model_fields) < set(DigestVisual.model_fields)


def test_every_committed_day_serves_a_view_that_validates() -> None:
    """The same migration on the projection a reader's browser fetches.

    A day must project to a payload the served contract accepts, and a field the
    file does not carry must come back unknown rather than as a number the run
    never recorded.
    """
    text, stripped = a_day_missing(RANKING_SIGNAL)
    assert stripped, "the fixture carries no story, so removing the fields proved nothing"

    view = DigestView.project(json.loads(text))
    assert len(view.items) == stripped
    for item in view.items:
        for name in RANKING_SIGNAL:
            assert getattr(item, name) is None, f"{item.item_id}: {name} invented"


def test_a_served_day_refuses_a_field_it_does_not_know() -> None:
    """The build is strict where the shell is tolerant, and that pairing is the design.

    A reader's browser must render a payload from a newer build, so its read is
    `JSON.parse` and nothing else. The build has no such excuse: a key nobody
    declared is a projection that widened without a decision, and it fails here
    rather than shipping.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"][0]["a_field_from_a_later_build"] = "a value no shell has ever seen"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DigestView.model_validate(payload)


def test_a_served_day_keeps_the_order_a_reader_already_read() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"].insert(0, payload["items"].pop())
    payload["items"][0]["introduced_by_run"] = 2
    with pytest.raises(ValueError, match="never reorders"):
        DigestView.model_validate(payload)


def test_a_served_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "feed"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        DigestView.model_validate(payload)


def test_a_served_day_written_before_the_version_existed_still_reads() -> None:
    """Section 11's release blocker, at the boundary that cannot be upgraded.

    A shell fetching a file this build did not write is the case the version is
    here for. The payload still loads and the stamp says which shape it is.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    del payload["version"]

    assert DigestView.model_validate(payload).version == DigestView.schema_version()


def test_a_summary_written_before_paragraphs_existed_reads_as_one_paragraph() -> None:
    """The read-side migration for 2026-09-17, and why it folds instead of refusing.

    Measured 2026-09-17 over the 9,989 summaries in `frontend/public/digest`:
    none holds a control character, but three end on a space and six carry a
    lone newline. A version of this rule that REFUSED them would make today's
    build unable to read days yesterday's build wrote, which section 11 calls a
    release blocker - so `Prose` folds.

    The shapes are built rather than read off the archive, because a committed
    day is re-staged on every build and a test that waits for one of those nine
    to come round is a test with a date on it (`CLAUDE.md` section 13).
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"][0]["summary"] = "A first claim.\nA second claim. "

    item = DigestView.model_validate(payload).items[0]

    assert item.summary == "A first claim. A second claim."
    assert paragraphs_of(item.summary) == ["A first claim. A second claim."]


def test_a_served_summary_carries_a_paragraph_break_through_unchanged() -> None:
    """The other half: a break a run wrote is the one thing the fold keeps."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"][0]["summary"] = "A first claim.\n\nA second claim."

    item = DigestView.model_validate(payload).items[0]

    assert paragraphs_of(item.summary) == ["A first claim.", "A second claim."]
