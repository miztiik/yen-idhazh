"""The dwell: how long a source has been under the mark, and when that retires it.

One question a test. The share itself, the evidence floors and the alarm
sentence are `test_source_health.py`'s; this file owns only the run length and
the date it completes.

Every day is built here rather than read out of `state/`, which also buys the
cases the archive has never produced - a run broken by one good day, a source
that decided nothing in the middle of one (CLAUDE.md section 13).
"""

from __future__ import annotations

import pytest

from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause
from idhazh.contracts.source_health_view import (
    DayYield,
    SourceAvailability,
    SourceHealthRow,
    SourceHealthView,
    SourcePermission,
)
from idhazh.contracts.sources import FeedDef
from idhazh.contracts.taxonomy import SourceTier
from idhazh.telemetry import source_health
from idhazh.telemetry.publish.source_health import dwell, retires_on

ALARM = 0.5

FEEDS = [
    FeedDef(
        id="quiet-wire",
        title="Quiet Wire",
        vertical="ai",
        url="https://quiet.test/f",
        tier=SourceTier.TRADE_PRESS,
    )
]


def judged_view() -> SourceHealthView:
    """A view whose one source has cleared both floors and completed its dwell.

    Built rather than read, so the case exists at all: no committed day has ever
    carried a completed dwell, because nothing has counted one until now.
    """
    days = run("u", "u", start=15)
    return SourceHealthView(
        version=SourceHealthView.schema_version(),
        generated_at="2026-09-16T06:20:00Z",
        run_id="2026-09-16-2",
        headline_sentence="One source is under the mark.",
        reliability_floor=0.5,
        reliability_window_days=30,
        min_complete_days=2,
        complete_dates=2,
        yield_readable=True,
        first_date="2026-09-15",
        last_date="2026-09-16",
        yield_alarm_point=ALARM,
        yield_alarm_min_decisions=1,
        dwell_days=2,
        auto_retire=True,
        dwell_dates=("2026-09-15", "2026-09-16"),
        sources=[
            SourceHealthRow(
                source_id="quiet-wire",
                title="Quiet Wire",
                vertical="ai",
                permission=SourcePermission.ALLOWED,
                availability=SourceAvailability.ANSWERING,
                retired=False,
                opportunities=20,
                publications=2,
                source_failures=18,
                reliability=1.0,
                reliability_reads=4,
                recent_days=tuple(days),
                days_under_the_mark=2,
                retires_on="2026-09-16",
            )
        ],
    )


def day(date: str, *, published: int, failed: int) -> DayYield:
    return DayYield(
        date=date,
        opportunities=published + failed,
        publications=published,
        source_failures=failed,
    )


def run(*shares: str, start: int = 1) -> list[DayYield]:
    """A strip spelled as characters: `u` under the mark, `a` at or above, `n` nothing."""
    built: list[DayYield] = []
    for offset, mark in enumerate(shares):
        date = f"2026-09-{start + offset:02d}"
        match mark:
            case "u":
                built.append(day(date, published=1, failed=9))
            case "a":
                built.append(day(date, published=9, failed=1))
            case "n":
                built.append(day(date, published=0, failed=0))
            case _:  # pragma: no cover - a typo in a test is a test bug
                raise ValueError(f"unknown mark {mark!r}")
    return built


def test_the_dwell_counts_only_the_unbroken_run_at_the_newest_end() -> None:
    assert dwell(run("u", "u", "u"), alarm_point=ALARM) == 3
    assert dwell(run("a", "u", "u"), alarm_point=ALARM) == 2


def test_one_day_back_at_the_mark_resets_the_dwell_to_zero() -> None:
    """A source that recovered keeps its place. This is the clause that makes it safe."""
    assert dwell(run("u", "u", "u", "u", "a"), alarm_point=ALARM) == 0


def test_a_fortnight_of_scattered_bad_days_retires_nothing() -> None:
    assert dwell(run("u", "a", "u", "a", "u", "a", "u", "a"), alarm_point=ALARM) == 0


def test_a_day_that_decided_nothing_neither_condemns_nor_clears() -> None:
    """It has no share, so the run reads through it rather than ending on it."""
    assert dwell(run("u", "n", "u"), alarm_point=ALARM) == 2
    assert dwell(run("a", "n", "u"), alarm_point=ALARM) == 1
    assert dwell(run("n", "n", "n"), alarm_point=ALARM) == 0


def test_a_source_exactly_on_the_mark_is_not_under_it() -> None:
    on_the_nose = [day("2026-09-01", published=5, failed=5)]

    assert dwell(on_the_nose, alarm_point=ALARM) == 0


