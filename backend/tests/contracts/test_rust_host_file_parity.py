"""Do actual native host bytes and closed Rust contracts match the Python candidates?"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import struct
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import BaseModel, ValidationError

from idhazh.contracts import host_events
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_events import HostEvent, HostSessionManifest, HostWindowCells
from idhazh.contracts.host_output import (
    HOST_OUTPUT_VERSION,
    CandidateFileEnvelope,
    CorrectedHostFingerprintRow,
    HostStoredRow,
    HostWriteCompletion,
    HostWritePlan,
    canonical_host_rows,
    fingerprint_v2,
    host_file_id,
    host_unit_id,
)
from idhazh.ledger import json_lines, parquet
from idhazh.ledger.arrow_schema import ColumnType
from idhazh.telemetry.host_output_verify import (
    VerificationLimits,
    host_output_columns,
    verify_host_output,
)

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "host-events" / "file-parity.json"


def binary() -> Path:
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "backend/var/rust-host-telemetry"))
    path = Path(os.environ.get(
        "IDHAZH_HOST_CODEC_FIXTURE",
        target / "debug" / ("codec-fixture.exe" if os.name == "nt" else "codec-fixture"),
    ))
    assert path.is_file(), "Build the locked Rust codec-fixture before native parity tests."
    return path


def rust(shape: str, value: Any, *, valid: bool = True) -> Any:
    result = subprocess.run(
        [str(binary()), "validate", shape],
        input=json.dumps(value, ensure_ascii=True, allow_nan=False).encode("ascii"),
        cwd=ROOT, capture_output=True, check=False, timeout=30,
    )
    if not valid:
        assert result.returncode != 0, (shape, value, result.stdout)
        return None
    assert result.returncode == 0, result.stderr.decode()
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def native_proofs() -> list[dict[str, Any]]:
    # Only Rust creates these native containers, their plans and physical hashes.
    output = f"backend/var/d10-python-parity/{uuid4()}"
    result = subprocess.run(
        [str(binary()), "render", FIXTURE.relative_to(ROOT).as_posix(), output],
        cwd=ROOT, capture_output=True, check=False, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()
    proofs = json.loads(result.stdout)
    assert len(proofs) == 4
    assert isinstance(proofs, list)
    return proofs


@pytest.mark.parametrize("index", range(4))
def test_exact_native_bytes_pass_candidate_actual_page_admission(
    native_proofs: list[dict[str, Any]], index: int,
) -> None:
    proof = native_proofs[index]
    plan = HostWritePlan.model_validate(proof["plan"])
    completion = HostWriteCompletion.model_validate(proof["completion"])
    limits = VerificationLimits(**json.loads(
        (ROOT / "config/host-telemetry-experiment.json").read_bytes()
    )["verification_limits"])
    path = ROOT / plan.target_root / plan.files[0].relative_path
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == proof["physical_sha256"]
    result = verify_host_output(
        plan, completion, workspace_root=ROOT, target_root=plan.target_root,
        publication_identity=plan.publication_identity, limits=limits,
    )
    assert result.complete and len(result.files) == 1
    verified = result.files[0]
    expected = CorrectedHostFingerprintRow.model_validate(json.loads(FIXTURE.read_bytes())["row"])
    expected = CorrectedHostFingerprintRow.model_validate(
        expected.model_dump() | {"fingerprint": fingerprint_v2(expected), "fingerprint_version": 2}
    )
    assert verified.rows[0].model_dump(exclude={"ledger", "covers", "attempt", "unit_id"}) == expected.model_dump()
    assert verified.envelope.unit_id == host_unit_id(covers=expected.date, identity=plan.publication_identity)
    assert verified.envelope.file_id == host_file_id(
        unit=verified.envelope.unit_id, attempt=2, written_at_ms=1791633600123,
    )
    canonical = canonical_host_rows(verified.rows)
    assert hashlib.sha256(canonical).hexdigest() == verified.envelope.content_sha256
    assert verified.rows[0].boot_seconds is not None
    assert math.copysign(1, verified.rows[0].boot_seconds) == -1
    assert verified.physical_sha256 == proof["physical_sha256"]
    assert verified.size_bytes == proof["size_bytes"] == len(original)
    expected_metadata = verified.envelope.as_metadata()
    if index == 0:
        metadata, rows = json_lines.read(original)
        assert original.partition(b"\n")[2] == canonical
        assert metadata == expected_metadata
        assert rows[0]["cpu_model"] == expected.cpu_model
        assert verified.envelope.writer == "idhazh_rust.ledger.json_lines"
        assert verified.envelope.compression.value == "none"
    else:
        metadata, rows = parquet.read(original)
        assert {key: value for key, value in metadata.items() if key != b"ARROW:schema"} == expected_metadata
        assert json_lines.rows_bytes(rows) == canonical
        assert verified.created_by == f"parquet-rs version {verified.envelope.writer_version}"
        with pa.BufferReader(original) as source, pq.ParquetFile(source) as opened:
            assert opened.schema_arrow.equals(
                parquet.schema_of(host_output_columns(HOST_OUTPUT_VERSION)), check_metadata=False,
            )
            assert opened.metadata.num_row_groups == opened.metadata.num_rows == 1
            group = opened.metadata.row_group(0)
            assert group.num_columns == 40
            for column in range(group.num_columns):
                chunk = group.column(column)
                assert set(chunk.encodings) <= {"PLAIN", "RLE"}
                assert not chunk.has_dictionary_page
                assert not chunk.has_column_index and not chunk.has_offset_index
                assert chunk.statistics is not None
    assert path.read_bytes() == original, "Verification changed the actual Rust file."


def test_rust_harness_itself_created_native_artifacts() -> None:
    path = ROOT / "backend/var/d10-rust-tests/parquet/proofs.json"
    assert path.is_file(), "Run locked offline cargo test before cross-language checks."
    proofs = json.loads(path.read_bytes())
    limits = VerificationLimits(**json.loads(
        (ROOT / "config/host-telemetry-experiment.json").read_bytes()
    )["verification_limits"])
    for proof in proofs:
        plan = HostWritePlan.model_validate(proof["plan"])
        completion = HostWriteCompletion.model_validate(proof["completion"])
        artifact = ROOT / plan.target_root / plan.files[0].relative_path
        data = artifact.read_bytes()
        assert hashlib.sha256(data).hexdigest() == proof["physical_sha256"]
        result = verify_host_output(
            plan, completion, workspace_root=ROOT, target_root=plan.target_root,
            publication_identity=plan.publication_identity, limits=limits,
        )
        assert result.complete and len(result.files) == 1
        assert result.files[0].physical_sha256 == proof["physical_sha256"]
        assert artifact.read_bytes() == data


def test_host_schema_exact_order_types_nullability_and_no_legacy_columns() -> None:
    columns = rust("schema", None)
    expected_columns = host_output_columns(HOST_OUTPUT_VERSION)
    assert all(isinstance(column.type, ColumnType) for column in expected_columns)
    assert columns == [
        {"name": column.name, "type": str(column.type), "nullable": column.nullable}
        for column in expected_columns
    ]
    assert [column["name"] for column in columns] == list(HostStoredRow.model_fields)


def test_ascii_canonical_objects_match_python_exact_bytes_and_hashes() -> None:
    vectors = [
        {"z": None, "a": "\u03bb\U0001f680\u007f\n\t\"\\", "float": -0.0},
        {"nested": [{"b": 1e-7, "a": 1e16}, {"a": [], "z": False}], "n": 0.0001},
        {"null": None, "int64": (1 << 63) - 1, "text": "\u0000\b\f\r"},
    ]
    for vector in vectors:
        result = subprocess.run(
            [str(binary()), "validate", "canonical"],
            input=json.dumps(vector).encode(), cwd=ROOT, capture_output=True, check=True,
        )
        expected = json.dumps(vector, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        assert result.stdout == expected
        assert hashlib.sha256(result.stdout).digest() == hashlib.sha256(expected).digest()


def test_shortest_float_digits_python_thresholds_and_random_ieee_vectors() -> None:
    generator = random.Random(20261010)
    values = [0.0, -0.0, 1e-5, 1e-4, 1e15, 1e16, 1e20, 1e23, 5e-324, -1.7976931348623157e308]
    for _ in range(20000):
        value = struct.unpack(">d", generator.getrandbits(64).to_bytes(8, "big"))[0]
        if math.isfinite(value):
            values.append(value)
    bits = [struct.pack(">d", value).hex() for value in values]
    result = rust("float-bits", bits)
    assert result == [repr(value) for value in values]
    for value in [math.inf, -math.inf, math.nan]:
        rust("float-bits", [struct.pack(">d", value).hex()], valid=False)


def test_corrected_default_fields_and_all_job_vocabulary() -> None:
    source = {"date": "2026-10-10", "run_id": "2026-10-10-42", "shard": 0}
    for job in ServerJob:
        data = source | {"job": job.value}
        candidate = CorrectedHostFingerprintRow.model_validate(data).model_dump(mode="json")
        assert rust("row", data) == candidate
    assert rust("row", source) == CorrectedHostFingerprintRow.model_validate(source).model_dump(mode="json")


@pytest.mark.parametrize("field", [
    "shard", "cpu_family", "cpu_model_number", "cpu_stepping", "cpu_physical_cores",
    "cpu_logical_processors", "cpu_allowed_processors", "l3_cache_bytes", "memcpy_probe_mib",
    "job_seconds", "server_prompt_tokens", "fingerprint_version",
])
@pytest.mark.parametrize("bad", [True, "1", 1.0, 1.5, 1 << 63])
def test_exact_int64_refusal(field: str, bad: Any) -> None:
    data = json.loads(FIXTURE.read_bytes())["row"] | {field: bad}
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate(data)
    rust("row", data, valid=False)


@pytest.mark.parametrize("field", [
    "cpu_quota_cores", "cpu_observed_mhz", "cpu_reported_max_mhz",
    "boot_seconds", "memcpy_gib_s", "model_load_ms", "server_prompt_seconds",
])
@pytest.mark.parametrize("bad", [True, "1", -1])
def test_exact_float_constraints(field: str, bad: Any) -> None:
    data = json.loads(FIXTURE.read_bytes())["row"] | {field: bad}
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate(data)
    rust("row", data, valid=False)


def event_data(kind: str, proofs: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = json.loads((ROOT / "tests/fixtures/host-events/manifest.json").read_bytes())
    target = manifest["workers"][0]["target"]
    window = {
        "window_id": manifest["windows"][0]["window_id"], "item_id": "fixture-01",
        "target": target, "server": manifest["workers"][0]["server"],
    }
    cells = {
        name: 2.0 if name.startswith("cpu_") or name == "load_1m" else 1024
        for name in HostWindowCells.model_fields
    }
    sample = {
        "ts": "2026-10-10T12:00:00Z", "llama_vmrss_kb": None, "llama_vmhwm_kb": None,
        "python_vmrss_kb": 100, "python_procs": 1, "python_vmhwm_kb": 100,
        "mem_total_kb": None, "mem_available_kb": None, "committed_as_kb": None,
        "cgroup_current_bytes": None,
    }
    row = proofs[0]["plan"]["files"][0]["rows"][0]
    row = {name: row[name] for name in CorrectedHostFingerprintRow.model_fields}
    sources = [
        {"source": source, "status": "complete", "expected": 4, "observed": 4, "reason": None}
        for source in ["sysfs.online", "sysfs.topology", "proc.cpuinfo", "sysfs.cpufreq",
                       "sched.affinity", "cgroup.cpuset", "cgroup.cpu_quota"]
    ]
    bodies = {
        "monitor.ready": {"boot_id": manifest["boot_id"], "supported_version": HOST_OUTPUT_VERSION},
        "host.probe": {"controls": manifest["controls"], "input_names": ["cpuinfo"]},
        "host.target": {"controls": manifest["controls"], "input_names": [], "target": target},
        "host.clock": {"controls": manifest["controls"], "input_names": ["clock"]},
        "host.result": {"row": row, "cpu": {"online_cpu_ids": [0, 1, 2, 3], "sources": sources, "target": target},
                        "completion_event_ids": [proofs[0]["completion"]["event_id"]]},
        "worker.register": {"target": target},
        "worker.registered": {"target": target},
        "window.begin": window, "window.end": window,
        "window.begun": window | {"captured_at": "2026-10-10T12:00:00Z"},
        "window.abort": window | {"reason": "cancelled"},
        "window.result": window | {"status": "complete", "opened_at": "2026-10-10T12:00:00Z",
                                   "closed_at": "2026-10-10T12:00:01Z", "cells": cells, "unavailable": []},
        "monitor.stop": {"reason": "completed"},
        "monitor.stopped": {"drained": True, "aborted_window_ids": []},
        "instrument.skipped": {"command_kind": "host.probe", "unavailable": [{"source": "proc.cpuinfo", "reason": "missing"}]},
        "protocol.fault": {"code": "invalid_state", "related_event_id": None},
        "host.write.plan": {"plan": proofs[0]["plan"]},
        "host.write.completed": {"completion": proofs[0]["completion"]},
        "job.sample": {"record": sample},
        "process.rollcall": {"records": [{"ts": sample["ts"], "pid": 100, "comm": "python", "vmrss_kb": 100,
                                         "vmhwm_kb": None, "exe": None, "args": None}]},
    }
    no_reply = kind in host_events.COMMAND_KINDS | {"monitor.ready", "job.sample", "process.rollcall", "protocol.fault"}
    return {
        "kind": kind, "event_id": str(uuid4()), "reply_to": None if no_reply else str(uuid4()),
        "date": row["date"], "run_id": row["run_id"], "attempt": 2, "job": "work", "shard": 0,
        "session_id": manifest["session_id"], "emitter_id": "monitor", "sequence": 1,
        "emitted_at": "2026-10-10T12:00:00Z", "body": bodies[kind],
    }


@pytest.mark.parametrize("kind", list(host_events._BODY_TYPES))
def test_each_exact_event_kind_body_defaults_fields_and_unknown_refusal(
    native_proofs: list[dict[str, Any]], kind: str,
) -> None:
    data = event_data(kind, native_proofs)
    expected = HostEvent.model_validate(data).model_dump(mode="json")
    assert rust("event", data) == expected
    for place in [data, data["body"]]:
        bad = copy.deepcopy(data)
        target = bad if place is data else bad["body"]
        target["unknown"] = True
        with pytest.raises(ValidationError):
            HostEvent.model_validate(bad)
        rust("event", bad, valid=False)


def test_manifest_and_nested_defaults_constraints_match_candidate() -> None:
    data = json.loads((ROOT / "tests/fixtures/host-events/manifest.json").read_bytes())
    assert rust("manifest", data) == HostSessionManifest.model_validate(data).model_dump(mode="json")
    data["controls"].pop("memory_profiling_enabled")
    assert rust("manifest", data)["controls"]["memory_profiling_enabled"] is True
    mutations = [
        ("event_root", "../escape"), ("date", "2026-02-30"), ("cpu_target_role", "python_worker"),
        ("windows", data["windows"] * 2), ("workers", data["workers"] * 2),
        ("output_roots", []), ("git_sha", "a" * 39),
    ]
    for key, value in mutations:
        bad = copy.deepcopy(data)
        bad[key] = value
        with pytest.raises(ValidationError):
            HostSessionManifest.model_validate(bad)
        rust("manifest", bad, valid=False)


def test_window_abort_memory_off_and_predicates(
    native_proofs: list[dict[str, Any]],
) -> None:
    data = event_data("window.result", native_proofs)
    body = data["body"]
    body["memory_profiling_enabled"] = False
    memory_sources = set(host_events.MEMORY_SOURCES) & set(host_events.WINDOW_CELL_SOURCES.values())
    for name, source in host_events.WINDOW_CELL_SOURCES.items():
        if source in memory_sources:
            body["cells"][name] = None
    body["unavailable"] = [{"source": source, "reason": "disabled"} for source in sorted(memory_sources)]
    assert rust("event", data) == HostEvent.model_validate(data).model_dump(mode="json")
    for name, value in [("llama_major_faults", 1), ("cpu_busy_pct", None)]:
        bad = copy.deepcopy(data)
        bad["body"]["cells"][name] = value
        with pytest.raises(ValidationError):
            HostEvent.model_validate(bad)
        rust("event", bad, valid=False)
    body["status"] = "incomplete"
    body["opened_at"] = body["closed_at"] = None
    body["cells"] = dict.fromkeys(HostWindowCells.model_fields)
    body["unavailable"] = [
        {"source": source, "reason": "disabled" if source in memory_sources else "missing"}
        for source in sorted(set(host_events.WINDOW_CELL_SOURCES.values()))
    ]
    assert rust("event", data) == HostEvent.model_validate(data).model_dump(mode="json")


def test_envelope_plan_completion_exact_fields_provenance_and_conflicts(
    native_proofs: list[dict[str, Any]],
) -> None:
    for proof in native_proofs:
        cases: list[tuple[str, type[BaseModel], dict[str, Any]]] = [
            ("plan", HostWritePlan, proof["plan"]),
            ("completion", HostWriteCompletion, proof["completion"]),
            ("envelope", CandidateFileEnvelope, proof["plan"]["files"][0]["envelope"]),
            ("stored", HostStoredRow, proof["plan"]["files"][0]["rows"][0]),
        ]
        for shape, model, data in cases:
            assert rust(shape, data) == model.model_validate(data).model_dump(mode="json")
            bad = copy.deepcopy(data)
            bad["unknown"] = 1
            with pytest.raises(ValidationError):
                model.model_validate(bad)
            rust(shape, bad, valid=False)
        bad = copy.deepcopy(proof["plan"])
        bad["files"][0]["envelope"]["content_sha256"] = "0" * 64
        with pytest.raises(ValidationError):
            HostWritePlan.model_validate(bad)
        rust("plan", bad, valid=False)
        bad_row = copy.deepcopy(proof["plan"]["files"][0]["rows"][0])
        bad_row["unit_id"] = bad_row["unit_id"].upper()
        with pytest.raises(ValidationError):
            HostStoredRow.model_validate(bad_row)
        rust("stored", bad_row, valid=False)


def test_named_module_boundaries_have_no_engines_outside_parquet_or_host_io() -> None:
    source = ROOT / "backend/rust/host-telemetry/src"
    paths = [
        "contracts/host.rs", "contracts/events.rs", "contracts/file_envelope.rs",
        "contracts/write_plan.rs", "config.rs", "canonical_json.rs", "ledger/schema.rs",
        "codec/jsonl.rs", "codec/parquet.rs",
    ]
    for path in paths:
        text = (source / path).read_text(encoding="utf-8")
        assert text.startswith("//! ")
        assert "std::fs" not in text and "std::process" not in text
        if path != "codec/parquet.rs":
            assert "use arrow_" not in text and "use parquet::" not in text
        assert "producers::" not in text and "monitor::" not in text
    lib = (source / "lib.rs").read_text()
    assert "fn " not in lib


def test_metadata_exact_optional_keys_decimal_and_native_scope(
    native_proofs: list[dict[str, Any]],
) -> None:
    envelope = CandidateFileEnvelope.model_validate(native_proofs[1]["plan"]["files"][0]["envelope"])
    metadata = {key.decode(): value.decode() for key, value in envelope.as_metadata().items()}
    assert len(metadata) == 18 and "period" not in metadata and "built_from" not in metadata
    assert rust("metadata", metadata) == metadata
    for key in metadata:
        bad = dict(metadata)
        bad.pop(key)
        rust("metadata", bad, valid=False)
    for key, value in [("attempt", "-1"), ("shard", "true"), ("written_at_ms", "1.0"),
                       ("period", None), ("built_from", None), ("writer", "fake.parquet")]:
        rust("metadata", metadata | {key: value}, valid=False)
    for writer in ["idhazh.ledger.parquet", "idhazh_rust.ledger.parquet",
                   "idhazh.ledger.json_lines", "idhazh_rust.ledger.json_lines"]:
        data = envelope.model_dump(mode="json") | {"writer": writer, "compression": "none"}
        assert rust("envelope", data) == CandidateFileEnvelope.model_validate(data).model_dump(mode="json")
    for key, value in [("tier", "compact"), ("row_schema_version", "2026-09-20"),
                       ("version", "2026-10-06"), ("ledger", "seen")]:
        data = envelope.model_dump(mode="json") | {key: value}
        with pytest.raises(ValidationError):
            CandidateFileEnvelope.model_validate(data)
        rust("envelope", data, valid=False)


@pytest.mark.parametrize("kind", list(host_events._BODY_TYPES))
def test_every_body_field_missing_matches_candidate_required_and_default_rules(
    native_proofs: list[dict[str, Any]], kind: str,
) -> None:
    data = event_data(kind, native_proofs)
    for key in data["body"]:
        missing = copy.deepcopy(data)
        missing["body"].pop(key)
        try:
            expected = HostEvent.model_validate(missing).model_dump(mode="json")
        except ValidationError:
            rust("event", missing, valid=False)
        else:
            assert rust("event", missing) == expected, (kind, key)


def test_cpu_evidence_reason_vocab_and_all_measurement_predicates(
    native_proofs: list[dict[str, Any]],
) -> None:
    data = event_data("host.result", native_proofs)
    for index in range(7):
        bad = copy.deepcopy(data)
        bad["body"]["cpu"]["sources"][index]["observed"] = 0
        with pytest.raises(ValidationError):
            HostEvent.model_validate(bad)
        rust("event", bad, valid=False)
    bad = copy.deepcopy(data)
    bad["body"]["cpu"]["online_cpu_ids"] = [0, 1, 1, 3]
    with pytest.raises(ValidationError):
        HostEvent.model_validate(bad)
    rust("event", bad, valid=False)
    # Partial observed frequency remains valid; topology and max require complete.
    partial = copy.deepcopy(data)
    partial["body"]["cpu"]["sources"][2].update(status="partial", observed=2, reason="incomplete_coverage")
    assert rust("event", partial) == HostEvent.model_validate(partial).model_dump(mode="json")
    for reason in host_events.UnavailableReason:
        skipped = event_data("instrument.skipped", native_proofs)
        skipped["body"]["unavailable"][0]["reason"] = reason.value
        assert rust("event", skipped) == HostEvent.model_validate(skipped).model_dump(mode="json")
    for source in host_events.CaptureSource:
        skipped = event_data("instrument.skipped", native_proofs)
        skipped["body"]["unavailable"][0]["source"] = source.value
        assert rust("event", skipped) == HostEvent.model_validate(skipped).model_dump(mode="json")
    for code in host_events.ProtocolFaultCode:
        fault = event_data("protocol.fault", native_proofs)
        fault["body"]["code"] = code.value
        assert rust("event", fault) == HostEvent.model_validate(fault).model_dump(mode="json")


def test_routine_ci_prepares_pinned_binary_before_offline_and_full_python_suites() -> None:
    import tomllib

    import yaml  # type: ignore[import-untyped]

    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_bytes())
    gates = workflow["jobs"]["gates"]
    steps = gates["steps"]
    preparation = next(step for step in steps if step.get("name") == "Pinned locked Rust preparation")
    offline = next(step for step in steps if step.get("name") == "Offline Rust module gates")
    python_tests = next(step for step in steps if step.get("name") == "Tests, including the five injection canaries")
    assert steps.index(preparation) < steps.index(offline) < steps.index(python_tests)
    assert preparation["working-directory"] == offline["working-directory"] == "backend/rust/host-telemetry"
    assert "cargo fetch --locked" in preparation["run"]
    assert "cargo build --locked --all-targets" in preparation["run"]
    assert "cargo clippy --locked --offline --all-targets -- -D warnings" in offline["run"]
    assert "cargo test --locked --offline" in offline["run"]
    assert offline["env"]["CARGO_NET_OFFLINE"] == "true"
    assert "pytest --junitxml=" in python_tests["run"], "Keep the existing full backend merge suite."
    pin = tomllib.loads((ROOT / "backend/rust/host-telemetry/rust-toolchain.toml").read_text())
    assert pin["toolchain"]["channel"] == "1.95.0"
