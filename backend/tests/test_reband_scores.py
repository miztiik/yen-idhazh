"""Tests for the historical eval re-band operator tool."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

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
reband = cast(Callable[[Iterable[dict[str, str]], EvaluationConfig], Any], _module.reband)


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
