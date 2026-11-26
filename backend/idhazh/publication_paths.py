"""Which literal file addresses can carry publication evidence?"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath


class IntegrityError(ValueError):
    """A named operation does not have safe, exact evidence."""

    def __init__(self, message: str, paths: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.paths = paths


def relative(path: str) -> str:
    """Accept literal, canonical repository paths, never options or pathspec syntax."""
    parts = PurePosixPath(path).parts
    if (
        not parts
        or PurePosixPath(path).as_posix() != path
        or path.startswith("/")
        or any(part in {"", ".", ".."} or part.casefold() == ".git" for part in parts)
        or any(ord(char) < 32 for char in path)
        or "\\" in path
        or ":" in path
    ):
        raise IntegrityError("not an exact relative repository path", (path,))
    return path


def contains(scope: str, path: str) -> bool:
    """Match whole path segments, not a prefix or a Git pattern."""
    return path == scope or path.startswith(scope + "/")


def safe_file(repo: Path, path: str, *, exists: bool) -> Path:
    relative(path)
    target = repo / path
    for parent in (target, *target.parents):
        if parent.is_symlink() or parent.is_junction():
            raise IntegrityError("symlink or junction in output path", (path,))
        if parent == repo:
            break
    if target.is_dir() or (exists and not target.is_file()):
        raise IntegrityError("operation does not name a completed file", (path,))
    if exists and target.stat().st_mode & 0o111 and os.name != "nt":
        raise IntegrityError("executable output is not a plain data file", (path,))
    return target
