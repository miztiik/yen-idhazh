"""Which compiled chart figures survived onto a run's final published cards?"""

from __future__ import annotations

from collections.abc import Sequence

from idhazh.contracts.chart_evidence import ChartEvidence
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.visual_decision import VisualDecision, VisualKind, VisualState


def published_chart_evidence(
    items: Sequence[DigestItem], decisions: Sequence[VisualDecision]
) -> ChartEvidence | None:
    """Sum exact counts for the caller's run-owned cards, never chart percentages."""
    by_item = {decision.item_id: decision for decision in decisions}
    displayed = derived = trusted = 0
    for item in items:
        visual = item.visual
        if (
            item.same_story_as is not None
            or visual is None
            or visual.kind is not VisualKind.CHART
            or visual.state is not VisualState.RENDERED
        ):
            continue
        decision = by_item.get(item.item_id)
        if (
            decision is None
            or decision.visual_state is not VisualState.RENDERED
            or decision.data_path != visual.data_path
            or decision.chart_evidence is None
        ):
            return None
        evidence = decision.chart_evidence
        displayed += evidence.displayed_values
        derived += evidence.derived_values
        trusted += evidence.trusted_values
    return ChartEvidence.from_counts(displayed=displayed, derived=derived, trusted=trusted)
