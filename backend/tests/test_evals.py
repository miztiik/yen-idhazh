"""Unit-tier tests for the model-free counterweights.

Each test names the defect the metric exists to catch, because a metric that
cannot separate a good summary from the bad one it was written for is a
constant column - and a constant column is worse than no column, since it looks
like a measurement.

No mocks and no network (Rule #7). The text here is written for the test.
"""

from __future__ import annotations

import pytest

from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.evals.metrics import (
    EVIDENTIAL_TERMS,
    HEDGE_TERMS,
    METRICS_VERSION,
    SPECULATIVE_TERMS,
    compression,
    evidential_density,
    extractiveness,
    hedge_dropped,
    lead_coverage,
    scorer_version,
    speculative_density,
    unsupported_numbers,
    verbatim_run,
    word_count,
)
from idhazh.evals.score import band

ARTICLE = (
    "Example Grid ordered four small modular reactors from Northwind Atomics on Tuesday, "
    "in a deal worth 4.2 billion dollars. The first unit is expected to reach the site in "
    "2029, with commissioning slipping to 2031. Regulators in Ontario have not yet approved "
    "the design.\n\n"
    "The order is the largest placed by a Canadian utility since 1994. Northwind said the "
    "reactors would deliver 1200 megawatts in total. A spokesperson declined to say whether "
    "further orders were planned."
)

FAITHFUL = (
    "Example Grid has ordered four small modular reactors from Northwind Atomics in a "
    "4.2 billion dollar deal, with the first unit due at the site in 2029 and commissioning "
    "in 2031. Ontario regulators have not approved the design."
)


def test_a_faithful_summary_keeps_the_lead() -> None:
    assert lead_coverage(FAITHFUL, ARTICLE) >= 0.8


def test_a_summary_that_dropped_the_story_scores_low() -> None:
    """The defect: everything true, nothing that made it news."""
    vague = "A utility has placed an order with a reactor supplier. Approval is still pending."
    assert lead_coverage(vague, ARTICLE) < 0.3


def test_a_summary_with_no_lead_coverage_cannot_band_high() -> None:
    assert (
        band(
            0.99,
            unsupported_numbers=0,
            lead_coverage=0.0,
            hedge_dropped=False,
            config=EvaluationConfig(),
        )
        is ConfidenceBand.MEDIUM
    )


def test_a_dropped_hedge_caps_high_at_medium() -> None:
    assert (
        band(
            0.99,
            unsupported_numbers=0,
            lead_coverage=1.0,
            hedge_dropped=True,
            config=EvaluationConfig(),
        )
        is ConfidenceBand.MEDIUM
    )


def test_lead_coverage_separates_the_two() -> None:
    """A metric with no dynamic range is a constant dressed as a measurement."""
    vague = "A utility has placed an order with a reactor supplier."
    assert lead_coverage(FAITHFUL, ARTICLE) - lead_coverage(vague, ARTICLE) > 0.5


def test_a_lead_with_nothing_salient_is_vacuously_covered() -> None:
    assert lead_coverage("anything at all", "it happened. and then it stopped.") == 1.0


# --- The defect nothing else can see: a wrong number -----------------------


def test_an_invented_number_is_counted() -> None:
    invented = "Example Grid ordered four reactors in a 7.8 billion dollar deal."
    assert unsupported_numbers(invented, ARTICLE) == 1


def test_every_number_present_in_the_source_is_supported() -> None:
    assert unsupported_numbers(FAITHFUL, ARTICLE) == 0


def test_thousands_separators_and_trailing_zeros_are_not_defects() -> None:
    assert unsupported_numbers("It delivers 1,200 megawatts.", ARTICLE) == 0
    assert unsupported_numbers("The deal is worth 4.20 billion.", ARTICLE) == 0


def test_a_number_only_in_the_full_article_still_counts_as_supported() -> None:
    """Checked against the full source: a figure the model never saw is still in the article."""
    assert unsupported_numbers("The largest since 1994.", ARTICLE) == 0


# --- The defect a faithfulness score marks generously ----------------------


def test_a_dropped_hedge_is_caught() -> None:
    hedged = "Northwind is reportedly weighing a second order. The company declined to comment."
    assert hedge_dropped("Northwind will place a second order.", hedged)


def test_a_kept_hedge_is_not_flagged() -> None:
    hedged = "Northwind is reportedly weighing a second order."
    assert not hedge_dropped("Northwind reportedly plans a second order.", hedged)


def test_an_unhedged_source_cannot_drop_a_hedge() -> None:
    assert not hedge_dropped("Northwind placed the order.", "Northwind placed the order.")


# --- What the article itself was worth ---------------------------------------
#
# The only metrics here that score the input. A faithful summary of an unsourced
# rumour scores well on everything above and is still an unsourced rumour.

SOURCED = (
    "The Ministry of Energy said the plant will close in March, according to a statement "
    "published on Tuesday. Two officials familiar with the decision claimed the date was "
    "set in June. A spokesperson for the operator said staff were told last week."
)

SPECULATIVE = (
    "The plant could close as early as March, and the operator may announce a date within "
    "weeks. Analysts expected to see a decision by June. A closure would leave the region "
    "short of capacity, and a replacement might not be approved for years."
)


