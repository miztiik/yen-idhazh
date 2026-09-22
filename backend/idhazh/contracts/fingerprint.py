"""What produced an output, recorded on the run record and gating nothing.

`temperature=0, seed=0` is not determinism; it is determinism given identical
logits. A quantisation swap, a llama.cpp rebuild, a reworded prompt, a widened
context or a publisher quietly rewriting an article at the same URL all move an
output without moving a single line of this repository. So the inputs are
enumerated by name, and `PipelineInputs` is that enumeration.

**It is a record and never a key.** No run, no pool, no window and no published
number turns on these values: a run whose inputs moved is counted, averaged and
published exactly as one whose inputs held still. They were a digest that gated
a skip nobody wired and keyed an eval window that never opened, and both jobs
were deleted on 2026-09-10 by owner decision. What survives is the reading.

`FingerprintRow` and `state/fingerprints.csv` were what the digest half left
behind. Both were deleted on 2026-09-13 with the field itself.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    Model,
    Sha256,
)

#: What this project called each runtime flag before the model file started
#: carrying llama-server's own spelling. A day written under the old names is
#: read through this table, so the console compares `-ctk` against `-ctk`
#: rather than reporting that every switch moved on the day of the rename.
#: Nine of the twelve renamed and nothing else about them changed.
RENAMED_FLAGS: Final[dict[str, str]] = dict(
    MappingProxyType(
        {
            "cache_type_k": "-ctk",
            "cache_type_v": "-ctv",
            "flash_attention": "-fa",
            "n_parallel": "-np",
            "n_threads_batch": "-tb",
            "checkpoint_min_step": "-cms",
            "ctx_checkpoints": "-ctxcp",
            "cache_ram": "-cram",
            "slot_prompt_similarity": "-sps",
        }
    )
)

#: The three that were one boolean and became a pair of flags. True was the
#: positive flag and False the `--no-` one, and a flag carries no value of its
#: own - it is present or it is not - so both sides record `SET`.
SPLIT_FLAGS: Final[dict[str, tuple[str, str]]] = dict(
    MappingProxyType(
        {
            "cache_prompt": ("--cache-prompt", "--no-cache-prompt"),
            "jinja": ("--jinja", "--no-jinja"),
            "reasoning_preserve": ("--reasoning-preserve", "--no-reasoning-preserve"),
        }
    )
)

#: What a settings mapping records for a key the model file leaves out. The
#: writer spells it too; it is repeated here because the migration has to write
#: it for the other half of a split boolean.
RUNTIME_DEFAULT: Final = "runtime-default"

#: What a bare flag records. A flag with no argument is present or absent, and
#: `SET` is what present looks like.
SET: Final = "set"


def _split_joined(spelling: str) -> dict[str, str]:
    """`a=1;b=2` back into the pairs somebody joined to make it.

    A term with no `=` is dropped rather than guessed at: the mapping is read
    key by key, and a key with no value would compare unequal to itself the
    moment anything downstream serialised it.
    """
    pairs: dict[str, str] = {}
    for term in spelling.split(";"):
        name, sep, value = term.partition("=")
        if sep and name:
            pairs[name] = value
    return pairs


def _flags_under_their_own_spelling(recorded: dict[str, str]) -> dict[str, str]:
    """One day's runtime switches, keyed the way llama-server keys them.

    A boolean that became a pair of flags writes both halves, so a day read
    through here has the same key set a day written today has. Writing only the
    half that was true would leave the other half absent on one day and
    `runtime-default` on the next, which is the false alarm this table exists to
    stop.
    """
    under: dict[str, str] = {}
    for name, value in recorded.items():
        if name in SPLIT_FLAGS:
            positive, negative = SPLIT_FLAGS[name]
            asked = value.strip().lower() == "true"
            under[positive] = SET if asked else RUNTIME_DEFAULT
            under[negative] = RUNTIME_DEFAULT if asked else SET
            continue
        under[RENAMED_FLAGS.get(name, name)] = value
    return under


class PipelineInputs(Model):
    """Every input that can move an output, and nothing that cannot.

    This is the recorded input manifest. It hangs off `RunRecord.inputs`, it is
    read by a person and by the one alarm that compares two runs, and nothing
    anywhere decides anything on it.

    Delete it and exactly one thing changes on the whole site: a rule disappears
    from two console charts. Not one figure moves and not one row vanishes. A
    gate fails that test by construction; a record passes it.

    `host_cpu` is deliberately absent: it is the one field that explains a
    determinism violation, and a run's own processor is luck rather than a
    choice anybody made.
    """

    model_sha256: Sha256
    quantisation: str = Field(min_length=1)
    runtime_build: str = Field(
        min_length=1, description="The llama.cpp build the weights were decoded by."
    )
    chat_template_sha256: Sha256
    prompt_sha256: Sha256
    turn_markers_sha256: Sha256 | None = Field(
        default=None,
        description=(
            "The turn envelope the prompts were rendered through - every marker "
            "string, the system placement and its joiner, digested as one. "
            "prompt_sha256 already moves when a marker moves, and stops short of two "
            "envelope facts that move an output without moving a rendered prompt: "
            "which of the two reply openings a call ends on, and the marker the "
            "thinking span stops at. Absent means a run written before 2026-09-14, "
            "when the markers first became able to move at all. It is never a default "
            "value: a substituted digest would say the envelope was recorded and "
            "unchanged, which is the one thing an absent key must not be read as."
        ),
    )
    output_schema_sha256: Sha256 = Field(
        description="The constrained-decoding schema. Its shape is the only guard on the output."
    )
    truncation_cap_tokens: int = Field(ge=1)
    sampling: dict[str, str] = Field(
        min_length=1,
        description=(
            "The decoding parameters, one key each, under the name the request body "
            "spells them with. A mapping rather than one joined string so the console "
            "compares key by key: a rename moves no key's value, and a setting that "
            "stopped being sent is a key that is absent rather than a record that "
            "differs everywhere."
        ),
    )
    runtime_flags: dict[str, str] = Field(
        min_length=1,
        description=(
            "The runtime switches that can move the arithmetic, one key each, spelled "
            "as llama-server spells them. A bare flag records `set`; a flag the model "
            "file leaves out records `runtime-default`, because what the server picks "
            "is a real and different choice from pinning a value."
        ),
    )
    n_ctx: int = Field(ge=1)
    n_batch: int = Field(ge=1)
    n_ubatch: int = Field(ge=1)
    n_threads: int = Field(ge=1)
    runner_class: str = Field(min_length=1)
    extractor_version: str = Field(min_length=1)
    sanitizer_version: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _read_the_joined_settings(cls, data: Any) -> Any:
        """Both settings blocks were one joined string until 2026-09-22.

        A published day is never rewritten, so every record written before that
        carries `temperature=0.2000;top_p=1.0000;...` where this shape now wants
        a mapping. The split is the whole migration for `sampling`: the keys
        were already this project's own names for the values, and a key a later
        run stopped sending is simply a key that is absent.

        `runtime_flags` needs one table on top, because the names moved as well
        as the shape. The model file started carrying llama-server's own flags
        on 2026-09-21, so the same switch was `cache_type_k` on Sunday and
        `-ctk` on Monday with the identical value behind it. Read through the
        table the two days compare equal, which is what they should have done -
        nothing about the decode moved.

        One old format is parsed and no chain of them. Three historical
        spellings exist and all three split the same way: a term this table does
        not name keeps its own name and compares against itself.
        """
        if not isinstance(data, dict):
            return data
        moved: dict[str, Any] = {}
        sampling = data.get("sampling")
        if isinstance(sampling, str):
            moved["sampling"] = _split_joined(sampling)
        flags = data.get("runtime_flags")
        if isinstance(flags, str):
            moved["runtime_flags"] = _flags_under_their_own_spelling(_split_joined(flags))
        return {**data, **moved} if moved else data

    def changed_inputs(self, previous: PipelineInputs) -> tuple[str, ...]:
        """Which named inputs differ from an earlier run's, in declaration order.

        The whole of the comparison, and it is the reason the record is a list of
        names rather than one digest: a digest affords equality and nothing else,
        which is a gate's only operation.
        """
        mine = self.model_dump(mode="json")
        theirs = previous.model_dump(mode="json")
        return tuple(name for name in type(self).model_fields if mine[name] != theirs[name])
