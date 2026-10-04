"""Which closed periods may a scheduled gardener task list?"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from idhazh import month_partition
from idhazh.contracts.knobs.gardener import CompactionPolicy, RetentionPolicy
from idhazh.gardener.period_inputs import paths_for_task, scheduled_range

from ._garden import GARDENER_FIXTURES


def _compaction_policy() -> CompactionPolicy:
    path = GARDENER_FIXTURES / "runner" / "compact-gardener.json"
    return CompactionPolicy.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _monthly_fold_policy() -> RetentionPolicy:
    return RetentionPolicy.model_validate(
        {
            "kind": "retention",
            "lifecycle_status": "active",
            "dry_run": True,
            "max_deletes_per_run": None,
            "owns": ["state/candidate-models"],
            "window": {"unit": "forever"},
            "fold": {"after_days": 1, "dry_run": False, "settles_months": True},
        }
    )


def _ledger_reader_policy() -> RetentionPolicy:
    """A retention task that reads one ledger's packed and raw files, as telemetry-aggregate does."""
    return RetentionPolicy.model_validate(
        {
            "kind": "retention",
            "lifecycle_status": "active",
            "dry_run": True,
            "max_deletes_per_run": None,
            "owns": ["state/item-health-summary"],
            "reads": ["state/compact/item-health", "state/raw/item-health"],
            "window": {"unit": "months", "value": 14},
        }
    )


def _named(root: Path, paths: tuple[Path, ...]) -> list[str]:
    """Each path as a repository path, in text order on every platform."""
    return sorted(path.relative_to(root).as_posix() for path in paths)


def test_compaction_range_uses_its_configured_month_lookback() -> None:
    policy = _compaction_policy()

    default_range = scheduled_range("compact-gardener", policy, date(2026, 9, 27))
    configured = policy.model_copy(update={"lookback": 4})
    configured_range = scheduled_range("compact-gardener", configured, date(2026, 9, 27))

    assert policy.lookback_periods == 2
    assert default_range is not None
    assert configured_range is not None
    assert len(month_partition.months_between(*default_range)) == 3
    assert len(month_partition.months_between(*configured_range)) == 5


def test_a_compaction_names_its_month_its_year_and_its_ledger_s_marks_and_nothing_else(
    tmp_path: Path,
) -> None:
    """A listing that lost a mark would hand the pass an index or watermark it reads as absent."""
    paths = paths_for_task(
        tmp_path,
        "compact-gardener",
        _compaction_policy(),
        ("2026-08", "2026-08"),
        today=date(2026, 9, 27),
    )

    assert _named(tmp_path, paths) == [
        "state/compact/gardener/daily/2026/08",
        "state/compact/gardener/daily/watermark.json",
        "state/compact/gardener/index/daily.json",
        "state/compact/gardener/index/monthly.json",
        "state/compact/gardener/index/yearly.json",
        "state/compact/gardener/monthly/2026/08.json",
        "state/compact/gardener/monthly/2026/08.parquet",
        "state/compact/gardener/monthly/watermark.json",
        "state/compact/gardener/yearly/2026/2026.json",
        "state/compact/gardener/yearly/2026/2026.parquet",
        "state/compact/gardener/yearly/watermark.json",
    ]


def test_a_task_that_reads_a_ledger_names_its_day_and_the_ledger_s_marks_and_nothing_else(
    tmp_path: Path,
) -> None:
    paths = paths_for_task(
        tmp_path,
        "telemetry-aggregate",
        _ledger_reader_policy(),
        ("2026-09-20", "2026-09-20"),
        today=date(2026, 9, 27),
    )

    assert _named(tmp_path, paths) == [
        "state/compact/item-health/daily/2026/09/20.json",
        "state/compact/item-health/daily/2026/09/20.parquet",
        "state/compact/item-health/daily/watermark.json",
        "state/compact/item-health/index/daily.json",
        "state/compact/item-health/index/monthly.json",
        "state/compact/item-health/index/yearly.json",
        "state/compact/item-health/monthly/watermark.json",
        "state/compact/item-health/yearly/2026/2026.json",
        "state/compact/item-health/yearly/2026/2026.parquet",
        "state/compact/item-health/yearly/watermark.json",
        "state/item-health-summary/2026/09/20",
        "state/item-health-summary/2026/09/20.csv",
        "state/item-health-summary/2026/09/20.json",
        "state/item-health-summary/2026/09/20.jsonl",
        "state/item-health-summary/2026/09/20.parquet",
        "state/raw/item-health/2026/09/20",
    ]


def test_monthly_fold_also_lists_its_fixed_closed_day_window(tmp_path: Path) -> None:
    policy = _monthly_fold_policy()
    assert policy.fold is not None
    policy = policy.model_copy(
        update={"fold": policy.fold.model_copy(update={"settles_months": True})}
    )
    today = date(2026, 10, 1)
    period_range = scheduled_range("candidate-models", policy, today)

    assert period_range is not None
    months = month_partition.months_between(*period_range)
    assert len(months) == 3

    paths = paths_for_task(
        tmp_path,
        "candidate-models",
        policy,
        period_range,
        today=today,
    )
    root = tmp_path / "state" / "candidate-models"
    assert root / "2026" / "08" in paths
    assert root / "2026" / "09" / "29" in paths
    assert root / "2026" / "09" / "21" not in paths
