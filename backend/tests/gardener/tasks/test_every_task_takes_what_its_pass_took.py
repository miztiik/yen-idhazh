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
below with why it has none, and its own test file holds what it takes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from ._oracle_tree import build, files_under
from ._task import declared, oracle, run_task

pytestmark = pytest.mark.slow

#: A file the ledger door names by a fresh id, spelled the way the record wrote it.
_FILE_ID: Final = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

#: The recorded entry that is not a task: the old visual pass's own report rows.
_NOT_A_TASK: Final = "visual-prune-rows"

#: Each retention task that replaced no pass of the old cleanup, and why it has none.
_REPLACED_NO_PASS: Final = {
    "span-rollup": (
        "the old cleanup never pruned state/span-rollup: no pass named it, and its sweep "
        "of trial folders skipped every folder a ledger owns. The task exists so the "
        "tree's owner folds its closed days; test_span_rollup_task.py holds what it takes"
    ),
}


def _normal(path: str) -> str:
    return _FILE_ID.sub("<file_id>", path)


def _recorded_tasks() -> list[str]:
    return sorted(name for name in oracle() if name != _NOT_A_TASK and name in declared())


def test_every_retention_task_has_a_recorded_pass_or_a_named_reason_it_has_none() -> None:
    """Both ways round, so a name above can neither hide a task nor outlive one."""
    retention = {name for name, policy in declared().items() if policy.kind == "retention"}
    recorded = set(oracle())
    named = set(_REPLACED_NO_PASS)
    assert sorted(retention - recorded - named) == [], "a retention task with nothing to answer to"
    assert sorted(named - retention) == [], "named as replacing no pass, and not a retention task"
    assert sorted(named & recorded) == [], "named as replacing no pass, and a pass is recorded"


@pytest.mark.parametrize("name", _recorded_tasks())
def test_a_dry_run_names_what_the_pass_removed_and_wrote_and_touches_nothing(
    name: str, tmp_path: Path
) -> None:
    root = build(tmp_path / "checkout")
    before = files_under(root)
    recorded = oracle()[name]

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
    recorded = oracle()[name]

    outcome = run_task(name, root, dry_run=False)

    after = files_under(root)
    removed = sorted(set(before) - set(after))
    written = sorted(
        _normal(path) for path in after if path not in before or before[path] != after[path]
    )
    assert removed == recorded["removed"]
    assert written == recorded["written"]
    assert sorted(outcome.taken) == removed
