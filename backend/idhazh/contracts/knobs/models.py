"""Which weights run, and everything a run needs to talk to them."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    Model,
    Sha256,
    Slug,
    without_retired_keys,
)
from idhazh.contracts.knobs.inference import SUPERSEDED_INFERENCE_NAMES, InferenceConfig
from idhazh.contracts.knobs.removed import refuse_a_removed_knob


class ModelRef(Model):
    """Which weights, from where. Per-item payloads carry only the `id`.

    **This is the shape a run recorded**, and `run_manifest.ModelUse` embeds it.
    `ModelEntry` below is the shape a person declares in `config/`. What a
    reasoning span is closed with belongs to the second and not to this one: no
    `model_ref` a run has ever written carries it, and a field required here
    would stop today's build reading yesterday's run (`CLAUDE.md` section 11).
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

    @model_validator(mode="before")
    @classmethod
    def _a_run_written_under_a_retired_entry_key_still_reads(cls, data: Any) -> Any:
        """The read-side migration a run record is owed (`CLAUDE.md` section 11).

        Six committed `run.json` files name a draft head, and `extra="forbid"`
        would refuse every one of them the day the field went. Dropped rather
        than renamed: nothing replaces it, so there is no number to carry.

        It is silent here and loud on `ModelEntry`, which is the same split
        `InferenceConfig` draws - there a payload an earlier run wrote, here a
        block a person typed, and accepting the second in silence teaches a knob
        that nothing reads.
        """
        return without_retired_keys(data, *RETIRED_ENTRY_NAMES)


#: The entry keys a `run.json` written before 2026-09-21 carries and nothing
#: carries now. A draft head is not a decoding knob priced on cost alone: two
#: paired dispatches on 2026-09-12 changed the summary on nine articles of nine
#: with the head on, so it was never the output-identical speed-up its publisher
#: claims. The turn block was a hand-transcribed copy of the model's own chat
#: template, and the server now reads those markers off the template itself.
#: Nothing replaces either.
RETIRED_ENTRY_NAMES: Final[Mapping[str, str]] = MappingProxyType({"draft": "", "turns": ""})


class ModelEntry(ModelRef):
    """Which weights, and everything a run needs to talk to them.

    **This is the shape a person declares**, and `ModelsConfig` is made of it.
    It is `ModelRef` plus the two facts about this model's reasoning that the
    model's own chat template cannot hand back - so a config entry that gets one
    wrong fails here, and a `run.json` written before either existed still
    reads.

    The markers that open and close a turn are not here. They are read off the
    template itself at server start (`idhazh.llm.server.derive_turn_markers`),
    because a field restating somebody else's file is a copy a model swap can
    leave behind.
    """

    arch: str = Field(
        min_length=1,
        description=(
            "The architecture name inside the GGUF - its `general.architecture` key, "
            "which reads `qwen35` for the weights this entry names. Required and with "
            "no default: an entry that inherits the incumbent's architecture claims "
            "something nobody checked. It is what a person reads when they want to know "
            "which family a committed entry belongs to, and it names the family in a "
            "refusal when a rule cannot read this model's template."
        ),
    )
    thinking_close: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "What this model writes to close its reasoning block, and the whole of the "
            "declaration that reasoning is wanted. Not null means a call is decoded as "
            "two spans - one unconstrained span that stops here, then the "
            "schema-constrained answer on the same slot. Null means one "
            "schema-constrained span and no reasoning, which is where the incumbent "
            "sits. It is declared rather than derived because a generation prompt never "
            "contains it: it is what the model writes, not what the template writes. A "
            "wrong one means the span never stops and the item lands model_timed_out, "
            "loudly and one item at a time."
        ),
    )
    thinking_kwarg: str | None = Field(
        default="enable_thinking",
        min_length=1,
        description=(
            "The template variable that turns this model's reasoning on and off, sent "
            "as the one key of chat_template_kwargs. It is declared rather than derived "
            "because a rendering cannot return the name of a variable nobody sent it. "
            "Null means this template reads no keywords at all, and then the request "
            "carries no chat_template_kwargs and thinking_close must be null too; this "
            "entry refuses the pair."
        ),
    )

    @property
    def thinks(self) -> bool:
        """Whether a call on these weights is decoded as two spans.

        One question with one answer, read off the marker that makes the second
        span possible. There is no flag beside it: a flag and a marker are two
        places to disagree, and the disagreement renders a prompt the grammar
        still accepts.
        """
        return self.thinking_close is not None

    @model_validator(mode="after")
    def _a_template_that_reads_no_keyword_cannot_be_asked_to_think(self) -> Self:
        """Reasoning is asked for through a template keyword, so a null name refuses it.

        Both halves are facts about somebody else's template, so this entry owns
        the pair. A null keyword with a closing marker declared is a claim
        nothing can satisfy: the request carries no `chat_template_kwargs` at
        all, the template renders its own default, and the only symptom is
        whatever that default happens to be.
        """
        if self.thinking_kwarg is None and self.thinking_close is not None:
            raise ValueError(
                f"thinking_kwarg is null, so a request sends no chat_template_kwargs at "
                f"all, and thinking_close is {self.thinking_close!r}, which asks this "
                "template to turn reasoning on through a keyword nothing sends. Name "
                "the keyword this model's template reads, or set thinking_close null"
            )
        return self

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
            refuse_a_removed_knob("models.<role>", data, RETIRED_ENTRY_NAMES)
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