def test_the_two_lexicons_do_not_overlap() -> None:
    """They mark opposite things. A term in both would count twice and mean nothing."""
    assert not set(EVIDENTIAL_TERMS) & set(SPECULATIVE_TERMS)


def test_splitting_the_lexicon_left_hedge_dropped_alone() -> None:
    """The split is for the new columns. Changing an existing column was not the ask."""
    assert HEDGE_TERMS == tuple(sorted(EVIDENTIAL_TERMS + SPECULATIVE_TERMS))
    assert len(HEDGE_TERMS) == len(EVIDENTIAL_TERMS) + len(SPECULATIVE_TERMS)


def test_a_sourced_article_is_dense_in_attribution_and_thin_on_speculation() -> None:
    assert evidential_density(SOURCED) > speculative_density(SOURCED)


def test_an_article_of_maybes_is_the_other_way_round() -> None:
    assert speculative_density(SPECULATIVE) > evidential_density(SPECULATIVE)


def test_the_pair_separates_two_articles_a_faithfulness_score_cannot() -> None:
    """The whole point. Both are internally consistent; one of them knows something."""
    assert evidential_density(SOURCED) > evidential_density(SPECULATIVE)
    assert speculative_density(SPECULATIVE) > speculative_density(SOURCED)


def test_a_density_is_a_share_and_not_a_count() -> None:
    """Doubling the article must not double the number, or it measures length."""
    once = evidential_density(SOURCED)
    twice = evidential_density(SOURCED + " " + SOURCED)
    assert once == pytest.approx(twice)


def test_a_density_stays_inside_the_bounds_the_ledger_declares() -> None:
    for text in (SOURCED, SPECULATIVE, ARTICLE, FAITHFUL):
        assert 0.0 <= evidential_density(text) <= 1.0
        assert 0.0 <= speculative_density(text) <= 1.0


def test_an_empty_article_does_not_divide_by_zero() -> None:
    assert evidential_density("") == 0.0
    assert speculative_density("") == 0.0


def test_a_marker_inside_a_longer_word_does_not_fire() -> None:
    """Whole words only, or "Mayor" makes every local story speculative."""
    assert speculative_density("The Mayor of Maybury opened the plant.") == 0.0


# --- Copying -----------------------------------------------------------------


def test_a_copied_paragraph_shows_as_a_long_verbatim_run() -> None:
    copied = ARTICLE.split("\n\n")[0]
    assert verbatim_run(copied, ARTICLE) > 0.9
    assert extractiveness(copied, ARTICLE) > 0.9


def test_an_original_summary_does_not() -> None:
    assert verbatim_run(FAITHFUL, ARTICLE) < 0.5


def test_function_words_alone_do_not_lift_the_score() -> None:
    """The reason this is 4-gram precision and not a longest common subsequence."""
    stopwords = "the of a to in and the of a to in and the of a to"
    assert extractiveness(stopwords, ARTICLE) < 0.2


def test_a_summary_shorter_than_one_ngram_is_not_extractive() -> None:
    assert extractiveness("Four reactors", ARTICLE) == 0.0


# --- Recorded, never flagged -------------------------------------------------


def test_compression_is_a_ratio_of_lengths() -> None:
    assert compression(FAITHFUL, ARTICLE) == pytest.approx(
        word_count(FAITHFUL) / word_count(ARTICLE)
    )


def test_compression_of_an_empty_source_does_not_divide_by_zero() -> None:
    assert compression(FAITHFUL, "") == 0.0


def test_a_short_article_is_not_a_defect() -> None:
    """The reason the 0.03-0.20 band was deleted: at a fixed output budget it
    fires on every short article, for a reason that is never about quality."""
    short_source = " ".join(["word"] * 400)
    summary = " ".join(["word"] * 160)
    assert compression(summary, short_source) > 0.20


# --- The version a row is written under --------------------------------------


def test_scorer_version_spells_its_components() -> None:
    version = scorer_version(
        scorer_id="hhem-2.1-open",
        scorer_revision="a1b2c3d4e5f6",
        weights_sha256="9f8e7d6c" + "0" * 56,
        evaluation=EvaluationConfig(),
    )
    assert (
        version
        == f"hhem-2.1-open@a1b2c3d4;weights-9f8e7d6c;metrics-{METRICS_VERSION};"
        "bands=0.80/0.50;lead=0.30"
    )


def test_a_moved_band_moves_the_scorer_version() -> None:
    """A threshold change makes a derived column mean something else."""
    args = {
        "scorer_id": "hhem-2.1-open",
        "scorer_revision": "a1b2c3d4e5f6",
        "weights_sha256": "9f8e7d6c" + "0" * 56,
    }
    assert scorer_version(evaluation=EvaluationConfig(), **args) != scorer_version(
        evaluation=EvaluationConfig(band_high_min=0.85), **args
    )


def test_a_moved_lead_floor_moves_the_scorer_version() -> None:
    """A counterweight threshold change makes a derived column mean something else."""
    args = {
        "scorer_id": "hhem-2.1-open",
        "scorer_revision": "a1b2c3d4e5f6",
        "weights_sha256": "9f8e7d6c" + "0" * 56,
    }
    assert scorer_version(evaluation=EvaluationConfig(), **args) != scorer_version(
        evaluation=EvaluationConfig(lead_coverage_min=0.40), **args
    )
