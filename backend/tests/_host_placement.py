"""A scoped guard for tests that must not request external host placement."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType

from idhazh.telemetry import silicon


@contextmanager
def refuse_external_placement() -> Iterator[None]:
    def guard(frame: FrameType, event: str, argument: object) -> None:
        if event == "call" and frame.f_code is silicon.placement.__code__:
            raise AssertionError("host collection must not request external placement")

    previous = sys.getprofile()
    sys.setprofile(guard)
    try:
        yield
    finally:
        sys.setprofile(previous)
