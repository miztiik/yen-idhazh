"""Does the pair verdict row hold the draw and the filed row in one shape, and refuse what no draw makes?

Four questions. The draw and the filed row are one shape and differ only in which cells are
filled; a pair the slice, the counts or the thresholds cannot account for is refused; the
judge's columns move together; and the two compact JSON text columns refuse text that is not
compact JSON. What none of this settles is whether the draw files the right pairs: nothing
writes this row yet, and the writer's own checks prove that.

Every payload here is the committed fixture with a few cells changed, built in memory.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.story_similarity_pair_verdict import PairBucket, StorySimilarityPairVerdict

pytestmark = pytest.mark.contract

FIXTURE = (
    CONTRACT_FIXTURES_DIR
    / "story-similarity-pair-verdict"
    / "a-judged-pair-with-its-slice-and-chance.json"
)

#: What a draw leaves empty: every judge column, and the two cells the collecting job fills.
THE_DRAW: dict[str, Any] = {
    "slice_pairs_usable": None,
    "sampling_chance": None,
    "verdict": None,
    "verdict_swapped": None,
    "readings_agree": False,
    "first_token_margin": None,
    "judge_model": None,
    "prompt_digest": None,
    "grammar_digest": None,
    "decode_seconds": None,
    "judge_temperature": None,
    "grammar_applied": None,
    "first_token_probabilities": None,
    "thinking_spans": None,
    "judge_policy_version": None,
}


def a_verdict(**changes: Any) -> dict[str, Any]:
    """The committed judged pair as a payload, with some cells changed."""
    payload: dict[str, Any] = json.loads(read_text(FIXTURE))
    return payload | changes


def refused(**changes: Any) -> str:
    """The refusal a payload with these cells changed draws, as one string."""
    with pytest.raises(ValidationError) as refusal:
        StorySimilarityPairVerdict.model_validate(a_verdict(**changes))
    return str(refusal.value)


def test_the_draw_and_the_filed_row_are_one_shape_in_the_scratch_csv() -> None:
    """The draw is the filed row with the judge's cells and the collected cells left empty."""
    filed = StorySimilarityPairVerdict.model_validate(a_verdict())
    draw = StorySimilarityPairVerdict.model_validate(a_verdict(**THE_DRAW))

    for row in (filed, draw):
        cells = row.csv_row()
        assert tuple(cells) == StorySimilarityPairVerdict.csv_columns()
        assert StorySimilarityPairVerdict.from_csv_row(cells) == row
    assert {name for name, cell in draw.csv_row().items() if cell == ""} == (
        set(THE_DRAW) - {"readings_agree"}
    )
    assert filed.csv_row()["config_versions"] == filed.config_versions


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"slice_low": 0.74, "slice_high": 0.73}, "runs from its lower edge up"),
        ({"slice_low": 0.74, "slice_high": 0.8}, "outside the slice"),
        ({"slice_low": float("nan")}, "finite number"),
        (
            {"lower_threshold_in_force": 0.93, "upper_threshold_in_force": 0.7},
            "is not below the upper threshold",
        ),
        (
            {"bucket": PairBucket.FULLY_DISSIMILAR, "slice_low": -1.0, "slice_high": 0.74},
            "fully dissimilar pair sits below",
        ),
        (
            {"bucket": PairBucket.FULLY_SIMILAR, "slice_low": 0.73, "slice_high": 1.0},
            "fully similar pair sits above",
        ),
        ({"sampling_chance": 1.2}, "less than or equal to 1"),
        ({"sampling_chance": 0.5}, "sampling_chance is 0.5"),
        ({"sampling_chance": None}, "filled together"),
        ({"slice_pairs_usable": 7, "sampling_chance": 7 / 31}, "usable of the 6"),
        ({"slice_pairs_judged": 32}, "took 32 pairs"),
    ],
)
def test_a_pair_the_slice_cannot_account_for_is_refused(
    changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**changes)


def test_a_slice_with_no_usable_pair_has_chance_zero_and_no_agreeing_row() -> None:
    """Chance zero is a measured fact about a slice, and no weight is ever taken from it."""
    disagreeing = a_verdict(
        verdict="YES",
        verdict_swapped="NO",
        readings_agree=False,
        slice_pairs_usable=0,
        sampling_chance=0.0,
    )

    assert StorySimilarityPairVerdict.model_validate(disagreeing).sampling_chance == 0.0
    assert "has at least one usable pair" in refused(slice_pairs_usable=0, sampling_chance=0.0)


