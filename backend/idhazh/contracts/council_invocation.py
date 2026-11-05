"""Which invocation, prepared files and reported units may the council authorize?"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    DateStamp,
    Model,
    RelPath,
    RunId,
    Sha256,
    Slug,
)
from idhazh.contracts.council_events import CodePlace, CouncilExit, ErrorName
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.knobs.council import CouncilConfig, JudgeLifecycleStatus


def _dates(values: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
    if len(set(values)) != len(values):
        raise ValueError("dates must be unique")
    for value in values:
        date.fromisoformat(value)
    return values


class ScheduleRequest(Model):
    """The UTC window and existing resource budgets offered to one plugin."""

    anchor_date: DateStamp
    window: tuple[DateStamp, ...]
    max_dates: int = Field(ge=1, strict=True)
    max_older_dates: int = Field(ge=0, strict=True)
    shards: int = Field(ge=1, strict=True)
    shard_seconds: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        _dates(self.window)
        date.fromisoformat(self.anchor_date)
        if self.anchor_date not in self.window:
            raise ValueError("window must include the anchor date")
        if any(day > self.anchor_date for day in self.window):
            raise ValueError("window cannot exceed the anchor date")
        return self


class JudgeSchedule(Model):
    """The plugin's complete answer, including an explicit empty answer."""

    dates: tuple[DateStamp, ...]

    _valid_dates = field_validator("dates")(_dates)

    def check(self, request: ScheduleRequest) -> Self:
        if (
            not set(self.dates) <= set(request.window)
            or len(self.dates) > request.max_dates
            or sum(day != request.anchor_date for day in self.dates) > request.max_older_dates
        ):
            raise ValueError("schedule exceeds the supplied window or budget")
        return self


class SelectedJudge(Model):
    """One registered plugin's exact status, dates and admitted width."""

    tenant: Slug
    status: JudgeLifecycleStatus
    dates: tuple[DateStamp, ...]
    shards: int = Field(ge=1, strict=True)

    _valid_dates = field_validator("dates")(_dates)


class Invocation(Model):
    """A transport identity that cannot be resumed by another revision or attempt."""

    run_id: RunId
    attempt: int = Field(ge=1, strict=True)
    git_sha: CommitSha


class Selection(Contract, Invocation):
    """The versioned authorization carried by this invocation's jobs."""

    __schema_stem__: ClassVar[str] = "council-selection"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-05",
            change="Bind selected plugins and widths to one invocation.",
            why="Only explicitly selected work is authorized.",
        ),
    )
    mode: Literal["scheduled", "manual"]
    anchor_date: DateStamp
    window: tuple[DateStamp, ...]
    judges: tuple[SelectedJudge, ...]

    @model_validator(mode="after")
    def valid_selection(self) -> Self:
        _dates(self.window)
        date.fromisoformat(self.anchor_date)
        if self.anchor_date not in self.window:
            raise ValueError("selection window must include its anchor")
        if len({judge.tenant for judge in self.judges}) != len(self.judges):
            raise ValueError("duplicate selected judge")
        for judge in self.judges:
            if judge.status is JudgeLifecycleStatus.RETIRED:
                raise ValueError("retired judges cannot run")
            if not set(judge.dates) <= set(self.window):
                raise ValueError("selected dates exceed the window")
        if self.mode == "scheduled":
            if any(judge.status is not JudgeLifecycleStatus.ACTIVE for judge in self.judges):
                raise ValueError("scheduled selections contain active judges only")
        elif not self.judges or any(judge.dates != (self.anchor_date,) for judge in self.judges):
            raise ValueError("manual selection requires judges and one shared date")
        return self

    @property
    def dates(self) -> tuple[DateStamp, ...]:
        return tuple(sorted({day for judge in self.judges for day in judge.dates}, reverse=True))

    def names(self, *, date: DateStamp | None = None, publish: bool = False) -> tuple[str, ...]:
        return tuple(
            judge.tenant
            for judge in self.judges
            if (date is None or date in judge.dates)
            and (not publish or judge.status is JudgeLifecycleStatus.ACTIVE)
        )

    def check(self, council: CouncilConfig) -> Self:
        if self.version != self.schema_version():
            raise ValueError("invocation selections are not migrated")
        if self.mode == "scheduled":
            anchor = date.fromisoformat(self.anchor_date)
            floor = max(
                date.fromisoformat(council.first_night),
                anchor - timedelta(days=council.repair_window_nights),
            )
            window = (
                self.anchor_date,
                *(
                    (floor + timedelta(days=offset)).isoformat()
                    for offset in range((anchor - floor).days)
                ),
            )
            if anchor < floor or self.window != window:
                raise ValueError("selection window differs from committed bounds")
        for judge in self.judges:
            if council.declaration(judge.tenant).lifecycle_status is not judge.status:
                raise ValueError("selected status differs from its declaration")
            if judge.shards > council.shards:
                raise ValueError("selected width exceeds council width")
            if self.mode == "scheduled":
                JudgeSchedule(dates=judge.dates).check(
                    ScheduleRequest(
                        anchor_date=self.anchor_date,
                        window=self.window,
                        max_dates=council.repair_dates_a_night + 1,
                        max_older_dates=council.repair_dates_a_night,
                        shards=judge.shards,
                        shard_seconds=0,
                    )
                )
        if self.mode == "scheduled" and self.names() != council.running():
            raise ValueError("scheduled selection differs from the active registration")
        return self

    def identify(self, *, run_id: str, attempt: int, git_sha: str) -> Self:
        if (self.run_id, self.attempt, self.git_sha) != (run_id, attempt, git_sha):
            raise ValueError("selection differs from this invocation")
        return self

    def judge(self, name: str, day: str) -> SelectedJudge:
        for judge in self.judges:
            if judge.tenant == name and day in judge.dates:
                return judge
        raise ValueError("judge/date is not authorized")

    def trial(self, name: str) -> bool:
        return any(
            judge.tenant == name and judge.status is JudgeLifecycleStatus.PAUSED
            for judge in self.judges
        )

    @property
    def trials(self) -> tuple[str, ...]:
        return tuple(judge.tenant for judge in self.judges if self.trial(judge.tenant))


