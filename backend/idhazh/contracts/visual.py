"""What a visual plan is, and the four things it may not carry."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError

from idhazh.contracts.base import ChangelogEntry, Contract, Model, SchemaVersion
from idhazh.contracts.element import (
    ELEMENT_ID_MAX_LENGTH,
    ELEMENT_ID_PATTERN,
    ElementId,
)
from idhazh.contracts.visual_type import VisualType as VisualType

#: The field this contract may never grow, and the reason it is spelled as a
#: name rather than left as an absence. Alt text assembled by the compiler is
#: satisfied by construction, because the compiler holds only element values;
#: alt text written by the model is prose restating the chart's own data, which
#: no validator can check (Guardrail #11). A trust boundary kept as an omission is
#: one careless widening away from gone; kept as a name, the widening does not
#: start - this module raises at import instead.
FORBIDDEN_FIELDS: Final = frozenset({"alt_text"})

#: The one numeric field, named so the "no geometry, no literal values" pair is
#: machine-checked rather than promised above. Bounded to 0..1 and drawn nowhere.
NUMERIC_FIELDS: Final = frozenset({"confidence"})

#: `<kind>-<span_start>-<span_end>` at its longest, and `ELEMENT_ID_PATTERN`
#: already admits no more than that, so `max_length` here is the belt and the
#: pattern is the braces; the number is element.py's because the identity rule
#: and this bound are one bound.
_PlanElementId = Annotated[
    ElementId, StringConstraints(pattern=ELEMENT_ID_PATTERN, max_length=ELEMENT_ID_MAX_LENGTH)
]

#: A date-stamp is at most `YYYY-MM-DDTHH:MM:SS`.
_VERSION_MAX_LENGTH: Final = 19
_PlanVersion = Annotated[SchemaVersion, StringConstraints(max_length=_VERSION_MAX_LENGTH)]

#: How many elements one plan may cite in total. `visuals.max_chart_points` is 8
#: and the widest type below, `bubble`, draws four channels per mark, so 8 x 4 is
#: the most any declarable type can reach for.
MAX_ELEMENT_IDS: Final = 32
#: One role is one channel and a channel carries one entry per mark, so this is
#: `visuals.max_chart_points`. A cap rise past 8 is a contract change on purpose,
#: and the model-facing encoding arrays read it.
MAX_IDS_PER_ROLE: Final = 8
_RoleIds = Annotated[list[_PlanElementId], Field(max_length=MAX_IDS_PER_ROLE)]
#: Eight marks and two axes.
MAX_LABELS: Final = 10
#: One mark should land first. Four is where "annotated" stops meaning anything.
MAX_ANNOTATIONS: Final = 4

TITLE_MAX_LENGTH: Final = 80
CAPTION_MAX_LENGTH: Final = 200
WHY_MAX_LENGTH: Final = 240

PlanTitle = Annotated[str, StringConstraints(min_length=1, max_length=TITLE_MAX_LENGTH)]
PlanCaption = Annotated[str, StringConstraints(min_length=1, max_length=CAPTION_MAX_LENGTH)]
PlanReason = Annotated[str, StringConstraints(min_length=1, max_length=WHY_MAX_LENGTH)]


class PlanDecision(StrEnum):
    """Whether this story wants a picture at all.

    `none` is the common and correct answer, and it is a decision rather than an
    absence - a plan that declines still records why it declined and how sure it
    was, so a refusal is legible.
    """

    #: The plan proposes a visual, and every field after `decision` describes it.
    VISUAL = "visual"
    #: The plan proposes nothing. No type, no elements, no title, no caption.
    NONE = "none"


class VisualPurpose(StrEnum):
    """What the reader is being asked to do, coarser than the type.

    A downgrade may change the type and never the purpose, so this is the thing
    that survives the ladder and the thing a cross-family move would break. Each
    member covers one or more rows of the section 7.2 type matrix.
    """

    #: Which of these is bigger - ranking and category comparison.
    COMPARISON = "comparison"
    #: Which way it is going over time.
    TREND = "trend"
    #: Whether one measure moves with another.
    RELATIONSHIP = "relationship"
    #: What it was, against what it is now.
    CHANGE = "change"
    #: What the parts of a declared whole are.
    COMPOSITION = "composition"
    #: How the values spread out.
    DISTRIBUTION = "distribution"
    #: What happened in what order.
    SEQUENCE = "sequence"
    #: The precise reading, across more than one dimension.
    DETAIL = "detail"
    #: The one figure, statement or short list worth stopping on.
    EMPHASIS = "emphasis"


class EncodingRole(StrEnum):
    """What an element does in the drawing - which channel it fills.

    Nine channels cover every type above, and no type fills more than four of
    them. Whether a role is required, optional or illegal for a given type is
    the validator's rule; this names the roles that exist.

    What each channel is for is the description on the field of the same name
    in `PlanEncodings`, which is the copy that reaches the generated schema. The
    member order is the field order of that object, and the two may not drift:
    this module refuses to import unless the names and the order match.

    There is no `label` role. What names a mark is the top-level `labels` field,
    and one fact with two homes is a fact that can disagree with itself.
    """

    CATEGORY = "category"
    QUANTITY = "quantity"
    QUANTITY_X = "quantity_x"
    TIME = "time"
    SERIES = "series"
    SIZE = "size"
    BINS = "bins"
    ENTITY = "entity"
    EVENT_LABEL = "event_label"


class PlanEncodings(Model):
    """Which elements fill which channel: every role a key, an unused one empty.

    References only - a channel names the elements that fill it and never the
    values they hold. Every field is required, so a plan cannot name a `bar` by
    quietly not mentioning `quantity`; an inapplicable channel is an empty
    array, and whether empty is legal for a given type is the validator's rule
    rather than this shape's.

    Field order is the order `EncodingRole` declares.
    """

    category: _RoleIds = Field(description="The discrete axis: what each mark is.")
    quantity: _RoleIds = Field(description="The measured axis: how big each mark is.")
    quantity_x: _RoleIds = Field(description="The second measured axis, where a type has two.")
    time: _RoleIds = Field(description="The temporal axis.")
    series: _RoleIds = Field(description="What splits the marks into groups.")
    size: _RoleIds = Field(description="The third channel, drawn as area.")
    bins: _RoleIds = Field(description="The quantity that is binned rather than plotted.")
    entity: _RoleIds = Field(description="Who or what a mark is about.")
    event_label: _RoleIds = Field(description="What names one dated event.")

    def filled(self) -> dict[EncodingRole, list[ElementId]]:
        """The channels this plan actually drew with, by role.

        Every role is present, so "which roles does this plan use" is a question
        about which are non-empty rather than about which are there. Both the
        validators below ask it, and so does anything that has to reason about a
        plan by role rather than by field.
        """
        drawn: dict[EncodingRole, list[ElementId]] = {}
        for role in EncodingRole:
            ids: list[ElementId] = getattr(self, role.value)
            if ids:
                drawn[role] = ids
        return drawn


class AxisTitles(Model):
    x: PlanTitle = Field(description="The title of the horizontal axis.")
    y: PlanTitle = Field(description="The title of the vertical axis.")
    size: PlanTitle | None = Field(default=None, description="The bubble size measure, if present.")


_RoleLabels = Annotated[list[PlanTitle], Field(max_length=MAX_IDS_PER_ROLE)]

MODEL_LABEL_ROLES: Final = (EncodingRole.CATEGORY, EncodingRole.ENTITY, EncodingRole.SERIES)


class ChartPresentation(Model):
    """Model wording in channel order, separate from source references."""

    axis_titles: AxisTitles | None = None
    category: _RoleLabels = Field(default_factory=list)
    entity: _RoleLabels = Field(default_factory=list)
    series: _RoleLabels = Field(default_factory=list)

    def filled(self) -> dict[EncodingRole, list[str]]:
        return {role: labels for role in MODEL_LABEL_ROLES if (labels := getattr(self, role.value))}


class VisualPlan(Contract):
    """One item's visual plan: references and closed names, and nothing else."""

    __schema_stem__: ClassVar[str] = "visual-plan"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-22", change="Separate model wording from reading references.",
            why="A display label is not source evidence.",
        ),
        ChangelogEntry(
            version="2026-11-21",
            change="Separate display labels from evidence spans.",
            why="Preserve the exact source slice.",
        ),
        ChangelogEntry(
            version="2026-11-18",
            change="confidence became optional.",
            why="Code builds the plan from a table now: nothing reads it and none is asked.",
        ),
        ChangelogEntry(
            version="2026-10-26T09:41",
            change="Plans may name one independently declared whole for composition charts.",
            why="A sum of parts is not evidence that the source declared those parts exhaustive.",
        ),
        ChangelogEntry(
            version="2026-09-09T03:11",
            change="Earlier changes are in git.",
            why="Git history is the archive for older contract changes.",
        ),
    )

    decision: PlanDecision = Field(
        description="Whether this story wants a picture. Decoded first, so nothing conditions it."
    )
    purpose: VisualPurpose | None = Field(
        description=(
            "What the reader is asked to do. Committed before the type, because a type "
            "chosen first turns the purpose into a rationalisation of it. Null on a plan "
            "that declines."
        )
    )
    type: VisualType | None = Field(
        description=(
            "The form, from the full declarable vocabulary. Null on a plan that declines."
        )
    )
    declared_whole_element_id: _PlanElementId | None = Field(
        default=None,
        description=(
            "The source quantity stating the whole for a pie or stacked bar. It is "
            "independent of the part quantities; code checks exact exhaustiveness."
        ),
    )
    encodings: PlanEncodings = Field(
        description=(
            "Which elements fill which channel. Every role is a key and the decoder may "
            "not skip one, so a plan that draws nothing in a channel says so with an "
            "empty array rather than by silence."
        )
    )
    element_ids: list[_PlanElementId] = Field(
        default_factory=list,
        max_length=MAX_ELEMENT_IDS,
        description=(
            "Every element this plan draws from, so the validator has one list to check "
            "existence against rather than nine."
        ),
    )
    labels: list[_PlanElementId] = Field(
        default_factory=list,
        max_length=MAX_LABELS,
        description=(
            "Historical element references for naming marks and axes."
        ),
    )
    display_labels: dict[_PlanElementId, PlanTitle] = Field(
        default_factory=dict,
        max_length=MAX_ELEMENT_IDS,
        exclude_if=lambda labels: not labels,
        description="Verified display wording keyed by its original label element.",
    )
    presentation: ChartPresentation | None = Field(
        default=None, exclude_if=lambda value: value is None,
        description="Model-written labels and axis titles, not source evidence.",
    )
    annotations: list[_PlanElementId] = Field(
        default_factory=list,
        max_length=MAX_ANNOTATIONS,
        description=(
            "Optional source references selecting one measured mark to emphasize."
        ),
    )
    why: PlanReason = Field(
        description=(
            "The recorded reason for this plan, for audit rather than display."
        )
    )
    title: PlanTitle | None = Field(
        description="What the picture is called. Null on a plan that declines."
    )
    caption: PlanCaption | None = Field(
        description="One sentence of framing under the picture. Optional on any plan."
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "How sure the model was, decoded after the type so it conditions nothing. "
            "Null where none was asked. Recorded, and it gates nothing."
        ),
    )
    plan_version: _PlanVersion = Field(
        description=(
            "The date-stamp of the planning vocabulary this plan was made against. "
            "Stamped by code, never decoded. A later build compares it against what it "
            "now holds, which is how vocabulary drift is found rather than drawn."
        )
    )

    @model_validator(mode="after")
    def _a_plan_that_declines_draws_nothing(self) -> Self:
        """`none` is a decision, so it is stated rather than left half-filled.

        A plan carrying a type and no decision to draw it is two answers to one
        question, and the compiler would have to guess which one it meant.
        """
        if self.decision is PlanDecision.NONE:
            empty = {
                "purpose": self.purpose,
                "type": self.type,
                "title": self.title,
                "caption": self.caption,
                "presentation": self.presentation,
            }
            for name, value in empty.items():
                if value is not None:
                    raise PydanticCustomError(
                        "visual_plan_decline_empty",
                        "a plan that declines carries no {field}",
                        {"field": name},
                    )
            for name, cited in (
                *(
                    (f"encodings.{role.value}", ids)
                    for role, ids in self.encodings.filled().items()
                ),
                ("element_ids", self.element_ids),
                ("labels", self.labels),
                ("display_labels", self.display_labels),
                ("annotations", self.annotations),
            ):
                if cited:
                    raise PydanticCustomError(
                        "visual_plan_decline_empty",
                        "a plan that declines cites no {field}",
                        {"field": name},
                    )
            return self
        for name, stated in (("purpose", self.purpose), ("type", self.type), ("title", self.title)):
            if stated is None:
                raise PydanticCustomError(
                    "visual_plan_field_required",
                    "a plan that proposes a visual states its {field}",
                    {"field": name},
                )
        if not self.element_ids:
            raise PydanticCustomError(
                "visual_plan_field_required",
                "a plan that proposes a visual cites the elements it draws from",
                {"field": "element_ids"},
            )
        return self

    @model_validator(mode="after")
    def _every_cited_element_is_one_the_plan_declared(self) -> Self:
        """`element_ids` is the plan's own element set, so nothing may reach past it.

        Whether each of those elements exists in the article's table is the
        validator's check. This one is cheaper and it is about the payload alone:
        a role, a label or an annotation naming an id the plan never listed is a
        plan disagreeing with itself.
        """
        declared = set(self.element_ids)
        cited: dict[str, set[str]] = {
            "labels": set(self.labels),
            "annotations": set(self.annotations),
        }
        for role, role_ids in self.encodings.filled().items():
            cited[f"encodings.{role.value}"] = set(role_ids)
        if self.declared_whole_element_id is not None:
            cited["declared_whole_element_id"] = {self.declared_whole_element_id}
        for where, ids in cited.items():
            if ids - declared:
                raise PydanticCustomError(
                    "visual_plan_reference_declared",
                    "{field} cites an element the plan did not declare",
                    {"field": where},
                )
        label_ids = {
            element_id
            for role in (EncodingRole.CATEGORY, EncodingRole.ENTITY, EncodingRole.SERIES)
            for element_id in getattr(self.encodings, role.value)
        }
        if self.display_labels.keys() - label_ids:
            raise PydanticCustomError(
                "visual_plan_reference_declared",
                "{field} must name a drawn label element",
                {"field": "display_labels"},
            )
        if self.presentation is not None and label_ids:
            raise ValueError("model wording and source label channels cannot be mixed")
        return self


