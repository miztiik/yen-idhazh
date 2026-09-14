"""Do the committed schemas still match the models that generate them?

The drift gate, the round trip through every fixture, and the version stamp a
writer inherits when it omits one."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SCHEMAS_DIR, read_text

from idhazh.contracts.base import Contract
from idhazh.contracts.export import CONTRACTS, expected_filenames, export
from idhazh.contracts.run_manifest import RunManifest

from ._fixtures import (
    BY_STEM,
    fixture_id,
    fixture_paths,
    load,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("path", fixture_paths(), ids=fixture_id)
def test_fixture_round_trips_byte_identically(path: Path) -> None:
    """Serialize, validate, deserialize, re-serialize - same bytes."""
    text = read_text(path)
    once = load(path).to_json()
    assert once == text
    twice = BY_STEM[path.parent.name].from_json(once).to_json()
    assert twice == once


def test_every_contract_has_at_least_one_fixture() -> None:
    covered = {path.parent.name for path in fixture_paths()}
    assert covered == set(BY_STEM), "a contract without a fixture has never been proven to load"


def test_committed_schemas_match_the_models(tmp_path: Path) -> None:
    export(tmp_path)
    for contract in CONTRACTS:
        name = contract.schema_filename()
        assert read_text(SCHEMAS_DIR / name) == read_text(tmp_path / name), (
            f"{name} is stale - edit the Pydantic model and regenerate, never the schema"
        )


def test_schemas_directory_holds_exactly_the_generated_files() -> None:
    on_disk = {path.name for path in SCHEMAS_DIR.glob("*.json")}
    assert on_disk == expected_filenames()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_schema_is_self_describing(contract: type[Contract]) -> None:
    schema: dict[str, Any] = json.loads(read_text(SCHEMAS_DIR / contract.schema_filename()))
    assert schema["$id"] == contract.schema_filename(), "$id is a relative filename, never a URL"
    assert schema["version"] == schema["changelog"][0]["version"]
    versions = [entry["version"] for entry in schema["changelog"]]
    assert versions == sorted(versions, reverse=True)
    assert len(set(versions)) == len(versions)
    for entry in schema["changelog"]:
        assert entry["change"] and entry["why"]


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_version_defaults_to_the_newest_changelog_entry(contract: type[Contract]) -> None:
    assert contract.schema_version() == contract.__changelog__[0].version


def test_an_older_payload_still_validates() -> None:
    """A payload yesterday's run wrote must load today, or it is a release blocker."""
    path = CONTRACT_FIXTURES_DIR / "summary" / "ok.json"
    payload = json.loads(read_text(path))
    payload["version"] = "2026-01-01"
    assert load_summary(payload).version == "2026-01-01"


def load_summary(payload: dict[str, Any]) -> Contract:
    return BY_STEM["summary"].model_validate(payload)


def test_a_payload_written_before_a_field_existed_still_reads() -> None:
    """Section 11's release blocker, tested against the key rather than the stamp.

    A payload from before the summarizer wrote titles has no `title` key at all.
    It must still load, and its committed `output_digest` must still verify -
    which it does because a null title is left out of the digested payload
    rather than digested as null.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    del payload["title"]
    assert load_summary(payload).title is None  # type: ignore[attr-defined]


def test_version_is_stamped_when_a_writer_omits_it() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    del payload["version"]
    assert load_summary(payload).version == BY_STEM["summary"].schema_version()


def test_a_manifest_written_before_the_verbosity_knob_still_reads() -> None:
    """Section 11's release blocker, for the other document the knob reached.

    `log_verbosity` landed on the embedded inference block on 2026-09-09, so
    every manifest published before that day has no such key. The claim that
    those still read is only worth making if something removes the key and
    checks - the canonical fixture carries it, so the fixture alone proves the
    new shape and nothing about the old one.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    stripped = 0
    for run in payload["runs"]:
        for use in run["models"]:
            del use["model_ref"]["inference"]["log_verbosity"]
            stripped += 1
    assert stripped, "the fixture stopped carrying an inference block, so this proves nothing"

    manifest = RunManifest.model_validate(payload)
    for run in manifest.runs:
        for use in run.models:
            assert use.model_ref.inference.log_verbosity is None
