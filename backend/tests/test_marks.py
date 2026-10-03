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

import tomllib
from typing import Final

from conftest import REPO_ROOT, read_text

from utilities.mark_census import (
    BUILTIN_MARKS,
    DECORATOR_MARK,
    declared_marks,
    module_marks,
    modules,
)
from utilities.slow_mark_audit import slow_threshold_seconds, threshold_phrase

#: Every test module that no mark selects, by stem. A module lands here because
#: a developer changing that area has no shorter thing to run than the module
#: itself, which is already the fast answer. It is a list rather than a rule so
#: that a NEW unmarked module fails this file instead of joining it unnoticed.
UNMARKED_MODULES: Final = frozenset(
    {
        "test_assemble_embeddings",
        "test_assembly",
        "test_backfill_vectors",
        "test_banding",
        "test_canary_day",
        "test_canary_packing",
        "test_candidate_pointer",
        "test_capture_root",
        "test_chunking",
        "test_classify",
        "test_console_payload_gate",
        "test_corpus",
        "test_corpus_harvest",
        "test_corpus_history",
        "test_council_matrix",
        "test_council_runs_without_a_judge",
        "test_cross_filing",
        "test_data_wrangler",
        "test_day_metrics_producer",
        "test_day_partition",
        "test_deadline",
        "test_decode_split",
        "test_degrade",
        "test_desk_bounds",
        "test_desk_field",
        "test_desk_knobs",
        "test_discover",
        "test_doc_load",
        "test_download_ceiling",
        "test_elements",
        "test_embed",
        "test_embedding_metrics",
        "test_entity_gap",
        "test_eval_ledger",
        "test_eval_row",
        "test_evals",
        "test_every_task_takes_what_its_pass_took",
        "test_evidence",
        "test_extract",
        "test_extraction_health",
        "test_fold_lands",
        "test_frame_knobs",
        "test_freshness_curve",
        "test_gate_lock",
        "test_github_trees",
        "test_grader_length_bias",
        "test_head_frame",
        "test_host_readings",
        "test_item_health_provenance",
        "test_item_records",
        "test_labels",
        "test_leading_stories",
        "test_marks",
        "test_measure_budgets",
        "test_measure_judge_call",
        "test_measure_ledgers",
        "test_measure_llm",
        "test_measure_two_calls",
        "test_memory_sampler",
        "test_merge_line_holdout",
        "test_metrics_sink",
        "test_migrate_to_day_shards",
        "test_model_runtime",
        "test_model_server_address",
        "test_month_partition",
        "test_night_plan",
        "test_notebooks",
        "test_order_of_the_day",
        "test_pipeline_artifact_analyzer",
        "test_plan",
        "test_plan_status",
        "test_policy_defaults",
        "test_prompt_loop",
        "test_publication_hook",
        "test_publication_registry",
        "test_publish",
        "test_publish_source_health",
        "test_publish_telemetry",
        "test_publish_window",
        "test_qualify",
        "test_qualify_call_path",
        "test_rank",
        "test_reband_scores",
        "test_recorded_inputs",
        "test_reference_dataset",
        "test_reference_set",
        "test_registry",
        "test_retrieval_eval",
        "test_run_identity",
        "test_run_timeline_producer",
        "test_runner",
        "test_same_story",
        "test_same_story_window",
        "test_sample_sheet",
        "test_scorer_sampling",
        "test_search_index",
        "test_session",
        "test_silicon",
        "test_similarity_applied",
        "test_similarity_selection",
        "test_similarity_fit",
        "test_similarity_counting",
        "test_similarity_judge",
        "test_similarity_handoff",
        "test_similarity_tenant",
        "test_site_weight",
        "test_slot_probe",
        "test_slow_mark_audit",
        "test_source_dwell",
        "test_source_health",
        "test_spans",
        "test_sparse_shard",
        "test_stream_order",
        "test_summarise_bench",
        "test_summarize",
        "test_sweep_verdict",
        "test_sweep_worktrees",
        "test_tag",
        "test_telemetry",
        "test_telemetry_aggregate_task",
        "test_thin_corpus",
        "test_two_calls",
        "test_two_runs",
        "test_validation",
        "test_visual_pruning",
        "test_widen_ledger_header",
        "test_work_health_payload",
        "test_work_order",
        "test_work_records",
    }
)


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


def test_the_slow_marker_text_names_the_configured_threshold() -> None:
    """`pyproject.toml`'s `slow` marker text is prose, not a copy of the number.

    `config/test-marks.json` is what `slow_mark_audit.py` reads to judge a
    module; the marker text is what a person reads. This is the one check that
    a change to the config is not forgotten in the words next to it.
    """
    manifest = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    descriptions = {
        str(entry).split(":", 1)[0].strip(): str(entry).split(":", 1)[1].strip()
        for entry in manifest["tool"]["pytest"]["ini_options"]["markers"]
    }
    assert "slow" in descriptions, "pyproject.toml no longer declares a `slow` marker"

    phrase = threshold_phrase(slow_threshold_seconds())
    assert phrase in descriptions["slow"], (
        f"the `slow` marker reads {descriptions['slow']!r} but config/test-marks.json's "
        f"threshold reads as {phrase!r}. Update whichever one is stale."
    )
