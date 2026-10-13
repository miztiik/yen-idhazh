"""Do declared D7 invocations retain exact windows, controls and native byte evidence?"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pipeline._builders import plan as recorded_plan
from test_host_event_client import SessionPeer, _reply
from test_host_event_client import _manifest as fixture_manifest
from test_host_event_resource_parity import prepare as prepare_native_resources
from test_host_event_resource_parity import run as replay_native_resources
from test_rust_host_receipts import LIMITS, native, plan_input

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_events import (
    ExpectedWindow,
    HostEvent,
    HostProducerInvocation,
    HostSessionManifest,
    ProcessTarget,
    ProtocolFaultBody,
    ProtocolFaultCode,
    StoppedBody,
    WorkerBody,
)
from idhazh.contracts.host_output import HostWriteCompletion, HostWritePlan, HostWriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths
from idhazh.telemetry.host_event_client import HostEventClient
from idhazh.telemetry.host_event_files import HostProtocolError
from idhazh.telemetry.host_evidence_inputs import read_bytes, retain_native, settings
from utilities import d7_host_telemetry as lifecycle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_runner_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)


def invocation_args(command: list[str], **changes: object) -> argparse.Namespace:
    return argparse.Namespace(
        **{
            "command": command,
            "run_id": None,
            "git_sha": None,
            "attempt": 2,
            "shard": 0,
        }
        | changes
    )


@pytest.mark.parametrize(
    ("script", "tail"),
    [
        ("digest_publish.py", ["run", "plan"]),
        ("digest_publish.py", ["run", "work"]),
        ("digest_publish.py", ["run", "assemble"]),
        ("digest_publish.py", ["run", "fingerprint"]),
        ("digest_publish.py", ["run", "job-clock"]),
        ("record_publish.py", ["run", "measure", "fingerprint"]),
        ("measure_llm.py", ["bench"]),
        ("runtime_sweep.py", ["sweep"]),
        ("compare_summary_encoders.py", ["score"]),
        ("compare_summary_encoders.py", ["collect"]),
        ("gardener_publish.py", []),
        ("council_publish.py", []),
    ],
)
def test_launcher_recognizes_only_named_table_w_commands(script: str, tail: list[str]) -> None:
    command = [sys.executable, str(ROOT / "backend" / "utilities" / script), *tail]
    assert lifecycle._native_command_supported(command)
    producer = lifecycle._producer(command)
    assert producer is not None
    stage = producer[0]
    job = {
        "plan": ServerJob.PLAN,
        "work": ServerJob.WORK,
        "assemble": ServerJob.ASSEMBLE,
        "bench": ServerJob.RUNTIME,
        "sweep": ServerJob.RUNTIME,
        "score": ServerJob.COLLECT,
        "collect": ServerJob.COLLECT,
        "run-tasks": ServerJob.RUN_TASKS,
        "save_council_results": ServerJob.SAVE_COUNCIL_RESULTS,
    }.get(stage, ServerJob.WORK)
    if script == "record_publish.py":
        job = ServerJob.RUNTIME
    bound = lifecycle._invocation(
        invocation_args(command, run_id="2026-08-21-37", git_sha="a" * 40),
        job,
        config.load(),
    )
    assert bound.identity.job is job and bound.command == tuple(command)
    assert bound.shards == (1 if stage == "work" else None)
    command[1] = str(ROOT / "backend" / "var" / script)
    assert not lifecycle._native_command_supported(command)


def test_council_without_publishable_work_skips_the_native_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = [
        sys.executable,
        str(ROOT / "backend" / "utilities" / "council_publish.py"),
        "--date",
        "2026-08-21",
        "--run-id",
        "2026-08-21-37",
        "--commit",
        "a" * 40,
    ]
    monkeypatch.setattr(lifecycle, "_council_has_publishable_work", lambda flags: False)
    observed: dict[str, object] = {}

    def run_child(child: list[str], *, env: dict[str, str], check: bool) -> SimpleNamespace:
        observed["command"] = child
        observed["environment"] = env
        assert check is False
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", run_child)
    monkeypatch.setattr(
        lifecycle, "_write_env", lambda values: observed.update({"handoff": values})
    )
    assert (
        lifecycle.run(
            argparse.Namespace(
                mode="rust",
                command=command,
                job=ServerJob.SAVE_COUNCIL_RESULTS.value,
            )
        )
        == 0
    )
    environment = observed["environment"]
    assert isinstance(environment, dict)
    assert not any(key.startswith("IDHAZH_HOST_TELEMETRY_") for key in environment)
    assert observed["handoff"] == {"IDHAZH_HOST_TELEMETRY_SKIPPED": "council-no-active-publishers"}


def test_historical_execution_is_bound_to_its_named_day_not_launcher_today() -> None:
    command = [
        sys.executable,
        str(ROOT / "backend" / "utilities" / "digest_publish.py"),
        "run",
        "work",
        "--date",
        "2026-08-21",
        "--execution",
        "37",
        "--commit",
        "a" * 40,
        "--shards",
        "2",
        "--shard",
        "1",
    ]
    invocation = lifecycle._invocation(
        invocation_args(command, run_id="37", shard=1), ServerJob.WORK, config.load()
    )
    assert invocation.date == "2026-08-21"
    assert invocation.identity.run_id == "2026-08-21-37"
    assert invocation.identity.attempt == 2
    assert invocation.identity.shard == 1
    assert invocation.identity.git_sha == "a" * 40
    assert invocation.execution == 37 and invocation.shards == 2


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"run_id": "2026-08-21-38"}, "execution"),
        ({"git_sha": "b" * 40}, "execution SHA"),
        ({"shard": 1}, "shard"),
        ({"attempt": 3}, "attempt"),
    ],
)
def test_launcher_refuses_independent_identity_conflicts(
    changes: dict[str, object], message: str
) -> None:
    command = [
        sys.executable,
        str(ROOT / "backend" / "utilities" / "digest_publish.py"),
        "run",
        "work",
        "--date",
        "2026-08-21",
        "--execution",
        "37",
        "--commit",
        "a" * 40,
        "--shard",
        "0",
        "--attempt",
        "2",
    ]
    with pytest.raises(ValueError, match=message):
        lifecycle._invocation(invocation_args(command, **changes), ServerJob.WORK, config.load())


def test_memory_off_does_not_turn_off_the_independent_copy_probe() -> None:
    native_settings, _, _ = settings()
    source = config.load()
    source.app.observability.host_fingerprint_bandwidth_jobs = (ServerJob.WORK,)
    source.app.observability.host_fingerprint_bandwidth_floor_mib = 512
    controls = lifecycle._controls(native_settings, source, False, ServerJob.WORK)
    assert not controls.memory_profiling_enabled
    assert controls.memcpy_enabled and controls.memcpy_probe_mib == 512
    assert controls.resource_interval_seconds == source.app.logging.waiting_heartbeat_seconds


def test_council_configuration_controls_native_memory_and_ledger_prefix(tmp_path: Path) -> None:
    from workflows._harness import _copy_config

    config_root = tmp_path / "council-config"
    _copy_config(config_root)
    app_path = config_root / "idhazh.json"
    app = json.loads(app_path.read_bytes())
    app["observability"]["memory_profiling_enabled"] = False
    app["run"]["trial_state_dirname"] = "council-controls"
    app_path.write_text(json.dumps(app), encoding="ascii", newline="\n")
    source = lifecycle._source_settings(
        "save_council_results", ["--config-root", str(config_root)]
    )
    native_settings, _, _ = settings()
    controls = lifecycle._controls(native_settings, source, None, ServerJob.SAVE_COUNCIL_RESULTS)
    assert controls.memory_profiling_enabled is False
    assert lifecycle._host_ledger_prefix(source) == "council-controls/host-fingerprint"


def test_worker_termination_reaps_only_its_owned_process() -> None:
    child = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(60)"])
    other = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(60)"])
    try:
        lifecycle._terminate_worker(child)
        assert child.poll() is not None
        assert other.poll() is None
    finally:
        for process in (child, other):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM refusal is a Linux process boundary")
def test_worker_termination_timeout_reaps_before_reporting_failure(tmp_path: Path) -> None:
    ready = tmp_path / "worker-ready"
    code = (
        "import pathlib,signal,sys,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "pathlib.Path(sys.argv[1]).touch(); time.sleep(60)"
    )
    child = subprocess.Popen([sys.executable, "-B", "-c", code, str(ready)])
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "generated worker did not install its signal handler"
        with pytest.raises(subprocess.TimeoutExpired):
            lifecycle._terminate_worker(child, timeout=0.1)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_producer_cannot_replace_the_actual_runner_execution_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    command = [
        sys.executable,
        str(ROOT / "backend" / "utilities" / "digest_publish.py"),
        "run",
        "plan",
        "--date",
        "2026-08-21",
        "--execution",
        "37",
        "--commit",
        "a" * 40,
    ]
    with pytest.raises(ValueError, match="runner invocation"):
        lifecycle._invocation(invocation_args(command), ServerJob.PLAN, config.load())


def test_producer_cannot_replace_the_actual_runner_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "3")
    command = [
        sys.executable,
        str(ROOT / "backend" / "utilities" / "digest_publish.py"),
        "run",
        "work",
        "--date",
        "2026-08-21",
        "--execution",
        "37",
        "--commit",
        "a" * 40,
    ]
    with pytest.raises(ValueError, match="executed runner"):
        lifecycle._invocation(invocation_args(command), ServerJob.WORK, config.load())


class DrainPeer(SessionPeer):
    """Reuse the file fixture's transport for the disabled-host register/stop lifecycle."""

    def _serve(self) -> None:
        handled = set()
        inbox = self.files.event_path(uuid4(), "inbox").parent
        while not self._stop.wait(0.002):
            if not inbox.exists():
                continue
            commands = [
                HostEvent.model_validate_json(path.read_bytes()) for path in inbox.glob("*.json")
            ]
            for command in sorted(commands, key=lambda value: value.sequence):
                if command.event_id in handled:
                    continue
                self.files.read_event(command.event_id, "inbox", now_ms=self._tick())
                handled.add(command.event_id)
                self.seen.append(command)
                self._sequence += 1
                body: WorkerBody | StoppedBody
                if command.kind == "worker.register":
                    assert isinstance(command.body, WorkerBody)
                    body = command.body
                    kind = "worker.registered"
                else:
                    assert command.kind == "monitor.stop"
                    body, kind = StoppedBody(drained=True, aborted_window_ids=()), "monitor.stopped"
                self.files.publish(
                    _reply(self.manifest, kind, self._sequence, command.event_id, body),
                    now_ms=self._tick(),
                )


