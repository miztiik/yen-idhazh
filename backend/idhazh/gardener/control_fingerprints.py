"""Which native readings belong to each gardener control runner?"""

from __future__ import annotations

import os
from datetime import date
from enum import StrEnum
from pathlib import Path

from idhazh.contracts.file_envelope import HOST_FINGERPRINT_PRODUCER, WriterIdentity
from idhazh.gardener.performance import PIPELINE
from idhazh.telemetry import machine_api, machine_evidence, task_probe


class Job(StrEnum):
    PLAN = "plan"
    HISTORY = "history"
    APPEND = "publish-fingerprints"


class Operation(StrEnum):
    PLAN = "plan"
    CHECK_HISTORY = "check-history-eligibility"
    SQUASH = "corpus-squash"
    PREPARE_APPEND = "prepare-control-append"


# Named workflow operations, not a task inventory supplied by an artifact.
OPERATIONS = {
    Job.PLAN: (Operation.PLAN,),
    Job.HISTORY: (Operation.CHECK_HISTORY, Operation.SQUASH),
    Job.APPEND: (Operation.PREPARE_APPEND,),
}


def expected(
    job: Job, *, run_id: str, attempt: int, revision: str,
) -> machine_evidence.ExpectedFile:
    day = date.fromisoformat(run_id[:10]).isoformat()
    return machine_evidence.ExpectedFile(
        WriterIdentity.for_pipeline_task(
            job=job, pipeline_name=PIPELINE, task_name=job,
            shard=0, run_id=run_id, attempt=attempt, git_sha=revision,
            producer=HOST_FINGERPRINT_PRODUCER,
        ),
        day,
    )


def artifact(job: Job, run_id: str, attempt: int) -> str:
    return f"gardener-fingerprint-{job}-{run_id}-{attempt}"


def task_file(
    opening: machine_evidence.ExpectedFile, operation: Operation,
) -> machine_evidence.ExpectedFile:
    return task_probe.task_file(
        opening.writer, pipeline=PIPELINE, task=operation, day=opening.date,
    )


def recording(
    repo: Path, bundle: Path, opening: machine_evidence.ExpectedFile,
) -> task_probe.Recording | None:
    if not os.environ.get(machine_api.ORIGIN_ENV):
        return None
    try:
        proof = machine_evidence.read_receipt(bundle, opening)
    except (OSError, ValueError) as error:
        machine_api.unavailable(opening.writer.task_key, "opening evidence", error)
        return None
    return task_probe.Recording.for_job(repo, proof)
