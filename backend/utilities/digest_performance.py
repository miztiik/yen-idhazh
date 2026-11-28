"""Which verified machine files may a digest job hand to publication?"""

from __future__ import annotations

import os
from pathlib import Path

from idhazh import config
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import HOST_FINGERPRINT_PRODUCER, WriterIdentity
from idhazh.telemetry import machine_api, machine_evidence, task_probe
from idhazh.telemetry.host_control import enabled
from utilities.publication_request import IntegrityError

PIPELINE = "digest"
SERVE = "serve-summarizer"
TASKS = {
    ServerJob.PLAN: ("plan",),
    ServerJob.WORK: ("work", SERVE),
    ServerJob.ASSEMBLE: ("assemble",),
}


def bundle(repo: Path, job: WriterIdentity) -> Path:
    return repo / "backend" / "var" / "digest-machine" / job.run_id / str(job.attempt)


def approved_scope(job: str, day: str) -> tuple[str, ...]:
    return (machine_evidence.raw_scope(machine_evidence.TASK, day),) if job in TASKS else ()


def task_file(job: WriterIdentity, task: str, day: str) -> machine_evidence.ExpectedFile:
    if job.job is None or task not in TASKS[ServerJob(job.job)]:
        raise IntegrityError("task is not declared for this digest publication job")
    return task_probe.task_file(
        job, pipeline=PIPELINE, task=task, day=day,
        kind="model-serving" if task == SERVE else "workflow-task",
    )


def opening_file(job: WriterIdentity, day: str) -> machine_evidence.ExpectedFile:
    if job.job is None:
        raise IntegrityError("opening fingerprint requires its digest job")
    writer = WriterIdentity(
        run_id=job.run_id, attempt=job.attempt, shard=job.shard, git_sha=job.git_sha,
        job=job.job, pipeline_name=PIPELINE,
        task_name=job.job, producer=HOST_FINGERPRINT_PRODUCER,
    )
    return machine_evidence.ExpectedFile(writer, day)


def read_opening(repo: Path, job: WriterIdentity, day: str) -> machine_evidence.VerifiedFile | None:
    return machine_evidence.read_receipt(bundle(repo, job), opening_file(job, day))


def capture(repo: Path, job: WriterIdentity, day: str, settings: config.Settings) -> None:
    if not enabled(settings.app.observability) or not settings.app.observability.host_fingerprint:
        return
    if (actual := os.environ.get("GITHUB_JOB")) and actual != job.job:
        raise IntegrityError("opening fingerprint does not name this digest runner")
    expected = opening_file(job, day)
    store = bundle(repo, job)
    if machine_evidence.read_receipt(store, expected) is not None:
        return
    machine_evidence.capture_opening(repo, store, expected)


def recording(repo: Path, job: WriterIdentity, day: str) -> task_probe.Recording | None:
    if not os.environ.get(machine_api.ORIGIN_ENV):
        return None
    try:
        opening = read_opening(repo, job, day)
    except (OSError, ValueError) as error:
        machine_api.unavailable(str(job.job), "opening evidence", error)
        return None
    return task_probe.Recording.for_job(repo, opening)


def evidence(repo: Path, job: WriterIdentity, day: str) -> dict[str, str]:
    """Place the exact opening and only this job's verified closed tasks."""
    if job.job is None:
        raise IntegrityError("digest publication requires its job identity")
    store = bundle(repo, job)
    opening = read_opening(repo, job, day)
    proofs = [] if opening is None else [opening]
    for task in TASKS[ServerJob(job.job)]:
        proof = machine_evidence.read_receipt(store, task_file(job, task, day))
        if proof is not None:
            machine_evidence.verify_host_link(proof, opening)
            proofs.append(proof)
    for proof in proofs:
        proof.place(repo)
    return {proof.path: proof.sha256 for proof in proofs}
