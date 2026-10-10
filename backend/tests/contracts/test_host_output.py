"""Do the isolated output candidates enforce AN/AO/H15/H16 without public changes?"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import FIXTURES_DIR
from pydantic import ValidationError

from idhazh.contracts import host_output
from idhazh.contracts.base import Contract, ServerJob
from idhazh.contracts.file_envelope import (
    Compression,
    FileEnvelope,
    Format,
    RowIdentity,
    WriterIdentity,
)
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.host_output import (
    HOST_OUTPUT_VERSION,
    HOST_PRODUCER,
    INT64_MAX,
    LEGACY_HOST_VERSIONS,
    CandidateFileEnvelope,
    CorrectedHostFingerprintRow,
    HostFingerprintInput,
    HostPlannedFile,
    HostPublicationReceipt,
    HostStoredRow,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
    LegacyHostFingerprintRow,
    canonical_host_rows,
    fingerprint_v1,
    fingerprint_v2,
    host_file_id,
    host_unit_id,
    normalize_host_row,
    normalize_stored_host_rows,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.ledger import arrow_schema, filenames, json_lines, parquet, paths
from idhazh.ledger.persist import file_columns
from idhazh.telemetry.silicon import fingerprint_of

pytestmark = pytest.mark.contract

BASE = {"date": "2026-10-10", "run_id": "2026-10-10-17", "shard": 0}


@pytest.mark.parametrize("field", ("measured_at", "cpu_target_measured_at"))
@pytest.mark.parametrize(
    "stamp",
    ("2026-02-30T12:00:00Z", "2026-10-10T25:99:99Z", "2026-10-10T12:60:00Z"),
)
def test_candidate_refuses_impossible_probe_and_target_instants(field: str, stamp: str) -> None:
    payload = BASE | {field: stamp}
    if field == "cpu_target_measured_at":
        payload["cpu_quota_state"] = "unavailable"
    with pytest.raises(ValueError):
        CorrectedHostFingerprintRow.model_validate(payload)


REMOVED = {"cores", "threads", "mhz_max", "mhz_at_probe"}
ADDED = {
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
INTEGERS = (
    "shard",
    "cpu_family",
    "cpu_model_number",
    "cpu_stepping",
    "cpu_physical_cores",
    "cpu_logical_processors",
    "cpu_allowed_processors",
    "l3_cache_bytes",
    "memcpy_probe_mib",
    "job_seconds",
    "server_prompt_tokens",
)
FLOATS = (
    "cpu_quota_cores",
    "cpu_observed_mhz",
    "cpu_reported_max_mhz",
    "boot_seconds",
    "memcpy_gib_s",
    "model_load_ms",
    "server_prompt_seconds",
)
WRITERS = (
    ("idhazh.ledger.parquet", Format.PARQUET),
    ("idhazh_rust.ledger.parquet", Format.PARQUET),
    ("idhazh.ledger.json_lines", Format.JSON),
    ("idhazh_rust.ledger.json_lines", Format.JSON),
)


def fixture(name: str) -> dict[str, Any]:
    data = json.loads((FIXTURES_DIR / "host-events" / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def identity(*, producer: str = HOST_PRODUCER, **changes: Any) -> HostWriterIdentity:
    return HostWriterIdentity.model_validate(
        {
            "run_id": BASE["run_id"],
            "attempt": 1,
            "job": "work",
            "shard": 0,
            "producer": producer,
            "git_sha": "a" * 40,
            **changes,
        }
    )


def stored(*, day: str = "2026-10-10", **changes: Any) -> HostStoredRow:
    unit = host_unit_id(covers=day, identity=identity())
    return HostStoredRow.model_validate(
        {
            **BASE,
            "date": day,
            "ledger": "host-fingerprint",
            "covers": day,
            "attempt": 1,
            "unit_id": str(unit),
            **changes,
        }
    )


def planned_file(
    *,
    day: str = "2026-10-10",
    fmt: Format = Format.JSON,
    writer: str | None = None,
    clock: int = 1791633601000,
    **cells: Any,
) -> HostPlannedFile:
    row = stored(day=day, **cells)
    unit = uuid.UUID(row.unit_id)
    file_id = host_file_id(unit=unit, attempt=1, written_at_ms=clock)
    env = CandidateFileEnvelope.model_validate(
        {
            "row_schema_version": HOST_OUTPUT_VERSION,
            "tier": "raw",
            "ledger": "host-fingerprint",
            "covers": day,
            "written_at_ms": clock,
            "identity": identity().model_dump(),
            "unit_id": unit,
            "file_id": file_id,
            "content_sha256": hashlib.sha256(canonical_host_rows((row,))).hexdigest(),
            "writer": writer
            or ("idhazh.ledger.parquet" if fmt is Format.PARQUET else "idhazh.ledger.json_lines"),
            "writer_version": (
                "fixture-native-engine"
                if writer is not None and writer.startswith("idhazh_rust.")
                else (
                    parquet.engine_version()
                    if fmt is Format.PARQUET
                    else json_lines.engine_version()
                )
            ),
            "compression": "none",
        }
    )
    suffix = ".parquet" if fmt is Format.PARQUET else ".json"
    return HostPlannedFile(
        envelope=env,
        format=fmt,
        relative_path=f"raw/host-fingerprint/{day.replace('-', '/')}/{file_id}{suffix}",
        rows=(row,),
    )


def plan(*files: HostPlannedFile, **changes: Any) -> HostWritePlan:
    return HostWritePlan.model_validate(
        {
            "event_id": "00000000-0000-4000-8000-000000000001",
            "target_root": "state",
            "publication_identity": identity(producer="stages.work").model_dump(),
            "files": files or (planned_file(),),
            **changes,
        }
    )


def completion(plan: HostWritePlan, **changes: Any) -> HostWriteCompletion:
    return HostWriteCompletion.model_validate(
        {
            "event_id": plan.event_id,
            "receipt": {
                "identity": plan.publication_identity.model_dump(),
                "writes": {
                    f"{plan.target_root}/{file.relative_path}": "b" * 64 for file in plan.files
                },
            },
            **changes,
        }
    )


def original_stored(payload: Mapping[str, Any]) -> dict[str, Any]:
    day = payload["date"]
    return {
        **payload,
        "ledger": "host-fingerprint",
        "covers": day,
        "attempt": 1,
        "job": payload.get("job", "work"),
        "unit_id": str(host_unit_id(covers=day, identity=identity())),
    }


def test_full_field_order_baseline_annotations_defaults_and_arrow_types() -> None:
    expected: list[str] = []
    for name in HostFingerprintRow.model_fields:
        if name == "cores":
            expected.extend(
                (
                    "cpu_physical_cores",
                    "cpu_logical_processors",
                    "cpu_allowed_processors",
                    "cpu_quota_cores",
                    "cpu_quota_state",
                    "cpu_target_measured_at",
                )
            )
        elif name == "mhz_max":
            expected.extend(("cpu_observed_mhz", "cpu_reported_max_mhz"))
        elif name not in REMOVED:
            expected.append(name)
            if name == "fingerprint":
                expected.append("fingerprint_version")
    assert list(CorrectedHostFingerprintRow.model_fields) == expected
    row = CorrectedHostFingerprintRow.model_validate(BASE)
    assert row.version == HOST_OUTPUT_VERSION
    assert row.job is ServerJob.WORK
    assert row.flags == ""
    for name, field in HostFingerprintRow.model_fields.items():
        if name not in REMOVED | {"version"}:
            candidate = CorrectedHostFingerprintRow.model_fields[name]
            assert candidate.annotation == field.annotation, name
            assert candidate.default == field.default, name
            assert candidate.is_required() == field.is_required(), name
    assert all(getattr(row, name) is None for name in ADDED)
    schema = CorrectedHostFingerprintRow.json_schema()
    assert schema["version"] == HOST_OUTPUT_VERSION
    assert schema["changelog"][0]["version"] == HOST_OUTPUT_VERSION
    assert schema["additionalProperties"] is False
    assert not REMOVED.intersection(schema["properties"])
    assert row.csv_columns() == tuple(expected)
    assert row.csv_row()["cpu_logical_processors"] == ""
    assert not REMOVED.intersection(row.csv_row())
    columns = arrow_schema.columns_of(CorrectedHostFingerprintRow)
    old_columns = {column.name: column for column in arrow_schema.columns_of(HostFingerprintRow)}
    for column in columns:
        if column.name not in ADDED | {"version"}:
            assert column == old_columns[column.name]
    types = {column.name: column.type for column in columns}
    assert all(types[name] is arrow_schema.ColumnType.INT64 for name in INTEGERS)
    assert all(types[name] is arrow_schema.ColumnType.FLOAT64 for name in FLOATS)
    assert types["fingerprint_version"] is arrow_schema.ColumnType.INT64
    assert arrow_schema.columns_of(HostStoredRow) == file_columns(CorrectedHostFingerprintRow)


@pytest.mark.parametrize("name", INTEGERS)
@pytest.mark.parametrize("value", [True, False, "1", 1.0, 1.5, INT64_MAX + 1, -(1 << 63) - 1])
def test_count_and_baseline_integer_fields_refuse_coercion_and_overflow(
    name: str, value: Any
) -> None:
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate({**BASE, name: value})


@pytest.mark.parametrize("name", FLOATS)
@pytest.mark.parametrize(
    "value", [True, False, "2.5", float("nan"), float("inf"), -float("inf"), 10**400]
)
def test_all_float_fields_are_finite_and_refuse_boolean_or_string_numbers(
    name: str, value: Any
) -> None:
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate({**BASE, name: value})


@pytest.mark.parametrize(
    "name", ("cpu_physical_cores", "cpu_logical_processors", "cpu_allowed_processors")
)
def test_corrected_counts_are_positive_int64_and_nullable(name: str) -> None:
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate({**BASE, name: 0})
    assert getattr(CorrectedHostFingerprintRow.model_validate({**BASE, name: None}), name) is None
    cells = {
        **BASE,
        "cpu_logical_processors": INT64_MAX,
        name: INT64_MAX,
        "cpu_quota_state": "unavailable",
        "cpu_target_measured_at": "2026-10-10T12:00:01Z",
    }
    assert getattr(CorrectedHostFingerprintRow.model_validate(cells), name) == INT64_MAX


@pytest.mark.parametrize(
    "name", ("cpu_quota_cores", "cpu_observed_mhz", "cpu_reported_max_mhz", "memcpy_gib_s")
)
@pytest.mark.parametrize("value", [0, -0.5])
def test_positive_float_measurements_do_not_use_zero_as_unknown(name: str, value: float) -> None:
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate({**BASE, name: value})


def test_unchanged_zero_and_signed_baseline_fields_are_not_reinterpreted() -> None:
    cells = {
        "cpu_family": -1,
        "cpu_model_number": -2,
        "cpu_stepping": -3,
        "l3_cache_bytes": 0,
        "memcpy_probe_mib": 0,
        "boot_seconds": 0,
        "model_load_ms": 0,
        "job_seconds": 0,
        "server_prompt_tokens": 0,
        "server_prompt_seconds": 0,
    }
    old = HostFingerprintRow.model_validate(BASE | cells)
    candidate = CorrectedHostFingerprintRow.model_validate(BASE | cells)
    assert all(getattr(old, name) == getattr(candidate, name) for name in cells)
    assert HostFingerprintRow.model_validate(BASE | {"shard": "1"}).shard == 1
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate(BASE | {"shard": "1"})


@pytest.mark.parametrize(
    "cells",
    [
        {"cpu_physical_cores": 5, "cpu_logical_processors": 4},
        {
            "cpu_allowed_processors": 5,
            "cpu_logical_processors": 4,
            "cpu_quota_state": "unlimited",
            "cpu_target_measured_at": "2026-10-10T12:00:01Z",
        },
        {"cpu_allowed_processors": 1},
        {
            "cpu_allowed_processors": 1,
            "cpu_quota_state": "unavailable",
            "cpu_target_measured_at": "2026-10-10T12:00:01Z",
        },
        {"cpu_quota_cores": 0.5},
        {"cpu_quota_state": "finite", "cpu_target_measured_at": "2026-10-10T12:00:01Z"},
        {
            "cpu_quota_cores": 0.5,
            "cpu_quota_state": "unlimited",
            "cpu_target_measured_at": "2026-10-10T12:00:01Z",
        },
        {
            "cpu_quota_cores": 0.5,
            "cpu_quota_state": "unavailable",
            "cpu_target_measured_at": "2026-10-10T12:00:01Z",
        },
        {"cpu_quota_state": "unknown"},
        {"cpu_quota_state": "unlimited"},
        {"cpu_target_measured_at": "2026-10-10T12:00:01Z"},
        {
            "cpu_quota_state": "unlimited",
            "cpu_target_measured_at": "2026-10-10T11:59:59Z",
            "measured_at": "2026-10-10T12:00:00Z",
        },
    ],
)
def test_quota_states_target_capture_and_counts_cannot_contradict(cells: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate(BASE | cells)


def test_snapshot_fixture_independent_counts_fractional_quota_and_no_fabrication() -> None:
    snapshots = fixture("cpu-snapshots.json")
    assert snapshots["version"] == HOST_OUTPUT_VERSION
    rows = [
        CorrectedHostFingerprintRow.model_validate(case["row"]) for case in snapshots["snapshots"]
    ]
    probe, target, unlimited, unavailable, changed = rows
    source = snapshots["snapshots"][0]
    assert probe.cpu_logical_processors == len(source["online_ids"])
    assert probe.cpu_physical_cores == len({tuple(pair) for pair in source["package_core_pairs"]})
    assert probe.cpu_observed_mhz == sum(source["valid_observed_mhz"]) / len(
        source["valid_observed_mhz"]
    )
    source = snapshots["snapshots"][1]
    assert target.cpu_allowed_processors == len(
        set(source["online_ids"])
        & set(source["affinity_ids"])
        & set(source["effective_cpuset_ids"])
    )
    assert target.cpu_quota_cores == source["quota_us"] / source["period_us"] == 0.5
    assert probe.cpu_target_measured_at is None and probe.cpu_quota_state is None
    assert unlimited.cpu_quota_cores is unavailable.cpu_quota_cores is None
    assert unlimited.cpu_quota_state != unavailable.cpu_quota_state
    assert changed.cpu_quota_cores == 8 and changed.cpu_logical_processors is None
    assert changed.cpu_allowed_processors is None


@pytest.mark.parametrize("version", [None, True, False, "1", 1.0, 0, 3])
def test_fingerprint_algorithm_labels_are_paired_strict_and_finite(version: Any) -> None:
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate(
            BASE | {"fingerprint": "a" * 16, "fingerprint_version": version}
        )


@pytest.mark.parametrize("version", [1, 2])
def test_fingerprint_label_without_hash_is_refused(version: int) -> None:
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate(BASE | {"fingerprint_version": version})


def test_fingerprint_golden_preimages_match_both_algorithms_and_unchanged_reference() -> None:
    vectors = fixture("fingerprint-versions.json")
    assert vectors["version"] == HOST_OUTPUT_VERSION
    for vector in vectors["vectors"]:
        legacy = LegacyHostFingerprintRow.model_validate(
            {
                **BASE,
                "version": "2026-09-20",
                **vector["facts"],
            }
        )
        assert fingerprint_v1(legacy) == fingerprint_of(vector["facts"]) == vector["v1"]
        preimage = vector["v1_preimage"].encode("ascii")
        assert not preimage.endswith(b"\n")
        assert hashlib.sha256(preimage).hexdigest()[:16] == vector["v1"]
        facts = {
            key: value for key, value in vector["facts"].items() if key not in {"cores", "threads"}
        }
        row = CorrectedHostFingerprintRow.model_validate(BASE | facts)
        assert fingerprint_v2(row) == vector["v2"]
        preimage = vector["v2_preimage"].encode("ascii")
        assert json.loads(preimage) == {key: row.model_dump()[key] for key in json.loads(preimage)}
        if vector["v2"] is not None:
            assert hashlib.sha256(preimage).hexdigest()[:16] == vector["v2"]
            validated = CorrectedHostFingerprintRow.model_validate(
                {
                    **BASE,
                    **facts,
                    "fingerprint": vector["v2"],
                    "fingerprint_version": 2,
                }
            )
            assert validated.fingerprint != vector["v1"]
        else:
            with pytest.raises(ValidationError):
                CorrectedHostFingerprintRow.model_validate(
                    {
                        **BASE,
                        **facts,
                        "fingerprint": hashlib.sha256(preimage).hexdigest()[:16],
                        "fingerprint_version": 2,
                    }
                )


def test_v2_excludes_dynamic_measurements_and_keeps_unicode_exact() -> None:
    base = CorrectedHostFingerprintRow.model_validate(BASE | {"cpu_model": "Xeon \u00e9"})
    changed = CorrectedHostFingerprintRow.model_validate(
        {
            **base.model_dump(),
            "cpu_model": "Xeon \u00e9",
            "cpu_physical_cores": 2,
            "cpu_logical_processors": 4,
            "cpu_allowed_processors": 3,
            "cpu_quota_cores": 0.5,
            "cpu_quota_state": "finite",
            "cpu_target_measured_at": "2026-10-10T12:00:01Z",
            "cpu_observed_mhz": 1000.0,
            "cpu_reported_max_mhz": 3600.0,
            "microcode": "new",
            "runner_name": "another",
            "vm_size": "new",
            "boot_seconds": 5,
            "memcpy_gib_s": 2,
            "job_seconds": 42,
        }
    )
    assert fingerprint_v2(base) == fingerprint_v2(changed)
    decomposed = CorrectedHostFingerprintRow.model_validate(BASE | {"cpu_model": "Xeon e\u0301"})
    assert fingerprint_v2(base) != fingerprint_v2(decomposed)
    with pytest.raises(ValidationError):
        CorrectedHostFingerprintRow.model_validate(
            {
                **BASE,
                "cpu_model": "Xeon",
                "fingerprint": "a" * 16,
                "fingerprint_version": 2,
            }
        )
    for flags in ("avx512f avx2", "avx2 avx2", "unknown", " avx2"):
        with pytest.raises(ValueError, match="flags"):
            fingerprint_v2(CorrectedHostFingerprintRow.model_validate(BASE | {"flags": flags}))


@pytest.mark.parametrize("version", LEGACY_HOST_VERSIONS)
def test_each_declared_historical_schema_normalizes_only_legitimate_average(version: str) -> None:
    payload = fixture("cpu-snapshots.json")["legacy_row"] | {"version": version}
    if version < "2026-09-18":
        payload.pop("job_seconds")
    old = dict(payload)
    row = normalize_host_row(payload)
    assert payload == old
    assert row.version == HOST_OUTPUT_VERSION
    assert row.fingerprint == old["fingerprint"] and row.fingerprint_version == 1
    assert row.cpu_observed_mhz == 2500
    assert row.memcpy_probe_mib == 512
    assert row.measured_at == old["measured_at"]
    assert not REMOVED.intersection(row.model_dump())
    assert all(
        getattr(row, name) is None for name in ADDED - {"fingerprint_version", "cpu_observed_mhz"}
    )


def test_absent_legacy_average_and_fingerprint_are_not_invented() -> None:
    row = normalize_host_row(
        {"version": "2026-09-20", **BASE, "mhz_max": 3000, "cores": 32, "threads": 4}
    )
    assert row.cpu_observed_mhz is None
    assert row.fingerprint is None
    assert row.fingerprint_version is None
    assert row.cpu_reported_max_mhz is row.cpu_physical_cores is row.cpu_logical_processors is None


@pytest.mark.parametrize(
    "changes",
    [
        {"version": "2026-09-15"},
        {"version": "2026-10-11"},
        {"version": HOST_OUTPUT_VERSION},
        {"unrecognized": None},
        {"cpu_logical_processors": 4},
        {"mhz_at_probe": "2500"},
        {"mhz_at_probe": float("nan")},
        {"mhz_max": float("inf")},
        {"cores": True},
        {"threads": 1.5},
        {"cores": INT64_MAX + 1},
        {"version": "2026-09-18", "server_prompt_tokens": None},
        {"version": "2026-09-17", "job_seconds": None},
        {"version": "2026-09-16", "job": "assemble"},
    ],
)
def test_unknown_mixed_and_invalid_legacy_input_is_not_projected_away(
    changes: dict[str, Any],
) -> None:
    payload = fixture("cpu-snapshots.json")["legacy_row"] | changes
    with pytest.raises(ValueError):
        normalize_host_row(payload)


def test_input_adapter_recognizes_only_the_exact_unstamped_probe_before_auto_stamp() -> None:
    old = HostFingerprintRow.model_validate(
        fixture("cpu-snapshots.json")["legacy_row"]
    ).model_dump()
    for key in (
        "version",
        "model_load_ms",
        "job_seconds",
        "server_prompt_tokens",
        "server_prompt_seconds",
    ):
        old.pop(key)
    untouched = dict(old)
    row = HostFingerprintInput.model_validate(old)
    assert old == untouched
    assert row.fingerprint_version == 1 and row.mhz_at_probe == 2500
    assert "mhz_at_probe" not in HostFingerprintInput.model_fields
    assert "mhz_at_probe" not in row.json_schema()["properties"]
    assert "mhz_at_probe" not in row.csv_columns()
    assert "mhz_at_probe" not in {
        column.name for column in arrow_schema.columns_of(HostFingerprintInput)
    }
    with pytest.raises(ValidationError):
        row.mhz_at_probe = 1  # type: ignore[misc]
    for bad in (
        BASE,
        old | {"unknown": 1},
        old | {"cpu_quota_state": None},
        {key: value for key, value in old.items() if key != "mhz_max"},
    ):
        with pytest.raises(ValueError, match="unstamped"):
            HostFingerprintInput.model_validate(bad)
    assert (
        HostFingerprintInput.model_validate(
            CorrectedHostFingerprintRow.model_validate(BASE).model_dump()
        ).version
        == HOST_OUTPUT_VERSION
    )


def test_stored_digest_and_identity_are_checked_before_defaults_or_migration() -> None:
    original = original_stored(fixture("cpu-snapshots.json")["legacy_row"])
    digest = hashlib.sha256(json_lines.rows_bytes([original])).hexdigest()
    rows = normalize_stored_host_rows([original], content_sha256=digest)
    assert rows[0].fingerprint_version == 1
    assert rows[0].attempt == 1
    assert rows[0].unit_id == original["unit_id"]
    assert hashlib.sha256(canonical_host_rows(rows)).hexdigest() != digest
    with pytest.raises(ValueError, match="original stored host content_sha256"):
        normalize_stored_host_rows([original | {"unknown": 1}], content_sha256=digest)
    with pytest.raises(ValueError, match="original stored host identity"):
        bad = original | {"covers": "2026-10-09", "unknown": 1}
        normalize_stored_host_rows(
            [bad], content_sha256=hashlib.sha256(json_lines.rows_bytes([bad])).hexdigest()
        )
    with pytest.raises(ValueError, match="original stored host unit_id"):
        bad = original | {"unit_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "wrong")), "unknown": 1}
        normalize_stored_host_rows(
            [bad], content_sha256=hashlib.sha256(json_lines.rows_bytes([bad])).hexdigest()
        )
    for key, value in (
        ("attempt", True),
        ("attempt", 1.5),
        ("shard", "0"),
        ("attempt", INT64_MAX + 1),
        ("ledger", "item-health"),
    ):
        bad = original | {key: value}
        with pytest.raises(ValueError):
            normalize_stored_host_rows(
                [bad], content_sha256=hashlib.sha256(json_lines.rows_bytes([bad])).hexdigest()
            )


@pytest.mark.parametrize(("writer", "fmt"), WRITERS)
def test_explicit_writer_container_pairs_and_unchanged_envelope_key_sets(
    writer: str, fmt: Format
) -> None:
    env = planned_file(fmt=fmt, writer=writer).envelope
    assert env.validate_container(fmt) is env
    assert set(CandidateFileEnvelope.model_fields) == set(FileEnvelope.model_fields)
    python_env = env.model_dump() | {
        "writer": "idhazh.ledger.parquet" if fmt is Format.PARQUET else "idhazh.ledger.json_lines"
    }
    assert set(env.as_metadata()) == set(FileEnvelope.model_validate(python_env).as_metadata())
    assert CandidateFileEnvelope.from_metadata(env.as_metadata()) == env
    with pytest.raises(ValueError, match="container"):
        env.validate_container(Format.JSON if fmt is Format.PARQUET else Format.PARQUET)
    with pytest.raises(ValueError):
        env.validate_container("csv")  # type: ignore[arg-type]
    if writer.startswith("idhazh_rust"):
        with pytest.raises(ValidationError):
            FileEnvelope.model_validate(env.model_dump())
    else:
        assert FileEnvelope.model_validate(env.model_dump()).writer == writer


@pytest.mark.parametrize(
    "changes",
    [
        {"version": "2026-10-06"},
        {"version": "2026-10-11"},
        {"row_schema_version": "2026-09-20"},
        {"row_schema_version": "2026-10-11"},
        {"ledger": "item-health"},
        {"tier": "compact", "period": "daily"},
        {"period": "daily"},
        {"built_from": 0},
        {"written_at_ms": True},
        {"written_at_ms": INT64_MAX + 1},
        {"writer": "idhazh_rust.ledger.arbitrary"},
        {"writer": "idhazh.ledger.unknown"},
        {"writer_version": ""},
        {"unexpected": "metadata"},
    ],
)
def test_native_provenance_requires_explicit_corrected_host_raw_scope(
    changes: dict[str, Any],
) -> None:
    env = planned_file(writer="idhazh_rust.ledger.json_lines").envelope
    with pytest.raises(ValidationError):
        CandidateFileEnvelope.model_validate(env.model_dump() | changes)


@pytest.mark.parametrize("compression", [Compression.SNAPPY, Compression.ZSTD])
def test_json_lines_cannot_claim_compression(compression: Compression) -> None:
    env = planned_file().envelope
    with pytest.raises(ValidationError):
        CandidateFileEnvelope.model_validate(env.model_dump() | {"compression": compression})
    parquet_env = planned_file(fmt=Format.PARQUET).envelope
    assert (
        CandidateFileEnvelope.model_validate(
            parquet_env.model_dump() | {"compression": compression}
        ).compression
        is compression
    )


@pytest.mark.parametrize("key", [b"attempt", b"shard", b"written_at_ms", b"built_from"])
@pytest.mark.parametrize("value", [b"True", b"+1", b" 1", b"1.0", "\u0661".encode()])
def test_metadata_integer_decoding_is_explicit_ascii_not_hidden_coercion(
    key: bytes, value: bytes
) -> None:
    metadata = planned_file().envelope.as_metadata() | {key: value}
    with pytest.raises(ValueError, match="ASCII decimal"):
        CandidateFileEnvelope.from_metadata(metadata)


def test_unit_and_file_ids_match_the_existing_namespace_and_clock_algorithm() -> None:
    for attempt in (1, 2, INT64_MAX):
        ident = identity(attempt=attempt, job="assemble", shard=7)
        for clock in (0, 1791633601000, INT64_MAX):
            unit = host_unit_id(covers="2026-10-10", identity=ident)
            assert unit == filenames.unit_id(
                ledger="host-fingerprint",
                covers="2026-10-10",
                run_id=ident.run_id,
                job=ident.job.value,
                shard=ident.shard,
                producer=HOST_PRODUCER,
            )
            file_id = host_file_id(unit=unit, attempt=attempt, written_at_ms=clock)
            assert file_id == filenames.file_id(unit=unit, attempt=attempt, written_at_ms=clock)
            assert unit.version == 5 and file_id.version == 8
    assert host_unit_id(covers="2026-10-10", identity=identity()) == host_unit_id(
        covers="2026-10-10", identity=identity(attempt=2)
    )
    with pytest.raises(ValueError):
        host_unit_id(covers="2026-10-10", identity=identity(producer="idhazh_rust"))
    invalid_seeds: tuple[tuple[Any, Any], ...] = (
        (True, 1),
        (1, False),
        (1.0, 1),
        (0, 1),
        (1, -1),
        (1, INT64_MAX + 1),
    )
    for invalid_attempt, invalid_clock in invalid_seeds:
        with pytest.raises(ValueError):
            host_file_id(
                unit=uuid.uuid5(uuid.NAMESPACE_URL, "unit"),
                attempt=invalid_attempt,
                written_at_ms=invalid_clock,
            )


@pytest.mark.parametrize("field", ["attempt", "shard"])
@pytest.mark.parametrize("value", [True, "1", 1.5, INT64_MAX + 1])
def test_plan_identity_is_strict_without_changing_public_identity(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        HostWriterIdentity.model_validate(identity().model_dump() | {field: value})
    assert (
        WriterIdentity.model_validate(identity().model_dump() | {field: "1"}).model_dump()[field]
        == 1
    )


def test_immutable_plan_roundtrips_exact_paths_and_matches_public_raw_path_builder() -> None:
    held = plan(planned_file(), planned_file(day="2026-10-11", fmt=Format.PARQUET))
    assert HostWritePlan.from_json(held.to_json()) == held
    for file in held.files:
        expected = paths.raw_path(
            Path("state"),
            LedgerName.HOST_FINGERPRINT,
            date=file.envelope.covers,
            file_id=file.envelope.file_id,
            fmt=file.format,
        )
        assert f"{held.target_root}/{file.relative_path}" == expected.as_posix()
    assert held.publication_identity.producer == "stages.work"
    assert all(file.envelope.identity.producer == HOST_PRODUCER for file in held.files)
    for obj, name, value in (
        (held, "event_id", uuid.uuid4()),
        (held.publication_identity, "attempt", 2),
        (held.files[0], "relative_path", "raw/another.json"),
        (held.files[0].envelope, "written_at_ms", 1),
        (held.files[0].rows[0], "shard", 1),
    ):
        with pytest.raises(ValidationError):
            setattr(obj, name, value)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.json",
        "raw/other/2026/10/10/file.json",
        "raw/host-fingerprint/2026/10/09/file.json",
        "compact/host-fingerprint/daily/file.json",
        "raw\\host-fingerprint\\file.json",
        "/state/raw/file.json",
        "C:/state/raw/file.json",
    ],
)
def test_plan_refuses_unplanned_paths_and_container_suffixes(path: str) -> None:
    file = planned_file()
    with pytest.raises(ValueError):
        plan(HostPlannedFile.model_validate(file.model_dump() | {"relative_path": path}))


def test_trial_prefix_and_task_owned_state_root_preserve_tier_first_tree() -> None:
    file = planned_file()
    changed = HostPlannedFile.model_validate(
        file.model_dump()
        | {
            "relative_path": file.relative_path.replace(
                "raw/host-fingerprint/", "raw/trials/cpu/host-fingerprint/"
            ),
        }
    )
    trial = plan(
        changed,
        prefix=("trials", "cpu", "host-fingerprint"),
        target_root="backend/var/experiment/state",
    )
    assert trial.files[0].relative_path.startswith("raw/trials/cpu/host-fingerprint/")
    for prefix in (
        (),
        ("other",),
        ("../bad", "host-fingerprint"),
        ("trial/path", "host-fingerprint"),
    ):
        with pytest.raises(ValueError):
            plan(file, prefix=prefix)


@pytest.mark.parametrize("key", ["run_id", "attempt", "job", "shard", "git_sha"])
def test_ledger_and_publication_invocation_identities_are_checked_independently(key: str) -> None:
    changes = {
        "run_id": "2026-10-10-18",
        "attempt": 2,
        "job": "assemble",
        "shard": 1,
        "git_sha": "c" * 40,
    }
    with pytest.raises(ValueError, match="publication invocation"):
        plan(
            publication_identity=identity(
                producer="stages.work", **{key: changes[key]}
            ).model_dump()
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"content_sha256": "f" * 64},
        {"unit_id": uuid.uuid5(uuid.NAMESPACE_URL, "other")},
        {"file_id": uuid.uuid4()},
        {
            "file_id": filenames.file_id(
                unit=uuid.uuid5(uuid.NAMESPACE_URL, "other"), attempt=1, written_at_ms=1791633601000
            )
        },
        {"identity": {**identity().model_dump(), "producer": "idhazh_rust.ledger.json_lines"}},
        {"written_at_ms": 1791633601001},
    ],
)
def test_planned_file_refuses_hash_unit_file_clock_or_logical_producer_contradictions(
    changes: dict[str, Any],
) -> None:
    file = planned_file()
    with pytest.raises(ValueError):
        HostPlannedFile.model_validate(
            file.model_dump() | {"envelope": file.envelope.model_dump() | changes}
        )


def test_all_day_groups_are_validated_and_duplicate_keys_days_are_refused() -> None:
    file = planned_file()
    with pytest.raises(ValueError, match="duplicate"):
        plan(file, file)
    with pytest.raises(ValueError, match="duplicate row keys"):
        HostPlannedFile.model_validate(
            file.model_dump() | {"rows": [file.rows[0].model_dump()] * 2}
        )
    bad = planned_file(day="2026-10-12").model_dump()
    bad["envelope"]["content_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="canonical hash"):
        plan(files=[file.model_dump(), planned_file(day="2026-10-11").model_dump(), bad])
    assert plan(file).files == (file,)


def test_successor_requires_later_real_clock_and_retry_retains_immutable_plan() -> None:
    prior = plan()
    assert prior.validate_successor(prior) is prior
    next_event = "00000000-0000-4000-8000-000000000002"
    changed = plan(planned_file(clock=1791633601001, job_seconds=42), event_id=next_event)
    assert changed.validate_successor(prior) is changed
    for clock in (1791633601000, 1791633600999):
        with pytest.raises(ValueError, match="later clock"):
            plan(planned_file(clock=clock, job_seconds=42), event_id=next_event).validate_successor(
                prior
            )
    with pytest.raises(ValueError, match="new event"):
        plan(planned_file(clock=1791633601001, job_seconds=42)).validate_successor(prior)
    with pytest.raises(ValueError, match="identical retries"):
        plan(planned_file(clock=1791633601001)).validate_successor(prior)
    with pytest.raises(ValueError, match="identical retries"):
        plan(event_id=next_event).validate_successor(prior)


def test_successor_can_retain_unchanged_day_groups_without_rewriting_their_files() -> None:
    unchanged = planned_file(day="2026-10-11")
    prior = plan(planned_file(), unchanged)
    next_event = "00000000-0000-4000-8000-000000000002"
    successor = plan(
        planned_file(clock=1791633601001, job_seconds=42), unchanged, event_id=next_event
    )
    assert successor.validate_successor(prior) is successor
    rewritten = plan(
        planned_file(clock=1791633601001, job_seconds=42),
        planned_file(day="2026-10-11", clock=1791633601001),
        event_id=next_event,
    )
    with pytest.raises(ValueError, match="unchanged day groups"):
        rewritten.validate_successor(prior)


def test_successor_can_capture_first_target_but_never_refresh_probe_or_target_facts() -> None:
    initial = plan(planned_file(cpu_logical_processors=4, measured_at="2026-10-10T12:00:00Z"))
    target_cells: dict[str, Any] = {
        "cpu_logical_processors": 4,
        "measured_at": "2026-10-10T12:00:00Z",
        "cpu_allowed_processors": 2,
        "cpu_quota_state": "finite",
        "cpu_quota_cores": 0.5,
        "cpu_target_measured_at": "2026-10-10T12:00:01Z",
    }
    target = plan(
        planned_file(clock=1791633601001, **target_cells),
        event_id="00000000-0000-4000-8000-000000000002",
    )
    assert target.validate_successor(initial) is target
    clock = plan(
        planned_file(clock=1791633601002, job_seconds=42, **target_cells),
        event_id="00000000-0000-4000-8000-000000000003",
    )
    assert clock.validate_successor(target) is clock
    for key, value in (("cpu_observed_mhz", 2400), ("measured_at", "2026-10-10T12:00:01Z")):
        changed = plan(
            planned_file(clock=1791633601002, **(target_cells | {key: value})),
            event_id="00000000-0000-4000-8000-000000000003",
        )
        with pytest.raises(ValueError, match="original machine probe"):
            changed.validate_successor(target)
    for target_key, target_value in (
        ("cpu_allowed_processors", 3),
        ("cpu_quota_cores", 1.0),
        ("cpu_target_measured_at", "2026-10-10T12:00:02Z"),
    ):
        changed = plan(
            planned_file(clock=1791633601002, **(target_cells | {target_key: target_value})),
            event_id="00000000-0000-4000-8000-000000000003",
        )
        with pytest.raises(ValueError, match="frozen target capture"):
            changed.validate_successor(target)


def test_stored_hash_is_ordered_ascii_json_lines_not_a_fingerprint_or_file_id() -> None:
    rows = (stored(cpu_model="Xeon \u00e9"), stored(day="2026-10-11", cpu_family=0))
    canonical = canonical_host_rows(rows)
    assert canonical == json_lines.rows_bytes([row.model_dump(mode="json") for row in rows])
    assert canonical.endswith(b"\n") and b"\\u00e9" in canonical
    assert (
        hashlib.sha256(canonical).digest()
        != hashlib.sha256(canonical_host_rows(tuple(reversed(rows)))).digest()
    )
    assert not REMOVED.intersection(json.loads(canonical.splitlines()[0]))


def test_python_provenance_retains_non_host_compact_semantics_without_native_widening() -> None:
    env = planned_file(fmt=Format.PARQUET).envelope.model_dump() | {
        "version": FileEnvelope.schema_version(),
        "row_schema_version": "2026-10-01",
        "ledger": "item-health",
        "tier": "compact",
        "period": "daily",
        "built_from": 0,
    }
    public = FileEnvelope.model_validate(env)
    candidate = CandidateFileEnvelope.model_validate(env)
    assert candidate.as_metadata() == public.as_metadata()
    assert candidate.validate_container(Format.PARQUET) is candidate
    with pytest.raises(ValidationError, match="native writer"):
        CandidateFileEnvelope.model_validate(env | {"writer": "idhazh_rust.ledger.parquet"})


def test_candidate_metadata_refuses_missing_or_extra_keys_and_retains_historical_stamp() -> None:
    env = planned_file().envelope
    metadata = env.as_metadata()
    with pytest.raises(ValueError, match="does not declare"):
        CandidateFileEnvelope.from_metadata(metadata | {b"created_by": b"not-an-envelope-key"})
    missing = dict(metadata)
    missing.pop(b"schema_version")
    with pytest.raises(ValueError, match="missing required"):
        CandidateFileEnvelope.from_metadata(missing)
    historical = metadata | {
        b"envelope_version": b"2026-10-06",
        b"schema_version": b"2026-09-20",
    }
    assert CandidateFileEnvelope.from_metadata(historical).row_schema_version == "2026-09-20"


def test_completed_evidence_keeps_public_receipt_shape_and_is_deeply_immutable() -> None:
    held = plan()
    done = completion(held)
    assert done.validate_plan(held) is done
    assert HostWriteCompletion.from_json(done.to_json()) == done
    ordinary = PublicationReceipt.model_validate(done.receipt.model_dump())
    assert ordinary.model_dump() == done.receipt.model_dump()
    assert (
        HostPublicationReceipt.json_schema()["properties"].keys()
        == PublicationReceipt.json_schema()["properties"].keys()
    )
    assert ordinary.version == "2026-10-09"
    with pytest.raises(TypeError):
        done.receipt.writes["unplanned"] = "a" * 64  # type: ignore[index]
    with pytest.raises(ValidationError):
        done.receipt.identity.attempt = 2
    with pytest.raises(ValidationError):
        done.event_id = uuid.uuid4()
    before = dict(done.receipt.writes)
    mutable = dict(before)
    safe = HostPublicationReceipt(
        version="2026-10-09", identity=held.publication_identity, writes=mutable
    )
    mutable.clear()
    assert dict(safe.writes) == before
    frozen = HostWriteCompletion.model_validate(
        {
            "event_id": held.event_id,
            "receipt": ordinary,
        }
    )
    ordinary.writes.clear()
    ordinary.identity.attempt = 2
    assert dict(frozen.receipt.writes) == before
    assert frozen.receipt.identity.attempt == 1


def test_completion_checks_event_receipt_identity_membership_and_partial_recovery() -> None:
    held = plan(planned_file(), planned_file(day="2026-10-11"))
    with pytest.raises(ValueError, match="triggering event"):
        completion(held, event_id=uuid.uuid4()).validate_plan(held)
    wrong = completion(held).model_dump()
    wrong["receipt"]["identity"]["producer"] = "other"
    with pytest.raises(ValueError, match="publication invocation"):
        HostWriteCompletion.model_validate(wrong).validate_plan(held)
    partial = completion(held).model_dump()
    partial["receipt"]["writes"].pop(next(reversed(partial["receipt"]["writes"])))
    recovered = HostWriteCompletion.model_validate(partial)
    assert recovered.validate_plan(held, require_all=False) is recovered
    with pytest.raises(ValueError, match="omits planned"):
        recovered.validate_plan(held)
    forged = completion(held).model_dump()
    forged["receipt"]["writes"]["state/raw/unplanned.json"] = "f" * 64
    with pytest.raises(ValueError, match="unplanned"):
        HostWriteCompletion.model_validate(forged).validate_plan(held, require_all=False)
    for key in ("version", "writes"):
        bad = completion(held).model_dump()
        if key == "version":
            bad["receipt"]["version"] = HOST_OUTPUT_VERSION
        else:
            bad["receipt"]["writes"] = {"../escape": "a" * 64}
        with pytest.raises(ValidationError):
            HostWriteCompletion.model_validate(bad)


@pytest.mark.parametrize("fmt", [Format.JSON, Format.PARQUET])
def test_real_container_bytes_roundtrip_original_hash_and_physical_receipt(fmt: Format) -> None:
    file = planned_file(fmt=fmt, cpu_logical_processors=4, cpu_observed_mhz=2500)
    held = plan(file)
    cells = [row.model_dump(mode="json") for row in file.rows]
    if fmt is Format.JSON:
        data = json_lines.render(cells, envelope=file.envelope.as_metadata())
        metadata, decoded = json_lines.read(data)
    else:
        data = parquet.render(
            file_columns(CorrectedHostFingerprintRow),
            cells,
            envelope=file.envelope.as_metadata(),
            compression=file.envelope.compression,
        )
        metadata, decoded = parquet.read(data)
    observed = CandidateFileEnvelope.from_metadata(metadata).validate_container(fmt)
    rows = normalize_stored_host_rows(decoded, content_sha256=observed.content_sha256)
    assert rows == file.rows
    assert canonical_host_rows(rows) == json_lines.rows_bytes(decoded)
    physical = hashlib.sha256(data).hexdigest()
    assert physical != observed.content_sha256
    done = HostWriteCompletion(
        version="2026-10-10",
        event_id=held.event_id,
        receipt=HostPublicationReceipt(
            version="2026-10-09",
            identity=held.publication_identity,
            writes={f"{held.target_root}/{file.relative_path}": physical},
        ),
    )
    assert done.validate_plan(held) is done
    changed_metadata = observed.as_metadata() | {b"writer_version": b"another-engine"}
    if fmt is Format.JSON:
        other = json_lines.render(cells, envelope=changed_metadata)
    else:
        other = parquet.render(
            file_columns(CorrectedHostFingerprintRow),
            cells,
            envelope=changed_metadata,
            compression=Compression.NONE,
        )
    assert hashlib.sha256(other).hexdigest() != physical
    assert hashlib.sha256(json_lines.rows_bytes(cells)).hexdigest() == observed.content_sha256


def test_output_contract_has_one_way_imports_and_no_transport_or_verifier_dependency() -> None:
    tree = ast.parse(Path(inspect.getfile(host_output)).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.endswith(
                ("host_events", "host_output_verify", "host_event_files")
            )
            if node.module.startswith("idhazh."):
                assert node.module.startswith("idhazh.contracts.")
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith("idhazh.") for alias in node.names)
    assert CorrectedHostFingerprintRow.schema_version() == HOST_OUTPUT_VERSION
    assert FileEnvelope.schema_version() == "2026-10-06"
    assert HostFingerprintRow.schema_version() == "2026-09-20"
    assert set(HostStoredRow.model_fields) - set(CorrectedHostFingerprintRow.model_fields) == set(
        RowIdentity.model_fields
    ) - {"run_id", "job", "shard"}


@pytest.mark.parametrize("model", [CorrectedHostFingerprintRow, HostWritePlan, HostWriteCompletion])
def test_candidate_schema_dates_are_not_arbitrary_or_algorithm_numbers(
    model: type[Contract],
) -> None:
    payload = (
        CorrectedHostFingerprintRow.model_validate(BASE).model_dump()
        if model is CorrectedHostFingerprintRow
        else (plan().model_dump() if model is HostWritePlan else completion(plan()).model_dump())
    )
    for version in ("2026-10-09", "2026-10-11", 2, True):
        with pytest.raises(ValidationError):
            model.model_validate(payload | {"version": version})
