"""The raw-day listing fixture is a real `RawDayIndex` beside the files it names."""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh.contracts.ledger_index import RawDayIndex

pytestmark = pytest.mark.contract

FIXTURE = Path("tests/fixtures/raw-day-listing/state/raw/item-health")


def test_raw_day_listing_fixture_names_the_files_beside_it() -> None:
    """A fixture edit that loses a file or changes the listing fails here."""
    listing = RawDayIndex.model_validate_json(
        (FIXTURE / "index" / "2026-09-02.json").read_text(encoding="utf-8")
    )
    files = sorted(path.name for path in (FIXTURE / "2026" / "09" / "02").iterdir())
    assert listing.files == files
    assert listing.bytes is None