@pytest.mark.parametrize(
    ("edge", "bucket", "slice_low", "slice_high", "bound"),
    [
        (1.0000000000000002, PairBucket.FULLY_SIMILAR, 0.99, 1.0, "less than or equal to 1"),
        (-1.0000000000000002, PairBucket.FULLY_DISSIMILAR, -1.0, 0.7, "greater than or equal to -1"),
    ],
)
def test_a_cosine_one_bit_past_the_range_is_folded_back_and_a_real_excess_is_refused(
    edge: float, bucket: PairBucket, slice_low: float, slice_high: float, bound: str
) -> None:
    """Two identical vectors can divide to one bit past 1.0, and that must not lose a night."""
    placed = {"bucket": bucket, "slice_low": slice_low, "slice_high": slice_high}
    row = StorySimilarityPairVerdict.model_validate(
        a_verdict(**placed, cosine=edge, similarity_score=edge)
    )

    assert (row.cosine, row.similarity_score) == (round(edge), round(edge))
    cells = row.csv_row() | {"cosine": repr(edge), "similarity_score": repr(edge)}
    assert StorySimilarityPairVerdict.from_csv_row(cells) == row
    assert bound in refused(**placed, cosine=edge * 1.001, similarity_score=edge * 1.001)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"grammar_digest": None}, "one fact in four columns"),
        ({"judge_policy_version": None}, "one fact in four columns"),
        ({"grammar_applied": False}, "held the grammar exactly when both"),
        ({"grammar_applied": None}, "held the grammar exactly when both"),
        ({"readings_agree": False}, "readings_agree must equal agreement"),
        ({"verdict_swapped": "YES"}, "readings_agree must equal agreement"),
        (THE_DRAW | {"verdict": "NO"}, "carries no verdict, no agreement and no grammar flag"),
        (THE_DRAW | {"grammar_applied": False}, "carries no verdict, no agreement"),
    ],
)
def test_the_judge_columns_move_together_and_an_unjudged_pair_carries_none(
    changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**changes)


def test_a_pair_whose_reading_was_refused_is_still_a_row() -> None:
    """The refusal is the fact being recorded, so a pair nothing could read is filed, not dropped."""
    row = StorySimilarityPairVerdict.model_validate(
        a_verdict(
            verdict=None,
            verdict_swapped=None,
            readings_agree=False,
            grammar_applied=False,
            first_token_margin=None,
        )
    )

    assert row.verdict is None and row.judge_model is not None and not row.readings_agree


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"pair_key": "0" * 64}, "pair_key is"),
        ({"similarity_score": 0.74}, "similarity_score is 0.74"),
        ({"headline": True}, "a headline match scores 1.0"),
    ],
)
def test_a_pair_cannot_claim_a_key_or_a_score_its_own_cells_do_not_give(
    changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**changes)


def test_two_address_keys_are_stored_in_sorted_order() -> None:
    payload = a_verdict()
    swapped = {"left_url_key": payload["right_url_key"], "right_url_key": payload["left_url_key"]}

    assert "sorted order" in refused(**swapped)


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '["judges/content-similarity-judge.json"]',
        "{}",
        '{"judges/content-similarity-judge.json": "2026-11-18"}',
        '{"b.json":"2026-11-18","a.json":"2026-11-18"}',
        '{"judges/content-similarity-judge.json":"20261118"}',
        '{"C:\\\\config\\\\judge.json":"2026-11-18"}',
        '{"judges/content-similarity-judge.json":"2026-11-18"}\n',
    ],
)
def test_config_versions_is_one_compact_json_object_of_config_paths_and_dates(text: str) -> None:
    assert "config_versions" in refused(config_versions=text)


def test_a_second_config_file_changes_no_column() -> None:
    both = (
        '{"judges/content-similarity-canaries.json":"2026-11-20",'
        '"judges/content-similarity-judge.json":"2026-11-18"}'
    )

    row = StorySimilarityPairVerdict.model_validate(a_verdict(config_versions=both))

    assert row.config_versions == both
