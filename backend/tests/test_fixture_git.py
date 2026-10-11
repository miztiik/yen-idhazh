"""Do generated Git fixtures fail closed without weakening inherited bare safety?"""

import subprocess
from pathlib import Path

import pytest
from fixture_git import command

pytestmark = pytest.mark.contract


def test_fixture_git_cannot_fall_back_to_enclosing_checkout(tmp_path: Path) -> None:
    nested = tmp_path / "uninitialized"
    nested.mkdir()
    with pytest.raises(ValueError, match="not initialized"):
        command(nested, "add", "--all")
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=nested,
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0


def test_generated_bare_fixture_uses_explicit_git_dir(tmp_path: Path) -> None:
    origin = tmp_path / "origin.git"
    subprocess.run(command(tmp_path, "init", "--bare", str(origin)), check=True,
                   capture_output=True)
    implicit = subprocess.run(
        ["git", "-c", "safe.bareRepository=explicit", "rev-parse", "--git-dir"],
        cwd=origin, capture_output=True, text=True, check=False,
    )
    assert implicit.returncode != 0
    explicit = subprocess.run(
        command(origin, "-c", "safe.bareRepository=explicit", "rev-parse", "--git-dir"),
        cwd=origin, capture_output=True, text=True, check=True,
    )
    assert Path(explicit.stdout.strip()).resolve() == origin.resolve()
