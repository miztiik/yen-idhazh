"""Does every persisted shape still read back the way it was written?

The round trip through every fixture, the version stamp a writer inherits when
it omits one, and the release blocker section 11 names: a payload yesterday's
run wrote has to load today.

The schema each contract describes is computed here rather than read off disk.
`schemas/` held a generated copy of it until 2026-09-23, and the gate that kept
the copy honest was most of what the copy was for."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts import CONTRACTS
from idhazh.contracts.base import Contract
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

#: One record a real run published, copied out of the archive. It carries the
#: settings block under its old key, with a weights digest, a decode cap and a
#: draft head that no build declares now.
RETIRED_OPTION_RECORD = "a-run-that-pinned-a-retired-option.json"


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


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_schema_is_self_describing(contract: type[Contract]) -> None:
    schema: dict[str, Any] = contract.json_schema()
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


@pytest.mark.parametrize(
    ("stem", "fixture"),
    [("digest-day", "two-runs.json"), ("digest-view", "one-day.json")],
)
def test_a_published_day_that_still_carries_key_points_reads(stem: str, fixture: str) -> None:
    """Section 11's release blocker, for a field that left a frozen payload.

    Every day published before 2026-09-24 carries `key_points` on every item,
    and a published day is never rewritten. `extra="forbid"` would refuse one
    outright, so the read side drops the key by name - and this is the arm that
    proves it, because the canonical fixture no longer carries the key and so
    proves only the new shape.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / stem / fixture))
    for item in payload["items"]:
        item["key_points"] = ["A point the day used to publish."]

    day = BY_STEM[stem].model_validate(payload)

    assert day.items, "a day with no items proves nothing here"  # type: ignore[attr-defined]
    assert not any(hasattr(item, "key_points") for item in day.items)  # type: ignore[attr-defined]


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
            assert "log_verbosity" not in use.model_ref.inference


def test_a_run_record_a_real_run_wrote_still_reads_after_the_blocks_split() -> None:
    """Section 11's release blocker, asked of a payload a run really published.

    The settings became two plain mappings on 2026-09-21. Every record written
    before that carries one typed block under the old key, with the spellings
    that day's build declared - `declared_for`, a decode cap, a draft head. A
    mapping is what lets all of them keep reading, and that claim is only worth
    making against bytes somebody's run actually wrote rather than against a
    fixture rewritten alongside the shape.

    One file, copied out of the archive rather than read from it: a test that
    walked the published days would cost more every day the pipeline runs and go
    red on a date nobody chose (`CLAUDE.md` section 13).
    """
    payload = json.loads(read_text(FIXTURES_DIR / "run-manifest" / RETIRED_OPTION_RECORD))
    carried = [
        use["model_ref"]["inference"]
        for run in payload["runs"]
        for use in run["models"]
        if "inference" in use["model_ref"]
    ]
    assert carried, "the fixture stopped carrying a settings block, so this proves nothing"
    assert any("declared_for" in block for block in carried)
    assert any("max_think_tokens" in block for block in carried)

    manifest = RunManifest.model_validate(payload)
    read_back = [use.model_ref.inference for run in manifest.runs for use in run.models]
    assert read_back == carried, "a mapping reads a recorded block back unchanged"


def test_a_manifest_that_named_any_retired_decode_knob_still_reads() -> None:
    """Section 11's release blocker for every knob that has left this block.

    A run record embeds `ModelRef`, which embeds the settings block. Three
    spellings of a decode budget have passed through - `max_output_tokens` until
    2026-09-14, then `max_answer_tokens` and `max_think_tokens` until 2026-09-21
    - and a `thinking` flag sat beside the first of them. A build that could not
    read a manifest naming any of the four would lose the whole archive.

    They are carried rather than dropped now: the block is a plain mapping, so a
    key this build does not name costs nothing to keep and a reader that wants
    to know what a run really ran on can still see it.

    The keys are put back into the canonical fixture rather than committed as a
    second one, so the two payloads differ in exactly what this migration is
    about - and no test here walks `frontend/public/digest/`, which would cost
    more every day the pipeline runs and go red on a date nobody chose
    (`CLAUDE.md` section 13).
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    retired = {
        "max_output_tokens": 250,
        "max_answer_tokens": 900,
        "max_think_tokens": 256,
        "thinking": False,
    }
    rewound = 0
    for run in payload["runs"]:
        for use in run["models"]:
            use["model_ref"]["inference"].update(retired)
            rewound += 1
    assert rewound, "the fixture stopped carrying an inference block, so this proves nothing"

    manifest = RunManifest.model_validate(payload)
    for run in manifest.runs:
        for use in run.models:
            assert retired.items() <= use.model_ref.inference.items()


def test_a_config_file_that_names_the_retired_settings_block_is_refused_by_name() -> None:
    """The other half of the split: a person's file is told where the block went.

    A run record is migrated in silence because refusing it would stop today's
    build reading yesterday's run. A config file is the opposite case - somebody
    typed the block, and accepting it in silence teaches a spelling that nothing
    reads.
    """
    raw = committed_models_raw()
    raw["summarizer"]["inference"] = {"n_ctx": 4096}

    with pytest.raises(ValidationError, match=re.escape("models.<role>.server")):
        ModelsConfig.model_validate(raw)
