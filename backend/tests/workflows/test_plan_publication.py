"""Does the plan commit keep its publication inventory with its state files?"""

from __future__ import annotations

import shlex

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import read_text

from ._harness import COMMIT_PROGRAM_CALL, WORKFLOWS_DIR, _mapping, _step

pytestmark = pytest.mark.workflow


def test_the_plan_commits_its_named_publication_inventory() -> None:
    workflow = _mapping(
        yaml.safe_load(read_text(WORKFLOWS_DIR / "digest.yml")), "the daily workflow"
    )
    step = _step(workflow, "plan", "name", "Commit what the plan saw")
    call = shlex.split(str(step["run"]))
    assert tuple(call[: len(COMMIT_PROGRAM_CALL)]) == COMMIT_PROGRAM_CALL
    paths = call[len(COMMIT_PROGRAM_CALL) :]
    assert paths[0] == "plan"
    from utilities.digest_publish import permissions

    assert "frontend/public/publication.json" in permissions("plan", date="2026-10-09"), (
        "the plan registers feed-health files, but its commit drops their publication inventory"
    )
