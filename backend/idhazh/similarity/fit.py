"""Where does the merge line go, given the record and the line that is applied now?

Pure arithmetic over a fixed record and a handful of written rows. Nothing here
opens a file, calls a model or looks at a clock - `idhazh.stages.judge_fit` does
the reading and the writing, and this module answers only the placement question.

Four steps, in this order and never another: walk the record to a proposal, damp
a fall towards yesterday, clamp what is left of the fall, and ask whether a week
of fresh evidence is still moving the answer. Each step is its own function so a
red test names the step that broke rather than the sequence.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from statistics import median

from idhazh.contracts.fitted_similarity_threshold import (
    ClampKind,
    FittedSimilarityThreshold,
    HeldReason,
)
from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.similarity.fold import SlotCounts


@dataclass(frozen=True, slots=True)
class Clamped:
    """What step 3 let through, which clamp shaped it, and how far it was held back."""

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


def damp(proposal: float, previous: float, *, smoothing_weight: float) -> float:
    """Step 2: a rise lands whole, a fall lands at `smoothing_weight` of the way.

    Damping is one-directional on purpose. Raising the line removes wrong merges
    and lowering it admits them, so the safe move arrives today and the risky one
    arrives over a week. Symmetric damping would make the safe move a week late
    for no gain.
    """
    if proposal >= previous:
        return proposal
    return previous + smoothing_weight * (proposal - previous)


def clamp(after_damping: float, previous: float, *, max_down_step: float) -> Clamped:
    """Step 3: the line may not fall further than `max_down_step` in one day.

    `movement` is how far the clamp held the line back, which is at or above zero
    because there is no upward clamp - a rise is never something this step has an
    opinion about.
    """
    lowest_today = previous - max_down_step
    if after_damping >= lowest_today:
        return Clamped(applied=after_damping, kind=ClampKind.NONE, movement=0.0)
    return Clamped(
        applied=lowest_today,
        kind=ClampKind.STEP,
        movement=lowest_today - after_damping,
    )


def held_at(previous: float, after_damping: float) -> Clamped:
    """The step-change guard firing: the line stays where it was for one more day.

    A separate answer from `clamp` rather than a fourth branch inside it. The
    daily clamp shapes a fall it still lets through; the guard refuses the whole
    move because one day's evidence disagreed with the fortnight before it, and
    a guard that let a fraction through would be a slower clamp rather than a
    hold.
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
