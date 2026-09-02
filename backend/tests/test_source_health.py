"""Unit-tier tests for the source-health reducer, and one ledger gate beside them.

Everything under the first heading is a fold over rows held in memory: no
network, no clock, no file. That is the point of the module under test - a rule
that decides whether an address is asked again has to be checkable without
standing up a run.

The one exception is the last section. Two stale checkouts appending the same
retirement is a fact about a file and a merge driver, so it is proved against a
file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh import ledger, source_health
from idhazh.contracts.feed_health import (
    FeedHealthRow,
    FetchOutcome,
    RobotsOutcome,
    derive_endpoint_key,
)
from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause
from idhazh.contracts.sources import FeedDef
from idhazh.contracts.taxonomy import LifecycleStatus, SourceTier

DATE = "2026-09-02"
FEED_URL = "https://trade.example-press.net/feed"
OTHER_URL = "https://blog.example-lab.org/feed"
KEY = derive_endpoint_key(FEED_URL)
OTHER_KEY = derive_endpoint_key(OTHER_URL)

TRADE = FeedDef(
    id="trade-press",
    vertical="ai",
    title="Example Trade Press",
    url=FEED_URL,
    tier=SourceTier.TRADE_PRESS,
)
LAB = FeedDef(
    id="lab-blog",
    vertical="ai",
    title="Example Lab",
    url=OTHER_URL,
    tier=SourceTier.INSTITUTION,
)

#: The rule under test, at its committed value. Five distinct runs.
RETIRE_AFTER = 5


def row(
    n: int,
    outcome: FetchOutcome,
    *,
    status: int | None = None,
    items: int = 0,
    key: str | None = KEY,
    feed_id: str = "trade-press",
    robots: RobotsOutcome | None = None,
) -> FeedHealthRow:
    """One feed's account of one run. `n` is the run, oldest first."""
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=f"{DATE}-{n}",
        date=DATE,
        feed_id=feed_id,
        checked_at=f"2026-09-02T{n:02d}:00:00Z",
        outcome=outcome,
        status=status,
        items=items,
        endpoint_key=key,
        robots_outcome=robots,
    )


def gone(n: int, **kwargs: object) -> FeedHealthRow:
    """The one result that counts toward a retirement."""
    return row(n, FetchOutcome.PERMANENT, status=410, **kwargs)  # type: ignore[arg-type]


def answered(n: int, **kwargs: object) -> FeedHealthRow:
    """A read that carried entries - the one result that clears the count."""
    return row(n, FetchOutcome.OK, status=200, items=7, **kwargs)  # type: ignore[arg-type]


def runs_gone(history: list[FeedHealthRow], key: str = KEY) -> int:
    record = source_health.endpoint_records(history).get(key)
    return 0 if record is None else len(record.gone_runs)


# --- the decision table: what each kind of evidence does to the 410 count -----


def test_five_distinct_runs_reading_gone_retire_the_address() -> None:
    """The whole rule, in one line. Only `410` says the address is not coming back."""
    history = [gone(n) for n in range(1, RETIRE_AFTER + 1)]
    record = source_health.endpoint_records(history)[KEY]
    assert record.gone_runs == tuple(f"{DATE}-{n}" for n in range(1, RETIRE_AFTER + 1))
    assert record.retires(after_runs=RETIRE_AFTER)


def test_four_runs_reading_gone_do_not() -> None:
    """One short is not enough, which is what makes the number a rule rather than a mood."""
    history = [gone(n) for n in range(1, RETIRE_AFTER)]
    assert not source_health.endpoint_records(history)[KEY].retires(after_runs=RETIRE_AFTER)


def test_one_run_written_down_five_times_is_one_run() -> None:
    """A second attempt at one run appends its own row, and the union merge keeps both.

    Counted raw, one bad afternoon retrying itself would retire an address on
    its own. The evidence is distinct runs, so the reducer settles first and
    then counts run ids rather than lines.
    """
    history = [gone(1) for _ in range(RETIRE_AFTER)]
    assert runs_gone(history) == 1
    assert not source_health.endpoint_records(history)[KEY].retires(after_runs=RETIRE_AFTER)


