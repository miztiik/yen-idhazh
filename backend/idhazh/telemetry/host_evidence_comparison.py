"""Do the same native files and live worker observations satisfy the frozen evidence contract?"""

from __future__ import annotations

import hashlib
import os
import platform
from datetime import UTC, datetime
from pathlib import Path

from idhazh.contracts.file_envelope import FileEnvelope, RowIdentity, WriterIdentity
from idhazh.contracts.host_events import (
    MEMORY_SOURCES,
    WINDOW_CELL_SOURCES,
    CollectionControls,
    CpuDiagnostics,
    HostCaptureLimits,
    HostCommandBody,
    HostEvent,
    HostEventLimits,
    HostResultBody,
    HostSessionManifest,
    HostWindowCells,
    JobSampleBody,
    LegacyJobSample,
    LegacyProcessRollcall,
    MonitorReadyBody,
    ProcessRollcallBody,
    ProcessTarget,
    SourceCoverage,
    StopBody,
    StoppedBody,
    WindowBegunBody,
    WindowBody,
    WindowResultBody,
    WorkerBody,
)
from idhazh.contracts.host_evidence import (
    EVIDENCE_VERSION,
    CleanupEvidence,
    CommandMeasurement,
    EvidenceFile,
    EvidenceRoots,
    EvidenceSession,
    FieldBound,
    FieldClassification,
    FieldComparison,
    GateEvidence,
    HostEvidenceReport,
    MonitorMeasurement,
    PairedEvidence,
    ReferenceSample,
    SamplerCompletion,
    Scalar,
    WindowSampleCoverage,
    WorkloadRequest,
    WorkloadResult,
)
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.host_output import (
    CorrectedHostFingerprintRow,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
    fingerprint_v2,
)
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.ledger.persist import load_stored, read_envelope
from idhazh.telemetry.host_evidence_artifacts import (
    CORRECTED_GATE,
    artifact_inventory,
    file_evidence,
    validate_gates,
)
from idhazh.telemetry.host_evidence_inputs import (
    ROOT,
    ComparisonSettings,
    NativeSettings,
    freeze_bounds,
    isolated_workspace,
    live_controls,
    read_bytes,
    read_model,
    resolve,
    settings,
    validate_roots,
    write_document,
)
from idhazh.telemetry.host_evidence_samples import (
    reference_coverage,
    resource_chain,
    sample_coverage,
)
from idhazh.telemetry.host_output_verify import verify_host_output

CORRECTED_FIELDS = frozenset(
    {
        "fingerprint",
        "fingerprint_version",
        "cpu_physical_cores",
        "cpu_logical_processors",
        "cpu_allowed_processors",
        "cpu_quota_cores",
        "cpu_quota_state",
        "cpu_target_measured_at",
        "cpu_observed_mhz",
        "cpu_reported_max_mhz",
    }
)
CONTEXT_FIELDS = frozenset({"version", "date", "run_id", "job", "shard"})
UNCHANGED_FIELDS = frozenset(
    {
        "cpu_model",
        "cpu_vendor",
        "cpu_family",
        "cpu_model_number",
        "cpu_stepping",
        "microcode",
        "l3_cache_bytes",
        "flags",
        "boot_seconds",
        "memcpy_gib_s",
        "memcpy_probe_mib",
        "vm_size",
        "vm_location",
        "vm_zone",
        "vm_fault_domain",
        "runner_name",
        "measured_at",
        "model_load_ms",
        "job_seconds",
        "server_prompt_tokens",
        "server_prompt_seconds",
    }
)


