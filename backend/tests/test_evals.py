"""Unit-tier tests for the model-free counterweights.

Each test names the defect the metric exists to catch, because a metric that
cannot separate a good summary from the bad one it was written for is a
constant column - and a constant column is worse than no column, since it looks
like a measurement.

No mocks and no network (Guardrail #7). The text here is written for the test.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import (
    CONTRACT_FIXTURES_DIR,
    FIXTURES_DIR,
    read_text,
    seed_scores,
    writer_identity,
)
from pydantic import ValidationError

from idhazh import cli, ledger
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.eval_row import DROPPED_CELLS as DROPPED_EVAL_CELLS
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.knobs.extract import ExtractConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import SourceTier
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
    scorer_version,
    self_repetition,
    semantic_coverage,
    speculative_density,
    unsupported_numbers,
    verbatim_run,
    word_count,
)
from idhazh.evals.score import band, to_eval_row
from idhazh.extract import to_article_with_source
from idhazh.fetch import FetchResult


#: The writer every case below files as. `assemble` is the job that scores a
#: whole day and it runs one shard, so this is what a finished run leaves. A
#: case that needs a second writer names its own.
def a_scoring_run(date: str) -> str:
    """The run that scored one UTC day."""
    return f"{date}-1"


def put(
    state: Path,
    rows: Sequence[EvalRow],
    *,
    run_id: str | None = None,
    attempt: int = 1,
) -> int:
    """One writer's measurements, filed the way a finished run files them."""
    return seed_scores(
        state,
        rows,
        run_id=run_id if run_id is not None else a_scoring_run(rows[0].date),
        attempt=attempt,
    )


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


#: One article and one summary of it, small enough for a reader to work the
#: answer out by hand. `mars`, `rock` and `rover` are used three times each and
#: `nasa` and `tube` twice, so the five most-used content words are exactly the
#: five with a count above one and no tie-break is needed to see the reference.
#: The summary carries three of the five.
_COVERAGE_SOURCE = (
    "Mars rover drilled rock. The rover sealed a rock sample in a tube. "
    "NASA said the Mars rover will drill more rock samples on Mars, "
    "and NASA praised the tube design."
)
_COVERAGE_SUMMARY = "The rover sealed a rock sample on Mars."


def test_semantic_coverage_is_the_share_of_the_top_terms_the_summary_kept() -> None:
    """Worked by hand, so a reader can check the arithmetic without running it.

    Reference at five terms: mars 3, rock 3, rover 3, nasa 2, tube 2. The
    summary carries mars, rock and rover and drops nasa and tube, so 3 of 5.
    """
    assert semantic_coverage(_COVERAGE_SUMMARY, _COVERAGE_SOURCE, terms=5) == 0.6


def test_a_source_with_no_content_word_is_unmeasured_rather_than_zero() -> None:
    """Null and 0.0 are two different facts, and only one of them is a reading."""
    assert semantic_coverage(_COVERAGE_SUMMARY, "") is None
    assert semantic_coverage(_COVERAGE_SUMMARY, "The and of to in on at") is None


def test_semantic_coverage_stays_inside_the_zero_to_one_bound() -> None:
    """A summary can carry every reference term and cannot carry more than all."""
    assert semantic_coverage(_COVERAGE_SOURCE, _COVERAGE_SOURCE, terms=5) == 1.0
    assert semantic_coverage("nothing whatever in common", _COVERAGE_SOURCE, terms=5) == 0.0


def test_semantic_coverage_does_not_grow_with_the_article() -> None:
    """The denominator is the reference size, never the article's own length.

    Recall against the whole article is the shape this replaced: it falls as the
    article lengthens whatever the summary says, which is a length measure
    wearing a quality measure's name. A few new words the summary does not use
    are enough to show that none displace a term the article keeps returning to.
    """
    padding = " ".join(f"filler{index}" for index in range(3))
    unchanged = semantic_coverage(_COVERAGE_SUMMARY, f"{_COVERAGE_SOURCE} {padding}", terms=5)

    assert unchanged == semantic_coverage(_COVERAGE_SUMMARY, _COVERAGE_SOURCE, terms=5) == 0.6


