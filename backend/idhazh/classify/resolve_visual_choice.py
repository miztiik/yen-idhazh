"""Bind each chart proposal row to explicit observations, then build a plan."""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from pydantic_core import PydanticCustomError

from idhazh.classify.chart_reply import (
    Bubble,
    ChartProposal,
    Comparison,
    Histogram,
    Line,
    Pie,
    Reading,
    Scatter,
    SizedPoint,
    Slope,
    StackedBar,
)
from idhazh.classify.source_observations import (
    FactIdentity,
    Observation,
    Observations,
    read_observations,
)
from idhazh.classify.source_readings import (
    date_key,
    plain_words,
    reading_key,
    source_key,
    words_key,
)
from idhazh.contracts.element import (
    Element,
    ElementKind,
    ElementTable,
    Extractor,
    derive_element_id,
)
from idhazh.contracts.visual import (
    CAPTION_MAX_LENGTH,
    EncodingRole,
    PlanDecision,
    PlanEncodings,
    VisualPlan,
    VisualPurpose,
    VisualType,
)
from idhazh.elements import SpanDriftError, normalise_unit, sentence_starts
from idhazh.visual_vocabulary import PLAN_VOCABULARY_VERSION, commensurable

_R = EncodingRole
_PURPOSE: Final = {
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
_TITLE_WORD = re.compile(r"[^\W_]+|[%$\u00a3\u20ac\u20b9]")
_TITLE_JOINERS = frozenset({"and", "by", "in", "through", "versus", "vs"})
_TITLE_PUNCTUATION = re.compile(r"[\s,:()\-\u2013\u2014]+")


def _refuse(field: str, rule: str, reason: str) -> PydanticCustomError:
    return PydanticCustomError(f"visual_choice_{rule}", reason, {"field": field})


def _matches_name(proposed: str, source: str) -> bool:
    """Accept case, whitespace and a leading article, not an unchecked paraphrase."""
    return plain_words(proposed) and words_key(proposed) == words_key(source)


def _matches_reading(proposed: Reading, source: Element) -> bool:
    return (key := reading_key(proposed)) is not None and key == source_key(source)


def _match(
    facts: Sequence[Observation],
    proposed: Reading,
    *,
    field: str,
    name: str | None = None,
    measure: str | None = None,
    when: str | None = None,
) -> Observation:
    # Multiple mentions of exactly the same fact supply one observation, not more
    # rows. Different subjects, measures, dates or scopes make an unqualified tie.
    matches: dict[FactIdentity, Observation] = {}
    values: dict[FactIdentity, set[tuple[str | None, str | None]]] = {}
    held_date = date_key(when) if when is not None else None
    for fact in facts:
        if not fact.measure:
            continue
        if name is not None and (fact.label is None or not _matches_name(name, fact.label.text)):
            continue
        if measure is not None and not _matches_name(measure, fact.measure):
            continue
        if when is not None and (
            held_date is None or fact.date is None or held_date != fact.date.value
        ):
            continue
        identity = fact.identity()
        values.setdefault(identity, set()).add((fact.reading.value, fact.reading.unit))
        if _matches_reading(proposed, fact.reading):
            matches.setdefault(identity, fact)
    if len(matches) != 1 or any(len(values[key]) != 1 for key in matches):
        raise _refuse(
            field,
            "unverified_observation",
            "the reading and its roles need one explicit source fact",
        )
    return next(iter(matches.values()))


def _terms(text: str) -> tuple[str, ...]:
    return tuple(normalise_unit(word) for word in _TITLE_WORD.findall(words_key(text)))


def _title(title: str, facts: Sequence[Observation], *, group: str = "") -> None:
    if not plain_words(title) or _TITLE_PUNCTUATION.sub("", _TITLE_WORD.sub("", title)):
        raise _refuse("title", "unsafe_prose", "chart wording must be plain text")
    named = _terms(title)
    measured = {_terms(group)} if group else {_terms(fact.measure) for fact in facts}
    phrases = {terms: {terms} for terms in measured if terms}
    for fact in facts:
        if fact.label is not None:
            phrases.setdefault(_terms(fact.label.text), set())
        if fact.reading.unit:
            phrases.setdefault(_terms(fact.reading.unit), set())
        if fact.date is not None:
            phrases.setdefault(_terms(fact.date.span_excerpt), set())
            phrases.setdefault(_terms(fact.date.value or ""), set())
        if fact.action in {"approved", "produced", "generated"}:
            measure = _terms(fact.measure)
            for phrase in ((*measure, fact.action), (fact.action, *measure)):
                phrases[phrase] = {measure}
    if facts and all(fact.action == "monetary" for fact in facts):
        for unit in {fact.reading.unit for fact in facts if fact.reading.unit}:
            phrases[_terms(f"{unit} amounts")] = measured
            phrases[_terms(f"amounts in {unit}")] = measured
    phrases.pop((), None)
    # Match whole verified phrases, never isolated words lifted out of context.
    found: set[tuple[str, ...]] = set()
    while named:
        longest = max(
            (phrase for phrase in phrases if named[: len(phrase)] == phrase),
            key=len,
            default=(),
        )
        if longest:
            found.update(phrases[longest])
            named = named[len(longest) :]
        elif len(named) > 1 and named[0] in _TITLE_JOINERS:
            named = named[1:]
        else:
            break
    if named or not measured <= found:
        raise _refuse("title", "unverified_measure", "the title must name the verified measure")


def _comparable(facts: Sequence[Observation], *, dates_are_axis: bool = False) -> None:
    measures = {words_key(fact.measure) for fact in facts}
    units = [fact.reading.unit for fact in facts]
    monetary_contexts = {(fact.actor, fact.context) for fact in facts}
    linked_amounts = all(fact.action == "monetary" for fact in facts) and (
        len(monetary_contexts) == 1
    )
    if (
        (len(measures) != 1 and not linked_amounts)
        or (any(fact.action == "monetary" for fact in facts) and not linked_amounts)
        or any(not commensurable(unit, units[0]) for unit in units[1:])
        or len({fact.action for fact in facts}) > 1
    ):
        raise _refuse("rows", "incompatible_measure", "the rows do not state a comparable measure")
    if not dates_are_axis and len({fact.date.value if fact.date else None for fact in facts}) > 1:
        raise _refuse("rows", "incompatible_scope", "the rows do not cover the same stated date")
    scopes = {fact.scope for fact in facts}
    if len(scopes) > 1 and not (
        linked_amounts
        or (scopes <= {"", "this week", "on the same day"}
        and all(fact.action == "approved" for fact in facts))
    ):
        raise _refuse("rows", "incompatible_scope", "the rows do not have comparable scope")


@dataclass
class _Plan:
    text: str
    table: ElementTable
    channels: dict[EncodingRole, list[str]] = field(default_factory=dict)
    display: dict[str, str] = field(default_factory=dict)
    context: list[str] = field(default_factory=list)
    facts: list[Observation] = field(default_factory=list)
    whole: Element | None = None
    captions: list[str] = field(default_factory=list)
    elements: dict[str, Element] = field(init=False)
    starts: list[int] = field(init=False)

    def __post_init__(self) -> None:
        self.elements = {item.element_id: item for item in self.table.elements}
        self.starts = sentence_starts(self.text)

    def draw(self, role: EncodingRole, item: Element) -> None:
        self.channels.setdefault(role, []).append(item.element_id)

    def label(
        self,
        role: EncodingRole,
        observed: Observation,
        display: str,
        *,
        entity: bool = False,
    ) -> Element:
        anchor = observed.label
        if anchor is None or not _matches_name(display, anchor.text):
            raise _refuse(
                "rows.label",
                "unverified_label",
                "the label must name the attached source observation",
            )
        element = next(
            (
                item
                for item in self.elements.values()
                if item.kind in {ElementKind.ENTITY, ElementKind.PLACE}
                and (item.span_start, item.span_end) == (anchor.start, anchor.end)
            ),
            None,
        )
        if element is None:
            element = Element(
                kind=ElementKind.ENTITY,
                element_id=derive_element_id(ElementKind.ENTITY, anchor.start, anchor.end),
                span_start=anchor.start,
                span_end=anchor.end,
                span_excerpt=anchor.text,
                sentence_index=bisect_right(self.starts, anchor.start),
                value=None,
                unit=None,
                extractor=Extractor.REGEX,
            )
        self.elements[element.element_id] = element
        if entity:
            self.ground(element, entity=element.element_id)
        self.draw(role, element)
        self.show(element, display)
        return element

    def show(self, element: Element, display: str) -> None:
        if self.display.get(element.element_id, display) != display:
            raise _refuse(
                "rows.label", "unverified_label", "one source label has two display readings"
            )
        self.display[element.element_id] = display

    def observe(self, role: EncodingRole, fact: Observation) -> None:
        if any(
            held.identity() == fact.identity() or held.reading == fact.reading
            for held in self.facts
        ):
            raise _refuse(
                "rows", "repeated_fact", "a repeated mention is not a separate observation"
            )
        self.facts.append(fact)
        self.draw(role, fact.reading)
        if fact.date is not None:
            self.context.append(fact.date.element_id)
        if fact.caption:
            self.captions.append(fact.caption)

    def ground(self, element: Element, **labels: str) -> None:
        self.elements[element.element_id] = Element.model_validate(
            element.model_dump()
            | labels
            | {
                "label_source": "visual-evidence",
                "ledger_version": VisualPlan.schema_version(),
            }
        )

    def finish(self, form: VisualType, title: str) -> tuple[VisualPlan, ElementTable]:
        encodings = PlanEncodings.model_validate(
            {role.value: self.channels.get(role, []) for role in EncodingRole}
        )
        tail = [self.whole.element_id] if self.whole else []
        ids = list(
            dict.fromkeys(
                [cited for ids in self.channels.values() for cited in ids] + self.context + tail
            )
        )
        captions = list(dict.fromkeys(self.captions))
        caption = ". ".join(captions)
        if len(caption) > CAPTION_MAX_LENGTH or (caption and not plain_words(caption)):
            raise _refuse(
                "rows", "unverified_scope", "the chart cannot preserve its source context"
            )
        plan = VisualPlan(
            version=VisualPlan.schema_version(),
            decision=PlanDecision.VISUAL,
            type=form,
            purpose=_PURPOSE[form],
            encodings=encodings,
            element_ids=ids,
            declared_whole_element_id=tail[0] if tail else None,
            display_labels={
                cited: name
                for cited, name in self.display.items()
                if name != self.elements[cited].span_excerpt
            },
            why="Chart proposal verified against explicit source observations",
            title=title,
            caption=caption or None,
            plan_version=PLAN_VOCABULARY_VERSION,
        )
        original = {item.element_id for item in self.table.elements}
        counts = Counter(self.table.candidates_found)
        counts.update(self.elements[cited].kind for cited in self.elements.keys() - original)
        return plan, ElementTable.model_validate(
            self.table.model_dump()
            | {
                "elements": sorted(self.elements.values(), key=lambda item: item.span_start),
                "candidates_found": counts,
            }
        )


def _dated(
    choice: Line | Slope,
    facts: Sequence[Observation],
    builder: _Plan,
) -> None:
    if isinstance(choice, Line):
        if any(row.series is None for row in choice.rows) != all(
            row.series is None for row in choice.rows
        ):
            raise _refuse(
                "rows.series", "unverified_series", "each line row needs the same series layout"
            )
        chosen = []
        for row in choice.rows:
            item = _match(facts, row.reading, name=row.series, when=row.date, field="rows.reading")
            assert item.date is not None
            if row.series is not None:
                builder.label(_R.SERIES, item, row.series)
            builder.draw(_R.TIME, item.date)
            builder.observe(_R.QUANTITY, item)
            chosen.append(item)
        if (
            choice.rows[0].series is None
            and len({words_key(item.label.text) if item.label else None for item in chosen}) > 1
        ):
            raise _refuse(
                "rows.series", "unverified_series", "a line without series must follow one subject"
            )
    else:
        dates = []
        for change in choice.rows:
            first = _match(
                facts, change.start, name=change.label, when=choice.start_date, field="rows.start"
            )
            last = _match(
                facts, change.end, name=change.label, when=choice.end_date, field="rows.end"
            )
            assert first.date is not None and last.date is not None
            if (
                first.date.value is None
                or last.date.value is None
                or first.date.value >= last.date.value
            ):
                raise _refuse(
                    "end_date",
                    "unverified_date",
                    "slope endpoints must be distinct and chronological",
                )
            if len(first.date.value) != len(last.date.value):
                raise _refuse(
                    "end_date",
                    "unverified_date",
                    "slope endpoints must have the same date precision",
                )
            dates.append((first.date, last.date))
            builder.label(_R.ENTITY, first, change.label)
            builder.observe(_R.QUANTITY, first)
            builder.observe(_R.QUANTITY, last)
        for date in dates[0]:
            builder.draw(_R.TIME, date)
    _comparable(builder.facts, dates_are_axis=True)
    _title(choice.title, builder.facts)


def _relationships(choice: Scatter | Bubble, facts: Sequence[Observation], builder: _Plan) -> None:
    measures = [choice.x_measure, choice.y_measure]
    if isinstance(choice, Bubble):
        measures.append(choice.size_measure)
    if len({words_key(value) for value in measures}) != len(measures):
        raise _refuse(
            "x_measure", "ambiguous_axes", "each axis must name a distinct source measure"
        )
    for row in choice.rows:
        readings = [
            _match(facts, reading, name=row.label, measure=measure, field=f"rows.{axis}")
            for reading, measure, axis in zip((row.x, row.y), measures[:2], ("x", "y"), strict=True)
        ]
        if isinstance(choice, Bubble) and isinstance(row, SizedPoint):
            size = _match(
                facts, row.size, name=row.label, measure=choice.size_measure, field="rows.size"
            )
            if size.reading.value is None or Decimal(size.reading.value) <= 0:
                raise _refuse("rows.size", "unverified_observation", "bubble size must be positive")
            readings.append(size)
        if len({item.label for item in readings}) != 1:
            raise _refuse(
                "rows.label",
                "unverified_relationship",
                "all axes must be attached to one source subject and scope",
            )
        entity = builder.label(_R.ENTITY, readings[0], row.label, entity=True)
        roles = (_R.QUANTITY_X, _R.QUANTITY, _R.SIZE) if len(readings) == 3 else (
            _R.QUANTITY_X, _R.QUANTITY,
        )
        for role, observed in zip(roles, readings, strict=True):
            builder.ground(observed.reading, entity=entity.element_id)
            builder.observe(role, observed)
    _title(choice.title, builder.facts)
    builder.captions += [
        f"{axis}: {measure}"
        for axis, measure in zip(("X", "Y", "Size")[:len(measures)], measures, strict=True)
    ]


def _composition(choice: Pie | StackedBar, source: Observations, builder: _Plan) -> None:
    partitions = [
        entry
        for entry in source.partitions
        if entry.whole.label is not None
        and (
            _matches_name(choice.whole.label, entry.whole.label.text)
            or _matches_name(choice.whole.label, entry.whole.measure)
        )
        and _matches_reading(choice.whole.reading, entry.whole.reading)
    ]
    if len(partitions) != 1 or len(partitions[0].parts) != len(choice.rows):
        raise _refuse(
            "whole", "unverified_partition", "the whole and all named parts must be stated together"
        )
    partition = partitions[0]
    whole = partition.whole
    builder.whole = whole.reading
    if isinstance(choice, StackedBar):
        if not _matches_name(choice.measure, whole.measure):
            raise _refuse(
                "measure", "unverified_measure", "the stack needs one stated common measure"
            )
        builder.draw(_R.CATEGORY, whole.reading)
        builder.show(whole.reading, choice.whole.label)
        builder.captions.append(f"Declared total: {whole.reading.span_excerpt}")
    labels = [words_key(row.label) for row in choice.rows]
    if any(
        left == right or f" {left} " in f" {right} "
        for i, left in enumerate(labels)
        for j, right in enumerate(labels)
        if i != j
    ):
        raise _refuse(
            "rows.label", "unverified_partition", "part names cannot repeat or contain another part"
        )
    for row in choice.rows:
        fact = _match(partition.parts, row.reading, name=row.label, field="rows.reading")
        builder.label(_R.SERIES if isinstance(choice, StackedBar) else _R.CATEGORY, fact, row.label)
        builder.observe(_R.QUANTITY, fact)
    if isinstance(choice, Pie):
        for fact in (whole, *builder.facts):
            builder.ground(
                fact.reading, measure=whole.measure, measure_canonical=whole.reading.element_id
            )
    _title(choice.title, (whole, *builder.facts))


def _distribution(choice: Histogram, source: Observations, builder: _Plan) -> None:
    matching = [
        sample for sample in source.samples if _matches_name(choice.group, sample.group.text)
    ]
    if len(matching) != 1:
        raise _refuse(
            "group",
            "unverified_sample",
            "the group must be a stated set of individual observations",
        )
    sample = matching[0]
    proposed = Counter(reading_key(reading) for reading in choice.rows)
    if None in proposed or proposed != Counter(source_key(item) for item in sample.observations):
        raise _refuse(
            "rows",
            "unverified_sample",
            "the readings must equal the stated observations, including repeats",
        )
    for item in sample.observations:
        builder.draw(_R.BINS, item)
    _title(choice.title, (), group=sample.group.text)


def resolve_visual_choice(
    choice: ChartProposal,
    forms: tuple[VisualType, ...],
    text: str,
    table: ElementTable,
) -> tuple[VisualPlan, ElementTable]:
    """Retain source ids and exact excerpts; publish only independently verified wording."""
    form = VisualType(choice.type)
    if form not in forms:
        raise _refuse("type", "unsupported_type", "the renderer did not offer that form")
    if drift := table.span_drift(text):
        raise SpanDriftError(drift)
    if not plain_words(choice.title) or not _terms(choice.title):
        raise _refuse("title", "unsafe_prose", "chart wording must be plain text")
    source = read_observations(text, table)
    builder = _Plan(text, table)
    if isinstance(choice, Line | Slope):
        _dated(choice, source.facts, builder)
    elif isinstance(choice, Scatter | Bubble):
        _relationships(choice, source.facts, builder)
    elif isinstance(choice, Pie | StackedBar):
        _composition(choice, source, builder)
    elif isinstance(choice, Histogram):
        _distribution(choice, source, builder)
    else:
        assert isinstance(choice, Comparison)
        for row in choice.rows:
            fact = _match(source.facts, row.reading, name=row.label, field="rows.reading")
            builder.label(_R.CATEGORY, fact, row.label)
            builder.observe(_R.QUANTITY, fact)
        _comparable(builder.facts)
        _title(choice.title, builder.facts)
        for fact in builder.facts:
            if fact.date is not None and not fact.caption:
                builder.captions.append(f"Stated period: {fact.date.span_excerpt}")
    return builder.finish(form, choice.title)
