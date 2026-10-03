"""Caller-named telemetry month ranges are real and inclusive."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from idhazh.month_partition import day_bounds, expired_months, months_before, months_between


def test_months_between_returns_the_named_calendar_months() -> None:
    assert months_between("2025-11", "2026-02") == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]


def test_month_files_are_selected_from_the_named_months(tmp_path: Path) -> None:
    from idhazh.month_partition import month_files

    for month in ("2025-12", "2026-01", "2026-02"):
        (tmp_path / f"{month}.csv").write_text(month, encoding="ascii")
    (tmp_path / "notes.csv").write_text("stray", encoding="ascii")

    assert month_files(tmp_path, ".csv", ["2026-02", "2025-12"]) == [
        tmp_path / "2025-12.csv",
        tmp_path / "2026-02.csv",
    ]
    assert month_files(tmp_path, ".csv", []) == []


def test_expired_months_are_a_fixed_window_before_the_retention_boundary() -> None:
    assert expired_months(date(2026, 10, 3), 14, 2) == ["2025-07", "2025-08"]
    assert months_before("2026-01", 2) == ["2025-11", "2025-12"]


def test_month_range_uses_valid_day_bounds_for_day_only_reports() -> None:
    assert day_bounds("2025-12", "2026-02") == ("2025-12-01", "2026-02-28")


@pytest.mark.parametrize(
    ("first", "last"),
    [
        ("2026-13", "2026-13"),
        ("2026-01", "2025-12"),
        ("2026-1", "2026-02"),
    ],
)
def test_months_between_refuses_invalid_or_reversed_endpoints(first: str, last: str) -> None:
    with pytest.raises(ValueError):
        months_between(first, last)
