"""Can the isolated evidence workflow collect locally without publishing or unsafe inputs?"""

from __future__ import annotations

import copy
import platform
import re
import subprocess
import sys
from typing import Literal

import pytest

from idhazh.telemetry.host_evidence_inputs import ROOT, live_controls, read_bytes, settings

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
    from utilities.host_telemetry_session import LIVE_PROBE_ROOTS

    probe_step = next(
        step for step in steps if step.get("name") == "Rust probe and native raw store"
    )
    for flag, root in zip(LIVE_PROBE_ROOTS[::2], LIVE_PROBE_ROOTS[1::2], strict=True):
        assert f"{flag} {root}" in probe_step["run"]
    for name in ("Rust probe and native raw store", "Rust clock and native raw store"):
        step = next(step for step in steps if step.get("name") == name)
        assert "--manifest host-manifest.json" in step["run"]
    assert "github.run_attempt" in text and '--attempt "$D5_ATTEMPT"' in text
    assert (ROOT / "backend/rust/host-telemetry/rust-toolchain.toml").read_text().find(
        '"1.95.0"'
    ) >= 0


def test_dispatch_memory_choice_resolves_into_the_effective_scratch_config() -> None:
    value = workflow()
    triggers = value["on"]
    assert isinstance(triggers, dict)
    dispatch = triggers["workflow_dispatch"]
    assert isinstance(dispatch, dict)
    control = dispatch["inputs"]["memory_profiling"]
    assert isinstance(control, dict)
    assert control["default"] == "inherit"
    assert control["options"] == ["inherit", "on", "off"]
    jobs = value["jobs"]
    assert isinstance(jobs, dict)
    work = jobs["work"]
    assert isinstance(work, dict)
    steps = work["steps"]
    assert isinstance(steps, list)
    prepare = next(
        step
        for step in steps
        if step.get("name") == "Prepare captures and freeze repeated reference bounds"
    )
    assert prepare["env"]["MEMORY_PROFILING"] == "${{ inputs.memory_profiling || 'inherit' }}"
    assert '!= "inherit"' in prepare["run"]
    assert "--memory-profiling" in prepare["run"]

    native, comparison, _ = settings()
    assert live_controls(native, comparison).memory_profiling_enabled
    assert not live_controls(native, comparison, False).memory_profiling_enabled


