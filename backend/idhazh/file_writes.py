"""Which exact bytes did an observed atomic write finish?"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

Observer = Callable[[Path, bytes], None]
_OBSERVERS: ContextVar[tuple[Observer, ...]] = ContextVar("file_write_observers", default=())


@contextmanager
def observe(observer: Observer) -> Iterator[None]:
    """Report writes to both an enclosing job and its current writer."""
    token = _OBSERVERS.set((*_OBSERVERS.get(), observer))
    try:
        yield
    finally:
        _OBSERVERS.reset(token)


def written(path: Path, data: bytes) -> None:
    """Only completed writes count; an observer can refuse their publication."""
    for observer in reversed(_OBSERVERS.get()):
        observer(path, data)
