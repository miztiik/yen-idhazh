"""What a gardener event says: the payload one log line carries, one model per event.

An event is not persisted, so it carries no version or changelog (CLAUDE.md
section 11): it is the structured envelope a step logs (CLAUDE.md section 1b),
and a step may also hand it to the next as its parameters. Every day, month and
year here is a UTC one.

**No field holds text the gardener read.** A period, a member's id, a count,
a closed word, a path the gardener named, and an exception's type and the place
in this package's code it was raised at - never an exception's message, which
can carry a ledger row's text fetched from the open web (Guardrail #11). A
field that holds what came from outside - an id GitHub gave, a count it gave -
takes the value as given, so logging can never stop a pass.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import Field, JsonValue, StringConstraints, model_validator

from idhazh.contracts.base import (
    DateStamp,
    Model,
    MonthStamp,
    PeriodStamp,
    RelPath,
    RunId,
    Slug,
    YearStamp,
)
from idhazh.contracts.collection_prune import MemberId, Recovery, StopReason
from idhazh.contracts.file_envelope import Period, Tier, covers_fits
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.knobs.gardener import PrunableCollection, TaskKind
from idhazh.contracts.ledger_fault import LedgerFault
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.shard_landing import ShardLanding

#: An exception's type name, such as `ValueError`: code, never what it said.
ERROR_TYPE_PATTERN: Final = r"^[A-Za-z_][A-Za-z0-9_]*$"
ErrorType = Annotated[str, StringConstraints(pattern=ERROR_TYPE_PATTERN, max_length=128)]

#: Where in this package's code an exception was raised, as `module:line`.
CODE_PLACE_PATTERN: Final = r"^[A-Za-z_][A-Za-z0-9_.]*:[0-9]+$"
CodePlace = Annotated[str, StringConstraints(pattern=CODE_PLACE_PATTERN, max_length=256)]


class StartReason(StrEnum):
    """Why the periods one compaction step may take start where they do."""

    #: The period after the step's mark, the newest one it has finished.
    MARK = "mark"
    #: The oldest period an index names: where a step with no mark yet starts,
    #: and where the drop step always starts, because the monthly index is its
    #: record of what is left to drop.
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
            "`ceiling` when the cap cut the span short while more was ready, `deferred` when "
            "an operator range starts after the period the step must take first: the step "
            "refuses that period with the fault `range-starts-late`. None when neither."
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
        if self.stopped_because in (StopReason.EXHAUSTED, StopReason.FAILED):
            raise ValueError(
                "a choice stops at the cap or at a range that starts late, never exhausted "
                "and never for a defect"
            )
        if self.stopped_because is StopReason.CEILING and self.first is None:
            raise ValueError("the cap cuts a span short, so a choice stopped by it has one")
        if self.stopped_because is StopReason.DEFERRED and self.first is not None:
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
    drops: StepChoice | None = Field(
        description=(
            "The UTC months the drop step may take: the monthly entries older than the keep "
            "line, oldest first, at most the cap, inside the operator range. The span counts "
            "entries, so a month inside it that the index does not name is not taken. None "
            "when the monthly window keeps every month."
        )
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
        """Each step chooses periods of its own grain, every span runs forward, and lines pair up.

        A declaration that packs years has a year line and a year choice; one that
        packs none has neither. A monthly window that drops months has a keep line
        and a drop choice; one that keeps every month has neither.
        """
        if (self.newest_packable_year is None) != (self.years is None):
            raise ValueError(
                "a year line and a year choice come together: a declaration that packs years "
                "has both, and one that packs none has neither"
            )
        if (self.keep_line is None) != (self.drops is None):
            raise ValueError(
                "a keep line and a drop choice come together: a monthly window that drops "
                "months has both, and one that keeps every month has neither"
            )
        spans = (("an operator range", self.operator_range), ("a re-run span", self.rerun_span))
        for named, span in spans:
            if span is not None and span[0] > span[1]:
                raise ValueError(f"{named} runs forward: {span[0]} comes after {span[1]}")
        for step, grain, period, choice in (
            ("drop", "month", Period.MONTHLY, self.drops),
            ("year", "year", Period.YEARLY, self.years),
            ("month", "month", Period.MONTHLY, self.months),
            ("day", "day", Period.DAILY, self.days),
        ):
            if choice is None:
                continue
            for stamp in (choice.first, choice.last, choice.resume_from):
                if stamp is None:
                    continue
                if not covers_fits(stamp, tier=Tier.COMPACT, period=period):
                    raise ValueError(
                        f"the {step} step chose {stamp!r}, and it chooses UTC {grain}s"
                    )
        return self


class TaskOutcome(StrEnum):
    """How one task ended, in one word a person can act on.

    `report.classify` reads the words in this order and takes the first that
    holds; a pass that found nothing to do ends on the idle word it chose itself.
    """

    #: A code defect stopped the task. The only outcome that turns the job red.
    FAILED = "failed"
    #: A cause outside the code stopped it: GitHub's API did not answer, or a
    #: period waits for a range that starts earlier or for a person. The job
    #: stays green, and the next wake resumes.
    DEFERRED = "deferred"
    #: It found work and only reported it.
    DRY_RUN = "dry-run"
    #: It did work and more is left; `resume_from` says where the next wake starts.
    CEILING = "ceiling"
    #: It did work and nothing is left. What it recovered does not change this.
    DONE = "done"
    #: The ledger holds nothing for any step to work on.
    EMPTY = "empty"
    #: Nothing has reached its line yet: the idle word unless a pass chose another.
    NOT_DUE = "not-due"
    #: A person named a range, and nothing that may be taken is inside it.
    OUTSIDE_RANGE = "outside-range"


class CompactionStep(StrEnum):
    """Which step of a compaction pass a period's event is about."""

    EXPIRE_YEARS = "expire-years"
    DROP_MONTHS = "drop-months"
    PACK_YEARS = "pack-years"
    CLOSE_MONTHS = "close-months"
    REOPEN_MONTHS = "reopen-months"
    PACK_DAYS = "pack-days"