def test_a_read_that_carried_entries_clears_the_count() -> None:
    """The address answers, so whatever it said before is history."""
    history = [gone(1), gone(2), gone(3), answered(4), gone(5)]
    assert runs_gone(history) == 1


@pytest.mark.parametrize(
    ("name", "middle"),
    [
        ("an empty success", row(3, FetchOutcome.OK, status=200, items=0)),
        ("a block", row(3, FetchOutcome.BLOCKED)),
        ("another permanent status", row(3, FetchOutcome.PERMANENT, status=404)),
        ("a transient failure", row(3, FetchOutcome.TRANSIENT, status=503)),
        ("a robots refusal", row(3, FetchOutcome.ROBOTS_DENIED, robots=RobotsOutcome.DENIED)),
        ("a rest", row(3, FetchOutcome.SKIPPED)),
    ],
    ids=lambda value: value if isinstance(value, str) else "row",
)
def test_only_a_real_success_clears_the_count(name: str, middle: FeedHealthRow) -> None:
    """Every other cell of the table leaves the count where it is.

    An empty success is the sharp one. It adds an availability strike, because a
    feed that parses to nothing is not working - and it says nothing at all
    about whether the address is permanently gone, so it may not launder a
    server that has been answering `410`.
    """
    history = [gone(1), gone(2), middle, gone(4), gone(5), gone(6)]
    assert runs_gone(history) == RETIRE_AFTER, name


def test_a_row_that_cannot_say_which_address_it_asked_is_no_evidence() -> None:
    """Every row committed before 2026-09-02 carries an empty `endpoint_key`.

    Backfilling one from today's config was refused when the column landed: the
    configured URL may have moved since, so a guess would file a retirement
    against an address that never failed. An unkeyed row therefore evidences
    nothing here, and the first automatic retirement can only rest on rows
    written after the writer started filling the cell.
    """
    history = [gone(n, key=None) for n in range(1, RETIRE_AFTER + 1)]
    assert source_health.endpoint_records(history) == {}


def test_two_addresses_keep_two_counts() -> None:
    """The record is per address, so one dead feed cannot retire a healthy sibling."""
    history = [gone(n) for n in range(1, RETIRE_AFTER + 1)]
    history += [answered(n, key=OTHER_KEY, feed_id="lab-blog") for n in range(1, 3)]
    records = source_health.endpoint_records(history)
    assert records[KEY].retires(after_runs=RETIRE_AFTER)
    assert not records[OTHER_KEY].retires(after_runs=RETIRE_AFTER)


# --- the decision table: permission ------------------------------------------


@pytest.mark.parametrize(
    ("answer", "permitted"),
    [
        (RobotsOutcome.ALLOWED, True),
        (RobotsOutcome.DENIED, False),
        (RobotsOutcome.UNREACHABLE, False),
    ],
)
def test_permission_is_the_newest_answer_on_record(
    answer: RobotsOutcome, permitted: bool
) -> None:
    """A refusal and a robots file nobody could read both stop the request.

    They are different facts and stay different values - one is a publisher's
    stated policy and the other is our own failed read - but neither lets a
    request go out, so neither address belongs in a count of what we may ask.
    """
    history = [row(1, FetchOutcome.OK, status=200, items=4, robots=RobotsOutcome.ALLOWED)]
    history.append(row(2, FetchOutcome.ROBOTS_DENIED, robots=answer))
    assert source_health.endpoint_records(history)[KEY].permission is answer
    assert source_health.endpoint_records(history)[KEY].permitted is permitted


def test_an_address_nobody_recorded_permission_for_is_permitted() -> None:
    """Absent is unknown, never denied.

    Every row written before the column existed carries an empty cell, so
    reading those as refusals would take every desk under its floor on the day
    this landed.
    """
    record = source_health.endpoint_records([row(1, FetchOutcome.TRANSIENT, status=503)])[KEY]
    assert record.permission is None
    assert record.permitted


def test_a_rest_disturbs_no_permission() -> None:
    """A run that did not ask cannot have established anything."""
    history = [
        row(1, FetchOutcome.ROBOTS_DENIED, robots=RobotsOutcome.DENIED),
        row(2, FetchOutcome.SKIPPED),
    ]
    assert source_health.endpoint_records(history)[KEY].permission is RobotsOutcome.DENIED


