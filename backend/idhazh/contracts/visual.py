"""What a visual plan is, and the four things it may not carry.

A **visual plan** is a model's answer to "should this story carry a picture,
and if so what shape and out of which facts". It is the payload the planner's
second call decodes into, and the only thing a compiler is allowed to draw
from. Everything a reader will see is reached through it, so what it may not
hold is as much of the contract as what it holds.

**Four prohibitions, and the shape carries three and a half of them.**

1. **No geometry.** Not a pixel, not a coordinate, not an axis extent, not a
   font size. Geometry is a number, the only number here is `confidence`, and
   `confidence` is bounded to 0..1 and is never drawn. A payload that carries a
   pixel carries a key this model does not declare, and an undeclared key does
   not load. This is the rule that keeps the compiler swappable: a plan that
   names a pixel is a plan bound to one renderer.
2. **No literal values.** No field anywhere accepts a free number. A bar height
   is reached by citing an `ElementId`, and the element carries the characters
   the article itself wrote. So the worst a prompt injection can do is pick the
   wrong bars; it cannot draw the wrong number.
3. **No authored text where a reader reads a fact.** `labels` and `annotations`
   are element references, not strings - code cuts every character a reader
   sees, and the model points and names. The three prose channels that remain -
   `title`, `caption` and `why` - are length-bounded here, and whether a numeral
   inside one is matched by a cited element is the validator's check, not the
   shape's. That half is the only part of the four this module hands on.
4. **No `alt_text`.** The compiler writes it, from the elements it already
   holds, so it is satisfied by construction. Written by the model it would be
   the last unguarded prose channel in the system. The field is not declared,
   it is named in `FORBIDDEN_FIELDS`, and this module refuses to import if one
   is ever added back.

**The decoder is the control, not the prompt.** Field order is decode order, so
the order below is load-bearing: `decision` and `purpose` are committed before
`type`, and `confidence` decodes **after** `type` rather than before it. Second
in the list, a confidence would condition every field after it - the model would
be reading its own hedge back as evidence. It is recorded and it gates nothing.

`version` and `plan_version` are stamped by code and are not decoded. `version`
is when this shape last moved; `plan_version` is which planning vocabulary the
plan was made against, and a later build comparing the two is how contract drift
is found rather than drawn.

## Every role is a key, and an unused one is empty

`encodings` is one flat object with a field per role, and the schema requires
every one of them. A `bar` therefore emits `"bins": []` and `"size": []`
alongside the two channels it fills.

**Presence is the guarantee; what may be empty is the validator's.** Left
optional, a role is a role the model can simply not mention, and a plan that
names `bar` and omits `quantity` reads as a complete answer - "a confident chart
with no bars in it", which happened twice on the first live run. Required, that
plan is a decode failure at the key rather than a chart with nothing in it.
Which roles a given type may leave empty needs the type's own rule set, and a
schema cannot say "at most four roles for a `bar`", so that ruling belongs to
the validator and this shape only guarantees it has something to rule on.

The one-per-role object is why the roles are fields rather than a map. A JSON
Schema can require the keys of an object it declares; it cannot require the keys
of a map. An eighteen-branch union, one per type, was the other way to reach the
same place, and it was refused: the decoder would have to pick a branch before
it has picked a type.

**There is no `label` role, and the top-level `labels` field is why.** `labels`
is the elements whose own characters name the marks and the axes - one naming
channel for the whole picture, capped at eight marks and two axes. A `label`
role would ask the same question a second time inside `encodings`, and a model
that answers it twice can answer it two ways, with no fact to settle which. So
naming stays one field, and `encodings` stays the answer to a different question:
which elements are *drawn*, and by which channel. `event_label` is not the
exception it looks like - a timeline's `time` channel places a dot and nothing
else, so the event text is the mark rather than a name for one.

**What required-but-empty costs, measured rather than assumed.** An empty role
is `"<name>":[]` and a comma, so the nine role names cost 114 characters on a
plan that fills none and the seven a `bar` leaves empty cost 87. Tokenized with
the Qwen3 vocabulary (`Qwen3-8B-Q4_K_M.gguf` through `llama-tokenize`,
2026-09-09; Qwen3-4B, the configured planner, is the same tokenizer) that is
**28 tokens** on the declining plan and **23** on the four-bar one, about 3.1
tokens an empty role. At the 13.00 tok/s the 4B decodes at (`ubuntu-latest`,
2026-08-22) that is 2.2 s and 1.8 s a plan; at the 6.01 tok/s the configured
summarizer decodes at (`ubuntu-latest`, 2026-08-23) it is 4.7 s and 3.8 s. Over
`run.safety_ceiling_per_run` (80) items it is 2.4 to 2.9 minutes of the 4B's
`run.visual_planner_budget_minutes` (40), which is 6 to 7 percent of that budget
and 8 to 10 percent on top of the 21.0 s an item the stage measured on
2026-08-24.

## The worst-case decoded reply, in characters

Every array here has a `maxItems` and every decoded string a `maxLength`
(`ELEMENT_ID_MAX_LENGTH` and the four below), so the longest reply the decoder
can produce is arithmetic rather than a hope. A token spans at least one
character, so the character total is also a hard ceiling on tokens.

An element id costs 24 characters in JSON: `ELEMENT_ID_MAX_LENGTH` (22) plus two
quotes. An array of `n` of them costs `25n + 1`.

| Field | Key | Widest value | Characters |
| --- | --- | --- | --- |
| `decision` | 11 | `"visual"` | 19 |
| `purpose` | 10 | `"distribution"` | 24 |
| `type` | 7 | `"stacked_bar"` | 20 |
| `encodings` | 12 | 9 required role keys (88) + 9 arrays of 8 (1809) + 8 commas + 2 braces | 1919 |
| `element_ids` | 14 | 32 ids | 815 |
| `labels` | 9 | 10 ids | 260 |
| `annotations` | 14 | 4 ids | 115 |
| `why` | 6 | 240 characters | 248 |
| `title` | 8 | 80 characters | 90 |
| `caption` | 10 | 200 characters | 212 |
| `confidence` | 13 | 20 characters of decimal | 33 |

3,755 for the fields, 10 commas between them and 2 braces around them:
**3,767 characters, and therefore at most 3,767 tokens.** `worst_case_reply_characters`
recomputes that from the generated schema and this module refuses to import if it
and `WORST_CASE_REPLY_CHARACTERS` disagree, so a bound cannot move without the
ceiling moving with it.

Making every role required moved none of that. The worst case already counted
every declared key, because a grammar-constrained decoder emits them all; what
changed is that the count is now true of an ordinary plan as well as of the
worst one.

The two committed fixtures measure **838 characters** for a four-bar plan citing
eight elements and **368** for one that declines - between a fifth and a tenth
of the ceiling, because at most two of the nine roles are filled and the prose
fields are nowhere near their caps.

`encodings` is 51 percent of the ceiling and `element_ids` a further 22 percent,
so the two element-reference fields are five sixths of it. No type in the
vocabulary below fills more than four of the nine roles, so the ceiling is loose
by construction - the schema is what constrains the decoder, and the schema
cannot say "at most four roles for a bar". Which roles a type may fill is the
validator's rule.

`visuals.max_output_tokens` is 400 and it is the single-call planner's budget, not
this shape's. Call 2 decodes a summary and this plan through one budget derived
from both shapes' bounds, which is the planner's work and not this contract's -
`classify.calls.call_two_output_tokens` does the arithmetic and
`widest_json_characters` below is the half of it this module owns.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Model, SchemaVersion
from idhazh.contracts.element import ELEMENT_ID_PATTERN, ElementId

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

#: Stamped by code, so a decoder spends no character on either and neither is in
#: the arithmetic. `version` says when this shape last moved; `plan_version` says
#: which planning vocabulary the plan was made against.
CODE_STAMPED_FIELDS: Final = frozenset({"version", "plan_version"})

#: A float's repr never runs past 17 significant digits, so `0.` and a sign in
#: front of them is 20 characters and is an upper bound with room in it.
_NUMBER_MAX_CHARACTERS: Final = 20

#: The longest reply the decoder can produce, derived from the bounds below and
#: checked against the generated schema at import. Written down as well as
#: computed because it is what the planner's output budget is derived from, and
#: a number nobody can read off the module is a number nobody re-derives.
WORST_CASE_REPLY_CHARACTERS: Final = 3767

#: `<kind>-<span_start>-<span_end>` at its longest: `quantity` is the longest
#: element kind at 8 characters, and six digits an offset. `extract` truncates a
#: body at `truncation_cap_tokens` (10000), which `truncate_to_tokens` spends as
#: `int(10000 / 1.3)` = 7,692 words, so six digits covers an article of 999,999
#: characters and is an upper bound with room in it. The ceiling is here rather
#: than on `ElementId` itself because it is a decoder bound, not an identity
#: rule: the pattern, and so the identity, stays element.py's.
ELEMENT_ID_MAX_LENGTH: Final = 22
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
#: `visuals.max_chart_points`. A cap rise past 8 is a contract change on purpose:
#: the worst-case reply length has to move when the number of marks does.
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


class VisualType(StrEnum):
    """The full declarable vocabulary of forms a plan may ask for.

    Declarable is not renderable. A type with no compiler template can be named
    by a plan and is deterministically downgraded to its nearest built
    neighbour, which is how the planner says which template is worth building
    next. What may reach a reader is gated elsewhere; what may be named is here.
    """

    BAR = "bar"
    DOT = "dot"
    LINE = "line"
    AREA = "area"
    SCATTER = "scatter"
    BUBBLE = "bubble"
    SLOPE = "slope"
    STACKED_BAR = "stacked_bar"
    PIE = "pie"
    HISTOGRAM = "histogram"
    TIMELINE = "timeline"
    TABLE = "table"
    FLOW = "flow"
    COMPARISON = "comparison"
    CALLOUT = "callout"
    QUOTECARD = "quotecard"
    WHOWHAT = "whowhat"
    KEYFACTS = "keyfacts"


class EncodingRole(StrEnum):
    """What an element does in the drawing - which channel it fills.

    Nine channels cover every type above, and no type fills more than four of
    them. Whether a role is required, optional or illegal for a given type is
    the validator's rule; this names the roles that exist.

    What each channel is for is the description on the field of the same name
    in `PlanEncodings`, which is the copy that reaches the generated schema and
    so the only copy a decoder is shown. The member order is the decode order of
    that object, and the two may not drift: this module refuses to import unless
    the names and the order match.

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
    values they hold. Every field is required, so a decoder cannot answer for a
    `bar` by quietly not mentioning `quantity`; an inapplicable channel is an
    empty array, and whether empty is legal for a given type is the validator's
    rule rather than this shape's.

    Field order is decode order here as it is on the plan itself, and it is the
    order `EncodingRole` declares.
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


