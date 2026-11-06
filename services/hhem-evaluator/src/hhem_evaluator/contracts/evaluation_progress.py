"""Which completed windows and measured durations can an outcome report?"""

from typing import Self

from pydantic import StrictBool, field_validator, model_validator

from hhem_evaluator.shared.contracts.base import (
    Count,
    Milliseconds,
    NativeContract,
    PositiveCount,
    Score,
)


class WindowCounts(NativeContract):
    """Count a known plan and only its completed valid windows."""

    planned: PositiveCount
    scored: Count

    @model_validator(mode="after")
    def require_bounded_progress(self) -> Self:
        if self.scored > self.planned:
            raise ValueError("scored must not exceed planned")
        return self


class EvaluationWindows(NativeContract):
    """Keep unknown plans null and distinguish logical full-source reuse."""

    primary: WindowCounts | None
    full: WindowCounts | None
    full_reused_primary: StrictBool


class WindowDetail(NativeContract):
    """Describe a completed window with end-exclusive word positions, not text."""

    index: Count
    start_word: Count
    end_word: PositiveCount
    score: Score

    @model_validator(mode="after")
    def require_nonempty_range(self) -> Self:
        if self.end_word <= self.start_word:
            raise ValueError("end_word must be greater than start_word")
        return self


class WindowDetails(NativeContract):
    """Retain the ordered prefix of completed windows for each comparison."""

    primary: tuple[WindowDetail, ...]
    full: tuple[WindowDetail, ...] | None

    @field_validator("primary", "full")
    @classmethod
    def require_ordered_windows(
        cls, windows: tuple[WindowDetail, ...] | None
    ) -> tuple[WindowDetail, ...] | None:
        if windows is not None:
            for index, window in enumerate(windows):
                if window.index != index:
                    raise ValueError("Window indices must be consecutive from zero")
                if index and window.start_word <= windows[index - 1].start_word:
                    raise ValueError("Window starts must increase")
        return windows


class EvaluationTimings(NativeContract):
    """Retain measured milliseconds, with null for work not started or reused."""

    queue_wait: Milliseconds | None
    primary_scoring: Milliseconds | None
    full_scoring: Milliseconds | None
    total: Milliseconds | None
