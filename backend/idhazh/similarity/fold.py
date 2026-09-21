"""How many YES and NO verdicts does each slot of the record hold, once today is added?

Pure arithmetic over a fixed row of slots. Nothing here opens a file, calls a
model or looks at a clock - `idhazh.stages.judge_fold` does the reading and the
writing, and this module answers only the counting question.

The record is the whole input to the fit, so it is rewritten whole and never
appended to. A day goes in once: `fold_day` refuses a date the record already
holds, which is what makes re-running a day free instead of damaging.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.story_similarity_distribution import (
    ScoreSlot,
    StorySimilarityDistribution,
)
from idhazh.contracts.story_similarity_pair import SameStoryVerdict, StorySimilarityPair
from idhazh.similarity.stamps import JudgeStamp, ScorerStamp

#: How far above a slot edge a score may sit, in slots, and still be that edge.
#: The record's own `GRID_TOLERANCE` is the same allowance on the score scale;
#: this one is applied to a quotient, which is where the error actually arrives.
SLOT_TOLERANCE: Final = 1e-9


@dataclass(frozen=True, slots=True)
class SlotCounts:
    """What one day put into one slot. Row 8 subtracts this to ask what today cost."""

    same: int = 0
    different: int = 0
    unclear: int = 0


def empty_record(
    knobs: SimilarityThresholdConfig, *, scorer: ScorerStamp, judge: JudgeStamp
) -> StorySimilarityDistribution:
    """A record of the configured band, every count zero and no date folded.

    The stamps are written in at birth rather than on the first fold, so a record
    that has counted nothing still says what it would have counted under.

    Built through `model_validate` because `JudgeStamp.judge_model` is a plain
    string: the stamp carries whatever `config/models/` names, and this is the
    place the contract checks it is an id the column can hold.
    """
    slots = round((knobs.band_high - knobs.band_low) / knobs.bin_width)
    return StorySimilarityDistribution.model_validate(
        {
            "version": StorySimilarityDistribution.schema_version(),
            "band_low": knobs.band_low,
            "band_high": knobs.band_high,
            "bin_width": knobs.bin_width,
            "scorer_model": scorer.scorer_model,
            "cosine_weight": scorer.cosine_weight,
            "key_point_weight": scorer.key_point_weight,
            "judge_model": judge.judge_model,
            "prompt_digest": judge.prompt_digest,
            "grammar_digest": judge.grammar_digest,
            "judge_temperature": judge.judge_temperature,
            "decode_digest": judge.decode_digest,
            "judge_thinks": judge.thinks,
            "folded_dates": (),
            "slots": tuple(
                ScoreSlot(bin_low=knobs.band_low + index * knobs.bin_width)
                for index in range(slots)
            ),
        }
    )


def slot_index(score: float, *, record: StorySimilarityDistribution) -> int | None:
    """Which slot a score falls in, or `None` when it is outside the band.

    A pair scoring a slot's lower edge lands in that slot and a pair scoring its
    upper edge lands in the next one, which is the rule `ScoreSlot.bin_low`
    states. `band_high` is the one exception: it has no next slot, so it lands in
    the last one rather than nowhere.

    The tolerance is what makes the first sentence true. `(0.950 - 0.88) / 0.001`
    is 69.99999999999995 in binary floating point, so an exact slot edge would
    otherwise file one slot low - and the fit reads the line off a slot edge, so
    that is a whole bin of error on the one number this feature sets. A billionth
    of a slot is far below any resolution a score is produced at.
    """
    if score < record.band_low or score > record.band_high:
        return None
    index = int((score - record.band_low) / record.bin_width + SLOT_TOLERANCE)
    return min(index, len(record.slots) - 1)


def _read_at(row: StorySimilarityPair) -> tuple[str, str]:
    """How recently a row was judged, as a value two rows can be compared on.

    `judged_by_run_id` first, because that is the run that READ the pair.
    `run_id` names the digest run that published the day, so two judging runs
    over one date write the identical string there and it can settle nothing on
    its own.

    An empty stamp sorts lowest, so a stamped re-judge beats the unstamped row
    it replaces. `run_id` stays in the pair rather than being dropped: without
    it two unstamped rows from different runs would compare equal and the first
    one seen would win, which is neither file order nor what this did before the
    column existed.
    """
    return (row.judged_by_run_id or "", row.run_id)


def one_row_a_pair(rows: Sequence[StorySimilarityPair]) -> list[StorySimilarityPair]:
    """At most one row per `pair_key`, the most recently judged one winning.

    The day file can hold one pair twice: once from the run that judged it and
    once from a later run that judged it again against a rebuilt day. Both rows
    stay in the file, because the two run stamps say they are two facts. The
    record counts the pair once, and it counts the latest reading, because that
    run read the day as it stands. Counting both would double one pair's weight
    in its slot with nothing downstream able to see it.
    """
    newest: dict[str, StorySimilarityPair] = {}
    for row in rows:
        held = newest.get(row.pair_key)
        if held is None or _read_at(row) > _read_at(held):
            newest[row.pair_key] = row
    return [newest[key] for key in sorted(newest)]


def day_counts(
    rows: Sequence[StorySimilarityPair], *, record: StorySimilarityDistribution
) -> dict[int, SlotCounts]:
    """Today's own contribution, slot by slot. Row 8 subtracts this.

    A row the judge could not vouch for is counted nowhere. `usable` is false
    when the two readings disagreed or the grammar could not be shown to have
    held, and a verdict nobody can stand behind still moves the line if it is
    counted - which is worse than having no verdict at all.
    """
    counts: dict[int, SlotCounts] = {}
    for row in one_row_a_pair(rows):
        if not row.usable:
            continue
        index = slot_index(row.composite_score, record=record)
        if index is None:
            continue
        held = counts.get(index, SlotCounts())
        counts[index] = SlotCounts(
            same=held.same + (row.verdict is SameStoryVerdict.YES),
            different=held.different + (row.verdict is SameStoryVerdict.NO),
            unclear=held.unclear + (row.verdict is SameStoryVerdict.UNCLEAR),
        )
    return counts


def fold_day(
    record: StorySimilarityDistribution,
    rows: Sequence[StorySimilarityPair],
    *,
    date: str,
) -> StorySimilarityDistribution:
    """The record with today added and `date` appended to `folded_dates`.

    Raises `ValueError` when the record already holds the date, so a re-run of
    this step is free rather than a day counted twice. The message names the date
    because that is the one thing the operator has to act on.
    """
    if date in record.folded_dates:
        raise ValueError(f"the record already counted {date}")
    counts = day_counts(rows, record=record)
    return record.model_copy(
        update={
            "folded_dates": tuple(sorted((*record.folded_dates, date))),
            "slots": tuple(
                slot.model_copy(
                    update={
                        "same_count": slot.same_count + counts[index].same,
                        "different_count": slot.different_count + counts[index].different,
                        "unclear_count": slot.unclear_count + counts[index].unclear,
                    }
                )
                if index in counts
                else slot
                for index, slot in enumerate(record.slots)
            ),
        }
    )


def inputs_changed(
    record: StorySimilarityDistribution,
    *,
    knobs: SimilarityThresholdConfig,
    scorer: ScorerStamp,
    judge: JudgeStamp,
) -> tuple[str, str] | None:
    """The old value and the new value of the first field that moved, or `None`.

    Returns the pair rather than a bare flag, because the operator reading a held
    line needs to know WHICH input moved: the encoder, a weight, the model, a
    reworded ask, a sampler, or a reasoning span in front of the verdict.
    Compared in a fixed order so two runs over one changed record name the same
    field.

    **Every value the record stamps is compared here.** A stamp column the
    detector cannot see is a stamp that lies: the record would archive under a
    new name with nothing able to say which input moved it.
    """
    for was, now in (
        (record.scorer_model, scorer.scorer_model),
        (record.cosine_weight, scorer.cosine_weight),
        (record.key_point_weight, scorer.key_point_weight),
        (record.judge_model, judge.judge_model),
        (record.prompt_digest, judge.prompt_digest),
        (record.grammar_digest, judge.grammar_digest),
        (record.judge_temperature, judge.judge_temperature),
        (record.decode_digest, judge.decode_digest),
        (record.judge_thinks, judge.thinks),
        (record.band_low, knobs.band_low),
        (record.band_high, knobs.band_high),
        (record.bin_width, knobs.bin_width),
    ):
        if was != now:
            return str(was), str(now)
    return None


def archive_stem(record: StorySimilarityDistribution) -> str:
    """The `<stamp>` of `state/story-similarity/archive/<stamp>.json`.

    The record's own stamp rather than a date: the stamp is what the counts
    inside it were taken under, so two archives from one day are two different
    questions and get two files, and an input moved back to what it was produces
    the archive already sitting there.
    """
    return record.record_stamp()
