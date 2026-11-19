"""Does the stage that reviews the thresholds read what the night filed, and file one honest row?

Every night here is laid down the way the collecting job finds it: a draw file, a verdict file
and a shipped reading for each unit that came back. The pairs go through `file_pair_verdicts`
into a real ledger in `tmp_path`, and the review then reads them back through the door. The last
test is the row's oracle: a run of 14 nights, every number of every row worked out again from the
ledger and from the row's own columns by a second, independent working. Nothing walks the
committed ledger (CLAUDE.md section 13).

The pure arithmetic of the review is `test_review_thresholds.py`, `test_similarity_threshold_*.py`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any, Final

import pytest
from support.judged_pairs import DATE, a_night_of_pairs, a_reading, a_saver, a_verdict_file
from support.ledger import seed_compact_index
from support.paths import CONFIG_DIR
from support.threshold_nights import LOOKBACK, RULES, STEADY, a_day, pairs_beside

from idhazh import atomic_write, ledger
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.ledger_reads import (
    load_pair_verdicts,
    load_threshold_history,
    review_days,
)
from idhazh.content_similarity_judge.tenant import JUDGE_ID
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair_verdict import (
    SameStoryVerdict,
    StorySimilarityPairVerdict,
)
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
    ThresholdHoldReason,
)
from idhazh.council import metrics_sink
from idhazh.similarity.thresholds_in_force import thresholds_in_force
from idhazh.stages import file_pair_verdicts, review_thresholds

PAIRS: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS
HISTORY: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY
JUDGE_CONFIG: Final = judge_settings.load(CONFIG_DIR)

#: Two pairs in the fully similar end and one in the fully dissimilar end, so each lightly
#: sampled end has a pool and a handful of answers. Every slice held three times what was drawn.
ENDS: Final = [(0.95, "YES"), (0.96, "YES"), (0.40, "NO")]


@dataclass(frozen=True, slots=True)
class Night:
    """Where a night's files are laid, for the stage that reads them."""

    date: str
    run_id: str
    draw: Path
    shipped: Path
    verdicts: Path
    units: int


def lay_down_a_night(
    root: Path,
    state: Path,
    step: int,
    *,
    thresholds: tuple[float, float] | None = None,
    shift: float = 0.0,
    units: int = 2,
    lost: Sequence[int] = (),
    extra: Sequence[tuple[float, str]] = (),
    attempt: int = 0,
) -> Night:
    """A night as the collecting job finds it, with its pairs filed and its review still to run.

    The draw follows the thresholds the history in `state` puts it at, as the real draw does,
    unless `thresholds` says what it followed. The pairs are dealt to the units in turn, a lost
    unit leaves no verdict file and no shipped reading, and the draw file names every pair either
    way. `attempt` gives another run of the same night its own run id and the same pairs.
    """
    date = a_day(step)
    run_id = f"{date}-{9 + attempt}"
    if thresholds is None:
        followed = thresholds_in_force(
            load_threshold_history(
                state, review_days(date, config=JUDGE_CONFIG).threshold_history
            ),
            night=date,
            within_days=LOOKBACK,
            lower_start=RULES.lower_start,
            upper_start=RULES.upper_start,
        )
        thresholds = (followed.lower, followed.upper)
    lower, upper = thresholds
    pairs = [*pairs_beside(lower, upper, shift=shift, night=step), *extra]
    drawn = a_night_of_pairs(
        pairs,
        answered=False,
        date=date,
        run_id=run_id,
        first_index=step * 1000,
        lower=lower,
        upper=upper,
    )
    judged = a_night_of_pairs(
        pairs, date=date, run_id=run_id, first_index=step * 1000, lower=lower, upper=upper
    )

    night = Night(
        date=date,
        run_id=run_id,
        draw=root / date / f"draw-{attempt}.csv",
        shipped=root / date / f"shipped-{attempt}",
        verdicts=root / date / f"verdicts-{attempt}",
        units=units,
    )
    atomic_write.write_atomic(night.draw, a_verdict_file(drawn))
    for unit in range(units):
        if unit in lost:
            continue
        rows = [
            row.model_copy(update={"work_part_index": unit}) for row in judged[unit::units]
        ]
        metrics_sink.ship_judge_metrics(
            a_reading(shard=unit, dealt=len(rows), date=date, run_id=run_id),
            judge_id=JUDGE_ID,
            name=str(unit),
            out_dir=night.shipped,
        )
        atomic_write.write_atomic(
            night.verdicts / f"{date}-{JUDGE_ID}-{unit:02d}.csv", a_verdict_file(rows)
        )
    file_pair_verdicts.stage_file_pair_verdicts(
        date,
        run_id=run_id,
        judge_id=JUDGE_ID,
        shipped_root=night.shipped,
        verdicts_dir=night.verdicts,
        identity=a_saver(run_id),
        expected_shards=units,
        state_dir=state,
    )
    return night


