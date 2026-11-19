"""What does the judge answer on the known-answer pairs this runner owns?

One stage, one module. The router does not name it: the judging stage calls it first, and the
council reaches that stage through the tenant that owns this judge (CLAUDE.md section 1a, "A
router is the sharpest case").

The pairs are the ones in `config/judges/content-similarity-canaries.json`: two summaries and
the answer a judge ought to give. Each is judged once per council run, on one runner. The pair
at position `i` of the file goes to runner `(i + the night's date ordinal) mod the runners`, so
the pairs move one runner a night and over a few nights every pair has run on every runner. A
runner dealt none still ships a reading, and its answers are empty rather than an empty object.

**The judge cannot tell a known-answer pair from a night's own.** Both reach the model through
`ModelReader.read_pair`, which is `judge.judge_pair`: the same prompt, fence, grammar and
sampler, with nothing marking the pair as a check. A pair that looked different to the model would
measure a different judge. The summaries are committed, reviewed ASCII and still go through the
fence like any other (Guardrail #11), and the comparison with the known answer is made here, by
code, and never by the model.

**A wrong answer is a reading and nothing more.** One that is not the expected word in both
orders - the other word, a split between the two orders, or a reading outside the grammar - is
logged as a warning naming the pair and stored as the judge gave it. Nothing holds, re-runs or
stops the night: a known answer is evidence about the judge, and a night held for it would cost
the thresholds the evidence of every pair that did come back.

**A call that raises stores nothing for its pair.** This stage runs before the runner's own pairs,
so a fault here would otherwise cost the night every pair behind it. The pair is logged as an
error naming its id, left out of the answers, and the next one goes on.

It is handed the instant it must stop by and checks it before each pair, never between a pair's two
readings, for the reason the judging stage gives.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any

from idhazh import config
from idhazh.content_similarity_judge.model_reader import ModelReader
from idhazh.contracts.knobs.content_similarity_canaries import CanaryPair
from idhazh.contracts.story_similarity_pair import SameStoryVerdict
from idhazh.contracts.story_similarity_threshold_history_row import canary_answers_text
from idhazh.similarity import judge
from idhazh.stages.common import LOG


@dataclass(frozen=True, slots=True)
class CanaryReport:
    """What one runner's known-answer pairs came to, and what judging them cost."""

    date: str
    shard: int

    #: How many pairs the dealing gave this runner.
    owned: int

    #: How many of them came back with an answer, right or wrong.
    judged: int

    #: How many of those were not the expected word in both orders.
    wrong: int

    #: The answers as the one compact text the night's threshold row carries, keyed by pair id.
    #: Empty, and never an empty object, when no pair was judged.
    answers: str | None

    #: What the calls cost, for the venue's own row and for nothing else. They are model time the
    #: unit spent, so the venue counts them, and they are kept out of the instrument's funnel and
    #: clocks, which describe the night's own pairs.
    model_calls: int
    tokens_in: int
    tokens_out: int
    model_seconds: float


def runner_of(index: int, *, date: str, shards: int) -> int:
    """The runner that judges the pair at position `index` of the file on `date`'s night.

    The date's ordinal moves every pair one runner a day, so with more than one runner the same
    pair is never on the same runner two nights running, and a repaired night deals as the night
    itself would have. A runner index is a place in the matrix and not a machine.
    """
    return (index + date_type.fromisoformat(date).toordinal()) % shards


def stage_judge_canary_pairs(
    date: str,
    *,
    shard: int,
    shards: int,
    settings: config.Settings,
    deadline: float,
    reader: ModelReader,
    canary_pairs: Sequence[CanaryPair],
) -> CanaryReport:
    """Judge the known-answer pairs this runner owns, in the order of the file.

    `canary_pairs` is handed in rather than read here, so a caller says which pairs it means and
    the judging stage's own tests run with none. `shards` is read, because it is the divisor of
    the dealing: a runner told the wrong width would judge pairs another runner also judges, and
    the night's row would name one of them twice.

    `deadline` is a `time.monotonic()` instant. A pair stopped by it has no answer, which reads
    as never judged.
    """
    owned = [
        (index, pair)
        for index, pair in enumerate(canary_pairs)
        if runner_of(index, date=date, shards=shards) == shard
    ]
    answers: dict[str, list[Any]] = {}
    spent: list[judge.Judged] = []
    wrong = 0
    for _, pair in owned:
        if time.monotonic() >= deadline:
            LOG.warning(
                "judge-canary-pairs shard=%s date=%s stopped on its deadline with %s of %s "
                "known-answer pair(s) judged",
                shard,
                date,
                len(spent),
                len(owned),
            )
            break
        try:
            judged = reader.read_pair(pair.left.summary, pair.right.summary, settings=settings)
        except Exception:
            LOG.exception(
                "judge-canary-pairs shard=%s date=%s canary=%s the judge raised, so no answer is "
                "stored for it and the night's own pairs go on",
                shard,
                date,
                pair.id,
            )
            continue
        spent.append(judged)
        answers[pair.id] = _answer_of(judged, runner=shard)
        if (judged.verdict, judged.verdict_swapped) != (pair.expected, pair.expected):
            wrong += 1
            LOG.warning(
                "judge-canary-pairs shard=%s date=%s canary=%s expected=%s answered=%s,%s",
                shard,
                date,
                pair.id,
                pair.expected.value,
                _said(judged.verdict),
                _said(judged.verdict_swapped),
            )

    report = CanaryReport(
        date=date,
        shard=shard,
        owned=len(owned),
        judged=len(spent),
        wrong=wrong,
        answers=canary_answers_text(answers),
        model_calls=sum(one.calls for one in spent),
        tokens_in=sum(one.prompt_tokens for one in spent),
        tokens_out=sum(one.completion_tokens for one in spent),
        model_seconds=sum(one.decode_seconds for one in spent),
    )
    LOG.info(
        "judge-canary-pairs shard=%s date=%s owned=%s judged=%s wrong=%s",
        report.shard,
        report.date,
        report.owned,
        report.judged,
        report.wrong,
    )
    return report


def _answer_of(judged: judge.Judged, *, runner: int) -> list[Any]:
    """The six cells the night's row keeps for one pair, in the order its contract names them.

    The answer in file order, the answer swapped, the two margins, the file-order call's prompt
    tokens and the runner. A reading outside the grammar is a null verdict and stays null. The
    server reports no prompt count as zero and a prompt is never empty, so zero is stored as
    missing and not as a count.
    """
    return [
        _word(judged.verdict),
        _word(judged.verdict_swapped),
        judged.first_token_margin,
        judged.first_token_margin_swapped,
        judged.prompt_tokens_file_order or None,
        runner,
    ]


def _word(verdict: SameStoryVerdict | None) -> str | None:
    return None if verdict is None else verdict.value


def _said(verdict: SameStoryVerdict | None) -> str:
    """One reading for the log: its word, or `refused` where the grammar did not hold."""
    return "refused" if verdict is None else verdict.value