class TaskPlanned(Model):
    """What one task is about to run with, said before it runs."""

    task: Slug = Field(description="The task, as its declaration is named.")
    kind: TaskKind = Field(description="Which kind of task it is.")
    shard: int = Field(ge=0, description="Which shard of the wake runs it.")
    run_id: RunId = Field(description="The run this is.")
    attempt: int = Field(ge=1, description="Which attempt of that run.")
    today: DateStamp = Field(description="The wake's UTC day, which every age is counted from.")
    operator_range: tuple[PeriodStamp, PeriodStamp] | None = Field(
        description=(
            "The first and last UTC day or month a person named for this run, both inside it. "
            "None on a scheduled wake."
        )
    )
    declared: dict[str, JsonValue] = Field(
        description=(
            "Every knob of the task's declaration, as the declaration says it: its windows, "
            "thresholds, ceilings and switches. Not what it owns, reads or appends to, nor "
            "its prose."
        )
    )
    absent: list[str] = Field(
        description=(
            "Folders the declaration names that the commit does not hold yet. Nothing has "
            "written one, so the task lists nothing there."
        )
    )


class WindowChosen(Model):
    """The window one pass holds members to, its ceiling and its mark, said before it lists any."""

    collection: str = Field(min_length=1, description="What the pass takes members of.")
    since: DateStamp | None = Field(description="The oldest UTC day a member may be from.")
    until: DateStamp | None = Field(description="The newest UTC day a member may be from.")
    ceiling: int | None = Field(
        ge=0, description="The most members the pass takes. None is no ceiling; 0 is a survey."
    )
    dry_run: bool = Field(description="Whether the pass only reports what it would take.")
    mark: DateStamp | None = Field(
        description=(
            "The UTC day an earlier pass handled every member through, which this one walks "
            "after. None on a pass that walks no mark."
        )
    )


class MemberOutOfOrder(Model):
    """A walk from a mark met a member from an earlier day than one before it, so the mark stays."""

    collection: str = Field(min_length=1, description="What the pass walks.")
    day: DateStamp = Field(description="The UTC day of the member that came late.")
    after: DateStamp = Field(description="The newest UTC day of a member before it.")


class PageOutOfOrder(Model):
    """A page holds a member from a day before one on a page read earlier, so every page is read."""

    collection: str = Field(min_length=1, description="What the walk reads.")
    page: int = Field(ge=1, description="The page, as the collection numbers them.")


