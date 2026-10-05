"""What a gardener event says: the payload one log line carries, one model per event.

An event is not persisted, so it carries no version or changelog (CLAUDE.md
section 11): it is the structured envelope a step logs (CLAUDE.md section 1b),
and a step may also hand it to the next as its parameters. Every day, month and
year here is a UTC one.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from idhazh.contracts.base import DateStamp, Model, MonthStamp, PeriodStamp, YearStamp
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, Tier, covers_fits
from idhazh.contracts.ledger_name import LedgerName


class StartReason(StrEnum):
    """Why the periods one compaction step may take start where they do."""

    #: The period after the step's mark, the newest one it has finished.
    MARK = "mark"
    #: The oldest period an index names, because the step has no mark yet.
    OLDEST_INDEXED = "oldest-indexed"
    #: The oldest raw day in the months a first day run looks in, because the
    #: step has no mark yet.
    OLDEST_RAW_DAY = "oldest-raw-day"
    #: The keep line: the oldest raw day of a first day run falls in a month the
    #: monthly window no longer keeps while its deletes are live, so the step
    #: starts at the oldest raw day the window keeps, or takes nothing.
    KEEP_LINE = "keep-line"
    #: An operator's range decided it: the range ends before the step's first
    #: period, it leaves out the period the step must take first, or it holds
    #: no whole period at the step's grain.
    OPERATOR_RANGE = "operator-range"
    #: The ledger holds nothing for the step to start from.
    NONE = "none"


class StepChoice(Model):
    """The periods one compaction step may take on this wake, where they start, and why."""

    start: StartReason = Field(description="Why the step's periods start where they do.")
    first: PeriodStamp | None = Field(
        default=None,
        description="The first UTC period the step may take. None when it may take none.",
    )
    last: PeriodStamp | None = Field(
        default=None,
        description="The last UTC period the step may take, the same shape as `first`.",
    )
    stopped_because: StopReason | None = Field(
        default=None,
        description=(
            "`ceiling` when the cap cut the span short while more was ready, `failed` when "
            "an operator range leaves out the period the step must take first. None when "
            "neither."
        ),
    )
    resume_from: PeriodStamp | None = Field(
        default=None,
        description=(
            "The UTC period the step takes next: the first one past the cap, or the one the "
            "operator range leaves out. Set exactly when `stopped_because` is."
        ),
    )

    @model_validator(mode="after")
    def _a_span_has_two_ends_and_a_stop_says_where_to_resume(self) -> Self:
        """A span is both ends or none, and a stop names the period the step takes next."""
        if (self.first is None) != (self.last is None):
            raise ValueError("a span names its first and its last period, or neither")
        if self.first is not None and self.last is not None and self.first > self.last:
            raise ValueError(f"a span runs forward: {self.first} comes after {self.last}")
        if (self.stopped_because is None) != (self.resume_from is None):
            raise ValueError("a choice that stops names where the step resumes, and only then")
        if self.stopped_because is StopReason.EXHAUSTED:
            raise ValueError("a choice stops at the cap or at a refusal, not at an exhausted list")
        if self.stopped_because is StopReason.CEILING and self.first is None:
            raise ValueError("the cap cuts a span short, so a choice stopped by it has one")
        if self.stopped_because is StopReason.FAILED and self.first is not None:
            raise ValueError("a refused choice takes nothing, so it has no span")
        return self


class PeriodsChosen(Model):
    """Which periods each compaction step may take on this wake, and what decided it.

    Chosen before the steps run, from the ledger's own marks, the wake's UTC day
    and the declaration, and for a first day run from the raw days the pass named
    in the months it looks back over - never from folders a planner named for
    another step. Each step takes its own choice as its parameters, and the pass
    logs the whole once.
    """

    ledger: LedgerName = Field(description="The ledger the compaction packs.")
    daily_mark: DateStamp | None = Field(
        description="The newest UTC day the day step has packed, or None before its first."
    )
    monthly_mark: MonthStamp | None = Field(
        description="The newest UTC month the month step has closed, or None before its first."
    )
    yearly_mark: YearStamp | None = Field(
        description="The newest UTC year the year step has packed, or None before its first."
    )
    newest_eligible_day: DateStamp = Field(
        description=(
            "The newest UTC day at least `compact_after_days` whole days past its end, at "
            "00:00 UTC on the wake's day."
        )
    )
    newest_closable_month: MonthStamp = Field(
        description=(
            "The newest UTC month at least `daily_keep_days` whole days past its end, at "
            "00:00 UTC on the wake's day."
        )
    )
    keep_line: MonthStamp | None = Field(
        description=(
            "The oldest UTC month the monthly window keeps at 00:00 UTC on the wake's day, "
            "or None when it keeps every month."
        )
    )
    newest_packable_year: YearStamp | None = Field(
        description=(
            "The newest UTC year at least `monthly_keep_days` whole days past its end, at "
            "00:00 UTC on the wake's day. None when the declaration packs no year."
        )
    )
    cap: int = Field(
        ge=1, description="`max_periods_per_run`: the most periods one step takes on this wake."
    )
    operator_range: tuple[MonthStamp, MonthStamp] | None = Field(
        description=(
            "The first and last UTC month a person named for this run, which limits every "
            "step. None on a scheduled wake."
        )
    )
    month_deletes_dry_run: bool = Field(
        description="Whether the monthly window's deletes only report on this wake."
    )
    years: StepChoice | None = Field(
        description=(
            "The UTC years the year step may pack. An operator range limits them to the whole "
            "calendar years it holds. None when the declaration packs no year."
        )
    )
    months: StepChoice = Field(description="The months the month step may close.")
    days: StepChoice = Field(
        description=(
            "The new UTC days after the daily mark the day step may pack, at most. A day it "
            "takes again counts against the same cap, so when those use it up the step's own "
            "stop names the day the next wake starts at."
        )
    )
    rerun_span: tuple[DateStamp, DateStamp] | None = Field(
        description=(
            "The first and last packed UTC day whose raw folders the day step names, because "
            "a GitHub re-run may still write into them: from `GITHUB_RERUN_DAYS` days before "
            "the wake's day to the daily mark, inside the operator range. None when no packed "
            "day is that recent."
        )
    )

    @model_validator(mode="after")
    def _each_step_chooses_its_own_grain_and_every_span_runs_forward(self) -> Self:
        """Each step chooses periods of its own grain, every span runs forward, and years pair up.

        A declaration that packs years has a year line and a year choice; one that
        packs none has neither.
        """
        if (self.newest_packable_year is None) != (self.years is None):
            raise ValueError(
                "a year line and a year choice come together: a declaration that packs years "
                "has both, and one that packs none has neither"
            )
        spans = (("an operator range", self.operator_range), ("a re-run span", self.rerun_span))
        for named, span in spans:
            if span is not None and span[0] > span[1]:
                raise ValueError(f"{named} runs forward: {span[0]} comes after {span[1]}")
        for step, period, choice in (
            ("year", Period.YEARLY, self.years),
            ("month", Period.MONTHLY, self.months),
            ("day", Period.DAILY, self.days),
        ):
            if choice is None:
                continue
            for stamp in (choice.first, choice.last, choice.resume_from):
                if stamp is None:
                    continue
                if not covers_fits(stamp, tier=Tier.COMPACT, period=period):
                    raise ValueError(
                        f"the {step} step chose {stamp!r}, and it chooses UTC {step}s"
                    )
        return self
