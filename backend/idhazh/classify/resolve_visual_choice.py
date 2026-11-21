"""Resolve the model's chart references against the one article it read."""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Annotated, Final, Self

from pydantic import Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError

from idhazh.classify.plan_visual_request import VisualInput
from idhazh.contracts.base import Model
from idhazh.contracts.element import (
    ELEMENT_ID_OFFSET_DIGITS,
    Element,
    ElementKind,
    ElementTable,
    Extractor,
    derive_element_id,
)
from idhazh.contracts.visual import (
    MAX_IDS_PER_ROLE,
    EncodingRole,
    PlanCaption,
    PlanDecision,
    PlanEncodings,
    PlanReason,
    PlanTitle,
    VisualPlan,
    VisualPurpose,
    VisualType,
)
from idhazh.elements import sentence_starts
from idhazh.sanitize import sanitize
from idhazh.visual_vocabulary import PLAN_VOCABULARY_VERSION

NO_CHART: Final = "none"
# Each code counts spans in one article; it cannot outgrow the source offset.
_INDEX: Final = rf"[1-9][0-9]{{0,{ELEMENT_ID_OFFSET_DIGITS - 1}}}"
QUANTITY_CODE: Final = rf"^q{_INDEX}$"
DATE_CODE: Final = rf"^d{_INDEX}$"
LABEL_CODE: Final = rf"^l{_INDEX}$"
QuantityRef = Annotated[str, StringConstraints(pattern=QUANTITY_CODE)]
DateRef = Annotated[str, StringConstraints(pattern=DATE_CODE)]
LabelRef = Annotated[str, StringConstraints(pattern=LABEL_CODE)]
_Names = Annotated[list[PlanTitle], Field(max_length=MAX_IDS_PER_ROLE)]
_Quantities = Annotated[list[QuantityRef], Field(max_length=MAX_IDS_PER_ROLE)]
_Dates = Annotated[list[DateRef], Field(max_length=MAX_IDS_PER_ROLE)]
COMPARISONS: Final = frozenset({VisualType.BAR, VisualType.DOT, VisualType.PIE})


class ComparisonPoint(Model):
    quantity: QuantityRef
    category: LabelRef


class ChartReferences(Model):
    quantity: _Quantities = Field(default_factory=list)
    time: _Dates = Field(default_factory=list)
    quantity_x: _Quantities = Field(default_factory=list)
    entity: _Names = Field(default_factory=list)
    series: _Names = Field(default_factory=list)
    size: _Quantities = Field(default_factory=list)
    bins: _Quantities = Field(default_factory=list)
    points: Annotated[list[ComparisonPoint], Field(max_length=MAX_IDS_PER_ROLE)] = Field(
        default_factory=list
    )


class PlanChoice(Model):
    why: PlanReason
    type: str
    encodings: ChartReferences
    focus: QuantityRef | None
    whole: QuantityRef | None
    measure: PlanTitle | None = None
    context: _Dates = Field(default_factory=list)
    title: PlanTitle | None
    caption: PlanCaption | None

    @model_validator(mode="after")
    def _chart_words_are_not_data(self) -> Self:
        if self.type == NO_CHART:
            return self
        if self.title is None or not sanitize(self.title).strip():
            raise _refusal("visual_choice_title_required", "a chart answer has a title", "title")
        if self.focus is None:
            raise _refusal(
                "visual_choice_focus_required", "a chart highlights one drawn reading", "focus"
            )
        if any(character.isdigit() for character in self.why):
            raise _refusal(
                "visual_choice_prose_has_digit", "the reason must name the comparison in words",
                "why",
            )
        for field in ("why", "title", "caption"):
            words = getattr(self, field)
            if words is not None and sanitize(words) != words.strip():
                raise _refusal(
                    "visual_choice_unsafe_prose", "chart prose is plain text", field
                )
        return self


_PURPOSE: Final[Mapping[VisualType, VisualPurpose]] = {
    VisualType.BAR: VisualPurpose.COMPARISON,
    VisualType.DOT: VisualPurpose.COMPARISON,
    VisualType.LINE: VisualPurpose.TREND,
    VisualType.SLOPE: VisualPurpose.CHANGE,
    VisualType.SCATTER: VisualPurpose.RELATIONSHIP,
    VisualType.BUBBLE: VisualPurpose.RELATIONSHIP,
    VisualType.PIE: VisualPurpose.COMPOSITION,
    VisualType.STACKED_BAR: VisualPurpose.COMPOSITION,
    VisualType.HISTOGRAM: VisualPurpose.DISTRIBUTION,
}


def _refusal(rule: str, reason: str, field: str) -> PydanticCustomError:
    return PydanticCustomError(rule, reason, {"field": field})


def _source_ref(code: str, request: VisualInput, field: str) -> Element:
    if (element := request.refs.get(code)) is None:
        raise _refusal("visual_choice_unknown_ref", "no source reading has that reference", field)
    return element


