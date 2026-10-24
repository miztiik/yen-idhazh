"""Seed publication and ledger fixtures through production writers."""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.evals import writer as eval_writer
from idhazh.stages import plan as plan_stage
from idhazh.telemetry import silicon

SEED_COMMIT: Final = "0" * 40
_SEED_CALLS: Final = itertools.count(1)
_HOST_PRODUCER: Final = silicon.PRODUCER


def seed_publication_inventory(public_root: Path) -> None:
    """Initialize a new publication fixture tree."""
    from idhazh.contracts.publication_inventory import PublicationInventory
    from idhazh.publication import initialize_inventory

    initialize_inventory(
        public_root,
        seed=PublicationInventory(version=PublicationInventory.schema_version(), dates=[]),
    )


def record_fixture_day(public_root: Path, day: str, *, items: int = 0) -> None:
    """Register a test-written digest day."""
    from idhazh.publication import record_files

    if not (public_root / "publication.json").exists():
        seed_publication_inventory(public_root)
    name = f"digest/{day.replace('-', '/')}/digest.json"
    record_files(public_root, dates=[day], paths=[name], item_counts={name: items})


def writer_identity(
    run_id: str,
    *,
    attempt: int = 1,
    job: ServerJob = ServerJob.ASSEMBLE,
    shard: int = 0,
    producer: str = "tests.conftest",
) -> WriterIdentity:
    return WriterIdentity(
        run_id=run_id,
        attempt=attempt,
        job=job,
        shard=shard,
        producer=producer,
        git_sha=SEED_COMMIT,
    )


def _item_health_key(row: ItemHealthRow) -> tuple[str, ...]:
    return tuple(str(getattr(row, name)) for name in ledger.ITEM_HEALTH_KEY)


def seed_item_health(state_dir: Path, date: str, rows: Iterable[ItemHealthRow]) -> int:
    """Add rows through the real writer, preserving the first row for each existing key."""
    pending = list(rows)
    days = {date, *(row.date for row in pending)}
    held = {
        _item_health_key(row)
        for row in ledger.load_days(state_dir, LedgerName.ITEM_HEALTH, days, model=ItemHealthRow)
    }
    kept: list[ItemHealthRow] = []
    for row in pending:
        key = _item_health_key(row)
        if key in held:
            continue
        held.add(key)
        kept.append(row)
    if not kept:
        return 0
    filed = ledger.persist(
        state_dir,
        kept,
        ledger=LedgerName.ITEM_HEALTH,
        covers=date,
        identity=writer_identity(f"{date}-1", producer=f"tests.conftest:seed-{next(_SEED_CALLS)}"),
    )
    return len(kept) if filed else 0


def seed_host_fingerprint(
    state_dir: Path, rows: Iterable[HostFingerprintRow], *, attempt: int = 1
) -> int:
    """Write each job's rows under its own identity so later attempts replace earlier ones."""
    by_job: dict[tuple[str, ServerJob, int], list[HostFingerprintRow]] = {}
    for row in rows:
        if row.job is None:
            raise ValueError("this history fixture requires legacy job identities")
        by_job.setdefault((row.run_id, ServerJob(row.job), row.shard), []).append(row)
    filed = 0
    for (run_id, job, shard), held in by_job.items():
        if ledger.persist(
            state_dir,
            held,
            ledger=LedgerName.HOST_FINGERPRINT,
            covers=held[0].date,
            identity=writer_identity(
                run_id, attempt=attempt, job=job, shard=shard, producer=_HOST_PRODUCER
            ),
        ):
            filed += len(held)
    return filed


def seed_feed_health(
    state_dir: Path,
    date: str,
    rows: Iterable[FeedHealthRow],
    *,
    run_id: str | None = None,
    attempt: int = 1,
    job: ServerJob = ServerJob.PLAN,
    shard: int = 0,
) -> int:
    recorded = list(rows)
    filed = ledger.persist(
        state_dir,
        recorded,
        ledger=LedgerName.FEED_HEALTH,
        covers=date,
        identity=writer_identity(
            run_id if run_id is not None else f"{date}-1",
            attempt=attempt,
            job=job,
            shard=shard,
            producer=plan_stage.PRODUCER,
        ),
    )
    return len(recorded) if filed else 0


def seed_scores(
    state_dir: Path,
    rows: Iterable[EvalRow],
    *,
    run_id: str,
    attempt: int = 1,
    job: ServerJob = ServerJob.ASSEMBLE,
    shard: int = 0,
) -> int:
    return eval_writer.file_measurements(
        state_dir,
        rows,
        identity=writer_identity(run_id, attempt=attempt, job=job, shard=shard),
    )
