"""Does the qualification job page say what the run measured?"""

from __future__ import annotations

import pytest
import test_qualify as built
from pydantic import ValidationError

from idhazh.contracts.qualification import (
    Diagnostic,
    GateName,
    GateOutcome,
    GateStatus,
    QualificationReport,
)
from idhazh.evals import qualification_summary

pytestmark = pytest.mark.contract


def a_report(
    *,
    failing: GateName | None = None,
    omit: GateName | None = None,
    shortfalls: list[str] | None = None,
) -> QualificationReport:
    """Eleven gates, one of them optionally red or absent. Built, never read off a run.

    The renderer is about what a reader is shown, so its input is composed here:
    a committed report would tie these assertions to whichever model was
    qualified last, and a failing gate is exactly the case no committed report
    holds.
    """
    gates = [
        GateOutcome(
            gate=gate,
            status=GateStatus.FAILED if gate is failing else GateStatus.PASSED,
            measured="0.612" if gate is failing else "1.000",
            threshold="0.700",
            source="evaluation.faithfulness_floor",
            detail="mean faithfulness over the scored items",
        )
        for gate in GateName
        if gate is not omit
    ]
    return QualificationReport(
        version=QualificationReport.schema_version(),
        date="2026-09-15",
        commit_sha="0123456789abcdef",
        runner="ubuntu-latest",
        candidate=built.a_passing_shard().candidate,
        scorer=built.a_passing_shard().scorer,
        corpus_digest="a" * 64,
        corpus_items=12,
        planned=12,
        repeats=3,
        scored=12,
        gates=gates,
        corpus_shortfalls=shortfalls or [],
        diagnostics=[
            Diagnostic(
                name="mean compression",
                value="0.31",
                unit="summary words per source word",
                denominator=12,
            )
        ],
        qualified=failing is None,
        detail="every gate passed" if failing is None else "faithfulness_floor measured 0.612",
    )


def test_a_shard_page_names_its_denominator_everywhere_it_names_a_count() -> None:
    """A rate with no denominator is how an unmeasured number gets cited later.

    Twelve calls out of twelve is a different reading from one out of one, and
    the page is read by somebody deciding whether the shard did enough work to
    be worth believing (Guardrail #10).
    """
    shard = built.a_passing_shard()
    page = qualification_summary.render_shard(shard)

    assert f"| Articles frozen | {len(shard.corpus)} of {shard.planned} planned |" in page
    assert "n = " in page, "the latency reading must carry its sample size"
    assert "%)" in page, "a count against its denominator, not a bare number"


def test_a_shard_page_names_the_items_the_sampler_reworded() -> None:
    """`wording_spread` reports a count. A reader asking how far the sampler went
    needs the article, and this page is the only place it is named."""
    shard = built.a_passing_shard()
    reworded = shard.observations[0].item_id
    shifted = [
        call.model_copy(update={"output_digest": "b" * 64})
        if call.item_id == reworded and call.repeat == 2
        else call
        for call in shard.observations
    ]

    page = qualification_summary.render_shard(shard.model_copy(update={"observations": shifted}))

    assert "worded more than one way" in page
    assert reworded in page


def test_a_shard_page_with_one_wording_each_does_not_invent_a_section() -> None:
    page = qualification_summary.render_shard(built.a_passing_shard())

    assert "worded more than one way." not in page
    assert "Items worded more than one way | 0 of" in page


def test_a_failed_call_is_named_by_its_code_rather_than_counted_away() -> None:
    """A failure that vanishes takes the denominator with it."""
    shard = built.a_passing_shard()
    broken = [
        call.model_copy(update={"ok": False, "failure_code": "model_refused"})
        if index == 0
        else call
        for index, call in enumerate(shard.observations)
    ]

    page = qualification_summary.render_shard(shard.model_copy(update={"observations": broken}))

    assert "Why items failed" in page
    assert "`model_refused` 1" in page


def test_the_verdict_puts_the_failing_gate_above_the_passing_ones() -> None:
    """A reader opens this page because a run went red. Do not make them scan.

    One row of the table sent them here: the failing gate is the first row and
    its own words are repeated under it, because `measured` and `threshold` say
    what happened and `detail` says what it means.
    """
    page = qualification_summary.render_report(a_report(failing=GateName.FAITHFULNESS_FLOOR))

    rows = [line for line in page.splitlines() if line.startswith("| FAIL") or line.startswith("| PASS")]
    assert rows[0].startswith("| FAIL"), "the failing gate is not the first row"
    assert sum(row.startswith("| FAIL") for row in rows) == 1
    assert len(rows) == len(GateName)

    assert "ESCALATE" in page
    assert "What failed, in the gate's own words" in page
    assert "faithfulness_floor" in page
    assert "0.612" in page and "0.700" in page, "both numbers, in the gate's own unit"


def test_a_clean_verdict_says_so_and_prints_no_failure_section() -> None:
    page = qualification_summary.render_report(a_report())

    assert "QUALIFIED" in page
    assert "ESCALATE" not in page
    assert "What failed" not in page
    assert f"{len(GateName)} of {len(GateName)} gates passed" in page


def test_a_report_may_not_omit_any_gate() -> None:
    """Every gate is asked of every run, so a report missing one is refused by name.

    That is what stops a run dropping a gate it did not like and publishing the
    verdict anyway. `determinism` was the one exception until 2026-09-18, when
    the owner retired the gate rather than the rule.
    """
    assert "determinism" not in {gate.value for gate in GateName}
    for gate in GateName:
        with pytest.raises(ValidationError, match=gate.value):
            a_report(omit=gate)


def test_the_verdict_counts_the_gates_it_was_given() -> None:
    """A page that named a gate the run did not ask would claim a number nobody
    measured (Guardrail #10)."""
    page = qualification_summary.render_report(a_report())
    rows = [line for line in page.splitlines() if line.startswith(("| FAIL", "| PASS"))]

    assert len(rows) == len(GateName)
    assert "`determinism`" not in page


def test_neither_page_writes_a_model_name_it_was_not_given() -> None:
    """The Oracle. A page that spells a model can describe a run that used another.

    Both renderers take the name off the payload, so a summary cannot name a
    model the run did not serve (Guardrail #6). Rename the candidate and the
    old name must be gone from both pages.
    """
    shard = built.a_passing_shard()
    renamed = shard.candidate.model_copy(update={"model_id": "a-model-nobody-has-served"})

    shard_page = qualification_summary.render_shard(shard.model_copy(update={"candidate": renamed}))
    report = a_report()
    report_page = qualification_summary.render_report(report.model_copy(update={"candidate": renamed}))

    for page in (shard_page, report_page):
        assert "a-model-nobody-has-served" in page
        assert shard.candidate.model_id not in page
