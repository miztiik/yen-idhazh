"""Select native hardware capture, explicit rollback or no host recording."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from idhazh import run_context
from idhazh.contracts.base import WORK_JOB, PipelineName, ServerJob, TaskName
from idhazh.contracts.file_envelope import HOST_FINGERPRINT_PRODUCER, WriterIdentity
from idhazh.telemetry import native_capture, silicon
from idhazh.telemetry.host_control import mode

if TYPE_CHECKING:
    from idhazh import config

_LOG = logging.getLogger("idhazh")


def utc_now() -> datetime:
    return datetime.now(UTC)


def native_writer(
    run_id: str, commit_sha: str, *, pipeline: PipelineName, task: TaskName,
    shard: int = 0, attempt: int | None = None, job: ServerJob | TaskName | None = None,
) -> WriterIdentity:
    return WriterIdentity(
        run_id=run_id, git_sha=commit_sha, shard=shard,
        job=os.environ.get("GITHUB_JOB") or job, pipeline_name=pipeline,
        task_name=task, producer=HOST_FINGERPRINT_PRODUCER,
        attempt=run_context.run_attempt() if attempt is None else attempt,
    )


@contextmanager
def record(
    *,
    date: str,
    run_id: str,
    settings: config.Settings | config.GardenerSettings,
    state_root: Path,
    commit_sha: str,
    job: ServerJob | TaskName | None = None,
    pipeline_name: PipelineName | None = None,
    task_name: TaskName | None = None,
    shard: int = 0,
    attempt: int | None = None,
    started_at: datetime | None = None,
    clock: Callable[[], datetime] = utc_now,
    ask_placement: bool = True,
    capture_opening: bool = True,
) -> Iterator[list[Path]]:
    """Yield opening files; only the explicit rollback adds the old closing clock."""
    if (pipeline_name is None) != (task_name is None):
        raise ValueError("pipeline_name and task_name must be present together")
    effective_task = task_name if task_name is not None else job or WORK_JOB
    writer_job = None if pipeline_name is not None else effective_task
    selected = mode(settings.app.observability)
    if selected == "off":
        _LOG.info("host telemetry off run=%s task=%s", run_id, effective_task)
        yield []
        return
    if selected == "typescript":
        paths: list[Path] = []
        if capture_opening and settings.app.observability.host_fingerprint:
            if pipeline_name is None or task_name is None:
                raise ValueError("native recording requires a declared pipeline and task")
            writer = native_writer(
                run_id, commit_sha, pipeline=pipeline_name, task=task_name,
                shard=shard, attempt=attempt, job=job,
            )
            _, paths = native_capture.file_opening(
                date=date, writer=writer, state=state_root,
                settings=settings, ask_placement=ask_placement,
            )
        yield paths
        return
    started = started_at if started_at is not None else clock()
    written: list[Path] = []
    try:
        if capture_opening:
            _, paths = silicon.file_machine_row(
                date=date,
                run_id=run_id,
                settings=settings,
                state_root=state_root,
                commit_sha=commit_sha,
                job=writer_job,
                pipeline_name=pipeline_name,
                task_name=task_name,
                shard=shard,
                attempt=attempt,
                ask_placement=ask_placement,
            )
            written.extend(paths)
    except OSError as error:
        _LOG.warning(
            "machine probe not written run=%s task=%s error=%s",
            run_id,
            effective_task,
            type(error).__name__,
        )
    try:
        yield written
    finally:
        try:
            _, paths = silicon.file_job_clock(
                date=date,
                run_id=run_id,
                settings=settings,
                state_root=state_root,
                commit_sha=commit_sha,
                job=writer_job,
                pipeline_name=pipeline_name,
                task_name=task_name,
                shard=shard,
                attempt=attempt,
                job_started_at=int(started.timestamp()),
                finished_at=clock().strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            written.extend(paths)
        except OSError as error:
            _LOG.warning(
                "machine clock not written run=%s task=%s error=%s",
                run_id,
                effective_task,
                type(error).__name__,
            )
