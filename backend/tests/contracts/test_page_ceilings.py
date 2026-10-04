"""What bounds a route that grows every time a run publishes?"""

from __future__ import annotations

import gzip
from datetime import date, timedelta
from typing import Final

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh import config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.knobs.gardener import CompactionPolicy, DaysWindow, MonthsWindow
from idhazh.contracts.knobs.page_weight import PageWeightConfig
from idhazh.contracts.knobs.windows import months_a_window_can_touch
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName

pytestmark = pytest.mark.contract

#: Where the published ledgers sit in the build, as a payload key names them.
LEDGERS: Final = "state/"
LEDGER_REGISTRY: Final = "config/ledgers.json"

#: The most days one calendar month holds. A month is absorbed whole, so a day
#: index holds between `daily_keep_days` and this many entries more.
LONGEST_MONTH_DAYS: Final = 31

#: The committed scores day index grown to 62 entries from its own row counts and
#: sizes, at gzip -5, measured 2026-09-30 through Python 3.14's zlib-ng on Windows.
#: The index the ceilings are checked against must weigh at least this, or they
#: would be checked against one lighter than a real index.
REAL_DAY_INDEX_AT_62_ENTRIES: Final = 662


def index_key(ledger: LedgerName) -> str:
    """The payload key that bounds one published ledger's two indexes."""
    return f"{LEDGERS}compact/{ledger.value}/index/"


def an_index(ledger: LedgerName, period: Period, entries: int) -> bytes:
    """An index of `entries` entries, written the way the compaction writes one.

    The row counts and sizes differ from entry to entry, four and six digits wide,
    because repeated values gzip to almost nothing and would make a ceiling look
    safer than it is.
    """
    first = date(2026, 1, 1)
    covers = [
        (first + timedelta(days=step)).isoformat()
        if period is Period.DAILY
        else f"{first.year + step // 12}-{step % 12 + 1:02d}"
        for step in range(entries)
    ]
    return (
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=ledger,
            period=period,
            entries=[
                CompactEntry(
                    covers=cover,
                    rows=1_000 + step * 7_919 % 9_000,
                    bytes=100_000 + step * 104_729 % 900_000,
                )
                for step, cover in enumerate(covers)
            ],
        )
        .to_json()
        .encode("ascii")
    )


def gzipped(data: bytes) -> int:
    """The size the bundle gate weighs a file at: gzip level 5."""
    return len(gzip.compress(data, compresslevel=5, mtime=0))


def months_kept(policy: CompactionPolicy) -> int:
    """The most month files a monthly window keeps at once."""
    window = policy.monthly_window
    if isinstance(window, MonthsWindow):
        return window.value
    if isinstance(window, DaysWindow):
        return months_a_window_can_touch(window.value)
    if policy.monthly_keep_days is not None:
        return 12 + months_a_window_can_touch(policy.monthly_keep_days)
    raise AssertionError("a published ledger needs a finite month window or yearly packing")


@pytest.mark.parametrize("keep_days", [93, 180, 367])
def test_yearly_packing_bounds_month_files_while_every_row_is_kept(keep_days: int) -> None:
    declared = CompactionPolicy.model_validate_json(
        read_text(CONFIG_DIR / "gardener" / "compact-summary-quality-evals.json")
    )
    policy = CompactionPolicy.model_validate(
        declared.model_dump() | {"monthly_keep_days": keep_days}
    )
    assert months_kept(policy) == 12 + months_a_window_can_touch(keep_days)


