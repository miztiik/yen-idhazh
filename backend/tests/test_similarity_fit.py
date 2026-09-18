"""Where does the walk put the line, what shapes it on the way out, and what holds it?

Every record and every row here is built in the test that uses it. Nothing walks
the committed day tree: the arithmetic is about one record and a handful of rows,
and a fixture that grows with the archive would make these slower every week
(CLAUDE.md section 13).

One step per test. A test that exercised the walk, the damping and both clamps at
once could go red without saying which of the four moved.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from conftest import read_text
from test_same_story import at, block, item, unit
from test_similarity_draw import MANIFEST_FIXTURE

from idhazh import assemble, config, ledger
from idhazh.contracts.digest_day import DigestDay, DigestRunRef, DigestVerticalRef
from idhazh.contracts.fitted_similarity_threshold import (
    ClampKind,
    FittedSimilarityThreshold,
    HeldReason,
)
from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.similarity import fit, fold
from idhazh.similarity.stamps import JudgeStamp, ScorerStamp
from idhazh.stages import common
from idhazh.stages.common import _load_day
from idhazh.stages.judge_fit import merge_count, stage_judge_fit

DATE: Final = "2026-09-18"

#: The shipped band, 0.88 to 1.00 in 120 slots of 0.001. The real grid rather
#: than a small one, because the one number every test here is about is where a
#: slot edge falls - and a band invented for the test would put it somewhere the
#: pipeline never puts it.
KNOBS: Final = SimilarityThresholdConfig()


def a_scorer() -> ScorerStamp:
    return ScorerStamp(
        scorer_model="all-minilm-l6-v2-quantized", cosine_weight=1.0, key_point_weight=0.0
    )


def a_judge() -> JudgeStamp:
    return JudgeStamp(
        judge_model="qwen3-5-9b-q4-k-m", prompt_digest="a" * 64, grammar_digest="b" * 64
    )


def a_record(
    *,
    knobs: SimilarityThresholdConfig = KNOBS,
    negatives: Mapping[float, int] | None = None,
    positives: Mapping[float, int] | None = None,
    unclear: Mapping[float, int] | None = None,
    dates: tuple[str, ...] = (),
) -> StorySimilarityDistribution:
    """A record with counts placed at scores a test names, and nothing else in it.

    The scores are the keys, so a failing assertion reads in the units the line
    is reported in rather than in slot numbers a reader has to convert.
    """
    record = fold.empty_record(knobs, scorer=a_scorer(), judge=a_judge())
    slots = list(record.slots)
    for column, counts in (
        ("same_count", positives or {}),
        ("different_count", negatives or {}),
        ("unclear_count", unclear or {}),
    ):
        for score, count in counts.items():
            index = fold.slot_index(score, record=record)
            if index is None:
                raise ValueError(f"{score} is outside the band this record covers")
            slots[index] = slots[index].model_copy(
                update={column: getattr(slots[index], column) + count}
            )
    return record.model_copy(update={"slots": tuple(slots), "folded_dates": dates})


def a_written_row(
    *,
    date: str,
    proposed: float | None = None,
    daily_shift: float | None = None,
    previous: float = 0.94,
    applied: float | None = None,
) -> FittedSimilarityThreshold:
    """One row as the ledger holds it. `proposed` absent is a held day."""
    settled_at = previous if proposed is None else proposed
    return FittedSimilarityThreshold(
        version=FittedSimilarityThreshold.schema_version(),
        date=date,
        run_id=f"{date}-1",
        record_stamp="c" * 64,
        previous=previous,
        proposed=proposed,
        after_damping=proposed,
        applied=settled_at if applied is None else applied,
        clamp_kind=ClampKind.NONE,
        clamp_movement=0.0,
        held_reason=HeldReason.NONE if proposed is not None else HeldReason.SHEET_TOO_SMALL,
        daily_shift=daily_shift,
        discard_share=KNOBS.discard_share,
        smoothing_weight=KNOBS.smoothing_weight,
        max_down_step=KNOBS.max_down_step,
        step_change_multiple=KNOBS.step_change_multiple,
        pairs_in_band=0,
        pairs_judged=0,
        pairs_usable=0,
        disagreement_rate=0.0,
        unclear_rate=0.0,
        negatives_on_record=0,
        above_line_on_record=0,
        days_on_record=0,
        merge_count=0,
        scorer_model="all-minilm-l6-v2-quantized",
        cosine_weight=1.0,
        key_point_weight=0.0,
    )


# --- step 1: the walk ---------------------------------------------------------


def test_the_line_is_the_upper_edge_of_the_slot_the_walk_stopped_in() -> None:
    """The walk stops past the discarded share, and reports the slot's TOP edge.

    100 negatives sets one pair aside. The single NO at 0.970 is that one, so the
    walk carries on into 0.950 where the other 99 sit, and the line comes back at
    0.951 rather than at 0.950.
    """
    record = a_record(negatives={0.970: 1, 0.950: 99})

    assert fit.fit_line(record, discard_share=KNOBS.discard_share) == pytest.approx(0.951)


def test_a_pair_scoring_the_line_merges_so_the_line_is_the_slots_upper_edge() -> None:
    """The `+ bin_width` is load-bearing, and this is the comparison that makes it so.

    `assemble` refuses a pair on `score < floor_min`, so a pair scoring EXACTLY
    the line still merges - the first assertion pins that operator on the real
    grouping pass rather than on a reading of it. Every NO the walk stopped at
    scores at or above its slot's lower edge and below the next one, so a line at
    the lower edge would merge the very pairs the walk stopped for. The second
    assertion is that the fitted line clears all of them.
    """
    both = ["world-01", "world-02"]
    grouped = assemble.collapse_same_story(
        [item(one, source=one) for one in both],
        block({one: unit(0.0) for one in both}),
        same_story=at(1.0),
    )
    assert [one.same_story_as for one in grouped].count(both[0]) == 1, (
        "two identical vectors score exactly 1.0, and a pair scoring the line merges"
    )

    line = fit.fit_line(a_record(negatives={0.950: 99}), discard_share=KNOBS.discard_share)
    assert line is not None
    assert line > 0.950 + KNOBS.bin_width - 1e-9, "the line is above every NO in that slot"


def test_one_stray_verdict_at_the_top_cannot_set_the_line() -> None:
    """A single NO at 0.99 would pin the line at 0.991 for ever if nothing discarded.

    200 negatives sets two aside, and the stray is one of them, so the line lands
    on the body of the evidence instead of on the outlier.
    """
    record = a_record(negatives={0.990: 1, 0.930: 200})

    assert fit.fit_line(record, discard_share=KNOBS.discard_share) == pytest.approx(0.931)


def test_the_discard_needs_enough_negatives_to_discard_anything() -> None:
    """One percent of 50 is nothing, so the walk stops at the highest NO on record.

    This is what `minimum_negatives` waits for: below 200 the discard sets aside
    fewer than two pairs, which is the same as setting aside none, and the line
    would be whatever the single highest verdict said.
    """
    record = a_record(negatives={0.990: 1, 0.930: 49})

    assert fit.fit_line(record, discard_share=KNOBS.discard_share) == pytest.approx(0.991)


def test_a_record_with_nothing_to_walk_reports_no_line() -> None:
    """An empty walk has no answer, and a number would read as one somebody took."""
    assert fit.fit_line(a_record(positives={0.950: 40}), discard_share=0.01) is None


# --- step 2: the damping ------------------------------------------------------


def test_a_rise_is_taken_whole() -> None:
    """Raising the line removes wrong merges, so the safe move arrives today."""
    assert fit.damp(0.95, 0.94, smoothing_weight=0.15) == pytest.approx(0.95)


def test_a_fall_is_damped() -> None:
    """Lowering the line admits merges, so it arrives over a week."""
    assert fit.damp(0.90, 0.94, smoothing_weight=0.15) == pytest.approx(0.934)


# --- step 3: the clamps -------------------------------------------------------


def test_the_downward_step_is_capped_at_the_knob() -> None:
    """A fall of 0.04 lands as a fall of 0.005, and the row says how much was held."""
    shaped = fit.clamp(0.90, 0.94, max_down_step=0.005)

    assert shaped.applied == pytest.approx(0.935)
    assert shaped.movement == pytest.approx(0.035)


def test_a_fall_inside_the_daily_step_is_not_clamped_at_all() -> None:
    """Nothing was held back, so `movement` is zero rather than a small number."""
    shaped = fit.clamp(0.9375, 0.94, max_down_step=0.005)

    assert shaped.applied == pytest.approx(0.9375)
    assert shaped.kind is ClampKind.NONE
    assert shaped.movement == 0.0


def test_the_row_says_which_clamp_fired() -> None:
    """A word, never a bool: the daily step and the guard are two different answers.

    The step lets a shaped fall through and the guard refuses the move outright,
    so a reader of a row that fell 0.005 has to be able to tell the two apart.
    """
    stepped = fit.clamp(0.90, 0.94, max_down_step=0.005)
    guarded = fit.held_at(0.94, 0.90)

    assert stepped.kind is ClampKind.STEP
    assert guarded.kind is ClampKind.GUARD
    assert guarded.applied == pytest.approx(0.94), "the guard holds the line where it was"


# --- the gates ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "negatives", "above_line", "days", "disagreement", "unclear", "fold_held"),
    [
        (HeldReason.SHEET_TOO_SMALL, 10, 100, 100, 0.0, 0.0, None),
        (HeldReason.SHEET_TOO_SMALL, 400, 1, 100, 0.0, 0.0, None),
        (HeldReason.SHEET_TOO_SMALL, 400, 100, 2, 0.0, 0.0, None),
        (HeldReason.JUDGE_UNSTABLE, 400, 100, 100, 0.9, 0.0, None),
        (HeldReason.JUDGE_UNCERTAIN, 400, 100, 100, 0.0, 0.9, None),
        (HeldReason.LEGS_MISSING, 400, 100, 100, 0.0, 0.0, HeldReason.LEGS_MISSING),
        (HeldReason.INPUTS_CHANGED, 400, 100, 100, 0.0, 0.0, HeldReason.INPUTS_CHANGED),
    ],
)
def test_each_gate_writes_its_own_reason_and_moves_nothing(
    reason: HeldReason,
    negatives: int,
    above_line: int,
    days: int,
    disagreement: float,
    unclear: float,
    fold_held: HeldReason | None,
) -> None:
    """One record per gate, each asked for the word it is supposed to say.

    A held day that said only "held" would leave an operator reading counts to
    work out which of five things went wrong.
    """
    record = a_record(negatives={0.930: negatives})

    assert (
        fit.gates(
            record,
            knobs=KNOBS,
            above_line=above_line,
            days=days,
            disagreement_rate=disagreement,
            unclear_rate=unclear,
            fold_held=fold_held,
        )
        is reason
    )


def test_a_record_that_clears_every_gate_holds_nothing() -> None:
    """The gates are what stop a fit, so a record past all of them returns nothing."""
    assert (
        fit.gates(
            a_record(negatives={0.930: 400}),
            knobs=KNOBS,
            above_line=100,
            days=100,
            disagreement_rate=0.0,
            unclear_rate=0.0,
        )
        is None
    )


# --- the step-change guard ----------------------------------------------------


def _days_back(count: int) -> list[str]:
    end = date_type.fromisoformat(DATE)
    return [(end - timedelta(days=offset)).isoformat() for offset in reversed(range(count))]


def test_the_guard_is_recorded_and_not_enforced_below_fourteen_rows() -> None:
    """Thirteen rows is not a median anybody should hold a line on.

    The stage still writes `daily_shift` on every one of those rows, which is what
    turns the estimated multiple of 5 into a measurement.
    """
    rows = [
        a_written_row(date=day, daily_shift=0.002) for day in _days_back(13)
    ]

    assert fit.typical_shift(rows, window_rows=KNOBS.step_change_window_rows) is None


def test_a_missed_run_does_not_disarm_the_guard() -> None:
    """Fourteen rows spread over twenty days is still fourteen rows.

    The bite: the window the fit asks for is `step_change_window_rows * 2` days,
    and a fourteen-day cover over this same evidence finds twelve rows and returns
    nothing - a guard that silently never fires. The second assertion is that same
    evidence read through the narrower cover.
    """
    spread = [day for index, day in enumerate(_days_back(20)) if index % 10 != 3][:14]
    rows = [a_written_row(date=day, daily_shift=0.002) for day in spread]

    assert fit.typical_shift(rows, window_rows=14) == pytest.approx(0.002)

    fourteen_day_cover = set(_days_back(15))
    narrowed = [row for row in rows if row.date in fourteen_day_cover]
    assert len(narrowed) < 14
    assert fit.typical_shift(narrowed, window_rows=14) is None


def test_a_record_with_no_negatives_gives_no_daily_shift() -> None:
    """A subtraction missing one of its two numbers is not a zero.

    A 0.0 in this column would read as "today moved the answer not at all", which
    is a measurement nobody took.
    """
    record = a_record(positives={0.950: 40}, dates=(DATE,))
    counts = {index: fold.SlotCounts(same=1) for index in (70,)}

    assert fit.daily_shift(record, counts, discard_share=KNOBS.discard_share) is None


def test_todays_own_evidence_is_what_the_daily_shift_measures() -> None:
    """The fit with today against the fit without it, and nothing else.

    With today the record holds 100 negatives, one is set aside, and the two at
    0.960 carry the walk past it - so the line is 0.961. Take today back out and
    98 are left, the discard sets aside none, and the walk runs all the way down
    to 0.930. Today moved the answer three hundredths on its own.
    """
    record = a_record(negatives={0.960: 2, 0.930: 98})
    today = {fold.slot_index(0.960, record=record) or 0: fold.SlotCounts(different=2)}

    shift = fit.daily_shift(record, today, discard_share=KNOBS.discard_share)

    assert shift == pytest.approx(0.030)


def test_subtracting_a_day_the_record_never_counted_is_refused() -> None:
    """A negative count lowers the walk's total and moves the line with nothing saying so."""
    record = a_record(negatives={0.930: 2})
    too_many = {fold.slot_index(0.930, record=record) or 0: fold.SlotCounts(different=5)}

    with pytest.raises(ValueError, match="does not hold the day being subtracted"):
        fit.without(record, too_many)


