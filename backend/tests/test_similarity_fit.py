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
from test_similarity_selection import MANIFEST_FIXTURE

from idhazh import assemble, cli, config, ledger
from idhazh.contracts.digest_day import DigestDay, DigestRunRef, DigestVerticalRef
from idhazh.contracts.fitted_similarity_threshold import (
    ClampKind,
    FittedSimilarityThreshold,
    HeldReason,
)
from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.council.run_identity import council_run_id
from idhazh.similarity import counting, fit
from idhazh.similarity.stamps import JudgeStamp, ScorerStamp
from idhazh.stages import common
from idhazh.stages.common import _load_day
from idhazh.stages.set_merge_line import merge_count, stage_set_merge_line

DATE: Final = "2026-09-18"

#: The day the council runs, which is the day AFTER the one it judges. Spelled
#: here so the gap between the two is visible in every assertion below: a run id
#: prefixed with the judged date would publish a standing lag nothing waited.
COUNCIL_DAY: Final = "2026-09-19"

#: What the platform called the run. A run id and never a run number: the number
#: starts again in the next workflow.
PLATFORM_RUN: Final = "35534060762"

#: What the council calls itself on the night it judges `DATE`.
COUNCIL_RUN: Final = f"{COUNCIL_DAY}-{PLATFORM_RUN}"

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
        judge_model="qwen3-5-9b-q4-k-m",
        prompt_digest="a" * 64,
        grammar_digest="b" * 64,
        judge_temperature=0.0,
        decode_digest="c" * 64,
        thinks=False,
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
    record = counting.empty_record(knobs, scorer=a_scorer(), judge=a_judge())
    slots = list(record.slots)
    for column, counts in (
        ("same_count", positives or {}),
        ("different_count", negatives or {}),
        ("unclear_count", unclear or {}),
    ):
        for score, count in counts.items():
            index = counting.slot_index(score, record=record)
            if index is None:
                raise ValueError(f"{score} is outside the band this record covers")
            slots[index] = slots[index].model_copy(
                update={column: getattr(slots[index], column) + count}
            )
    return record.model_copy(update={"slots": tuple(slots), "counted_dates": dates})


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
        fall_weight=KNOBS.fall_weight,
        rise_weight=KNOBS.rise_weight,
        max_down_step=KNOBS.max_down_step,
        max_up_step=KNOBS.max_up_step,
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

    100 negatives sets three pairs aside. The single NO at 0.970 is inside that
    set-aside, so the walk carries on into 0.950 where the other 99 sit, and the
    line comes back at 0.951 rather than at 0.950.
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


def test_one_bad_night_at_the_top_cannot_set_the_line() -> None:
    """The share has to absorb a CLUSTER of wrong NO verdicts, not one stray.

    A judge that misreads one news cluster produces a block of wrong verdicts on
    one night, not independent ones: in the 200 labelled pairs of 2026-09-19 all
    four two-story marks came from a single cluster. Four NO verdicts at 0.99
    would pin the line at 0.991 for ever if the share did not reach past them.
    At 204 negatives, 0.03 sets six aside and the block is inside it; 0.01 sets
    two aside and the block sets the line.
    """
    record = a_record(negatives={0.990: 4, 0.930: 200})

    assert fit.fit_line(record, discard_share=KNOBS.discard_share) == pytest.approx(0.931)
    assert fit.fit_line(record, discard_share=0.01) == pytest.approx(0.991), (
        "one percent sets two aside, which one bad night walks straight past"
    )


def test_the_discard_needs_enough_negatives_to_absorb_a_bad_night() -> None:
    """Three percent of 100 sets three aside, and a four-verdict cluster beats it.

    This is what `minimum_negatives` waits for. The same record at 200 negatives
    sets six aside and the cluster is absorbed, so the gate is not a round number
    somebody liked - it is where the share first covers one bad night.
    """
    too_few = a_record(negatives={0.990: 4, 0.930: 96})
    enough = a_record(negatives={0.990: 4, 0.930: 196})

    assert fit.fit_line(too_few, discard_share=KNOBS.discard_share) == pytest.approx(0.991)
    assert fit.fit_line(enough, discard_share=KNOBS.discard_share) == pytest.approx(0.931)


def test_a_record_with_nothing_to_walk_reports_no_line() -> None:
    """An empty walk has no answer, and a number would read as one somebody took."""
    assert (
        fit.fit_line(a_record(positives={0.950: 40}), discard_share=KNOBS.discard_share)
        is None
    )


# --- step 2: the dead zone ----------------------------------------------------


