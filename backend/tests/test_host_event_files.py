"""Do real named files enforce immutable bounded host-session exchanges and recovery?"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import pytest
from conftest import FIXTURES_DIR
from contracts.test_host_events import manifest_data, message, result_body, window_body
from pydantic import ValidationError

from idhazh.contracts.file_envelope import Format
from idhazh.contracts.host_events import (
    CaptureSource,
    CpuDiagnostics,
    HostEvent,
    HostResultBody,
    HostSessionManifest,
    ProtocolFaultCode,
    SourceCoverage,
    UnavailableReason,
    WriteCompletedBody,
)
from idhazh.contracts.host_output import (
    CandidateFileEnvelope,
    CorrectedHostFingerprintRow,
    HostPlannedFile,
    HostStoredRow,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
    canonical_host_rows,
    host_file_id,
    host_unit_id,
)
from idhazh.ledger import json_lines
from idhazh.telemetry import host_event_files
from idhazh.telemetry.host_event_files import (
    HostEventFiles,
    HostProtocolError,
    event_bytes,
)

pytestmark = pytest.mark.contract


def store(tmp_path: Path, **limits: int) -> HostEventFiles:
    data = manifest_data()
    data["limits"].update(limits)
    session = HostSessionManifest.model_validate(data)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(session.model_dump_json().encode() + b"\n")
    return HostEventFiles.open(tmp_path, manifest_path, limits=session.limits)


def cpu_evidence(online_ids: tuple[int, ...] = (0, 2)) -> CpuDiagnostics:
    sources = (
        CaptureSource.ONLINE,
        CaptureSource.TOPOLOGY,
        CaptureSource.CPUINFO,
        CaptureSource.CPUFREQ,
        CaptureSource.AFFINITY,
        CaptureSource.CPUSET,
        CaptureSource.QUOTA,
    )
    return CpuDiagnostics(
        online_cpu_ids=online_ids,
        sources=tuple(
            SourceCoverage(
                source=source,
                status="complete"
                if source is CaptureSource.ONLINE and online_ids
                else "unavailable",
                expected=len(online_ids),
                observed=len(online_ids) if source is CaptureSource.ONLINE else 0,
                reason=None
                if source is CaptureSource.ONLINE and online_ids
                else UnavailableReason.MISSING,
            )
            for source in sources
        ),
    )


def ready(files: HostEventFiles) -> HostEvent:
    session = files.manifest
    event = message(
        session, "monitor.ready", {"boot_id": session.boot_id, "supported_version": session.version}
    )
    files.publish(event, now_ms=0)
    return event


def register(
    files: HostEventFiles, *, index: int = 0, monitor_sequence: int = 2
) -> tuple[HostEvent, HostEvent]:
    session = files.manifest
    worker = session.workers[index]
    body = {
        "target": worker.target,
        "server": worker.server,
        "memory_profiling_enabled": session.controls.memory_profiling_enabled,
    }
    command = message(session, "worker.register", body, emitter=worker.emitter_id)
    ack = message(
        session, "worker.registered", body, sequence=monitor_sequence, reply_to=command.event_id
    )
    files.publish(command, now_ms=1)
    files.publish(ack, now_ms=1)
    return command, ack


def begin(
    files: HostEventFiles, *, index: int = 0, monitor_sequence: int = 3
) -> tuple[HostEvent, HostEvent]:
    session = files.manifest
    body = window_body(session, index)
    command = message(
        session, "window.begin", body, emitter=session.windows[index].emitter_id, sequence=2
    )
    ack = message(
        session,
        "window.begun",
        {**body, "captured_at": "2026-10-10T12:00:00Z"},
        sequence=monitor_sequence,
        reply_to=command.event_id,
    )
    files.publish(command, now_ms=2)
    files.publish(ack, now_ms=2)
    return command, ack


def generated_plan(
    files: HostEventFiles,
    command: HostEvent,
    *,
    clock: int = 1791633601000,
    day: str | None = None,
    **row_cells: Any,
) -> HostWritePlan:
    session = files.manifest
    day = day or session.date
    identity = HostWriterIdentity(
        run_id=session.run_id,
        attempt=session.attempt,
        job=session.job,
        shard=session.shard,
        producer="telemetry.silicon",
        git_sha=session.git_sha,
    )
    unit = host_unit_id(covers=day, identity=identity)
    row = HostStoredRow.model_validate(
        {
            "date": day,
            "run_id": session.run_id,
            "job": session.job,
            "shard": session.shard,
            "ledger": "host-fingerprint",
            "covers": day,
            "attempt": session.attempt,
            "unit_id": str(unit),
            "measured_at": "2026-10-10T12:00:00Z",
            "cpu_logical_processors": 2,
            **row_cells,
        }
    )
    file_id = host_file_id(unit=unit, attempt=session.attempt, written_at_ms=clock)
    envelope = CandidateFileEnvelope.model_validate(
        {
            "row_schema_version": row.version,
            "tier": "raw",
            "ledger": "host-fingerprint",
            "covers": day,
            "written_at_ms": clock,
            "identity": identity,
            "unit_id": unit,
            "file_id": file_id,
            "content_sha256": hashlib.sha256(canonical_host_rows((row,))).hexdigest(),
            "writer": "idhazh.ledger.json_lines",
            "writer_version": json_lines.engine_version(),
            "compression": "none",
        }
    )
    planned = HostPlannedFile(
        envelope=envelope,
        format=Format.JSON,
        relative_path=f"raw/host-fingerprint/{day.replace('-', '/')}/{file_id}.json",
        rows=(row,),
    )
    return HostWritePlan(
        version="2026-10-10",
        event_id=command.event_id,
        target_root=session.output_roots[0],
        publication_identity=identity,
        files=(planned,),
    )


def host_exchange(files: HostEventFiles) -> tuple[HostEvent, HostWritePlan, HostEvent]:
    session = files.manifest
    command = message(
        session,
        "host.probe",
        {"controls": session.controls, "input_names": ("cpuinfo",), "target": session.cpu_target},
        emitter=session.operator_emitter_id,
    )
    plan = generated_plan(files, command)
    files.publish(command, now_ms=1)
    files.publish(
        message(session, "host.write.plan", {"plan": plan}, sequence=2, reply_to=command.event_id),
        now_ms=1,
    )
    planned = plan.files[0]
    output = files.project_root / plan.target_root / planned.relative_path
    output.parent.mkdir(parents=True)
    # Real Python-container fixture bytes, not a claim that a Rust writer exists.
    output.write_bytes(
        json_lines.render(
            (row.model_dump(mode="json") for row in planned.rows),
            envelope=planned.envelope.as_metadata(),
        )
    )
    completion = HostWriteCompletion.model_validate(
        {
            "event_id": command.event_id,
            "receipt": {
                "identity": plan.publication_identity,
                "writes": {
                    f"{plan.target_root}/{planned.relative_path}": hashlib.sha256(
                        output.read_bytes()
                    ).hexdigest()
                },
            },
        }
    )
    completed = message(
        session,
        "host.write.completed",
        {"completion": completion},
        sequence=3,
        reply_to=command.event_id,
    )
    files.publish(completed, now_ms=1)
    row = CorrectedHostFingerprintRow.model_validate(
        {name: getattr(planned.rows[0], name) for name in CorrectedHostFingerprintRow.model_fields}
    )
    result = message(
        session,
        "host.result",
        HostResultBody(
            row=row,
            cpu=cpu_evidence(),
            completion_event_ids=(completed.event_id,),
        ),
        sequence=4,
        reply_to=command.event_id,
    )
    files.publish(result, now_ms=1)
    return command, plan, result


def test_generated_files_replay_the_same_registration_ack(tmp_path: Path) -> None:
    files = store(tmp_path)
    startup = ready(files)
    command, ack = register(files)
    assert files.read_event(command.event_id, "inbox", now_ms=2).replies == (ack,)
    assert files.publish(command, now_ms=3).replayed
    reader = HostEventFiles(tmp_path, files.manifest)
    named: list[tuple[HostEvent, Literal["inbox", "results"]]] = [
        (startup, "results"),
        (command, "inbox"),
        (ack, "results"),
    ]
    for event, direction in named:
        assert reader.read_event(event.event_id, direction, now_ms=4).event == event
        assert files.event_path(event.event_id, direction).read_bytes() == event_bytes(event)
    assert reader.read_event(command.event_id, "inbox", now_ms=5).replies == (ack,)


def test_overlapping_workers_do_not_share_window_results(tmp_path: Path) -> None:
    files = store(tmp_path)
    ready(files)
    register(files)
    register(files, index=1, monitor_sequence=3)
    begin(files, monitor_sequence=4)
    begin(files, index=1, monitor_sequence=5)
    session = files.manifest
    for index in (1, 0):
        command = message(
            session,
            "window.end",
            window_body(session, index),
            emitter=session.windows[index].emitter_id,
            sequence=3,
        )
        files.publish(command, now_ms=3 + 3 * (1 - index))
        result = message(
            session,
            "window.result",
            result_body(session, index=index),
            sequence=6 + (1 - index),
            reply_to=command.event_id,
        )
        files.publish(result, now_ms=4 + 3 * (1 - index))
        assert files.read_event(command.event_id, "inbox", now_ms=5 + 3 * (1 - index)).replies == (
            result,
        )


@pytest.mark.parametrize(
    "fault",
    [
        "end_before_begin",
        "work_before_ack",
        "wrong_target",
        "wrong_item",
        "wrong_worker",
        "same_sequence",
        "reused_id",
        "wrong_session",
        "wrong_attempt",
        "wrong_boot",
    ],
)
def test_protocol_faults_never_publish_or_advance_state(tmp_path: Path, fault: str) -> None:
    files = store(tmp_path)
    startup = ready(files)
    command, ack = register(files)
    session = files.manifest
    body = window_body(session)
    event = message(session, "window.begin", body, emitter="worker-0", sequence=2)
    changes: dict[str, Any] = {}
    if fault == "end_before_begin":
        changes["kind"] = "window.end"
    elif fault == "work_before_ack":
        files = HostEventFiles(tmp_path, session)
        files.bookkeeping.accept(startup, now_ms=0)
        files.bookkeeping.accept(command, now_ms=1)
    elif fault == "wrong_target":
        changes["body"] = {**body, "target": {"pid": 200, "start_ticks": 901}}
    elif fault == "wrong_item":
        changes["body"] = {**body, "item_id": "another-99"}
    elif fault == "wrong_worker":
        changes["emitter_id"] = "worker-1"
    elif fault == "same_sequence":
        changes["sequence"] = 1
    elif fault == "reused_id":
        changes["event_id"] = command.event_id
    elif fault == "wrong_session":
        changes["session_id"] = uuid4()
    elif fault == "wrong_attempt":
        changes["attempt"] = 2
    else:
        event = message(
            session,
            "monitor.ready",
            {"boot_id": uuid4(), "supported_version": session.version},
            sequence=3,
        )
    invalid = HostEvent.model_validate(event.model_dump() | changes)
    before = files.bookkeeping.total_events
    with pytest.raises(HostProtocolError):
        files.publish(invalid, now_ms=2)
    assert files.bookkeeping.total_events == before
    assert (
        not files.event_path(
            invalid.event_id, "inbox" if invalid.kind != "monitor.ready" else "results"
        ).exists()
        or invalid.event_id == command.event_id
    )
    assert ack.event_id != invalid.event_id


def test_concurrent_identical_atomic_publication_has_one_immutable_file(tmp_path: Path) -> None:
    files = store(tmp_path)
    session = files.manifest
    startup = message(
        session, "monitor.ready", {"boot_id": session.boot_id, "supported_version": session.version}
    )
    writers = [HostEventFiles(tmp_path, session), HostEventFiles(tmp_path, session)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer.publish, startup, now_ms=0) for writer in writers]
        assert all(future.result().event == startup for future in futures)
    assert files.event_path(startup.event_id, "results").read_bytes() == event_bytes(startup)
    assert list(files.event_path(startup.event_id, "results").parent.iterdir()) == [
        files.event_path(startup.event_id, "results")
    ]


def test_existing_changed_bytes_are_not_overwritten(tmp_path: Path) -> None:
    files = store(tmp_path)
    startup = ready(files)
    path = files.event_path(startup.event_id, "results")
    changed = event_bytes(startup).replace(b'"monitor"', b'"another"')
    path.write_bytes(changed)
    with pytest.raises(HostProtocolError):
        files.publish(startup, now_ms=1)
    assert path.read_bytes() == changed


@pytest.mark.parametrize(
    "limit", ["max_files", "max_session_events", "max_session_bytes", "max_command_bytes"]
)
def test_capacity_exhaustion_keeps_old_evidence_and_refuses_new_work(
    tmp_path: Path, limit: str
) -> None:
    limits = (
        {limit: 1} if limit in ("max_files", "max_session_events") else {"max_command_bytes": 64}
    )
    if limit == "max_session_bytes":
        limits = {"max_command_bytes": 700, "max_result_bytes": 700, "max_session_bytes": 700}
    files = store(tmp_path, **limits)
    startup = ready(files)
    worker = files.manifest.workers[0]
    command = message(
        files.manifest,
        "worker.register",
        {"target": worker.target, "server": worker.server},
        emitter=worker.emitter_id,
    )
    with pytest.raises(HostProtocolError) as fault:
        files.publish(command, now_ms=1)
    assert fault.value.code is ProtocolFaultCode.BOUNDS
    assert files.event_path(startup.event_id, "results").exists()
    assert not files.event_path(command.event_id, "inbox").exists()


def test_retirement_waits_for_consumption_and_last_retry_then_blocks_id_reuse(
    tmp_path: Path,
) -> None:
    files = store(tmp_path)
    ready(files)
    command, ack = register(files)
    with pytest.raises(HostProtocolError, match="consumed"):
        files.retire(command.event_id, now_ms=10000)
    files.bookkeeping.mark_consumed(command.event_id)
    files.bookkeeping.mark_consumed(ack.event_id)
    with pytest.raises(HostProtocolError, match="elapsed"):
        files.retire(command.event_id, now_ms=100)
    files.publish(command, now_ms=4999)
    with pytest.raises(HostProtocolError, match="elapsed"):
        files.retire(command.event_id, now_ms=5001)
    assert files.retire(command.event_id, now_ms=10000) == (command.event_id, ack.event_id)
    assert not files.event_path(command.event_id, "inbox").exists()
    assert not files.event_path(ack.event_id, "results").exists()
    with pytest.raises(HostProtocolError) as fault:
        files.publish(command, now_ms=10001)
    assert fault.value.code is ProtocolFaultCode.RETIRED


def test_unfinished_command_and_individual_reply_cannot_be_retired(tmp_path: Path) -> None:
    files = store(tmp_path)
    ready(files)
    _, ack = register(files)
    command, _ = begin(files)
    end = message(
        files.manifest, "window.end", window_body(files.manifest), emitter="worker-0", sequence=3
    )
    files.publish(end, now_ms=3)
    files.bookkeeping.mark_consumed(end.event_id)
    with pytest.raises(HostProtocolError, match="unfinished"):
        files.retire(end.event_id, now_ms=10000)
    with pytest.raises(HostProtocolError, match="triggering"):
        files.retire(ack.event_id, now_ms=10000)
    assert command.event_id != end.event_id


@pytest.mark.parametrize("limit", ["max_reads", "max_read_bytes"])
def test_read_budget_covers_retries_and_named_inputs(tmp_path: Path, limit: str) -> None:
    data = manifest_data()
    data["limits"][limit] = 1 if limit == "max_reads" else 65536
    session = HostSessionManifest.model_validate(data)
    files = HostEventFiles(tmp_path, session)
    captures = tmp_path / "captures"
    captures.mkdir()
    path = captures / "cpuinfo.txt"
    path.write_bytes(b"data\n" if limit == "max_reads" else b"x" * 65536)
    files.read_input("cpuinfo")
    with pytest.raises(HostProtocolError, match="budget"):
        files.read_input("cpuinfo")
    assert path.exists()


@pytest.mark.parametrize(
    "bad",
    [
        b"{}\r\n",
        b"{}",
        b'{"kind":"monitor.ready","kind":"monitor.stop"}\n',
        b"[]\n",
        b"\xff\n",
        b'{"version":NaN}\n',
    ],
)
def test_malformed_real_files_are_refused(tmp_path: Path, bad: bytes) -> None:
    files = store(tmp_path)
    event_id = uuid4()
    path = files.event_path(event_id, "results")
    path.parent.mkdir(parents=True)
    path.write_bytes(bad)
    with pytest.raises((HostProtocolError, ValidationError)):
        files.read_event(event_id, "results", now_ms=0)
    assert files.bookkeeping.total_events == 0


def test_named_file_id_and_direction_are_verified(tmp_path: Path) -> None:
    files = store(tmp_path)
    startup = ready(files)
    other = uuid4()
    path = files.event_path(other, "results")
    path.write_bytes(event_bytes(startup))
    with pytest.raises(HostProtocolError, match="contradicts"):
        files.read_event(other, "results", now_ms=1)
    inbox = files.event_path(startup.event_id, "inbox")
    inbox.parent.mkdir()
    inbox.write_bytes(event_bytes(startup))
    with pytest.raises(HostProtocolError):
        files.read_event(startup.event_id, "inbox", now_ms=1)
    with pytest.raises(HostProtocolError, match="not named"):
        files.read_input("undeclared")


def test_manifest_byte_cap_and_effective_limits_are_checked_before_use(tmp_path: Path) -> None:
    session = HostSessionManifest.model_validate(manifest_data())
    path = tmp_path / "manifest.json"
    path.write_bytes(b"x" * (session.limits.max_manifest_bytes + 1))
    with pytest.raises(HostProtocolError, match="bounded"):
        HostEventFiles.open(tmp_path, path, limits=session.limits)
    path.write_bytes((FIXTURES_DIR / "host-events" / "manifest.json").read_bytes())
    changed = session.limits.model_dump() | {"max_reads": 1}
    with pytest.raises(HostProtocolError, match="effective config"):
        HostEventFiles.open(tmp_path, path, limits=type(session.limits).model_validate(changed))


def test_linked_ordinary_capture_is_not_read(tmp_path: Path) -> None:
    files = store(tmp_path)
    other = tmp_path / "outside-captures"
    other.mkdir()
    (other / "cpuinfo.txt").write_bytes(b"secret\n")
    link = tmp_path / "captures"
    try:
        link.symlink_to(other, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"host cannot create a symlink: {error}")
    with pytest.raises(HostProtocolError, match="links"):
        files.read_input("cpuinfo")


def test_stop_aborts_unresolved_windows_before_stopped_ack(tmp_path: Path) -> None:
    files = store(tmp_path)
    ready(files)
    register(files)
    begin(files)
    session = files.manifest
    stop = message(
        session, "monitor.stop", {"reason": "cancelled"}, emitter=session.operator_emitter_id
    )
    files.publish(stop, now_ms=3)
    stopped = message(
        session,
        "monitor.stopped",
        {"drained": True, "aborted_window_ids": (session.windows[0].window_id,)},
        sequence=5,
        reply_to=stop.event_id,
    )
    with pytest.raises(HostProtocolError, match="unresolved"):
        files.publish(stopped, now_ms=4)
    abort = message(
        session,
        "window.result",
        result_body(session, abort=True),
        sequence=4,
        reply_to=stop.event_id,
    )
    files.publish(abort, now_ms=4)
    files.publish(stopped, now_ms=5)
    assert files.read_event(stop.event_id, "inbox", now_ms=6).replies == (abort, stopped)


def test_host_plan_completion_and_result_refer_to_real_written_bytes(tmp_path: Path) -> None:
    files = store(tmp_path)
    ready(files)
    command, plan, result = host_exchange(files)
    replies = files.read_event(command.event_id, "inbox", now_ms=2).replies
    assert [event.kind for event in replies] == [
        "host.write.plan",
        "host.write.completed",
        "host.result",
    ]
    assert isinstance(result.body, HostResultBody)
    assert result.body.row.cpu_logical_processors == 2
    planned = plan.files[0]
    output = tmp_path / plan.target_root / planned.relative_path
    before = output.read_bytes()
    receipt = replies[1].body.completion.receipt  # type: ignore[union-attr]
    assert (
        receipt.writes[f"{plan.target_root}/{planned.relative_path}"]
        == hashlib.sha256(before).hexdigest()
    )
    for event in (command, *replies):
        files.bookkeeping.mark_consumed(event.event_id)
    files.retire(command.event_id, now_ms=10000)
    assert output.read_bytes() == before


def test_forged_host_result_cannot_skip_write_evidence(tmp_path: Path) -> None:
    files = store(tmp_path)
    ready(files)
    command = message(
        files.manifest,
        "host.probe",
        {
            "controls": files.manifest.controls,
            "input_names": (),
            "target": files.manifest.cpu_target,
        },
        emitter="operator",
    )
    files.publish(command, now_ms=1)
    row = CorrectedHostFingerprintRow(
        version="2026-10-10", date=files.manifest.date, run_id=files.manifest.run_id, shard=0
    )
    result = message(
        files.manifest,
        "host.result",
        {
            "row": row,
            "cpu": cpu_evidence(()),
            "completion_event_ids": (uuid4(),),
        },
        sequence=2,
        reply_to=command.event_id,
    )
    with pytest.raises(HostProtocolError, match="completion"):
        files.publish(result, now_ms=2)


def test_transport_imports_only_exchange_contracts_and_reads_no_growing_tree() -> None:
    tree = ast.parse(inspect.getsource(host_event_files))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("idhazh."):
            assert node.module in {"idhazh.contracts.host_events", "idhazh.contracts.host_output"}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"glob", "rglob", "walk", "iterdir", "listdir"}
    assert Path(host_event_files.__file__).is_file()


@pytest.mark.parametrize("bad", [True, "1", 1.0, -1, 1 << 63])
def test_local_monotonic_ticks_are_strict(bad: Any, tmp_path: Path) -> None:
    files = store(tmp_path)
    event = message(
        files.manifest,
        "monitor.ready",
        {"boot_id": files.manifest.boot_id, "supported_version": files.manifest.version},
    )
    with pytest.raises(HostProtocolError):
        files.bookkeeping.accept(event, now_ms=bad)


def publish_completion(
    files: HostEventFiles,
    plan: HostWritePlan,
    *,
    monitor_sequence: int,
    now_ms: int,
    indices: tuple[int, ...] | None = None,
) -> HostEvent:
    writes = {}
    for index in range(len(plan.files)) if indices is None else indices:
        planned = plan.files[index]
        physical = files.project_root / plan.target_root / planned.relative_path
        physical.parent.mkdir(parents=True, exist_ok=True)
        raw = json_lines.render(
            (row.model_dump(mode="json") for row in planned.rows),
            envelope=planned.envelope.as_metadata(),
        )
        if physical.exists():
            assert physical.read_bytes() == raw
        else:
            physical.write_bytes(raw)
        writes[f"{plan.target_root}/{planned.relative_path}"] = hashlib.sha256(
            physical.read_bytes()
        ).hexdigest()
    completion = HostWriteCompletion.model_validate(
        {
            "event_id": plan.event_id,
            "receipt": {"identity": plan.publication_identity, "writes": writes},
        }
    )
    completed = message(
        files.manifest,
        "host.write.completed",
        {"completion": completion},
        sequence=monitor_sequence,
        reply_to=plan.event_id,
    )
    files.publish(completed, now_ms=now_ms)
    return completed


def publish_host_successor(
    files: HostEventFiles,
    command: HostEvent,
    plan: HostWritePlan,
    cpu: CpuDiagnostics,
    *,
    monitor_sequence: int,
    now_ms: int,
) -> HostEvent:
    session = files.manifest
    files.publish(command, now_ms=now_ms)
    files.publish(
        message(
            session,
            "host.write.plan",
            {"plan": plan},
            sequence=monitor_sequence,
            reply_to=command.event_id,
        ),
        now_ms=now_ms,
    )
    completed = publish_completion(
        files, plan, monitor_sequence=monitor_sequence + 1, now_ms=now_ms
    )
    planned = plan.files[0]
    row = CorrectedHostFingerprintRow.model_validate(
        {name: getattr(planned.rows[0], name) for name in CorrectedHostFingerprintRow.model_fields}
    )
    result = message(
        session,
        "host.result",
        HostResultBody(row=row, cpu=cpu, completion_event_ids=(completed.event_id,)),
        sequence=monitor_sequence + 2,
        reply_to=command.event_id,
    )
    files.publish(result, now_ms=now_ms)
    return result


def test_target_then_clock_enrich_the_same_real_unit_without_remeasuring_cpu(
    tmp_path: Path,
) -> None:
    files = store(tmp_path)
    ready(files)
    _, first_plan, first = host_exchange(files)
    register(files, monitor_sequence=5)
    register(files, index=1, monitor_sequence=6)
    session = files.manifest
    target_command = message(
        session,
        "host.target",
        {
            "controls": session.controls,
            "input_names": (),
            "target": session.cpu_target,
            "previous_result_id": first.event_id,
        },
        emitter="operator",
        sequence=2,
    )
    target_cells: dict[str, Any] = {
        "cpu_allowed_processors": 1,
        "cpu_quota_state": "unlimited",
        "cpu_target_measured_at": "2026-10-10T12:00:01Z",
    }
    target_plan = generated_plan(files, target_command, clock=1791633602000, **target_cells)
    original = cpu_evidence()
    target_cpu = CpuDiagnostics(
        online_cpu_ids=original.online_cpu_ids,
        target=session.cpu_target,
        sources=tuple(
            SourceCoverage(source=entry.source, status="complete", expected=1, observed=1)
            if entry.source in {CaptureSource.AFFINITY, CaptureSource.CPUSET, CaptureSource.QUOTA}
            else entry
            for entry in original.sources
        ),
    )
    target = publish_host_successor(
        files, target_command, target_plan, target_cpu, monitor_sequence=7, now_ms=2
    )
    clock_command = message(
        session,
        "host.clock",
        {
            "controls": session.controls,
            "input_names": ("clock",),
            "target": session.cpu_target,
            "previous_result_id": target.event_id,
        },
        emitter="operator",
        sequence=3,
    )
    clock_plan = generated_plan(
        files,
        clock_command,
        clock=1791633603000,
        model_load_ms=50.0,
        job_seconds=1,
        **target_cells,
    )
    clock = publish_host_successor(
        files, clock_command, clock_plan, target_cpu, monitor_sequence=10, now_ms=3
    )
    assert first_plan.files[0].envelope.unit_id == clock_plan.files[0].envelope.unit_id
    assert first_plan.files[0].envelope.file_id != clock_plan.files[0].envelope.file_id
    assert isinstance(clock.body, HostResultBody)
    assert clock.body.row.cpu_target_measured_at == "2026-10-10T12:00:01Z"
    assert clock.body.row.measured_at == "2026-10-10T12:00:00Z"
    assert clock.body.row.job_seconds == 1
    assert clock.body.cpu == target_cpu


def test_skipped_clock_preserves_the_already_completed_probe_files(tmp_path: Path) -> None:
    files = store(tmp_path)
    ready(files)
    _, plan, result = host_exchange(files)
    physical = tmp_path / plan.target_root / plan.files[0].relative_path
    original = physical.read_bytes()
    command = message(
        files.manifest,
        "host.clock",
        {
            "controls": files.manifest.controls,
            "input_names": ("clock",),
            "target": files.manifest.cpu_target,
            "previous_result_id": result.event_id,
        },
        emitter="operator",
        sequence=2,
    )
    files.publish(command, now_ms=2)
    skipped = message(
        files.manifest,
        "instrument.skipped",
        {
            "command_kind": "host.clock",
            "unavailable": ({"source": "clock.log", "reason": "missing"},),
        },
        sequence=5,
        reply_to=command.event_id,
    )
    files.publish(skipped, now_ms=2)
    assert files.read_event(command.event_id, "inbox", now_ms=3).replies == (skipped,)
    assert physical.read_bytes() == original


@pytest.mark.parametrize("opening", [True, False])
def test_shutdown_resolves_an_unacknowledged_open_or_close_command(
    tmp_path: Path, opening: bool
) -> None:
    files = store(tmp_path)
    ready(files)
    register(files)
    session = files.manifest
    body = window_body(session)
    if opening:
        unfinished = message(session, "window.begin", body, emitter="worker-0", sequence=2)
        files.publish(unfinished, now_ms=2)
        monitor_sequence = 3
    else:
        begin(files)
        unfinished = message(session, "window.end", body, emitter="worker-0", sequence=3)
        files.publish(unfinished, now_ms=2)
        monitor_sequence = 4
    stop = message(session, "monitor.stop", {"reason": "cancelled"}, emitter="operator")
    files.publish(stop, now_ms=3)
    failed = result_body(session, abort=True).model_dump()
    if not opening:
        failed["opened_at"] = "2026-10-10T12:00:00Z"
    incomplete = message(
        session,
        "window.result",
        failed,
        sequence=monitor_sequence,
        reply_to=unfinished.event_id,
    )
    files.publish(incomplete, now_ms=3)
    stopped = message(
        session,
        "monitor.stopped",
        {
            "drained": True,
            "aborted_window_ids": (session.windows[0].window_id,),
        },
        sequence=monitor_sequence + 1,
        reply_to=stop.event_id,
    )
    files.publish(stopped, now_ms=4)
    assert files.read_event(unfinished.event_id, "inbox", now_ms=5).replies[-1] == incomplete


def test_pending_event_bound_has_no_silent_drop_and_recovers_after_safe_retirement(
    tmp_path: Path,
) -> None:
    files = store(tmp_path)
    startup = ready(files)
    limit = 4 * 0 + files.manifest.limits.max_concurrent_windows + 8
    events = [startup]
    for sequence in range(2, limit + 1):
        event = message(
            files.manifest,
            "protocol.fault",
            {"code": "limit_exhausted", "related_event_id": None},
            sequence=sequence,
        )
        files.publish(event, now_ms=1)
        events.append(event)
    extra = message(
        files.manifest,
        "protocol.fault",
        {"code": "limit_exhausted", "related_event_id": None},
        sequence=limit + 1,
    )
    with pytest.raises(HostProtocolError) as fault:
        files.publish(extra, now_ms=2)
    assert fault.value.code is ProtocolFaultCode.BOUNDS
    assert all(files.event_path(event.event_id, "results").exists() for event in events)
    files.bookkeeping.mark_consumed(startup.event_id)
    files.retire(startup.event_id, now_ms=10000)
    files.publish(extra, now_ms=10000)
    assert files.bookkeeping.total_events == limit + 1


def test_memory_off_blocks_legacy_artifact_events_but_keeps_cpu_windows(tmp_path: Path) -> None:
    data = manifest_data()
    data["controls"]["memory_profiling_enabled"] = False
    session = HostSessionManifest.model_validate(data)
    files = HostEventFiles(tmp_path, session)
    ready(files)
    register(files)
    begin(files)
    end = message(session, "window.end", window_body(session), emitter="worker-0", sequence=3)
    files.publish(end, now_ms=3)
    complete = message(
        session, "window.result", result_body(session), sequence=4, reply_to=end.event_id
    )
    files.publish(complete, now_ms=3)
    rollcall = message(session, "process.rollcall", {"records": ()}, sequence=5)
    with pytest.raises(HostProtocolError, match="memory off"):
        files.publish(rollcall, now_ms=4)
    assert not files.event_path(rollcall.event_id, "results").exists()


def test_abort_after_ack_returns_and_replays_explicit_incomplete_cells(tmp_path: Path) -> None:
    files = store(tmp_path)
    ready(files)
    register(files)
    begin(files)
    command = message(
        files.manifest,
        "window.abort",
        {**window_body(files.manifest), "reason": "work_failed"},
        emitter="worker-0",
        sequence=3,
    )
    files.publish(command, now_ms=3)
    incomplete = message(
        files.manifest,
        "window.result",
        result_body(files.manifest, abort=True),
        sequence=4,
        reply_to=command.event_id,
    )
    files.publish(incomplete, now_ms=3)
    assert files.read_event(command.event_id, "inbox", now_ms=4).replies == (incomplete,)


def test_unselected_early_probe_resolves_the_first_registered_server_target(tmp_path: Path) -> None:
    data = manifest_data()
    data.update(cpu_target=None, cpu_target_role="unselected")
    session = HostSessionManifest.model_validate(data)
    files = HostEventFiles(tmp_path, session)
    ready(files)
    _, _, first = host_exchange(files)
    assert files.bookkeeping.cpu_target is None
    register(files, monitor_sequence=5)
    assert files.bookkeeping.cpu_target == session.workers[0].server
    command = message(
        session,
        "host.target",
        {
            "controls": session.controls,
            "input_names": (),
            "target": files.bookkeeping.cpu_target,
            "previous_result_id": first.event_id,
        },
        emitter="operator",
        sequence=2,
    )
    files.publish(command, now_ms=2)
    assert session.cpu_target is None


def test_single_shard_cannot_declare_conflicting_model_server_targets() -> None:
    data = manifest_data()
    data["workers"][1]["server"]["start_ticks"] += 1
    with pytest.raises(ValidationError, match="selected model server"):
        HostSessionManifest.model_validate(data)


@pytest.mark.parametrize("order", ["begin_first", "abort_first", "abort_only", "after_stop"])
def test_abort_before_opening_ack_resolves_begin_and_retains_both_responses(
    tmp_path: Path, order: str
) -> None:
    files = store(tmp_path)
    ready(files)
    register(files)
    session = files.manifest
    opening = message(session, "window.begin", window_body(session), emitter="worker-0", sequence=2)
    abort = message(
        session,
        "window.abort",
        {**window_body(session), "reason": "work_failed"},
        emitter="worker-0",
        sequence=3,
    )
    files.publish(opening, now_ms=2)
    files.publish(abort, now_ms=3)
    requests = (opening, abort) if order == "begin_first" else (abort, opening)
    responses = []
    sequence = 3
    for request in requests:
        if request == opening and order in ("abort_only", "after_stop"):
            continue
        response = message(
            session,
            "window.result",
            result_body(session, abort=True),
            sequence=sequence,
            reply_to=request.event_id,
        )
        files.publish(response, now_ms=4)
        responses.append(response)
        sequence += 1
    stop = message(session, "monitor.stop", {"reason": "completed"}, emitter="operator")
    files.publish(stop, now_ms=5)
    stopped = message(
        session,
        "monitor.stopped",
        {"drained": True, "aborted_window_ids": (session.windows[0].window_id,)},
        sequence=sequence,
        reply_to=stop.event_id,
    )
    files.publish(stopped, now_ms=6)
    if order == "after_stop":
        late = message(
            session,
            "window.result",
            result_body(session, abort=True),
            sequence=sequence + 1,
            reply_to=opening.event_id,
        )
        files.publish(late, now_ms=7)
        responses.append(late)
    begin_replies = files.read_event(opening.event_id, "inbox", now_ms=8).replies
    abort_replies = files.read_event(abort.event_id, "inbox", now_ms=8).replies
    assert begin_replies
    assert abort_replies == tuple(response for response in responses if response.reply_to == abort.event_id)
    assert set(begin_replies) | set(abort_replies) == set(responses)
    for response in responses:
        assert files.publish(response, now_ms=9).replayed
        assert files.event_path(response.event_id, "results").read_bytes() == event_bytes(response)
    for event in (opening, abort, *responses):
        files.bookkeeping.mark_consumed(event.event_id)
    retired = set(files.retire(opening.event_id, now_ms=10000))
    if order == "begin_first":
        assert retired == {opening.event_id, responses[0].event_id}
        retired.update(files.retire(abort.event_id, now_ms=10000))
    assert retired == {opening.event_id, abort.event_id, *(response.event_id for response in responses)}
    assert files.read_event(stop.event_id, "inbox", now_ms=10001).replies == (stopped,)


@pytest.mark.parametrize("encoding", ["native", "reordered"])
def test_native_and_noncanonical_utf8_lf_events_keep_original_immutable_bytes(
    tmp_path: Path, encoding: str
) -> None:
    files = store(tmp_path)
    session = files.manifest
    worker = session.workers[0]
    startup = message(
        session, "monitor.ready", {"boot_id": session.boot_id, "supported_version": session.version}
    )
    command = message(
        session,
        "worker.register",
        {"target": worker.target, "server": worker.server},
        emitter=worker.emitter_id,
    )
    ack = message(session, "worker.registered", command.body, sequence=2, reply_to=command.event_id)
    named: list[tuple[HostEvent, Literal["inbox", "results"]]] = [
        (startup, "results"), (command, "inbox"), (ack, "results")
    ]
    accepted_bytes = {}
    for event, direction in named:
        raw = (
            event.model_dump_json().encode("utf-8") + b"\n"
            if encoding == "native"
            else json.dumps(
                dict(reversed(list(event.model_dump(mode="json").items()))),
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8") + b"\n"
        )
        assert raw != event_bytes(event)
        path = files.event_path(event.event_id, direction)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        assert files.read_event(event.event_id, direction, now_ms=0).event == event
        accepted_bytes[event.event_id] = raw
    assert files.bookkeeping.total_bytes == sum(map(len, accepted_bytes.values()))
    assert files.read_event(command.event_id, "inbox", now_ms=1).replies == (ack,)
    path = files.event_path(command.event_id, "inbox")
    path.write_bytes(event_bytes(command))
    with pytest.raises(HostProtocolError) as fault:
        files.read_event(command.event_id, "inbox", now_ms=2)
    assert fault.value.code is ProtocolFaultCode.DUPLICATE
    path.write_bytes(accepted_bytes[command.event_id])
    with pytest.raises(HostProtocolError) as fault:
        files.publish(command, now_ms=2)
    assert fault.value.code is ProtocolFaultCode.DUPLICATE
    for event, direction in named:
        assert files.event_path(event.event_id, direction).read_bytes() == accepted_bytes[event.event_id]
        files.bookkeeping.mark_consumed(event.event_id)
    assert files.retire(command.event_id, now_ms=10000) == (command.event_id, ack.event_id)
    assert files.retire(startup.event_id, now_ms=10000) == (startup.event_id,)
    path.write_bytes(accepted_bytes[command.event_id])
    with pytest.raises(HostProtocolError) as fault:
        files.read_event(command.event_id, "inbox", now_ms=10001)
    assert fault.value.code is ProtocolFaultCode.RETIRED


def two_day_plan(
    files: HostEventFiles, command: HostEvent, *, clock: int = 1791633601000,
    first_cells: dict[str, Any] | None = None, second_cells: dict[str, Any] | None = None,
) -> HostWritePlan:
    first = generated_plan(files, command, clock=clock, **(first_cells or {}))
    second = generated_plan(files, command, clock=clock, day="2026-10-11", **(second_cells or {}))
    return HostWritePlan.model_validate(first.model_dump() | {"files": (*first.files, *second.files)})


def host_command(
    files: HostEventFiles, kind: str, *, sequence: int, previous: HostEvent | None = None,
) -> HostEvent:
    return message(
        files.manifest, kind,
        {
            "controls": files.manifest.controls,
            "input_names": (),
            "target": files.bookkeeping.cpu_target,
            "previous_result_id": previous.event_id if previous is not None else None,
        },
        emitter="operator", sequence=sequence,
    )


def consume_exchange(files: HostEventFiles, command: HostEvent, *, now_ms: int) -> None:
    replies = files.read_event(command.event_id, "inbox", now_ms=now_ms).replies
    for event in (command, *replies):
        files.bookkeeping.mark_consumed(event.event_id)
    files.retire(command.event_id, now_ms=now_ms + files.manifest.limits.retry_window_ms)


@pytest.mark.parametrize("completed_index", [0, 1])
@pytest.mark.parametrize("attack", ["same_path", "rollback"])
def test_partial_two_day_skip_keeps_each_completed_file_constraints_after_retirement(
    tmp_path: Path, completed_index: int, attack: str
) -> None:
    files = store(tmp_path)
    ready(files)
    probe = host_command(files, "host.probe", sequence=1)
    original = two_day_plan(files, probe)
    first = publish_host_successor(
        files, probe, original, cpu_evidence(), monitor_sequence=2, now_ms=1
    )
    consume_exchange(files, probe, now_ms=2)
    partial_command = host_command(files, "host.clock", sequence=2, previous=first)
    partial = two_day_plan(
        files, partial_command, clock=1791633602000,
        first_cells={"job_seconds": 1}, second_cells={"job_seconds": 2},
    )
    files.publish(partial_command, now_ms=6000)
    plan_event = message(
        files.manifest, "host.write.plan", {"plan": partial}, sequence=5,
        reply_to=partial_command.event_id,
    )
    files.publish(plan_event, now_ms=6000)
    completed = publish_completion(
        files, partial, monitor_sequence=6, now_ms=6000, indices=(completed_index,)
    )
    skipped = message(
        files.manifest, "instrument.skipped",
        {
            "command_kind": "host.clock",
            "unavailable": ({"source": "clock.log", "reason": "missing"},),
            "completion_event_ids": (completed.event_id,),
        },
        sequence=7, reply_to=partial_command.event_id,
    )
    files.publish(skipped, now_ms=6000)
    physical = tmp_path / partial.target_root / partial.files[completed_index].relative_path
    immutable = physical.read_bytes()
    consume_exchange(files, partial_command, now_ms=6001)
    retry = host_command(files, "host.clock", sequence=3, previous=first)
    files.publish(retry, now_ms=12000)
    candidate = two_day_plan(
        files, retry, clock=1791633603000,
        first_cells={"job_seconds": 3}, second_cells={"job_seconds": 3},
    )
    bad_file = (
        generated_plan(
            files, retry, clock=1791633602000,
            day=partial.files[completed_index].rows[0].date, job_seconds=3,
        ).files[0]
        if attack == "same_path" else original.files[completed_index]
    )
    invalid_files = list(candidate.files)
    invalid_files[completed_index] = bad_file
    invalid = HostWritePlan.model_validate(candidate.model_dump() | {"files": invalid_files})
    invalid_event = message(
        files.manifest, "host.write.plan", {"plan": invalid}, sequence=8,
        reply_to=retry.event_id,
    )
    with pytest.raises(ValueError, match="strictly later clock"):
        files.publish(invalid_event, now_ms=12000)
    assert not files.event_path(invalid_event.event_id, "results").exists()
    assert physical.read_bytes() == immutable
    valid_files = list(candidate.files)
    valid_files[completed_index] = partial.files[completed_index]
    valid = HostWritePlan.model_validate(candidate.model_dump() | {"files": valid_files})
    result = publish_host_successor(
        files, retry, valid, cpu_evidence(), monitor_sequence=8, now_ms=12000
    )
    assert isinstance(result.body, HostResultBody)
    assert result.body.row.job_seconds == (1 if completed_index == 0 else 3)
    assert physical.read_bytes() == immutable
    replies = files.read_event(retry.event_id, "inbox", now_ms=12001).replies
    assert len(replies) == 3
    assert isinstance(replies[1].body, WriteCompletedBody)
    assert set(replies[1].body.completion.receipt.writes) == {
        f"{valid.target_root}/{file.relative_path}" for file in valid.files
    }


@pytest.mark.parametrize("kind", ["host.clock", "host.target"])
@pytest.mark.parametrize("reverse", [False, True])
def test_two_day_command_ownership_matches_every_unit_not_file_position(
    tmp_path: Path, kind: str, reverse: bool
) -> None:
    files = store(tmp_path)
    ready(files)
    register(files)
    probe = host_command(files, "host.probe", sequence=1)
    initial = two_day_plan(files, probe)
    first = publish_host_successor(
        files, probe, initial, cpu_evidence(), monitor_sequence=3, now_ms=2
    )
    command = host_command(files, kind, sequence=2, previous=first)
    target_cells: dict[str, Any] = {
        "cpu_allowed_processors": 1,
        "cpu_quota_state": "unlimited",
        "cpu_target_measured_at": "2026-10-10T12:00:01Z",
    }
    candidate = two_day_plan(
        files, command, clock=1791633602000,
        first_cells={"job_seconds": 1} if kind == "host.clock" else target_cells,
        second_cells=target_cells if kind == "host.clock" else {"job_seconds": 1},
    )
    if reverse:
        candidate = HostWritePlan.model_validate(
            candidate.model_dump() | {"files": tuple(reversed(candidate.files))}
        )
    files.publish(command, now_ms=3)
    plan_event = message(
        files.manifest, "host.write.plan", {"plan": candidate}, sequence=6,
        reply_to=command.event_id,
    )
    with pytest.raises(HostProtocolError, match="another instrument"):
        files.publish(plan_event, now_ms=3)
    assert not files.event_path(plan_event.event_id, "results").exists()
    valid = two_day_plan(
        files, command, clock=1791633602000,
        first_cells={"job_seconds": 1} if kind == "host.clock" else target_cells,
        second_cells={"job_seconds": 2} if kind == "host.clock" else target_cells,
    )
    valid_event = message(
        files.manifest, "host.write.plan", {"plan": valid}, sequence=6,
        reply_to=command.event_id,
    )
    files.publish(valid_event, now_ms=3)
    assert files.read_event(command.event_id, "inbox", now_ms=4).replies == (valid_event,)


def test_targetless_probe_cannot_publish_selected_manifest_target_cells(tmp_path: Path) -> None:
    files = store(tmp_path)
    ready(files)
    session = files.manifest
    command = message(
        session, "host.probe", {"controls": session.controls, "input_names": (), "target": None},
        emitter="operator",
    )
    files.publish(command, now_ms=1)
    invalid = two_day_plan(
        files, command,
        second_cells={
            "cpu_allowed_processors": 1, "cpu_quota_state": "unlimited",
            "cpu_target_measured_at": "2026-10-10T12:00:01Z",
        },
    )
    plan_event = message(
        session, "host.write.plan", {"plan": invalid}, sequence=2, reply_to=command.event_id
    )
    with pytest.raises(HostProtocolError) as fault:
        files.publish(plan_event, now_ms=1)
    assert fault.value.code is ProtocolFaultCode.TARGET
    assert not files.event_path(plan_event.event_id, "results").exists()
    valid = generated_plan(files, command)
    first = publish_host_successor(
        files, command, valid, cpu_evidence(), monitor_sequence=2, now_ms=1
    )
    assert isinstance(first.body, HostResultBody)
    assert first.body.cpu.target is None
    assert first.body.row.cpu_target_measured_at is None
    enrichment = host_command(files, "host.target", sequence=2, previous=first)
    with pytest.raises(HostProtocolError, match="registration ACK"):
        files.publish(enrichment, now_ms=2)
    register(files, monitor_sequence=5)
    target_cells: dict[str, Any] = {
        "cpu_allowed_processors": 1, "cpu_quota_state": "unlimited",
        "cpu_target_measured_at": "2026-10-10T12:00:01Z",
    }
    enriched_plan = generated_plan(files, enrichment, clock=1791633602000, **target_cells)
    original_cpu = cpu_evidence()
    target_cpu = CpuDiagnostics(
        online_cpu_ids=original_cpu.online_cpu_ids, target=session.cpu_target,
        sources=tuple(
            SourceCoverage(source=source.source, status="complete", expected=1, observed=1)
            if source.source in {CaptureSource.AFFINITY, CaptureSource.CPUSET, CaptureSource.QUOTA}
            else source
            for source in original_cpu.sources
        ),
    )
    enriched = publish_host_successor(
        files, enrichment, enriched_plan, target_cpu, monitor_sequence=6, now_ms=3
    )
    assert isinstance(enriched.body, HostResultBody)
    assert enriched.body.cpu.target == session.cpu_target
    assert enriched.body.row.cpu_allowed_processors == 1


def test_probe_result_target_stays_bound_to_command_when_registration_arrives(
    tmp_path: Path,
) -> None:
    data = manifest_data()
    data.update(cpu_target=None, cpu_target_role="unselected")
    session = HostSessionManifest.model_validate(data)
    files = HostEventFiles(tmp_path, session)
    ready(files)
    command = host_command(files, "host.probe", sequence=1)
    plan = generated_plan(files, command)
    files.publish(command, now_ms=1)
    plan_event = message(
        session, "host.write.plan", {"plan": plan}, sequence=2, reply_to=command.event_id
    )
    files.publish(plan_event, now_ms=1)
    completed = publish_completion(files, plan, monitor_sequence=3, now_ms=1)
    register(files, monitor_sequence=4)
    target = files.bookkeeping.cpu_target
    assert target == session.workers[0].server and target is not None
    original = cpu_evidence()
    captured = CpuDiagnostics(
        online_cpu_ids=original.online_cpu_ids, target=target,
        sources=tuple(
            SourceCoverage(source=source.source, status="complete", expected=1, observed=1)
            if source.source in {CaptureSource.AFFINITY, CaptureSource.CPUSET, CaptureSource.QUOTA}
            else source
            for source in original.sources
        ),
    )
    row = CorrectedHostFingerprintRow.model_validate(
        {
            name: getattr(plan.files[0].rows[0], name)
            for name in CorrectedHostFingerprintRow.model_fields
        }
        | {
            "cpu_allowed_processors": 1, "cpu_quota_state": "unlimited",
            "cpu_target_measured_at": "2026-10-10T12:00:01Z",
        }
    )
    forged = message(
        session, "host.result",
        HostResultBody(row=row, cpu=captured, completion_event_ids=(completed.event_id,)),
        sequence=5, reply_to=command.event_id,
    )
    with pytest.raises(HostProtocolError) as fault:
        files.publish(forged, now_ms=2)
    assert fault.value.code is ProtocolFaultCode.TARGET
    assert not files.event_path(forged.event_id, "results").exists()
    valid_row = CorrectedHostFingerprintRow.model_validate(
        {name: getattr(plan.files[0].rows[0], name) for name in CorrectedHostFingerprintRow.model_fields}
    )
    valid = message(
        session, "host.result",
        HostResultBody(row=valid_row, cpu=original, completion_event_ids=(completed.event_id,)),
        sequence=5, reply_to=command.event_id,
    )
    files.publish(valid, now_ms=2)
    assert files.read_event(command.event_id, "inbox", now_ms=3).replies == (plan_event, completed, valid)
