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
from typing import Final

from conftest import FIXTURES_DIR

from idhazh import config
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.evals import writer
from utilities import build_canary_day

EVALUATION: Final = config.load().app.evaluation
BANDS: Final = config.load().app.summarize.bands
ITEMS: Final = build_canary_day.published_items(EVALUATION, FIXTURES_DIR / "canaries")
ROWS: Final = build_canary_day.score_rows(ITEMS, EVALUATION)
#: The rows the compression plot can place. A row with no recorded article
#: length has no x, so the plot drops it and says how many it dropped.
PLOTTED: Final = [row for row in ROWS if row.source_word_count is not None]


def source_words(row: EvalRow) -> int:
    """The article's length before the cut, where the fixture recorded one.

    `EvalRow.source_word_count` is nullable because a row written before
    2026-08-27 whose article was truncated has no full length anywhere. Two
    fixture rows are in that state on purpose - it is the state the sentence
    under the plot counts - so every caller here reads `PLOTTED` and a None
    reaching this function is a broken fixture rather than a row the chart has
    to survive.
    """
    assert row.source_word_count is not None, f"{row.item_id} records no article length"
    return row.source_word_count


def test_every_published_item_is_scored() -> None:
    """A day whose ledger names items the digest does not carry disagrees with itself."""
    assert [row.item_id for row in ROWS] == [item.item_id for item in ITEMS]
    assert {row.date for row in ROWS} == {build_canary_day.DATE}


def test_the_published_band_and_the_ledger_band_agree() -> None:
    """Two files, one judgement. The console and the digest page read different ones."""
    assert [row.band for row in ROWS] == [item.band for item in ITEMS]


def test_the_fixture_covers_every_confidence_band() -> None:
    assert {row.band for row in ROWS} == set(ConfidenceBand)


def test_a_truncated_item_is_drawn_and_an_untruncated_one_is_too() -> None:
    """The plot marks the two differently, so a fixture needs both.

    Counted over the rows the plot can place, not over every row the day scored.
    A flagged row with no length before the cut has no x, so it is a cut the
    ledger records and not a diamond the plot draws. The day holds one of those,
    and over `ROWS` this test would pass on a fixture whose every flagged row was
    unplaceable - a plot drawing no diamond at all.
    """
    flagged = [row for row in PLOTTED if row.truncation_flagged]
    assert flagged, "no row draws a truncation diamond"
    assert len(flagged) < len(PLOTTED), "every row draws a diamond, so no row draws a dot"


def test_the_truncation_flag_follows_the_configured_rule() -> None:
    """The flag says extract cut the body, so the two length columns must agree.

    This is the whole rule now. It used to be checked against a faithfulness gap
    as well, and that second check was the defect: the gap is a score difference
    and this column names a cut, so a row could satisfy one and contradict the
    other. Over the committed ledger it did - the flag was true on exactly one
    row, and that row read 748 words of a 748-word article.
    """
    for row in PLOTTED:
        # A cut page is a page the model saw less of. The two columns are the
        # only record of how much less, and a row missing one of them says
        # nothing about the cut either way.
        assert (row.source_seen_word_count < source_words(row)) == row.truncation_flagged


def test_some_rows_record_no_article_length_and_still_score() -> None:
    """The state the sentence under the plot exists to declare.

    A row without a pre-cap length has no x, so the chart drops it. Dropping it
    silently is the failure: the plot would under-report its own gaps and every
    count printed beside it would be over a denominator nobody stated. Two rows,
    not one, so a page printing whatever number it found cannot pass by luck.
    """
    unrecorded = [row for row in ROWS if row.source_word_count is None]
    assert len(unrecorded) == 2, "the plot has no unplaceable row to report"
    assert len(PLOTTED) == len(ROWS) - 2
    # One either side of the cut. Cut and unplaceable together is the real
    # historical state - a row written before the pre-cap length was persisted
    # has no full length to recover - and it is the row the day's count holds
    # while the plot drops it, so the two figures differ on purpose.
    cut = [row for row in unrecorded if row.truncation_flagged]
    assert len(cut) == 1, "no unplaceable row is cut, so the two figures cannot differ"
    for row in unrecorded:
        # It scored, it banded, and the model read something. Only the length
        # before the cut is missing.
        assert row.source_seen_word_count > 0
        assert row.summary_word_count > 0


def test_source_lengths_cross_more_than_one_decade() -> None:
    """The x axis is a log one and labels whole decades, so one decade labels once."""
    lengths = [source_words(row) for row in PLOTTED]
    assert min(lengths) * 10 < max(lengths)


def test_every_configured_target_zone_carries_a_mark() -> None:
    """The zone is drawn as a step across every band, so every step needs a point.

    A step with nothing under it is a rule the chart states and the fixture
    never tests it against.
    """
    floors = sorted(band.min_source_words for band in BANDS)
    assert len(floors) > 1, "the config has one target zone, so this asserts nothing"
    for index, floor in enumerate(floors):
        ceiling = floors[index + 1] if index + 1 < len(floors) else None
        under = [
            row
            for row in PLOTTED
            if source_words(row) >= floor and (ceiling is None or source_words(row) < ceiling)
        ]
        assert under, f"no scored item sits in the target zone above {floor} source words"


def test_a_summary_stays_inside_the_axis_the_chart_draws() -> None:
    """The y domain is zero to the longest summary, capped by the configured limit."""
    for row in ROWS:
        assert 0 < row.summary_word_count <= EVALUATION.summary_words_max


def test_the_ledger_header_is_the_contract(tmp_path: Path) -> None:
    """Written by the pipeline's writer, so the column order cannot be invented here."""
    build_canary_day.scores(tmp_path, ITEMS, EVALUATION)

    assert writer.read_header(writer.ledger_path(tmp_path)) == EvalRow.csv_columns()


def test_a_fresh_run_writes_the_same_ledger_every_time(tmp_path: Path) -> None:
    """The rows are a function of the fixture, never of how often it was built."""
    written = []
    for index in range(3):
        state = tmp_path / f"run-{index}"
        assert build_canary_day.scores(state, ITEMS, EVALUATION) == len(ITEMS)
        written.append(writer.ledger_path(state).read_bytes())

    assert written[0] == written[1] == written[2]


def test_appending_the_same_day_twice_adds_nothing(tmp_path: Path) -> None:
    """The second write is the same measurement, so the writer drops it.

    The builder clears its state directory before writing, so this is the belt
    behind that brace: a ledger that survived the clear still cannot double.
    """
    ledger = writer.ledger_path(tmp_path)
    assert build_canary_day.scores(tmp_path, ITEMS, EVALUATION) == len(ITEMS)
    once = ledger.read_bytes()

    assert build_canary_day.scores(tmp_path, ITEMS, EVALUATION) == 0
    assert ledger.read_bytes() == once
