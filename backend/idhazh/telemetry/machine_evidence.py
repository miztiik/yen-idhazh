"""How do exact machine readings travel without changing their original writer?"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, overload

from idhazh import ledger
from idhazh.atomic_write import write_atomic, write_atomic_bytes
from idhazh.contracts.file_envelope import FileEnvelope, Format, RowIdentity, Tier, WriterIdentity
from idhazh.contracts.host_fingerprint import (
    HOST_HARDWARE_VERSION,
    HostFingerprintRow,
    HostHardwareRow,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.contracts.task_performance import TaskPerformanceKind, TaskPerformanceRow
from idhazh.ledger.filenames import file_id, unit_id
from idhazh.publication_paths import IntegrityError, contains, safe_file
from idhazh.telemetry import machine_api
from idhazh.telemetry.silicon import CLOCK_CELLS

HOST: Final = LedgerName.HOST_FINGERPRINT
TASK: Final = LedgerName.TASK_PERFORMANCE
STATE = Path(ledger.STATE_DIRNAME)
NATIVE_PARQUET = "idhazh_typescript.ledger.parquet"


def raw_scope(name: LedgerName, day: str) -> str:
    return (ledger.raw_root(STATE, name) / day.replace("-", "/")).as_posix()


def verified_raw(
    root: Path, relative: str, data: bytes, *, name: LedgerName, date: str,
    identity: WriterIdentity,
) -> tuple[FileEnvelope, list[dict[str, object]]]:
    """Verify the exact named Parquet's envelope, row digest and writer."""
    from idhazh.ledger import json_lines, parquet

    meta, rows = parquet.read(data)
    envelope = FileEnvelope.from_metadata(meta).validate_container(Format.PARQUET)
    expected_unit = unit_id(
        ledger=name, covers=date, run_id=identity.run_id, job=identity.job,
        pipeline_name=identity.pipeline_name, task_name=identity.task_name,
        shard=identity.shard, producer=identity.producer,
    )
    expected_file = file_id(
        unit=expected_unit, attempt=identity.attempt, written_at_ms=envelope.written_at_ms,
    )
    want = ledger.raw_path(root, name, date, expected_file).relative_to(root).as_posix()
    if (
        relative != want or envelope.tier is not Tier.RAW or envelope.ledger != name
        or envelope.covers != date or envelope.identity != identity
        or envelope.unit_id != expected_unit or envelope.file_id != expected_file
        or len(rows) != 1
        or hashlib.sha256(json_lines.rows_bytes(rows)).hexdigest() != envelope.content_sha256
    ):
        raise IntegrityError(
            "completed raw file does not match its exact path or writer", (relative,),
        )
    return envelope, rows


@dataclass(frozen=True, slots=True)
class ExpectedFile:
    """Admitted work, determined without reading an artifact or a receipt."""

    writer: WriterIdentity
    date: str
    kind: TaskPerformanceKind | None = None
    subject: str | None = None
    native: bool = False

    @property
    def ledger(self) -> LedgerName:
        return HOST if self.kind is None else TASK

    @property
    def receipt(self) -> str:
        key = self.writer.task_key
        return f"machine-receipts/{self.date}/{key}-{self.writer.shard}-{self.ledger}.json"


@dataclass(frozen=True, slots=True)
class VerifiedFile:
    path: str
    data: bytes
    sha256: str
    envelope: FileEnvelope
    row: HostFingerprintRow | HostHardwareRow | TaskPerformanceRow

    def place(self, root: Path) -> Path | None:
        """Copy only the original bytes; report which new file needs caller cleanup."""
        target = safe_file(root, self.path, exists=False)
        if target.exists():
            if safe_file(root, self.path, exists=True).read_bytes() != self.data:
                raise IntegrityError(
                    "completed file would replace different local bytes", (self.path,),
                )
            return None
        write_atomic_bytes(target, self.data)
        return target

    def save_receipt(self, root: Path, expected: ExpectedFile) -> None:
        self.place(root)
        write_atomic(
            safe_file(root, expected.receipt, exists=False),
            PublicationReceipt(
                version=PublicationReceipt.schema_version(),
                identity=expected.writer,
                writes={self.path: self.sha256},
            ).to_json(),
        )


@overload
def verified_reading(
    path: str, data: bytes, *, name: Literal[LedgerName.HOST_FINGERPRINT], date: str,
    identity: WriterIdentity, kind: None = None, subject: str | None = None,
) -> tuple[FileEnvelope, HostFingerprintRow | HostHardwareRow]: ...


@overload
def verified_reading(
    path: str, data: bytes, *, name: Literal[LedgerName.TASK_PERFORMANCE], date: str,
    identity: WriterIdentity, kind: TaskPerformanceKind, subject: str | None = None,
) -> tuple[FileEnvelope, TaskPerformanceRow]: ...


