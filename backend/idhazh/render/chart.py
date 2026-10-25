"""A plan becomes the data a reader's browser draws. Nothing here draws.

**The reader's browser draws the chart and the pipeline never draws one**
(owner ruling, 2026-09-13,
[`docs/architecture/publishing/visuals.md`](../../../docs/architecture/publishing/visuals.md)).
Until then this module also held `render_chart`, which handed a Vega-Lite spec
to `vl-convert` and got SVG bytes back. That half is gone, with the dependency,
the 495 committed drawings and the fixed canvas they were drawn on.

**The file kept its name because the name was never about the renderer.**
`chart.py` says what it produces, not how, and it still produces a chart - as
data now rather than as pixels. Stripping it in place is also the diff a
reviewer can read: the resolution path below, which is the whole safety
argument, shows as untouched lines rather than as a file that arrived from
nowhere (Fowler, 2026-09-13).

`compile_chart` takes one validated `VisualPlan` and one article's element table
and returns what a reader gets: the sentence a screen reader hears, and the
marks a browser draws. It compiles only the position-and-length family, and a
type this build cannot compile is refused by name rather than approximated.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final, NamedTuple

from idhazh.contracts.chart_evidence import ChartEvidence
from idhazh.contracts.derived import DisplayedValue
from idhazh.contracts.element import Element, ElementId, ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import EncodingRole, PlanDecision, VisualPlan, VisualType
from idhazh.contracts.visual_data import (
    RENDERER_VERSION,
    VisualData,
    VisualEncoding,
    VisualMark,
)
from idhazh.derived_values import measure_displayed_values, resolve_displayed_values
from idhazh.sanitize import sanitize
from idhazh.visual_vocabulary import VALUE_ROLES

#: How many of an element's own characters name one bar. The drawn label is the
#: article's text, so it is cut rather than reworded.
MARK_NAME_MAX: Final = 40
#: What a screen reader gets, and the same cap `UntrustedLine` holds the
#: decision's `alt_text` to.
ALT_TEXT_MAX: Final = 300


class CompileError(RuntimeError):
    """The plan did not become data. The item still publishes, without a picture.

    It stood under a `RenderError` parent until 2026-09-13, when the renderer
    that raised the parent was deleted. A parent with no other subclass and no
    raiser left is a name that only ever widens an `except`, so the two
    collapsed into this one.
    """


class CompiledChart(NamedTuple):
    """What a plan becomes: the words a reader hears, and the marks a browser draws.

    Both from one call and one resolution of the plan. The alt text is assembled
    from the same figures the marks carry, so the sentence and the picture cannot
    disagree - which is the reason `alt_text` is not a field the model may write
    (`docs/architecture/publishing/visuals.md`).

    Evidence counts the same numeric sequence that supplies the marks.
    """

    alt_text: str
    data: VisualData
    evidence: ChartEvidence


class _Figure(NamedTuple):
    """One quantity and what it measures, read off a resolved plan.

    `stated` is the characters the source writes and `value` is the number they
    mean. Both, from one branch, because the alt text is written from the number
    and the published data carries the characters - and a second function
    reaching for the same figure is the drift that would let the sentence and
    the picture disagree.
    """

    stated: str
    value: Decimal
    unit: str | None


def can_compile(visual_type: VisualType | None) -> bool:
    """The current compiler capability, not the configurable request vocabulary."""
    return visual_type in {VisualType.BAR, VisualType.DOT, VisualType.SLOPE}


def compile_chart(
    plan: VisualPlan, table: ElementTable, *, visuals: VisualsConfig
) -> CompiledChart:
    """Compile a position-and-length plan as marks grounded in the article.

    Bar and dot pair categories and optional series labels with quantities.
    Slope pairs two time labels with consecutive quantity pairs and one entity
    or series label per line. Other source channels are never compiled by
    approximation.
    """
    if plan.decision is not PlanDecision.VISUAL:
        raise CompileError("this plan asks for no picture, so there is nothing to compile")
    visual_type = plan.type
    if visual_type is None or not can_compile(visual_type):
        named = visual_type.value if visual_type is not None else "no type"
        raise CompileError(f"this build draws bar, dot and slope, and the plan says {named}")

    resolved = resolve_displayed_values(plan, table, visuals=visuals)
    if resolved.refusal is not None:
        raise CompileError(f"{resolved.refusal.check.value}: {resolved.refusal.detail}")

    known = {element.element_id: element for element in table.elements}
    allowed = (
        {EncodingRole.CATEGORY, EncodingRole.QUANTITY, EncodingRole.SERIES}
        if visual_type in (VisualType.BAR, VisualType.DOT)
        else {EncodingRole.TIME, EncodingRole.QUANTITY, EncodingRole.SERIES, EncodingRole.ENTITY}
    )
    unsupported = [
        role.value
        for role in EncodingRole
        if role not in allowed and getattr(plan.encodings, role.value)
    ]
    if unsupported:
        raise CompileError(
            f"{visual_type.value} cannot draw source channels: {', '.join(unsupported)}"
        )
    channels = {
        role: [value for value in resolved.values if value.role is role] if role in allowed else []
        for role in EncodingRole
    }
    _check_channel_pairing(visual_type, channels, known)
    data, figures = _chart_data(table.item_id, channels, plan, visual_type, known)
    return CompiledChart(
        _chart_alt_text(visual_type, channels, figures, known),
        data,
        measure_displayed_values(channels[EncodingRole.QUANTITY], table),
    )


def compile_bar(plan: VisualPlan, table: ElementTable, *, visuals: VisualsConfig) -> CompiledChart:
    """Compile a bar plan for callers that explicitly request that shape."""
    if plan.decision is not PlanDecision.VISUAL:
        return compile_chart(plan, table, visuals=visuals)
    if plan.type is not VisualType.BAR:
        named = plan.type.value if plan.type is not None else "no type"
        raise CompileError(f"compile_bar cannot compile {named}")
    return compile_chart(plan, table, visuals=visuals)


def _check_channel_pairing(
    visual_type: VisualType,
    channels: Mapping[EncodingRole, Sequence[DisplayedValue]],
    known: Mapping[ElementId, Element],
) -> None:
    """Refuse a channel shape that cannot be drawn without losing values."""
    quantities = channels[EncodingRole.QUANTITY]
    if visual_type in (VisualType.BAR, VisualType.DOT):
        categories = channels[EncodingRole.CATEGORY]
        series = channels[EncodingRole.SERIES]
        if not categories or len(categories) != len(quantities):
            raise CompileError("category and quantity channels do not pair")
        if series and len(series) != len(quantities):
            raise CompileError("series and quantity channels do not pair")
        return

    times = channels[EncodingRole.TIME]
    entities = channels[EncodingRole.ENTITY]
    series = channels[EncodingRole.SERIES]
    pair_count = len(quantities) // 2
    if len(times) != 2 or len(quantities) < 4 or len(quantities) % 2:
        raise CompileError("a slope needs two times and an even pair of at least four quantities")
    if not entities and not series:
        raise CompileError("a slope needs an entity or series label for each line")
    if entities and len(entities) != pair_count:
        raise CompileError("a slope needs one entity label for each quantity pair")
    if series and len(series) != pair_count:
        raise CompileError("a slope needs one series label for each quantity pair")
    if len({_mark_text(value, known) for value in times}) != 2:
        raise CompileError("a slope needs two distinct time labels")
    if not entities and len({_mark_text(value, known) for value in series}) != pair_count:
        raise CompileError("a slope needs distinct series labels when entity labels are absent")


def _chart_data(
    item_id: str,
    channels: Mapping[EncodingRole, Sequence[DisplayedValue]],
    plan: VisualPlan,
    visual_type: VisualType,
    known: Mapping[ElementId, Element],
) -> tuple[VisualData, list[_Figure]]:
    """Write each filled source channel once, keeping its role in the payload."""
    marks: list[VisualMark] = []
    figures: list[_Figure] = []
    encoded: dict[str, list[str]] = {role.value: [] for role in EncodingRole}
    mark_by_value: dict[tuple[EncodingRole, int], str] = {}
    for role in EncodingRole:
        for index, value in enumerate(channels[role]):
            mark_id = f"m{len(marks)}"
            mark_by_value[(role, index)] = mark_id
            if role in VALUE_ROLES:
                figure = _figure(value, known)
                figures.append(figure)
                marks.append(
                    VisualMark(
                        mark_id=mark_id,
                        text=None,
                        value=figure.stated,
                        unit=figure.unit,
                        source_text=(
                            sanitize(
                                "; ".join(
                                    known[cited].span_excerpt for cited in value.derived.inputs
                                )
                            )
                            if value.derived is not None
                            else None
                        ),
                        element_id=value.element_id,
                        derived=value.derived,
                    )
                )
            else:
                text = _mark_text(value, known)
                if not text:
                    raise CompileError(
                        f"a {role.value} mark has nothing after sanitizing and cannot be drawn"
                    )
                marks.append(
                    VisualMark(
                        mark_id=mark_id,
                        text=text,
                        value=None,
                        unit=None,
                        source_text=None,
                        element_id=value.element_id,
                        derived=value.derived,
                    )
                )
            encoded[role.value].append(mark_id)

    emphasized = _emphasized_chart_mark(
        plan, _observations(visual_type, channels, mark_by_value), visual_type
    )
    data = VisualData(
        version=VisualData.schema_version(),
        item_id=item_id,
        type=visual_type,
        renderer_version=RENDERER_VERSION,
        title=sanitize(plan.title).strip() or None if plan.title is not None else None,
        caption=sanitize(plan.caption).strip() or None if plan.caption is not None else None,
        emphasized_mark_id=emphasized,
        marks=marks,
        encoding=VisualEncoding(**encoded),
    )
    quantity_ids = encoded[EncodingRole.QUANTITY.value]
    figure_by_mark = dict(zip(quantity_ids, figures, strict=True))
    return data, [figure_by_mark[mark_id] for mark_id in quantity_ids]


def _observations(
    visual_type: VisualType,
    channels: Mapping[EncodingRole, Sequence[DisplayedValue]],
    mark_by_value: Mapping[tuple[EncodingRole, int], str],
) -> list[tuple[list[DisplayedValue], list[str]]]:
    quantities = channels[EncodingRole.QUANTITY]
    if visual_type in (VisualType.BAR, VisualType.DOT):
        return [
            (
                [
                    channels[EncodingRole.CATEGORY][index],
                    quantities[index],
                    *(
                        [channels[EncodingRole.SERIES][index]]
                        if channels[EncodingRole.SERIES]
                        else []
                    ),
                ],
                [mark_by_value[(EncodingRole.QUANTITY, index)]],
            )
            for index in range(len(quantities))
        ]
    observations = []
    for index, quantity in enumerate(quantities):
        line = index // 2
        side = index % 2
        observations.append(
            (
                [
                    quantity,
                    channels[EncodingRole.TIME][side],
                    *(
                        [channels[EncodingRole.ENTITY][line]]
                        if channels[EncodingRole.ENTITY]
                        else []
                    ),
                    *(
                        [channels[EncodingRole.SERIES][line]]
                        if channels[EncodingRole.SERIES]
                        else []
                    ),
                ],
                [mark_by_value[(EncodingRole.QUANTITY, index)]],
            )
        )
    return observations


def _emphasized_chart_mark(
    plan: VisualPlan,
    observations: Sequence[tuple[Sequence[DisplayedValue], Sequence[str]]],
    visual_type: VisualType,
) -> str:
    """Resolve selected elements to exactly one displayed measurement."""
    selected: set[str] = set()
    matched: set[str] = set()
    annotations = set(plan.annotations)
    for values, mark_ids in observations:
        inputs = {
            cited
            for value in values
            for cited in (
                value.derived.inputs if value.derived is not None
                else ([value.element_id] if value.element_id is not None else [])
            )
        }
        found = annotations & inputs
        if found:
            selected.update(mark_ids)
            matched.update(found)
    if matched != annotations:
        raise CompileError("an annotation does not identify a displayed measurement")
    if len(selected) != 1:
        selected_name = {
            VisualType.BAR: "bars",
            VisualType.DOT: "dots",
            VisualType.SLOPE: "slope measurements",
        }[visual_type]
        raise CompileError(
            f"annotations select {len(selected)} distinct {selected_name}; exactly one is required"
        )
    return selected.pop()


def _mark_text(value: DisplayedValue, known: Mapping[ElementId, Element]) -> str:
    """A label taken from its own source characters and sanitized before publication."""
    if value.element_id is None:
        raise CompileError("a label has to be an element the article wrote")
    return sanitize(known[value.element_id].span_excerpt)[:MARK_NAME_MAX]


def _chart_alt_text(
    visual_type: VisualType,
    channels: Mapping[EncodingRole, Sequence[DisplayedValue]],
    figures: Sequence[_Figure],
    known: Mapping[ElementId, Element],
) -> str:
    """State every visible label and figure from the source channels."""
    unit = f" {figures[0].unit}" if figures and figures[0].unit else ""
    if visual_type in (VisualType.BAR, VisualType.DOT):
        categories = channels[EncodingRole.CATEGORY]
        series = channels[EncodingRole.SERIES]
        name = "Bar chart" if visual_type is VisualType.BAR else "Dot chart"
        facts = [
            f"{_mark_text(categories[index], known)}"
            f"{f' ({_mark_text(series[index], known)})' if series else ''} "
            f"{format(figure.value.normalize(), ',f')}{unit}"
            for index, figure in enumerate(figures)
        ]
        return f"{name}. {'; '.join(facts)}."[:ALT_TEXT_MAX]

    times = [_mark_text(value, known) for value in channels[EncodingRole.TIME]]
    entities = channels[EncodingRole.ENTITY]
    series = channels[EncodingRole.SERIES]
    facts = []
    for index in range(len(figures) // 2):
        label = _mark_text(entities[index], known) if entities else _mark_text(series[index], known)
        family = f" ({_mark_text(series[index], known)})" if entities and series else ""
        before = format(figures[index * 2].value.normalize(), ',f')
        after = format(figures[index * 2 + 1].value.normalize(), ',f')
        facts.append(f"{label}{family}: {times[0]} {before}{unit}; {times[1]} {after}{unit}")
    return f"Slope chart. {'; '.join(facts)}."[:ALT_TEXT_MAX]


def _figure(value: DisplayedValue, known: Mapping[ElementId, Element]) -> _Figure:
    """A displayed figure: the element's stated value, or the converted one."""
    if value.derived is not None:
        return _Figure(value.derived.value, Decimal(value.derived.value), value.derived.unit)
    element = known[value.element_id] if value.element_id is not None else None
    if element is None or element.value is None:  # pragma: no cover - the resolver refuses first
        raise CompileError("a bar's length has to be a figure the article states")
    return _Figure(element.value, Decimal(element.value), element.unit)
