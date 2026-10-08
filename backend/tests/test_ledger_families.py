"""Does the family listing say what the registry it is handed holds?

Driven from a registry and a state tree the test writes, never from the
committed ones: the listing reads every file under every ledger, and a test that
pointed it at `state/` would cost more every day the pipeline runs (CLAUDE.md
Guardrail #12).

The registry is the committed one with one family's status and description
changed, because the contract refuses a registry that leaves any ledger out, and
a changed family is what proves the listing prints what it was handed rather
than what the committed file says.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths
from utilities import ledger_families

pytestmark = pytest.mark.contract

A_DESCRIPTION: Final = "A family this test paused, so the listing has something to report."
AN_ONBOARDING: Final = "2026-09-01"


def a_registry(config_dir: Path) -> Path:
    """The committed registry with the day-metrics family paused, described and dated anew."""
    held: dict[str, Any] = json.loads(
        (REPO_ROOT / "config" / paths.REGISTRY_FILENAME).read_text(encoding="utf-8")
    )
    for family in held["families"]:
        if family["name"] == LedgerName.DAY_METRICS.value:
            family["lifecycle_status"] = "paused"
            family["description"] = A_DESCRIPTION
            family["onboarded"] = AN_ONBOARDING
    config_dir.mkdir(parents=True)
    (config_dir / paths.REGISTRY_FILENAME).write_text(json.dumps(held), encoding="utf-8")
    return config_dir


def a_state_tree(state: Path, files: tuple[str, ...]) -> Path:
    """A state tree holding exactly these files, each one line long."""
    for relative in files:
        target = state / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("version\n", encoding="utf-8")
    return state


def test_each_family_prints_its_status_its_day_and_what_it_holds(tmp_path: Path) -> None:
    """The four facts a family carries, one block per family, in the registry's order."""
    lines = ledger_families.listing(
        a_registry(tmp_path / "config"), tmp_path / "state", ["day-metrics/absent.json"]
    )

    first = lines.index(f"day-metrics: paused, onboarded {AN_ONBOARDING} UTC")
    assert lines[first + 1] == f"  {A_DESCRIPTION}"
    assert lines[first + 2] == "  - day-metrics: 0 files"
    assert any(line.startswith("content-similarity-judge: active, onboarded ") for line in lines)


def test_each_ledger_counts_the_files_under_its_own_address(tmp_path: Path) -> None:
    """A folder counts every file below it; a one-file ledger counts that file alone.

    The judge's score distribution sits in the same folder as the CSV files its
    fitted line and its hand marks filed before they moved to the door, so a count
    that walked the folder for the score distribution would take those too. Both
    now count their files under the door's roots, and the CSV files left behind
    belong to no ledger. A dot file is a placeholder and holds no rows.
    """
    named = (
        "day-metrics/2026/09/18.json",
        "day-metrics/2026/09/19.json",
        "content-similarity-judge/score-distribution.json",
        "content-similarity-judge/holdout-pairs.csv",
        "content-similarity-judge/fitted-thresholds/2026/09/18.csv",
        "raw/content-similarity-judge/fitted-thresholds/2026/09/19/"
        "01a0d03c-2e00-8461-98e0-a67898e9a804.parquet",
        "traces/.gitkeep",
    )
    state = a_state_tree(tmp_path / "state", named)

    lines = ledger_families.listing(a_registry(tmp_path / "config"), state, list(named))

    assert "  - day-metrics: 2 files" in lines
    assert "  - score-distribution: 1 file" in lines
    assert "  - holdout-pairs under raw/: 0 files" in lines
    assert "  - fitted-thresholds under raw/: 1 file" in lines
    assert "  - fitted-thresholds under compact/: 0 files" in lines
    assert "  - traces: 0 files" in lines
    assert "  - item-health-summary under raw/: 0 files" in lines
    assert "  - item-health-summary under compact/: 0 files" in lines


def test_a_ledger_under_the_two_roots_counts_each_root_on_its_own_line(tmp_path: Path) -> None:
    """Its prefix is the path inside each root, so a count of `state/<prefix>` would read zero."""
    state = a_state_tree(
        tmp_path / "state",
        (
            "raw/gardener/2026/09/27/01a0d03c-2e00-8461-98e0-a67898e9a802.parquet",
            "raw/gardener/2026/09/28/01a0d03c-2e00-8461-98e0-a67898e9a803.parquet",
            "raw/gardener/index/2026-09-27.json",
            "compact/gardener/daily/2026/09/27.parquet",
        ),
    )

    lines = ledger_families.listing(
        a_registry(tmp_path / "config"),
        state,
        [
            "raw/gardener/2026/09/27/01a0d03c-2e00-8461-98e0-a67898e9a802.parquet",
            "raw/gardener/2026/09/28/01a0d03c-2e00-8461-98e0-a67898e9a803.parquet",
            "raw/gardener/index/2026-09-27.json",
            "compact/gardener/daily/2026/09/27.parquet",
        ],
    )

    assert "  - gardener under raw/: 3 files" in lines
    assert "  - gardener under compact/: 1 file" in lines