def verified_reading(
    path: str, data: bytes, *, name: LedgerName, date: str,
    identity: WriterIdentity, kind: TaskPerformanceKind | None = None, subject: str | None = None,
) -> tuple[FileEnvelope, HostFingerprintRow | HostHardwareRow | TaskPerformanceRow]:
    envelope, (cells,) = verified_raw(
        STATE, path, data, name=name, date=date, identity=identity,
    )
    row_model = (
        HostHardwareRow if name is HOST and envelope.row_schema_version == HOST_HARDWARE_VERSION
        else HostFingerprintRow if name is HOST
        else TaskPerformanceRow
    )
    row = row_model.model_validate({
        key: value for key, value in cells.items()
        if key not in RowIdentity.model_fields or key in row_model.model_fields
    })
    stamped = RowIdentity.model_validate({key: cells.get(key) for key in RowIdentity.model_fields})
    if (
        row.version != envelope.row_schema_version
        or (row.date, row.run_id, row.pipeline_name, row.task_name, row.shard) != (
            date, identity.run_id, identity.pipeline_name, identity.task_name, identity.shard,
        )
        or stamped != RowIdentity(
            ledger=name, covers=date, unit_id=str(envelope.unit_id), run_id=identity.run_id,
            attempt=identity.attempt, job=identity.job, shard=identity.shard,
            pipeline_name=identity.pipeline_name, task_name=identity.task_name,
        )
    ):
        raise IntegrityError("completed row does not match its recorded task", (path,))
    if isinstance(row, HostHardwareRow):
        if row.job != identity.job or envelope.writer != NATIVE_PARQUET:
            raise IntegrityError("hardware capture is not from the native runner", (path,))
    elif isinstance(row, HostFingerprintRow):
        if row.job != identity.job or any(getattr(row, field) is not None for field in CLOCK_CELLS):
            raise IntegrityError("fingerprint is not the execution's opening capture", (path,))
    elif (
        envelope.writer != NATIVE_PARQUET or row.task_kind != kind
        or (subject is not None and row.subject_id != subject)
    ):
        raise IntegrityError("Task Performance file does not match its native task", (path,))
    return envelope, row


def verify_file(
    root: Path, path: str, expected: ExpectedFile, *, sha256: str | None = None,
) -> VerifiedFile:
    if not contains(raw_scope(expected.ledger, expected.date), path):
        raise IntegrityError("machine receipt is outside its admitted raw day", (path,))
    data = safe_file(root, path, exists=True).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if sha256 is not None and digest != sha256:
        raise IntegrityError("completed write bytes changed", (path,))
    relative = path.removeprefix(f"{STATE}/")
    envelope, row = (
        verified_reading(relative, data, name=HOST, date=expected.date, identity=expected.writer)
        if expected.kind is None
        else verified_reading(
            relative, data, name=TASK, date=expected.date, identity=expected.writer,
            kind=expected.kind, subject=expected.subject,
        )
    )
    if expected.native and envelope.writer != NATIVE_PARQUET:
        raise IntegrityError("opening fingerprint did not use the native writer", (path,))
    return VerifiedFile(path, data, digest, envelope, row)


def verify_capture(
    state: Path, response: machine_api.Captured, expected: ExpectedFile,
) -> VerifiedFile:
    if expected.kind is not None or len(response.files) != 1:
        raise IntegrityError("native fingerprint must return one completed file")
    (receipt,) = response.files
    relative = ledger.raw_path(
        STATE, HOST, expected.date, receipt.file_id,
    ).relative_to(STATE).as_posix()
    if receipt.path != relative or receipt.covers != expected.date:
        raise IntegrityError("native fingerprint receipt is outside its exact raw path")
    data = safe_file(state, relative, exists=True).read_bytes()
    envelope, row = verified_reading(
        relative, data, name=HOST, date=expected.date, identity=expected.writer,
    )
    if (
        row != response.row or str(envelope.unit_id) != receipt.unit_id
        or envelope.content_sha256 != receipt.content_sha256
    ):
        raise IntegrityError("native fingerprint receipt does not match the completed file")
    return VerifiedFile(f"state/{relative}", data, hashlib.sha256(data).hexdigest(), envelope, row)


def capture_opening(
    repo: Path, destination: Path, expected: ExpectedFile, *, ask_placement: bool = True,
) -> VerifiedFile | None:
    """Retain exactly the native opening receipt before the listener goes away."""
    client = machine_api.MachineApi.for_job()
    if client is None:
        machine_api.warn(
            f"Opening fingerprint unavailable for {expected.writer.task_key}: no listener"
        )
        return None
    response = client.fingerprint(expected.date, expected.writer, ask_placement=ask_placement)
    if not isinstance(response, machine_api.Captured):
        return None
    proof = verify_capture(machine_api.private_state(repo), response, expected)
    proof.save_receipt(destination, expected)
    return proof


def read_receipt(root: Path, expected: ExpectedFile) -> VerifiedFile | None:
    target = safe_file(root, expected.receipt, exists=False)
    if not target.exists():
        return None
    receipt = PublicationReceipt.read(safe_file(root, expected.receipt, exists=True))
    if receipt.identity != expected.writer or len(receipt.writes) != 1:
        raise IntegrityError("machine receipt does not name its exact writer and one file")
    (path, digest), = receipt.writes.items()
    return verify_file(root, path, expected, sha256=digest)


def verify_host_link(proof: VerifiedFile, opening: VerifiedFile | None) -> None:
    expected = None if opening is None else str(opening.envelope.unit_id)
    if isinstance(proof.row, TaskPerformanceRow) and proof.row.host_unit_id != expected:
        raise IntegrityError("Task Performance host reference lacks verified opening evidence")
