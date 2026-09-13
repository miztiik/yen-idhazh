"""Unit-tier tests for the model-free counterweights.

Each test names the defect the metric exists to catch, because a metric that
cannot separate a good summary from the bad one it was written for is a
constant column - and a constant column is worse than no column, since it looks
like a measurement.

No mocks and no network (Guardrail #7). The text here is written for the test.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import statistics
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import cli, ledger
from idhazh.contracts.app_config import EvaluationConfig, ExtractConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.score_archive import ScoreCohort
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import SourceTier
from idhazh.evals import archive as score_archive
from idhazh.evals import writer
from idhazh.evals.hhem import HHEM_REVISION, HhemScorer, is_pinned, weights_digest
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
    new_fact_rate,
    restates_summary,
    scorer_version,
    self_repetition,
    speculative_density,
    unsupported_numbers,
    verbatim_run,
    word_count,
)
from idhazh.evals.score import band, to_eval_row
from idhazh.extract import to_article_with_source
from idhazh.fetch import FetchResult

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


def test_a_title_line_cannot_glue_to_a_capitalised_body_line() -> None:
    source = (
        "The Intrinsic Valuation of Biodiversity Loss\n"
        "We explore the welfare costs of the loss of animal life in a utilitarian framework. "
        "Moral philosophy and neuroscience define sentience as the capacity for experience."
    )
    summary = (
        "The authors report that biodiversity loss has welfare costs because animal sentience "
        "has intrinsic value."
    )

    assert lead_coverage(summary, source) >= EvaluationConfig().lead_coverage_min


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


# --- Repeating itself --------------------------------------------------------
#
# The defect greedy decoding makes possible and every metric above is blind to.
# A repeated sentence is still perfectly supported by the article, so it scores
# BETTER on faithfulness the worse it gets.
#
# The pair below is one summary written twice at the same length: `LOOPED` says
# one clause three times, `CONTROL` says it once and then says something else.
# They are built so the older metrics cannot tell them apart, which is the whole
# claim the column makes.

_SHARED = "Northwind Atomics won the order for four reactors."
_CLAUSE = "Ontario has still not signed off."
_ELSEWHERE = "The regulator has asked for more paperwork and a longer review window."

LOOPED = f"{_SHARED} {_CLAUSE} {_CLAUSE} {_CLAUSE}"
CONTROL = f"{_SHARED} {_CLAUSE} {_ELSEWHERE}"


def test_a_looping_summary_is_invisible_to_every_metric_that_reads_the_source() -> None:
    """The blind spot, stated as an equality rather than as an opinion.

    Same length, same 4-gram overlap with the article, same longest copied run,
    same surviving lead facts. Four numbers that cannot separate a summary that
    said one thing three times from a summary that said three things.
    """
    assert word_count(LOOPED) == word_count(CONTROL) == 26
    assert extractiveness(LOOPED, ARTICLE) == extractiveness(CONTROL, ARTICLE)
    assert verbatim_run(LOOPED, ARTICLE) == verbatim_run(CONTROL, ARTICLE)
    assert lead_coverage(LOOPED, ARTICLE) == lead_coverage(CONTROL, ARTICLE)

    assert self_repetition(CONTROL) == 0.0
    assert self_repetition(LOOPED) > 0.0


def test_ordinary_prose_sits_at_the_zero_point() -> None:
    """Zero is not "good" - it is "every four-word window is different"."""
    assert self_repetition(FAITHFUL) == 0.0
    assert self_repetition(ARTICLE) == 0.0


def test_one_phrase_said_three_times_is_all_it_takes() -> None:
    """The smallest repetition a four-word window can see, and what it reads as.

    Two of this summary's 97 windows go on repeat, so the number is 0.02. Small
    on purpose: one echoed phrase in a hundred words is a wobble. A whole clause
    said three times, as above, is 0.39.
    """
    phrase = "at the same time"
    gaps = [" ".join(f"filler{n}" for n in range(at, at + 22)) for at in (0, 22, 44, 66)]
    summary = " ".join((gaps[0], phrase, gaps[1], phrase, gaps[2], phrase, gaps[3]))

    assert word_count(summary) == 100
    assert self_repetition(summary) == pytest.approx(2 / 97)


def test_a_summary_shorter_than_one_window_cannot_repeat_itself() -> None:
    assert self_repetition("Four reactors") == 0.0
    assert self_repetition("") == 0.0


def test_self_repetition_stays_inside_the_bounds_the_ledger_declares() -> None:
    for text in (LOOPED, CONTROL, FAITHFUL, ARTICLE, SOURCED, SPECULATIVE, ""):
        assert 0.0 <= self_repetition(text) <= 1.0


# --- A key point that restates the summary -----------------------------------
#
# `restates_summary` is the copying measure pointed at our own summary instead
# of the article: the share of a key point's four-grams already in the summary.
# It is a distinctness floor for one key point, and the drop that reads it lives
# in `to_summary`. The point of the measure is the gap - a lifted phrase scores
# near one, a new fact scores near zero even when it reuses the summary's words.

_KP_SUMMARY = (
    "The bank held its policy rate at four percent and said inflation is easing "
    "faster than it forecast in June, though it warned that energy prices remain "
    "the largest risk to the outlook."
)


def test_a_key_point_lifted_from_the_summary_scores_near_one() -> None:
    assert restates_summary("The bank held its policy rate at four percent", _KP_SUMMARY) > 0.9


def test_a_new_fact_that_reuses_the_summarys_words_scores_low() -> None:
    """The floor is on distinctness, not on any shared word. This key point shares
    "rate" and "bank" with the summary and still adds when the bank last met."""
    distinct = "The rate has not moved since the bank last met in July."
    assert restates_summary(distinct, _KP_SUMMARY) < 0.2


def test_a_key_point_shorter_than_one_four_gram_reads_as_distinct() -> None:
    """No four-gram to measure, so the safe direction is to keep the fragment."""
    assert restates_summary("Rate held", _KP_SUMMARY) == 0.0


def test_restatement_stays_inside_the_zero_to_one_bound() -> None:
    for point in ("The bank held its policy rate", "energy prices remain", "", "one two three"):
        assert 0.0 <= restates_summary(point, _KP_SUMMARY) <= 1.0


# --- How often a key point adds a fact ---------------------------------------
#
# `new_fact_rate` is the aggregate inverse of `restates_summary`, read at the
# ceiling `to_summary`'s drop uses, so a key point that counts here is exactly
# one the drop keeps. Recorded and never acted on - it is the instrument for
# whether the reordered key-point prompt found facts, not an input to any band.

_KP_LIFTED = "The bank held its policy rate at four percent"
_KP_DISTINCT = "The rate has not moved since the bank last met in July."


def test_every_key_point_restating_the_summary_adds_nothing() -> None:
    assert new_fact_rate([_KP_LIFTED, _KP_LIFTED], _KP_SUMMARY, ceiling=0.5) == 0.0


def test_every_key_point_stating_a_new_fact_adds_one_each() -> None:
    assert new_fact_rate([_KP_DISTINCT, _KP_DISTINCT], _KP_SUMMARY, ceiling=0.5) == 1.0


def test_a_mixed_reply_reports_the_share_that_added() -> None:
    assert new_fact_rate([_KP_LIFTED, _KP_DISTINCT], _KP_SUMMARY, ceiling=0.5) == 0.5


def test_a_reply_with_no_key_points_added_no_fact() -> None:
    assert new_fact_rate([], _KP_SUMMARY, ceiling=0.5) == 0.0


def test_the_new_fact_rate_stays_inside_the_zero_to_one_bound() -> None:
    for points in ([], [_KP_LIFTED], [_KP_DISTINCT], [_KP_LIFTED, _KP_DISTINCT]):
        assert 0.0 <= new_fact_rate(points, _KP_SUMMARY, ceiling=0.5) <= 1.0


def test_a_key_point_counts_here_exactly_when_the_drop_would_keep_it() -> None:
    """One ceiling, read by the metric and by the drop, so they never disagree."""
    ceiling = 0.5
    points = [_KP_LIFTED, _KP_DISTINCT]
    kept = sum(1 for point in points if restates_summary(point, _KP_SUMMARY) <= ceiling)
    assert new_fact_rate(points, _KP_SUMMARY, ceiling=ceiling) == kept / len(points)


def test_the_ledger_row_carries_the_repetition_and_leaves_faithfulness_alone() -> None:
    """The wiring, and the one metric this suite cannot compute itself.

    `hhem` is a model score handed to the scorer, never recomputed from the
    summary, so a loop cannot move it. HHEM's weights are not on the machine
    that runs this suite and no test may fetch them (Guardrail #7), so what is proved
    here is the plumbing: the same faithfulness number goes in for both
    summaries and the same number comes out, while the new column separates
    them.
    """
    item = RunPlan.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")
    ).items[0]
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    written = Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))

    def scored(text: str) -> EvalRow:
        return to_eval_row(
            item=item,
            article=article,
            summary=written.model_copy(update={"summary": text}),
            full_text=ARTICLE,
            premise=ARTICLE,
            hhem=0.91,
            hhem_full=0.89,
            config=EvaluationConfig(),
            date="2026-08-21",
            run_id="2026-08-21-1",
            scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
            scored_at="2026-08-21T06:18:02Z",
        )

    control, looped = scored(CONTROL), scored(LOOPED)

    assert control.hhem == looped.hhem == 0.91
    assert control.hhem_full == looped.hhem_full == 0.89
    assert control.extractiveness == looped.extractiveness
    assert control.verbatim_run == looped.verbatim_run
    assert control.coverage == looped.coverage
    assert control.band == looped.band

    assert control.self_repetition == 0.0
    assert looped.self_repetition is not None
    assert looped.self_repetition > 0.0


def test_the_row_carries_the_new_fact_rate_of_the_summarys_key_points() -> None:
    """The wiring, not the metric: a scored row reports the share of its own key
    points that add a fact, read at the ceiling the drop uses (0.5 by default)."""
    item = RunPlan.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")
    ).items[0]
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    written = Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))

    row = to_eval_row(
        item=item,
        article=article,
        summary=written,
        full_text=ARTICLE,
        premise=ARTICLE,
        hhem=0.91,
        hhem_full=0.89,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )

    assert written.key_points, "the summary fixture must carry key points to measure"
    assert row.new_fact_rate == new_fact_rate(
        written.key_points, written.summary or "", ceiling=0.5
    )


def test_an_eval_row_written_before_the_new_fact_rate_column_still_loads() -> None:
    """Nullable, so a row already in the ledger is not a release blocker (section 11).

    The pre-change shape is a committed row with the key removed, which is what
    every row in `state/scores/` carried before the migration. Null is the honest
    value: 0.0 would claim a scored reply whose every key point restated.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    del payload["new_fact_rate"]

    assert EvalRow.model_validate(payload).new_fact_rate is None


def test_an_eval_row_written_before_this_column_still_loads() -> None:
    """Nullable, so yesterday's committed row is not a release blocker (section 11).

    The pre-change shape is a committed fixture with the key removed, which is
    exactly what every row already in `state/scores.csv` carries. Null is the
    honest value: 0.0 would claim the summary was read and never repeated.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    del payload["self_repetition"]

    before = EvalRow.model_validate(payload)

    assert before.self_repetition is None
    assert before.version == "2026-08-21T03:00", "an older stamp still validates"
    columns = EvalRow.csv_columns()
    assert columns.index("self_repetition") > columns.index("speculative_density"), (
        "appended, so no cell shifts right"
    )


# --- The article's length, before the cap and after it ------------------------


def _row_for(article: Article) -> EvalRow:
    """One ledger row for one article, with everything else held still."""
    item = RunPlan.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")
    ).items[0]
    written = Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    return to_eval_row(
        item=item,
        article=article,
        summary=written,
        full_text=article.text or "",
        premise=article.text or "",
        hhem=0.91,
        hhem_full=0.91,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )


def test_a_truncated_article_files_two_different_lengths() -> None:
    """The defect this pair exists to expose, and the assertion that was missing.

    Until 2026-08-27 `source_word_count` was `metrics.word_count(full_text)` - a
    regex over word shapes - while `source_seen_word_count` was
    `len(article.text.split())`. Production handed the same truncated string to
    both, so the pair was two counters over one text and the difference between
    them was tokenisation noise, not truncation. On 610 of 2,346 committed rows
    the seen count came out LARGER than the full count. Nothing compared the two
    cells, which is why it survived for months.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "truncated.json"))
    row = _row_for(article)

    assert article.truncated, "the fixture has to be an article that was actually cut"
    assert row.source_word_count == article.source_word_count == 5240
    assert row.source_seen_word_count == article.word_count == 4310
    assert row.source_seen_word_count < row.source_word_count, "930 words never reached the model"


