"""Which pairs of the last few nights say where one threshold sits?

A threshold is where the same-story share crosses a level, and the share is read off the
judge's own answers on pairs scoring close to it. This module picks those pairs out of the
`pair-verdicts` rows from a bounded adaptive window (`min_window_nights` up to
`max_window_nights` ending on the night) and says how much evidence they are.

**Each pair counts once, by its newest row.** A re-run of a night judges the same pairs again
and both runs keep their rows, so a pair can have several. The row filed last is the one
that counts, whatever it says, and it is chosen before anything else is asked of the pair: a
newer reading that disagreed with itself is the pair's reading now, and the older agreeing
one is not kept beside it.

**Only pairs read under tonight's meaning count.** A change of judge model, prompt, grammar,
encoder, cosine weight or judge policy changes what an answer means, so a night's pairs are
pooled only with pairs that were read the same way. The window then restarts by itself on
the night after a change, and `nights_used` on the night's row shows it.

**A usable pair is one whose two readings agree, and cosine fits exclude headline overrides.**
An answer is "the same story" for a YES and anything else for a NO or an UNCLEAR, the way the
share is defined. Pairs with `headline=True` score 1.0 outright by rule rather than by cosine,
so they are excluded from the curve evidence even though they are still judged for diagnostics.

Pure: the caller read the rows and names the threshold, the width and the stamp.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from typing import Literal

from idhazh.contracts.story_similarity_pair_verdict import (
    SameStoryVerdict,
    StorySimilarityPairVerdict,
)

#: Which of the two thresholds. The row's columns come in pairs, `lower_*` and `upper_*`.
Side = Literal["lower", "upper"]


@dataclass(frozen=True, slots=True)
class MeaningStamp:
    """Everything that decides what a pair's verdict and score mean.

    Two pairs with one stamp were scored and judged the same way, so their answers can be
    counted together.
    """

    judge_model: str | None
    prompt_digest: str | None
    grammar_digest: str | None
    scorer_model: str
    cosine_weight: float
    judge_policy_version: str | None


@dataclass(frozen=True, slots=True)
class Evidence:
    """The pairs near one threshold: their scores and answers, in a fixed order."""

    scores: tuple[float, ...]
    #: 1 for a pair both readings called the same story, 0 for any other agreed answer.
    answers: tuple[int, ...]
    #: How many distinct nights the pairs came from.
    nights_used: int
    #: The earliest of those nights, empty when there are no pairs.
    first_date: str | None
    #: In the same order as scores and answers, before the proof sorts the key set.
    pair_keys: tuple[str, ...]
    judge_temperatures: frozenset[float | None]

    @property
    def usable_pairs_used(self) -> int:
        return len(self.scores)


def meaning_stamp(row: StorySimilarityPairVerdict) -> MeaningStamp:
    """The stamp one pair row was scored and judged under."""
    return MeaningStamp(
        judge_model=row.judge_model,
        prompt_digest=row.prompt_digest,
        grammar_digest=row.grammar_digest,
        scorer_model=row.scorer_model,
        cosine_weight=row.cosine_weight,
        judge_policy_version=row.judge_policy_version,
    )


def tonights_stamp(rows: Sequence[StorySimilarityPairVerdict]) -> MeaningStamp | None:
    """The one stamp the night's own rows carry, none when it has none, refused when two.

    `rows` are the judged pairs of this run. A night nothing was judged on has no stamp, and so
    no evidence: a stamp read off anything else would be a guess at what an answer means.
    The night's rows come from units of one run, which share a build and a config, so two
    stamps in one run is a shape the night's row cannot describe, because it names one judge
    model and one policy. The night is refused here rather than filed under one of them.
    """
    stamps = {meaning_stamp(row) for row in rows}
    if len(stamps) > 1:
        raise ValueError(
            f"a night's rows carry one meaning stamp, and these {len(rows)} carry {len(stamps)}"
        )
    return next(iter(stamps), None)


def evidence_days(night: str, *, window_nights: int) -> tuple[str, ...]:
    """The `window_nights` UTC days that end on `night`, oldest first, which are the days to read.

    **Guardrail #12 declaration.** The fixed-size input is `window_nights`, a named setting,
    so the read costs the same on the thousandth night as on the third. The collecting job's
    sparse checkout is told the same days, so the read and the declaration cannot disagree.
    """
    last = date_type.fromisoformat(night)
    return tuple(
        (last - timedelta(days=back)).isoformat() for back in range(window_nights - 1, -1, -1)
    )


def current_pairs(
    rows: Sequence[StorySimilarityPairVerdict], *, stamp: MeaningStamp | None
) -> list[StorySimilarityPairVerdict]:
    """The pairs of the window that are usable and were read under `stamp`, each one once.

    `rows` come in the order the ledger door returns them: oldest day first, and within a
    day in the order the door filed them, so the last row of a pair is the newest. With no
    stamp there is no meaning to pool under, and no pair.
    """
    if stamp is None:
        return []
    newest: dict[str, StorySimilarityPairVerdict] = {}
    for row in rows:
        newest[row.pair_key] = row
    return [
        row
        for row in newest.values()
        if row.readings_agree and meaning_stamp(row) == stamp
    ]


def evidence_near(
    pairs: Sequence[StorySimilarityPairVerdict], *, threshold: float, width: float
) -> Evidence:
    """The non-headline pairs scoring within `width` of `threshold`, either side.

    Identical-headline overrides (`headline=True`, scored 1.0 outright) are excluded so they
    cannot distort the cosine logistic curve. The interval is closed, so a score exactly `width`
    away is in it, and the test is the plain comparison with no tolerance added: it is the
    setting the config names and nothing wider, so a night can be worked again by hand. In
    floating point a score that merely looks like it sits on an edge may fall to either side of
    it, since 0.76 less 0.70 is a hair over 0.06.

    The pairs come in the order of the night they came from and then of the pair's key, whatever
    order the ledger returned them in, so the fit sees one sequence for one set of pairs.
    """
    near = sorted(
        (
            row
            for row in pairs
            if not row.headline and abs(row.similarity_score - threshold) <= width
        ),
        key=lambda row: (row.date, row.pair_key),
    )
    return Evidence(
        scores=tuple(row.similarity_score for row in near),
        answers=tuple(int(row.verdict is SameStoryVerdict.YES) for row in near),
        nights_used=len({row.date for row in near}),
        first_date=near[0].date if near else None,
        pair_keys=tuple(row.pair_key for row in near),
        judge_temperatures=frozenset(row.judge_temperature for row in near),
    )


def adaptive_evidence_near(
    rows: Sequence[StorySimilarityPairVerdict],
    *,
    night: str,
    threshold: float,
    width: float,
    min_window_nights: int,
    max_window_nights: int,
    minimum_usable_pairs: int,
    stamp: MeaningStamp | None,
) -> Evidence:
    """Pairs near `threshold`, expanding from `min_window_nights` up to `max_window_nights`.

    Starts from the newest `min_window_nights` UTC days ending on `night` and expands backward
    one UTC day at a time until `usable_pairs_used >= minimum_usable_pairs`, or returns the
    `max_window_nights` evidence if still short. Stopping depends only on the usable pair count
    and never on verdicts. Each `pair_key` inside the bounded maximum window counts at most
    once, by its newest row.
    """
    if min_window_nights < 1:
        raise ValueError(f"min_window_nights must be at least 1, got {min_window_nights}")
    if max_window_nights < min_window_nights:
        raise ValueError(
            f"max_window_nights {max_window_nights} is below min_window_nights {min_window_nights}"
        )
    if minimum_usable_pairs < 1:
        raise ValueError(f"minimum_usable_pairs must be at least 1, got {minimum_usable_pairs}")
    max_days = evidence_days(night, window_nights=max_window_nights)
    allowed_max = frozenset(max_days)
    bounded = sorted((row for row in rows if row.date in allowed_max), key=lambda row: row.date)
    usable = current_pairs(bounded, stamp=stamp)
    evidence = evidence_near((), threshold=threshold, width=width)
    if not usable:
        return evidence
    for span in range(min_window_nights, max_window_nights + 1):
        cutoff = max_days[max_window_nights - span]
        in_span = [row for row in usable if row.date >= cutoff]
        evidence = evidence_near(in_span, threshold=threshold, width=width)
        if evidence.usable_pairs_used >= minimum_usable_pairs:
            return evidence
    return evidence
