"""How does a desk sit beside the feed's own word, and why does a story never name a third?"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts import canonical_json
from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import DigestDay, DigestItem
from idhazh.contracts.digest_view import DigestView
from idhazh.contracts.item_health import TimeSource
from idhazh.contracts.knobs.ui import UiConfig
from idhazh.contracts.run_plan import RunPlan

pytestmark = pytest.mark.contract


#
# The oracle of row #6 of TODO/20260910-23-article-classification-plan.md: an
# item whose desk differs from its vertical validates, publishes and renders
# under the desk, with its `item_id` still addressed `<vertical>-`. That
# combination is exactly what repointing `Article.vertical` makes impossible, so
# these prove the choice rather than the code - and they go red the day somebody
# repoints the field.


def _desk_differs_payload() -> dict[str, Any]:
    payload = json.loads(read_text(FIXTURES_DIR / "digest" / "desk-differs-from-vertical.json"))
    assert isinstance(payload, dict)
    return payload


def test_an_item_whose_desk_differs_from_its_vertical_still_carries_its_address() -> None:
    """The whole row in one assertion, on the fixture the row is driven from.

    `energy-9435555854` is an energy feed's story about compute. It publishes
    under the AI desk and keeps the address a reader may already have shared,
    because `item_id` is addressed from the carrying feed's word and that word
    did not move.
    """
    item = DigestItem.model_validate(_desk_differs_payload())
    assert item.vertical == "energy"
    assert item.desk == "ai"
    assert item.item_id.startswith("energy-"), "the published address is the feed's word"


def test_repointing_the_vertical_to_the_desk_is_rejected_at_read_time() -> None:
    """Rejected alternative 1, run rather than described.

    Repointing `vertical` was the earlier draft's plan. The contract's own
    identity rule refuses it on every item whose desk moved - which is why the
    desk is a second field and never a new meaning for the first.
    """
    payload = _desk_differs_payload()
    repointed = {**payload, "vertical": "ai"}
    with pytest.raises(ValueError, match="item_id must be addressed"):
        DigestItem.model_validate(repointed)

    article = json.loads(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    assert article["item_id"].startswith(f"{article['vertical']}-")
    with pytest.raises(ValueError, match="item_id must be addressed"):
        Article.model_validate({**article, "vertical": "energy"})


def test_an_item_published_before_the_desk_existed_reads_as_its_vertical() -> None:
    """The read-side migration, proved by removing the key rather than by waiting.

    Every one of the 22 committed days was written without `desk`. A test that
    counted how many of them still lack it would be timed to go red on the day
    the last one aged out; removing the key from a payload cannot age out.
    """
    payload = _desk_differs_payload()
    del payload["desk"]
    item = DigestItem.model_validate(payload)
    assert item.desk is None, "absent is unknown, never a desk of its own"


def test_a_day_must_list_the_desk_it_published_a_story_under() -> None:
    """A rendered story under a name the payload does not carry is an unnamed page.

    The desk decides the heading, the pill and the topic route, so a day that
    publishes a story under a name its own `verticals` list has never heard of
    draws a page with no display name and no count.
    """
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    listed = {ref["id"] for ref in day["verticals"]}
    unlisted = next(name for name in ("world", "india", "business-economy") if name not in listed)
    day["items"][0]["desk"] = unlisted
    with pytest.raises(ValueError, match="names an unlisted desk"):
        DigestDay.model_validate(day)


def test_the_two_counts_answer_two_questions() -> None:
    """`count` is the feed's word and `desk_count` is what the page draws.

    Decision 5: `count` keeps its meaning because 22 frozen published days
    already carry it and a published day is never rewritten. So a relabelled
    story is counted under its vertical by one number and under its desk by the
    other, and neither is allowed to disagree with the items beside it.
    """
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    moved = day["items"][0]
    other = next(ref for ref in day["verticals"] if ref["id"] != moved["vertical"])
    home = next(ref for ref in day["verticals"] if ref["id"] == moved["vertical"])
    moved["desk"] = other["id"]

    for ref in day["verticals"]:
        ref["desk_count"] = ref["count"]
    with pytest.raises(ValueError, match="desk_count disagrees"):
        DigestDay.model_validate(day)

    home["desk_count"] = home["count"] - 1
    other["desk_count"] = other["count"] + 1
    settled = DigestDay.model_validate(day)
    by_id = {ref.id: ref for ref in settled.verticals}
    assert by_id[home["id"]].count == home["count"], "the feed's word still counts the story"
    assert by_id[home["id"]].desk_count == home["count"] - 1, "the page no longer draws it here"
    assert by_id[other["id"]].desk_count == other["count"] + 1


def test_a_second_desk_that_repeats_the_first_is_refused() -> None:
    """A story names at most two desks, which is the oracle of plan 25 row #8.

    One name written twice reads as two desks to anything counting them and is
    one desk to a reader. The rule is stated against the desk the day FILED the
    story under, so it holds on an item whose `desk` is null and whose filing is
    therefore the feed's own word.
    """
    payload = _desk_differs_payload()
    assert payload["vertical"] == "energy" and payload["desk"] == "ai"

    crossed = DigestItem.model_validate({**payload, "secondary_desk": "energy"})
    assert crossed.secondary_desk == "energy", "the feed's word is a lawful second desk"

    with pytest.raises(ValueError, match="secondary_desk repeats"):
        DigestItem.model_validate({**payload, "secondary_desk": "ai"})

    unfiled = {**payload, "desk": None}
    with pytest.raises(ValueError, match="secondary_desk repeats"):
        DigestItem.model_validate({**unfiled, "secondary_desk": "energy"})


def test_an_item_published_before_the_second_desk_existed_reads_as_unknown() -> None:
    """The read-side migration, proved by removing the key rather than by waiting.

    Absent is nothing having named a second desk. It is never the story saying
    it has none, which would be a claim about 9,353 committed items nobody made.
    """
    payload = _desk_differs_payload()
    payload.pop("secondary_desk", None)
    item = DigestItem.model_validate(payload)
    assert item.secondary_desk is None


def test_a_day_must_list_the_second_desk_a_story_names() -> None:
    """A claim on a topic the day never listed is a claim nothing can honour.

    `desk` is already checked this way. The second name is owed the same check,
    because `assemble.build_day` lists every word any story holds and a payload
    that skipped one would carry a topic with no display name and no count.
    """
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    listed = {ref["id"] for ref in day["verticals"]}
    unlisted = next(name for name in ("world", "india", "business-economy") if name not in listed)
    day["items"][0]["secondary_desk"] = unlisted
    with pytest.raises(ValueError, match="names an unlisted second desk"):
        DigestDay.model_validate(day)


def test_a_day_written_before_desk_count_existed_still_reads() -> None:
    """Additive, so the 22 frozen days validate with the key absent everywhere."""
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for ref in day["verticals"]:
        ref.pop("desk_count", None)
    for item in day["items"]:
        item.pop("desk", None)
    settled = DigestDay.model_validate(day)
    assert all(ref.desk_count is None for ref in settled.verticals)
    assert all(item.desk is None for item in settled.items)


def test_the_served_day_carries_the_desk_a_page_groups_by() -> None:
    """The browser is what groups stories, so the projection may not drop the desk.

    `DigestView` is the copy a reader's browser fetches. A desk the committed
    day knows and this file drops is a grouping the page cannot make.
    """
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    moved = day["items"][0]
    other = next(ref for ref in day["verticals"] if ref["id"] != moved["vertical"])
    moved["desk"] = other["id"]
    view = DigestView.project(day)
    assert view.items[0].desk == other["id"]
    assert view.items[0].vertical == moved["vertical"]


def test_the_thin_desk_floor_is_a_knob_the_frontend_agrees_with() -> None:
    """The two-copies problem again, on the knob that decides whether a desk speaks.

    The rule runs in the browser off the frontend's own default, so a fresh
    clone with no `config/` resolves it there. Let the two drift and the page
    explains a desk the contract would call healthy, or stays silent on one it
    would call thin - and nothing else would catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"desk_thin_max:\s*(\d+),", reader)
    assert mirrored is not None, "the frontend dropped its desk_thin_max default"
    assert int(mirrored.group(1)) == UiConfig().desk_thin_max