class ArtifactFile(Model):
    """One opaque file's relative address and measured bytes."""

    path: RelPath
    size_bytes: int = Field(ge=0, strict=True)
    sha256: Sha256


class PreparationReceipt(Contract, Invocation):
    """Whether one selected plugin/date produced admitted work or bookkeeping."""

    __schema_stem__: ClassVar[str] = "council-preparation"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-05",
            change="Declare preparation readiness and opaque file evidence.",
            why="No work and absent work must remain distinct.",
        ),
    )
    judge_id: Slug
    date: DateStamp
    state: Literal["ready", "no_work", "failed"]
    shards: int = Field(ge=0, strict=True)
    files: tuple[ArtifactFile, ...]
    error: ErrorName | None = None
    where: CodePlace | None = None

    @model_validator(mode="after")
    def valid_state(self) -> Self:
        date.fromisoformat(self.date)
        if (self.state == "ready") != (self.shards > 0):
            raise ValueError("only ready preparation has a positive width")
        if self.state == "ready" and not self.files:
            raise ValueError("ready preparation requires a task file")
        if self.state == "failed" and (self.files or self.error is None):
            raise ValueError("failed preparation admits no files and names its fault")
        if self.state != "failed" and (self.error is not None or self.where is not None):
            raise ValueError("successful preparation cannot name a fault")
        if len({file.path for file in self.files}) != len(self.files):
            raise ValueError("duplicate file destination")
        return self


class ShardFiles(Contract, Invocation):
    """One selected shard's declared files, independent of its reported outcome."""

    __schema_stem__: ClassVar[str] = "council-shard-files"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-05",
            change="Bind opaque shard output files to an invocation and cell.",
            why="Transport cannot authorize another unit's files.",
        ),
    )
    judge_id: Slug
    date: DateStamp
    shard: int = Field(ge=0, strict=True)
    shards: int = Field(ge=1, strict=True)
    files: tuple[ArtifactFile, ...]

    @model_validator(mode="after")
    def valid_part(self) -> Self:
        date.fromisoformat(self.date)
        if self.shard >= self.shards:
            raise ValueError("part index must be below its width")
        if len({file.path for file in self.files}) != len(self.files):
            raise ValueError("duplicate file destination")
        return self


class Cell(Model):
    """One selected job authorized only after matching ready preparation."""

    tenant: Slug
    date: DateStamp
    shard: int = Field(ge=0, strict=True)
    shards: int = Field(ge=1, strict=True)
    runs_model: bool = Field(strict=True)

    @model_validator(mode="after")
    def valid_cell(self) -> Self:
        date.fromisoformat(self.date)
        if self.shard >= self.shards:
            raise ValueError("shard must be below shards")
        return self

    def event_path(self, root: Path) -> Path:
        return root / self.tenant / self.date / f"{self.shard}.jsonl"


ShardReportState = Literal["reported", "refused", "missing", "invalid", "not_dispatched"]


class ShardReport(Model):
    """Normalized complete or unavailable unit/program evidence for one shard."""

    shard: int = Field(ge=0, strict=True)
    shards: int = Field(ge=1, strict=True)
    report_state: ShardReportState
    outcome: ShardOutcome | None = None
    code: CouncilExit | None = None

    @model_validator(mode="after")
    def valid_report(self) -> Self:
        if self.shard >= self.shards:
            raise ValueError("shard must be below shards")
        if self.report_state == "reported" and (self.outcome is None or self.code is None):
            raise ValueError("reported work requires unit and program outcomes")
        if self.report_state != "reported" and self.outcome is not None:
            raise ValueError("unreported work cannot claim a unit outcome")
        return self