def test_permission_returns_on_the_run_the_publisher_allows_us_again() -> None:
    """Reversible, which is what separates it from a retirement."""
    history = [
        row(1, FetchOutcome.ROBOTS_DENIED, robots=RobotsOutcome.DENIED),
        answered(2, robots=RobotsOutcome.ALLOWED),
    ]
    assert source_health.endpoint_records(history)[KEY].permitted


# --- filing the retirement ---------------------------------------------------


def records_after(*history: FeedHealthRow) -> dict[str, source_health.EndpointRecord]:
    return source_health.endpoint_records(list(history))


def test_the_run_that_reads_the_fifth_gone_files_one_row() -> None:
    filed = source_health.retirements(
        [TRADE, LAB],
        records=records_after(*[gone(n) for n in range(1, RETIRE_AFTER + 1)]),
        already=set(),
        after_runs=RETIRE_AFTER,
        date=DATE,
        run_id=f"{DATE}-6",
    )
    assert len(filed) == 1
    assert filed[0].feed_id == "trade-press"
    assert filed[0].endpoint_key == KEY
    assert filed[0].cause is RetirementCause.HTTP_410
    assert filed[0].decided_by_run == f"{DATE}-6"
    assert len(filed[0].evidence_run_ids) == RETIRE_AFTER


def test_an_address_already_on_the_ledger_is_not_filed_again() -> None:
    """A retirement is permanent for one address, so a second row says nothing new."""
    filed = source_health.retirements(
        [TRADE],
        records=records_after(*[gone(n) for n in range(1, RETIRE_AFTER + 1)]),
        already={KEY},
        after_runs=RETIRE_AFTER,
        date=DATE,
        run_id=f"{DATE}-6",
    )
    assert filed == []


def test_two_feeds_configured_at_one_address_file_one_row_between_them() -> None:
    """The ledger is keyed on the address, so two rows would be one fact twice."""
    twin = TRADE.model_copy(update={"id": "trade-press-mirror"})
    filed = source_health.retirements(
        [TRADE, twin],
        records=records_after(*[gone(n) for n in range(1, RETIRE_AFTER + 1)]),
        already=set(),
        after_runs=RETIRE_AFTER,
        date=DATE,
        run_id=f"{DATE}-6",
    )
    assert [record.feed_id for record in filed] == ["trade-press"]


def test_editing_the_configured_url_starts_a_clean_record() -> None:
    """A changed address is a new endpoint, with no inherited strikes and no retirement.

    That is the reversal path, and it is one line of curated config rather than
    a flag anybody has to remember to clear.
    """
    moved = TRADE.model_copy(update={"url": "https://trade.example-press.net/feed/v2"})
    records = records_after(*[gone(n) for n in range(1, RETIRE_AFTER + 1)])
    filed = source_health.retirements(
        [moved],
        records=records,
        already={KEY},
        after_runs=RETIRE_AFTER,
        date=DATE,
        run_id=f"{DATE}-6",
    )
    assert filed == []
    assert source_health.retired([moved], {KEY}) == frozenset()
    assert source_health.retired([TRADE], {KEY}) == {"trade-press"}


# --- the feed floor counts what we may ask -----------------------------------


def eligible_ids(feeds: list[FeedDef], **kwargs: object) -> list[str]:
    kept = source_health.eligible(feeds, "ai", **kwargs)  # type: ignore[arg-type]
    return [feed.id for feed in kept]


def test_a_desk_with_no_record_at_all_counts_every_active_feed() -> None:
    """A fresh clone has no history, and every configured address is askable."""
    assert eligible_ids([TRADE, LAB], retired_keys=set(), records={}) == [
        "trade-press",
        "lab-blog",
    ]


def test_a_curated_tombstone_is_not_counted() -> None:
    """A person's decision, enforced by the shape of the config rather than here."""
    dead = LAB.model_copy(
        update={"status": LifecycleStatus.RETIRED, "retired_on": "2026-08-01"}
    )
    assert eligible_ids([TRADE, dead], retired_keys=set(), records={}) == ["trade-press"]


def test_a_retired_endpoint_is_not_counted() -> None:
    assert eligible_ids([TRADE, LAB], retired_keys={KEY}, records={}) == ["lab-blog"]


