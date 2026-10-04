"""The canary day's score ledger - the fixture the console's compression plot draws.

The browser suite runs against this day, so a state the fixture does not carry
is a state that suite cannot test. The plot draws source words against summary
words on a log x axis, shades the configured target zone behind the marks, and
draws a diamond where the scorer flagged truncation. Each of those needs a row
of the right shape, and none of them had one while the day carried no scored
item at all.

These assertions are about the fixture's shape rather than its numbers. A value
in `SCORED` is a fixture and may be edited; a fixture that stopped exercising a
state the chart can draw is the defect this file guards against.
"""

from __future__ import annotations

from pathlib import Path

from conftest import FIXTURES_DIR

from idhazh import config, ledger
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.sources import SourceForm
from utilities import build_canary_day


def evaluation() -> EvaluationConfig:
    """The committed evaluation settings the day is scored under."""
    return config.load().app.evaluation


def published() -> list[DigestItem]:
    """The day's published items, read off the canary fixtures by the test that asks."""
    return build_canary_day.published_items(evaluation(), FIXTURES_DIR / "canaries")


def scored() -> list[EvalRow]:
    """The day's score rows, one per published item."""
    return build_canary_day.score_rows(published(), evaluation())


def plotted() -> list[EvalRow]:
    """The rows the compression plot can place.

    A row with no recorded article length has no x, so the plot drops it and
    says how many it dropped.
    """
    return [row for row in scored() if row.source_words_before_cap is not None]


def source_words(row: EvalRow) -> int:
    """The article's length before the cut, where the fixture recorded one.

    `EvalRow.source_words_before_cap` is nullable because a row written before
    2026-08-27 whose article was truncated has no full length anywhere. Two
    fixture rows are in that state on purpose - it is the state the sentence
    under the plot counts - so every caller here reads `plotted()` and a None
    reaching this function is a broken fixture rather than a row the chart has
    to survive.
    """
    assert row.source_words_before_cap is not None, f"{row.item_id} records no article length"
    return row.source_words_before_cap


def test_every_published_item_is_scored() -> None:
    """A day whose ledger names items the digest does not carry disagrees with itself."""
    rows = scored()
    assert [row.item_id for row in rows] == [item.item_id for item in published()]
    assert {row.date for row in rows} == {build_canary_day.DATE}


def test_the_eight_item_day_has_a_rendered_chart_after_the_canary_seed(tmp_path: Path) -> None:
    settings = config.load()
    day = build_canary_day.build(tmp_path / "digest", settings.app.evaluation, settings.app.visuals)
    assert len(day.items) == 8
    item = next(item for item in day.items if item.item_id == "ai-04")
    assert item.visual is not None
    assert item.visual.kind == "chart"
    assert item.visual.state == "rendered"
    assert item.visual.data_path == "digest/2026/08/20/ai-04.json"
    assert (tmp_path / item.visual.data_path).is_file()


def test_the_published_band_and_the_ledger_band_agree() -> None:
    """Two files, one judgement. The console and the digest page read different ones."""
    assert [row.band for row in scored()] == [item.band for item in published()]


def test_the_fixture_covers_every_confidence_band() -> None:
    assert {row.band for row in scored()} == set(ConfidenceBand)


def test_a_truncated_item_is_drawn_and_an_untruncated_one_is_too() -> None:
    """The plot marks the two differently, so a fixture needs both.

    Counted over the rows the plot can place, not over every row the day scored.
    A flagged row with no length before the cut has no x, so it is a cut the
    ledger records and not a diamond the plot draws. The day holds one of those,
    and over every scored row this test would pass on a fixture whose every
    flagged row was unplaceable - a plot drawing no diamond at all.
    """
    placed = plotted()
    flagged = [row for row in placed if row.truncation_flagged]
    assert flagged, "no row draws a truncation diamond"
    assert len(flagged) < len(placed), "every row draws a diamond, so no row draws a dot"


def test_the_truncation_flag_follows_the_configured_rule() -> None:
    """The flag says extract cut the body, so the two length columns must agree.

    This is the whole rule now. It used to be checked against a faithfulness gap
    as well, and that second check was the defect: the gap is a score difference
    and this column names a cut, so a row could satisfy one and contradict the
    other. Over the committed ledger it did - the flag was true on exactly one
    row, and that row read 748 words of a 748-word article.
    """
    for row in plotted():
        # A cut page is a page the model saw less of. The two columns are the
        # only record of how much less, and a row missing one of them says
        # nothing about the cut either way.
        assert (row.source_words < source_words(row)) == row.truncation_flagged


