"""Which weights run, and everything a run needs to talk to them."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    Model,
    Sha256,
    Slug,
)
from idhazh.contracts.knobs.removed import refuse_a_removed_knob


class CompanionFile(Model):
    """One more file these weights need, and the flag that hands it to the server.

    A model is not always one file. Google ships a multi-token-prediction head
    beside the gemma weights; another family ships a projector, an adapter or a
    vocoder. Each is the same fact - bytes from a hub repository, verified, then
    named on the command line - so each is an entry here rather than a typed
    block of its own with its own five fields and its own argv branch.

    `flag` is what makes this a declaration rather than a download list. The
    builder emits `<flag> <landed path>` and knows nothing about what the file
    is for, so a projector or an adapter is a config-only change. A companion
    with no flag is a file that must simply be present.
    """

    repo: str = Field(min_length=1, description="Hugging Face repository the file is pulled from.")
    revision: CommitSha = Field(
        description=(
            "The hub commit the file is fetched at. Never a branch: a branch gets "
            "whatever was uploaded last, under a digest that still reads the old bytes."
        )
    )
    file: str = Field(
        min_length=1,
        description=(
            "The file name inside the repository, and one path segment. It becomes a "
            "path under the models directory and a shell argument beside it."
        ),
    )
    sha256: Sha256 = Field(
        description=(
            "Required, with no exception. A blank digest makes `sha256sum --check` "
            "report 'no properly formatted checksum lines found', which names neither "
            "the entry nor the field."
        )
    )
    byte_count: int | None = Field(
        default=None,
        ge=1,
        description="How many bytes the hub reports. Absent where nobody has fetched it yet.",
    )
    flag: str | None = Field(
        default=None,
        pattern=r"^--[a-z0-9-]+$",
        description=(
            "The llama-server flag that takes this file's landed path. Absent means "
            "the file must be present and is named by nothing on the command line."
        ),
    )

    @model_validator(mode="after")
    def _the_file_name_stays_inside_the_models_directory(self) -> CompanionFile:
        """The name is joined to a directory, so the grammar is the only guard.

        Guardrail #11: this value reaches a filesystem path and a shell argument.
        """
        name = self.file
        if name.split() != [name]:
            raise ValueError(f"companion file name is empty or not one word: {name!r}")
        if "/" in name or "\\" in name or name.startswith("."):
            raise ValueError(f"companion file name is not one path segment: {name!r}")
        return self


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
    inference: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "What a run recorded under the one settings block, before llama-server's "
            "own flags and the request values were split into the two blocks beside "
            "this one. A plain mapping and nothing writes it: a record written under "
            "the typed shape carries keys this build no longer names, and a typed "
            "field would refuse every one of them."
        ),
    )
    server: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "llama-server's own flags, spelled exactly as the binary spells them - "
            "`--ctx-size`, `-fa`, `--no-warmup`. A null value is a bare flag with no "
            "argument. Emitted verbatim, so naming one more option is a key here and "
            "no edit anywhere else, and a flag this build does not accept is refused "
            "by llama-server at start-up with the flag named."
        ),
    )
    request: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "What goes in a request body rather than on the command line, under this "
            "project's own names. A sampling value cannot reach the command line "
            "because the builder reads only the block above."
        ),
    )
    companion_files: tuple[CompanionFile, ...] = Field(
        default=(),
        description=(
            "Every extra file these weights need beside the GGUF the entry names. The "
            "weights themselves stay in the fields above, because moving them here "
            "would move `declared_for`, the health check and `--model` for no gain."
        ),
    )
    draft: Mapping[str, Any] | None = Field(
        default=None,
        description=(
            "What a run recorded when the draft head was a typed block of its own. A "
            "plain mapping and nothing writes it: six committed run records carry it, "
            "the reader forbids an extra key, and the head is now a companion file "
            "with its decode settings in the server block."
        ),
    )


class ModelEntry(ModelRef):
    """Which weights, and everything a run needs to talk to them.

    **This is the shape a person declares**, and `ModelsConfig` is made of it.
    It is `ModelRef` plus the two facts about this model's reasoning that the
    model's own chat template cannot hand back, and the digest those facts and
    the settings were derived against - so a config entry that gets one wrong
    fails here, and a `run.json` written before any of them existed still reads.

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
    declared_for: Sha256 | None = Field(
        default=None,
        description=(
            "The weights this entry's settings and markers were derived against - the "
            "sha256 the entry itself carries. Every number and every marker below is a "
            "measurement about one model on one runner, so the entry states which bytes "
            "they were put in front of. Change the weights strings in place and this is "
            "left behind holding the old digest, which is the one event the field "
            "exists to make loud. Absent means an entry nobody has measured yet."
        ),
    )
    sampling: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "What decides which token is drawn, spelled exactly as the request body "
            "spells it - `temperature`, `top_k`, `min_p`, `repeat_penalty`. Sent whole "
            "and never translated, so naming one more sampler is a key here and no "
            "edit anywhere else, and a key this runtime does not accept is refused at "
            "request time with the key named. A sampling value cannot reach the "
            "command line because the argv builder reads only the block above."
        ),
    )
    request_timeout_minutes: float = Field(
        gt=0.0,
        description=(
            "How long one POST may wait for an answer. Required, because llama-server "
            "has no default that bounds it and this project multiplies it by sixty. It "
            "sits beside the sampling block rather than inside it: it is how long the "
            "client waits, so it never goes on the wire, and a key in the block that "
            "is splatted into a request body would be sent to the server."
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

        An empty settings mapping is what this shape serialises to, because it
        inherits the recorded blocks from `ModelRef`. Refusing those would make
        a config file fail to reload the bytes it just wrote, so a superseded
        name is refused only when it carries a value.
        """
        if isinstance(data, dict):
            typed = {
                key: value
                for key, value in data.items()
                if key not in SUPERSEDED_ENTRY_NAMES or value
            }
            refuse_a_removed_knob("models.<role>", typed, SUPERSEDED_ENTRY_NAMES)
        return data


#: The entry keys a person may no longer write, and where each one went. Each is
#: refused by name rather than by "extra inputs are not permitted", which tells
#: an operator nothing about where their number went.
#:
#: `inference` held one typed block that both named llama-server's flags under
#: this project's own spellings and carried the request values. The file now
#: spells the flags as the binary spells them, so nineteen keys that existed to
#: be translated have no translation left to do.
#:
#: `turns` was a hand-transcribed copy of the model's own chat template. The
#: server reads those markers off the template it renders through, so there is
#: nothing left for a person to write down and nothing to point them at.
#:
#: `request` named the envelope rather than the setting, and held the client's
#: own timeout beside three values that go on the wire. The wire values are the
#: `sampling` block and the timeout is a field of its own.
#:
#: **This map refuses a config file and never a run record.** `ModelRef` is the
#: shape an earlier run wrote and it still reads `inference` and `request` as
#: plain mappings.
SUPERSEDED_ENTRY_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "inference": "models.<role>.server and models.<role>.sampling",
        "request": "models.<role>.sampling and models.<role>.request_timeout_minutes",
        "draft": "models.<role>.companion_files and models.<role>.server",
        "turns": "",
    }
)


#: The `models` keys this block used to carry. `inference` held a single
#: settings block that both roles were served on, so a swap of either entry
#: inherited numbers measured against the other. There is no lift onto the
#: entries, because the lift IS the inheritance: it would hand a swapped entry
#: the previous weights' numbers and raise nothing. `visual_planner` and its
#: older spelling `route` named the retired small model; the two calls on the
#: summarizer replaced it, so nothing answers for them. `summarize` named the
#: slot after the job rather than after what fills it, and a slot holds a model
#: (`CLAUDE.md` section 1a).
SUPERSEDED_MODELS_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "inference": "models.<role>.server",
        "summarize": "models.summarizer",
        "route": "",
        "visual_planner": "",
    }
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
            version="2026-09-23T01:00",
            change="The slot is `summarizer`; a file still naming the verb is refused.",
            why="A slot holds a model, so its name is a noun.",
        ),
        ChangelogEntry(
            version="2026-09-23",
            change="The request block becomes `sampling`; the client timeout becomes a field.",
            why="A setting this project does not compute on is passed through, never mapped.",
        ),
        ChangelogEntry(
            version="2026-09-21T06:00",
            change="The turn block goes; two keys move onto the entry and a run still reads.",
            why="The markers are the model's own template, so the server reads them off it.",
        ),
        ChangelogEntry(
            version="2026-09-21T05:00",
            change="The draft head becomes a companion file; its decode settings join `server`.",
            why="A file that cannot name what a publisher ships cannot describe that model.",
        ),
        ChangelogEntry(
            version="2026-09-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    summarizer: ModelEntry
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
                name for name, field in cls.model_fields.items() if field.annotation is ModelEntry
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
        return tuple((name, entry) for name, entry in declared if isinstance(entry, ModelEntry))

    @model_validator(mode="before")
    @classmethod
    def _a_removed_key_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("models", data, SUPERSEDED_MODELS_NAMES)
