"""Do the four story-similarity shapes refuse the rows that would misreport the line?

Every rule here is one a writer could break without the run failing: a pair filed
under another pair's identity, a score that is not the arithmetic the row
carries, a verdict with no judge behind it, a record whose slots do not line up
with its own band, a held row that also claims a clamp. None of them is a shape
pydantic would catch on its own, and each would leave a number on a committed row
that a later fit reads as evidence.

Everything is driven from a value built here or from one small committed fixture
read inside the test that needs it. Nothing walks the archive (`CLAUDE.md`
section 13).
"""

from __future__ import annotations

import json
from typing import Any, get_args

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.base import derive_text_digest, derive_url_key
from idhazh.contracts.fitted_similarity_threshold import (
    ClampKind,
    FittedSimilarityThreshold,
    HeldReason,
)
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import (
    JudgeModelId,
    SameStoryVerdict,
    ScorerModelId,
    StorySimilarityPair,
)
from idhazh.embed import EMBEDDER_ID

pytestmark = pytest.mark.contract

DATE = "2026-09-18"
RUN = "2026-09-18-1"
LEFT = "https://example.com/one"
RIGHT = "https://example.org/two"


def keys_of(left: str, right: str) -> tuple[str, str, str]:
    """The two address keys in stored order, and the identity they digest to."""
    low, high = sorted((derive_url_key(left), derive_url_key(right)))
    return low, high, derive_text_digest(low + high)


def a_pair(**overrides: Any) -> dict[str, Any]:
    """A scored, unjudged pair. Every field the shape requires and nothing else."""
    low, high, key = keys_of(LEFT, RIGHT)
    payload: dict[str, Any] = {
        "date": DATE,
        "run_id": RUN,
        "shard": 0,
        "pair_key": key,
        "left_url_key": low,
        "right_url_key": high,
        "composite_score": 0.9,
        "cosine": 0.9,
        "key_point": 0.4,
        "headline": False,
        "scorer_model": "all-minilm-l6-v2-quantized",
        "cosine_weight": 1.0,
        "key_point_weight": 0.0,
    }
    return payload | overrides


def a_record(**overrides: Any) -> dict[str, Any]:
    """A twenty-slot band, empty, on the committed grid."""
    payload: dict[str, Any] = {
        "band_low": 0.88,
        "band_high": 0.9,
        "bin_width": 0.001,
        "slots": [{"bin_low": round(0.88 + i * 0.001, 3)} for i in range(20)],
    }
    return payload | overrides


def a_fit(**overrides: Any) -> dict[str, Any]:
    """A row where a fit ran and nothing clamped it."""
    payload: dict[str, Any] = {
        "date": DATE,
        "run_id": RUN,
        "record_stamp": derive_text_digest("a record"),
        "previous": 0.94,
        "proposed": 0.938,
        "after_damping": 0.9397,
        "applied": 0.9397,
        "discard_share": 0.01,
        "smoothing_weight": 0.15,
        "max_down_step": 0.005,
        "step_change_multiple": 5.0,
        "pairs_in_band": 400,
        "pairs_judged": 200,
        "pairs_usable": 180,
        "disagreement_rate": 0.07,
        "unclear_rate": 0.11,
        "negatives_on_record": 241,
        "above_line_on_record": 48,
        "days_on_record": 12,
        "merge_count": 22,
        "scorer_model": "all-minilm-l6-v2-quantized",
        "cosine_weight": 1.0,
        "key_point_weight": 0.0,
    }
    return payload | overrides


def a_mark(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "left_url": LEFT,
        "right_url": RIGHT,
        "left_date": DATE,
        "right_date": DATE,
        "left_title": "One headline",
        "right_title": "Another headline",
        "same_story": False,
        "marked_on": DATE,
        "note": "Two events that share a subject.",
    }
    return payload | overrides


def test_the_scorer_literal_names_the_encoder_the_pipeline_actually_runs() -> None:
    """A Literal that names a model nothing runs would type-check and mean nothing.

    The scorer column exists so that swapping the encoder is a schema diff. That
    only holds while the spelling on the row is the spelling the embedder
    answers to, so the two are held against each other rather than both
    maintained by hand.
    """
    assert get_args(ScorerModelId) == (EMBEDDER_ID,)


