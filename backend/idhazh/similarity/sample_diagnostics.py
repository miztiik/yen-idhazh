"""What did this attempt return, and how did the scores agree with the judge?"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from itertools import groupby
from operator import itemgetter
from typing import Final

from pydantic import ValidationError

from idhazh.contracts.story_similarity_diagnostics import (
    SampleStatus,
    SliceOutcome,
    SliceOutcomes,
    diagnostic_text,
)
from idhazh.contracts.story_similarity_pair_verdict import (
    PairBucket,
    SameStoryVerdict,
    StorySimilarityPairVerdict,
)

LOG: Final = logging.getLogger("idhazh")
_RECALL_90: Final = (9, 10)  # This target defines the named reading; it is not a knob.

type _SliceKey = tuple[float, float, PairBucket]
type _Columns = dict[str, str | int | float | None]
type _BinaryPair = tuple[float, bool]


class _DrawMismatchError(ValueError):
    """The diagnostic cannot match this draw to this batch."""


def _index_rows(
    rows: Sequence[StorySimilarityPairVerdict], *, date: str, run_id: str, source: str
) -> dict[str, StorySimilarityPairVerdict]:
    indexed: dict[str, StorySimilarityPairVerdict] = {}
    for row in rows:
        if (row.date, row.run_id) != (date, run_id):
            raise _DrawMismatchError(f"{source}_identity")
        if row.pair_key in indexed:
            raise _DrawMismatchError(f"{source}_duplicate_key")
        indexed[row.pair_key] = row
    return indexed


def _slice_key(row: StorySimilarityPairVerdict) -> _SliceKey:
    return row.slice_low, row.slice_high, row.bucket


def _draw_slice_counts(
    drawn: Iterable[StorySimilarityPairVerdict],
) -> dict[_SliceKey, tuple[int, int]]:
    declared: dict[_SliceKey, tuple[int, int]] = {}
    counted: Counter[_SliceKey] = Counter()
    for row in drawn:
        key = _slice_key(row)
        counts = _slice_size(row)
        if declared.setdefault(key, counts) != counts:
            raise _DrawMismatchError("draw_slice_count_conflict")
        counted[key] += 1
    if any(counted[key] != taken for key, (_, taken) in declared.items()):
        raise _DrawMismatchError("draw_slice_size")
    return declared


def _slice_size(row: StorySimilarityPairVerdict) -> tuple[int, int]:
    return row.slice_pairs_available, row.slice_pairs_judged


def _outcome(row: StorySimilarityPairVerdict) -> str:
    if row.verdict is None or row.verdict_swapped is None:
        return "refused"
    if row.verdict != row.verdict_swapped:
        return "split"
    return row.verdict.value


def sample_columns(
    draw_rows: Sequence[StorySimilarityPairVerdict],
    filed_rows: Sequence[StorySimilarityPairVerdict] | None,
    *,
    date: str,
    run_id: str,
    cutoff: float,
    upper_cutoff: float,
) -> _Columns:
    """Join only the exact filed batch; never fill a missing return from a ledger read."""
    known: _Columns = {}
    try:
        drawn = _index_rows(draw_rows, date=date, run_id=run_id, source="draw")
        shapes = _draw_slice_counts(drawn.values())
        known["pairs_drawn"] = len(drawn)
        if filed_rows is None:
            return known | {"sample_status": SampleStatus.NOT_FILED}

        filed = _index_rows(filed_rows, date=date, run_id=run_id, source="filed")
        counts: defaultdict[_SliceKey, Counter[str]] = defaultdict(Counter)
        binary: list[_BinaryPair] = []
        for key, row in filed.items():
            original = drawn.get(key)
            if original is None:
                raise _DrawMismatchError("filed_key_missing_from_draw")
            if row.similarity_score != original.similarity_score:
                raise _DrawMismatchError("filed_score_mismatch")
            if row.work_part_index != original.work_part_index:
                raise _DrawMismatchError("filed_shard_mismatch")
            section = _slice_key(row)
            if section != _slice_key(original) or _slice_size(row) != _slice_size(original):
                raise _DrawMismatchError("filed_slice_mismatch")
            outcome = _outcome(row)
            counts[section][outcome] += 1
            if outcome in (SameStoryVerdict.YES, SameStoryVerdict.NO):
                binary.append((row.similarity_score, outcome == SameStoryVerdict.YES))

        outcomes: list[SliceOutcome] = []
        for section, (available, taken) in sorted(shapes.items()):
            low, high, bucket = section
            tally = counts[section]
            outcomes.append(
                SliceOutcome(
                    bucket=bucket,
                    low=low,
                    high=high,
                    available=available,
                    drawn=taken,
                    yes=tally[SameStoryVerdict.YES],
                    no=tally[SameStoryVerdict.NO],
                    unclear=tally[SameStoryVerdict.UNCLEAR],
                    split=tally["split"],
                    refused=tally["refused"],
                )
            )
        slices = SliceOutcomes(slices=tuple(outcomes))
    except (_DrawMismatchError, ValidationError) as error:
        reason = str(error) if isinstance(error, _DrawMismatchError) else "invalid_slice_outcomes"
        status = SampleStatus.NOT_FILED if filed_rows is None else SampleStatus.DRAW_MISMATCH
        LOG.warning(
            "review-thresholds sample date=%s run=%s status=%s reason=%s",
            date,
            run_id,
            status,
            reason,
        )
        return known | {"sample_status": status}

    return (
        known
        | {
            "sample_status": SampleStatus.MEASURED,
            "pairs_returned": len(filed),
            "slice_outcomes": diagnostic_text(slices),
        }
        | _cutoff_columns(binary, cutoff=cutoff, upper_cutoff=upper_cutoff)
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _confusion(pairs: Sequence[_BinaryPair], cutoff: float) -> tuple[int, int, int, int]:
    tp = fp = fn = tn = 0
    for score, yes in pairs:
        if score >= cutoff:
            tp += yes
            fp += not yes
        else:
            fn += yes
            tn += not yes
    return tp, fp, fn, tn


def _cutoff_columns(
    pairs: Sequence[_BinaryPair], *, cutoff: float, upper_cutoff: float
) -> _Columns:
    tp, fp, fn, tn = _confusion(pairs, cutoff)
    upper_tp, upper_fp, upper_fn, _ = _confusion(pairs, upper_cutoff)
    upper_support = upper_tp + upper_fp
    return {
        "evaluated_cutoff": cutoff,
        "sample_tp": tp,
        "sample_fp": fp,
        "sample_fn": fn,
        "sample_tn": tn,
        "sample_precision": _ratio(tp, tp + fp),
        "sample_recall": _ratio(tp, tp + fn),
        "cutoff_brier_score": _ratio(fp + fn, len(pairs)),
        "upper_cutoff_sample_size": upper_support,
        "upper_cutoff_false_match_share": _ratio(upper_fp, upper_support),
        "upper_cutoff_brier_score": _ratio(upper_fp + upper_fn, len(pairs)),
        "sample_f0_5": _ratio(5 * tp, 5 * tp + 4 * fp + fn),
    } | _ranking_columns(pairs, positives=tp + fn)


def _ranking_columns(pairs: Sequence[_BinaryPair], *, positives: int) -> _Columns:
    if not positives:
        return {}
    ordered = sorted(pairs, key=itemgetter(0), reverse=True)
    tp = predicted = 0
    terms: list[float] = []
    at_recall_90: _Columns = {}
    target_numerator, target_denominator = _RECALL_90
    for score, group in groupby(ordered, key=itemgetter(0)):
        tied = list(group)
        gained = sum(yes for _, yes in tied)
        predicted += len(tied)
        tp += gained
        precision = tp / predicted
        terms.append(gained * precision)
        if not at_recall_90 and tp * target_denominator >= target_numerator * positives:
            at_recall_90 = {
                "sample_precision_at_recall_90": precision,
                "sample_recall_90_cutoff": score,
                "sample_recall_at_recall_90_cutoff": tp / positives,
            }
    return {"sample_average_precision": math.fsum(terms) / positives} | at_recall_90
