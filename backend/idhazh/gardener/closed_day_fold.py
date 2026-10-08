"""Which closed days and months of a task's CSV day trees become one file each, and what changes?

A CSV day tree files one file per writer: a job writes its own rows at
`<tree>/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` and nothing else
opens that path, which is what lets two jobs push at once. What it costs is
files. Twenty work shards and five runs leave a hundred small files in one day,
and a day nobody will write again keeps them for ever. So once a day is closed,
this reads it through the settlement every reader uses, writes the answer as
`settled.csv`, and deletes the files it read.

**The fold changes no answer.** `day_shards.settled_rows` gives one row per
record whether it reads a hundred writer files or one settled file, so a folded
day and an unfolded day read the same. That is what makes a fold safe to repeat,
safe to skip for a wake, and safe to run live while the window beside it only
reports.

**A day is closed `after_days` whole days after it ends**, the rule
`schedule.is_eligible` holds for a compaction too, measured from 00:00 UTC on the
wake's own day so every wake of one UTC day folds the same days. A writer that
lands in a day after its fold - a re-run reaches back - is folded in at the next
wake, beside the settled file it joins.

**A task may settle a closed month whole** (`fold.settles_months`). A month is
closed `after_days` whole days after its last day ends, and then every file of
it - each day's writer files and settled file - is settled into one
`settled.csv` in the month's own folder, and the files it read are deleted. A
day of a closed month is the month's from then on and is never folded on its
own, and a day a re-run lands in it later is settled in at the next wake. So
such a tree holds one file a closed month plus the open month's days: one file
a month, where it gained one a day, and the readers still see every row.

**Which trees a task folds is read off what it walks**: every CSV day tree whose
root is one of the folders the runner handed the task. A tree no task walks is
folded by nobody.

**The window goes first.** A day folder the window's pass took, or would take on
a dry run, is left to the window, and so is a month holding one: a shard refuses
a path it both writes and deletes, and a day the window is removing needs no
fold.

**A fold lists only its fixed day and month windows.** The task names those
period paths before the fold starts, so the listing cost follows its configured
lookbacks, not every day the tree holds. The names come from the task's listing,
and only the days and months that still hold a file to settle are fetched and
opened, a tree's folders in one fetch.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path

from idhazh import day_partition, day_shards, ledger
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.knobs.gardener import FoldPolicy
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.gardener import error_cause, named_trees, retention_files, schedule
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing


@dataclass(frozen=True, slots=True)
class SettledDay:
    """One day folder a fold settled into one file, and the files that file replaced."""

    tree: LedgerName
    #: The UTC day the folder holds, as `YYYY-MM-DD`.
    day: str
    folder: Path
    replaced: tuple[Path, ...]

    @property
    def settled(self) -> Path:
        """The one file the day holds once the fold is done."""
        return self.folder / day_shards.SETTLED_NAME


@dataclass(frozen=True, slots=True)
class SettledMonth:
    """One closed month a fold settled into one file in its folder, and the files it replaced."""

    tree: LedgerName
    #: The UTC month the folder holds, as `YYYY-MM`.
    month: str
    folder: Path
    replaced: tuple[Path, ...]

    @property
    def settled(self) -> Path:
        """The one file the month holds once the fold is done."""
        return self.folder / day_shards.SETTLED_NAME


@dataclass(frozen=True, slots=True)
class Folded:
    """What one fold settled, or would settle on a dry run, tree by tree and oldest first.

    `fault` says the fold stopped part way, and why: `raised` for a code defect,
    `api-unavailable` when what it fetched did not answer. The months and days
    before the stop are settled on disk all the same, so they are here and they
    land. None when the fold finished.
    """

    dry_run: bool
    days: tuple[SettledDay, ...] = ()
    fault: GardenerFault | None = None
    months: tuple[SettledMonth, ...] = ()

    @property
    def files(self) -> int:
        """How many files the fold replaced, or would replace."""
        return sum(len(month.replaced) for month in self.months) + sum(
            len(day.replaced) for day in self.days
        )


class FoldInterruptedError(Exception):
    """A fold that stopped part way. `so_far` holds the months and days it had already settled.

    Carried rather than bare for the reason `one_at_a_time.PruneInterruptedError`
    gives: the months and days before the failure are already settled on disk,
    and the shard still lands them. `so_far.fault` is what stopped it, as
    `error_cause` reads the error, so a code defect is never read as an outage.
    A dry-run fold settled none of the months and days it named, and its message
    says so.
    """

    def __init__(self, so_far: Folded, where: str) -> None:
        kept = "It was a dry run, so none was settled" if so_far.dry_run else "Those stand"
        super().__init__(
            f"the fold stopped at {where} after {len(so_far.months)} months and "
            f"{len(so_far.days)} days. {kept}, and the next wake starts again from the "
            "oldest still waiting"
        )
        self.so_far = so_far


def trees_walked(context: TaskContext) -> tuple[LedgerName, ...]:
    """Every CSV day tree whose root is one of the folders this task walks, in name order."""
    return tuple(
        sorted(
            (
                tree
                for tree in DAY_TREES
                if retention_files.owned_tree(context, ledger.tree_root(context.state_dir, tree))
                is not None
            ),
            key=lambda tree: tree.value,
        )
    )


def run(context: TaskContext, declared: FoldPolicy, *, skip: Iterable[str]) -> Folded:
    """This task's fold: each closed day or month of the trees it walks, but what its window took.

    `skip` is every repository path the window's pass took, or would take on a
    dry run; a day folder holding one of them is left as it stands, and so is a
    month holding one.
    """
    return fold(
        context.state_dir,
        trees_walked(context),
        now=datetime.combine(context.today, time.min, tzinfo=UTC),
        after_days=declared.after_days,
        dry_run=declared.dry_run,
        settles_months=declared.settles_months,
        skip={(context.repo_root / taken).parent for taken in skip},
        listing=context.listing,
    )


def fold(
    state_dir: Path,
    trees: Iterable[LedgerName],
    *,
    now: datetime,
    after_days: int,
    dry_run: bool,
    settles_months: bool = False,
    skip: Collection[Path] = (),
    listing: FileListing | None = None,
    period_paths: Iterable[Path] | None = None,
) -> Folded:
    """Settle every closed day of these trees that still holds a file other than its settled one.

    `now` is the instant the question is asked at. With `settles_months`, every
    closed month that still holds a day's file is settled whole first, and a day
    of a closed month is left to its month. A day folder in `skip` is left as it
    stands, and so is a month whose own folder, or one of whose day folders, is
    in it. A dry run reads and settles everything it would fold, so a row that
    will not parse stops it the way it would stop a live fold, and it writes and
    deletes nothing.     `listing` is where the names come from. A direct disk caller must name its
    period paths.
    """
    chosen = sorted(trees, key=lambda which: which.value)
    if listing is None:
        if period_paths is None:
            raise ValueError("a fold without a listing requires named period paths")
        roots = [ledger.tree_root(state_dir, tree) for tree in chosen]
        listing = FileListing.from_disk(
            state_dir.parent,
            [root.relative_to(state_dir.parent).as_posix() for root in roots],
            paths=period_paths,
        )
    days_done: list[SettledDay] = []
    months_done: list[SettledMonth] = []
    for tree in chosen:
        root = ledger.tree_root(state_dir, tree)
        where = tree.value
        try:
            key = ledger.segment_key(tree)
            model = ledger.segment_contract(tree)
            waiting = _waiting(
                listing, root, now=now, after_days=after_days, settles_months=settles_months
            )
            month_folders = [(month, root / month[:4] / month[5:7]) for month in waiting.months]
            day_folders = [(day, root / day[:4] / day[5:7] / day[8:10]) for day in waiting.days]
            months = [
                (month, folder)
                for month, folder in month_folders
                if not any(folder in (taken, taken.parent) for taken in skip)
            ]
            days = [(day, folder) for day, folder in day_folders if folder not in skip]
            listing.fetch([folder for _, folder in (*months, *days)])
            for month, folder in months:
                where = f"{tree.value} {month}"
                replaced = _fold_month(root, month, key, model, dry_run=dry_run)
                if replaced:
                    months_done.append(
                        SettledMonth(tree=tree, month=month, folder=folder, replaced=replaced)
                    )
            for day, folder in days:
                where = f"{tree.value} {day}"
                replaced = _fold_day(root, day, key, model, dry_run=dry_run)
                if replaced:
                    days_done.append(
                        SettledDay(tree=tree, day=day, folder=folder, replaced=replaced)
                    )
        except Exception as failure:
            so_far = Folded(
                dry_run=dry_run,
                days=tuple(days_done),
                months=tuple(months_done),
                fault=error_cause.fault_of(error_cause.classify(failure)),
            )
            raise FoldInterruptedError(so_far, where) from failure
    return Folded(dry_run=dry_run, days=tuple(days_done), months=tuple(months_done))


@dataclass(frozen=True, slots=True)
class _Waiting:
    """The closed months and the closed days of one tree that a fold settles, oldest first."""

    months: tuple[str, ...]
    days: tuple[str, ...]


def _waiting(
    listing: FileListing, root: Path, *, now: datetime, after_days: int, settles_months: bool
) -> _Waiting:
    """Every month and day of one tree a fold at `now` settles, read off the listing's names.

    A day waits while it is closed and holds a file besides its settled one.
    With `settles_months`, a closed month waits while it holds any day's file,
    and every day of a closed month is the month's. No file is opened to answer
    it.
    """
    with_a_day: set[str] = set()
    unsettled: dict[str, bool] = {}
    for shard in named_trees.shard_files(listing, root):
        if day_shards.is_month_file(shard):
            continue
        day = day_shards.date_of(shard)
        with_a_day.add(day[:7])
        unsettled[day] = unsettled.get(day, False) or shard.name != day_shards.SETTLED_NAME
    closed = {
        month
        for month in with_a_day
        if settles_months and schedule.is_month_eligible(month, now=now, after_days=after_days)
    }
    return _Waiting(
        months=tuple(sorted(closed)),
        days=tuple(
            day
            for day, waits in unsettled.items()
            if waits
            and day[:7] not in closed
            and schedule.is_eligible(date.fromisoformat(day), now=now, after_days=after_days)
        ),
    )


def _fold_month(
    root: Path,
    month: str,
    key: tuple[str, ...],
    model: type[ledger.CsvContract],
    *,
    dry_run: bool,
) -> tuple[Path, ...]:
    """Fold one closed month of one tree into its folder's settled file. Returns what it replaced.

    The month's settled file, when an earlier fold left one, is read with the
    rest and written again, so a day a re-run added since is settled in. A month
    holding nothing but its settled file is left alone, so a second fold writes
    nothing and makes no diff. The settled file is written before anything goes,
    so the month folder is never empty, and each emptied day folder goes with
    its last file.
    """
    settled = root / month[:4] / month[5:7] / day_shards.SETTLED_NAME
    replaced = tuple(shard for shard in day_shards.one_month(root, month) if shard != settled)
    if not replaced:
        return ()
    rows = day_shards.settled_month(root, month, key, model)
    if dry_run:
        return replaced
    settled.write_text(ledger.render_file(model.csv_columns(), rows), encoding="utf-8", newline="")
    for shard in replaced:
        shard.unlink()
        day_partition.drop_empty_day_dirs(shard)
    return replaced


def _fold_day(
    root: Path,
    day: str,
    key: tuple[str, ...],
    model: type[ledger.CsvContract],
    *,
    dry_run: bool,
) -> tuple[Path, ...]:
    """Fold one closed day of one tree. Returns the files the settled file replaced.

    A day already holding nothing but its settled file is left alone, so a second
    fold of a folded day writes nothing and makes no diff.
    """
    shards = day_shards.one_day(root, day)
    replaced = tuple(shard for shard in shards if shard.name != day_shards.SETTLED_NAME)
    if not replaced:
        return ()
    rows = day_shards.settled_day(root, day, key, model)
    if dry_run:
        return replaced
    settled = shards[0].parent / day_shards.SETTLED_NAME
    settled.write_text(ledger.render_file(model.csv_columns(), rows), encoding="utf-8", newline="")
    for shard in replaced:
        shard.unlink()
    return replaced
