"""Does the shipped selector scope checks from real Git changes?"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest
from support.paths import REPO_ROOT

from ._harness import _git, _isolated_env, _write

pytestmark = pytest.mark.workflow

requires_node: Final = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="no node on this host to execute frontend/scripts/test-scope.ts",
)
SELECTOR: Final = REPO_ROOT / "frontend" / "scripts" / "test-scope.ts"
BROWSER_SCOPE_CASES: Final = (
    ("frontend/src/routes/console/+page.svelte", True, True, True, False, False, False),
    ("frontend/src/routes/[date]/+page.svelte", True, True, False, False, False, True),
    ("config/idhazh.json", True, True, False, True, True, True),
    ("docs/reference/pipeline-cost.md", False, False, False, False, False, False),
)


def _two_commits(
    tmp_path: Path, changed: Sequence[str]
) -> tuple[Path, dict[str, str], str, str]:
    env = _isolated_env(tmp_path)
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, env, "init", "--quiet", "--initial-branch=main")
    _write(root / "seed.txt", "seed\n")
    _git(root, env, "add", "seed.txt")
    _git(root, env, "commit", "--quiet", "-m", "seed")
    base = _git(root, env, "rev-parse", "HEAD").strip()
    for name in changed:
        _write(root / name, "changed\n")
        _git(root, env, "add", name)
    _git(root, env, "commit", "--quiet", "-m", "change")
    return root, env, base, _git(root, env, "rev-parse", "HEAD").strip()


def _browser_scope(
    tmp_path: Path, changed: Sequence[str], event: str = "pull_request"
) -> dict[str, str]:
    root, env, base, head = _two_commits(tmp_path, changed)
    completed = subprocess.run(
        ["node", SELECTOR.as_posix(), "--ci"],
        cwd=root,
        env={**env, "EVENT": event, "BASE": base, "HEAD": head},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return dict(
        line.split("=", 1) for line in completed.stdout.strip().splitlines() if "=" in line
    )


@requires_node
@pytest.mark.parametrize(
    ("changed", "browser", "code", "console", "robots", "validate_all", "model_absent"),
    BROWSER_SCOPE_CASES,
)
def test_changed_paths_select_the_expected_checks(
    changed: str,
    browser: bool,
    code: bool,
    console: bool,
    robots: bool,
    validate_all: bool,
    model_absent: bool,
    tmp_path: Path,
) -> None:
    assert _browser_scope(tmp_path, [changed]) == {
        "browser": str(browser).lower(),
        "code": str(code).lower(),
        "model_absent": str(model_absent).lower(),
        "console": str(console).lower(),
        "robots": str(robots).lower(),
        "validate_all": str(validate_all).lower(),
    }


@requires_node
def test_a_mixed_change_still_selects_the_path_that_reaches_readers(tmp_path: Path) -> None:
    mixed = ["docs/reference/pipeline-cost.md", "frontend/src/routes/+page.svelte"]
    assert _browser_scope(tmp_path, mixed)["browser"] == "true"


@requires_node
def test_a_push_with_code_runs_every_check_without_path_filtering(tmp_path: Path) -> None:
    assert _browser_scope(tmp_path, ["docs/x.md", "backend/idhazh/discover.py"], event="push") == {
        "browser": "true",
        "code": "true",
        "model_absent": "true",
        "console": "true",
        "robots": "true",
        "validate_all": "true",
    }


@requires_node
def test_a_documentation_only_push_starts_no_code_jobs(tmp_path: Path) -> None:
    assert _browser_scope(tmp_path, ["docs/x.md"], event="push") == {
        "browser": "false",
        "code": "false",
        "model_absent": "false",
        "console": "false",
        "robots": "false",
        "validate_all": "false",
    }
