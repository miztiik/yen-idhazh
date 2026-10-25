"""Which recent direct deliveries supply a shard's immutable fallback mark counts?"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from types import MappingProxyType

from idhazh import ledger
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_type import VisualType

type VisualPopulation = MappingProxyType[VisualType, tuple[int, ...]]


def load_visual_population(
    state_dir: Path, *, on: str, visuals: VisualsConfig,
) -> VisualPopulation | None:
    """Read only the previous configured UTC days, once before a shard starts its items."""
    if not visuals.downgrade_enabled:
        return None
    today = date.fromisoformat(on)
    if today.isoformat() != on:
        raise ValueError("the visual population date must be a YYYY-MM-DD UTC day")
    days = [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(1, visuals.downgrade_lookback_days + 1)
    ]
    rows = ledger.load_days(state_dir, LedgerName.ITEM_HEALTH, days, model=ItemHealthRow)
    rows.sort(
        key=lambda row: (row.date, row.item_ended_at or "", row.run_id, row.item_id),
        reverse=True,
    )
    counts: dict[VisualType, list[int]] = defaultdict(list)
    for row in rows:
        if (
            row.outcome is ItemOutcome.OK
            and row.planned_type is not None
            and row.planned_type is row.rendered_type
            and row.downgrade_depth == 0
            and row.marks is not None
            and len(counts[row.planned_type]) < visuals.downgrade_max_samples_per_type
        ):
            counts[row.planned_type].append(row.marks)
    return MappingProxyType({kind: tuple(marks) for kind, marks in counts.items()})