class PageCountChanged(Model):
    """A page counted other than the first page less the walk's deletes, so the mark stays."""

    collection: str = Field(min_length=1, description="What the walk reads.")
    page: int = Field(ge=1, description="The page, as the collection numbers them.")
    counted: int = Field(description="What that page says the collection holds.")
    expected: int = Field(description="The first page's count less what this walk deleted.")


class ListEndMissing(Model):
    """The list does not end where the first page's count says, so the mark stays."""

    collection: str = Field(min_length=1, description="What the walk reads.")
    page: int = Field(ge=1, description="The page the count says is the last.")
    first_count: int = Field(description="What the first page says the collection holds.")


class ExpiredYearsChosen(Model):
    """Which expired UTC years the yearly expiry takes on this wake, said before it takes any."""

    ledger: LedgerName = Field(description="The ledger the compaction packs.")
    years: list[YearStamp] = Field(
        description=(
            "The expired indexed UTC years this pass takes, oldest first: at most "
            "`max_periods_per_run`, and only whole years inside an operator range. A live pass "
            "deletes each year's files and its entry; a dry run only names them. Empty when no "
            "year is due."
        )
    )


class PeriodRefused(Model):
    """A period a compaction step will not take, and why, in words.

    `fault` is the word the task's record carries; `ledger_fault` is the
    ledger's own word for a file it is missing, the one the query door and the
    ledger reader use. A refusal our own code made has no `error`; one an
    exception made names its type and where it was raised.
    """

    ledger: LedgerName = Field(description="The ledger the compaction packs.")
    step: CompactionStep = Field(description="The step that refused the period.")
    period: PeriodStamp = Field(description="The UTC day, month or year refused.")
    fault: GardenerFault = Field(description="Why, as the task's record says it.")
    ledger_fault: LedgerFault | None = Field(
        default=None, description="The file the ledger is missing, when that is why."
    )
    error: ErrorType | None = Field(
        default=None, description="The type of the exception that refused it, if one did."
    )
    where: CodePlace | None = Field(
        default=None, description="Where in this package's code that exception was raised."
    )


class DownloadOverBudget(Model):
    """A compaction step stopped where what it would download no longer fits the shard's budget."""

    ledger: LedgerName = Field(description="The ledger the compaction packs.")
    resume_from: MemberId = Field(
        description=(
            "The period the step stopped at, or the index folder when the marks alone do "
            "not fit."
        )
    )
    needed_bytes: int = Field(description="What fetching that period downloads.")
    room_bytes: int = Field(description="What was left of the shard's budget.")
    max_downloaded_mb: int = Field(description="The shard's whole budget, in MB.")
    stopped_because: StopReason = Field(
        description=(
            "`ceiling` when a later wake has room for it; `failed` when it is larger than "
            "the whole budget, which only a person can raise."
        )
    )

    @model_validator(mode="after")
    def _a_budget_stops_at_the_ceiling_or_fails(self) -> Self:
        if self.stopped_because not in (StopReason.CEILING, StopReason.FAILED):
            raise ValueError("a download over the budget stops at the ceiling or fails")
        return self


class LedgerFaultMet(Model):
    """A ledger fault a compaction step met and went on past: a dropped month's file was gone."""

    ledger: LedgerName = Field(description="The ledger the compaction packs.")
    step: CompactionStep = Field(description="The step that met it.")
    period: PeriodStamp = Field(description="The UTC period it is about.")
    ledger_fault: LedgerFault = Field(description="The ledger's own word for what is missing.")


class RawFileSkipped(Model):
    """A file under a ledger's raw folder that sits in no UTC day folder, so no step reads it."""

    path: str = Field(min_length=1, description="The file, relative to the repository.")


