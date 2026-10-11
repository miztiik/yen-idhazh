"""Does the persisted migration contract reject unsafe or falsely ready scopes?"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from idhazh.contracts.host_migration import HistoryManifest, HistoryReport

pytestmark = pytest.mark.contract


def manifest_document() -> dict[str, Any]:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "host-events"
        / "history-migration.json"
    )
    document: object = json.loads(fixture.read_bytes())["manifest"]
    if not isinstance(document, dict):
        raise ValueError("manifest fixture requires a JSON object")
    return document


def test_scope_hash_and_schema_are_stable() -> None:
    manifest = HistoryManifest.model_validate(manifest_document())
    assert HistoryManifest.from_json(manifest.to_json()) == manifest
    assert manifest.scope_hash() == HistoryManifest.model_validate(manifest_document()).scope_hash()
    assert HistoryManifest.json_schema()["version"] == "2026-10-11"
    assert HistoryReport.json_schema()["version"] == "2026-10-11"


@pytest.mark.parametrize(
    "path", ["../state", "C:/state", "/state", "state\\raw", "state//raw", "state/./raw"]
)
def test_unsafe_root_path_is_refused(path: str) -> None:
    document = manifest_document()
    document["roots"][0]["state_root"] = path
    with pytest.raises(ValueError):
        HistoryManifest.model_validate(document)


@pytest.mark.parametrize("fault", ["future", "unknown", "duplicate", "range", "output", "trial"])
def test_closed_manifest_consistency(fault: str) -> None:
    document = manifest_document()
    if fault == "future":
        document["range_end"] = "2026-10-11"
    elif fault == "unknown":
        document["version"] = "2099-01-01"
    elif fault == "duplicate":
        document["closed_periods"].append(document["closed_periods"][0])
    elif fault == "range":
        document["range_start"] = "2026-09-21"
    elif fault == "output":
        document["isolated_root"] = "state/replacements"
    elif fault == "trial":
        document["roots"][0]["kind"] = "trial"
    with pytest.raises(ValueError):
        HistoryManifest.model_validate(document)
