"""Which closed periods may a scheduled gardener task list?"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from idhazh import config
from idhazh.contracts.knobs.gardener import CompactionPolicy, RetentionPolicy
from idhazh.gardener.period_inputs import paths_for_task, scheduled_range


def _ledger_reader_policy() -> RetentionPolicy:
    """A retention task that reads one ledger's packed and raw files, as telemetry-aggregate does."""
    return RetentionPolicy.model_validate(
        {
            "kind": "retention",
            "lifecycle_status": "active",
            "dry_run": True,
            "max_deletes_per_run": None,
            "owns": ["frontend/public/telemetry"],
            "appends_to": ["item-health-summary"],
            "reads": [
                "state/compact/item-health",
                "state/raw/item-health",
                "state/raw/item-health-summary",
            ],
            "window": {"unit": "months", "value": 14},
        }
    )


def _named(root: Path, paths: tuple[Path, ...]) -> list[str]:
    """Each path as a repository path, in text order on every platform."""
    return sorted(path.relative_to(root).as_posix() for path in paths)


def test_every_compaction_names_its_ledger_s_marks_and_nothing_else(tmp_path: Path) -> None:
    """A compaction's steps name the periods they choose, so the planner names only marks.

    A scheduled wake builds no window for a compaction, and a range a person
    names limits what the steps choose, not what the listing starts with. A
    ledger's marks are its three indexes; a listing that lost one would hand the
    pass an index it reads as absent, and rebuilds.
    """
    today = date(2026, 9, 27)
    compactions = {
        name: policy
        for name, policy in config.load_gardener().tasks.items()
        if isinstance(policy, CompactionPolicy) and not name.startswith("compact-trial-")
    }

    assert compactions, "config/idhazh_gardener.json names no compaction"
    for name, policy in compactions.items():
        compact = f"state/compact/{policy.ledger.value}"
        assert scheduled_range(name, policy, today) is None, name
        for period_range in (None, ("2026-08", "2026-08")):
            assert _named(
                tmp_path, paths_for_task(tmp_path, name, policy, period_range, today=today)
            ) == [
                f"{compact}/index/daily.json",
                f"{compact}/index/monthly.json",
                f"{compact}/index/yearly.json",
            ], (name, period_range)


def test_a_trial_compaction_lists_only_its_declared_root_indexes(tmp_path: Path) -> None:
    policy = config.load_gardener().tasks["compact-trial-item-health"]
    assert isinstance(policy, CompactionPolicy)

    paths = paths_for_task(tmp_path, "compact-trial-item-health", policy, None, today=date(2026, 9, 27))

    expected = {
        tmp_path / root / "compact" / "item-health" / "index" / f"{period}.json"
        for root in policy.state_roots
        for period in ("daily", "monthly", "yearly")
    }
    assert set(paths) == expected
    assert tmp_path / "state" / "compact" / "item-health" / "index" / "daily.json" not in paths


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
        "frontend/public/telemetry/2026/09/20",
        "frontend/public/telemetry/2026/09/20.csv",
        "frontend/public/telemetry/2026/09/20.json",
        "frontend/public/telemetry/2026/09/20.jsonl",
        "frontend/public/telemetry/2026/09/20.parquet",
        "state/compact/item-health/daily/2026/09/20.json",
        "state/compact/item-health/daily/2026/09/20.parquet",
        "state/compact/item-health/index/daily.json",
        "state/compact/item-health/index/monthly.json",
        "state/compact/item-health/index/yearly.json",
        "state/compact/item-health/yearly/2026/2026.json",
        "state/compact/item-health/yearly/2026/2026.parquet",
        "state/raw/item-health-summary/2026/09/20",
        "state/raw/item-health/2026/09/20",
    ]


def test_a_c1_case_traces_folder_lists_each_named_day_folder(tmp_path: Path) -> None:
    """A nested traces root uses the generic dated tree branch, not the old trial prefix."""
    policy = RetentionPolicy.model_validate(
        {
            "kind": "retention",
            "lifecycle_status": "active",
            "dry_run": True,
            "max_deletes_per_run": None,
            "owns": ["state/pipeline-tests/case-2026-09-20/traces"],
            "window": {"unit": "days", "value": 90},
        }
    )

    paths = paths_for_task(
        tmp_path,
        "trials",
        policy,
        ("2026-09-20", "2026-09-22"),
        today=date(2026, 9, 27),
    )

    root = tmp_path / "state" / "pipeline-tests" / "case-2026-09-20" / "traces"
    assert root / "2026" / "09" / "20" in paths
    assert root / "2026" / "09" / "21" in paths
    assert root / "2026" / "09" / "22" in paths
