"""Is every workflow job that reaches the ledger door wired for it?

Two conditions, one question. The door's files are parquet, and the engine is
the optional `parquet` extra, so a job whose verb reads or writes a ledger
through the door and installs only `.` fails on the first file it opens - the
plan stage on its first retirements read, and the cleanup record behind a
`continue-on-error` where nobody sees it. And every file the door writes names
the commit its run checked out, so a step that runs a writing verb without
`--commit` records forty zeros and fails nothing at all.

Nothing here names a job or a verb. The verbs are derived from the package's own
code by `_ledger_derivation.py`, and the jobs from the workflows' own steps, so a
job that starts running `idhazh plan` is held to both conditions from its first
commit.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from ._harness import _load_workflows, _mapping, _stage_invocations, _steps
from ._ledger_derivation import (
    _door_calls,
    _door_verbs,
    _job_verbs,
    _persisted_by,
    _reachable_modules,
)

pytestmark = pytest.mark.workflow

#: An install of this package that carries the parquet extra, however the extras
#: are listed or quoted.
ENGINE_INSTALL: Final = re.compile(r"pip install -e \"?\.\[[a-z0-9_,-]*\bparquet\b[a-z0-9_,-]*\]")

#: The flag a writing verb takes the commit on.
COMMIT_FLAG: Final = "--commit"


def test_the_two_readers_of_a_door_ledger_are_door_calls() -> None:
    """A derived list that shrinks fails nothing, so its two known members are named here.

    Both readers moved from the raw reader to the whole-ledger reader, and a
    derivation that followed only the first would drop them in silence - and
    with them every job whose verb reads a retirement.
    """
    assert {"load_retirements", "load_visual_prunes"} <= _door_calls()


def _writing_verbs() -> dict[str, set[str]]:
    """CLI verb -> the modules it reaches that file rows through the door."""
    writing: dict[str, set[str]] = {}
    for verb, reachable in _reachable_modules().items():
        for module in reachable:
            if _persisted_by(module):
                writing.setdefault(verb, set()).add(module.__name__)
    return writing


def test_every_job_that_reaches_the_door_installs_the_engine() -> None:
    """A job whose verb opens a door file installs `.[parquet]`, whatever the job is for."""
    touching = _door_verbs()
    assert touching, "no verb reaches the ledger door, so nothing here is checked"
    missing: list[str] = []
    credited: list[str] = []
    for workflow_name, workflow in sorted(_load_workflows().items()):
        for job_name in sorted(_mapping(workflow.get("jobs"), f"{workflow_name} jobs")):
            reached = sorted(_job_verbs(workflow, job_name) & set(touching))
            if not reached:
                continue
            credited.append(f"{workflow_name}:{job_name}")
            installs = [
                step["run"]
                for step in _steps(workflow, job_name)
                if isinstance(step.get("run"), str) and ENGINE_INSTALL.search(str(step["run"]))
            ]
            if installs:
                continue
            reasons = "; ".join(
                f"`idhazh {verb}` reaches {', '.join(sorted(touching[verb]))}" for verb in reached
            )
            missing.append(
                f"{workflow_name} job {job_name} runs a verb that opens a ledger door file "
                f"({reasons}) and installs no `.[parquet]`. Install the package with that "
                "extra in the job's install step."
            )
    assert not missing, "\n".join(missing)
    assert credited, "no workflow job runs a verb that reaches the door, so nothing was checked"


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
