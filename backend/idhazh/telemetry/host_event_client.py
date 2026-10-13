"""How does Python exchange optional host lifecycle events without owning measurements?"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Literal
from uuid import UUID, uuid4

from idhazh.contracts.host_events import (
    CaptureSource,
    HostCommandBody,
    HostEvent,
    HostProducerInvocation,
    HostResultBody,
    InstrumentSkippedBody,
    ProtocolFaultBody,
    ProtocolFaultCode,
    StopBody,
    WindowAbortBody,
    WindowBody,
    WindowResultBody,
    WorkerBody,
    WriteCompletedBody,
    WritePlanBody,
)
from idhazh.contracts.host_output import (
    HostPublicationReceipt,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
)
from idhazh.contracts.run_plan import RunPlan
from idhazh.telemetry import host
from idhazh.telemetry.host_event_files import HostEventFiles, HostProtocolError, _decode
from idhazh.telemetry.host_evidence_inputs import (
    CONFIG_BYTES,
    NativeSettings,
    read_bytes,
    write_document,
)
from idhazh.telemetry.host_output_verify import verify_host_output

_LOG = logging.getLogger("idhazh")


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _monotonic_ms() -> int:
    return time.monotonic_ns() // 1_000_000


class HostEventClient:
    """One bounded file-event session for shadow observation or native ownership."""

    def __init__(
        self,
        workspace: Path,
        manifest_path: Path,
        config_path: Path,
        *,
        memory_profiling_enabled: bool | None = None,
        native: bool = False,
    ) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.manifest_path = self._inside(manifest_path)
        self.config_path = self._inside(config_path)
        effective = NativeSettings.model_validate_json(read_bytes(self.config_path, CONFIG_BYTES))
        self.files = HostEventFiles.open(
            self.workspace,
            self.manifest_path,
            limits=effective.limits,
        )
        self.manifest = self.files.manifest
        if (
            effective.controls != self.manifest.controls
            or effective.capture_limits != self.manifest.capture_limits
        ):
            raise ValueError("host event manifest differs from its named effective config")
        if (
            memory_profiling_enabled is not None
            and effective.controls.memory_profiling_enabled != memory_profiling_enabled
        ):
            raise ValueError(
                "host event effective memory control differs from the resolved invocation"
            )
        self._sequence: dict[str, int] = {}
        self._seen_results: set[UUID] = set()
        self._worker_id: str | None = None
        self._registered = False
        self._healthy = True
        self._last_host_result: UUID | None = None
        self._native = native
        self._native_started = False
        self._verification_limits = effective.verification_limits
        self._previous_plan: HostWritePlan | None = None
        self._verified_writes: dict[str, str] = {}
        self._verified_bytes = 0
        self._host_result: HostResultBody | None = None
        self._job_begun = False
        self._job_ended = False
        self._stopped: HostEvent | None = None
        self._retirement_candidates: set[UUID] = set()
        self._io_lock = threading.RLock()
        self._pending_results: list[HostEvent] = []
        self._resource_stop = threading.Event()
        self._resource_consumer: threading.Thread | None = None
        self._resource_error: ValueError | OSError | TimeoutError | None = None
        self.invocation: HostProducerInvocation | None = None
        invocation_path = self.manifest_path.parent / "invocation.json"
        if native and invocation_path.exists():
            self.invocation = HostProducerInvocation.model_validate_json(
                read_bytes(self._inside(invocation_path), effective.limits.max_manifest_bytes)
            )
            self.validate_invocation(identity=self.invocation.identity, date=self.invocation.date)

    @classmethod
    def from_environment(
        cls,
        *,
        memory_profiling_enabled: bool | None = None,
        host_enabled: bool | None = None,
        identity: HostWriterIdentity | None = None,
        date: str | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> HostEventClient | None:
        """Open the launcher's serialized session; never substitute a Python collector."""
        env = os.environ if environ is None else environ
        mode = env.get("IDHAZH_HOST_TELEMETRY_MODE", "legacy")
        if mode in ("legacy", "off"):
            return None
        if mode != "rust":
            raise ValueError("IDHAZH_HOST_TELEMETRY_MODE must be 'legacy', 'rust' or 'off'")
        names = ("WORKSPACE", "MANIFEST", "CONFIG", "INVOCATION")
        missing = [name for name in names if not env.get(f"IDHAZH_HOST_TELEMETRY_{name}")]
        if missing:
            raise ValueError("native host session needs " + ", ".join(missing))
        client = cls(
            Path(env["IDHAZH_HOST_TELEMETRY_WORKSPACE"]),
            Path(env["IDHAZH_HOST_TELEMETRY_MANIFEST"]),
            Path(env["IDHAZH_HOST_TELEMETRY_CONFIG"]),
            memory_profiling_enabled=memory_profiling_enabled,
            native=True,
        )
        invocation_path = client._inside(Path(env["IDHAZH_HOST_TELEMETRY_INVOCATION"]))
        if invocation_path != client.manifest_path.parent / "invocation.json":
            raise ValueError("producer invocation must belong to the named host session")
        if client.invocation is None:
            raise ValueError("native host session has no independent producer invocation")
        if host_enabled is not None and host_enabled != client.invocation.host_enabled:
            raise ValueError("native host control differs from the resolved producer invocation")
        client.validate_invocation(identity=client.invocation.identity, date=client.invocation.date)
        command = client.invocation.command
        if (
            len(command) < 2
            or Path(command[1]).resolve() != Path(sys.argv[0]).resolve()
            or tuple(command[2:]) != tuple(sys.argv[1:])
        ):
            raise ValueError("host event producer command differs from this worker invocation")
        if identity is not None:
            client.validate_invocation(identity=identity, date=date or identity.run_id[:10])
        return client

    def validate_invocation(self, *, identity: HostWriterIdentity, date: str) -> None:
        """Compare independently selected worker identity, not values copied from a plan."""
        if date != self.manifest.date or any(
            getattr(identity, name) != getattr(self.manifest, name)
            for name in ("run_id", "attempt", "job", "shard", "git_sha")
        ):
            raise ValueError("host event manifest differs from the executed worker invocation")

    def validate_plan(self, plan: RunPlan, *, shard: int, shards: int) -> None:
        """Require exactly this shard's declared item windows before any model I/O."""
        if shards < 1 or not 0 <= shard < shards or shard != self.manifest.shard:
            raise ValueError("host event shard differs from the selected run plan")
        if (plan.date, plan.run_id) != (self.manifest.date, self.manifest.run_id):
            raise ValueError("host event manifest differs from the expected run plan identity")
        selected = tuple(
            item.item_id for index, item in enumerate(plan.items) if index % shards == shard
        )
        worker = next(
            (entry for entry in self.manifest.workers if entry.target.pid == os.getpid()), None
        )
        if (
            worker is None
            or tuple(
                window.item_id
                for window in self.manifest.windows
                if window.emitter_id == worker.emitter_id
            )
            != selected
        ):
            raise ValueError("host event windows differ from the exact selected run plan shard")
        if self.invocation is not None:
            import hashlib

            if self.invocation.shards != shards:
                raise ValueError("host event fanout differs from the producer invocation")
            if (
                self.invocation.plan_sha256
                != hashlib.sha256(plan.to_json().encode("utf-8")).hexdigest()
            ):
                raise ValueError("host event selected run plan changed before worker invocation")

    @property
    def native(self) -> bool:
        """Whether this client owns the production host-row boundary."""
        return self._native

    @property
    def native_started(self) -> bool:
        """Whether a native command has been published in this session."""
        return self._native_started

    def _inside(self, path: Path) -> Path:
        absolute = path if path.is_absolute() else self.workspace / path
        if not absolute.is_relative_to(self.workspace):
            raise ValueError("host event input escapes its isolated workspace")
        ordinary = HostEventFiles._safe_path(self.workspace, absolute.relative_to(self.workspace))
        resolved = ordinary.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("host event input must be a regular file")
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
        with self._io_lock:
            results = (*self._pending_results, *self._read_results())
            self._pending_results.clear()
            return results

    def _read_results(self) -> tuple[HostEvent, ...]:
        self._retire_local()
        pending: list[tuple[int, UUID, HostEvent, bytes]] = []
        for event_id in self._result_ids():
            path = self.files.event_path(event_id, "results")
            raw = self.files._bounded_read(path, self.manifest.limits.max_result_bytes)
            event = HostEvent.model_validate(_decode(raw))
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

    def _start_resource_consumer(self) -> None:
        if not self.native or self.invocation is None or self._resource_consumer is not None:
            return
        self._resource_consumer = threading.Thread(target=self._consume_resources, daemon=True)
        self._resource_consumer.start()

    def _consume_resources(self) -> None:
        try:
            while not self._resource_stop.wait(self.manifest.limits.poll_ms / 1000):
                with self._io_lock:
                    results = self._read_results()
                    for result in results:
                        if isinstance(result.body, ProtocolFaultBody):
                            raise HostProtocolError(
                                result.body.code, "native resource session failed"
                            )
                    for result in results:
                        if result.kind in {"job.sample", "process.rollcall"}:
                            self._consume(result)
                        else:
                            self._pending_results.append(result)
        except (ValueError, OSError, TimeoutError) as error:
            self._resource_error = error
            self._resource_stop.set()

    def _stop_resource_consumer(self) -> None:
        self._resource_stop.set()
        if self._resource_consumer is not None:
            self._resource_consumer.join()

    def _raise_resource_error(self) -> None:
        if self._resource_error is not None:
            raise self._resource_error

    def _retire_local(self) -> None:
        for event_id in tuple(self._retirement_candidates):
            try:
                retired = self.files.bookkeeping.retire(event_id, now_ms=_monotonic_ms())
            except HostProtocolError as error:
                if error.code == ProtocolFaultCode.STATE:
                    continue
                raise
            self._retirement_candidates.difference_update(retired)

    def _publish(self, command: HostEvent) -> None:
        limits = self.manifest.limits
        capacity = min(limits.max_files, self.manifest.pending_event_limit)
        reserve = (4 if command.kind in {"host.probe", "host.target", "host.clock"} else 2) + (
            2 if self.manifest.controls.memory_profiling_enabled else 0
        )
        deadline = _monotonic_ms() + limits.retry_window_ms
        while True:
            with self._io_lock:
                if command.kind != "monitor.stop":
                    self._raise_resource_error()
                self._retire_local()
                if len(self.files.bookkeeping._events) <= capacity - reserve:
                    self.files.publish(command, now_ms=_monotonic_ms())
                    return
            if _monotonic_ms() >= deadline:
                raise HostProtocolError(
                    ProtocolFaultCode.BOUNDS, "pending native evidence has not become retireable"
                )
            time.sleep(limits.poll_ms / 1000)

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
        with self._io_lock:
            self._consume_locked(event)

    def _consume_locked(self, event: HostEvent) -> None:
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
        cap = (
            self.manifest.limits.max_command_bytes
            if direction == "inbox"
            else self.manifest.limits.max_result_bytes
        )
        raw = self.files._bounded_read(original, cap)
        if HostEvent.model_validate(_decode(raw)) != event:
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
            self.files.bookkeeping.mark_consumed(event.event_id)
            self._retirement_candidates.add(event.reply_to or event.event_id)
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
        self.files.bookkeeping.mark_consumed(event.event_id)
        self._retirement_candidates.add(event.reply_to or event.event_id)

    def _wait(
        self,
        command: HostEvent | None,
        expected: set[str],
        *,
        timeout_ms: int,
    ) -> HostEvent | None:
        deadline = _monotonic_ms() + timeout_ms
        while True:
            if command is None or command.kind != "monitor.stop":
                self._raise_resource_error()
            results = self._new_results()
            for result in results:
                if result.kind in {"job.sample", "process.rollcall"}:
                    self._consume(result)
                    continue
                if result.reply_to is None and isinstance(result.body, ProtocolFaultBody):
                    raise HostProtocolError(result.body.code, "uncorrelated host protocol fault")
            for result in results:
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
            if self._native:
                raise HostProtocolError(ProtocolFaultCode.STORE, "native monitor is unavailable")
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
            if self._native:
                raise HostProtocolError(
                    ProtocolFaultCode.STORE, "native monitor readiness timed out"
                )
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
        if self._native:
            self._native_started = True
        self._publish(command)
        reply = self._wait(
            command,
            {"worker.registered"},
            timeout_ms=self.manifest.limits.ack_timeout_ms,
        )
        if reply is None:
            if self._native:
                raise HostProtocolError(
                    ProtocolFaultCode.STORE, "native worker registration timed out"
                )
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

    def native_watch(
        self,
        *,
        item_id: str,
        interval_s: float = 0,
        on_tick: Callable[[float], None] | None = None,
    ) -> NativeWatch:
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
        return NativeWatch(
            self,
            WindowBody(
                window_id=declared.window_id,
                item_id=declared.item_id,
                target=worker.target,
                server=worker.server,
            ),
            interval_s=interval_s,
            on_tick=on_tick,
        )

    def _window_command(
        self,
        kind: str,
        body: WindowBody | WindowAbortBody,
    ) -> HostEvent | None:
        self._raise_resource_error()
        if not self._healthy or self._worker_id is None:
            return None
        command = self._event(kind, self._worker_id, body)
        self._publish(command)
        expected = {"window.begun"} if kind == "window.begin" else {"window.result"}
        reply = self._wait(command, expected, timeout_ms=self.manifest.limits.ack_timeout_ms)
        if reply is None:
            self._healthy = False
            _LOG.warning("host event window unavailable kind=%s reason=timed_out", kind)
        return reply

    def begin_job(self) -> bool:
        self._raise_resource_error()
        if self._job_begun:
            return self._healthy
        if self._native and not self._registered:
            worker = next(
                (
                    entry
                    for entry in self.manifest.workers
                    if entry.target.pid == os.getpid()
                ),
                None,
            )
            selected_server_pid = (
                worker.server.pid
                if worker is not None and worker.server is not None
                else None
            )
            if not self.register_worker(server_pid=selected_server_pid):
                return False
        if not self._healthy:
            return False
        if self.invocation is not None and not self.invocation.host_enabled:
            self._job_begun = True
            self._start_resource_consumer()
            return True
        self._host_command("host.probe")
        if self._last_host_result is not None and self.manifest.cpu_target is not None:
            self._host_command("host.target")
        self._job_begun = True
        self._start_resource_consumer()
        return True

    def end_job(self) -> bool:
        self._stop_resource_consumer()
        if self._job_ended:
            self._raise_resource_error()
            return self._healthy
        if not self._healthy:
            if self.native:
                raise HostProtocolError(
                    ProtocolFaultCode.STORE, "native session failed before close"
                )
            return False
        try:
            self._raise_resource_error()
            if self._last_host_result is not None:
                self._host_command("host.clock")
        finally:
            failed = sys.exception()
            self._job_ended = True
            if self.native:
                try:
                    reason: Literal["completed", "cancelled", "failed"] = (
                        "completed"
                        if failed is None
                        else "failed"
                        if isinstance(failed, Exception)
                        else "cancelled"
                    )
                    self.stop(reason=reason)
                    self._save_receipt()
                except (ValueError, OSError, HostProtocolError, TimeoutError) as error:
                    if failed is None:
                        raise
                    failed.add_note(f"native host drain also failed: {type(error).__name__}")
        return True

    def stop(
        self, *, reason: Literal["completed", "cancelled", "failed"] = "completed"
    ) -> HostEvent:
        """Drain the same monitor before a publisher uses its native file evidence."""
        self._stop_resource_consumer()
        if self._stopped is not None:
            return self._stopped
        command = self._event(
            "monitor.stop", self.manifest.operator_emitter_id, StopBody(reason=reason)
        )
        write_document(self.manifest_path.parent / "stop.json", command)
        self._publish(command)
        result = self._wait(
            command, {"monitor.stopped"}, timeout_ms=self.manifest.limits.drain_timeout_ms
        )
        if result is None:
            raise HostProtocolError(ProtocolFaultCode.STORE, "native monitor drain timed out")
        self._stopped = result
        write_document(self.manifest_path.parent / "drained.json", result)
        return result

    def host_facts(self) -> host.HostFacts:
        """Reuse native probe facts without a second Python host measurement."""
        row = self._host_result.row if self._host_result is not None else None
        return host.HostFacts(
            cpu_model=row.cpu_model if row else None,
            runner_name=row.runner_name if row else None,
            job=self.manifest.job,
        )

    def publication_receipt(self) -> HostPublicationReceipt:
        """Close and drain before handing unchanged native bytes to any publisher."""
        if not self.native:
            raise ValueError("shadow evidence cannot enter production publication")
        self.end_job()
        self.stop()
        return self._save_receipt()

    def _save_receipt(self) -> HostPublicationReceipt:
        identity = HostWriterIdentity(
            **self.manifest.model_dump(include={"run_id", "attempt", "job", "shard", "git_sha"}),
            producer="telemetry.silicon",
        )
        if not self._verified_writes and (self.invocation is None or self.invocation.host_enabled):
            raise ValueError("native host session has no completed verified file evidence")
        if (
            self.invocation is not None
            and not self.invocation.host_enabled
            and self._verified_writes
        ):
            raise ValueError("disabled native host session unexpectedly completed host files")
        receipt = HostPublicationReceipt(
            version="2026-10-09", identity=identity, writes=self._verified_writes
        )
        receipt_path = self.manifest_path.parent / "receipt.json"
        write_document(receipt_path, receipt)
        return receipt

    def _host_command(self, kind: str) -> None:
        if self.invocation is not None and not self.invocation.host_enabled:
            raise ValueError("disabled native host invocation cannot issue a host command")
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
        if self._native:
            write_document(self.manifest_path.parent / f"operator-{command.sequence}.json", command)
        if self._native:
            self._native_started = True
        self._publish(command)
        result = self._wait_host(
            command,
            expected={
                "host.result",
                "host.write.plan",
                "host.write.completed",
                "instrument.skipped",
            },
        )
        if result is None:
            raise TimeoutError(f"{kind} result timed out")
        if isinstance(result.body, HostResultBody):
            self._last_host_result = result.event_id
            self._host_result = result.body
        elif isinstance(result.body, InstrumentSkippedBody):
            _LOG.warning("host event instrument unavailable kind=%s", kind)
        else:
            raise HostProtocolError(
                ProtocolFaultCode.IDENTITY, "host command returned another body"
            )

    def _wait_host(
        self, command: HostEvent, *, expected: set[str] | None = None
    ) -> HostEvent | None:
        expected = expected or {"host.result", "instrument.skipped", "protocol.fault"}
        seen_kinds: set[str] = set()
        completion_event_id: UUID | None = None
        host_result: HostResultBody | None = None
        host_result_event: HostEvent | None = None
        plan: HostWritePlan | None = None
        completion: HostWriteCompletion | None = None
        deadline = _monotonic_ms() + self.manifest.limits.ack_timeout_ms
        while True:
            self._raise_resource_error()
            pending: list[HostEvent] = []
            for result in self._new_results():
                if isinstance(result.body, ProtocolFaultBody) and result.reply_to in (
                    None,
                    command.event_id,
                ):
                    raise HostProtocolError(result.body.code, "host command failed")
                if result.kind in {"job.sample", "process.rollcall"}:
                    self._consume(result)
                if result.reply_to == command.event_id:
                    if result.kind not in expected | {"protocol.fault"}:
                        raise HostProtocolError(
                            ProtocolFaultCode.IDENTITY, "host reply kind differs from its command"
                        )
                    pending.append(result)
            for result in sorted(pending, key=lambda event: event.sequence):
                if result.kind == "host.write.plan":
                    if (
                        not isinstance(result.body, WritePlanBody)
                        or result.body.plan.event_id != command.event_id
                    ):
                        raise HostProtocolError(
                            ProtocolFaultCode.IDENTITY, "host write plan differs from command"
                        )
                    plan = result.body.plan
                elif result.kind == "host.write.completed":
                    if (
                        not isinstance(result.body, WriteCompletedBody)
                        or result.body.completion.event_id != command.event_id
                    ):
                        raise HostProtocolError(
                            ProtocolFaultCode.IDENTITY,
                            "host completion receipt differs from command",
                        )
                    completion_event_id = result.event_id
                    completion = result.body.completion
                elif result.kind == "host.result":
                    if not isinstance(result.body, HostResultBody):
                        raise HostProtocolError(
                            ProtocolFaultCode.IDENTITY, "host result body differs from command"
                        )
                    host_result = result.body
                    host_result_event = result
                self._consume(result)
                seen_kinds.add(result.kind)
                if result.kind == "instrument.skipped" and "instrument.skipped" in expected:
                    self._consume(command)
                    return result
            if (
                host_result_event is not None
                and "host.result" in expected
                and (
                    not {"host.write.plan", "host.write.completed"} <= expected
                    or {"host.write.plan", "host.write.completed"} <= seen_kinds
                )
            ):
                if {"host.write.plan", "host.write.completed"} <= expected and (
                    completion_event_id is None
                    or host_result is None
                    or completion_event_id not in host_result.completion_event_ids
                ):
                    raise HostProtocolError(
                        ProtocolFaultCode.IDENTITY,
                        "host result does not reference its completion receipt",
                    )
                if self._native:
                    if plan is None or completion is None:
                        raise HostProtocolError(
                            ProtocolFaultCode.STORE, "native result has no completed write plan"
                        )
                    if (
                        host_result is None
                        or len(plan.files) != 1
                        or any(
                            getattr(plan.files[0].rows[0], name) != getattr(host_result.row, name)
                            for name in type(host_result.row).model_fields
                        )
                    ):
                        raise HostProtocolError(
                            ProtocolFaultCode.IDENTITY,
                            "native host result differs from its file row",
                        )
                    assert isinstance(command.body, HostCommandBody)
                    if host_result.cpu.target != command.body.target:
                        raise HostProtocolError(
                            ProtocolFaultCode.TARGET,
                            "native probe captured another selected target",
                        )
                    verified = verify_host_output(
                        plan,
                        completion,
                        workspace_root=self.workspace,
                        target_root=self.manifest.output_roots[0],
                        publication_identity=HostWriterIdentity(
                            **self.manifest.model_dump(
                                include={"run_id", "attempt", "job", "shard", "git_sha"}
                            ),
                            producer="telemetry.silicon",
                        ),
                        limits=self._verification_limits,
                        previous_plan=self._previous_plan,
                    )
                    for file in verified.files:
                        name = f"{plan.target_root}/{file.relative_path}"
                        old = self._verified_writes.get(name)
                        if old is not None and old != file.physical_sha256:
                            raise ValueError("native host bytes changed across completed plans")
                        if old is None:
                            self._verified_writes[name] = file.physical_sha256
                            self._verified_bytes += file.size_bytes
                    if (
                        len(self._verified_writes) > self._verification_limits.max_files
                        or self._verified_bytes > self._verification_limits.max_total_bytes
                    ):
                        raise ValueError("native receipt exceeds aggregate file or byte limits")
                    self._previous_plan = plan
                self._consume(command)
                return host_result_event
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
                except (OSError, ValueError, TimeoutError) as event_error:
                    assert exc is not None
                    exc.add_note(f"host event abort also failed: {type(event_error).__name__}")
            self._closed = True
        suppressed = self._watch.__exit__(exc_type, exc, traceback)
        return suppressed if isinstance(suppressed, bool) else None


