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

`FingerprintRow` and `state/fingerprints.csv` are what the digest half left
behind. Nothing writes either one; they are removed with the field itself.
"""

from __future__ import annotations

import hashlib
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    Model,
    RunId,
    Sha256,
    Timestamp,
    canonical_json,
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

    def fingerprint(self) -> str:
        """sha256 over the sorted, fully-enumerated input set.

        Kept so a payload written before 2026-09-12 can still be read back and
        checked against the inputs beside it. Nothing calls it to decide
        anything, and the comparison a reader wants is `changed_inputs`, which
        names which input moved where a digest can only say that one did.
        """
        return hashlib.sha256(
            canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()

    def changed_inputs(self, previous: PipelineInputs) -> tuple[str, ...]:
        """Which named inputs differ from an earlier run's, in declaration order.

        The whole of the comparison, and it is the reason the record is a list of
        names rather than one digest: a digest affords equality and nothing else,
        which is a gate's only operation.
        """
        mine = self.model_dump(mode="json")
        theirs = previous.model_dump(mode="json")
        return tuple(name for name in type(self).model_fields if mine[name] != theirs[name])


class FingerprintRow(Contract):
    """One row of the retired `state/fingerprints.csv`. Nothing writes it.

    Kept only so the ten rows already committed can be read back. It goes with
    the field, in the commit that drops `pipeline_fingerprint` from every model.
    """

    __schema_stem__: ClassVar[str] = "fingerprint-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-12T21:00",
            change="pipeline_fingerprint is optional, and nothing writes this row any more.",
            why=(
                "The ledger existed to expand a digest that gated a skip nobody wired. The "
                "digest went, so the writer went. The ten committed rows still read back, "
                "and the rebuilt-not-trusted check still holds wherever a stamp is present."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change="Digest the five runtime knobs that move the logits, as `runtime_flags`.",
            why=(
                "cache_type_k, cache_type_v, flash_attention, n_parallel and n_threads_batch "
                "each change the arithmetic the runtime does, so one of them could rewrite a "
                "summary while the stamp held still. Every fingerprint moves, which is why it "
                "rides the model swap's reset rather than spending a second one. The ledger "
                "carried a header and no rows, so nothing written before this had to migrate."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: the stamp, the inputs it digests, and the host as diagnostic.",
            why="A fingerprint nobody can expand is meaningless hex three years from now.",
        ),
    )

    pipeline_fingerprint: Sha256 | None = Field(
        default=None,
        description="Null since 2026-09-12. Nothing builds a stamp and nothing writes a row.",
    )
    first_seen_run: RunId
    first_seen_at: Timestamp
    inputs: PipelineInputs
    host_cpu: str = Field(
        min_length=1,
        description="Diagnostic only. Excluded from the digest by construction, not by filter.",
    )

    @model_validator(mode="after")
    def _fingerprint_is_rebuilt_not_trusted(self) -> Self:
        if self.pipeline_fingerprint is None:
            return self
        if self.pipeline_fingerprint != self.inputs.fingerprint():
            raise ValueError("pipeline_fingerprint must be the digest of inputs, rebuilt on read")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The ledger's column order, flattened one level so every cell is a scalar.

        One definition, so a writer and a reader cannot disagree about the shape.
        """
        columns: list[str] = []
        for name in cls.model_fields:
            if name == "inputs":
                columns.extend(PipelineInputs.model_fields)
            else:
                columns.append(name)
        return tuple(columns)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        flat: dict[str, str] = {**payload.pop("inputs"), **payload}
        return {column: str(flat[column]) for column in self.csv_columns()}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        nested = {name: row[name] for name in PipelineInputs.model_fields}
        top = {name: row[name] for name in cls.model_fields if name != "inputs"}
        return cls.model_validate({**top, "inputs": nested})
