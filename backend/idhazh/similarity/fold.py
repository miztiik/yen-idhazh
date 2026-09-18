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

from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.story_similarity_distribution import (
    ScoreSlot,
    StorySimilarityDistribution,
)
from idhazh.contracts.story_similarity_pair import SameStoryVerdict, StorySimilarityPair
from idhazh.similarity.stamps import JudgeStamp, ScorerStamp


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
    """
    if score < record.band_low or score > record.band_high:
        return None
    index = int((score - record.band_low) / record.bin_width)
    return min(index, len(record.slots) - 1)


def one_row_a_pair(rows: Sequence[StorySimilarityPair]) -> list[StorySimilarityPair]:
    """At most one row per `pair_key`, the newest `run_id` winning.

    The day file can hold one pair twice: once from the run that judged it and
    once from a later run that judged it again against a rebuilt day. Both rows
    stay in the file, because `run_id` says they are two facts. The record counts
    the pair once, and it counts the newest run, because that run read the day as
    it stands. Counting both would double one pair's weight in its slot with
    nothing downstream able to see it.
    """
    newest: dict[str, StorySimilarityPair] = {}
    for row in rows:
        held = newest.get(row.pair_key)
        if held is None or row.run_id > held.run_id:
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
    line needs to know WHICH input moved: the encoder, a weight, the model, or a
    reworded ask. Compared in a fixed order so two runs over one changed record
    name the same field.
    """
    for was, now in (
        (record.scorer_model, scorer.scorer_model),
        (record.cosine_weight, scorer.cosine_weight),
        (record.key_point_weight, scorer.key_point_weight),
        (record.judge_model, judge.judge_model),
        (record.prompt_digest, judge.prompt_digest),
        (record.grammar_digest, judge.grammar_digest),
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