def review(night: Night, state: Path) -> review_thresholds.ReviewReport:
    return review_thresholds.stage_review_thresholds(
        night.date,
        run_id=night.run_id,
        judge_id=JUDGE_ID,
        shipped_root=night.shipped,
        draw_path=night.draw,
        identity=a_saver(night.run_id),
        expected_shards=night.units,
        state_dir=state,
        config_dir=CONFIG_DIR,
    )


def settle_a_night(
    root: Path,
    state: Path,
    step: int,
    *,
    shift: float = 0.0,
    units: int = 2,
    lost: Sequence[int] = (),
    extra: Sequence[tuple[float, str]] = (),
    attempt: int = 0,
) -> StorySimilarityThresholdHistoryRow:
    """Lay a night down and review it, and hand back the row it filed."""
    night = lay_down_a_night(
        root, state, step, shift=shift, units=units, lost=lost, extra=extra, attempt=attempt
    )
    report = review(night, state)
    assert report.row is not None and report.filed
    return report.row


def test_a_night_that_dealt_no_pair_files_no_row(tmp_path: Path) -> None:
    """No draw rows and no judged rows is a night nothing ran, and a missing row is how it reads."""
    state, draw = tmp_path / "state", tmp_path / "draw.csv"
    atomic_write.write_atomic(draw, a_verdict_file([]))
    night = Night(DATE, f"{DATE}-9", draw, tmp_path / "nothing-shipped", tmp_path / "none", 2)

    report = review(night, state)

    assert (report.row, report.filed) == (None, False)
    assert not ledger.raw_root(state, HISTORY).exists()


def test_a_night_whose_every_pair_was_lost_files_a_row_that_says_so(tmp_path: Path) -> None:
    """The draw dealt pairs and both units died: no evidence, both thresholds held, pools kept.

    The pair-verdicts ledger holds nothing of the night, so the size of each lightly sampled end
    comes from the draw file, and what scored the night comes from its rows. The row is what
    tells this night from one that dealt nothing.
    """
    state = tmp_path / "state"

    row = settle_a_night(tmp_path, state, 0, lost=(0, 1), extra=ENDS)

    assert (row.runners_expected, row.runners_reported, row.pairs_dealt) == (2, 0, 0)
    assert row.lower_held_because is ThresholdHoldReason.NOT_ENOUGH_EVIDENCE
    assert row.upper_held_because is ThresholdHoldReason.NOT_ENOUGH_EVIDENCE
    assert (row.lower_threshold_before, row.lower_threshold_after) == (0.70, 0.70)
    assert (row.lower_usable_pairs_used, row.lower_estimate, row.lower_curve_steepness) == (0, None, None)
    assert (row.above_upper_pairs_available, row.above_upper_pairs_usable) == (6, 0)
    assert (row.below_lower_pairs_available, row.below_lower_pairs_usable) == (3, 0)
    assert (row.above_upper_same_story_estimated, row.below_lower_different_story_estimated) == (
        None,
        None,
    )
    assert row.scorer_model == "all-minilm-l6-v2-quantized" and row.judge_model is None
    assert load_pair_verdicts(state, [a_day(0)]) == []


