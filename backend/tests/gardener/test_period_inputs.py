"""Which closed periods may a scheduled gardener task list?"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from conftest import CONFIG_DIR

from idhazh import ledger, month_partition
from idhazh.contracts.knobs.gardener import CompactionPolicy, RetentionPolicy
from idhazh.gardener.period_inputs import paths_for_task, periods_in_range, scheduled_range

from ._garden import GARDENER_FIXTURES


def _compaction_policy() -> CompactionPolicy:
    path = GARDENER_FIXTURES / "runner" / "compact-gardener.json"
    return CompactionPolicy.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _monthly_fold_policy() -> RetentionPolicy:
    path = CONFIG_DIR / "gardener" / "feed-health.json"
    return RetentionPolicy.model_validate(json.loads(path.read_text(encoding="utf-8")))


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


def test_compaction_inputs_do_not_name_retired_raw_indexes(tmp_path: Path) -> None:
    policy = _compaction_policy()
    today = date(2026, 9, 27)
    period_range = scheduled_range("compact-gardener", policy, today)

    assert period_range is not None
    days, _ = periods_in_range(period_range)
    paths = set(
        paths_for_task(
            tmp_path,
            "compact-gardener",
            policy,
            period_range,
            today=today,
        )
    )
    old_indexes = {
        ledger.raw_index_path(tmp_path / "state", policy.ledger, day.isoformat())
        for day in days
    }

    assert paths.isdisjoint(old_indexes)


def test_monthly_fold_also_lists_its_fixed_closed_day_window(tmp_path: Path) -> None:
    policy = _monthly_fold_policy()
    assert policy.fold is not None
    policy = policy.model_copy(
        update={"fold": policy.fold.model_copy(update={"settles_months": True})}
    )
    today = date(2026, 10, 1)
    period_range = scheduled_range("feed-health", policy, today)

    assert period_range is not None
    months = month_partition.months_between(*period_range)
    assert len(months) == 3

    paths = paths_for_task(
        tmp_path,
        "feed-health",
        policy,
        period_range,
        today=today,
    )
    root = tmp_path / "state" / "feed-health"
    assert root / "2026" / "08" in paths
    assert root / "2026" / "09" / "29" in paths
    assert root / "2026" / "09" / "21" not in paths
