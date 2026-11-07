"""Which genuine legacy dimension calls and resources reproduce one bounded coverage capture?"""

from __future__ import annotations

import hashlib
from typing import Annotated, ClassVar, Literal, Self

from pydantic import ConfigDict, Field, JsonValue, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    Model,
    RelPath,
    Sha256,
    Slug,
)
from idhazh.contracts.recorded_instant import RecordedInstant

COVERAGE_RECORDING_VERSION: Literal["2026-11-07"] = "2026-11-07"
Dimension = Literal["fluency", "coherence", "consistency"]
Text = Annotated[str, StringConstraints(strict=True, min_length=1)]


class CoverageRecordingCaseInput(Model):
    id: Slug
    source_text: Text
    summary_text: Text


class CoverageRecordingInputs(Contract):
    """Declare the finite project-authored inputs before any real model capture."""

    __schema_stem__: ClassVar[str] = "coverage-recording-inputs"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=COVERAGE_RECORDING_VERSION,
            change="Declare bounded named source-coverage capture inputs.",
            why="A fixed input list makes the real capture finite and replayable.",
        ),
    )
    version: Literal["2026-11-07"] = COVERAGE_RECORDING_VERSION
    max_cases: int = Field(strict=True, gt=0)
    max_input_bytes: int = Field(strict=True, gt=0)
    cases: tuple[CoverageRecordingCaseInput, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_bounded_distinct_inputs(self) -> Self:
        if len(self.cases) > self.max_cases or len({case.id for case in self.cases}) != len(
            self.cases
        ):
            raise ValueError("Capture inputs must be distinct and within their declared count")
        for case in self.cases:
            if not case.source_text.strip() or not case.summary_text.strip():
                raise ValueError("Capture text must not be blank")
            if len(case.source_text.encode("utf-8")) + len(
                case.summary_text.encode("utf-8")
            ) > self.max_input_bytes:
                raise ValueError("Capture text exceeds its declared UTF-8 allowance")
        return self


class CoverageDimensionCall(Model):
    """Retain the actual converted inputs and returned dictionaries in call order."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    index: int = Field(strict=True, ge=0)
    dimension: Dimension
    overall: Literal[False]
    inputs: tuple[dict[str, str], ...] = Field(min_length=1)
    results: tuple[dict[str, float], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_complete_dimension(self) -> Self:
        if len(self.results) != len(self.inputs):
            raise ValueError("A recording requires the genuine complete batch")
        fields = {"system_output"} if self.dimension == "fluency" else {
            "system_output", "source"
        }
        if any(set(item) != fields for item in self.inputs):
            raise ValueError("Recorded inputs must be the actual dimension-call shape")
        if any(set(result) != {self.dimension} for result in self.results):
            raise ValueError("Recorded results must contain the requested dimension")
        if any(not 0 <= result[self.dimension] <= 1 for result in self.results):
            raise ValueError("Recorded dimension scores must be probabilities")
        return self


class CoverageRecordedCase(Model):
    id: Slug
    input_sha256: Sha256
    calls: tuple[CoverageDimensionCall, ...] = Field(min_length=3, max_length=3)
    expected_metrics: dict[str, JsonValue]

    @model_validator(mode="after")
    def require_ordered_calls(self) -> Self:
        if [(call.index, call.dimension) for call in self.calls] != [
            (0, "fluency"), (1, "coherence"), (2, "consistency")
        ]:
            raise ValueError("Coverage calls must retain the producer's dimension order")
        return self


class CoverageCaptureProvenance(Model):
    producer: RelPath
    source_revision: CommitSha
    producer_sha256: Sha256
    code_repository: Text
    code_revision: CommitSha
    code_files: dict[RelPath, Sha256]
    model_reference: Text
    configured_model_revision: CommitSha
    loaded_model_revision: CommitSha
    tokenizer_revision: CommitSha
    tokenizer_files: dict[RelPath, Sha256]
    runtime_versions: dict[str, str]
    platform: dict[str, JsonValue]


class CoverageModelRecording(Contract):
    """Current-only real model-call evidence; HTTP metric models remain with the scorer."""

    __schema_stem__: ClassVar[str] = "coverage-model-recording"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=COVERAGE_RECORDING_VERSION,
            change="Retain genuine dimension-call inputs, results and coverage provenance.",
            why="Final metrics alone cannot establish calculation parity.",
        ),
    )
    version: Literal["2026-11-07"] = COVERAGE_RECORDING_VERSION
    captured_at: RecordedInstant = Field(description="When this actual capture completed, in UTC.")
    inputs_sha256: Sha256
    settings_sha256: Sha256
    effective_settings: dict[str, JsonValue]
    provenance: CoverageCaptureProvenance
    cases: tuple[CoverageRecordedCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_observed_identity(self) -> Self:
        identity = self.provenance
        if identity.configured_model_revision != identity.loaded_model_revision:
            raise ValueError("The observed model must match the configured immutable revision")
        if not identity.code_files or not identity.tokenizer_files or not identity.runtime_versions:
            raise ValueError("Capture provenance must identify the real code and tokenizer files")
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Recorded cases must have distinct names")
        return self

    def require_inputs(self, inputs: CoverageRecordingInputs) -> None:
        """Bind the recording to the exact declared input bytes and case order."""
        if hashlib.sha256(inputs.to_json().encode("utf-8")).hexdigest() != self.inputs_sha256:
            raise ValueError("The recording belongs to different declared inputs")
        if [case.id for case in self.cases] != [case.id for case in inputs.cases]:
            raise ValueError("Recorded cases must match the declared input order")
        for recorded, selected in zip(self.cases, inputs.cases, strict=True):
            encoded = selected.model_dump_json().encode("utf-8")
            if hashlib.sha256(encoded).hexdigest() != recorded.input_sha256:
                raise ValueError("A recorded case belongs to different input bytes")
