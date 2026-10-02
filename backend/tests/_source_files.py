"""Which source files can a test read without walking generated output?"""

from __future__ import annotations

import subprocess
from collections.abc import Collection
from functools import cache
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_PATHS = (
    "backend",
    "frontend/src",
    "frontend/tests",
    ".github",
    "config",
    "docs",
    "TODO",
)


def _git_files(*arguments: str) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    return tuple(
        name.decode("utf-8", "surrogateescape")
        for name in result.stdout.split(b"\0")
        if name
    )


@cache
def _repository_files() -> tuple[Path, ...]:
    """List tracked and visible untracked files once for this test process."""
    names = {
        *_git_files("ls-files", "-z", "--", *_SOURCE_PATHS),
        *_git_files("ls-files", "--others", "--exclude-standard", "-z", "--", *_SOURCE_PATHS),
    }
    return tuple(
        sorted(REPO_ROOT.joinpath(*PurePosixPath(name).parts) for name in names)
    )


def source_files(
    *,
    roots: Collection[Path],
    suffixes: Collection[str] | None = None,
    excluded_roots: Collection[Path] = (),
) -> list[Path]:
    """Return listed files under selected roots, filtering before callers read them."""
    return [
        path
        for path in _repository_files()
        if any(path == root or root in path.parents for root in roots)
        and not any(path == root or root in path.parents for root in excluded_roots)
        and (suffixes is None or path.suffix in suffixes)
    ]