# --- step 4: settling ---------------------------------------------------------


def test_a_week_that_proposed_the_same_line_is_settled() -> None:
    """Compared against the proposal, never the applied value.

    The damping and the clamps are what make two applied values agree, so asking
    whether the applied number stopped moving asks the smoothing whether the
    smoothing worked.
    """
    rows = [a_written_row(date=day, proposed=0.9405) for day in _days_back(10)]

    assert fit.settled(
        rows, proposed=0.9410, date=DATE, window_days=7, delta=KNOBS.settled_delta
    )


def test_a_week_that_is_still_moving_is_not_settled() -> None:
    rows = [a_written_row(date=day, proposed=0.930) for day in _days_back(10)]

    assert not fit.settled(
        rows, proposed=0.941, date=DATE, window_days=7, delta=KNOBS.settled_delta
    )


def test_a_week_that_has_not_happened_yet_has_settled_nothing() -> None:
    rows = [a_written_row(date=day, proposed=0.9405) for day in _days_back(3)]

    assert not fit.settled(
        rows, proposed=0.9405, date=DATE, window_days=7, delta=KNOBS.settled_delta
    )


# --- the stage ----------------------------------------------------------------


def a_published_day(root: Path, *, date: str = DATE) -> None:
    """One day on disk with its manifest, reusing the grouping test's own builders."""
    items = [
        item("world-01", source="wire", outlet="The Wire"),
        item("world-02", source="paper", outlet="The Paper"),
        item("world-03", source="herald", outlet="The Herald"),
    ]
    manifest = RunManifest.from_json(read_text(MANIFEST_FIXTURE))
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=date,
        generated_at=f"{date}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[
            DigestRunRef(
                n=run.n,
                at=run.started_at,
                items_added=sum(1 for one in items if one.introduced_by_run == run.n),
            )
            for run in manifest.runs
        ],
        verticals=[
            DigestVerticalRef(id=name, display_name=name.title(), count=count)
            for name, count in sorted(Counter(one.vertical for one in items).items())
        ],
        items=items,
        embeddings=block({one.item_id: unit(index * 12.0) for index, one in enumerate(items)}),
    )
    target = assemble.day_dir(root, date)
    assemble.write_atomic(target / "digest.json", day.to_json())
    assemble.write_atomic(target / "run.json", manifest.to_json())


