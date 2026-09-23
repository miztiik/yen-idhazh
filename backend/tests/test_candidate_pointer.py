"""Does a scratch config move the pointer and nothing else?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utilities import candidate_pointer


def _scratch(tmp_path: Path) -> Path:
    """A copied config tree, as `cp -a config` leaves one."""
    scratch = tmp_path / "candidate-config"
    scratch.mkdir()
    (scratch / "idhazh.json").write_text(
        json.dumps(
            {
                "models_file": "config/models/incumbent.json",
                "run": {"trial_state_dirname": "state"},
                "summarize": {"truncate_chars": 6000},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return scratch


def test_the_pointer_moves_and_so_does_the_trial_state(tmp_path: Path) -> None:
    scratch = _scratch(tmp_path)

    written = candidate_pointer.point_at(
        "config/models/candidate.json", scratch=scratch, trial_state="trial"
    )

    settings = json.loads(written.read_text(encoding="utf-8"))
    assert settings["models_file"] == "config/models/candidate.json"
    assert settings["run"]["trial_state_dirname"] == "trial"
    assert settings["summarize"] == {"truncate_chars": 6000}, "a control the bench reads moved"


def test_a_field_transplanted_onto_the_entry_is_refused(tmp_path: Path) -> None:
    """The refusal, over every caller rather than over one workflow's YAML.

    A copy that carries the candidate's digest, revision or quantisation onto
    the committed entry says the numbers measured for one model hold for
    another (Guardrail #10).
    """
    committed = json.loads((_scratch(tmp_path) / "idhazh.json").read_text(encoding="utf-8"))
    transplanted = json.loads(json.dumps(committed))
    transplanted["models_file"] = "config/models/candidate.json"
    transplanted["summarizer"]["sha256"] = "a" * 64

    with pytest.raises(ValueError, match=r"summarize\.sha256"):
        candidate_pointer.refuse_any_other_move(committed, transplanted)


def test_a_control_the_numbers_are_read_under_cannot_be_edited(tmp_path: Path) -> None:
    committed = json.loads((_scratch(tmp_path) / "idhazh.json").read_text(encoding="utf-8"))
    edited = json.loads(json.dumps(committed))
    edited["summarize"]["truncate_chars"] = 12000

    with pytest.raises(ValueError, match=r"summarize\.truncate_chars"):
        candidate_pointer.refuse_any_other_move(committed, edited)


def test_moving_only_the_two_allowed_keys_is_allowed(tmp_path: Path) -> None:
    committed = json.loads((_scratch(tmp_path) / "idhazh.json").read_text(encoding="utf-8"))
    allowed = json.loads(json.dumps(committed))
    allowed["models_file"] = "config/models/candidate.json"
    allowed["run"]["trial_state_dirname"] = "trial"

    candidate_pointer.refuse_any_other_move(committed, allowed)