def test_a_proposal_inside_one_slot_of_the_line_is_not_a_move() -> None:
    """The line is a slot's upper edge, so half a slot lands on no edge at all.

    Without this the damping leaves a geometric tail whose steps shrink below one
    slot for ever, and the applied line never formally arrives at its proposal.
    """
    assert not fit.is_a_move(0.9395, 0.94, dead_zone=KNOBS.dead_zone)
    assert not fit.is_a_move(0.9405, 0.94, dead_zone=KNOBS.dead_zone)
    assert fit.is_a_move(0.939, 0.94, dead_zone=KNOBS.dead_zone)
    assert fit.is_a_move(0.941, 0.94, dead_zone=KNOBS.dead_zone)


# --- step 3: the damping ------------------------------------------------------


def test_a_fall_is_the_fast_direction() -> None:
    """Lowering the line publishes less, which is the house rule, so half lands today."""
    landed = fit.damp(0.90, 0.94, fall_weight=0.5, rise_weight=0.15)

    assert landed == pytest.approx(0.92)


def test_a_rise_is_the_slow_direction() -> None:
    """Raising the line folds more stories together, so it arrives over weeks."""
    landed = fit.damp(0.95, 0.94, fall_weight=0.5, rise_weight=0.15)

    assert landed == pytest.approx(0.9415)


def test_the_fast_direction_is_still_damped() -> None:
    """A fall does not land whole, and this is the assertion that says so.

    One judge misreading one news cluster produces a block of adjacent wrong
    verdicts on a single night. Undamped, the line takes that whole block at
    once; the step-change guard ships off, so the damping is the only filter
    between a one-day spike and the published line.
    """
    landed = fit.damp(0.90, 0.94, fall_weight=KNOBS.fall_weight, rise_weight=KNOBS.rise_weight)

    assert landed > 0.90, "an undamped fall would land the whole proposal"


# --- step 4: the clamps -------------------------------------------------------


def a_clamp(after_damping: float, previous: float, **over: float) -> fit.Clamped:
    """`fit.clamp` under the committed knobs, with any of them overridden by name."""
    caps: dict[str, float] = {
        "max_down_step": KNOBS.max_down_step,
        "max_up_step": KNOBS.max_up_step,
        "band_low": KNOBS.band_low,
        "band_high": KNOBS.band_high,
    }
    caps.update(over)
    return fit.clamp(after_damping, previous, **caps)


def test_the_downward_step_is_capped_at_the_knob() -> None:
    """A fall of 0.04 lands as a fall of 0.010, and the row says how much was held."""
    shaped = a_clamp(0.90, 0.94)

    assert shaped.applied == pytest.approx(0.93)
    assert shaped.movement == pytest.approx(0.03)


def test_the_upward_step_is_capped_tighter_than_the_downward_one() -> None:
    """Both directions are capped, and the rise cap is the smaller of the two.

    Ten slots down against three up is the whole asymmetry in one comparison. A
    reader who makes these equal has reversed the house rule.
    """
    fell = a_clamp(0.80, 0.94)
    rose = a_clamp(0.99, 0.94)

    assert 0.94 - fell.applied == pytest.approx(KNOBS.max_down_step)
    assert rose.applied - 0.94 == pytest.approx(KNOBS.max_up_step)
    assert 0.94 - fell.applied > rose.applied - 0.94


def test_a_move_inside_the_daily_cap_is_not_clamped_at_all() -> None:
    """Nothing was held back, so `movement` is zero rather than a small number."""
    shaped = a_clamp(0.935, 0.94)

    assert shaped.applied == pytest.approx(0.935)
    assert shaped.kind is ClampKind.NONE
    assert shaped.movement == 0.0


def test_the_row_says_which_clamp_fired() -> None:
    """A word, never a bool: the daily cap and the guard are two different answers.

    The cap lets a shaped move through and the guard refuses the move outright,
    so a reader of a row that fell 0.010 has to be able to tell the two apart.
    """
    stepped = a_clamp(0.90, 0.94)
    guarded = fit.held_at(0.94, 0.90)

    assert stepped.kind is ClampKind.STEP
    assert guarded.kind is ClampKind.GUARD
    assert guarded.applied == pytest.approx(0.94), "the guard holds the line where it was"


def test_a_line_resting_on_a_band_wall_is_its_own_word() -> None:
    """A line at the top of the band folds nothing, which is not the same as silence.

    From the outside a line at `band_high` looks like the feature is switched off
    rather than pinned, so it gets a word of its own - and it gets it whether or
    not the wall moved it that day, because resting there is the state worth
    reporting. The floor is the same answer at the other end.
    """
    pushed = a_clamp(1.05, 0.999)
    resting = a_clamp(1.0, 1.0)
    bottomed = a_clamp(0.80, 0.885)

    assert pushed.kind is ClampKind.CEILING
    assert pushed.applied == pytest.approx(KNOBS.band_high)
    assert resting.kind is ClampKind.CEILING, "resting on the wall is the reported state"
    assert resting.movement == 0.0, "nothing moved it, so nothing was held back"
    assert bottomed.kind is ClampKind.FLOOR
    assert bottomed.applied == pytest.approx(KNOBS.band_low)


