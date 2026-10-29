"""How is one settled visual decision filed without losing another actual attempt?"""

from pathlib import Path

from idhazh import ledger
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual import PlanDecision
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.contracts.visual_telemetry import FAMILY_OF, VisualAttemptRow
from idhazh.elements import ExtractionHealth
from idhazh.visual_outcomes import project_visual_outcome


def project(
    decision: VisualDecision,
    *,
    date: str,
    run_id: str,
    extraction: ExtractionHealth | None,
) -> VisualAttemptRow:
    """Copy producer evidence; deepest search depth is not selected replacement depth."""
    outcome = project_visual_outcome(decision)
    outcome["downgrade_depth"] = decision.deepest_downgrade_depth
    return VisualAttemptRow.model_validate(
        outcome | {
            "date": date,
            "run_id": run_id,
            "item_id": decision.item_id,
            "decision": PlanDecision.VISUAL
            if decision.drafted_chart or decision.planned_type is not None
            else PlanDecision.NONE,
            "none_reason": decision.none_reason,
            "rejection_reason": decision.rejection_reason,
            "potential_primary": extraction.element_class if extraction else None,
            "family": FAMILY_OF[decision.planned_type] if decision.planned_type else None,
            "elements_found": extraction.elements_found if extraction else None,
            "state": decision.visual_state,
            "gate_floor_applied": decision.gate_floor_applied,
        }
    )


def record(
    state_dir: Path,
    decision: VisualDecision,
    *,
    date: str,
    identity: WriterIdentity,
    extraction: ExtractionHealth | None,
) -> list[Path]:
    """File one actual decision, using its identity to keep distinct attempts apart."""
    row = project(decision, date=date, run_id=identity.run_id, extraction=extraction)
    return ledger.persist(
        state_dir,
        [row],
        ledger=LedgerName.VISUAL_DESIGN_ATTEMPTS,
        covers=date,
        identity=identity.model_copy(update={"producer": f"{__name__}:{decision.visual_id}"}),
    )
