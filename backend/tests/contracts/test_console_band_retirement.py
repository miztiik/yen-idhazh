"""Old console bands read without restoring retired projection fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from idhazh.contracts.console_band import ConsoleBand

pytestmark = pytest.mark.contract

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests/fixtures/contracts/console-band/newest-day.json"
)


def test_old_and_new_bands_have_the_same_retained_facts() -> None:
    old = json.loads(FIXTURE.read_text(encoding="utf-8"))
    old["months"] = ["2026-08", "2026-09"]
    snapshot = json.loads(json.dumps(old))
    migrated = ConsoleBand.model_validate(old)
    assert old == snapshot, "migration must not mutate the caller's payload"
    new = {key: value for key, value in old.items() if key != "months"}
    assert migrated == ConsoleBand.model_validate(new)
    assert "months" not in migrated.model_dump()
    assert "months" not in ConsoleBand.model_json_schema()["properties"]
    assert migrated.settings_moved == ConsoleBand.model_validate(new).settings_moved
    assert migrated.checker_moved == ConsoleBand.model_validate(new).checker_moved


def test_legacy_months_does_not_hide_any_other_unknown_key() -> None:
    old = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for payload in (old, {**old, "months": ["2026-09"]}):
        with pytest.raises(ValidationError, match="unexpected_field"):
            ConsoleBand.model_validate({**payload, "unexpected_field": 1})
