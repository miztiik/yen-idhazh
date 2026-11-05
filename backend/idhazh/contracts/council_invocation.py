"""Which judges, dates and cells does this invocation authorize?"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import DateStamp, Model, Slug
from idhazh.contracts.knobs.council import CouncilConfig, JudgeLifecycleStatus


class SelectedJudge(Model):
    """One registered judge's explicit status and its own dates."""

    tenant: Slug
    status: JudgeLifecycleStatus
    dates: tuple[DateStamp, ...]

    @field_validator("dates")
    @classmethod
    def valid_dates(cls, dates: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        if not dates or len(set(dates)) != len(dates):
            raise ValueError("selected dates must be nonempty and unique")
        for given in dates:
            date.fromisoformat(given)
        return dates


class Selection(Model):
    """The transient source of truth carried between this workflow's jobs."""

    mode: Literal["scheduled", "manual"]
    judges: tuple[SelectedJudge, ...]

    @model_validator(mode="after")
    def valid_selection(self) -> Selection:
        if len({judge.tenant for judge in self.judges}) != len(self.judges):
            raise ValueError("duplicate selected judge")
        if any(judge.status is JudgeLifecycleStatus.RETIRED for judge in self.judges):
            raise ValueError("retired judges cannot run")
        if self.mode == "scheduled":
            if any(judge.status is not JudgeLifecycleStatus.ACTIVE for judge in self.judges):
                raise ValueError("scheduled selections contain active judges only")
        elif not self.judges or any(len(judge.dates) != 1 for judge in self.judges):
            raise ValueError("manual selections require judges and one date")
        elif len(self.dates) != 1:
            raise ValueError("manual selections must share one date")
        return self

    @property
    def dates(self) -> tuple[DateStamp, ...]:
        """The collector's aggregate, never another judge's work list."""
        return tuple(sorted({day for judge in self.judges for day in judge.dates}, reverse=True))

    def names(self, *, date: DateStamp | None = None, publish: bool = False) -> tuple[str, ...]:
        return tuple(
            judge.tenant
            for judge in self.judges
            if (date is None or date in judge.dates)
            and (not publish or judge.status is JudgeLifecycleStatus.ACTIVE)
        )

    def check(self, council: CouncilConfig) -> Selection:
        """Refuse altered declarations or out-of-bound work before resolving code."""
        for judge in self.judges:
            if council.declaration(judge.tenant).lifecycle_status is not judge.status:
                raise ValueError("selected judge status differs from its declaration")
            if self.mode == "scheduled" and len(judge.dates) > council.repair_dates_a_night + 1:
                raise ValueError("selected dates exceed the repair cap")
        if self.mode == "scheduled" and self.names() != council.running():
            raise ValueError("scheduled selection differs from the active declaration set")
        return self

    def trial(self, name: str) -> bool:
        return any(
            judge.tenant == name and judge.status is JudgeLifecycleStatus.PAUSED
            for judge in self.judges
        )

    @property
    def trials(self) -> tuple[str, ...]:
        return tuple(judge.tenant for judge in self.judges if self.trial(judge.tenant))


class Cell(Model):
    """One planner-selected job whose report must not be inferred from output bytes."""

    tenant: Slug
    date: DateStamp
    shard: int = Field(ge=0, strict=True)
    shards: int = Field(ge=1, strict=True)
    runs_model: bool = Field(strict=True)

    @model_validator(mode="after")
    def valid_cell(self) -> Cell:
        date.fromisoformat(self.date)
        if self.shard >= self.shards:
            raise ValueError("shard must be below shards")
        return self

    def event_path(self, root: Path) -> Path:
        return root / self.tenant / self.date / f"{self.shard}.jsonl"
