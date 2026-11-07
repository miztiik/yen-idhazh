"""Which immutable code, model and tokenizer did this coverage backend actually load?"""

from typing import Self

from pydantic import Field, model_validator

from summary_evaluator.shared.contracts.base import CommitId, ModelReference, NonblankText
from summary_evaluator.source_coverage.contracts.base import CoverageContract


class CoverageModelIdentity(CoverageContract):
    reference: ModelReference
    configured_revision: CommitId
    loaded_revision: CommitId
    tokenizer_revision: CommitId
    code_revision: CommitId
    runtime_versions: dict[str, NonblankText] = Field(min_length=1)

    @model_validator(mode="after")
    def require_observed_selected_resources(self) -> Self:
        if self.loaded_revision != self.configured_revision:
            raise ValueError("The observed legacy model must match the selected revision")
        if self.tokenizer_revision != self.loaded_revision:
            raise ValueError("The legacy tokenizer must belong to the loaded model snapshot")
        return self
