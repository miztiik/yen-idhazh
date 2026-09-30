"""Which closed days of a task's CSV day trees become one file each, and what does that change?

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

**Which trees a task folds is read off what it walks**: every CSV day tree whose
root is one of the folders the runner handed the task. A tree no task walks is
folded by nobody.

**The window goes first.** A day folder the window's pass took, or would take on
a dry run, is left to the window: a shard refuses a path it both writes and
deletes, and a day the window is removing needs no fold.

**Listing a tree reads every day folder's name it holds.** The question is
which days still hold a writer file, and no bounded input answers it, so the
cost of the listing grows with the tree (Guardrail #12,
`docs/concepts/growing-reads.md`). The names come from the task's listing, and
only the days that still hold a writer file are fetched and opened, a tree's
days in one fetch.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path

from idhazh import day_shards, ledger
from idhazh.contracts.knobs.gardener import FoldPolicy
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.gardener import named_trees, retention_files, schedule
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
class Folded:
    """What one fold settled, or would settle on a dry run, tree by tree and oldest day first.

    `failed` says the fold stopped part way. The days before the stop are settled
    on disk all the same, so they are here and they land.
    """

    dry_run: bool
    days: tuple[SettledDay, ...] = ()
    failed: bool = False

    @property
    def files(self) -> int:
        """How many files the fold replaced, or would replace."""
        return sum(len(day.replaced) for day in self.days)


class FoldInterruptedError(Exception):
    """A fold that stopped part way. `so_far` holds the days it had already settled.

    Carried rather than bare for the reason `one_at_a_time.PruneInterruptedError`
    gives: the days before the failure are already settled on disk, and the
    shard still lands them.
    """

    def __init__(self, so_far: Folded, where: str) -> None:
        super().__init__(
            f"the fold stopped at {where} after settling {len(so_far.days)} days. Those "
            "stand, and the next wake starts again from the oldest day still waiting"
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
    """This task's fold: every closed day of the trees it walks, but the days its window took.

    `skip` is every repository path the window's pass took, or would take on a
    dry run; a day folder holding one of them is left as it stands.
    """
    return fold(
        context.state_dir,
        trees_walked(context),
        now=datetime.combine(context.today, time.min, tzinfo=UTC),
        after_days=declared.after_days,
        dry_run=declared.dry_run,
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
    skip: Collection[Path] = (),
    listing: FileListing | None = None,
) -> Folded:
    """Settle every closed day of these trees that still holds a file other than its settled one.

    `now` is the instant the question is asked at. A day folder in `skip` is left
    as it stands. A dry run reads and settles every day it would fold, so a row
    that will not parse stops it the way it would stop a live fold, and it writes
    and deletes nothing. `listing` is where the names come from; a caller that
    folds a tree on disk passes none, and the trees are listed as the disk holds
    them.
    """
    chosen = sorted(trees, key=lambda which: which.value)
    if listing is None:
        roots = [ledger.tree_root(state_dir, tree) for tree in chosen]
        listing = FileListing.from_disk(
            state_dir.parent, [root.relative_to(state_dir.parent).as_posix() for root in roots]
        )
    done: list[SettledDay] = []
    for tree in chosen:
        root = ledger.tree_root(state_dir, tree)
        where = tree.value
        try:
            key = ledger.segment_key(tree)
            model = ledger.segment_contract(tree)
            days = [
                (day, root / day[:4] / day[5:7] / day[8:10])
                for day in _closed_days(listing, root, now=now, after_days=after_days)
            ]
            waiting = [(day, folder) for day, folder in days if folder not in skip]
            listing.fetch([folder for _, folder in waiting])
            for day, folder in waiting:
                where = f"{tree.value} {day}"
                replaced = _fold_day(root, day, key, model, dry_run=dry_run)
                if replaced:
                    done.append(SettledDay(tree=tree, day=day, folder=folder, replaced=replaced))
        except Exception as failure:
            so_far = Folded(dry_run=dry_run, days=tuple(done), failed=True)
            raise FoldInterruptedError(so_far, where) from failure
    return Folded(dry_run=dry_run, days=tuple(done))


def _closed_days(
    listing: FileListing, root: Path, *, now: datetime, after_days: int
) -> Iterator[str]:
    """Every day of one tree closed at `now` that holds a file besides its settled one.

    Read off the listing's names, so no file is opened to answer it, oldest day first.
    """
    waiting: dict[str, bool] = {}
    for shard in named_trees.shard_files(listing, root):
        day = day_shards.date_of(shard)
        waiting[day] = waiting.get(day, False) or shard.name != day_shards.SETTLED_NAME
    for day, unsettled in waiting.items():
        if unsettled and schedule.is_eligible(
            date.fromisoformat(day), now=now, after_days=after_days
        ):
            yield day


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
