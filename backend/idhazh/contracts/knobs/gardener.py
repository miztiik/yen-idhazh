"""What may the gardener delete and rewrite, and how is each of its tasks declared?

Two shapes, and they answer one question at two sizes. `GardenerConfig` is
`config/idhazh_gardener.json`: how many shards a wake splits into, how many
times a shard may try to land its record, and how much one shard may download.
`TaskPolicy` is one file under `config/gardener/`: one task, what it owns and
what it only reads, how far back it keeps, and whether it may delete at all.

**Every default reports and deletes nothing.** A task has no default for
`dry_run`, so a declaration says which it is in so many words. That is the same
promise `RetentionConfig` makes and for the same reason: a fresh clone that
starts deleting on its first run is a clone nobody can try out.

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

from idhazh.contracts.base import DateStamp, Model, RelPath, Slug
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
#: month folders it reads - a month of the scores ledger measured 3.5 MB on
#: 2026-09-30 - so this leaves room for a compaction that catches up on several
#: months at once. Move it to about twice the largest `downloaded_bytes` of the
#: first thirty scheduled wakes.
DEFAULT_MAX_DOWNLOADED_MB: Final = 128


class GardenerConfig(Model):
    """How a wake is split into shards, how hard each tries to land, and how much one may fetch."""

    version: DateStamp = Field(
        description="The UTC day this file's shape was last changed, as YYYY-MM-DD."
    )
    attempts: int = Field(
        ge=1,
        description=(
            "How many times one shard may try to push its commit before it gives up "
            "with exit 3. Each try fetches main again, so a push that lost to another "
            "shard is retried against the new tip. No sleep follows the last try."
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
            "counted. A shard over it still runs its tasks and lands its record, then "
            "exits 1 naming what it downloaded, this ceiling and its three heaviest "
            "folders."
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
    #: Rolls a ledger's raw day files into its daily and monthly periods.
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
    owns: list[RelPath] | None = Field(
        default=None,
        description=(
            "The repository-relative folders this task may delete or write under. A "
            "folder, never a file: a shard checks out folders, so a file here would "
            "match nothing."
        ),
    )
    owns_everything_else_under: list[RelPath] | None = Field(
        default=None,
        description=(
            "The complement form: every folder under these that no other task owns and "
            "no ledger family claims. At most one task may use it."
        ),
    )
    appends_to: list[LedgerName] = Field(
        default_factory=list,
        description=(
            "The ledgers this task files a report of its own into, through the ledger door: "
            "one new raw file under the wake's day, dry run or not. Appending is not "
            "owning. The door names each file afresh, so it cannot overwrite anything, and "
            "the folder it lands in stays with whichever task owns it."
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
    def _one_way_of_owning(self) -> Self:
        if (self.owns is None) == (self.owns_everything_else_under is None):
            raise ValueError(
                "a declaration names exactly one of owns and owns_everything_else_under: "
                "what a task may touch is either a list of folders or everything under a "
                "root that nothing else owns"
            )
        return self

    @model_validator(mode="after")
    def _reads_only_what_it_does_not_own(self) -> Self:
        if self.reads and self.owns is None:
            raise ValueError(
                "a task that owns everything else under a root already lists every folder "
                "there, so it declares no reads"
            )
        for read in self.reads:
            for owned in self.owns or ():
                inner, outer = PurePosixPath(read).parts, PurePosixPath(owned).parts
                if inner[: len(outer)] == outer or outer[: len(inner)] == inner:
                    raise ValueError(
                        f"{read} is in reads and {owned} is in owns, and one is or holds "
                        "the other: a folder a task owns is listed for it already, so "
                        "reads names only folders it does not own"
                    )
        return self

    def claims(self) -> tuple[str, ...]:
        """The folders this declaration names, in either form."""
        return tuple(self.owns if self.owns is not None else self.owns_everything_else_under or ())


#: How many whole days after a UTC day ends before the gardener acts on it. One
#: rule decides when a day is closed, so a fold and a compaction agree about it.
DEFAULT_CLOSED_AFTER_DAYS: Final = 1


class FoldPolicy(Model):
    """When a closed day of a CSV day tree becomes one file, and whether that happens yet.

    A CSV day tree files one file per writer under `YYYY/MM/DD/`, so a busy day
    holds a hundred small files. Once the day is closed, the fold settles them the
    way every reader does and writes that answer as `settled.csv` in their place.
    It changes no answer a reader gets, which is why it has a switch of its own:
    it may run live while the window beside it only reports.
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


