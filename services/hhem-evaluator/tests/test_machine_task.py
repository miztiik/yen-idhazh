"""Exercise the actual Python-to-Bun machine helper and its owned loopback Hono application."""

import contextlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from summary_eval_pipeline.contracts import WORKFLOW_VERSION, RunIdentity
from summary_eval_pipeline.control import HostReady, StartupPacket
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.host_reader import MachineUsage, measurement_complete
from summary_eval_pipeline.model_selection import select_model, stage_configuration
from summary_eval_pipeline.services import OwnedService
from summary_eval_pipeline.settings import PipelineSettings, load_pipeline_settings

from hhem_evaluator.contracts.service_settings import ServiceSettings, StartupContext
from hhem_evaluator.load_settings import load_settings
from hhem_evaluator.resolve_ids import create_execution_id

from .contract_examples import REPOSITORY
from .test_host_profile_reader_parity import required_bun
from .test_pipeline_lifetime import CHILD_STARTUP_MS


def available_loopback_port() -> int:
    result = subprocess.run(
        [
            required_bun(),
            "-e",
            'import {createServer} from "node:net"; const server=createServer(); '
            'await new Promise((resolve,reject)=>{server.once("error",reject);'
            'server.listen(0,"127.0.0.1",resolve)}); const address=server.address(); '
            'if(address===null||typeof address==="string") throw new Error("Missing port"); '
            "console.log(address.port); "
            "await new Promise((resolve,reject)=>server.close("
            "error=>error?reject(error):resolve()));",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, "The loopback-only port reservation failed."
    port = int(result.stdout.strip())
    assert 0 < port < 65536
    return port


def stage_machine_run(
    root: Path,
) -> tuple[StartupPacket, ServiceSettings, PipelineSettings]:
    pipeline = load_pipeline_settings(REPOSITORY)
    (root / "config").mkdir()
    (root / "config" / "summary-eval-tests.json").write_bytes(
        (REPOSITORY / "config" / "summary-eval-tests.json").read_bytes()
    )
    runtime = root / pipeline.output_directory
    stage_configuration(REPOSITORY, runtime, select_model(REPOSITORY, ""))
    listener = runtime / "config" / "hono-server.json"
    settings = json.loads(listener.read_bytes())
    settings["port"] = available_loopback_port()
    listener.write_text(json.dumps(settings), encoding="utf-8")
    fingerprint = runtime / "config" / "host-fingerprints.json"
    controls = json.loads(fingerprint.read_bytes())
    controls["metadata_url"] = None
    fingerprint.write_text(json.dumps(controls), encoding="utf-8")
    run = RunIdentity(
        run_id="123456",
        attempt=1,
        git_sha="a" * 40,
        started_at=datetime.now(UTC),
    )
    packet = StartupPacket(
        version=WORKFLOW_VERSION,
        startup_id=create_execution_id(),
        context=StartupContext(
            run_id=f"{run.started_at:%Y-%m-%d}-{run.run_id}",
            pipeline_name=pipeline.pipeline_name,
            task_name=f"{pipeline.task_name}-generation",
        ),
        git_sha=run.git_sha,
        attempt=run.attempt,
        request_id=create_execution_id(),
        correlation_id=create_execution_id(),
        phase="generation",
        run=run,
    )
    return (
        packet,
        load_settings(REPOSITORY / "config" / "hhem-evaluator" / "settings.json"),
        pipeline,
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="The native machine collector requires Linux proc."
)
def test_serialized_python_packet_starts_stops_and_retains_native_http_machine_results(
    tmp_path: Path,
) -> None:
    packet, settings, pipeline = stage_machine_run(tmp_path)
    assert packet.run is not None
    assert json.loads(packet.model_dump_json())["run"]["git_sha"] == packet.git_sha
    script = REPOSITORY / ".github" / "scripts" / "summary-eval-tests" / "machine-task.ts"
    child = OwnedService(
        "host",
        [required_bun(), "run", "--no-install", str(script), str(tmp_path)],
        tmp_path,
        packet,
        settings,
        pipeline,
    )
    try:
        ready = child.wait_ready(CHILD_STARTUP_MS)
        assert isinstance(ready, HostReady)
        assert ready.pid == child.process.pid and ready.profile_started
        assert ready.hardware.status == "collected"
        controls = json.loads(
            (tmp_path / pipeline.output_directory / "config" / "host-probes.json").read_bytes()
        )
        time.sleep(controls["task_profile"]["cpu_window_ms"] / 1000)
        child.finish_measurement("success")
        stopped = child.close(ready.lifecycle_timeout_ms + settings.worker.stop_grace_ms)
        assert stopped.clean and child.process.returncode == 0
        assert measurement_complete(stopped.machine)
        assert stopped.machine is not None and stopped.machine.outcome == "success"
        assert stopped.machine.end_reason == "explicit_stop"
        assert stopped.server is not None and stopped.server.startup == "ready"
        assert stopped.server.shutdown == "stopped" and stopped.server.exit_code == 0
        evidence = tmp_path / pipeline.output_directory / "logs" / "hono-server-machine.json"
        with evidence.open("rb") as stream:
            encoded = stream.read(pipeline.max_response_bytes + 1)
        assert len(encoded) <= pipeline.max_response_bytes
        native = json.loads(encoded)
        assert native["group"] == "machine" and native["run_id"] == packet.run.run_id
        profile = MachineUsage.model_validate_json(json.dumps(native["reported_profiles"][-1]))
        expected = profile.model_copy(update={"samples": (profile.samples[0], profile.samples[-1])})
        assert stopped.machine == expected
    finally:
        if not child.closed:
            with contextlib.suppress(WorkflowError):
                child.close(settings.worker.shutdown_timeout_ms)
        assert child.process.poll() is not None