#: What an operator does next when an entry's declared block names weights the
#: entry does not.
_REDERIVE_THE_NUMBERS: Final = (
    "Every setting in that block was measured against one model on one runner, "
    "so re-derive them for these weights"
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
    window they were measured in. Held in the shared file, a swap is an edit
    across every one of those lines and a revert is the same edit backwards,
    with the previous model's numbers gone. Held here, the incumbent and the
    candidate are two committed files and the swap is `models_file` in
    `config/idhazh.json`.
    """

    __schema_stem__: ClassVar[str] = "models-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-21T04:00",
            change="The turn block goes; two keys move onto the entry and a run still reads.",
            why="The markers are the model's own template, so the server reads them off it.",
        ),
        ChangelogEntry(
            version="2026-09-21T03:00",
            change="Both inference decode caps go; a run that pinned one still reads.",
            why="Each sent a number where the runtime's own default is already unbounded.",
        ),
        ChangelogEntry(
            version="2026-09-21T02:00",
            change="The draft head goes from the entry; a run that named one still reads.",
            why="It changed the summary on nine articles of nine, so it never was a free speed-up.",
        ),
        ChangelogEntry(
            version="2026-09-21",
            change="Add an optional judge entry, decoding on the served role's weights.",
            why="The judge could only open a thinking channel by moving the summariser too.",
        ),
        ChangelogEntry(
            version="2026-09-14",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    summarize: ModelEntry
    #: How the content-similarity judge decodes, when it is not the summariser's
    #: own entry. Null in every committed file and null is the default, so a
    #: fresh clone judges exactly as it judges today. It exists because the one
    #: thing the judge wants - a reasoning span in front of its verdict - lives
    #: in an entry that also moves the summariser's answer budget, its cache
    #: types and its batch size, and moving those for a judge's benefit is an
    #: uninstrumented change to the words a reader gets. It is filled when a
    #: replay says a reasoned verdict is a better verdict; until then it stays
    #: null and the channel stays shut
    #: (`docs/reference/benchmarks/what-the-margin-rule-changes.md`).
    judge: ModelEntry | None = None

    @classmethod
    def roles(cls) -> tuple[str, ...]:
        """The roles this document declares, in name order.

        Not `model_fields`. A persisted document carries a `version` stamp of
        its own, so the field list stopped being the role list on the day this
        shape became a file - and a caller that read it as one would offer
        `version` as a model an operator could name.

        **A role here is a model a server is stood up for**, which is why the
        optional judge entry is not one: it re-decodes on the weights the served
        role already holds, so it is fetched by nobody and started by nobody.
        `entries` below is what a caller wants when the question is every entry
        that was declared.
        """
        return tuple(
            sorted(
                name
                for name, field in cls.model_fields.items()
                if field.annotation is ModelEntry
            )
        )

    def entries(self) -> tuple[tuple[str, ModelEntry], ...]:
        """Every entry this document actually declares, named, in name order.

        `roles` is the list of models a server is stood up for; this is the list
        of entries somebody wrote down. An optional entry left out is absent here
        rather than present and null, so a caller loops over what exists instead
        of testing each one.
        """
        declared = ((name, getattr(self, name)) for name in sorted(type(self).model_fields))
        return tuple(
            (name, entry) for name, entry in declared if isinstance(entry, ModelEntry)
        )

    @model_validator(mode="before")
    @classmethod
    def _a_removed_key_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("models", data, SUPERSEDED_MODELS_NAMES)

    @model_validator(mode="after")
    def _a_second_entry_decodes_on_the_weights_the_server_holds(self) -> Self:
        """An entry nobody stands a server up for has to name the running weights.

        One llama-server, one file. An entry naming a second set of weights would
        either double what the runner's cache carries - the largest fixed cost in
        the pipeline (Guardrail #2) - or, worse, decode against whatever the
        running server happens to hold while the row records the id it asked for.
        Nothing raises in that case and every verdict is attributed to a model
        that never saw the pair.

        What a second entry is free to move is the decode: its temperature, its
        budgets, and whether it opens a reasoning channel.
        """
        for role, entry in self.entries():
            if role in type(self).roles() or entry.sha256 == self.summarize.sha256:
                continue
            raise ValueError(
                f"models.{role} names weights {entry.sha256 or 'nothing at all'} and "
                f"models.summarize names {self.summarize.sha256 or 'nothing at all'}. "
                f"No server is started for models.{role}, so it decodes on the weights "
                "the summariser's server holds - name those, or make it a role of its own"
            )
        return self

    @model_validator(mode="after")
    def _every_block_names_the_weights_it_is_declared_for(self) -> Self:
        """A settings block belongs to one entry's bytes, and says which.

        The swap this refuses is five strings edited in place: repo, file,
        revision, digest and id, with the block underneath them untouched. That
        raises nothing on its own, and the run then stands a server up on numbers
        derived for weights it never opened.

        Both digests absent is legal and means an entry nobody has measured yet.
        The stamp already refuses to run on one: `idhazh.fingerprint.build_inputs`
        stops when the weights have no recorded digest.
        """
        for role, entry in self.entries():
            declared = entry.inference.declared_for
            if declared == entry.sha256:
                continue
            raise ValueError(
                f"models.{role}.inference is declared for "
                f"{declared or 'no weights at all'}, and models.{role} names "
                f"{entry.sha256 or 'no weights at all'}. {_REDERIVE_THE_NUMBERS} and set "
                f"models.{role}.inference.declared_for to the digest the entry "
                "carries - or put the entry back"
            )
        return self
