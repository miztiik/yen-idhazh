"""The raw-day listing fixture is a real `RawDayIndex` beside the files it names."""

from __future__ import annotations

from typing import cast

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.file_envelope import FileEnvelope
from idhazh.contracts.ledger_index import RawDayIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.tasks._index_day import listing
from idhazh.ledger import RawFile

pytestmark = pytest.mark.contract

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "raw-day-listing" / "state" / "raw" / "item-health"


def test_raw_day_listing_fixture_names_the_files_beside_it() -> None:
    """A fixture edit that loses a file or changes the listing fails here."""
    listing = RawDayIndex.model_validate_json(
        (FIXTURE / "index" / "2026-09-02.json").read_text(encoding="utf-8")
    )
    files = sorted(path.name for path in (FIXTURE / "2026" / "09" / "02").iterdir())
    assert listing.files == files
    assert listing.bytes is None


def test_raw_day_listing_fixture_is_the_compaction_writer_output() -> None:
    """A changed digest or ordering fails against the real compaction helper."""
    listed = RawDayIndex.model_validate_json(
        (FIXTURE / "index" / "2026-09-02.json").read_text(encoding="utf-8")
    )
    files = [
        RawFile(path, cast(FileEnvelope, None))
        for path in sorted((FIXTURE / "2026" / "09" / "02").iterdir())
    ]
    assert listing(
        files,
        ledger=LedgerName.ITEM_HEALTH,
        day="2026-09-02",
        listed_at=listed.listed_at,
    ) == listed
