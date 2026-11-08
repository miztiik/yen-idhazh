"""Do ledger helpers preserve writer ownership and derived-data boundaries?"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from support.paths import REPO_ROOT

from idhazh import ledger, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.path_classes import DERIVED
from idhazh.telemetry.publish import day_metrics

pytestmark = pytest.mark.workflow

SUBSTITUTED_DATE = "2026-10-09"
SUBSTITUTED_DAY_DIR = "2026/10/09"


def _under(relpath: str, named: str) -> bool:
    return relpath == named or relpath.startswith(f"{named}/")


def test_a_file_one_writer_owns_takes_no_merge_driver() -> None:
    one_writer = [
        telemetry.committed_trace_relpath(
            run_id=f"{SUBSTITUTED_DATE}-1", attempt=1, job=ServerJob.WORK, shard=1
        )
    ]
    answered = subprocess.run(
        ["git", "check-attr", "merge", "--", *one_writer],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert answered == [f"{path}: merge: unspecified" for path in one_writer]


def test_assemble_hands_back_no_tree_a_worker_wrote_into() -> None:
    refreshed = [path.format(day_dir=SUBSTITUTED_DAY_DIR) for path in DERIVED]
    state = Path(ledger.STATE_DIRNAME)
    written_once = [
        ledger.tree_root(state, LedgerName.TRACES).as_posix(),
        *(
            ledger.raw_root(state, which).as_posix()
            for which in LedgerName
            if ledger.entry(which).grain is Grain.RAW_AND_COMPACT
        ),
    ]
    for tree in written_once:
        covered = [path for path in refreshed if tree == path or tree.startswith(f"{path}/")]
        assert not covered, f"{covered} includes the completed artifact tree {tree} in regeneration"


def test_the_day_metrics_are_regenerated_but_published_rows_are_not() -> None:
    refreshed = [path.format(day_dir=SUBSTITUTED_DAY_DIR) for path in DERIVED]
    rebuilt = day_metrics.day_metrics_relpath(SUBSTITUTED_DATE)
    filed = ledger.raw_root(Path(ledger.STATE_DIRNAME), LedgerName.PUBLISHED).as_posix()
    assert any(_under(rebuilt, path) for path in refreshed)
    assert not any(_under(filed, path) for path in refreshed)