def test_an_untruncated_article_reads_the_same_length_twice() -> None:
    """Equal is the truth here: the whole article IS the text the model saw."""
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    row = _row_for(article)

    assert not article.truncated
    assert row.source_word_count == row.source_seen_word_count == 1320


def test_the_lengths_do_not_move_when_the_scored_text_does() -> None:
    """Both counts come off the `Article`, so no caller can make them disagree.

    The three production callers pass `article.text` as `full_text`. Feeding a
    different string used to change one cell of the pair and not the other,
    which is exactly how the two ended up counting different things.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "truncated.json"))
    row = _row_for(article)
    other = to_eval_row(
        item=RunPlan.from_json(
            read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")
        ).items[0],
        article=article,
        summary=Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json")),
        full_text=ARTICLE,
        premise=article.text or "",
        hhem=0.91,
        hhem_full=0.91,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )

    assert other.source_word_count == row.source_word_count
    assert other.source_seen_word_count == row.source_seen_word_count


def test_an_old_payload_that_was_cut_cannot_say_how_long_the_article_was() -> None:
    """None travels through rather than becoming a length nobody measured.

    `Article.source_word_count` is None on a payload written before extract
    recorded it. When that payload was truncated the pre-cap body is gone, so
    the post-cap count would claim the article was exactly as long as the part
    the model read.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "truncated.json"))
    row = _row_for(article.model_copy(update={"source_word_count": None}))

    assert article.truncated
    assert row.source_word_count is None
    assert row.source_seen_word_count == 4310, "the seen count is still a measurement"


