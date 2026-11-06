"""When does a body-free evaluation outcome truthfully describe completed work?"""

from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from hhem_evaluator.contracts.base import OutcomeStatus, SchemaVersion
from hhem_evaluator.contracts.error_detail import ErrorDetail
from hhem_evaluator.contracts.evaluate_request import EffectiveSettings
from hhem_evaluator.contracts.evaluation_progress import (
    EvaluationTimings,
    EvaluationWindows,
    WindowCounts,
    WindowDetails,
)
from hhem_evaluator.contracts.model_identity import ModelIdentity
from hhem_evaluator.contracts.worker_identity import WorkerIdentity
from hhem_evaluator.shared.contracts.base import Delta, NativeContract, Score, Uuid4, Uuid5
from hhem_evaluator.shared.contracts.optional_fields import is_absent, omit_default


class EvaluationResult(NativeContract):
    """Preserve completed primary scoring without claiming unfinished work."""

    version: SchemaVersion
    status: OutcomeStatus
    execution_id: Uuid4
    request_id: Uuid4 | None
    correlation_id: Uuid4 | None
    terminal_event_id: Uuid5 | None
    hhem: Score | None
    hhem_full: Score | None
    hhem_delta: Delta | None
    effective_settings: EffectiveSettings | None
    windows: EvaluationWindows
    model: ModelIdentity | None
    worker: WorkerIdentity | None
    timings_ms: EvaluationTimings
    errors: tuple[ErrorDetail, ...]
    window_details: WindowDetails | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )

    @field_validator("window_details", mode="after")
    @classmethod
    def reject_null_details(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit unrequested window_details instead of supplying null")
        return value

    @model_validator(mode="after")
    def require_consistent_outcome(self) -> Self:
        if any(error.code == "CLIENT_DISCONNECTED" for error in self.errors):
            raise ValueError("Client disconnect belongs only in a terminal event")
        logging_failed = any(error.code == "LOGGING_FAILED" for error in self.errors)
        if (self.terminal_event_id is None) != logging_failed:
            raise ValueError("terminal_event_id is null only when terminal logging failed")
        if self.status == "complete":
            if self.errors or self.hhem is None:
                raise ValueError("Complete requires a primary score and no errors")
            if self.timings_ms.total is None:
                raise ValueError("Complete requires measured total timing")
        elif not self.errors:
            raise ValueError("Partial and failed outcomes require errors")
        if (self.status == "failed") != (self.hhem is None):
            raise ValueError("Partial preserves primary scoring; failed has no primary score")
        if self.hhem is not None and (
            self.request_id is None
            or self.correlation_id is None
            or self.model is None
            or self.worker is None
            or self.timings_ms.queue_wait is None
            or self.timings_ms.primary_scoring is None
        ):
            raise ValueError("Completed primary scoring requires its identities and timings")
        self.require_comparison(self.hhem, self.windows.primary)
        if self.windows.primary is None and self.timings_ms.primary_scoring is not None:
            raise ValueError("Unplanned primary scoring requires null timing")
        if self.windows.full is None and self.timings_ms.full_scoring is not None:
            raise ValueError("Unplanned full scoring requires null timing")
        if self.windows.full is not None and self.windows.full.scored and self.hhem is None:
            raise ValueError("Full scoring cannot start before primary completion")
        if self.effective_settings is None:
            if (
                self.hhem is not None
                or self.hhem_full is not None
                or self.hhem_delta is not None
                or self.window_details is not None
                or self.windows.primary is not None
                or self.windows.full is not None
                or self.windows.full_reused_primary
            ):
                raise ValueError("Unresolved settings cannot report planned or completed scoring")
            return self
        self.require_full_consistency()
        self.require_details_consistency()
        return self

    @staticmethod
    def require_comparison(score: float | None, counts: WindowCounts | None) -> None:
        if score is not None and (counts is None or counts.scored != counts.planned):
            raise ValueError("A score requires every planned window to be completed")
        if score is None and counts is not None and counts.scored == counts.planned:
            raise ValueError("A fully scored comparison requires its completed score")

    def require_full_consistency(self) -> None:
        effective = self.effective_settings
        if effective is None:
            return
        if not effective.hhem_full:
            if (
                self.hhem_full is not None
                or self.hhem_delta is not None
                or self.windows.full is not None
                or self.windows.full_reused_primary
                or self.timings_ms.full_scoring is not None
            ):
                raise ValueError("Disabled full comparison cannot report work or a score")
        elif self.windows.full_reused_primary:
            if (
                self.hhem is None
                or self.hhem_full != self.hhem
                or self.windows.primary is None
                or self.windows.full is None
                or self.windows.full.planned != self.windows.primary.planned
                or self.windows.full.scored != 0
                or self.timings_ms.full_scoring is not None
            ):
                raise ValueError("Full reuse requires the primary score and no additional scoring")
        else:
            self.require_comparison(self.hhem_full, self.windows.full)
            if self.hhem_full is not None and self.timings_ms.full_scoring is None:
                raise ValueError("Completed full scoring requires its measured duration")
        if self.hhem_full is not None and self.hhem is None:
            raise ValueError("Full scoring cannot complete before primary scoring")
        expected_delta = (
            self.hhem - self.hhem_full
            if self.hhem is not None and self.hhem_full is not None
            else None
        )
        if self.hhem_delta != expected_delta:
            raise ValueError("hhem_delta must be primary minus full, or null without both")
        if self.status == "complete" and effective.hhem_full and self.hhem_full is None:
            raise ValueError("Complete requires the requested full comparison")

    def require_details_consistency(self) -> None:
        effective = self.effective_settings
        if effective is None:
            return
        if (self.window_details is not None) != effective.include_window_details:
            raise ValueError("window_details must be present exactly when requested")
        details = self.window_details
        if details is None:
            return
        expected_primary = self.windows.primary.scored if self.windows.primary is not None else 0
        if len(details.primary) != expected_primary:
            raise ValueError("Primary details must contain only all completed windows")
        if self.hhem is not None and max(window.score for window in details.primary) != self.hhem:
            raise ValueError("Primary score must match its completed window maximum")
        if self.windows.full_reused_primary:
            if details.full != details.primary:
                raise ValueError("Reused full details must mirror primary details")
        elif self.windows.full is None:
            if details.full is not None:
                raise ValueError("Unplanned full comparison requires null full details")
        elif details.full is None or len(details.full) != self.windows.full.scored:
            raise ValueError("Full details must contain only all completed windows")
        if (
            self.hhem_full is not None
            and details.full is not None
            and max(window.score for window in details.full) != self.hhem_full
        ):
            raise ValueError("Full score must match its completed window maximum")
