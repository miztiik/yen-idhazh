"""Does every step that writes through the ledger door name the commit its run checked out?

Every file the door writes names that commit, so a step that runs a writing verb
without `--commit` records forty zeros and fails nothing at all.

Nothing here names a job or a verb. The verbs are derived from the package's own
code by `_ledger_derivation.py`, and the steps from the workflows' own `run:`
bodies, so a step that starts running a writing verb is held to this from its
first commit.
"""

from __future__ import annotations

from typing import Final

import pytest

from ._harness import _load_workflows, _stage_invocations
from ._ledger_derivation import _persisted_by, _reachable_modules

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

#: The flag a writing verb takes the commit on.
COMMIT_FLAG: Final = "--commit"


def _writing_verbs() -> dict[str, set[str]]:
    """CLI verb -> the modules it reaches that file rows through the door."""
    writing: dict[str, set[str]] = {}
    for verb, reachable in _reachable_modules().items():
        for module in reachable:
            if _persisted_by(module):
                writing.setdefault(verb, set()).add(module.__name__)
    return writing


def test_every_step_that_writes_through_the_door_names_its_commit() -> None:
    """A writing verb is run with `--commit`, or its files name forty zeros as their code."""
    writing = _writing_verbs()
    assert writing, "no verb writes through the ledger door, so nothing here is checked"
    unnamed: list[str] = []
    checked = 0
    for workflow_name, workflow in sorted(_load_workflows().items()):
        for job_name, step_name, stage, words in _stage_invocations(workflow, workflow_name):
            if stage not in writing:
                continue
            checked += 1
            if COMMIT_FLAG in words:
                continue
            unnamed.append(
                f"{workflow_name} job {job_name}, step {step_name!r}, runs `idhazh {stage}`, "
                f"which files rows through the door from {', '.join(sorted(writing[stage]))}, "
                f"and passes no {COMMIT_FLAG}. Pass {COMMIT_FLAG} with the commit the run "
                "checked out."
            )
    assert not unnamed, "\n".join(unnamed)
    assert checked, "no workflow step runs a verb that writes through the door"
