"""How do native GLiNER2 mentions become validated source spans?"""

from pydantic import ValidationError

from gliner_api.declare_analysis_contracts import NativeMention
from gliner_api.declare_api_contracts import (
    ApiContract,
    EntityMention,
    ExactText,
    NerRequest,
    NerResult,
    ResultValidationError,
)
from gliner_api.load_model import NativeModel


class _NativeEntities(ApiContract):
    entities: dict[ExactText, list[NativeMention]]


def normalize_entities(raw: object, request: NerRequest) -> NerResult:
    """Validate label membership and exact Unicode offsets without repairing predictions."""
    try:
        native = _NativeEntities.model_validate(raw)
        if native.entities.keys() - set(request.labels):
            raise ValueError("Native labels must belong to this request")
        entities: list[EntityMention] = []
        for label in request.labels:
            for mention in native.entities.get(label, []):
                if (
                    mention.start >= mention.end
                    or mention.end > len(request.text)
                    or request.text[mention.start : mention.end] != mention.text
                ):
                    raise ValueError("Native mention must reproduce its original source span")
                entities.append(
                    EntityMention(
                        text=mention.text,
                        label=label,
                        start_char=mention.start,
                        end_char=mention.end,
                        score=mention.confidence,
                    )
                )
        return NerResult(entities=entities)
    except (ValidationError, ValueError):
        raise ResultValidationError("The native entity result is invalid.") from None


def extract_entities(model: NativeModel, request: NerRequest) -> NerResult:
    """Use native overlapping chunks and document offsets, never a source-text cap."""
    raw = model.extract_entities_long(
        request.text,
        request.labels,
        include_confidence=True,
        include_spans=True,
    )
    return normalize_entities(raw, request)
