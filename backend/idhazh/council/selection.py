"""Which judges and dates does this invocation authorize, without storing a ledger?"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Literal

from pydantic import field_validator, model_validator

from idhazh.contracts.base import DateStamp, Model, Slug
from idhazh.contracts.knobs.council import CouncilConfig, JudgeLifecycleStatus

# These names describe invocation transport, not persisted fields or tunable policy.
ENVIRONMENT_NAME = "COUNCIL_SELECTION"


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


def for_dates(council: CouncilConfig, dates: tuple[DateStamp, ...]) -> Selection:
    """An explicitly named local date list, without asking about outstanding work."""
    return Selection(
        mode="scheduled",
        judges=tuple(
            SelectedJudge(
                tenant=name,
                status=council.declaration(name).lifecycle_status,
                dates=tuple(dict.fromkeys(dates)),
            )
            for name in council.running()
        ),
    )


def manual(council: CouncilConfig, *, judges: str, day: DateStamp) -> Selection:
    """Validate the entire request before importing even the first selected judge."""
    raw = json.loads(judges)
    if not isinstance(raw, list) or not raw or any(not isinstance(name, str) for name in raw):
        raise ValueError("manual judges must be a nonempty JSON list of names")
    return Selection(
        mode="manual",
        judges=tuple(
            SelectedJudge(
                tenant=name, status=council.declaration(name).lifecycle_status, dates=(day,)
            )
            for name in raw
        ),
    ).check(council)


def from_environment(council: CouncilConfig) -> Selection | None:
    """Absent transport means a local command; present but empty transport is refused."""
    raw = os.environ.get(ENVIRONMENT_NAME)
    if raw is None:
        return None
    try:
        return Selection.model_validate_json(raw).check(council)
    except ValueError as error:
        from idhazh.council.outcome import CouncilExit

        raise SystemExit(CouncilExit.REFUSED) from error
