"""Where is a model's turn envelope declared, and what may an entry leave out?"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.knobs.models import ModelEntry, ModelRef, ModelsConfig
from idhazh.contracts.run_manifest import ModelRole, ModelUse

from ._envelope import (
    turns_of,
)
from ._fixtures import committed_models, committed_models_raw, swapped_summarizer

pytestmark = pytest.mark.contract


def test_a_model_swap_can_no_longer_inherit_markers_nothing_declared_for_it() -> None:
    """The Oracle for the envelope, and the same rule the settings block obeys.

    A wrong marker is worse than a wrong number: it renders a prompt with no
    turn structure that the decoder's grammar still accepts, so the run
    publishes a plausible day and nothing anywhere raises.

    The swap here is the half-done one - `inference` re-declared for the new
    weights and `turns` left behind - because a swap that moved neither block is
    already refused by the settings gate above and would prove nothing here.
    """
    committed = committed_models()
    assert committed.summarize.turns.declared_for == committed.summarize.sha256

    raw = swapped_summarizer()
    raw["summarize"]["inference"]["declared_for"] = "1" * 64
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(raw)
    message = str(raised.value)
    assert "models.summarize.turns" in message, "the message names the block"
    assert "re-record them for these weights" in message, "and what to do about it"
    assert "1" * 64 in message, "and the weights the entry now names"


def test_an_entry_with_no_turn_envelope_at_all_is_refused() -> None:
    """Required with no default. An entry that forgets its markers fails at load."""
    raw = committed_models_raw()
    del raw["summarize"]["turns"]
    with pytest.raises(ValidationError, match="turns"):
        ModelsConfig.model_validate(raw)


@pytest.mark.parametrize("marker", ["turn_closing", "reply_opening", "reply_opening_thinking"])
def test_an_empty_marker_is_refused(marker: str) -> None:
    """`continued_prompt` splices the summarize-and-plan call onto `turn_closing`.

    An empty seam joins two turns into one, the grammar still answers, and the
    prefix the two-call design rests on is gone with nothing to read it off.
    """
    raw = committed_models_raw()
    turns_of(raw)[marker] = ""
    with pytest.raises(ValidationError, match="at least 1 character"):
        ModelsConfig.model_validate(raw)


@pytest.mark.parametrize("opening", ["<|im_start|>\n", "<|im_start|>$speaker\n"])
def test_a_turn_opening_that_names_no_role_is_refused(opening: str) -> None:
    """A substitution over a string that names nothing returns it unchanged.

    Every turn then renders with no role header, the prompt is still
    syntactically fine, and no reader downstream can tell. The second case is the
    renamed placeholder, which raises at the first render rather than at load -
    late, and in the middle of a shard.
    """
    raw = committed_models_raw()
    turns_of(raw)["turn_opening"] = opening
    with pytest.raises(ValidationError, match=re.escape("must name $role")):
        ModelsConfig.model_validate(raw)


def test_a_run_records_which_weights_ran_and_not_how_their_turns_are_written() -> None:
    """The split the envelope is required on one shape and absent from the other for.

    `ModelUse` embeds `ModelRef`, and no `model_ref` a run has ever written
    carries markers - requiring it there would stop this build reading them
    (`CLAUDE.md` section 11). So the entry is narrowed on the way into the
    record, and this asserts the narrowing rather than trusting it: a leaked
    `turns` would pass `extra="forbid"` on write and fail on the next read.

    What is given up is that `run.json` never says how the turns were written.
    `RunRecord.inputs.prompt_sha256` digests both turns rendered through them,
    so a marker that moved still moves the stamp.
    """
    entry = committed_models().summarize
    assert "turns" not in ModelRef.model_fields
    assert "turns" in ModelEntry.model_fields

    use = ModelUse(role=ModelRole.SUMMARIZE, model_ref=entry)
    recorded = json.loads(use.model_dump_json())

    assert "turns" not in recorded["model_ref"]
    assert recorded["model_ref"]["sha256"] == entry.sha256
    ModelUse.model_validate(recorded), "and the record it wrote reads back"


def test_the_retired_marker_file_is_refused_if_it_comes_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file nothing reads is a set of markers an operator believes are live.

    The package directory is exactly where somebody would put them back, so the
    path is checked rather than forgotten. Proved by making the file and watching
    the refusal, never by asserting it is absent - an assertion that it is absent
    passes on a tree where the check does not exist.

    The file is made at a redirected path, and the real one is pinned by a
    separate assertion. The suite runs several processes over one working tree,
    so a file written into the package refuses every config load a sibling
    process happens to be making at that moment.
    """
    assert config.RETIRED_TURN_MARKERS == (
        REPO_ROOT / "backend" / "idhazh" / "prompts" / "turn_markers.json"
    ), "the check must name the package directory, which is where they would come back"
    assert not config.RETIRED_TURN_MARKERS.exists(), "the row deleted it"

    came_back = tmp_path / "turn_markers.json"
    came_back.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(config, "RETIRED_TURN_MARKERS", came_back)
    with pytest.raises(ValueError, match=re.escape("models.<role>.turns")):
        config.load(CONFIG_DIR)

    monkeypatch.undo()
    assert config.load(CONFIG_DIR).models.summarize.turns.turn_closing