def test_an_old_payload_that_was_never_cut_knows_its_own_length() -> None:
    """The same recovery the ledger migration makes, at the writer.

    Nothing was cut, so the article IS the text the model saw and the two counts
    are equal by construction. Refusing to say so would throw away a fact.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    row = _row_for(article.model_copy(update={"source_word_count": None}))

    assert not article.truncated
    assert row.source_word_count == row.source_seen_word_count == 1320


# --- The flag that says extract cut the body ---------------------------------

_PAGE = FIXTURES_DIR / "pages" / "article.html"
_PAGE_URL = "https://newsroom.example-grid.com/2026/08/reactor-order"
_PAGE_ITEM = PlannedItem(
    item_id="energy-01",
    url_key=derive_url_key(_PAGE_URL),
    source_url=_PAGE_URL,
    canonical_url=_PAGE_URL,
    source_id="grid-newsroom",
    tier=SourceTier.INSTITUTION,
    vertical="energy",
    title="Example Grid orders four small modular reactors",
    rank_score=1.4,
)


def _really_extracted(cap_tokens: int) -> Article:
    """The captured page through the real extractor, at the cap this arm asks for.

    Never a hand-written payload. `truncated` typed into a fixture proves only
    that the test agrees with itself, and the defect this column carried was
    exactly a flag that read true about an article nobody had cut.
    """
    return to_article_with_source(
        _PAGE_ITEM,
        FetchResult(FetchOutcome.OK, status=200, body=_PAGE.read_bytes()),
        config=ExtractConfig(truncation_cap_tokens=cap_tokens),
        fetched_at="2026-08-21T06:03:11Z",
    ).article


def _row_for_page(article: Article, *, hhem: float, hhem_full: float) -> EvalRow:
    return to_eval_row(
        item=_PAGE_ITEM,
        article=article,
        summary=Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json")),
        full_text=article.text or "",
        premise=article.text or "",
        hhem=hhem,
        hhem_full=hhem_full,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )


def test_a_page_the_extractor_cut_is_flagged_whatever_the_two_scores_did() -> None:
    """A real cut, and no gap at all between the two faithfulness scores.

    The rule this replaces needed a gap above 0.100 and this arm hands it 0.000,
    so the assertion cannot pass on the old rule.
    """
    article = _really_extracted(cap_tokens=256)
    row = _row_for_page(article, hhem=0.91, hhem_full=0.91)

    assert article.source_word_count is not None
    assert article.word_count < article.source_word_count, "the extractor really cut the body"
    assert article.truncated
    assert row.hhem_delta == 0.0
    assert row.truncation_flagged is article.truncated
    assert row.truncation_flagged


def test_a_page_left_whole_is_not_flagged_whatever_the_two_scores_did() -> None:
    """Nothing cut, and a gap three times the ceiling the old rule read.

    This is the defect the column had, in one assertion: on the committed ledger
    the flag was true on exactly one row, and that row read 748 words of a
    748-word article.
    """
    article = _really_extracted(cap_tokens=ExtractConfig().truncation_cap_tokens)
    row = _row_for_page(article, hhem=0.94, hhem_full=0.61)

    assert article.word_count == article.source_word_count, "nothing was cut"
    assert not article.truncated
    assert row.hhem_delta == pytest.approx(0.33)
    assert row.truncation_flagged is article.truncated
    assert not row.truncation_flagged


def test_the_counterweights_did_not_change_meaning() -> None:
    """Nothing in `metrics.py` moved, so the constant that names it may not either.

    `METRICS_VERSION` sits inside `scorer_version`, and a new scorer version
    restarts the ten-run-day count `docs/concepts/evaluation.md` requires before
    any threshold may move. `truncation_flagged` is not a `band()` input and no
    derived column reads it, so every row written under `metrics-3` still says
    exactly what it said.
    """
    assert METRICS_VERSION == "3"


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
        "window=900/150/anchored;bands=0.80/0.50;lead=0.30"
    )


def test_the_counterweights_version_did_not_move_for_the_window() -> None:
    """`METRICS_VERSION` names the definitions in `metrics.py`, and none changed.

    Moving it would assert a change to the counterweights that did not happen,
    and it is the same string the ten-run-day label gate counts on. The window
    geometry is recorded by its own field instead.
    """
    assert METRICS_VERSION == "3"


def test_a_moved_window_moves_the_scorer_version() -> None:
    """A different premise is a different measurement, so rows must not pool.

    Both halves of the geometry count. The size decides how much article one
    score saw; the overlap decides how many windows the max is taken over.
    """
    args = {
        "scorer_id": "hhem-2.1-open",
        "scorer_revision": "a1b2c3d4e5f6",
        "weights_sha256": "9f8e7d6c" + "0" * 56,
    }
    assert scorer_version(evaluation=EvaluationConfig(), **args) != scorer_version(
        evaluation=EvaluationConfig(chunk_words=1800), **args
    )
    assert scorer_version(evaluation=EvaluationConfig(), **args) != scorer_version(
        evaluation=EvaluationConfig(chunk_overlap_words=300), **args
    )


def test_an_overlap_at_or_above_the_window_is_refused() -> None:
    """The chunker clamps the step to one word, so it walks rather than fails.

    A 4,000-word article at a zero step is 3,101 scorer passes instead of six.
    That is a job that never finishes, which is the worst way for a config typo
    to show up.
    """
    with pytest.raises(ValidationError, match="chunk_overlap_words must sit below"):
        EvaluationConfig(chunk_words=900, chunk_overlap_words=900)


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


# --- The instrument is pinned, and says so -----------------------------------


def test_the_configured_scorer_revision_is_immutable() -> None:
    """It was the branch name `main` until 2026-08-26. A branch moves, and a
    faithfulness floor read off a moving instrument measures nothing (Guardrail #10)."""
    assert is_pinned(HHEM_REVISION)


@pytest.mark.parametrize("revision", ["main", "v2.1", "refs/heads/main", ""])
def test_a_pointer_is_not_a_pin(revision: str) -> None:
    assert not is_pinned(revision)


def test_a_scorer_that_never_loaded_cannot_name_its_weights() -> None:
    """The old fallback hashed the name it was asked for, which validated and
    said nothing about the bytes that ran."""
    with pytest.raises(RuntimeError, match="has not loaded"):
        weights_digest(HhemScorer())


# --- The archived month ------------------------------------------------------


#: Columns of the eval row that identify a measurement rather than being one.
#: Every other column has to be a signal or a moment, and the test below is what
#: makes that a rule instead of a habit.
ARCHIVE_KEY_COLUMNS: frozenset[str] = frozenset(
    {
        "version",
        "date",
        "run_id",
        "item_id",
        "url_key",
        "source_url",
        "title",
        "vertical",
        "model_id",
        "band",
        "pipeline_fingerprint",
        "output_digest",
        "scorer_version",
        "scored_at",
        "source_digest",
    }
)


def test_a_prompt_change_inside_a_month_no_longer_withholds_the_month_figure(
    tmp_path: Path,
) -> None:
    """A quality number exists where there used to be an absence.

    `tests/fixtures/evals/prompt-changed-window.csv` is three rows of one day,
    one run, one model and one scorer, whose middle row was written under a
    different `pipeline_fingerprint` - the shape a reworded prompt produced every
    time somebody shipped one. While the stamp was part of the cohort key that
    day summarised as two cohorts of two rows and one row, so the month had no
    faithfulness figure over its own window, only fragments of one.

    Measured on the base commit 0e049ed8, 2026-09-12: two cohorts, means 0.85
    over two rows and 0.70 over one. Here: one cohort, three rows, 0.80.

    A fixture rather than the committed ledger, because asserting on a live run
    would assert on whatever the pipeline published that morning
    (`CLAUDE.md` section 13).
    """
    shard = tmp_path / "2026-09.csv"
    shutil.copyfile(FIXTURES_DIR / "evals" / "prompt-changed-window.csv", shard)

    summary = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)

    assert len(summary.cohorts) == 1, (
        "one day, one run, one model and one scorer is one cohort - "
        "a reworded prompt inside the month is not a second population"
    )
    faithfulness = summary.cohorts[0].measurements["hhem"]
    assert faithfulness.n == 3
    assert faithfulness.sum / faithfulness.n == pytest.approx(0.80)


