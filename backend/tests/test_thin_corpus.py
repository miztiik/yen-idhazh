"""What happens to a verdict when the corpus was thinner than the config asks for?"""

from __future__ import annotations

import test_qualify as built

from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.qualification import CorpusItem
from idhazh.evals import qualify


def a_thin_corpus() -> list[CorpusItem]:
    """The passing corpus with its whole first band taken out."""
    return [row for row in built.a_passing_corpus() if row.band_index != 0]


def test_a_thin_corpus_is_named_rather_than_fatal() -> None:
    """The run that found it still has nine verdicts worth writing down.

    Until 2026-09-18 `decide` computed every gate and then exited before writing
    any of them, so a corpus one tier short deleted the evidence it had. Four
    dispatches on 2026-09-17 cost about eleven hours of runner time and produced
    no verdict for that reason.
    """
    shortfalls = qualify.corpus_shortfalls(
        a_thin_corpus(), summarize=built.SUMMARIZE, evaluation=EvaluationConfig()
    )

    assert shortfalls, "a corpus missing a whole band has to be named"
    assert any("band 0" in line for line in shortfalls)


def test_the_corpus_shape_is_read_from_config_rather_than_typed_in_source() -> None:
    """The substitution test (Guardrail #6): change the config, change the behaviour.

    These three were literals in `evals/qualify.py` until 2026-09-18 - the only
    thresholds in the whole qualification that were not config, and the ones that
    stopped a run.
    """
    generous = EvaluationConfig(qualification_min_per_band=99)
    forgiving = EvaluationConfig(
        qualification_min_per_band=0,
        qualification_min_over_cap=0,
        qualification_min_brief=0,
    )

    passing = built.a_passing_corpus()
    assert qualify.corpus_shortfalls(
        passing, summarize=built.SUMMARIZE, evaluation=generous
    ), "a corpus that satisfies 3 a band cannot satisfy 99"
    assert (
        qualify.corpus_shortfalls(
            a_thin_corpus(), summarize=built.SUMMARIZE, evaluation=forgiving
        )
        == []
    ), "asking for nothing cannot be short of anything"


def test_the_shortfall_says_what_it_asked_for_rather_than_only_what_it_found() -> None:
    """A reader who sees `has 0` and nothing else cannot tell whether that is wrong."""
    shortfalls = qualify.corpus_shortfalls(
        a_thin_corpus(),
        summarize=built.SUMMARIZE,
        evaluation=EvaluationConfig(qualification_min_per_band=3),
    )

    assert all("the corpus asks for" in line for line in shortfalls)
