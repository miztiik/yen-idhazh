"""Where does the merge line go, given the record and the line that is applied now?

Pure arithmetic over a fixed record and a handful of written rows. Nothing here
opens a file, calls a model or looks at a clock - `idhazh.stages.judge_fit` does
the reading and the writing, and this module answers only the placement question.

Five steps, in this order and never another: walk the record to a proposal, ask
whether the proposal is far enough from today's line to be a move at all, damp
what is left towards yesterday, clamp it to the day's cap and to the band, and
ask whether a week of fresh evidence is still moving the answer. Each step is its
own function so a red test names the step that broke rather than the sequence.

The line falls fast and rises slow. Both directions are damped and both are
capped; what differs is the size of each. Lowering the line publishes less, and
publishing less is the house rule, so down is the quick direction. Anyone about
to make this symmetric should read the design rationale in
`docs/architecture/publishing/same-story.md` first.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from statistics import median

from idhazh.contracts.fitted_similarity_threshold import (
    LINE_TOLERANCE,
    ClampKind,
    FittedSimilarityThreshold,
    HeldReason,
)
from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.similarity.fold import SlotCounts


@dataclass(frozen=True, slots=True)
class Clamped:
    """What step 4 let through, what shaped it, and how far it was held back."""

    applied: float
    kind: ClampKind
    movement: float


def negatives_on(record: StorySimilarityDistribution) -> int:
    """Agreed NO readings across the whole record. The gate `minimum_negatives` reads."""
    return sum(slot.different_count for slot in record.slots)


def judged_at_or_above(record: StorySimilarityDistribution, line: float) -> int:
    """Every verdict the record holds in a slot at or above `line`.

    All three verdicts rather than the negatives alone: these are the pairs the
    day actually merged, so a YES here is the evidence that the merge was right
    and an UNCLEAR is a merge nobody could vouch for. The gate asks whether
    enough merges have been looked at, not whether enough of them were wrong.
    """
    return sum(
        slot.same_count + slot.different_count + slot.unclear_count
        for slot in record.slots
        if slot.bin_low >= line
    )


def fit_line(
    record: StorySimilarityDistribution, *, discard_share: float
) -> float | None:
    """Step 1: walk the record down from the top and stop past the discarded share.

    Returns the UPPER edge of the slot the walk stopped in, and the `+ bin_width`
    is load-bearing. `assemble.collapse_same_story` refuses a pair on
    `score < floor_min`, so a pair scoring exactly the line merges. Every pair
    inside the stopped slot scores at or above that slot's lower edge, so a line
    at the lower edge would merge the very pairs the walk stopped at.

    The share is taken as a count set aside once, `floor(total * discard_share)`,
    and the walk stops at the first slot whose running total EXCEEDS it. A
    decrementing budget lands on a different slot at the boundary, which is why
    the arithmetic is written this way round and not that one.

    `None` when the record holds no NO readings at all. A record with nothing to
    walk has no line to report, and a number returned from an empty walk would
    read as an answer somebody measured.
    """
    total = negatives_on(record)
    if total == 0:
        return None
    set_aside = math.floor(total * discard_share)
    seen = 0
    for slot in reversed(record.slots[1:]):
        seen += slot.different_count
        if seen > set_aside:
            return slot.bin_low + record.bin_width
    # The walk always stops somewhere: `discard_share` is below 0.5, so the whole
    # record exceeds what it sets aside, and the lowest slot is where that is true
    # at the latest. Written as the tail rather than as a branch inside the loop,
    # so there is no return the arithmetic cannot reach.
    return record.slots[0].bin_low + record.bin_width


def without(
    record: StorySimilarityDistribution, counts: Mapping[int, SlotCounts]
) -> StorySimilarityDistribution:
    """The record with one day's counts taken back out. Never written to disk.

    `daily_shift` is the only caller, and the question it asks is what today's
    evidence alone moved. Raises when a slot does not hold what is being
    subtracted: a negative count would lower the walk's total and move the line
    with nothing on the row able to say why.
    """
    slots = []
    for index, slot in enumerate(record.slots):
        taken = counts.get(index)
        if taken is None:
            slots.append(slot)
            continue
        left = (
            slot.same_count - taken.same,
            slot.different_count - taken.different,
            slot.unclear_count - taken.unclear,
        )
        if min(left) < 0:
            raise ValueError(
                f"slot {index} does not hold the day being subtracted: the record has "
                f"{slot.same_count}/{slot.different_count}/{slot.unclear_count} and the "
                f"day carries {taken.same}/{taken.different}/{taken.unclear} "
                "(same/different/unclear)"
            )
        slots.append(
            slot.model_copy(
                update={
                    "same_count": left[0],
                    "different_count": left[1],
                    "unclear_count": left[2],
                }
            )
        )
    return record.model_copy(update={"slots": tuple(slots)})


def is_a_move(proposal: float, previous: float, *, dead_zone: float) -> bool:
    """Step 2: is the proposal far enough from today's line to be worth applying?

    A proposal inside `dead_zone` of the applied line is not a move. The line is
    a slot's upper edge, so a step of less than one slot lands on no edge the
    next walk can produce - and without this the damping leaves a geometric tail
    whose steps shrink below one slot for ever, so the applied line never
    formally arrives at its proposal. The dead zone deletes that tail honestly.
    """
    return abs(proposal - previous) >= dead_zone


def damp(
    proposal: float, previous: float, *, fall_weight: float, rise_weight: float
) -> float:
    """Step 3: a fall lands at `fall_weight` of the way, a rise at `rise_weight`.

    Both directions are damped, and the weights are different on purpose.
    Lowering the line publishes less, which is the house rule, so a fall is the
    quick direction and a rise arrives over weeks.

    Damping stays on the quick direction rather than letting a fall land whole.
    One judge misreading one news cluster produces a block of adjacent wrong
    verdicts on a single night - in the 200 labelled pairs of 2026-09-19 all four
    two-story marks came from one cluster - and an undamped fall would take that
    whole block at once. Damping filters a one-day spike; a bare cap only slows
    it down and lets it persist.
    """
    if proposal < previous:
        return previous + fall_weight * (proposal - previous)
    return previous + rise_weight * (proposal - previous)


def clamp(
    after_damping: float,
    previous: float,
    *,
    max_down_step: float,
    max_up_step: float,
    band_low: float,
    band_high: float,
) -> Clamped:
    """Step 4: hold the move to the day's cap, and the result inside the band.

    Two caps rather than one, and the fall cap is the wider of the two. The
    step-change guard ships off, so the caps and the damping are the whole brake
    - an uncapped direction would have no bound a reader could state.

    The band walls bind after the caps. The record holds slots only between
    `band_low` and `band_high`, so a line outside them is a line the next walk
    cannot propose again. A line resting on a wall is reported as its own kind
    rather than as silence: at `band_high` the line folds nothing at all, which
    from the outside looks like the feature is switched off instead of pinned.

    `movement` is a distance, so it is at or above zero whichever wall moved the
    line and in whichever direction.
    """
    lowest_today = max(previous - max_down_step, band_low)
    highest_today = min(previous + max_up_step, band_high)
    applied = min(max(after_damping, lowest_today), highest_today)
    movement = abs(applied - after_damping)
    if applied >= band_high - LINE_TOLERANCE:
        return Clamped(applied=applied, kind=ClampKind.CEILING, movement=movement)
    if applied <= band_low + LINE_TOLERANCE:
        return Clamped(applied=applied, kind=ClampKind.FLOOR, movement=movement)
    if movement > LINE_TOLERANCE:
        return Clamped(applied=applied, kind=ClampKind.STEP, movement=movement)
    return Clamped(applied=applied, kind=ClampKind.NONE, movement=0.0)


def held_at(previous: float, after_damping: float) -> Clamped:
    """The step-change guard firing: the line stays where it was for one more day.

    A separate answer from `clamp` rather than another branch inside it. The
    daily caps shape a move they still let through; the guard refuses the whole
    move because one day's evidence disagreed with the fortnight before it, and
    a guard that let a fraction through would be a slower cap rather than a hold.
    """
    return Clamped(
        applied=previous, kind=ClampKind.GUARD, movement=abs(previous - after_damping)
    )


def daily_shift(
    record: StorySimilarityDistribution,
    counts: Mapping[int, SlotCounts],
    *,
    discard_share: float,
) -> float | None:
    """How far today's own evidence moved the answer: the fit with it against without.

    `None` whenever either walk has nothing to read. A subtraction missing one of
    its two numbers is not a zero, and a 0.0 on the row would read as "today moved
    the answer not at all" - a measurement nobody took.
    """
    with_today = fit_line(record, discard_share=discard_share)
    without_today = fit_line(without(record, counts), discard_share=discard_share)
    if with_today is None or without_today is None:
        return None
    return abs(with_today - without_today)


def typical_shift(
    rows: Sequence[FittedSimilarityThreshold], *, window_rows: int
) -> float | None:
    """The median daily shift over the newest `window_rows` rows that carry one.

    A median rather than a standard deviation, because the daily shift shrinks as
    one over the days on record and is nowhere near normally distributed - a
    sigma would be a ruler marked in the wrong units.

    `None` below `window_rows`, which is what keeps the guard unarmed while the
    record is still filling. A median over four rows fires on noise.

    Sorted by date, and the sort is stable, so two rows written on one date stay
    in the order the ledger appended them - which is the order they ran in.
    """
    shifts = [
        row.daily_shift
        for row in sorted(rows, key=lambda row: row.date)
        if row.daily_shift is not None
    ]
    if len(shifts) < window_rows:
        return None
    return median(shifts[-window_rows:])


def gates(
    record: StorySimilarityDistribution,
    *,
    knobs: SimilarityThresholdConfig,
    above_line: int,
    days: int,
    disagreement_rate: float,
    unclear_rate: float,
    fold_held: HeldReason | None = None,
) -> HeldReason | None:
    """The first gate that fails, or `None` when the fit may run.

    The order is fixed, so two runs over one held day name the same reason and an
    operator comparing two rows is comparing one answer. `fold_held` comes first
    because a record today was never counted into cannot be read for anything
    else. The sheet comes next: on a young record every other gate is being asked
    of a sample too small to answer it, and "the sheet is too small" is the useful
    sentence. The judge's own health comes last.
    """
    if fold_held is not None:
        return fold_held
    if (
        negatives_on(record) < knobs.minimum_negatives
        or above_line < knobs.minimum_above_line
        or days < knobs.minimum_days
    ):
        return HeldReason.SHEET_TOO_SMALL
    if disagreement_rate > knobs.disagreement_max:
        return HeldReason.JUDGE_UNSTABLE
    if unclear_rate > knobs.unclear_max:
        return HeldReason.JUDGE_UNCERTAIN
    return None


def settled(
    rows: Sequence[FittedSimilarityThreshold],
    *,
    proposed: float,
    date: str,
    window_days: int,
    delta: float,
) -> bool:
    """Step 4: whether the fit a week back proposed a line within `delta` of today's.

    Read off the newest row at or before the week-ago mark rather than the row on
    that exact day, so a missed run costs the comparison a little age instead of
    disarming it. `False` when no row that old carries a proposal: a week that
    has not happened yet has not settled anything.

    Compared against `proposed` rather than against `applied`, because the damping
    and the clamps are what make two applied values agree. Asking whether the
    smoothed number stopped moving asks the smoothing whether the smoothing
    worked.
    """
    mark = (date_type.fromisoformat(date) - timedelta(days=window_days)).isoformat()
    older = [
        (row.date, row.proposed)
        for row in rows
        if row.date <= mark and row.proposed is not None
    ]
    if not older:
        return False
    _, then = max(older)
    return abs(then - proposed) <= delta