def test_the_archived_cohort_no_longer_knows_what_produced_it() -> None:
    """The stamp leaves the cohort key, and the field stays on the shape.

    Relaxing rather than removing is what lets an archive written before today
    still validate. The field is dropped, with its read-side migration, in its
    own commit.
    """
    assert "pipeline_fingerprint" not in score_archive.COHORT_KEY
    assert "pipeline_fingerprint" in ScoreCohort.model_fields


def test_every_column_of_the_eval_row_is_filed_somewhere_in_the_archive() -> None:
    """A column that falls out of the archive stops existing fourteen months later.

    Held closed-world over `EvalRow` itself, so adding a column and forgetting
    the archive fails here rather than silently in 2027. A new column is either
    part of a measurement's identity, a boolean signal, or a number with a
    moment - and the commit that adds it has to say which.
    """
    filed = (
        ARCHIVE_KEY_COLUMNS
        | set(score_archive.SIGNAL_COLUMNS)
        | set(score_archive.MEASUREMENT_COLUMNS)
    )

    assert set(EvalRow.csv_columns()) == filed
    assert set(score_archive.COHORT_KEY) <= ARCHIVE_KEY_COLUMNS
    assert not set(score_archive.SIGNAL_COLUMNS) & set(score_archive.MEASUREMENT_COLUMNS)


def test_the_signals_are_the_booleans_and_the_measurements_are_the_numbers() -> None:
    """Asked of the model's own annotations, so a retyped column moves itself.

    `bool` is a subclass of `int` in Python, which is exactly how a boolean ends
    up averaged into a mean nobody meant to take.
    """
    for name, field in EvalRow.model_fields.items():
        annotation = str(field.annotation)
        if name in score_archive.SIGNAL_COLUMNS:
            assert "bool" in annotation, f"{name} is filed as a signal and is not a boolean"
        if name in score_archive.MEASUREMENT_COLUMNS:
            assert "bool" not in annotation, f"{name} is filed as a moment and is a boolean"
            assert "int" in annotation or "float" in annotation, f"{name} is not a number"


def test_an_observation_digest_cannot_be_forged_by_moving_a_separator() -> None:
    """The scorer version carries semicolons and slashes, so a join is not a key.

    Two different observations whose values differ only in where a separator
    falls must digest differently. A `"|".join` would give them one digest and
    silently drop the second measurement for ever.
    """
    left = score_archive.digest_of(("a;b", "c"))
    right = score_archive.digest_of(("a", "b;c"))

    assert left != right
    assert score_archive.digest_of(("a;b", "c")) == left, "the digest is not stable"


def test_the_summary_indexes_one_digest_per_distinct_measurement(tmp_path: Path) -> None:
    """The index is over distinct observations, and the row count is over rows.

    They differ whenever a shard holds a repeat the settlement has not dropped,
    and reporting one as the other is how a dedupe silently loses a row.
    """
    shard = tmp_path / "2026-01.csv"
    rows = [_archive_row(number) for number in range(4)]
    _write_shard(shard, [*rows, rows[0]])

    built = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)

    assert built.source_rows == 5
    assert len(built.observation_digests) == 4
    assert built.observation_digests == sorted(built.observation_digests)
    assert sum(cohort.rows for cohort in built.cohorts) == 5


