"""The source-health view: what it says, and what it cannot say.

Every test here drives the fold with rows it built itself, because the point of
the view is the arithmetic and the boundary rather than any particular day's
ledger. The one test that reads the committed record is the census identity,
which is the claim that would rot silently.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from idhazh import config, ledger, publish_source_health
from idhazh.contracts.app_config import CollectConfig
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import (
    FeedHealthRow,
    FetchOutcome,
    RobotsOutcome,
    derive_endpoint_key,
)
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.source_health_view import (
    FORBIDDEN_FIELDS,
    SourceAvailability,
    SourceHealthRow,
    SourceHealthView,
    SourcePermission,
)
from idhazh.contracts.sources import FeedDef, SourceForm
from idhazh.contracts.taxonomy import SourceKind, SourceTier

DATE = "2026-08-20"
COLLECT = CollectConfig()


def feed(feed_id: str, *, vertical: str = "ai") -> FeedDef:
    return FeedDef(
        id=feed_id,
        vertical=vertical,
        title=f"{feed_id} title",
        url=f"https://{feed_id}.example.com/feed.xml",
        tier=SourceTier.TRADE_PRESS,
        kind=SourceKind.REPORTING,
        form=SourceForm.ARTICLE,
    )


def health(
    feed_id: str,
    *,
    date: str,
    n: int,
    outcome: FetchOutcome,
    items: int = 0,
    status: int | None = 200,
    robots: RobotsOutcome | None = None,
) -> FeedHealthRow:
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=f"{date}-{n}",
        date=date,
        feed_id=feed_id,
        checked_at=f"{date}T{n:02d}:00:00Z",
        outcome=outcome,
        status=status,
        items=items,
        endpoint_key=derive_endpoint_key(f"https://{feed_id}.example.com/feed.xml"),
        robots_outcome=robots,
        robots_checked_at=None,
        robots_status=None,
        target_attempted=outcome is not FetchOutcome.SKIPPED,
    )


def item(
    feed_id: str,
    *,
    date: str,
    n: int,
    index: int,
    published: bool,
    code: FailureCode | None = None,
) -> ItemHealthRow:
    url = f"https://{feed_id}.example.com/{date}/{index}"
    failure = code or FailureCode.NO_TEXT
    # The stage has to be one the code belongs to - the contract checks the pair -
    # so a neutral code lands on the stage that owns it rather than on extract.
    stage = ItemStage.SUMMARIZE if failure is FailureCode.MODEL_UNREACHABLE else ItemStage.EXTRACT
    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=date,
        run_id=f"{date}-{n}",
        item_id=f"{feed_id}-{index:04d}",
        url_key=derive_url_key(url),
        canonical_url=url,
        vertical="ai",
        source_id=feed_id,
        stage=ItemStage.PUBLISH if published else stage,
        outcome=ItemOutcome.OK if published else ItemOutcome.FAILED,
        code=None if published else failure,
    )


def fold(
    *,
    feeds: Sequence[FeedDef],
    health_rows: Sequence[FeedHealthRow] = (),
    items: Sequence[ItemHealthRow] = (),
    retired_on: dict[str, str] | None = None,
    date: str = DATE,
) -> SourceHealthView:
    return publish_source_health.build(
        feeds=feeds,
        collect=COLLECT,
        health=health_rows,
        items=items,
        retired_on=retired_on or {},
        date=date,
        run_id=f"{date}-1",
        generated_at=f"{date}T06:20:00Z",
    )


def only(view: SourceHealthView) -> SourceHealthRow:
    assert len(view.sources) == 1
    return view.sources[0]


def test_a_view_carries_no_field_that_could_hold_an_address_or_a_diagnostic() -> None:
    """The boundary is the shape, not a filter the writer remembers to apply.

    A projection spelled as a dict of names gains a cell by a one-word edit and
    nothing refuses it. This asserts the refusal exists at all, and the import
    guard in the contract is what makes it fire where the field is written.
    """
    fields = set(SourceHealthRow.model_fields) | set(SourceHealthView.model_fields)
    assert FORBIDDEN_FIELDS & fields == set()
    assert "endpoint_key" not in fields, "the key identifies the address, so it may not cross"
    assert "detail" not in fields, "the ledger's detail is our own free text about a failed host"


def test_the_published_bytes_carry_no_address_key_or_robots_answer_body() -> None:
    """The same check one level down: what a page reads is the file, not the class."""
    view = fold(
        feeds=[feed("wire")],
        health_rows=[health("wire", date=DATE, n=1, outcome=FetchOutcome.OK, items=4)],
        items=[item("wire", date="2026-08-19", n=1, index=0, published=True)],
    )
    payload = json.dumps(json.loads(view.to_json()))
    for word in ("http://", "https://", "url_key", "endpoint_key", "robots"):
        assert word not in payload, f"the published view carries {word!r}"


def test_permission_is_the_newest_answer_on_record() -> None:
    """And an absent cell is unrecorded rather than allowed.

    Reading absence as permission claims a check nobody ran; reading it as a
    refusal would take every desk under its feed floor on the day the column
    landed. Neither is what the record says.
    """
    rows = [
        health("wire", date="2026-08-19", n=1, outcome=FetchOutcome.OK, items=3),
        health(
            "wire",
            date=DATE,
            n=1,
            outcome=FetchOutcome.ROBOTS_DENIED,
            robots=RobotsOutcome.DENIED,
        ),
    ]
    assert only(fold(feeds=[feed("wire")], health_rows=rows)).permission is SourcePermission.DENIED
    assert (
        only(fold(feeds=[feed("wire")], health_rows=rows[:1])).permission
        is SourcePermission.UNRECORDED
    )
    unreachable = [
        health(
            "wire",
            date=DATE,
            n=1,
            outcome=FetchOutcome.ROBOTS_DENIED,
            robots=RobotsOutcome.UNREACHABLE,
        )
    ]
    assert (
        only(fold(feeds=[feed("wire")], health_rows=unreachable)).permission
        is SourcePermission.UNREACHABLE
    )


def test_permission_states_sum_to_the_number_of_addresses() -> None:
    """Every configured address is in exactly one permission state, always.

    That is what makes the console's tally a census rather than a sample, and it
    holds by construction: one row per feed, one permission on each.
    """
    feeds = [feed("allowed-wire"), feed("refused-wire"), feed("silent-wire")]
    view = fold(
        feeds=feeds,
        health_rows=[
            health(
                "allowed-wire",
                date=DATE,
                n=1,
                outcome=FetchOutcome.OK,
                items=2,
                robots=RobotsOutcome.ALLOWED,
            ),
            health(
                "refused-wire",
                date=DATE,
                n=1,
                outcome=FetchOutcome.ROBOTS_DENIED,
                robots=RobotsOutcome.DENIED,
            ),
        ],
    )
    counted = [row.permission for row in view.sources]
    assert len(counted) == len(feeds)
    assert sorted(state.value for state in counted) == ["allowed", "denied", "unrecorded"]


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        ([(FetchOutcome.OK, 4)], SourceAvailability.ANSWERING),
        ([(FetchOutcome.OK, 4), (FetchOutcome.TRANSIENT, 0)], SourceAvailability.FAILING),
        ([(FetchOutcome.OK, 0)], SourceAvailability.FAILING),
        ([(FetchOutcome.SKIPPED, 0)], SourceAvailability.NEVER_ASKED),
        ([(FetchOutcome.ROBOTS_DENIED, 0)], SourceAvailability.NEVER_ASKED),
    ],
)
def test_availability_reports_the_run_s_own_rule(
    outcomes: list[tuple[FetchOutcome, int]], expected: SourceAvailability
) -> None:
    """A refusal is not a read, so a refused address has never been asked.

    That is the defect this row exists to fix: until 2026-09-03 a source whose
    every result was a polite refusal was reported as one that had never failed.
    """
    rows = [
        health("wire", date=DATE, n=index + 1, outcome=outcome, items=items)
        for index, (outcome, items) in enumerate(outcomes)
    ]
    assert only(fold(feeds=[feed("wire")], health_rows=rows)).availability is expected


def test_a_feed_past_the_strike_count_is_resting_rather_than_failing() -> None:
    """The rest is the decision an operator can act on; failing is the symptom."""
    rows = [
        health("wire", date=DATE, n=n, outcome=FetchOutcome.TRANSIENT, status=503)
        for n in range(1, COLLECT.availability_strikes_before_rest + 1)
    ]
    assert only(fold(feeds=[feed("wire")], health_rows=rows)).availability is (
        SourceAvailability.RESTING
    )


def test_retirement_is_rendered_and_never_re_derived() -> None:
    """The row carries the backend's decision and the day it was filed.

    Keyed on the address rather than the feed, so a retirement follows the URL:
    editing that URL is a different key with a clean record, which is the whole
    reversal path.
    """
    key = derive_endpoint_key("https://wire.example.com/feed.xml")
    view = fold(feeds=[feed("wire")], retired_on={key: "2026-08-11"})
    row = only(view)
    assert row.retired is True
    assert row.retired_on == "2026-08-11"
    assert row.title, "a retired row that resolves to no title names nothing an operator can act on"
    assert only(fold(feeds=[feed("wire")])).retired is False


def test_a_retirement_day_and_the_retirement_are_one_fact() -> None:
    """Neither can be read alone, so the shape refuses one without the other."""
    with pytest.raises(ValidationError, match="retired_on is present exactly when"):
        SourceHealthRow(
            source_id="wire",
            title="Wire",
            vertical="ai",
            permission=SourcePermission.ALLOWED,
            availability=SourceAvailability.ANSWERING,
            retired=True,
            retired_on=None,
            opportunities=0,
            publications=0,
            source_failures=0,
        )


def test_the_census_counts_one_address_on_one_date_once() -> None:
    """Five runs of a day may not inflate either side of the ratio.

    A retried address writes a row every run it is attempted, so counting rows
    would multiply both the offer and the publication by however often the
    schedule fired that day.
    """
    yesterday = "2026-08-19"
    rows = [
        item("wire", date=yesterday, n=1, index=0, published=False),
        item("wire", date=yesterday, n=2, index=0, published=False),
        # The third run of the same day got it through.
        item("wire", date=yesterday, n=3, index=0, published=True),
        item("wire", date=yesterday, n=1, index=1, published=True),
    ]
    row = only(fold(feeds=[feed("wire")], items=rows))
    assert row.opportunities == 2, "two addresses were planned, over four rows"
    assert row.publications == 2
    assert row.source_failures == 0, "an address that published is not also a loss"


def test_a_source_owned_loss_is_reported_beside_the_ratio_and_not_inside_it() -> None:
    """One lost article is counted once, and a neutral failure is not the source's."""
    yesterday = "2026-08-19"
    rows = [
        item("wire", date=yesterday, n=1, index=0, published=True),
        item("wire", date=yesterday, n=1, index=1, published=False, code=FailureCode.NO_TEXT),
        # Our own model was unreachable, which says nothing about the source.
        item(
            "wire",
            date=yesterday,
            n=1,
            index=2,
            published=False,
            code=FailureCode.MODEL_UNREACHABLE,
        ),
    ]
    row = only(fold(feeds=[feed("wire")], items=rows))
    assert (row.opportunities, row.publications, row.source_failures) == (3, 1, 1)


