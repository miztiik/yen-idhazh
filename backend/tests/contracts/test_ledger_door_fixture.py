"""Does the query door's fixture ledger say exactly what its files hold?

`tests/fixtures/ledger-door/` holds two state roots of one compacted
`host-fingerprint` ledger, laid out as the committed tree is. `state/` holds a
daily and a monthly index and the compact files they name; `year-state/` holds
the same rows after their year was packed, under a yearly and a daily index.
Each root also holds the third index, naming nothing, because the compaction
writes a ledger's three indexes together. The
frontend's `ledger-door.spec.ts` reads both through the door's entry points, so
an index that disagreed with its files would test the door against a tree the
compaction never writes. This checks each root with the backend's own readers:
every index is a `CompactIndex` document, every entry's `rows` is the row count
`persist.load` returns and its `bytes` is the file's size on disk, each file's
envelope names the ledger, the period and what its entry covers. It also pins the cases the spec
drives the door through, so a regenerated fixture cannot drop one quietly.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pyarrow.parquet
import pytest
from conftest import REPO_ROOT

from idhazh.contracts.file_envelope import Period, Tier
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import load, read_envelope
from idhazh.ledger.paths import compact_index_path, compact_path

pytestmark = pytest.mark.contract

FIXTURE: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "ledger-door"
LEDGER: Final = LedgerName.HOST_FINGERPRINT

#: Each state root, and the periods whose index names a file. The root's other
#: index is there too, and names nothing.
HELD: Final[dict[str, tuple[Period, ...]]] = {
    "state": (Period.DAILY, Period.MONTHLY),
    "year-state": (Period.DAILY, Period.YEARLY),
}
INDEXED: Final = [(root, period) for root, periods in HELD.items() for period in periods]


def index(root: str, period: Period) -> CompactIndex:
    """One of a root's indexes, read the way a later run reads a payload."""
    return CompactIndex.read(compact_index_path(FIXTURE / root, LEDGER, period))


@pytest.mark.parametrize("root", list(HELD))
def test_every_root_holds_all_three_indexes_as_the_compaction_writes_them(root: str) -> None:
    """The compaction writes a ledger's three indexes together, so the door never
    asks for one that is not there, and an index a root packs nothing into names nothing."""
    for period in Period:
        held = index(root, period)
        assert (held.ledger, held.period) == (LEDGER, period)
        assert held.version <= CompactIndex.schema_version()
        if period not in HELD[root]:
            assert held.entries == [], f"the fixture's {root} {period.value} index names a file"


@pytest.mark.parametrize(("root", "period"), INDEXED)
def test_each_index_is_a_compact_index_for_its_ledger_and_period(root: str, period: Period) -> None:
    """Validated by the contract itself, at a stamp the frontend copy can read."""
    held = index(root, period)
    assert (held.ledger, held.period) == (LEDGER, period)
    assert held.version <= CompactIndex.schema_version()
    assert held.entries, f"the fixture's {root} {period.value} index names no file"


@pytest.mark.parametrize(("root", "period"), INDEXED)
def test_every_entry_matches_the_file_the_backend_reader_opens(root: str, period: Period) -> None:
    """Rows as `persist.load` counts them, bytes as the disk measures them, and the
    envelope inside the file agreeing about what it covers."""
    for entry in index(root, period).entries:
        path = compact_path(FIXTURE / root, LEDGER, period, entry.covers)
        assert path.is_file(), f"{entry.covers} is named in {root} {period.value}.json, not on disk"
        rows = load([path], model=HostFingerprintRow)
        assert len(rows) == entry.rows, f"{path.name} holds {len(rows)} rows, entry says {entry.rows}"
        assert path.stat().st_size == entry.bytes, f"{path.name} is not {entry.bytes} bytes"
        envelope = read_envelope(path)
        assert (envelope.tier, envelope.ledger, envelope.period, envelope.covers) == (
            Tier.COMPACT,
            LEDGER,
            period,
            entry.covers,
        )


def test_the_fixture_carries_every_case_the_door_is_driven_through() -> None:
    """A month file, a zero-row day, a hole, and a day both indexes name."""
    days = [entry.covers for entry in index("state", Period.DAILY).entries]
    months = [entry.covers for entry in index("state", Period.MONTHLY).entries]
    quiet = [entry.covers for entry in index("state", Period.DAILY).entries if entry.rows == 0]
    first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    span = [(first + timedelta(days=n)).isoformat() for n in range((last - first).days + 1)]
    holes = [day for day in span if day not in days and day[:7] not in months]
    both = [day for day in days if day[:7] in months]
    assert months, "no monthly file, so the coarsest-period rule is never exercised"
    assert quiet, "no day with rows 0, so a quiet day is never told from a hole"
    assert holes, "no hole at or before the newest daily entry"
    assert both, "no day named by both indexes, so reading one file a day cannot fail"


def test_the_packed_year_holds_the_first_root_s_rows_one_row_group_a_month() -> None:
    """What the first root serves for August and September, and one row group for each.

    So the spec can ask one span of both roots and expect the same rows, and a
    reader that filters on a date can skip the month it does not want.
    """
    state = FIXTURE / "state"
    august = [compact_path(state, LEDGER, Period.MONTHLY, "2026-08")]
    september = [
        compact_path(state, LEDGER, Period.DAILY, entry.covers)
        for entry in index("state", Period.DAILY).entries
        if entry.covers.startswith("2026-09-")
    ]
    year = compact_path(FIXTURE / "year-state", LEDGER, Period.YEARLY, "2026")
    months = [load(august, model=HostFingerprintRow), load(september, model=HostFingerprintRow)]
    assert load([year], model=HostFingerprintRow) == months[0] + months[1]
    footer = pyarrow.parquet.read_metadata(year)
    groups = [footer.row_group(at).num_rows for at in range(footer.num_row_groups)]
    assert groups == [len(month) for month in months]
