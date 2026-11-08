"""Drive the real owner's bounded private transport and observed process exits without HTTP."""

import os
import subprocess
import sys
import threading
from pathlib import Path

from local_api_host.propagate_trace_context import create_child_operation
from pydantic import RootModel
from summary_eval_pipeline.channels import open_owned_channels
from summary_eval_pipeline.contracts import WORKFLOW_VERSION, Hardware
from summary_eval_pipeline.control import (
    HostReady,
    ServiceStartFailed,
    ServiceStopped,
    StartupPacket,
)
from summary_eval_pipeline.scorer_control import (
    SCORER_CONTROL_VERSION,
    ScorerReady,
    ScorerStartupPacket,
    ScorerStopped,
)
from summary_eval_pipeline.serve_api import emit_control, watch_parent_lifetime
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData, ServerEvent
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings
from summary_evaluator.shared.contracts.worker_exit import WorkerExit
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.read_process_identity import read_owned_process_identity


def api_transport_case(packet: ScorerStartupPacket, mode: str) -> None:
    root = Path(__file__).resolve().parents[3]
    with open_owned_channels() as channels:
        settings = load_hhem_settings(
            root / "config" / "summary-evals" / "hhem-evaluator" / "settings.json"
        )
        launch = (
            create_child_operation(packet.operation_metadata)
            if mode == "crossed_launch" else packet.operation_metadata
        )
        operation = create_child_operation(launch)
        controls = load_pipeline_settings(root)
        events = EventWriter(
            settings.logging, channels.events, scorer=packet.scorer,
            service_operation=operation, propagate_trace_context=True,
        )
        process = read_owned_process_identity(
            os.getpid(), settings.worker.max_proc_identity_bytes
        )
        events.diagnostic(ApiDiagnosticData(component="api", action="started", level="INFO"))
        emit_control(
            ScorerReady(
                version=SCORER_CONTROL_VERSION, kind="ready", service="api",
                scorer=packet.scorer, startup_id=packet.startup_id, process=process,
                launch_operation_metadata=launch, operation_metadata=operation,
                service_instance_id=create_execution_id(), log_file=None, log_available=False,
            ),
            channels.control,
            controls.control_max_bytes,
        )
        if mode == "invalid_event":
            channels.events.write("PrivateRawChildCanary\n")
            channels.events.flush()
        if mode == "replay_event":
            line = sys.stdin.buffer.readline(settings.logging.max_event_bytes + 1)
            saved = ServerEvent.model_validate_json(line)
            channels.events.write(saved.encode_json_line(settings.logging.max_event_bytes).decode())
            channels.events.flush()
        sys.stdin.buffer.read(1)
        worker: subprocess.Popen[bytes] | None = None
        try:
            if mode != "invalid_event":
                held = mode in ("unconfirmed_stop", "unconfirmed_unieval_stop")
                worker = subprocess.Popen(
                    [
                        sys.executable, "-c",
                        "import sys; print('PrivateInheritedOutputCanary',flush=True); "
                        "print('PrivateInheritedErrorCanary',file=sys.stderr,flush=True)"
                        + ("; sys.stdin.buffer.read(1)" if held else ""),
                    ],
                    stdin=subprocess.PIPE if held else subprocess.DEVNULL,
                )
                if not held:
                    worker.wait(timeout=5)
            observed = WorkerExit(
                pid=worker.pid if worker is not None else None,
                exit_code=worker.poll() if worker is not None else None,
                confirmed=worker.poll() is not None if worker is not None else None,
            )
            events.diagnostic(ApiDiagnosticData(component="api", action="stopped", level="INFO"))
            emit_control(
                ScorerStopped(
                    version=SCORER_CONTROL_VERSION, kind="stopped", service="api",
                    scorer=packet.scorer, startup_id=packet.startup_id, process=process,
                    launch_operation_metadata=launch,
                    operation_metadata=(
                        create_child_operation(launch) if mode == "crossed_service" else operation
                    ),
                    clean=mode != "unclean_stop", worker_exit=observed,
                    log_file=None, log_available=False,
                ),
                channels.control,
                controls.control_max_bytes,
            )
        finally:
            if worker is not None:
                if worker.stdin is not None:
                    worker.stdin.close()
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=5)
            events.close()


def main() -> None:
    packet = RootModel[ScorerStartupPacket | StartupPacket].model_validate_json(
        sys.stdin.buffer.readline(16384)
    ).root
    mode = sys.argv[1]
    if mode == "early_exit":
        return
    if isinstance(packet, ScorerStartupPacket):
        api_transport_case(packet, mode)
        return
    if mode == "coded_startup_failure":
        sys.stdout.write(
            ServiceStartFailed(
                version=WORKFLOW_VERSION, kind="failed", service="host",
                startup_id=packet.startup_id, pid=os.getpid(),
                error_code="MACHINE_API_STARTUP_INVALID",
            ).model_dump_json() + "\n"
        )
        sys.stdout.write(
            ServiceStopped(
                version=WORKFLOW_VERSION, kind="stopped", service="host",
                startup_id=packet.startup_id, pid=os.getpid(), clean=False,
                worker_exit_confirmed=None, error_code="MACHINE_API_STARTUP_INVALID",
                cleanup_error_code="MACHINE_EVIDENCE_INVALID",
            ).model_dump_json() + "\n"
        )
        sys.stdout.flush()
        raise SystemExit(1)
    ready = HostReady(
        version=WORKFLOW_VERSION, kind="ready", service="host",
        startup_id=create_execution_id() if mode == "mismatch" else packet.startup_id,
        pid=os.getpid(),
        hardware=Hardware(
            status="disabled", cpu_model=None, cpu_logical_processors=None,
            cpu_physical_cores=None, machine_memory_total_mib=None,
            unavailable={}, reason="configured_off",
        ),
        profile_started=False, lifecycle_timeout_ms=1000,
    )
    sys.stdout.write(ready.model_dump_json() + "\n")
    sys.stdout.flush()
    if mode in ("parent_loss", "parent_loss_blocked"):
        stop, finished = threading.Event(), threading.Event()
        threading.Thread(
            target=watch_parent_lifetime,
            args=(sys.stdin.buffer, stop.set, finished, 500), daemon=True,
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
        version=WORKFLOW_VERSION, kind="stopped", service="host",
        startup_id=packet.startup_id, pid=os.getpid(), clean=True, worker_exit_confirmed=None,
    )
    sys.stdout.write(stopped.model_dump_json() + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
