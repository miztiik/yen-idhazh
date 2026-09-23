"""Does every committed path a producer writes fall in exactly one class?

Three answers decide what git may do with a committed path when two runs arrive
together: it is written once by a named writer, it is derived and handed back,
or it takes a union. A path in two classes is two answers to one question, and a
path in none is a conflict nobody planned for.

**The writers are enumerated from the modules that declare them, never from the
tree.** `ledger.SegmentLedger` is the closed set of day trees a writer fills and
`paths.DERIVED` and `paths.UNION_SAFE` are the other two lists, so nothing here
walks `state/` and the answer does not change because a run committed a file
(CLAUDE.md section 13, Guardrail #12). A tenth tree that arrives without a class
fails here rather than in the rebase that could not merge it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh import day_shards, ledger, paths
from idhazh.contracts.base import ServerJob

pytestmark = pytest.mark.contract

#: A run identity in the shape a workflow hands one over: the run id matches
#: `contracts.base.RUN_ID_PATTERN`, the attempt is GitHub's own and starts at 1,
#: and the shard is two digits wide because `ledger.segment_name` writes it so.
A_RUN_ID = "2026-08-20-3"
AN_ATTEMPT = 2
A_SHARD = 7
A_DATE = "2026-08-20"

#: A day directory as the plan job derives one, for the two derived entries that
#: carry a placeholder.
A_DAY_DIR = "frontend/public/digest/2026/08/25"


def _under(relpath: str, entry: str) -> bool:
    """Whether a committed path is claimed by one declared entry.

    A path entry claims itself and everything inside it. An entry with no
    separator is a filename instead, and it claims that file in whatever
    directory it turns up in - which is what the fold is.
    """
    if "/" not in entry:
        return Path(relpath).name == entry
    rendered = entry.format(day_dir=A_DAY_DIR)
    return relpath == rendered or relpath.startswith(f"{rendered}/")


def _classes(relpath: str) -> set[str]:
    """Which of the three classes claim this path. One is the only right answer."""
    found = set()
    if paths.is_written_once(relpath):
        found.add("written once")
    if any(_under(relpath, entry) for entry in paths.DERIVED):
        found.add("derived")
    if any(_under(relpath, entry) for entry in paths.UNION_SAFE):
        found.add("union safe")
    return found


def _a_writer_file(tree: ledger.SegmentLedger) -> str:
    """One day-shard path of one tree, spelled by the producer that writes them."""
    return ledger.day_shard_relpath(
        tree,
        date=A_DATE,
        run_id=A_RUN_ID,
        attempt=AN_ATTEMPT,
        job=ServerJob.WORK,
        shard=A_SHARD,
    )


def test_every_day_tree_writer_names_a_file_only_it_can_have_written() -> None:
    """Rule 1 over the closed set of day trees, one file each.

    A tree here is one a writer fills with a file carrying its own identity, so
    two runs never arrive at one path and there is nothing for git to settle. A
    tree that also appeared in the derived or the union-safe list would be two
    answers to that question.
    """
    assert list(ledger.SegmentLedger), "a closed set with no members declares no writer"

    for tree in ledger.SegmentLedger:
        relpath = _a_writer_file(tree)
        assert _classes(relpath) == {"written once"}, (
            f"{relpath} is classed {sorted(_classes(relpath))}, and a committed path "
            "needs exactly one answer about what git may do with it"
        )


def test_a_writers_file_carries_the_run_the_attempt_the_job_and_the_shard() -> None:
    """The identity is what makes the name one writer's, so the name carries all four.

    Read back through the producer's own parser rather than by eye, because a
    name this test spelled itself would prove only that this test can spell.
    """
    for tree in ledger.SegmentLedger:
        relpath = _a_writer_file(tree)
        read = ledger.parse_segment_name(Path(relpath))
        assert read.run_id == A_RUN_ID
        assert read.attempt == AN_ATTEMPT
        assert read.job is ServerJob.WORK
        assert read.shard == A_SHARD


def test_a_derived_path_is_rebuilt_and_is_neither_written_once_nor_unioned() -> None:
    """Rule 1 over the list a job rebuilds rather than merges.

    A leaf inside each entry, because the commit step hands back the entry and
    git acts on the files under it. The fold is skipped here - it is a filename
    rather than a directory, and the test below is the one that places it.
    """
    for entry in paths.DERIVED:
        if "/" not in entry:
            continue
        for relpath in (entry.format(day_dir=A_DAY_DIR), f"{entry.format(day_dir=A_DAY_DIR)}/2026/08/20.json"):
            assert _classes(relpath) == {"derived"}, (
                f"{relpath} is classed {sorted(_classes(relpath))}; a path that is "
                "rebuilt cannot also be one git merges or one writer owns"
            )


def test_a_union_safe_path_takes_a_union_and_is_neither_derived_nor_written_once() -> None:
    """Rule 1 over the list `.gitattributes` gives `merge=union`.

    A union is right only where two writers appending are not in disagreement. A
    path that was also written once would make the union pointless, and one that
    was also derived would make it wrong - a rebuild would drop the other side's
    rows.
    """
    for entry in paths.UNION_SAFE:
        leaves = [entry] if entry.endswith(".csv") else [entry, f"{entry}/2026/08/20.csv"]
        for relpath in leaves:
            assert _classes(relpath) == {"union safe"}, (
                f"{relpath} is classed {sorted(_classes(relpath))}; a path git unions "
                "cannot also be one a rebuild replaces or one writer owns"
            )


def test_the_fold_is_derived_in_every_day_tree_and_is_never_handed_back() -> None:
    """A closed day's `settled.csv` is derived, and it is the one entry not rebuilt.

    Derived, because the fold is a function of the writer files it read: two
    runs that fold one closed day compute the same bytes, and a merge of two
    copies is never the answer.

    Not handed back, because `idhazh assemble` re-emits no fold. A job that gave
    this path back to the tip would delete it rather than rebuild it. A
    conflicted fold refuses the push instead - it carries no writer identity, so
    the resolver answers "not mine" and stops.
    """
    for tree in ledger.SegmentLedger:
        fold = (Path(_a_writer_file(tree)).parent / day_shards.SETTLED_NAME).as_posix()
        assert _classes(fold) == {"derived"}, (
            f"{fold} is classed {sorted(_classes(fold))}, and a fold is derived in "
            "every tree that has one"
        )
        assert not paths.is_written_once(fold), "a fold is derived from writers, never one of them"

    handed_back = paths.refresh_paths(day_dir=A_DAY_DIR).split(" ")
    assert day_shards.SETTLED_NAME not in handed_back


def test_an_operators_repair_is_written_once_so_it_never_collides_with_a_writer() -> None:
    """A repair adds rows into a committed day, and no run can take its name.

    The one add `evals.writer.rebuild_index` makes. It is stamped with the
    instant it was minted rather than a run identity, which is what keeps two
    repairs apart and what keeps a repair out of every writer's way.
    """
    repair = f"state/{ledger.SCORE_INDEX_DIRNAME}/2026/08/20/repair-20260820T091500Z.csv"

    assert _classes(repair) == {"written once"}


def test_a_name_outside_the_grammar_is_in_no_class_at_all() -> None:
    """The tripwire this whole file exists to arm.

    A file somebody drops into a day directory under a name nothing spells is
    what a lost push race turns into a conflict. It has to read as unclassified
    here, or the rule above proves nothing.
    """
    assert _classes(f"state/{ledger.SCORES_DIRNAME}/2026/08/20/notes.csv") == set()
    assert _classes("state/some-tree-nobody-declared/2026/08/20.csv") == set()