def test_an_empty_strip_has_no_dwell_and_no_date() -> None:
    assert dwell([], alarm_point=ALARM) == 0
    assert retires_on([], under=0, dwell_days=14) is None


def test_the_retirement_date_counts_from_the_newest_day_the_ledger_holds() -> None:
    """Never from a wall clock: a console re-opened at midnight must not move it."""
    days = run("u", "u", "u", start=1)

    assert retires_on(days, under=3, dwell_days=14) == "2026-09-14"
    assert retires_on(days, under=14, dwell_days=14) == "2026-09-03"


def test_no_dwell_means_no_date() -> None:
    assert retires_on(run("a", "a"), under=0, dwell_days=14) is None


def test_a_completed_dwell_files_one_row_naming_the_days_it_rests_on() -> None:
    """The evidence is days, because a day the schedule fired five times is one day."""
    filed = source_health.low_yield_retirements(
        FEEDS,
        view=judged_view(),
        already=(),
        date="2026-09-16",
        run_id="2026-09-16-2",
    )

    assert [row.feed_id for row in filed] == ["quiet-wire"]
    assert filed[0].cause is RetirementCause.LOW_YIELD
    assert filed[0].evidence_dates == ("2026-09-15", "2026-09-16")
    assert filed[0].evidence_run_ids == ()


def test_a_retirement_already_on_the_ledger_is_not_filed_twice() -> None:
    first = source_health.low_yield_retirements(
        FEEDS, view=judged_view(), already=(), date="2026-09-16", run_id="2026-09-16-2"
    )

    again = source_health.low_yield_retirements(
        FEEDS,
        view=judged_view(),
        already={row.endpoint_key for row in first},
        date="2026-09-16",
        run_id="2026-09-16-3",
    )

    assert again == []


def test_a_source_whose_date_has_not_arrived_is_not_retired() -> None:
    filed = source_health.low_yield_retirements(
        FEEDS,
        view=judged_view(),
        already=(),
        date="2026-09-15",
        run_id="2026-09-15-1",
    )

    assert filed == []


def test_the_two_causes_fill_two_different_evidence_cells() -> None:
    """A row carrying neither is a retirement nobody can check."""

    def row(**named: object) -> FeedRetirementRow:
        return FeedRetirementRow(
            version=FeedRetirementRow.schema_version(),
            feed_id="quiet-wire",
            endpoint_key="a" * 64,
            retired_on="2026-09-16",
            decided_by_run="2026-09-16-2",
            **named,  # type: ignore[arg-type]
        )

    gone = row(cause=RetirementCause.HTTP_410, evidence_run_ids=("2026-09-16-2",))
    quiet = row(cause=RetirementCause.LOW_YIELD, evidence_dates=("2026-09-16",))

    assert gone.evidence_dates == ()
    assert quiet.evidence_run_ids == ()
    with pytest.raises(ValueError, match="read the 410"):
        row(cause=RetirementCause.HTTP_410, evidence_dates=("2026-09-16",))
    with pytest.raises(ValueError, match="stayed under the mark"):
        row(cause=RetirementCause.LOW_YIELD, evidence_run_ids=("2026-09-16-2",))


def test_a_retirement_row_survives_the_csv_round_trip_on_either_cause() -> None:
    """Each evidence list is one cell, so the header cannot grow with the evidence."""
    row = FeedRetirementRow(
        version=FeedRetirementRow.schema_version(),
        feed_id="quiet-wire",
        endpoint_key="a" * 64,
        retired_on="2026-09-16",
        decided_by_run="2026-09-16-2",
        cause=RetirementCause.LOW_YIELD,
        evidence_dates=("2026-09-15", "2026-09-16"),
    )

    assert FeedRetirementRow.from_csv_row(row.csv_row()) == row


def test_a_row_written_before_the_dates_column_still_reads() -> None:
    """A committed file has no `evidence_dates` header, and its absence is no evidence."""
    row = FeedRetirementRow(
        version=FeedRetirementRow.schema_version(),
        feed_id="dead-wire",
        endpoint_key="b" * 64,
        retired_on="2026-08-27",
        decided_by_run="2026-08-27-3",
        cause=RetirementCause.HTTP_410,
        evidence_run_ids=("2026-08-26-1", "2026-08-27-3"),
    )
    older = {name: cell for name, cell in row.csv_row().items() if name != "evidence_dates"}

    assert FeedRetirementRow.from_csv_row(older) == row
