"""What does every gardener test build before it asks its question?

Three things, each real. A config folder: the committed `config/idhazh.json`,
`config/appearance.json` and `config/idhazh_gardener.json`, with declarations
copied in from a fixture tree under `tests/fixtures/gardener/`. A package of
task modules, imported from `tests/fixtures/gardener/task_packages/` - real
modules that do real work through the real core. And a checkout with a bare
repository standing in for origin, so the commit loop pushes to something that
answers the way GitHub does, with no network (CLAUDE.md section 13).

Git runs with no machine configuration to fall back on, so a developer's own
settings - a signing key, a hook, an identity - cannot make a test pass or fail.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR

GARDENER_FIXTURES: Final = FIXTURES_DIR / "gardener"
TASK_PACKAGES: Final = GARDENER_FIXTURES / "task_packages"

#: The committed files a gardener config folder needs beside its declarations.
COMMITTED_FILES: Final = ("idhazh.json", "appearance.json", "idhazh_gardener.json")

#: Who the seed commits are by. Not the repository's identity, on purpose: a
#: commit the gardener made is told from the seed by its author.
SEED_IDENTITY: Final = ("-c", "user.name=Scripted Origin", "-c", "user.email=origin@example.invalid")


def a_config(root: Path, *declarations: Path) -> Path:
    """A config folder under `root`: the committed files, plus these declarations.

    Each argument is a declaration file, or a fixture folder whose every
    declaration is copied.
    """
    config_dir = root / "config"
    (config_dir / "gardener").mkdir(parents=True, exist_ok=True)
    for name in COMMITTED_FILES:
        shutil.copyfile(CONFIG_DIR / name, config_dir / name)
    for given in declarations:
        for source in sorted(given.glob("*.json")) if given.is_dir() else [given]:
            shutil.copyfile(source, config_dir / "gardener" / source.name)
    return config_dir


def task_package(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """One fixture package, imported by its name from the fixture folder, for one test."""
    monkeypatch.syspath_prepend(str(TASK_PACKAGES))
    return importlib.import_module(name)


def quiet_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git in this process and its children, with no machine configuration at all."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)


def git(repo: Path, *args: str) -> str:
    """One git command in `repo`, as the seed's author, raising on failure."""
    done = subprocess.run(
        ["git", *SEED_IDENTITY, *args],
        cwd=repo,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"git {' '.join(args)} failed: {done.stderr}"
    return done.stdout


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii", newline="\n")
    return path


def an_origin(root: Path, files: dict[str, str]) -> tuple[Path, Path]:
    """A bare origin holding these files in one commit, and a clone of it to work in."""
    origin = root / "origin.git"
    git(root, "init", "--quiet", "--bare", "-b", "main", str(origin))
    seed = root / "seed"
    git(root, "clone", "--quiet", str(origin), str(seed))
    for relative, text in {"README.md": "seed\n", **files}.items():
        write(seed / relative, text)
    git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "seed")
    git(seed, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    checkout = root / "checkout"
    git(root, "clone", "--quiet", str(origin), str(checkout))
    return origin, checkout


def on_origin(origin: Path, relative: str) -> str | None:
    """What `main` on the origin holds at this path, or None when it holds nothing.

    Read as bytes, because a record is parquet: text decoding would fail on it
    in the reader thread and look like a file that never landed.
    """
    done = subprocess.run(
        ["git", "show", f"main:{relative}"],
        cwd=origin,
        env=os.environ.copy(),
        capture_output=True,
        check=False,
    )
    return done.stdout.decode("utf-8", errors="replace") if done.returncode == 0 else None


def commits_on(origin: Path) -> list[str]:
    """Every commit on the origin's `main`, newest first, as `author: subject`."""
    return git(origin, "log", "--format=%an <%ae>: %s", "main").splitlines()


def a_hook(origin: Path, body: str) -> None:
    """A pre-receive hook on the origin, the way a racing push or a refusal is staged."""
    hook = origin / "hooks" / "pre-receive"
    hook.write_text(f"#!/bin/sh\n{body}\n", encoding="ascii", newline="\n")
    hook.chmod(0o755)