def test_today_is_never_a_complete_date() -> None:
    """A run is still working, so its addresses have not all been attempted.

    Counting today would report every source as having failed work it has not
    reached, which is the standard way a partial day reads as an outage.
    """
    rows = [
        item("wire", date=DATE, n=1, index=0, published=False),
        item("wire", date="2026-08-19", n=1, index=0, published=True),
    ]
    view = fold(feeds=[feed("wire")], items=rows)
    assert view.complete_dates == 1
    assert (view.first_date, view.last_date) == ("2026-08-19", "2026-08-19")
    assert only(view).opportunities == 1


def test_the_record_says_it_is_too_short_rather_than_printing_a_rate() -> None:
    """Below the configured history the view refuses to call itself readable.

    A ratio over four days presented as a yield is an estimate wearing a
    measurement's clothes (Rule #10).
    """
    rows = [
        item("wire", date=f"2026-08-{day:02d}", n=1, index=0, published=True)
        for day in range(10, 14)
    ]
    short = fold(feeds=[feed("wire")], items=rows)
    assert short.complete_dates == 4
    assert short.min_complete_days == COLLECT.source_yield_min_complete_days
    assert short.yield_readable is False

    enough = [
        item("wire", date=day, n=1, index=0, published=True)
        for day in sorted(
            {
                f"2026-{month:02d}-{day:02d}"
                for month, days in ((7, range(20, 32)), (8, range(1, 20)))
                for day in days
            }
        )
    ]
    long_enough = fold(feeds=[feed("wire")], items=enough)
    assert long_enough.complete_dates == COLLECT.source_yield_min_complete_days
    assert long_enough.yield_readable is True


