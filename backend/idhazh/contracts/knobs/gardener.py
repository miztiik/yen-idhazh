"""What may the gardener delete and rewrite, and how is each of its tasks declared?

Two shapes, and they answer one question at two sizes. `GardenerConfig` is
`config/idhazh_gardener.json`: how many shards a wake splits into, how many
times a shard may try to land its record, how much one shard may download, and
the first year a ledger can hold.
`TaskPolicy` is one file under `config/gardener/`: one task, what it owns and
what it only reads, how far back it keeps, and whether it may delete at all.

**Every default reports and deletes nothing.** A task has no default for
`dry_run`, so a declaration says which it is in so many words. That is the same
promise `RetentionConfig` makes and for the same reason: a fresh clone that
starts deleting on its first run is a clone nobody can try out.

**A compaction names every setting it runs with.** No setting of a pass has a
default in code, so the declaration a person reads holds every number the pass
uses, and the loader refuses one that leaves a setting out, naming it.

**A declaration names its module by what it is, and never by a path.** Which
Python runs a task is decided by `idhazh.gardener.registry` from the task's
name and its `kind`, both closed words. A config value that named a module to
import would be text from a file choosing code to run (Guardrail #11).

**The collections GitHub holds are not in this repository.** Nothing under
`state/` or `frontend/public/` is a workflow artifact or a workflow run, so no
retention rule over the tree can reach them, which is why they have a
vocabulary of their own here.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Final, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import DateStamp, Model, RelPath, Slug, YearStamp
from idhazh.contracts.ledger_name import LedgerName


class PrunableCollection(StrEnum):
    """Every collection a gardener task may take from, and the word its declaration names.

    A closed vocabulary, so a word outside it is refused with the whole list
    rather than resolved against anything. The same rule `idhazh telemetry
    prune` holds for its ledgers: a deletion whose destination is an arbitrary
    string is a deletion primitive pointed at whatever the file happened to say
    (Guardrail #11).
    """

    #: The files a job uploaded with `actions/upload-artifact`. Each one has its
    #: own bytes and its own id, and deleting one cannot damage another.
    WORKFLOW_ARTIFACTS = "workflow-artifacts"
    #: A whole workflow run and the logs it holds. Deleting one removes the run
    #: from the Actions history, so its age wants to outlive any question
    #: somebody still asks of a failure.
    WORKFLOW_RUNS = "workflow-runs"


# --- config/idhazh_gardener.json ---------------------------------------------


#: The most file content one shard may download for its tasks, in megabytes of
#: 1024 * 1024 bytes. An estimate, not a measurement of a limit (Guardrail #10):
#: a shard checks out only code and config, and a task downloads the day or
#: month folders it reads - a month of the eval ledger measured 3.5 MB on
#: 2026-09-30 - so this leaves room for a compaction that catches up on several
#: months at once. Move it to about twice the largest `downloaded_bytes` of the
#: first thirty scheduled wakes.
DEFAULT_MAX_DOWNLOADED_MB: Final = 128


class GardenerConfig(Model):
    """How a wake is split into shards, how hard each tries to land, and how much one may fetch."""

    version: DateStamp = Field(
        description="The UTC day this file's shape was last changed, as YYYY-MM-DD."
    )
    task_names: tuple[Slug, ...] = Field(
        description=(
            "The complete configured task-name list. Declaration readers open only these "
            "named files and never discover tasks by listing the config directory."
        )
    )
    attempts: int = Field(
        ge=1,
        description=(
            "How many times one shard may try to push its commit. Each try fetches main "
            "again, so a push that lost to another shard is retried against the new tip. "
            "No sleep follows the last try. If every try fails and main did not move, main "
            "refused the push, and the shard exits 3. If main moved, other writers are "
            "landing, and the shard warns and exits 0."
        ),
    )
    shards: int = Field(
        ge=1,
        description=(
            "The most shards one wake splits its tasks into. Fewer run when there are "
            "fewer tasks, so no shard is ever empty."
        ),
    )
    max_downloaded_mb: int = Field(
        default=DEFAULT_MAX_DOWNLOADED_MB,
        ge=1,
        description=(
            "The most file content one shard may download for its tasks, in megabytes "
            "of 1024 * 1024 bytes. The code and config every shard checks out are not "
            "counted. A compaction takes only the periods whose files fit what is left "
            "of it. A shard over it still runs its tasks and lands its record, then "
            "exits 1 naming what it downloaded, this ceiling and its three heaviest "
            "folders."
        ),
    )
    first_ledger_year: YearStamp = Field(
        description=(
            "The UTC year, as YYYY, from which a compaction looks for year and month files "
            "when one of a ledger's indexes is absent and is rebuilt from the files at their "
            "named paths. No ledger holds a row from before it."
        ),
    )

    @model_validator(mode="after")
    def _the_last_shard_has_a_try_left(self) -> Self:
        """Every shard of one wake pushes to the same branch at the same time.

        The shard that lands last has lost a race to every other one first, so
        it needs one try more than there are shards. `attempts - shards` is how
        many pushes from outside the wake, or failed pushes, one wave can absorb,
        and at `attempts == shards` that number is zero.
        """
        if self.attempts <= self.shards:
            raise ValueError(
                f"attempts is {self.attempts} and shards is {self.shards}, and attempts "
                "must be above shards: the shard that lands last loses a race to every "
                "other shard first, so at attempts == shards it has no try left for a "
                "push from outside the wake"
            )
        if len(self.task_names) != len(set(self.task_names)):
            raise ValueError("task_names repeats a task")
        return self


# --- config/gardener/<task>.json ---------------------------------------------


class TaskLifecycleStatus(StrEnum):
    """Whether a task runs. Every status keeps its declaration and its claim on what it owns."""

    #: Runs at every wake.
    ACTIVE = "active"
    #: Does not run, and still owns what it owns, so nothing else may claim it.
    PAUSED = "paused"
    #: Never runs again. The declaration stays as the record of how far back the
    #: tree it owned reached, and its claim stays with it.
    RETIRED = "retired"


class TaskKind(StrEnum):
    """Which member of `TaskPolicy` validates a declaration, and which module may serve it."""

    #: Deletes the files a window has aged out of a tree it owns.
    RETENTION = "retention"
    #: Deletes members of a collection GitHub holds, outside this repository.
    COLLECTION = "collection"
    #: Rolls a ledger's raw day files into its daily and monthly periods, and a
    #: finished year's month files into one yearly file where its declaration asks.
    COMPACTION = "compaction"
    #: Rewrites git history. Run by its own job, never by the matrix.
    HISTORY = "history"


class DaysWindow(Model):
    """Everything older than this many whole days."""

    unit: Literal["days"]
    value: int = Field(
        ge=1,
        description=(
            "Whole days, never zero: a window that includes today would delete what "
            "the running job just wrote."
        ),
    )


class MonthsWindow(Model):
    """Everything older than this many calendar months."""

    unit: Literal["months"]
    value: int = Field(ge=1, description="Whole calendar months, never zero.")


class ForeverWindow(Model):
    """Nothing is ever old enough. A person chose never to delete what this covers."""

    unit: Literal["forever"]


#: How far back a task keeps what it owns. Discriminated on `unit`, so `forever`
#: carries no value at all rather than a number that means never.
Window = Annotated[DaysWindow | MonthsWindow | ForeverWindow, Field(discriminator="unit")]

#: One series of a task that keeps several at once. The same union as `Window`,
#: because both answer "how long do I keep this" and one question has one spelling.
SeriesWindow = Window

#: Default number of earlier periods a scheduled day-grain pass also examines.
DEFAULT_DAY_LOOKBACK_PERIODS: Final = 7
#: Default number of earlier periods a scheduled month-grain pass also examines.
DEFAULT_MONTH_LOOKBACK_PERIODS: Final = 2
#: How many UTC days of its own record a collection task reads for its mark. A
#: wake runs once a day, so a week finds the last pass after six missed wakes.
DEFAULT_MARK_LOOKBACK_DAYS: Final = 7


class _Declared(Model):
    """The keys every declaration carries, whatever its kind."""

    lifecycle_status: TaskLifecycleStatus = Field(
        description="`active` runs, `paused` does not, `retired` never will. No default."
    )
    window: Window = Field(description="How far back this task keeps what it owns.")
    dry_run: bool = Field(
        description=(
            "True reports what a live pass would take and takes nothing. No default, "
            "so a declaration says which it is in so many words."
        )
    )
    max_deletes_per_run: int | None = Field(
        ge=0,
        description=(
            "The most one pass deletes before it stops and names where the next one "
            "starts. Null is no ceiling and 0 is a survey. A collection pruned through "
            "GitHub's API spends one request a delete, so a null ceiling there can use "
            "up the token's hourly allowance on one backlog."
        ),
    )
    owns: list[RelPath] = Field(
        description=(
            "The repository-relative folders this task may delete or write under. A "
            "folder, never a file: a shard lists the files under each folder, so a "
            "file here would list nothing."
        ),
    )
    appends_to: list[LedgerName] = Field(
        default_factory=list,
        description=(
            "The ledgers this task writes into through the ledger door without owning their "
            "folders. A path in written is held to the row's date and lands only on a live "
            "run. A path in appended is a report, held to the wake day, and lands dry run or "
            "not. The door names each file afresh, so it cannot overwrite anything, and the "
            "folder stays with whichever task owns it."
        ),
    )
    reads: list[RelPath] = Field(
        default_factory=list,
        description=(
            "The repository-relative folders this task reads and does not own. Their file "
            "names are listed for it and it may open their files; it never writes or "
            "deletes there. A folder it neither owns nor reads is refused when it asks."
        ),
    )

    @model_validator(mode="after")
    def _reads_only_what_it_does_not_own(self) -> Self:
        for read in self.reads:
            for owned in self.owns:
                inner, outer = PurePosixPath(read).parts, PurePosixPath(owned).parts
                if inner[: len(outer)] == outer or outer[: len(inner)] == inner:
                    raise ValueError(
                        f"{read} is in reads and {owned} is in owns, and one is or holds "
                        "the other: a folder a task owns is listed for it already, so "
                        "reads names only folders it does not own"
                    )
        return self

    def claims(self) -> tuple[str, ...]:
        """The exact folders this declaration names."""
        return tuple(self.owns)

    @property
    def lookback_periods(self) -> int:
        """A non-retention declaration has no period lookback."""
        return 0


#: How many whole days after a UTC day ends before a fold acts on it, where the
#: fold names no number of its own. A compaction writes its own number, as
#: `compact_after_days`, and both are counted by the one rule in `schedule`.
DEFAULT_CLOSED_AFTER_DAYS: Final = 1


class FoldPolicy(Model):
    """When a closed day of a CSV day tree becomes one file, and whether that happens yet.

    A CSV day tree files one file per writer under `YYYY/MM/DD/`, so a busy day
    holds a hundred small files. Once the day is closed, the fold settles them the
    way every reader does and writes that answer as `settled.csv` in their place.
    A task may ask for a closed month to become one file the same way. It changes
    no answer a reader gets, which is why it has a switch of its own: it may run
    live while the window beside it only reports.
    """

    after_days: int = Field(
        default=DEFAULT_CLOSED_AFTER_DAYS,
        ge=1,
        description=(
            "How many whole days after a UTC day ends before its writer files are "
            "folded, measured from 00:00 UTC on the day after it - the rule "
            "compact_after_days reads. Whole days, so every wake of one UTC day folds "
            "the same days."
        ),
    )
    dry_run: bool = Field(
        description=(
            "True reads and settles every day the fold would take and changes nothing. "
            "The fold's own switch, apart from the window's. No default."
        )
    )
    settles_months: bool = Field(
        default=False,
        description=(
            "True also settles each closed month - after_days whole days after its last "
            "day ended - into one settled.csv in the month's own folder, and deletes its "
            "days' files; a day a re-run adds to it later is settled in at the next wake. "
            "False keeps one settled.csv a closed day. A month's file names no day, so a "
            "task whose window counts days may not turn it on."
        ),
    )


class RetentionPolicy(_Declared):
    """A task that deletes what its window has aged out of the trees it owns."""

    kind: Literal[TaskKind.RETENTION]
    lookback: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many earlier periods a scheduled pass checks beyond the period that "
            "just expired. Defaults to 7 days or 2 months."
        ),
    )
    series: dict[Slug, SeriesWindow] | None = Field(
        default=None,
        description=(
            "One window per series, for the one task that keeps several series of one "
            "tree family at different ages. Absent on every other task."
        ),
    )
    fold: FoldPolicy | None = Field(
        default=None,
        description=(
            "Folds each closed day of the CSV day trees this task owns into one "
            "settled.csv, or each closed month where settles_months asks, after the "
            "window has run. Absent on a task that owns no such tree."
        ),
    )

    @property
    def lookback_periods(self) -> int:
        """The configured lookback, or the default for this window's grain."""
        if self.lookback is not None:
            return self.lookback
        if isinstance(self.window, MonthsWindow):
            return DEFAULT_MONTH_LOOKBACK_PERIODS
        if isinstance(self.window, DaysWindow):
            return DEFAULT_DAY_LOOKBACK_PERIODS
        if self.fold is not None:
            return (
                DEFAULT_MONTH_LOOKBACK_PERIODS
                if self.fold.settles_months
                else DEFAULT_DAY_LOOKBACK_PERIODS
            )
        return 0

    @model_validator(mode="after")
    def _a_month_settles_only_where_the_window_keeps_whole_months(self) -> Self:
        """A settled month's file names no day, so a window of days cannot take part of it."""
        settles_months = self.fold is not None and self.fold.settles_months
        if settles_months and isinstance(self.window, DaysWindow):
            raise ValueError(
                f"fold.settles_months is true and the window is {self.window.value} days. A "
                "closed month settled into one file names no day, so a window of days would "
                "take the whole month once its first day aged out, rows it keeps included. "
                "Fold by day here, or keep whole months"
            )
        return self


class CollectionTaskPolicy(_Declared):
    """A task that deletes members of a collection GitHub holds for this repository.

    One module serves every declaration of this kind, so the collection is a typed
    field rather than read off the file's name, and the loader refuses a
    declaration not named for it - which is what keeps one collection to one task,
    because `owns` is empty here and the overlap check has nothing to compare.
    """

    kind: Literal[TaskKind.COLLECTION]
    collection: PrunableCollection = Field(
        description=(
            "The collection this task prunes. The declaration must be called "
            "<collection>.json, so no collection has two windows."
        )
    )
    window: DaysWindow = Field(
        description=(
            "How many whole days a member is kept, counted back from the wake's UTC day. "
            "Days and nothing else: GitHub dates a member by its day, and the pass "
            "counts whole days back from the wake."
        )
    )
    mark_lookback_days: int = Field(
        default=DEFAULT_MARK_LOOKBACK_DAYS,
        ge=1,
        description=(
            "How many UTC days of the gardener's record, today included, a pass reads "
            "to find the day its last pass handled through. With no row in reach it "
            "starts with no mark, which is correct and only slower."
        ),
    )


#: How many days after a workflow run GitHub still lets it be re-run. A re-run
#: writes into the day its run first wrote, so a month must stay open to it for
#: at least this long. GitHub's number, not a knob: nothing here can move it.
GITHUB_RERUN_DAYS: Final = 30

#: The size in bytes over which GitHub warns about a pushed file; it refuses a
#: push holding a file over twice this. GitHub's number, not a knob. A year file
#: over it is refused and its month files are kept, so a ledger that grows never
#: makes every later push fail.
GITHUB_LARGE_FILE_BYTES: Final = 50 * 1024 * 1024

#: The days from the end of a UTC year to the end of its next January. A year is
#: packed only once that January is absorbed, `daily_keep_days` after it ends,
#: and one wake later, because a pass packs years before it absorbs months. So
#: `monthly_keep_days` takes effect only from `daily_keep_days` plus this plus one.
JANUARY_DAYS: Final = 31


class CompactionPolicy(_Declared):
    """A task that rolls one ledger's raw files into its daily and monthly periods.

    Its periods are its retention, so the two keys every other task uses to
    bound what it deletes are fixed here: `window` is `forever` and
    `max_deletes_per_run` is null. A declaration that sets `monthly_keep_days`
    also packs each finished year's month files into one yearly file, kept for
    ever. It has two switches, because packing loses no row and its monthly
    window does: `dry_run` for the whole pass, and `month_deletes_dry_run` for
    what the window deletes, so a ledger can pack live while its window only
    reports.
    """

    kind: Literal[TaskKind.COMPACTION]
    window: ForeverWindow = Field(
        description=(
            "Always forever. How far back the ledger reaches is daily_keep_days and "
            "monthly_window, so a second window here would be a number nothing reads."
        )
    )
    max_deletes_per_run: None = Field(
        description=(
            "Always null. A pass absorbs a period whole or not at all, and a ceiling "
            "could stop it with a month half absorbed."
        )
    )
    ledger: LedgerName = Field(
        description=(
            "The ledger this task compacts. Typed rather than read off the file's name, "
            "and the declaration must be called compact-<ledger>."
        )
    )
    lookback: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many months before the month that holds the newest eligible day, the "
            "newest day at least compact_after_days whole days past its end, a first pass "
            "with no daily mark looks back over for its oldest raw day. Raw days older than "
            "that stay raw. A named range replaces this look-back. Defaults to two months."
        ),
    )
    daily_keep_days: int = Field(
        ge=GITHUB_RERUN_DAYS + 1,
        description=(
            "How many days after a UTC month ends it is absorbed into its monthly file. "
            "The daily period holds between this and 31 days more. At least one more "
            "than the 30 days GitHub allows a re-run, so no re-run lands in a closed month."
        ),
    )
    monthly_window: Window = Field(
        description=(
            "How long a monthly file survives once its month is absorbed. Month M goes "
            "at the instant month M plus this window is absorbed, so the period holds "
            "exactly this many months, and the ledger reaches back daily_keep_days more. "
            "Forever when monthly_keep_days is set: each month file then leaves by being "
            "packed into its year."
        ),
    )
    month_deletes_dry_run: bool = Field(
        description=(
            "True keeps every file monthly_window would delete - each month file past "
            "it and each raw day in a month past it - and packs those days and months "
            "like the rest. The record counts the files kept in selected and not in "
            "deleted, so selected minus deleted is what turning the window live would "
            "take. False lets the window delete them. With dry_run true a pass changes "
            "nothing either way."
        )
    )
    monthly_keep_days: int | None = Field(
        ge=1,
        description=(
            "How many whole days after a UTC year ends, at 00:00 UTC on 1 January, its "
            "month files are packed into one yearly file and deleted. Null packs no year. "
            "Set, it needs monthly_window forever and at least daily_keep_days + 32: a "
            "year is packed only once its next January is absorbed, so no smaller value "
            "changes anything. Year files are kept for ever."
        ),
    )
    max_periods_per_run: int = Field(
        ge=1,
        description=(
            "The most days, and separately the most months and the most years, one pass "
            "compacts, and separately the most months past monthly_window it drops, before "
            "it stops for the next wake."
        ),
    )
    max_raw_files_per_period: int = Field(
        ge=1,
        description=(
            "The most raw files one period may be built from in one pass. A day holding "
            "more packs its oldest that many, and the rest wait for the next wake."
        ),
    )
    compact_after_days: int = Field(
        ge=1,
        description=(
            "How many whole days after a UTC day ends before that day may be compacted, "
            "measured from 00:00 UTC on the day after it. Whole days, so every wake of "
            "one UTC day finds the same days eligible."
        ),
    )
    prune_refusal: str | None = Field(
        min_length=1,
        description=(
            "Whether `idhazh telemetry prune` may take a range of days out of this "
            "ledger. Null lets it. A sentence refuses the ledger, and the command prints "
            "that sentence as the reason. No default, so a declaration says which in so "
            "many words."
        ),
    )

    @property
    def lookback_periods(self) -> int:
        """How many months before the newest eligible day's month a first pass looks back over."""
        return self.lookback or DEFAULT_MONTH_LOOKBACK_PERIODS

    @model_validator(mode="after")
    def _a_year_packs_every_month_it_holds(self) -> Self:
        """Year packing keeps every month file until its year takes it, and waits long enough.

        A monthly window would delete a month file before its year is packed, so the
        year file would miss that month's rows. And a wait shorter than the one the
        next January already imposes would be a number that changes nothing.
        """
        if self.monthly_keep_days is None:
            return self
        if not isinstance(self.monthly_window, ForeverWindow):
            raise ValueError(
                f"monthly_keep_days is {self.monthly_keep_days}, so each finished year's "
                "month files are packed into one year file, and monthly_window is "
                f"{self.monthly_window.value} {self.monthly_window.unit}. It must be "
                "forever: a window would delete a month file before its year is packed, "
                "and the year file would miss that month's rows"
            )
        earliest = self.daily_keep_days + JANUARY_DAYS + 1
        if self.monthly_keep_days < earliest:
            raise ValueError(
                f"monthly_keep_days is {self.monthly_keep_days}, and a year is packed only "
                f"once its next January is absorbed: {self.daily_keep_days} days after that "
                f"January ends, and one wake later, {earliest} days after the year ends. "
                f"Any smaller value changes nothing, so set at least {earliest}"
            )
        return self