def test_a_dropped_hedge_caps_high_at_medium() -> None:
    assert (
        band(0.99, unsupported_numbers=0, hedge_dropped=True, config=EvaluationConfig())
        is ConfidenceBand.MEDIUM
    )


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

    Same length, same 4-gram overlap with the article, same longest copied run.
    Three numbers that cannot separate a summary that said one thing three times
    from a summary that said three things.
    """
    assert word_count(LOOPED) == word_count(CONTROL) == 26
    assert extractiveness(LOOPED, ARTICLE) == extractiveness(CONTROL, ARTICLE)
    assert verbatim_run(LOOPED, ARTICLE) == verbatim_run(CONTROL, ARTICLE)

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
    that runs this suite and no test may fetch them (Guardrail #7), so what is proved
    here is the plumbing: the same faithfulness number goes in for both
    summaries and the same number comes out, while the new column separates
    them.
    """
    item = RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")).items[
        0
    ]
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
    assert control.semantic_coverage == looped.semantic_coverage
    assert control.band == looped.band

    assert control.self_repetition == 0.0
    assert looped.self_repetition is not None
    assert looped.self_repetition > 0.0


def test_a_row_still_carrying_the_two_retired_cells_reads_through_the_migration() -> None:
    """The read-side migration `CLAUDE.md` section 11 owes a removed column.

    A work shard seals one `.eval.json` per item and two later jobs read it back
    hours afterwards, so a column that leaves the row in between is a key
    `extra="forbid"` would refuse - and the run that wrote the payload would lose
    its whole day. The fixture is the wide shape as it stood before the
    narrowing: the two cells are put back onto a committed payload by hand.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    wide = {**payload, "coverage": 0.62, "new_fact_rate": 0.5}

    row = EvalRow.model_validate(wide)

    assert not hasattr(row, "coverage")
    assert not hasattr(row, "new_fact_rate")
    assert row.hhem == payload["hhem"], "the rest of the row survives the drop"
    assert {"coverage", "new_fact_rate"} == DROPPED_EVAL_CELLS


def test_a_committed_shard_under_the_wide_header_still_parses_row_by_row() -> None:
    """The CSV half of the same migration, driven from a bounded fixture.

    A day file an earlier run wrote names both retired headings in its header
    line. `from_csv_row` has to place the cells it still knows and drop the two
    it does not, because the one-time move onto the ledger door reads every old
    CSV day of the eval ledger through it.
    """
    row = EvalRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    wide_cells = {**row.csv_row(), "coverage": "0.62", "new_fact_rate": "0.5"}

    read_back = EvalRow.from_csv_row(wide_cells)

    assert read_back.hhem == row.hhem
    assert read_back.csv_row().keys() == set(EvalRow.csv_columns())


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
    item = RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")).items[
        0
    ]
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
    assert row.source_words_before_cap == article.source_word_count == 5240
    assert row.source_words == article.word_count == 4310
    assert row.source_words < row.source_words_before_cap, "930 words never reached the model"


def test_an_untruncated_article_reads_the_same_length_twice() -> None:
    """Equal is the truth here: the whole article IS the text the model saw."""
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    row = _row_for(article)

    assert not article.truncated
    assert row.source_words_before_cap == row.source_words == 1320


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

    assert other.source_words_before_cap == row.source_words_before_cap
    assert other.source_words == row.source_words


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
    assert row.source_words_before_cap is None
    assert row.source_words == 4310, "the seen count is still a measurement"


def test_an_old_payload_that_was_never_cut_knows_its_own_length() -> None:
    """The same recovery the ledger migration makes, at the writer.

    Nothing was cut, so the article IS the text the model saw and the two counts
    are equal by construction. Refusing to say so would throw away a fact.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    row = _row_for(article.model_copy(update={"source_word_count": None}))

    assert not article.truncated
    assert row.source_words_before_cap == row.source_words == 1320


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
    """The captured page through the real extractor, at the cap this case asks for.

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

    The rule this replaces needed a gap above 0.100 and this case hands it 0.000,
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
    """Nothing in `metrics.py` moved for this column, so the constant may not either.

    `METRICS_VERSION` sits inside `scorer_version`, and a new scorer version
    restarts the ten-run-day count `docs/concepts/evaluation.md` requires before
    any threshold may move. `truncation_flagged` is not a `band()` input and no
    derived column reads it, so the stamp did not move for it.
    """
    assert METRICS_VERSION == "4"


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
        version == f"hhem-2.1-open@a1b2c3d4;weights-9f8e7d6c;metrics-{METRICS_VERSION};"
        "window=900/150/anchored;bands=0.80/0.50"
    )


def test_the_counterweights_version_moved_when_the_set_of_counterweights_did() -> None:
    """`METRICS_VERSION` names the definitions in `metrics.py`, and the set changed.

    It stayed at 3 through a window geometry change and two added columns,
    because none of those changed what an existing column meant. It moves to 4
    because two columns LEFT and two arrived, so a row cannot be read as if it
    came from the same set of instruments.
    """
    assert METRICS_VERSION == "4"


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


def test_the_scorer_version_no_longer_names_a_counterweight_nothing_reads() -> None:
    """It carried a `lead=` component until 2026-09-24.

    The band input behind it is retired, so the string stops naming it - which
    moves every row's `scorer_version` once and restarts the run-day count in
    `evaluation.label_min_run_days`. Pinned here so a later change that puts a
    dead threshold back into the stamp fails rather than lands.
    """
    stamp = scorer_version(
        scorer_id="hhem-2.1-open",
        scorer_revision="a1b2c3d4e5f6",
        weights_sha256="9f8e7d6c" + "0" * 56,
        evaluation=EvaluationConfig(),
    )
    assert "lead=" not in stamp
    assert stamp.endswith("bands=0.80/0.50")


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


# --- The observation digest --------------------------------------------------


def test_an_observation_digest_cannot_be_forged_by_moving_a_separator() -> None:
    """The scorer version carries semicolons and slashes, so a join is not a key.

    Two different observations whose values differ only in where a separator
    falls must digest differently. A `"|".join` would give them one digest and
    silently drop the second measurement for ever.
    """

    def observed(url_key: str, output_digest: str) -> dict[str, str]:
        return {
            "url_key": url_key,
            "output_digest": output_digest,
            "scorer_version": "hhem-2.2-open@cccccccc;metrics-4",
        }

    left = writer.observation_digest(observed("a;b", "c"))
    right = writer.observation_digest(observed("a", "b;c"))

    assert left != right
    assert writer.observation_digest(observed("a;b", "c")) == left, "the digest is not stable"


def test_the_lookup_keeps_every_filed_day_and_scorer(tmp_path: Path) -> None:
    """Distinct scorer identities survive filing, including rows from different months."""
    january = [_measurement(number) for number in range(6)]
    february = [
        row.model_copy(update={"date": "2026-02-03", "run_id": "2026-02-03-1"})
        for row in (_measurement(80), _measurement(81))
    ]
    retaken = january[0].model_copy(update={"scorer_version": "hhem-2.2-open@cccccccc;metrics-4"})
    rows = [*january, retaken, *february]
    state = tmp_path / "state"
    expected = {writer.observation_digest(row.model_dump(mode="json")) for row in rows}

    assert len(expected) == len(rows), "the fixture repeated an observation"
    assert put(state, rows) == len(rows)

    produced = {writer.observation_digest(record) for record in writer.records(state)}
    assert produced == expected
    assert writer.recorded_observations(state, expected) == expected
    assert ledger.held_days(state, LedgerName.SUMMARY_QUALITY_EVALS) == [
        "2026-01-09",
        "2026-02-03",
    ]


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
    """One fixture-backed eval row with distinct item and measurement identities."""
    return _scored_row(0).model_copy(
        update={
            "item_id": f"ai-{number:05d}",
            "url_key": hashlib.sha256(f"index-url-{number}".encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"index-out-{number}".encode("ascii")).hexdigest(),
        }
    )


#: Who files the rows `_seeded` lays down: a writer of its own, so its file is
#: never taken for a later write of the work unit `put` files as.
ROWS_ONLY_PRODUCER: Final = "tests.test_evals:rows-only"


def _seeded(state: Path, rows: list[EvalRow], *, copies: int = 1) -> None:
    """A ledger holding `rows` with no index beside them, each row filed `copies` times.

    Filed through the ledger door and not through the writer, so no digest is
    minted: this is what a day looks like when its rows arrived from something
    that never knew the index existed. More than one copy is a real state, not a
    contrivance: two writers of one day can each file the same observation, and
    the reader settles them. It is also the case that separates "the read grows
    with the rows" from "the read grows with the measurements".
    """
    ledger.persist(
        state,
        [row for row in rows for _ in range(copies)],
        ledger=LedgerName.SUMMARY_QUALITY_EVALS,
        covers=rows[0].date,
        identity=writer_identity(a_scoring_run(rows[0].date), producer=ROWS_ONLY_PRODUCER),
    )


def _day_digests(state: Path, date: str) -> set[str]:
    """The distinct observations one day's rows hold, derived from the rows.

    The one read of the score rows in this section, and it is here so a test can
    say what the index is supposed to mirror without asking the index.
    """
    return {
        writer.observation_digest(row.model_dump(mode="json"))
        for row in ledger.load_days(state, LedgerName.SUMMARY_QUALITY_EVALS, [date], model=EvalRow)
    }


def test_a_repeat_is_still_refused_when_the_index_is_the_only_thing_read(tmp_path: Path) -> None:
    """The invariant. Nothing about how the answer is stored may move it.

    Same address, same pipeline, same words, same scorer is the same
    measurement, and the ledger counts measurements rather than times the
    pipeline looked.
    """
    state = tmp_path / "state"
    rows = [_measurement(number) for number in range(4)]

    assert put(state, rows) == 4
    assert put(state, rows) == 0, "a measurement already held came back as new"
    assert put(state, [_measurement(9)]) == 1, "a new measurement was refused"

    expected = {
        writer.observation_digest(row.model_dump(mode="json"))
        for row in [*rows, _measurement(9)]
    }
    assert {writer.observation_digest(record) for record in writer.records(state)} == expected
    assert writer.recorded_observations(state, expected) == expected


def test_a_repeat_across_months_is_not_a_new_measurement(tmp_path: Path) -> None:
    state = tmp_path / "state"
    original = _measurement(0)
    later = original.model_copy(update={"date": "2026-02-03", "run_id": "2026-02-03-1"})

    assert put(state, [original]) == 1
    assert put(state, [later]) == 0
    assert list(writer.records(state)) == [original.csv_row()]


def test_two_copies_in_one_batch_are_filed_once(tmp_path: Path) -> None:
    state = tmp_path / "state"
    row = _measurement(0)

    assert put(state, [row, row]) == 1
    assert list(writer.records(state)) == [row.csv_row()]


def test_candidate_lookup_returns_only_requested_recorded_ids(tmp_path: Path) -> None:
    state = tmp_path / "state"
    rows = [_measurement(number) for number in range(3)]
    assert put(state, rows) == 3
    held = writer.observation_digest(rows[0].model_dump(mode="json"))
    absent = writer.observation_digest(_measurement(9).model_dump(mode="json"))

    assert writer.recorded_observations(state, iter([held, absent, held])) == {held}
    assert writer.recorded_observations(state, []) == set()


def test_candidate_lookup_refuses_a_missing_index(tmp_path: Path) -> None:
    candidate = writer.observation_digest(_measurement(0).model_dump(mode="json"))

    with pytest.raises(FileNotFoundError):
        writer.recorded_observations(tmp_path / "state", [candidate])


def test_the_writers_read_does_not_grow_with_the_rows_the_day_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guardrail #12, as bytes rather than as a clock.

    Two trees hold the same two measurements. One carries each row once, the
    other carries it ten more times in a second writer's file, so the rows are
    eleven times the bytes and the identities are identical. What the writer
    opens has to be the same figure, and the score rows have to be absent from
    it entirely.
    """
    rows = [_measurement(number) for number in range(2)]
    lean = tmp_path / "lean" / "state"
    fat = tmp_path / "fat" / "state"
    for state in (lean, fat):
        put(state, rows)  # the rows and the index the writer minted beside them
    _seeded(fat, rows, copies=10)  # the same two measurements, ten times the rows

    candidates = {writer.observation_digest(rows[0].model_dump(mode="json"))}
    thin = _opened_bytes(monkeypatch, lean, lambda: writer.recorded_observations(lean, candidates))
    thick = _opened_bytes(monkeypatch, fat, lambda: writer.recorded_observations(fat, candidates))

    rows_live_under = [
        f"{tier}/{LedgerName.SUMMARY_QUALITY_EVALS.value}/"
        for tier in (ledger.paths.RAW_DIRNAME, ledger.paths.COMPACT_DIRNAME)
    ]
    opened_there = [name for name in thick if name.startswith(tuple(rows_live_under))]
    assert not opened_there, f"the writer opened {opened_there}, which is what this row removes"
    assert sorted(thin.values()) == sorted(thick.values()), (
        "the writer's read moved with the rows: "
        f"{sum(thin.values())} B against {sum(thick.values())} B over the same two measurements"
    )
    assert sum(thick.values()) > 0, "the writer read nothing at all, so this proves nothing"


