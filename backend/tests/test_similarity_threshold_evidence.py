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
    adaptive_evidence_near,
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
        a_judged_pair(4, score=0.8126, answer="YES", judge_temperature=0.5),
    ]

    evidence = evidence_near(rows, threshold=0.75, width=0.0625)

    assert sorted(zip(evidence.scores, evidence.answers, strict=True)) == [
        (0.6875, 0),
        (0.75, 1),
        (0.8125, 1),
    ]
    assert evidence.judge_temperatures == frozenset({0.0})
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

    assert evidence == Evidence(
        scores=(), answers=(), nights_used=0, first_date=None, pair_keys=(),
        judge_temperatures=frozenset(),
    )


def test_one_set_of_pairs_gives_one_sequence_whatever_order_the_ledger_returned_them_in() -> None:
    rows = [
        a_judged_pair(index, score=0.66 + 0.01 * index, date=f"2026-11-1{day}")
        for index, day in enumerate((8, 6, 7, 6, 8, 7))
    ]

    forward = evidence_near(rows, threshold=0.7, width=0.06)
    backward = evidence_near(rows[::-1], threshold=0.7, width=0.06)

    assert forward == backward
    by_key = {row.pair_key: row for row in rows}
    ordered = [by_key[key] for key in forward.pair_keys]
    assert [row.date for row in ordered] == [
        "2026-11-16", "2026-11-16", "2026-11-17", "2026-11-17", "2026-11-18", "2026-11-18",
    ]
    assert forward.scores == tuple(row.similarity_score for row in ordered)


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


def test_evidence_near_excludes_identical_headline_overrides_from_cosine_fits() -> None:
    """Identical-headline pairs (score=1.0 outright) never distort the cosine logistic curve."""
    cosine_near = a_judged_pair(0, score=0.98, answer="YES")
    cosine_one = a_judged_pair(1, score=1.0, answer="YES", headline=False)
    headline_override = a_judged_pair(2, score=1.0, cosine=0.5, answer="YES", headline=True)

    evidence = evidence_near(
        [cosine_near, cosine_one, headline_override], threshold=0.95, width=0.06
    )

    assert evidence.pair_keys == tuple(sorted((cosine_near.pair_key, cosine_one.pair_key)))
    assert headline_override.pair_key not in evidence.pair_keys
    assert evidence.usable_pairs_used == 2


def test_adaptive_evidence_near_stops_at_min_window_expands_day_by_day_and_deduplicates() -> None:
    """Adaptive window stops at min_window when full, expands up to max_window, dedupes newest."""
    night = "2026-11-28"
    days_29 = evidence_days(night, window_nights=29)
    too_old = days_29[0]
    days_28 = days_29[1:]
    stamp = meaning_stamp(a_judged_pair(0, score=0.70, date=night))

    # 2 pairs per day across 28 days + 1 pair on day 29 (outside max_window_nights=28).
    rows = [
        a_judged_pair(day_index * 10 + slot, score=0.70, answer="NO", date=day)
        for day_index, day in enumerate(days_28)
        for slot in range(2)
    ]
    rows.insert(0, a_judged_pair(9999, score=0.70, answer="YES", date=too_old))

    # Stops at min_window_nights=7 when 14 >= 14, without pulling day 8.
    at_min = adaptive_evidence_near(
        rows,
        night=night,
        threshold=0.70,
        width=0.06,
        min_window_nights=7,
        max_window_nights=28,
        minimum_usable_pairs=14,
        stamp=stamp,
    )
    assert (at_min.nights_used, at_min.usable_pairs_used, at_min.first_date) == (
        7,
        14,
        days_28[-7],
    )

    # Expands day-by-day from 7 to 10 days to reach 20 usable pairs.
    expanded = adaptive_evidence_near(
        rows,
        night=night,
        threshold=0.70,
        width=0.06,
        min_window_nights=7,
        max_window_nights=28,
        minimum_usable_pairs=19,
        stamp=stamp,
    )
    assert (expanded.nights_used, expanded.usable_pairs_used, expanded.first_date) == (
        10,
        20,
        days_28[-10],
    )

    # Caps at max_window_nights=28 when still short, never reading day 29.
    capped = adaptive_evidence_near(
        rows,
        night=night,
        threshold=0.70,
        width=0.06,
        min_window_nights=7,
        max_window_nights=28,
        minimum_usable_pairs=100,
        stamp=stamp,
    )
    assert (capped.nights_used, capped.usable_pairs_used, capped.first_date) == (
        28,
        56,
        days_28[0],
    )

    # Repeated pair_key across days keeps only the newest row; a newer disagreement drops it.
    repeated_day_older = days_28[-10]
    repeated_day_newer = days_28[-2]
    older_agreed = a_judged_pair(
        0, score=0.70, answer="YES", date=repeated_day_older, pair=777, run_id=f"{repeated_day_older}-1"
    )
    newer_no = a_judged_pair(
        1, score=0.70, answer="NO", date=repeated_day_newer, pair=777, run_id=f"{repeated_day_newer}-1"
    )
    older_agreed_2 = a_judged_pair(
        2, score=0.70, answer="YES", date=repeated_day_older, pair=778, run_id=f"{repeated_day_older}-1"
    )
    newer_split = a_judged_pair(
        3,
        score=0.70,
        answer=("YES", "NO"),
        date=repeated_day_newer,
        pair=778,
        run_id=f"{repeated_day_newer}-1",
    )
    headline_row = a_judged_pair(
        4, score=1.0, cosine=0.5, answer="YES", date=night, headline=True, pair=779
    )
    deduped = adaptive_evidence_near(
        [older_agreed, older_agreed_2, newer_no, newer_split, headline_row],
        night=night,
        threshold=0.70,
        width=0.06,
        min_window_nights=7,
        max_window_nights=28,
        minimum_usable_pairs=5,
        stamp=stamp,
    )
    assert deduped.pair_keys == (newer_no.pair_key,)
    assert deduped.answers == (0,)
    assert deduped.first_date == repeated_day_newer