def test_a_moment_gives_back_the_mean_and_the_spread(tmp_path: Path) -> None:
    """Five numbers, because a stored mean cannot be re-added and a stored spread
    cannot be pooled. These can do both."""
    shard = tmp_path / "2026-01.csv"
    rows = [_archive_row(number) for number in range(4)]
    _write_shard(shard, rows)

    built = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)
    moment = built.cohorts[0].measurements["hhem"]
    values = [float(row.hhem) for row in rows]

    assert moment.n == len(values)
    assert moment.mean == pytest.approx(sum(values) / len(values))
    assert moment.stdev == pytest.approx(statistics.pstdev(values))
    assert moment.min == pytest.approx(min(values))
    assert moment.max == pytest.approx(max(values))


def test_a_column_nothing_measured_reads_as_absent_and_never_as_zero(tmp_path: Path) -> None:
    """A nullable column is empty on every row written before it existed.

    Counting those as zero would say the scorer read the value and got nothing,
    which is a measurement. Absent is not a measurement.
    """
    shard = tmp_path / "2026-01.csv"
    _write_shard(shard, [_archive_row(number) for number in range(3)])

    moment = score_archive.summarise(
        shard, observation_key=writer.OBSERVATION_KEY
    ).cohorts[0].measurements["evidential_density"]

    assert moment.n == 0
    assert moment.min is None and moment.max is None
    assert moment.mean is None and moment.stdev is None


def test_a_summary_that_does_not_describe_its_shard_says_which_part(tmp_path: Path) -> None:
    """A bare inequality says the archive is wrong and nothing about how.

    The person reading this message is deciding whether a committed file may be
    deleted, so it names the field, both readings, and the shard that stays.
    """
    shard = tmp_path / "2026-01.csv"
    _write_shard(shard, [_archive_row(number) for number in range(3)])
    built = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)
    tampered = built.model_copy(update={"source_rows": 2})

    with pytest.raises(ValueError, match="the shard's source_rows"):
        score_archive.reconcile(tampered, shard, observation_key=writer.OBSERVATION_KEY)


def test_the_dedupe_reads_the_live_rows_and_the_archived_digests(tmp_path: Path) -> None:
    """Decision 2's whole reason for storing the digests, asserted directly."""
    state = tmp_path / "state"
    rows = [_archive_row(number) for number in range(3)]
    assert writer.append(state, rows) == 3
    live = writer.recorded_observations(state)

    shard = writer.ledger_shards(state)[0]
    built = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)
    score_archive.write(score_archive.archive_path(state, shard.stem), built)
    shard.unlink()

    assert writer.recorded_observations(state) == live
    assert writer.append(state, rows) == 0, "a deleted shard made its rows new again"


def test_an_archive_is_written_whole_or_not_at_all(tmp_path: Path) -> None:
    """Temp-then-rename, so an interrupted write cannot leave half a summary
    standing where the next run reads a complete one."""
    shard = tmp_path / "2026-01.csv"
    _write_shard(shard, [_archive_row(number) for number in range(3)])
    built = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)
    target = tmp_path / "archive" / "2026-01.json"

    score_archive.write(target, built)

    assert score_archive.read(target) == built
    assert target.read_bytes() == built.to_json().encode("utf-8")
    assert list(target.parent.iterdir()) == [target], "a temp file survived the write"


# --- The observation index -------------------------------------------------
#
# The writer used to answer "have we measured this already?" by reading every
# score row it had ever written - 800 bytes a row, and every run paid it again.
# The identity is four fields wide and the answer only needs the digest, so the
# ledger keeps a second, fixed-width record of the same identities and the rows
# are not read at all.
#
# Every fixture here is built in the test (Guardrail #12, CLAUDE.md section 13). None
# of it reads `state/scores/`.


def _opened_bytes(
    monkeypatch: pytest.MonkeyPatch, root: Path, work: Callable[[], object]
) -> dict[str, int]:
    """What `work` opened under `root`, by relative path, in bytes.

    Measured at the file boundary rather than by timing, so the answer is the
    same on a loaded machine. `Path.open` is where every read in this module
    goes, so a spy on it counts real I/O and mocks nothing (Guardrail #7).
    """
    real = Path.open
    opened: dict[str, int] = {}

    def spy(self: Path, *args: Any, **kwargs: Any) -> Any:
        try:
            relative = self.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            relative = ""
        if relative:
            opened[relative] = opened.get(relative, 0) + (
                self.stat().st_size if self.is_file() else 0
            )
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy)
    try:
        work()
    finally:
        monkeypatch.undo()
    return opened


def _measurement(number: int) -> EvalRow:
    """One eval row, unique in every identity field and legal at any count.

    `_archive_row` walks its faithfulness score up the band and runs out of
    range past ten rows. Nothing here is about the scores, so this one moves
    only the four fields `OBSERVATION_KEY` reads.
    """
    return _archive_row(0).model_copy(
        update={
            "item_id": f"ai-{number:05d}",
            "url_key": hashlib.sha256(f"index-url-{number}".encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"index-out-{number}".encode("ascii")).hexdigest(),
        }
    )


def _seeded(state: Path, rows: list[EvalRow], *, copies: int = 1) -> None:
    """A ledger holding `rows`, with each row written `copies` times.

    More than one copy is a real state, not a contrivance: `merge=union`
    concatenates two runs that both appended, and `idhazh dedupe-ledgers`
    settles it afterwards. It is also the arm that separates "the read grows
    with the rows" from "the read grows with the measurements".
    """
    shard = writer.ledger_path(state, rows[0].date)
    shard.parent.mkdir(parents=True, exist_ok=True)
    _write_shard(shard, [row for row in rows for _ in range(copies)])


def _indexed(state: Path, month: str) -> set[str]:
    """The digests one month's index holds, read from that file rather than the union."""
    with writer.index_path(state, month).open("r", encoding="utf-8", newline="") as handle:
        return {record["observation_digest"] for record in csv.DictReader(handle)}


def _shard_digests(state: Path, month: str) -> set[str]:
    """The distinct observations one month's rows hold, derived from the rows.

    The one read of the score rows in this section, and it is here so a test can
    say what the index is supposed to mirror without asking the index.
    """
    with writer.ledger_path(state, month).open("r", encoding="utf-8", newline="") as handle:
        return {writer.observation_digest(record) for record in csv.DictReader(handle)}


def test_a_repeat_is_still_refused_when_the_index_is_the_only_thing_read(tmp_path: Path) -> None:
    """The invariant. Nothing about how the answer is stored may move it.

    Same address, same pipeline, same words, same scorer is the same
    measurement, and the ledger counts measurements rather than times the
    pipeline looked.
    """
    state = tmp_path / "state"
    rows = [_measurement(number) for number in range(4)]

    assert writer.append(state, rows) == 4
    assert writer.append(state, rows) == 0, "a measurement already held came back as new"
    assert writer.append(state, [_measurement(9)]) == 1, "a new measurement was refused"


