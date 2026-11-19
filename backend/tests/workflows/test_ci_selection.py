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


def _two_commits(tmp_path: Path, changed: Sequence[str]) -> tuple[Path, dict[str, str], str, str]:
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


@requires_node
@pytest.mark.parametrize(
    ("event", "paths", "expected"),
    [
        (
            "pull_request",
            ["docs/a.md", "frontend/src/routes/+page.svelte"],
            {"code": "true", "bun": "false", "logic": "true", "tooling": "false"},
        ),
        (
            "push",
            ["backend/idhazh/discover.py"],
            {"code": "true", "bun": "false", "logic": "false", "tooling": "false"},
        ),
        (
            "push",
            ["services/feed-ingest-plan/bun.lock"],
            {"code": "true", "bun": "true", "logic": "false", "tooling": "false"},
        ),
        (
            "push",
            ["docs/a.md"],
            {"code": "false", "bun": "false", "logic": "false", "tooling": "false"},
        ),
    ],
)
def test_changed_paths_select_the_expected_checks(
    event: str, paths: list[str], expected: dict[str, str], tmp_path: Path
) -> None:
    root, env, base, head = _two_commits(tmp_path, paths)
    completed = subprocess.run(
        ["node", SELECTOR.as_posix(), "--ci"],
        cwd=root,
        env={**env, "EVENT": event, "BASE": base, "HEAD": head},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert dict(line.split("=", 1) for line in completed.stdout.splitlines()) == expected
