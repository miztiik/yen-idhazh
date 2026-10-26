"""Do the four planner ledgers survive real native packing without generic row identity?"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from contracts._fixtures import planner_payload
from gardener.tasks._task import run_declared
from support.paths import CONFIG_DIR, REPO_ROOT, read_text

from idhazh import config, ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.feed_health_state import FeedHealthStateRow
from idhazh.contracts.feed_ingest_discovered_article import DiscoveredArticleRow, PlannerRow
from idhazh.contracts.feed_ingest_plan_run import PlanRunRow
from idhazh.contracts.feed_ingest_selected_article import SelectedArticleRow
from idhazh.contracts.file_envelope import (
    PLANNER_FOOTER_KEYS,
    Format,
    Period,
    PlannerFileEnvelope,
)
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgersConfig
from idhazh.ledger import paths, stored_output
from idhazh.ledger.persist import PlannerStoredRow

pytestmark = pytest.mark.contract

PRODUCED_PLANNING_LEDGERS = (
    ("discovered-articles", DiscoveredArticleRow),
    ("selected-articles", SelectedArticleRow),
    ("feed-health-state", FeedHealthStateRow),
    ("plan-runs", PlanRunRow),
)


@pytest.mark.parametrize(("name", "model"), PRODUCED_PLANNING_LEDGERS)
def test_planning_ledger_registration(name: str, model: type[PlannerRow]) -> None:
    which = LedgerName(name)
    entry = paths.entry(which)
    assert entry.grain is Grain.RAW_AND_COMPACT
    assert entry.prefix == ("feed-ingest-plan", name)
    assert ledger.door_contract(which) is model and ledger.door_key(which)
    model.model_validate(planner_payload(name))
    policy = config.load_gardener().tasks[f"compact-feed-ingest-plan-{name}"]
    assert isinstance(policy, CompactionPolicy) and policy.ledger is which
    assert list(policy.owns) == [f"state/raw/feed-ingest-plan/{name}", f"state/compact/feed-ingest-plan/{name}"]
    assert (policy.dry_run, policy.compact_after_days, policy.daily_keep_days) == (False, 1, 45)
    assert (policy.monthly_keep_days, policy.monthly_window.unit) == (93, "forever")
    assert (policy.yearly_keep_months, policy.yearly_prune_enable) == (36, True)


def test_planning_family_has_exactly_the_declared_ledgers() -> None:
    families = LedgersConfig.from_json(read_text(CONFIG_DIR / "ledgers.json")).families
    family = next(held for held in families if held.name == "feed-ingest-plan")
    assert {held.name.value for held in family.ledgers} == {name for name, _model in PRODUCED_PLANNING_LEDGERS}


def _row(
    model: type[PlannerRow], *, attempt: int, run: int = 1, second: bool = False,
) -> PlannerRow:
    return model.model_validate(planner_payload(model.__name__, attempt=attempt, run=run, second=second))


def _raw[C: PlannerRow](
    state: Path, which: LedgerName, model: type[C],
) -> list[list[PlannerStoredRow[C]]]:
    return [
        ledger.load_stored([held.path], model=model)
        for held in ledger.read_day_files(state, which, "2026-10-20")
    ]


def _snapshot[C: PlannerRow](rows: Sequence[PlannerStoredRow[C]]) -> list[str]:
    return sorted(held.row.to_json() for held in rows)


@pytest.mark.parametrize(("name", "model"), PRODUCED_PLANNING_LEDGERS)
def test_attempts_survive_real_compaction_and_late_repacking(
    tmp_path: Path, name: str, model: type[PlannerRow],
) -> None:
    which = LedgerName(name)
    state = tmp_path / "state"
    first = _row(model, attempt=1)
    second = _row(model, attempt=1, second=True)
    # A run summary is one row per attempt, unlike the article/feed ledgers.
    initial = [first] if model is PlanRunRow else [first, second]
    for rows in (
        initial, [first], [_row(model, attempt=2)], [_row(model, attempt=1, run=2)],
    ):
        ledger.persist(state, rows, ledger=which, covers="2026-10-20", fmt=Format.PARQUET)
    key = ledger.door_key(which)
    raw = ledger.settle_rows(_raw(state, which, model), key)
    expected_count = 2 if model is DiscoveredArticleRow else 3 if model is PlanRunRow else 4
    assert len(raw) == expected_count
    assert all(isinstance(held, PlannerStoredRow) for held in raw)
    files = ledger.read_day_files(state, which, "2026-10-20")
    for held in files:
        assert isinstance(held.envelope, PlannerFileEnvelope)
        assert {key.decode() for key in held.envelope.as_metadata()} <= set(PLANNER_FOOTER_KEYS)
        assert not hasattr(held.envelope, "identity") and not hasattr(held.envelope, "unit_id")
    assert stored_output.check_raw_day(state, which, "2026-10-20")
    task = f"compact-feed-ingest-plan-{name}"
    policy = config.load_gardener().tasks[task]
    assert isinstance(policy, CompactionPolicy)
    before = {held.path: held.path.read_bytes() for held in files}
    dry = run_declared(
        task, policy.model_copy(update={"dry_run": True}), tmp_path,
        today=date(2026, 10, 22), first_year="2026",
    )
    assert dry.dry_run and dry.written and dry.taken
    assert all(path.read_bytes() == data for path, data in before.items())
    assert not ledger.compact_index_path(state, which, Period.DAILY).exists()
    live = run_declared(task, policy, tmp_path, today=date(2026, 10, 22), first_year="2026")
    assert set(live.taken) == set(dry.taken) and set(live.written) == set(dry.written)
    packed = ledger.compact_path(state, which, Period.DAILY, "2026-10-20")
    stored = ledger.load_stored([packed], model=model)
    assert _snapshot(stored) == _snapshot(raw)
    assert not ledger.read_day_files(state, which, "2026-10-20")
    assert stored_output.check_compact_period(state, which, Period.DAILY, "2026-10-20")
    # Read raw/compact overlap once, but do not erase another attempt's actual work.
    ledger.persist(state, [first], ledger=which, covers="2026-10-20", fmt=Format.PARQUET)
    assert len(ledger.load_days(state, which, {"2026-10-20"}, model=model)) == expected_count
    late = _row(model, attempt=3)
    ledger.persist(state, [late], ledger=which, covers="2026-10-20", fmt=Format.PARQUET)
    expected = ledger.settle_rows([stored, *_raw(state, which, model)], key)
    run_declared(task, policy, tmp_path, today=date(2026, 10, 23), first_year="2026")
    assert _snapshot(ledger.load_stored([packed], model=model)) == _snapshot(expected)
    if model is FeedHealthStateRow:
        measured = [FeedHealthStateRow.model_validate(held.row.model_dump()) for held in expected]
        assert all(row.feed_requests is not None for row in measured)
        assert sum(row.feed_requests for row in measured if row.feed_requests is not None) == 10
        # Both public native readers must include late work beside every compact tier.
        retry = FeedHealthStateRow.model_validate(planner_payload(name, attempt=2))
        phases = (
            (Period.DAILY, date(2026, 10, 23), "2026-10-20"),
            (Period.MONTHLY, date(2026, 11, 3), "2026-10"),
            (Period.YEARLY, date(2027, 3, 15), "2026"),
        )
        for target_index, (target_period, _today, target_covers) in enumerate(phases):
            root = tmp_path / f"late-{target_period.value}"
            branch = root / "state"
            ledger.persist(branch, [first], ledger=which, covers="2026-10-20", fmt=Format.PARQUET)
            tuned = policy.model_copy(update={
                "max_periods_per_run": 400, "daily_keep_days": 1, "monthly_keep_days": 33,
            })
            for _period, wake_day, _covers in phases[:target_index + 1]:
                for _wake in range(3):
                    run_declared(task, tuned, root, today=wake_day, first_year="2026")
            assert ledger.compact_path(branch, which, target_period, target_covers).exists()
            for extra in (retry, first):
                ledger.persist(
                    branch, [extra], ledger=which, covers="2026-10-20", fmt=Format.PARQUET,
                )
            for readback in (
                ledger.load_days(branch, which, {"2026-10-20"}, model=FeedHealthStateRow),
                ledger.load_ledger_rows(branch, which, model=FeedHealthStateRow),
            ):
                assert sorted(row.attempt for row in readback) == [1, 2]
                assert sum(row.article_requests or 0 for row in readback) == 2
                assert sum(row.feed_requests or 0 for row in readback) == 4

    if model is DiscoveredArticleRow:
        # Neither feed attribution nor the day partitions the global URL key.
        older = model.model_validate(planner_payload(name) | {
            "first_seen_at": "2026-10-19T23:59:59.999Z", "date": "2026-10-19",
        })
        assert isinstance(older, DiscoveredArticleRow)
        ledger.persist(state, [older], ledger=which, covers="2026-10-19", fmt=Format.PARQUET)
        read = ledger.load_days(state, which, {"2026-10-19", "2026-10-20"}, model=model)
        found = next(
            row for row in read
            if isinstance(row, DiscoveredArticleRow) and row.url_key == older.url_key
        )
        assert isinstance(found, DiscoveredArticleRow)
        assert found.first_seen_at == "2026-10-19T23:59:59.999Z"


def test_zero_completion_evidence_survives_without_erasing_an_earlier_complete_attempt(
    tmp_path: Path,
) -> None:
    """Real Bun output brackets daily, monthly, reopened-month and yearly native packing."""
    bun = shutil.which("bun")
    assert bun, "Install the declared TypeScript planner dependencies before this CI case"
    generated = tmp_path / "native-attempts"
    driver = REPO_ROOT / "services" / "feed-ingest-plan" / "test" / "compaction-recording.ts"
    subprocess.run([bun, str(driver), "produce", str(generated)], check=True, cwd=REPO_ROOT, timeout=120)
    native = json.loads((generated / "attempts.json").read_text(encoding="utf-8"))
    assert native["keys"] == {
        name: list(ledger.door_key(LedgerName(name))) for name, _model in PRODUCED_PLANNING_LEDGERS
    }
    state = generated / "state"
    expected = {
        name: ledger.settle_rows(_raw(state, LedgerName(name), model), ledger.door_key(LedgerName(name)))
        for name, model in PRODUCED_PLANNING_LEDGERS
    }
    assert any(
        isinstance(held.row, PlanRunRow) and held.row.selected_count == 0
        for held in expected["plan-runs"]
    )
    health_rows = [
        FeedHealthStateRow.model_validate(held.row.model_dump())
        for held in expected["feed-health-state"]
    ]
    assert all(row.article_requests is not None for row in health_rows)
    health_spend = sum(row.article_requests for row in health_rows if row.article_requests is not None)
    assert health_spend > 0
    for tier, today in (
        ("daily", date(2026, 10, 23)), ("monthly", date(2026, 11, 3)),
        ("reopened", date(2026, 11, 4)), ("yearly", date(2027, 3, 15)),
    ):
        if tier == "reopened":
            subprocess.run([bun, str(driver), "late", str(generated)], check=True, cwd=REPO_ROOT, timeout=120)
            expected = {
                name: ledger.settle_rows([expected[name], *_raw(state, LedgerName(name), model)], ledger.door_key(LedgerName(name)))
                for name, model in PRODUCED_PLANNING_LEDGERS
            }
        for name, model in PRODUCED_PLANNING_LEDGERS:
            task = f"compact-feed-ingest-plan-{name}"
            declaration = config.load_gardener().tasks[task]
            tuned = declaration.model_copy(update={
                "max_periods_per_run": 400, "daily_keep_days": 1, "monthly_keep_days": 33,
            })
            for _wake in range(3):
                run_declared(task, tuned, generated, today=today, first_year="2026")
            period = Period.DAILY if tier == "daily" else Period.YEARLY if tier == "yearly" else Period.MONTHLY
            covers = "2026-10-20" if period is Period.DAILY else "2026" if period is Period.YEARLY else "2026-10"
            packed = ledger.compact_path(state, LedgerName(name), period, covers)
            assert packed.exists(), f"{name}: genuine {tier} packing did not produce a file"
            assert _snapshot(ledger.load_stored([packed], model=model)) == _snapshot(expected[name])
            assert stored_output.check_compact_period(state, LedgerName(name), period, covers)
        subprocess.run(
            [bun, str(driver), "verify", str(generated), tier], check=True, cwd=REPO_ROOT, timeout=120,
        )


def test_planning_keys_are_trusted_and_never_applied_to_another_ledger(tmp_path: Path) -> None:
    which = LedgerName.FEED_INGEST_PLAN_SELECTED_ARTICLES
    state = tmp_path / "state"
    row = SelectedArticleRow.model_validate(planner_payload("selected-articles"))
    ledger.persist(state, [row], ledger=which, covers=row.date, fmt=Format.PARQUET)
    files = _raw(state, which, SelectedArticleRow)
    with pytest.raises(ValueError, match="declared key"):
        ledger.settle_rows(files, ("__class__",))
    original = files[0][0]
    changed = original.row.model_copy(update={"title": "Different title"})
    conflict = replace(original, row=changed)
    with pytest.raises(ValueError, match="conflicting duplicate"):
        ledger.settle_rows([*files, [conflict]], ledger.door_key(which))
    ledger.persist(state, [changed], ledger=which, covers=row.date, fmt=Format.PARQUET)
    before = {held.path: held.path.read_bytes() for held in ledger.read_day_files(state, which, row.date)}
    task = "compact-feed-ingest-plan-selected-articles"
    refused = run_declared(
        task, config.load_gardener().tasks[task], tmp_path,
        today=date(2026, 10, 22), first_year="2026",
    )
    assert refused.stopped_because is StopReason.FAILED
    assert all(path.read_bytes() == data for path, data in before.items())
    assert not ledger.compact_path(state, which, Period.DAILY, row.date).exists()
    health = FeedHealthStateRow.model_validate(planner_payload("feed-health-state"))
    mixed = tmp_path / "mixed-health"
    with pytest.raises(ValueError, match="one run attempt"):
        ledger.persist(
            mixed, [health, health.model_copy(update={"attempt": 2})],
            ledger=LedgerName.FEED_INGEST_PLAN_FEED_HEALTH_STATE, covers=health.date,
            fmt=Format.PARQUET,
        )
    assert not mixed.exists()
