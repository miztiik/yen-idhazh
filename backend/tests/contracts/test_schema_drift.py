"""Does every Python-owned persisted shape still read back the way it was written?

The round trip through every fixture, and the release blocker section 11 names:
a payload yesterday's run wrote has to load today.

The schema each contract describes is computed here rather than read off disk.
`schemas/` held a generated copy of it until 2026-09-23, and the gate that kept
the copy honest was most of what the copy was for. TypeScript planner fixtures
are validated by the TypeScript contract tests, not by Python mirrors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from support.paths import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh.contracts import CONTRACTS
from idhazh.contracts.base import Contract
from idhazh.contracts.eval_row import DROPPED_CELLS as DROPPED_EVAL_CELLS
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.knobs.prompts import PromptFilesConfig
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.visual_decision import VisualKind

from . import _fixtures
from ._fixtures import BY_STEM, fixture_id, fixture_paths, load

pytestmark = pytest.mark.contract

#: One record a real run published, copied out of the archive. It carries the
#: settings block under its old key, with a weights digest, a decode cap and a
#: draft head that no build declares now.
RETIRED_OPTION_RECORD = "a-run-that-pinned-a-retired-option.json"


@pytest.mark.parametrize("path", fixture_paths(), ids=fixture_id)
def test_fixture_round_trips_without_losing_values(path: Path) -> None:
    """Keep every written value except the retired diagnostic, and keep migrations stable.

    Formatting is not compared here. `test_json_serialization.py` holds the bytes.
    """
    original = json.loads(read_text(path))
    contract = BY_STEM[path.parent.name]
    record = load(path)
    once = record.to_json()
    if record.version == original["version"]:
        expected = original
        if contract.__schema_stem__ == "sources":
            expected = {
                **original,
                "publishers": [],
                "feeds": [
                    {
                        **feed, "added_on": None, "publisher_id": None,
                        "retirement_reason": None,
                    }
                    for feed in original["feeds"]
                ],
                "retired": [
                    {
                        **feed, "added_on": None, "publisher_id": None,
                        "retirement_reason": None,
                    }
                    for feed in original["retired"]
                ],
            }
        elif contract.__schema_stem__ == "review-queue":
            row_defaults = {
                "alt_text": None,
                "asset_relpath": None,
                "none_reason": None,
                "planned_type": None,
                "rationale": None,
                "rendered_type": None,
                "title": None,
                "visual_id": None,
            }
            expected = {
                **original,
                "rows": [
                    {**row_defaults, **row}
                    for row in original["rows"]
                ],
            }
        elif "publisher_id" in contract.model_fields and "publisher_id" not in original:
            expected = {**original, "publisher_id": None}
        elif contract.__schema_stem__ == "fetched-document":
            expected = {
                "parent_fetch_request_id": None, "parent_batch_id": None,
                "entry_ordinal": None, **original,
            }
        elif contract.__schema_stem__ == "host-fingerprint-row":
            expected = {"machine_memory_total_mib": None, **original}
        elif contract.__schema_stem__ == "item-health-row":
            expected = {"visual_id": None, "analyze_ms": None, **original}
        elif contract.__schema_stem__ == "visual-attempt-row":
            expected = {
                "visual_id": None,
                **original,
                "planned_type": None,
                "rendered_type": None,
                "gate_floor_applied": None,
            }
        elif contract.__schema_stem__ == "visual-decision":
            expected = {
                **original,
                "deepest_downgrade_depth": None,
                "rejection_reason": None,
                "gate_floor_applied": None,
            }
            if "visual_id" in contract.model_fields and "visual_id" not in original:
                expected["visual_id"] = None
        elif "visual_id" in contract.model_fields and "visual_id" not in original:
            expected = {**original, "visual_id": None}
        if contract.__schema_stem__ in {
            "story-similarity-pair", "story-similarity-distribution",
            "content-similarity-judge-metrics", "fitted-similarity-threshold",
        }:
            expected = {"judge_policy_version": None, **expected}
        if contract.__schema_stem__ == "fitted-similarity-threshold":
            expected = {"pairs_refused": None, **expected}
        if contract.__schema_stem__ in {
            "story-similarity-distribution", "fitted-similarity-threshold",
        }:
            expected = {"calibration_policy_version": None, **expected}
        if contract.__schema_stem__ == "day-metrics":
            expected.pop("label_similarity", None)
            for key in ("bands", "reasons", "determinism_violations"):
                expected.pop(key, None)
            expected["sources"] = [
                {key: value for key, value in source.items() if key != "doubted"}
                for source in expected["sources"]
            ]
            expected["instruments"] = [
                entry for entry in expected["instruments"]
                if entry["column"] not in DROPPED_EVAL_CELLS
            ]
        if contract.__schema_stem__ == "eval-row":
            expected = {
                key: value for key, value in expected.items() if key not in DROPPED_EVAL_CELLS
            }
        if contract.__schema_stem__ == "label-row":
            expected = {
                key: value for key, value in expected.items()
                if key not in {"unsupported_numbers", "hedge_dropped"}
            }
        if contract.__schema_stem__ == "run-manifest":
            expected = {
                **expected,
                "runs": [
                    {key: value for key, value in run.items() if key != "determinism_violations"}
                    for run in expected["runs"]
                ],
            }
        if contract.__schema_stem__ == "app-config" and "prompt_files" not in original:
            expected = {**expected, "prompt_files": PromptFilesConfig().model_dump(mode="json")}
        if contract.__schema_stem__ == "app-config":
            evaluation = dict(expected["evaluation"])
            if "verbatim_reject_ceiling" in evaluation:
                evaluation["corpus_compression_ceiling"] = evaluation.pop("verbatim_reject_ceiling")
            expected = {
                **expected,
                "evaluation": evaluation,
                "drift": {
                    key: value for key, value in expected["drift"].items()
                    if key != "extractiveness_rise"
                },
                "finetune": {
                    key: value for key, value in expected["finetune"].items()
                    if key != "prompt_iterations"
                },
            }
        assert json.loads(once) == expected
    else:
        assert original["version"] < record.version
        assert record.version == contract.schema_version()
    reloaded = contract.from_json(once)
    if contract.__schema_stem__ == "day-metrics":
        assert reloaded == record.model_copy(update={"label_similarity": None})
    else:
        assert reloaded == record
    assert reloaded.to_json() == once


def test_every_contract_has_at_least_one_fixture() -> None:
    covered = {path.parent.name for path in fixture_paths()}
    assert covered == set(BY_STEM), "a contract without a fixture has never been proven to load"


def test_named_fixture_inputs_do_not_discover_added_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_fixtures, "CONTRACT_FIXTURES_DIR", tmp_path)
    extra = tmp_path / "unregistered"
    extra.mkdir()
    (extra / "extra.json").write_text("{}", encoding="utf-8", newline="\n")

    selected = fixture_paths()

    assert selected == [tmp_path / name for name in _fixtures.FIXTURE_FILES]
    assert extra / "extra.json" not in selected
    assert len(selected) == len(set(selected)), "a fixture must not be read twice"


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_schema_is_self_describing(contract: type[Contract]) -> None:
    schema: dict[str, Any] = contract.json_schema()
    for entry in schema["changelog"]:
        assert entry["change"] and entry["why"]


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


def test_a_summary_written_while_the_length_verdict_existed_still_reads() -> None:
    """Section 10's release blocker, for a field that left a payload a later run reads.

    A day is recovered from an earlier run's worker artifacts, so a build reads
    summaries written while the length verdict existed, and each carries
    `length_action`. `extra="forbid"` would refuse one outright, so the read side
    drops the key by name - and this is the half that proves it, because the
    canonical fixture no longer carries the key and so proves only the new shape.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    payload["length_action"] = "trim"

    assert not hasattr(load_summary(payload), "length_action")