class NativeWatch:
    """Use the Rust window result as the item-health host-cell source."""

    def __init__(
        self,
        client: HostEventClient,
        body: WindowBody,
        *,
        interval_s: float = 0,
        on_tick: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._body = body
        self._closed = False
        self._result: WindowResultBody | None = None
        self._interval_s = interval_s
        self._on_tick = on_tick
        self._started = 0.0
        self._stop_heartbeat = threading.Event()
        self._heartbeat: threading.Thread | None = None

    def _tick(self) -> None:
        while not self._stop_heartbeat.wait(self._interval_s):
            if self._on_tick is not None:
                self._on_tick(time.monotonic() - self._started)

    def _close_heartbeat(self) -> None:
        self._stop_heartbeat.set()
        if self._heartbeat is not None:
            self._heartbeat.join()

    def __enter__(self) -> NativeWatch:
        self._started = time.monotonic()
        begun = self._client._window_command("window.begin", self._body)
        if begun is None:
            raise HostProtocolError(ProtocolFaultCode.STORE, "native window begin timed out")
        if self._interval_s > 0 and self._on_tick is not None:
            self._heartbeat = threading.Thread(target=self._tick, daemon=True)
            self._heartbeat.start()
        return self

    def close(self) -> host.HostCells:
        if not self._closed:
            self._close_heartbeat()
            result = self._client._window_command("window.end", self._body)
            if result is None or not isinstance(result.body, WindowResultBody):
                raise HostProtocolError(
                    ProtocolFaultCode.IDENTITY, "native window result body differs"
                )
            self._result = result.body
            self._closed = True
        if self._result is None:
            raise HostProtocolError(ProtocolFaultCode.STATE, "native window has no result")
        return host.HostCells(**self._result.cells.model_dump())

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if not self._closed:
            self._close_heartbeat()
            if exc_type is None:
                self.close()
            else:
                reason: Literal["cancelled", "work_failed"] = (
                    "cancelled" if not issubclass(exc_type, Exception) else "work_failed"
                )
                abort = WindowAbortBody(**self._body.model_dump(), reason=reason)
                try:
                    self._client._window_command("window.abort", abort)
                except (OSError, ValueError, TimeoutError) as event_error:
                    assert exc is not None
                    exc.add_note(f"native host abort also failed: {type(event_error).__name__}")
                self._closed = True
        return None