def test_the_judge_literal_names_every_model_this_repo_ships() -> None:
    """A judge this repository cannot stand up is a judge no row can honestly name.

    Read off `config/models/` rather than spelled twice: five files carry four
    distinct ids, and a model added there without a spelling here would be
    unnameable on a row the day somebody pointed `models_file` at it.
    """
    shipped = set()
    for path in sorted((CONFIG_DIR / "models").glob("*.json")):
        payload = json.loads(read_text(path))
        shipped.add(payload["summarize"]["id"])

    assert set(get_args(JudgeModelId)) == shipped


def test_a_pair_named_by_the_wrong_digest_is_refused() -> None:
    """A pair filed under another pair's identity joins to the wrong holdout mark.

    Nothing downstream re-derives it, so a writer that filled the cell from a
    stale variable would put this pair's verdict on a different pair for ever.
    """
    with pytest.raises(ValidationError, match="pair_key"):
        StorySimilarityPair.model_validate(a_pair(pair_key=derive_text_digest("elsewhere")))

    other_way = a_pair()
    other_way["left_url_key"], other_way["right_url_key"] = (
        other_way["right_url_key"],
        other_way["left_url_key"],
    )
    with pytest.raises(ValidationError, match="sorted order"):
        StorySimilarityPair.model_validate(other_way)


def test_a_pair_whose_score_is_not_its_weighted_terms_is_refused() -> None:
    """The row carries the terms and the answer, so a row that disagrees is unreadable.

    A later reweighting is computed from the two raw terms on the row. A
    composite that no rule on the row produces would make that computation
    silently wrong rather than loudly impossible.
    """
    with pytest.raises(ValidationError, match="composite_score"):
        StorySimilarityPair.model_validate(a_pair(composite_score=0.99))

    split = StorySimilarityPair.model_validate(
        a_pair(cosine=0.9, key_point=0.5, cosine_weight=0.8, key_point_weight=0.2, composite_score=0.82)
    )
    assert split.composite_score == 0.82


def test_a_headline_matched_pair_scores_one_and_is_accepted() -> None:
    """The second of the two rules, which a weighted-sum-only check would refuse.

    A shared headline scores 1.0 outright whatever the cosine is, and the
    fixture's cosine of 0.7298 is nowhere near 1.0 - so this is the case that
    proves the validator reads `headline` rather than only the weights.
    """
    path = CONTRACT_FIXTURES_DIR / "story-similarity-pair" / "a-headline-match-scores-one.json"
    row = StorySimilarityPair.from_json(read_text(path))

    assert row.headline is True
    assert row.composite_score == 1.0
    assert row.cosine < 0.8, "the fixture stopped being a case the weights alone would refuse"

    with pytest.raises(ValidationError, match=r"scores 1\.0 outright"):
        StorySimilarityPair.model_validate(a_pair(headline=True))


def test_a_verdict_with_no_judge_named_is_refused() -> None:
    """A label nobody can re-read is a label the record must not fold.

    The three judge columns are one fact, and `usable` is the flag the fold
    reads - so a row that sets it before the two readings agree would fold a
    disagreement as evidence.
    """
    with pytest.raises(ValidationError, match="names the judge"):
        StorySimilarityPair.model_validate(a_pair(verdict=SameStoryVerdict.NO))

    with pytest.raises(ValidationError, match="all three or none"):
        StorySimilarityPair.model_validate(a_pair(judge_model="qwen3-5-9b-q4-k-m"))

    judged = a_pair(
        verdict=SameStoryVerdict.NO,
        verdict_swapped=SameStoryVerdict.YES,
        usable=True,
        judge_model="qwen3-5-9b-q4-k-m",
        prompt_digest=derive_text_digest("a turn"),
        grammar_digest=derive_text_digest("a grammar"),
    )
    with pytest.raises(ValidationError, match="usable"):
        StorySimilarityPair.model_validate(judged)

    both_unclear = judged | {
        "verdict": SameStoryVerdict.UNCLEAR,
        "verdict_swapped": SameStoryVerdict.UNCLEAR,
    }
    assert StorySimilarityPair.model_validate(both_unclear).usable is True


