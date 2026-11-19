"""Which pairs of the last few nights count as evidence for a threshold, and how much of it?

Every row is built in the test that uses it, through the contract (CLAUDE.md section 13).
What these cannot settle is whether the judge's answers near a threshold follow a curve at
all: that is what the first real nights show.
"""

from __future__ import annotations

from typing import Any

import pytest
from support.judged_pairs import a_judged_pair

from idhazh.similarity.threshold_evidence import (
    Evidence,
    current_pairs,
    evidence_days,
    evidence_near,
    meaning_stamp,
    tonights_stamp,
)


def test_the_window_is_the_days_that_end_on_the_night_oldest_first() -> None:
    assert evidence_days("2026-11-19", window_nights=7) == (
        "2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16",
        "2026-11-17", "2026-11-18", "2026-11-19",
    )
    assert evidence_days("2026-03-01", window_nights=3) == ("2026-02-27", "2026-02-28", "2026-03-01")
    assert evidence_days("2026-11-19", window_nights=1) == ("2026-11-19",)


def test_each_pair_counts_once_by_the_row_filed_last() -> None:
    """A re-run judged the same pair again, and both runs kept their rows."""
    first = a_judged_pair(0, score=0.71, answer="NO", pair=5, run_id="2026-11-18-1")
    rerun = a_judged_pair(1, score=0.71, answer="YES", pair=5, run_id="2026-11-18-2")
    other = a_judged_pair(2, score=0.72, answer="NO", pair=6)

    kept = current_pairs([first, other, rerun], stamp=meaning_stamp(first))

    assert sorted((row.pair_key, row.verdict.value) for row in kept if row.verdict) == sorted(
        [(other.pair_key, "NO"), (rerun.pair_key, "YES")]
    )


def test_a_newer_reading_that_disagreed_replaces_the_older_one_that_agreed() -> None:
    """The newest row is the pair's reading, so it is chosen before usability is asked."""
    agreed = a_judged_pair(0, score=0.71, answer="YES", pair=5, run_id="2026-11-18-1")
    later_disagreed = a_judged_pair(
        1, score=0.71, answer=("YES", "NO"), pair=5, run_id="2026-11-18-2"
    )

    assert current_pairs([agreed, later_disagreed], stamp=meaning_stamp(agreed)) == []


@pytest.mark.parametrize(
    "change",
    [
        {"judge_model": "another-model-q4"},
        {"prompt_digest": "c" * 64},
        {"grammar_digest": "d" * 64},
        {"scorer_model": "another-encoder"},
        {"cosine_weight": 0.9, "cosine": 0.71 / 0.9},
        {"judge_policy_version": "2026-10-01"},
    ],
    ids=["judge", "prompt", "grammar", "scorer", "cosine weight", "judge policy"],
)
def test_a_pair_read_under_another_meaning_is_not_pooled_with_tonights(
    change: dict[str, Any],
) -> None:
    tonight = a_judged_pair(0, score=0.71)
    earlier = a_judged_pair(1, score=0.71, date="2026-11-17", **change)

    kept = current_pairs([earlier, tonight], stamp=meaning_stamp(tonight))

    assert kept == [tonight]


def test_only_a_pair_whose_two_readings_agree_is_usable() -> None:
    agreed = a_judged_pair(0, score=0.71, answer="UNCLEAR")
    disagreed = a_judged_pair(1, score=0.71, answer=("YES", "NO"))

    assert current_pairs([agreed, disagreed], stamp=meaning_stamp(agreed)) == [agreed]


def test_the_pairs_near_a_threshold_are_those_within_the_width_either_side_edges_included() -> None:
    """The edges are exact in binary, 0.75 less 0.0625 and 0.75 plus 0.0625, so none is a guess."""
    rows = [
        a_judged_pair(0, score=0.6874, answer="NO"),
        a_judged_pair(1, score=0.6875, answer="NO"),
        a_judged_pair(2, score=0.75, answer="YES"),
        a_judged_pair(3, score=0.8125, answer="YES"),
        a_judged_pair(4, score=0.8126, answer="YES"),
    ]

    evidence = evidence_near(rows, threshold=0.75, width=0.0625)

    assert sorted(zip(evidence.scores, evidence.answers, strict=True)) == [
        (0.6875, 0),
        (0.75, 1),
        (0.8125, 1),
    ]
    assert evidence.usable_pairs_used == 3


def test_an_unclear_pair_is_not_the_same_story_and_nor_is_a_no() -> None:
    rows = [
        a_judged_pair(0, score=0.70, answer="UNCLEAR"),
        a_judged_pair(1, score=0.71, answer="NO"),
        a_judged_pair(2, score=0.72, answer="YES"),
    ]

    evidence = evidence_near(rows, threshold=0.7, width=0.06)

    assert sorted(zip(evidence.scores, evidence.answers, strict=True)) == [
        (0.70, 0),
        (0.71, 0),
        (0.72, 1),
    ]


def test_the_evidence_says_how_many_nights_it_came_from_and_where_it_starts() -> None:
    rows = [
        a_judged_pair(0, score=0.70, date="2026-11-17"),
        a_judged_pair(1, score=0.71, date="2026-11-15"),
        a_judged_pair(2, score=0.72, date="2026-11-15"),
        a_judged_pair(3, score=0.90, date="2026-11-13"),
    ]

    evidence = evidence_near(rows, threshold=0.7, width=0.06)

    assert (evidence.nights_used, evidence.first_date) == (2, "2026-11-15")


def test_no_pair_near_the_threshold_is_no_nights_and_no_first_day() -> None:
    evidence = evidence_near([a_judged_pair(0, score=0.9)], threshold=0.7, width=0.06)

    assert evidence == Evidence(scores=(), answers=(), nights_used=0, first_date=None)


def test_one_set_of_pairs_gives_one_sequence_whatever_order_the_ledger_returned_them_in() -> None:
    rows = [
        a_judged_pair(index, score=0.66 + 0.01 * index, date=f"2026-11-1{day}")
        for index, day in enumerate((8, 6, 7, 6, 8, 7))
    ]

    forward = evidence_near(rows, threshold=0.7, width=0.06)
    backward = evidence_near(rows[::-1], threshold=0.7, width=0.06)

    assert forward == backward


def test_the_nights_own_rows_carry_one_stamp_or_the_night_is_refused() -> None:
    tonight = [a_judged_pair(0, score=0.71), a_judged_pair(1, score=0.72)]

    assert tonights_stamp(tonight) == meaning_stamp(tonight[0])
    with pytest.raises(ValueError, match="one meaning stamp"):
        tonights_stamp([*tonight, a_judged_pair(2, score=0.73, judge_model="another-model-q4")])


def test_a_night_nothing_was_judged_on_has_no_stamp_and_so_no_evidence() -> None:
    """Every runner lost: no pair was read tonight, so there is no meaning to pool the window under."""
    earlier = a_judged_pair(0, score=0.71, date="2026-11-17")

    assert tonights_stamp([]) is None
    assert current_pairs([earlier], stamp=None) == []
