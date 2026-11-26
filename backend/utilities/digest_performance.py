"""Which exact Host Probes files may a digest job hand to publication?"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from idhazh import ledger
from idhazh.atomic_write import write_atomic_bytes
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import FileEnvelope, RowIdentity, WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.task_performance import TaskPerformanceOutcome, TaskPerformanceRow
from idhazh.ledger.staging import staged_path
from idhazh.telemetry import machine_api, silicon
from utilities import publication_evidence
from utilities.publication_request import IntegrityError, contains, safe_file
from utilities.publication_request import relative as relative_path

LOG = logging.getLogger(__name__)
PIPELINE = "digest"
SERVE = "serve-summarizer"
RECORD = "task-performance"
TASKS = {
    ServerJob.PLAN: ("plan",),
    ServerJob.WORK: ("work", SERVE),
    ServerJob.ASSEMBLE: ("assemble",),
}
TASK_LEDGER = LedgerName.TASK_PERFORMANCE
HOST_LEDGER = LedgerName.HOST_FINGERPRINT


@dataclass(frozen=True, slots=True)
class OpeningCapture:
    unit_id: str
    path: str
    sha256: str


def raw_scope(repo: Path, name: LedgerName, day: str) -> str:
    return (ledger.raw_root(repo / "state", name) / day.replace("-", "/")).relative_to(
        repo
    ).as_posix()


def approved_scope(job: str, day: str) -> tuple[str, ...]:
    return (f"{staged_path(TASK_LEDGER)}/{day.replace('-', '/')}",) if job in TASKS else ()


def task_writer(job: WriterIdentity, task: str) -> WriterIdentity:
    if job.job is None or task not in TASKS[ServerJob(job.job)]:
        raise IntegrityError("task is not declared for this digest publication job")
    return WriterIdentity.for_pipeline_task(
        run_id=job.run_id, attempt=job.attempt, shard=job.shard, git_sha=job.git_sha,
        pipeline_name=PIPELINE, task_name=task, producer=machine_api.PRODUCER,
    )


def _opening_writer(job: WriterIdentity) -> WriterIdentity:
    if job.job is None:
        raise IntegrityError("opening fingerprint requires its digest job")
    return WriterIdentity.for_pipeline_task(
        run_id=job.run_id, attempt=job.attempt, shard=job.shard, git_sha=job.git_sha,
        pipeline_name=PIPELINE, task_name=job.job, producer=silicon.PRODUCER,
    )


def opening_capture(
    repo: Path, job: WriterIdentity, date: str, *, private_state: Path | None = None,
) -> OpeningCapture | None:
    """Reuse a named, verified pipeline-scoped opening file, without recapturing."""
    identity = _opening_writer(job)
    receipt = publication_evidence.receipt_path(repo, identity, "fingerprint")
    if not receipt.is_file():
        if private_state is not None:
            legacy = publication_evidence.receipt_path(repo, job, "fingerprint")
            reason = "host_capture_unscoped" if legacy.is_file() else "host_capture_missing"
            LOG.info("Task Performance host reference unavailable: %s", reason)
        return None
    writes = publication_evidence.read_receipt(receipt, identity).writes
    if not writes:
        return None
    if len(writes) != 1:
        raise IntegrityError("opening fingerprint must name one completed file")
    (path, digest), = writes.items()
    if not contains(raw_scope(repo, HOST_LEDGER, date), path):
        raise IntegrityError("opening fingerprint is outside its admitted raw day", (path,))
    read_path = safe_file(repo, path, exists=True)
    data = read_path.read_bytes()
    if digest != hashlib.sha256(data).hexdigest():
        raise IntegrityError("opening fingerprint bytes changed", (path,))
    envelope, _ = publication_evidence.verified_raw(
        repo / "state", path.removeprefix("state/"), data, name=HOST_LEDGER,
        date=date, identity=identity,
    )
    (stored,) = ledger.load_stored([read_path], model=HostFingerprintRow)
    if (
        stored.identity != _row_identity(envelope, identity)
        or (
            stored.row.date, stored.row.run_id, stored.row.pipeline_name,
            stored.row.task_name, stored.row.shard,
        ) != (date, identity.run_id, PIPELINE, identity.task_name, identity.shard)
        or any(getattr(stored.row, field) is not None for field in silicon.CLOCK_CELLS)
    ):
        raise IntegrityError("fingerprint is not the execution's opening capture", (path,))
    if private_state is not None:
        _copy_exact(private_state, path.removeprefix("state/"), data)
    return OpeningCapture(str(envelope.unit_id), path, digest)


def _copy_exact(root: Path, path: str, data: bytes) -> None:
    target = safe_file(root, path, exists=False)
    if not target.exists():
        write_atomic_bytes(target, data)
    elif target.read_bytes() != data:
        raise IntegrityError("completed file would replace different local bytes", (path,))


def _row_identity(envelope: FileEnvelope, writer: WriterIdentity) -> RowIdentity:
    return RowIdentity(
        ledger=envelope.ledger, covers=envelope.covers, unit_id=str(envelope.unit_id),
        run_id=writer.run_id, attempt=writer.attempt, job=writer.job, shard=writer.shard,
        pipeline_name=writer.pipeline_name, task_name=writer.task_name,
    )


def _verified_task(
    root: Path, path: str, data: bytes, *, identity: WriterIdentity, date: str,
) -> tuple[TaskPerformanceRow, str, str]:
    envelope, (cells,) = publication_evidence.verified_raw(
        root, path, data, name=TASK_LEDGER, date=date, identity=identity,
    )
    if envelope.writer != "idhazh_typescript.ledger.parquet":
        raise IntegrityError("Task Performance file did not come from the native writer", (path,))
    row = TaskPerformanceRow.model_validate({
        key: cells[key] for key in TaskPerformanceRow.model_fields if key in cells
    })
    stamped = RowIdentity.model_validate({key: cells.get(key) for key in RowIdentity.model_fields})
    if (
        row.version != envelope.row_schema_version
        or (row.date, row.run_id, row.pipeline_name, row.task_name, row.shard) != (
            date, identity.run_id, identity.pipeline_name, identity.task_name, identity.shard,
        )
        or stamped != _row_identity(envelope, identity)
        or row.task_kind != ("model-serving" if identity.task_name == SERVE else "workflow-task")
    ):
        raise IntegrityError("Task Performance row does not match its recorded task", (path,))
    return row, str(envelope.unit_id), envelope.content_sha256


def retain(
    repo: Path, private_state: Path, *, job: WriterIdentity, date: str, task: str,
    response: machine_api.Written | machine_api.NotWritten,
) -> None:
    """Register the actual child's file, not a newly authored or scanned output."""
    if isinstance(response, machine_api.NotWritten):
        LOG.info("Task Performance %s for %s: %s", response.status, task, response.reason)
        return
    identity = task_writer(job, task)
    (receipt,) = response.files
    expected = ledger.raw_path(
        private_state, TASK_LEDGER, date, receipt.file_id,
    ).relative_to(private_state).as_posix()
    if receipt.path != expected or receipt.covers != date:
        raise IntegrityError("native receipt is outside the task's exact raw path")
    data = safe_file(private_state, expected, exists=True).read_bytes()
    row, unit, digest = _verified_task(private_state, expected, data, identity=identity, date=date)
    if (row, unit, digest) != (response.row, receipt.unit_id, receipt.content_sha256):
        raise IntegrityError("native receipt does not match the completed file", (expected,))
    _copy_exact(repo, f"state/{expected}", data)
    publication_evidence.save(
        repo, identity, RECORD, {repo / "state" / expected: hashlib.sha256(data).hexdigest()},
    )