class RetiringPeer(SessionPeer):
    """Use real consumption and advance the isolated peer clock to retry deadlines."""

    _retirement_floor_ms = 0

    def _tick(self) -> int:
        now = max(int(time.monotonic() * 1000), self._retirement_floor_ms)
        book = self.files.bookkeeping
        consumed = self.files.event_path(uuid4(), "results").parent.parent / "consumed"
        if consumed.exists():
            for path in consumed.glob("*.json"):
                event_id = UUID(path.stem)
                if event_id in book._events:
                    book.mark_consumed(event_id)
                    now = max(
                        now,
                        book._received_at[event_id] + self.manifest.limits.retry_window_ms,
                    )
        self._retirement_floor_ms = now
        for event_id, event in tuple(book._events.items()):
            if event.reply_to is not None or event_id not in book._events:
                continue
            try:
                self.files.retire(event_id, now_ms=now)
            except HostProtocolError as error:
                if error.code is not ProtocolFaultCode.STATE:
                    raise
        return now


@pytest.mark.parametrize("memory", [True, False])
def test_disabled_host_registers_drains_and_retains_its_explicit_control(
    tmp_path: Path, memory: bool
) -> None:
    manifest = fixture_manifest(tmp_path, item_id=())
    source = manifest.model_dump(mode="json")
    source["controls"]["memory_profiling_enabled"] = memory
    manifest = HostSessionManifest.model_validate(source)
    (tmp_path / "manifest.json").write_text(manifest.to_json(), encoding="ascii", newline="\n")
    native_settings = json.loads((tmp_path / "config.json").read_bytes())
    native_settings["controls"] = source["controls"]
    (tmp_path / "config.json").write_text(
        json.dumps(native_settings) + "\n", encoding="ascii", newline="\n"
    )
    identity = HostWriterIdentity(
        **manifest.model_dump(include={"run_id", "attempt", "job", "shard", "git_sha"}),
        producer="telemetry.silicon",
    )
    invocation = HostProducerInvocation(
        date=manifest.date,
        identity=identity,
        command=("disabled-host-fixture",),
        stage="work",
        shards=1,
        host_enabled=False,
    )
    (tmp_path / "invocation.json").write_text(
        invocation.model_dump_json() + "\n", encoding="ascii", newline="\n"
    )
    peer = DrainPeer(tmp_path, manifest)
    try:
        client = HostEventClient(
            tmp_path,
            Path("manifest.json"),
            Path("config.json"),
            memory_profiling_enabled=memory,
            native=True,
        )
        assert client.register_worker(server_pid=None)
        assert client.begin_job() and client.begin_job()
        assert client.end_job() and client.end_job()
        receipt = client.publication_receipt()
        assert receipt.identity == identity and not receipt.writes
    finally:
        peer.close()
    assert [event.kind for event in peer.seen] == ["worker.register", "monitor.stop"]
    assert client.files.bookkeeping._phase == "stopped"
    assert (tmp_path / "drained.json").is_file() and (tmp_path / "receipt.json").is_file()
    lifecycle._stop(
        tmp_path,
        manifest,
        "completed",
        root=tmp_path,
        binary=ROOT
        / "backend"
        / "var"
        / "rust-host-telemetry"
        / "debug"
        / "idhazh-host-telemetry.exe",
    )
    stop = HostEvent.model_validate_json((tmp_path / "stop.json").read_bytes())
    changed = stop.model_copy(update={"event_id": uuid4()})
    (tmp_path / "stop.json").write_text(changed.to_json(), encoding="ascii", newline="\n")
    with pytest.raises(ValueError, match="named stop command"):
        lifecycle._stop(
            tmp_path,
            manifest,
            "completed",
            root=tmp_path,
            binary=ROOT
            / "backend"
            / "var"
            / "rust-host-telemetry"
            / "debug"
            / "idhazh-host-telemetry.exe",
        )


