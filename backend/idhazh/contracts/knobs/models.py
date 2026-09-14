"""Which weights run, and everything a run needs to talk to them."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, CommitSha, Contract, Model, Sha256, Slug
from idhazh.contracts.knobs.inference import InferenceConfig
from idhazh.contracts.knobs.removed import refuse_a_removed_knob
from idhazh.contracts.knobs.turns import TurnsConfig


class ModelRef(Model):
    """Which weights, from where. Per-item payloads carry only the `id`.

    **This is the shape a run recorded**, and `run_manifest.ModelUse` embeds it.
    `ModelEntry` below is the shape a person declares in `config/`. The turn
    envelope belongs to the second and not to this one: no `model_ref` a run has
    ever written carries markers, and a field required here would stop today's
    build reading yesterday's run (`CLAUDE.md` section 11).
    """

    id: Slug
    repo: str = Field(min_length=1, description="Hugging Face repository the GGUF is pulled from.")
    revision: CommitSha | None = Field(
        default=None,
        description=(
            "The hub commit the weights are fetched at. A download that names a branch "
            "gets whatever was uploaded last, so the bytes can change under a config "
            "that still records the old sha256."
        ),
    )
    file: str = Field(min_length=1)
    quantisation: str = Field(min_length=1)
    sha256: Sha256 | None = Field(
        default=None,
        description="Recorded once measured. A weight that changes silently changes every output.",
    )
    hf_base_repo: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "The safetensors repository a fine-tune trains against, when this entry "
            "names a GGUF conversion of somebody else's weights. It sits here rather "
            "than in `finetune` because the two strings describe the same model: held "
            "apart, a model swap moves one and leaves the other, and a LoRA adapter "
            "loads onto a mismatched base without raising. Optional - only an entry we "
            "intend to fine-tune needs it."
        ),
    )
    inference: InferenceConfig = Field(
        default_factory=InferenceConfig,
        description=(
            "The runtime this entry's weights are served on. It sits on the entry for "
            "the same reason `hf_base_repo` does: held apart, a model swap moves the "
            "weights and leaves the numbers, and llama-server starts on them without "
            "raising. `ModelsConfig` refuses a block whose declared_for is not this "
            "entry's sha256, so a default block under measured weights is refused "
            "rather than inherited."
        ),
    )


class ModelEntry(ModelRef):
    """Which weights, and everything a run needs to talk to them.

    **This is the shape a person declares**, and `ModelsConfig` is made of it.
    It is `ModelRef` plus the turn envelope, which is required here and absent
    from the recorded shape - so a config entry that forgets its markers fails
    at load, and a `run.json` written before the markers were declared still
    reads. A swap that moved the markers is still visible in a run record:
    `RunRecord.inputs.prompt_sha256` digests both turns rendered through them.

    Do not move `turns` down onto `ModelRef` as a tidy-up. That is the change
    this split exists to prevent. `arch` is here for the same reason and not
    for a different one.
    """

    arch: str = Field(
        min_length=1,
        description=(
            "The architecture name inside the GGUF - its `general.architecture` key, "
            "which reads `qwen35` for the weights this entry names. Required and with "
            "no default, for the reason `turns` is: an entry that inherits the "
            "incumbent's architecture claims something nobody checked. "
            "`idhazh.llm.server.prove_the_entry` reads the key back out of the file "
            "the server was pointed at and refuses the run before the first item when "
            "the two disagree, which is what makes this a fact rather than a claim. It "
            "catches a repackaged GGUF under a familiar name - the one case where the "
            "digest, the alias and the filename all agree and only the words get worse."
        ),
    )
    turns: TurnsConfig = Field(
        description=(
            "The turn envelope these weights are rendered with. Required and with no "
            "default: an entry that forgets its markers must fail rather than inherit "
            "the incumbent's, because inheriting them renders a prompt the grammar "
            "still accepts and nothing else can see is wrong."
        ),
    )

    @model_validator(mode="after")
    def _a_template_that_reads_no_keyword_cannot_be_asked_to_think(self) -> Self:
        """Reasoning is asked for through a template keyword, so a null name refuses it.

        The two halves sit in different blocks - the keyword is a fact about
        somebody else's template and the switch is a decoding choice - so
        neither block can see the pair and the entry has to. A null keyword with
        reasoning on is a claim nothing can satisfy: the request carries no
        `chat_template_kwargs` at all, the template renders its own default, and
        the only symptom is whatever that default happens to be.
        """
        if self.turns.thinking_kwarg is None and self.inference.thinking:
            raise ValueError(
                f"models entry {self.id} sets turns.thinking_kwarg null, so the request "
                "sends no chat_template_kwargs at all, and inference.thinking true, "
                "which asks this template to turn reasoning on through a keyword "
                "nothing sends. Name the keyword this model's template reads, or set "
                "inference.thinking false"
            )
        return self


#: The `models` keys this block used to carry. `inference` held a single
#: settings block that both roles were served on, so a swap of either entry
#: inherited numbers measured against the other. There is no lift onto the
#: entries, because the lift IS the inheritance: it would hand a swapped entry
#: the previous weights' numbers and raise nothing. `visual_planner` and its
#: older spelling `route` named the small model plan 11 row #6 retired; the two
#: calls on `summarize` replaced it, so nothing answers for them.
SUPERSEDED_MODELS_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {"inference": "<role>.inference", "route": "", "visual_planner": ""}
)


#: Where the active model's whole entry lives, relative to `config/`. Pinned to
#: one directory and to `.json` by the schema rather than checked in the loader:
#: the value is an operator's edit that becomes a path this build opens, so the
#: grammar is what rules out a traversal, an absolute path and a Windows
#: separator (CLAUDE.md section 2).
MODELS_FILE_PATTERN: Final = r"^models/[a-z0-9]+(?:[.-][a-z0-9]+)*\.json$"


ModelsFile = Annotated[str, StringConstraints(pattern=MODELS_FILE_PATTERN)]


#: What an operator does next when one of an entry's two declared blocks names
#: weights the entry does not. The check is the same for both; only the repair
#: differs, so each block carries its own clause rather than a second copy of
#: the rule.
_REDERIVE_THE_NUMBERS: Final = (
    "Every setting in that block was measured against one model on one runner, "
    "so re-derive them for these weights"
)


_RERECORD_THE_MARKERS: Final = (
    "Every marker in that block was recorded off the server that renders these "
    "turns, so re-record them for these weights"
)


class ModelsConfig(Contract):
    """`config/models/<name>.json` - one whole model, in one file of its own.

    One entry per role, and each entry carries the settings it runs on. There is
    no block shared between the entries. A role is a model family served by its
    own llama-server process, and one block over two roles is a measurement
    about one of them quietly applied to the other.

    One role is left. Plan 11 row #6 retired the small visual planner: the two
    calls the work stage now makes per item run on these weights, so the picture
    is decided by the same model that wrote the summary.

    It is a file rather than a block of `config/idhazh.json` because everything
    in it is a fact about one set of weights - the repository, the digest, the
    window they were measured in, the markers their server renders. Held in the
    shared file, a swap is an edit across every one of those lines and a revert
    is the same edit backwards, with the previous model's numbers gone. Held
    here, the incumbent and the candidate are two committed files and the swap
    is `models_file` in `config/idhazh.json`.
    """

    __schema_stem__: ClassVar[str] = "models-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-14T03:00",
            change=(
                "models.<role>.turns gains system_role, system_joiner and "
                "thinking_kwarg. system_role is a closed choice of own_turn and "
                "fold_into_first_user; system_joiner is required under the fold and "
                "refused under own_turn; thinking_kwarg names the template variable "
                "chat_template_kwargs carries and defaults to the incumbent's "
                "enable_thinking, with null meaning the request sends no template "
                "keywords at all and inference.thinking must then be false. All three "
                "sit on TurnsConfig, which ModelEntry carries and ModelRef does not, so "
                "a run.json written before today still reads."
            ),
            why=(
                "Plan 28 row #11. Where the system text goes and which keyword turns "
                "reasoning off are facts about somebody else's chat template, and both "
                "were spelled in this project's source and sent to every model - so a "
                "model with no system role could not be configured at all, only coded "
                "for. The prompt TEXT does not follow them onto the entry and cannot: "
                "prose_changed_alone reports nothing whenever model_sha256 moved, so "
                "per-model wording would hide every prompt edit that rode in on a swap. "
                "Ruled by Andre, 2026-09-14."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T02:00",
            change=(
                "models.<role>.arch, required: the architecture name inside the GGUF. "
                "It sits on ModelEntry, not on ModelRef, so a run.json written before "
                "today still reads - run_manifest.ModelUse embeds ModelRef, and a "
                "required field there would stop this build reading yesterday's run "
                "(CLAUDE.md section 11)."
            ),
            why=(
                "Plan 28 row #5. Row #2 moved the turn envelope onto the entry, so the "
                "entry now claims how a turn opens and closes and nothing checked the "
                "claim against the running server. The start-up probe checks all five "
                "claims before the first item, and this is the field the fourth of them "
                "compares: the weights on disk declare an architecture, and an entry "
                "that names a different one is serving a repackaged file under a "
                "familiar name. Ruled by Carmack, 2026-09-14."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14",
            change=(
                "Initial shape, lifted whole out of app-config.models with no field "
                "renamed, retyped or given a different default. It is the same "
                "ModelsConfig, now a document of its own under config/models/, and it "
                "carries a version date-stamp because a persisted document does. "
                "app-config.models is gone in the same commit and app-config.models_file "
                "names which of these files is active."
            ),
            why=(
                "Plan 28 row #6. Swapping the summarizer has to cost no source edit, and "
                "it used to cost eleven lines edited in place in the one file every "
                "other knob lives in - so a revert had to reconstruct the previous "
                "model's measured numbers from git rather than read them off disk. One "
                "file per model makes both directions a pointer, and puts the numbers "
                "that were measured for a set of weights in the same file that names "
                "them. Ruled by Fowler, 2026-09-14."
            ),
        ),
    )

    summarize: ModelEntry

    @classmethod
    def roles(cls) -> tuple[str, ...]:
        """The roles this document declares, in name order.

        Not `model_fields`. A persisted document carries a `version` stamp of
        its own, so the field list stopped being the role list on the day this
        shape became a file - and a caller that read it as one would offer
        `version` as a model an operator could name.
        """
        return tuple(
            sorted(
                name
                for name, field in cls.model_fields.items()
                if field.annotation is ModelEntry
            )
        )

    @model_validator(mode="before")
    @classmethod
    def _a_removed_key_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("models", data, SUPERSEDED_MODELS_NAMES)

    @model_validator(mode="after")
    def _every_block_names_the_weights_it_is_declared_for(self) -> Self:
        """A settings block belongs to one entry's bytes, and says which.

        The swap this refuses is five strings edited in place: repo, file,
        revision, digest and id, with the blocks underneath them untouched. That
        raises nothing on its own, and the run then stands a server up on numbers
        derived for weights it never opened.

        **Two blocks, one rule, one loop.** `inference` and `turns` are both
        measurements about one model, so the check is the same for both and only
        the repair differs - re-derive the numbers, or re-record the markers off
        the server that applies them.

        Both digests absent is legal and means an entry nobody has measured yet.
        The stamp already refuses to run on one: `idhazh.fingerprint.build_inputs`
        stops when the weights have no recorded digest.
        """
        for role in type(self).roles():
            entry: ModelEntry = getattr(self, role)
            for block, declared, repair in (
                ("inference", entry.inference.declared_for, _REDERIVE_THE_NUMBERS),
                ("turns", entry.turns.declared_for, _RERECORD_THE_MARKERS),
            ):
                if declared == entry.sha256:
                    continue
                raise ValueError(
                    f"models.{role}.{block} is declared for "
                    f"{declared or 'no weights at all'}, and models.{role} names "
                    f"{entry.sha256 or 'no weights at all'}. {repair} and set "
                    f"models.{role}.{block}.declared_for to the digest the entry "
                    "carries - or put the entry back"
                )
        return self
