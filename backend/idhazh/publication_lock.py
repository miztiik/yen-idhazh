"""Serialize inventory updates across processes before any writer reads the current document."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Concatenate

if sys.platform == "win32":
    import msvcrt

    def acquire_lock(descriptor: int) -> None:
        """Acquire the inventory's one-byte Windows lock, or fail closed."""
        msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)

    def release_lock(descriptor: int) -> None:
        """Release the inventory's one-byte Windows lock."""
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def acquire_lock(descriptor: int) -> None:
        """Acquire the Unix inventory lock until its holder releases it."""
        fcntl.flock(descriptor, fcntl.LOCK_EX)

    def release_lock(descriptor: int) -> None:
        """Release the Unix inventory lock."""
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def serialize_update[**P, R](
    operation: Callable[Concatenate[Path, P], R],
) -> Callable[Concatenate[Path, P], R]:
    """Hold an OS file lock across the complete read, update and atomic replacement."""

    @wraps(operation)
    def locked(public_root: Path, /, *args: P.args, **kwargs: P.kwargs) -> R:
        # Outside the served tree. Never unlink: waiters must lock the same inode.
        path = public_root.parent / f".{public_root.name}.publication.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            acquire_lock(handle.fileno())
            try:
                return operation(public_root, *args, **kwargs)
            finally:
                handle.seek(0)
                release_lock(handle.fileno())

    return locked