@pytest.mark.parametrize("answer", [RobotsOutcome.DENIED, RobotsOutcome.UNREACHABLE])
def test_an_address_we_may_not_ask_is_not_counted(answer: RobotsOutcome) -> None:
    """The floor measures lawful source diversity, so it counts what we may ask.

    A source we are never going to request pads the number that exists to stop a
    thin desk reaching a reader, which is exactly how that number stops working.
    """
    records = records_after(row(1, FetchOutcome.ROBOTS_DENIED, robots=answer))
    assert eligible_ids([TRADE, LAB], retired_keys=set(), records=records) == ["lab-blog"]


def test_a_resting_or_failing_endpoint_is_still_counted() -> None:
    """The load-bearing half of the rule, and the one that keeps a bad day survivable.

    A rest lifts itself. Dropping a resting endpoint from the floor would let
    one afternoon of outages take a desk dark, and the desk's problem then is
    that today went badly rather than that it is under-sourced.
    """
    records = records_after(
        row(1, FetchOutcome.TRANSIENT, status=503),
        row(2, FetchOutcome.SKIPPED),
    )
    assert eligible_ids([TRADE, LAB], retired_keys=set(), records=records) == [
        "trade-press",
        "lab-blog",
    ]


def test_another_desks_feed_is_not_counted() -> None:
    energy = TRADE.model_copy(update={"id": "energy-wire", "vertical": "energy"})
    assert eligible_ids([energy, LAB], retired_keys=set(), records={}) == ["lab-blog"]


# --- two stale checkouts, one address ----------------------------------------


def retirement(feed_id: str = "trade-press", key: str = KEY) -> FeedRetirementRow:
    return FeedRetirementRow(
        version=FeedRetirementRow.schema_version(),
        feed_id=feed_id,
        endpoint_key=key,
        retired_on=DATE,
        decided_by_run=f"{DATE}-6",
        cause=RetirementCause.HTTP_410,
        evidence_run_ids=tuple(f"{DATE}-{n}" for n in range(1, RETIRE_AFTER + 1)),
    )


def test_two_stale_checkouts_filing_one_address_settle_to_one_row(tmp_path: Path) -> None:
    """`state/**/*.csv` is `merge=union`, so this never conflicts - it concatenates.

    Both jobs read a checkout frozen at the commit their run was triggered at,
    so neither can see the row the other pushed, and both file the same address.
    The settlement is `FEED_RETIREMENT_KEY` plus `drop_repeated_rows`, and the
    first row wins because there is nothing to choose between: a retirement is
    permanent, and a second row for one address says nothing the first did not.
    """
    path = ledger.feed_retirements_path(tmp_path)
    assert ledger.append_retirements(tmp_path, [retirement()]) == 1

    # The merge, spelled the way `merge=union` spells it: the other side's line
    # appended to ours, header and all already agreed.
    merged = path.read_text(encoding="utf-8")
    path.write_text(merged + merged.splitlines()[1] + "\n", encoding="utf-8")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3

    assert ledger.drop_repeated_rows(path, ledger.FEED_RETIREMENT_KEY) == 1

    rows = ledger.load_retirements(tmp_path)
    assert len(rows) == 1
    assert rows[0].endpoint_key == KEY


def test_appending_an_address_already_on_the_ledger_gains_nothing(tmp_path: Path) -> None:
    """The one-checkout half of the same guarantee."""
    assert ledger.append_retirements(tmp_path, [retirement()]) == 1
    assert ledger.append_retirements(tmp_path, [retirement()]) == 0
    assert len(ledger.load_retirements(tmp_path)) == 1


def test_a_retirement_row_that_no_longer_parses_is_skipped(tmp_path: Path) -> None:
    """The safe direction: an unreadable row costs one request to a dead address.

    The next run reads the same evidence and files it again. Refusing to start
    would cost the reader the day.
    """
    ledger.append_retirements(tmp_path, [retirement()])
    path = ledger.feed_retirements_path(tmp_path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(f"{FeedRetirementRow.schema_version()},trade,not-a-key,1999,x,http_410,r\n")
    assert len(ledger.load_retirements(tmp_path)) == 1


def test_reading_a_ledger_that_was_never_written_is_empty(tmp_path: Path) -> None:
    assert ledger.load_retirements(tmp_path) == []