def test_a_record_whose_slot_count_disagrees_with_its_band_is_refused() -> None:
    """A short record is a band with a hole in it that every later fold widens.

    The fit walks the slots from the top, so a missing slot is a count read at
    the wrong score rather than a count that is absent.
    """
    short = a_record()
    short["slots"] = short["slots"][:-1]
    with pytest.raises(ValidationError, match="19"):
        StorySimilarityDistribution.model_validate(short)

    with pytest.raises(ValidationError, match="does not divide into whole slots"):
        StorySimilarityDistribution.model_validate(a_record(bin_width=0.0007))


def test_a_record_whose_slots_are_off_the_grid_is_refused() -> None:
    """A slot at the wrong edge files a pair's verdict under a score it did not get.

    The count is right and the score is wrong, which is the failure no total can
    see: the record still sums to the number of pairs judged.
    """
    drifted = a_record()
    drifted["slots"][7]["bin_low"] = 0.8875
    with pytest.raises(ValidationError, match="slot 7"):
        StorySimilarityDistribution.model_validate(drifted)


def test_a_date_already_folded_is_refused() -> None:
    """A day counted twice cannot be uncounted, so it is refused rather than absorbed.

    This is what makes a re-run free: the second fold is a no-op instead of a
    doubling nothing downstream can detect.
    """
    with pytest.raises(ValidationError, match="already holds"):
        StorySimilarityDistribution.model_validate(
            a_record(folded_dates=["2026-09-17", "2026-09-17"])
        )

    with pytest.raises(ValidationError, match="sorted"):
        StorySimilarityDistribution.model_validate(
            a_record(folded_dates=["2026-09-18", "2026-09-17"])
        )


def test_a_held_row_says_nothing_was_clamped() -> None:
    """A held day ran no fit, so there was nothing for a clamp to shape.

    A row carrying both would read as a day the line was pushed back, which is
    the opposite of what happened, and the guard's median would then be taken
    over a movement nobody made.
    """
    held = a_fit(
        held_reason=HeldReason.SHEET_TOO_SMALL,
        proposed=None,
        after_damping=None,
        applied=0.94,
        clamp_kind=ClampKind.STEP,
        clamp_movement=0.001,
    )
    with pytest.raises(ValidationError, match="could be clamped"):
        FittedSimilarityThreshold.model_validate(held)

    moved = held | {"clamp_kind": ClampKind.NONE, "clamp_movement": 0.0, "applied": 0.93}
    with pytest.raises(ValidationError, match="the line stays at"):
        FittedSimilarityThreshold.model_validate(moved)


def test_a_held_row_carries_no_proposal() -> None:
    """No fit ran, so there is no evidence to report and an empty cell is the honest one.

    A held row that carried a proposal would let a later reader compute a shift
    from a number the run never acted on.
    """
    path = (
        CONTRACT_FIXTURES_DIR
        / "fitted-similarity-threshold"
        / "the-record-is-too-small-to-fit-on.json"
    )
    row = FittedSimilarityThreshold.from_json(read_text(path))

    assert row.held_reason is HeldReason.SHEET_TOO_SMALL
    assert (row.proposed, row.after_damping) == (None, None)
    assert row.applied == row.previous

    with pytest.raises(ValidationError, match="no proposal"):
        FittedSimilarityThreshold.model_validate(
            a_fit(held_reason=HeldReason.LEGS_MISSING, applied=0.94, proposed=0.93)
        )

    with pytest.raises(ValidationError, match="both the proposal"):
        FittedSimilarityThreshold.model_validate(a_fit(proposed=None, after_damping=None))


def test_a_row_from_the_first_fortnight_has_no_typical_shift() -> None:
    """The guard fills over fourteen rows, and an empty cell is how a reader sees it.

    Zero would read as a median of zero, which is a guard that fires on the
    first day. The column is nullable so that "not yet" and "no movement" are
    two different readings.
    """
    early = FittedSimilarityThreshold.model_validate(a_fit(daily_shift=0.0011))

    assert early.typical_shift is None
    assert early.daily_shift == 0.0011


