"""Where is a model's turn envelope declared, and what may an entry leave out?"""

from __future__ import annotations

import json
import re

import pytest
from conftest import CONFIG_DIR
from pydantic import ValidationError

from idhazh.config import refuse_a_model_nothing_could_run
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

    The swap is the one an operator really makes: five strings edited in place
    with the markers underneath them untouched. One digest on the entry now
    answers for the settings and the markers together, because both are
    measurements about one model and the repair is the same sentence.
    """
    committed = committed_models()
    assert committed.summarize.declared_for == committed.summarize.sha256

    with pytest.raises(ValueError) as raised:
        refuse_a_model_nothing_could_run(
            "models/x.json", ModelsConfig.model_validate(swapped_summarizer())
        )
    message = str(raised.value)
    assert "models.summarize is declared for" in message, "the message names the entry"
    assert "re-derive them for these weights" in message, "and what to do about it"
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


def test_the_thinking_arms_closing_marker_is_derived_from_its_own_reply_openings() -> None:
    """Guardrail #10 over a string: the marker is read off this model, not guessed.

    `qwen3.5-9b-q4km-thinking.json` is the incumbent's weights with reasoning
    declared. Its marker is a newline, the closing think tag, then two newlines,
    and it was derived rather than
    typed from memory: both reply openings were recorded from the server that
    applies Qwen's own template, and the no-reasoning one is the reasoning one
    with an EMPTY block already closed - which is Qwen's documented way to turn
    reasoning off. So the difference between the two strings IS what closes a
    block, and a non-empty block closes with the same bytes.

    A wrong marker is the failure this whole envelope exists to stop: the stop
    never fires, the span runs to the window, and the grammar still accepts
    whatever comes back. That makes it worth an identity rather than a comment.
    """
    entry = ModelsConfig.from_json(
        (CONFIG_DIR / "models" / "qwen3.5-9b-q4km-thinking.json").read_text(encoding="utf-8")
    ).summarize
    turns = entry.turns

    assert turns.thinks, "the arm exists to turn reasoning on"
    assert turns.thinking_close is not None
    assert turns.reply_opening_thinking + turns.thinking_close == turns.reply_opening
    assert turns.thinking_close == "\n</think>\n\n"
    assert turns.thinking_kwarg == "enable_thinking", "a marker with no keyword is refused"
    assert entry.sha256 == committed_models().summarize.sha256, "same weights, one dossier"