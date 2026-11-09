"""Does native analysis evidence belong to its request and exact Unicode source?"""

from collections.abc import Container

from gliner2.inference.schema_model import EntityInput, FieldInput, StructureInput
from pydantic import JsonValue, ValidationError

from gliner_api.declare_analysis_contracts import (
    AnalysisSchema,
    AnalyzeTextRequest,
    AnalyzeTextResult,
    NativeMention,
    NativeSelection,
    NativeTextScore,
)
from gliner_api.declare_api_contracts import ResultValidationError


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError("Native evidence must be an object")
    return value


def _list(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ValueError("Native evidence must be a list")
    return value


def _mention(value: JsonValue, text: str) -> NativeMention:
    mention = NativeMention.model_validate(value)
    if (
        mention.start >= mention.end
        or mention.end > len(text)
        or text[mention.start : mention.end] != mention.text
    ):
        raise ValueError("Native evidence must reproduce its global source span")
    return mention


def _selections(value: JsonValue, labels: Container[str], multi_label: bool) -> None:
    values = value if isinstance(value, list) else [value]
    if not multi_label and len(values) > 1:
        raise ValueError("Single-label tasks cannot return multiple selections")
    selected = [NativeSelection.model_validate(item).label for item in values]
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
        values = ([] if prediction is None else [prediction]) if scalar else _list(prediction)
        attributes = {
            name: group
            for name, group in (schema.entity_attributes or {}).items()
            if group.applies_to is None or label in group.applies_to
        }
        seen = set()
        for value in values:
            item = _object(value)
            if item.keys() != {"text", "confidence", "start", "end"} | attributes.keys():
                raise ValueError("Native mentions must retain exactly their declared attributes")
            mention = _mention(
                {key: part for key, part in item.items() if key not in attributes}, request.text
            )
            identity = (mention.start, mention.end)
            if identity in seen:
                raise ValueError("Native entity occurrences must be distinct")
            seen.add(identity)
            for name, group in attributes.items():
                _selections(item[name], group.labels, group.multi_label)


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


def _structures(value: JsonValue, structure: StructureInput, text: str) -> None:
    fields = {field.name: field for field in structure.fields}
    seen_records = set()
    exclusive_spans: set[tuple[int, int]] = set()
    bound_spans: set[tuple[int, int]] = set()
    for value in _list(value):
        record = _object(value)
        if record.keys() != fields.keys():
            raise ValueError("Native records must retain exactly the requested fields")
        record_identity = []
        for name, field in fields.items():
            scalar, required = _field_cardinality(field, structure)
            prediction = record[name]
            values = ([] if prediction is None else [prediction]) if scalar else _list(prediction)
            if required and not values:
                raise ValueError("Required native record fields cannot be absent")
            seen = set()
            for item in values:
                if field.choices is not None:
                    choice = NativeTextScore.model_validate(item)
                    if choice.text not in field.choices:
                        raise ValueError("Native choices must belong to the requested field")
                    identity: str | tuple[int, int] = choice.text
                else:
                    mention = _mention(item, text)
                    identity = (mention.start, mention.end)
                    if structure.mode is not None:
                        if identity in exclusive_spans or (
                            field.exclusive and identity in bound_spans
                        ):
                            raise ValueError("Exclusive native spans cannot bind more than once")
                        bound_spans.add(identity)
                        if field.exclusive:
                            exclusive_spans.add(identity)
                if identity in seen:
                    raise ValueError("Native field selections must be distinct")
                seen.add(identity)
            record_identity.append((name, frozenset(seen)))
        identity_record = tuple(record_identity)
        if identity_record in seen_records:
            raise ValueError("Native records must be distinct")
        seen_records.add(identity_record)


def _relations(value: JsonValue, schema: AnalysisSchema, text: str) -> None:
    relations = _object(value)
    if relations.keys() != set(schema.relations or []):
        raise ValueError("Native relations must retain the requested relation types")
    for predictions in relations.values():
        seen = set()
        for value in _list(predictions):
            relation = _object(value)
            if relation.keys() != {"head", "tail"}:
                raise ValueError("Native relations require exactly head and tail")
            head = _mention(relation["head"], text)
            tail = _mention(relation["tail"], text)
            identity = (head.start, head.end, tail.start, tail.end)
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
        if native.keys() != expected:
            raise ValueError("Native results must retain exactly the requested tasks")
        if schema.entities is not None:
            _entities(native["entities"], request)
        for task in schema.classifications or []:
            _selections(native[task.task], task.labels, task.multi_label)
        for name, structure in (schema.structures or {}).items():
            _structures(native[name], structure, request.text)
        if schema.relations is not None:
            _relations(native["relation_extraction"], schema, request.text)
        return result
    except (ValidationError, ValueError):
        raise ResultValidationError("The native analysis result is invalid.") from None
