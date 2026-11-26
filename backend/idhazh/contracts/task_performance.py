"""What did one pipeline task cost by the time it reached a terminal outcome?"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, ClassVar, Final, Literal, Self

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, PipelineName, RunId, TaskName
from idhazh.contracts.file_envelope import UnitId
from idhazh.contracts.recorded_instant import RecordedInstant

# These integers must remain exact in the TypeScript writer and browser.
_MAX_SAFE_INTEGER: Final = (1 << 53) - 1
_Count = Annotated[int, Field(strict=True, ge=0, le=_MAX_SAFE_INTEGER)]
_Reading = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
_Percent = Annotated[_Reading, Field(le=100)]

TaskPerformanceKind = Literal["workflow-task", "model-serving", "judge"]
TaskPerformanceOutcome = Literal["success", "error", "cancelled"]


class TaskPerformanceRow(Contract):
    """Terminal task measurements; unobserved cells remain null."""

    __schema_stem__: ClassVar[str] = "task-performance-row"
    __require_explicit_version__: ClassVar[bool] = True
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-25",
            change="Declare terminal task outcomes and their measured costs.",
            why="Task costs belong outside the hardware fingerprint.",
        ),
    )

    version: Literal["2026-11-25"]
    date: DateStamp = Field(description="Trusted UTC accounting day used to file the row.")
    run_id: RunId
    pipeline_name: PipelineName
    task_name: TaskName
    shard: _Count
    task_kind: TaskPerformanceKind
    outcome: TaskPerformanceOutcome
    subject_id: TaskName | None = None
    started_at: RecordedInstant | None = Field(default=None, description="Actual UTC start.")
    finished_at: RecordedInstant | None = Field(default=None, description="Actual UTC finish.")
    host_unit_id: UnitId | None = Field(
        default=None, description="Verified host capture work unit for this run and attempt."
    )
    elapsed_ms: _Reading | None = None
    machine_cpu_busy_pct: _Percent | None = Field(
        default=None, description="Whole-interval CPU busy percentage."
    )
    machine_cpu_steal_pct: _Percent | None = Field(
        default=None, description="Whole-interval CPU steal percentage."
    )
    machine_memory_available_min_kib: _Count | None = None
    worker_rss_peak_kib: _Count | None = Field(
        default=None, description="Maximum sampled worker RSS in KiB."
    )
    worker_cpu_time_ms: _Reading | None = None
    model_load_ms: _Reading | None = None
    server_prompt_seconds: _Reading | None = None
    server_prompt_tokens: _Count | None = None
    model_calls: _Count | None = None
    tokens_in: _Count | None = None
    tokens_out: _Count | None = None
    model_seconds: _Reading | None = None

    @field_validator("date")
    @classmethod
    def _valid_accounting_day(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def _matches_task_kind(self) -> Self:
        if (
            self.started_at is not None
            and self.finished_at is not None
            and datetime.fromisoformat(self.finished_at) < datetime.fromisoformat(self.started_at)
        ):
            raise ValueError("finished_at must be at or after started_at")
        if self.task_kind != "workflow-task" and self.subject_id is None:
            raise ValueError("model-serving and judge tasks require subject_id")

        serving = (self.model_load_ms, self.server_prompt_seconds, self.server_prompt_tokens)
        if self.task_kind == "model-serving":
            phase = (
                self.elapsed_ms,
                self.model_calls,
                self.tokens_in,
                self.tokens_out,
                self.model_seconds,
            )
            if any(value is not None for value in phase):
                raise ValueError("model-serving cannot report phase measurements or elapsed_ms")
            if all(value is None for value in serving):
                raise ValueError("model-serving requires at least one observed serving measurement")
        else:
            if self.elapsed_ms is None:
                raise ValueError("workflow-task and judge tasks require elapsed_ms")
            if any(value is not None for value in serving):
                raise ValueError("only model-serving tasks can report serving measurements")
        return self
