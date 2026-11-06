"""Keep whole-machine observations honest through missing data, EOF and close failures."""

from pathlib import Path

import pytest
from summary_eval_pipeline.host_reader import measurement_complete

from summary_eval_tests.pipeline_cases import NativeHostPipe, prepare_proc


@pytest.mark.parametrize(
    "mode",
    ["normal", "disabled", "unavailable", "missing_ram", "eof", "close_failure"],
)
def test_native_collector_preserves_measurements_and_exact_failure_reasons(
    tmp_path: Path,
    mode: str,
) -> None:
    prepare_proc(tmp_path, memory=mode != "missing_ram")
    host = NativeHostPipe(
        tmp_path,
        platform="unsupported" if mode == "unavailable" else "linux",
        task_profile={"enabled": mode != "disabled"},
        fail_report=mode == "close_failure",
    )
    try:
        prepare_proc(tmp_path, closing=True, memory=mode != "missing_ram")
        clean, profile = host.close(explicit=mode != "eof")
        assert clean is (mode != "close_failure")
        assert host.hardware.status == "collected"
        assert host.hardware.cpu_model is not None
        if mode == "disabled":
            assert profile is None and host.started is False
            return
        assert profile is not None
        if mode == "unavailable":
            assert profile.cpu.value is None
            assert profile.cpu.root.reason == "unsupported_platform"
            assert profile.machine_available_min_kb is None
        elif mode == "missing_ram":
            assert profile.cpu.value is not None
            assert profile.machine_available_min_kb is None
            assert profile.unavailable["machine_available_min_kb"] == "missing_file"
        else:
            assert profile.cpu.value is not None
            assert profile.cpu.value.user + profile.cpu.value.system > 0
            assert profile.machine_available_min_kb == 2048
        if mode == "eof":
            assert profile.outcome == "cancelled" and profile.end_reason == "service_stopped"
        assert measurement_complete(profile) is (mode in ("normal", "close_failure"))
    finally:
        host.close()
        assert host.process.poll() is not None
