"""What became of this shard's typed visual requests?"""

from collections import Counter
from collections.abc import Iterable
from typing import NamedTuple

from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.visual_decision import VisualDecision


class VisualOutcomes(NamedTuple):
    """Derived request counts and the fraction not delivered in the requested form."""

    requested_types: dict[str, int]
    measured_requests: int
    wasted_decode_rate: float | None


def project_visual_outcome(decision: VisualDecision) -> dict[str, object]:
    """Copy the final decision's measurements without deriving a second outcome."""
    return decision.model_dump(
        mode="json", include={"planned_type", "rendered_type", "downgrade_depth", "marks"}
    ) | {"visual_id": decision.visual_id}


def count_visual_outcomes(rows: Iterable[ItemHealthRow]) -> VisualOutcomes:
    """Count replacements and refusals, excluding unknown historical or untyped requests."""
    requested: Counter[str] = Counter()
    wasted = 0
    for row in rows:
        if row.planned_type is None or row.downgrade_depth is None:
            continue
        requested[row.planned_type.value] += 1
        wasted += row.planned_type is not row.rendered_type
    total = sum(requested.values())
    return VisualOutcomes(dict(sorted(requested.items())), total, wasted / total if total else None)