def test_readiness_fault_cannot_be_hidden_by_a_ready_event_in_the_same_batch(
    tmp_path: Path,
) -> None:
    manifest = fixture_manifest(tmp_path, item_id=())
    peer = SessionPeer(tmp_path, manifest)
    try:
        fault = _reply(
            manifest,
            "protocol.fault",
            2,
            uuid4(),
            ProtocolFaultBody(code=ProtocolFaultCode.BOUNDS, related_event_id=None),
        ).model_copy(update={"reply_to": None})
        peer.files.publish(fault, now_ms=peer._tick())
        client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
        with pytest.raises(HostProtocolError) as refused:
            client.register_worker(server_pid=None)
    finally:
        peer.close()
    assert refused.value.code is ProtocolFaultCode.BOUNDS
    assert not peer.seen


def test_bound_lifecycle_consumes_actual_native_periodic_events_while_producer_is_idle(
    tmp_path: Path,
) -> None:
    root = tmp_path / "native-resources"
    values, _ = prepare_native_resources(root, memory=True, periodic=True)
    manifest = HostSessionManifest.model_validate(values)
    (root / "manifest.json").write_text(manifest.to_json(), encoding="ascii", newline="\n")
    identity = HostWriterIdentity(
        **manifest.model_dump(include={"run_id", "attempt", "job", "shard", "git_sha"}),
        producer="telemetry.silicon",
    )
    invocation = HostProducerInvocation(
        date=manifest.date,
        identity=identity,
        command=("native-resource-fixture",),
        stage="work",
        shards=1,
        host_enabled=False,
    )
    (root / "invocation.json").write_text(
        invocation.model_dump_json() + "\n", encoding="ascii", newline="\n"
    )
    native_events = replay_native_resources(
        root, "resource-replay", "--snapshot", "resources", "--artifact-root", "artifacts"
    )
    assert native_events.returncode == 0, native_events.stderr.decode()
    raw_events: list[tuple[HostEvent, bytes]] = []
    for count, path in enumerate((root / manifest.event_root / "results").iterdir(), start=1):
        assert count <= manifest.limits.max_files
        raw = read_bytes(path, manifest.limits.max_result_bytes)
        event = HostEvent.model_validate_json(raw)
        if event.kind in {"job.sample", "process.rollcall"}:
            raw_events.append((event, raw))
    assert raw_events
    raw_events.sort(key=lambda value: value[0].sequence)
    peer_root = tmp_path / "consumer"
    peer_root.mkdir()
    (peer_root / "manifest.json").write_text(manifest.to_json(), encoding="ascii", newline="\n")
    (peer_root / "config.json").write_text(
        json.dumps(json.loads((root / "config.json").read_bytes())) + "\n",
        encoding="ascii",
        newline="\n",
    )
    (peer_root / "invocation.json").write_text(
        invocation.model_dump_json() + "\n", encoding="ascii", newline="\n"
    )
    peer = DrainPeer(peer_root, manifest)
    client = HostEventClient(peer_root, Path("manifest.json"), Path("config.json"), native=True)
    try:
        server = manifest.workers[0].server
        assert server is not None
        assert client.register_worker(server_pid=server.pid)
        assert client.begin_job()
        for event, raw in raw_events:
            peer.files.bookkeeping.accept(event, now_ms=peer._tick(), raw=raw)
            retain_native(
                peer.files.event_path(event.event_id, "results"),
                raw,
                manifest.limits.max_result_bytes,
            )
            peer._sequence = event.sequence
        consumed = peer.files.event_path(uuid4(), "results").parent.parent / "consumed"
        deadline = time.monotonic() + manifest.limits.ack_timeout_ms / 1000
        while not all((consumed / f"{event.event_id}.json").exists() for event, _ in raw_events):
            client._raise_resource_error()
            assert time.monotonic() < deadline
            time.sleep(manifest.limits.poll_ms / 1000)
        for event, raw in raw_events:
            assert (consumed / f"{event.event_id}.json").read_bytes() == raw
        assert client.end_job()
        resource_consumer = client._resource_consumer
        assert resource_consumer is not None
        assert not resource_consumer.is_alive()
        assert not client.publication_receipt().writes
    finally:
        client._stop_resource_consumer()
        peer.close()