def test_a_published_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "feed"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        DigestDay.model_validate(payload)


def test_a_published_item_with_no_time_may_only_say_unknown() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "unknown"

    day = DigestDay.model_validate(payload)

    assert day.items[0].time_source is TimeSource.UNKNOWN
    assert day.items[0].published_at is None


def test_a_planned_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "first_seen"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        RunPlan.model_validate(payload)


def test_the_ranking_signal_survives_a_round_trip_with_values_in_it() -> None:
    """The fixture carries nulls, so the populated shape needs its own oracle."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0].update(
        carried_by=3, watchlist_hit=True, on_front_page=True, rank_score=3.4, time_source="feed"
    )

    once = DigestDay.model_validate(payload).to_json()
    twice = DigestDay.from_json(once)

    assert twice.to_json() == once
    assert twice.items[0].carried_by == 3
    assert twice.items[0].rank_score == 3.4
    assert twice.items[0].time_source is TimeSource.FEED


def test_a_story_no_feed_carried_cannot_be_published() -> None:
    """`carried_by` counts the feeds that carried one address, so its floor is 1.

    Null is how a run that did not record the count says so. Zero would be a
    story that arrived from nowhere.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["carried_by"] = 0
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        DigestDay.model_validate(payload)


def test_canonical_json_is_sorted_and_newline_terminated() -> None:
    text = canonical_json({"b": 1, "a": 2})
    assert text == '{\n  "a": 2,\n  "b": 1\n}\n'
