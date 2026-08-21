"""Unit-tier tests for the retention job and the site-budget alarm.

The prune is the most dangerous code in this repository - it is the only thing
that deletes a published byte - so the tests are written around the ways it goes
wrong rather than the way it goes right.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from idhazh.contracts.app_config import RetentionConfig
from idhazh.retention import (
    PAGES_HARD_CAP_MB,
    cutoff,
    headroom_mb,
    measure,
    over_budget,
    prune,
    visuals_older_than,
)


def site(root: Path, days: dict[str, list[str]]) -> Path:
    for day, files in days.items():
        year, month, number = day.split("-")
        folder = root / year / month / number
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "digest.json").write_text(f'{{"date": "{day}"}}', encoding="utf-8")
        for name in files:
            (folder / name).write_bytes(b"x" * 1000)
    return root


# --- The alarm, on from the first run ---------------------------------------


def test_an_absent_site_measures_as_nothing(tmp_path: Path) -> None:
    assert measure(tmp_path / "missing").bytes_used == 0


def test_the_site_is_measured_every_run(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a.webp", "b.webp"]})
    size = measure(root)
    assert size.files == 3
    assert size.bytes_used > 2000


def test_the_alarm_fires_below_the_platform_ceiling(tmp_path: Path) -> None:
    """There has to be room to act between the alarm and the wall."""
    config = RetentionConfig()
    assert config.site_budget_mb < PAGES_HARD_CAP_MB


def test_a_small_site_is_not_over_budget(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a.webp"]})
    assert not over_budget(measure(root), RetentionConfig())


def test_headroom_is_measured_against_the_hard_cap(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a.webp"]})
    assert headroom_mb(measure(root)) == pytest.approx(PAGES_HARD_CAP_MB, abs=1)


# --- Retention ships disabled ------------------------------------------------


def test_retention_is_off_by_default() -> None:
    """A default is a promise, not a placeholder."""
    config = RetentionConfig()
    assert config.image_months == -1
    assert config.dry_run is True
    assert cutoff(date(2026, 8, 21), config.image_months) is None


def test_a_disabled_policy_deletes_nothing(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})
    result = prune(root, RetentionConfig(), date(2026, 8, 21))
    assert result.deleted == 0
    assert (root / "2020" / "01" / "01" / "old.webp").exists()


# --- What may be deleted, and what may never be -------------------------------


def test_only_visuals_are_candidates(tmp_path: Path) -> None:
    """The payload is the record that a day happened. Text is never pruned."""
    root = site(tmp_path, {"2020-01-01": ["old.webp", "notes.txt"]})
    found = visuals_older_than(root, date(2026, 8, 21))
    assert [path.name for path in found] == ["old.webp"]


def test_a_recent_day_is_never_a_candidate(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["new.webp"]})
    assert visuals_older_than(root, date(2026, 1, 1)) == []


def test_a_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})
    config = RetentionConfig(image_months=6, dry_run=True)
    result = prune(root, config, date(2026, 8, 21))
    assert result.considered == 1
    assert result.deleted == 0
    assert (root / "2020" / "01" / "01" / "old.webp").exists()


def test_an_enabled_policy_deletes_the_old_visual_and_keeps_the_day(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})
    config = RetentionConfig(image_months=6, dry_run=False)
    result = prune(root, config, date(2026, 8, 21))
    assert result.deleted == 1
    assert not (root / "2020" / "01" / "01" / "old.webp").exists()
    assert (root / "2020" / "01" / "01" / "digest.json").exists(), "the day survives its picture"


def test_the_fuse_caps_what_one_run_can_delete(tmp_path: Path) -> None:
    """An off-by-one in a date parse must not eat the archive."""
    root = site(tmp_path, {"2020-01-01": [f"{n}.webp" for n in range(10)]})
    config = RetentionConfig(image_months=6, dry_run=False, max_deletes_per_run=3)
    result = prune(root, config, date(2026, 8, 21))
    assert result.deleted == 3
    assert result.fuse_tripped
    assert result.considered == 10


def test_a_directory_that_is_not_a_date_is_left_alone(tmp_path: Path) -> None:
    stray = tmp_path / "assets" / "brand"
    stray.mkdir(parents=True)
    (stray / "logo.svg").write_bytes(b"x" * 10)
    config = RetentionConfig(image_months=1, dry_run=False)
    assert prune(tmp_path, config, date(2026, 8, 21)).deleted == 0
    assert (stray / "logo.svg").exists()
