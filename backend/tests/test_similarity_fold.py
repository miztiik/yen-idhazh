"""What does the record hold after a day is counted into it, and what is refused?

Every record and every row here is built in the test that uses it. Nothing walks
the committed day tree: the arithmetic is about one record and a handful of rows,
and a fixture that grows with the archive would make these slower every week
(CLAUDE.md section 13).
"""

from __future__ import annotations

import json
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import SameStoryVerdict, StorySimilarityPair
from idhazh.similarity import fold
from idhazh.similarity.stamps import JudgeStamp, ScorerStamp

DATE: Final = "2026-09-18"

#: A twelve-slot band, wide enough to tell an edge from a middle and small enough
#: that a failing assertion names a slot a reader can count to.
KNOBS: Final = SimilarityThresholdConfig(band_low=0.50, band_high=0.62, bin_width=0.01)


def a_scorer() -> ScorerStamp:
    return ScorerStamp(scorer_model="all-minilm-l6-v2-quantized", cosine_weight=1.0,
                       key_point_weight=0.0)


def a_judge() -> JudgeStamp:
    return JudgeStamp(judge_model="qwen3-5-9b-q4-k-m", prompt_digest="a" * 64,
                      grammar_digest="b" * 64)


def a_record() -> StorySimilarityDistribution:
    return fold.empty_record(KNOBS, scorer=a_scorer(), judge=a_judge())


def a_row(
    *,
    score: float,
    verdict: SameStoryVerdict = SameStoryVerdict.NO,
    usable: bool = True,
    pair_key: str | None = None,
    run_id: str = f"{DATE}-1",
    judged_by_run_id: str | None = None,
) -> StorySimilarityPair:
    """One judged pair, re-cast from the committed contract fixture.

    Read inside the helper rather than at module scope, so a fixture that stops
    parsing fails the test that asked for a row instead of every test here.
    """
    raw = json.loads(
        read_text(
            CONTRACT_FIXTURES_DIR / "story-similarity-pair" / "judged-the-same-in-both-orders.json"
        )
    )
    return StorySimilarityPair.model_validate(
        raw
        | {
            "version": StorySimilarityPair.schema_version(),
            "date": DATE,
            "run_id": run_id,
            "judged_by_run_id": judged_by_run_id,
            "composite_score": score,
            "cosine": score,
            "verdict": verdict.value,
            "verdict_swapped": verdict.value,
            "usable": usable,
            "pair_key": pair_key or raw["pair_key"],
        }
    )


def test_a_score_lands_in_the_slot_whose_lower_edge_it_clears() -> None:
    """A pair scoring a slot's lower edge is in that slot, not the one below."""
    record = a_record()

    assert fold.slot_index(0.50, record=record) == 0
    assert fold.slot_index(0.5099, record=record) == 0
    assert fold.slot_index(0.51, record=record) == 1


def test_a_score_at_the_top_of_the_band_lands_in_the_last_slot() -> None:
    """`band_high` has no next slot to fall into, so it closes the last one."""
    record = a_record()

    assert fold.slot_index(0.62, record=record) == len(record.slots) - 1


def test_a_score_outside_the_band_lands_nowhere() -> None:
    """Below the band nothing was ever judged, so the record can say nothing."""
    record = a_record()

    assert fold.slot_index(0.499, record=record) is None
    assert fold.slot_index(0.621, record=record) is None


def test_an_exact_slot_edge_on_the_shipped_band_is_that_slot() -> None:
    """`(0.950 - 0.88) / 0.001` is 69.99999999999995, and an untoleranced walk files 69.

    Driven on the band the pipeline actually ships rather than this module's
    twelve-slot one, because the defect only appears at edges where the division
    lands a hair short - and the shipped band has 120 of them. The fit reads the
    merge line off a slot edge, so filing one slot low is a whole bin of error on
    the one number this feature exists to set.
    """
    record = fold.empty_record(
        SimilarityThresholdConfig(), scorer=a_scorer(), judge=a_judge()
    )

    for score in (0.900, 0.930, 0.950, 0.970, 0.990):
        index = fold.slot_index(score, record=record)
        assert index is not None
        assert record.slots[index].bin_low == pytest.approx(score), (
            f"{score} is a slot's own lower edge and belongs in that slot"
        )