def test_the_census_reads_at_most_the_configured_number_of_complete_days() -> None:
    """The window is the same knob the readability bar is, because it is one question."""
    days = [f"2026-07-{day:02d}" for day in range(1, 32)] + ["2026-08-01"]
    rows = [item("wire", date=day, n=1, index=0, published=True) for day in days]
    view = fold(feeds=[feed("wire")], items=rows, date=DATE)
    assert view.complete_dates == COLLECT.source_yield_min_complete_days
    assert view.last_date == "2026-08-01"
    assert only(view).opportunities == COLLECT.source_yield_min_complete_days


def test_no_yield_numerator_can_exceed_its_opportunity_count() -> None:
    """A ratio over a denominator it can beat is a page printing 110 percent."""
    with pytest.raises(ValidationError, match="publications cannot exceed opportunities"):
        SourceHealthRow(
            source_id="wire",
            title="Wire",
            vertical="ai",
            permission=SourcePermission.ALLOWED,
            availability=SourceAvailability.ANSWERING,
            retired=False,
            retired_on=None,
            opportunities=2,
            publications=3,
            source_failures=0,
        )


def test_a_view_names_each_source_once_and_in_order() -> None:
    """A repeated source would double one permission state and break the tally."""
    view = fold(feeds=[feed("zulu"), feed("alpha")])
    assert [row.source_id for row in view.sources] == ["alpha", "zulu"]
    with pytest.raises(ValidationError, match="must name each source once"):
        SourceHealthView(
            version=SourceHealthView.schema_version(),
            generated_at=f"{DATE}T06:20:00Z",
            run_id=f"{DATE}-1",
            min_complete_days=30,
            complete_dates=0,
            yield_readable=False,
            first_date=None,
            last_date=None,
            sources=[only(fold(feeds=[feed("wire")])), only(fold(feeds=[feed("wire")]))],
        )