def _leaves(schema: dict[str, Any], defs: dict[str, Any], path: str) -> list[tuple[str, Any]]:
    """Every subschema of the generated document, flattened, with `$ref` followed.

    The guard below is asked of the generated JSON Schema rather than of the
    Python annotations - the schema is the surface every other reader of a
    plan meets.
    """
    found: list[tuple[str, Any]] = [(path, schema)]
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        found += _leaves(defs[ref.removeprefix("#/$defs/")], defs, path)
    for key in ("items", "additionalProperties", "propertyNames"):
        child = schema.get(key)
        if isinstance(child, dict):
            found += _leaves(child, defs, f"{path}.{key}")
    for key in ("anyOf", "oneOf", "allOf"):
        for index, child in enumerate(schema.get(key, [])):
            found += _leaves(child, defs, f"{path}.{key}[{index}]")
    for name, child in schema.get("properties", {}).items():
        found += _leaves(child, defs, f"{path}.{name}" if path else name)
    return found


def numeric_leaves() -> set[str]:
    """Every place in the generated schema where a payload may carry a number.

    Geometry is a number and a drawn value is a number, so prohibitions 1 and 2
    are one question asked of the schema: which fields admit one?
    """
    schema = VisualPlan.json_schema()
    defs = schema.get("$defs", {})
    return {
        path.split(".")[0]
        for path, node in _leaves(schema, defs, "")
        if node.get("type") in {"number", "integer"}
    }


_declared = set(VisualPlan.model_fields)
if not _declared.isdisjoint(FORBIDDEN_FIELDS):
    raise TypeError(
        "the compiler writes alt text from the element values it already holds; a plan "
        f"field named one of {sorted(FORBIDDEN_FIELDS)} is a prose channel no validator "
        "can check (12.8 X6)"
    )
#: The role vocabulary and the object that carries it are two spellings of one
#: list, and the validator reads the first while a saved plan is held to the
#: second. Order as well as names, so the two never disagree about which channel
#: is which.
if tuple(PlanEncodings.model_fields) != tuple(role.value for role in EncodingRole):
    raise TypeError(
        "every role is a channel and every channel is a role, in one order - "
        f"EncodingRole says {[role.value for role in EncodingRole]} and PlanEncodings "
        f"says {list(PlanEncodings.model_fields)}"
    )
if numeric_leaves() != NUMERIC_FIELDS:
    raise TypeError(
        "a visual plan carries no geometry and no literal value, so the only number in it "
        f"is {sorted(NUMERIC_FIELDS)} - found {sorted(numeric_leaves())}"
    )