def field_classes() -> tuple[FieldClassification, ...]:
    fields = set(CorrectedHostFingerprintRow.model_fields)
    if fields != CORRECTED_FIELDS | CONTEXT_FIELDS | UNCHANGED_FIELDS:
        raise ValueError("every candidate host field needs an explicit classification")
    classes = [
        FieldClassification(
            field=f"host.{name}",
            classification=(
                "corrected"
                if name in CORRECTED_FIELDS
                else "context"
                if name in CONTEXT_FIELDS
                else "unchanged"
            ),
        )
        for name in CorrectedHostFingerprintRow.model_fields
    ]
    for label, model, category in (
        ("window", HostWindowCells, "unchanged"),
        ("identity", RowIdentity, "context"),
        ("envelope", FileEnvelope, "physical"),
        ("job_sample", LegacyJobSample, "unchanged"),
        ("population", LegacyProcessRollcall, "context"),
        ("event", HostEvent, "context"),
        ("cpu_diagnostics", CpuDiagnostics, "context"),
        ("plan", HostWritePlan, "context"),
        ("completion", HostWriteCompletion, "physical"),
        ("receipt", PublicationReceipt, "physical"),
        ("manifest", HostSessionManifest, "context"),
        ("roots", EvidenceRoots, "context"),
        ("workload", WorkloadResult, "context"),
        ("reference_sample", ReferenceSample, "context"),
        ("session", EvidenceSession, "context"),
        ("compile", CommandMeasurement, "context"),
        ("monitor", MonitorMeasurement, "context"),
        ("paired", PairedEvidence, "context"),
        ("report", HostEvidenceReport, "context"),
        ("host_result", HostResultBody, "context"),
        ("host_command", HostCommandBody, "context"),
        ("window_result", WindowResultBody, "context"),
        ("source_coverage", SourceCoverage, "context"),
        ("window_coverage", WindowSampleCoverage, "context"),
        ("process_target", ProcessTarget, "context"),
        ("bound", FieldBound, "context"),
        ("request", WorkloadRequest, "context"),
        ("sampler_completion", SamplerCompletion, "context"),
        ("cleanup", CleanupEvidence, "context"),
        ("file", EvidenceFile, "physical"),
        ("field_comparison", FieldComparison, "context"),
        ("field_classification", FieldClassification, "context"),
        ("gates", GateEvidence, "context"),
        ("ready", MonitorReadyBody, "context"),
        ("worker", WorkerBody, "context"),
        ("window_command", WindowBody, "context"),
        ("window_begun", WindowBegunBody, "context"),
        ("stop", StopBody, "context"),
        ("stopped", StoppedBody, "context"),
        ("sample_event", JobSampleBody, "unchanged"),
        ("rollcall_event", ProcessRollcallBody, "context"),
        ("controls", CollectionControls, "context"),
        ("transport_limits", HostEventLimits, "context"),
        ("capture_limits", HostCaptureLimits, "context"),
        ("native_config", NativeSettings, "context"),
        ("comparison_config", ComparisonSettings, "context"),
    ):
        classes.extend(
            FieldClassification.model_validate(
                {
                    "field": f"{label}.{name}",
                    "classification": category,
                }
            )
            for name in model.model_fields
        )
    return tuple(classes)


def compare_cell(name: str, left: Scalar, right: Scalar, bound: float = 0.0) -> FieldComparison:
    passed = left == right
    if left is not None and right is not None and bound:
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            passed = abs(left - right) <= bound
        elif name.endswith("measured_at") and isinstance(left, str) and isinstance(right, str):
            passed = (
                abs((datetime.fromisoformat(left) - datetime.fromisoformat(right)).total_seconds())
                <= bound
            )
    return FieldComparison(
        field=name,
        classification="unchanged",
        reference=left,
        native=right,
        absolute_bound=bound,
        passed=passed,
    )