class HistoryPolicy(_Declared):
    """The one task that rewrites git history, run by its own job.

    Its window is whole days and nothing else, because the squash cuts history
    at 00:00 UTC on the day `window.value` days back, and a month has no fixed
    number of days to count back by.
    """

    kind: Literal[TaskKind.HISTORY]
    window: DaysWindow = Field(
        description=(
            "How many days of history a squash keeps. At every_days 30 and 60 days the "
            "history holds 60 to 90 days of commits, and the boundary commit and the tip "
            "each hold a whole copy of the corpus."
        )
    )
    every_days: int = Field(
        ge=1,
        description=(
            "How many whole days apart two rewrites of history may run. Each one costs a "
            "force-push of main, the one exception CLAUDE.md section 8 allows."
        ),
    )
    push_attempts: int = Field(
        ge=1,
        description=(
            "How many pushes one run makes in all. A push is refused when main moved "
            "after the run read it, and each refusal is followed by a whole new squash "
            "on the new tip. After the last refusal the run is not recorded, so the "
            "squash is due again at the next daily wake. No default."
        ),
    )
    push_retry_delay_seconds: int = Field(
        ge=0,
        description=(
            "How many seconds a run waits after a refused push before it fetches main "
            "and squashes again. Every wait, and every squash, must fit inside the "
            "history job's timeout. No default."
        ),
    )


#: One declaration, validated by the member its `kind` names. A key that belongs
#: to another member is refused by name, because every member forbids extras.
TaskPolicy = Annotated[
    RetentionPolicy | CollectionTaskPolicy | CompactionPolicy | HistoryPolicy,
    Field(discriminator="kind"),
]
