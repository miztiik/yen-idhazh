"""Does fallback read only recent measured direct deliveries and freeze them per shard?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.ledger import seed_item_health, writer_identity
from support.paths import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_type import VisualType
from idhazh.visual_population import load_visual_population

pytestmark = [pytest.mark.visual, pytest.mark.contract]


def health(on: str, number: int, **changed: object) -> ItemHealthRow:
    old = json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row/published.json"))
    return ItemHealthRow.model_validate(old | {
        "version": ItemHealthRow.schema_version(),
        "date": on, "run_id": f"{on}-1", "item_id": f"energy-{number:02d}",
        "item_ended_at": f"{on}T12:00:00Z",
        "planned_type": "bar", "rendered_type": "bar", "downgrade_depth": 0, "marks": 4,
    } | changed)


def test_disabled_population_does_not_inspect_even_an_invalid_state_root(tmp_path: Path) -> None:
    blocked = tmp_path / "not-a-directory"
    blocked.write_bytes(b"not a state directory")
    assert load_visual_population(blocked, on="not-a-date", visuals=VisualsConfig()) is None


def test_population_is_bounded_recent_direct_evidence_and_immutable(tmp_path: Path) -> None:
    state = tmp_path / "state"
    rows = [
        health("2026-08-20", 1, marks=3),
        health("2026-08-20", 2, marks=5),
        health("2026-08-19", 3, marks=8),
        health("2026-08-18", 4, marks=7),
        health("2026-08-21", 5, marks=8),
        health("2026-08-22", 6, marks=8),
        health("2026-08-20", 7, planned_type="dot", downgrade_depth=1, marks=8),
        health(
            "2026-08-20", 8, planned_type=None, rendered_type=None,
            downgrade_depth=None, marks=None,
        ),
        health(
            "2026-08-20", 9, rendered_type=None, marks=None,
            stage="summarize", outcome="failed", code="model_refused",
        ),
    ]
    seed_item_health(state, "2026-08-20", rows)
    knobs = VisualsConfig(
        downgrade_enabled=True, downgrade_lookback_days=2, downgrade_max_samples_per_type=2
    )
    population = load_visual_population(state, on="2026-08-21", visuals=knobs)
    assert population == {VisualType.BAR: (5, 3)}
    assert population is not None
    assert isinstance(population[VisualType.BAR], tuple)

    seed_item_health(state, "2026-08-20", [health("2026-08-20", 10, marks=8)])
    assert population == {VisualType.BAR: (5, 3)}, "new rows must not alter a shard's snapshot"
    assert load_visual_population(state, on="2026-08-21", visuals=knobs) == {
        VisualType.BAR: (8, 5)
    }


def test_cold_start_is_empty_evidence_not_a_fabricated_floor(tmp_path: Path) -> None:
    knobs = VisualsConfig(downgrade_enabled=True)
    assert load_visual_population(tmp_path / "state", on="2026-08-21", visuals=knobs) == {}


@pytest.mark.parametrize("period", [Period.DAILY, Period.MONTHLY])
def test_raw_and_compact_history_supply_the_same_floor(tmp_path: Path, period: Period) -> None:
    fixture = json.loads(read_text(FIXTURES_DIR / "chart-vocabulary/row1.json"))
    on = fixture["history_date"]
    rows = [
        health(on, number, marks=marks)
        for number, marks in enumerate(fixture["history_marks"], start=1)
    ]
    state = tmp_path / "state"
    raw = ledger.persist(
        state, rows, ledger=LedgerName.ITEM_HEALTH, covers=on,
        identity=writer_identity(f"{on}-1"),
    )
    knobs = VisualsConfig(downgrade_enabled=True)
    expected = load_visual_population(state, on=fixture["date"], visuals=knobs)
    covers = on if period is Period.DAILY else on[:7]
    packed = ledger.persist_period(
        state, ledger.load_stored(raw, model=ItemHealthRow), model=ItemHealthRow,
        ledger=LedgerName.ITEM_HEALTH, period=period, covers=covers,
        identity=writer_identity(f"{fixture['date']}-1"), built_from=len(raw),
    )
    index = CompactIndex(
        version=CompactIndex.schema_version(), ledger=LedgerName.ITEM_HEALTH, period=period,
        entries=[CompactEntry(covers=covers, rows=len(rows), bytes=packed.stat().st_size)],
    )
    index_path = ledger.compact_index_path(state, LedgerName.ITEM_HEALTH, period)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(index.to_json(), encoding="ascii", newline="\n")
    assert load_visual_population(state, on=fixture["date"], visuals=knobs) == expected


def test_a_malformed_file_outside_the_named_days_is_not_read(tmp_path: Path) -> None:
    outside = tmp_path / "state" / "raw" / "item-health" / "2026" / "07" / "01" / "bad.parquet"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"not a ledger")
    assert load_visual_population(
        tmp_path / "state", on="2026-08-21",
        visuals=VisualsConfig(downgrade_enabled=True, downgrade_lookback_days=1),
    ) == {}
