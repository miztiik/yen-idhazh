"""Does read-only verification refuse bad evidence on real generated container bytes?"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pyarrow
import pyarrow.parquet
import pytest
from pydantic import ValidationError

from idhazh.contracts.file_envelope import FileEnvelope, Format
from idhazh.contracts.host_output import (
    HOST_OUTPUT_VERSION,
    HOST_PRODUCER,
    LEGACY_HOST_VERSIONS,
    CandidateFileEnvelope,
    HostPlannedFile,
    HostStoredRow,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
    LegacyHostFingerprintRow,
    fingerprint_v1,
    host_file_id,
    host_unit_id,
)
from idhazh.ledger import json_lines, parquet
from idhazh.telemetry.host_output_verify import (
    HostOutputVerification,
    VerificationLimits,
    host_output_columns,
    load_verification_document,
    read_host_output,
    verify_host_output,
)

pytestmark = pytest.mark.contract
LIMITS = VerificationLimits(
    max_files=4,
    max_file_bytes=1_000_000,
    max_total_bytes=4_000_000,
    max_rows=4,
    max_footer_bytes=100_000,
    max_decode_bytes=2_000_000,
    max_thrift_items=1000,
    max_json_depth=12,
)


def identity(**changes: Any) -> HostWriterIdentity:
    return HostWriterIdentity.model_validate(
        {
            "run_id": "2026-10-10-17",
            "attempt": 1,
            "job": "work",
            "shard": 0,
            "producer": HOST_PRODUCER,
            "git_sha": "b" * 40,
            **changes,
        }
    )


def source_row(version: str = HOST_OUTPUT_VERSION, *, day: str = "2026-10-10") -> dict[str, Any]:
    writer = identity()
    unit = host_unit_id(covers=day, identity=writer)
    base = {
        "version": version,
        "date": day,
        "run_id": writer.run_id,
        "job": "work",
        "shard": 0,
        "cpu_model": "Recorded CPU \u03b1",
        "measured_at": "2026-10-10T12:00:00Z",
    }
    if version == HOST_OUTPUT_VERSION:
        row = HostStoredRow.model_validate(
            {
                **base,
                "ledger": "host-fingerprint",
                "covers": base["date"],
                "attempt": 1,
                "unit_id": str(unit),
            }
        ).model_dump(mode="json")
    else:
        old = LegacyHostFingerprintRow.model_validate(
            {
                **base,
                "fingerprint": "0" * 16,
                "cores": 2,
                "threads": 4,
                "mhz_max": 5000.0,
                "mhz_at_probe": 2300.0,
            }
        )
        row = old.model_dump(mode="json")
        row["fingerprint"] = fingerprint_v1(old)
        row = {c.name: row[c.name] for c in host_output_columns(version) if c.name in row}
        row.update(ledger="host-fingerprint", covers=base["date"], attempt=1, unit_id=str(unit))
    return row


def render_file(
    root: Path,
    fmt: Format = Format.JSON,
    *,
    rows: list[dict[str, Any]] | None = None,
    metadata_changes: dict[bytes, bytes] | None = None,
    columns: Any = None,
    native_candidate: bool = False,
    compression: str = "none",
    clock: int = 1791633601000,
) -> tuple[Path, CandidateFileEnvelope, bytes]:
    rows = rows if rows is not None else [source_row()]
    version = rows[0]["version"] if rows else HOST_OUTPUT_VERSION
    day = rows[0]["date"] if rows else "2026-10-10"
    unit = host_unit_id(covers=day, identity=identity())
    file_id = host_file_id(unit=unit, attempt=1, written_at_ms=clock)
    writer = ("idhazh_rust" if native_candidate else "idhazh") + (
        ".ledger.parquet" if fmt is Format.PARQUET else ".ledger.json_lines"
    )
    envelope = CandidateFileEnvelope.model_validate(
        {
            "version": HOST_OUTPUT_VERSION,
            "row_schema_version": version,
            "tier": "raw",
            "ledger": "host-fingerprint",
            "covers": day,
            "written_at_ms": clock,
            "identity": identity(),
            "unit_id": unit,
            "file_id": file_id,
            "content_sha256": hashlib.sha256(json_lines.rows_bytes(rows)).hexdigest(),
            "writer": writer,
            # This is candidate envelope coverage, never a claimed Rust codec.
            "writer_version": (
                "candidate-only"
                if native_candidate
                else parquet.engine_version()
                if fmt is Format.PARQUET
                else json_lines.engine_version()
            ),
            "compression": compression,
        }
    )
    metadata = envelope.as_metadata() | (metadata_changes or {})
    if fmt is Format.JSON:
        data = json_lines.render(rows, envelope=metadata)
    else:
        data = parquet.render(
            host_output_columns(version) if columns is None else columns,
            rows,
            envelope=metadata,
            compression=envelope.compression,
        )
    suffix = ".parquet" if fmt is Format.PARQUET else ".json"
    path = root / "raw" / "host-fingerprint" / Path(*day.split("-")) / f"{file_id}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path, envelope, data


def evidence(
    workspace: Path, fmt: Format = Format.JSON, **options: Any
) -> tuple[HostWritePlan, HostWriteCompletion, Path, bytes]:
    root = workspace / "state"
    path, envelope, data = render_file(root, fmt, **options)
    planned = HostPlannedFile(
        envelope=envelope,
        format=fmt,
        relative_path=path.relative_to(root).as_posix(),
        rows=(HostStoredRow.model_validate(options.get("rows", [source_row()])[0]),),
    )
    plan = HostWritePlan.model_validate(
        {
            "event_id": uuid.UUID("00000000-0000-4000-8000-000000000001"),
            "target_root": "state",
            "publication_identity": identity(producer="stages.work"),
            "files": (planned,),
        }
    )
    completion = HostWriteCompletion.model_validate(
        {
            "event_id": plan.event_id,
            "receipt": {
                "identity": plan.publication_identity,
                "writes": {f"state/{planned.relative_path}": hashlib.sha256(data).hexdigest()},
            },
        }
    )
    return plan, completion, path, data


def verify(
    workspace: Path, plan: HostWritePlan, completion: HostWriteCompletion, **options: Any
) -> HostOutputVerification:
    return verify_host_output(
        plan,
        completion,
        workspace_root=workspace,
        target_root="state",
        publication_identity=identity(producer="stages.work"),
        limits=LIMITS,
        **options,
    )


@pytest.mark.parametrize("fmt", list(Format))
def test_exact_bytes_are_verified_without_writes(tmp_path: Path, fmt: Format) -> None:
    plan, completion, path, data = evidence(tmp_path, fmt)
    before = path.stat()
    result = verify(tmp_path, plan, completion)
    assert result.complete and result.planned_files == 1
    assert result.files[0].rows == plan.files[0].rows
    assert result.files[0].physical_sha256 == hashlib.sha256(data).hexdigest()
    assert result.files[0].created_by == (
        f"parquet-cpp-arrow version {parquet.engine_version()}" if fmt is Format.PARQUET else None
    )
    assert path.read_bytes() == data
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("version", LEGACY_HOST_VERSIONS)
@pytest.mark.parametrize("fmt", list(Format))
def test_original_legacy_digest_precedes_normalization(
    tmp_path: Path, version: str, fmt: Format
) -> None:
    original = source_row(version)
    path, env, data = render_file(tmp_path, fmt, rows=[original])
    result = read_host_output(path, root=tmp_path, limits=LIMITS)
    row = result.rows[0]
    assert row.version == HOST_OUTPUT_VERSION
    assert row.fingerprint_version == 1
    assert row.fingerprint == original["fingerprint"]
    assert row.cpu_observed_mhz == 2300.0
    assert row.cpu_physical_cores is None and row.cpu_reported_max_mhz is None
    assert (
        hashlib.sha256(json_lines.rows_bytes([row.model_dump(mode="json")])).hexdigest()
        != env.content_sha256
    )
    assert path.read_bytes() == data
    path, _, broken = render_file(
        tmp_path,
        fmt,
        rows=[original],
        metadata_changes={
            b"content_sha256": b"0" * 64,
        },
    )
    with pytest.raises(ValueError, match="original stored host content_sha256"):
        read_host_output(path, root=tmp_path, limits=LIMITS)
    assert path.read_bytes() == broken


def test_generated_jsonl_exercises_only_the_native_candidate_envelope(tmp_path: Path) -> None:
    plan, completion, path, data = evidence(tmp_path, native_candidate=True)
    result = verify(tmp_path, plan, completion)
    assert result.files[0].envelope.writer == "idhazh_rust.ledger.json_lines"
    assert result.files[0].created_by is None
    with pytest.raises(ValidationError):
        FileEnvelope.from_metadata(plan.files[0].envelope.as_metadata())
    assert path.read_bytes() == data


def test_python_parquet_bytes_cannot_pass_as_native_created_by(tmp_path: Path) -> None:
    plan, completion, path, data = evidence(tmp_path, Format.PARQUET, native_candidate=True)
    with pytest.raises(ValueError, match="created_by"):
        verify(tmp_path, plan, completion)
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "changes",
    [
        {b"writer": b"idhazh.ledger.anything"},
        {b"writer": b"idhazh.ledger.parquet"},
        {b"schema_version": b"2026-10-11"},
        {b"envelope_version": b"2026-10-11"},
        {b"tier": b"compact", b"period": b"daily"},
        {b"producer": b"telemetry.host"},
        {b"ledger": b"item-health"},
        {b"written_at_ms": b"1791633601001"},
        {b"attempt": b"9223372036854775808"},
        {b"shard": b"+0"},
        {b"unknown": b"value"},
    ],
)
def test_finite_provenance_schema_tier_and_identity_pairs(
    tmp_path: Path, changes: dict[bytes, bytes]
) -> None:
    path, _, _ = render_file(tmp_path, metadata_changes=changes)
    with pytest.raises(ValueError):
        read_host_output(path, root=tmp_path, limits=LIMITS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cpu_logical_processors", True),
        ("cpu_logical_processors", 1.5),
        ("cpu_logical_processors", "4"),
        ("cpu_logical_processors", 1 << 63),
        ("cpu_quota_cores", "1.5"),
        ("fingerprint_version", True),
        ("job_seconds", 1 << 63),
        ("measured_at", "2026-99-99T12:00:00Z"),
        ("unit_id", str(uuid.uuid5(uuid.NAMESPACE_URL, "foreign"))),
        ("run_id", "2026-10-10-18"),
        ("attempt", 2),
        ("version", "2026-09-20"),
    ],
)
def test_malformed_rows_are_not_coerced_or_dropped(tmp_path: Path, field: str, value: Any) -> None:
    row = source_row()
    row[field] = value
    # Keep the corrected declared schema even when the stored row stamp is forged.
    path, _, _ = render_file(
        tmp_path,
        rows=[row],
        metadata_changes={
            b"schema_version": HOST_OUTPUT_VERSION.encode(),
        },
    )
    with pytest.raises(ValueError):
        read_host_output(path, root=tmp_path, limits=LIMITS)


@pytest.mark.parametrize(
    "rows",
    [
        [source_row(), source_row()],
        [source_row(), source_row("2026-09-20")],
        [source_row() | {"arbitrary": None}],
        [{key: value for key, value in source_row().items() if key != "flags"}],
    ],
)
def test_duplicate_mixed_or_unknown_stored_rows_are_refused(
    tmp_path: Path, rows: list[dict[str, Any]]
) -> None:
    path, _, _ = render_file(tmp_path, rows=rows)
    with pytest.raises(ValueError):
        read_host_output(path, root=tmp_path, limits=LIMITS)


@pytest.mark.parametrize("kind", ["order", "type", "nullability"])
def test_parquet_schema_is_checked_before_row_coercion(tmp_path: Path, kind: str) -> None:
    columns = list(host_output_columns(HOST_OUTPUT_VERSION))
    if kind == "order":
        columns[0], columns[1] = columns[1], columns[0]
    else:
        from idhazh.ledger.arrow_schema import Column, ColumnType

        index = next(i for i, c in enumerate(columns) if c.name == "shard")
        columns[index] = Column(
            "shard",
            ColumnType.FLOAT64 if kind == "type" else ColumnType.INT64,
            kind == "nullability",
        )
    path, _, _ = render_file(tmp_path, Format.PARQUET, columns=columns)
    with pytest.raises(ValueError, match="column types, order or nullability"):
        read_host_output(path, root=tmp_path, limits=LIMITS)


@pytest.mark.parametrize("compression", ["none", "zstd", "snappy"])
def test_actual_parquet_compression_and_engine_metadata(tmp_path: Path, compression: str) -> None:
    path, _, _ = render_file(tmp_path, Format.PARQUET, compression=compression)
    assert (
        read_host_output(path, root=tmp_path, limits=LIMITS).envelope.compression.value
        == compression
    )
    path, _, _ = render_file(
        tmp_path,
        Format.PARQUET,
        compression=compression,
        metadata_changes={b"writer_version": b"fiction"},
    )
    with pytest.raises(ValueError, match="created_by"):
        read_host_output(path, root=tmp_path, limits=LIMITS)
    path, _, _ = render_file(
        tmp_path,
        Format.PARQUET,
        compression=compression,
        metadata_changes={b"compression": b"none" if compression != "none" else b"zstd"},
    )
    with pytest.raises(ValueError, match="compression"):
        read_host_output(path, root=tmp_path, limits=LIMITS)


def test_conflicting_parquet_footer_and_arrow_schema_metadata(tmp_path: Path) -> None:
    path, env, _ = render_file(tmp_path, Format.PARQUET)
    schema = parquet.schema_of(host_output_columns(HOST_OUTPUT_VERSION)).with_metadata(
        env.as_metadata()
    )
    sink = pyarrow.BufferOutputStream()
    with pyarrow.parquet.ParquetWriter(sink, schema, compression=None) as writer:
        writer.write_table(pyarrow.Table.from_pylist([source_row()], schema=schema))
        writer.add_key_value_metadata({b"producer": b"foreign"})
    path.write_bytes(sink.getvalue().to_pybytes())
    with pytest.raises(ValueError, match="metadata conflict"):
        read_host_output(path, root=tmp_path, limits=LIMITS)


@pytest.mark.parametrize(
    "limit",
    [
        "max_file_bytes",
        "max_rows",
        "max_footer_bytes",
        "max_decode_bytes",
        "max_thrift_items",
    ],
)
def test_parquet_bounds_precede_row_loading(tmp_path: Path, limit: str) -> None:
    rows = [source_row(), source_row()] if limit == "max_rows" else None
    path, _, data = render_file(tmp_path, Format.PARQUET, rows=rows)
    with pytest.raises((ValueError, OSError)):
        read_host_output(path, root=tmp_path, limits=replace(LIMITS, **{limit: 1}))
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "transform",
    [
        lambda data: data[:-1],
        lambda data: data.replace(b"\n", b"\r\n"),
        lambda data: data.replace(b'"shard":0', b'"shard":0,"shard":0'),
        lambda data: data.replace(b'"cpu_quota_cores":null', b'"cpu_quota_cores":NaN'),
        lambda data: data.replace(b'"cpu_quota_cores":null', b'"cpu_quota_cores":1e999'),
        lambda data: data.replace(b'"cpu_model":', b'"cpu_model" :'),
    ],
)
def test_jsonl_malformed_physical_bytes_are_not_repaired(tmp_path: Path, transform: Any) -> None:
    path, _, data = render_file(tmp_path)
    broken = transform(data)
    path.write_bytes(broken)
    with pytest.raises(ValueError):
        read_host_output(path, root=tmp_path, limits=LIMITS)
    assert path.read_bytes() == broken


def test_forged_footer_length_and_json_depth_are_bounded(tmp_path: Path) -> None:
    path, _, data = render_file(tmp_path, Format.PARQUET)
    path.write_bytes(data[:-8] + (0xFFFFFFFF).to_bytes(4, "little") + b"PAR1")
    with pytest.raises(ValueError, match="footer"):
        read_host_output(path, root=tmp_path, limits=LIMITS)
    document = tmp_path / "nested.json"
    document.write_bytes(b'{"files":' + b"[" * 20 + b"]" * 20 + b"}")
    with pytest.raises(ValueError, match="nesting limit"):
        load_verification_document(document, root=tmp_path, limits=LIMITS)


@pytest.mark.parametrize("change", ["hash", "event", "path", "missing", "attempt", "git_sha"])
def test_stale_foreign_forged_or_missing_completion(tmp_path: Path, change: str) -> None:
    plan, completion, _, _ = evidence(tmp_path)
    payload = completion.model_dump(mode="json")
    writes = payload["receipt"]["writes"]
    if change == "hash":
        writes[next(iter(writes))] = "0" * 64
    elif change == "event":
        payload["event_id"] = str(uuid.uuid4())
    elif change == "path":
        payload["receipt"]["writes"] = {"state/raw/foreign.json": "0" * 64}
    elif change == "missing":
        payload["receipt"]["writes"] = {}
    else:
        payload["receipt"]["identity"][change] = 2 if change == "attempt" else "a" * 40
    with pytest.raises(ValueError):
        verify(tmp_path, plan, HostWriteCompletion.model_validate(payload))


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", "2026-10-10-18"),
        ("attempt", 2),
        ("job", "runtime"),
        ("shard", 1),
        ("git_sha", "a" * 40),
        ("producer", "stages.other"),
    ],
)
def test_plan_and_receipt_cannot_supply_their_own_invocation_authority(
    tmp_path: Path, field: str, value: Any
) -> None:
    plan, completion, _, _ = evidence(tmp_path)
    with pytest.raises(ValueError, match="foreign root or publication"):
        verify_host_output(
            plan,
            completion,
            workspace_root=tmp_path,
            target_root="state",
            limits=LIMITS,
            publication_identity=identity(producer="stages.work", **{field: value})
            if field != "producer"
            else identity(producer=value),
        )


def test_partial_completion_is_explicit_and_never_certifies_all_files(tmp_path: Path) -> None:
    plan, completion, _, _ = evidence(tmp_path)
    payload = completion.model_dump(mode="json")
    payload["receipt"]["writes"] = {}
    partial = HostWriteCompletion.model_validate(payload)
    result = verify(tmp_path, plan, partial, require_all=False)
    assert result.files == () and not result.complete and result.planned_files == 1


def test_out_of_root_moved_file_and_linked_ancestor_are_refused(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan, completion, path, _ = evidence(workspace)
    with pytest.raises(ValueError, match="outside"):
        read_host_output(path, root=tmp_path / "other", limits=LIMITS)
    moved = path.with_name(str(uuid.uuid4()) + path.suffix)
    path.rename(moved)
    with pytest.raises(ValueError, match="path contradicts"):
        read_host_output(moved, root=workspace / "state", limits=LIMITS)
    moved.rename(path)
    original = workspace / "state"
    outside = workspace / "other-state"
    original.rename(outside)
    # Windows junctions require no elevated symlink privilege.
    if sys.platform == "win32":
        command = f'New-Item -ItemType Junction -Path "{original}" -Target "{outside}" | Out-Null'
        subprocess.run(["powershell", "-NoProfile", "-Command", command], check=True)
    else:
        original.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match="symlink or reparse"):
            verify(workspace, plan, completion)
    finally:
        if sys.platform == "win32":
            original.rmdir()
        else:
            original.unlink()


def test_named_plan_document_bounds_and_revalidation(tmp_path: Path) -> None:
    plan, completion, _, _ = evidence(tmp_path)
    named = tmp_path / "plan.json"
    payload = plan.model_dump(mode="json")
    payload["files"] *= LIMITS.max_files + 1
    named.write_text(json.dumps(payload), encoding="ascii")
    with pytest.raises(ValueError, match="file count"):
        load_verification_document(named, root=tmp_path, limits=LIMITS)
    forged = plan.model_copy(update={"target_root": "../foreign"})
    with pytest.raises(ValueError):
        verify(tmp_path, forged, completion)
    with pytest.raises(ValueError, match="total byte"):
        verify_host_output(
            plan,
            completion,
            workspace_root=tmp_path,
            target_root="state",
            publication_identity=identity(producer="stages.work"),
            limits=replace(LIMITS, max_total_bytes=1),
        )


def test_cli_loads_named_documents_and_does_not_modify_them(tmp_path: Path) -> None:
    plan, completion, path, data = evidence(tmp_path)
    plan_path, completion_path = tmp_path / "plan.json", tmp_path / "completion.json"
    plan_path.write_text(json.dumps(plan.model_dump(mode="json")), encoding="ascii", newline="\n")
    completion_path.write_text(completion.model_dump_json(), encoding="ascii", newline="\n")
    before = {p: p.read_bytes() for p in (plan_path, completion_path, path)}
    cli = Path(__file__).parents[1] / "utilities" / "verify_host_output.py"
    command = [
        sys.executable,
        str(cli),
        "--workspace-root",
        str(tmp_path),
        "--target-root",
        "state",
        "--plan",
        "plan.json",
        "--completion",
        "completion.json",
        "--run-id",
        identity().run_id,
        "--attempt",
        "1",
        "--job",
        "work",
        "--shard",
        "0",
        "--git-sha",
        identity().git_sha,
        "--publication-producer",
        "stages.work",
    ]
    for key, value in asdict(LIMITS).items():
        command.extend(["--" + key.replace("_", "-"), str(value)])
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout)["complete"] is True
    assert before == {p: p.read_bytes() for p in before}
    path.write_bytes(data + b"\n")
    failed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert failed.returncode == 1 and json.loads(failed.stdout)["verified"] is False
    assert path.read_bytes() == data + b"\n"


@pytest.mark.parametrize("limit", ["max_file_bytes", "max_footer_bytes", "max_decode_bytes"])
def test_jsonl_byte_bounds_are_checked_before_decode(tmp_path: Path, limit: str) -> None:
    path, _, data = render_file(tmp_path)
    with pytest.raises(ValueError, match="limit"):
        read_host_output(path, root=tmp_path, limits=replace(LIMITS, **{limit: 1}))
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "bad",
    [
        {"files": None},
        {"files": "not-a-list"},
        {"receipt": None},
        {"receipt": {"writes": []}},
        {"files": [{"rows": "not-a-list"}]},
        {"files": [{"rows": [{}] * 5}]},
    ],
)
def test_named_documents_refuse_bad_shapes_before_contract_loading(
    tmp_path: Path, bad: dict[str, Any]
) -> None:
    path = tmp_path / "document.json"
    path.write_bytes(json.dumps(bad).encode())
    with pytest.raises(ValueError):
        load_verification_document(path, root=tmp_path, limits=LIMITS)


def test_multi_day_partial_completion_and_file_count_bound(tmp_path: Path) -> None:
    plan, completion, _, _ = evidence(tmp_path)
    path, envelope, data = render_file(
        tmp_path / "state", Format.PARQUET, rows=[source_row(day="2026-10-11")]
    )
    second = HostPlannedFile.model_validate(
        {
            "envelope": envelope,
            "format": "parquet",
            "relative_path": path.relative_to(tmp_path / "state").as_posix(),
            "rows": [source_row(day="2026-10-11")],
        }
    )
    plan = HostWritePlan.model_validate(plan.model_dump() | {"files": (*plan.files, second)})
    partial = verify(tmp_path, plan, completion, require_all=False)
    assert len(partial.files) == 1 and not partial.complete
    payload = completion.model_dump(mode="json")
    payload["receipt"]["writes"][f"state/{second.relative_path}"] = hashlib.sha256(data).hexdigest()
    completion = HostWriteCompletion.model_validate(payload)
    assert verify(tmp_path, plan, completion).complete
    with pytest.raises(ValueError, match="file count"):
        verify_host_output(
            plan,
            completion,
            workspace_root=tmp_path,
            target_root="state",
            publication_identity=identity(producer="stages.work"),
            limits=replace(LIMITS, max_files=1),
        )
    path.write_bytes(b"{" * (LIMITS.max_file_bytes + 1))
    with pytest.raises(ValueError, match="file byte limit"):
        verify(tmp_path, plan, completion)


def test_enrichment_requires_later_clock_and_frozen_probe(tmp_path: Path) -> None:
    before, _, _, _ = evidence(tmp_path)
    later_row = source_row() | {"job_seconds": 1}
    later, completion, _, _ = evidence(
        tmp_path, rows=[later_row], clock=before.files[0].envelope.written_at_ms + 1
    )
    later = HostWritePlan.model_validate(later.model_dump() | {"event_id": uuid.uuid4()})
    completion = HostWriteCompletion.model_validate(
        completion.model_dump() | {"event_id": later.event_id}
    )
    assert verify(tmp_path, later, completion, previous_plan=before).complete
    assert verify(tmp_path, later, completion, previous_plan=later).complete
    same_clock, completion, _, _ = evidence(tmp_path, rows=[later_row])
    same_clock = HostWritePlan.model_validate(same_clock.model_dump() | {"event_id": uuid.uuid4()})
    completion = HostWriteCompletion.model_validate(
        completion.model_dump() | {"event_id": same_clock.event_id}
    )
    with pytest.raises(ValueError, match="strictly later clock"):
        verify(tmp_path, same_clock, completion, previous_plan=before)
    changed_probe, completion, _, _ = evidence(
        tmp_path,
        rows=[later_row | {"cpu_model": "Other CPU"}],
        clock=before.files[0].envelope.written_at_ms + 2,
    )
    changed_probe = HostWritePlan.model_validate(
        changed_probe.model_dump() | {"event_id": uuid.uuid4()}
    )
    completion = HostWriteCompletion.model_validate(
        completion.model_dump() | {"event_id": changed_probe.event_id}
    )
    with pytest.raises(ValueError, match="cannot remeasure"):
        verify(tmp_path, changed_probe, completion, previous_plan=before)


@pytest.mark.parametrize("limit", [0, -1, True, 1 << 63])
def test_limits_cannot_be_disabled_or_overflow(limit: Any) -> None:
    with pytest.raises(ValueError):
        replace(LIMITS, max_files=limit)
