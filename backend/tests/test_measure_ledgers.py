"""The three ledger figures, each checked against a second, independent expression.

A single expression cannot catch its own error, so every figure here is computed
twice: once by `measure_ledgers` and once by arithmetic written a different way -
the stdlib's own least squares for the regression, a counting definition for the
percentile, and a positional re-read of the fixture for the clocks.

The fixture is a small ledger of four runs designed so each branch has exactly
one witness: one run proven at the cap by its eval stamp, one by a row cut on the
ceiling, one proven by neither, and one whose shard filed no clock. One of the
four names its shard on every row and so splits per shard; the rest predate the
column and read as whole runs.
"""

from __future__ import annotations

import csv
import statistics
from collections.abc import Sequence
from typing import Final

from conftest import CONFIG_DIR, FIXTURES_DIR, STATE_DIR

from idhazh import config
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from utilities.measure_ledgers import (
    UPPER_PERCENTILE,
    Residual,
    ShardClock,
    WordsToTokens,
    admissions,
    ceiling_words,
    percentile,
    read_items,
    report,
    shard_clocks,
    sized_pairs,
    stamps_by_run,
)

LEDGERS: Final = FIXTURES_DIR / "state" / "measure-ledgers"
#: The fixture is written against this cap, so its ceiling is 3846 words and the
#: run that proves itself by a cut has a row sitting exactly there.
CAP_TOKENS: Final = 5000


def clock_for(scope: str) -> ShardClock:
    return next(c for c in shard_clocks(LEDGERS, read_items(LEDGERS)) if c.scope == scope)


def fixture_rows() -> list[list[str]]:
    """The item ledger re-read positionally, which shares no code with `read_items`."""
    with (LEDGERS / "item-health" / "2026-01.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))[1:]


def admitted_pairs() -> list[tuple[int, int]]:
    items = read_items(LEDGERS)
    admitted = [a.run_id for a in admissions(LEDGERS, items, cap_tokens=CAP_TOKENS) if a.admitted]
    return sized_pairs(items, admitted)


def naive_percentile(values: Sequence[int], share: float) -> int:
    """The smallest value at least `share` of the sample sits at or under.

    Written as a search rather than as a rank, so it cannot repeat a rounding
    mistake made in `percentile`.
    """
    ordered = sorted(values)
    for value in ordered:
        if sum(1 for other in ordered if other <= value) / len(ordered) >= share:
            return value
    raise AssertionError("a percentile of a non-empty sample always exists")


def test_the_fixture_only_names_columns_the_real_ledgers_have() -> None:
    pairs = (
        ("item-health/2026-01.csv", ItemHealthRow.csv_columns()),
        ("runtime-counters.csv", RuntimeCountersRow.csv_columns()),
        ("scores/2026-01.csv", EvalRow.csv_columns()),
    )
    for relpath, columns in pairs:
        with (LEDGERS / relpath).open(encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle))
        assert set(header) <= set(columns), relpath


def test_the_unaccounted_seconds_are_the_job_clocks_minus_the_item_milliseconds() -> None:
    shard_zero = clock_for("2026-01-01-2 shard 0")
    shard_one = clock_for("2026-01-01-2 shard 1")
    milliseconds = sum(
        int(row[3]) + int(row[4]) + int(row[5])
        for row in fixture_rows()
        if row[1] == "2026-01-01-2"
    )

    assert shard_zero.job_seconds == 100
    assert shard_one.job_seconds == 200
    assert milliseconds == 250_000
    assert shard_zero.accounted_seconds + shard_one.accounted_seconds == milliseconds / 1000
    assert shard_zero.unaccounted_seconds == 14.0
    assert shard_one.unaccounted_seconds == 36.0
    assert shard_zero.unaccounted_share == 14.0 / 100
    assert shard_one.model_share == 160.0 / 200
    assert shard_zero.joinable and shard_one.joinable


def test_a_run_whose_rows_name_no_shard_reads_as_one_whole_run() -> None:
    """`shard` landed 2026-08-30, so every older row is empty and reads at run grain."""
    scopes = {clock.scope for clock in shard_clocks(LEDGERS, read_items(LEDGERS))}

    assert "2026-01-01-2" not in scopes
    assert {"2026-01-01-2 shard 0", "2026-01-01-2 shard 1"} <= scopes
    assert {"2026-01-01-1", "2026-01-01-3"} <= scopes
    assert clock_for("2026-01-01-1").shard is None


def test_a_shard_scraped_twice_leaves_the_two_ledgers_unjoinable() -> None:
    clock = clock_for("2026-01-01-3")

    assert clock.counter_rows == 3
    assert clock.distinct_shards == 2
    assert not clock.joinable
    assert "a shard was re-run" in clock.verdict


def test_items_claiming_more_time_than_the_shard_clocks_hold_is_not_a_measurement() -> None:
    clock = clock_for("2026-01-01-1")

    assert clock.unaccounted_seconds < 0
    assert not clock.joinable
    assert "filed no clock" in clock.verdict


