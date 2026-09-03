"""Unit-tier tests for the model-free counterweights.

Each test names the defect the metric exists to catch, because a metric that
cannot separate a good summary from the bad one it was written for is a
constant column - and a constant column is worse than no column, since it looks
like a measurement.

No mocks and no network (Rule #7). The text here is written for the test.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.app_config import EvaluationConfig, ExtractConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.run_plan import PlannedItem, RunPlan
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


def test_the_ledger_row_carries_the_repetition_and_leaves_faithfulness_alone() -> None:
    """The wiring, and the one metric this suite cannot compute itself.

    `hhem` is a model score handed to the scorer, never recomputed from the
    summary, so a loop cannot move it. HHEM's weights are not on the machine
    that runs this suite and no test may fetch them (Rule #7), so what is proved
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
    faithfulness floor read off a moving instrument measures nothing (Rule #10)."""
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
