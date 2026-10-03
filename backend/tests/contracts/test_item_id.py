"""Do old decimal and new base32 item addresses remain readable?"""

from __future__ import annotations

import json

import pytest
from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.digest_day import DigestDay, DigestItem

pytestmark = pytest.mark.contract


def test_an_item_id_reads_in_both_shapes_and_the_pattern_never_contracts() -> None:
    """A frozen decimal address must keep reading after base32 addresses arrive."""
    assert "[0-9]{2,}" in ITEM_ID_PATTERN, "the decimal branch is never removed"

    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    assert [item.item_id for item in day.items][:2] == ["ai-01", "energy-01"]

    payload = json.loads(read_text(FIXTURES_DIR / "digest" / "desk-differs-from-vertical.json"))
    old = DigestItem.model_validate(payload)
    assert old.item_id == "energy-9435555854", "a real ten-digit address"

    new = DigestItem.model_validate({**payload, "item_id": "energy-wfyypy5sgvnwcxd3"})
    assert new.item_id == "energy-wfyypy5sgvnwcxd3"

    for excluded in "ilou":
        with pytest.raises(ValidationError):
            DigestItem.model_validate({**payload, "item_id": f"energy-{excluded}fyypy5sgvnwcxd3"})
