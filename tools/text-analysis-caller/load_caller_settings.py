"""Which committed native schema and output controls does the reporting caller send?"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, ClassVar, Final

from gliner2.inference.schema_model import EntityInput, SchemaInput
from gliner_api.load_settings import SettingsChange
from project_gliner_analysis import EVENT_FIELDS
from pydantic import ConfigDict, Field, TypeAdapter

CALLER_SETTINGS_VERSION: Final = "2026-11-10"
CALLER_SETTINGS_PATH: Final = Path("config") / "text-analysis" / "caller.json"


@dataclass(frozen=True)
class CallerAnalysisSettings:
    """Keep extraction definitions in one native schema, independently of classification."""

    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        allow_inf_nan=False,
        hide_input_in_errors=True,
        json_schema_extra={
            "version": CALLER_SETTINGS_VERSION,
            "changelog": [
                {
                    "version": CALLER_SETTINGS_VERSION,
                    "change": "Configure native reporting evidence.",
                }
            ],
        }
    )

    version: Annotated[str, Field(json_schema_extra={"const": CALLER_SETTINGS_VERSION})]
    changelog: Annotated[list[SettingsChange], Field(min_length=1, max_length=5)]
    analysis_schema: Annotated[SchemaInput, Field(alias="schema")]
    include_confidence: bool = False
    include_spans: bool = False

    def __post_init__(self) -> None:
        versions = [entry.version for entry in self.changelog]
        if (
            self.version != CALLER_SETTINGS_VERSION
            or versions[0] != self.version
            or versions != sorted(set(versions), reverse=True)
        ):
            raise ValueError("Caller settings require the current dated shape and changelog.")
        schema = self.analysis_schema
        if (
            not isinstance(schema.entities, dict)
            or schema.classifications is not None
            or schema.relations is not None
            or schema.entity_attributes is not None
        ):
            raise ValueError("The caller accepts described entities and optional event records.")
        for entity in schema.entities.values():
            if (
                not isinstance(entity, EntityInput)
                or not entity.description
                or not entity.description.strip()
            ):
                raise ValueError("Each offered entity requires its configured description.")
        if schema.structures is not None:
            if set(schema.structures) != {"events"}:
                raise ValueError("The caller accepts only its optional events structure.")
            structure = schema.structures["events"]
            if (
                structure.mode != "natural"
                or structure.anchor != "action"
                or [field.name for field in structure.fields] != list(EVENT_FIELDS)
            ):
                raise ValueError("Events require the ordered action-anchored native template.")
            for index, field in enumerate(structure.fields):
                if (
                    field.dtype != ("str" if index == 0 else "list")
                    or field.cardinality != ("required_one" if index == 0 else "zero_or_more")
                    or field.exclusive
                    or field.choices is not None
                ):
                    raise ValueError("Event roles require their nonexclusive native cardinality.")


def load_caller_settings(root: Path, labels: list[str]) -> CallerAnalysisSettings:
    """Refuse drift from the existing ordered presentation offering, without a fallback map."""
    settings: CallerAnalysisSettings = TypeAdapter(CallerAnalysisSettings).validate_json(
        (root / CALLER_SETTINGS_PATH).read_bytes(), strict=True
    )
    if list(settings.analysis_schema.entities or []) != labels:
        raise ValueError("Caller entity descriptions differ from the presentation offering.")
    return settings
