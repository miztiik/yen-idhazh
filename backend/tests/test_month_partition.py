"""Caller-named telemetry month ranges are real and inclusive."""

from __future__ import annotations

import pytest

from idhazh.month_partition import months_between


def test_months_between_returns_the_named_calendar_months() -> None:
    assert months_between("2025-11", "2026-02") == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]


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
