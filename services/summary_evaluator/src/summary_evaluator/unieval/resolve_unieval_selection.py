"""Which resolved control authorizes relevance for this exact request?"""

from summary_evaluator.unieval.contracts.unieval_contract import RelevanceSkipReason
from summary_evaluator.unieval.contracts.unieval_request import UnievalControls, UnievalRequest


def resolve_unieval_selection(
    request: UnievalRequest, scoring: UnievalControls
) -> tuple[UnievalControls, RelevanceSkipReason | None]:
    controls = UnievalControls.model_validate({
        **scoring.model_dump(),
        "consistency_source_mode": (
            request.consistency_source_mode or scoring.consistency_source_mode
        ),
        "evaluate_relevance": (
            scoring.evaluate_relevance
            if request.evaluate_relevance is None else request.evaluate_relevance
        ),
    })
    reason: RelevanceSkipReason | None = (
        "disabled" if not controls.evaluate_relevance
        else "reference_not_supplied" if request.reference_summary_text is None
        else None
    )
    return controls, reason