def _source_phrase(
    phrase: str, text: str, sentences: Sequence[int], *,
    field: str, in_sentences: set[int] | None = None,
) -> Element:
    """Re-slice a whole phrase; do not take a partial word or guess an occurrence."""
    hits = [
        (match, bisect_right(sentences, match.start()))
        for match in re.finditer(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.IGNORECASE)
    ]
    matches = [
        (match, sentence) for match, sentence in hits
        if (in_sentences is None or sentence in in_sentences)
        and bisect_right(sentences, match.end() - 1) == sentence
    ]
    if (
        len(matches) != 1
        or not any(character.isalpha() for character in phrase)
        or phrase != phrase.strip()
        or "\n" in phrase
        or sanitize(phrase) != phrase
        or sanitize(matches[0][0].group()) != matches[0][0].group()
    ):
        raise _refusal(
            "visual_choice_unanchored_label",
            "a label must identify one literal phrase in its source evidence",
            field,
        )
    match, sentence = matches[0]
    return Element(
        kind=ElementKind.ENTITY,
        element_id=derive_element_id(ElementKind.ENTITY, match.start(), match.end()),
        span_start=match.start(),
        span_end=match.end(),
        span_excerpt=text[match.start():match.end()],
        sentence_index=sentence,
        value=None,
        unit=None,
        extractor=Extractor.MODEL,
    )


def _label_scope(
    role: EncodingRole, form: VisualType, index: int, quantities: Sequence[Element]
) -> set[int] | None:
    if form is VisualType.SLOPE:
        return {value.sentence_index for value in quantities[index * 2 : index * 2 + 2]}
    if form in {VisualType.BAR, VisualType.DOT} and role is EncodingRole.SERIES:
        # A series may be named once for multiple marks; the compiler checks pairing.
        return None
    return {quantities[index].sentence_index} if index < len(quantities) else set()


def _with_grounding(element: Element, **labels: str) -> Element:
    return Element.model_validate(element.model_dump() | labels | {
        "label_source": "visual-evidence",
        "ledger_version": VisualPlan.schema_version(),
    })


def _bind_relationship(
    channels: Mapping[EncodingRole, list[Element]], known: dict[str, Element]
) -> None:
    """A same-sentence source subject must unambiguously cover each point's measures."""
    entities = channels[EncodingRole.ENTITY]
    if len({element.sentence_index for element in entities}) != len(entities):
        raise _refusal(
            "visual_choice_ambiguous_relationship",
            "each relationship point needs a separate source sentence",
            "encodings.entity",
        )
    for role in (EncodingRole.QUANTITY, EncodingRole.QUANTITY_X, EncodingRole.SIZE):
        values = channels[role]
        if not values:
            continue
        if len(values) != len(entities):
            continue  # The existing type validator reports the incomplete channel.
        for entity, value in zip(entities, values, strict=True):
            if (
                entity.sentence_index == value.sentence_index
                and entity.span_end <= value.span_start
            ):
                identity = f"span-{entity.span_start}-{entity.span_end}"
                known[entity.element_id] = _with_grounding(entity, entity=identity)
                known[value.element_id] = _with_grounding(value, entity=identity)


def _bind_whole(
    whole: Element, parts: Sequence[Element], phrase: str, *,
    text: str, sentences: Sequence[int], known: dict[str, Element],
) -> None:
    """Use one explicitly written measure only within the slice supporting the whole."""
    scope = {whole.sentence_index}
    field = "measure"
    anchor = _source_phrase(phrase, text, sentences, field=field, in_sentences=scope)
    if (
        whole.unit is None
        or anchor.span_end > whole.span_start
        or any(part.sentence_index not in scope or part.unit != whole.unit for part in parts)
    ):
        raise _refusal(
            "visual_choice_ambiguous_whole",
            "the whole and its parts need one explicitly named measure and unit",
            field,
        )
    for value in (whole, *parts):
        known[value.element_id] = _with_grounding(
            value, measure=anchor.span_excerpt,
            measure_canonical=f"span-{anchor.span_start}-{anchor.span_end}",
        )


def _check_category_order(categories: Sequence[Element], quantities: Sequence[Element]) -> None:
    """Do not swap labels around when the source lists several readings together."""
    if len(categories) != len(quantities):
        return  # The compiler reports that there is no label for each quantity.
    by_sentence: dict[int, list[tuple[int, int]]] = {}
    for label, value in zip(categories, quantities, strict=True):
        if label.sentence_index == value.sentence_index:
            by_sentence.setdefault(value.sentence_index, []).append(
                (value.span_start, label.span_start)
            )
    for pairs in by_sentence.values():
        labels = [label for _, label in sorted(pairs)]
        if labels != sorted(labels):
            raise _refusal(
                "visual_choice_swapped_categories",
                "labels in one sentence must follow the source order of their readings",
                "encodings.category",
            )