def test_no_page_number_names_a_route_that_grows_when_a_run_publishes() -> None:
    """This test was the opposite of itself until 2026-09-10, and the inversion is
    the point.

    It used to insist `/archive/` and the three `/console/` routes each carried a
    byte number, on the argument that an unnamed route grows unwatched. What
    actually happened is that those four numbers moved when the pipeline
    published rather than when anybody wrote code, so the gate fired on ordinary
    publishing and the recorded answer was always a bigger number - `/archive/`
    twice in one day on 2026-08-26. Meanwhile `/console/` drifted to 7.2 times
    the page it bounded and stood there four days with the build green. A number
    that cannot tell correct from far-too-loose is not an instrument.

    **The property those numbers were a proxy for is asserted directly**, by
    `frontend/tests/payload-weight.spec.ts`: no document that does not render a
    day may contain a day payload marker. That is the one regression this surface
    has ever had - a layout inlining a day, 313,300 gzipped bytes on 2026-08-26 -
    and the marker check returns the same verdict whatever the archive holds.

    So the assertion is now on absence. `/404` stays, because it
    passes the test in the name: it moves only when a person edits source, never
    when a run appends a day. Owner ruling, 2026-09-10.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    ceilings = committed.page_weight.ceilings_bytes

    assert PageWeightConfig().ceilings_bytes == {}, "the model default must stay empty"
    assert ceilings["/404"] > 0
    for route in ("/archive/", "/console/", "/console/model/", "/console/machine/"):
        assert route not in ceilings, (
            f"{route} has a byte number again. Its weight moves when the pipeline "
            "publishes, so the number has to move too, and the only way past it is to "
            "type a bigger one - which is what got these four deleted. The regression "
            "worth catching here is a day payload inlined by a layout, and "
            "frontend/tests/payload-weight.spec.ts asserts that directly."
        )


def test_the_committed_config_caps_what_a_cold_console_load_fetches() -> None:
    """The page ceilings above cannot see these bytes, and that is why they exist.

    The console stopped inlining its telemetry on 2026-09-09. That took 3.4 MB out
    of a document a ceiling watched and put it into files nothing watched, and a
    reader still waits for them - measured 2026-09-10 in a real browser, a cold
    `/console/` load fetches two telemetry shards worth 303,306 bytes on the wire
    and no other payload at all. A document ceiling now reads as a bound on what
    the console costs a reader, and it is not one.

    `cold_console_load_bytes` bounds the design rather than the data: the per-file
    ceilings say how heavy one shard may be, this says how many of them one
    opening of the page is allowed to want. The two are asserted against each
    other here, because a total below the sum of its parts is a gate that cannot
    be satisfied at the limit and a total far above it is a gate that never fires.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    weight = committed.page_weight
    payloads = weight.payload_ceilings_bytes

    assert PageWeightConfig().payload_ceilings_bytes == {}, "the model default must stay empty"
    assert PageWeightConfig().cold_console_load_bytes == 0, "the model default must stay empty"

    for path in ("console/band.json", "telemetry/"):
        assert path in payloads, (
            f"{path} is fetched by a reader's browser and has no ceiling - the bundle "
            "gate cannot fail a file nobody named, so this one would grow unwatched"
        )

    assert LEDGER_REGISTRY in payloads, (
        "the data explorer fetches config/ledgers.json, so it needs its own payload "
        "ceiling even though a cold opening of /console/ does not fetch it"
    )
    assert payloads[LEDGER_REGISTRY] >= 2 * gzipped((CONFIG_DIR / "ledgers.json").read_bytes())

    # The worst case a run of N consecutive days can land in, because February is
    # the shortest month there is. Mirrors the arithmetic in bundle-gate.mjs: a key
    # naming a file counts once, a key naming a directory of month shards once a
    # month the window touches, and a key under `state/` not at all, because no
    # cold opening of `/console/` fetches a published ledger.
    window = committed.console.default_window_days
    months_touched = 1 + -(-(window - 1) // 28)
    worst = sum(
        ceiling * (months_touched if path.endswith("/") else 1)
        for path, ceiling in payloads.items()
        if not path.startswith(LEDGERS) and path != LEDGER_REGISTRY
    )
    assert weight.cold_console_load_bytes >= worst, (
        "a cold load of every payload sitting exactly on its own ceiling is already "
        f"over cold_console_load_bytes ({worst} against "
        f"{weight.cold_console_load_bytes}) - the two gates contradict each other"
    )
    assert weight.cold_console_load_bytes < worst + payloads["telemetry/"], (
        "cold_console_load_bytes has room for one more telemetry shard than the "
        "default window reaches, so widening console.default_window_days past a "
        "month would not fire it - which is the one thing it exists to catch"
    )


def test_every_published_ledger_bounds_its_indexes_at_twice_their_longest() -> None:
    """A browser reads a published ledger's indexes first, and config sets their length.

    A day index holds at most `daily_keep_days` plus 31 entries, because a month
    is absorbed whole, and a month index at most the months `monthly_window`
    keeps. So each published ledger's index key has to be at least twice the
    heavier of the two at that length. Raising `daily_keep_days` without raising
    the key fails here, in the commit that raised it, rather than in the gate on
    some later pull request.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    payloads = committed.page_weight.payload_ceilings_bytes
    tasks = config.load_gardener(CONFIG_DIR).tasks

    bounded = sorted(path for path in payloads if path.startswith(LEDGERS))
    assert bounded == sorted(index_key(ledger) for ledger in committed.ledger.published), (
        "every published ledger has one payload key for its index directory, and no "
        "other ledger has one: a ledger without a key ships indexes no gate weighs, and "
        "a key for a ledger that is not published names nothing in the build"
    )
    for ledger in committed.ledger.published:
        policy = tasks.get(f"compact-{ledger.value}")
        assert isinstance(policy, CompactionPolicy), (
            f"{ledger.value} is published and no compaction task writes its indexes"
        )
        days = policy.daily_keep_days + LONGEST_MONTH_DAYS
        months = months_kept(policy)
        heaviest = max(
            gzipped(an_index(ledger, Period.DAILY, days)),
            gzipped(an_index(ledger, Period.MONTHLY, months)),
        )
        assert payloads[index_key(ledger)] >= 2 * heaviest, (
            f"{index_key(ledger)} is capped at {payloads[index_key(ledger)]} bytes, and "
            f"its day index can hold {days} entries, {heaviest} bytes at gzip -5. The "
            "cap is at least twice that, so raise it with the knob that grew the index"
        )


def test_the_index_the_ceilings_are_checked_against_weighs_what_a_real_one_does() -> None:
    """A made-up index that gzips better than a real one would pass a cap that is too low."""
    assert (
        gzipped(an_index(LedgerName.SUMMARY_QUALITY_EVALS, Period.DAILY, 62))
        >= REAL_DAY_INDEX_AT_62_ENTRIES
    )


def test_a_page_ceiling_bounds_a_route_and_bounds_it_above_zero() -> None:
    """A ceiling of zero passes nothing and a key that is not a route bounds nothing."""
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(ceilings_bytes={"/404": 0})
    with pytest.raises(ValueError, match="is not a route"):
        PageWeightConfig(ceilings_bytes={"404": 2475})


def test_a_payload_ceiling_bounds_a_path_in_the_build() -> None:
    """The leading slash is what tells the two objects apart.

    A route ceiling has one and a payload ceiling does not, so a number typed
    into the wrong object is refused by shape here rather than discovered later
    as a gate quietly checking nothing.
    """
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(payload_ceilings_bytes={"telemetry/": 0})
    with pytest.raises(ValueError, match="is a route, not a path"):
        PageWeightConfig(payload_ceilings_bytes={"/telemetry/": 500_000})
    with pytest.raises(ValueError, match="not a relative POSIX path"):
        PageWeightConfig(payload_ceilings_bytes={"telemetry\\2026-09.csv": 500_000})
    with pytest.raises(ValueError, match="not a relative POSIX path"):
        PageWeightConfig(payload_ceilings_bytes={"../telemetry/": 500_000})
