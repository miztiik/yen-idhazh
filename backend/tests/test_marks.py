"""Every test is reachable from a mark, or is named here as carrying none.

The four marks declared in `pyproject.toml` let a developer run what a change
can break instead of the whole suite. That is only safe when a test outside
every subset is FOUND rather than silently never run, so this module collects
the suite once whole, once for each declared mark and once for the complement,
then holds those sets against each other by node id.

A mark is a module-level `pytestmark`, so a module that is renamed or moved
carries its mark with it and nothing here needs an edit. What does need an edit
is a module carrying no mark at all, and that edit is the point: the set below
is the one place the fact "no mark selects this" is written down.

The marks never decide what a merge is checked against. CI runs the whole suite
(`docs/how-to/run-the-gates.md`), so a wrong mark costs a developer a re-run
rather than a missed regression.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from collections.abc import Iterable
from functools import cache
from pathlib import PurePosixPath
from typing import Final

import pytest
from conftest import REPO_ROOT, read_text

pytestmark = pytest.mark.slow

#: Every test module that no mark selects, by stem. A module lands here because
#: a developer changing that area has no shorter thing to run than the module
#: itself, which is already the fast answer. It is a list rather than a rule so
#: that a NEW unmarked module fails this file instead of joining it unnoticed.
UNMARKED_MODULES: Final = frozenset(
    {
        "test_assemble_embeddings",
        "test_backfill_vectors",
        "test_canary_day",
        "test_corpus",
        "test_corpus_harvest",
        "test_data_wrangler",
        "test_discover",
        "test_embed",
        "test_evals",
        "test_evidence",
        "test_extract",
        "test_grader_length_bias",
        "test_labels",
        "test_leading_stories",
        "test_measure_ledgers",
        "test_measure_llm",
        "test_notebooks",
        "test_plan",
        "test_publish_source_health",
        "test_publish_telemetry",
        "test_qualify",
        "test_reband_scores",
        "test_reference_set",
        "test_same_story",
        "test_search_index",
        "test_source_health",
        "test_spans",
        "test_summarise_bench",
        "test_summarize",
        "test_sweep_worktrees",
        "test_tag",
        "test_telemetry",
        "test_validation",
    }
)


def declared_marks() -> tuple[str, ...]:
    """The mark names `pyproject.toml` declares, in the order it declares them.

    Read rather than copied, so a fifth mark is covered by this file the moment
    somebody adds it.
    """
    manifest = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    declared = manifest["tool"]["pytest"]["ini_options"]["markers"]
    return tuple(str(entry).split(":", 1)[0].strip() for entry in declared)


@cache
def collected(expression: str) -> frozenset[str]:
    """The node ids `-m <expression>` selects, from a real collection.

    `-o addopts=` clears the repository defaults, so the output shape does not
    depend on how quiet `addopts` happens to be and no second layer of xdist
    workers starts. It also drops `--strict-markers`, which is deliberate: a
    misspelled mark must reach this file as an unmarked module rather than
    stopping the subprocess, so the failure names the module either way.
    """
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "addopts=",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    if expression:
        argv += ["-m", expression]
    done = subprocess.run(
        argv, cwd=REPO_ROOT, capture_output=True, text=True, check=False, encoding="utf-8"
    )
    # 5 is "nothing was collected", which is an answer here rather than a failure.
    assert done.returncode in {0, 5}, (
        f"collection failed for -m {expression!r}:\n{done.stdout}\n{done.stderr}"
    )
    return frozenset(
        line.strip()
        for line in done.stdout.splitlines()
        if line.startswith("backend/tests/") and "::" in line
    )


def unmarked_expression() -> str:
    return " and ".join(f"not {name}" for name in declared_marks())


def by_module(node_ids: Iterable[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for node_id in sorted(node_ids):
        grouped.setdefault(PurePosixPath(node_id.split("::", 1)[0]).stem, []).append(node_id)
    return grouped


def test_every_mark_selects_tests_and_together_with_the_rest_they_are_the_suite() -> None:
    """The four subsets and the complement are the suite, with nothing outside them.

    One test rather than four, because each collection costs a subprocess and
    `-n auto` gives two tests two processes that cannot share the cache.
    """
    marks = declared_marks()
    empty = [name for name in marks if not collected(name)]
    assert not empty, (
        f"pyproject.toml declares {empty} and no test carries them. "
        "A module-level `pytestmark` was removed, or the name was never applied."
    )

    whole = collected("")
    marked: set[str] = set()
    for name in marks:
        marked |= collected(name)
    rest = collected(unmarked_expression())

    missing = whole - (marked | rest)
    assert not missing, f"{len(missing)} node ids are in no subset at all: {sorted(missing)[:5]}"
    assert not (marked | rest) - whole, "a subset selected something the whole suite did not"
    assert rest == whole - marked, (
        "`-m 'not <every mark>'` and 'the whole suite minus the marked subsets' disagree, "
        f"by {len(rest ^ (whole - marked))} node ids"
    )


def test_a_module_in_no_subset_is_one_this_file_names() -> None:
    """An unmarked module is a decision somebody wrote down, never an oversight."""
    rest = by_module(collected(unmarked_expression()))
    appeared = sorted(set(rest) - UNMARKED_MODULES)
    vanished = sorted(UNMARKED_MODULES - set(rest))

    named = "\n".join(
        f"  {name}: {len(rest[name])} tests, e.g. {rest[name][0]}" for name in appeared
    )
    assert not appeared, (
        "no mark selects these modules and UNMARKED_MODULES does not name them:\n"
        f"{named}\n"
        "Give the module a `pytestmark`, or add it to UNMARKED_MODULES so the next "
        "reader can see the omission was a choice."
    )
    assert not vanished, (
        f"UNMARKED_MODULES names {vanished}, which a mark now selects or which no longer exist. "
        "Drop them from the set."
    )