def resolve_visual_choice(
    choice: PlanChoice, request: VisualInput, text: str, table: ElementTable,
) -> tuple[VisualPlan, ElementTable]:
    """Map the transient reply to the existing plan and article-backed elements."""
    form = next((form for form in request.forms if form.value == choice.type), None)
    if form is None:
        raise _refusal(
            "visual_choice_unsupported_type", "the renderer did not offer that form", "type"
        )
    whole = _source_ref(choice.whole, request, "whole") if choice.whole is not None else None
    if whole is not None and form not in {VisualType.PIE, VisualType.STACKED_BAR}:
        raise _refusal("visual_choice_unexpected_whole", "only composition cites a whole", "whole")
    references = choice.encodings
    if references.points and (form not in COMPARISONS or references.quantity):
        raise _refusal(
            "visual_choice_unexpected_points",
            "category points belong to comparisons and replace the quantity channel",
            "encodings.points",
        )
    source = {element.element_id: element for element in table.elements}
    known = source.copy()
    sentences = sentence_starts(text)
    channels: dict[EncodingRole, list[Element]] = {role: [] for role in EncodingRole}
    for role in (
        EncodingRole.QUANTITY, EncodingRole.QUANTITY_X, EncodingRole.TIME,
        EncodingRole.SIZE, EncodingRole.BINS,
    ):
        field = f"encodings.{role.value}"
        channels[role] = [
            _source_ref(code, request, field) for code in getattr(references, role.value)
        ]
    quantities = channels[EncodingRole.QUANTITY]
    for point in references.points:
        reading = _source_ref(point.quantity, request, "encodings.points.quantity")
        label = request.labels.get(point.quantity, {}).get(point.category)
        if label is None:
            raise _refusal(
                "visual_choice_unanchored_label",
                "the label reference must belong to its own reading",
                "encodings.points.category",
            )
        known.setdefault(label.element_id, label)
        channels[EncodingRole.CATEGORY].append(label)
        quantities.append(reading)
    for role in (EncodingRole.ENTITY, EncodingRole.SERIES):
        field = f"encodings.{role.value}"
        for index, phrase in enumerate(getattr(references, role.value)):
            scope = _label_scope(role, form, index, quantities)
            if re.fullmatch(DATE_CODE, phrase):
                element = _source_ref(phrase, request, field)
                if scope is not None and element.sentence_index not in scope:
                    raise _refusal(
                        "visual_choice_unanchored_label",
                        "a date label must be in the source sentence of its reading",
                        field,
                    )
            else:
                element = _source_phrase(phrase, text, sentences, field=field, in_sentences=scope)
                if any(
                    reading.kind is ElementKind.QUANTITY
                    and element.span_start < reading.span_end
                    and reading.span_start < element.span_end
                    for reading in request.refs.values()
                ):
                    raise _refusal(
                        "visual_choice_unanchored_label",
                        "a label must name the reading, not quote the quantity itself",
                        field,
                    )
                known.setdefault(element.element_id, element)
            channels[role].append(element)
    if form is VisualType.STACKED_BAR and whole is not None and not channels[EncodingRole.CATEGORY]:
        # A stacked chart's sole row label is its independently stated whole.
        channels[EncodingRole.CATEGORY].append(whole)
    if form in COMPARISONS:
        _check_category_order(channels[EncodingRole.CATEGORY], quantities)
    if form in {VisualType.SCATTER, VisualType.BUBBLE}:
        _bind_relationship(channels, known)
    if form is VisualType.STACKED_BAR and whole is not None and choice.measure is not None:
        _bind_whole(whole, quantities, choice.measure, text=text, sentences=sentences, known=known)
    annotations = []
    if choice.focus is not None:
        focus = _source_ref(choice.focus, request, "focus")
        if focus not in (*quantities, *channels[EncodingRole.BINS]):
            raise _refusal(
                "visual_choice_undrawn_focus", "the highlight must be a drawn reading", "focus"
            )
        annotations.append(focus.element_id)
    encodings = PlanEncodings.model_validate({
        role.value: [element.element_id for element in values] for role, values in channels.items()
    })
    ids = list(dict.fromkeys(cited for ids in encodings.filled().values() for cited in ids))
    if whole is not None and whole.element_id not in ids:
        ids.append(whole.element_id)
    if choice.context:
        # Context dates can justify prose, but never participate in an encoding.
        ids = list(dict.fromkeys([
            *ids, *(_source_ref(code, request, "context").element_id for code in choice.context),
        ]))
    plan = VisualPlan(
        version=VisualPlan.schema_version(), decision=PlanDecision.VISUAL,
        type=form, purpose=_PURPOSE[form], encodings=encodings, element_ids=ids,
        declared_whole_element_id=whole.element_id if whole is not None else None,
        annotations=annotations, why=choice.why, title=choice.title, caption=choice.caption,
        plan_version=PLAN_VOCABULARY_VERSION,
    )
    if known == source:
        return plan, table
    counts = Counter(table.candidates_found)
    counts.update(known[cited].kind for cited in known.keys() - source.keys())
    return plan, ElementTable.model_validate(table.model_dump() | {
        "elements": sorted(known.values(), key=lambda element: element.span_start),
        "candidates_found": counts,
    })
