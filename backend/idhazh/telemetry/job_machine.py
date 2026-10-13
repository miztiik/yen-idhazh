"""Record a job's machine before its work and its elapsed time afterwards."""

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
from idhazh.telemetry import silicon
from idhazh.telemetry.host_event_client import HostEventClient

if TYPE_CHECKING:
    from idhazh import config

_LOG = logging.getLogger("idhazh")


def utc_now() -> datetime:
    return datetime.now(UTC)


def from_environment(
    settings: config.Settings | config.GardenerSettings,
) -> HostEventClient | None:
    """Open the session supplied by the workflow, never infer a native fallback."""
    mode = os.environ.get("IDHAZH_HOST_TELEMETRY_MODE")
    if mode not in (None, "", "legacy", "rust"):
        raise ValueError("IDHAZH_HOST_TELEMETRY_MODE must be 'legacy' or 'rust'")
    selected = settings.app.observability.host_event_mode
    if mode == "rust":
        selected = "native"
    elif mode == "legacy":
        selected = "legacy"
    if selected == "legacy" and not settings.app.observability.host_event_shadow:
        return None
    if selected == "native" and settings.app.observability.host_event_shadow:
        raise ValueError("native host events cannot also use shadow collection")
    names = (
        "IDHAZH_HOST_TELEMETRY_WORKSPACE",
        "IDHAZH_HOST_TELEMETRY_MANIFEST",
        "IDHAZH_HOST_TELEMETRY_CONFIG",
    )
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ValueError("host event session needs " + ", ".join(missing))
    memory = settings.app.observability.memory_profiling_enabled
    override = os.environ.get("IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING")
    if override is not None:
        if override not in ("true", "false"):
            raise ValueError("IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING must be 'true' or 'false'")
        memory = override == "true"
    if selected == "native":
        client = HostEventClient.from_environment(
            memory_profiling_enabled=memory,
            environ={**os.environ, "IDHAZH_HOST_TELEMETRY_MODE": "rust"},
        )
        if client is None:
            raise RuntimeError("native machine session is unavailable")
        return client
    return HostEventClient(
        *(Path(os.environ[name]) for name in names),
        memory_profiling_enabled=memory,
        native=False,
    )


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
    """Yield the exact files to stage, including the clock even if the work fails.

    Only instrument I/O failures degrade to a logged missing reading. Work
    failures and invalid configuration still propagate to the caller.
    """
    if host_events is None:
        host_events = from_environment(settings)
    mode = os.environ.get("IDHAZH_HOST_TELEMETRY_MODE")
    native_selected = mode == "rust" or (
        mode is None and settings.app.observability.host_event_mode == "native"
    )
    if native_selected and host_events is not None and not host_events.native:
        raise ValueError("native host session cannot use a Python or shadow collector")
    if isinstance(host_events, HostEventClient):
        manifest = host_events.manifest
        expected = (date, run_id, job, shard, commit_sha)
        actual = (manifest.date, manifest.run_id, manifest.job, manifest.shard, manifest.git_sha)
        if expected != actual or manifest.attempt != (
            run_context.run_attempt() if attempt is None else attempt
        ):
            raise ValueError("host event manifest differs from the job's exact invocation identity")
    started = started_at if started_at is not None else clock()
    written: list[Path] = []
    native_active = False
    events_started = False
    if host_events is not None:
        try:
            events_started = host_events.begin_job()
            native_active = events_started and host_events.native
        except OSError as error:
            if host_events.native:
                raise
            _LOG.warning(
                "native machine probe unavailable run=%s job=%s error=%s",
                run_id,
                job,
                type(error).__name__,
            )
        if host_events.native and not native_active:
            raise RuntimeError(
                "native machine session is unavailable; Python collection is disabled"
            )
    try:
        if not native_active:
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
        if events_started and host_events is not None:
            try:
                if not host_events.end_job() and host_events.native:
                    raise RuntimeError("native machine session did not close")
                if host_events.native and isinstance(host_events, HostEventClient):
                    receipt = host_events.publication_receipt()
                    written.extend(host_events.workspace / path for path in receipt.writes)
            except OSError as error:
                if host_events.native:
                    raise
                _LOG.warning(
                    "native machine clock unavailable run=%s job=%s error=%s",
                    run_id,
                    job,
                    type(error).__name__,
                )
        if not native_active:
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
