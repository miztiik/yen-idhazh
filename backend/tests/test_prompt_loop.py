"""The offline prompt loop: the gate disposes, the judge only proposes.

The load-bearing test here is `test_a_candidate_the_judge_prefers_but_the_scorers_refuse_leaves_the_incumbent`.
It is the whole point of the row: a model judge that prefers a worse candidate
must not be able to promote it. Every other test guards a piece of that - the
gate is a Pareto beat, `new_fact_rate` is never a gate target, and the number
checker the gate leans on agrees with an independent count.

The judge and the summariser are driven by recorded fixtures. The model is not
under test; the gate logic is (CLAUDE.md section 13).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import pytest

from idhazh.evals.metrics import (
    hedge_dropped,
    lead_coverage,
    new_fact_rate,
    unsupported_numbers,
    verbatim_run,
)
from utilities.prompt_loop import (
    FrozenItem,
    ItemSummary,
    LoopResult,
    Scorecard,
    beats_incumbent,
    run_loop,
    score_prompt,
)

_LEAD_MIN = 0.3
_CEILING = 0.5


# --- Recorded judges and summarisers (no model, no network) -----------------


class RecordedSummarizer:
    """Return pre-recorded summaries per prompt. The gate reads these; no model runs."""

    def __init__(self, by_prompt: dict[str, list[ItemSummary]]):
        self._by_prompt = by_prompt

    def summarize(self, prompt: str, items: Sequence[FrozenItem]) -> list[ItemSummary]:
        return self._by_prompt[prompt]


class RecordedJudge:
    """Propose a fixed candidate and state a fixed preference, every round."""

    def __init__(self, candidate: str, *, prefers: bool):
        self._candidate = candidate
        self._prefers = prefers

    def revise(self, prompt: str, rubric: str, scores: Scorecard, round_index: int) -> str:
        return self._candidate

    def prefers_candidate(self, incumbent: str, candidate: str, rubric: str) -> bool:
        return self._prefers


# --- A tiny frozen set with an invented number as the injected defect -------

_SOURCE_A = (
    "Regulators fined the bank 250 million dollars on Monday, the agency said. "
    "The penalty followed a long inquiry into overdraft fees. "
    "Executives reportedly knew of the practice for years."
)
_SOURCE_B = (
    "The council approved 1,320 new homes on the eastern edge of the city. "
    "Building starts next spring, the planning office confirmed. "
    "The site was farmland until 2019."
)
_ITEMS = [
    FrozenItem(key="a", source=_SOURCE_A),
    FrozenItem(key="b", source=_SOURCE_B),
]

# The incumbent's summaries: faithful, no invented figure.
_INCUMBENT_SUMMARIES = [
    ItemSummary(
        key="a",
        summary="The agency fined the bank 250 million dollars after an inquiry into fees.",
        key_points=("A regulator penalised the bank over overdraft fees.",),
    ),
    ItemSummary(
        key="b",
        summary="The council approved 1,320 homes, with building due to start next spring.",
        key_points=("A council cleared a large housing scheme.",),
    ),
]

# The candidate's summaries: identical, plus one figure that is nowhere in the
# source. That is the single most damaging defect a news summary can carry, and
# the deterministic gate must refuse it however much the judge likes the prose.
_CANDIDATE_SUMMARIES = [
    ItemSummary(
        key="a",
        summary=(
            "The agency fined the bank 250 million dollars after an inquiry into fees. "
            "It affected 9999 accounts."
        ),
        key_points=("A regulator penalised the bank over overdraft fees.",),
    ),
    ItemSummary(
        key="b",
        summary="The council approved 1,320 homes, with building due to start next spring.",
        key_points=("A council cleared a large housing scheme.",),
    ),
]

_INCUMBENT = "incumbent-prompt"
_CANDIDATE = "candidate-prompt"


def _loop(*, prefers: bool, iterations: int = 1) -> LoopResult:
    summarizer = RecordedSummarizer(
        {_INCUMBENT: _INCUMBENT_SUMMARIES, _CANDIDATE: _CANDIDATE_SUMMARIES}
    )
    judge = RecordedJudge(_CANDIDATE, prefers=prefers)
    return run_loop(
        incumbent_prompt=_INCUMBENT,
        items=_ITEMS,
        summarizer=summarizer,
        judge=judge,
        rubric="the editor rubric",
        iterations=iterations,
        lead_coverage_min=_LEAD_MIN,
        restatement_ceiling=_CEILING,
        seed=7,
    )


# --- The oracle -------------------------------------------------------------


def test_a_candidate_the_judge_prefers_but_the_scorers_refuse_leaves_the_incumbent() -> None:
    """The load-bearing case: judge prefers, deterministic suite refuses, incumbent stands.

    The candidate carries an invented figure, so it is worse on the
    `unsupported_numbers` gate target. The judge prefers it anyway. Promotion must
    not happen: a disagreement is a stop, never a promotion.
    """
    result = _loop(prefers=True)

    assert result.winning_prompt == _INCUMBENT
    assert result.promoted is False
    round_ = result.rounds[0]
    assert round_.judge_preferred is True  # the judge did prefer it
    assert round_.beat_incumbent is False  # and it was refused anyway


def test_the_incumbent_survives_every_round_when_no_candidate_clears_the_gate() -> None:
    """Bounding by more than one round changes nothing when the gate keeps refusing."""
    result = _loop(prefers=True, iterations=3)

    assert result.winning_prompt == _INCUMBENT
    assert result.promoted is False
    assert [round_.beat_incumbent for round_ in result.rounds] == [False, False, False]
    assert all(round_.judge_preferred for round_ in result.rounds)


def test_the_gate_promotes_a_real_winner_even_when_the_judge_is_against_it() -> None:
    """The gate rules both ways: it does not block a candidate that genuinely wins.

    The two summary sets differ on item "a" by one token - the source figure 250
    against an invented 999 - so the word count, and with it `verbatim_run`, is held
    equal while `unsupported_numbers` and `lead_missing` improve. The judge does NOT
    prefer the winner. It is promoted regardless, because the deterministic gate is
    the whole decision.
    """
    worse = [
        ItemSummary("a", "A separate note put the penalty at 999 pounds overall.", ("A fine was set.",)),
        ItemSummary("b", "The council cleared 1320 homes for next spring.", ("Homes were cleared.",)),
    ]
    better = [
        ItemSummary("a", "A separate note put the penalty at 250 pounds overall.", ("A fine was set.",)),
        ItemSummary("b", "The council cleared 1320 homes for next spring.", ("Homes were cleared.",)),
    ]
    # Precondition: prove the crafted sets are a clean Pareto beat before the loop.
    worse_card = score_prompt(worse, _ITEMS, lead_coverage_min=_LEAD_MIN, restatement_ceiling=_CEILING)
    better_card = score_prompt(better, _ITEMS, lead_coverage_min=_LEAD_MIN, restatement_ceiling=_CEILING)
    assert beats_incumbent(better_card, worse_card) is True

    summarizer = RecordedSummarizer({_INCUMBENT: worse, _CANDIDATE: better})
    judge = RecordedJudge(_CANDIDATE, prefers=False)
    result = run_loop(
        incumbent_prompt=_INCUMBENT,
        items=_ITEMS,
        summarizer=summarizer,
        judge=judge,
        rubric="the editor rubric",
        iterations=1,
        lead_coverage_min=_LEAD_MIN,
        restatement_ceiling=_CEILING,
        seed=7,
    )

    assert result.winning_prompt == _CANDIDATE
    assert result.promoted is True
    assert result.rounds[0].judge_preferred is False


# --- The gate is a Pareto beat over the four targets ------------------------

_BASE = Scorecard(
    unsupported_numbers=0.5,
    lead_missing_rate=0.2,
    hedge_dropped_rate=0.1,
    verbatim_run=0.3,
    new_fact_rate=0.6,
)


def test_a_candidate_no_worse_everywhere_and_better_on_one_target_wins() -> None:
    better = Scorecard(
        unsupported_numbers=0.5,
        lead_missing_rate=0.2,
        hedge_dropped_rate=0.1,
        verbatim_run=0.25,  # strictly better, rest equal
        new_fact_rate=0.6,
    )
    assert beats_incumbent(better, _BASE) is True


def test_a_tie_on_every_target_does_not_win() -> None:
    assert beats_incumbent(_BASE, _BASE) is False


def test_worse_on_any_target_does_not_win_however_much_better_elsewhere() -> None:
    mixed = Scorecard(
        unsupported_numbers=0.0,  # much better here
        lead_missing_rate=0.2,
        hedge_dropped_rate=0.1,
        verbatim_run=0.9,  # but worse here
        new_fact_rate=0.6,
    )
    assert beats_incumbent(mixed, _BASE) is False


# --- new_fact_rate is recorded, never a gate target -------------------------


def test_a_candidate_that_only_raises_the_new_fact_rate_does_not_win() -> None:
    """The Goodhart guard, at the gate. A candidate equal on every gate target but
    with a higher new-fact rate must not win - acting on that number is exactly the
    optimisation the metric's own contract forbids (metrics.new_fact_rate).
    """
    only_new_fact = Scorecard(
        unsupported_numbers=0.5,
        lead_missing_rate=0.2,
        hedge_dropped_rate=0.1,
        verbatim_run=0.3,
        new_fact_rate=0.99,  # the only change, and it is not a gate target
    )
    assert beats_incumbent(only_new_fact, _BASE) is False


def test_new_fact_rate_is_absent_from_the_gate_targets() -> None:
    from utilities.prompt_loop import GATE_TARGETS

    assert "new_fact_rate" not in GATE_TARGETS
    assert set(GATE_TARGETS) == {
        "unsupported_numbers",
        "lead_missing_rate",
        "hedge_dropped_rate",
        "verbatim_run",
    }


# --- score_prompt reduces the right metric over the right pairing -----------


def test_score_prompt_applies_each_metric_to_its_own_source_and_averages() -> None:
    card = score_prompt(
        _INCUMBENT_SUMMARIES, _ITEMS, lead_coverage_min=_LEAD_MIN, restatement_ceiling=_CEILING
    )
    pairs = [
        (_INCUMBENT_SUMMARIES[0].summary, _SOURCE_A),
        (_INCUMBENT_SUMMARIES[1].summary, _SOURCE_B),
    ]
    assert card.unsupported_numbers == pytest.approx(
        sum(unsupported_numbers(s, src) for s, src in pairs) / 2
    )
    assert card.lead_missing_rate == pytest.approx(
        sum(1 for s, src in pairs if lead_coverage(s, src) < _LEAD_MIN) / 2
    )
    assert card.hedge_dropped_rate == pytest.approx(
        sum(1 for s, src in pairs if hedge_dropped(s, src)) / 2
    )
    assert card.verbatim_run == pytest.approx(
        sum(verbatim_run(s, src) for s, src in pairs) / 2
    )
    expected_new_fact = (
        new_fact_rate(list(_INCUMBENT_SUMMARIES[0].key_points), _INCUMBENT_SUMMARIES[0].summary, ceiling=_CEILING)
        + new_fact_rate(list(_INCUMBENT_SUMMARIES[1].key_points), _INCUMBENT_SUMMARIES[1].summary, ceiling=_CEILING)
    ) / 2
    assert card.new_fact_rate == pytest.approx(expected_new_fact)


def test_the_injected_figure_is_the_only_unsupported_number_across_the_set() -> None:
    """The candidate set carries exactly one invented figure; the incumbent carries none."""
    incumbent = score_prompt(
        _INCUMBENT_SUMMARIES, _ITEMS, lead_coverage_min=_LEAD_MIN, restatement_ceiling=_CEILING
    )
    candidate = score_prompt(
        _CANDIDATE_SUMMARIES, _ITEMS, lead_coverage_min=_LEAD_MIN, restatement_ceiling=_CEILING
    )
    assert incumbent.unsupported_numbers == pytest.approx(0.0)
    assert candidate.unsupported_numbers == pytest.approx(0.5)  # one of two items


# --- Decision 4: the checker cross-check (O33) ------------------------------
#
# `unsupported_numbers` is what the gate leans on hardest, and nothing had ever
# verified the checker itself. This is an independent count of numbers in the
# summary that are absent from the source, computed a different way - canonical
# numeric identity through float(), not the metric's string-set subtraction - over
# a bounded, committed set of pairs. It tests the checker, never the archive
# (Rule #12).

_INT_OR_DECIMAL = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _independent_unsupported(summary: str, source: str) -> int:
    """Numbers the summary states that are nowhere in the source, counted independently.

    Different mechanism from `metrics.unsupported_numbers`: it strips commas and
    reads each token as a float so 1,320 and 1320 and 1320.0 are one number by
    numeric equality, then subtracts the source's numeric set. Single digits are
    skipped, matching the metric's deliberate choice not to chase them.
    """

    def numbers(text: str) -> set[float]:
        found: set[float] = set()
        for token in _INT_OR_DECIMAL.findall(text):
            cleaned = token.replace(",", "")
            if len(cleaned.replace(".", "")) < 2:
                continue
            found.add(float(cleaned))
        return found

    return len(numbers(summary) - numbers(source))


# (summary, source, expected count) - each pins a behaviour the metric must keep.
_CHECKER_CASES: list[tuple[str, str, int]] = [
    ("Fined 250 million.", "The bank was fined 250 million dollars.", 0),
    ("It hit 9999 accounts.", "The bank was fined 250 million dollars.", 1),
    ("Approved 1320 homes.", "The council approved 1,320 new homes.", 0),  # comma vs plain
    ("A 4.20 percent rate.", "Rates rose to 4.2 percent.", 0),  # trailing zero
    ("Only 3 people came.", "A crowd gathered.", 0),  # single digit is not chased
    ("Costs of 100 and 200.", "The bill was 100 dollars.", 1),  # 200 invented
]


@pytest.mark.parametrize("summary, source, expected", _CHECKER_CASES)
def test_unsupported_numbers_agrees_with_an_independent_count(
    summary: str, source: str, expected: int
) -> None:
    assert unsupported_numbers(summary, source) == expected
    assert _independent_unsupported(summary, source) == expected