class VisualPlan(Contract):
    """One item's visual plan: references and closed names, and nothing else."""

    __schema_stem__: ClassVar[str] = "visual-plan"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-09T03:11",
            change=(
                "encodings became one flat object with a field per role, and the schema "
                "requires every one of them. It was a map whose keys were optional, so a "
                "reply could name a type and never mention the channel that draws it. An "
                "inapplicable role is now an empty array. No role was added or removed "
                "and no bound moved, so the worst-case reply is the same 3767 characters."
            ),
            why=(
                "Optional role keys produced a confident chart with no bars in it, twice, "
                "on the first live run, and a plan that omits quantity reads as a complete "
                "answer rather than as a failure. A JSON Schema can require the keys of an "
                "object it declares and cannot require the keys of a map, so the roles had "
                "to become fields for the decoder to be held to them. Presence is all this "
                "shape guarantees: which roles a given type may leave empty needs that "
                "type's own rule set, which is the validator's and not the schema's. The "
                "cost is nine keys on every reply and it is measured rather than assumed - "
                "28 tokens on a plan that declines and 23 on a four-bar one, about 2 "
                "seconds a plan and 6 to 7 percent of the planner's run budget."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09",
            change=(
                "Initial shape: the plan a compiler draws from, carrying element "
                "references and closed vocabularies only. No geometry field, no numeric "
                "field but a 0..1 confidence, no alt_text, and labels and annotations "
                "typed as element ids rather than as strings. Every array carries a "
                "maxItems and every decoded string a maxLength."
            ),
            why=(
                "Contracts before logic - the planner's second call and the compiler are "
                "both written against a fixed payload (Guardrail #3). The prohibitions are the "
                "point of the shape rather than a note beside it: a plan that can name a "
                "pixel is a plan bound to one renderer, and a plan that can state a "
                "number turns the worst a prompt injection can do from picking the wrong "
                "bars into drawing the wrong figure. alt_text is left out because the "
                "compiler assembles it from element values it already holds, where the "
                "model writing it would be the last prose channel in the system that no "
                "validator can check. The bounds are what make the worst-case decoded "
                "reply arithmetic rather than a hope, and the arithmetic is in the module "
                "docstring so it can be re-derived when a bound moves."
            ),
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
            "The elements whose own characters name the marks and the axes. A reference "
            "and never a string: code cuts every character a reader sees, and the model "
            "points at which characters."
        ),
    )
    annotations: list[_PlanElementId] = Field(
        default_factory=list,
        max_length=MAX_ANNOTATIONS,
        description=(
            "The elements to mark first, so one mark lands before its siblings. A "
            "reference for the same reason a label is."
        ),
    )
    why: PlanReason = Field(
        description=(
            "Why this form, or why nothing. Model prose, shown to no reader and to no "
            "reviewer - it is read when a decision is being audited and nowhere else."
        )
    )
    title: PlanTitle | None = Field(
        description="What the picture is called. Null on a plan that declines."
    )
    caption: PlanCaption | None = Field(
        description="One sentence of framing under the picture. Optional on any plan."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How sure the model was, decoded after the type so it conditions nothing. "
            "Recorded, and it gates nothing."
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
            }
            for name, value in empty.items():
                if value is not None:
                    raise ValueError(f"a plan that declines carries no {name}")
            for name, cited in (
                ("encodings", self.encodings.filled()),
                ("element_ids", self.element_ids),
                ("labels", self.labels),
                ("annotations", self.annotations),
            ):
                if cited:
                    raise ValueError(f"a plan that declines cites no {name}")
            return self
        for name, stated in (("purpose", self.purpose), ("type", self.type), ("title", self.title)):
            if stated is None:
                raise ValueError(f"a plan that proposes a visual states its {name}")
        if not self.element_ids:
            raise ValueError("a plan that proposes a visual cites the elements it draws from")
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
        for where, ids in cited.items():
            unknown = sorted(ids - declared)
            if unknown:
                raise ValueError(f"{where} cites an element the plan did not declare: {unknown[0]}")
        return self


