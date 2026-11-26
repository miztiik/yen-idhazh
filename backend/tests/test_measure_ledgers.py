"""The two ledger reports, each checked against a second, independent expression.

A single expression cannot catch its own error, so every figure here is computed
twice: once by `measure_ledgers` and once by arithmetic written a different way -
the stdlib's own least squares for the regression, a counting definition for the
percentile, and a positional re-read of the fixture for per-item timing.

Each test files the committed item rows through the ledger door into its own
tree first. The CSV is what the second expression re-reads.
"""

from __future__ import annotations

import csv
import statistics
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from support.ledger import seed_item_health
from support.paths import FIXTURES_DIR

from idhazh.contracts.base import derive_url_key
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.item_health import RETIRED_CELLS, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.extract import TOKENS_PER_WORD
from utilities.measure_ledgers import (
    UPPER_PERCENTILE,
    Residual,
    WordsToTokens,
    admissions,
    ceiling_words,
    percentile,
    read_items,
    report,
    sized_pairs,
)

FIXTURE: Final = FIXTURES_DIR / "state" / "measure-ledgers"
#: The item rows, one file for the ledger.
ITEMS: Final = FIXTURE / "item-health.csv"
#: The day every fixture row is filed under.
DAY: Final = "2026-01-01"
#: The cap the fixture rows were written under. It is the fixture's own, not
#: today's config: a run is admitted on the cut its rows recorded, so this number
#: only sizes the ceiling the report prints.
CAP_TOKENS: Final = 5000


def fixture_cells(path: Path) -> list[dict[str, str]]:
    """One committed fixture file's rows, read by name."""
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def census_row(cells: dict[str, str]) -> ItemHealthRow:
    """One fixture item as a whole census row: the fixture's cells over a published item.

    Read through the contract's own reader, so the fixture's `shard` heading lands
    in `machine_shard` the way any row of that generation does.
    """
    url = f"https://wire.example.org/{cells['item_id']}"
    return ItemHealthRow.from_csv_row(
        {
            "version": ItemHealthRow.schema_version(),
            "url_key": derive_url_key(url),
            "canonical_url": url,
            "vertical": "ai",
            "source_id": "wire",
            "stage": ItemStage.PUBLISH.value,
            "outcome": ItemOutcome.OK.value,
        }
        | cells
    )


def a_ledger(tmp_path: Path) -> Path:
    """The fixture's item ledger, filed through the ledger door."""
    state = tmp_path / "state"
    census = [census_row(cells) for cells in fixture_cells(ITEMS)]
    assert seed_item_health(state, DAY, census) == len(census)
    return state


def fixture_rows() -> list[list[str]]:
    """The item fixture re-read positionally, which shares no code with `read_items`."""
    with ITEMS.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))[1:]


def admitted_pairs(state: Path) -> list[tuple[int, int]]:
    items = read_items(state)
    admitted = [a.run_id for a in admissions(state, items, cap_tokens=CAP_TOKENS) if a.admitted]
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
    """Every heading the fixture names reads into a column its ledger has now.

    The item file still names the machine's shard under its old heading `shard`,
    which the census reader places in `machine_shard` - so a heading passes if it
    is a column today or one `RETIRED_CELLS` still reads.
    """
    pairs = (
        (ITEMS, {*ItemHealthRow.csv_columns(), *RETIRED_CELLS}),
        (FIXTURE / "scores.csv", set(EvalRow.csv_columns())),
    )
    for path, columns in pairs:
        with path.open(encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle))
        assert set(header) <= columns, path.relative_to(FIXTURE).as_posix()


def test_the_residual_matches_a_second_expression_over_the_same_rows(tmp_path: Path) -> None:
    residual = Residual.over(read_items(a_ledger(tmp_path)))
    by_hand = [
        int(row[5]) - int(row[6]) - int(row[7]) for row in fixture_rows() if row[5] and row[6]
    ]

    assert residual.count == len(by_hand) == 7
    assert residual.minimum == min(by_hand)
    assert residual.maximum == max(by_hand)
    assert residual.median == statistics.median(by_hand)
    assert residual.negatives == sum(1 for value in by_hand if value < 0) == 1
    assert residual.upper == naive_percentile(by_hand, UPPER_PERCENTILE)


def test_a_row_missing_a_clock_is_skipped_rather_than_read_as_zero(tmp_path: Path) -> None:
    unclocked = [item for item in read_items(a_ledger(tmp_path)) if item.summarize_ms is None]

    assert len(unclocked) == 1
    assert unclocked[0].residual_ms is None
    assert Residual.over(unclocked).values == ()


