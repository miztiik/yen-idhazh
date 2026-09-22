"""Where does a model's turn envelope come from, and what may an entry leave out?"""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.knobs.models import ModelEntry, ModelRef, ModelsConfig
from idhazh.contracts.run_manifest import ModelRole, ModelUse
from idhazh.llm.server import (
    PROBE_SYSTEM,
    PROBE_USER,
    ProbeRefusedError,
    SystemPlacement,
    TurnMarkers,
    render_prompt,
    turn_markers_from_renderings,
)

from ._fixtures import committed_models, committed_models_raw

pytestmark = pytest.mark.contract

#: What every refusal of a marker the sanitizer cannot strip has said since the
#: check was written, whether it ran at configuration load or at server start.
#: Quoted here rather than imported: a message that moved is what this test
#: exists to catch, and importing it would let the two move together.
BOUNDARY_ADVICE = (
    "An article carrying that marker would reach this model with the turn "
    "boundary intact. Teach the family to backend/idhazh/sanitize.py and move "
    "SANITIZER_VERSION with it, or name a model whose markers it already strips"
)


def recorded() -> dict[str, Any]:
    """Three renderings per model, as the model's own template made them.

    Read inside the test that wants it (`CLAUDE.md` section 13), never at
    import.
    """
    loaded: dict[str, Any] = json.loads(
        read_text(FIXTURES_DIR / "llm" / "derived-turn-markers.json")
    )
    return loaded


def derived(case: dict[str, Any]) -> TurnMarkers:
    return turn_markers_from_renderings(
        model_id=str(case["model_id"]),
        plain=str(case["plain"]),
        thinking=str(case["thinking"]),
        history=str(case["history"]),
        thinking_close=case["thinking_close"],
        thinking_kwarg=case["thinking_kwarg"],
    )


def committed_model_files() -> list[str]:
    """Every model file the repository commits, by name.

    Read rather than listed, so a model added tomorrow is covered by the Oracle
    below on the day it lands. The hand-typed list this replaced named four of
    the five already there.
    """
    return sorted(path.name for path in (CONFIG_DIR / "models").glob("*.json"))


@pytest.mark.parametrize("model_file", committed_model_files())
def test_the_derived_markers_render_the_prompt_the_typed_ones_rendered(
    model_file: str,
) -> None:
    """The Oracle. Markers read off a template render what markers typed by hand rendered.

    Byte-identical, per committed entry, so the change that deleted eight typed
    fields moved no published word. A wrong split of one rendering into markers
    renders a different prompt, and the grammar would still accept every reply
    it came back with - which is why this is an identity and not a shape check.

    Driven by a recorded reply, so nothing here touches the network (Guardrail
    #7). What it cannot settle is a template family none of the four uses: that
    is found at server start, before the first article.
    """
    case = recorded()["entries"][model_file]

    assert (
        render_prompt(system=PROBE_SYSTEM, user=PROBE_USER, markers=derived(case))
        == case["prompt_today"]
    )


def test_a_template_with_no_system_role_folds_the_system_text_and_says_so() -> None:
    """The second placement, read off the rendering rather than declared.

    A template with no system role puts the same words one turn earlier, behind
    whatever it joins the two blocks with. Both facts come out of the render, so
    a model of that family needs no field and no code path of its own.
    """
    markers = derived(recorded()["a_template_with_no_system_role"])

    assert markers.system_role is SystemPlacement.FOLD_INTO_FIRST_USER
    assert markers.system_joiner == "\n\n"
    assert markers.turn_opening.template == "<start_of_turn>${role}\n"


def test_a_marker_the_sanitizer_cannot_strip_is_refused_at_server_start() -> None:
    """Guardrail #11's control, in the place it now runs.

    It moved from configuration load to server start on 2026-09-21, because the
    markers stopped being typed by a person and started being read off the
    model's own template. What it refuses did not move with it: the same
    families, and the same sentence about what to do next.

    A template whose markers are ordinary words is the case with nowhere to
    widen toward - a pattern that stripped `Turn from user:` would strip prose -
    so an article could write a whole forged turn and it would survive into a
    prompt.
    """
    with pytest.raises(ProbeRefusedError) as refused:
        derived(recorded()["a_template_whose_markers_are_words"])

    said = str(refused.value)
    assert BOUNDARY_ADVICE in said, "the same sentence configuration load used to give"
    assert "turn_opening.system renders" in said, "and which marker it was"
    assert "an article may write it whole" in said, "and what the sanitizer said about it"


