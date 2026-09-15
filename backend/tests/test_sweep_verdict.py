"""Does the bench keep the repeats that can be compared, and refuse the rest?

The sweep that runs the cases needs a server, a subprocess and forty minutes.
This half needs none of them, so every case here is built - including the ones
the runner has never produced and the one that cost two dispatches.
"""

from __future__ import annotations

from typing import Any

from utilities import sweep_verdict


def a_result(
    label: str = "baseline",
    repeat: int = 1,
    *,
    text: str = "first",
    summary: str = "a",
    **timings: int,
) -> dict[str, Any]:
    """One repeat's readings, built. `text` stands for what the five pages said."""
    return {
        "label": label,
        "repeat": repeat,
        "sources": {f"item-{n}": f"{text}-{n}" for n in range(5)},
        "digests": {f"item-{n}": f"{summary}-{n}" for n in range(5)},
        "startup_ms": timings.get("startup_ms", 5000),
        "work_ms": timings.get("work_ms", 100_000),
        "total_ms": timings.get("total_ms", 105_000),
        "model_path_ms": timings.get("model_path_ms", 90_000),
    }


def test_three_clean_repeats_pass_and_all_three_are_timed() -> None:
    results = [a_result(repeat=n) for n in (1, 2, 3)]

    found = sweep_verdict.judge(results, labels=["baseline"], candidate="baseline")

    assert found.verdict == sweep_verdict.PASSED
    assert len(found.comparable) == 3
    assert found.problems == []


def test_one_repeat_whose_pages_moved_is_dropped_and_the_rest_still_pass() -> None:
    """The case that cost two complete dispatches on 2026-09-15.

    Repeats 2 and 3 agreed byte for byte and were thrown away to protect a
    comparison they could have made. A publisher editing a page inside a
    multi-hour job is ordinary, and it may not be fatal.
    """
    results = [
        a_result(repeat=1, text="before-the-edit"),
        a_result(repeat=2, text="after-the-edit"),
        a_result(repeat=3, text="after-the-edit"),
    ]

    found = sweep_verdict.judge(results, labels=["baseline"], candidate="baseline")

    assert found.verdict == sweep_verdict.PASSED
    assert [result["repeat"] for result in found.comparable] == [2, 3]
    assert [problem["why"] for problem in found.problems] == [sweep_verdict.INPUT_DRIFT_DROPPED]
    assert found.problems[0]["repeat"] == 1


def test_a_run_with_one_agreeing_repeat_left_is_refused() -> None:
    """Dropping repeats may not become a way to report a median over one reading."""
    results = [
        a_result(repeat=1, text="one"),
        a_result(repeat=2, text="two"),
        a_result(repeat=3, text="three"),
    ]

    found = sweep_verdict.judge(results, labels=["baseline"], candidate="baseline")

    assert found.verdict == sweep_verdict.REJECTED_INPUT_DRIFT
    assert found.thin == ["baseline"]
    assert sweep_verdict.TOO_FEW_AGREEING in {problem.get("why") for problem in found.problems}


def test_a_thin_run_reports_no_timing_at_all() -> None:
    """A median over one reading reads like a measurement and is not one."""
    results = [a_result(repeat=1, text="one"), a_result(repeat=2, text="two")]

    found = sweep_verdict.judge(results, labels=["baseline"], candidate="baseline")

    assert sweep_verdict.timings(found, labels=["baseline"], candidate="baseline") == {}


def test_two_repeats_that_read_the_same_text_and_wrote_different_summaries_fail() -> None:
    """That is the model being unstable, which is what this gate is for."""
    results = [a_result(repeat=1, summary="a"), a_result(repeat=2, summary="b")]

    found = sweep_verdict.judge(results, labels=["baseline"], candidate="baseline")

    assert found.verdict == sweep_verdict.REJECTED_OUTPUT_DRIFT


def test_a_publishers_edit_is_never_reported_as_the_model_being_unstable() -> None:
    """Different text may write a different summary. Saying otherwise names the
    wrong cause, and sends the reader of that failure to look at the decoder."""
    results = [
        a_result(repeat=1, text="before", summary="a"),
        a_result(repeat=2, text="after", summary="b"),
        a_result(repeat=3, text="after", summary="b"),
    ]

    found = sweep_verdict.judge(results, labels=["baseline"], candidate="baseline")

    assert found.verdict == sweep_verdict.PASSED


def test_a_paired_run_compares_the_two_cases_on_the_model_path() -> None:
    """Both cases ran on one machine, which is the whole point of pairing."""
    results = [
        a_result(label="baseline", repeat=n, model_path_ms=100_000) for n in (1, 2)
    ] + [a_result(label="no_draft", repeat=n, model_path_ms=90_000) for n in (1, 2)]

    found = sweep_verdict.judge(results, labels=["baseline", "no_draft"], candidate="no_draft")
    timing = sweep_verdict.timings(found, labels=["baseline", "no_draft"], candidate="no_draft")

    assert found.verdict == sweep_verdict.PASSED
    assert timing["candidate_vs_baseline"]["comparison_key"] == "model_path_ms"
    assert timing["candidate_vs_baseline"]["faster_by_ms"] == 10_000
    assert timing["candidate_vs_baseline"]["beats_baseline_outside_spread"] is True


def test_a_gain_inside_the_spread_is_a_gain_this_instrument_cannot_see() -> None:
    """Guardrail #10: an instrument too coarse to see a difference has said nothing."""
    results = [
        a_result(label="baseline", repeat=1, model_path_ms=100_000),
        a_result(label="baseline", repeat=2, model_path_ms=80_000),
        a_result(label="no_draft", repeat=1, model_path_ms=89_000),
        a_result(label="no_draft", repeat=2, model_path_ms=89_000),
    ]

    found = sweep_verdict.judge(results, labels=["baseline", "no_draft"], candidate="no_draft")
    timing = sweep_verdict.timings(found, labels=["baseline", "no_draft"], candidate="no_draft")

    assert timing["candidate_vs_baseline"]["faster_by_ms"] == 1_000
    assert timing["candidate_vs_baseline"]["beats_baseline_outside_spread"] is False


def test_the_parallel_case_is_judged_on_wall_clock_rather_than_the_model_path() -> None:
    """It runs two workers at once, so its gain does not show in one item's path."""
    results = [
        a_result(label="baseline", repeat=n, total_ms=200_000) for n in (1, 2)
    ] + [a_result(label="np2_inflight", repeat=n, total_ms=150_000) for n in (1, 2)]

    found = sweep_verdict.judge(
        results, labels=["baseline", "np2_inflight"], candidate="np2_inflight"
    )
    timing = sweep_verdict.timings(
        found, labels=["baseline", "np2_inflight"], candidate="np2_inflight"
    )

    assert timing["candidate_vs_baseline"]["comparison_key"] == "total_ms"


def test_a_case_that_lost_its_repeats_takes_the_run_down_with_it() -> None:
    """A paired comparison needs both sides, so one thin case refuses the run."""
    results = [
        a_result(label="baseline", repeat=1, text="same"),
        a_result(label="baseline", repeat=2, text="same"),
        a_result(label="no_draft", repeat=1, text="same"),
        a_result(label="no_draft", repeat=2, text="moved"),
    ]

    found = sweep_verdict.judge(results, labels=["baseline", "no_draft"], candidate="no_draft")

    assert found.verdict == sweep_verdict.REJECTED_INPUT_DRIFT
    assert found.thin == ["no_draft"]
