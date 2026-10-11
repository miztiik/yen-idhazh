"""How are the owned worker and native event session started, drained and stopped?"""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Compression, Format
from idhazh.contracts.host_events import HostEvent, HostSessionManifest, ProcessTarget
from idhazh.contracts.host_evidence import (
    EVIDENCE_VERSION,
    CleanupEvidence,
    EvidenceRoots,
    EvidenceSession,
    MonitorMeasurement,
    PairedEvidence,
    WorkloadRequest,
    WorkloadResult,
)
from idhazh.contracts.host_output import HostWriterIdentity
from idhazh.telemetry.host_evidence_comparison import field_classes
from idhazh.telemetry.host_evidence_inputs import (
    ROOT,
    freeze_bounds,
    isolated_workspace,
    live_controls,
    read_bytes,
    read_model,
    resolve,
    retain_native,
    settings,
    validate_roots,
    write_document,
    write_json,
)
from utilities.host_telemetry_reference import identity, process_cost
from utilities.host_telemetry_workload import now, wait_for


def binary() -> Path:
    path = ROOT / "backend/var/rust-host-telemetry/release/idhazh-host-telemetry"
    if not path.is_file():
        raise ValueError("build the same pinned release crate before live evidence")
    return path


def invoke(workspace: Path, verb: str, *args: str, manifest: str = "manifest.json") -> bytes:
    native, compare, _ = settings()
    output = workspace / f"command-{uuid4()}.log"
    with output.open("wb") as stream:
        child = subprocess.Popen(
            [
                str(binary()),
                verb,
                "--workspace",
                str(workspace),
                "--manifest",
                manifest,
                "--config",
                "native-config.json",
                *args,
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + compare.worker_timeout_seconds
        try:
            while child.poll() is None:
                if time.monotonic() >= deadline:
                    raise ValueError(f"native {verb} exceeded its configured deadline")
                if output.stat().st_size > compare.max_command_output_bytes:
                    raise ValueError(f"native {verb} output exceeded its configured cap")
                time.sleep(native.limits.poll_ms / 1000)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=native.limits.drain_timeout_ms / 1000)
    raw = read_bytes(output, max(native.limits.max_result_bytes, compare.max_command_output_bytes))
    if child.returncode:
        raise ValueError(f"native {verb} failed: {raw.decode('ascii', 'replace')}")
    return raw


def request(workspace: Path, sequence: int, mode: str) -> WorkloadResult:
    native, compare, _ = settings()
    value = WorkloadRequest.model_validate({"sequence": sequence, "mode": mode})
    write_document(workspace / f"requests/{sequence}.json", value)
    path = workspace / f"responses/{sequence}.json"
    target = read_model(
        workspace / "worker-launched.json", ProcessTarget, native.limits.max_result_bytes
    )

    def check_worker() -> None:
        if stopped(target):
            logs = [
                read_bytes(workspace / name, compare.max_command_output_bytes).decode(
                    "utf-8", "replace"
                )
                for name in ("worker.log", f"sampler-{sequence}.log")
                if (workspace / name).exists()
            ]
            raise ValueError(f"owned workload worker stopped before {path.name}: " + "".join(logs))

    wait_for(
        path,
        compare.worker_timeout_seconds,
        native.limits.poll_ms,
        check_producer=check_worker,
    )
    return read_model(path, WorkloadResult, native.limits.max_result_bytes)


def event(
    manifest: HostSessionManifest, kind: str, sequence: int, body: object, emitter: str
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
            "reply_to": None,
            "emitter_id": emitter,
            "sequence": sequence,
            "emitted_at": now(),
            "body": body,
        }
    )


