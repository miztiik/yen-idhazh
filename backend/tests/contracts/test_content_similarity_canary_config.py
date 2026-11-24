"""Does the file of known-answer pairs refuse every shape that would make the check meaningless?

The committed file is read as the judge reads it. Each refusal then changes one thing in an
in-memory copy of it, so a case goes red only for the rule it names, and one positive control
(a well-formed hand-written pair) shows the refusals are not refusing everything.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from support.paths import CONFIG_DIR, read_text

from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.knobs.content_similarity_canaries import (
    ANSWER_OF_KIND,
    MAX_CANARY_PAIRS,
    CanaryKind,
    ContentSimilarityCanaryConfig,
)

pytestmark = pytest.mark.contract

COMMITTED_FILE = CONFIG_DIR / "judges" / "content-similarity-canaries.json"


def committed() -> dict[str, Any]:
    """The committed file as raw JSON, for a case to change one thing in."""
    raw: dict[str, Any] = json.loads(read_text(COMMITTED_FILE))
    return raw


def a_hand_written_pair(identifier: str = "synthetic-same-1", **changes: Any) -> dict[str, Any]:
    """A pair that follows every rule, written by hand and so naming no published item."""
    pair: dict[str, Any] = {
        "id": identifier,
        "kind": "same",
        "expected": "YES",
        "origin": "synthetic",
        "labelled_by": "agent",
        "basis": "Two plain restatements of one invented event",
        "left": {"summary": "A footbridge over the river opened on Monday."},
        "right": {"summary": "On Monday the new river footbridge was opened."},
    }
    return pair | changes


def refusal_of(raw: dict[str, Any]) -> str:
    with pytest.raises(ValueError) as refused:
        ContentSimilarityCanaryConfig.model_validate(raw)
    return str(refused.value)


def test_the_committed_file_is_ascii_and_holds_one_pair_of_every_kind_at_least() -> None:
    raw_bytes = COMMITTED_FILE.read_bytes()
    pairs = judge_settings.load_canaries(CONFIG_DIR).pairs

    assert raw_bytes.isascii(), "the repository's files are ASCII, and this one holds summaries"
    assert b"\r" not in raw_bytes
    assert {pair.kind for pair in pairs} == set(CanaryKind)
    assert len(pairs) <= MAX_CANARY_PAIRS
    assert all(pair.expected is ANSWER_OF_KIND[pair.kind] for pair in pairs)


def test_a_well_formed_hand_written_pair_is_accepted() -> None:
    """The positive control: what the refusals below are not refusing."""
    raw = committed()
    raw["pairs"].append(a_hand_written_pair())

    loaded = ContentSimilarityCanaryConfig.model_validate(raw)

    assert loaded.pairs[-1].origin == "synthetic"
    assert loaded.pairs[-1].left.item_id is None


def drop_all_unclear_pairs(raw: dict[str, Any]) -> None:
    raw["pairs"] = [pair for pair in raw["pairs"] if pair["kind"] != "unclear"]


def repeat_an_id(raw: dict[str, Any]) -> None:
    raw["pairs"][1]["id"] = raw["pairs"][0]["id"]


def mislabel_a_same_pair(raw: dict[str, Any]) -> None:
    raw["pairs"][0]["expected"] = "NO"


def add_too_many_pairs(raw: dict[str, Any]) -> None:
    extra = [
        a_hand_written_pair(f"synthetic-same-{number}") for number in range(MAX_CANARY_PAIRS)
    ]
    raw["pairs"] = [*raw["pairs"], *extra]


def give_a_hand_written_pair_a_plain_id(raw: dict[str, Any]) -> None:
    raw["pairs"].append(a_hand_written_pair("same-3"))


def record_published_sources(raw: dict[str, Any]) -> None:
    pair = raw["pairs"][0]
    pair["origin"] = "published"
    pair["left"].update(date="2026-11-07", item_id="india-4at2refk8ng9fhy3")
    pair["right"].update(date="2026-11-07", item_id="india-689nbq3f7gm8ja9d")


def give_a_published_pair_the_hand_written_prefix(raw: dict[str, Any]) -> None:
    record_published_sources(raw)
    raw["pairs"][0]["id"] = "synthetic-same-1"


def forget_where_a_published_pair_came_from(raw: dict[str, Any]) -> None:
    record_published_sources(raw)
    raw["pairs"][0]["left"].pop("item_id")
    raw["pairs"][0]["left"].pop("date")


def name_an_item_for_a_hand_written_pair(raw: dict[str, Any]) -> None:
    raw["pairs"].append(
        a_hand_written_pair(
            left={
                "summary": "A footbridge over the river opened on Monday.",
                "date": "2026-11-07",
                "item_id": "india-4at2refk8ng9fhy3",
            }
        )
    )


def name_a_day_without_an_item(raw: dict[str, Any]) -> None:
    record_published_sources(raw)
    raw["pairs"][0]["left"].pop("item_id")


def name_a_day_that_does_not_exist(raw: dict[str, Any]) -> None:
    record_published_sources(raw)
    raw["pairs"][0]["left"]["date"] = "2026-02-30"


@pytest.mark.parametrize(
    ("change", "refused"),
    [
        pytest.param(drop_all_unclear_pairs, "no pair of kind ['unclear']", id="a missing kind"),
        pytest.param(repeat_an_id, "ids repeat", id="duplicate ids"),
        pytest.param(mislabel_a_same_pair, "which is answered YES", id="a mislabelled kind"),
        pytest.param(
            add_too_many_pairs, f"at most {MAX_CANARY_PAIRS} items", id="over the cap"
        ),
        pytest.param(
            give_a_hand_written_pair_a_plain_id, "starts with synthetic-", id="no synthetic prefix"
        ),
        pytest.param(
            give_a_published_pair_the_hand_written_prefix,
            "starts with synthetic-",
            id="a published pair with the prefix",
        ),
        pytest.param(
            forget_where_a_published_pair_came_from,
            "names the item it came from",
            id="published with no source",
        ),
        pytest.param(
            name_an_item_for_a_hand_written_pair, "hand-written", id="synthetic naming an item"
        ),
        pytest.param(name_a_day_without_an_item, "both the day and the item", id="a day alone"),
        pytest.param(name_a_day_that_does_not_exist, "not a calendar day", id="a day that is not"),
    ],
)
def test_a_set_that_would_make_the_check_meaningless_is_refused(
    change: Callable[[dict[str, Any]], None], refused: str
) -> None:
    raw = committed()
    change(raw)

    assert refused in refusal_of(raw)


@pytest.mark.parametrize(
    ("summary", "refused"),
    [
        ("", "at least 1 character"),
        ("A caf\u00e9 opened on Monday.", "is ASCII"),
        ("A footbridge  opened on Monday.", "not shaped like a published one"),
        ("A footbridge opened on Monday.\n", "not shaped like a published one"),
        ("A footbridge opened\ton Monday.", "not shaped like a published one"),
    ],
    ids=["empty", "non-ascii", "a run of spaces", "a trailing newline", "a control character"],
)
def test_a_summary_that_is_empty_or_not_ascii_or_not_shaped_like_a_published_one_is_refused(
    summary: str, refused: str
) -> None:
    raw = committed()
    raw["pairs"][0]["right"]["summary"] = summary

    assert refused in refusal_of(raw)


def test_a_file_with_no_version_or_an_unknown_key_is_refused() -> None:
    no_version = committed()
    del no_version["version"]
    unknown = committed()
    unknown["pairs"][0]["url"] = "https://example.invalid/"
    unknown_kind = committed()
    unknown_kind["pairs"][0]["kind"] = "similar"

    assert "version" in refusal_of(no_version)
    assert "url" in refusal_of(unknown)
    assert "kind" in refusal_of(unknown_kind)


def test_a_basis_is_one_line_of_ascii() -> None:
    raw = committed()
    raw["pairs"][0]["basis"] = "Two lines\nof reasons"

    assert "basis" in refusal_of(raw)


@pytest.mark.parametrize(
    "version",
    [20261118, "2026-02-30", "9999-12-31"],
    ids=["an integer", "a day that does not exist", "a day to come"],
)
def test_a_version_that_is_not_a_past_date_is_refused_by_the_reader(
    tmp_path: Path, version: object
) -> None:
    raw = committed()
    raw["version"] = version
    target = tmp_path / "judges" / "content-similarity-canaries.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(raw), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match=re.escape("content-similarity-canaries.json is refused")):
        judge_settings.load_canaries(tmp_path)


def test_a_version_of_today_is_read_and_a_file_that_breaks_a_rule_names_itself(
    tmp_path: Path,
) -> None:
    today = datetime.now(UTC).date().isoformat()
    raw = copy.deepcopy(committed()) | {"version": today}
    target = tmp_path / "judges" / "content-similarity-canaries.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    assert judge_settings.load_canaries(tmp_path).version == today

    repeat_an_id(raw)
    target.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match=re.escape("config/judges/content-similarity-canaries.json")):
        judge_settings.load_canaries(tmp_path)
