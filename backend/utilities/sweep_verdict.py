"""Which of a bench's repeats may be compared with each other, and did anything drift?

No server, no subprocess and no clock, so it can be driven from built readings.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

#: Every repeat read the same articles and every reading is comparable.
PASSED = "passed"

#: Too few repeats agreed on what they read. Not "some drifted" - that is
#: ordinary and is reported instead.
REJECTED_INPUT_DRIFT = "rejected_input_drift"

#: Two repeats read the same text and wrote different summaries, which is the
#: model being unstable rather than a newsroom editing a page.
REJECTED_OUTPUT_DRIFT = "rejected_output_drift"

#: A repeat whose articles moved under it. Recorded, never fatal on its own.
INPUT_DRIFT_DROPPED = "input_drift_dropped"

#: What is left cannot carry a spread, so there is nothing to report.
TOO_FEW_AGREEING = "too_few_agreeing_repeats"

#: The reading a candidate is judged on. `np2_inflight` runs two workers at
#: once, so its gain shows in the wall-clock rather than in the model path.
WALL_CLOCK_CANDIDATES: frozenset[str] = frozenset({"np2_inflight"})

#: Below this a label has one reading, and one reading has no spread.
MIN_AGREEING_REPEATS = 2

BASELINE = "baseline"


class Verdict(NamedTuple):
    """What the sweep found, and which readings earned a place in the medians."""

    verdict: str
    problems: list[dict[str, Any]]
    comparable: list[dict[str, Any]]
    thin: list[str]


def input_key(result: Mapping[str, Any]) -> str:
    """The articles a repeat actually read, as one comparable string."""
    return json.dumps(result["sources"], sort_keys=True)


def judge(results: Sequence[dict[str, Any]], *, labels: Sequence[str], candidate: str) -> Verdict:
    """Keep the repeats that agree on what they read, and say what the rest were.

    **Every repeat refetches**, and a publisher editing a page inside a
    multi-hour job is ordinary rather than unlucky - on 2026-09-15 it happened
    to two of five articles on both of two dispatches. A repeat that summarized
    different text may not sit in the same median as one that did not, and that
    is what this guard is for.

    **What it may not do is throw the job away.** Until 2026-09-15 any drift at
    all raised, which discarded three complete repeats to protect a comparison
    that two of them could still have made - and did, byte for byte. So the
    largest agreeing set is what gets timed, the rest are named, and the run is
    refused only when what is left cannot carry a spread.
    """
    counted = Counter(input_key(result) for result in results)
    agreed, _ = counted.most_common(1)[0]
    comparable = [result for result in results if input_key(result) == agreed]
    drifted = [result for result in results if input_key(result) != agreed]

    verdict = PASSED
    problems: list[dict[str, Any]] = []
    expected_sources = comparable[0]["sources"]
    for result in drifted:
        problems.append(
            {
                "why": INPUT_DRIFT_DROPPED,
                "label": result["label"],
                "repeat": result["repeat"],
                "expected_sources": expected_sources,
                "actual_sources": result["sources"],
            }
        )

    thin = sorted(
        label
        for label in labels
        if sum(1 for result in comparable if result["label"] == label) < MIN_AGREEING_REPEATS
    )
    if thin:
        verdict = REJECTED_INPUT_DRIFT
        problems.append(
            {
                "why": TOO_FEW_AGREEING,
                "labels": thin,
                "kept": len(comparable),
                "ran": len(results),
            }
        )

    # Output drift is only a question about identical inputs. Asking it across
    # the drifted repeats reports a newsroom's edit as the model being
    # unstable, which sends the reader of that failure to the decoder.
    digest_sets: dict[str, list[dict[str, str]]] = {}
    for result in comparable:
        digest_sets.setdefault(result["label"], []).append(result["digests"])
    for label, maps in digest_sets.items():
        first = maps[0]
        for index, current in enumerate(maps[1:], start=2):
            if current != first:
                if verdict == PASSED:
                    verdict = REJECTED_OUTPUT_DRIFT
                problems.append(
                    {"label": label, "repeat": index, "expected": first, "actual": current}
                )
    if candidate != BASELINE and not thin:
        if digest_sets[candidate][0] != digest_sets[BASELINE][0]:
            if verdict == PASSED:
                verdict = REJECTED_OUTPUT_DRIFT
            problems.append(
                {
                    "label": candidate,
                    "expected": digest_sets[BASELINE][0],
                    "actual": digest_sets[candidate][0],
                }
            )

    return Verdict(verdict=verdict, problems=problems, comparable=comparable, thin=thin)


def _stats(comparable: Sequence[Mapping[str, Any]], label: str, key: str) -> dict[str, Any]:
    values = [result[key] for result in comparable if result["label"] == label]
    return {
        "values": values,
        "median": statistics.median(values),
        "spread": max(values) - min(values),
    }


def timings(found: Verdict, *, labels: Sequence[str], candidate: str) -> dict[str, Any]:
    """The medians, over the repeats that agreed and no others.

    Empty when a label kept fewer than two: the summary is still written,
    because the problems are what a person needs to see, but a median over one
    reading would read like a measurement (CLAUDE.md Guardrail #10).
    """
    if found.thin:
        return {}
    timing: dict[str, Any] = {
        label: {
            key: _stats(found.comparable, label, key)
            for key in ("startup_ms", "work_ms", "total_ms", "model_path_ms")
        }
        for label in labels
    }
    if candidate != BASELINE:
        key = "total_ms" if candidate in WALL_CLOCK_CANDIDATES else "model_path_ms"
        baseline = timing[BASELINE][key]
        against = timing[candidate][key]
        faster_by_ms = baseline["median"] - against["median"]
        timing["candidate_vs_baseline"] = {
            "comparison_key": key,
            "faster_by_ms": faster_by_ms,
            # A gain inside the spread is a gain this instrument cannot see.
            "beats_baseline_outside_spread": faster_by_ms
            > max(baseline["spread"], against["spread"]),
        }
    return timing
