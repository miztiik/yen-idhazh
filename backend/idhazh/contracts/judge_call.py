"""What was the instrument SET TO when it wrote the reading beside this?

Seven columns, declared once so that two judges spell them one way. Grain-free,
so any row may carry them whatever its own unit of work is. A judge that runs no
model does not inherit this at all - it is the stamp for a model call, not for a
judge.

**It names no judge and no judge's model.** A roster declared here would put one
tenant's vocabulary into every other tenant's contract, and a record typed with
it could not be imported at all in a repository with no judge in it, because a
`Literal` with no members is not legal Python. So `judge_id` is a slug the writer
states and `judge_model` is one printable line. Each judge narrows both in its own
row - pydantic lets a subclass narrow a field's type - which keeps the closed set
where it can be honestly closed and absent where it cannot.

**A mixin over the plain model base, inherited alongside `Contract`.** Never
alongside the CSV protocol: `CsvRecord` and `CsvContract` are `typing.Protocol`s
in `idhazh.ledger`, mixing one with a pydantic model is a metaclass conflict, and
the import runs the other way round in any case.

**It declares no schema stem and joins no export tuple, and that is a carve-out
rather than an omission.** `contracts.export.CONTRACTS` is typed
`tuple[type[Contract], ...]` and the exporter calls `schema_filename()` on every
member, so a stem-less mixin registered there would stop the export. This is a
`Model`; every row that inherits it is the `Contract`, and each of those
registers itself.

**A row with committed rows behind it does not inherit this.** Base fields are
collected first, so inheriting reorders the header and makes the store
unappendable. Such a row declares the columns it needs in its own body, at the
tail, where a header only grows to the right.

**There is no per-call half, and that is a deliberate deletion.** An earlier
draft split this in two and gave the second half three fields - whether the
grammar applied, the first-token window and one call's clock. Nothing inherited
it: the shard-shaped rows have no single call, and neither the council's own
record nor a holdout row involves a model at all. Three fields declared for a row
that does not exist is speculative generality, so the per-call columns live where
they are used and each one names its own grain there. The second real caller is
what extracts a per-call mixin.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints

from idhazh.contracts.base import PRINTABLE_LINE_PATTERN, Model, Sha256, Slug

#: How a model is named in a cell: one printable line, at most 96 characters.
#: Long enough for a repository path with a quantisation suffix, and a line
#: because a newline splits the row for any reader that takes a day file a line
#: at a time.
ModelReference = Annotated[str, StringConstraints(pattern=PRINTABLE_LINE_PATTERN, max_length=96)]

#: How long a recorded slug may be. A judge names itself and nothing here checks
#: the name against a list, so the only rule left is that the cell stays a cell.
SLUG_MAX_LENGTH = 64


class JudgeConfigStamp(Model):
    """What the instrument was set to when it wrote the reading beside this."""

    judge_id: Slug = Field(
        max_length=SLUG_MAX_LENGTH,
        description=(
            "Which instrument wrote this reading. Recorded rather than checked "
            "against a list of who may exist: a judge narrows this column to its own "
            "single value in its own row, which is where a closed set can be closed "
            "honestly."
        ),
    )
    judge_model: ModelReference | None = Field(
        default=None,
        description=(
            "Which weights judged. Empty where the reading was taken without a model, "
            "which is a different fact from a model nobody recorded."
        ),
    )
    judge_temperature: float | None = Field(
        default=None,
        ge=0,
        description=(
            "The sampler temperature, as the number it was set to. An operator "
            "reading a row needs the value, not a digest of it."
        ),
    )
    decode_digest: Sha256 | None = Field(
        default=None,
        description=(
            "sha256 of the canonical JSON of every key the caller posted that is not "
            "excluded. Taken from the payload rather than from config, because a "
            "digest built off config cannot see a payload-builder defect. Three keys "
            "are excluded and each for its own reason: the prompt differs every row "
            "and would make this a row id, and the grammar and the model reference "
            "both have a column here already."
        ),
    )
    thinking_spans: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many reasoning spans the call decoded before its answer - 0 for a "
            "cold answer, 1 under a thinking envelope. A column of its own because "
            "the digest above cannot see the envelope: the only posted key it moves "
            "is the prompt, and the prompt is excluded. Without this cell a reading "
            "taken after reasoning and one taken cold are one population to every "
            "reader."
        ),
    )
    prompt_digest: Sha256 | None = Field(
        default=None, description="sha256 of the rendered system turn."
    )
    grammar_digest: Sha256 | None = Field(
        default=None, description="sha256 of the grammar handed to the decoder."
    )