def test_the_cap_population_is_admitted_only_by_a_row_cut_on_the_ceiling(
    tmp_path: Path,
) -> None:
    """One physical proof, and a run that cannot show it stays out.

    The proof is the cap the row names in `truncation_cap_tokens`, written at the
    moment of the cut. It is not an equality against a ceiling re-derived from
    today's ratio: the ratio is a reading, and when it was retaken on 2026-09-14
    the implied ceiling moved 1,000 words to 953 and every historical row stopped
    matching at once.

    The fixture carries all three cases. `2026-01-01-3` names the configured cap
    and is admitted. `2026-01-01-1` was cut under a **different** cap and stays
    out, which is the case the recorded number exists to separate - the two word
    counts alone say it was cut and cannot say by what. `2026-01-01-2` recorded no
    cap and stays out too: it ran before the column and cannot say what it ran at.

    The eval stamp was the second proof until 2026-09-12. It went with the field.
    """
    state = a_ledger(tmp_path)
    by_run = {
        entry.run_id: entry
        for entry in admissions(state, read_items(state), cap_tokens=CAP_TOKENS)
    }

    assert by_run["2026-01-01-3"].cut_by_the_cap
    assert "naming the configured cap" in by_run["2026-01-01-3"].proof
    assert not by_run["2026-01-01-1"].cut_by_the_cap, "cut at 2000, not at the configured cap"
    assert not by_run["2026-01-01-2"].admitted, "recorded no cap at all"
    assert "none" in by_run["2026-01-01-1"].proof
    assert "2026-01-01-4" not in by_run
    assert sorted(run for run, entry in by_run.items() if entry.admitted) == ["2026-01-01-3"]


def test_the_ceiling_a_cap_implies_follows_the_measured_ratio() -> None:
    """The report still prints a ceiling, so it still has to be the config's.

    Derived from both inputs rather than pinned, so it follows a retake of the
    ratio and a change to the cap without an edit here (Guardrail #6).
    """
    assert ceiling_words(CAP_TOKENS) == int(CAP_TOKENS / TOKENS_PER_WORD)


def test_the_regression_agrees_with_the_stdlib_least_squares(tmp_path: Path) -> None:
    pairs = admitted_pairs(a_ledger(tmp_path))
    fit = WordsToTokens.over(pairs)
    expected = statistics.linear_regression([w for w, _ in pairs], [t for _, t in pairs])
    residuals = [t - (expected.intercept + expected.slope * w) for w, t in pairs]

    assert fit.count == len(pairs) == 2
    assert fit.slope == expected.slope
    assert fit.intercept == expected.intercept
    assert fit.residual_sd == statistics.stdev(residuals)
    assert fit.widest_words == 3846
    assert fit.prompt_at(3846) == expected.intercept + expected.slope * 3846

    # One admitted run leaves two rows, and a line through two points has no
    # spread to measure - so the spread case is driven by a built population
    # instead (`CLAUDE.md` section 13). It is arithmetic and needs no ledger.
    spread = [(500, 1100), (1000, 2150), (2000, 4050), (3846, 7800)]
    over_spread = WordsToTokens.over(spread)
    line = statistics.linear_regression([w for w, _ in spread], [t for _, t in spread])
    scatter = [t - (line.intercept + line.slope * w) for w, t in spread]

    assert over_spread.residual_sd == statistics.stdev(scatter) > 0


def test_dividing_reads_a_different_rate_from_regressing(tmp_path: Path) -> None:
    """The whole reason this is a regression: a ratio carries the fixed prompt in it."""
    fit = WordsToTokens.over(admitted_pairs(a_ledger(tmp_path)))

    assert fit.ratio_on_widest == 7800 / 3846
    assert fit.ratio_on_widest > fit.slope
    assert fit.intercept > 0


def test_percentile_takes_the_nearest_rank() -> None:
    assert percentile([7], 0.95) == 7
    assert percentile([1, 2, 3, 4], 0.5) == 2
    assert percentile([1, 2, 3, 4], 1.0) == 4


def test_the_report_keeps_item_timing_and_token_size(tmp_path: Path) -> None:
    text = report(a_ledger(tmp_path), cap_tokens=CAP_TOKENS, context_tokens=8192, output_tokens=900)

    assert "1. The clock residual" in text
    assert "2. Words to tokens" in text
    assert "tokens an article word" in text
