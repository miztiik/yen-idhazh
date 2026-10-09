"""Does every committed path a producer writes fall in exactly one class?

Two answers decide what git may do with a committed path when two runs arrive
together: it is written once by a named writer, or it is derived and handed
back. A path in both classes is two answers to one question, and a path in
neither is a conflict nobody planned for.

**The writers are enumerated from the modules that declare them, never from the
tree.** The trace sink names the one file a writer still names for itself, and
`path_classes.DERIVED` is the other list, so nothing here walks `state/` and the
answer does not change because a run committed a file (CLAUDE.md section 13,
Guardrail #12). A tree that arrives without a class fails here rather than in
the rebase that could not merge it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh import ledger, path_classes
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry.traces import TRACE_SUFFIX, committed_trace_path

pytestmark = pytest.mark.contract

#: A run identity in the shape a workflow hands one over: the run id matches
#: `contracts.base.RUN_ID_PATTERN`, the attempt is GitHub's own and starts at 1,
#: and the shard is two digits wide because `ledger.segment_name` writes it so.
A_RUN_ID = "2026-08-20-3"
AN_ATTEMPT = 2
A_SHARD = 7

#: A day directory as the plan job derives one, for the two derived entries that
#: carry a placeholder.
A_DAY_DIR = "frontend/public/digest/2026/08/25"


def _under(relpath: str, entry: str) -> bool:
    """Whether a committed path is claimed by one declared entry: the entry itself or inside it."""
    rendered = entry.format(day_dir=A_DAY_DIR)
    return relpath == rendered or relpath.startswith(f"{rendered}/")


def _classes(relpath: str) -> set[str]:
    """Which of the two classes claim this path. One is the only right answer."""
    found = set()
    if path_classes.is_written_once(relpath):
        found.add("written once")
    if any(_under(relpath, entry) for entry in path_classes.DERIVED):
        found.add("derived")
    return found


def _a_trace() -> str:
    """One job's committed trace, spelled by the producer that writes it."""
    return committed_trace_path(
        Path("state"), run_id=A_RUN_ID, attempt=AN_ATTEMPT, job=ServerJob.WORK, shard=A_SHARD
    ).as_posix()


def test_a_writer_named_file_is_written_once_and_in_no_other_class() -> None:
    """Rule 1 over the file a writer still names for itself: one job's trace.

    A file carrying its writer's identity is one two runs never arrive at
    together, so there is nothing for git to settle. A path that also appeared
    in the derived list would be two answers to that question. The ledgers that
    filed rows this way have moved to the raw ledger tree, so the trace is the
    writer left to check.
    """
    relpath = _a_trace()
    assert _classes(relpath) == {"written once"}, (
        f"{relpath} is classed {sorted(_classes(relpath))}, and a committed path "
        "needs exactly one answer about what git may do with it"
    )


def test_a_writers_file_carries_the_run_the_attempt_the_job_and_the_shard() -> None:
    """The identity is what makes the name one writer's, so the name carries all four.

    Read back through the producer's own parser rather than by eye, because a
    name this test spelled itself would prove only that this test can spell.
    """
    read = ledger.parse_segment_name(Path(_a_trace()), suffix=TRACE_SUFFIX)
    assert read.run_id == A_RUN_ID
    assert read.attempt == AN_ATTEMPT
    assert read.job is ServerJob.WORK
    assert read.shard == A_SHARD


def test_a_derived_path_is_rebuilt_and_is_never_written_once() -> None:
    """Rule 1 over the list a job rebuilds rather than merges.

    A leaf inside each entry, because the commit step hands back the entry and
    git acts on the files under it.
    """
    for entry in path_classes.DERIVED:
        for relpath in (entry.format(day_dir=A_DAY_DIR), f"{entry.format(day_dir=A_DAY_DIR)}/2026/08/20.json"):
            assert _classes(relpath) == {"derived"}, (
                f"{relpath} is classed {sorted(_classes(relpath))}; a path that is "
                "rebuilt cannot also be one writer owns"
            )


def test_a_name_outside_the_grammar_is_in_no_class_at_all() -> None:
    """The tripwire this whole file exists to set.

    A file somebody drops into a day directory under a name nothing spells is
    what a lost push race turns into a conflict. It has to read as unclassified
    here, or the rule above proves nothing.
    """
    assert _classes(f"state/{LedgerName.SUMMARY_QUALITY_EVALS}/2026/08/20/notes.csv") == set()
    assert _classes("state/some-tree-nobody-declared/2026/08/20.csv") == set()