"""Every test module is reachable from a mark, or is named here as carrying none.

The four marks declared in `pyproject.toml` let a developer run what a change
can break instead of the whole suite. That is only safe when a module outside
every subset is FOUND rather than silently never run, so this module reads the
module-level `pytestmark` off every test module and holds the four against it.

A mark is a module-level `pytestmark`, so a module that is renamed or moved
carries its mark with it and nothing here needs an edit. What does need an edit
is a module carrying no mark at all, and that edit is the point: the set below
is the one place the fact "no mark selects this" is written down.

The marks never decide what a merge is checked against. CI runs the whole suite
(`docs/how-to/run-the-gates.md`), so a wrong mark costs a developer a re-run
rather than a missed regression. That is also why this file buys its answer as
cheaply as it can.

## Design rationale

**2026-09-14: the answer is read from source, not bought with a collection.**
This file used to spawn a subprocess that collected the whole suite and asked
pytest which marks resolved onto each test. That cost 29.2 s for the answer
alone, and 95.6 s of the suite's own reported time - rank 8 of 3,407 timed
tests, and the worst per test by a factor of three - to defend a developer
shortcut that never gates a merge. Reading `pytestmark` off 131 files is the
same answer far more cheaply.

The two agree because of a property of this tree rather than of pytest, so it is
held rather than assumed: **no declared mark is ever applied by decorator.** All
139 `@pytest.mark.` decorators under `backend/tests` are `parametrize`, which is
a builtin and selects nothing. `test_a_declared_mark_is_never_applied_by_decorator`
is what makes the cheap read safe - decorate a test with `contract` tomorrow and
it fails, naming the file.

The collection this replaces answered 3,498 tests, 53 unmarked modules, and
981/226/432/182 tests per mark on 2026-09-14. Reading source reproduces the same
53 modules and the same four non-empty marks.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT, read_text

pytestmark = pytest.mark.slow

TESTS_DIR: Final = REPO_ROOT / "backend" / "tests"

#: Every test module that no mark selects, by stem. A module lands here because
#: a developer changing that area has no shorter thing to run than the module
#: itself, which is already the fast answer. It is a list rather than a rule so
#: that a NEW unmarked module fails this file instead of joining it unnoticed.
UNMARKED_MODULES: Final = frozenset(
    {
        "test_assemble_embeddings",
        "test_backfill_vectors",
        "test_canary_day",
        "test_chrome",
        "test_classify",
        "test_corpus",
        "test_corpus_harvest",
        "test_cross_filing",
        "test_data_wrangler",
        "test_day_metrics_producer",
        "test_day_partition",
        "test_decode_split",
        "test_desk_bounds",
        "test_desk_field",
        "test_desk_knobs",
        "test_discover",
        "test_doc_load",
        "test_elements",
        "test_embed",
        "test_eval_ledger",
        "test_eval_row",
        "test_evals",
        "test_evidence",
        "test_extract",
        "test_extraction_health",
        "test_feed_health_shards",
        "test_frame_knobs",
        "test_freshness_curve",
        "test_frozen_days",
        "test_gate_lock",
        "test_grader_length_bias",
        "test_head_frame",
        "test_host_readings",
        "test_item_health_provenance",
        "test_item_records",
        "test_labels",
        "test_leading_stories",
        "test_measure_budgets",
        "test_measure_ledgers",
        "test_measure_llm",
        "test_measure_two_calls",
        "test_migrate_to_day_shards",
        "test_notebooks",
        "test_order_of_the_day",
        "test_pipeline_artifact_analyzer",
        "test_plan",
        "test_plan_status",
        "test_policy_defaults",
        "test_prompt_loop",
        "test_publish_source_health",
        "test_publish_telemetry",
        "test_qualify",
        "test_qualify_call_path",
        "test_rank",
        "test_reband_scores",
        "test_reference_dataset",
        "test_reference_set",
        "test_retention_oracle",
        "test_run_timeline_producer",
        "test_same_story",
        "test_same_story_window",
        "test_search_index",
        "test_seen_days",
        "test_silicon",
        "test_similarity_draw",
        "test_site_alarm",
        "test_slot_probe",
        "test_source_dwell",
        "test_source_health",
        "test_spans",
        "test_stream_order",
        "test_summarise_bench",
        "test_summarize",
        "test_sweep_verdict",
        "test_sweep_worktrees",
        "test_tag",
        "test_telemetry",
        "test_telemetry_fold",
        "test_trace_tree",
        "test_two_runs",
        "test_validation",
        "test_visual_pruning",
        "test_work_order",
    }
)


#: A mark applied to one test rather than to its module. `parametrize` and the
#: other builtins select nothing, so they are the only ones this tree may carry.
DECORATOR_MARK: Final = re.compile(r"@pytest\.mark\.(\w+)")
BUILTIN_MARKS: Final = frozenset({"parametrize", "skip", "skipif", "xfail", "usefixtures"})


def declared_marks() -> tuple[str, ...]:
    """The mark names `pyproject.toml` declares, in the order it declares them.

    Read rather than copied, so a fifth mark is covered by this file the moment
    somebody adds it.
    """
    manifest = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    declared = manifest["tool"]["pytest"]["ini_options"]["markers"]
    return tuple(str(entry).split(":", 1)[0].strip() for entry in declared)


def modules() -> list[Path]:
    """Every test module, including the ones that sit inside a package."""
    found = sorted(TESTS_DIR.rglob("test_*.py"))
    # A census of nothing would make every assertion below vacuous, which reads
    # exactly like a pass.
    assert len(found) > 100, f"found {len(found)} test modules, so the walk did not walk"
    return found


def mark_names(value: ast.expr) -> Iterator[str]:
    """The mark names a `pytestmark` right-hand side carries.

    Covers `pytest.mark.slow`, a list or tuple of those, and the called form
    `pytest.mark.slow(...)`. Anything else yields nothing, which `module_marks`
    turns into a refusal rather than a silent zero.
    """
    items = value.elts if isinstance(value, ast.List | ast.Tuple) else [value]
    for item in items:
        node = item.func if isinstance(item, ast.Call) else item
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "mark"
        ):
            yield node.attr


def module_marks(path: Path) -> frozenset[str]:
    """The marks a module's own `pytestmark` names, read from its source.

    A `pytestmark` in a shape this cannot read is refused by name rather than
    counted as no marks, because no marks is a legal answer here and would hide
    the mistake inside `UNMARKED_MODULES`.
    """
    for node in ast.parse(read_text(path)).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            names = frozenset(mark_names(node.value))
            assert names, (
                f"{path.relative_to(REPO_ROOT).as_posix()} assigns `pytestmark` in a shape this "
                "file cannot read. Write it as `pytest.mark.<name>` or a list of those."
            )
            return names
    return frozenset()


def test_every_mark_selects_modules_and_no_module_falls_outside_them() -> None:
    marks = declared_marks()
    assert marks, "pyproject.toml declares no marks at all"

    declared = frozenset(marks)
    carried = {path.stem: module_marks(path) & declared for path in modules()}

    empty = [name for name in marks if not any(name in got for got in carried.values())]
    assert not empty, (
        f"pyproject.toml declares {empty} and no module carries them. "
        "A module-level `pytestmark` was removed, or the name was never applied."
    )

    # An unmarked module is a decision somebody wrote down, never an oversight.
    rest = {stem for stem, got in carried.items() if not got}
    appeared = sorted(rest - UNMARKED_MODULES)
    vanished = sorted(UNMARKED_MODULES - rest)

    assert not appeared, (
        "no mark selects these modules and UNMARKED_MODULES does not name them:\n"
        + "\n".join(f"  {name}" for name in appeared)
        + "\nGive the module a `pytestmark`, or add it to UNMARKED_MODULES so the next "
        "reader can see the omission was a choice."
    )
    assert not vanished, (
        f"UNMARKED_MODULES names {vanished}, which a mark now selects or which no longer exist. "
        "Drop them from the set."
    )


def test_a_declared_mark_is_never_applied_by_decorator() -> None:
    """The property that lets this file read source instead of collecting.

    Reading `pytestmark` sees a module's marks and nothing else, which is the
    whole answer only while no single test carries a declared mark of its own.
    """
    declared = frozenset(declared_marks())
    offenders: list[str] = []
    for path in modules():
        where = path.relative_to(REPO_ROOT).as_posix()
        for found in DECORATOR_MARK.findall(read_text(path)):
            if found in declared:
                offenders.append(f"  {where}: @pytest.mark.{found} is a declared selector")
            elif found not in BUILTIN_MARKS:
                offenders.append(f"  {where}: @pytest.mark.{found} is neither declared nor builtin")

    assert not offenders, (
        "a declared mark is applied to a test rather than to its module, so reading "
        "`pytestmark` no longer sees every mark:\n" + "\n".join(offenders) + "\nMove it to a "
        "module-level `pytestmark`, or make this file collect the suite again."
    )
