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
from summary_evaluator.hhem.contracts.evaluation_event import EventDetails
from summary_evaluator.hhem.emit_events import EventEmitter
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.shared.create_execution_id import create_execution_id


def private_output_case(packet: StartupPacket, mode: str) -> None:
    root = Path(__file__).resolve().parents[4]
    with open_owned_channels() as channels:
        settings = load_settings(
            root / "config" / "summary-evals" / "hhem-evaluator" / "settings.json"
        )
        emitter = EventEmitter(
            EventWriter(settings.logging, channels.events).write, packet.context, settings.logging
        )
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
        blocked = (mode == "unconfirmed_stop", mode == "unconfirmed_unieval_stop")
        workers = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import sys; print('PrivateInheritedOutputCanary',flush=True); "
                    "print('PrivateInheritedErrorCanary',file=sys.stderr,flush=True)"
                    + ("; sys.stdin.buffer.read(1)" if held else ""),
                ],
                stdin=subprocess.PIPE if held else subprocess.DEVNULL,
            )
            for held in blocked
        ]
        try:
            for worker, held in zip(workers, blocked, strict=True):
                if not held:
                    worker.wait(timeout=5)
            confirmed = [worker.poll() is not None for worker in workers]
            emitter.emit("service", "completed", EventDetails(status="stopping"), cause=cause)
            emit_control(
                ServiceStopped(
                    version=WORKFLOW_VERSION,
                    kind="stopped",
                    service="api",
                    startup_id=packet.startup_id,
                    pid=os.getpid(),
                    clean=mode != "unclean_stop",
                    worker_exit_confirmed=confirmed[0],
                    unieval_worker_exit_confirmed=confirmed[1],
                ),
                channels.control,
            )
        finally:
            for worker in workers:
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
    if mode in (
        "raw_inherited_output",
        "unclean_stop",
        "unconfirmed_stop",
        "unconfirmed_unieval_stop",
    ):
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