class RetentionPolicy(_Declared):
    """A task that deletes what its window has aged out of the trees it owns."""

    kind: Literal[TaskKind.RETENTION]
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
            "settled.csv, after the window has run. Absent on a task that owns no such "
            "tree."
        ),
    )


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


#: The compaction defaults, one line each so a declaration that omits a key and
#: a reader of this file see the same number.
DEFAULT_RAW_INDEX_KEEP_DAYS: Final = 90
DEFAULT_DAILY_KEEP_DAYS: Final = 45
DEFAULT_MONTHLY_WINDOW_MONTHS: Final = 13
DEFAULT_MAX_PERIODS_PER_RUN: Final = 8
DEFAULT_MAX_RAW_FILES_PER_PERIOD: Final = 2000
DEFAULT_COMPACT_AFTER_DAYS: Final = DEFAULT_CLOSED_AFTER_DAYS

#: How many days after a workflow run GitHub still lets it be re-run. A re-run
#: writes into the day its run first wrote, so a month must stay open to it for
#: at least this long. GitHub's number, not a knob: nothing here can move it.
GITHUB_RERUN_DAYS: Final = 30


def _default_monthly_window() -> Window:
    return MonthsWindow(unit="months", value=DEFAULT_MONTHLY_WINDOW_MONTHS)


class CompactionPolicy(_Declared):
    """A task that rolls one ledger's raw files into its daily and monthly periods.

    Its two periods are its retention, so the two keys every other task uses to
    bound what it deletes are fixed here: `window` is `forever` and
    `max_deletes_per_run` is null.
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
    raw_index_keep_days: int = Field(
        default=DEFAULT_RAW_INDEX_KEEP_DAYS,
        ge=1,
        description=(
            "How many days after a UTC day ends its raw listing survives. Never shorter "
            "than daily_keep_days, or a daily file loses the index it would be rebuilt from."
        ),
    )
    daily_keep_days: int = Field(
        default=DEFAULT_DAILY_KEEP_DAYS,
        ge=GITHUB_RERUN_DAYS + 1,
        description=(
            "How many days after a UTC month ends it is absorbed into its monthly file. "
            "The daily period holds between this and 31 days more. At least one more "
            "than the 30 days GitHub allows a re-run, so no re-run lands in a closed month."
        ),
    )
    monthly_window: Window = Field(
        default_factory=_default_monthly_window,
        description=(
            "How long a monthly file survives once its month is absorbed. Month M goes "
            "at the instant month M plus this window is absorbed, so the period holds "
            "exactly this many months, and the ledger reaches back daily_keep_days more."
        ),
    )
    max_periods_per_run: int = Field(
        default=DEFAULT_MAX_PERIODS_PER_RUN,
        ge=1,
        description=(
            "The most days, and separately the most months, one pass compacts before "
            "it stops for the next wake."
        ),
    )
    max_raw_files_per_period: int = Field(
        default=DEFAULT_MAX_RAW_FILES_PER_PERIOD,
        ge=1,
        description="The most raw files one period may be built from in one pass.",
    )
    compact_after_days: int = Field(
        default=DEFAULT_COMPACT_AFTER_DAYS,
        ge=1,
        description=(
            "How many whole days after a UTC day ends before that day may be compacted, "
            "measured from 00:00 UTC on the day after it. Whole days, so every wake of "
            "one UTC day finds the same days eligible."
        ),
    )


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


#: One declaration, validated by the member its `kind` names. A key that belongs
#: to another member is refused by name, because every member forbids extras.
TaskPolicy = Annotated[
    RetentionPolicy | CollectionTaskPolicy | CompactionPolicy | HistoryPolicy,
    Field(discriminator="kind"),
]
