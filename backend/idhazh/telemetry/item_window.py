"""Close the native item window without tying the progress log to it."""

from __future__ import annotations

from asyncio import CancelledError
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from idhazh.contracts.model_server_pin import ModelServerPin
from idhazh.contracts.task_performance import TaskPerformanceOutcome
from idhazh.telemetry.host import HostCells
from idhazh.telemetry.item_heartbeat import ItemHeartbeat
from idhazh.telemetry.machine_api import MachineApi, MachineApiError, ProfileIdentity, warn


def item_listener() -> MachineApi | None:
    try:
        listener = MachineApi.for_job()
    except (ValueError, MachineApiError):
        warn("item window listener settings invalid; no item profile")
        return None
    if listener is None:
        warn("item window listener unavailable; no item profile")
    return listener


def item_server_pin(pid: int) -> ModelServerPin | None:
    """Keep the original launch identity even if the kernel reuses its PID."""
    try:
        pin = ModelServerPin.read(Path("llama-server.pin.json"))
    except (OSError, ValueError):
        warn("item window model-server launch pin unavailable")
        return None
    if pin.pid != pid:
        warn("item window model-server PID does not match the launch pin")
        return None
    return pin


class ItemWindow:
    def __init__(
        self, listener: MachineApi, identity: ProfileIdentity, *, interval_s: int,
        on_tick: Callable[[float], None], server: ModelServerPin | None,
        memory_profiling_enabled: bool,
    ) -> None:
        self._listener = listener
        self._identity = identity
        self._heartbeat = ItemHeartbeat(interval_s=interval_s, on_tick=on_tick)
        self._cells: HostCells | None = None
        self._handle: UUID | None = None
        try:
            self._handle = listener.start_item_window(
                identity, heartbeat_seconds=interval_s, server=server,
                memory_profiling_enabled=memory_profiling_enabled,
            )
        except (ValueError, MachineApiError) as error:
            warn(f"item window start unavailable: {type(error).__name__}")

    def __enter__(self) -> ItemWindow:
        self._heartbeat.__enter__()
        return self

    def close(self, outcome: TaskPerformanceOutcome = "success") -> HostCells:
        if self._cells is None:
            self._cells = self._heartbeat.close()
            if self._handle is not None:
                try:
                    self._cells = self._listener.stop_item_window(
                        self._handle, self._identity, outcome,
                    )
                except (ValueError, MachineApiError) as error:
                    warn(f"item window close unavailable: {type(error).__name__}")
        return self._cells

    def __exit__(self, _exc_type: object, exc: BaseException | None, _traceback: object) -> None:
        if isinstance(exc, (CancelledError, KeyboardInterrupt)):
            self.close("cancelled")
        else:
            self.close("error" if exc is not None else "success")