def verify_result(
    workspace: Path,
    name: str,
    session: EvidenceSession,
    *,
    previous_plan: HostWritePlan | None = None,
) -> HostResultBody:
    native, _, _ = settings()
    event = read_model(resolve(workspace, name), HostEvent, native.limits.max_result_bytes)
    if not isinstance(event.body, HostResultBody) or event.reply_to is None:
        raise ValueError("required native host result is absent")
    if any(
        getattr(event, key) != getattr(session.host_manifest, key)
        for key in ("run_id", "attempt", "job", "shard", "session_id")
    ):
        raise ValueError("native result belongs to another session")
    root = session.host_manifest.event_root
    command = read_model(
        resolve(workspace, f"{root}/commands/{event.reply_to}.json"),
        HostEvent,
        native.limits.max_command_bytes,
    )
    if (
        not isinstance(command.body, HostCommandBody)
        or command.kind not in {"host.probe", "host.clock"}
        or command.session_id != event.session_id
        or command.emitter_id != session.host_manifest.operator_emitter_id
        or event.emitter_id != session.host_manifest.monitor_emitter_id
        or event.sequence != command.sequence
        or command.body.target != session.host_manifest.cpu_target
        or command.body.controls != session.host_manifest.controls
    ):
        raise ValueError("native host result contradicts its retained triggering command")
    plan = read_model(
        resolve(workspace, f"{root}/writes/{event.reply_to}.plan.json"),
        HostWritePlan,
        native.limits.max_result_bytes,
    )
    completion = read_model(
        resolve(workspace, f"{root}/writes/{event.reply_to}.completed-1.json"),
        HostWriteCompletion,
        native.limits.max_result_bytes,
    )
    if plan.target_root != session.roots.native:
        raise ValueError("native writer evidence names a foreign root")
    if plan.event_id != command.event_id or event.body.completion_event_ids != (
        completion.event_id,
    ):
        raise ValueError("native result lacks exact event/completion linkage")
    expected_identity = HostWriterIdentity(
        run_id=session.manifest.run_id,
        attempt=session.manifest.attempt,
        job=session.manifest.job,
        shard=session.manifest.shard,
        producer="telemetry.silicon",
        git_sha=session.manifest.git_sha,
    )
    verified = verify_host_output(
        plan,
        completion,
        workspace_root=workspace,
        target_root=session.roots.native,
        publication_identity=expected_identity,
        limits=native.verification_limits,
        previous_plan=previous_plan,
    )
    if not verified.complete or len(verified.files) != 1:
        raise ValueError("required native completion evidence is absent")
    stored = verified.files[0]
    if (
        stored.rows[0].model_dump(include=set(CorrectedHostFingerprintRow.model_fields))
        != event.body.row.model_dump()
    ):
        raise ValueError("native event and the same stored bytes disagree")
    path = resolve(workspace, f"{session.roots.native}/{stored.relative_path}")
    before = file_evidence(workspace, path, native.verification_limits.max_file_bytes)
    shared = load_stored([path], model=HostFingerprintRow)
    if len(shared) != 1 or shared[0].row != event.body.row:
        raise ValueError("shared reader changed the corrected native host row")
    if before != file_evidence(workspace, path, native.verification_limits.max_file_bytes):
        raise ValueError("comparison modified native bytes")
    return event.body


