"""Commit what one shard measured, before anything can throw it away.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from typing import Final

from idhazh import (
    config,
    ledger,
    run_context,
    telemetry,
)
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from idhazh.evals import writer
from idhazh.stages import common
from idhazh.stages.common import (
    LOG,
    _extraction_health,
    _item_payloads,
    _run_dir,
    shard_of,
)

#: The name every file this stage writes carries as its producer: what keeps its
#: work unit apart from assemble's when both file rows for one day.
PRODUCER: Final = __name__.partition(".")[2]


def stage_record(
    plan: RunPlan,
    *,
    settings: config.Settings,
    commit_sha: str,
    shard: int = 0,
    shards: int = 1,
) -> tuple[int, int]:
    """Commit what one shard measured, before anything can throw it away.

    `stage_assemble` writes the whole day's census, and it runs in another job on
    another machine hours later. Until then a shard's verdicts exist only inside
    its `items-<shard>` artifact, which expires and is never committed. So a run
    stopped between the workers and the publish had measured every item and
    recorded none of it.

    Only settled items are recorded, which is what `telemetry.is_final` decides.
    An item whose summary is not written yet was interrupted rather than failed,
    and this ledger has no way to correct a row once it is in.

    **The row is the one the shard sealed wherever there is one.** The work stage
    validates 119 cells an item and leaves them beside the article and the
    summary; rebuilding from those two payloads carries 40 of them. So this reads
    the shard's own row and only falls back to `telemetry.classify_item` for an
    item no shard sealed one for - which on a healthy run is none of them, and is
    why the log line below says how many were rebuilt.

    Each rebuilt row is stamped with this worker's own `shard` and with `work`,
    the workflow job this stage runs in, which is the only moment either is
    known: `stage_assemble` runs once for the whole day and cannot say which
    machine an item was for, so the rows it adds leave both cells empty. The pair
    is `HOST_FINGERPRINT_KEY` minus the date and the run, so it is what takes an
    item to the `state/host-fingerprint/` row for the machine that read it.

    **Both ledgers go to this shard's own files, never to a file others open.**
    Up to eight work shards and assemble all record the same day, and each files
    its own raw file through the ledger door, named for the writer. A re-run's
    second attempt replaces its first try rather than colliding with it.

    Returns the item-health rows and the eval rows that landed.
    """
    items_dir = _run_dir(plan.date) / "items"
    mine = {item.item_id for item in shard_of(plan, shard=shard, shards=shards)}
    health: list[ItemHealthRow] = []
    rows: list[EvalRow] = []
    rebuilt = 0
    for payload in _item_payloads(plan, items_dir):
        if payload.planned.item_id not in mine:
            continue
        if not telemetry.is_final(payload.article, payload.summary):
            continue
        rebuilt += payload.recorded is None
        health.append(
            telemetry.census_row(
                recorded=payload.recorded,
                planned=payload.planned,
                article=payload.article,
                summary=payload.summary,
                date=plan.date,
                run_id=plan.run_id,
                shard=shard,
                job=ServerJob.WORK,
                extraction=_extraction_health(payload.article, settings),
            )
        )
        if payload.eval_path.exists():
            rows.append(EvalRow.read(payload.eval_path))
    identity = WriterIdentity(
        run_id=plan.run_id,
        attempt=run_context.run_attempt(),
        job=ServerJob.WORK,
        shard=shard,
        producer=PRODUCER,
        git_sha=commit_sha,
    )
    # The door writes nothing into a paused family, and says so by returning no path.
    landed = ledger.persist(
        common.STATE_ROOT,
        health,
        ledger=LedgerName.ITEM_HEALTH,
        covers=plan.date,
        identity=identity,
    )
    recorded = len(health) if landed else 0
    scored = writer.file_measurements(common.STATE_ROOT, rows, identity=identity)
    attempt = identity.attempt
    LOG.info(
        "recorded shard=%s/%s run=%s attempt=%s settled=%s rebuilt=%s item_health_rows=%s "
        "eval_rows=%s",
        shard,
        shards,
        plan.run_id,
        attempt,
        len(health),
        rebuilt,
        recorded,
        scored,
    )
    return recorded, scored