def test_the_view_round_trips_through_its_own_serialization() -> None:
    """A payload a run wrote and a later build cannot read is a release blocker."""
    view = fold(
        feeds=[feed("wire")],
        health_rows=[health("wire", date=DATE, n=1, outcome=FetchOutcome.OK, items=2)],
        items=[item("wire", date="2026-08-19", n=1, index=0, published=True)],
    )
    text = view.to_json()
    assert SourceHealthView.from_json(text).to_json() == text


def test_publish_writes_the_view_where_the_console_reads_it(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """And it reads the committed ledgers rather than anything held in memory."""
    state = tmp_path / "state"
    ledger.append_health(
        state,
        DATE,
        [health("wire", date=DATE, n=1, outcome=FetchOutcome.OK, items=3)],
    )
    settings = config.load()
    path = tmp_path / "public" / publish_source_health.PUBLIC_FILENAME
    returned = publish_source_health.publish(
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        collect=settings.app.collect,
        date=DATE,
        run_id=f"{DATE}-1",
        generated_at=f"{DATE}T06:20:00Z",
        state_root=state,
        path=path,
    )
    assert path.name == "source-health.json"
    assert publish_source_health.public_relpath() == "frontend/public/source-health.json"
    view = SourceHealthView.from_json(path.read_text(encoding="utf-8"))
    assert view.to_json() == returned.to_json()
    assert len(view.sources) == len(
        publish_source_health.active_feeds(
            settings.sources, [vertical.id for vertical in settings.taxonomy.verticals]
        )
    )


def test_the_active_census_is_exactly_the_addresses_a_run_would_ask() -> None:
    """A feed a curator retired is not an address we may ask, so it is not counted.

    Read against the committed config, because the claim that would rot is the
    one about this repository rather than about a fixture.
    """
    settings = config.load()
    counted = publish_source_health.active_feeds(
        settings.sources, [vertical.id for vertical in settings.taxonomy.verticals]
    )
    names = {feed.id for feed in counted}
    assert names, "the committed source list is empty"
    assert names & {feed.id for feed in settings.sources.retired} == set()
    assert len(names) == len(counted), "one address counted twice inflates a permission state"


def _yielding(
    feed_id: str, *, published: int, lost: int, outcome: FetchOutcome = FetchOutcome.OK
) -> tuple[FeedDef, list[FeedHealthRow], list[ItemHealthRow]]:
    """A source whose fate over one prior day is exactly `published` and `lost`.

    Built rather than read, because the alarm has to be right on day 400 and the
    committed record holds thirteen days (CLAUDE.md section 13, owner ruling
    2026-09-06). A built source can also carry a shape the archive has never
    produced - nought published out of seventy-three, say.
    """
    day = "2026-08-19"
    rows = [item(feed_id, date=day, n=1, index=i, published=True) for i in range(published)] + [
        item(
            feed_id, date=day, n=1, index=published + i, published=False, code=FailureCode.PAYWALLED
        )
        for i in range(lost)
    ]
    return (
        feed(feed_id),
        [
            health(
                feed_id,
                date=DATE,
                n=1,
                outcome=outcome,
                items=published + lost,
                robots=RobotsOutcome.ALLOWED,
            )
        ],
        rows,
    )


def test_a_source_that_answers_but_does_not_read_is_named() -> None:
    """The scmp-news shape, and the one this whole knob exists for.

    Permission allowed, availability answering, HTTP 200 every run - and four
    stories out of a hundred and eleven decisions. Every other signal reported
    it healthy for a fortnight.
    """
    wall, wall_health, wall_items = _yielding("wall", published=4, lost=107)
    view = fold(feeds=[wall], health_rows=wall_health, items=wall_items)

    row = only(view)
    assert row.availability is SourceAvailability.ANSWERING
    assert row.permission is SourcePermission.ALLOWED
    assert row.decisions == 111
    assert row.source_yield == pytest.approx(4 / 111)

    alarm = publish_source_health.yield_alarm(view, alarm_point=0.5, min_decisions=30)
    assert alarm is not None
    assert "wall 4/111 (4%)" in alarm
    assert "probe_feeds.py" in alarm, "an alarm that names no next step is a nag"


def test_a_thin_record_is_never_named_however_bad_it_looks() -> None:
    """One of seven is 14 percent and it is not evidence about a source.

    Measured 2026-09-06 over the committed view: without this floor the alarm's
    first run names cnn-world, which the source docs already ruled is a working
    feed carrying real reporting. A flag that is wrong on its first run is the
    flag nobody reads.
    """
    thin, thin_health, thin_items = _yielding("thin", published=1, lost=6)
    view = fold(feeds=[thin], health_rows=thin_health, items=thin_items)

    assert only(view).source_yield == pytest.approx(1 / 7)
    assert publish_source_health.yield_alarm(view, alarm_point=0.5, min_decisions=30) is None


def test_a_source_is_not_charged_for_a_failure_it_does_not_own() -> None:
    """A model that would not answer is our outage, not the publisher's.

    Measured 2026-09-06 over the committed view: aljazeera-economy is 78 of 115
    offered and 78 of 79 decided. Dividing by opportunities calls a 99 percent
    source a 68 percent one, which is a false positive built into the ratio.
    """
    day = "2026-08-19"
    rows = [item("ours", date=day, n=1, index=0, published=True)] + [
        item("ours", date=day, n=1, index=i, published=False, code=FailureCode.MODEL_UNREACHABLE)
        for i in range(1, 60)
    ]
    view = fold(
        feeds=[feed("ours")],
        health_rows=[
            health(
                "ours",
                date=DATE,
                n=1,
                outcome=FetchOutcome.OK,
                items=60,
                robots=RobotsOutcome.ALLOWED,
            )
        ],
        items=rows,
    )

    row = only(view)
    assert row.opportunities == 60
    assert row.source_failures == 0
    assert row.decisions == 1, "only the address the source itself decided"
    assert row.source_yield == 1.0
    assert publish_source_health.yield_alarm(view, alarm_point=0.5, min_decisions=1) is None


def test_a_source_nobody_asked_has_no_yield_rather_than_a_zero() -> None:
    """0 of 0 is not nought percent, and printing it is an accusation."""
    view = fold(
        feeds=[feed("quiet")],
        health_rows=[
            health(
                "quiet",
                date=DATE,
                n=1,
                outcome=FetchOutcome.OK,
                items=0,
                robots=RobotsOutcome.ALLOWED,
            )
        ],
    )
    row = only(view)
    assert row.decisions == 0
    assert row.source_yield is None
    assert publish_source_health.yield_alarm(view, alarm_point=0.5, min_decisions=0) is None


def test_a_rested_or_retired_source_is_left_out_of_the_alarm() -> None:
    """Naming a source the run already stopped asking reports the symptom.

    The alarm exists for the source nothing gives up on. A rest is a decision an
    operator can already see, and a retirement is one they already took.
    """
    resting, resting_health, resting_items = _yielding(
        "gone", published=0, lost=40, outcome=FetchOutcome.PERMANENT
    )
    strikes = [
        health(
            "gone",
            date=DATE,
            n=n,
            outcome=FetchOutcome.PERMANENT,
            items=0,
            robots=RobotsOutcome.ALLOWED,
        )
        for n in range(1, COLLECT.availability_strikes_before_rest + 1)
    ]
    rested = fold(feeds=[resting], health_rows=strikes, items=resting_items)
    assert only(rested).permission is SourcePermission.ALLOWED, (
        "the rest has to be the only reason this one is left out"
    )
    assert only(rested).availability is SourceAvailability.RESTING
    assert publish_source_health.yield_alarm(rested, alarm_point=0.5, min_decisions=1) is None

    retired = fold(
        feeds=[resting],
        health_rows=resting_health,
        items=resting_items,
        retired_on={derive_endpoint_key(resting.url): DATE},
    )
    assert only(retired).retired
    assert publish_source_health.yield_alarm(retired, alarm_point=0.5, min_decisions=1) is None


def test_a_healthy_source_raises_nothing_and_the_worst_is_named_first() -> None:
    """Silence when nothing is wrong, and an order a person can act down."""
    good, good_health, good_items = _yielding("good", published=95, lost=5)
    assert (
        publish_source_health.yield_alarm(
            fold(feeds=[good], health_rows=good_health, items=good_items),
            alarm_point=0.5,
            min_decisions=30,
        )
        is None
    )

    bad, bad_health, bad_items = _yielding("bad", published=0, lost=73)
    worse, worse_health, worse_items = _yielding("mid", published=26, lost=72)
    alarm = publish_source_health.yield_alarm(
        fold(
            feeds=[good, bad, worse],
            health_rows=[*good_health, *bad_health, *worse_health],
            items=[*good_items, *bad_items, *worse_items],
        ),
        alarm_point=0.5,
        min_decisions=30,
    )
    assert alarm is not None
    assert "good" not in alarm
    assert alarm.index("bad 0/73") < alarm.index("mid 26/98")