def compare(
    workspace: Path,
    *,
    probe: str,
    clock: str,
    memory_profiling: bool | None = None,
) -> HostEvidenceReport:
    if platform.system() != "Linux":
        raise ValueError("live Linux evidence cannot be certified from another operating system")
    comparison_utc = datetime.now(UTC)
    native, config, digest = settings()
    controls = live_controls(native, config, memory_profiling)
    workspace = isolated_workspace(workspace)
    session = read_model(
        workspace / "session.json", EvidenceSession, native.limits.max_result_bytes
    )
    for filename, manifest in (
        ("manifest.json", session.manifest),
        ("host-manifest.json", session.host_manifest),
    ):
        if (
            read_model(workspace / filename, HostSessionManifest, native.limits.max_manifest_bytes)
            != manifest
        ):
            raise ValueError("retained manifest differs from its frozen session declaration")
    effective = read_model(
        workspace / "native-config.json", NativeSettings, native.limits.max_manifest_bytes
    )
    expected_native = NativeSettings.model_validate(
        {
            **native.model_dump(),
            "controls": controls,
        }
    )
    if (
        effective != expected_native
        or session.manifest.limits != native.limits
        or session.manifest.capture_limits != native.capture_limits
    ):
        raise ValueError("native limits or effective config differ from the committed declaration")
    if session.config_sha256 != digest or session.field_classes != field_classes():
        raise ValueError("comparison config or field classification changed after calibration")
    if (
        session.manifest.controls != controls
        or len(session.manifest.workers) != 1
        or session.manifest.workers[0].server is not None
        or session.manifest.cpu_target_role != "python_worker"
        or len(session.manifest.windows) != config.paired_runs * 2
    ):
        raise ValueError("live controls or selected workload topology differ from the declaration")
    if len(session.calibration) != config.calibration_runs or session.bounds != freeze_bounds(
        session.calibration, config
    ):
        raise ValueError("numeric bounds were not frozen from the pre-Rust references")
    validate_roots(
        workspace, session.roots, session.manifest.event_root, session.host_manifest.event_root
    )
    gates = validate_gates(workspace, config)
    build = read_model(
        workspace / "compile.json", CommandMeasurement, native.limits.max_result_bytes
    )
    if build.git_sha != session.manifest.git_sha or "rustc 1.95.0" not in build.rustc:
        raise ValueError("build revision or pinned toolchain differs from the session")
    executable = read_bytes(
        ROOT / "backend/var/rust-host-telemetry/release/idhazh-host-telemetry",
        config.max_artifact_bytes,
    )
    if (
        build.executable_bytes != len(executable)
        or build.executable_sha256 != hashlib.sha256(executable).hexdigest()
    ):
        raise ValueError("measured build differs from the actual native executable")
    if build.command != (
        "cargo",
        "build",
        "--locked",
        "--offline",
        "--release",
        "--bin",
        "idhazh-host-telemetry",
    ):
        raise ValueError("compile evidence did not build the intended pinned crate")
    original = artifact_inventory(workspace, config)
    probe_body, final = verify_host_chain(workspace, probe, clock, session)
    if final.cpu != probe_body.cpu:
        raise ValueError("clock recaptured CPU facts")
    if final.cpu.target != session.manifest.cpu_target:
        raise ValueError("live comparison did not observe the same selected worker")
    pair_evidence = read_model(
        workspace / "paired.json",
        PairedEvidence,
        native.limits.max_result_bytes,
    )
    paired = pair_evidence.rows
    resource_ids = resource_chain(workspace, session)
    if len(paired) != config.paired_runs * 2:
        raise ValueError("required paired runs are absent")
    all_runs = (*session.calibration, session.plain, *paired)
    if tuple(row.sequence for row in all_runs) != tuple(range(1, len(all_runs) + 1)):
        raise ValueError("workload evidence is missing or reordered")
    reference_coverage(workspace, all_runs, config)
    if session.plain.mode != "native_only" or any(
        row.mode != ("reference" if index % 2 == 0 else "native_only")
        for index, row in enumerate(paired)
    ):
        raise ValueError("paired instrumentation modes differ from the predeclared sequence")
    if any(
        row.target != session.manifest.cpu_target
        or row.digest != session.plain.digest
        or row.iterations != config.workload_iterations
        or row.wall_seconds < config.workload_min_seconds
        for row in all_runs
    ):
        raise ValueError("workload inputs, digest or actual process identity changed")
    expected_writer = WriterIdentity(
        run_id=session.manifest.run_id,
        attempt=session.manifest.attempt,
        job=session.manifest.job,
        shard=session.manifest.shard,
        producer="telemetry.silicon",
        git_sha=session.manifest.git_sha,
    )
    for row in all_runs:
        if row.mode == "native_only":
            if row.samples or row.population or row.reference_files or row.host or row.cells:
                raise ValueError("native-only runs must not manufacture Python instrumentation")
            continue
        if row.host is None or row.cells is None or not row.samples or not row.reference_files:
            raise ValueError("required persisted Python reference evidence is absent")
        if row.target not in row.population:
            raise ValueError("selected worker is absent from the actual reference population")
        for name in row.reference_files:
            path = resolve(workspace, name)
            if not path.is_relative_to(resolve(workspace, session.roots.reference)):
                raise ValueError("Python writer evidence names a foreign root")
            raw = read_bytes(path, native.verification_limits.max_file_bytes)
            if raw.startswith(b"PAR1"):
                raise ValueError("the bounded Python reference must remain plain JSON lines")
            stored = load_stored([path], model=HostFingerprintRow)
            if len(stored) != 1 or stored[0].row != row.host:
                raise ValueError("persisted Python reference differs from its recorded host row")
            if read_envelope(path).identity != expected_writer:
                raise ValueError("Python reference writer identity differs from the session")
    bounds = {value.field: value.absolute for value in session.bounds}
    comparisons: list[FieldComparison] = []
    reference = session.calibration[-1].host
    if reference is None:
        raise ValueError("Python reference host evidence is absent")
    for field in CorrectedHostFingerprintRow.model_fields:
        actual = getattr(final.row, field)
        if field in CORRECTED_FIELDS:
            passed = any(CORRECTED_GATE in case for case in gates.names)
            if field == "fingerprint":
                passed = passed and actual == fingerprint_v2(final.row)
            elif field == "fingerprint_version":
                passed = passed and actual == 2
            elif field == "cpu_logical_processors":
                passed = passed and actual == len(final.cpu.online_cpu_ids)
            elif field == "cpu_target_measured_at":
                passed = passed and actual is not None
            comparisons.append(
                FieldComparison(
                    field=f"host.{field}",
                    classification="corrected",
                    reference=f"{CORRECTED_GATE}; independent declared bytes and typed diagnostics",
                    native=actual,
                    absolute_bound=0.0,
                    passed=passed,
                )
            )
        elif field in CONTEXT_FIELDS:
            comparisons.append(
                FieldComparison(
                    field=f"host.{field}",
                    classification="context",
                    reference=getattr(session.manifest, field),
                    native=actual,
                    absolute_bound=0.0,
                    passed=actual == getattr(session.manifest, field),
                )
            )
        else:
            expected = getattr(reference, field)
            if field == "job_seconds":
                start = datetime.fromisoformat(
                    read_bytes(
                        workspace / "inputs/start.txt",
                        native.capture_limits.max_log_bytes,
                    )
                    .decode()
                    .strip()
                )
                expected = int((comparison_utc - start).total_seconds())
            comparisons.append(
                compare_cell(f"host.{field}", expected, actual, bounds.get(field, 0.0))
            )
    windows: list[WindowResultBody] = []
    for index, row in enumerate(paired):
        event = read_model(
            workspace / f"observed/{2 + index * 2}.json", HostEvent, native.limits.max_result_bytes
        )
        if not isinstance(event.body, WindowResultBody) or event.body.status != "complete":
            raise ValueError("live window is missing or incomplete")
        if (
            event.body.target != row.target
            or event.body.window_id != session.manifest.windows[index].window_id
        ):
            raise ValueError("live window identity differs from the selected worker")
        windows.append(event.body)
        if index % 2 == 0:
            if row.cells is None:
                raise ValueError("paired reference window evidence is absent")
            for field in HostWindowCells.model_fields:
                if (
                    not controls.memory_profiling_enabled
                    and WINDOW_CELL_SOURCES[field] in MEMORY_SOURCES
                ):
                    comparisons.append(
                        compare_cell(
                            f"window.{index}.{field}",
                            None,
                            getattr(event.body.cells, field),
                            0.0,
                        )
                    )
                    continue
                comparisons.append(
                    compare_cell(
                        f"window.{index}.{field}",
                        getattr(row.cells, field),
                        getattr(event.body.cells, field),
                        bounds.get(field, 0.0),
                    )
                )
    drained = read_model(workspace / "drained.json", HostEvent, native.limits.max_result_bytes)
    if drained.kind != "monitor.stopped":
        raise ValueError("required native drain evidence is absent")
    if controls.memory_profiling_enabled:
        sample_count, coverage = sample_coverage(workspace, tuple(windows), config)
        population: set[int] = set().union(
            *(window.python_pids for index, window in enumerate(coverage) if index % 2)
        )
    else:
        artifact_root = resolve(workspace, session.roots.native_artifacts)
        if artifact_root.exists():
            raise ValueError("memory-off session created native memory artifacts")
        sample_count, coverage, population = 0, (), set()
    reference_population = {p.pid for row in paired for p in row.population}
    if controls.memory_profiling_enabled and (
        session.manifest.cpu_target is None or session.manifest.cpu_target.pid not in population
    ):
        raise ValueError(
            "the actual selected Python worker is absent from native population evidence"
        )
    startup = read_model(
        workspace / "startup.json", MonitorMeasurement, native.limits.max_result_bytes
    )
    monitor = read_model(
        workspace / "monitor-cost.json", MonitorMeasurement, native.limits.max_result_bytes
    )
    if startup.startup_seconds is None or startup.target != monitor.target:
        raise ValueError("monitor startup or process-cost identity evidence is absent")
    if controls.memory_profiling_enabled != (
        startup.rss_bytes is not None and monitor.rss_bytes is not None
    ):
        raise ValueError("monitor RSS evidence contradicts the resolved memory control")
    if monitor.target.pid in population:
        raise ValueError("the Rust monitor must not be counted as Python")
    ack = pair_evidence.ack_seconds
    if len(ack) != 1 + len(paired) * 2:
        raise ValueError("required event ACK latency evidence is absent")
    report = HostEvidenceReport(
        version=EVIDENCE_VERSION,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        git_sha=session.manifest.git_sha,
        platform="linux",
        runner=os.environ.get("RUNNER_NAME", "unknown"),
        toolchain=build.rustc,
        config_sha256=digest,
        session=session,
        compile=build,
        startup_seconds=startup.startup_seconds,
        monitor_cpu_seconds=monitor.cpu_seconds - startup.cpu_seconds,
        monitor_rss_bytes=monitor.rss_bytes,
        ack_seconds=ack,
        paired=paired,
        resource_event_ids=resource_ids,
        native_population=tuple(sorted(population)),
        population_reference_only=tuple(sorted(reference_population - population)),
        population_native_only=tuple(sorted(population - reference_population)),
        native_sample_count=sample_count,
        window_sample_coverage=coverage,
        comparisons=tuple(comparisons),
        files=original,
        gates=gates,
        candidate_reader="idhazh.telemetry.host_output_verify.verify_host_output",
        shared_reader="expected_rejection_before_reader_migration",
        correctness="passed" if all(row.passed for row in comparisons) else "failed",
    )
    if original != artifact_inventory(workspace, config):
        raise ValueError("read-only verification changed its input files")
    write_document(workspace / "report.json", report)
    return report


