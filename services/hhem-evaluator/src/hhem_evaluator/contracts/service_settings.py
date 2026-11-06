"""Which authored startup settings can an independent evaluator accept?"""

from typing import Self

from pydantic import Field, StrictBool, model_validator

from hhem_evaluator.contracts.base import SchemaVersion
from hhem_evaluator.shared.contracts.base import Count, NativeContract, PositiveCount, RelativePath
from hhem_evaluator.shared.contracts.service_settings import (
    EvaluationSettings,
    ListenerSettings,
    LoggingSettings,
    ModelAssetSettings,
    QueueSettings,
    WorkerSettings,
)


class HhemSettings(NativeContract):
    """Select the model assets, foundation assets and relative cache path."""

    model: ModelAssetSettings
    foundation: ModelAssetSettings
    cache_directory: RelativePath


class ScoringSettings(NativeContract):
    """Bound window geometry and the number of planned comparisons."""

    chunk_words: PositiveCount
    chunk_overlap_words: Count
    max_windows_per_comparison: PositiveCount

    @model_validator(mode="after")
    def require_valid_overlap(self) -> Self:
        if self.chunk_overlap_words >= self.chunk_words:
            raise ValueError("chunk_overlap_words must be smaller than chunk_words")
        return self


class ResponseSettings(NativeContract):
    """Select the two independent optional response controls."""

    hhem_full: StrictBool
    include_window_details: StrictBool


class ServiceSettings(NativeContract):
    """Freeze scoring settings and the shared listener snapshot sent to a worker."""

    version: SchemaVersion
    enabled: StrictBool = Field(
        description="Whether the shared application's explicit route selection enables HHEM."
    )
    hhem: HhemSettings
    scoring: ScoringSettings
    response: ResponseSettings
    listener: ListenerSettings
    queue: QueueSettings
    evaluation: EvaluationSettings
    worker: WorkerSettings
    logging: LoggingSettings
