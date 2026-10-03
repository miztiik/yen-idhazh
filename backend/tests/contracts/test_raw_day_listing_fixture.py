"""The raw-day listing fixture is a real `RawDayIndex` beside the files it names."""

from __future__ import annotations

from hashlib import sha256

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.ledger_index import RawDayIndex

pytestmark = pytest.mark.contract

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "raw-day-listing" / "state" / "raw" / "item-health"


def _listed() -> RawDayIndex:
    return RawDayIndex.model_validate_json(
        (FIXTURE / "index" / "2026-09-02.json").read_text(encoding="utf-8")
    )


def test_raw_day_listing_fixture_names_the_files_beside_it() -> None:
    """A fixture edit that loses a file or changes the listing fails here."""
    listing = _listed()
    files = sorted(path.name for path in (FIXTURE / "2026" / "09" / "02").iterdir())
    assert listing.files == files
    assert listing.bytes is None


def test_raw_day_listing_fixture_digest_follows_the_contract_rule() -> None:
    """A changed name or digest fails against the rule `content_sha256` declares."""
    listing = _listed()
    names = "\n".join(listing.files).encode("utf-8")
    assert listing.content_sha256 == sha256(names).hexdigest()