def test_a_tree_with_rows_and_no_index_requires_explicit_migration(tmp_path: Path) -> None:
    """Unindexed history must not silently admit measurements it already holds."""
    rows = [_measurement(number) for number in range(5)]
    state = tmp_path / "state"
    _seeded(state, rows)
    before = list(writer.records(state))

    with pytest.raises(FileNotFoundError, match="explicit observation lookup migration"):
        put(state, rows)

    assert list(writer.records(state)) == before


def test_an_append_keeps_every_filed_days_observations_recorded(tmp_path: Path) -> None:
    """Every persisted row remains findable after several batches across months."""
    state = tmp_path / "state"
    january = [_measurement(number) for number in range(4)]
    february = [
        row.model_copy(update={"date": "2026-02-03", "run_id": "2026-02-03-1"})
        for row in (_measurement(80), _measurement(81))
    ]

    assert put(state, january) == 4
    assert put(state, january) == 0, "a held measurement came back as new"
    assert put(state, february) == 2

    days = ledger.held_days(state, LedgerName.SUMMARY_QUALITY_EVALS)
    assert days == ["2026-01-09", "2026-02-03"], f"both days were not written: {days}"
    for date in days:
        candidates = _day_digests(state, date)
        assert writer.recorded_observations(state, candidates) == candidates


@pytest.mark.parametrize("options", [[], ["--month", "2026-02"], ["--every-shard"]])
def test_the_retired_rebuild_command_is_refused(
    options: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """A global identity lookup cannot report extra identities for one day."""
    with pytest.raises(SystemExit) as retired:
        cli.main(["rebuild-summary-quality-evals-index", *options])

    assert retired.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert "rebuild-summary-quality-evals-index" not in cli.STAGES


def test_the_retired_rebuild_options_are_not_advertised(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as help_requested:
        cli.main(["--help"])

    assert help_requested.value.code == 0
    help_text = capsys.readouterr().out
    assert "rebuild-summary-quality-evals-index" not in help_text
    assert "--month" not in help_text
    assert "--every-shard" not in help_text


def _scored_row(number: int) -> EvalRow:
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
