"""Does native analysis evidence belong to its request and exact Unicode source?"""

from collections.abc import Container

from gliner2.inference.schema_model import EntityInput, FieldInput, StructureInput
from pydantic import JsonValue, TypeAdapter, ValidationError

from gliner_api.declare_analysis_contracts import (
    AnalysisSchema,
    AnalyzeTextRequest,
    AnalyzeTextResult,
    NativeMention,
    NativeSelection,
    NativeSpan,
    NativeText,
    NativeTextScore,
)
from gliner_api.declare_api_contracts import Confidence, ResultValidationError

_CONFIDENCE = TypeAdapter(Confidence)


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError("Native evidence must be an object")
    return value


def _list(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ValueError("Native evidence must be a list")
    return value


def _leaf(
    value: JsonValue, request: AnalyzeTextRequest, *, choice: bool = False
) -> tuple[str, tuple[int, int] | None]:
    spans = request.include_spans and (
        not choice or isinstance(value, dict) and ("start" in value or "end" in value)
    )
    if spans:
        mention = (
            NativeMention.model_validate(value)
            if request.include_confidence
            else NativeSpan.model_validate(value)
        )
        if (
            mention.start >= mention.end
            or mention.end > len(request.text)
            or request.text[mention.start : mention.end] != mention.text
        ):
            raise ValueError("Native evidence must reproduce its global source span")
        return mention.text, (mention.start, mention.end)
    if request.include_confidence:
        return NativeTextScore.model_validate(value).text, None
    return NativeText.model_validate({"text": value}).text, None


def _selections(
    value: JsonValue, labels: Container[str], multi_label: bool, include_confidence: bool
) -> None:
    values = [] if value is None else (value if isinstance(value, list) else [value])
    if not multi_label and len(values) > 1:
        raise ValueError("Single-label tasks cannot return multiple selections")
    selected = [
        NativeSelection.model_validate(item).label
        if include_confidence
        else NativeText.model_validate({"text": item}).text
        for item in values
    ]
    if len(selected) != len(set(selected)) or any(label not in labels for label in selected):
        raise ValueError("Native selections must be distinct offered labels")


def _entities(value: JsonValue, request: AnalyzeTextRequest) -> None:
    schema = request.analysis_schema
    offered = schema.entities or []
    entities = _object(value)
    if entities.keys() - set(offered):
        raise ValueError("Native entity types must belong to this request")
    for label, prediction in entities.items():
        config = offered[label] if isinstance(offered, dict) else None
        scalar = isinstance(config, EntityInput) and config.dtype == "str"
        values = (
            ([] if prediction is None or prediction == "" else [prediction])
            if scalar else _list(prediction)
        )
        attributes = {
            name: group
            for name, group in (schema.entity_attributes or {}).items()
            if group.applies_to is None or label in group.applies_to
        }
        seen = set()
        for value in values:
            if attributes:
                item = _object(value)
                keys = {"text"} | ({"confidence"} if request.include_confidence else set())
                keys |= {"start", "end"} if request.include_spans else set()
                if item.keys() != keys | attributes.keys():
                    raise ValueError("Native mentions must retain their declared attributes")
                leaf: JsonValue = {key: part for key, part in item.items() if key in keys}
                if not request.include_confidence and not request.include_spans:
                    leaf = item["text"]
                for name, group in attributes.items():
                    _selections(item[name], group.labels, group.multi_label, True)
            else:
                leaf = value
            _text, identity = _leaf(leaf, request)
            if identity is not None:
                if identity in seen:
                    raise ValueError("Native entity occurrences must be distinct")
                seen.add(identity)


def _field_cardinality(field: FieldInput, structure: StructureInput) -> tuple[bool, bool]:
    """Record modes use native cardinality; ordinary fields use their native dtype."""
    cardinality = field.cardinality if structure.mode is not None else None
    if cardinality is None and structure.mode == "natural" and field.name == structure.anchor:
        cardinality = "required_one"
    scalar = (
        cardinality in {"optional_one", "required_one"}
        if cardinality is not None
        else field.dtype == "str"
    )
    required = cardinality in {"required_one", "one_or_more"}
    return scalar, required


def _structures(
    value: JsonValue, structure: StructureInput, request: AnalyzeTextRequest
) -> None:
    fields = {field.name: field for field in structure.fields}
    seen_records = set()
    exclusive_spans: set[tuple[int, int]] = set()
    bound_spans: set[tuple[int, int]] = set()
    for raw_record in _list(value):
        record = _object(raw_record)
        metadata = {"confidence"} if structure.mode is not None and "confidence" in record else set()
        if record.keys() != fields.keys() | metadata:
            raise ValueError("Native records must retain exactly the requested fields")
        if metadata:
            _CONFIDENCE.validate_python(record["confidence"], strict=True)
        record_identity = []
        has_spans = False
        for name, field in fields.items():
            scalar, required = _field_cardinality(field, structure)
            prediction = record[name]
            values = (
                ([] if prediction is None or prediction == "" else [prediction])
                if scalar else _list(prediction)
            )
            if required and not values:
                raise ValueError("Required native record fields cannot be absent")
            seen = set()
            for item in values:
                text, span = _leaf(item, request, choice=field.choices is not None)
                if field.choices is not None and text not in field.choices:
                    raise ValueError("Native choices must belong to the requested field")
                identity: str | tuple[int, int] = span if span is not None else text
                if span is not None:
                    has_spans = True
                    if structure.mode is not None and field.choices is None:
                        if span in exclusive_spans or (
                            field.exclusive and span in bound_spans
                        ):
                            raise ValueError("Exclusive native spans cannot bind more than once")
                        bound_spans.add(span)
                        if field.exclusive:
                            exclusive_spans.add(span)
                    if identity in seen:
                        raise ValueError("Native field occurrences must be distinct")
                seen.add(identity)
            record_identity.append((name, frozenset(seen)))
        identity_record = tuple(record_identity)
        if has_spans and identity_record in seen_records:
            raise ValueError("Native records must be distinct")
        if has_spans:
            seen_records.add(identity_record)


def _relations(value: JsonValue, schema: AnalysisSchema, request: AnalyzeTextRequest) -> None:
    relations = _object(value)
    if relations.keys() != set(schema.relations or []):
        raise ValueError("Native relations must retain the requested relation types")
    for predictions in relations.values():
        seen = set()
        for value in _list(predictions):
            relation = _object(value)
            metadata = {"confidence"} if "confidence" in relation else set()
            if relation.keys() != {"head", "tail"} | metadata:
                raise ValueError("Native relations require exactly head and tail")
            if metadata:
                _CONFIDENCE.validate_python(relation["confidence"], strict=True)
            _head, head_span = _leaf(relation["head"], request)
            _tail, tail_span = _leaf(relation["tail"], request)
            if head_span is not None and tail_span is not None:
                identity = (head_span, tail_span)
                if identity in seen:
                    raise ValueError("Native relations must be distinct")
                seen.add(identity)


def validate_analysis_results(raw: object, request: AnalyzeTextRequest) -> AnalyzeTextResult:
    """Refuse damaged evidence without changing, repairing or manufacturing native values."""
    try:
        result = AnalyzeTextResult.model_validate({"result": raw})
        native = result.result
        schema = request.analysis_schema
        expected = set(schema.structures or {}) | {
            task.task for task in schema.classifications or []
        }
        if schema.entities is not None:
            expected.add("entities")
        if schema.relations is not None:
            expected.add("relation_extraction")
        optional = {
            name for name, structure in (schema.structures or {}).items()
            if structure.mode is not None
        }
        if native.keys() - expected or expected - optional - native.keys():
            raise ValueError("Native results must retain exactly the requested tasks")
        if schema.entities is not None:
            _entities(native["entities"], request)
        for task in schema.classifications or []:
            _selections(native[task.task], task.labels, task.multi_label, request.include_confidence)
        for name, structure in (schema.structures or {}).items():
            if name in native:
                _structures(native[name], structure, request)
        if schema.relations is not None:
            _relations(native["relation_extraction"], schema, request)
        return result
    except (ValidationError, ValueError):
        raise ResultValidationError("The native analysis result is invalid.") from None
