"""Keep waiting logs alive while host telemetry is explicitly disabled."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from idhazh.telemetry.host import HostCells


class ItemHeartbeat:
    def __init__(
        self, *, interval_s: float, on_tick: Callable[[float], None] | None = None
    ) -> None:
        self._interval_s = interval_s
        self._on_tick = on_tick
        self._started = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _tick(self) -> None:
        while not self._stop.wait(self._interval_s):
            if self._on_tick is not None:
                self._on_tick(time.monotonic() - self._started)

    def __enter__(self) -> ItemHeartbeat:
        self._started = time.monotonic()
        if self._interval_s > 0 and self._on_tick is not None:
            self._thread = threading.Thread(target=self._tick, name="item-heartbeat", daemon=True)
            self._thread.start()
        return self

    def close(self) -> HostCells:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        return HostCells(**dict.fromkeys(HostCells.__dataclass_fields__))

    def __exit__(self, *_: object) -> None:
        self.close()
