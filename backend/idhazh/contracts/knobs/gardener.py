"""What may the gardener delete and rewrite, and how is each of its tasks declared?

Three shapes, and they answer one question at three sizes. `GardenerConfig` is
`config/idhazh_gardener.json`: how many shards a wake splits into and how many
times a shard may try to land its record. `TaskPolicy` is one file under
`config/gardener/`: one task, what it owns, how far back it keeps, and whether
it may delete at all. `PruneConfig` is the `prune` block of `config/idhazh.json`
that `backend/utilities/prune_artifacts.py` reads for a pass an operator runs
by hand over the collections GitHub holds.

**Every default reports and deletes nothing.** A task has no default for
`dry_run`, so a declaration says which it is in so many words, and the `prune`
block ships `dry_run: true`. That is the same promise `RetentionConfig` makes
and for the same reason: a fresh clone that starts deleting on its first run is
a clone nobody can try out.

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
from typing import Annotated, Final, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import DateStamp, Model, RelPath, Slug
from idhazh.contracts.ledger_name import LedgerName


class PrunableCollection(StrEnum):
    """Every collection a pass may take from, and the word an operator types.

    A closed vocabulary, so a word outside it is refused with the whole list
    rather than resolved against anything. The same rule `idhazh telemetry
    prune` holds for its ledgers: a deletion command whose destination is an
    arbitrary string is a deletion primitive pointed at whatever the caller
    happened to pass (Guardrail #11).
    """

    #: The files a job uploaded with `actions/upload-artifact`. Each one has its
    #: own bytes and its own id, and deleting one cannot damage another.
    WORKFLOW_ARTIFACTS = "workflow-artifacts"
    #: A whole workflow run and the logs it holds. Deleting one removes the run
    #: from the Actions history, so its age wants to outlive any question
    #: somebody still asks of a failure.
    WORKFLOW_RUNS = "workflow-runs"


#: How many members one pass takes when a collection names no ceiling of its
#: own. An estimate and not a measurement (Guardrail #10): each delete is one
#: REST call, and GitHub publishes no number for how many deletes a minute it
#: will accept before it applies a secondary rate limit. Fifty is chosen to sit
#: far under any plausible burst limit and to finish inside a step nobody is
#: waiting on. What would settle it is a run that deletes in a loop until the
#: API answers 403 with a `Retry-After` header, and reads the count off that.
DEFAULT_CEILING: Final = 50


class CollectionPolicy(Model):
    """One collection's line: how old a member must be, and how many go in a pass."""

    retain_days: int = Field(
        ge=1,
        description=(
            "How many days a member is kept before a pass may take it. Whole days and "
            "never zero: a window that includes today would delete the artifact the "
            "running job just uploaded."
        ),
    )
    max_deletes_per_run: int = Field(
        default=DEFAULT_CEILING,
        ge=0,
        description=(
            "The ceiling. One pass deletes at most this many and then stops cleanly, "
            "naming where the next pass resumes. 0 surveys: it reports the first "
            "member the window holds and deletes nothing, which is how an operator "
            "sees what a window selects without committing to a number."
        ),
    )


def default_collections() -> dict[PrunableCollection, CollectionPolicy]:
    """Both collections, with a line drawn for each, taking nothing until dry_run is off.

    The two ages differ because the two questions differ. An artifact is bytes a
    job wrote for the next job, and once the run that produced it is read there
    is nothing left to ask of it. A run is the record that the work happened,
    and somebody reading a regression three months later still wants it.
    """
    return {
        PrunableCollection.WORKFLOW_ARTIFACTS: CollectionPolicy(retain_days=30),
        PrunableCollection.WORKFLOW_RUNS: CollectionPolicy(retain_days=90),
    }


class PruneConfig(Model):
    """The collections a pass may take from, and whether it may take anything at all."""

    dry_run: bool = Field(
        default=True,
        description=(
            "Report what a live pass would delete and delete nothing. True by default, "
            "so a fresh clone removes nothing it was not asked twice for. The CLI's "
            "--no-dry-run is the second word."
        ),
    )
    collections: dict[PrunableCollection, CollectionPolicy] = Field(
        default_factory=default_collections,
        description=(
            "One policy per collection this may be pointed at. A collection absent "
            "from this map is refused by name: the vocabulary says the word exists and "
            "the map says whether this repository has drawn a line for it."
        ),
    )


# --- config/idhazh_gardener.json ---------------------------------------------


class GardenerConfig(Model):
    """How a wake is split into shards, and how hard each shard tries to land its record."""

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

    @model_validator(mode="after")
    def _one_way_of_owning(self) -> Self:
        if (self.owns is None) == (self.owns_everything_else_under is None):
            raise ValueError(
                "a declaration names exactly one of owns and owns_everything_else_under: "
                "what a task may touch is either a list of folders or everything under a "
                "root that nothing else owns"
            )
        return self

    def claims(self) -> tuple[str, ...]:
        """The folders this declaration names, in either form."""
        return tuple(self.owns if self.owns is not None else self.owns_everything_else_under or ())


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


class CollectionTaskPolicy(_Declared):
    """A task that deletes members of a collection GitHub holds for this repository.

    Not `CollectionPolicy`: that name is the `prune` block's per-collection line,
    which the hand-run utility still reads.
    """

    kind: Literal[TaskKind.COLLECTION]


#: The compaction defaults, one line each so a declaration that omits a key and
#: a reader of this file see the same number.
DEFAULT_RAW_INDEX_KEEP_DAYS: Final = 90
DEFAULT_DAILY_KEEP_DAYS: Final = 45
DEFAULT_MONTHLY_WINDOW_MONTHS: Final = 13
DEFAULT_MAX_PERIODS_PER_RUN: Final = 8
DEFAULT_MAX_RAW_FILES_PER_PERIOD: Final = 2000
DEFAULT_COMPACT_AFTER_HOURS: Final = 24


def _default_monthly_window() -> Window:
    return MonthsWindow(unit="months", value=DEFAULT_MONTHLY_WINDOW_MONTHS)


class CompactionPolicy(_Declared):
    """A task that rolls one ledger's raw files into its daily and monthly periods."""

    kind: Literal[TaskKind.COMPACTION]
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
            "How long one raw day's listing survives. Never shorter than daily_keep_days, "
            "or a daily file loses the index it would be rebuilt from."
        ),
    )
    daily_keep_days: int = Field(
        default=DEFAULT_DAILY_KEEP_DAYS,
        ge=1,
        description=(
            "How old every day of a month must be before the month is absorbed into its "
            "monthly file. The daily period holds between this and 31 days more."
        ),
    )
    monthly_window: Window = Field(
        default_factory=_default_monthly_window,
        description=(
            "How long a monthly file survives. With daily_keep_days it is how far back "
            "the ledger reaches once it files this way."
        ),
    )
    max_periods_per_run: int = Field(
        default=DEFAULT_MAX_PERIODS_PER_RUN,
        ge=1,
        description="The most periods one pass compacts before it stops for the next wake.",
    )
    max_raw_files_per_period: int = Field(
        default=DEFAULT_MAX_RAW_FILES_PER_PERIOD,
        ge=1,
        description="The most raw files one period may be built from in one pass.",
    )
    compact_after_hours: int = Field(
        default=DEFAULT_COMPACT_AFTER_HOURS,
        ge=1,
        description=(
            "How many whole hours after a UTC day ends before that day may be compacted, "
            "measured from 00:00 UTC on the day after it."
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
