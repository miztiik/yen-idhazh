"""Exercise the actual Python-to-Bun machine helper and its owned loopback Hono application."""

import contextlib
import json
import sys
import time
from pathlib import Path

import pytest
from summary_eval_pipeline.control import HostReady
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.host_reader import MachineUsage, measurement_complete
from summary_eval_pipeline.services import OwnedService

from .contract_examples import REPOSITORY
from .machine_task_cases import reserved_loopback_listener, stage_machine_run
from .test_host_profile_reader_parity import required_bun
from .test_pipeline_lifetime import CHILD_STARTUP_MS


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


@pytest.mark.skipif(
    sys.platform != "linux", reason="The native machine collector requires Linux proc."
)
@pytest.mark.parametrize("failure", ["invalid_settings", "occupied_listener"])
def test_real_helper_startup_failure_retains_safe_cause_without_adopting_another_listener(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    packet, settings, pipeline = stage_machine_run(tmp_path)
    path = tmp_path / pipeline.output_directory / "config" / "hono-server.json"
    controls = json.loads(path.read_bytes())
    with reserved_loopback_listener() as (port, unrelated):
        controls["port"] = "PrivateMachineSettingsCanary" if failure == "invalid_settings" else port
        path.write_text(json.dumps(controls), encoding="utf-8")
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
            with pytest.raises(WorkflowError) as original:
                child.wait_ready(CHILD_STARTUP_MS)
            assert original.value.error.code == "STARTUP_FAILED"
            assert original.value.error.source_code == (
                "MACHINE_API_STARTUP_INVALID"
                if failure == "invalid_settings"
                else "TYPESCRIPT_API_BIND_FAILED"
            )
        finally:
            if not child.closed:
                with pytest.raises(WorkflowError):
                    child.close(settings.worker.shutdown_timeout_ms)
        assert child.process.returncode == 1 and child.stopped is not None
        assert child.stopped.error_code == original.value.error.source_code
        assert unrelated.poll() is None
    captured = capfd.readouterr()
    assert captured.out == ""
    assert "summary_machine_failed" in captured.err
    assert "PrivateMachineSettingsCanary" not in captured.err
    assert "ZodError" not in captured.err
    assert child.stopped.machine is None


@pytest.mark.skipif(
    sys.platform != "linux", reason="The native machine collector requires Linux proc."
)
def test_invalid_private_close_retains_native_cancelled_measurement_and_safe_failure(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    packet, settings, pipeline = stage_machine_run(tmp_path)
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
        assert isinstance(child.wait_ready(CHILD_STARTUP_MS), HostReady)
        assert child.process.stdin is not None
        child.process.stdin.write(b'{"kind":"stop","outcome":"PrivateInvalidCloseCanary"}\n')
        child.process.stdin.flush()
        with pytest.raises(WorkflowError) as failure:
            child.close(settings.worker.shutdown_timeout_ms + settings.worker.forced_stop_ms)
        assert failure.value.error.source_code
        assert child.stopped is not None and child.stopped.error_code
        assert child.stopped.machine is not None
        assert child.stopped.machine.outcome == "cancelled"
        assert child.stopped.machine.end_reason == "service_stopped"
        assert not measurement_complete(child.stopped.machine)
    finally:
        if not child.closed:
            with contextlib.suppress(WorkflowError):
                child.close(settings.worker.shutdown_timeout_ms)
        assert child.process.poll() is not None
    captured = capfd.readouterr()
    assert captured.out == "" and "summary_machine_failed" in captured.err
    assert "PrivateInvalidCloseCanary" not in captured.err