def prepare(
    workspace: Path, *, git_sha: str, run_number: str, attempt: int, compile_file: Path, gates: Path
) -> None:
    if platform.system() != "Linux":
        raise ValueError("live preparation requires Linux")
    native, compare, digest = settings()
    controls = live_controls(native, compare)
    if not run_number.isdecimal():
        raise ValueError("run number must be an operator-derived decimal identity")
    binary()
    workspace = isolated_workspace(workspace, create=True)
    roots = EvidenceRoots(
        reference="reference",
        native="native/state",
        native_artifacts="native-artifacts",
        generated_state="generated/state",
        corpus="generated-corpus",
        frontend="generated-frontend",
    )
    day = now()[:10]
    run_id = f"{day}-{run_number}"
    HostWriterIdentity(
        run_id=run_id,
        attempt=attempt,
        job=ServerJob.WORK,
        shard=0,
        producer="telemetry.silicon",
        git_sha=git_sha,
    )
    boot_id = (
        read_bytes(
            Path("/proc/sys/kernel/random/boot_id"), native.capture_limits.max_proc_text_bytes
        )
        .decode()
        .strip()
    )
    with (workspace / "worker.log").open("wb") as log:
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "utilities.host_telemetry_workload",
                "worker",
                "--workspace",
                str(workspace),
                "--day",
                day,
                "--run-id",
                run_id,
                "--git-sha",
                git_sha,
                "--attempt",
                str(attempt),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    target = identity(child.pid, native)
    write_document(workspace / "worker-launched.json", target)
    session_id = uuid4()
    event_root = f"backend/var/host-events/{run_id}/{attempt}/work/0/{session_id}"
    validate_roots(workspace, roots, event_root)
    effective = native.model_dump(mode="json")
    effective["controls"] = controls.model_dump(mode="json")
    manifest = HostSessionManifest.model_validate(
        {
            "version": "2026-10-10",
            "date": day,
            "run_id": run_id,
            "attempt": attempt,
            "job": "work",
            "shard": 0,
            "git_sha": git_sha,
            "session_id": str(session_id),
            "operator_emitter_id": "operator",
            "monitor_emitter_id": "monitor",
            "boot_id": boot_id,
            "event_root": event_root,
            "output_roots": [roots.native],
            "named_inputs": [],
            "workers": [{"emitter_id": "worker", "target": target.model_dump(), "server": None}],
            "windows": [
                {"window_id": str(uuid4()), "item_id": f"bounded-{i:02d}", "emitter_id": "worker"}
                for i in range(compare.paired_runs * 2)
            ],
            "cpu_target": target.model_dump(),
            "cpu_target_role": "python_worker",
            **{key: effective[key] for key in ("controls", "limits", "capture_limits")},
        }
    )
    host_id = uuid4()
    host_root = f"backend/var/host-events/{run_id}/{attempt}/work/0/{host_id}"
    host_manifest = HostSessionManifest.model_validate(
        {
            **manifest.model_dump(mode="json"),
            "session_id": str(host_id),
            "event_root": host_root,
            "operator_emitter_id": "host-operator",
            "monitor_emitter_id": "host-results",
            "windows": [],
            "named_inputs": [
                {
                    "name": "metadata",
                    "source": "proc.cpuinfo",
                    "relative_path": "inputs/metadata.json",
                },
                {"name": "start", "source": "clock.log", "relative_path": "inputs/start.txt"},
            ],
        }
    )
    validate_roots(workspace, roots, event_root, host_root)
    write_document(workspace / "manifest.json", manifest)
    write_document(workspace / "host-manifest.json", host_manifest)
    write_json(workspace / "native-config.json", effective)
    write_json(workspace / "inputs/metadata.json", {})
    (workspace / "inputs/start.txt").write_bytes((now() + "\n").encode("ascii"))
    wait_for(
        workspace / "worker.json",
        compare.worker_timeout_seconds,
        native.limits.poll_ms,
        child=child,
    )
    ready = read_model(workspace / "worker.json", ProcessTarget, native.limits.max_result_bytes)
    if ready != target:
        raise ValueError("worker readiness does not identify the launched child")
    calibration = tuple(
        request(workspace, i + 1, "reference") for i in range(compare.calibration_runs)
    )
    bounds = freeze_bounds(calibration, compare)
    plain = request(workspace, compare.calibration_runs + 1, "native_only")
    session = EvidenceSession(
        version=EVIDENCE_VERSION,
        created_at=now(),
        manifest=manifest,
        host_manifest=host_manifest,
        roots=roots,
        calibration=calibration,
        bounds=bounds,
        plain=plain,
        config_sha256=digest,
        field_classes=field_classes(),
    )
    write_document(workspace / "session.json", session)
    for source, name in ((compile_file, "compile.json"), (gates, "gates.xml")):
        if not source.resolve().is_relative_to(ROOT / "backend/var"):
            raise ValueError("build/gate evidence must be an explicitly named generated file")
        maximum = (
            compare.max_junit_bytes if name.endswith(".xml") else native.limits.max_result_bytes
        )
        (workspace / name).write_bytes(read_bytes(source, maximum))
    probe = event(
        host_manifest,
        "host.probe",
        1,
        {
            "controls": manifest.controls.model_dump(),
            "input_names": ["metadata"],
            "target": target.model_dump(),
            "previous_result_id": None,
        },
        host_manifest.operator_emitter_id,
    )
    probe_id = uuid4()
    write_document(workspace / "probe.json", probe)
    clock = event(
        host_manifest,
        "host.clock",
        2,
        {
            "controls": manifest.controls.model_dump(),
            "input_names": ["start"],
            "target": target.model_dump(),
            "previous_result_id": str(probe_id),
        },
        host_manifest.operator_emitter_id,
    )
    write_document(workspace / "clock.json", clock)
    clock_id = uuid4()
    lines = {
        "D5_WORKSPACE": workspace.relative_to(ROOT).as_posix(),
        "D5_EVENT_ROOT": event_root,
        "D5_HOST_EVENT_ROOT": host_root,
        "D5_PROBE_ID": str(probe_id),
        "D5_CLOCK_ID": str(clock_id),
        "D5_PROBE_RESULT": f"{host_root}/results/{probe_id}.json",
        "D5_PROBE_PLAN": f"{host_root}/writes/{probe.event_id}.plan.json",
        "D5_CLOCK_RESULT": f"{host_root}/results/{clock_id}.json",
        "D5_FORMAT": compare.source.ledger.format.value,
        "D5_COMPRESSION": (
            Compression.NONE.value
            if compare.source.ledger.format is Format.JSON
            else compare.source.ledger.compression_raw.value
        ),
        "D5_CACHE_MULTIPLE": str(
            compare.source.observability.host_fingerprint_bandwidth_cache_multiple
        ),
    }
    (workspace / "workflow.env").write_bytes(
        "".join(f"{key}={value}\n" for key, value in lines.items()).encode("ascii")
    )


