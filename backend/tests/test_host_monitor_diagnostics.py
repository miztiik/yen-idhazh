"""Are the original monitor failures visible without replacing the producer's failure?"""

from pathlib import Path

import pytest
from workflows._harness import _job, _load_workflows, _mapping, _steps

from utilities.d7_host_telemetry import _report_monitor_failure


def test_failure_log_surfaces_the_native_artifact_budget_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "monitor.log").write_text(
        "legacy artifact capacity exhausted\n", encoding="ascii"
    )
    _report_monitor_failure(tmp_path, 1024)
    assert "legacy artifact capacity exhausted" in capsys.readouterr().err


def test_failure_log_remains_bounded_and_reports_missing_diagnostics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "monitor.log").write_bytes(b"x" * 1025)
    _report_monitor_failure(tmp_path, 1024)
    assert "diagnostics unavailable: ValueError" in capsys.readouterr().err
    (tmp_path / "monitor.log").unlink()
    _report_monitor_failure(tmp_path, 1024)
    assert "diagnostics unavailable:" in capsys.readouterr().err


def test_plan_monitor_diagnostics_are_retained_separately_from_run_plan() -> None:
    workflow = _load_workflows()["digest.yml"]
    retained = [
        step for step in _steps(workflow, "plan")
        if step.get("name") == "Retain the plan monitor diagnostics"
    ]
    assert len(retained) == 1
    step = retained[0]
    assert "always()" in str(step["if"])
    assert "IDHAZH_HOST_TELEMETRY_MODE == 'rust'" in str(step["if"])
    assert "IDHAZH_HOST_TELEMETRY_SESSION != ''" in str(step["if"])
    settings = _mapping(step["with"], "diagnostic artifact")
    assert settings["name"] == "host-telemetry-plan"
    assert settings["path"] == "${{ env.IDHAZH_HOST_TELEMETRY_SESSION }}/"
    assert settings["if-no-files-found"] == "error"
    assert _job(workflow, "plan")["outputs"] is not None