def test_the_clamp_movement_is_what_the_clamp_held_back() -> None:
    """The word and the number are one fact twice, so a row that disagrees lies to one.

    `clamp_kind` is what a person scans and `clamp_movement` is what a later fit
    reads, and a step clamp recording no movement would hide exactly the days
    the line wanted to fall furthest.
    """
    path = (
        CONTRACT_FIXTURES_DIR
        / "fitted-similarity-threshold"
        / "the-clamp-held-a-fall-back-to-the-step.json"
    )
    row = FittedSimilarityThreshold.from_json(read_text(path))

    assert row.clamp_kind is ClampKind.STEP
    assert row.held_reason is HeldReason.NONE
    assert row.after_damping is not None
    assert row.clamp_movement == pytest.approx(row.applied - row.after_damping)

    with pytest.raises(ValidationError, match="clamp_movement"):
        FittedSimilarityThreshold.model_validate(
            a_fit(clamp_kind=ClampKind.STEP, clamp_movement=0.004)
        )

    with pytest.raises(ValidationError, match=r"clamp_movement is 0\.0"):
        FittedSimilarityThreshold.model_validate(a_fit(clamp_movement=0.002))

    with pytest.raises(ValidationError, match="the guard holds the line"):
        FittedSimilarityThreshold.model_validate(a_fit(clamp_kind=ClampKind.GUARD))


def test_a_holdout_row_recomputes_its_own_keys() -> None:
    """A person types this file, so no cell they could mistype decides identity.

    The pair key is what joins a mark to a scored row, and a typed digest is a
    mark that quietly attaches to the wrong pair.
    """
    path = (
        CONTRACT_FIXTURES_DIR
        / "similarity-holdout-pair"
        / "two-stories-a-person-marked-apart.json"
    )
    mark = SimilarityHoldoutPair.from_json(read_text(path))

    assert mark.same_story is False
    assert mark.left_url_key == derive_url_key(mark.left_url)
    assert mark.right_url_key == derive_url_key(mark.right_url)
    low, high = sorted((mark.left_url_key, mark.right_url_key))
    assert mark.pair_key == derive_text_digest(low + high)
    assert "url_key" not in mark.model_dump(mode="json"), "a derived key is not a column"

    with pytest.raises(ValidationError, match="two articles"):
        SimilarityHoldoutPair.model_validate(a_mark(right_url=LEFT))


def test_every_row_shape_survives_the_ledger_round_trip() -> None:
    """A CSV cell is a string, so every nullable and every bool has to come back.

    The three row shapes are appended to files a later run reads back. An empty
    cell that returned as the string "" or a bool that returned as the truthy
    "False" would validate and mean the opposite of what was written.
    """
    pair = StorySimilarityPair.model_validate(a_pair())
    assert pair.csv_row()["verdict"] == ""
    assert StorySimilarityPair.from_csv_row(pair.csv_row()) == pair

    judged = StorySimilarityPair.model_validate(
        a_pair(
            verdict=SameStoryVerdict.YES,
            verdict_swapped=SameStoryVerdict.YES,
            usable=True,
            judge_model="qwen3-5-9b-q4-k-m",
            prompt_digest=derive_text_digest("a turn"),
            grammar_digest=derive_text_digest("a grammar"),
            decode_seconds=151.8,
        )
    )
    assert StorySimilarityPair.from_csv_row(judged.csv_row()) == judged

    fit = FittedSimilarityThreshold.model_validate(a_fit(settled=True))
    assert fit.csv_row()["typical_shift"] == ""
    assert FittedSimilarityThreshold.from_csv_row(fit.csv_row()) == fit

    mark = SimilarityHoldoutPair.model_validate(a_mark())
    assert mark.csv_row()["same_story"] == "False"
    assert SimilarityHoldoutPair.from_csv_row(mark.csv_row()) == mark

    for shape in (StorySimilarityPair, FittedSimilarityThreshold, SimilarityHoldoutPair):
        assert shape.csv_columns()[0] == "version", "a row records the contract that wrote it"