def test_an_unusable_row_is_counted_nowhere() -> None:
    """A verdict nobody can vouch for still moves the line if it is counted."""
    record = a_record()

    folded = fold.fold_day(record, [a_row(score=0.55, usable=False)], date=DATE)

    assert sum(slot.different_count for slot in folded.slots) == 0
    assert folded.folded_dates == (DATE,), "the day is still counted as read"


def test_an_unclear_verdict_is_counted_only_as_unclear() -> None:
    """Counted and never fitted on, so a rising share of them is visible."""
    record = a_record()

    folded = fold.fold_day(
        record, [a_row(score=0.55, verdict=SameStoryVerdict.UNCLEAR)], date=DATE
    )

    slot = folded.slots[fold.slot_index(0.55, record=record) or 0]
    assert (slot.same_count, slot.different_count, slot.unclear_count) == (0, 0, 1)


def test_folding_a_date_the_record_already_holds_raises() -> None:
    """A re-run of the fold is free rather than a day counted twice."""
    record = fold.fold_day(a_record(), [a_row(score=0.55)], date=DATE)

    with pytest.raises(ValueError, match=DATE):
        fold.fold_day(record, [a_row(score=0.55)], date=DATE)


def test_a_changed_scorer_stamp_archives_and_starts_empty() -> None:
    """A different weight puts the same pair in a different slot."""
    record = a_record()
    moved = ScorerStamp(
        scorer_model="all-minilm-l6-v2-quantized", cosine_weight=0.8, key_point_weight=0.2
    )

    assert fold.inputs_changed(record, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()) is None
    assert fold.inputs_changed(record, knobs=KNOBS, scorer=moved, judge=a_judge()) == ("1.0", "0.8")
    assert fold.archive_stem(record) != fold.archive_stem(
        fold.empty_record(KNOBS, scorer=moved, judge=a_judge())
    )


def test_one_pair_judged_twice_is_counted_once_at_the_newer_run() -> None:
    """The newer run read the day as it stands; counting both doubles one pair."""
    record = a_record()
    rows = [
        a_row(score=0.55, verdict=SameStoryVerdict.YES, run_id=f"{DATE}-1"),
        a_row(score=0.55, verdict=SameStoryVerdict.NO, run_id=f"{DATE}-2"),
    ]

    kept = fold.one_row_a_pair(rows)

    assert [row.run_id for row in kept] == [f"{DATE}-2"]
    folded = fold.fold_day(record, rows, date=DATE)
    slot = folded.slots[fold.slot_index(0.55, record=record) or 0]
    assert (slot.same_count, slot.different_count) == (0, 1)


def test_a_stamped_re_judge_beats_the_unstamped_rows_it_replaces() -> None:
    """Three rows, because two of them are what the old ordering decided between.

    `judged_by_run_id` is empty on every row written before the column existed,
    and an empty stamp sorts lowest - so a re-judge wins whichever digest run it
    is filed under. The two unstamped rows are still ordered by `run_id`, which
    is what this did before the column existed: drop that half of the pair and
    they would compare equal and the first one seen would win.
    """
    rows = [
        a_row(score=0.55, verdict=SameStoryVerdict.YES, run_id=f"{DATE}-2"),
        a_row(
            score=0.55,
            verdict=SameStoryVerdict.NO,
            run_id=f"{DATE}-1",
            judged_by_run_id=f"{DATE}-7",
        ),
        a_row(score=0.55, verdict=SameStoryVerdict.UNCLEAR, run_id=f"{DATE}-1"),
    ]

    kept = fold.one_row_a_pair(rows)

    assert [row.verdict for row in kept] == [SameStoryVerdict.NO]
    assert [row.run_id for row in fold.one_row_a_pair(rows[::2])] == [f"{DATE}-2"]