def test_a_row_is_written_on_a_day_nothing_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A line that moves itself has to leave a record on the days it stayed put.

    An empty state tree is the most held day there is: no record, no verdicts, no
    fold. The row still lands, it carries the committed floor on both sides, and
    it says which gate refused - which is what a reader needs to tell this from a
    day the job never ran.
    """
    digest_root = tmp_path / "digest"
    a_published_day(digest_root)
    monkeypatch.setattr(common, "PUBLIC_ROOT", digest_root)
    state = tmp_path / "state"
    settings = config.load(config.REPO_ROOT / "config")

    row = stage_judge_fit(DATE, settings=settings, state_dir=state, digest_root=digest_root)

    assert row is not None
    assert row.held_reason is HeldReason.LEGS_MISSING, "the record never counted this date"
    assert row.applied == pytest.approx(settings.app.assemble.same_story.floor_min)
    assert row.applied == pytest.approx(row.previous), "a held day moves the line nowhere"
    assert row.proposed is None and row.after_damping is None

    written = ledger.load_fitted_thresholds(state, today=DATE, within_days=1)
    assert [one.date for one in written] == [DATE], "the row survives the CSV round trip"
    assert written[0].held_reason is HeldReason.LEGS_MISSING


def test_a_day_that_never_published_is_not_a_run_to_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No run to file a row under and no merges to count is a day that did not happen."""
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "digest")

    assert (
        stage_judge_fit(
            DATE,
            settings=config.load(config.REPO_ROOT / "config"),
            state_dir=tmp_path / "state",
            digest_root=tmp_path / "digest",
        )
        is None
    )