def _leaves(schema: dict[str, Any], defs: dict[str, Any], path: str) -> list[tuple[str, Any]]:
    """Every subschema of the generated document, flattened, with `$ref` followed.

    The generated JSON Schema is what a grammar-constrained decoder is held to,
    so the two guards below are asked of that document rather than of the Python
    annotations - the schema is the surface a model's output actually meets.
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
    """Every place in the generated schema where a decoder may write a number.

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


def unbounded_leaves() -> set[str]:
    """Every place a decoder may write an unbounded string, array or map.

    A bound with nothing to total is half a decision, so this is what makes the
    worst-case arithmetic in the module docstring true rather than intended. A
    closed vocabulary needs no length: an enum is bounded by its longest member.
    """
    schema = VisualPlan.json_schema()
    defs = schema.get("$defs", {})
    loose: set[str] = set()
    for path, node in _leaves(schema, defs, ""):
        kind = node.get("type")
        if kind == "string" and "maxLength" not in node and "enum" not in node:
            loose.add(path.split(".")[0])
        elif kind == "array" and "maxItems" not in node:
            loose.add(path.split(".")[0])
        # A closed object writes `additionalProperties: false` and needs no count;
        # a map writes a value schema there, and how many keys it may hold is the
        # only thing bounding it.
        elif kind == "object" and isinstance(node.get("additionalProperties"), dict):
            if "maxProperties" not in node:
                loose.add(path.split(".")[0])
    return loose


