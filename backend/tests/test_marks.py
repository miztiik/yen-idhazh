"""Every test is reachable from a mark, or is named here as carrying none.

The four marks declared in `pyproject.toml` let a developer run what a change
can break instead of the whole suite. That is only safe when a test outside
every subset is FOUND rather than silently never run, so this module collects
the suite once and asks pytest which marks it resolved onto each test.

A mark is a module-level `pytestmark`, so a module that is renamed or moved
carries its mark with it and nothing here needs an edit. What does need an edit
is a module carrying no mark at all, and that edit is the point: the set below
is the one place the fact "no mark selects this" is written down.

The marks never decide what a merge is checked against. CI runs the whole suite
(`docs/how-to/run-the-gates.md`), so a wrong mark costs a developer a re-run
rather than a missed regression. That is also why this file buys its answer as
cheaply as it can.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterable
from functools import cache
from pathlib import Path, PurePosixPath
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
        "test_archive_readers",
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


#: Collects the suite and reports what pytest resolved onto each test.
#:
#: `pytest_collection_modifyitems` runs after every `pytestmark`, class mark and
#: decorator has been applied, so `iter_markers` is pytest's own answer rather
#: than this file re-reading source and guessing. The JSON goes to a file
#: because pytest owns stdout.
CENSUS: Final = """
import json, sys
import pytest

class Census:
    def __init__(self):
        self.rows = []

    def pytest_collection_modifyitems(self, items):
        for item in items:
            self.rows.append([item.nodeid, sorted({m.name for m in item.iter_markers()})])

census = Census()
code = pytest.main(
    ["-o", "addopts=", "--collect-only", "-q", "-p", "no:cacheprovider"],
    plugins=[census],
)
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump({"code": int(code), "rows": census.rows}, handle)
"""


def declared_marks() -> tuple[str, ...]:
    """The mark names `pyproject.toml` declares, in the order it declares them.

    Read rather than copied, so a fifth mark is covered by this file the moment
    somebody adds it.
    """
    manifest = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    declared = manifest["tool"]["pytest"]["ini_options"]["markers"]
    return tuple(str(entry).split(":", 1)[0].strip() for entry in declared)


@cache
def census() -> dict[str, frozenset[str]]:
    """Every node id in the suite, against the marks pytest resolved onto it.

    One collection, where this file used to run six - the whole suite, one per
    declared mark, and the complement - at 32 s of subprocess each. The five
    extra runs were asking pytest's `-m` engine to confirm set arithmetic that
    pytest's own mark data already answers, and that engine is not ours to test.
    Measured 2026-09-05 on Intel Core i7-1265U / Windows 11: 195 s to 34 s.

    `-o addopts=` clears the repository defaults, so no second layer of xdist
    workers starts. It also drops `--strict-markers`, which is deliberate: a
    misspelled mark must reach this file as an unmarked module rather than
    stopping the subprocess, so the failure names the module either way.
    """
    with tempfile.TemporaryDirectory() as room:
        out = Path(room) / "census.json"
        done = subprocess.run(
            [sys.executable, "-c", CENSUS, str(out)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )
        assert out.exists(), f"the census never ran:\n{done.stdout}\n{done.stderr}"
        payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["code"] == 0, f"collection failed:\n{done.stdout}\n{done.stderr}"
    rows = {node_id: frozenset(marks) for node_id, marks in payload["rows"]}
    # A census of nothing would make every assertion below vacuous, which reads
    # exactly like a pass.
    assert len(rows) > 1000, f"the census collected {len(rows)} tests, so it did not collect"
    return rows


def selected_by(name: str) -> frozenset[str]:
    return frozenset(node_id for node_id, marks in census().items() if name in marks)


def selected_by_nothing() -> frozenset[str]:
    declared = frozenset(declared_marks())
    return frozenset(node_id for node_id, marks in census().items() if not (marks & declared))


def by_module(node_ids: Iterable[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for node_id in sorted(node_ids):
        grouped.setdefault(PurePosixPath(node_id.split("::", 1)[0]).stem, []).append(node_id)
    return grouped


def test_every_mark_selects_tests_and_no_module_falls_outside_them() -> None:
    """One test, because `-n auto` gives two tests two processes and the census
    cache cannot cross them."""
    marks = declared_marks()
    assert marks, "pyproject.toml declares no marks at all"
    empty = [name for name in marks if not selected_by(name)]
    assert not empty, (
        f"pyproject.toml declares {empty} and no test carries them. "
        "A module-level `pytestmark` was removed, or the name was never applied."
    )

    # An unmarked module is a decision somebody wrote down, never an oversight.
    rest = by_module(selected_by_nothing())
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
