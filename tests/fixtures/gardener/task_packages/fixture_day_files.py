"""How does a fixture task delete one day file at a time from the folders it is pointed at?

Shared by the fixture task packages beside it, so each fixture module is the
two names a real task module holds and nothing else. It is a real task body:
it lists real files, and a live pass really deletes them, through the same
core every gardener task uses.

A day file is `<YYYY-MM-DD>.txt`, and its member id is its path relative to the
checkout, which is what the runner holds to what the task owns.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

from idhazh.contracts.knobs.gardener import DaysWindow
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Collection, Member, Pass, Window, take


def day_files(context: TaskContext, folders: Sequence[str]) -> Pass:
    """Take every day file older than the declaration's window, oldest first."""
    window = context.policy.window
    assert isinstance(window, DaysWindow), "a fixture task keeps a window in days"
    root = context.repo_root

    def listing() -> Iterator[Path]:
        for folder in folders:
            yield from sorted((root / folder).glob("*.txt"))

    def describe(path: Path) -> Member:
        return Member(
            id=path.relative_to(root).as_posix(),
            day=path.stem,
            size_bytes=path.stat().st_size,
            label=path.name,
        )

    return take(
        Collection(name=folders[0], listing=listing, describe=describe, delete=Path.unlink),
        window=Window.older_than(today=context.today.isoformat(), days=window.value),
        ceiling=context.policy.max_deletes_per_run,
        dry_run=context.policy.dry_run,
    )