def evidence(repo: Path, job: WriterIdentity, date: str) -> dict[str, str]:
    """Verify only the task receipts the publisher already admits for this job."""
    if job.job is None:
        raise IntegrityError("digest publication requires its job identity")
    scope = raw_scope(repo, TASK_LEDGER, date)
    writes: dict[str, str] = {}
    for task in TASKS[ServerJob(job.job)]:
        identity = task_writer(job, task)
        path = publication_evidence.receipt_path(repo, identity, RECORD)
        if not path.is_file():
            continue
        receipt = publication_evidence.read_receipt(path, identity)
        if len(receipt.writes) != 1:
            raise IntegrityError("Task Performance receipt must name one file")
        (relative, digest), = receipt.writes.items()
        if not contains(scope, relative) or relative in writes:
            raise IntegrityError(
                "Task Performance receipt exceeds its declared raw day", (relative,),
            )
        data = safe_file(repo, relative, exists=True).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise IntegrityError("completed write bytes changed", (relative,))
        row, _, _ = _verified_task(
            repo / "state", relative.removeprefix("state/"), data, identity=identity, date=date,
        )
        if row.host_unit_id is not None:
            host = opening_capture(repo, job, date)
            if host is None or row.host_unit_id != host.unit_id:
                raise IntegrityError(
                    "Task Performance host reference lacks verified opening evidence"
                )
            writes[host.path] = host.sha256
        writes[relative] = digest
    return writes


