"""How are omitted request controls resolved against frozen startup settings?"""

from pydantic import ValidationError

from hhem_evaluator.contracts.error_detail import ErrorDetail, ErrorField
from hhem_evaluator.contracts.evaluate_request import EffectiveSettings, EvaluateRequest
from hhem_evaluator.contracts.service_settings import ServiceSettings


class RequestResolutionError(ValueError):
    """Expose only the closed failure for invalid effective controls."""

    def __init__(self, error: ErrorDetail) -> None:
        self.error = error
        super().__init__(error.message)


def resolve_request(request: EvaluateRequest, settings: ServiceSettings) -> EffectiveSettings:
    """Apply both geometry defaults before validating their relationship."""
    try:
        effective = EffectiveSettings(
            chunk_words=(
                settings.scoring.chunk_words if request.chunk_words is None else request.chunk_words
            ),
            chunk_overlap_words=(
                settings.scoring.chunk_overlap_words
                if request.chunk_overlap_words is None
                else request.chunk_overlap_words
            ),
            hhem_full=(
                settings.response.hhem_full if request.hhem_full is None else request.hhem_full
            ),
            include_window_details=(
                settings.response.include_window_details
                if request.include_window_details is None
                else request.include_window_details
            ),
        )
    except ValidationError as error:
        location = error.errors(include_input=False, include_context=False)[0]["loc"]
        field: ErrorField = "chunk_words" if location == ("chunk_words",) else "chunk_overlap_words"
        raise RequestResolutionError(
            ErrorDetail.from_code("INVALID_REQUEST", "request", field=field)
        ) from None
    if effective.hhem_full and request.full_source_text is None:
        raise RequestResolutionError(
            ErrorDetail.from_code("INVALID_REQUEST", "request", field="full_source_text")
        )
    return effective
