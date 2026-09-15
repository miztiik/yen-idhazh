"""What does the bench do when a publisher edits an article mid-run?"""

from __future__ import annotations

import re

import pytest

from ._harness import (
    BENCH_SERVER_JOB,
    RUNTIME_CANDIDATES,
    _declared_dispatch_inputs,
    _load_workflows,
    _script,
    _step,
)

pytestmark = pytest.mark.workflow

MEASURE = "measure.yml"
SWEEP_STEP = "Measure runtime candidate"


def sweep_script() -> str:
    """The runtime case's inline python, read inside the test that asserts on it."""
    workflow = _load_workflows()[MEASURE]
    return _script(
        _step(workflow, BENCH_SERVER_JOB, "name", SWEEP_STEP),
        f"{MEASURE}/{BENCH_SERVER_JOB}/{SWEEP_STEP}",
    )


def test_a_repeat_whose_article_moved_is_dropped_rather_than_failing_the_job() -> None:
    """Three complete repeats were thrown away on 2026-09-15 to protect a
    comparison that two of them could still have made - and did, byte for byte.

    The guard's reason stands: a repeat that summarized different text may not
    sit in the same median as one that did not. What may not stand is the
    consequence, because a news page being edited inside a multi-hour job is
    ordinary rather than unlucky.
    """
    script = sweep_script()

    assert "input_drift_dropped" in script, "a dropped repeat is named, not silently discarded"
    assert re.search(r"comparable = \[", script), "the timing reads the agreeing set"
    assert 'for result in comparable if result["label"] == label' in script, (
        "stats() still reads every result, so a drifted repeat is back in the median"
    )


def test_a_run_with_nothing_left_to_compare_is_still_refused() -> None:
    """Dropping repeats cannot become a way to report a median over one reading."""
    script = sweep_script()

    assert "too_few_agreeing_repeats" in script
    assert "rejected_input_drift" in script, "the refusal still exists for the case that earns it"
    assert re.search(r"if\s+thin:\s*\n\s+verdict = \"rejected_input_drift\"", script)


def test_output_drift_is_only_asked_about_repeats_that_read_the_same_text() -> None:
    """Otherwise a publisher's edit is reported as the model being unstable.

    That names the wrong cause, and it is the reader of the failure who pays:
    they go looking at the decoder for something a newsroom did.
    """
    script = sweep_script()

    assert "for result in comparable:\n" in script.replace("              ", ""), (
        "digest_sets is built from every result, including the drifted ones"
    )


def test_the_summary_says_how_many_repeats_the_timing_was_taken_over() -> None:
    """A median over a denominator nobody was told is not a reading (Guardrail #10)."""
    script = sweep_script()

    assert '"repeats_timed": len(comparable)' in script
    assert '"repeats": REPEATS' in script, "what was asked for stays beside what was used"


def test_the_repeat_count_is_dispatchable_and_floors_at_two() -> None:
    """A named case runs two cases, so three repeats does not fit the job timeout.

    The runner budget is GitHub's rather than ours, so the design is what gives
    (CLAUDE.md Guardrail #2) - an operator lowers the count instead of asking
    for a longer job.
    """
    declared = _declared_dispatch_inputs(_load_workflows()[MEASURE])

    assert "runtime_repeats" in declared
    script = sweep_script()
    assert 'REPEATS = int(os.environ["RUNTIME_REPEATS"])' in script
    assert "runtime_repeats must be at least 2" in script


def test_the_draft_head_is_a_case_the_bench_can_pair_on_one_machine() -> None:
    """Two dispatches landed on two processors and answered nothing.

    On 2026-09-15 the cases differed by 5.3 percent across runs while the same
    `llama-bench` decode test on the same weights differed by 8.8 percent
    between two machines both reporting EPYC 7763. A paired case cancels the
    machine, and it needs no second download because both cases open the same
    weights file.
    """
    assert "no_draft" in RUNTIME_CANDIDATES
    script = sweep_script()

    assert 'if name == "no_draft":' in script
    assert 'return {"draft": None}, 1' in script


def test_the_draft_case_reaches_outside_inference_and_no_other_case_does() -> None:
    """`draft` is a sibling of `inference`, not a knob inside it.

    Applying it to `inference` would write a key the models contract refuses,
    and the case would fail on a validation error rather than measuring
    anything. It is written rather than indexed because an entry that declares
    no draft head has no such key to index.
    """
    script = sweep_script()

    assert '"draft" in inference' in script
    assert 'payload["summarize"].update({"draft": inference.pop("draft")})' in script
    assert 'payload["summarize"]["draft"]' not in script, (
        "indexing a key the incumbent does not declare is a KeyError on the runner"
    )
    assert 'payload["summarize"]["inference"].update(inference)' in script, (
        "the remaining patch still goes to inference, so every other case is unchanged"
    )