def test_workflow_memory_off_survives_session_preparation_in_manifest_and_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hashlib import sha256
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace

    from idhazh.contracts.host_events import HostSessionManifest, ProcessTarget
    from idhazh.contracts.host_evidence import EVIDENCE_VERSION, EvidenceSession, WorkloadResult
    from idhazh.telemetry.host_evidence_inputs import NativeSettings
    from utilities import compare_host_telemetry, host_telemetry_session

    triggers = workflow()["on"]
    assert isinstance(triggers, dict)
    dispatch = triggers["workflow_dispatch"]
    assert isinstance(dispatch, dict)
    memory_choice = dispatch["inputs"]["memory_profiling"]["options"][-1]
    assert memory_choice == "off"
    override = compare_host_telemetry.memory_profiling(memory_choice)

    _, comparison, _ = settings()
    assert comparison.source.observability.memory_profiling_enabled

    target = ProcessTarget(pid=1234, start_ticks=5678)
    child = SimpleNamespace(pid=target.pid)
    process_calls: list[list[str]] = []

    def fake_popen(args: list[str], **_: object) -> SimpleNamespace:
        process_calls.append(args)
        return child

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(host_telemetry_session, "binary", lambda: None)
    monkeypatch.setattr(
        host_telemetry_session,
        "subprocess",
        SimpleNamespace(
            Popen=fake_popen, DEVNULL=subprocess.DEVNULL, STDOUT=subprocess.STDOUT
        ),
    )
    monkeypatch.setattr(host_telemetry_session, "identity", lambda *_: target)

    def fake_wait_for(path: Path, *_: object, **__: object) -> None:
        path.write_text(target.model_dump_json(), encoding="ascii")

    monkeypatch.setattr(host_telemetry_session, "wait_for", fake_wait_for)

    def fake_request(
        _: Path, sequence: int, mode: Literal["reference", "native_only"]
    ) -> WorkloadResult:
        return WorkloadResult(
            version=EVIDENCE_VERSION,
            sequence=sequence,
            mode=mode,
            target=target,
            wall_seconds=0.0,
            clock_skew_seconds=0.0,
            cpu_seconds=0.0,
            instrument_wall_seconds=0.0,
            instrument_cpu_seconds=0.0,
            digest=sha256(f"{sequence}:{mode}".encode("ascii")).hexdigest(),
            iterations=1,
            samples=0,
            cells=None,
            host=None,
            population=(),
            reference_files=(),
        )

    monkeypatch.setattr(host_telemetry_session, "request", fake_request)
    monkeypatch.setattr(host_telemetry_session, "freeze_bounds", lambda *_: ())
    def fake_boot_id(path: Path, maximum: int) -> bytes:
        if str(path).replace("\\", "/").lstrip("/") == "proc/sys/kernel/random/boot_id":
            return b"00000000-0000-0000-0000-000000000001"
        return read_bytes(path, maximum)

    monkeypatch.setattr("utilities.host_telemetry_session.read_bytes", fake_boot_id)

    var_root = ROOT / "backend/var"
    var_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="d16-memory-off-", dir=var_root) as directory:
        evidence_root = Path(directory)
        compile_file = evidence_root / "compile.json"
        compile_file.write_text("{}", encoding="ascii")
        gates = evidence_root / "gates.xml"
        gates.write_text("<testsuites />", encoding="ascii")
        workspace = evidence_root / "workspace"
        host_telemetry_session.prepare(
            workspace,
            git_sha="0" * 40,
            run_number="17",
            attempt=1,
            compile_file=compile_file,
            gates=gates,
            memory_profiling=override,
        )

        effective_config = NativeSettings.model_validate_json(
            (workspace / "native-config.json").read_bytes()
        )
        manifest = HostSessionManifest.model_validate_json(
            (workspace / "manifest.json").read_bytes()
        )
        host_manifest = HostSessionManifest.model_validate_json(
            (workspace / "host-manifest.json").read_bytes()
        )
        session = EvidenceSession.model_validate_json((workspace / "session.json").read_bytes())

    assert len(process_calls) == 1
    assert process_calls[0][1:4] == ["-m", "utilities.host_telemetry_workload", "worker"]
    assert effective_config.controls.memory_profiling_enabled is False
    assert manifest.controls.memory_profiling_enabled is False
    assert host_manifest.controls.memory_profiling_enabled is False
    assert session.manifest.controls.memory_profiling_enabled is False


def test_memory_dispatch_vocabulary_and_launcher_propagation_are_shared() -> None:
    workflows = _load_workflows()
    for name in ("digest.yml", "measure.yml", "rust-host-telemetry.yml"):
        triggers = workflows[name]["on"]
        assert isinstance(triggers, dict)
        dispatch = triggers["workflow_dispatch"]
        assert isinstance(dispatch, dict)
        inputs = dispatch["inputs"]
        assert isinstance(inputs, dict)
        control = inputs["memory_profiling"]
        assert isinstance(control, dict)
        assert control["default"] == "inherit"
        assert control["options"] == ["inherit", "on", "off"]

    digest_text = "\n".join(_strings(workflows["digest.yml"]))
    assert "memory_profiling_control.py" in digest_text
    assert 'MEMORY_ARGS=(--memory-profiling "$MEMORY_PROFILING")' in digest_text
    assert "no sampler started" in digest_text

    measure_text = "\n".join(_strings(workflows["measure.yml"]))
    assert "--config-root backend/var/candidate-config" in measure_text
    assert "Resolve runtime memory collection" in measure_text
    assert "llama-bench memory qualification requires memory profiling" in measure_text


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
