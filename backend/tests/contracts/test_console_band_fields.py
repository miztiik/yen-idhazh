"""Does the band reader name the producer's fields and nullable movement shapes?"""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts.console_band import (
    BandCheckerMoved,
    BandSettingsMoved,
    CheckerMove,
    ConsoleBand,
    SettingsMove,
)

pytestmark = pytest.mark.contract


def test_reader_field_set_matches_the_band_contract() -> None:
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "console" / "band.ts")
    reader = source[source.index("export function readBand"):]
    # Historical compaction readings remain persisted, but the band no longer draws them.
    unread = {"version", "compaction_lag_days", "rows_uncompacted", "covers_through"}
    assert set(re.findall(r"\braw\.(\w+)", reader)) == set(ConsoleBand.model_fields) - unread
    for model in (SettingsMove, CheckerMove, BandSettingsMoved, BandCheckerMoved):
        body = re.search(rf"export interface {model.__name__} \{{([^}}]+)\}}", source)
        assert body is not None
        assert set(re.findall(r"\t(\w+):", body[1])) == set(model.model_fields)
    assert "score_moved: boolean;" in source
    assert "compared_from: string | null;" in source


def test_historic_bands_without_new_keys_read_as_unknown() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "console-band" / "newest-day.json"))
    payload.pop("settings_moved", None)
    payload.pop("checker_moved", None)
    historic = ConsoleBand.model_validate(payload)
    assert historic.settings_moved is None
    assert historic.checker_moved is None


@pytest.mark.parametrize("model,change", [
    (BandSettingsMoved, {"date": "2026-09-17", "inputs": ["prompt_sha256"]}),
    (BandCheckerMoved, {"date": "2026-09-17", "score_moved": False}),
])
def test_movement_shapes_refuse_duplicate_dates_and_missing_comparison(
    model: type[BandSettingsMoved] | type[BandCheckerMoved], change: dict[str, object]
) -> None:
    for payload in (
        {"compared_from": None, "changes": [change]},
        {"compared_from": "2026-09-18", "changes": [change]},
        {"compared_from": "2026-09-16", "changes": [change, change]},
    ):
        with pytest.raises(ValidationError):
            model.model_validate(payload)


def test_settings_names_refuse_values_duplicates_and_empty_changes() -> None:
    for names in ([], ["prompt_sha256", "prompt_sha256"], ["A" * 64], ["runtime_flags./path"]):
        with pytest.raises(ValidationError):
            SettingsMove(date="2026-09-17", inputs=names)
    assert SettingsMove(date="2026-09-17", inputs=["runtime_flags.-ctk"]).inputs == ["runtime_flags.-ctk"]
