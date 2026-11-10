"""Which native schemas and unchanged JSON results can one analysis request carry?"""

from typing import Annotated, Self

from gliner2.inference.schema import Schema
from gliner2.inference.schema_model import ClassificationInput, EntityInput, SchemaInput
from pydantic import ConfigDict, Field, JsonValue, ValidateAs, model_validator

from gliner_api.declare_api_contracts import (
    ANALYSIS_CONTRACT_VERSION,
    API_VERSION,
    ApiContract,
    Confidence,
    ExactText,
    require_nonblank_utf8,
)


class _SingletonClassificationInput(ClassificationInput):
    """Keep the public builder's singleton support without replacing native validation."""

    model_config = ConfigDict(strict=True, allow_inf_nan=False, hide_input_in_errors=True)
    labels: list[str] | dict[str, str] = Field(min_length=1)


def _retain_classification(value: _SingletonClassificationInput) -> ClassificationInput:
    return value


_ClassificationInput = Annotated[
    ClassificationInput, ValidateAs(_SingletonClassificationInput, _retain_classification)
]

_ANALYSIS_METADATA: dict[str, JsonValue] = {
    "version": ANALYSIS_CONTRACT_VERSION,
    "changelog": [
        {"version": ANALYSIS_CONTRACT_VERSION, "change": "Add optional native metadata controls."},
        {"version": "2026-11-09", "change": "Declare native schema-driven analysis."},
        {"version": API_VERSION, "change": "Keep earlier inference payloads readable as evidence."},
    ],
}


class AnalysisSchema(SchemaInput):
    """Reuse the SDK grammar while refusing names that native formatting would overwrite."""

    model_config = ConfigDict(
        strict=True,
        allow_inf_nan=False,
        hide_input_in_errors=True,
        json_schema_extra=_ANALYSIS_METADATA,
    )
    classifications: list[_ClassificationInput] | None = None

    @model_validator(mode="after")
    def require_lossless_schema(self) -> Self:
        names = [
            *(self.structures or {}),
            *(task.task for task in self.classifications or []),
            *(self.relations or []),
        ]
        if len(names) != len(set(names)) or set(names) & {"entities", "relation_extraction"}:
            raise ValueError("Native task names must be distinct and not reserved")
        for name in names:
            require_nonblank_utf8(name)
        for task in self.classifications or []:
            for label in task.labels:
                require_nonblank_utf8(label)
            if isinstance(task.labels, dict):
                for definition in task.labels.values():
                    require_nonblank_utf8(definition)
        for structure in (self.structures or {}).values():
            fields = [field.name for field in structure.fields]
            if len(fields) != len(set(fields)):
                raise ValueError("Structure fields must be distinct")
            if structure.mode is not None and set(fields) & {"confidence", "label", "text"}:
                raise ValueError("Record fields must not collide with native metadata")
            for field in structure.fields:
                require_nonblank_utf8(field.name)
                if field.choices is not None:
                    if len(field.choices) != len(set(field.choices)):
                        raise ValueError("Field choices must be distinct")
                    for choice in field.choices:
                        require_nonblank_utf8(choice)
        for name in self.entity_attributes or {}:
            require_nonblank_utf8(name)
        self.to_native_schema()
        return self

    def to_native_schema(self, entity_confidence_threshold: float | None = None) -> Schema:
        """Parse non-classification sections, then append tasks through the public builder."""
        sections = self.model_dump(exclude={"classifications"}, exclude_none=True)
        if self.entities is not None and entity_confidence_threshold is not None:
            entities = {}
            for name in self.entities:
                value = self.entities[name] if isinstance(self.entities, dict) else None
                configuration = (
                    value.model_dump(exclude_none=True)
                    if isinstance(value, EntityInput)
                    else ({"description": value} if value is not None else {})
                )
                if configuration.get("threshold") is None:
                    configuration["threshold"] = entity_confidence_threshold
                entities[name] = configuration
            sections["entities"] = entities
        # The SDK's public empty-schema constructor has no type annotation.
        native = Schema.from_dict(sections) if sections else Schema()  # type: ignore[no-untyped-call]
        for task in self.classifications or []:
            native.classification(**task.model_dump(exclude_none=True))
        return native


class AnalyzeTextRequest(ApiContract):
    """Admit exact source text and the SDK's caller-defined schema, with no model selector."""

    model_config = ConfigDict(json_schema_extra=_ANALYSIS_METADATA)

    text: ExactText
    analysis_schema: AnalysisSchema = Field(alias="schema")
    include_confidence: bool = False
    include_spans: bool = False


class AnalyzeTextResult(ApiContract):
    """Retain the request-validated native JSON object without normalizing its representation."""

    model_config = ConfigDict(json_schema_extra=_ANALYSIS_METADATA)

    result: dict[str, JsonValue]


class NativeSelection(ApiContract):
    """Describe a native label selection without changing its confidence."""

    label: ExactText
    confidence: Confidence


class NativeText(ApiContract):
    """Describe one verbatim native value without invented metadata."""

    text: ExactText


class NativeTextScore(NativeText):
    """Describe a native choice selection that need not occur in the source."""

    confidence: Confidence


class NativeSpan(NativeText):
    """Locate a native mention in the unchanged Unicode source."""

    start: int = Field(ge=0)
    end: int = Field(gt=0)


class NativeMention(NativeSpan):
    """Locate a native scored mention in the unchanged Unicode source."""

    confidence: Confidence
