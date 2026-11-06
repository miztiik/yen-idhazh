"""Which ordered body-free event describes one actual service operation?"""

from datetime import timedelta
from typing import Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from summary_evaluator.hhem.contracts.base import Operation, SchemaVersion
from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.model_identity import ModelIdentity
from summary_evaluator.hhem.resolve_ids import create_event_id
from summary_evaluator.shared.contracts.base import (
    ContextIdentity,
    Count,
    Milliseconds,
    NativeContract,
    OutcomeStatus,
    PositiveCount,
    Score,
    ServiceStatus,
    Uuid4,
    Uuid5,
)
from summary_evaluator.shared.contracts.optional_fields import is_absent, omit_default
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity


class EventDetails(NativeContract):
    """Allow only typed measured values, never an arbitrary diagnostic dictionary."""

    status: OutcomeStatus | ServiceStatus | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    worker: WorkerIdentity | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    model: ModelIdentity | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    window_index: Count | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    window_count: PositiveCount | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    scored_window_count: Count | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    queue_depth: Count | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    duration_ms: Milliseconds | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    score: Score | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    errors: tuple[ErrorDetail, ...] | SkipJsonSchema[None] = Field(
        default=None, min_length=1, exclude_if=is_absent, json_schema_extra=omit_default
    )

    @field_validator(
        "status",
        "worker",
        "model",
        "window_index",
        "window_count",
        "scored_window_count",
        "queue_depth",
        "duration_ms",
        "score",
        "errors",
        mode="after",
    )
    @classmethod
    def reject_unmeasured_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit unmeasured event details instead of supplying null")
        return value

    @model_validator(mode="after")
    def require_consistent_counts(self) -> Self:
        if self.window_count is not None:
            if self.window_index is not None and self.window_index >= self.window_count:
                raise ValueError("window_index must be below window_count")
            if (
                self.scored_window_count is not None
                and self.scored_window_count > self.window_count
            ):
                raise ValueError("scored_window_count must not exceed window_count")
        return self


class EvaluationEvent(NativeContract):
    """Bind one UTC occurrence and deterministic event ID to its execution."""

    version: SchemaVersion
    event_id: Uuid5
    execution_id: Uuid4
    sequence: PositiveCount
    request_id: Uuid4 | None
    correlation_id: Uuid4 | None
    caused_by_event_id: Uuid5 | None
    run_id: ContextIdentity | None
    pipeline_name: ContextIdentity | None
    task_name: ContextIdentity | None
    operation_id: Uuid4
    operation: Operation
    phase: Literal["started", "completed", "failed", "cancelled"]
    occurred_at: AwareDatetime = Field(
        description="UTC instant captured when the event is emitted."
    )
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    details: EventDetails

    @model_validator(mode="after")
    def require_event_identity(self) -> Self:
        if self.event_id != create_event_id(self.execution_id, self.sequence):
            raise ValueError("event_id does not match execution_id and sequence")
        if self.caused_by_event_id == self.event_id:
            raise ValueError("An event cannot cause itself")
        if self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must use UTC")
        if self.operation in ("request", "service") and self.phase == "started":
            if self.caused_by_event_id is not None:
                raise ValueError("Root request and service starts have no cause")
        elif self.operation in ("queue", "primary", "full") and self.caused_by_event_id is None:
            raise ValueError("Queue and comparison events require their initiating cause")
        return self

    def encode_json_line(self, max_bytes: int) -> bytes:
        """Bound the complete UTF-8 JSONL record without truncating it."""
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_event_bytes must be a positive integer")
        encoded = (self.model_dump_json() + "\n").encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError("Event exceeds logging.max_event_bytes")
        return encoded
