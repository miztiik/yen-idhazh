"""Tests for the historical eval re-band operator tool."""

from __future__ import annotations

import importlib.util
import re
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from idhazh.contracts.app_config import EvaluationConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "evals" / "scores-reband.csv"
DISPLAY_PATH = Path("tests/fixtures/evals/scores-reband.csv")
UTILITY = REPO_ROOT / "backend" / "utilities" / "reband_scores.py"


def _load_reband_scores() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reband_scores", UTILITY)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_module = cast(Any, _load_reband_scores())
lines_for = cast(Callable[[Any, Path], list[str]], _module.lines_for)
read_rows = cast(Callable[[Path], list[dict[str, str]]], _module.read_rows)
read_ledger = cast(Callable[[Path], list[dict[str, str]]], _module.read_ledger)
reband = cast(Callable[[Iterable[dict[str, str]], EvaluationConfig], Any], _module.reband)
main = cast(Callable[[list[str]], int], _module.main)


def test_reband_reports_current_distribution_and_move_reasons() -> None:
    report = reband(read_rows(FIXTURE), EvaluationConfig())

    assert report.rows == 7
    assert report.recorded == {"high": 5, "medium": 1, "low": 1}
    assert report.current == {"high": 1, "medium": 4, "low": 2}
    assert report.moves == {("high", "medium"): 3, ("high", "low"): 1}
    assert report.reasons == {
        "lead coverage": 1,
        "dropped hedge": 1,
        "lead coverage and dropped hedge": 1,
        "unsupported numbers": 1,
    }


def test_reband_output_is_stable_for_operators() -> None:
    report = reband(read_rows(FIXTURE), EvaluationConfig())

    assert lines_for(report, DISPLAY_PATH) == [
        "scores: tests/fixtures/evals/scores-reband.csv",
        "rows: 7",
        "recorded bands:",
        "  high: 5 (71.4%)",
        "  medium: 1 (14.3%)",
        "  low: 1 (14.3%)",
        "current bands:",
        "  high: 1 (14.3%)",
        "  medium: 4 (57.1%)",
        "  low: 2 (28.6%)",
        "rows moved: 4 (57.1%)",
        "moves:",
        "  high -> low: 1",
        "  high -> medium: 3",
        "move reasons:",
        "  lead coverage: 1",
        "  dropped hedge: 1",
        "  lead coverage and dropped hedge: 1",
        "  unsupported numbers: 1",
    ]


# --- Reading the sharded ledger ----------------------------------------------


def _shard(state: Path, month: str, lines: list[str]) -> Path:
    """One month of the ledger, in the layout `evals.writer` writes."""
    shard = state / "scores" / f"{month}.csv"
    shard.parent.mkdir(parents=True, exist_ok=True)
    header = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    shard.write_text("\n".join([header, *lines]) + "\n", encoding="utf-8", newline="")
    return shard


def test_a_report_covers_every_month_the_ledger_holds(tmp_path: Path) -> None:
    """The defect this replaces: it opened `state/scores.csv` by name.

    Once the ledger sharded, that path stopped existing - and a tool that reads
    one file would report on whichever slice of history that file happened to
    be, which is worse than failing. Three months, one row each, and the count
    has to be three.
    """
    state = tmp_path / "state"
    _shard(state, "2026-02", ["high,0.91,0,1.0,False"])
    _shard(state, "2026-03", ["high,0.40,0,1.0,False"])
    _shard(state, "2026-04", ["low,0.95,0,1.0,False"])

    report = reband(read_ledger(state), EvaluationConfig())

    assert report.rows == 3
    assert report.recorded == {"high": 2, "low": 1}


def test_a_ledger_with_no_shard_says_so_rather_than_reporting_on_nothing(
    tmp_path: Path,
) -> None:
    """Zero rows is a percentage of zero, and every share would print 0.0%.

    A report that looks calm because it read nothing is the failure mode the
    absent file used to have, so the directory has to be as loud as the file was.
    """
    with pytest.raises(ValueError, match=re.escape("holds no <YYYY-MM>.csv shard")):
        read_ledger(tmp_path / "state")


def test_a_shard_missing_a_column_is_named_by_its_own_filename(tmp_path: Path) -> None:
    """A month written before a column existed fails by name, not by KeyError.

    With many shards the operator needs to know which one, and the arithmetic
    downstream would otherwise raise somewhere that names no file at all.
    """
    state = tmp_path / "state"
    _shard(state, "2026-02", ["high,0.91,0,1.0,False"])
    narrow = state / "scores" / "2026-03.csv"
    narrow.write_text("band,hhem\nhigh,0.91\n", encoding="utf-8", newline="")

    with pytest.raises(ValueError, match=re.escape("2026-03.csv is missing columns")):
        read_ledger(state)


def test_the_operator_is_told_which_directory_was_read(tmp_path: Path) -> None:
    """The first printed line names the ledger, and it is now a directory."""
    state = tmp_path / "state"
    _shard(state, "2026-02", ["high,0.91,0,1.0,False"])

    report = reband(read_ledger(state), EvaluationConfig())

    assert lines_for(report, state / "scores")[0].endswith("scores")
