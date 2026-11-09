"""How do native schema-based selections become validated requested label IDs?"""

from pydantic import ConfigDict, TypeAdapter, ValidationError

from gliner_api.declare_analysis_contracts import NativeSelection
from gliner_api.declare_api_contracts import (
    ClassificationRequest,
    ClassificationResult,
    ResultValidationError,
    SelectedLabel,
)
from gliner_api.load_model import NativeModel

_NATIVE_CLASSIFICATIONS = TypeAdapter(
    dict[str, NativeSelection | list[NativeSelection]],
    config=ConfigDict(strict=True, allow_inf_nan=False, hide_input_in_errors=True),
)


def normalize_classifications(
    raw: object, request: ClassificationRequest
) -> ClassificationResult:
    """Reject missing tasks, invented IDs, duplicate selections and invalid confidences."""
    try:
        native = _NATIVE_CLASSIFICATIONS.validate_python(raw)
        if native.keys() != request.tasks.keys():
            raise ValueError("Native classifications must retain the requested tasks")
        classifications: dict[str, list[SelectedLabel]] = {}
        for name, task in request.tasks.items():
            prediction = native[name]
            selections = prediction if isinstance(prediction, list) else [prediction]
            if not task.multi_label and len(selections) > 1:
                raise ValueError("Single-label tasks cannot return multiple selections")
            if any(selection.label not in task.labels for selection in selections):
                raise ValueError("Every selected ID must belong to its request")
            classifications[name] = [
                SelectedLabel(id=selection.label, score=selection.confidence)
                for selection in selections
            ]
        return ClassificationResult(classifications=classifications)
    except (ValidationError, ValueError):
        raise ResultValidationError("The native classification result is invalid.") from None


def classify_text(model: NativeModel, request: ClassificationRequest) -> ClassificationResult:
    """Delegate definitions, selection mode and long-text merging to the native SDK."""
    tasks: dict[str, dict[str, object]] = {
        name: {"labels": task.labels, "multi_label": task.multi_label}
        for name, task in request.tasks.items()
    }
    raw = model.classify_text_long(request.text, tasks, include_confidence=True)
    return normalize_classifications(raw, request)
