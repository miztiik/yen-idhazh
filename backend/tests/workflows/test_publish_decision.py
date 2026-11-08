"""When does the Pages workflow publish, and which commit does it build?"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from ._harness import PUBLISH_DECISION_MODULE

pytestmark = pytest.mark.workflow

STEP_NAMES: Final = frozenset(
    {"EVENT_NAME", "CONCLUSION", "TIP", "DISPATCHED_REF", "DEFAULT_BRANCH"}
)


def decision(workspace: Path, **step_env: str) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if name not in STEP_NAMES}
    env.update(step_env)
    done = subprocess.run(
        [sys.executable, str(PUBLISH_DECISION_MODULE)],
        cwd=workspace,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("=", 1) for line in done.stdout.splitlines())


@pytest.mark.parametrize(
    ("conclusion", "branch", "published"),
    [
        ("success", "main", "true"),
        ("not_verified", "main", "false"),
        ("failure", "main", "false"),
        ("success", "a-branch", "false"),
    ],
)
def test_scheduled_publish_requires_successful_ci_on_the_default_branch_tip(
    tmp_path: Path, conclusion: str, branch: str, published: str
) -> None:
    tip = "a" * 40
    result = decision(
        tmp_path,
        EVENT_NAME="schedule",
        CONCLUSION=conclusion,
        TIP=tip,
        DISPATCHED_REF=branch,
        DEFAULT_BRANCH="main",
    )
    assert result["publish"] == published
    assert result["ref"] == tip


@pytest.mark.parametrize(("dispatched", "published"), [("main", "true"), ("a-branch", "false")])
def test_manual_publish_runs_from_main_only(
    tmp_path: Path, dispatched: str, published: str
) -> None:
    tip = "b" * 40
    result = decision(
        tmp_path,
        EVENT_NAME="workflow_dispatch",
        TIP=tip,
        DISPATCHED_REF=dispatched,
        DEFAULT_BRANCH="main",
    )
    assert result["publish"] == published
    assert result["ref"] == tip


@pytest.mark.parametrize("event", ["push", "pull_request", "workflow_run"])
def test_other_events_do_not_publish(tmp_path: Path, event: str) -> None:
    result = decision(
        tmp_path,
        EVENT_NAME=event,
        TIP="c" * 40,
        DEFAULT_BRANCH="main",
        DISPATCHED_REF="main",
    )
    assert result["publish"] == "false"