def test_a_night_whose_units_reported_files_the_totals_of_the_units_that_did(tmp_path: Path) -> None:
    """Both units back: the ends' pools and weighted totals, and every reading summed.

    The fully similar end held 6 pairs and the draw took 2, both judged the same story, so each
    stands for 3 and the end is estimated at 6. The fully dissimilar end held 3, took one, and
    is estimated at 3. One unit lost leaves its readings out of every sum, so the four endings
    still add up to the pairs dealt, and `runners_reported` says one was lost.
    """
    both = settle_a_night(tmp_path / "both", tmp_path / "both-state", 0, extra=ENDS)
    one = settle_a_night(tmp_path / "one", tmp_path / "one-state", 0, extra=ENDS, lost=(1,))

    assert (both.above_upper_pairs_available, both.above_upper_pairs_usable) == (6, 2)
    assert both.above_upper_same_story_estimated == pytest.approx(6.0)
    assert both.below_lower_different_story_estimated == pytest.approx(3.0)
    assert (both.runners_reported, both.pairs_dealt) == (2, 83)
    assert both.decode_seconds_total == pytest.approx(3.5 + 4.5)
    assert both.decode_seconds_slowest_runner == pytest.approx(4.5)
    assert (one.runners_expected, one.runners_reported, one.pairs_dealt) == (2, 1, 42)
    assert one.decode_seconds_total == pytest.approx(3.5)
    assert one.pairs_agreed == one.pairs_dealt


def test_tonights_pairs_are_read_even_when_the_day_was_recorded_as_quiet(tmp_path: Path) -> None:
    """A night the judge repairs is a day the gardener already recorded as empty.

    The door serves such a day from the record and never opens the raw files filed after it, so
    the review reads tonight's rows raw and the nights before it through the door.
    """
    state = tmp_path / "state"
    day = a_day(3)
    seed_compact_index(
        state, PAIRS, Period.DAILY, [CompactEntry(covers=day, rows=0, bytes=0, state=EntryState.EMPTY)]
    )
    seed_compact_index(state, PAIRS, Period.MONTHLY, [])
    seed_compact_index(state, PAIRS, Period.YEARLY, [])

    row = settle_a_night(tmp_path, state, 3)

    assert load_pair_verdicts(state, [day]) == [], "the door still serves the day as empty"
    assert (row.lower_usable_pairs_used, row.upper_usable_pairs_used) == (40, 40)
    assert row.lower_nights_used == 1