def test_a_historical_visual_without_a_kind_still_reads_as_a_chart() -> None:
    """A day written before the separate grid format has no family field.

    Every historical visual was a chart, so adding a family must not make an
    earlier published day unreadable or send its file to a new reader.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    visual = next(item["visual"] for item in payload["items"] if item.get("visual") is not None)
    del visual["kind"]

    day = BY_STEM["digest-day"].model_validate(payload)

    item = next(item for item in day.items if item.visual is not None)  # type: ignore[attr-defined]
    assert item.visual is not None
    assert item.visual.kind is VisualKind.CHART


@pytest.mark.parametrize(
    ("stem", "fixture"),
    [("digest-day", "two-runs.json"), ("digest-view", "one-day.json")],
)
def test_a_published_day_that_still_carries_key_points_reads(stem: str, fixture: str) -> None:
    """Section 11's release blocker, for a field that left a frozen payload.

    Every day published before 2026-09-24 carries `key_points` on every item,
    and a published day is never rewritten. `extra="forbid"` would refuse one
    outright, so the read side drops the key by name - and this is the half that
    proves it, because the canonical fixture no longer carries the key and so
    proves only the new shape.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / stem / fixture))
    for item in payload["items"]:
        item["key_points"] = ["A point the day used to publish."]

    day = BY_STEM[stem].model_validate(payload)

    assert day.items, "a day with no items proves nothing here"  # type: ignore[attr-defined]
    assert not any(hasattr(item, "key_points") for item in day.items)  # type: ignore[attr-defined]


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
    assert all("determinism_violations" not in run.model_dump() for run in manifest.runs)
    for before, after in zip(payload["runs"], manifest.runs, strict=True):
        assert after.run_id == before["run_id"]
        assert after.inputs is not None
        assert after.inputs == PipelineInputs.model_validate(before["inputs"])
