"""Is the served day a narrowing of the published one, and what can it never carry?"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts.digest_day import DigestItem, DigestVisual
from idhazh.contracts.digest_view import DigestView, DigestViewItem, DigestViewVisual

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
    """
    published = DigestItem.model_json_schema()["properties"]
    served = DigestViewItem.model_json_schema()["properties"]

    assert set(served) < set(published), "the served item names a field the published one does not"
    for name, shape in served.items():
        if name == "visual":
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
