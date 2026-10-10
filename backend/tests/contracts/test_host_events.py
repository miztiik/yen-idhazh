"""Do the serialized host exchanges match their real output and legacy cell sources?"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any, Literal, get_args, get_origin
from uuid import uuid4

import pytest
from conftest import FIXTURES_DIR
from pydantic import ValidationError

from idhazh.contracts import host_events
from idhazh.contracts.host_events import (
    MEMORY_SOURCES,
    WINDOW_CELL_SOURCES,
    CaptureSource,
    CollectionControls,
    CpuDiagnostics,
    HostCaptureLimits,
    HostEvent,
    HostEventLimits,
    HostResultBody,
    HostSessionManifest,
    HostWindowCells,
    LegacyJobSample,
    LegacyProcessRollcall,
    ProcessTarget,
    SourceCoverage,
    UnavailableReason,
    WindowResultBody,
)
from idhazh.contracts.host_output import INT64_MAX, CorrectedHostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.telemetry.host import HostCells
from utilities import memory_sampler

pytestmark = pytest.mark.contract


def manifest_data() -> dict[str, Any]:
    value = json.loads((FIXTURES_DIR / "host-events" / "manifest.json").read_bytes())
    assert isinstance(value, dict)
    return value


def test_committed_experiment_sections_validate_and_have_no_production_root() -> None:
    from dataclasses import fields

    from idhazh.telemetry.host_output_verify import VerificationLimits

    config = json.loads(
        (Path(__file__).resolve().parents[3] / "config" / "host-telemetry-experiment.json").read_bytes()
    )
    assert set(config) == {
        "version", "controls", "limits", "capture_limits", "verification_limits"
    }
    assert config["version"] == host_events.HOST_EVENT_VERSION
    assert CollectionControls.model_validate(config["controls"]).memory_profiling_enabled
    HostEventLimits.model_validate(config["limits"])
    HostCaptureLimits.model_validate(config["capture_limits"])
    assert set(config["verification_limits"]) == {
        field.name for field in fields(VerificationLimits)
    }
    VerificationLimits(**config["verification_limits"])


def manifest(**changes: Any) -> HostSessionManifest:
    return HostSessionManifest.model_validate(manifest_data() | changes)


def message(
    session: HostSessionManifest,
    kind: str,
    body: Any,
    *,
    emitter: str | None = None,
    sequence: int = 1,
    reply_to: Any = None,
    **changes: Any,
) -> HostEvent:
    return HostEvent.model_validate(
        {
            "kind": kind,
            "event_id": uuid4(),
            "reply_to": reply_to,
            "date": session.date,
            "run_id": session.run_id,
            "attempt": session.attempt,
            "job": session.job,
            "shard": session.shard,
            "session_id": session.session_id,
            "emitter_id": emitter or session.monitor_emitter_id,
            "sequence": sequence,
            "emitted_at": "2026-10-10T12:00:00Z",
            "body": body,
            **changes,
        }
    )


def window_body(session: HostSessionManifest, index: int = 0) -> dict[str, Any]:
    window = session.windows[index]
    worker = next(worker for worker in session.workers if worker.emitter_id == window.emitter_id)
    return {
        "window_id": window.window_id,
        "item_id": window.item_id,
        "target": worker.target,
        "server": worker.server,
    }


def result_body(
    session: HostSessionManifest,
    *,
    index: int = 0,
    abort: bool = False,
) -> WindowResultBody:
    memory = session.controls.memory_profiling_enabled
    cells = {
        name: None
        if abort or (not memory and source in MEMORY_SOURCES)
        else 2.0
        if name in {"cpu_busy_pct", "cpu_busy_max", "cpu_busy_min", "cpu_steal_pct", "load_1m"}
        else 1024
        for name, source in WINDOW_CELL_SOURCES.items()
    }
    sources = set(WINDOW_CELL_SOURCES.values()) if abort else set()
    if not memory:
        sources |= set(WINDOW_CELL_SOURCES.values()) & MEMORY_SOURCES
    return WindowResultBody.model_validate(
        {
            **window_body(session, index),
            "status": "incomplete" if abort else "complete",
            "opened_at": None if abort else "2026-10-10T12:00:00Z",
            "closed_at": None if abort else "2026-10-10T12:00:01Z",
            "memory_profiling_enabled": memory,
            "cells": cells,
            "unavailable": [
                {
                    "source": source,
                    "reason": "disabled" if not memory and source in MEMORY_SOURCES else "missing",
                }
                for source in sorted(sources)
            ],
        }
    )


def test_exact_host_cells_keys_types_and_item_health_binding() -> None:
    empty = HostCells(**dict.fromkeys(HostWindowCells.model_fields))
    assert empty.cells() == HostWindowCells().model_dump()
    assert set(WINDOW_CELL_SOURCES) == set(empty.cells())
    for name, field in HostWindowCells.model_fields.items():

        def scalar_types(annotation: Any) -> frozenset[Any]:
            if get_origin(annotation) is Annotated:
                return scalar_types(get_args(annotation)[0])
            args = get_args(annotation)
            if args:
                return frozenset(value for part in args for value in scalar_types(part))
            return frozenset((annotation,))

        assert scalar_types(field.annotation) == scalar_types(
            ItemHealthRow.model_fields[name].annotation
        )
    complete = result_body(manifest())
    assert HostWindowCells.model_validate_json(complete.cells.model_dump_json()) == complete.cells
    for name, value in complete.cells.model_dump().items():
        assert value is not None
        annotation = ItemHealthRow.model_fields[name].annotation
        assert type(value) is (float if "float" in str(annotation) else int)


def test_manifest_roundtrip_and_memory_default() -> None:
    session = manifest()
    assert HostSessionManifest.model_validate_json(session.model_dump_json()) == session
    assert session.pending_event_limit == 4 * len(session.workers) + 2 + 8
    controls = session.controls.model_dump()
    controls.pop("memory_profiling_enabled")
    assert CollectionControls.model_validate(controls).memory_profiling_enabled is True
    schema = HostSessionManifest.json_schema()
    assert schema["version"] == "2026-10-10"
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("bad", [True, False, "1", 1.0, 1.5, -1, INT64_MAX + 1])
@pytest.mark.parametrize("field", ["pid", "start_ticks"])
def test_target_integers_are_not_coerced(field: str, bad: Any) -> None:
    with pytest.raises(ValidationError):
        ProcessTarget.model_validate({"pid": 1, "start_ticks": 0, field: bad})


@pytest.mark.parametrize("bad", [True, "1", 1.0, 1.5, -1, INT64_MAX + 1])
@pytest.mark.parametrize("field", ["attempt", "shard"])
def test_envelope_integers_are_strict(field: str, bad: Any) -> None:
    session = manifest()
    with pytest.raises(ValidationError):
        message(
            session,
            "monitor.ready",
            {"boot_id": session.boot_id, "supported_version": session.version},
            **{field: bad},
        )


@pytest.mark.parametrize("field", tuple(manifest_data()["limits"]))
@pytest.mark.parametrize("bad", [True, "1", 1.0, INT64_MAX + 1, 0])
def test_all_transport_limits_are_bounded_integers(field: str, bad: Any) -> None:
    data = manifest_data()
    data["limits"][field] = bad
    with pytest.raises(ValidationError):
        HostSessionManifest.model_validate(data)


@pytest.mark.parametrize("field", tuple(HostWindowCells.model_fields))
@pytest.mark.parametrize("bad", [True, "3", float("nan"), float("inf"), -1])
def test_all_window_cells_refuse_invalid_measurements(field: str, bad: Any) -> None:
    with pytest.raises(ValidationError):
        HostWindowCells.model_validate({field: bad})


@pytest.mark.parametrize(
    "field",
    tuple(
        name
        for name in HostWindowCells.model_fields
        if name not in {"cpu_busy_pct", "cpu_busy_max", "cpu_busy_min", "cpu_steal_pct", "load_1m"}
    ),
)
@pytest.mark.parametrize("bad", [1.0, 1.5, INT64_MAX + 1])
def test_memory_and_fault_cells_are_whole_int64(field: str, bad: Any) -> None:
    with pytest.raises(ValidationError):
        HostWindowCells.model_validate({field: bad})


@pytest.mark.parametrize("bad", ["true", "false", 0, 1, None])
def test_memory_control_is_one_real_boolean(bad: Any) -> None:
    data = manifest_data()
    data["controls"]["memory_profiling_enabled"] = bad
    with pytest.raises(ValidationError):
        HostSessionManifest.model_validate(data)


def test_memory_off_nulls_only_memory_and_fault_cells() -> None:
    data = manifest_data()
    data["controls"]["memory_profiling_enabled"] = False
    result = result_body(HostSessionManifest.model_validate(data))
    assert result.cells.cpu_busy_pct == 2.0
    assert result.cells.load_1m == 2.0
    assert {entry.reason for entry in result.unavailable} == {UnavailableReason.DISABLED}
    bad = result.model_dump(mode="json")
    bad["cells"]["llama_rss_bytes"] = 0
    with pytest.raises(ValidationError, match="memory off"):
        WindowResultBody.model_validate(bad)


@pytest.mark.parametrize(
    "change",
    [
        {"status": "complete", "observed": 1, "expected": 2},
        {"status": "complete", "reason": "missing"},
        {"status": "partial"},
        {"status": "unavailable", "observed": 1, "reason": "missing"},
        {"reason": "unlimited"},
        {"source": "invented"},
        {"observed": True},
        {"expected": INT64_MAX + 1},
        {"expected": 0, "observed": 0},
    ],
)
def test_source_coverage_is_finite_and_consistent(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SourceCoverage.model_validate(
            {"source": "proc.cpuinfo", "status": "complete", "expected": 1, "observed": 1, **change}
        )


@pytest.mark.parametrize(
    "change",
    [
        {"version": "2099-01-01"},
        {"date": "2026-02-30"},
        {"kind": "unknown"},
        {"sequence": True},
        {"sequence": 0},
        {"sequence": 1.0},
        {"emitted_at": "2026-10-10T99:00:00Z"},
        {"unknown": 1},
        {"event_id": "../outside"},
        {"body": {"boot_id": str(uuid4()), "supported_version": "2026-10-10", "extra": {}}},
    ],
)
def test_unknown_event_fields_versions_kinds_and_bad_dates_fail(change: dict[str, Any]) -> None:
    session = manifest()
    ready = message(
        session, "monitor.ready", {"boot_id": session.boot_id, "supported_version": session.version}
    )
    with pytest.raises(ValidationError):
        HostEvent.model_validate(ready.model_dump(mode="json") | change)


def test_schema_kind_selects_typed_body_and_no_open_body_maps() -> None:
    session = manifest()
    ready = message(
        session, "monitor.ready", {"boot_id": session.boot_id, "supported_version": session.version}
    )
    schema = HostEvent.json_schema()
    assert HostEvent.model_validate_json(ready.model_dump_json()) == ready
    bad = ready.model_dump(mode="json")
    bad["body"] = {"reason": "completed"}
    with pytest.raises(ValidationError):
        HostEvent.model_validate(bad)
    variants = schema["allOf"][0]["oneOf"]
    for variant in variants:
        definition = schema["$defs"][variant["properties"]["body"]["$ref"].split("/")[-1]]
        assert definition["additionalProperties"] is False
    assert {variant["properties"]["kind"]["const"] for variant in variants} == {
        "monitor.ready",
        "host.probe",
        "host.target",
        "host.clock",
        "host.result",
        "worker.register",
        "worker.registered",
        "window.begin",
        "window.begun",
        "window.end",
        "window.abort",
        "window.result",
        "monitor.stop",
        "monitor.stopped",
        "instrument.skipped",
        "protocol.fault",
        "host.write.plan",
        "host.write.completed",
        "job.sample",
        "process.rollcall",
    }
    for cls in vars(host_events).values():
        if isinstance(cls, type) and issubclass(cls, host_events.ExchangeModel):
            assert cls.model_config["extra"] == "forbid"
            assert cls.model_config["frozen"] is True


@pytest.mark.parametrize("change", ["worker", "window", "input", "root", "target", "role"])
def test_manifest_duplicate_and_identity_conflicts(change: str) -> None:
    data = manifest_data()
    if change == "worker":
        data["workers"].append(data["workers"][0])
    elif change == "window":
        data["windows"].append(data["windows"][0])
    elif change == "input":
        data["named_inputs"].append(data["named_inputs"][0])
    elif change == "root":
        data["event_root"] = "backend/var/host-events/another-session"
    elif change == "target":
        data["cpu_target"]["start_ticks"] += 1
    else:
        data["cpu_target_role"] = "python_worker"
    with pytest.raises(ValidationError):
        HostSessionManifest.model_validate(data)


def test_legacy_bodies_come_from_the_current_real_sampler(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    for pid, comm, status in [
        (100, "llama-server", "VmRSS: 2048 kB\nVmHWM: 4096 kB\n"),
        (200, "python3", "VmRSS: 512 kB\nVmHWM: 768 kB\n"),
        (300, "python3.12", "VmRSS: 256 kB\n"),
    ]:
        entry = proc / str(pid)
        entry.mkdir(parents=True)
        (entry / "comm").write_bytes((comm + "\n").encode())
        (entry / "status").write_bytes(status.encode())
        (entry / "cmdline").write_bytes(b"python3\0-m\0idhazh\0work\0secret-is-not-exported\0")
    (proc / "meminfo").write_bytes(
        b"MemTotal: 8192 kB\nMemAvailable: 6144 kB\nCommitted_AS: 4096 kB\n"
    )
    charge = tmp_path / "memory.current"
    charge.write_bytes(b"1024\n")
    sample, rollcall = memory_sampler.sample_once(
        100, proc_root=proc, cgroup_paths=(charge,), now="2026-10-10T12:00:00Z"
    )
    assert LegacyJobSample.model_validate(sample).model_dump() == sample
    assert LegacyJobSample.model_validate(sample).python_vmhwm_kb == 1024
    assert [LegacyProcessRollcall.model_validate(row).model_dump() for row in rollcall] == rollcall
    assert set(LegacyJobSample.model_fields) == set(sample)
    assert set(LegacyProcessRollcall.model_fields) == set(rollcall[0])
    assert host_events.LEGACY_JOB_SAMPLE_FILENAME == memory_sampler.RSS_SAMPLE_FILE.name
    assert host_events.LEGACY_PROCESS_ROLLCALL_FILENAME == memory_sampler.PYTHON_PROCS_FILE.name
    assert all("secret" not in (row["args"] or "") for row in rollcall)
    samples = tmp_path / host_events.LEGACY_JOB_SAMPLE_FILENAME
    rows = tmp_path / host_events.LEGACY_PROCESS_ROLLCALL_FILENAME
    samples.write_bytes(LegacyJobSample.model_validate(sample).model_dump_json().encode() + b"\n")
    rows.write_bytes(
        b"".join(
            LegacyProcessRollcall.model_validate(row).model_dump_json().encode() + b"\n"
            for row in rollcall
        )
    )
    result = subprocess.run(
        [sys.executable, "-m", "utilities.memory_sampler", "summarize"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "peak python VmHWM 1024 kB" in result.stderr + result.stdout
    assert "n=1 samples" in result.stderr + result.stdout


def test_contract_has_no_reverse_transport_collector_or_verifier_imports() -> None:
    tree = ast.parse(inspect.getsource(host_events))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("idhazh."):
            assert node.module is not None and node.module.startswith("idhazh.contracts.")


@pytest.mark.parametrize(
    ("field", "source", "value"),
    [
        ("cpu_physical_cores", CaptureSource.TOPOLOGY, 1),
        ("cpu_reported_max_mhz", CaptureSource.CPUFREQ, 3200.0),
    ],
)
@pytest.mark.parametrize("online_ids", [(), (0, 2)])
def test_positive_cpu_measurements_cannot_claim_zero_or_unvalidated_coverage(
    field: str, source: CaptureSource, value: int | float, online_ids: tuple[int, ...]
) -> None:
    row = CorrectedHostFingerprintRow.model_validate(
        {
            "version": "2026-10-10", "date": "2026-10-10",
            "run_id": "2026-10-10-123456789", "shard": 0, field: value,
        }
    )
    sources = [
        {
            "source": name,
            "status": "complete" if name == source else "unavailable",
            "expected": len(online_ids) if name != source else 0,
            "observed": 0,
            "reason": None if name == source else "missing",
        }
        for name in (
            CaptureSource.ONLINE, CaptureSource.TOPOLOGY, CaptureSource.CPUINFO,
            CaptureSource.CPUFREQ, CaptureSource.AFFINITY, CaptureSource.CPUSET, CaptureSource.QUOTA,
        )
    ]
    with pytest.raises(ValidationError, match=r"complete coverage|online inventory"):
        HostResultBody.model_validate(
            {
                "row": row,
                "cpu": {"online_cpu_ids": online_ids, "sources": sources},
                "completion_event_ids": (uuid4(),),
            }
        )


@pytest.mark.parametrize("status", ["complete", "partial", "unavailable"])
def test_online_inventory_cannot_disagree_with_its_source_coverage(
    status: Literal["complete", "partial", "unavailable"],
) -> None:
    names = (
        CaptureSource.ONLINE, CaptureSource.TOPOLOGY, CaptureSource.CPUINFO,
        CaptureSource.CPUFREQ, CaptureSource.AFFINITY, CaptureSource.CPUSET, CaptureSource.QUOTA,
    )
    sources = [
        SourceCoverage(
            source=name, status=status if name == CaptureSource.ONLINE else "unavailable",
            expected=3,
            observed=(3 if status == "complete" else 1 if status == "partial" else 0)
            if name == CaptureSource.ONLINE else 0,
            reason=None if name == CaptureSource.ONLINE and status == "complete" else UnavailableReason.MISSING,
        )
        for name in names
    ]
    with pytest.raises(ValidationError, match="online inventory"):
        CpuDiagnostics(online_cpu_ids=(0, 2), sources=tuple(sources))


def test_positive_cpu_measurements_accept_real_nonempty_complete_coverage() -> None:
    names = (
        CaptureSource.ONLINE, CaptureSource.TOPOLOGY, CaptureSource.CPUINFO,
        CaptureSource.CPUFREQ, CaptureSource.AFFINITY, CaptureSource.CPUSET, CaptureSource.QUOTA,
    )
    measured = {CaptureSource.ONLINE, CaptureSource.TOPOLOGY, CaptureSource.CPUFREQ}
    cpu = CpuDiagnostics(
        online_cpu_ids=(0, 2),
        sources=tuple(
            SourceCoverage(
                source=name, expected=2, observed=2 if name in measured else 0,
                status="complete" if name in measured else "unavailable",
                reason=None if name in measured else UnavailableReason.MISSING,
            )
            for name in names
        ),
    )
    row = CorrectedHostFingerprintRow(
        version="2026-10-10", date="2026-10-10", run_id="2026-10-10-123456789", shard=0,
        cpu_physical_cores=1, cpu_logical_processors=2, cpu_reported_max_mhz=3200.0,
    )
    result = HostResultBody(row=row, cpu=cpu, completion_event_ids=(uuid4(),))
    assert result.row.cpu_physical_cores == 1
    assert result.row.cpu_reported_max_mhz == 3200.0
