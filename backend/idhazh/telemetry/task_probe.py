"""How does named work retain verified receipts from the owned native recorder?"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.task_performance import TaskPerformanceKind
from idhazh.publication_paths import IntegrityError
from idhazh.telemetry import machine_api, machine_evidence


def task_file(
    execution: WriterIdentity, *, pipeline: str, task: str, day: str,
    kind: TaskPerformanceKind = "workflow-task", subject: str | None = None,
) -> machine_evidence.ExpectedFile:
    return machine_evidence.ExpectedFile(
        WriterIdentity.for_pipeline_task(
            run_id=execution.run_id, attempt=execution.attempt, shard=execution.shard,
            git_sha=execution.git_sha, producer=machine_api.PRODUCER,
            pipeline_name=pipeline, task_name=task,
        ), day, kind, subject,
    )


@dataclass(frozen=True, slots=True)
class Recording:
    client: machine_api.MachineApi
    private: Path
    opening: machine_evidence.VerifiedFile | None

    @classmethod
    def for_job(
        cls, repo: Path, opening: machine_evidence.VerifiedFile | None,
    ) -> Recording | None:
        try:
            client = machine_api.MachineApi.for_job()
            if client is None:
                return None
            state = machine_api.private_state(repo)
            if opening is not None:
                opening.place(state.parent)
        except (OSError, ValueError, KeyError, machine_api.MachineApiError) as error:
            machine_api.unavailable("runner", "listener or opening evidence", error)
            return None
        return cls(client, state.parent, opening)

    def profile(
        self, expected: machine_evidence.ExpectedFile, store: Path | None = None,
    ) -> AbstractContextManager[machine_api.TaskClose]:
        writer = expected.writer
        if writer.pipeline_name is None or writer.task_name is None:
            raise IntegrityError("a native task must have a pipeline and a task name")
        pin = machine_api.ProfileIdentity(
            run_id=writer.run_id, pipeline_name=writer.pipeline_name, task_name=writer.task_name,
        )
        return self.client.profile(pin, partial(self.record, expected, store))

    def record(
        self, expected: machine_evidence.ExpectedFile, store: Path | None,
        measurement: Mapping[str, object],
    ) -> None:
        response = self.client.record(
            date=expected.date, identity=expected.writer,
            measurement={
                **measurement,
                "host_unit_id": (
                    str(self.opening.envelope.unit_id) if self.opening is not None else None
                ),
            },
        )
        if isinstance(response, machine_api.NotWritten):
            machine_api.LOG.info(
                "Task Performance %s for %s: %s",
                response.status, expected.writer.task_name, response.reason,
            )
            return
        if len(response.files) != 1:
            raise IntegrityError("native recorder did not return one receipt")
        (receipt,) = response.files
        path = ledger.raw_path(
            machine_evidence.STATE, machine_evidence.TASK, expected.date, receipt.file_id,
        ).as_posix()
        if f"{machine_evidence.STATE}/{receipt.path}" != path or receipt.covers != expected.date:
            raise IntegrityError("native receipt is outside the task's exact raw path")
        proof = machine_evidence.verify_file(self.private, path, expected)
        if (
            proof.row != response.row or str(proof.envelope.unit_id) != receipt.unit_id
            or proof.envelope.content_sha256 != receipt.content_sha256
        ):
            raise IntegrityError("native receipt does not match the completed file", (path,))
        machine_evidence.verify_host_link(proof, self.opening)
        proof.save_receipt(self.private if store is None else store, expected)


def profile(
    recording: Recording | None, expected: machine_evidence.ExpectedFile,
    store: Path | None = None,
) -> AbstractContextManager[machine_api.TaskClose]:
    if recording is None:
        return nullcontext(machine_api.TaskClose())
    return recording.profile(expected, store)
