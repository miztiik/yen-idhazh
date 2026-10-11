"""Does isolated host evidence refuse missing, drifting or unsafe inputs?"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from pydantic import ValidationError

from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_events import HostEvent
from idhazh.contracts.host_evidence import WorkloadRequest, WorkloadResult

pytestmark = pytest.mark.contract


@pytest.fixture
def evidence_workspace(tmp_path: Path) -> Iterator[Path]:
    from idhazh.telemetry.host_evidence_inputs import ROOT

    root = ROOT / "backend/var"
    if tmp_path.is_relative_to(root):
        yield tmp_path
        return
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="d5-test-", dir=root) as directory:
        yield Path(directory)


@pytest.mark.parametrize("mode", ["reference", "native_only", "stop"])
def test_workload_request_round_trip_has_a_versioned_contract(mode: str) -> None:
    request = WorkloadRequest.model_validate({"sequence": 1, "mode": mode})
    assert WorkloadRequest.model_validate_json(request.model_dump_json()) == request
    assert request.version == WorkloadRequest.schema_version()


@pytest.mark.parametrize(
    "payload",
    [
        {"sequence": True, "mode": "reference"},
        {"sequence": 0, "mode": "reference"},
        {"sequence": 1, "mode": "model"},
        {"sequence": 1, "mode": "reference", "url": "https://example.org"},
    ],
)
def test_workload_request_refuses_nonlocal_or_unbounded_commands(payload: object) -> None:
    with pytest.raises(ValidationError):
        WorkloadRequest.model_validate(payload)


def recorded_result(sequence: int = 1) -> WorkloadResult:
    import hashlib
    import json

    from idhazh.contracts.host_events import HostWindowCells, ProcessTarget
    from idhazh.contracts.host_evidence import EVIDENCE_VERSION, WorkloadResult
    from idhazh.contracts.host_fingerprint import HostFingerprintRow
    from idhazh.telemetry.host_evidence_inputs import ROOT, read_bytes

    raw = read_bytes(ROOT / "tests/fixtures/host-events/resource-windows.json", 1048576)
    recorded = json.loads(raw)
    return WorkloadResult(
        version=EVIDENCE_VERSION,
        sequence=sequence,
        mode="reference",
        target=ProcessTarget(pid=100, start_ticks=800),
        wall_seconds=3.0,
        clock_skew_seconds=0.0,
        cpu_seconds=0.0,
        instrument_wall_seconds=0.0,
        instrument_cpu_seconds=0.0,
        digest=hashlib.sha256(raw).hexdigest(),
        iterations=1,
        samples=2,
        cells=HostWindowCells.model_validate(recorded["expected_periodic"]),
        host=HostFingerprintRow(
            version=HostFingerprintRow.schema_version(),
            date="2026-10-10",
            run_id="2026-10-10-17",
            job=ServerJob.WORK,
            shard=0,
            boot_seconds=100.0,
            measured_at="2026-10-10T12:00:00Z",
        ),
        population=(),
        reference_files=(),
    )


def test_frozen_bounds_use_only_preceding_references_and_refuse_noise_or_missing_evidence() -> None:
    from idhazh.contracts.host_events import HostWindowCells
    from idhazh.telemetry.host_evidence_inputs import freeze_bounds, settings

    _, config, _ = settings()
    first = recorded_result()
    second = recorded_result(2)
    frozen = freeze_bounds((first, second), config)
    assert {item.field for item in frozen} == set(config.bounds)
    cpu = next(item for item in frozen if item.field == "cpu_busy_pct")
    assert cpu.absolute == config.bounds["cpu_busy_pct"][0]
    assert cpu.observed_reference_spread == 0.0
    assert second.cells is not None
    cells = HostWindowCells.model_validate({**second.cells.model_dump(), "cpu_busy_pct": 100.0})
    with pytest.raises(ValueError, match="noise exceeds"):
        freeze_bounds((first, second.model_copy(update={"cells": cells})), config)
    with pytest.raises(ValueError, match="evidence is absent"):
        freeze_bounds((first, second.model_copy(update={"cells": None})), config)
    assert freeze_bounds((first, second), config) == frozen


def test_exact_and_numeric_comparisons_do_not_hide_missing_or_corrected_cells() -> None:
    from idhazh.contracts.host_output import CorrectedHostFingerprintRow
    from idhazh.telemetry.host_evidence_comparison import compare_cell, field_classes

    assert compare_cell("cpu_model", "a", "a").passed
    assert not compare_cell("cpu_model", "a", "b", 1.0).passed
    assert not compare_cell("rss", None, 1, 1000.0).passed
    assert compare_cell("rss", 100, 101, 1.0).passed
    assert not compare_cell("rss", 100, 102, 1.0).passed
    classes = {field.field: field.classification for field in field_classes()}
    assert {name.removeprefix("host.") for name in classes if name.startswith("host.")} == set(
        CorrectedHostFingerprintRow.model_fields
    )
    assert classes["host.cpu_logical_processors"] == "corrected"
    assert classes["host.fingerprint"] == "corrected"
    assert classes["host.cpu_model"] == "unchanged"
    assert classes["envelope.writer"] == "physical"


@pytest.mark.parametrize(
    "root", ["state", "state/raw/host-fingerprint", "frontend/public", "corpus"]
)
def test_production_roots_never_become_an_experiment_default(root: str) -> None:
    from idhazh.telemetry.host_evidence_inputs import ROOT, isolated_workspace

    with pytest.raises(ValueError, match="task-owned"):
        isolated_workspace(ROOT / root, create=True)


def test_generated_roots_refuse_aliases_escapes_and_oversized_reads(tmp_path: Path) -> None:
    from idhazh.contracts.host_evidence import EvidenceRoots
    from idhazh.telemetry.host_evidence_inputs import read_bytes, resolve, validate_roots

    roots = EvidenceRoots(
        reference="reference",
        native="native/state",
        native_artifacts="native-artifacts",
        generated_state="generated/state",
        corpus="generated-corpus",
        frontend="generated-frontend",
    )
    validate_roots(tmp_path, roots, "backend/var/events")
    with pytest.raises(ValueError, match="overlap"):
        validate_roots(tmp_path, roots.model_copy(update={"native": "reference/state"}), "events")
    for name in ("../state", "state\\raw", "/state"):
        with pytest.raises(ValueError):
            resolve(tmp_path, name)
    path = tmp_path / "bounded.json"
    path.write_bytes(b"x" * 65)
    with pytest.raises(ValueError, match="byte cap"):
        read_bytes(path, 64)


def test_actual_bounded_hash_workload_changes_with_declared_inputs() -> None:
    import hashlib

    from idhazh.telemetry.host_evidence_inputs import settings
    from utilities.host_telemetry_workload import execute_work

    _, config, _ = settings()
    small = config.model_copy(update={"workload_iterations": 2})
    buffer = bytearray(b"bounded fixture")
    assert execute_work(buffer, small) == hashlib.sha256(bytes(buffer) * 2).hexdigest()
    assert execute_work(buffer, small) != execute_work(buffer, config)


def test_read_only_verifier_consumes_actual_native_cli_bytes_without_python_delegation(
    tmp_path: Path,
) -> None:
    import json
    import os
    import subprocess
    from pathlib import Path
    from uuid import uuid4

    from idhazh.contracts.host_events import HostEvent, HostSessionManifest
    from idhazh.contracts.host_evidence import EVIDENCE_VERSION, EvidenceRoots, EvidenceSession
    from idhazh.telemetry.host_evidence_comparison import (
        field_classes,
        verify_host_chain,
        verify_result,
    )
    from idhazh.telemetry.host_evidence_inputs import (
        ROOT,
        read_bytes,
        settings,
        write_document,
        write_json,
    )

    native, _, config_hash = settings()
    manifest = json.loads(read_bytes(ROOT / "tests/fixtures/host-events/manifest.json", 65536))
    manifest["named_inputs"] = [
        {"name": "capture", "source": "proc.cpuinfo", "relative_path": "capture.json"},
        {"name": "start", "source": "clock.log", "relative_path": "start.txt"},
    ]
    manifest["output_roots"] = ["output/state"]
    model = HostSessionManifest.model_validate(manifest)
    config = native.model_dump(mode="json")
    for key in ("controls", "limits", "capture_limits"):
        config[key] = manifest[key]
    write_json(tmp_path / "config.json", config)
    write_document(tmp_path / "manifest.json", model)
    (tmp_path / "capture.json").write_bytes(
        read_bytes(ROOT / "tests/fixtures/host-events/probe-clock.json", 1048576)
    )
    (tmp_path / "start.txt").write_bytes(b"2026-10-10T11:59:18Z\n")
    command = HostEvent.model_validate(
        {
            **{
                key: manifest[key]
                for key in (
                    "version",
                    "date",
                    "run_id",
                    "attempt",
                    "job",
                    "shard",
                    "session_id",
                )
            },
            "kind": "host.probe",
            "event_id": str(uuid4()),
            "reply_to": None,
            "emitter_id": "operator",
            "sequence": 1,
            "emitted_at": "2026-10-10T12:00:00Z",
            "body": {
                "controls": manifest["controls"],
                "input_names": ["capture"],
                "target": manifest["cpu_target"],
            },
        }
    )
    write_document(tmp_path / "command.json", command)
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "backend/var/rust-host-telemetry"))
    binary = (
        target
        / "debug"
        / ("idhazh-host-telemetry.exe" if os.name == "nt" else "idhazh-host-telemetry")
    )
    assert binary.is_file(), "Run the existing native group before these file integration tests."
    result = subprocess.run(
        [
            str(binary),
            "probe",
            "--workspace",
            str(tmp_path),
            "--manifest",
            "manifest.json",
            "--config",
            "config.json",
            "--command",
            "command.json",
            "--snapshot",
            "capture",
            "--format",
            "json",
            "--cache-multiple",
            "2",
            "--result-id",
            str(uuid4()),
        ],
        cwd=ROOT,
        env={**os.environ, "IDHAZH_PYTHON": "missing-python", "PYTHON": "missing-python"},
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()
    roots = EvidenceRoots(
        reference="reference",
        native="output/state",
        native_artifacts="native-artifacts",
        generated_state="generated/state",
        corpus="generated-corpus",
        frontend="generated-frontend",
    )
    rows = (recorded_result(), recorded_result(2))
    resource_id = uuid4()
    session = EvidenceSession(
        version=EVIDENCE_VERSION,
        created_at="2026-10-10T12:00:00Z",
        manifest=HostSessionManifest.model_validate(
            {
                **model.model_dump(mode="json"),
                "session_id": str(resource_id),
                "event_root": model.event_root.replace(str(model.session_id), str(resource_id)),
            }
        ),
        host_manifest=model,
        roots=roots,
        calibration=rows,
        bounds=(),
        plain=rows[0],
        config_sha256=config_hash,
        field_classes=field_classes(),
    )
    result_name = result.stdout.decode().strip()
    body = verify_result(tmp_path, result_name, session)
    assert (body.row.cpu_physical_cores, body.row.cpu_logical_processors) == (3, 4)
    assert body.row.cpu_quota_cores == 0.5 and body.row.fingerprint_version == 2
    with pytest.raises(ValidationError, match="must be distinct"):
        EvidenceSession.model_validate({**session.model_dump(), "manifest": model})
    with pytest.raises(ValidationError, match="identity and target"):
        EvidenceSession.model_validate(
            {
                **session.model_dump(),
                "host_manifest": model.model_copy(update={"git_sha": "0" * 40}),
            }
        )
    with pytest.raises(ValueError, match="foreign root"):
        verify_result(
            tmp_path,
            result_name,
            session.model_copy(
                update={
                    "roots": roots.model_copy(update={"native": "foreign/state"}),
                }
            ),
        )
    probe_event = HostEvent.model_validate_json(read_bytes(tmp_path / result_name, 262144))
    write_document(tmp_path / "probe.json", command)
    clock_command = HostEvent.model_validate(
        {
            **command.model_dump(mode="json"),
            "kind": "host.clock",
            "sequence": 2,
            "event_id": str(uuid4()),
            "body": {
                **command.body.model_dump(mode="json"),
                "input_names": ["capture", "start"],
                "previous_result_id": str(probe_event.event_id),
            },
        }
    )
    write_document(tmp_path / "clock.json", clock_command)
    capture = json.loads(read_bytes(tmp_path / "capture.json", 1048576))
    capture["written_at_ms"] += 1
    (tmp_path / "capture.json").write_text(json.dumps(capture), encoding="ascii")
    clock_output = subprocess.run(
        [
            str(binary),
            "clock",
            "--workspace",
            str(tmp_path),
            "--manifest",
            "manifest.json",
            "--config",
            "config.json",
            "--command",
            "clock.json",
            "--snapshot",
            "capture",
            "--previous-result",
            result_name,
            "--job-start-input",
            "start",
            "--previous-plan",
            f"{model.event_root}/writes/{command.event_id}.plan.json",
            "--format",
            "json",
            "--result-id",
            str(uuid4()),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=60,
        env={**os.environ, "IDHAZH_PYTHON": "missing-python", "PYTHON": "missing-python"},
    )
    assert clock_output.returncode == 0, clock_output.stderr.decode()
    clock_name = clock_output.stdout.decode().strip()
    first, last = verify_host_chain(tmp_path, result_name, clock_name, session)
    assert first.cpu == last.cpu and first.row.fingerprint == last.row.fingerprint
    assert last.row.job_seconds == 42 and first.row.job_seconds is None
    from idhazh.contracts.host_output import HostWritePlan
    from idhazh.telemetry.host_evidence_inputs import read_model

    clock_plan = read_model(
        tmp_path / f"{model.event_root}/writes/{clock_command.event_id}.plan.json",
        HostWritePlan,
        262144,
    )
    with pytest.raises(ValueError, match="strictly later clock"):
        verify_result(tmp_path, result_name, session, previous_plan=clock_plan)
    retained = tmp_path / f"{model.event_root}/commands/{clock_command.event_id}.json"
    raw = read_bytes(retained, 65536)
    declared = read_bytes(tmp_path / "clock.json", 65536)
    for changes in (
        {"sequence": 1},
        {
            "body": {
                **clock_command.body.model_dump(mode="json"),
                "previous_result_id": str(uuid4()),
            }
        },
    ):
        changed = json.dumps({**clock_command.model_dump(mode="json"), **changes}).encode("ascii")
        retained.write_bytes(changed)
        (tmp_path / "clock.json").write_bytes(changed)
        with pytest.raises(ValueError, match="predecessor"):
            verify_host_chain(tmp_path, result_name, clock_name, session)
        retained.write_bytes(raw)
        (tmp_path / "clock.json").write_bytes(declared)


def test_live_certification_is_not_a_windows_fixture_success(evidence_workspace: Path) -> None:
    import platform

    from idhazh.telemetry.host_evidence_comparison import compare

    if platform.system() != "Linux":
        with pytest.raises(ValueError, match="another operating system"):
            compare(evidence_workspace, probe="probe.json", clock="clock.json")
    else:
        with pytest.raises(FileNotFoundError):
            compare(evidence_workspace, probe="probe.json", clock="clock.json")


def test_real_native_replay_population_reconciles_and_refuses_nonpython_counts(
    tmp_path: Path,
) -> None:
    import json

    from test_host_event_resource_parity import prepare, run

    from idhazh.contracts.host_events import (
        HostEvent,
        LegacyJobSample,
        LegacyProcessRollcall,
        ProcessTarget,
        WindowResultBody,
    )
    from idhazh.contracts.host_evidence import EVIDENCE_VERSION, ReferenceSample, SamplerCompletion
    from idhazh.telemetry.host_evidence_inputs import read_bytes, settings, write_document
    from idhazh.telemetry.host_evidence_samples import reference_coverage, sample_coverage

    root = tmp_path / "resources"
    manifest, replay = prepare(root, memory=True, periodic=True)
    result = run(
        root, "resource-replay", "--snapshot", "resources", "--artifact-root", "native-artifacts"
    )
    assert result.returncode == 0, result.stderr.decode()
    events = [
        HostEvent.model_validate_json(read_bytes(path, 262144))
        for path in (root / manifest["event_root"] / "results").glob("*.json")
    ]
    windows = tuple(event.body for event in events if isinstance(event.body, WindowResultBody))
    _, comparison, _ = settings()
    with pytest.raises(ValueError, match="coverage is absent"):
        sample_coverage(root, windows, comparison)
    # Declared enclosing-window fixture, not a live certificate: boundary samples
    # are unassignable in the original short replay and must be refused above.
    windows = tuple(
        window.model_copy(update={"opened_at": "2026-10-10T11:59:59Z"}) for window in windows
    )
    count, coverage = sample_coverage(root, windows, comparison)
    assert count == 1 and len(coverage) == 2
    assert all(window.samples == 1 for window in coverage)
    roster_path = root / "native-artifacts/python-procs.jsonl"
    raw = read_bytes(roster_path, 1048576)
    rows = [json.loads(line) for line in raw.splitlines()]
    rows[0]["comm"] = "idhazh-host-telemetry"
    roster_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="ascii")
    with pytest.raises(ValueError, match="rollcall"):
        sample_coverage(root, windows, comparison)
    roster_path.write_bytes(raw)
    with pytest.raises(ValueError, match="coverage is absent"):
        sample_coverage(root, windows, comparison.model_copy(update={"min_window_samples": 100}))
    population = tuple(
        ProcessTarget.model_validate(process["target"])
        for process in replay["frames"][0]["population"]["value"]
    )
    reference = ReferenceSample(
        version=EVIDENCE_VERSION,
        record=LegacyJobSample.model_validate_json(
            read_bytes(root / "native-artifacts/rss-samples.jsonl", 1048576).splitlines()[0]
        ),
        population=population,
        rollcall=tuple(
            LegacyProcessRollcall.model_validate_json(line) for line in raw.splitlines()
        ),
    )
    path = root / "reference/samples-1/sample-0.json"
    write_document(path, reference)
    count_path = path.with_name("count.json")
    write_document(count_path, SamplerCompletion(version=EVIDENCE_VERSION, samples=1))
    row = recorded_result().model_copy(
        update={"samples": 1, "target": population[0], "population": population}
    )
    reference_coverage(root, (row,), comparison)
    with pytest.raises(ValueError, match="sample count"):
        reference_coverage(root, (row.model_copy(update={"samples": 2}),), comparison)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        reference_coverage(root, (row,), comparison)


@pytest.mark.parametrize(
    "body",
    [
        "<testsuites/>",
        '<testsuites><testcase classname="fixture" name="case"><failure/></testcase></testsuites>',
        '<testsuites><testcase classname="fixture" name="case"><skipped/></testcase></testsuites>',
        '<testsuites><testcase classname="fixture" name="case"/></testsuites>',
    ],
)
def test_absent_or_failed_required_fixture_evidence_can_not_be_a_green_verdict(
    tmp_path: Path, body: str
) -> None:
    from idhazh.telemetry.host_evidence_artifacts import validate_gates
    from idhazh.telemetry.host_evidence_inputs import settings

    (tmp_path / "gates.xml").write_text(body, encoding="ascii")
    _, config, _ = settings()
    with pytest.raises(ValueError, match=r"evidence|gates"):
        validate_gates(tmp_path, config)


def test_empty_logs_are_valid_artifacts_but_inventory_growth_is_bounded(tmp_path: Path) -> None:
    from idhazh.telemetry.host_evidence_artifacts import artifact_inventory
    from idhazh.telemetry.host_evidence_inputs import settings

    (tmp_path / "worker.log").write_bytes(b"")
    _, config, _ = settings()
    assert artifact_inventory(tmp_path, config)[0].bytes == 0
    (tmp_path / "payload.json").write_bytes(b"bounded")
    with pytest.raises(ValueError, match="inventory exceeds"):
        artifact_inventory(tmp_path, config.model_copy(update={"max_artifact_files": 1}))


def test_real_partial_worker_cleanup_refuses_reused_identity_and_verifies_exit(
    evidence_workspace: Path,
) -> None:
    import platform
    import subprocess
    import sys

    from idhazh.contracts.host_events import ProcessTarget
    from idhazh.contracts.host_evidence import CleanupEvidence
    from idhazh.telemetry.host_evidence_inputs import read_model, settings, write_document
    from utilities.host_telemetry_reference import identity
    from utilities.host_telemetry_session import cleanup, stop_partial

    if platform.system() != "Linux":
        with pytest.raises(ValueError, match="requires live Linux"):
            stop_partial(ProcessTarget(pid=1, start_ticks=1))
        return
    native, _, _ = settings()
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        target = identity(child.pid, native)
        with pytest.raises(ValueError, match="reused"):
            stop_partial(target.model_copy(update={"start_ticks": target.start_ticks + 1}))
        assert child.poll() is None
        write_document(evidence_workspace / "worker-launched.json", target)
        cleanup(evidence_workspace)
        child.wait(timeout=native.limits.drain_timeout_ms / 1000)
        assert child.returncode is not None
        assert read_model(
            evidence_workspace / "cleanup.json", CleanupEvidence, native.limits.max_result_bytes
        ).targets == (target,)
        (evidence_workspace / "worker.log").write_text(
            "recorded worker failure\n", encoding="ascii"
        )
        from utilities.host_telemetry_session import request

        with pytest.raises(ValueError, match=r"worker stopped.*recorded worker failure"):
            request(evidence_workspace, 1, "reference")
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=native.limits.drain_timeout_ms / 1000)


def test_full_linux_yaml_stages_or_explicit_windows_refusal(evidence_workspace: Path) -> None:
    import os
    import platform

    from idhazh.contracts.host_evidence import (
        CommandMeasurement,
        EvidenceSession,
        HostEvidenceReport,
    )
    from idhazh.telemetry.host_evidence_comparison import compare
    from idhazh.telemetry.host_evidence_inputs import ROOT, read_bytes, read_model, settings
    from utilities.host_telemetry_session import cleanup, drain, invoke, prepare, start, workload

    native, _, _ = settings()
    workspace = evidence_workspace / "live"
    if os.environ.get("IDHAZH_D5_LIVE_TEST") != "1":
        if platform.system() != "Linux":
            with pytest.raises(ValueError, match="requires Linux"):
                prepare(
                    workspace,
                    git_sha="0" * 40,
                    run_number="1",
                    attempt=1,
                    compile_file=evidence_workspace / "missing.json",
                    gates=evidence_workspace / "missing.xml",
                )
        else:
            # Routine gates do not create a second live trial or invent missing build evidence.
            with pytest.raises(FileNotFoundError):
                read_model(
                    evidence_workspace / "missing.json",
                    CommandMeasurement,
                    native.limits.max_result_bytes,
                )
        return
    assert platform.system() == "Linux"
    build_path = ROOT / "backend/var/d5-compile.json"
    build = read_model(build_path, CommandMeasurement, native.limits.max_result_bytes)
    try:
        prepare(
            workspace,
            git_sha=build.git_sha,
            run_number="1",
            attempt=2,
            compile_file=build_path,
            gates=ROOT / "backend/var/d5-gates.xml",
        )
        env = dict(
            line.split("=", 1)
            for line in read_bytes(
                workspace / "workflow.env",
                native.limits.max_result_bytes,
            )
            .decode("ascii")
            .splitlines()
        )
        session = read_model(
            workspace / "session.json", EvidenceSession, native.limits.max_result_bytes
        )
        frozen = session.bounds
        assert session.manifest.attempt == session.host_manifest.attempt == 2
        assert session.manifest.session_id != session.host_manifest.session_id
        assert session.manifest.cpu_target == session.host_manifest.cpu_target
        codec = ("--format", env["D5_FORMAT"], "--compression", env["D5_COMPRESSION"])
        invoke(
            workspace,
            "probe",
            "--command",
            "probe.json",
            "--metadata-input",
            "metadata",
            "--cache-multiple",
            env["D5_CACHE_MULTIPLE"],
            "--result-id",
            env["D5_PROBE_ID"],
            *codec,
            manifest="host-manifest.json",
        )
        start(workspace)
        workload(workspace)
        drain(workspace)
        invoke(
            workspace,
            "clock",
            "--command",
            "clock.json",
            "--previous-result",
            env["D5_PROBE_RESULT"],
            "--previous-plan",
            env["D5_PROBE_PLAN"],
            "--job-start-input",
            "start",
            "--result-id",
            env["D5_CLOCK_ID"],
            *codec,
            manifest="host-manifest.json",
        )
        report = compare(workspace, probe=env["D5_PROBE_RESULT"], clock=env["D5_CLOCK_RESULT"])
        assert report.session.bounds == frozen
        assert report.correctness == "passed", report.model_dump_json()
        assert report.native_sample_count >= len(report.paired)
        assert session.manifest.cpu_target is not None
        assert session.manifest.cpu_target.pid in report.native_population
        assert len(report.ack_seconds) == 1 + 2 * len(report.paired)
        assert any(
            file.path.startswith("native/state/raw/host-fingerprint/") for file in report.files
        )
        assert any(
            file.path.startswith("reference/state/raw/host-fingerprint/") for file in report.files
        )
        assert (
            read_model(
                workspace / "report.json", HostEvidenceReport, native.limits.max_result_bytes
            )
            == report
        )
    finally:
        if workspace.is_dir():
            cleanup(workspace)


def test_recorded_population_keeps_memory_when_executable_is_unavailable(tmp_path: Path) -> None:
    from test_host_event_resource_parity import prepare, write_frame

    from idhazh.telemetry.host_evidence_inputs import settings
    from utilities.host_telemetry_reference import sample_population

    _, replay = prepare(tmp_path / "resources", memory=True, periodic=True)
    frame = replay["frames"][0]
    proc = tmp_path / "proc"
    write_frame(proc, frame)
    first_pid = frame["population"]["value"][0]["target"]["pid"]
    (proc / str(first_pid) / "cmdline").write_bytes(
        b"/usr/bin/python\0-u\0-m\0idhazh\0secret-not-exported\0"
    )
    native, comparison, _ = settings()
    sample = sample_population(
        tmp_path / "capture", native, comparison, "2026-10-10T12:00:00Z", proc=proc
    )
    assert {row.pid for row in sample.rollcall} == {
        process["target"]["pid"] for process in frame["population"]["value"]
    }
    assert sample.record.python_procs == 3
    assert sample.record.python_vmrss_kb == 350
    assert sample.record.python_vmhwm_kb == 420
    assert all(row.exe is None for row in sample.rollcall)
    assert all(row.args is None or "secret-not-exported" not in row.args for row in sample.rollcall)
    assert (tmp_path / f"capture/{first_pid}/cmdline").read_bytes() == (
        b"/usr/bin/python\0-u\0-m\0idhazh"
    )


def test_missing_evidence_refuses_an_exited_producer_without_waiting(tmp_path: Path) -> None:
    import subprocess
    import sys

    from utilities.host_telemetry_workload import wait_for

    child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(7)"])
    child.wait(timeout=30)
    with pytest.raises(ValueError, match="producer exited with code 7"):
        wait_for(tmp_path / "missing.json", 120, 50, child=child)


def test_configuration_refuses_missing_bounds_reserved_overrides_and_nonendpoint_cadence() -> None:
    import json

    from idhazh.telemetry.host_evidence_inputs import (
        ComparisonSettings,
        comparison_settings,
        settings,
    )

    _, config, _ = settings()
    data = config.model_dump()
    changes: tuple[dict[str, Any], ...] = (
        {"bounds": {}},
        {"resource_interval_seconds": 1.0},
        {"workload_memory_mib": True},
        {"unknown": 1},
    )
    for change in changes:
        with pytest.raises(ValidationError):
            ComparisonSettings.model_validate({**data, **change})
    with pytest.raises(ValueError, match="cannot override"):
        comparison_settings(json.dumps(data, default=str).encode("ascii"), config.source)


def test_real_native_resource_exchange_rejects_reordered_or_foreign_received_evidence(
    tmp_path: Path,
) -> None:
    import json
    from uuid import uuid4

    from test_host_event_resource_parity import event, prepare, run

    from idhazh.contracts.host_events import HostEvent, HostSessionManifest, ProcessTarget
    from idhazh.contracts.host_evidence import EVIDENCE_VERSION, EvidenceRoots, EvidenceSession
    from idhazh.telemetry.host_evidence_comparison import field_classes
    from idhazh.telemetry.host_evidence_inputs import (
        read_bytes,
        retain_native,
        settings,
        write_json,
    )
    from idhazh.telemetry.host_evidence_samples import resource_chain

    root = tmp_path / "exchange"
    manifest, replay = prepare(root, memory=True, periodic=False)
    manifest["workers"] = [{**manifest["workers"][0], "server": None}]
    manifest["windows"] = manifest["windows"][:1]
    manifest["cpu_target"] = manifest["workers"][0]["target"]
    manifest["cpu_target_role"] = "python_worker"
    actions: list[dict[str, Any]] = [
        {"frame": frame, "at_ms": frame * 1000, "event": event(manifest, kind, 0, sequence)}
        for kind, sequence, frame in (
            ("worker.register", 1, 0),
            ("window.begin", 2, 0),
            ("window.end", 3, 3),
            ("monitor.stop", 1, 3),
        )
    ]
    replay["actions"] = actions
    (root / "manifest.json").write_bytes(json.dumps(manifest).encode("ascii"))
    (root / f"{manifest['event_root']}/captures/resources.json").write_bytes(
        json.dumps(replay).encode("ascii")
    )
    result = run(
        root, "resource-replay", "--snapshot", "resources", "--artifact-root", "native-artifacts"
    )
    assert result.returncode == 0, result.stderr.decode()
    bodies: dict[str, tuple[HostEvent, bytes]] = {}
    for path in (root / manifest["event_root"] / "results").glob("*.json"):
        raw = read_bytes(path, 262144)
        value = HostEvent.model_validate_json(raw)
        bodies[value.kind] = (value, raw)
    for index, kind in enumerate(("worker.registered", "window.begun", "window.result")):
        retain_native(root / f"observed/{index}.json", bodies[kind][1], 262144)
    retain_native(root / "ready.json", bodies["monitor.ready"][1], 262144)
    retain_native(root / "drained.json", bodies["monitor.stopped"][1], 262144)
    for action in actions:
        command = action["event"]
        write_json(
            root
            / (
                "stop.json"
                if command["kind"] == "monitor.stop"
                else f"commands/{command['event_id']}.json"
            ),
            command,
        )
    model = HostSessionManifest.model_validate(manifest)
    host_id = uuid4()
    host = HostSessionManifest.model_validate(
        {
            **manifest,
            "session_id": str(host_id),
            "event_root": model.event_root.replace(str(model.session_id), str(host_id)),
        }
    )
    row = recorded_result().model_copy(
        update={"target": ProcessTarget.model_validate(manifest["cpu_target"])}
    )
    session = EvidenceSession(
        version=EVIDENCE_VERSION,
        created_at="2026-10-10T12:00:00Z",
        manifest=model,
        host_manifest=host,
        roots=EvidenceRoots(
            reference="reference",
            native=manifest["output_roots"][0],
            native_artifacts="native-artifacts",
            generated_state="generated/state",
            corpus="generated-corpus",
            frontend="generated-frontend",
        ),
        calibration=(row, row.model_copy(update={"sequence": 2})),
        plain=row,
        bounds=(),
        config_sha256=settings()[2],
        field_classes=field_classes(),
    )
    ids = resource_chain(root, session)
    assert len(ids) == 5 and ids[0] == bodies["monitor.ready"][0].event_id
    path = root / "observed/1.json"
    raw = read_bytes(path, 262144)
    for change, message in (
        ({"sequence": 1}, "ordering"),
        ({"session_id": str(uuid4())}, "identity"),
        (
            {
                "body": {
                    **bodies["window.begun"][0].body.model_dump(mode="json"),
                    "item_id": "foreign-item-99",
                }
            },
            "selected window",
        ),
    ):
        path.write_bytes(
            json.dumps({**bodies["window.begun"][0].model_dump(mode="json"), **change}).encode(
                "ascii"
            )
        )
        with pytest.raises(ValueError, match=message):
            resource_chain(root, session)
        path.write_bytes(raw)


def test_live_controls_refuse_memory_off_or_copy_allocation_before_any_capture() -> None:
    from idhazh.telemetry.host_evidence_inputs import live_controls, settings

    native, config, _ = settings()
    controls = live_controls(native, config)
    assert controls.resource_interval_seconds == config.resource_interval_seconds
    assert controls.job_sample_interval_seconds == config.sample_interval_seconds
    for change in ({"memory_profiling_enabled": False}, {"memcpy_enabled": True}):
        changed = native.model_copy(update={"controls": native.controls.model_copy(update=change)})
        with pytest.raises(ValueError, match="requires memory on"):
            live_controls(changed, config)
    with pytest.raises(ValueError, match="retry retention"):
        live_controls(native, config.model_copy(update={"sample_interval_seconds": 0.5}))
