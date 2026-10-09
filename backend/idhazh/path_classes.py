"""Which committed paths are written once, and which are derived?

Two answers about one committed path, and each of them decides what git is
allowed to do with it when two runs arrive together.

A **derived** path's content is a function of other jobs' output, so two runs
that start from different bases compute different bytes for it and git has no
way to choose between them. The answer is never a merge: before it rebases, a
job hands every path in `DERIVED` back to the tip it is pushing at, and then
runs its own producer again against that tip.

A **written-once** path carries the name of the one writer that can have written
it, so two runs never arrive at one path and there is nothing to settle.
`is_written_once` is what reads a name back.

No committed path takes a union merge. A union settled two appends to one
shared file, and no writer appends to a shared file any more: the ledger door
gives each write a file of its own, and every other path a run commits is
written once or derived.

Every entry is a relative POSIX path (CLAUDE.md section 2). Two of them sit
inside the day a run publishes, so they carry the one placeholder this module
understands, `{day_dir}`; `refresh_paths` is what fills it in.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Final

from idhazh import ledger
from idhazh.ledger.filenames import _SEGMENT_NAME

#: The one span an entry may carry, filled in by `refresh_paths`. A second kind
#: of placeholder would be a second thing the caller has to know, and the caller
#: is a workflow step with one value in its hand.
DAY_DIR: Final = "{day_dir}"

#: Every committed path a run rebuilds rather than merges.
#:
#: The day's own directory is deliberately absent and the two payload files in it
#: are named one at a time. The directory also holds the day's charts, and a
#: chart is never handed back: this run's copy of one the tip already publishes
#: is dropped before the rebase instead (`render.write.drop_raced_assets`).
#:
#: **Eight `state/` trees left this list on 2026-09-22 and the reason is the
#: same for all of them.** Each one now names its file for the single writer
#: that wrote it, so two runs never compute different bytes for one path and
#: there is nothing to hand back. `state/day-metrics` is the one that stays: it
#: is one whole-file-per-day JSON that assemble rewrites from the day's rows, so
#: two runs of one day do land on one path, and the rebuild answers the race in
#: milliseconds.
DERIVED: Final[tuple[str, ...]] = (
    f"{DAY_DIR}/digest.json",
    f"{DAY_DIR}/run.json",
    "frontend/public/publication.json",
    "frontend/public/telemetry",
    "frontend/public/assist/index",
    "frontend/public/source-health.json",
    "frontend/public/console",
    "frontend/public/run-days",
    "frontend/public/day-metrics",
    "frontend/public/machine",
    "frontend/public/run-timeline",
    "state/day-metrics",
)


def is_written_once(relpath: str) -> bool:
    """Whether this committed path is a file exactly one writer can have written.

    Two kinds of name pass. One is the identity grammar every producer spells
    through `ledger.segment_name`, whatever the tree's suffix. The other is the
    one reserved name left, declared in `idhazh.ledger` with its removal
    condition beside it: `<ordinal>-<shard>.jsonl` for a trace written before
    traces carried identity.
    """
    stem, _, suffix = PurePosixPath(relpath).name.rpartition(".")
    if not stem:
        return False
    if _SEGMENT_NAME.fullmatch(stem) is not None:
        return True
    return suffix == "jsonl" and ledger.PRE_IDENTITY_TRACE.fullmatch(stem) is not None


def refresh_paths(*, day_dir: str) -> str:
    """The derived paths a job hands back, as one line for the commit step.

    The commit script word-splits what it is given, so the separator is a single
    space and a path carrying one would be read as two. That rule used to be a
    comment above a hand-written string; here it is checked before the line is
    emitted, and a path that broke it fails in the job that wrote it rather than
    in the rebase that could not find the file.
    """
    rendered = [entry.format(day_dir=day_dir) for entry in DERIVED]
    carries_a_space = [path for path in rendered if " " in path]
    if carries_a_space:
        raise ValueError(
            "a refreshed path may not carry a space - the commit step word-splits "
            f"this line: {carries_a_space}"
        )
    return " ".join(rendered)