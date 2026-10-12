"""Run one producer under the D7 Rust host-telemetry lifecycle.

The workflow wrapper deliberately owns the process boundary.  The child is
created before the monitor, but is held at a gate until the monitor has
published ``monitor.ready``.  This gives the runtime an immutable PID/start
identity while keeping the monitor-before-events ordering explicit.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

# Workflow steps invoke this file by path, so make the source-tree packages
# available even when the caller has not exported PYTHONPATH.
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from idhazh.contracts.base import ServerJob  # noqa: E402
from idhazh.contracts.host_events import (  # noqa: E402
    HostEvent,
    HostSessionManifest,
    ProcessTarget,
)
from idhazh.telemetry.host_evidence_inputs import (  # noqa: E402
    CONFIG_BYTES,
    live_controls,
    read_bytes,
    settings,
)
from utilities.host_telemetry_reference import identity  # noqa: E402
from utilities.host_telemetry_session import (  # noqa: E402
    invoke,
    retain_native,
    write_document,
    write_json,
)

GATE_CODE = (
    "import json,os,sys\n"
    "gate,env_file=sys.argv[1:3]; argv=sys.argv[3:]\n"
    "while not os.path.exists(gate):\n"
    "    import time; time.sleep(.05)\n"
    "with open(env_file, encoding='utf-8') as stream:\n"
    "    os.environ.update(json.load(stream))\n"
    "os.execvp(argv[0], argv)\n"
)
JOB_ALIASES = {"encoder-comparison": ServerJob.COLLECT.value}


class _CancelledError(Exception):
    pass


def _binary(explicit: str | None) -> Path:
    candidate = Path(
        explicit
        or os.environ.get("IDHAZH_HOST_TELEMETRY_BINARY", "")
        or ROOT / "backend/var/rust-host-telemetry/release/idhazh-host-telemetry"
    )
    if not candidate.is_file():
        raise SystemExit(f"D7 Rust monitor is absent: {candidate}")
    return candidate.resolve()


def _run_id(value: str) -> str:
    if value.isdecimal():
        return f"{datetime.now(UTC).date().isoformat()}-{value}"
    return value


def _boot_id(native: object) -> UUID:
    del native
    return UUID(Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip())


def _server_target(path: str | None, native: object) -> ProcessTarget | None:
    pid_value = (
        Path(path).read_text(encoding="ascii").strip()
        if path
        else os.environ.get("IDHAZH_MODEL_SERVER_PID")
    )
    if not pid_value:
        return None
    pid = int(pid_value)
    return identity(pid, native)


def _write_env(values: dict[str, str]) -> None:
    path = os.environ.get("GITHUB_ENV")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}<<D7_EOF\n{value}\nD7_EOF\n")


def _manifest(
    *,
    workspace: Path,
    native: object,
    controls: object,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
    git_sha: str,
    worker: ProcessTarget,
    server: ProcessTarget | None,
) -> HostSessionManifest:
    session_id = uuid4()
    event_root = (
        f"backend/var/host-events/{run_id}/{attempt}/{job.value}/{shard}/{session_id}"
    )
    manifest = HostSessionManifest.model_validate(
        {
            "version": "2026-10-10",
            "date": run_id[:10],
            "run_id": run_id,
            "attempt": attempt,
            "job": job.value,
            "shard": shard,
            "git_sha": git_sha,
            "session_id": str(session_id),
            "operator_emitter_id": "operator",
            "monitor_emitter_id": "monitor",
            "boot_id": str(_boot_id(native)),
            "event_root": event_root,
            "output_roots": [
                f"backend/var/d7-output/{run_id}/{attempt}/{job.value}/{shard}/{session_id}"
            ],
            "named_inputs": [],
            "workers": [
                {
                    "emitter_id": "worker",
                    "target": worker.model_dump(),
                    **({"server": server.model_dump()} if server else {}),
                }
            ],
            "windows": [],
            "cpu_target": (server or worker).model_dump(),
            "cpu_target_role": "model_server" if server else "python_worker",
            "controls": controls.model_dump(),
            "limits": native.limits.model_dump(),
            "capture_limits": native.capture_limits.model_dump(),
        }
    )
    write_document(workspace / "manifest.json", manifest)
    return manifest


def _effective_config(workspace: Path, native: object, controls: object) -> None:
    effective = native.model_dump(mode="json")
    effective["controls"] = controls.model_dump(mode="json")
    write_json(workspace / "native-config.json", effective)
    write_json(
        workspace / "effective-config.json",
        {
            "mode": "rust",
            "controls": controls.model_dump(mode="json"),
            "limits": native.limits.model_dump(mode="json"),
            "capture_limits": native.capture_limits.model_dump(mode="json"),
        },
    )


def _stop(workspace: Path, manifest: HostSessionManifest, reason: str) -> None:
    stop = HostEvent.model_validate(
        {
            **manifest.model_dump(
                include={"version", "date", "run_id", "attempt", "job", "shard", "session_id"},
                mode="json",
            ),
            "kind": "monitor.stop",
            "event_id": str(uuid4()),
            "reply_to": None,
            "emitter_id": "operator",
            "sequence": 1,
            "emitted_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "body": {"reason": reason},
        }
    )
    write_document(workspace / "stop.json", stop)
    invoke(workspace, "event-send", "--command", "stop.json")
    raw = invoke(workspace, "event-wait", "--command", "stop.json")
    stopped = HostEvent.model_validate_json(raw)
    if stopped.kind != "monitor.stopped" or stopped.session_id != manifest.session_id:
        raise RuntimeError("D7 monitor did not return a drained monitor.stopped receipt")
    retain_native(workspace / "drained.json", raw, settings()[0].limits.max_result_bytes)


def _cleanup(workspace: Path, binary: str | None) -> None:
    monitor_file = workspace / "monitor.json"
    manifest_file = workspace / "manifest.json"
    if not monitor_file.exists() or not manifest_file.exists():
        return
    target = ProcessTarget.model_validate_json(read_bytes(monitor_file, CONFIG_BYTES))
    try:
        invoke(
            workspace,
            "monitor-cleanup",
            "--pid",
            str(target.pid),
            "--start-ticks",
            str(target.start_ticks),
        )
    except ValueError as error:
        # A monitor which already acknowledged stop is allowed to have exited.
        if target.pid != os.getpid() and "No such process" not in str(error):
            raise
    del binary


def run(args: argparse.Namespace) -> int:
    if args.mode == "legacy":
        return subprocess.run(args.command, check=False).returncode
    if args.mode != "rust":
        raise SystemExit(f"unsupported IDHAZH_HOST_TELEMETRY_MODE={args.mode!r}")
    if os.name != "posix" or not Path("/proc").is_dir():
        raise SystemExit("D7 Rust host telemetry requires a Linux /proc runner")
    binary = _binary(args.binary)
    native, compare, _ = settings()
    memory = {"on": True, "off": False}.get(args.memory_profiling)
    controls = live_controls(native, compare, memory)
    run_id = _run_id(args.run_id)
    job_name = JOB_ALIASES.get(args.job, args.job)
    job = ServerJob(job_name)
    workspace = (
        ROOT
        / "backend/var/d7-host-telemetry"
        / run_id
        / str(args.attempt)
        / job.value
        / str(args.shard)
        / str(uuid4())
    )
    workspace.mkdir(parents=True, exist_ok=False)
    gate = workspace / "release"
    child: subprocess.Popen[bytes] | None = None
    monitor: subprocess.Popen[bytes] | None = None
    manifest: HostSessionManifest | None = None
    drained = False
    status = "failed"

    def cancelled(signum: int, frame: object) -> None:
        nonlocal status
        del signum, frame
        status = "cancelled"
        raise _CancelledError

    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGINT, cancelled)
    try:
        env_file = workspace / "worker-env.json"
        gate_command = [
            sys.executable,
            "-c",
            GATE_CODE,
            str(gate),
            str(env_file),
            *args.command,
        ]
        child = subprocess.Popen(
            gate_command,
            env={
                **os.environ,
                "IDHAZH_HOST_TELEMETRY_MODE": "rust",
                "IDHAZH_HOST_TELEMETRY_ENV_FILE": str(env_file),
            },
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        worker = identity(child.pid, native)
        server = _server_target(args.server_pid_file, native)
        manifest = _manifest(
            workspace=workspace,
            native=native,
            controls=controls,
            run_id=run_id,
            attempt=args.attempt,
            job=job,
            shard=args.shard,
            git_sha=args.git_sha,
            worker=worker,
            server=server,
        )
        _effective_config(workspace, native, controls)
        env = {
            "IDHAZH_HOST_TELEMETRY_MODE": "rust",
            "IDHAZH_HOST_TELEMETRY_WORKSPACE": str(workspace),
            "IDHAZH_HOST_TELEMETRY_MANIFEST": str(workspace / "manifest.json"),
            "IDHAZH_HOST_TELEMETRY_CONFIG": str(workspace / "native-config.json"),
            "IDHAZH_HOST_TELEMETRY_EFFECTIVE_CONFIG": str(workspace / "effective-config.json"),
            "IDHAZH_HOST_TELEMETRY_WORKER_PID": str(worker.pid),
            "IDHAZH_HOST_TELEMETRY_WORKER_START_TICKS": str(worker.start_ticks),
            "IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING": str(
                controls.memory_profiling_enabled
            ).lower(),
            "IDHAZH_HOST_TELEMETRY_RECEIPT": str(workspace / "receipt.json"),
            "IDHAZH_HOST_TELEMETRY_BINARY": str(binary),
        }
        if server:
            env.update(
                {
                    "IDHAZH_MODEL_SERVER_PID": str(server.pid),
                    "IDHAZH_MODEL_SERVER_START_TICKS": str(server.start_ticks),
                }
            )
        env_file.write_text(json.dumps(env), encoding="utf-8")
        _write_env(env)
        log = (workspace / "monitor.log").open("wb")
        monitor = subprocess.Popen(
            [
                str(binary),
                "monitor",
                "--workspace",
                str(workspace),
                "--manifest",
                "manifest.json",
                "--config",
                "native-config.json",
                "--artifact-root",
                "native-artifacts",
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        write_document(workspace / "monitor.json", identity(monitor.pid, native))
        ready = HostEvent.model_validate_json(invoke(workspace, "event-wait"))
        if ready.kind != "monitor.ready" or ready.session_id != manifest.session_id:
            raise RuntimeError("D7 Rust monitor did not become ready before worker release")
        retain_native(
            workspace / "ready.json",
            ready.model_dump_json().encode(),
            native.limits.max_result_bytes,
        )
        gate.touch()
        child_rc = child.wait(timeout=compare.worker_timeout_seconds)
        status = "completed" if child_rc == 0 else "failed"
        if child_rc:
            raise subprocess.CalledProcessError(child_rc, args.command)
        _stop(workspace, manifest, "completed")
        drained = True
        if not (workspace / "receipt.json").is_file():
            raise RuntimeError(
                "D7 producer did not write IDHAZH_HOST_TELEMETRY_RECEIPT before monitor drain"
            )
        receipt = json.loads((workspace / "receipt.json").read_text(encoding="utf-8"))
        if (
            receipt.get("verified") is not True
            or receipt.get("session_id") != str(manifest.session_id)
            or receipt.get("worker_pid") != worker.pid
            or receipt.get("worker_start_ticks") != worker.start_ticks
            or (
                server is not None
                and (
                    receipt.get("server_pid") != server.pid
                    or receipt.get("server_start_ticks") != server.start_ticks
                )
            )
        ):
            raise RuntimeError("D7 host receipt failed verification")
        _write_env({"IDHAZH_HOST_TELEMETRY_VERIFIED": "1"})
        return 0
    finally:
        if child and child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        if monitor and monitor.poll() is None and manifest is not None and not drained:
            try:
                _stop(workspace, manifest, status)
            except Exception:
                monitor.terminate()
                monitor.wait(timeout=10)
        if monitor:
            _cleanup(workspace, args.binary)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="verb", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--mode", default=os.environ.get("IDHAZH_HOST_TELEMETRY_MODE", "rust"))
    run_parser.add_argument("--job", required=True)
    run_parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "0"))
    run_parser.add_argument(
        "--attempt", type=int, default=int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    )
    run_parser.add_argument("--shard", type=int, default=0)
    run_parser.add_argument("--git-sha", default=os.environ.get("GITHUB_SHA", "0" * 40))
    run_parser.add_argument("--binary")
    run_parser.add_argument("--server-pid-file")
    run_parser.add_argument(
        "--memory-profiling",
        choices=("inherit", "on", "off"),
        default="inherit",
    )
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    clean_parser = sub.add_parser("cleanup")
    clean_parser.add_argument("--workspace", required=True)
    clean_parser.add_argument("--binary")
    args = parser.parse_args()
    if args.verb == "run":
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]
        if not args.command:
            raise SystemExit("D7 run requires a command after --")
        return run(args)
    _cleanup(Path(args.workspace), args.binary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
