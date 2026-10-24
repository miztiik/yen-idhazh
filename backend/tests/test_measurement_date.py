"""Resolve a budget measurement's date without borrowing the host's local day."""

from datetime import date, datetime

import pytest

from utilities.measure_budgets import parse_args, resolve_measurement_date

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("instant", "taken_on", "expected"),
    [
        ("2027-01-01T00:30:00+02:00", None, date(2026, 12, 31)),
        ("2026-12-31T23:30:00-02:00", None, date(2027, 1, 1)),
        ("2027-01-01T00:30:00+02:00", "2026-06-15", date(2026, 6, 15)),
    ],
    ids=["east-of-utc-year-end", "west-of-utc-year-end", "operator-date"],
)
def test_measurement_date_uses_the_utc_day_unless_the_operator_supplies_one(
    instant: str, taken_on: str | None, expected: date
) -> None:
    argv = ["read", "--runner", "date-resolution-test"]
    if taken_on is not None:
        argv += ["--taken-on", taken_on]
    args = parse_args(argv)

    assert resolve_measurement_date(
        args.taken_on, now=datetime.fromisoformat(instant)
    ) == expected


def test_measurement_date_refuses_an_instant_without_a_utc_offset() -> None:
    with pytest.raises(ValueError, match="must include a UTC offset"):
        resolve_measurement_date(None, now=datetime(2027, 1, 1))
