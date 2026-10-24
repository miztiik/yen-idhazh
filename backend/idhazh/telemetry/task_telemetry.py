"""Record a task's machine before its work and its elapsed time afterwards."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from idhazh.contracts.base import WORK_JOB, PipelineName, ServerJob, TaskName
from idhazh.telemetry import silicon
from idhazh.telemetry.host_control import enabled as host_telemetry_enabled

if TYPE_CHECKING:
    from idhazh import config

_LOG = logging.getLogger("idhazh")


def utc_now() -> datetime:
    return datetime.now(UTC)


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
) -> Iterator[list[Path]]:
    """Yield exact files for a generic task, including its clock on work failure."""
    if (pipeline_name is None) != (task_name is None):
        raise ValueError("pipeline_name and task_name must be present together")
    effective_task = task_name if task_name is not None else job or WORK_JOB
    writer_job = None if pipeline_name is not None else effective_task
    if not host_telemetry_enabled(settings.app.observability):
        _LOG.info("host telemetry off run=%s task=%s", run_id, effective_task)
        yield []
        return
    started = started_at if started_at is not None else clock()
    written: list[Path] = []
    try:
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