def test_the_applied_line_can_never_leave_the_band() -> None:
    """Whatever the record says, the line stays where a later walk can propose it again.

    The record holds slots only between `band_low` and `band_high`. A line
    outside them is a line no fit can read back, so the walls bind after the
    daily caps rather than before them. Driven from both ends: a record that
    agrees about everything and one that disagrees about everything.
    """
    all_agree = a_record(negatives={0.999: 300})
    all_disagree = a_record(negatives={0.881: 300})
    top = fit.fit_line(all_agree, discard_share=KNOBS.discard_share)
    bottom = fit.fit_line(all_disagree, discard_share=KNOBS.discard_share)
    assert top is not None and bottom is not None

    for proposal in (top, bottom, 1.5, -0.5):
        previous = KNOBS.band_low
        for _ in range(400):
            after = (
                fit.damp(
                    proposal,
                    previous,
                    fall_weight=KNOBS.fall_weight,
                    rise_weight=KNOBS.rise_weight,
                )
                if fit.is_a_move(proposal, previous, dead_zone=KNOBS.dead_zone)
                else previous
            )
            previous = a_clamp(after, previous).applied
            assert KNOBS.band_low <= previous <= KNOBS.band_high, (
                f"a proposal of {proposal} walked the line to {previous}"
            )


# --- the gates ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "negatives", "above_line", "days", "disagreement", "unclear", "collect_held"),
    [
        (HeldReason.SHEET_TOO_SMALL, 10, 100, 100, 0.0, 0.0, None),
        (HeldReason.SHEET_TOO_SMALL, 400, 1, 100, 0.0, 0.0, None),
        (HeldReason.SHEET_TOO_SMALL, 400, 100, 2, 0.0, 0.0, None),
        (HeldReason.JUDGE_UNSTABLE, 400, 100, 100, 0.9, 0.0, None),
        (HeldReason.JUDGE_UNCERTAIN, 400, 100, 100, 0.0, 0.9, None),
        (HeldReason.SHARDS_MISSING, 400, 100, 100, 0.0, 0.0, HeldReason.SHARDS_MISSING),
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
    collect_held: HeldReason | None,
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
            collect_held=collect_held,
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
    counts = {index: counting.SlotCounts(same=1) for index in (70,)}

    assert fit.daily_shift(record, counts, discard_share=KNOBS.discard_share) is None


def test_todays_own_evidence_is_what_the_daily_shift_measures() -> None:
    """The fit with today against the fit without it, and nothing else.

    With today the record holds 105 negatives, three are set aside, and the five
    at 0.960 carry the walk past them - so the line is 0.961. Take today back out
    and 100 are left, all at 0.930, and the walk runs all the way down to 0.931.
    Today moved the answer three hundredths on its own.
    """
    record = a_record(negatives={0.960: 5, 0.930: 100})
    today = {counting.slot_index(0.960, record=record) or 0: counting.SlotCounts(different=5)}

    shift = fit.daily_shift(record, today, discard_share=KNOBS.discard_share)

    assert shift == pytest.approx(0.030)


def test_subtracting_a_day_the_record_never_counted_is_refused() -> None:
    """A negative count lowers the walk's total and moves the line with nothing saying so."""
    record = a_record(negatives={0.930: 2})
    too_many = {counting.slot_index(0.930, record=record) or 0: counting.SlotCounts(different=5)}

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
    day counted. The row still lands, it carries the committed floor on both sides,
    and it says which gate refused - which is what a reader needs to tell this from
    a day the job never ran.
    """
    digest_root = tmp_path / "digest"
    a_published_day(digest_root)
    monkeypatch.setattr(common, "PUBLIC_ROOT", digest_root)
    state = tmp_path / "state"
    settings = config.load(config.REPO_ROOT / "config")

    row = stage_set_merge_line(
        DATE, run_id=COUNCIL_RUN, settings=settings, state_dir=state, digest_root=digest_root
    )

    assert row is not None
    assert row.run_id == COUNCIL_RUN, "the run that fitted the line is the council night"
    assert row.held_reason is HeldReason.SHARDS_MISSING, "the record never counted this date"
    assert row.applied == pytest.approx(settings.app.assemble.same_story.floor_min)
    assert row.applied == pytest.approx(row.previous), "a held day moves the line nowhere"
    assert row.proposed is None and row.after_damping is None

    written = ledger.load_fitted_thresholds(state, today=DATE, within_days=1)
    assert [one.date for one in written] == [DATE], "the row survives the CSV round trip"
    assert written[0].held_reason is HeldReason.SHARDS_MISSING


def test_a_day_that_never_published_is_not_a_run_to_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No merges to count is a day that did not happen."""
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "digest")

    assert (
        stage_set_merge_line(
            DATE,
            run_id=COUNCIL_RUN,
            settings=config.load(config.REPO_ROOT / "config"),
            state_dir=tmp_path / "state",
            digest_root=tmp_path / "digest",
        )
        is None
    )


