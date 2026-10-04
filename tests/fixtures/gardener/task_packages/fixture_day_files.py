"""How does a fixture task delete one day file at a time from the folders it is pointed at?

Shared by the fixture task packages beside it, so each fixture module is the
two names a real task module holds and nothing else. It is a real task body:
it lists real files, and a live pass really deletes them, through the same
core every gardener task uses.

A day file is `<YYYY-MM-DD>.txt` directly inside a folder, and its member id is
its path relative to the checkout, which is what the runner holds to what the
task owns. Its names and sizes come from the task's listing, the way every
shipped task learns them: the walk covers the periods the listing names under
each folder, so a checkout that never downloaded the file still takes it by name.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

from idhazh.contracts.knobs.gardener import DaysWindow
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Collection, Member, Pass, Window, take


def day_files(context: TaskContext, folders: Sequence[str]) -> Pass:
    """Take every day file older than the declaration's window, oldest first."""
    from idhazh.gardener import named_trees

    window = context.policy.window
    assert isinstance(window, DaysWindow), "a fixture task keeps a window in days"
    root = context.repo_root
    listing = context.listing

    def members() -> Iterator[Path]:
        for folder in folders:
            yield from named_trees.files_named(listing, root / folder, ".txt")

    def describe(path: Path) -> Member:
        return Member(
            id=path.relative_to(root).as_posix(),
            day=path.stem,
            size_bytes=listing.size_of(path),
            label=path.name,
        )

    def delete(path: Path) -> None:
        path.unlink(missing_ok=True)

    return take(
        Collection(
            name=folders[0] if folders else "no folder",
            listing=members,
            describe=describe,
            delete=delete,
        ),
        window=Window.older_than(today=context.today.isoformat(), days=window.value),
        ceiling=context.policy.max_deletes_per_run,
        dry_run=context.policy.dry_run,
    )
