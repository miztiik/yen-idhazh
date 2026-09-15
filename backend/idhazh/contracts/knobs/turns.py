"""How one turn is written for the weights an entry names."""

from __future__ import annotations

from enum import StrEnum
from string import Template
from typing import Final, Self

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import Model, Sha256

#: The name a turn opening substitutes the role under. `string.Template` renders
#: it, so both `$role` and `${role}` spell it and the validator accepts either.
TURN_ROLE: Final = "role"


class SystemPlacement(StrEnum):
    """Where this model's template takes the system text. Two, and no third.

    A turn topology, so it is an enum rather than a free-form string: what
    "folded into the first user turn" MEANS is a code path, and expressing it as
    data would need a template language in config - a second renderer nobody
    tests (docs/architecture/summarize/model-boundary.md).
    """

    #: A system turn of its own, ahead of the first user turn. Every chat
    #: template that has a system role.
    OWN_TURN = "own_turn"
    #: No system role exists, so the same bytes open the first user turn instead,
    #: behind the joiner the entry declares. The same words at a different
    #: address, never different words.
    FOLD_INTO_FIRST_USER = "fold_into_first_user"


class TurnsConfig(Model):
    """How one turn is written for the weights this entry names.

    It is the envelope, never the content. These strings decide where a turn
    opens and closes, where the system text goes and how a reply begins; what
    the turns SAY is `backend/idhazh/prompts/*.txt` and is the same set for
    every model (docs/architecture/summarize/model-boundary.md).

    They belong beside the entry that names the weights, not in this project's
    prompt directory: a marker is a fact about somebody else's weights, and
    holding it apart from the entry lets a model swap move one and leave the
    other. Nothing raises when that happens - a wrong
    marker renders a prompt with no turn structure that the decoder's grammar
    still accepts - worse summaries and no error anywhere.

    **The trailing newlines are load-bearing and invisible.** They survive here
    because JSON spells them `\\n` rather than leaving them at the end of a line
    for an editor or a line-ending pass to rewrite.
    """

    turn_opening: str = Field(
        min_length=1,
        description=(
            "Opens a turn, with the role substituted in. A string.Template "
            "placeholder, so `$role` or `${role}`; the substitution is strict, so a "
            "placeholder by any other name raises at the first render."
        ),
    )
    turn_closing: str = Field(
        min_length=1,
        description=(
            "Closes a turn. The second call's prompt is the first one's spliced on "
            "this marker, so an empty seam would join two turns into one and break "
            "the prefix the two-call design rests on."
        ),
    )
    reply_opening: str = Field(
        min_length=1,
        description=(
            "Where the model starts writing, with reasoning off. Not derived from "
            "turn_opening: a chat template ends a generation prompt with more than a "
            "role header, and what it ends with belongs to the model."
        ),
    )
    reply_opening_thinking: str = Field(
        min_length=1,
        description="The same, with reasoning on. Recorded from the server that applies it.",
    )
    thinking_close: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "What this model writes to close its reasoning block, and the whole of the "
            "declaration that reasoning is wanted. Not null means a call is decoded as "
            "two spans - one unconstrained span that stops here, then the "
            "schema-constrained answer on the same slot - and the prompt ends on "
            "reply_opening_thinking rather than reply_opening. Null means one "
            "schema-constrained span and no reasoning, which is where the incumbent "
            "sits. It replaced inference.thinking on 2026-09-14: a flag beside a "
            "marker is two places to disagree, and the flag alone could not have "
            "worked - the output schema binds the decode from the first token, so a "
            "think opener is not a legal token on either transport."
        ),
    )
    system_role: SystemPlacement = Field(
        default=SystemPlacement.OWN_TURN,
        description=(
            "Where this model's template takes the system text - its own turn, or "
            "folded into the first user turn. It is read by "
            "idhazh.llm.server.render_prompt, which never reads a model id: without "
            "this field a model with no system role could not be configured at all, "
            "only coded for. It has a default where the markers beside it have none, "
            "because the default is the topology of every template that HAS a system "
            "role rather than the incumbent's own string, and because case 1 of "
            "idhazh.llm.server.prove_the_entry refuses a run whose render disagrees "
            "with the server's own render of the same turns - so a placement declared "
            "wrong is caught before the first item rather than inherited in silence."
        ),
    )
    system_joiner: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "What sits between the system text and the article when the two share a "
            "turn. Required under fold_into_first_user and refused under own_turn: a "
            "field that is read on one case and ignored on the other is a field "
            "somebody will set and trust. It may not be empty, because folding with no "
            "separator runs the last instruction into the opening fence of the "
            "untrusted block on one line, and the grammar still accepts the reply."
        ),
    )
    thinking_kwarg: str | None = Field(
        default="enable_thinking",
        min_length=1,
        description=(
            "The template variable that turns this model's reasoning on and off, sent "
            "as the one key of chat_template_kwargs. It is a name belonging to "
            "somebody else's Jinja template, so it is a model fact and not a project "
            "constant - it was spelled in this project's source and sent to every "
            "model until 2026-09-14. Null means this template reads no keywords at "
            "all, and then the request carries no chat_template_kwargs and "
            "thinking_close must be null too; this block refuses the pair."
        ),
    )
    declared_for: Sha256 | None = Field(
        default=None,
        description=(
            "The weights these markers are recorded from - the sha256 of the entry "
            "that carries them. It sits here for the reason inference.declared_for "
            "sits beside the numbers: swap the weights and the block is left behind, "
            "and this is the one event the field exists to make loud. Absent means an "
            "entry nobody has measured yet, which is legal; ModelsConfig refuses a "
            "block whose digest is not the entry's."
        ),
    )

    @field_validator("turn_opening")
    @classmethod
    def _the_opening_names_the_role(cls, value: str) -> str:
        """A turn opening with no placeholder renders every turn without a role header.

        `Template.substitute` over a string that names nothing returns it
        unchanged, so the prompt is syntactically fine, the grammar still
        accepts the reply, and every turn in the conversation is anonymous.
        Nothing downstream can see it.
        """
        if TURN_ROLE not in Template(value).get_identifiers():
            raise ValueError(
                f"a turn opening must name ${TURN_ROLE}, and {value!r} names "
                f"{sorted(Template(value).get_identifiers()) or 'nothing'} - a turn with no "
                "role header renders cleanly and says nothing about who is speaking"
            )
        return value

    @model_validator(mode="after")
    def _the_joiner_belongs_to_the_fold(self) -> Self:
        """The joiner is required by one placement and read by no other.

        Both directions raise, because both failures are silent. Absent under
        the fold renders the instructions and the article as one unbroken line.
        Present under `own_turn` is a value an operator set, a reviewer read,
        and nothing ever applied.
        """
        folded = self.system_role is SystemPlacement.FOLD_INTO_FIRST_USER
        if folded and self.system_joiner is None:
            raise ValueError(
                f"turns.system_joiner is required under system_role="
                f"'{SystemPlacement.FOLD_INTO_FIRST_USER.value}' and is absent - "
                "folding the system text into the first user turn with no declared "
                "separator runs the last instruction into the opening fence of the "
                "untrusted block, and the grammar still accepts the reply"
            )
        if not folded and self.system_joiner is not None:
            raise ValueError(
                f"turns.system_joiner is {self.system_joiner!r} under system_role="
                f"'{SystemPlacement.OWN_TURN.value}', where the system text has a turn "
                "of its own and nothing joins it to anything - remove the joiner, or "
                f"declare system_role='{SystemPlacement.FOLD_INTO_FIRST_USER.value}'"
            )
        return self

    @model_validator(mode="after")
    def _a_template_that_reads_no_keyword_cannot_be_asked_to_think(self) -> Self:
        """Reasoning is asked for through a template keyword, so a null name refuses it.

        Both halves are facts about somebody else's template, so this block owns
        the pair. A null keyword with a closing marker declared is a claim
        nothing can satisfy on the chat route: the request carries no
        `chat_template_kwargs` at all, the template renders its own default, and
        the only symptom is whatever that default happens to be.
        """
        if self.thinking_kwarg is None and self.thinking_close is not None:
            raise ValueError(
                f"turns.thinking_kwarg is null, so a chat request sends no "
                f"chat_template_kwargs at all, and turns.thinking_close is "
                f"{self.thinking_close!r}, which asks this template to turn reasoning "
                "on through a keyword nothing sends. Name the keyword this model's "
                "template reads, or set turns.thinking_close null"
            )
        return self

    @property
    def thinks(self) -> bool:
        """Whether a call on these weights is decoded as two spans.

        One question with one answer, read off the marker that makes the second
        span possible. There is no flag beside it: a flag and a marker are two
        places to disagree, and the disagreement renders a prompt the grammar
        still accepts.
        """
        return self.thinking_close is not None