class PeriodsTaken(Model):
    """What one compaction pass did, period by period, and how far each mark reached.

    An entry the pass adopted from a packed file is listed under its state, as
    one it packed; the task's `recovered` says how it got there. A dry run lists
    what a live pass would do.
    """

    days_packed: list[DateStamp] = Field(
        description="UTC days no entry named before, now `packed`: packed, or adopted."
    )
    days_retaken: list[DateStamp] = Field(
        description="Packed UTC days written again, because raw files landed in them."
    )
    months_closed: list[MonthStamp] = Field(
        description="UTC months no entry named before, now `packed` into a month file."
    )
    years_packed: list[YearStamp] = Field(
        description="UTC years no entry named before, now `packed` into a year file."
    )
    months_dropped: list[MonthStamp] = Field(
        description=(
            "UTC months the monthly window dropped, or named and kept while its deletes only "
            "report."
        )
    )
    raw_days_dropped: list[DateStamp] = Field(
        description="Raw UTC days past the keep line dropped by their paths, or named and kept."
    )
    empty_periods: list[PeriodStamp] = Field(
        description="Periods no entry named before, now `empty`: looked at, with no row."
    )
    lost_days: list[DateStamp] = Field(
        description=(
            "UTC days the pass recorded lost: an entry written `lost`, or a day a month's or "
            "year's entry newly lists in `lost_days`."
        )
    )
    set_aside_paths: list[str] = Field(
        description="Files moved to the set-aside folder, by the path each one had."
    )
    daily_mark: DateStamp | None = Field(description="The newest UTC day packed after the pass.")
    monthly_mark: MonthStamp | None = Field(
        description="The newest UTC month closed after the pass."
    )
    yearly_mark: YearStamp | None = Field(description="The newest UTC year packed after the pass.")


class TaskFinished(Model):
    """How one task ended, what it took and wrote, and what the next wake does."""

    task: Slug = Field(description="The task, as its declaration is named.")
    outcome: TaskOutcome = Field(description="How it ended, in one word.")
    dry_run: bool = Field(description="Whether the task only reported what it would take.")
    seen: int = Field(ge=0, description="Members or files the pass read or weighed.")
    selected: int = Field(ge=0, description="Members or files the window held.")
    collection: PrunableCollection | None = Field(
        default=None,
        description=(
            "The GitHub collection a collection task takes members of, which says what "
            "`taken` holds: that collection's member ids. None when `taken` holds files."
        ),
    )
    taken: list[str] = Field(
        description=(
            "What the pass deleted, or would delete on a dry run: member ids, or files "
            "relative to the repository."
        )
    )
    written: list[str] = Field(
        description="Files the pass wrote, or would write on a dry run, relative to the repository."
    )
    bytes_freed: int = Field(ge=0, description="What the deletes free, or would.")
    stopped_because: StopReason = Field(description="Why the pass stopped.")
    resume_from: MemberId | None = Field(
        default=None, description="Where the next pass starts, when this one stopped short."
    )
    handled_through: DateStamp | None = Field(
        default=None,
        description="The newest UTC day a walk from a mark handled every member through.",
    )
    fault: GardenerFault | None = Field(
        default=None, description="Why a fault stopped the task. None when none did."
    )
    error: ErrorType | None = Field(
        default=None, description="The type of the exception that stopped the task, if one did."
    )
    where: CodePlace | None = Field(
        default=None, description="Where in this package's code that exception was raised."
    )
    recovered: list[Recovery] = Field(
        description="Each fault the pass recorded instead of stopping, in the order it met them."
    )
    next: str = Field(min_length=1, description="What happens next, for a person.")
    pages_read: int | None = Field(
        default=None, ge=0, description="Pages the listing read. None for a listing with no pages."
    )
    duration_ms: int = Field(ge=0, description="How long the task ran.")
    periods: PeriodsTaken | None = Field(
        default=None, description="What a compaction did, period by period. None for other tasks."
    )


class ShardStop(StrEnum):
    """Why one shard stopped before its commit came to rest on main, in one word."""

    #: The files under the shard's folders could not be listed from its commit,
    #: so no task ran and nothing landed. The next wake tries again.
    LISTING_FAILED = "listing-failed"
    #: An ownership or integrity check refused the shard, before its tasks ran or
    #: after. Nothing landed, and a person fixes the cause.
    CHECK_REFUSED = "check-refused"
    #: An exception escaped the publisher, so it cannot say what ran or landed.
    CRASHED = "crashed"


