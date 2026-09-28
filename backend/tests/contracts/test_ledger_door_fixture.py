"""Does the query door's fixture ledger say exactly what its files hold?

`tests/fixtures/ledger-door/state/` is a compacted `host-fingerprint` ledger laid
out as the committed tree is: two indexes and the compact files they name. The
frontend's `ledger-door.spec.ts` reads it through both of the door's entry points,
so an index that disagreed with its files would test the door against a tree the
compaction never writes. This checks the fixture with the backend's own readers:
both indexes are `CompactIndex` documents, every entry's `rows` is the row count
`persist.load` returns and its `bytes` is the file's size on disk, each file's
envelope names the ledger, the period and what its entry covers, and no compact
file sits in the tree without an entry naming it. It also pins the cases the
spec drives the door through, so a regenerated fixture cannot drop one quietly.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.file_envelope import Period, Tier
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import load, read_envelope
from idhazh.ledger.paths import compact_index_path, compact_path

pytestmark = pytest.mark.contract

STATE: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "ledger-door" / "state"
LEDGER: Final = LedgerName.HOST_FINGERPRINT


def index(period: Period) -> CompactIndex:
    """One of the fixture's two indexes, read the way a later run reads a payload."""
    return CompactIndex.read(compact_index_path(STATE, LEDGER, period))


@pytest.mark.parametrize("period", list(Period))
def test_each_index_is_a_compact_index_for_its_ledger_and_period(period: Period) -> None:
    """Validated by the contract itself, at the stamp the frontend copy reads."""
    held = index(period)
    assert (held.ledger, held.period) == (LEDGER, period)
    assert held.version == CompactIndex.schema_version()
    assert held.entries, f"the fixture's {period.value} index names no file"


@pytest.mark.parametrize("period", list(Period))
def test_every_entry_matches_the_file_the_backend_reader_opens(period: Period) -> None:
    """Rows as `persist.load` counts them, bytes as the disk measures them, and the
    envelope inside the file agreeing about what it covers."""
    for entry in index(period).entries:
        path = compact_path(STATE, LEDGER, period, entry.covers)
        assert path.is_file(), f"{entry.covers} is named in {period.value}.json and not on disk"
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


def test_no_compact_file_sits_in_the_tree_without_an_entry() -> None:
    """A file no index names is a file the door can never reach and the spec never tests."""
    named = {
        compact_path(STATE, LEDGER, period, entry.covers)
        for period in Period
        for entry in index(period).entries
    }
    on_disk = {
        path
        for period in Period
        for path in (STATE / "compact" / LEDGER.value / period.value).rglob("*")
        if path.is_file()
    }
    assert on_disk == named


def test_the_fixture_carries_every_case_the_door_is_driven_through() -> None:
    """A month file, a zero-row day, a hole, and a day both indexes name."""
    days = [entry.covers for entry in index(Period.DAILY).entries]
    months = [entry.covers for entry in index(Period.MONTHLY).entries]
    quiet = [entry.covers for entry in index(Period.DAILY).entries if entry.rows == 0]
    first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    span = [(first + timedelta(days=n)).isoformat() for n in range((last - first).days + 1)]
    holes = [day for day in span if day not in days and day[:7] not in months]
    both = [day for day in days if day[:7] in months]
    assert months, "no monthly file, so the coarsest-period rule is never exercised"
    assert quiet, "no day with rows 0, so a quiet day is never told from a hole"
    assert holes, "no hole at or before the newest daily entry"
    assert both, "no day named by both indexes, so reading one file a day cannot fail"
