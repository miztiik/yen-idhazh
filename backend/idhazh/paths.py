"""Which committed paths are derived from what other jobs wrote?

A derived path's content is a function of other jobs' output, so two runs that
start from different bases compute different bytes for it and git has no way to
choose between them. The answer is never a merge: before it rebases, a job hands
every path named here back to the tip it is pushing at, and then runs its own
producer again against that tip.

The list used to be a space-split string inside a workflow step, whose own header
warned that no path in it may carry a space - a rule nothing could check - and a
second copy of it lived in the workflow tests. It is one tuple now, and both the
workflow and the tests read it.

Every entry is a relative POSIX path (CLAUDE.md section 2). Two of them sit
inside the day a run publishes, so they carry the one placeholder this module
understands, `{day_dir}`; `refresh_paths` is what fills it in.
"""

from __future__ import annotations

from typing import Final

#: The one span an entry may carry, filled in by `refresh_paths`. A second kind
#: of placeholder would be a second thing the caller has to know, and the caller
#: is a workflow step with one value in its hand.
DAY_DIR: Final = "{day_dir}"

#: Every committed path a run rebuilds rather than merges.
#:
#: The day's own directory is deliberately absent and the two payload files in it
#: are named one at a time: the `shard-visuals-*` artifacts unpack this run's
#: rendered charts into that directory and no producer in the assemble job can
#: make those again, so handing the directory back would delete them.
#:
#: Some entries here are not derived in the strict sense - `state/traces` is
#: named for one shard of one run and `state/published` settles on the earliest
#: publication date - and they are here because the refresh list has always
#: carried them. Handing back a path that needs no hand-back costs a rebuild it
#: would have done anyway. Taking them out is the work of the rows that give
#: every writer its own filename, not of the row that moved the list.
DERIVED: Final[tuple[str, ...]] = (
    f"{DAY_DIR}/digest.json",
    f"{DAY_DIR}/run.json",
    "frontend/public/telemetry",
    "frontend/public/assist/index",
    "frontend/public/source-health.json",
    "frontend/public/console",
    "frontend/public/run-days",
    "frontend/public/day-metrics",
    "frontend/public/machine",
    "frontend/public/span-rollup",
    "frontend/public/run-timeline",
    "state/published",
    "state/scores",
    "state/score-index",
    "state/item-health",
    "state/span-rollup",
    "state/traces",
    "state/host-fingerprint",
    "state/segments",
)


def refresh_paths(*, day_dir: str) -> str:
    """`DERIVED` as one line, for the commit step that hands these paths back.

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
