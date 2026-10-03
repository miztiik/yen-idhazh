"""Does each retention task take exactly the files the pass it replaced took, and write what it wrote?

The oracle each task was held to when it replaced a pass. Each pass of the old
state cleanup was run once, live and dry, over the tree `_oracle_tree.build`
makes, with the committed windows, and what it removed and wrote was recorded in
`tests/fixtures/gardener/prune-oracle/removals.json` before the module went.
Each task now runs over the same tree with its committed declaration.

A dry run names every file a live run takes and every file it writes, and
changes nothing on disk but the report a task appends through the ledger door.
A live run takes exactly those files and writes exactly those files.

A retention task that replaced no pass has no record to be held to. It is named
below with why it has none, and its own test file holds what it takes. A task
that no longer does what its pass did is named the same way, with the test file
that holds what it does now. A retired task is run by nothing, so it is held to
nothing.

Three ledgers moved off their CSV day trees onto the ledger door after the
record was taken, and what bounds their rows now is each ledger's compaction,
not the task that owned the old tree. So a recorded path under one of those old
trees is no task's to answer for, and every other recorded path is held to
exactly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.knobs.gardener import CompactionPolicy, TaskLifecycleStatus
from idhazh.contracts.ledger_name import LedgerName

from ._oracle_tree import build, files_under
from ._task import declared, oracle, run_task

pytestmark = pytest.mark.slow

#: A file the ledger door names by a fresh id, spelled the way the record wrote it.
_FILE_ID: Final = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

#: The recorded entry that is not a task: the old visual pass's own report rows.
_NOT_A_TASK: Final = "visual-prune-rows"

#: Each retention task that replaced no pass of the old cleanup, and why it has none.
_REPLACED_NO_PASS: Final[dict[str, str]] = {}

#: Each recorded task that no longer does what its pass did to a tree it still
#: owns, why, and the test file that holds what it does now.
_NO_LONGER_ITS_PASS: Final[dict[str, str]] = {}

#: The ledgers whose CSV day trees moved onto the ledger door after the record
#: was taken. Their rows sit under `state/raw/` and `state/compact/`, and each
#: one's compaction bounds them now, so a recorded path under the old tree is not
#: held against the task that owned it.
_MOVED_TO_THE_DOOR: Final = (
    LedgerName.HOST_FINGERPRINT,
    LedgerName.ITEM_HEALTH,
    LedgerName.SUMMARY_QUALITY_EVALS,
)


def _normal(path: str) -> str:
    return _FILE_ID.sub("<file_id>", path)


def _in_a_moved_tree(path: str) -> bool:
    """Whether a recorded path sits in the old CSV day tree of a ledger that moved."""
    return any(
        path.startswith(f"{ledger.STATE_DIRNAME}/{moved.value}/") for moved in _MOVED_TO_THE_DOOR
    )


def _answered_for(name: str) -> dict[str, list[str]]:
    """What one task's pass removed and wrote, less what sat in a moved ledger's old tree."""
    recorded: dict[str, list[str]] = oracle()[name]
    return {
        kind: [path for path in paths if not _in_a_moved_tree(path)]
        for kind, paths in recorded.items()
    }


def _runnable_retention() -> set[str]:
    """Every retention declaration a wake can run. A retired one has no module to run."""
    return {
        name
        for name, policy in declared().items()
        if policy.kind == "retention"
        and policy.lifecycle_status is not TaskLifecycleStatus.RETIRED
    }


def _recorded_tasks() -> list[str]:
    """Every task a wake can run whose recorded pass it still does."""
    runnable = _runnable_retention()
    return sorted(name for name in oracle() if name in runnable and name not in _NO_LONGER_ITS_PASS)


def test_every_retention_task_has_a_recorded_pass_or_a_named_reason_it_has_none() -> None:
    """Both ways round, so a name above can neither hide a task nor outlive one.

    Only the tasks a wake can run are counted. A retired declaration has no
    module and nothing runs it, so a pass recorded for it holds nothing to
    account and it owes no reason for having none.
    """
    retention = _runnable_retention()
    recorded = set(oracle()) - {_NOT_A_TASK}
    named = set(_REPLACED_NO_PASS)
    left = set(_NO_LONGER_ITS_PASS)
    assert sorted(retention - recorded - named) == [], "a retention task with nothing to answer to"
    assert sorted(named - retention) == [], "named as replacing no pass, and not a retention task"
    assert sorted(named & recorded) == [], "named as replacing no pass, and a pass is recorded"
    assert sorted(left - (retention & recorded)) == [], (
        "named as leaving its pass, and not a task a wake runs with a recorded pass"
    )


def test_every_tree_left_out_of_the_record_is_one_a_compaction_keeps() -> None:
    """The reason a recorded path under a moved tree is no task's to answer for, held true."""
    compacted = {
        policy.ledger for policy in declared().values() if isinstance(policy, CompactionPolicy)
    }
    assert sorted(set(_MOVED_TO_THE_DOOR) - compacted) == [], "a moved ledger no compaction keeps"


@pytest.mark.parametrize("name", _recorded_tasks())
def test_a_dry_run_names_what_the_pass_removed_and_wrote_and_touches_nothing(
    name: str, tmp_path: Path
) -> None:
    root = build(tmp_path / "checkout")
    before = files_under(root)
    recorded = _answered_for(name)

    outcome = run_task(name, root, dry_run=True)

    after = files_under(root)
    appended = sorted(_normal(path) for path in set(after) - set(before))
    assert sorted(outcome.taken) == recorded["removed"]
    assert sorted(_normal(path) for path in outcome.written) == [
        path for path in recorded["written"] if path not in recorded["dry_written"]
    ]
    assert appended == recorded["dry_written"]
    assert {path: after[path] for path in before} == before, "a dry run changed a file"


@pytest.mark.parametrize("name", _recorded_tasks())
def test_a_live_run_removes_and_writes_exactly_what_the_pass_did(
    name: str, tmp_path: Path
) -> None:
    root = build(tmp_path / "checkout")
    before = files_under(root)
    recorded = _answered_for(name)

    outcome = run_task(name, root, dry_run=False)

    after = files_under(root)
    removed = sorted(set(before) - set(after))
    written = sorted(
        _normal(path) for path in after if path not in before or before[path] != after[path]
    )
    assert removed == recorded["removed"]
    assert written == recorded["written"]
    assert sorted(outcome.taken) == removed