def test_native_heartbeat_passes_elapsed_time_without_sampling_python_host(
    tmp_path: Path,
) -> None:
    manifest = fixture_manifest(tmp_path)
    peer = SessionPeer(tmp_path, manifest)
    heartbeat = threading.Event()
    ticks: list[float] = []

    def on_tick(elapsed: float) -> None:
        ticks.append(elapsed)
        heartbeat.set()

    try:
        client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
        assert client.register_worker(server_pid=None)
        watch = client.native_watch(item_id="item-01", interval_s=0.005, on_tick=on_tick)
        with watch:
            assert heartbeat.wait(manifest.limits.ack_timeout_ms / 1000)
            cells = watch.close()
        assert ticks and all(value >= 0 for value in ticks)
        assert cells.cpu_busy_pct is not None
        heartbeat_thread = watch._heartbeat
        assert heartbeat_thread is not None
        assert not heartbeat_thread.is_alive()
    finally:
        peer.close()


def test_resource_consumer_preserves_window_acknowledgments_for_the_waiting_producer(
    tmp_path: Path,
) -> None:
    manifest = fixture_manifest(tmp_path)
    invocation = HostProducerInvocation(
        date=manifest.date,
        identity=HostWriterIdentity(
            **manifest.model_dump(include={"run_id", "attempt", "job", "shard", "git_sha"}),
            producer="telemetry.silicon",
        ),
        command=("queued-window-fixture",),
        stage="work",
        shards=1,
        host_enabled=False,
    )
    (tmp_path / "invocation.json").write_text(
        invocation.model_dump_json() + "\n", encoding="ascii", newline="\n"
    )
    peer = SessionPeer(tmp_path, manifest)
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
    try:
        assert client.register_worker(server_pid=None) and client.begin_job()
        watch = client.native_watch(item_id="item-01")
        worker_id = client._worker_id
        assert worker_id is not None
        command = client._event("window.begin", worker_id, watch._body)
        client._publish(command)
        deadline = time.monotonic() + manifest.limits.ack_timeout_ms / 1000
        while not client._pending_results:
            client._raise_resource_error()
            assert time.monotonic() < deadline
            time.sleep(manifest.limits.poll_ms / 1000)
        begun = client._wait(command, {"window.begun"}, timeout_ms=manifest.limits.ack_timeout_ms)
        assert begun is not None and begun.reply_to == command.event_id
        ended = client._window_command("window.end", watch._body)
        assert ended is not None and ended.kind == "window.result"
        assert not (tmp_path / "receipt.json").exists()
    finally:
        client._stop_resource_consumer()
        peer.close()


