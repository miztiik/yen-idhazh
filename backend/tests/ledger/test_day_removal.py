"""Does the door name every file that holds a range of days, and build each one again without them?

`ledger/day_removal.py` answers the two questions a prune on the ledger door
asks before it changes anything: which files hold a row of the days, and what
each compact one holds without them. Neither writes a file, so the tree is built
once for the module and shared by every test that only reads it; a test that
breaks a file first works on a copy of its own.

The tree is the census `ledger/_every_tier.py` files through the door and the
shipped compaction, so its days sit in a year file, a month file, daily files
and raw files, each as a wake would have left it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

import pyarrow.parquet
import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period, Tier, WriterIdentity
from idhazh.contracts.item_health import ItemHealthRow

from ._every_tier import CENSUS, QUIET_DAY, RAW_DAYS, YEAR_DAYS, a_census_in_every_tier

pytestmark = pytest.mark.contract

#: Who a rebuilt file says rebuilt it: a prune, filing rows again.
WRITER: Final = WriterIdentity(
    run_id="2026-03-21-1",
    attempt=1,
    job=ServerJob.MIGRATE,
    shard=0,
    producer="telemetry.prune",
    git_sha="c" * 40,
)


@pytest.fixture(scope="module")
def every_tier(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The census in every kind of file, built once, and its state root."""
    return a_census_in_every_tier(tmp_path_factory.mktemp("every-tier"))


def a_copy(state: Path, under: Path) -> Path:
    """The built tree copied to a folder of its own, and the copy's state root."""
    shutil.copytree(state.parent, under)
    return under / ledger.STATE_DIRNAME


def put_aside(data: bytes, under: Path, name: str) -> Path:
    """A built file's bytes in a scratch file, so it is read back the way any file is."""
    under.mkdir(parents=True, exist_ok=True)
    scratch = under / name
    scratch.write_bytes(data)
    return scratch


def test_every_kind_of_file_that_holds_a_day_of_the_range_is_named(every_tier: Path) -> None:
    """A raw day, a daily file, a month file and a year file, each with the days it covers.

    Raw files first, then daily, monthly and yearly. A day whose daily file
    counts no row, and a day no file covers, are named by nothing.
    """
    days = ["2025-12-20", "2026-01-22", "2026-02-10", QUIET_DAY, RAW_DAYS[0], "2027-01-01"]

    held = ledger.find_holding_files(every_tier, CENSUS, days)

    assert [(found.tier, found.period, found.covers, found.days) for found in held] == [
        (Tier.RAW, None, RAW_DAYS[0], (RAW_DAYS[0],)),
        (Tier.COMPACT, Period.DAILY, "2026-02-10", ("2026-02-10",)),
        (Tier.COMPACT, Period.MONTHLY, "2026-01", ("2026-01-22",)),
        (Tier.COMPACT, Period.YEARLY, "2025", ("2025-12-20",)),
    ]
    assert all(found.path.is_file() for found in held)


def test_a_month_file_built_without_a_day_keeps_every_other_row_and_writes_nothing(
    every_tier: Path, tmp_path: Path
) -> None:
    """The day's rows go, every other row comes back as it was stored, and the file is untouched."""
    (month,) = ledger.find_holding_files(every_tier, CENSUS, ["2026-01-22"])
    before = month.path.read_bytes()
    stored = ledger.load_stored([month.path], model=ItemHealthRow)
    kept = [held for held in stored if held.identity.covers != "2026-01-22"]
    assert kept and len(kept) < len(stored), "the month file does not hold both of its days"

    built = ledger.rebuild_without(every_tier, month, ["2026-01-22"], identity=WRITER)

    assert (built.path, built.rows) == (month.path, len(kept))
    scratch = put_aside(built.data, tmp_path, month.path.name)
    assert ledger.load_stored([scratch], model=ItemHealthRow) == kept
    assert month.path.read_bytes() == before, "building a file wrote it"


