"""Bracket one job's Rust session and return only its verified raw host paths."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from idhazh import run_context
from idhazh.contracts.base import ServerJob
from idhazh.telemetry.host_event_client import HostEventClient

if TYPE_CHECKING:
    from idhazh import config

_LOG = logging.getLogger("idhazh")


def utc_now() -> datetime:
    return datetime.now(UTC)


def from_environment(
    settings: config.Settings | config.GardenerSettings,
) -> HostEventClient | None:
    memory = settings.app.observability.memory_profiling_enabled
    override = os.environ.get("IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING")
    if override is not None:
        if override not in ("true", "false"):
            raise ValueError("IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING must be 'true' or 'false'")
        memory = override == "true"
    return HostEventClient.from_environment(memory_profiling_enabled=memory)


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
    host_events: HostEventClient | None = None,
) -> Iterator[list[Path]]:
    if host_events is None:
        host_events = from_environment(settings)
    written: list[Path] = []
    if host_events is None:
        _LOG.info("host measurements unavailable: no bound Rust session run=%s job=%s", run_id, job)
        yield written
        return
    if not host_events.native:
        raise ValueError(
            "host jobs require a native session; Python and shadow collectors were removed"
        )
    manifest = host_events.manifest
    expected = (date, run_id, job, shard, commit_sha)
    actual = (manifest.date, manifest.run_id, manifest.job, manifest.shard, manifest.git_sha)
    if expected != actual or manifest.attempt != (
        run_context.run_attempt() if attempt is None else attempt
    ):
        raise ValueError("host event manifest differs from the job's exact invocation identity")
    if not host_events.begin_job():
        raise RuntimeError("native machine session is unavailable; no collector fallback exists")
    try:
        yield written
    finally:
        if not host_events.end_job():
            raise RuntimeError("native machine session did not close")
        receipt = host_events.publication_receipt()
        written.extend(host_events.workspace / path for path in receipt.writes)
