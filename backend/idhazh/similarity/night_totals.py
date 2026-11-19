"""What do a night's own pairs and runners say, apart from where the thresholds stand?

Two parts of a night's threshold row need no curve. The first is the two lightly sampled
ends: how many pairs the draw found in each, how many came back usable, and how many the judge
would have called the same story (above the upper threshold) or a different one (below the
lower), weighting each usable pair by one over its sampling chance. The second is the runners:
how many reported and what each pair came to, added up, with the answers they gave on the
known-answer pairs gathered into the night's one text.

Both are made from rows already read, so a night's totals can be worked again from its rows and
the runners' readings. Pure arithmetic: no file, no config file, no clock.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Sequence
from typing import Any, Final

from idhazh.contracts.story_similarity_pair_verdict import (
    PairBucket,
    SameStoryVerdict,
    StorySimilarityPairVerdict,
)
from idhazh.contracts.story_similarity_runner_report import StorySimilarityRunnerReport
from idhazh.contracts.story_similarity_threshold_history_row import canary_answers_text
from idhazh.similarity.statistics import combined_statistics, shipped_statistics

LOG: Final = logging.getLogger("idhazh")


def pool_sizes(
    draw: Sequence[StorySimilarityPairVerdict], tonight: Sequence[StorySimilarityPairVerdict]
) -> dict[PairBucket, int]:
    """How many pairs the draw found in each lightly sampled end.

    The draw file names a slice for every pair the draw took, whether or not its runner came
    back, so an end whose rows were all lost still has its pool there. A slice the draw took
    nothing from is named nowhere, and its pool is read off a filed row when one exists.
    """
    pools: dict[PairBucket, int] = {}
    for row in (*draw, *tonight):
        if row.bucket in (PairBucket.FULLY_SIMILAR, PairBucket.FULLY_DISSIMILAR):
            held = pools.setdefault(row.bucket, row.slice_pairs_available)
            if held != row.slice_pairs_available:
                raise ValueError(
                    f"the {row.bucket.value} end held {held} pairs by one row and "
                    f"{row.slice_pairs_available} by another, so the rows are not from one draw"
                )
    return pools


def _one_end(
    tonight: Sequence[StorySimilarityPairVerdict],
    pools: dict[PairBucket, int],
    *,
    bucket: PairBucket,
    counted: Callable[[StorySimilarityPairVerdict], bool],
) -> tuple[int, int, float | None]:
    """One lightly sampled end: its pool, its usable pairs, and the pairs it would have given.

    Each usable pair stands for one over its sampling chance pairs of its slice, and one slice
    is the whole of an end. The estimate is empty when no pair there was usable, because a
    total over no pairs is not a count of zero.
    """
    usable = [row for row in tonight if row.bucket is bucket and row.readings_agree]
    weights = [1.0 / row.sampling_chance for row in usable if counted(row) and row.sampling_chance]
    return pools.get(bucket, 0), len(usable), math.fsum(weights) if usable else None


def end_columns(
    tonight: Sequence[StorySimilarityPairVerdict], pools: dict[PairBucket, int]
) -> dict[str, Any]:
    """The two lightly sampled ends' columns: pool, usable pairs and the weighted total.

    With a handful of pairs a night the weighted totals are an alarm and never move a
    threshold.
    """
    similar = _one_end(
        tonight,
        pools,
        bucket=PairBucket.FULLY_SIMILAR,
        counted=lambda row: row.verdict is SameStoryVerdict.YES,
    )
    dissimilar = _one_end(
        tonight,
        pools,
        bucket=PairBucket.FULLY_DISSIMILAR,
        counted=lambda row: row.verdict is not SameStoryVerdict.YES,
    )
    return {
        "above_upper_pairs_available": similar[0],
        "above_upper_pairs_usable": similar[1],
        "above_upper_same_story_estimated": similar[2],
        "below_lower_pairs_available": dissimilar[0],
        "below_lower_pairs_usable": dissimilar[1],
        "below_lower_different_story_estimated": dissimilar[2],
    }


def merged_canary_answers(readings: Sequence[StorySimilarityRunnerReport]) -> str | None:
    """The known-answer pairs' answers of every runner that reported, as the night's one text.

    Each pair is dealt to one runner, so the runners' answers name different pairs and the
    night's are their union. None when no runner reported any, which means no known-answer pair
    ran: an empty object would read as pairs that ran and had nothing to say.

    **A pair two readings both answer is warned about and never raised on.** It cannot happen
    by construction, since a reading names only its own work part and one reading is shipped
    for each, so it is a fault of the artifacts and not a wrong answer. Raising would cost the
    night its threshold row, and nothing in a known-answer pair taints a number that row
    holds, so the lower runner's answer is kept and the fault is named.
    """
    merged: dict[str, Any] = {}
    owners: dict[str, int] = {}
    for reading in sorted(readings, key=lambda one: one.work_part_index):
        if reading.canary_answers is None:
            continue
        for canary_id, answer in json.loads(reading.canary_answers).items():
            if canary_id in merged:
                LOG.warning(
                    "known-answer pair %s was answered by runner %s and by runner %s, so the "
                    "answer of runner %s is kept",
                    canary_id,
                    owners[canary_id],
                    reading.work_part_index,
                    owners[canary_id],
                )
                continue
            merged[canary_id] = answer
            owners[canary_id] = reading.work_part_index
    return canary_answers_text(merged)


def runner_columns(
    readings: Sequence[StorySimilarityRunnerReport], *, expected_shards: int
) -> dict[str, Any]:
    """What the runners that reported were dealt and how each pair ended, added up.

    A runner that never reported is not in any sum, so the four endings still add up to the
    pairs dealt on a night that lost one, and `runners_reported` against `runners_expected`
    says that one was lost. The rates come from the summed counts and never from averaging
    the runners' own rates. `canary_answers` gathers what the reporting runners answered on the
    known-answer pairs, which are in no sum, rate or clock here; it is empty when no runner
    judged one.
    """
    counts = combined_statistics(shipped_statistics(one) for one in readings)
    seconds = [one.decode_seconds_total for one in readings if one.decode_seconds_total is not None]
    return {
        "runners_expected": expected_shards,
        "runners_reported": len(readings),
        "pairs_dealt": sum(one.pairs_dealt for one in readings),
        "pairs_valid": counts.valid,
        "pairs_agreed": counts.agreed,
        "pairs_unreadable": sum(one.pairs_unreadable for one in readings),
        "pairs_refused": sum(one.pairs_refused for one in readings),
        "pairs_abandoned": sum(one.pairs_abandoned for one in readings),
        "disagreement_rate": counts.disagreement_rate,
        "unclear_rate": counts.unclear_rate,
        "decode_seconds_total": math.fsum(seconds) if seconds else None,
        "decode_seconds_slowest_runner": max(seconds) if seconds else None,
        "canary_answers": merged_canary_answers(readings),
    }
