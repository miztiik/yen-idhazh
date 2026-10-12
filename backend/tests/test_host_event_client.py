"""Do inactive production boundaries exchange real bounded event files in order?"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from uuid import uuid4

import pytest

from idhazh.contracts.host_events import (
    CaptureSource,
    HostEvent,
    HostSessionManifest,
    HostWindowCells,
    MonitorReadyBody,
    UnavailableDiagnostic,
    UnavailableReason,
    WindowBegunBody,
    WindowResultBody,
    WorkerBody,
)
from idhazh.telemetry import host
from idhazh.telemetry.host_event_client import HostEventClient
from idhazh.telemetry.host_event_files import HostEventFiles

ROOT = Path(__file__).resolve().parents[2]


def _manifest(root: Path, *, item_id: str | tuple[str, ...] = "item-01") -> HostSessionManifest:
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
    native = json.loads((ROOT / "config/host-telemetry-experiment.json").read_bytes())
    for name in ("controls", "limits", "capture_limits"):
        native[name] = manifest.model_dump(mode="json")[name]
    (root / "config.json").write_text(
        json.dumps(native, sort_keys=True) + "\n", encoding="ascii", newline="\n"
    )
    return manifest


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
    ) -> None:
        self.files = HostEventFiles(root, manifest)
        self.manifest = manifest
        self.incomplete_end = incomplete_end
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
                elif command.kind == "window.begin":
                    body = WindowBegunBody(
                        **command.body.model_dump(), captured_at="2026-10-10T12:00:01Z"
                    )
                    kind = "window.begun"
                elif command.kind in {"window.end", "window.abort"}:
                    unavailable: tuple[UnavailableDiagnostic, ...] = ()
                    cells = HostWindowCells(
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
                    status = "complete"
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
                                reason=UnavailableReason.PID_EXITED,
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
                        memory_profiling_enabled=True,
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
        self.thread.join(timeout=1)


def _client(root: Path, *, incomplete_end: bool = False) -> tuple[HostEventClient, SessionPeer]:
    manifest = _manifest(root)
    peer = SessionPeer(root, manifest, incomplete_end=incomplete_end)
    return HostEventClient(root, Path("manifest.json"), Path("config.json")), peer


def test_window_events_bracket_the_authoritative_watch_once(tmp_path: Path) -> None:
    client, peer = _client(tmp_path)
    try:
        assert client.register_worker(server_pid=None)
        with client.shadow_watch(
            host.Watch(interval_s=0, server_pid=None), item_id="item-01"
        ) as watch:
            first = watch.close()
            second = watch.close()
        assert first.cells() == second.cells()
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
    client, peer = _client(tmp_path)
    try:
        assert client.register_worker(server_pid=None)
        with pytest.raises(raised):
            with client.shadow_watch(host.Watch(interval_s=0, server_pid=None), item_id="item-01"):
                raise raised()
        abort = peer.seen[-1]
        assert abort.kind == "window.abort"
        assert abort.body.reason == reason
    finally:
        peer.close()


def test_exited_target_result_does_not_replace_python_cells(tmp_path: Path) -> None:
    client, peer = _client(tmp_path, incomplete_end=True)
    try:
        assert client.register_worker(server_pid=None)
        with client.shadow_watch(
            host.Watch(interval_s=0, server_pid=None), item_id="item-01"
        ) as watch:
            cells = watch.close()
        assert isinstance(cells, host.HostCells)
        assert peer.seen[-1].kind == "window.end"
    finally:
        peer.close()
