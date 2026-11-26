"""How does a gardener shard keep new measurements out of the work it measures?"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.telemetry import machine_api, machine_evidence, silicon, task_probe

PIPELINE = "gardener"


def opening_file(execution: WriterIdentity) -> machine_evidence.ExpectedFile:
    return machine_evidence.ExpectedFile(
        WriterIdentity.for_pipeline_task(
            run_id=execution.run_id, attempt=execution.attempt, shard=execution.shard,
            git_sha=execution.git_sha, producer=silicon.PRODUCER, pipeline_name=PIPELINE,
            task_name=ServerJob.RUN_TASKS,
        ), execution.run_id[:10],
    )


def task_file(execution: WriterIdentity, name: str) -> machine_evidence.ExpectedFile:
    return task_probe.task_file(execution, pipeline=PIPELINE, task=name, day=execution.run_id[:10])


def record_in_private(
    repo: Path, execution: WriterIdentity, paths: Sequence[Path],
) -> task_probe.Recording | None:
    if not os.environ.get(machine_api.ORIGIN_ENV):
        return None
    expected = opening_file(execution)
    opening = None
    try:
        if paths:
            (path,) = paths
            opening = machine_evidence.verify_file(
                repo, path.relative_to(repo).as_posix(), expected,
            )
        recording = task_probe.Recording.for_job(repo, opening)
        if recording is not None and opening is not None:
            opening.save_receipt(recording.private, expected)
        return recording
    except (OSError, ValueError) as error:
        machine_api.unavailable(ServerJob.RUN_TASKS, "opening evidence", error)
        return None


def append_evidence(
    private: Path, execution: WriterIdentity, names: Sequence[str],
) -> tuple[machine_evidence.VerifiedFile | None, tuple[machine_evidence.VerifiedFile, ...]]:
    opening = machine_evidence.read_receipt(private, opening_file(execution))
    proofs = []
    for name in names:
        proof = machine_evidence.read_receipt(private, task_file(execution, name))
        if proof is not None:
            machine_evidence.verify_host_link(proof, opening)
            proofs.append(proof)
    return opening, tuple(proofs)


def append_scope(execution: WriterIdentity) -> str:
    return machine_evidence.raw_scope(machine_evidence.TASK, execution.run_id[:10])
