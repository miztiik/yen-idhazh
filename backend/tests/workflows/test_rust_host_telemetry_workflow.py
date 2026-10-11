"""Can the isolated evidence workflow collect locally without publishing or unsafe inputs?"""

from __future__ import annotations

import copy
import re
import subprocess
import sys

import pytest

from idhazh.telemetry.host_evidence_inputs import ROOT, settings

from ._harness import _load_workflows, _strings

pytestmark = pytest.mark.workflow


def workflow() -> dict[str, object]:
    return _load_workflows()["rust-host-telemetry.yml"]


def require_isolation(value: dict[str, object]) -> None:
    assert value["permissions"] == {"contents": "read"}
    jobs = value["jobs"]
    assert isinstance(jobs, dict) and set(jobs) == {"work"}
    job = jobs["work"]
    assert job["runs-on"] == "ubuntu-latest"
    assert "permissions" not in job
    steps = job["steps"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] == "false"
    text = "\n".join(_strings(value))
    assert not re.search(
        r"secrets\.|git\s+(?:push|commit)|gh\s+(?:pr|workflow|run)|"
        r"measure\.yml|deploy-pages|model-server|feed_url|https?://",
        text,
    )
    upload = next(
        step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert upload["if"] == "always()"
    assert upload["with"]["retention-days"] == "7"
    assert upload["with"]["if-no-files-found"] == "error"
    stop = next(step for step in steps if step.get("name") == "Stop only owned process identities")
    assert stop["if"] == "always()"
    assert "cleanup --workspace" in stop["run"]


def test_workflow_has_read_only_permissions_local_inputs_and_expiring_artifacts() -> None:
    require_isolation(workflow())


@pytest.mark.parametrize(
    "fault", ["permissions", "credentials", "publishing", "retention", "cleanup"]
)
def test_generated_unsafe_workflow_is_rejected(fault: str) -> None:
    value = copy.deepcopy(workflow())
    jobs = value["jobs"]
    assert isinstance(jobs, dict)
    steps = jobs["work"]["steps"]
    if fault == "permissions":
        value["permissions"] = {"contents": "write"}
    elif fault == "credentials":
        steps[0]["with"]["persist-credentials"] = True
    elif fault == "publishing":
        steps.append({"run": "gh workflow run measure.yml"})
    elif fault == "retention":
        steps[-1]["with"]["retention-days"] = 30
    else:
        steps[-2]["if"] = "success()"
    with pytest.raises(AssertionError):
        require_isolation(value)


def test_yaml_separates_every_required_event_lifetime_boundary() -> None:
    value = workflow()
    jobs = value["jobs"]
    assert isinstance(jobs, dict)
    steps = jobs["work"]["steps"]
    names = [step.get("name") for step in steps]
    required = [
        "Prepare captures and freeze repeated reference bounds",
        "Rust probe and native raw store",
        "Start native monitor and verify readiness",
        "Same-target reference and native-only paired workloads",
        "Close windows and drain",
        "Rust clock and native raw store",
        "Read-only same-file and receipt comparison",
        "Stop only owned process identities",
    ]
    positions = [names.index(name) for name in required]
    assert positions == sorted(positions)
    text = "\n".join(_strings(value))
    for name in (
        "test_rust_host_file_parity",
        "test_rust_host_store_parity",
        "test_rust_host_receipts",
        "test_host_event_rust_parity",
        "test_host_event_resource_parity",
        "test_host_migration",
        "test_host_fingerprint_migration",
    ):
        assert name in text
    assert "cargo fetch --locked" in text
    assert "cargo test --locked --offline" in text
    assert "--metadata-input metadata" in text
    assert "--job-start-input start" in text
    for name in ("Rust probe and native raw store", "Rust clock and native raw store"):
        step = next(step for step in steps if step.get("name") == name)
        assert "--manifest host-manifest.json" in step["run"]
    assert "github.run_attempt" in text and '--attempt "$D5_ATTEMPT"' in text
    assert (ROOT / "backend/rust/host-telemetry/rust-toolchain.toml").read_text().find(
        '"1.95.0"'
    ) >= 0


def test_cli_requires_an_explicit_root_and_can_not_dispatch_measurements() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "utilities.compare_host_telemetry", "prepare"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0 and b"--workspace" in result.stderr
    result = subprocess.run(
        [sys.executable, "-m", "utilities.compare_host_telemetry", "measure"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0 and b"invalid choice" in result.stderr


def test_comparison_settings_do_not_add_sections_to_the_strict_native_config() -> None:
    native, comparison, _ = settings()
    assert set(native.model_dump()) == {
        "version",
        "controls",
        "limits",
        "capture_limits",
        "verification_limits",
    }
    assert comparison.calibration_runs >= 2 and comparison.paired_runs >= 2
    assert comparison.workload_memory_mib <= 128 and comparison.workload_iterations <= 256
