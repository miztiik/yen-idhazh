"""Read, publish and retire only named immutable messages in a bounded host session."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NoReturn, cast
from uuid import UUID, uuid4

from idhazh.contracts.host_events import (
    COMMAND_KINDS,
    MEMORY_SOURCES,
    HostCommandBody,
    HostEvent,
    HostEventLimits,
    HostResultBody,
    HostSessionManifest,
    InstrumentSkippedBody,
    JobSampleBody,
    MonitorReadyBody,
    ProcessRollcallBody,
    ProcessTarget,
    ProtocolFaultBody,
    ProtocolFaultCode,
    StoppedBody,
    WindowBegunBody,
    WindowBody,
    WindowResultBody,
    WorkerBody,
    WriteCompletedBody,
    WritePlanBody,
)
from idhazh.contracts.host_output import INT64_MAX, HostPlannedFile, HostWritePlan

_CLOCK_FIELDS = frozenset(
    {"model_load_ms", "job_seconds", "server_prompt_tokens", "server_prompt_seconds"}
)
_TARGET_FIELDS = frozenset(
    {"cpu_allowed_processors", "cpu_quota_cores", "cpu_quota_state", "cpu_target_measured_at"}
)


class HostProtocolError(ValueError):
    """A refused exchange, distinct from an unavailable optional instrument."""

    def __init__(self, code: ProtocolFaultCode, message: str) -> None:
        self.code = code
        super().__init__(message)


def _refuse(code: ProtocolFaultCode, message: str) -> NoReturn:
    raise HostProtocolError(code, message)


def _tick(value: int) -> None:
    if type(value) is not int or not 0 <= value <= INT64_MAX:
        _refuse(ProtocolFaultCode.BOUNDS, "local monotonic milliseconds must be an int64")


def event_bytes(event: HostEvent) -> bytes:
    """One canonical UTF-8 JSON object followed by LF, never CRLF."""
    return (
        json.dumps(
            event.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _refuse(ProtocolFaultCode.DUPLICATE, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _decode(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or b"\r" in raw:
        _refuse(ProtocolFaultCode.STATE, "published JSON requires LF and no CR")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise HostProtocolError(ProtocolFaultCode.STATE, "malformed published JSON") from error
    if not isinstance(value, dict):
        _refuse(ProtocolFaultCode.STATE, "published JSON must be one object")
    return cast(dict[str, Any], value)


@dataclass(frozen=True)
class EventAcceptance:
    event: HostEvent
    replayed: bool
    replies: tuple[HostEvent, ...]


class HostSessionBookkeeping:
    """Validate exchange order without collecting or writing host rows."""

    def __init__(self, manifest: HostSessionManifest) -> None:
        self.manifest = HostSessionManifest.model_validate(manifest.model_dump(mode="json"))
        self._events: dict[UUID, HostEvent] = {}
        self._digests: dict[UUID, str] = {}
        self._sizes: dict[UUID, int] = {}
        self._sequences: dict[str, int] = {}
        self._replies: dict[UUID, tuple[UUID, ...]] = {}
        self._terminal: set[UUID] = set()
        self._consumed: set[UUID] = set()
        self._received_at: dict[UUID, int] = {}
        self._registered: set[str] = set()
        self._cpu_target = self.manifest.cpu_target
        self._windows: dict[UUID, str] = {}
        self._window_opened: dict[UUID, str] = {}
        self._aborted: set[UUID] = set()
        self._cancelled_begins: set[UUID] = set()
        self._plans: dict[UUID, WritePlanBody] = {}
        self._completions: dict[UUID, WriteCompletedBody] = {}
        self._completed_files: dict[UUID, tuple[HostWritePlan, HostPlannedFile]] = {}
        self._last_host: HostEvent | None = None
        self._last_plan: WritePlanBody | None = None
        self._phase = "starting"
        self.total_events = 0
        self.total_bytes = 0
        self._now_ms = 0

    @property
    def cpu_target(self) -> ProcessTarget | None:
        """The operator's target, or the first registration ACK's selected process."""
        return self._cpu_target

    def _checkpoint(self) -> dict[str, Any]:
        return {
            name: value.copy() if isinstance(value, (dict, set)) else value
            for name, value in self.__dict__.items()
        }

    def _restore(self, checkpoint: dict[str, Any]) -> None:
        self.__dict__.update(checkpoint)

    def accept(
        self, event: HostEvent, *, now_ms: int, raw: bytes | None = None
    ) -> EventAcceptance:
        """Identical retries return retained replies; failures leave every state unchanged."""
        _tick(now_ms)
        event = HostEvent.model_validate(event.model_dump(mode="json"))
        if now_ms < self._now_ms:
            _refuse(ProtocolFaultCode.ORDER, "local monotonic time moved backwards")
        if raw is None:
            raw = event_bytes(event)
        elif HostEvent.model_validate(_decode(raw)) != event:
            _refuse(ProtocolFaultCode.IDENTITY, "accepted bytes differ from the typed event")
        digest = hashlib.sha256(raw).hexdigest()
        if event.event_id in self._digests:
            if self._digests[event.event_id] != digest:
                _refuse(ProtocolFaultCode.DUPLICATE, "event ID reused with different content")
            if event.event_id not in self._events:
                _refuse(ProtocolFaultCode.RETIRED, "event is outside the retained recovery window")
            for member in (event.event_id, *self._replies.get(event.event_id, ())):
                self._received_at[member] = now_ms
            self._now_ms = now_ms
            return EventAcceptance(
                event,
                True,
                tuple(self._events[reply] for reply in self._replies.get(event.event_id, ())),
            )
        limits = self.manifest.limits
        cap = limits.max_command_bytes if event.kind in COMMAND_KINDS else limits.max_result_bytes
        if (
            len(raw) > cap
            or self.total_events >= limits.max_session_events
            or self.total_bytes + len(raw) > limits.max_session_bytes
            or len(self._events)
            >= min(
                limits.max_files,
                4 * len(self._registered) + limits.max_concurrent_windows + 8,
            )
        ):
            _refuse(ProtocolFaultCode.BOUNDS, "session event/byte/pending capacity exhausted")
        self._identity(event)
        if event.sequence <= self._sequences.get(event.emitter_id, 0):
            _refuse(ProtocolFaultCode.ORDER, "new event sequence must increase per emitter")
        checkpoint = self._checkpoint()
        try:
            self._transition(event)
            self._events[event.event_id] = event
            self._digests[event.event_id] = digest
            self._sizes[event.event_id] = len(raw)
            self._sequences[event.emitter_id] = event.sequence
            self._received_at[event.event_id] = now_ms
            if event.reply_to is not None:
                self._replies[event.reply_to] = (
                    *self._replies.get(event.reply_to, ()),
                    event.event_id,
                )
            self.total_events += 1
            self.total_bytes += len(raw)
            self._now_ms = now_ms
        except Exception:
            self._restore(checkpoint)
            raise
        return EventAcceptance(event, False, ())

    def _identity(self, event: HostEvent) -> None:
        manifest = self.manifest
        if any(
            getattr(event, name) != getattr(manifest, name)
            for name in ("date", "run_id", "attempt", "job", "shard", "session_id")
        ):
            _refuse(ProtocolFaultCode.IDENTITY, "event belongs to another invocation/session")
        workers = {worker.emitter_id: worker for worker in manifest.workers}
        if event.kind in COMMAND_KINDS:
            expected: str | None
            if event.kind.startswith(("host.", "monitor.")):
                expected = manifest.operator_emitter_id
            else:
                expected = event.emitter_id if event.emitter_id in workers else None
            if event.emitter_id != expected:
                _refuse(ProtocolFaultCode.IDENTITY, "command came from an undeclared emitter")
        elif event.emitter_id != manifest.monitor_emitter_id:
            _refuse(ProtocolFaultCode.IDENTITY, "result did not come from the declared monitor")
        body = event.body
        if isinstance(body, WorkerBody):
            worker_id = event.emitter_id
            if event.reply_to is not None and event.reply_to in self._events:
                worker_id = self._events[event.reply_to].emitter_id
            worker = workers.get(worker_id)
            if worker is None or (body.target, body.server) != (worker.target, worker.server):
                _refuse(ProtocolFaultCode.TARGET, "worker PID/start ticks or server changed")
            if body.memory_profiling_enabled != manifest.controls.memory_profiling_enabled:
                _refuse(ProtocolFaultCode.IDENTITY, "worker memory control differs from manifest")
        if isinstance(body, WindowBody):
            declared = next(
                (window for window in manifest.windows if window.window_id == body.window_id),
                None,
            )
            if declared is None or declared.item_id != body.item_id:
                _refuse(ProtocolFaultCode.IDENTITY, "window/item is not declared")
            if event.kind in COMMAND_KINDS and event.emitter_id != declared.emitter_id:
                _refuse(ProtocolFaultCode.IDENTITY, "window command belongs to another worker")
            worker = workers[declared.emitter_id]
            if (body.target, body.server) != (worker.target, worker.server):
                _refuse(ProtocolFaultCode.TARGET, "window target differs from registered identity")
            if isinstance(body, WindowResultBody):
                if body.memory_profiling_enabled != manifest.controls.memory_profiling_enabled:
                    _refuse(ProtocolFaultCode.IDENTITY, "window memory control differs")
        if isinstance(body, HostCommandBody):
            target_matches = body.target == self._cpu_target
            if event.kind == "host.probe" and body.target is None:
                target_matches = True
            if body.controls != manifest.controls or not target_matches:
                _refuse(ProtocolFaultCode.TARGET, "host controls/target differ from manifest")
            names = {entry.name for entry in manifest.named_inputs}
            if not set(body.input_names) <= names:
                _refuse(ProtocolFaultCode.IDENTITY, "host command references undeclared input")
            if event.kind == "host.target" and body.target is None:
                _refuse(ProtocolFaultCode.TARGET, "target enrichment requires a selected process")
        if not manifest.controls.memory_profiling_enabled:
            if isinstance(body, (JobSampleBody, ProcessRollcallBody)):
                _refuse(ProtocolFaultCode.STATE, "memory off forbids sample and rollcall artifacts")
            if isinstance(body, HostResultBody):
                for source in body.cpu.sources:
                    if source.source in MEMORY_SOURCES:
                        _refuse(ProtocolFaultCode.STATE, "memory off forbids memory observations")
        if isinstance(body, ProcessRollcallBody):
            if len(body.records) > manifest.capture_limits.max_processes:
                _refuse(ProtocolFaultCode.BOUNDS, "rollcall exceeds process cap")
            if len({record.pid for record in body.records}) != len(body.records):
                _refuse(ProtocolFaultCode.DUPLICATE, "rollcall repeats a PID")
        if isinstance(body, JobSampleBody):
            if body.record.python_procs > manifest.capture_limits.max_processes:
                _refuse(ProtocolFaultCode.BOUNDS, "job sample exceeds process population cap")
        if isinstance(body, HostResultBody):
            ids = body.cpu.online_cpu_ids
            if len(ids) > manifest.capture_limits.max_cpu_ids or (
                ids and ids[-1] > manifest.capture_limits.max_cpu_id
            ):
                _refuse(ProtocolFaultCode.BOUNDS, "CPU evidence exceeds declared ID bounds")

    def _request(
        self, event: HostEvent, kinds: set[str], *, cancelled_begin: bool = False
    ) -> HostEvent:
        request = self._events.get(event.reply_to) if event.reply_to is not None else None
        if (
            request is None
            or request.kind not in kinds
            or (
                request.event_id in self._terminal
                and not (cancelled_begin and request.event_id in self._cancelled_begins)
            )
        ):
            _refuse(ProtocolFaultCode.STATE, "reply has no matching unfinished command")
        assert request is not None
        if isinstance(event.body, WindowBody) and isinstance(request.body, WindowBody):
            if event.body.window_id != request.body.window_id:
                _refuse(ProtocolFaultCode.IDENTITY, "reply names another window")
        return request

    @staticmethod
    def _owned_cells(before: HostPlannedFile, after: HostPlannedFile, kind: str) -> None:
        allowed = (
            _CLOCK_FIELDS
            if kind == "host.clock"
            else _TARGET_FIELDS
            if kind == "host.target"
            else ()
        )
        row = before.rows[0]
        if any(
            getattr(row, name) != getattr(after.rows[0], name)
            for name in type(row).model_fields
            if name not in allowed
        ):
            _refuse(ProtocolFaultCode.STATE, "host command changed another instrument's cells")

    def _completed_successor(self, plan: HostWritePlan, kind: str) -> None:
        current = {file.envelope.unit_id: file for file in plan.files}
        if not self._completed_files.keys() <= current.keys():
            _refuse(ProtocolFaultCode.IDENTITY, "successor omitted a completed work unit")
        for unit, (previous, old) in self._completed_files.items():
            new = current[unit]
            before = previous.model_copy(update={"files": (old,)})
            after = plan.model_copy(update={"files": (new,)})
            if new.envelope.content_sha256 == old.envelope.content_sha256:
                # Other days may change under a new command; this completed file may not.
                after = after.model_copy(update={"event_id": before.event_id})
            after.validate_successor(before)
            self._owned_cells(old, new, kind)

    def _resolve_cancelled_begin(self, event: HostEvent, window_id: UUID) -> None:
        for pending in self._events.values():
            if (
                pending.kind == "window.begin"
                and isinstance(pending.body, WindowBody)
                and pending.body.window_id == window_id
                and pending.event_id not in self._terminal
            ):
                self._terminal.add(pending.event_id)
                self._cancelled_begins.add(pending.event_id)
                self._replies[pending.event_id] = (
                    *self._replies.get(pending.event_id, ()),
                    event.event_id,
                )

    def _transition(self, event: HostEvent) -> None:
        body, kind = event.body, event.kind
        if kind == "monitor.ready":
            assert isinstance(body, MonitorReadyBody)
            if self._phase != "starting" or body.boot_id != self.manifest.boot_id:
                _refuse(ProtocolFaultCode.IDENTITY, "readiness phase or boot identity conflicts")
            self._phase = "ready"
            return
        late_begin_failure = kind == "window.result" and event.reply_to in self._cancelled_begins
        if self._phase == "starting" or (self._phase == "stopped" and not late_begin_failure):
            _refuse(ProtocolFaultCode.STATE, "monitor is not ready or has stopped")
        if kind in COMMAND_KINDS and self._phase == "stopping":
            _refuse(ProtocolFaultCode.STATE, "monitor is draining; new commands are refused")
        if kind == "worker.register":
            if event.emitter_id in self._registered or any(
                old.kind == kind and old.emitter_id == event.emitter_id
                for old in self._events.values()
            ):
                _refuse(ProtocolFaultCode.STATE, "worker already registering or registered")
        elif kind == "worker.registered":
            request = self._request(event, {"worker.register"})
            if body != request.body:
                _refuse(ProtocolFaultCode.TARGET, "registration ACK changed the worker targets")
            self._registered.add(request.emitter_id)
            assert isinstance(body, WorkerBody)
            if self._cpu_target is None:
                self._cpu_target = body.server or body.target
            self._terminal.add(request.event_id)
        elif kind in ("window.begin", "window.end", "window.abort"):
            assert isinstance(body, WindowBody)
            if event.emitter_id not in self._registered:
                _refuse(ProtocolFaultCode.STATE, "window requires registration ACK")
            state = self._windows.get(body.window_id)
            if kind == "window.begin":
                if state is not None:
                    _refuse(ProtocolFaultCode.STATE, "window already began")
                active = sum(value != "complete" for value in self._windows.values())
                if active >= self.manifest.limits.max_concurrent_windows:
                    _refuse(ProtocolFaultCode.BOUNDS, "active-window concurrency exhausted")
                self._windows[body.window_id] = "opening"
            elif kind == "window.end":
                if state != "begun":
                    _refuse(ProtocolFaultCode.STATE, "end requires opening snapshot ACK")
                self._windows[body.window_id] = "closing"
            else:
                if state not in ("opening", "begun"):
                    _refuse(ProtocolFaultCode.STATE, "abort requires an unresolved open window")
                self._windows[body.window_id] = "aborting"
        elif kind == "window.begun":
            request = self._request(event, {"window.begin"})
            assert isinstance(body, WindowBegunBody)
            if self._windows.get(body.window_id) != "opening":
                _refuse(ProtocolFaultCode.STATE, "opening snapshot ACK arrived after abort")
            self._windows[body.window_id] = "begun"
            self._window_opened[body.window_id] = body.captured_at
            self._terminal.add(request.event_id)
        elif kind == "window.result":
            request = self._request(
                event,
                {"window.begin", "window.end", "window.abort", "monitor.stop"},
                cancelled_begin=True,
            )
            assert isinstance(body, WindowResultBody)
            state = self._windows.get(body.window_id)
            if request.kind == "monitor.stop":
                if state not in ("opening", "begun", "closing", "aborting"):
                    _refuse(ProtocolFaultCode.STATE, "stop result has no unresolved window")
            elif request.kind == "window.begin":
                if (
                    state != "aborting"
                    and not (state == "complete" and body.window_id in self._aborted)
                    and not (self._phase == "stopping" and state == "opening")
                ):
                    _refuse(ProtocolFaultCode.STATE, "begin failure requires abort or shutdown")
            elif state != ("closing" if request.kind == "window.end" else "aborting"):
                _refuse(ProtocolFaultCode.STATE, "window result has no closing/abort command")
            if request.kind != "window.end":
                if body.status != "incomplete" or any(
                    value is not None for value in body.cells.model_dump().values()
                ):
                    _refuse(ProtocolFaultCode.STATE, "abort requires incomplete null cells")
                self._aborted.add(body.window_id)
            elif body.opened_at != self._window_opened.get(body.window_id):
                _refuse(ProtocolFaultCode.IDENTITY, "result changed the opening snapshot time")
            if self._phase == "stopping" and body.status == "incomplete":
                self._aborted.add(body.window_id)
            if request.kind != "window.begin" or state != "aborting":
                self._windows[body.window_id] = "complete"
                if request.kind in ("window.abort", "monitor.stop"):
                    self._resolve_cancelled_begin(event, body.window_id)
            if request.kind != "monitor.stop":
                self._terminal.add(request.event_id)
            if request.kind == "window.begin":
                self._cancelled_begins.discard(request.event_id)
        elif kind.startswith("host.") and kind in COMMAND_KINDS:
            assert isinstance(body, HostCommandBody)
            if any(
                old.kind in {"host.probe", "host.target", "host.clock"}
                and old.event_id not in self._terminal
                for old in self._events.values()
            ):
                _refuse(ProtocolFaultCode.STATE, "another host command is unresolved")
            if kind == "host.probe":
                if self._last_host is not None or body.previous_result_id is not None:
                    _refuse(ProtocolFaultCode.STATE, "probe cannot replace an existing whole row")
            elif self._last_host is None or body.previous_result_id != self._last_host.event_id:
                _refuse(ProtocolFaultCode.IDENTITY, "enrichment requires the latest whole row")
            if kind == "host.target":
                selected = [
                    worker.emitter_id
                    for worker in self.manifest.workers
                    if self._cpu_target in (worker.target, worker.server)
                ]
                if not self._registered.intersection(selected):
                    _refuse(ProtocolFaultCode.STATE, "target capture requires registration ACK")
        elif kind == "host.write.plan":
            request = self._request(event, {"host.probe", "host.target", "host.clock"})
            assert isinstance(body, WritePlanBody)
            plan = body.plan
            if (
                plan.event_id != request.event_id
                or plan.target_root not in self.manifest.output_roots
            ):
                _refuse(ProtocolFaultCode.IDENTITY, "plan references another event or output root")
            invocation = plan.publication_identity
            if any(
                getattr(invocation, name) != getattr(self.manifest, name)
                for name in ("run_id", "attempt", "job", "shard", "git_sha")
            ):
                _refuse(ProtocolFaultCode.IDENTITY, "plan has another publication invocation")
            if request.event_id in self._plans:
                _refuse(ProtocolFaultCode.DUPLICATE, "command already has an immutable plan")
            assert isinstance(request.body, HostCommandBody)
            if request.body.target is None and any(
                getattr(file.rows[0], name) is not None
                for file in plan.files
                for name in _TARGET_FIELDS
            ):
                _refuse(ProtocolFaultCode.TARGET, "targetless command requires null target cells")
            if self._last_plan is not None:
                plan.validate_successor(self._last_plan.plan)
                prior_files = {
                    file.envelope.unit_id: file for file in self._last_plan.plan.files
                }
                prior_files.update(
                    {unit: file for unit, (_, file) in self._completed_files.items()}
                )
                for file in plan.files:
                    self._owned_cells(prior_files[file.envelope.unit_id], file, request.kind)
            self._completed_successor(plan, request.kind)
            self._plans[request.event_id] = body
        elif kind == "host.write.completed":
            request = self._request(event, {"host.probe", "host.target", "host.clock"})
            assert isinstance(body, WriteCompletedBody)
            plan_body = self._plans.get(request.event_id)
            if plan_body is None:
                _refuse(ProtocolFaultCode.STATE, "completion requires an immutable plan")
            assert plan_body is not None
            body.completion.validate_plan(plan_body.plan, require_all=False)
            prior = [
                completed.completion.receipt.writes
                for completed in self._completions.values()
                if completed.completion.event_id == request.event_id
            ]
            if any(
                not set(writes) <= set(body.completion.receipt.writes)
                or any(
                    body.completion.receipt.writes[path] != digest
                    for path, digest in writes.items()
                )
                for writes in prior
            ):
                _refuse(ProtocolFaultCode.STORE, "completion lost/changed earlier evidence")
            self._completions[event.event_id] = body
            for file in plan_body.plan.files:
                path = f"{plan_body.plan.target_root}/{file.relative_path}"
                if path in body.completion.receipt.writes:
                    self._completed_files[file.envelope.unit_id] = (plan_body.plan, file)
        elif kind in ("host.result", "instrument.skipped"):
            request = self._request(event, {"host.probe", "host.target", "host.clock"})
            assert isinstance(body, (HostResultBody, InstrumentSkippedBody))
            if isinstance(body, InstrumentSkippedBody) and body.command_kind != request.kind:
                _refuse(ProtocolFaultCode.IDENTITY, "skipped result names another command")
            for reference in body.completion_event_ids:
                completed = self._completions.get(reference)
                if completed is None or completed.completion.event_id != request.event_id:
                    _refuse(ProtocolFaultCode.IDENTITY, "unknown or foreign completion reference")
            expected_references = {
                reference
                for reference, completed in self._completions.items()
                if completed.completion.event_id == request.event_id
            }
            if set(body.completion_event_ids) != expected_references:
                _refuse(ProtocolFaultCode.STORE, "result omitted earlier completed-file evidence")
            if isinstance(body, HostResultBody):
                assert isinstance(request.body, HostCommandBody)
                if body.cpu.target is not None and body.cpu.target != request.body.target:
                    _refuse(ProtocolFaultCode.TARGET, "CPU result captured another command target")
                if request.body.target is None and any(
                    getattr(body.row, name) is not None for name in _TARGET_FIELDS
                ):
                    _refuse(
                        ProtocolFaultCode.TARGET, "targetless command requires null target cells"
                    )
                plan_body = self._plans.get(request.event_id)
                if plan_body is None:
                    _refuse(ProtocolFaultCode.STATE, "host result requires a write plan")
                assert plan_body is not None
                latest = self._completions[body.completion_event_ids[-1]].completion
                latest.validate_plan(plan_body.plan)
                rows = [
                    file.rows[0]
                    for file in plan_body.plan.files
                    if file.rows[0].date == body.row.date
                ]
                if len(rows) != 1 or any(
                    getattr(rows[0], name) != getattr(body.row, name)
                    for name in type(body.row).model_fields
                ):
                    _refuse(ProtocolFaultCode.IDENTITY, "host result differs from its planned row")
                if self._last_host is not None and request.kind == "host.target":
                    previous = self._last_host.body
                    assert isinstance(previous, HostResultBody)
                    if (
                        body.row.cpu_allowed_processors is not None
                        and body.cpu.online_cpu_ids != previous.cpu.online_cpu_ids
                    ):
                        _refuse(
                            ProtocolFaultCode.IDENTITY,
                            "target affinity used another online snapshot",
                        )
                if self._last_host is not None and request.kind == "host.clock":
                    previous = self._last_host.body
                    assert isinstance(previous, HostResultBody)
                    if body.cpu != previous.cpu:
                        _refuse(
                            ProtocolFaultCode.STATE, "clock cannot remeasure CPU source evidence"
                        )
                self._last_host, self._last_plan = event, plan_body
            self._terminal.add(request.event_id)
        elif kind == "monitor.stop":
            self._phase = "stopping"
        elif kind == "monitor.stopped":
            request = self._request(event, {"monitor.stop"})
            assert isinstance(body, StoppedBody)
            if any(state != "complete" for state in self._windows.values()):
                _refuse(ProtocolFaultCode.STATE, "monitor stopped with unresolved windows")
            if set(body.aborted_window_ids) != self._aborted:
                _refuse(ProtocolFaultCode.IDENTITY, "stopped result omitted aborted windows")
            unfinished = {
                old.event_id
                for old in self._events.values()
                if old.kind in COMMAND_KINDS and old.event_id not in self._terminal
            }
            if unfinished != {request.event_id}:
                _refuse(ProtocolFaultCode.STATE, "monitor stopped before pending command results")
            self._terminal.add(request.event_id)
            self._phase = "stopped"
        elif kind == "protocol.fault":
            assert isinstance(body, ProtocolFaultBody)
            if event.reply_to is not None:
                request = self._request(event, set(COMMAND_KINDS))
                if body.related_event_id != request.event_id:
                    _refuse(ProtocolFaultCode.IDENTITY, "fault references another triggering event")
                self._terminal.add(request.event_id)

    def mark_consumed(self, event_id: UUID) -> None:
        """The caller explicitly confirms its result/recovery evidence was consumed."""
        if event_id not in self._events:
            _refuse(ProtocolFaultCode.RETIRED, "cannot consume unknown or retired event")
        self._consumed.add(event_id)

    def retirement_group(self, event_id: UUID, *, now_ms: int) -> tuple[UUID, ...]:
        _tick(now_ms)
        event = self._events.get(event_id)
        if event is None:
            _refuse(ProtocolFaultCode.RETIRED, "unknown or retired event")
        assert event is not None
        if event.kind in COMMAND_KINDS:
            if event_id not in self._terminal:
                _refuse(ProtocolFaultCode.STATE, "unfinished command cannot be retired")
            group = (event_id, *self._replies.get(event_id, ()))
            # Cancellation evidence can resolve both begin and abort/stop. Retain it together.
            members = set(group)
            while True:
                related = {
                    command
                    for command, replies in self._replies.items()
                    if members.intersection(replies)
                }
                expanded = members | related | {
                    reply for command in related for reply in self._replies[command]
                }
                if expanded == members:
                    break
                members = expanded
            if any(
                member not in self._terminal
                for member in members
                if self._events[member].kind in COMMAND_KINDS
            ):
                _refuse(ProtocolFaultCode.STATE, "unfinished related command cannot be retired")
            group = (*group, *sorted(members - set(group), key=str))
        elif event.reply_to is not None:
            _refuse(ProtocolFaultCode.STATE, "retire replies with their triggering command")
        else:
            group = (event_id,)
        if not set(group) <= self._consumed:
            _refuse(ProtocolFaultCode.STATE, "retirement requires all evidence to be consumed")
        if any(
            now_ms - self._received_at[member] < self.manifest.limits.retry_window_ms
            for member in group
        ):
            _refuse(ProtocolFaultCode.STATE, "retry/recovery retention window has not elapsed")
        return group

    def retire(self, event_id: UUID, *, now_ms: int) -> tuple[UUID, ...]:
        group = self.retirement_group(event_id, now_ms=now_ms)
        for member in group:
            self._events.pop(member)
            self._received_at.pop(member)
            self._consumed.discard(member)
            self._completions.pop(member, None)
            self._sizes.pop(member, None)
            self._replies.pop(member, None)
            self._plans.pop(member, None)
            self._terminal.discard(member)
            self._cancelled_begins.discard(member)
        # Digests/sequences remain as bounded tombstones: retirement never permits ID reuse.
        return group


class HostEventFiles:
    """A finite session inbox/results store; no discovery scans and no host ledger writes."""

    def __init__(self, project_root: Path, manifest: HostSessionManifest) -> None:
        self.project_root = project_root.resolve(strict=True)
        self.manifest = HostSessionManifest.model_validate(manifest.model_dump(mode="json"))
        self.bookkeeping = HostSessionBookkeeping(self.manifest)
        self.read_count = 0
        self.read_bytes = 0

    @classmethod
    def open(
        cls,
        project_root: Path,
        manifest_path: Path,
        *,
        limits: HostEventLimits,
    ) -> HostEventFiles:
        """Load one named manifest using trusted caller limits, not limits from unread bytes."""
        root = project_root.resolve(strict=True)
        try:
            relative = manifest_path.absolute().relative_to(root)
        except ValueError as error:
            raise HostProtocolError(
                ProtocolFaultCode.IDENTITY,
                "manifest escapes project root",
            ) from error
        path = cls._safe_path(root, relative)
        raw = cls._read(path, limits.max_manifest_bytes)
        if len(raw) > limits.max_read_bytes:
            _refuse(ProtocolFaultCode.BOUNDS, "manifest exceeds cumulative read budget")
        manifest = HostSessionManifest.model_validate(_decode(raw))
        if manifest.limits != limits:
            _refuse(ProtocolFaultCode.IDENTITY, "manifest limits differ from effective config")
        store = cls(root, manifest)
        store.read_count, store.read_bytes = 1, len(raw)
        return store

    @staticmethod
    def _safe_path(root: Path, relative: Path) -> Path:
        if relative.is_absolute() or any(part in (".", "..") for part in relative.parts):
            _refuse(ProtocolFaultCode.IDENTITY, "ordinary path must remain inside its root")
        path = root
        for part in relative.parts:
            path = path / part
            if path.is_symlink() or path.is_junction():
                _refuse(ProtocolFaultCode.IDENTITY, "ordinary inputs cannot follow links/junctions")
        if not path.resolve().is_relative_to(root):
            _refuse(ProtocolFaultCode.IDENTITY, "ordinary path escapes the declared root")
        return path

    @staticmethod
    def _read(path: Path, cap: int) -> bytes:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > cap:
                _refuse(ProtocolFaultCode.BOUNDS, "named input is not a bounded regular file")
            raw = stream.read(cap + 1)
            after = os.fstat(stream.fileno())
        if len(raw) > cap:
            _refuse(ProtocolFaultCode.BOUNDS, "named input exceeds its byte cap")
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            _refuse(ProtocolFaultCode.STORE, "immutable input changed during read")
        return raw

    def _bounded_read(self, path: Path, cap: int) -> bytes:
        limits = self.manifest.limits
        if self.read_count >= limits.max_reads or self.read_bytes >= limits.max_read_bytes:
            _refuse(ProtocolFaultCode.BOUNDS, "session read budget exhausted")
        available = min(cap, limits.max_read_bytes - self.read_bytes)
        self.read_count += 1
        try:
            raw = self._read(path, available)
        except Exception:
            self.read_bytes += available
            raise
        self.read_bytes += len(raw)
        return raw

    def event_path(self, event_id: UUID, direction: Literal["inbox", "results"]) -> Path:
        if not isinstance(event_id, UUID):
            _refuse(ProtocolFaultCode.IDENTITY, "event paths require validated UUID and direction")
        if direction not in ("inbox", "results"):
            _refuse(ProtocolFaultCode.IDENTITY, "event direction must be inbox or results")
        relative = Path(self.manifest.event_root) / direction / f"{event_id}.json"
        return self._safe_path(self.project_root, relative)

    def read_event(
        self,
        event_id: UUID,
        direction: Literal["inbox", "results"],
        *,
        now_ms: int,
    ) -> EventAcceptance:
        limits = self.manifest.limits
        cap = limits.max_command_bytes if direction == "inbox" else limits.max_result_bytes
        raw = self._bounded_read(self.event_path(event_id, direction), cap)
        event = HostEvent.model_validate(_decode(raw))
        if event.event_id != event_id or (event.kind in COMMAND_KINDS) != (direction == "inbox"):
            _refuse(ProtocolFaultCode.IDENTITY, "event ID or kind contradicts the named file")
        return self.bookkeeping.accept(event, now_ms=now_ms, raw=raw)

    def read_input(self, name: str) -> bytes:
        declared = next((entry for entry in self.manifest.named_inputs if entry.name == name), None)
        if declared is None:
            _refuse(ProtocolFaultCode.IDENTITY, "input is not named by the manifest")
        assert declared is not None
        path = self._safe_path(self.project_root, Path(declared.relative_path))
        limits = self.manifest.capture_limits
        if declared.source.value.startswith("proc."):
            cap = limits.max_proc_text_bytes
        elif declared.source.value.startswith(("sysfs.", "cgroup.")):
            cap = limits.max_sysfs_text_bytes
        else:
            cap = limits.max_log_bytes
        return self._bounded_read(path, cap)

    def publish(self, event: HostEvent, *, now_ms: int) -> EventAcceptance:
        direction: Literal["inbox", "results"] = (
            "inbox" if event.kind in COMMAND_KINDS else "results"
        )
        target = self.event_path(event.event_id, direction)
        checkpoint = self.bookkeeping._checkpoint()
        accepted = self.bookkeeping.accept(event, now_ms=now_ms)
        raw = event_bytes(event)
        staging: Path | None = None
        try:
            if target.exists():
                existing = self._bounded_read(target, len(raw))
                if existing != raw:
                    _refuse(ProtocolFaultCode.DUPLICATE, "immutable published event conflicts")
                return accepted
            if accepted.replayed:
                _refuse(ProtocolFaultCode.STORE, "retained immutable event file is missing")
            target.parent.mkdir(parents=True, exist_ok=True)
            staging = target.with_name(f".{target.stem}.{uuid4()}.pending")
            with staging.open("xb") as stream:
                stream.write(raw)
                stream.flush()
            # A hard-link publication is the portable atomic no-overwrite equivalent
            # of a same-filesystem rename. POSIX rename alone would replace a rival.
            try:
                os.link(staging, target)
            except FileExistsError:
                if self._bounded_read(target, len(raw)) != raw:
                    _refuse(ProtocolFaultCode.DUPLICATE, "concurrent publication conflicts")
        except Exception:
            self.bookkeeping._restore(checkpoint)
            raise
        finally:
            if staging is not None:
                staging.unlink(missing_ok=True)
        return accepted

    def retire(self, event_id: UUID, *, now_ms: int) -> tuple[UUID, ...]:
        group = self.bookkeeping.retirement_group(event_id, now_ms=now_ms)
        paths = []
        for member in group:
            event = self.bookkeeping._events[member]
            direction: Literal["inbox", "results"] = (
                "inbox" if event.kind in COMMAND_KINDS else "results"
            )
            path = self.event_path(member, direction)
            raw = self._bounded_read(path, self.bookkeeping._sizes[member])
            if (
                len(raw) != self.bookkeeping._sizes[member]
                or hashlib.sha256(raw).hexdigest() != self.bookkeeping._digests[member]
            ):
                _refuse(ProtocolFaultCode.DUPLICATE, "retirement found changed immutable evidence")
            paths.append(path)
        for path in paths:
            path.unlink()
        return self.bookkeeping.retire(event_id, now_ms=now_ms)