class ShardPublished(Model):
    """How one shard ended: the publisher's last word on it, whether or not anything landed.

    Said once a shard, after its push loop or where the shard stopped short of
    one. `landing` names how the shard's commit came to rest on main, and
    `stopped_because` why it never came to rest; exactly one of the two is set.
    """

    shard: int = Field(ge=0, description="Which shard of the wake this is.")
    run_id: RunId = Field(description="The run this is.")
    attempt: int = Field(ge=1, description="Which attempt of that run.")
    tasks: list[Slug] = Field(description="The tasks the shard was to run, in the order they run.")
    failed_tasks: list[Slug] = Field(
        description="The tasks whose row says `failed`: a code defect stopped each one."
    )
    landing: ShardLanding | None = Field(
        default=None,
        description="How the shard's commit came to rest on main. None when it stopped first.",
    )
    stopped_because: ShardStop | None = Field(
        default=None,
        description="Why the shard stopped before its commit came to rest. None when it did.",
    )
    push_try: int | None = Field(
        default=None,
        ge=1,
        description=(
            "The try the commit came to rest on, counted from 1: each try fetches main "
            "again. Set exactly when `landing` is."
        ),
    )
    push_tries: int = Field(
        ge=1, description="The most tries the publisher takes: `attempts` in its config."
    )
    record: RelPath | None = Field(
        default=None,
        description="The record the shard wrote, relative to the repository. None before one.",
    )
    stale_paths: list[RelPath] = Field(
        default_factory=list,
        description=(
            "The shard's paths main changed after the commit the shard ran on, sorted. "
            "They are why nothing landed, so they are listed exactly when `landing` is "
            "`stale`."
        ),
    )
    downloaded_bytes: int | None = Field(
        default=None,
        ge=0,
        description="What the shard's tasks downloaded to read. None when nothing measured it.",
    )
    over_budget: bool = Field(
        default=False,
        description=(
            "Whether that passed `max_downloaded_mb`. A step that chooses its periods by "
            "the budget never passes it, so a shard over it is a code defect."
        ),
    )
    max_downloaded_mb: int = Field(
        ge=1, description="The shard's download budget, in MB of 1024 x 1024 bytes."
    )
    exit_code: int = Field(ge=0, description="The code the shard exits with.")
    means: str = Field(min_length=1, description="What that exit code means, for a person.")
    error: ErrorType | None = Field(
        default=None,
        description=(
            "The type of the exception that stopped the shard before it could land: the "
            "listing that failed, or one that escaped the publisher. Never its text."
        ),
    )
    where: CodePlace | None = Field(
        default=None, description="Where in this package's code that exception was raised."
    )

    @model_validator(mode="after")
    def _a_shard_either_came_to_rest_or_says_why_it_did_not(self) -> Self:
        """One of the two words, the try beside a landing, and the paths beside a stale one."""
        if (self.landing is None) == (self.stopped_because is None):
            raise ValueError("a shard came to rest on main or says why it did not, never both")
        if self.landing is not None and self.record is None:
            raise ValueError("a commit that came to rest on main carries the shard's record")
        if (self.landing is None) != (self.push_try is None):
            raise ValueError("a landing names the try it came to rest on, and only a landing")
        if self.push_try is not None and self.push_try > self.push_tries:
            raise ValueError(f"try {self.push_try} is past the {self.push_tries} tries allowed")
        if bool(self.stale_paths) != (self.landing is ShardLanding.STALE):
            raise ValueError("the paths main changed are listed exactly when the shard is stale")
        thrown = self.stopped_because in (ShardStop.LISTING_FAILED, ShardStop.CRASHED)
        if (self.error is not None) != thrown:
            raise ValueError(
                "an exception's type is named exactly when a listing failed or a crash stopped "
                "the shard"
            )
        if self.where is not None and self.error is None:
            raise ValueError("a place in the code is named only beside the exception's type")
        if self.over_budget and self.downloaded_bytes is None:
            raise ValueError("a shard over its budget says what it downloaded")
        return self


class LoggedText(Model):
    """A line a module outside the gardener logged as text while a task ran, kept as it was said."""

    logger: str = Field(description="The logger that said it.")
    message: str = Field(description="What it said.")
    error: ErrorType | None = Field(
        default=None, description="The type of the exception it logged, if any; never its text."
    )
    where: CodePlace | None = Field(
        default=None, description="Where in this package's code that exception was raised."
    )