def _private_state(repo: Path) -> Path:
    root = relative_path(os.environ[machine_api.STATE_ROOT_ENV])
    parts = root.split("/")
    if (
        len(parts) != 4 or parts[:2] != ["backend", "var"]
        or not parts[2].startswith("machine-task-") or parts[3] != "state"
    ):
        raise IntegrityError("machine recording state is not job private")
    return repo / root


def record_measurement(
    client: machine_api.MachineApi, repo: Path, job: WriterIdentity, date: str, task: str,
    measurement: Mapping[str, object], *, host: str | None,
) -> None:
    response = client.record(
        date=date, identity=task_writer(job, task),
        measurement={**measurement, "host_unit_id": host},
    )
    retain(repo, _private_state(repo), job=job, date=date, task=task, response=response)


def import_opening_capture(repo: Path, job: WriterIdentity, date: str) -> str | None:
    try:
        capture = opening_capture(repo, job, date, private_state=_private_state(repo))
        return capture.unit_id if capture is not None else None
    except (OSError, ValueError, KeyError) as error:
        LOG.warning("Task Performance host reference unavailable: %s", error)
        return None


@contextmanager
def profile(
    repo: Path, job: WriterIdentity, date: str, task: str,
) -> Iterator[Callable[[int], None]]:
    """Measure the actual Python process before it starts and while it is still alive."""
    client = None
    handle = None
    host = None
    pin = machine_api.ProfileIdentity(
        run_id=job.run_id, pipeline_name=PIPELINE, task_name=task,
    )
    try:
        client = machine_api.MachineApi.for_job()
        if client is not None:
            host = import_opening_capture(repo, job, date)
            handle = client.start(pin)
    except (ValidationError, machine_api.MachineApiError) as error:
        LOG.warning("Task Performance start unavailable for %s: %s", task, error)
    outcome: TaskPerformanceOutcome = "success"

    def completed(status: int) -> None:
        nonlocal outcome
        outcome = "error" if status else "success"

    try:
        yield completed
    except KeyboardInterrupt:
        outcome = "cancelled"
        raise
    except SystemExit as error:
        if error.code not in (None, 0):
            outcome = "error"
        raise
    except BaseException:
        outcome = "error"
        raise
    finally:
        if client is not None and handle is not None:
            try:
                record_measurement(
                    client, repo, job, date, task, client.stop(handle, pin, outcome), host=host,
                )
            except (OSError, ValueError, KeyError, machine_api.MachineApiError) as error:
                LOG.warning("Task Performance close unavailable for %s: %s", task, error)