def test_two_runs_of_one_night_start_from_the_same_thresholds_and_count_each_pair_once(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    for step in range(3):
        settle_a_night(tmp_path, state, step)

    first = settle_a_night(tmp_path, state, 3)
    again = settle_a_night(tmp_path, state, 3, attempt=1)

    assert (again.lower_threshold_before, again.upper_threshold_before) == (
        first.lower_threshold_before,
        first.upper_threshold_before,
    )
    assert (again.lower_usable_pairs_used, again.upper_usable_pairs_used) == (160, 160)
    assert again.lower_nights_used == first.lower_nights_used == 4
    assert [row.run_id for row in load_threshold_history(state, [a_day(3)])] == [
        first.run_id,
        again.run_id,
    ]


def test_a_reading_that_names_another_night_stops_the_review_and_files_nothing(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    night = lay_down_a_night(tmp_path, state, 0)
    metrics_sink.ship_judge_metrics(
        a_reading(shard=5, dealt=1, date=a_day(9), run_id=f"{a_day(9)}-9"),
        judge_id=JUDGE_ID,
        name="5",
        out_dir=night.shipped,
    )

    with pytest.raises(ValueError, match="another night's artifact"):
        review(night, state)

    assert not ledger.raw_root(state, HISTORY).exists()


def test_a_draw_file_that_is_missing_stops_the_review_and_files_nothing(tmp_path: Path) -> None:
    """A missing draw is an incomplete artifact, and would file every pool as empty."""
    state = tmp_path / "state"
    night = lay_down_a_night(tmp_path, state, 0)
    night.draw.unlink()

    with pytest.raises(FileNotFoundError, match="does not exist"):
        review(night, state)

    assert not ledger.raw_root(state, HISTORY).exists()
    assert len(load_pair_verdicts(state, [a_day(0)])) == 80


def test_a_draw_that_followed_thresholds_the_history_does_not_show_stops_the_review(
    tmp_path: Path,
) -> None:
    """A checkout missing the history would reset both thresholds to the starts without a word.

    The draw followed 0.66 and 0.93, and this checkout's history is empty, so it works them out
    as the starts. The review refuses, and the night keeps its pair rows and has no threshold
    row, which the scheduler reads as a night done.
    """
    state = tmp_path / "state"
    night = lay_down_a_night(tmp_path, state, 0, thresholds=(0.66, 0.93))

    with pytest.raises(ValueError, match="not the history the draw read"):
        review(night, state)

    assert not ledger.raw_root(state, HISTORY).exists()
    assert len(load_pair_verdicts(state, [a_day(0)])) == 80


# --- the oracle ---------------------------------------------------------------------------


def a_logit(share: float) -> float:
    return math.log(share / (1.0 - share))


def column(row: StorySimilarityThresholdHistoryRow, side: str, name: str) -> Any:
    """One of a row's `lower_` or `upper_` columns by its name."""
    return getattr(row, f"{side}_{name}")


def independent_after(
    side: str, before: float, gap: float, other: float
) -> float:
    """Where a move of this gap lands, worked from the documented rule and not the stage's code.

    The gap is cut to its step (far, widening for the move out, narrowing for the move in), then
    clamped by the one limit that faces its way, which only ever shortens it.
    """
    outward = gap < 0 if side == "lower" else gap > 0
    step = (
        RULES.far_gap_step
        if abs(gap) > RULES.far_gap
        else RULES.widening_step
        if outward
        else RULES.narrowing_step
    )
    landed = before + max(-step, min(step, gap))
    if side == "lower":
        return (
            max(landed, min(before, RULES.lowest_lower_threshold))
            if gap < 0
            else min(landed, max(before, other - RULES.smallest_gap))
        )
    return (
        max(landed, min(before, other + RULES.smallest_gap))
        if gap < 0
        else min(landed, max(before, RULES.highest_upper_threshold))
    )


def the_row_agrees_with_the_ledger(
    state: Path,
    row: StorySimilarityThresholdHistoryRow,
    previous: StorySimilarityThresholdHistoryRow | None,
) -> None:
    """Every number of one night's row, worked again from the ledger and from its own columns."""
    last = date_type.fromisoformat(row.date)
    days = [(last - timedelta(days=back)).isoformat() for back in range(6, -1, -1)]
    newest: dict[str, StorySimilarityPairVerdict] = {}
    for pair in load_pair_verdicts(state, days):
        newest[pair.pair_key] = pair
    usable = [pair for pair in newest.values() if pair.readings_agree]
    adjacent = previous is not None and previous.date == (last - timedelta(days=1)).isoformat()
    lower_after = row.lower_threshold_after

    for side in ("lower", "upper"):
        get = partial(column, row, side)
        before = get("threshold_before")
        expected_before = (
            getattr(previous, f"{side}_threshold_after")
            if adjacent
            else RULES.lower_start if side == "lower" else RULES.upper_start
        )
        assert before == pytest.approx(expected_before, abs=1e-9), f"{row.date} {side} chain"

        near = [pair for pair in usable if abs(pair.similarity_score - before) <= RULES.near_threshold_width]
        assert get("usable_pairs_used") == len(near), f"{row.date} {side} evidence"
        assert get("nights_used") == len({pair.date for pair in near})
        assert get("window_first_date") == (min(pair.date for pair in near) if near else None)

        estimate, gap = get("estimate"), get("gap")
        if estimate is None:
            assert get("curve_intercept") is None and gap is None
        else:
            a, b = get("curve_intercept"), get("curve_steepness")
            level = RULES.lower_share_level if side == "lower" else RULES.upper_share_level
            assert estimate == pytest.approx((a_logit(level) - a) / b, abs=1e-6)
            assert gap == pytest.approx(estimate - before, abs=1e-6)
            slope_a = slope_b = 0.0
            for pair in near:
                answer = float(pair.verdict is SameStoryVerdict.YES)
                chance = 1.0 / (1.0 + math.exp(-(a + b * pair.similarity_score)))
                slope_a += answer - chance
                slope_b += (answer - chance) * pair.similarity_score
            slope_b -= (b - get("pull_centre")) / get("pull_spread") ** 2
            assert abs(slope_a) < 1e-3 and abs(slope_b) < 1e-3, f"{row.date} {side} is not a maximum"

        beyond = 0
        if gap is not None and abs(gap) > RULES.ignore_range:
            before_gap = getattr(previous, f"{side}_gap") if adjacent else None
            beyond = (
                getattr(previous, f"{side}_nights_beyond_ignore_range") + 1
                if before_gap is not None
                and getattr(previous, f"{side}_nights_beyond_ignore_range") >= 1
                and (before_gap > 0) == (gap > 0)
                else 1
            )
        assert get("nights_beyond_ignore_range") == beyond

        held = (
            ThresholdHoldReason.NOT_ENOUGH_EVIDENCE
            if len(near) < RULES.minimum_usable_pairs
            else ThresholdHoldReason.FIT_FAILED
            if gap is None
            else ThresholdHoldReason.WITHIN_IGNORE_RANGE
            if abs(gap) <= RULES.ignore_range
            else ThresholdHoldReason.WAITING_FOR_SECOND_NIGHT
            if beyond < RULES.nights_running_required
            else ThresholdHoldReason.NONE
        )
        assert get("held_because") is held, f"{row.date} {side} word"
        other = row.upper_threshold_before if side == "lower" else lower_after
        after = before if held is not ThresholdHoldReason.NONE else independent_after(
            side, before, gap, other
        )
        assert get("threshold_after") == pytest.approx(after, abs=1e-9), f"{row.date} {side} move"
        assert get("move") == pytest.approx(after - before, abs=1e-9)


def test_fourteen_nights_through_the_stage_agree_with_a_second_working_of_every_number(
    tmp_path: Path,
) -> None:
    """Six steady nights and eight of a curve 0.05 lower: the rows hold, wait, move and settle.

    Inputs: 40 pairs beside each threshold a night, answered by a judge whose curve is known
    (`support.threshold_nights`), filed through `file_pair_verdicts` and reviewed through the
    stage. The oracle reads the ledger back and recomputes each stored number without the stage's
    own code: the evidence counts, the curve as a maximum of the pulled likelihood, the estimate,
    the gap, the nights in a row, the word and the move.
    """
    state = tmp_path / "state"
    rows = [
        settle_a_night(tmp_path, state, step, shift=-0.05 if step >= STEADY else 0.0)
        for step in range(STEADY + 8)
    ]

    previous = None
    for row in rows:
        the_row_agrees_with_the_ledger(state, row, previous)
        previous = row
    moves = {
        side: [round(getattr(row, f"{side}_move"), 6) for row in rows if getattr(row, f"{side}_move")]
        for side in ("lower", "upper")
    }
    assert moves["lower"] and moves["upper"], "the shift was never acted on"
    assert rows[STEADY - 1].lower_held_because is not ThresholdHoldReason.NONE
    assert load_threshold_history(state, [row.date for row in rows]) == rows