def test_some_rows_record_no_article_length_and_still_score() -> None:
    """The state the sentence under the plot exists to declare.

    A row without a pre-cap length has no x, so the chart drops it. Dropping it
    silently is the failure: the plot would under-report its own gaps and every
    count printed beside it would be over a denominator nobody stated. Two rows,
    not one, so a page printing whatever number it found cannot pass by luck.
    """
    rows = scored()
    unrecorded = [row for row in rows if row.source_words_before_cap is None]
    assert len(unrecorded) == 2, "the plot has no unplaceable row to report"
    assert len(plotted()) == len(rows) - 2
    # One either side of the cut. Cut and unplaceable together is the real
    # historical state - a row written before the pre-cap length was persisted
    # has no full length to recover - and it is the row the day's count holds
    # while the plot drops it, so the two figures differ on purpose.
    cut = [row for row in unrecorded if row.truncation_flagged]
    assert len(cut) == 1, "no unplaceable row is cut, so the two figures cannot differ"
    for row in unrecorded:
        # It scored, it banded, and the model read something. Only the length
        # before the cut is missing.
        assert row.source_words > 0
        assert row.summary_words > 0


def test_source_lengths_cross_more_than_one_decade() -> None:
    """The x axis is a log one and labels whole decades, so one decade labels once."""
    lengths = [source_words(row) for row in plotted()]
    assert min(lengths) * 10 < max(lengths)


def test_every_configured_target_zone_carries_a_mark() -> None:
    """The zone is drawn as a step across every band, so every step needs a point.

    A step with nothing under it is a rule the chart states and the fixture
    never tests it against.
    """
    floors = sorted(band.min_source_words for band in config.load().app.summarize.bands)
    placed = plotted()
    assert len(floors) > 1, "the config has one target zone, so this asserts nothing"
    for index, floor in enumerate(floors):
        ceiling = floors[index + 1] if index + 1 < len(floors) else None
        under = [
            row
            for row in placed
            if source_words(row) >= floor and (ceiling is None or source_words(row) < ceiling)
        ]
        assert under, f"no scored item sits in the target zone above {floor} source words"


def test_a_summary_stays_inside_the_axis_the_chart_draws() -> None:
    """The y domain is zero to the longest summary the ladder can publish."""
    ceiling = config.load().app.summarize.decoder_words_max()
    for row in scored():
        assert 0 < row.summary_words <= ceiling


def test_the_digest_and_the_ledger_agree_on_which_items_were_cut() -> None:
    """One rule, two files. A reader is told what the console counts."""
    items = published()
    assert [item.truncated for item in items] == [row.truncation_flagged for row in scored()]
    assert any(item.truncated for item in items), "no published item was cut"


def test_one_published_item_is_both_an_abstract_and_cut() -> None:
    """The note joins a sentence per limit, and nothing rendered the pair.

    Nothing in extract exempts an abstract from the cap, so the two facts can
    land on one real item. They never have: measured 2026-08-29 over every
    committed `frontend/public/digest/**/digest.json`, no published item carries
    an abstract note at all. Without this row the joined sentence has a unit test
    and no page, so no browser can read back what a reader would meet.

    Exactly one, because the browser suite addresses it and two would make the
    assertion there depend on which one Playwright found first.
    """
    both = [
        item
        for item in published()
        if item.source_form is SourceForm.ABSTRACT and item.truncated
    ]

    assert len(both) == 1, "no published item is both an abstract and cut"
    # Composed by `assemble.reader_note`, never spelled in the builder. The share
    # is 2,100 words of 2,800, which is the cap over this row's `source_words`.
    assert both[0].reader_note == (
        "This is a summary of the paper's abstract. The full paper is a PDF. "
        "We could only read the first 75 percent of this page."
    )


def filed_rows(state: Path) -> list[EvalRow]:
    """The day's score rows as the ledger door reads them back."""
    return ledger.load_days(state, LedgerName.SUMMARY_QUALITY_EVALS, [build_canary_day.DATE], model=EvalRow)


def test_the_scores_are_filed_by_the_pipelines_writer(tmp_path: Path) -> None:
    """Filed by the writer the pipeline files with, so no shape can be invented here.

    The rows read back through the ledger door are the rows the builder scored,
    field for field.
    """
    rows = scored()
    assert build_canary_day.file_scores(tmp_path, published(), evaluation()) == len(rows)

    assert filed_rows(tmp_path) == rows


def test_a_fresh_run_writes_the_same_ledger_every_time(tmp_path: Path) -> None:
    """The rows are a function of the fixture, never of how often it was built.

    Compared as the rows the door reads back rather than as bytes, because each
    raw file names the instant it was written.
    """
    items, settings = published(), evaluation()
    written = []
    for index in range(3):
        state = tmp_path / f"run-{index}"
        assert build_canary_day.file_scores(state, items, settings) == len(items)
        written.append(filed_rows(state))

    assert written[0] == written[1] == written[2]


def test_filing_the_same_day_twice_reads_back_the_same_rows(tmp_path: Path) -> None:
    """The second write is the same work unit, so a read takes it in place of the first.

    The builder clears its state directory before writing, so this is the belt
    behind that brace: a ledger that survived the clear still cannot double.
    """
    items, settings = published(), evaluation()
    assert build_canary_day.file_scores(tmp_path, items, settings) == len(items)
    once = filed_rows(tmp_path)

    assert build_canary_day.file_scores(tmp_path, items, settings) == len(items)
    assert filed_rows(tmp_path) == once
