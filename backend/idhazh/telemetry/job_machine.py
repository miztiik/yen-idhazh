"""Record a job's machine before its work and its elapsed time afterwards."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from idhazh.contracts.base import ServerJob
from idhazh.telemetry import silicon

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
    job: ServerJob,
    shard: int = 0,
    attempt: int | None = None,
    started_at: datetime | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> Iterator[list[Path]]:
    """Yield the exact files to stage, including the clock even if the work fails.

    Only instrument I/O failures degrade to a logged missing reading. Work
    failures and invalid configuration still propagate to the caller.
    """
    started = started_at if started_at is not None else clock()
    written: list[Path] = []
    try:
        _, paths = silicon.file_machine_row(
            date=date,
            run_id=run_id,
            settings=settings,
            state_root=state_root,
            commit_sha=commit_sha,
            job=job,
            shard=shard,
            attempt=attempt,
        )
        written.extend(paths)
    except OSError as error:
        _LOG.warning(
            "machine probe not written run=%s job=%s error=%s", run_id, job, type(error).__name__
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
                job=job,
                shard=shard,
                attempt=attempt,
                job_started_at=int(started.timestamp()),
                finished_at=clock().strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            written.extend(paths)
        except OSError as error:
            _LOG.warning(
                "machine clock not written run=%s job=%s error=%s",
                run_id,
                job,
                type(error).__name__,
            )