def test_the_writers_read_does_not_grow_with_the_rows_the_shard_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guardrail #12, as bytes rather than as a clock.

    Two trees hold the same 200 measurements. One shard carries each row once,
    the other carries it ten times, so the rows are ten times the bytes and the
    identities are identical. What the writer opens has to be the same figure,
    and the score shard has to be absent from it entirely.
    """
    rows = [_measurement(number) for number in range(200)]
    lean = tmp_path / "lean" / "state"
    fat = tmp_path / "fat" / "state"
    _seeded(lean, rows)
    _seeded(fat, rows, copies=10)
    for state in (lean, fat):
        writer.recorded_observations(state)  # the first read fills the index

    thin = _opened_bytes(monkeypatch, lean, lambda: writer.recorded_observations(lean))
    thick = _opened_bytes(monkeypatch, fat, lambda: writer.recorded_observations(fat))

    shard = writer.ledger_path(fat, rows[0].date).relative_to(fat).as_posix()
    assert shard not in thick, f"the writer opened {shard}, which is what this row removes"
    assert thin == thick, (
        "the writer's read moved with the rows: "
        f"{sum(thin.values())} B against {sum(thick.values())} B over the same 200 measurements"
    )
    assert sum(thick.values()) > 0, "the writer read nothing at all, so this proves nothing"


def test_an_archived_month_whose_rows_are_gone_still_refuses_its_observations(
    tmp_path: Path,
) -> None:
    """The half that cannot be bounded, and the reason the archive keeps digests.

    A month past `observability.scores_full_grain_months` has no rows left. Its
    digests are the only record those measurements were ever made, so dropping
    them would make every one of them new again on the day the shard went.
    """
    state = tmp_path / "state"
    rows = [_measurement(number) for number in range(3)]
    assert writer.append(state, rows) == 3

    shard = writer.ledger_shards(state)[0]
    built = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)
    score_archive.write(score_archive.archive_path(state, shard.stem), built)
    shard.unlink()

    assert writer.append(state, rows) == 0, "a deleted shard made its rows new again"


def test_a_tree_with_shards_and_no_index_answers_the_same_as_one_with_an_index(
    tmp_path: Path,
) -> None:
    """The read-side migration, stated as an equality rather than as a procedure.

    The first run after this lands meets shards and no index. It has to refuse
    exactly what it refuses today, and it has to leave an index behind so the
    second run does not read the rows either.
    """
    rows = [_measurement(number) for number in range(5)]
    fresh = tmp_path / "fresh" / "state"
    carried = tmp_path / "carried" / "state"
    _seeded(fresh, rows)
    _seeded(carried, rows)
    writer.recorded_observations(carried)  # this one already has its index

    assert not writer.index_shards(fresh), "the fresh tree was not the un-migrated one"
    assert writer.recorded_observations(fresh) == writer.recorded_observations(carried)
    assert writer.append(fresh, rows) == 0, "the migrated tree let a held measurement back in"
    assert [path.stem for path in writer.index_shards(fresh)] == [
        path.stem for path in writer.index_shards(carried)
    ]
    assert writer.index_path(fresh, rows[0].date[:7]).read_bytes() == (
        writer.index_path(carried, rows[0].date[:7]).read_bytes()
    )


def test_an_append_leaves_the_index_holding_every_observation_its_shard_holds(
    tmp_path: Path,
) -> None:
    """The invariant the pair rests on, asserted over the files rather than a return value.

    `refresh_index` fills a month with no index and never looks at one that
    exists, so keeping the two in step is `append`'s job: it writes the rows and
    the digests it minted in one call, and every writer of `state/scores/` in
    this repository goes through it.

    Held over the shards after several calls and two months, because the two
    ways to break it are silent. A row filed under one month whose digest lands
    under another, or a row written with no digest at all, both leave a green
    return value and surface weeks later as a measurement counted twice.
    """
    state = tmp_path / "state"
    january = [_measurement(number) for number in range(4)]
    february = [
        row.model_copy(update={"date": "2026-02-03", "run_id": "2026-02-03-1"})
        for row in (_measurement(80), _measurement(81))
    ]

    assert writer.append(state, january) == 4
    assert writer.append(state, [*january, *february]) == 2, "a held measurement came back as new"

    months = [shard.stem for shard in writer.ledger_shards(state)]
    assert months == ["2026-01", "2026-02"], f"both months were not written: {months}"
    for month in months:
        assert _indexed(state, month) == _shard_digests(state, month), (
            f"{writer.index_relpath(month)} does not hold what the rows beside it hold"
        )


def test_an_index_left_behind_its_shard_is_put_right_by_dropping_it(tmp_path: Path) -> None:
    """The one gap the pair cannot close by itself, its cost, and what closes it.

    A shard can grow behind the index's back - rows appended by something that
    never knew the index existed, which is what a long-lived branch meets when
    it merges a `main` older than the index. Nothing detects it, because
    detecting it means reading the rows every run, which is the bill the index
    removes.

    So the writer under-reports, and this pins both halves of that. The repeat
    lands, `ledger.drop_repeated_rows` settles it against `OBSERVATION_KEY`, and
    the ledger is left counting the measurement once - which is the promise the
    file makes. Under-reporting is the safe direction precisely because it has a
    repair; over-reporting would leave a digest whose row nothing ever wrote.

    The repair for the index itself is one deletion: dropping the month puts it
    back into the case `refresh_index` does cover, and the refill reads the rows
    once. The second tree is the same defect with that repair applied.
    """
    held = [_measurement(number) for number in range(4)]
    behind = [_measurement(70), _measurement(71)]
    month = held[0].date[:7]

    stale = tmp_path / "stale" / "state"
    assert writer.append(stale, held) == 4
    _write_shard(writer.ledger_path(stale, month), [*held, *behind])

    assert writer.append(stale, behind) == 2, (
        "an index behind its shard refused a measurement it has never seen, "
        "so this tree was not the stale one"
    )
    dropped = ledger.drop_repeated_rows(writer.ledger_path(stale, month), writer.OBSERVATION_KEY)
    rows = list(writer.records(stale))
    assert dropped == 2, f"the settle dropped {dropped} of the 2 repeated rows"
    assert len(rows) == len(_shard_digests(stale, month)) == 6, (
        f"the settled ledger holds {len(rows)} rows for "
        f"{len(_shard_digests(stale, month))} measurements"
    )

    repaired = tmp_path / "repaired" / "state"
    assert writer.append(repaired, held) == 4
    _write_shard(writer.ledger_path(repaired, month), [*held, *behind])
    writer.index_path(repaired, month).unlink()

    assert writer.append(repaired, behind) == 0, "the refilled index let a held measurement back in"
    assert _indexed(repaired, month) == _shard_digests(repaired, month)


def test_a_month_that_became_an_archive_drops_its_live_index(tmp_path: Path) -> None:
    """Two records of one month's identities is one too many.

    The archive carries them for ever; the live index carries them while the
    rows do. The moment the rows go the live copy is redundant, and leaving it
    would double the 11.9 MB a year this index is supposed to cost.

    A live index is only ever dropped when the archive that supersedes it is on
    disk. Nothing here removes the last record of a measurement.
    """
    state = tmp_path / "state"
    rows = [_measurement(number) for number in range(3)]
    assert writer.append(state, rows) == 3
    month = rows[0].date[:7]
    assert writer.index_path(state, month).exists()

    shard = writer.ledger_shards(state)[0]
    built = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)
    score_archive.write(score_archive.archive_path(state, shard.stem), built)
    shard.unlink()
    held = writer.recorded_observations(state)

    assert not writer.index_path(state, month).exists(), "two copies of one month survived"
    assert held == writer.recorded_observations(state), "dropping the copy moved the answer"


def test_a_live_index_with_no_shard_and_no_archive_is_left_alone(tmp_path: Path) -> None:
    """The guard on the drop, asserted from the side that would lose a record.

    A shard removed by hand, or by a prune whose archive would not reconcile,
    leaves the index as the only thing that remembers the month. Dropping it
    there would silently make every measurement in it new again.
    """
    state = tmp_path / "state"
    rows = [_measurement(number) for number in range(3)]
    assert writer.append(state, rows) == 3
    writer.ledger_shards(state)[0].unlink()

    assert writer.append(state, rows) == 0, "the last record of those measurements was dropped"
    assert writer.index_path(state, rows[0].date[:7]).exists()


def test_the_index_costs_a_fixed_number_of_bytes_an_observation(tmp_path: Path) -> None:
    """The measured price of the cover this row declares, held to arithmetic.

    A stamp, a comma, sixty-four hex characters and a newline. It is fixed by
    construction rather than by a corpus, which is why a count is an assertion
    here and not a measurement that drifts.
    """
    state = tmp_path / "state"
    rows = [_measurement(number) for number in range(10)]
    writer.append(state, rows)
    index = writer.index_path(state, rows[0].date[:7])

    header = ",".join(ObservationIndexRow.csv_columns()) + "\n"
    a_row = len(ObservationIndexRow.schema_version()) + 1 + 64 + 1

    assert ObservationIndexRow.csv_columns() == ("version", "observation_digest")
    assert index.stat().st_size == len(header) + 10 * a_row
    assert a_row == 76


# --- Rebuilding the observation index --------------------------------------
#
# `refresh_index` fills a month with NO index and never compares one that
# exists against the shard beside it, because comparing means reading the rows
# and reading the rows is the bill the index removes. So an index that drifted
# has no repair and no check, and the next dedupe silently admits a measurement
# the ledger already holds. `rebuild_index` is the repair; the fixture below is
# the check.
#
# The rows are committed and the disagreement is built on top of them. A
# committed index cannot say what it means for long: its digests are minted over
# `OBSERVATION_KEY`, so the day that key moves every one of them stops matching
# the rows beside it, both faults below turn into the same fault, and every
# assertion here passes on a fixture that no longer holds the shape it names.
# Rebuilding the index and then spoiling it in one direction per month costs two
# file writes and says what it means on any key. The rows are three shards and
# nothing appends to them, so the tree is fixed in size (Guardrail #12).

INDEX_REBUILD: Final = FIXTURES_DIR / "evals" / "index-rebuild"
REBUILD_MONTHS: Final = ("2026-01", "2026-02")

#: A digest no row can produce - a run of one character rather than a hash of
#: anything, which makes it impossible rather than merely unlikely.
ROLLED_BACK: Final = "f" * 64


def _index_rows(state: Path, month: str) -> list[dict[str, str]]:
    with writer.index_path(state, month).open("r", encoding="utf-8", newline="") as handle:
        return sorted(csv.DictReader(handle), key=lambda row: row["observation_digest"])


def _write_index(state: Path, month: str, rows: Sequence[dict[str, str]]) -> None:
    """One month's index, written to the file rather than through the writer.

    The writer can only mint a digest its own rows produce, and a digest the rows
    cannot produce is half of what this section is about.
    """
    with writer.index_path(state, month).open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=writer.index_columns(), lineterminator="\n")
        out.writeheader()
        out.writerows(rows)


def _drifted_tree(tmp_path: Path) -> Path:
    """The committed rows, with each month's index spoilt in one direction.

    `2026-01` gains a digest no row of that month can produce, which is what a
    restore that rolled a row back leaves behind. `2026-02` loses one its rows do
    produce, which is what a fill a crash cut short leaves behind. Two faults on
    opposite sides of the answer, so a one-directional check cannot pass.
    """
    state = tmp_path / "state"
    shutil.copytree(INDEX_REBUILD, state)
    writer.rebuild_index(state, REBUILD_MONTHS)

    grown = _index_rows(state, "2026-01")
    _write_index(state, "2026-01", [*grown, {**grown[0], "observation_digest": ROLLED_BACK}])
    _write_index(state, "2026-02", _index_rows(state, "2026-02")[1:])
    return state


def _rows_produce(state: Path, months: Sequence[str]) -> set[str]:
    """The digests the ledger's rows produce, read from the rows.

    The oracle's own arithmetic. The index is compared against this and never
    against another read of itself, which is the only comparison that can catch
    a digest the rows cannot produce.
    """
    held: set[str] = set()
    for month in months:
        with writer.ledger_path(state, month).open("r", encoding="utf-8", newline="") as handle:
            held |= {writer.observation_digest(row) for row in csv.DictReader(handle)}
    return held


def test_a_rebuilt_index_holds_exactly_the_digests_the_rows_produce(tmp_path: Path) -> None:
    """No more and no fewer, asserted in both directions.

    Two partitions, each spoilt in one direction, and both defects are real:
    `2026-01`'s index carries a digest no row of that month can produce, which
    is what a restore that rolled a row back leaves behind, and `2026-02`'s is
    missing one its rows do produce, which is what a fill a crash cut short
    leaves behind.

    **A one-directional assertion passes on an index that only ever grows**, and
    an index that only grows is what a repeated dedupe over a re-scored item
    looks like. So the fixture is checked as wrong both ways before the rebuild,
    and the equality is asserted both ways after it.
    """
    state = _drifted_tree(tmp_path)
    produced = _rows_produce(state, REBUILD_MONTHS)
    before = {digest for month in REBUILD_MONTHS for digest in _indexed(state, month)}

    assert before - produced, "the fixture held nothing the rows cannot produce"
    assert produced - before, "the fixture was missing nothing the rows do produce"

    writer.rebuild_index(state, REBUILD_MONTHS)

    after = {digest for month in REBUILD_MONTHS for digest in _indexed(state, month)}
    assert not after - produced, (
        f"the rebuilt index holds {len(after - produced)} digests the rows cannot produce"
    )
    assert not produced - after, (
        f"the rebuilt index lacks {len(produced - after)} digests the rows do produce"
    )
    assert after == produced


def test_the_rebuild_names_what_each_month_had_wrong(tmp_path: Path) -> None:
    """A repair that reported nothing would hide the drift it exists to reveal.

    One digest too many in one partition and one too few in the other, each on
    its own side of the answer - so an operator reading the log can tell an
    index that grew from one that was cut short, which are different faults with
    different causes.
    """
    state = _drifted_tree(tmp_path)
    produced = _rows_produce(state, REBUILD_MONTHS)

    found = writer.rebuild_index(state, REBUILD_MONTHS)

    assert len(found["2026-01"].extra) == 1 and not found["2026-01"].missing
    assert len(found["2026-02"].missing) == 1 and not found["2026-02"].extra
    assert found["2026-01"].extra.isdisjoint(produced), "the extra digest was one the rows produce"
    assert found["2026-02"].missing < produced, "the missing digest was not one the rows produce"


def test_rebuilding_one_month_opens_and_rewrites_only_that_month(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cover is the months the caller names, and nothing else is read.

    A rebuild reads every score row of the months it is given, which is the read
    the index exists to avoid (Guardrail #12). That is affordable because a person
    names the months; it stops being affordable the moment naming one month
    opens the archive.
    """
    state = _drifted_tree(tmp_path)
    untouched = writer.index_path(state, "2026-01").read_bytes()

    opened = _opened_bytes(monkeypatch, state, lambda: writer.rebuild_index(state, ["2026-02"]))

    assert "scores/2026-01.csv" not in opened, f"a month nobody named was read: {sorted(opened)}"
    assert "scores/2026-02.csv" in opened, "the rows of the named month were never read"
    assert writer.index_path(state, "2026-01").read_bytes() == untouched
    assert _indexed(state, "2026-02") == _rows_produce(state, ["2026-02"])


