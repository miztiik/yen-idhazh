"""Which weights run, and everything a run needs to talk to them."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, CommitSha, Contract, Model, Sha256, Slug
from idhazh.contracts.knobs.inference import SUPERSEDED_INFERENCE_NAMES, InferenceConfig
from idhazh.contracts.knobs.removed import refuse_a_removed_knob
from idhazh.contracts.knobs.turns import TurnsConfig


class SpeculationType(StrEnum):
    """Which kind of speculation the runtime is told to use.

    Only the three this project can actually stand up. Build b10598 accepts
    eleven - the full list is `none`, `draft-simple`, `draft-eagle3`,
    `draft-mtp`, `draft-dflash`, `draft-dspark` and five `ngram-*` variants,
    read off `llama-server --help` by `.github/workflows/probe.yml` on
    2026-09-15. The ones left out either need a purpose-built draft head
    nobody has published for our weights, or a lookup cache nothing here
    writes. A closed choice is what stops an operator naming one of them and
    getting a server that starts and drafts nothing.

    `draft-mtp` is here because the head now exists: Unsloth publishes a
    multi-token-prediction head for the Gemma entry, and the publisher's guide
    names this exact value. Naming `draft-simple` for that head instead is not
    a slow server, it is a dead one - every request failed on
    `decode() failed: failed to process speculative batch`, five of five, on
    run 34941400155.
    """

    DRAFT_SIMPLE = "draft-simple"
    DRAFT_MTP = "draft-mtp"
    NGRAM_SIMPLE = "ngram-simple"


class DraftConfig(Model):
    """A second, much smaller set of weights that guesses ahead of the first.

    **Speculative decoding is output-identical by construction, and this
    configuration is not doing that.** The target is supposed to verify every
    drafted token and reject any it would not have produced, so the text is the
    text the target would have written alone. The publisher of these weights
    makes exactly that claim for this head and this flag. Two paired dispatches
    refused it on nine of nine articles: every summary changed when the head was
    on. Whether the cause is the head, the acceptance rule or the pinned
    llama.cpp build is unmeasured -
    `docs/reference/benchmarks/what-the-draft-head-is-worth.md` holds the
    readings and what is still open.

    **So this block is not a decoding knob priced on cost alone.** Until a
    configuration is shown to be output-identical, turning the head on or off is
    a model change and the configuration that was qualified is the one that has
    to publish.

    What it can also do is waste time. A draft the target keeps rejecting costs a
    forward pass per rejected token and returns nothing, so the acceptance rate
    is the number that says whether it paid. `llama-server` publishes it:
    `llamacpp:spec_decode_num_accepted_tokens_total` over
    `llamacpp:spec_decode_num_draft_tokens_total`, both already in the
    `/metrics` body a shard reads at job end.
    """

    repo: str = Field(min_length=1, description="Hugging Face repository the draft GGUF is in.")
    revision: CommitSha = Field(
        description="The hub commit. Required here and optional on ModelRef: a block "
        "somebody added by hand is a block that can pin properly from the start."
    )
    file: str = Field(min_length=1)
    sha256: Sha256 = Field(description="Refused before the server starts, like the target's.")
    byte_count: int | None = Field(default=None, ge=1)
    spec_type: SpeculationType = Field(default=SpeculationType.DRAFT_SIMPLE)
    n_max: int = Field(
        default=3,
        ge=1,
        le=64,
        description=(
            "How many tokens are drafted before the target verifies. The runtime's own "
            "default. Higher drafts further ahead and wastes more when the draft is "
            "wrong, so it is a bet on how predictable the text is."
        ),
    )
    n_min: int = Field(default=0, ge=0, le=64)
    p_min: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Below this probability the draft stops guessing and lets the target "
            "decode. 0.0 is the runtime default and means never stop early."
        ),
    )

    @model_validator(mode="after")
    def _a_minimum_above_the_maximum_drafts_nothing(self) -> Self:
        if self.n_min > self.n_max:
            raise ValueError(
                f"draft.n_min is {self.n_min} and draft.n_max is {self.n_max}. A minimum "
                "above the maximum asks the runtime for a draft length that cannot "
                "exist, and it starts anyway and drafts nothing"
            )
        return self


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
    byte_count: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many bytes those weights are, as the hub reports them. Optional: an "
            "entry nobody has fetched yet declares none, and the run then records the "
            "size it opened on both sides rather than comparing a number to itself. It "
            "sits beside sha256 because it is the same kind of fact and has the same "
            "source, and because a qualification that had to be told it on the command "
            "line was a fact about these weights living somewhere other than the file "
            "that names them."
        ),
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
    draft: DraftConfig | None = Field(
        default=None,
        description=(
            "A second, smaller set of weights that drafts tokens this entry's model "
            "then verifies. Null is the default and means one model and no "
            "speculation. It sits beside `inference` rather than inside it because it "
            "names weights of its own - a repository, a commit, a filename and a "
            "digest - and a block that fetches a file is not a decoding knob. On "
            "`ModelRef` rather than `ModelEntry` so a run record says whether the day "
            "was drafted; a run that cannot answer that cannot explain its own "
            "throughput."
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

    @model_validator(mode="before")
    @classmethod
    def _a_removed_settings_knob_is_refused_by_name(cls, data: Any) -> Any:
        """A config file is refused by name; a run record is migrated in silence.

        The split is this class against `ModelRef`. Here a person wrote the
        block, and silent acceptance teaches the wrong spelling - so the removed
        name is refused and the message says where the knob went. There the
        block is a payload an earlier run wrote, and refusing it would stop
        today's build reading yesterday's run.
        """
        if isinstance(data, dict):
            refuse_a_removed_knob(
                "models.<role>.inference", data.get("inference"), SUPERSEDED_INFERENCE_NAMES
            )
        return data


#: The `models` keys this block used to carry. `inference` held a single
#: settings block that both roles were served on, so a swap of either entry
#: inherited numbers measured against the other. There is no lift onto the
#: entries, because the lift IS the inheritance: it would hand a swapped entry
#: the previous weights' numbers and raise nothing. `visual_planner` and its
#: older spelling `route` named the retired small model; the two calls on
#: `summarize` replaced it, so nothing answers for them.
SUPERSEDED_MODELS_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {"inference": "models.<role>.inference", "route": "", "visual_planner": ""}
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

    One role is left. The small visual planner is retired: the two calls the
    work stage now makes per item run on these weights, so the picture is
    decided by the same model that wrote the summary.

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
            version="2026-09-20",
            change="Add optional CPU, cache, checkpoint and template controls.",
            why="Each model can declare the runtime settings it needs.",
        ),
        ChangelogEntry(
            version="2026-09-17T02:00",
            change="inference.seed is the sampling control rather than dead code.",
            why="Every entry pins temperature 0.2, where the seed decides which token is drawn.",
        ),
        ChangelogEntry(
            version="2026-09-17",
            change="inference.max_think_tokens accepts null, and null is the default.",
            why="A cap set from no reading of these weights truncates a thought mid-sentence.",
        ),
        ChangelogEntry(
            version="2026-09-15T12:30",
            change="models.<role>.draft.spec_type accepts a third value, draft-mtp.",
            why="A model that predicts its own next tokens needs no second set of weights.",
        ),
        ChangelogEntry(
            version="2026-09-14",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
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