def test_the_row_is_written_from_a_date_and_a_run_id_the_council_minted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The two things the stage is handed are the day it judges and the name the council minted.

    The published day's run manifest is removed, so there is no digest run on
    disk to borrow a name from and nothing to read an ordinal out of. The row
    still lands, and it lands under the council's own name - which the contract
    validated on the way into the file, so a name `RunId` refuses never reaches
    the store.

    Before the council minted its own, this stage read the manifest for the one
    string it wanted and returned `None` without it, so this day fitted nothing.
    """
    digest_root = tmp_path / "digest"
    a_published_day(digest_root)
    (assemble.day_dir(digest_root, DATE) / "run.json").unlink()
    monkeypatch.setattr(common, "PUBLIC_ROOT", digest_root)
    state = tmp_path / "state"
    minted = council_run_id(opened_on=COUNCIL_DAY, platform_run_id=PLATFORM_RUN)

    stage_set_merge_line(
        DATE,
        run_id=minted,
        settings=config.load(config.REPO_ROOT / "config"),
        state_dir=state,
        digest_root=digest_root,
    )

    written = ledger.load_fitted_thresholds(state, today=DATE, within_days=1)
    assert [one.run_id for one in written] == [minted]


def test_a_council_verb_refuses_to_invent_a_run_it_was_not_given() -> None:
    """A verb with no name to file under stops at the command line, not two hours in.

    Every value it could reach for belongs to somebody else, so the refusal is
    the whole of the design: a digest run's id claims a machine and a clock this
    night never drew.
    """
    with pytest.raises(SystemExit) as refused:
        cli.main(["council-settle", "--date", DATE])

    assert refused.value.code == 2, "argparse refuses a bad command line with 2"


def test_a_story_naming_itself_is_not_a_group(tmp_path: Path) -> None:
    """The count on the row and the count the console draws read the same items."""
    digest_root = tmp_path / "digest"
    a_published_day(digest_root)

    day = _load_day(assemble.day_dir(digest_root, DATE) / "digest.json")
    assert day is not None

    assert merge_count(day) == 0, "nothing in this day was grouped behind anything"


# --- the five steps in sequence -----------------------------------------------


def test_a_fortnight_of_built_days_converges() -> None:
    """Fourteen identical days counted in sequence, and the answer stops moving.

    The evidence is the same shape every day on purpose: this asks whether the
    five steps settle on a stationary input, which is the only case where a
    failure to settle is the steps' own fault rather than the news moving.

    The gates hold the first nine days - `minimum_days` is 10 - so the line sits
    at the committed floor until the record is old enough, then rises once and
    stays: the next day's proposal is inside the dead zone and is not a move.
    Every one of the last three moves is below `settled_delta`.
    """
    record = counting.empty_record(KNOBS, scorer=a_scorer(), judge=a_judge())
    a_day = {0.900: 20, 0.910: 20, 0.920: 20, 0.930: 20, 0.940: 20}
    previous = 0.94
    applied: list[float] = []

    for date in _days_back(14):
        counts = {
            counting.slot_index(score, record=record) or 0: counting.SlotCounts(different=count)
            for score, count in a_day.items()
        }
        record = record.model_copy(
            update={
                "counted_dates": tuple(sorted((*record.counted_dates, date))),
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
            days=len(record.counted_dates),
            disagreement_rate=0.0,
            unclear_rate=0.0,
        )
        proposal = fit.fit_line(record, discard_share=KNOBS.discard_share)
        if held is None and proposal is not None:
            after = (
                fit.damp(
                    proposal,
                    previous,
                    fall_weight=KNOBS.fall_weight,
                    rise_weight=KNOBS.rise_weight,
                )
                if fit.is_a_move(proposal, previous, dead_zone=KNOBS.dead_zone)
                else previous
            )
            previous = fit.clamp(
                after,
                previous,
                max_down_step=KNOBS.max_down_step,
                max_up_step=KNOBS.max_up_step,
                band_low=KNOBS.band_low,
                band_high=KNOBS.band_high,
            ).applied
        applied.append(previous)

    moves = [abs(applied[index] - applied[index - 1]) for index in range(1, len(applied))]
    assert all(move < KNOBS.settled_delta for move in moves[-3:]), (
        f"the last three moves were {moves[-3:]}"
    )
    assert applied[-1] > 0.94, "the record did move the line off the committed floor"
