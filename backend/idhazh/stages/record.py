"""Commit what one shard measured, before anything can throw it away.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from idhazh import (
    config,
    ledger,
    telemetry,
)
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.item_health import ItemHealthRow
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


def stage_record(
    plan: RunPlan, *, settings: config.Settings, shard: int = 0, shards: int = 1
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
    validates 113 cells an item and leaves them beside the article and the
    summary; rebuilding from those two payloads carries 40 of them. So this reads
    the shard's own row and only falls back to `telemetry.classify_item` for an
    item no shard sealed one for - which on a healthy run is none of them, and is
    why the log line below says how many were rebuilt.

    Each row is stamped with this worker's own `shard`, which is the only moment
    the number is known: `stage_assemble` runs once for the whole day and cannot
    say which machine an item was for, so the rows it adds leave the cell empty.
    `state/runtime-counters.csv` carries the same number at the run grain, and
    the pair is what lets a per-item rate be read against the host that ran it.

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
                extraction=_extraction_health(payload.article, settings),
            )
        )
        if payload.eval_path.exists():
            rows.append(EvalRow.read(payload.eval_path))
    recorded = ledger.append_item_health(common.STATE_ROOT, plan.date, health)
    scored = writer.append(common.STATE_ROOT, rows)
    LOG.info(
        "recorded shard=%s/%s run=%s settled=%s rebuilt=%s item_health_rows=%s eval_rows=%s",
        shard,
        shards,
        plan.run_id,
        len(health),
        rebuilt,
        recorded,
        scored,
    )
    return recorded, scored