def test_native_client_retires_consumed_local_groups_without_weakening_native_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = fixture_manifest(tmp_path, item_id=tuple(f"item-{index:02d}" for index in range(5)))
    native_settings, _, _ = settings()
    values = manifest.model_dump(mode="json") | {
        "limits": native_settings.limits.model_dump(mode="json")
    }
    manifest = HostSessionManifest.model_validate(values)
    (tmp_path / "manifest.json").write_text(manifest.to_json(), encoding="ascii", newline="\n")
    effective = json.loads((tmp_path / "config.json").read_bytes())
    effective["limits"] = values["limits"]
    (tmp_path / "config.json").write_text(
        json.dumps(effective) + "\n", encoding="ascii", newline="\n"
    )
    peer = RetiringPeer(tmp_path, manifest)
    try:
        client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
        assert client.register_worker(server_pid=None)
        for window in manifest.windows:
            with client.native_watch(item_id=window.item_id):
                pass
        book = client.files.bookkeeping
        digests = book._digests.copy()
        retire_at = book._now_ms + client.manifest.limits.retry_window_ms
        with monkeypatch.context() as clock:
            clock.setattr(
                "idhazh.telemetry.host_event_client._monotonic_ms",
                lambda: retire_at,
            )
            assert client._new_results() == ()
        assert book._digests == digests
        assert len(book._digests) > len(book._events)
        assert book.total_events == 3 + 4 * len(manifest.windows)
        assert client.manifest.limits == native_settings.limits
    finally:
        peer.close()