def _resolve(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return _resolve(defs[ref.removeprefix("#/$defs/")], defs)
    return node


def _widest(node: dict[str, Any], defs: dict[str, Any]) -> int:
    """The longest JSON text this subschema can hold, in characters."""
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return _widest(defs[ref.removeprefix("#/$defs/")], defs)
    for key in ("anyOf", "oneOf"):
        if key in node:
            return max(_widest(branch, defs) for branch in node[key])
    kind = node.get("type")
    if kind == "null":
        return len("null")
    if kind == "boolean":
        # `false` is the longer of the two literals a decoder may write here.
        return len("false")
    if kind in {"number", "integer"}:
        return _NUMBER_MAX_CHARACTERS
    if kind == "string":
        if "enum" in node:
            return max(len(member) for member in node["enum"]) + 2
        return int(node["maxLength"]) + 2
    if kind == "array":
        items = int(node["maxItems"])
        return items * _widest(node["items"], defs) + max(items - 1, 0) + 2
    properties = node.get("properties")
    if properties is not None:
        # Under grammar-constrained decoding every declared key is emitted, so the
        # worst case counts them all rather than only the required ones.
        pairs = [
            len(name) + 3 + _widest(child, defs)
            for name, child in properties.items()
            if name not in CODE_STAMPED_FIELDS
        ]
        return sum(pairs) + max(len(pairs) - 1, 0) + 2
    keys = sorted((len(m) for m in _resolve(node["propertyNames"], defs)["enum"]), reverse=True)
    kept = keys[: int(node["maxProperties"])]
    value = _widest(node["additionalProperties"], defs)
    return sum(length + 3 + value for length in kept) + max(len(kept) - 1, 0) + 2


def widest_json_characters(schema: dict[str, Any]) -> int:
    """The longest JSON text a generated schema can hold, in characters.

    Public because both model calls derive their output budget from the bounds
    of the shape they will be held to, and this is that arithmetic. Written once
    here rather than copied there: two implementations of one piece disagree the
    first time a bound moves, and the one that is wrong is the one nobody reads.

    It counts every declared property, not only the required ones, because a
    grammar-constrained decoder emits them all. The two fields code stamps are
    skipped, because a decoder never writes either.
    """
    return _widest(schema, schema.get("$defs", {}))


def worst_case_reply_characters() -> int:
    """The longest plan the decoder can produce, in characters of JSON.

    Row 14's bounds exist so this is arithmetic rather than a hope, and a number
    written once in a docstring goes stale the first time a bound moves - so it
    is computed from the generated schema and checked at import instead. A token
    spans at least one character, so this is also a ceiling on tokens, which is
    what the planner's output budget is derived from.
    """
    return widest_json_characters(VisualPlan.json_schema())


_declared = set(VisualPlan.model_fields)
if not _declared.isdisjoint(FORBIDDEN_FIELDS):
    raise TypeError(
        "the compiler writes alt text from the element values it already holds; a plan "
        f"field named one of {sorted(FORBIDDEN_FIELDS)} is a prose channel no validator "
        "can check (12.8 X6)"
    )
#: The role vocabulary and the object that carries it are two spellings of one
#: list, and the validator reads the first while the decoder is held to the
#: second. Order as well as names, because field order is decode order.
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
#: `version` is stamped by code on read and is never decoded, so the decoder
#: cannot spend a token on it and it is outside the arithmetic above.
if unbounded_leaves() - {"version"}:
    raise TypeError(
        "every decoded array and string is bounded, or the worst-case reply length is a "
        f"hope - unbounded: {sorted(unbounded_leaves() - {'version'})}"
    )
if worst_case_reply_characters() != WORST_CASE_REPLY_CHARACTERS:
    raise TypeError(
        "a bound moved and the worst-case reply length did not follow it - the schema now "
        f"admits {worst_case_reply_characters()} characters against a recorded "
        f"{WORST_CASE_REPLY_CHARACTERS}; re-derive the table in the module docstring"
    )
