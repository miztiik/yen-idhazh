"""Which committed paths are written once, which are derived, which take a union?

Three answers about one committed path, and every one of them decides what git
is allowed to do with it when two runs arrive together.

A **derived** path's content is a function of other jobs' output, so two runs
that start from different bases compute different bytes for it and git has no
way to choose between them. The answer is never a merge: before it rebases, a
job hands every path in `DERIVED` back to the tip it is pushing at, and then
runs its own producer again against that tip.

A **written-once** path carries the name of the one writer that can have written
it, so two runs never arrive at one path and there is nothing to settle.
`is_written_once` is what reads a name back.

A **union-safe** path is appended to by writers that are not in disagreement, so
the union of two sides is the answer and `.gitattributes` says so. `UNION_SAFE`
is the list in this repository's own words, beside the other two.

Every entry is a relative POSIX path (CLAUDE.md section 2). Two of them sit
inside the day a run publishes, so they carry the one placeholder this module
understands, `{day_dir}`; `refresh_paths` is what fills it in. One entry is a
bare filename instead, because the thing it names is derived in every directory
it appears in, and a derived path is not always a path a job can hand back.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Final

from idhazh import day_shards, ledger

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
    "frontend/public/telemetry",
    "frontend/public/assist/index",
    "frontend/public/source-health.json",
    "frontend/public/console",
    "frontend/public/run-days",
    "frontend/public/day-metrics",
    "frontend/public/machine",
    "frontend/public/span-rollup",
    "frontend/public/run-timeline",
    "state/day-metrics",
    # A closed day's fold, derived from the writer files it read. It is the one
    # entry `refresh_paths` leaves out: `idhazh assemble` re-emits no fold, so a
    # job that handed this back would delete it rather than rebuild it.
    day_shards.SETTLED_NAME,
)

#: Every committed collection `.gitattributes` gives `merge=union`, in this
#: repository's own words rather than only in a glob git reads.
#:
#: A union is right only where two writers appending are not in disagreement -
#: a row about one address, one day, one shard or one pair, which a reader
#: settles by key. Where two writers on one path ARE a disagreement, the answer
#: is the written-once name instead: a union there would make the conflict quiet
#: rather than remove it. `state/feed-health` is the tree that says so - it
#: takes no driver.
UNION_SAFE: Final[tuple[str, ...]] = (
    "state/published",
    "state/visual-prunes",
    "state/seen",
    "state/feed-retirements.csv",
    "state/llm-council/shard-outcomes",
    "state/content-similarity-judge/metrics",
    "state/content-similarity-judge/merge-line-holdout-scores",
    "state/content-similarity-judge/scored-pairs",
    "state/content-similarity-judge/fitted-thresholds",
)


def is_written_once(relpath: str) -> bool:
    """Whether this committed path is a file exactly one writer can have written.

    Two kinds of name pass. One is the identity grammar every producer spells
    through `ledger.segment_name`, whatever the tree's suffix. The other is a
    reserved name, each declared in `idhazh.ledger` with its own removal
    condition beside it: `before-partition.csv` for the bytes a committed head
    already held, `<ordinal>-<shard>.jsonl` for a trace written before traces
    carried identity, and `repair-<stamp>.csv` for an operator's one add.

    `settled.csv` is deliberately absent. A fold is derived - `DERIVED` carries
    its name - and the two classes answer different questions.
    """
    name = PurePosixPath(relpath).name
    if name == ledger.BEFORE_PARTITION_NAME or ledger.is_repair(name):
        return True
    stem, _, suffix = name.rpartition(".")
    if not stem:
        return False
    if ledger.SEGMENT_NAME.fullmatch(stem) is not None:
        return True
    return suffix == "jsonl" and ledger.PRE_IDENTITY_TRACE.fullmatch(stem) is not None


def refresh_paths(*, day_dir: str) -> str:
    """The derived paths a job hands back, as one line for the commit step.

    The commit script word-splits what it is given, so the separator is a single
    space and a path carrying one would be read as two. That rule used to be a
    comment above a hand-written string; here it is checked before the line is
    emitted, and a path that broke it fails in the job that wrote it rather than
    in the rebase that could not find the file.

    A bare filename is dropped. It names a file derived in many directories, so
    there is no one path to hand back, and the producer that would rebuild it
    does not run in the job doing the handing. A conflicted fold refuses the
    push instead: it carries no writer identity, so the resolver answers "not
    mine" and stops.
    """
    rendered = [entry.format(day_dir=day_dir) for entry in DERIVED if "/" in entry]
    carries_a_space = [path for path in rendered if " " in path]
    if carries_a_space:
        raise ValueError(
            "a refreshed path may not carry a space - the commit step word-splits "
            f"this line: {carries_a_space}"
        )
    return " ".join(rendered)