def test_manifest_keeps_declared_windows_and_uses_managed_state_root(tmp_path: Path) -> None:
    native_settings, _, _ = settings()
    windows = tuple(
        ExpectedWindow(window_id=uuid4(), item_id=f"item-{index:02d}", emitter_id="worker")
        for index in range(native_settings.limits.max_windows)
    )
    boot_id = uuid4()

    def manifest_for(selected_windows: tuple[ExpectedWindow, ...]) -> HostSessionManifest:
        return lifecycle._manifest(
            workspace=tmp_path,
            native=native_settings,
            controls=native_settings.controls,
            run_id="2026-08-21-37",
            attempt=2,
            job=ServerJob.WORK,
            shard=0,
            git_sha="a" * 40,
            worker=ProcessTarget(pid=os.getpid(), start_ticks=1),
            server=None,
            windows=selected_windows,
            boot_id=boot_id,
        )

    manifest = manifest_for(windows)
    assert manifest.windows == windows
    assert manifest.output_roots == ("state",)
    (tmp_path / "manifest.json").unlink()
    with pytest.raises(ValueError, match="max_windows"):
        manifest_for(
            (
                *windows,
                ExpectedWindow(window_id=uuid4(), item_id="item-extra-01", emitter_id="worker"),
            )
        )


def test_selected_plan_names_the_exact_run_and_round_robin_shard_under_its_overlay(
    tmp_path: Path,
) -> None:
    plan = recorded_plan()
    source = config.load()
    source.app.run.trial_state_dirname = "d7-plan-fixture"
    source.app.run.trial_case_dirname = None
    registry = ledger.overlay_registry(("d7-plan-fixture",))
    writer = WriterIdentity(
        run_id=plan.run_id,
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
        producer="stages.plan",
        git_sha="a" * 40,
    )
    ledger.persist(
        tmp_path / "state",
        [plan],
        ledger=LedgerName.RUN_PLAN,
        covers=plan.date,
        identity=writer,
        registry=registry,
    )
    foreign = plan.model_copy(update={"run_id": f"{plan.date}-99999"})
    ledger.persist(
        tmp_path / "state",
        [foreign],
        ledger=LedgerName.RUN_PLAN,
        covers=plan.date,
        identity=writer.model_copy(update={"run_id": foreign.run_id}),
        registry=registry,
    )
    session = tmp_path / "session"
    session.mkdir()
    command = [
        sys.executable,
        str(ROOT / "backend" / "utilities" / "digest_publish.py"),
        "run",
        "work",
        "--date",
        plan.date,
        "--shards",
        "2",
        "--shard",
        "1",
        "--commit",
        "a" * 40,
    ]
    invocation = lifecycle._invocation(
        invocation_args(command, run_id=plan.run_id, shard=1), ServerJob.WORK, source
    )
    selected, windows = lifecycle._selected_plan(invocation, source, session, repo=tmp_path)
    assert [window.item_id for window in windows] == [
        item.item_id for index, item in enumerate(plan.items) if index % 2 == 1
    ]
    assert len({window.window_id for window in windows}) == len(windows)
    assert selected.identity.run_id == plan.run_id
    assert selected.plan_path == "session/selected-plan.json"
    retained = (tmp_path / selected.plan_path).read_bytes()
    assert retained == plan.to_json().encode("utf-8")
    assert selected.plan_sha256 == hashlib.sha256(retained).hexdigest()


