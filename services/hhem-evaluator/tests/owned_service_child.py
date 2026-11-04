"""Drive the real caller's pipe ownership without opening an HTTP listener."""

import os
import subprocess
import sys
import threading
from pathlib import Path

from summary_eval_pipeline.channels import open_owned_channels
from summary_eval_pipeline.contracts import WORKFLOW_VERSION, Hardware
from summary_eval_pipeline.control import (
    ApiReady,
    HostReady,
    ServiceStartFailed,
    ServiceStopped,
    StartupPacket,
)
from summary_eval_pipeline.serve_api import emit_control, watch_parent_lifetime

from hhem_evaluator.contracts.evaluation_event import EventDetails
from hhem_evaluator.emit_events import EventEmitter, EventWriter
from hhem_evaluator.load_settings import load_settings
from hhem_evaluator.resolve_ids import create_execution_id


def private_output_case(packet: StartupPacket, mode: str) -> None:
    root = Path(__file__).resolve().parents[3]
    with open_owned_channels() as channels:
        settings = load_settings(root / "config" / "hhem-evaluator" / "settings.json")
        emitter = EventEmitter(EventWriter(settings.logging, channels.events), packet.context)
        cause = emitter.emit("service", "started", EventDetails(status="disabled"))
        emit_control(
            ApiReady(
                version=WORKFLOW_VERSION,
                kind="ready",
                service="api",
                startup_id=packet.startup_id,
                pid=os.getpid(),
                service_instance_id=create_execution_id(),
            ),
            channels.control,
        )
        sys.stdin.buffer.read(1)
        unconfirmed = mode == "unconfirmed_stop"
        worker = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys; print('PrivateInheritedOutputCanary',flush=True); "
                "print('PrivateInheritedErrorCanary',file=sys.stderr,flush=True)"
                + ("; sys.stdin.buffer.read(1)" if unconfirmed else ""),
            ],
            stdin=subprocess.PIPE if unconfirmed else subprocess.DEVNULL,
        )
        try:
            if not unconfirmed:
                worker.wait(timeout=5)
            confirmed = worker.poll() is not None
            emitter.emit("service", "completed", EventDetails(status="stopping"), cause=cause)
            emit_control(
                ServiceStopped(
                    version=WORKFLOW_VERSION,
                    kind="stopped",
                    service="api",
                    startup_id=packet.startup_id,
                    pid=os.getpid(),
                    clean=mode != "unclean_stop",
                    worker_exit_confirmed=confirmed,
                ),
                channels.control,
            )
        finally:
            if worker.stdin is not None:
                worker.stdin.close()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)


def main() -> None:
    packet = StartupPacket.model_validate_json(sys.stdin.buffer.readline(16384))
    mode = sys.argv[1]
    if mode == "coded_startup_failure":
        sys.stdout.write(
            ServiceStartFailed(
                version=WORKFLOW_VERSION,
                kind="failed",
                service="host",
                startup_id=packet.startup_id,
                pid=os.getpid(),
                error_code="MACHINE_API_STARTUP_INVALID",
            ).model_dump_json()
            + "\n"
        )
        sys.stdout.write(
            ServiceStopped(
                version=WORKFLOW_VERSION,
                kind="stopped",
                service="host",
                startup_id=packet.startup_id,
                pid=os.getpid(),
                clean=False,
                worker_exit_confirmed=None,
                error_code="MACHINE_API_STARTUP_INVALID",
                cleanup_error_code="MACHINE_EVIDENCE_INVALID",
            ).model_dump_json()
            + "\n"
        )
        sys.stdout.flush()
        raise SystemExit(1)
    if mode in ("raw_inherited_output", "unclean_stop", "unconfirmed_stop"):
        private_output_case(packet, mode)
        return
    if mode == "early_exit":
        return
    ready: ApiReady | HostReady
    if mode == "invalid_event":
        ready = ApiReady(
            version=WORKFLOW_VERSION,
            kind="ready",
            service="api",
            startup_id=packet.startup_id,
            pid=os.getpid(),
            service_instance_id=create_execution_id(),
        )
        sys.stderr.write("PrivateRawChildCanary\n")
        sys.stderr.flush()
    else:
        ready = HostReady(
            version=WORKFLOW_VERSION,
            kind="ready",
            service="host",
            startup_id=create_execution_id() if mode == "mismatch" else packet.startup_id,
            pid=os.getpid(),
            hardware=Hardware(
                status="disabled",
                cpu_model=None,
                cpu_logical_processors=None,
                cpu_physical_cores=None,
                machine_memory_total_mib=None,
                unavailable={},
                reason="configured_off",
            ),
            profile_started=False,
            lifecycle_timeout_ms=1000,
        )
    sys.stdout.write(ready.model_dump_json() + "\n")
    sys.stdout.flush()
    if mode in ("parent_loss", "parent_loss_blocked"):
        stop, finished = threading.Event(), threading.Event()
        threading.Thread(
            target=watch_parent_lifetime,
            args=(sys.stdin.buffer, stop.set, finished, 500),
            daemon=True,
        ).start()
        stop.wait()
        if mode == "parent_loss_blocked":
            threading.Event().wait()
        finished.set()
    else:
        sys.stdin.buffer.read(1)
    if mode == "blocked_close":
        threading.Event().wait()
    stopped = ServiceStopped(
        version=WORKFLOW_VERSION,
        kind="stopped",
        service=ready.service,
        startup_id=packet.startup_id,
        pid=os.getpid(),
        clean=True,
        worker_exit_confirmed=None,
    )
    sys.stdout.write(stopped.model_dump_json() + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