def start(workspace: Path) -> None:
    native, _, _ = settings()
    session = read_model(
        workspace / "session.json", EvidenceSession, native.limits.max_result_bytes
    )
    started = time.perf_counter()
    with (workspace / "monitor.log").open("wb") as log:
        child = subprocess.Popen(
            [
                str(binary()),
                "monitor",
                "--workspace",
                str(workspace),
                "--manifest",
                "manifest.json",
                "--config",
                "native-config.json",
                "--artifact-root",
                session.roots.native_artifacts,
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    target = identity(child.pid, native)
    write_document(workspace / "monitor.json", target)
    ready_raw = invoke(workspace, "event-wait")
    ready = HostEvent.model_validate_json(ready_raw)
    if ready.kind != "monitor.ready" or ready.session_id != session.manifest.session_id:
        raise ValueError("native monitor did not become ready")
    retain_native(workspace / "ready.json", ready_raw, native.limits.max_result_bytes)
    cpu, rss = process_cost(target, native)
    write_document(
        workspace / "startup.json",
        MonitorMeasurement(
            version=EVIDENCE_VERSION,
            target=target,
            cpu_seconds=cpu,
            rss_bytes=rss,
            startup_seconds=time.perf_counter() - started,
        ),
    )


def workload(workspace: Path) -> None:
    native, compare, _ = settings()
    session = read_model(
        workspace / "session.json", EvidenceSession, native.limits.max_result_bytes
    )
    manifest = session.manifest
    registration = event(
        manifest,
        "worker.register",
        1,
        {
            "target": manifest.cpu_target.model_dump() if manifest.cpu_target else None,
            "server": None,
            "memory_profiling_enabled": manifest.controls.memory_profiling_enabled,
        },
        "worker",
    )
    acks: list[float] = []
    paired: list[WorkloadResult] = []
    commands = [registration]
    for index, window in enumerate(manifest.windows):
        body = {
            "window_id": str(window.window_id),
            "item_id": window.item_id,
            "target": manifest.cpu_target.model_dump() if manifest.cpu_target else None,
            "server": None,
        }
        commands.extend(
            [
                event(manifest, "window.begin", 2 + index * 2, body, "worker"),
                event(manifest, "window.end", 3 + index * 2, body, "worker"),
            ]
        )
    for index, command in enumerate(commands):
        name = f"commands/{command.event_id}.json"
        write_document(resolve(workspace, name), command)
        started = time.perf_counter()
        invoke(workspace, "event-send", "--command", name)
        raw = invoke(workspace, "event-wait", "--command", name)
        result = HostEvent.model_validate_json(raw)
        acks.append(time.perf_counter() - started)
        expected = {
            "worker.register": "worker.registered",
            "window.begin": "window.begun",
            "window.end": "window.result",
        }[command.kind]
        if result.kind != expected:
            raise ValueError("required healthy acknowledgement is absent")
        retain_native(workspace / f"observed/{index}.json", raw, native.limits.max_result_bytes)
        if command.kind == "window.begin":
            window_index = (index - 1) // 2
            paired.append(
                request(
                    workspace,
                    compare.calibration_runs + 2 + window_index,
                    "reference" if window_index % 2 == 0 else "native_only",
                )
            )
    write_document(
        workspace / "paired.json",
        PairedEvidence(
            version=EVIDENCE_VERSION,
            rows=tuple(paired),
            ack_seconds=tuple(acks),
        ),
    )


def drain(workspace: Path) -> None:
    native, _, _ = settings()
    session = read_model(
        workspace / "session.json", EvidenceSession, native.limits.max_result_bytes
    )
    command = event(session.manifest, "monitor.stop", 1, {"reason": "completed"}, "operator")
    write_document(workspace / "stop.json", command)
    target = read_model(workspace / "monitor.json", ProcessTarget, native.limits.max_result_bytes)
    cpu, rss = process_cost(target, native)
    write_document(
        workspace / "monitor-cost.json",
        MonitorMeasurement(
            version=EVIDENCE_VERSION,
            target=target,
            cpu_seconds=cpu,
            rss_bytes=rss,
            startup_seconds=None,
        ),
    )
    invoke(workspace, "event-send", "--command", "stop.json")
    raw = invoke(workspace, "event-wait", "--command", "stop.json")
    stopped = HostEvent.model_validate_json(raw)
    if stopped.kind != "monitor.stopped":
        raise ValueError("native monitor did not drain")
    retain_native(workspace / "drained.json", raw, native.limits.max_result_bytes)


def cleanup(workspace: Path) -> None:
    native, config, _ = settings()
    workspace = isolated_workspace(workspace)
    names = (
        "monitor.json",
        *(
            f"sampler-{index}.json"
            for index in range(1, config.calibration_runs + config.paired_runs * 2 + 2)
        ),
        "worker-launched.json",
    )
    faults: list[str] = []
    targets: list[ProcessTarget] = []
    for name in names:
        path = workspace / name
        if path.exists():
            try:
                target = read_model(path, ProcessTarget, native.limits.max_result_bytes)
                targets.append(target)
                if (workspace / "manifest.json").exists():
                    invoke(
                        workspace,
                        "monitor-cleanup",
                        "--pid",
                        str(target.pid),
                        "--start-ticks",
                        str(target.start_ticks),
                    )
                else:
                    stop_partial(target)
                wait_stopped(target)
            except (OSError, ValueError) as error:
                faults.append(str(error))
    if faults:
        raise ValueError("owned cleanup failures: " + "; ".join(faults))
    write_document(
        workspace / "cleanup.json",
        CleanupEvidence(
            version=EVIDENCE_VERSION,
            targets=tuple(targets),
        ),
    )


def stopped(target: ProcessTarget) -> bool:
    native, _, _ = settings()
    try:
        raw = read_bytes(
            Path(f"/proc/{target.pid}/stat"), native.capture_limits.max_proc_text_bytes
        )
    except FileNotFoundError:
        return True
    if identity(target.pid, native) != target:
        raise ValueError("cleanup refuses a reused task PID")
    return raw.decode().rpartition(") ")[2].split()[0] in {"Z", "X", "x"}


def wait_stopped(target: ProcessTarget) -> None:
    native, _, _ = settings()
    deadline = time.monotonic() + native.limits.drain_timeout_ms / 1000
    while not stopped(target):
        if time.monotonic() >= deadline:
            raise ValueError("owned process did not terminate within its declared drain bound")
        time.sleep(native.limits.poll_ms / 1000)


def stop_partial(target: ProcessTarget) -> None:
    if sys.platform == "linux":
        if stopped(target):
            return
        descriptor = os.pidfd_open(target.pid)
        try:
            if not stopped(target):
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        finally:
            os.close(descriptor)
        return
    raise ValueError("partial cleanup requires live Linux process identity")
