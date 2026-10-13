"""Do native production boundaries exchange real bounded event files in order?"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest

from idhazh.contracts.host_events import (
    MEMORY_SOURCES,
    WINDOW_CELL_SOURCES,
    CaptureSource,
    HostEvent,
    HostProducerInvocation,
    HostSessionManifest,
    HostWindowCells,
    InstrumentSkippedBody,
    MonitorReadyBody,
    UnavailableDiagnostic,
    UnavailableReason,
    WindowAbortBody,
    WindowBegunBody,
    WindowResultBody,
    WorkerBody,
)
from idhazh.contracts.host_output import HostWriterIdentity
from idhazh.telemetry import host
from idhazh.telemetry.host_event_client import HostEventClient
from idhazh.telemetry.host_event_files import HostEventFiles
from idhazh.telemetry.host_evidence_inputs import NativeSettings
from idhazh.telemetry.host_output_verify import VerificationLimits

ROOT = Path(__file__).resolve().parents[2]


def _manifest(
    root: Path,
    *,
    item_id: str | tuple[str, ...] = "item-01",
    memory_profiling_enabled: bool = True,
) -> HostSessionManifest:
    source = json.loads((ROOT / "tests/fixtures/host-events/manifest.json").read_bytes())
    session_id = uuid4()
    source.update(
        {
            "session_id": str(session_id),
            "operator_emitter_id": "operator",
            "monitor_emitter_id": "monitor",
            "event_root": (
                f"backend/var/host-events/{source['run_id']}/{source['attempt']}/"
                f"{source['job']}/{source['shard']}/{session_id}"
            ),
            "workers": [
                {
                    "emitter_id": "worker",
                    "target": {"pid": os.getpid(), "start_ticks": 1},
                    "server": None,
                }
            ],
            "windows": [
                {"window_id": str(uuid4()), "item_id": value, "emitter_id": "worker"}
                for value in ((item_id,) if isinstance(item_id, str) else item_id)
            ],
            "cpu_target": {"pid": os.getpid(), "start_ticks": 1},
            "cpu_target_role": "python_worker",
        }
    )
    source["controls"]["memory_profiling_enabled"] = memory_profiling_enabled
    source["limits"].update(
        {
            "poll_ms": 5,
            "readiness_timeout_ms": 500,
            "ack_timeout_ms": 500,
            "drain_timeout_ms": 500,
            "max_files": 256,
            "max_session_events": 256,
            "max_windows": 64,
            "max_concurrent_windows": 64,
        }
    )
    manifest = HostSessionManifest.model_validate(source)
    (root / "manifest.json").write_text(manifest.to_json(), encoding="ascii", newline="\n")
    native = NativeSettings(
        version=manifest.version,
        controls=manifest.controls,
        limits=manifest.limits,
        capture_limits=manifest.capture_limits,
        verification_limits=VerificationLimits(
            max_files=64,
            max_file_bytes=1048576,
            max_total_bytes=16777216,
            max_rows=64,
            max_footer_bytes=262144,
            max_decode_bytes=1048576,
            max_thrift_items=4096,
            max_json_depth=32,
        ),
    )
    (root / "config.json").write_text(
        native.model_dump_json() + "\n", encoding="ascii", newline="\n"
    )
    return manifest


def test_client_refuses_a_different_resolved_memory_control(tmp_path: Path) -> None:
    _manifest(tmp_path)
    with pytest.raises(ValueError, match="effective memory control"):
        HostEventClient(
            tmp_path,
            Path("manifest.json"),
            Path("config.json"),
            memory_profiling_enabled=False,
        )


def _reply(
    manifest: HostSessionManifest,
    kind: str,
    sequence: int,
    reply_to: object,
    body: object,
) -> HostEvent:
    return HostEvent.model_validate(
        {
            **manifest.model_dump(
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
            "reply_to": str(reply_to),
            "emitter_id": manifest.monitor_emitter_id,
            "sequence": sequence,
            "emitted_at": "2026-10-10T12:00:00Z",
            "body": body,
        }
    )


class SessionPeer:
    """A real file-protocol peer used only for generated test sessions."""

    def __init__(
        self,
        root: Path,
        manifest: HostSessionManifest,
        *,
        incomplete_end: bool = False,
        window_cells: HostWindowCells | None = None,
    ) -> None:
        self.files = HostEventFiles(root, manifest)
        self.manifest = manifest
        self.incomplete_end = incomplete_end
        self.window_cells = window_cells
        self.seen: list[HostEvent] = []
        self._stop = threading.Event()
        self._sequence = 1
        self._now = 1
        ready = HostEvent.model_validate(
            {
                **manifest.model_dump(
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
                "kind": "monitor.ready",
                "event_id": str(uuid4()),
                "reply_to": None,
                "emitter_id": manifest.monitor_emitter_id,
                "sequence": self._sequence,
                "emitted_at": "2026-10-10T12:00:00Z",
                "body": MonitorReadyBody(
                    boot_id=manifest.boot_id, supported_version=manifest.version
                ).model_dump(mode="json"),
            }
        )
        self.files.publish(ready, now_ms=self._tick())
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _tick(self) -> int:
        self._now += 1
        return self._now

    def _serve(self) -> None:
        handled: set[object] = set()
        inbox = self.files.event_path(uuid4(), "inbox").parent
        while not self._stop.wait(0.002):
            if not inbox.exists():
                continue
            commands: list[HostEvent] = []
            for path in inbox.glob("*.json"):
                event = HostEvent.model_validate_json(path.read_bytes())
                if event.event_id not in handled:
                    commands.append(event)
            for command in sorted(commands, key=lambda event: event.sequence):
                self.files.read_event(command.event_id, "inbox", now_ms=self._tick())
                handled.add(command.event_id)
                self.seen.append(command)
                self._sequence += 1
                if command.kind == "worker.register":
                    assert isinstance(command.body, WorkerBody)
                    body: object = command.body
                    kind = "worker.registered"
                elif command.kind in {"host.probe", "host.target", "host.clock"}:
                    body = InstrumentSkippedBody(
                        command_kind=command.kind,
                        unavailable=(
                            UnavailableDiagnostic(
                                source=CaptureSource.CPUINFO,
                                reason=UnavailableReason.PERMISSION_DENIED,
                            ),
                        ),
                    )
                    kind = "instrument.skipped"
                elif command.kind == "window.begin":
                    body = WindowBegunBody(
                        **command.body.model_dump(), captured_at="2026-10-10T12:00:01Z"
                    )
                    kind = "window.begun"
                elif command.kind in {"window.end", "window.abort"}:
                    unavailable: tuple[UnavailableDiagnostic, ...] = ()
                    cells = self.window_cells or HostWindowCells(
                        cpu_busy_pct=0.0,
                        cpu_busy_max=0.0,
                        cpu_busy_min=0.0,
                        cpu_steal_pct=0.0,
                        load_1m=0.0,
                        **{
                            name: 0
                            for name in HostWindowCells.model_fields
                            if name
                            not in {
                                "cpu_busy_pct",
                                "cpu_busy_max",
                                "cpu_busy_min",
                                "cpu_steal_pct",
                                "load_1m",
                            }
                        },
                    )
                    if not self.manifest.controls.memory_profiling_enabled:
                        cells = HostWindowCells(
                            **{
                                name: getattr(cells, name)
                                for name in (
                                    "cpu_busy_pct",
                                    "cpu_busy_max",
                                    "cpu_busy_min",
                                    "cpu_steal_pct",
                                    "load_1m",
                                )
                            }
                        )
                        unavailable = tuple(
                            UnavailableDiagnostic(source=source, reason=UnavailableReason.DISABLED)
                            for source in sorted(
                                MEMORY_SOURCES & set(WINDOW_CELL_SOURCES.values()),
                                key=lambda source: source.value,
                            )
                        )
                    status: Literal["complete", "incomplete"] = "complete"
                    opened_at: str | None = "2026-10-10T12:00:01Z"
                    closed_at: str | None = "2026-10-10T12:00:02Z"
                    if command.kind == "window.abort" or self.incomplete_end:
                        status = "incomplete"
                        if command.kind == "window.abort":
                            opened_at = None
                            closed_at = None
                        cells = HostWindowCells()
                        unavailable = tuple(
                            UnavailableDiagnostic(
                                source=source,
                                reason=(
                                    UnavailableReason.DISABLED
                                    if not self.manifest.controls.memory_profiling_enabled
                                    and source in MEMORY_SOURCES
                                    else UnavailableReason.PID_EXITED
                                ),
                            )
                            for source in (
                                CaptureSource.CPU_STAT,
                                CaptureSource.LOAD,
                                CaptureSource.SERVER_MEMORY,
                                CaptureSource.MAJOR_FAULTS,
                                CaptureSource.WORKER_MEMORY,
                                CaptureSource.MACHINE_MEMORY,
                            )
                        )
                    body = WindowResultBody(
                        **command.body.model_dump(exclude={"reason"}),
                        status=status,
                        opened_at=opened_at,
                        closed_at=closed_at,
                        memory_profiling_enabled=self.manifest.controls.memory_profiling_enabled,
                        cells=cells,
                        unavailable=unavailable,
                    )
                    kind = "window.result"
                else:
                    continue
                reply = _reply(
                    self.manifest,
                    kind,
                    self._sequence,
                    command.event_id,
                    body,
                )
                self.files.publish(reply, now_ms=self._tick())

    def close(self) -> None:
        self._stop.set()
        self.thread.join()


def _client(
    root: Path, *, incomplete_end: bool = False, native: bool = False
) -> tuple[HostEventClient, SessionPeer]:
    manifest = _manifest(root)
    peer = SessionPeer(root, manifest, incomplete_end=incomplete_end)
    return HostEventClient(root, Path("manifest.json"), Path("config.json"), native=native), peer


def test_resource_only_session_brackets_native_window_results_once(tmp_path: Path) -> None:
    client, peer = _client(tmp_path)
    try:
        assert client.register_worker(server_pid=None)
        with client.native_watch(item_id="item-01") as watch:
            cells = watch.close()
        assert isinstance(cells, host.HostCells)
        assert [event.kind for event in peer.seen] == [
            "worker.register",
            "window.begin",
            "window.end",
        ]
        consumed = client.files.event_path(uuid4(), "results").parent.parent / "consumed"
        assert len(tuple(consumed.glob("*.json"))) == 7
    finally:
        peer.close()


@pytest.mark.parametrize(
    ("raised", "reason"),
    [(RuntimeError, "work_failed"), (KeyboardInterrupt, "cancelled")],
)
def test_failed_and_cancelled_work_abort_before_watch_exit(
    tmp_path: Path, raised: type[BaseException], reason: str
) -> None:
    client, peer = _client(tmp_path, native=True)
    ticked = threading.Event()
    threads: list[threading.Thread] = []

    def tick(_: float) -> None:
        threads.append(threading.current_thread())
        ticked.set()

    try:
        assert client.register_worker(server_pid=None)
        with pytest.raises(raised):
            with client.native_watch(item_id="item-01", interval_s=0.005, on_tick=tick):
                assert ticked.wait(1)
                raise raised()
        assert threads and all(not thread.is_alive() for thread in threads)
        abort = peer.seen[-1]
        assert abort.kind == "window.abort"
        assert isinstance(abort.body, WindowAbortBody)
        assert abort.body.reason == reason
    finally:
        peer.close()


def test_exited_target_result_keeps_unavailable_native_cells_null(tmp_path: Path) -> None:
    client, peer = _client(tmp_path, incomplete_end=True, native=True)
    try:
        assert client.register_worker(server_pid=None)
        with client.native_watch(item_id="item-01") as watch:
            cells = watch.close()
        assert isinstance(cells, host.HostCells)
        assert all(value is None for value in cells.cells().values())
        assert watch._result is not None
        assert {entry.reason for entry in watch._result.unavailable} == {
            UnavailableReason.PID_EXITED
        }
        assert peer.seen[-1].kind == "window.end"
    finally:
        peer.close()


@pytest.mark.parametrize("memory_profiling_enabled", [False, True])
def test_no_environment_binding_is_uninstrumented(memory_profiling_enabled: bool) -> None:
    assert (
        HostEventClient.from_environment(
            environ={}, memory_profiling_enabled=memory_profiling_enabled
        )
        is None
    )


@pytest.mark.parametrize(
    "environ",
    [
        {"IDHAZH_HOST_TELEMETRY_MODE": "legacy"},
        {"IDHAZH_HOST_TELEMETRY_MODE": "shadow"},
        {"IDHAZH_HOST_TELEMETRY_MODE": ""},
        {"IDHAZH_HOST_TELEMETRY_WORKSPACE": "named-workspace"},
        {"IDHAZH_HOST_TELEMETRY_MANIFEST": ""},
    ],
)
def test_explicit_legacy_or_partial_environment_binding_is_refused(
    environ: dict[str, str],
) -> None:
    with pytest.raises(ValueError, match=r"requires.*MODE='rust'"):
        HostEventClient.from_environment(environ=environ)


def test_rust_environment_marker_requires_all_independent_session_paths() -> None:
    with pytest.raises(ValueError, match="WORKSPACE, MANIFEST, CONFIG, INVOCATION"):
        HostEventClient.from_environment(environ={"IDHAZH_HOST_TELEMETRY_MODE": "rust"})


def test_environment_binding_keeps_independent_invocation_checks(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    invocation = HostProducerInvocation(
        date=manifest.date,
        identity=HostWriterIdentity(
            **manifest.model_dump(include={"run_id", "attempt", "job", "shard", "git_sha"}),
            producer="telemetry.silicon",
        ),
        command=(sys.executable, *sys.argv),
        stage="work",
        shards=1,
        host_enabled=True,
    )
    (tmp_path / "invocation.json").write_text(
        invocation.model_dump_json() + "\n", encoding="ascii", newline="\n"
    )
    environ = {
        "IDHAZH_HOST_TELEMETRY_MODE": "rust",
        "IDHAZH_HOST_TELEMETRY_WORKSPACE": str(tmp_path),
        "IDHAZH_HOST_TELEMETRY_MANIFEST": str(tmp_path / "manifest.json"),
        "IDHAZH_HOST_TELEMETRY_CONFIG": str(tmp_path / "config.json"),
        "IDHAZH_HOST_TELEMETRY_INVOCATION": str(tmp_path / "invocation.json"),
    }
    client = HostEventClient.from_environment(
        environ=environ, identity=invocation.identity, date=manifest.date, host_enabled=True
    )
    assert client is not None and client.native
    assert client.invocation == invocation
    with pytest.raises(ValueError, match="native host control"):
        HostEventClient.from_environment(environ=environ, host_enabled=False)
    wrong_identity = invocation.identity.model_copy(update={"attempt": manifest.attempt + 1})
    with pytest.raises(ValueError, match="executed worker invocation"):
        HostEventClient.from_environment(environ=environ, identity=wrong_identity)
    altered = invocation.model_copy(update={"command": (*invocation.command, "--wrong-command")})
    (tmp_path / "invocation.json").write_text(
        altered.model_dump_json() + "\n", encoding="ascii", newline="\n"
    )
    with pytest.raises(ValueError, match="producer command differs"):
        HostEventClient.from_environment(environ=environ)


def test_native_window_result_becomes_item_health_cells(tmp_path: Path) -> None:
    client, peer = _client(tmp_path, native=True)
    try:
        assert client.register_worker(server_pid=None)
        with client.native_watch(item_id="item-01") as watch:
            cells = watch.close()
        assert cells.cpu_busy_pct == 0.0
        assert cells.load_1m == 0.0
        assert [event.kind for event in peer.seen] == [
            "worker.register",
            "window.begin",
            "window.end",
        ]
    finally:
        peer.close()


def test_memory_off_native_window_keeps_cpu_load_and_heartbeat_without_memory(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path, memory_profiling_enabled=False)
    peer = SessionPeer(
        tmp_path,
        manifest,
        window_cells=HostWindowCells(
            cpu_busy_pct=25.0,
            cpu_busy_max=50.0,
            cpu_busy_min=10.0,
            cpu_steal_pct=2.0,
            load_1m=1.5,
        ),
    )
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
    ticked = threading.Event()
    threads: list[threading.Thread] = []

    def tick(_: float) -> None:
        threads.append(threading.current_thread())
        ticked.set()

    try:
        assert client.register_worker(server_pid=None)
        with client.native_watch(item_id="item-01", interval_s=0.005, on_tick=tick) as watch:
            assert ticked.wait(1)
            cells = watch.close()
        assert threads and all(not thread.is_alive() for thread in threads)
        expected = {
            "cpu_busy_pct": 25.0,
            "cpu_busy_max": 50.0,
            "cpu_busy_min": 10.0,
            "cpu_steal_pct": 2.0,
            "load_1m": 1.5,
        }
        assert {name: cells.cells()[name] for name in expected} == expected
        assert all(value is None for name, value in cells.cells().items() if name not in expected)
        assert watch._result is not None
        assert {entry.source for entry in watch._result.unavailable} == MEMORY_SOURCES & set(
            WINDOW_CELL_SOURCES.values()
        )
        assert {entry.reason for entry in watch._result.unavailable} == {UnavailableReason.DISABLED}
    finally:
        peer.close()


def test_native_unavailable_command_is_a_typed_refusal_without_python_fallback(
    tmp_path: Path,
) -> None:
    client, peer = _client(tmp_path, native=True)
    try:
        assert client.register_worker(server_pid=None)
        assert client.begin_job()
        assert client.native_started
        assert [event.kind for event in peer.seen] == ["worker.register", "host.probe"]
    finally:
        peer.close()