def test_a_month_with_no_committed_shard_is_refused_by_name(tmp_path: Path) -> None:
    """A typo must not read as a clean pass over nothing.

    The rule `validate-days` and `site-weight` already hold, on the store where
    getting it wrong is quietest: a rebuild that skipped an unknown month would
    print the same line as one that rewrote every month asked for. The refusal
    comes before any file is touched, so the months named beside the typo keep
    the index they had.
    """
    state = _drifted_tree(tmp_path)
    before = writer.index_path(state, "2026-02").read_bytes()

    with pytest.raises(FileNotFoundError, match="2026-03"):
        writer.rebuild_index(state, ["2026-02", "2026-03"])
    with pytest.raises(ValueError, match="no month"):
        writer.rebuild_index(state, [])

    assert writer.index_path(state, "2026-02").read_bytes() == before, (
        "a refused rebuild rewrote a month anyway"
    )


def test_the_rebuild_is_an_operator_command_and_no_scheduled_stage_calls_it(
    tmp_path: Path,
) -> None:
    """Reachable by hand, refused without a stated cover, and scheduled nowhere.

    An index that repaired itself on a schedule would hide the drift it exists
    to reveal, and the full pass reads every score row on record - which is a
    decision somebody takes out loud (Guardrail #12). So the verb appears in no
    workflow and no shell script, and the mechanism is called from one module.
    """
    state = _drifted_tree(tmp_path)
    assert cli.stage_rebuild_score_index(months=["2026-02"], state_dir=state) == 0
    assert _indexed(state, "2026-02") == _rows_produce(state, ["2026-02"])
    assert cli.stage_rebuild_score_index(months=None, state_dir=state) == 0
    assert cli.stage_rebuild_score_index(months=["2026-03"], state_dir=state) == 1

    with pytest.raises(SystemExit) as unsaid:
        cli.main(["rebuild-score-index"])
    assert unsaid.value.code == 2
    with pytest.raises(SystemExit) as both:
        cli.main(["rebuild-score-index", "--month", "2026-02", "--every-shard"])
    assert both.value.code == 2

    automated = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (
            *(REPO_ROOT / ".github" / "workflows").glob("*.y*ml"),
            *(REPO_ROOT / ".github" / "scripts").glob("*.sh"),
        )
        if "rebuild-score-index" in read_text(path)
    )
    assert not automated, f"the rebuild is a step of {automated}"

    callers = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "backend" / "idhazh").rglob("*.py")
        if "rebuild_index" in read_text(path)
    )
    assert callers == ["backend/idhazh/cli.py", "backend/idhazh/evals/writer.py"], (
        f"the rebuild is reached from {callers}"
    )


def _archive_row(number: int) -> EvalRow:
    """One eval row off the committed fixture, unique in every key field."""
    base = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    faithfulness = round(0.55 + number / 20, 4)
    return EvalRow.model_validate(
        {
            **base,
            "date": "2026-01-09",
            "run_id": "2026-01-09-1",
            "item_id": f"ai-{number:02d}",
            "url_key": hashlib.sha256(f"url-{number}".encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"out-{number}".encode("ascii")).hexdigest(),
            "hhem": faithfulness,
            "hhem_full": faithfulness,
            "hhem_delta": 0.0,
            "band": ConfidenceBand.HIGH.value
            if faithfulness >= 0.80
            else ConfidenceBand.MEDIUM.value,
            "scored_at": "2026-01-09T06:18:02Z",
        }
    )


def _write_shard(path: Path, rows: list[EvalRow]) -> None:
    names = EvalRow.csv_columns()
    with path.open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        out.writeheader()
        for row in rows:
            payload = row.model_dump(mode="json")
            out.writerow(
                {name: "" if payload[name] is None else payload[name] for name in names}
            )
