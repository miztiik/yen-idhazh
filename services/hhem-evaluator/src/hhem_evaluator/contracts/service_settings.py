"""Which authored startup settings can an independent evaluator accept?"""

from typing import Literal, Self

from pydantic import Field, StrictBool, model_validator

from .base import (
    AssetName,
    CommitId,
    ContextIdentity,
    Count,
    ModelReference,
    NativeContract,
    PositiveCount,
    RelativePath,
    SchemaVersion,
)


class ModelAssetSettings(NativeContract):
    """Name one immutable repository and its finite asset inventory."""

    reference: ModelReference
    revision: CommitId
    files: tuple[AssetName, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_files(self) -> Self:
        if len(set(self.files)) != len(self.files):
            raise ValueError("files must contain distinct asset names")
        return self


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


class ListenerSettings(NativeContract):
    """Bound loopback input without selecting host CPU or memory resources."""

    host: Literal["127.0.0.1", "::1"]
    port: int = Field(strict=True, ge=1, le=65535)
    max_body_bytes: PositiveCount
    body_read_timeout_ms: PositiveCount


class QueueSettings(NativeContract):
    """Bound waiting reservations and their advertised retry delay."""

    capacity: PositiveCount
    wait_timeout_ms: PositiveCount
    retry_after_seconds: PositiveCount


class EvaluationSettings(NativeContract):
    """Bound the combined evaluation after it leaves the queue."""

    timeout_ms: PositiveCount


class WorkerSettings(NativeContract):
    """Bound owned process lifetimes and one process identity read."""

    startup_timeout_ms: PositiveCount
    replacement_timeout_ms: PositiveCount
    stop_grace_ms: PositiveCount
    forced_stop_ms: PositiveCount
    shutdown_timeout_ms: PositiveCount
    max_proc_identity_bytes: PositiveCount

    @model_validator(mode="after")
    def require_complete_shutdown_budget(self) -> Self:
        if self.shutdown_timeout_ms < self.stop_grace_ms + self.forced_stop_ms:
            raise ValueError(
                "shutdown_timeout_ms must accommodate stop_grace_ms and forced_stop_ms"
            )
        return self


class LoggingSettings(NativeContract):
    """Select structured event severity and the serialized event byte bound."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    max_event_bytes: PositiveCount


class ServiceSettings(NativeContract):
    """Freeze every authored operational setting before a service starts."""

    version: SchemaVersion
    enabled: StrictBool = Field(
        description=(
            "Development flag; remove when the standalone API is released after "
            "real-model workflow verification."
        )
    )
    hhem: HhemSettings
    scoring: ScoringSettings
    response: ResponseSettings
    listener: ListenerSettings
    queue: QueueSettings
    evaluation: EvaluationSettings
    worker: WorkerSettings
    logging: LoggingSettings


class StartupContext(NativeContract):
    """Carry only bounded operator-supplied run identities."""

    run_id: ContextIdentity | None = None
    pipeline_name: ContextIdentity | None = None
    task_name: ContextIdentity | None = None
