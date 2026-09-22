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

from pydantic import Field

from idhazh.contracts.base import (
    Model,
    Sha256,
)


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
    sampling: str = Field(
        min_length=1, description="One canonical spelling of the decoding parameters."
    )
    runtime_flags: str = Field(
        min_length=1,
        description="One canonical spelling of the runtime knobs that move the arithmetic.",
    )
    n_ctx: int = Field(ge=1)
    n_batch: int = Field(ge=1)
    n_ubatch: int = Field(ge=1)
    n_threads: int = Field(ge=1)
    runner_class: str = Field(min_length=1)
    extractor_version: str = Field(min_length=1)
    sanitizer_version: str = Field(min_length=1)

    def changed_inputs(self, previous: PipelineInputs) -> tuple[str, ...]:
        """Which named inputs differ from an earlier run's, in declaration order.

        The whole of the comparison, and it is the reason the record is a list of
        names rather than one digest: a digest affords equality and nothing else,
        which is a gate's only operation.
        """
        mine = self.model_dump(mode="json")
        theirs = previous.model_dump(mode="json")
        return tuple(name for name in type(self).model_fields if mine[name] != theirs[name])