def test_a_shard_row_with_an_empty_clock_produces_no_reading() -> None:
    clocked = {clock.run_id for clock in shard_clocks(LEDGERS, read_items(LEDGERS))}

    assert "2026-01-01-4" not in clocked
def test_the_residual_matches_a_second_expression_over_the_same_rows() -> None:
    residual = Residual.over(read_items(LEDGERS))
    by_hand = [
        int(row[5]) - int(row[6]) - int(row[7]) for row in fixture_rows() if row[5] and row[6]
    ]

    assert residual.count == len(by_hand) == 7
    assert residual.minimum == min(by_hand)
    assert residual.maximum == max(by_hand)
    assert residual.median == statistics.median(by_hand)
    assert residual.negatives == sum(1 for value in by_hand if value < 0) == 1
    assert residual.upper == naive_percentile(by_hand, UPPER_PERCENTILE)


def test_a_row_missing_a_clock_is_skipped_rather_than_read_as_zero() -> None:
    unclocked = [item for item in read_items(LEDGERS) if item.summarize_ms is None]

    assert len(unclocked) == 1
    assert unclocked[0].residual_ms is None
    assert Residual.over(unclocked).values == ()


def test_the_cap_population_is_admitted_by_two_independent_proofs() -> None:
    by_run = {
        entry.run_id: entry
        for entry in admissions(LEDGERS, read_items(LEDGERS), cap_tokens=CAP_TOKENS)
    }

    assert ceiling_words(CAP_TOKENS) == 3846
    assert stamps_by_run(LEDGERS)[0] == "bbbbbbbb"
    assert by_run["2026-01-01-2"].carries_live_stamp
    assert not by_run["2026-01-01-2"].cut_at_ceiling
    assert by_run["2026-01-01-3"].cut_at_ceiling
    assert not by_run["2026-01-01-3"].carries_live_stamp
    assert not by_run["2026-01-01-1"].admitted
    assert "2026-01-01-4" not in by_run
    assert sorted(run for run, entry in by_run.items() if entry.admitted) == [
        "2026-01-01-2",
        "2026-01-01-3",
    ]


def test_the_regression_agrees_with_the_stdlib_least_squares() -> None:
    pairs = admitted_pairs()
    fit = WordsToTokens.over(pairs)
    expected = statistics.linear_regression([w for w, _ in pairs], [t for _, t in pairs])
    residuals = [t - (expected.intercept + expected.slope * w) for w, t in pairs]

    assert fit.count == len(pairs) == 5
    assert fit.slope == expected.slope
    assert fit.intercept == expected.intercept
    assert fit.residual_sd == statistics.stdev(residuals)
    assert fit.widest_words == 3846
    assert fit.prompt_at(3846) == expected.intercept + expected.slope * 3846


def test_dividing_reads_a_different_rate_from_regressing() -> None:
    """The whole reason this is a regression: a ratio carries the fixed prompt in it."""
    fit = WordsToTokens.over(admitted_pairs())

    assert fit.ratio_on_widest == 7800 / 3846
    assert fit.ratio_on_widest > fit.slope
    assert fit.intercept > 0


def test_percentile_takes_the_nearest_rank() -> None:
    assert percentile([7], 0.95) == 7
    assert percentile([1, 2, 3, 4], 0.5) == 2
    assert percentile([1, 2, 3, 4], 1.0) == 4


def test_the_report_says_which_grain_each_line_is() -> None:
    text = report(LEDGERS, cap_tokens=CAP_TOKENS, context_tokens=8192, output_tokens=900)

    assert "3 of 8 committed rows name their shard" in text
    assert "2026-01-01-2 shard 0:" in text
    assert "2026-01-01-1:" in text
    assert "2. The clock residual" in text
    assert "tokens an article word" in text


def test_the_committed_ledgers_still_answer_all_three() -> None:
    """No fixture: the real `state/` tree, read-only, so a shape change fails loudly."""
    cap = config.load(CONFIG_DIR).app.extract.truncation_cap_tokens
    items = read_items(STATE_DIR)
    admitted = [a.run_id for a in admissions(STATE_DIR, items, cap_tokens=cap) if a.admitted]
    fit = WordsToTokens.over(sized_pairs(items, admitted))

    assert Residual.over(items).count > 0
    assert fit.count > 0
    assert 1.0 < fit.slope < 2.0
    assert fit.intercept > 0
    assert any(clock.job_seconds > 0 for clock in shard_clocks(STATE_DIR, items))


def test_both_ledgers_now_name_the_shard_that_did_the_work() -> None:
    """`shard` landed on the item ledger on 2026-08-30; before that only counters had it."""
    assert "shard" in RuntimeCountersRow.csv_columns()
    assert "shard" in ItemHealthRow.csv_columns()
