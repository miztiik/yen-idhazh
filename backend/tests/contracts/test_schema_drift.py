"""Do the committed schemas still match the models that generate them?

The drift gate, the round trip through every fixture, and the version stamp a
writer inherits when it omits one."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SCHEMAS_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.base import Contract
from idhazh.contracts.export import CONTRACTS, expected_filenames, export
from idhazh.contracts.knobs.inference import RETIRED_INFERENCE_NAMES
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.run_manifest import RunManifest

from ._fixtures import (
    BY_STEM,
    committed_models_raw,
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


def test_a_manifest_that_named_any_retired_decode_knob_still_reads() -> None:
    """Section 11's release blocker for every knob that has left this block.

    A run record embeds `ModelRef`, which embeds the settings block, and `Model`
    forbids a key it no longer declares. Three spellings of a decode budget have
    passed through - `max_output_tokens` until 2026-09-14, then
    `max_answer_tokens` and `max_think_tokens` until 2026-09-21 - and a
    `thinking` flag sat beside the first of them. A build that could not read a
    manifest naming any of the four would lose the whole archive.

    They are dropped rather than carried: no field replaces them, and a cap that
    no longer bounds anything is not a reading worth keeping (Guardrail #10).

    The keys are put back into the canonical fixture rather than committed as a
    second one, so the two payloads differ in exactly what this migration is
    about - and no test here walks `frontend/public/digest/`, which would cost
    more every day the pipeline runs and go red on a date nobody chose
    (`CLAUDE.md` section 13).
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    rewound = 0
    for run in payload["runs"]:
        for use in run["models"]:
            use["model_ref"]["inference"].update(
                max_output_tokens=250,
                max_answer_tokens=900,
                max_think_tokens=256,
                thinking=False,
            )
            rewound += 1
    assert rewound, "the fixture stopped carrying an inference block, so this proves nothing"

    manifest = RunManifest.model_validate(payload)
    for run in manifest.runs:
        for use in run.models:
            written = use.model_ref.inference.model_dump(mode="json")
            assert not RETIRED_INFERENCE_NAMES & written.keys()


def test_a_config_file_that_names_a_retired_decode_knob_is_refused_by_name() -> None:
    """The other half of the split: a person's file is told where the knob went.

    A run record is migrated in silence because refusing it would stop today's
    build reading yesterday's run. A config file is the opposite case - somebody
    typed the block, and accepting it in silence teaches a knob that nothing
    reads.
    """
    for retired in sorted(RETIRED_INFERENCE_NAMES):
        raw = committed_models_raw()
        raw["summarize"]["inference"][retired] = 1

        with pytest.raises(ValidationError, match=re.escape(retired)):
            ModelsConfig.model_validate(raw)