def test_host_ledger_prefix_follows_the_selected_trial_registry() -> None:
    source = config.load()
    assert lifecycle._host_ledger_prefix(source) == "/".join(
        paths.entry(LedgerName.HOST_FINGERPRINT).prefix
    )
    source.app.run.trial_state_dirname = "pipeline-tests"
    source.app.run.trial_case_dirname = "bench-01"
    assert lifecycle._host_ledger_prefix(source) == ("pipeline-tests/bench-01/host-fingerprint")


def test_legacy_launcher_preserves_exit_status_and_cannot_inherit_native_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = tmp_path / "mode.txt"
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "rust")
    code = (
        "import os,pathlib,sys; "
        "pathlib.Path(sys.argv[1]).write_text(os.environ['IDHAZH_HOST_TELEMETRY_MODE']); "
        "sys.exit(7)"
    )
    assert (
        lifecycle.run(
            argparse.Namespace(mode="legacy", command=[sys.executable, "-c", code, str(result)])
        )
        == 7
    )
    assert result.read_text() == "legacy"


def test_receipt_is_built_from_actual_native_files_without_python_target_writes(
    tmp_path: Path,
) -> None:
    plan, input_path, _ = plan_input({"format": "json", "compression": "none"})
    output_root = ROOT / Path(plan.target_root).parent
    fixture = fixture_manifest(tmp_path)
    identity = HostWriterIdentity.model_validate(
        plan.publication_identity.model_dump() | {"producer": "telemetry.silicon"}
    )
    plan = HostWritePlan.model_validate(
        plan.model_dump(mode="json")
        | {
            "publication_identity": identity.model_dump(mode="json"),
            "files": [plan.files[0].model_dump(mode="json")],
        }
    )
    values = (
        fixture.model_dump(mode="json")
        | identity.model_dump(mode="json", exclude={"producer"})
        | {"date": plan.files[0].rows[0].date, "output_roots": [plan.target_root]}
    )
    values["event_root"] = (
        f"backend/var/host-events/{identity.run_id}/{identity.attempt}/"
        f"{identity.job.value}/{identity.shard}/{fixture.session_id}"
    )
    manifest = HostSessionManifest.model_validate(values)
    event_root = ROOT / manifest.event_root
    evidence = f"{manifest.event_root}/writes"
    try:
        (ROOT / input_path).write_text(plan.to_json(), encoding="utf-8", newline="\n")
        output = native("write", input_path, evidence)
        assert output.returncode == 0, output.stderr.decode()
        completion = HostWriteCompletion.model_validate(json.loads(output.stdout)["completion"])
        before = {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in completion.receipt.writes
        }
        receipt = lifecycle._verified_receipt(ROOT, manifest, LIMITS)
        assert receipt.writes == before == completion.receipt.writes
        assert {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in receipt.writes
        } == before
        interrupted_plan = plan.model_copy(update={"event_id": uuid4()})
        (ROOT / input_path).write_text(interrupted_plan.to_json(), encoding="utf-8", newline="\n")
        interrupted = native("write", input_path, evidence, "plan")
        assert interrupted.returncode == 70, interrupted.stderr.decode()
        with pytest.raises(RuntimeError, match="matching typed plan"):
            lifecycle._verified_receipt(ROOT, manifest, LIMITS)
        prefix = lifecycle._verified_receipt(ROOT, manifest, LIMITS, allow_incomplete_commands=True)
        assert prefix.writes == before
    finally:
        shutil.rmtree(output_root)
        if event_root.exists():
            shutil.rmtree(event_root)