def verify_host_chain(
    workspace: Path,
    probe: str,
    clock: str,
    session: EvidenceSession,
) -> tuple[HostResultBody, HostResultBody]:
    events = tuple(
        read_model(
            resolve(workspace, name), HostEvent, session.host_manifest.limits.max_result_bytes
        )
        for name in (probe, clock)
    )
    commands = tuple(
        read_model(workspace / name, HostEvent, session.host_manifest.limits.max_command_bytes)
        for name in ("probe.json", "clock.json")
    )
    for result, command in zip(events, commands, strict=True):
        retained = read_model(
            resolve(
                workspace, f"{session.host_manifest.event_root}/commands/{command.event_id}.json"
            ),
            HostEvent,
            session.host_manifest.limits.max_command_bytes,
        )
        if result.reply_to != command.event_id or retained != command:
            raise ValueError("host result names another declared triggering command")
    first, last = commands
    if (
        first.kind != "host.probe"
        or last.kind != "host.clock"
        or first.sequence >= last.sequence
        or not isinstance(first.body, HostCommandBody)
        or not isinstance(last.body, HostCommandBody)
        or first.body.previous_result_id is not None
        or last.body.previous_result_id != events[0].event_id
    ):
        raise ValueError("probe-to-clock predecessor or independent ordering evidence differs")
    probe_result = verify_result(workspace, probe, session)
    probe_plan = read_model(
        resolve(workspace, f"{session.host_manifest.event_root}/writes/{first.event_id}.plan.json"),
        HostWritePlan,
        session.host_manifest.limits.max_result_bytes,
    )
    return probe_result, verify_result(workspace, clock, session, previous_plan=probe_plan)
