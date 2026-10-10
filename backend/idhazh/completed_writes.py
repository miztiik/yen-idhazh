"""How can a caller collect completed atomic writes without discovering an archive?"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_completed: ContextVar[dict[Path, str] | None] = ContextVar("completed_writes", default=None)


def record(path: Path, data: bytes) -> None:
    """Record only after replacement succeeded; observers grant no permissions."""
    writes = _completed.get()
    if writes is not None:
        writes[path.absolute()] = hashlib.sha256(data).hexdigest()


@contextmanager
def collect() -> Iterator[dict[Path, str]]:
    """One invocation's completed files, including those preceding an exception."""
    writes: dict[Path, str] = {}
    token = _completed.set(writes)
    try:
        yield writes
    finally:
        _completed.reset(token)
