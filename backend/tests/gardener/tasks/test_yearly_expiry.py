"""Does finite yearly retention delete only due indexed years and preserve restart progress?"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from idhazh import config, ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.knobs.gardener import (
    CompactionPolicy,
    DaysWindow,
    ForeverWindow,
    MonthsWindow,
)
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState
from idhazh.gardener.one_at_a_time import Pass
from idhazh.gardener.tasks import compaction
from idhazh.gardener.tasks._yearly_expiry import expires_at
from idhazh.telemetry.door_prune import take_days

from ._marks import marks_on_disk
from ._task import context_for
from .test_compaction_years import (
    COMPACTION,
    TASK,
    VISUALS,
    a_finished_year,
    compact,
    index_entries,
    state,
)

pytestmark = pytest.mark.contract


def indexed_years(root: Path, years: tuple[str, ...]) -> dict[str, Path]:
    """A bounded tree with three indexes and unreadable files expiry must not download."""
    paths = {}
    for year in years:
        path = ledger.compact_path(state(root), VISUALS, Period.YEARLY, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"expiry deletes by path, never by parsing rows")
        paths[year] = path
    index_entries(
        root,
        Period.YEARLY,
        [CompactEntry(covers=year, rows=1, bytes=paths[year].stat().st_size) for year in years],
    )
    index_entries(root, Period.MONTHLY, [])
    index_entries(root, Period.DAILY, [])
    return paths


def run(root: Path, today: date = date(2030, 1, 1), **changed: object) -> Pass:
    context = context_for(TASK, root, today=today, wake=True)
    policy = CompactionPolicy.model_validate(
        {
            **context.policy.model_dump(mode="json"),
            "dry_run": False,
            "monthly_window": {"unit": "forever"},
            "monthly_keep_days": 93,
            "yearly_keep_months": 36,
            "yearly_prune_enable": True,
            **changed,
        }
    )
    return compaction.run(replace(context, policy=policy))


def test_exact_calendar_expiry_uses_year_end_and_utc() -> None:
    due = expires_at("2026", 36)
    assert due == datetime(2030, 1, 1, tzinfo=UTC)
    assert expires_at("2026", 37) == datetime(2030, 2, 1, tzinfo=UTC)
    assert due - timedelta(microseconds=1) < due
    assert datetime(2030, 1, 1, 2, tzinfo=timezone(timedelta(hours=2))) == due


@pytest.mark.parametrize(
    ("today", "changed", "deleted"),
    [
        (date(2029, 12, 31), {}, False),
        (date(2030, 1, 1), {}, True),
        (date(2030, 1, 1), {"yearly_prune_enable": False}, False),
        (date(2030, 1, 1), {"dry_run": True}, False),
        (date(2030, 1, 1), {"yearly_keep_months": 37}, False),
    ],
)
def test_boundary_toggle_and_dry_run(
    tmp_path: Path, today: date, changed: dict[str, object], deleted: bool
) -> None:
    paths = indexed_years(tmp_path, ("2026", "2027"))
    result = run(tmp_path, today, **changed)
    assert paths["2026"].exists() is not deleted
    assert paths["2027"].exists()
    held = CompactIndex.read(ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY))
    assert held.expired_through == ("2026" if deleted else None)
    if changed.get("dry_run"):
        assert paths["2026"].relative_to(tmp_path).as_posix() in result.taken
    assert not set(result.taken) & set(result.written)


def test_cap_empty_entries_and_restart_after_every_entry_is_deleted(tmp_path: Path) -> None:
    paths = indexed_years(tmp_path, ("2024", "2025", "2026"))
    paths["2025"].unlink()
    index_entries(
        tmp_path,
        Period.YEARLY,
        [
            CompactEntry(covers="2024", rows=1, bytes=paths["2024"].stat().st_size),
            CompactEntry(covers="2025", rows=0, bytes=0, state=EntryState.EMPTY),
            CompactEntry(covers="2026", rows=1, bytes=paths["2026"].stat().st_size),
        ],
    )
    first = run(tmp_path, max_periods_per_run=1)
    assert first.stopped_because is StopReason.CEILING
    assert first.resume_from == "2025"
    assert not paths["2024"].exists() and paths["2026"].exists()
    run(tmp_path, max_periods_per_run=1)
    run(tmp_path, max_periods_per_run=1)
    held = CompactIndex.read(ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY))
    assert held.entries == [] and held.expired_through == "2026"
    assert marks_on_disk(state(tmp_path), VISUALS)[Period.YEARLY] == "2026"
    again = run(tmp_path, max_periods_per_run=1)
    assert not any("/yearly/" in path for path in again.written)
    disabled = run(tmp_path, max_periods_per_run=1, yearly_prune_enable=False)
    assert not any("/yearly/" in path for path in disabled.written)
    assert (
        CompactIndex.read(
            ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY)
        ).expired_through
        == "2026"
    )


def test_all_formats_are_deleted_but_unindexed_files_are_not_walked(tmp_path: Path) -> None:
    indexed_years(tmp_path, ("2026",))
    paths = [
        ledger.compact_path(state(tmp_path), VISUALS, Period.YEARLY, "2026", fmt=fmt)
        for fmt in Format
    ]
    for path in paths:
        path.write_bytes(b"unread rows")
    other = ledger.compact_path(state(tmp_path), VISUALS, Period.YEARLY, "2025")
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b"not indexed")
    result = run(tmp_path)
    assert all(not path.exists() for path in paths)
    assert other.exists()
    assert all(path.relative_to(tmp_path).as_posix() in result.taken for path in paths)


def test_missing_yearly_index_fails_by_name_and_new_tree_initializes(tmp_path: Path) -> None:
    indexed_years(tmp_path, ("2026",))
    index = ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY)
    index.unlink()
    with pytest.raises(ValueError, match=r"index/yearly.json is missing"):
        run(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    run(empty)
    for period in Period:
        held = CompactIndex.read(ledger.compact_index_path(state(empty), VISUALS, period))
        assert held.entries == [] and held.expired_through is None
    fresh = tmp_path / "new"
    from .test_compaction import a_pass, filed

    filed(fresh, a_pass("2029-12-29"))
    run(fresh)
    assert (
        CompactIndex.read(
            ledger.compact_index_path(state(fresh), VISUALS, Period.YEARLY)
        ).expired_through
        is None
    )


def test_corrupt_index_is_not_guessed_empty(tmp_path: Path) -> None:
    paths = indexed_years(tmp_path, ("2026",))
    ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY).write_bytes(b"not json")
    with pytest.raises(ValueError):
        run(tmp_path)
    assert paths["2026"].exists()


def test_authoritative_legacy_tree_onboards_only_with_pruning_explicitly_disabled(
    tmp_path: Path,
) -> None:
    """A trusted pre-expiry tree may rebuild its missing index before enabling deletion."""
    root = a_finished_year(tmp_path)
    index = ledger.compact_index_path(state(root), VISUALS, Period.YEARLY)
    index.unlink()
    with pytest.raises(ValueError, match=r"index/yearly\.json is missing"):
        run(root, date(2027, 4, 5))
    run(root, date(2027, 4, 5), yearly_prune_enable=False)
    held = CompactIndex.read(index)
    assert held.expired_through is None
    assert [entry.covers for entry in held.entries] == ["2026"]
    run(root, date(2027, 4, 5))
    assert CompactIndex.read(index) == held


def test_recovery_never_adopts_expired_months(tmp_path: Path) -> None:
    indexed_years(tmp_path, ("2026",))
    run(tmp_path)
    stale = ledger.compact_path(state(tmp_path), VISUALS, Period.MONTHLY, "2026-12")
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"must not be adopted")
    ledger.compact_index_path(state(tmp_path), VISUALS, Period.MONTHLY).unlink()
    run(tmp_path)
    held = CompactIndex.read(ledger.compact_index_path(state(tmp_path), VISUALS, Period.MONTHLY))
    assert not any(entry.covers.startswith("2026") for entry in held.entries)
    assert stale.exists()


def test_old_indexes_migrate_and_expiry_only_belongs_to_yearly() -> None:
    held = CompactIndex.model_validate(
        {"version": "2026-10-04", "ledger": VISUALS, "period": "yearly", "entries": []}
    )
    assert held.expired_through is None
    for period in (Period.DAILY, Period.MONTHLY):
        with pytest.raises(ValueError, match="may not set expired_through"):
            CompactIndex(
                version=CompactIndex.schema_version(),
                ledger=VISUALS,
                period=period,
                entries=[],
                expired_through="2026",
            )
    with pytest.raises(ValueError, match="at or before expired_through"):
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=VISUALS,
            period=Period.YEARLY,
            entries=[CompactEntry(covers="2026", rows=0, bytes=0, state=EntryState.EMPTY)],
            expired_through="2026",
        )


def test_manual_pruning_preserves_the_expiry_mark(tmp_path: Path) -> None:
    root = a_finished_year(tmp_path)
    compact(
        root,
        date(2027, 4, 5),
        monthly_window={"unit": "forever"},
        monthly_keep_days=93,
    )
    path = ledger.compact_index_path(state(root), VISUALS, Period.YEARLY)
    held = CompactIndex.read(path)
    assert held.entries
    path.write_bytes(held.model_copy(update={"expired_through": "2025"}).to_json().encode("ascii"))
    take_days(
        state(root),
        VISUALS,
        since="2026-01-05",
        until="2026-01-05",
        ceiling=1,
        dry_run=False,
        identity=COMPACTION,
    )
    assert CompactIndex.read(path).expired_through == "2025"


def test_reader_floor_is_finite_and_toggle_restores_forever(tmp_path: Path) -> None:
    policy = context_for(TASK, tmp_path).policy
    assert isinstance(policy, CompactionPolicy)
    policy = CompactionPolicy.model_validate(
        {
            **policy.model_dump(mode="json"),
            "monthly_window": {"unit": "forever"},
            "monthly_keep_days": 93,
            "yearly_keep_months": 36,
            "yearly_prune_enable": True,
        }
    )
    for days in (90, 366, 730, 36 * 28):
        assert config.compaction_reaches(policy, DaysWindow(unit="days", value=days))
    assert not config.compaction_reaches(policy, DaysWindow(unit="days", value=36 * 28 + 1))
    assert not config.compaction_reaches(policy, ForeverWindow(unit="forever"))
    assert config.compaction_reaches(policy, MonthsWindow(unit="months", value=36))
    assert not config.compaction_reaches(policy, MonthsWindow(unit="months", value=37))
    disabled = CompactionPolicy.model_validate(
        {**policy.model_dump(mode="json"), "yearly_prune_enable": False}
    )
    assert config.compaction_reaches(disabled, ForeverWindow(unit="forever"))
