"""How does a test start from a built git origin without building it again?

A built origin costs several git processes. A test that only reads or pushes to
its own copy needs the bytes, not the build, so each distinct origin is built
once for the session and every test copies it (CLAUDE.md section 13).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Final

#: Where a built origin lives, keyed by what it holds.
_TEMPLATES: Final[dict[tuple[str, ...], Path]] = {}


def discard() -> None:
    """Delete every built origin once the last test that copies one has run."""
    for root in _TEMPLATES.values():
        shutil.rmtree(root, ignore_errors=True)
    _TEMPLATES.clear()


def template(key: tuple[str, ...]) -> tuple[Path, bool]:
    """The directory this template lives in, and whether it still has to be filled.

    Outside any test's `tmp_path`, because one build serves the whole session -
    and `tmp_path` is removed with the test that owned it.
    """
    root = _TEMPLATES.get(key)
    if root is not None:
        return root, False
    root = Path(tempfile.mkdtemp(prefix="yen-idhazh-origin-"))
    _TEMPLATES[key] = root
    return root, True


def ignore_locks(_directory: str, names: list[str]) -> set[str]:
    """Lock files git's own background maintenance leaves in a template.

    A template is copied once per test and several xdist workers copy the same
    one at the same time. git maintenance can create and delete
    objects/maintenance.lock between copytree listing a directory and
    reading it, which fails the copy with a file that was never part of the
    template anyway.
    """
    return {name for name in names if name.endswith(".lock")}


def copy_origin(root: Path, destination: Path) -> None:
    """A private copy of the bare origin a template holds, for one test to push to."""
    shutil.copytree(root / "origin.git", destination, ignore=ignore_locks)
