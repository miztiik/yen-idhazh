"""Does each retention task take exactly the files the pass it replaced took, and write what it wrote?

The oracle row 5 was held to. Each pass in the deleted `stages/prune_state.py`
was run once, live and dry, over the tree `_oracle_tree.build` makes, with the
committed windows, and what it removed and wrote was recorded in
`tests/fixtures/gardener/prune-oracle/removals.json` before the module went.
Each task now runs over the same tree with its committed declaration.

A dry run names every file a live run takes and every file it writes, and
changes nothing on disk but the report a task appends through the ledger door.
A live run takes exactly those files and writes exactly those files.
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


def _normal(path: str) -> str:
    return _FILE_ID.sub("<file_id>", path)


def _recorded_tasks() -> list[str]:
    return sorted(name for name in oracle() if name != _NOT_A_TASK and name in declared())


def test_every_retention_task_declared_has_a_recorded_pass_to_answer_to() -> None:
    retention = sorted(name for name, policy in declared().items() if policy.kind == "retention")
    assert [name for name in retention if name not in oracle()] == []


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
