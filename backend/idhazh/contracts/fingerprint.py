"""The inputs that produced an output, and the ledger that expands them.

`temperature=0, seed=0` is not determinism; it is determinism given identical
logits. A quantisation swap, a llama.cpp rebuild, a reworded prompt, a widened
context or a publisher quietly rewriting an article at the same URL all move an
output without moving a single line of this repository.

So the stamp is a digest over an explicitly enumerated input set, and that set
is `PipelineInputs` itself: the digest is taken over the model's own
serialization, which means a field added here changes every fingerprint, and a
field that was never declared cannot be silently forgotten.

`evals/fingerprints.csv` is append-only and never pruned, because a fingerprint
with nothing to expand it into is meaningless hex three years from now.
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

    `host_cpu` is deliberately absent: it is the one field that explains a
    determinism violation, and including it would make every runner a different
    fingerprint, which would hide the violation it exists to expose.
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
    n_ctx: int = Field(ge=1)
    n_batch: int = Field(ge=1)
    n_ubatch: int = Field(ge=1)
    n_threads: int = Field(ge=1)
    runner_class: str = Field(min_length=1)
    extractor_version: str = Field(min_length=1)
    sanitizer_version: str = Field(min_length=1)

    def fingerprint(self) -> str:
        """sha256 over the sorted, fully-enumerated input set."""
        return hashlib.sha256(
            canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class FingerprintRow(Contract):
    """One row of `evals/fingerprints.csv`, appended the first time a stamp is seen."""

    __schema_stem__: ClassVar[str] = "fingerprint-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: the stamp, the inputs it digests, and the host as diagnostic.",
            why="A fingerprint nobody can expand is meaningless hex three years from now.",
        ),
    )

    pipeline_fingerprint: Sha256
    first_seen_run: RunId
    first_seen_at: Timestamp
    inputs: PipelineInputs
    host_cpu: str = Field(
        min_length=1,
        description="Diagnostic only. Excluded from the digest by construction, not by filter.",
    )

    @model_validator(mode="after")
    def _fingerprint_is_rebuilt_not_trusted(self) -> Self:
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
