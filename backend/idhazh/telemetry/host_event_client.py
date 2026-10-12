"""How does Python exchange optional host lifecycle events without owning measurements?"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Literal
from uuid import UUID, uuid4

from idhazh.contracts.host_events import (
    CaptureSource,
    HostCommandBody,
    HostEvent,
    HostResultBody,
    InstrumentSkippedBody,
    ProtocolFaultBody,
    ProtocolFaultCode,
    WindowAbortBody,
    WindowBody,
    WorkerBody,
)
from idhazh.telemetry.host_event_files import HostEventFiles, HostProtocolError, event_bytes
from idhazh.telemetry.host_evidence_inputs import CONFIG_BYTES, NativeSettings, read_bytes

_LOG = logging.getLogger("idhazh")


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _monotonic_ms() -> int:
    return time.monotonic_ns() // 1_000_000


class HostEventClient:
    """One bounded file-event session used only when the shadow knob is on."""

    def __init__(
        self,
        workspace: Path,
        manifest_path: Path,
        config_path: Path,
    ) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.config_path = self._inside(config_path)
        native = NativeSettings.model_validate_json(read_bytes(self.config_path, CONFIG_BYTES))
        self.files = HostEventFiles.open(
            self.workspace,
            self._inside(manifest_path),
            limits=native.limits,
        )
        self.manifest = self.files.manifest
        if (
            native.controls != self.manifest.controls
            or native.capture_limits != self.manifest.capture_limits
        ):
            raise ValueError("host event manifest differs from its named effective config")
        self._sequence: dict[str, int] = {}
        self._seen_results: set[UUID] = set()
        self._worker_id: str | None = None
        self._registered = False
        self._healthy = True
        self._last_host_result: UUID | None = None

    def _inside(self, path: Path) -> Path:
        resolved = path if path.is_absolute() else self.workspace / path
        resolved = resolved.resolve(strict=True)
        if not resolved.is_relative_to(self.workspace):
            raise ValueError("host event input escapes its isolated workspace")
        return resolved

    def _next(self, emitter: str) -> int:
        sequence = self._sequence.get(emitter, 0) + 1
        self._sequence[emitter] = sequence
        return sequence

    def _event(self, kind: str, emitter: str, body: object) -> HostEvent:
        return HostEvent.model_validate(
            {
                **self.manifest.model_dump(
                    include={
                        "version",
                        "date",
                        "run_id",
                        "attempt",
                        "job",
                        "shard",
                        "session_id",
                    },
                    mode="json",
                ),
                "kind": kind,
                "event_id": str(uuid4()),
                "reply_to": None,
                "emitter_id": emitter,
                "sequence": self._next(emitter),
                "emitted_at": _utc_now(),
                "body": body,
            }
        )

    def _result_ids(self) -> tuple[UUID, ...]:
        root = self.files.event_path(uuid4(), "results").parent
        if not root.exists():
            return ()
        ids: list[UUID] = []
        entries = 0
        for entry in root.iterdir():
            entries += 1
            if entries > self.manifest.limits.max_files:
                raise HostProtocolError(
                    ProtocolFaultCode.BOUNDS, "result directory exceeds max_files"
                )
            if entry.name.startswith("."):
                continue
            try:
                event_id = UUID(entry.name.removesuffix(".json"))
            except ValueError as error:
                raise HostProtocolError(
                    ProtocolFaultCode.IDENTITY, "foreign result filename"
                ) from error
            if entry.name != f"{event_id}.json":
                raise HostProtocolError(ProtocolFaultCode.IDENTITY, "noncanonical result filename")
            if event_id not in self._seen_results:
                ids.append(event_id)
        return tuple(ids)

    def _new_results(self) -> tuple[HostEvent, ...]:
        pending: list[tuple[int, UUID, HostEvent, bytes]] = []
        for event_id in self._result_ids():
            path = self.files.event_path(event_id, "results")
            raw = self.files._bounded_read(path, self.manifest.limits.max_result_bytes)
            event = HostEvent.model_validate_json(raw)
            if event.event_id != event_id or event.kind in {
                "host.probe",
                "host.target",
                "host.clock",
                "worker.register",
                "window.begin",
                "window.end",
                "window.abort",
                "monitor.stop",
            }:
                raise HostProtocolError(
                    ProtocolFaultCode.IDENTITY, "result file identity or kind conflicts"
                )
            pending.append((event.sequence, event_id, event, raw))
        results: list[HostEvent] = []
        for _, event_id, event, raw in sorted(pending):
            accepted = self.files.bookkeeping.accept(event, now_ms=_monotonic_ms(), raw=raw)
            self._seen_results.add(event_id)
            results.append(accepted.event)
        return tuple(results)

    def _physical_usage(self) -> tuple[int, int]:
        root = self.files.event_path(uuid4(), "results").parent.parent
        files = 0
        size = 0
        for name in ("inbox", "results", "consumed"):
            directory = root / name
            if not directory.exists():
                continue
            if directory.is_symlink() or directory.is_junction():
                raise HostProtocolError(
                    ProtocolFaultCode.IDENTITY, "session directory cannot be a link"
                )
            for path in directory.iterdir():
                if path.name.startswith("."):
                    continue
                if path.is_symlink() or path.is_junction() or not path.is_file():
                    raise HostProtocolError(
                        ProtocolFaultCode.IDENTITY,
                        "session entry must be a regular file",
                    )
                files += 1
                if files > self.manifest.limits.max_files:
                    raise HostProtocolError(
                        ProtocolFaultCode.BOUNDS, "session file capacity exhausted"
                    )
                size += path.stat().st_size
        return files, size

    def _consume(self, event: HostEvent) -> None:
        direction: Literal["inbox", "results"] = (
            "inbox"
            if event.kind
            in {
                "host.probe",
                "host.target",
                "host.clock",
                "worker.register",
                "window.begin",
                "window.end",
                "window.abort",
                "monitor.stop",
            }
            else "results"
        )
        original = self.files.event_path(event.event_id, direction)
        raw = event_bytes(event)
        if read_bytes(original, len(raw)) != raw:
            raise HostProtocolError(ProtocolFaultCode.DUPLICATE, "consumption differs from event")
        consumed = (
            self.files.event_path(event.event_id, "results").parent.parent
            / "consumed"
            / f"{event.event_id}.json"
        )
        if consumed.parent.exists() and (
            consumed.parent.is_symlink() or consumed.parent.is_junction()
        ):
            raise HostProtocolError(
                ProtocolFaultCode.IDENTITY, "consumed directory cannot be a link"
            )
        consumed.parent.mkdir(parents=True, exist_ok=True)
        if consumed.is_symlink() or consumed.is_junction():
            raise HostProtocolError(ProtocolFaultCode.IDENTITY, "consumed event cannot be a link")
        if consumed.exists():
            if read_bytes(consumed, len(raw)) != raw:
                raise HostProtocolError(ProtocolFaultCode.DUPLICATE, "consumed event conflicts")
            return
        files, size = self._physical_usage()
        if (
            files >= self.manifest.limits.max_files
            or size + len(raw) > self.manifest.limits.max_session_bytes
        ):
            raise HostProtocolError(
                ProtocolFaultCode.BOUNDS, "consumption exceeds session capacity"
            )
        staging = consumed.with_name(f".{consumed.stem}.{uuid4()}.pending")
        try:
            staging.write_bytes(raw)
            os.link(staging, consumed)
        except FileExistsError:
            if read_bytes(consumed, len(raw)) != raw:
                raise HostProtocolError(
                    ProtocolFaultCode.DUPLICATE, "concurrent consumption conflicts"
                ) from None
        finally:
            staging.unlink(missing_ok=True)

    def _wait(
        self,
        command: HostEvent | None,
        expected: set[str],
        *,
        timeout_ms: int,
    ) -> HostEvent | None:
        deadline = _monotonic_ms() + timeout_ms
        while True:
            for result in self._new_results():
                if result.reply_to is None and isinstance(result.body, ProtocolFaultBody):
                    raise HostProtocolError(result.body.code, "uncorrelated host protocol fault")
                if command is not None and result.reply_to != command.event_id:
                    continue
                if command is None and result.kind != "monitor.ready":
                    continue
                if isinstance(result.body, ProtocolFaultBody):
                    raise HostProtocolError(result.body.code, "host protocol command failed")
                if result.kind not in expected:
                    raise HostProtocolError(
                        ProtocolFaultCode.IDENTITY, "reply kind contradicts its command"
                    )
                self._consume(result)
                if command is not None:
                    self._consume(command)
                return result
            if _monotonic_ms() >= deadline:
                return None
            time.sleep(self.manifest.limits.poll_ms / 1000)

    def _ready(self) -> bool:
        if not self._healthy:
            return False
        if self.files.bookkeeping._phase != "starting":
            return True
        ready = self._wait(
            None,
            {"monitor.ready"},
            timeout_ms=self.manifest.limits.readiness_timeout_ms,
        )
        if ready is None:
            self._healthy = False
            _LOG.warning("host event monitor unavailable reason=timed_out")
            return False
        return True

    def register_worker(self, *, server_pid: int | None) -> bool:
        """Register the actual Python worker and selected server before model work."""
        if self._registered:
            return self._healthy
        worker = next(
            (entry for entry in self.manifest.workers if entry.target.pid == os.getpid()),
            None,
        )
        if worker is None:
            raise ValueError("host event manifest does not declare this Python worker")
        if (worker.server.pid if worker.server else None) != server_pid:
            raise ValueError("host event manifest server differs from the selected server")
        self._worker_id = worker.emitter_id
        if not self._ready():
            return False
        body = WorkerBody(
            target=worker.target,
            server=worker.server,
            memory_profiling_enabled=self.manifest.controls.memory_profiling_enabled,
        )
        command = self._event("worker.register", worker.emitter_id, body)
        self.files.publish(command, now_ms=_monotonic_ms())
        reply = self._wait(
            command,
            {"worker.registered"},
            timeout_ms=self.manifest.limits.ack_timeout_ms,
        )
        if reply is None:
            self._healthy = False
            _LOG.warning("host event registration unavailable reason=timed_out")
            return False
        self._registered = True
        return True

    def shadow_watch(
        self,
        watch: Any,
        *,
        item_id: str,
    ) -> ShadowWatch:
        if self._worker_id is None:
            raise ValueError("host event worker must register before opening a window")
        declared = next(
            (
                entry
                for entry in self.manifest.windows
                if entry.item_id == item_id and entry.emitter_id == self._worker_id
            ),
            None,
        )
        if declared is None:
            raise ValueError("host event manifest does not declare this item window")
        worker = next(
            entry for entry in self.manifest.workers if entry.emitter_id == self._worker_id
        )
        body = WindowBody(
            window_id=declared.window_id,
            item_id=declared.item_id,
            target=worker.target,
            server=worker.server,
        )
        return ShadowWatch(self, watch, body)

    def _window_command(
        self,
        kind: str,
        body: WindowBody | WindowAbortBody,
    ) -> HostEvent | None:
        if not self._healthy or self._worker_id is None:
            return None
        command = self._event(kind, self._worker_id, body)
        self.files.publish(command, now_ms=_monotonic_ms())
        expected = {"window.begun"} if kind == "window.begin" else {"window.result"}
        reply = self._wait(command, expected, timeout_ms=self.manifest.limits.ack_timeout_ms)
        if reply is None:
            self._healthy = False
            _LOG.warning("host event window unavailable kind=%s reason=timed_out", kind)
        return reply

    def begin_job(self) -> None:
        self._host_command("host.probe")
        if self._last_host_result is not None and self.manifest.cpu_target is not None:
            self._host_command("host.target")

    def end_job(self) -> None:
        if self._last_host_result is not None:
            self._host_command("host.clock")

    def _host_command(self, kind: str) -> None:
        sources = {
            "host.clock": {CaptureSource.CLOCK_LOG},
            "host.target": {CaptureSource.AFFINITY, CaptureSource.CPUSET, CaptureSource.QUOTA},
        }
        selected = sources.get(kind)
        names = tuple(
            entry.name
            for entry in self.manifest.named_inputs
            if selected is None or entry.source in selected
        )
        body = HostCommandBody(
            controls=self.manifest.controls,
            input_names=names,
            target=None if kind == "host.probe" else self.manifest.cpu_target,
            previous_result_id=None if kind == "host.probe" else self._last_host_result,
        )
        command = self._event(kind, self.manifest.operator_emitter_id, body)
        self._publish_unchecked(command)
        result = self._wait_unchecked(command)
        if result is None:
            raise TimeoutError(f"{kind} result timed out")
        if isinstance(result.body, HostResultBody):
            self._last_host_result = result.event_id
        elif isinstance(result.body, InstrumentSkippedBody):
            _LOG.warning("host event instrument unavailable kind=%s", kind)
        else:
            raise HostProtocolError(
                ProtocolFaultCode.IDENTITY, "host command returned another body"
            )

    def _publish_unchecked(self, event: HostEvent) -> None:
        target = self.files.event_path(event.event_id, "inbox")
        raw = event_bytes(event)
        files, size = self._physical_usage()
        if (
            len(raw) > self.manifest.limits.max_command_bytes
            or files >= self.manifest.limits.max_files
            or size + len(raw) > self.manifest.limits.max_session_bytes
        ):
            raise HostProtocolError(
                ProtocolFaultCode.BOUNDS, "host command exceeds session capacity"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.stem}.{uuid4()}.pending")
        try:
            staging.write_bytes(raw)
            os.link(staging, target)
        except FileExistsError:
            if read_bytes(target, len(raw)) != raw:
                raise HostProtocolError(
                    ProtocolFaultCode.DUPLICATE, "immutable command conflicts"
                ) from None
        finally:
            staging.unlink(missing_ok=True)

    def _wait_unchecked(self, command: HostEvent) -> HostEvent | None:
        deadline = _monotonic_ms() + self.manifest.limits.ack_timeout_ms
        while True:
            for event_id in self._result_ids():
                path = self.files.event_path(event_id, "results")
                result = HostEvent.model_validate_json(
                    self.files._bounded_read(path, self.manifest.limits.max_result_bytes)
                )
                self._seen_results.add(event_id)
                if result.reply_to != command.event_id:
                    continue
                if any(
                    getattr(result, name) != getattr(self.manifest, name)
                    for name in ("date", "run_id", "attempt", "job", "shard", "session_id")
                ) or result.kind not in {
                    "host.result",
                    "instrument.skipped",
                    "protocol.fault",
                }:
                    raise HostProtocolError(
                        ProtocolFaultCode.IDENTITY, "host result invocation or kind differs"
                    )
                if result.emitter_id != self.manifest.monitor_emitter_id:
                    raise HostProtocolError(
                        ProtocolFaultCode.IDENTITY, "host result emitter differs"
                    )
                if isinstance(result.body, ProtocolFaultBody):
                    raise HostProtocolError(result.body.code, "host command failed")
                self._consume(result)
                self._consume(command)
                return result
            if _monotonic_ms() >= deadline:
                return None
            time.sleep(self.manifest.limits.poll_ms / 1000)


class ShadowWatch:
    """Keep the existing Python Watch authoritative while bracketing it with events."""

    def __init__(
        self,
        client: HostEventClient,
        watch: Any,
        body: WindowBody,
    ) -> None:
        self._client = client
        self._watch = watch
        self._body = body
        self._entered: Any = None
        self._closed = False

    def __enter__(self) -> ShadowWatch:
        self._entered = self._watch.__enter__()
        self._client._window_command("window.begin", self._body)
        return self

    def close(self) -> Any:
        if not self._closed:
            self._client._window_command("window.end", self._body)
            self._closed = True
        return self._entered.close()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if not self._closed:
            if exc_type is None:
                self._client._window_command("window.end", self._body)
            else:
                if not issubclass(exc_type, Exception):
                    abort = WindowAbortBody(**self._body.model_dump(), reason="cancelled")
                else:
                    abort = WindowAbortBody(**self._body.model_dump(), reason="work_failed")
                try:
                    self._client._window_command("window.abort", abort)
                except Exception as event_error:
                    assert exc is not None
                    exc.add_note(f"host event abort also failed: {type(event_error).__name__}")
            self._closed = True
        suppressed = self._watch.__exit__(exc_type, exc, traceback)
        return suppressed if isinstance(suppressed, bool) else None