def test_every_committed_model_carries_markers_the_sanitizer_strips() -> None:
    """The other half: the check passes on every entry that has to pass it."""
    for model_file, case in recorded()["entries"].items():
        assert derived(case).turn_closing, model_file


def test_a_turn_block_left_in_a_model_file_is_refused_by_name() -> None:
    """The read-side migration a person's file is owed (`CLAUDE.md` section 11).

    Eight of the block's keys are the model's own template and are read off it
    now. A file still carrying them is refused rather than accepted in silence,
    because silence teaches a block that nothing reads.
    """
    raw = committed_models_raw()
    raw["summarize"]["turns"] = {"turn_opening": "<|im_start|>$role\n"}

    with pytest.raises(ValidationError, match="turns"):
        ModelsConfig.model_validate(raw)


def test_a_template_that_reads_no_keyword_cannot_be_asked_to_think() -> None:
    """The pair rule, on the entry that owns both halves.

    A null keyword means the request carries no `chat_template_kwargs` at all,
    so a closing marker beside it asks the template to turn reasoning on through
    a name nothing sends. The only symptom would be whatever the template's own
    default happens to be.
    """
    raw = committed_models_raw()
    raw["summarize"]["thinking_kwarg"] = None
    raw["summarize"]["thinking_close"] = "</think>"

    with pytest.raises(ValidationError, match="thinking_kwarg is null"):
        ModelsConfig.model_validate(raw)


def test_a_run_records_which_weights_ran_and_not_how_their_turns_are_written() -> None:
    """The split that keeps a recorded run readable.

    `ModelUse` embeds `ModelRef`, and no `model_ref` a run has ever written
    carries a closing marker - requiring it there would stop this build reading
    them (`CLAUDE.md` section 11). So the entry is narrowed on the way into the
    record, and this asserts the narrowing rather than trusting it.

    What is given up is that `run.json` never says how the turns were written.
    `RunRecord.inputs.turn_markers_sha256` digests the whole envelope the server
    derived, so a model whose template differs still moves the stamp.
    """
    entry = committed_models().summarize
    assert "thinking_close" not in ModelRef.model_fields
    assert "thinking_close" in ModelEntry.model_fields

    use = ModelUse(role=ModelRole.SUMMARIZE, model_ref=entry)
    written = json.loads(use.model_dump_json())

    assert "thinking_close" not in written["model_ref"]
    assert written["model_ref"]["sha256"] == entry.sha256
    ModelUse.model_validate(written), "and the record it wrote reads back"


def test_the_thinking_arms_closing_marker_is_derived_from_its_own_reply_openings() -> None:
    """Guardrail #10 over a string: the marker is read off this model, not guessed.

    `qwen3.5-9b-q4km-thinking.json` is the incumbent's weights with reasoning
    declared. Its marker is a newline, the closing think tag, then two newlines,
    and it was derived rather than typed from memory: both reply openings come
    off the server that applies Qwen's own template, and the no-reasoning one is
    the reasoning one with an EMPTY block already closed - which is Qwen's
    documented way to turn reasoning off. So the difference between the two
    strings IS what closes a block.

    A wrong marker is the one failure the entry still carries: the stop never
    fires, the span runs to the window, and the item lands `model_timed_out`.
    That makes it worth an identity rather than a comment.
    """
    entry = ModelsConfig.from_json(
        (CONFIG_DIR / "models" / "qwen3.5-9b-q4km-thinking.json").read_text(encoding="utf-8")
    ).summarize
    markers = derived(recorded()["entries"]["qwen3.5-9b-q4km-thinking.json"])

    assert entry.thinks, "the arm exists to turn reasoning on"
    assert entry.thinking_close == "\n</think>\n\n"
    assert markers.reply_opening_thinking + entry.thinking_close == markers.reply_opening
    assert entry.thinking_kwarg == "enable_thinking", "a marker with no keyword is refused"
    assert entry.sha256 == committed_models().summarize.sha256, "same weights, one dossier"
