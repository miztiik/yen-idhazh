"""Tests for the historical eval re-band operator tool."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text, seed_scores

from idhazh.contracts.base import derive_url_key
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.knobs.evaluation import EvaluationConfig

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
    # Two of the four rows that used to move were moved by lead coverage alone.
    # That counterweight is retired, so they stay where they were recorded.
    assert report.current == {"high": 2, "medium": 3, "low": 2}
    assert report.moves == {("high", "medium"): 2, ("high", "low"): 1}
    assert report.reasons == {
        "dropped hedge": 2,
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
        "  high: 2 (28.6%)",
        "  medium: 3 (42.9%)",
        "  low: 2 (28.6%)",
        "rows moved: 3 (42.9%)",
        "moves:",
        "  high -> low: 1",
        "  high -> medium: 2",
        "move reasons:",
        "  dropped hedge: 2",
        "  unsupported numbers: 1",
    ]


# --- Reading the ledger through the door ---------------------------------------


def _file(state: Path, date: str, *, band: str, hhem: float) -> None:
    """One measurement on `date`, filed by the writer the pipeline files with.

    The committed eval-row fixture re-dated, with its own address so the writer
    files it as a new measurement rather than as a repeat of another day's.
    """
    held = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    address = f"{held['source_url']}-{date}"
    row = EvalRow.model_validate(
        {
            **held,
            "date": date,
            "run_id": f"{date}-1",
            "scored_at": f"{date}T06:18:02Z",
            "source_url": address,
            "url_key": derive_url_key(address),
            "band": band,
            "hhem": hhem,
            "hhem_full": hhem,
            "hhem_delta": 0.0,
        }
    )
    assert seed_scores(state, [row], run_id=f"{date}-1") == 1


def test_a_report_covers_every_day_the_ledger_holds(tmp_path: Path) -> None:
    """The defect this replaces: it opened `state/scores.csv` by name.

    Once the ledger partitioned, that path stopped existing - and a tool that
    reads one file would report on whichever slice of history that file happened
    to be, which is worse than failing. Three days, one row each, and the count
    has to be three.
    """
    state = tmp_path / "state"
    _file(state, "2026-02-09", band="high", hhem=0.91)
    _file(state, "2026-03-11", band="high", hhem=0.40)
    _file(state, "2026-04-02", band="low", hhem=0.95)

    report = reband(read_ledger(state), EvaluationConfig())

    assert report.rows == 3
    assert report.recorded == {"high": 2, "low": 1}


def test_a_ledger_with_no_day_says_so_rather_than_reporting_on_nothing(
    tmp_path: Path,
) -> None:
    """Zero rows is a percentage of zero, and every share would print 0.0%.

    A report that looks calm because it read nothing is the failure mode the
    absent file used to have, so the refusal has to be as loud as the file was,
    and it names the directory it read.
    """
    state = tmp_path / "state"

    with pytest.raises(ValueError, match=re.escape(f"{state.as_posix()} holds no day")):
        read_ledger(state)


def test_the_operator_is_told_which_directory_was_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The first printed line names the state directory the ledger was read from."""
    state = tmp_path / "state"
    _file(state, "2026-02-09", band="high", hhem=0.91)

    assert main(["--state", str(state), "--config", str(CONFIG_DIR)]) == 0

    assert capsys.readouterr().out.splitlines()[0] == "scores: state"
