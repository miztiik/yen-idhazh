"""Which day files does a task take when it walks the disk rather than the commit's names?

A real defect, written down: a checkout can hold a file nobody committed, and a
task that lists its folder off the disk takes that file as a member. The shard
that lands it refuses a deletion the commit never listed, so nothing lands.
"""

from collections.abc import Iterator
from pathlib import Path

from idhazh.contracts.knobs.gardener import DaysWindow, TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Collection, Member, Pass, Window, take

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    window = context.policy.window
    assert isinstance(window, DaysWindow), "a fixture task keeps a window in days"
    root = context.repo_root

    def on_disk() -> Iterator[Path]:
        for folder in context.owned_folders:
            yield from sorted((root / folder).glob("*.txt"))

    def describe(path: Path) -> Member:
        return Member(
            id=path.relative_to(root).as_posix(),
            day=path.stem,
            size_bytes=path.stat().st_size,
            label=path.name,
        )

    return take(
        Collection(name="disk", listing=on_disk, describe=describe, delete=Path.unlink),
        window=Window.older_than(today=context.today.isoformat(), days=window.value),
        ceiling=context.policy.max_deletes_per_run,
        dry_run=context.policy.dry_run,
    )
