"""What does a person reading the qualification job page need to see?"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence

from idhazh.contracts.qualification import (
    GateOutcome,
    GateStatus,
    ItemObservation,
    ItemScore,
    QualificationReport,
    QualificationShard,
)

#: A verdict a reader can find without reading the row. The words beside them
#: carry the meaning; these only say where to look.
_PASSED = "PASS"
_FAILED = "FAIL"


def _percent(part: int, whole: int) -> str:
    """A count against its denominator, because a rate alone is not a reading."""
    if whole == 0:
        return "0 of 0"
    return f"{part} of {whole} ({100 * part / whole:.0f}%)"


def _spread(values: Sequence[float]) -> str:
    """Median, and the range around it. One number cannot say a run was even."""
    if not values:
        return "no calls"
    if len(values) == 1:
        return f"{values[0]:.1f} s, n = 1"
    return (
        f"median {statistics.median(values):.1f} s, "
        f"fastest {min(values):.1f} s, slowest {max(values):.1f} s, n = {len(values)}"
    )


def _determinism_violations(observations: Iterable[ItemObservation]) -> list[str]:
    """Items whose repeats did not agree, by item.

    The gate reports one number for the shard. A reader fixing it needs to know
    WHICH item drifted, and that is not in the gate's own words.
    """
    digests: dict[str, set[str]] = {}
    for observation in observations:
        digests.setdefault(observation.item_id, set()).add(observation.output_digest)
    return sorted(item for item, seen in digests.items() if len(seen) > 1)


def _worst_scores(scores: Sequence[ItemScore], *, keep: int) -> list[ItemScore]:
    """The lowest faithfulness first - the rows a reviewer would open."""
    return sorted(scores, key=lambda score: score.hhem)[:keep]


def _which_path(shard: QualificationShard) -> str:
    """Which call path produced these numbers, said before any of them are read.

    It goes above the table rather than in it. A reader who takes the token
    counts for a single call's and finds the footnote afterwards has already
    compared them against a shard that measured different work (Guardrail #10).
    """
    if shard.calls_per_item == 1:
        return (
            "**One call per item.** The qualification's own path, which the digest "
            "does not run. Every number below is that call's."
        )
    return (
        f"**{shard.calls_per_item} calls per item** - the path the digest runs. Every "
        "per-item number below is the whole item's, so the token counts are the "
        "calls' sum and a decode cut in any of them counts the item as cut. They do "
        "not compare against a shard that made one call."
    )


def render_shard(shard: QualificationShard, *, worst_items: int = 5) -> str:
    """One shard's run, as markdown.

    The shard payload is already uploaded and already complete, so this adds no
    measurement. What it adds is that a reader does not have to download an
    artifact and read JSON to learn whether the shard did anything.

    No model name is written here as a literal. Everything comes off the
    payload, so a summary cannot describe a model the run did not use
    (Guardrail #6).
    """
    calls = shard.observations
    ok = [call for call in calls if call.ok]
    drifted = _determinism_violations(calls)

    lines = [
        f"## Qualification shard {shard.shard} of {shard.shards}",
        "",
        f"`{shard.candidate.model_id}` on {shard.date}, "
        f"{shard.repeats} repeats, {shard.elapsed_seconds / 60:.1f} minutes.",
        "",
        _which_path(shard),
        "",
        "| Reading | Value |",
        "| --- | --- |",
        f"| Articles frozen | {len(shard.corpus)} of {shard.planned} planned |",
        f"| Items that answered | {_percent(len(ok), len(calls))} |",
        f"| Schema-valid summaries | {_percent(sum(c.schema_valid for c in calls), len(calls))} |",
        f"| Summaries needing repair | {sum(c.repaired for c in calls)} |",
        f"| Items whose repeats disagreed | {len(drifted)} of {len(shard.corpus)} |",
        f"| One item, summarized | {_spread([c.summarize_seconds for c in calls])} |",
        "",
    ]

    failures: dict[str, int] = {}
    for call in calls:
        if not call.ok:
            code = call.failure_code or "unknown"
            failures[code] = failures.get(code, 0) + 1
    if failures:
        lines += ["**Why items failed.** " + ", ".join(
            f"`{code}` {count}" for code, count in sorted(failures.items())
        ), ""]

    if drifted:
        lines += [
            "**Repeats that disagreed.** The determinism gate allows none, and it "
            "names a count rather than an item, so they are named here: "
            + ", ".join(f"`{item}`" for item in drifted),
            "",
        ]

    breaches = [canary for canary in shard.canaries if canary.markers_present]
    silent = [canary for canary in shard.canaries if not canary.replied]
    lines += [
        f"**Injection canaries.** {len(shard.canaries)} run, {len(breaches)} with a planted "
        f"marker in the reply, {len(silent)} with no reply at all.",
        "",
    ]

    if shard.scores:
        lines += [
            f"### The {min(worst_items, len(shard.scores))} least faithful summaries",
            "",
            "| Item | Faithfulness | Longest copied run | Compression | Brief |",
            "| --- | --- | --- | --- | --- |",
        ]
        for score in _worst_scores(shard.scores, keep=worst_items):
            lines.append(
                f"| `{score.item_id}` | {score.hhem:.3f} | {score.verbatim_run:.3f} "
                f"| {score.compression:.2f} | {'yes' if score.brief else 'no'} |"
            )
        lines.append("")

    return "\n".join(lines)


def render_report(report: QualificationReport) -> str:
    """The merged verdict, as markdown.

    Every gate, whether it passed, and the two numbers that decided it. The
    gates do not share a unit, so `measured` and `threshold` are printed as the
    gate spelled them rather than formatted here - a column that means a
    different thing on every row is a column nobody can read.
    """
    failed = [outcome for outcome in report.gates if outcome.status is GateStatus.FAILED]
    verdict = "QUALIFIED" if report.qualified else "ESCALATE"

    lines = [
        f"## Qualification verdict: {verdict}",
        "",
        f"`{report.candidate.model_id}` on {report.date}, "
        f"{report.corpus_items} frozen articles, {report.repeats} repeats, "
        f"{report.scored} scored.",
        "",
        f"{len(report.gates) - len(failed)} of {len(report.gates)} gates passed.",
        "",
        "| | Gate | Measured | Bar | Read from |",
        "| --- | --- | --- | --- | --- |",
    ]
    # Failures first. A reader who opens this page because a run went red should
    # not have to scan eleven rows to find the one that sent them here.
    def _failures_first(outcome: GateOutcome) -> tuple[bool, str]:
        return outcome.status is GateStatus.PASSED, outcome.gate.value

    for outcome in sorted(report.gates, key=_failures_first):
        mark = _FAILED if outcome.status is GateStatus.FAILED else _PASSED
        lines.append(
            f"| {mark} | `{outcome.gate.value}` | {outcome.measured} "
            f"| {outcome.threshold} | {outcome.source} |"
        )
    lines.append("")

    if failed:
        lines += ["### What failed, in the gate's own words", ""]
        lines += [f"- **`{outcome.gate.value}`** - {outcome.detail}" for outcome in failed]
        lines.append("")

    if report.diagnostics:
        lines += [
            "### Recorded, and blocked on by nothing",
            "",
            "| Diagnostic | Value | Observations |",
            "| --- | --- | --- |",
        ]
        lines += [
            f"| {diagnostic.name} | {diagnostic.value} | {diagnostic.denominator} |"
            for diagnostic in report.diagnostics
        ]
        lines.append("")

    lines += [
        f"Corpus digest `{report.corpus_digest[:12]}`, commit `{report.commit_sha[:12]}`.",
        "",
    ]
    return "\n".join(lines)
