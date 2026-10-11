"""Do changes compare the newest recorded value, not every value ever seen?"""

from __future__ import annotations

import json

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.telemetry.publish.settings_moved import checker_moved, inputs_moved

pytestmark = pytest.mark.contract


def _inputs() -> PipelineInputs:
    fixture = REPO_ROOT / "tests" / "fixtures" / "settings-moved" / "five-on-one-day.json"
    return PipelineInputs.model_validate(json.loads(fixture.read_text())["days"][2]["records"][0]["inputs"])


def test_both_languages_use_the_authored_expected_fixture() -> None:
    root = REPO_ROOT / "tests" / "fixtures" / "settings-moved"
    fixture = json.loads((root / "five-on-one-day.json").read_text())
    days = {
        day["date"]: [
            PipelineInputs.model_validate(run["inputs"])
            for run in day["records"] if run["inputs"] is not None
        ]
        for day in fixture["days"]
    }
    expected = json.loads((root / "five-on-one-day.expected.json").read_text())
    assert inputs_moved(days, "2026-09-14").model_dump() == expected
    assert days["2026-09-18"][0].prompt_sha256 != days["2026-09-18"][1].prompt_sha256


def test_missing_values_do_not_erase_a_names_last_recorded_value() -> None:
    original = _inputs()
    absent = original.model_copy(update={"turn_markers_sha256": None})
    changed = original.model_copy(update={"turn_markers_sha256": "a" * 64})
    result = inputs_moved({
        "2026-09-16": [original], "2026-09-17": [absent],
        "2026-09-18": [changed], "2026-09-19": [original],
    }, "2026-09-17")
    assert result.model_dump() == {
        "compared_from": "2026-09-17",
        "changes": [
            {"date": "2026-09-18", "inputs": ["turn_markers_sha256"]},
            {"date": "2026-09-19", "inputs": ["turn_markers_sha256"]},
        ],
    }


def test_first_values_and_removed_keys_do_not_claim_a_change() -> None:
    original = _inputs()
    first = original.model_copy(update={"turn_markers_sha256": None, "sampling": {"seed": "7"}})
    result = inputs_moved({"2026-09-16": [first], "2026-09-18": [original],
                          "2026-09-19": [first]}, "2026-09-14")
    assert result.model_dump() == {"compared_from": "2026-09-17", "changes": []}


def test_block_keys_are_in_code_point_order_and_carry_no_values() -> None:
    original = _inputs()
    changed = original.model_copy(update={"runtime_flags": {"-ctv": "f16", "-ctk": "f16"}})
    result = inputs_moved({"2026-09-16": [original], "2026-09-17": [changed]}, "2026-09-16")
    assert result.changes[0].inputs == ["runtime_flags.-ctk", "runtime_flags.-ctv"]


@pytest.mark.parametrize("stamp,first,expected", [
    (None, "2026-09-16", None),
    ("2026-09-18", "2026-09-16", "2026-09-19"),
    ("2026-09-15", "2026-09-16", "2026-09-16"),
])
def test_comparison_start(stamp: str | None, first: str, expected: str | None) -> None:
    days = {} if stamp is None else {stamp: [_inputs()]}
    assert inputs_moved(days, first).compared_from == expected


def test_checker_and_scorer_changes_have_independent_oracles() -> None:
    a = "scorer-a;metrics-a;bands=a;lead=a"
    b = "scorer-a;metrics-b;bands=b;lead=b"
    c = "scorer-b;metrics-b;bands=b;lead=b"
    result = checker_moved({
        "2026-09-15": [a], "2026-09-16": [b], "2026-09-17": [],
        "2026-09-18": [c], "2026-09-19": [b], "2026-09-20": [b, c],
        "2026-09-21": [c], "2026-09-22": ["scorer-b"],
    }, "2026-09-16")
    assert result.model_dump() == {
        "compared_from": "2026-09-16",
        "changes": [
            {"date": "2026-09-16", "score_moved": False},
            {"date": "2026-09-18", "score_moved": True},
            {"date": "2026-09-19", "score_moved": True},
            {"date": "2026-09-20", "score_moved": True},
            {"date": "2026-09-22", "score_moved": False},
        ],
    }
    assert checker_moved({}, "2026-09-16").compared_from is None