def test_a_story_naming_itself_is_not_a_group(tmp_path: Path) -> None:
    """The count on the row and the count the console draws read the same items."""
    digest_root = tmp_path / "digest"
    a_published_day(digest_root)

    day = _load_day(assemble.day_dir(digest_root, DATE) / "digest.json")
    assert day is not None

    assert merge_count(day) == 0, "nothing in this day was grouped behind anything"


# --- the four steps in sequence -----------------------------------------------


def test_a_fortnight_of_built_days_converges() -> None:
    """Fourteen identical days folded in sequence, and the answer stops moving.

    The evidence is the same shape every day on purpose: this asks whether the
    four steps settle on a stationary input, which is the only case where a
    failure to settle is the steps' own fault rather than the news moving.

    The gates hold the first nine days - `minimum_days` is 10 - so the line sits
    at the committed floor until the record is old enough, then rises once and
    stays. Every one of the last three moves is below `settled_delta`.
    """
    record = fold.empty_record(KNOBS, scorer=a_scorer(), judge=a_judge())
    a_day = {0.900: 20, 0.910: 20, 0.920: 20, 0.930: 20, 0.940: 20}
    previous = 0.94
    applied: list[float] = []

    for date in _days_back(14):
        counts = {
            fold.slot_index(score, record=record) or 0: fold.SlotCounts(different=count)
            for score, count in a_day.items()
        }
        record = record.model_copy(
            update={
                "folded_dates": tuple(sorted((*record.folded_dates, date))),
                "slots": tuple(
                    slot.model_copy(
                        update={"different_count": slot.different_count + counts[index].different}
                    )
                    if index in counts
                    else slot
                    for index, slot in enumerate(record.slots)
                ),
            }
        )
        held = fit.gates(
            record,
            knobs=KNOBS,
            above_line=fit.judged_at_or_above(record, previous),
            days=len(record.folded_dates),
            disagreement_rate=0.0,
            unclear_rate=0.0,
        )
        proposal = fit.fit_line(record, discard_share=KNOBS.discard_share)
        if held is None and proposal is not None:
            after = fit.damp(proposal, previous, smoothing_weight=KNOBS.smoothing_weight)
            previous = fit.clamp(after, previous, max_down_step=KNOBS.max_down_step).applied
        applied.append(previous)

    moves = [abs(applied[index] - applied[index - 1]) for index in range(1, len(applied))]
    assert all(move < KNOBS.settled_delta for move in moves[-3:]), (
        f"the last three moves were {moves[-3:]}"
    )
    assert applied[-1] > 0.94, "the record did move the line off the committed floor"