def test_a_daily_file_whose_every_row_goes_is_built_empty_and_reads_back(
    every_tier: Path, tmp_path: Path
) -> None:
    """An emptied period is still a file, whose envelope names the prune that rebuilt it."""
    (day,) = ledger.find_holding_files(every_tier, CENSUS, ["2026-02-10"])

    built = ledger.rebuild_without(every_tier, day, ["2026-02-10"], identity=WRITER)

    scratch = put_aside(built.data, tmp_path, day.path.name)
    envelope = ledger.read_envelope(scratch)
    assert built.rows == 0
    assert ledger.load_stored([scratch], model=ItemHealthRow) == []
    assert (envelope.tier, envelope.period, envelope.covers) == (
        Tier.COMPACT,
        Period.DAILY,
        "2026-02-10",
    )
    assert (envelope.identity, envelope.built_from) == (WRITER, 1)


@pytest.mark.parametrize(
    ("gone", "groups"),
    [(("2025-12-20",), 2), (("2025-11-14",), 1), (YEAR_DAYS, 0)],
    ids=["a-day-of-december", "all-of-november", "every-row"],
)
def test_a_year_file_is_built_one_row_group_for_each_month_that_keeps_a_row(
    every_tier: Path, tmp_path: Path, gone: tuple[str, ...], groups: int
) -> None:
    """A month that keeps a row keeps its own row group, and a month that keeps none has none.

    A reader filtering on a date skips a row group by its statistics, so a year
    rebuilt as one group would be read whole to answer a question about one day.
    """
    (year,) = ledger.find_holding_files(every_tier, CENSUS, list(gone))

    built = ledger.rebuild_without(every_tier, year, gone, identity=WRITER)

    scratch = put_aside(built.data, tmp_path, year.path.name)
    assert pyarrow.parquet.read_metadata(scratch).num_row_groups == groups
    assert {
        held.identity.covers for held in ledger.load_stored([scratch], model=ItemHealthRow)
    } == set(YEAR_DAYS) - set(gone)


def test_a_raw_file_is_refused_because_a_day_taken_out_takes_it_whole(every_tier: Path) -> None:
    """A raw file holds one writer's rows of one day, so it is deleted, never rebuilt."""
    (raw,) = ledger.find_holding_files(every_tier, CENSUS, [RAW_DAYS[0]])

    with pytest.raises(ValueError, match="is a raw file"):
        ledger.rebuild_without(every_tier, raw, [RAW_DAYS[0]], identity=WRITER)


def test_a_file_asked_for_as_another_period_is_refused(every_tier: Path) -> None:
    """The envelope says what a file covers, and a rebuild trusts it over the caller."""
    (month,) = ledger.find_holding_files(every_tier, CENSUS, ["2026-01-22"])
    wrong = month._replace(period=Period.DAILY, covers="2026-01-22")

    with pytest.raises(ValueError, match="asked for as the daily file covering 2026-01-22"):
        ledger.rebuild_without(every_tier, wrong, ["2026-01-22"], identity=WRITER)


def test_an_index_that_cannot_be_read_is_refused_rather_than_read_as_empty(
    every_tier: Path, tmp_path: Path
) -> None:
    """A reader passes over an unreadable index; a prune that did would leave the rows behind."""
    state = a_copy(every_tier, tmp_path / "copy")
    ledger.compact_index_path(state, CENSUS, Period.MONTHLY).write_text(
        "{not an index", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="cannot be read"):
        ledger.find_holding_files(state, CENSUS, ["2026-01-22"])


def test_an_index_entry_whose_file_is_gone_is_refused_by_name(
    every_tier: Path, tmp_path: Path
) -> None:
    """An index that counts rows in a file nobody can open says the rows cannot be taken."""
    state = a_copy(every_tier, tmp_path / "copy")
    month = ledger.compact_file(state, CENSUS, Period.MONTHLY, "2026-01")
    assert month is not None
    month.unlink()

    with pytest.raises(ValueError, match="names 2026-01 and no file holds it"):
        ledger.find_holding_files(state, CENSUS, ["2026-01-22"])


@pytest.mark.parametrize("day", ["2026-1-22", "20260122", "2026-01"])
def test_a_day_that_is_not_a_utc_day_is_refused_before_a_file_is_read(
    every_tier: Path, day: str
) -> None:
    """A day is compared as text everywhere, so one in another shape would match nothing."""
    with pytest.raises(ValueError, match="is not a YYYY-MM-DD UTC day"):
        ledger.find_holding_files(every_tier, CENSUS, [day])
