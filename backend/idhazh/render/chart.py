"""A plan becomes the data a reader's browser draws. Nothing here draws.

**The reader's browser draws the chart and the pipeline never draws one**
(maintainer ruling, 2026-09-13,
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
marks a browser draws. It compiles the supported chart forms, and a type this
build cannot compile is refused by name rather than approximated.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final, NamedTuple

from idhazh.contracts.chart_evidence import ChartEvidence
from idhazh.contracts.derived import DisplayedValue
from idhazh.contracts.element import Element, ElementId, ElementKind, ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import EncodingRole, PlanDecision, VisualPlan, VisualType
from idhazh.contracts.visual_data import (
    RENDERER_VERSION,
    VisualData,
    VisualEncoding,
    VisualMark,
    VisualWhole,
)
from idhazh.derived_values import (
    histogram_unit_and_version,
    measure_displayed_values,
    resolve_displayed_values,
)
from idhazh.relationship_evidence import refuse_relationship
from idhazh.sanitize import sanitize
from idhazh.text_fit import fit_source_span
from idhazh.visual_vocabulary import TYPE_RULES, VALUE_ROLES

#: What a screen reader gets, and the same cap `UntrustedLine` holds the
#: decision's `alt_text` to.
ALT_TEXT_MAX: Final = 300
#: SI unit symbols have fixed case; normalized payload units remain unchanged.
DISPLAY_UNIT_SYMBOLS: Final[dict[str, str]] = {
    "w": "W",
    "watt": "W",
    "kw": "kW",
    "kilowatt": "kW",
    "mw": "MW",
    "megawatt": "MW",
    "gw": "GW",
    "gigawatt": "GW",
    "tw": "TW",
    "terawatt": "TW",
    "wh": "Wh",
    "kwh": "kWh",
    "mwh": "MWh",
    "gwh": "GWh",
    "twh": "TWh",
    "g": "g",
    "gram": "g",
    "kg": "kg",
    "kilogram": "kg",
    "t": "t",
    "tonne": "t",
    "kt": "kt",
    "kilotonne": "kt",
    "mm": "mm",
    "cm": "cm",
    "km": "km",
    "kilometre": "km",
    "kilometer": "km",
    "s": "s",
    "second": "s",
    "min": "min",
    "minute": "min",
    "hr": "h",
    "hour": "h",
    "day": "d",
}


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
    return visual_type in {
        VisualType.BAR,
        VisualType.DOT,
        VisualType.SLOPE,
        VisualType.LINE,
        VisualType.SCATTER,
        VisualType.BUBBLE,
        VisualType.STACKED_BAR,
        VisualType.PIE,
        VisualType.HISTOGRAM,
    }


def compile_chart(
    plan: VisualPlan, table: ElementTable, *, visuals: VisualsConfig
) -> CompiledChart:
    """Compile a supported plan as marks grounded in the article.

    Bar and dot pair categories and optional series labels with quantities.
    Slope pairs two time labels with consecutive quantity pairs and one entity
    or series label per line. Line pairs each quantity with a date and optional
    series label. Relationship charts pair every measure with a source-labelled
    entity, and bubble also carries one positive size measure per entity.
    Unsupported source channels are refused rather than approximated.
    """
    if plan.decision is not PlanDecision.VISUAL:
        raise CompileError("this plan asks for no picture, so there is nothing to compile")
    visual_type = plan.type
    if visual_type is None or not can_compile(visual_type):
        named = visual_type.value if visual_type is not None else "no type"
        raise CompileError(f"this build cannot draw the plan's {named} type")

    if visual_type in (VisualType.STACKED_BAR, VisualType.PIE, VisualType.HISTOGRAM):
        from idhazh.visual_validator import validate_plan

        if rejections := validate_plan(plan, table, visuals=visuals):
            names = ", ".join(rejection.check.value for rejection in rejections)
            raise CompileError(f"{visual_type.value} was refused on {names}")

    if visual_type in (VisualType.SCATTER, VisualType.BUBBLE):
        source = {element.element_id: element for element in table.elements}
        detail = refuse_relationship(plan, {
            role: [source[cited] for cited in ids if cited in source]
            for role, ids in plan.encodings.filled().items()
        })
        if detail is not None:
            raise CompileError(detail)

    resolved = resolve_displayed_values(plan, table, visuals=visuals)
    if resolved.refusal is not None:
        raise CompileError(f"{resolved.refusal.check.value}: {resolved.refusal.detail}")

    known = {element.element_id: element for element in table.elements}
    rules = TYPE_RULES[visual_type]
    allowed = rules.required | rules.optional
    channels = {
        role: [value for value in resolved.values if value.role is role] if role in allowed else []
        for role in EncodingRole
    }
    max_label_characters = (
        None if visual_type is VisualType.STACKED_BAR else visuals.max_label_characters
    )
    _check_channel_pairing(visual_type, channels, known, max_label_characters=max_label_characters)
    data, figures = _chart_data(
        table.item_id,
        channels,
        plan,
        visual_type,
        known,
        max_label_characters=max_label_characters,
    )
    return CompiledChart(
        _chart_alt_text(
            visual_type,
            channels,
            figures,
            known,
            data.declared_whole,
            data.histogram_unit,
            max_label_characters=max_label_characters,
        ),
        data,
        measure_displayed_values(
            [value for role in VALUE_ROLES for value in channels[role]], table
        ),
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
    *,
    max_label_characters: int | None,
) -> None:
    """Refuse a channel shape that cannot be drawn without losing values."""
    quantities = channels[EncodingRole.QUANTITY]
    if visual_type in (VisualType.SCATTER, VisualType.BUBBLE):
        names = [
            _mark_text(value, known, max_length=max_label_characters)
            for value in channels[EncodingRole.ENTITY]
        ]
        if len(set(names)) != len(names):
            raise CompileError("relationship entity labels must remain distinct after fitting")
        if visual_type is VisualType.BUBBLE and len(channels[EncodingRole.SIZE]) != len(quantities):
            raise CompileError("a bubble needs one size measure for every point")
        return
    if visual_type in (VisualType.BAR, VisualType.DOT):
        categories = channels[EncodingRole.CATEGORY]
        series = channels[EncodingRole.SERIES]
        if not categories or len(categories) != len(quantities):
            raise CompileError("category and quantity channels do not pair")
        if series and len(series) != len(quantities):
            raise CompileError("series and quantity channels do not pair")
        return
    if visual_type is VisualType.STACKED_BAR:
        categories = channels[EncodingRole.CATEGORY]
        series = channels[EncodingRole.SERIES]
        if len(categories) != 1 or len(quantities) < 2 or len(series) != len(quantities):
            raise CompileError("a stacked bar has one whole and one label for each part")
        labels = [_mark_text(value, known, max_length=max_label_characters) for value in series]
        if len(set(labels)) != len(labels):
            raise CompileError("stacked-bar part labels must remain distinct as source text")
        return
    if visual_type is VisualType.PIE:
        categories = channels[EncodingRole.CATEGORY]
        labels = [_mark_text(value, known, max_length=max_label_characters) for value in categories]
        if len(categories) != len(quantities):
            raise CompileError("a pie pairs one category with each part quantity")
        if len(set(labels)) != len(labels):
            raise CompileError("pie category names must remain distinct after fitting")
        return
    if visual_type is VisualType.HISTOGRAM:
        if not 2 <= len(channels[EncodingRole.BINS]) <= 8:
            raise CompileError("a histogram needs between two and eight configured bins")
        if any(
            channels[role]
            for role in EncodingRole
            if role is not EncodingRole.BINS
        ):
            raise CompileError("a histogram draws only its bins channel")
        return

    times = channels[EncodingRole.TIME]
    entities = channels[EncodingRole.ENTITY]
    series = channels[EncodingRole.SERIES]
    if visual_type is VisualType.LINE:
        if len(quantities) < 2 or len(times) != len(quantities):
            raise CompileError("a line needs at least two quantities paired with dates")
        if series and len(series) != len(quantities):
            raise CompileError("a line needs one series label for each quantity")
        by_series: dict[str, set[str]] = {}
        precisions: set[int] = set()
        for index, time in enumerate(times):
            element = known[time.element_id] if time.element_id is not None else None
            if element is None or element.kind is not ElementKind.DATE or element.value is None:
                raise CompileError("a line time has no source date")
            precisions.add(len(element.value))
            label = (
                _mark_text(series[index], known, max_length=max_label_characters) if series else ""
            )
            dates = by_series.setdefault(label, set())
            if element.value in dates:
                raise CompileError("a line has two readings for one series and date")
            dates.add(element.value)
        if len(precisions) != 1:
            raise CompileError("a line cannot mix year and day precision")
        if any(len(dates) < 2 for dates in by_series.values()):
            raise CompileError("each line series needs at least two dates")
        return
    pair_count = len(quantities) // 2
    if len(times) != 2 or len(quantities) < 4 or len(quantities) % 2:
        raise CompileError("a slope needs two times and an even pair of at least four quantities")
    if not entities and not series:
        raise CompileError("a slope needs an entity or series label for each line")
    if entities and len(entities) != pair_count:
        raise CompileError("a slope needs one entity label for each quantity pair")
    if series and len(series) != pair_count:
        raise CompileError("a slope needs one series label for each quantity pair")
    if len({_mark_text(value, known, max_length=max_label_characters) for value in times}) != 2:
        raise CompileError("a slope needs two distinct time labels")
    if (
        not entities
        and len({_mark_text(value, known, max_length=max_label_characters) for value in series})
        != pair_count
    ):
        raise CompileError("a slope needs distinct series labels when entity labels are absent")


def _chart_data(
    item_id: str,
    channels: Mapping[EncodingRole, Sequence[DisplayedValue]],
    plan: VisualPlan,
    visual_type: VisualType,
    known: Mapping[ElementId, Element],
    *,
    max_label_characters: int | None,
) -> tuple[VisualData, list[_Figure]]:
    """Write each filled source channel once, keeping its role in the payload."""
    _refuse_label_fit_collisions(channels, known, max_label_characters=max_label_characters)
    marks: list[VisualMark] = []
    measured_figures: dict[str, _Figure] = {}
    encoded: dict[str, list[str]] = {role.value: [] for role in EncodingRole}
    mark_by_value: dict[tuple[EncodingRole, int], str] = {}
    for role in EncodingRole:
        for index, value in enumerate(channels[role]):
            mark_id = f"m{len(marks)}"
            mark_by_value[(role, index)] = mark_id
            if role in VALUE_ROLES:
                figure = _figure(value, known)
                if role is EncodingRole.QUANTITY or (
                    visual_type is VisualType.HISTOGRAM and role is EncodingRole.BINS
                ):
                    measured_figures[mark_id] = figure
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
                text = _mark_text(value, known, max_length=max_label_characters)
                if not text:
                    raise CompileError(
                        f"a {role.value} mark has nothing after sanitizing and cannot be drawn"
                    )
                time = _time_value(value, known) if role is EncodingRole.TIME else None
                marks.append(
                    VisualMark(
                        mark_id=mark_id,
                        text=text,
                        time=time,
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
    whole_id = (
        plan.declared_whole_element_id
        if visual_type in (VisualType.PIE, VisualType.STACKED_BAR)
        else None
    )
    whole = (
        known[plan.declared_whole_element_id]
        if visual_type is VisualType.PIE and plan.declared_whole_element_id is not None
        else None
    )
    histogram_unit, histogram_unit_table_version = (
        histogram_unit_and_version([known[cited] for cited in plan.encodings.bins])
        if visual_type is VisualType.HISTOGRAM
        else (None, None)
    )
    data = VisualData(
        version=VisualData.schema_version(),
        item_id=item_id,
        type=visual_type,
        renderer_version=RENDERER_VERSION,
        histogram_unit=histogram_unit,
        histogram_unit_table_version=histogram_unit_table_version,
        declared_whole_element_id=whole_id,
        declared_whole=(
            VisualWhole(
                element_id=whole.element_id,
                text=sanitize(whole.span_excerpt).strip(),
            )
            if whole is not None
            else None
        ),
        title=sanitize(plan.title).strip() or None if plan.title is not None else None,
        caption=sanitize(plan.caption).strip() or None if plan.caption is not None else None,
        emphasized_mark_id=emphasized,
        marks=marks,
        encoding=VisualEncoding(**encoded),
    )
    figure_role = (
        EncodingRole.BINS
        if visual_type is VisualType.HISTOGRAM
        else EncodingRole.QUANTITY
    )
    figure_ids = encoded[figure_role.value]
    return data, [measured_figures[mark_id] for mark_id in figure_ids]


def _observations(
    visual_type: VisualType,
    channels: Mapping[EncodingRole, Sequence[DisplayedValue]],
    mark_by_value: Mapping[tuple[EncodingRole, int], str],
) -> list[tuple[list[DisplayedValue], list[str]]]:
    quantities = channels[EncodingRole.QUANTITY]
    if visual_type in (VisualType.SCATTER, VisualType.BUBBLE):
        return [
            (
                [
                    quantities[index],
                    channels[EncodingRole.QUANTITY_X][index],
                    *(
                        [channels[EncodingRole.SIZE][index]]
                        if visual_type is VisualType.BUBBLE else []
                    ),
                    channels[EncodingRole.ENTITY][index],
                    *([channels[EncodingRole.SERIES][index]]
                      if channels[EncodingRole.SERIES] else []),
                ],
                [mark_by_value[(EncodingRole.QUANTITY, index)]],
            )
            for index in range(len(quantities))
        ]
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
    if visual_type is VisualType.STACKED_BAR:
        return [
            (
                [
                    channels[EncodingRole.CATEGORY][0],
                    quantities[index],
                    channels[EncodingRole.SERIES][index],
                ],
                [mark_by_value[(EncodingRole.QUANTITY, index)]],
            )
            for index in range(len(quantities))
        ]
    if visual_type is VisualType.PIE:
        return [
            (
                [channels[EncodingRole.CATEGORY][index], quantities[index]],
                [mark_by_value[(EncodingRole.QUANTITY, index)]],
            )
            for index in range(len(quantities))
        ]
    if visual_type is VisualType.HISTOGRAM:
        bins = channels[EncodingRole.BINS]
        return [
            ([value], [mark_by_value[(EncodingRole.BINS, index)]])
            for index, value in enumerate(bins)
        ]
    if visual_type is VisualType.LINE:
        times = channels[EncodingRole.TIME]
        series = channels[EncodingRole.SERIES]
        return [
            (
                [quantities[index], times[index], *([series[index]] if series else [])],
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
            VisualType.STACKED_BAR: "stacked-bar parts",
            VisualType.SLOPE: "slope measurements",
            VisualType.LINE: "line measurements",
            VisualType.SCATTER: "scatter points",
            VisualType.BUBBLE: "bubbles",
            VisualType.HISTOGRAM: "histogram bins",
        }[visual_type]
        raise CompileError(
            f"annotations select {len(selected)} distinct {selected_name}; exactly one is required"
        )
    return selected.pop()


def _mark_text(
    value: DisplayedValue,
    known: Mapping[ElementId, Element],
    *,
    max_length: int | None,
) -> str:
    """Publish unchanged source characters or their exact fitted prefix."""
    if value.element_id is None:
        raise CompileError("a label has to be an element the article wrote")
    source_span = known[value.element_id].span_excerpt
    safe_span = sanitize(source_span)
    if not safe_span:
        return ""
    if safe_span != source_span:
        raise CompileError("a source label changed when sanitized and cannot be drawn")
    return (
        source_span
        if max_length is None
        else fit_source_span(source_span, max_characters=max_length)
    )


def _refuse_label_fit_collisions(
    channels: Mapping[EncodingRole, Sequence[DisplayedValue]],
    known: Mapping[ElementId, Element],
    *,
    max_label_characters: int | None,
) -> None:
    """Keep distinct source labels distinct after shortening."""
    if max_label_characters is None:
        return
    for role, values in channels.items():
        if role in VALUE_ROLES:
            continue
        sources_by_label: dict[str, set[str]] = {}
        for value in values:
            if value.element_id is None:
                continue
            source_span = known[value.element_id].span_excerpt
            label = _mark_text(value, known, max_length=max_label_characters)
            sources_by_label.setdefault(label, set()).add(source_span)
        if any(len(sources) > 1 for sources in sources_by_label.values()):
            raise CompileError(
                f"different source labels in {role.value} become identical after shortening"
            )


def _time_value(value: DisplayedValue, known: Mapping[ElementId, Element]) -> str:
    """The element's checked date or year, separate from its source wording."""
    if value.element_id is None:
        raise CompileError("a time label has to be a source date element")
    element = known[value.element_id]
    if element.kind is not ElementKind.DATE or element.value is None:
        raise CompileError("a time label has no canonical date or year")
    return element.value


def _chart_alt_text(
    visual_type: VisualType,
    channels: Mapping[EncodingRole, Sequence[DisplayedValue]],
    figures: Sequence[_Figure],
    known: Mapping[ElementId, Element],
    declared_whole: VisualWhole | None,
    histogram_unit: str | None,
    *,
    max_label_characters: int | None,
) -> str:
    """State every visible label and figure from the source channels."""
    unit = f" {figures[0].unit}" if figures and figures[0].unit else ""
    if visual_type is VisualType.SCATTER:
        facts = []
        for index, figure in enumerate(figures):
            horizontal = _figure(channels[EncodingRole.QUANTITY_X][index], known)
            label = _mark_text(
                channels[EncodingRole.ENTITY][index],
                known,
                max_length=max_label_characters,
            )
            facts.append(
                f"{label}: x {horizontal.stated} {horizontal.unit or ''}, "
                f"y {figure.stated}{unit}"
            )
        return f"Scatter chart. {'; '.join(facts)}."[:ALT_TEXT_MAX]
    if visual_type is VisualType.BUBBLE:
        sizes = channels[EncodingRole.SIZE]
        facts = []
        for index, figure in enumerate(figures):
            horizontal = _figure(channels[EncodingRole.QUANTITY_X][index], known)
            size = _figure(sizes[index], known)
            label = _mark_text(
                channels[EncodingRole.ENTITY][index],
                known,
                max_length=max_label_characters,
            )
            facts.append(
                f"{label}: x {horizontal.stated} {horizontal.unit or ''}, "
                f"y {figure.stated} {figure.unit or ''}, "
                f"area {size.stated} {size.unit or ''}"
            )
        return f"Bubble chart. {'; '.join(facts)}."[:ALT_TEXT_MAX]
    if visual_type in (VisualType.BAR, VisualType.DOT):
        categories = channels[EncodingRole.CATEGORY]
        series = channels[EncodingRole.SERIES]
        name = "Bar chart" if visual_type is VisualType.BAR else "Dot chart"
        facts = []
        for index, figure in enumerate(figures):
            category = _mark_text(categories[index], known, max_length=max_label_characters)
            series_label = (
                f" ({_mark_text(series[index], known, max_length=max_label_characters)})"
                if series
                else ""
            )
            facts.append(f"{category}{series_label} {format(figure.value.normalize(), ',f')}{unit}")
        return f"{name}. {'; '.join(facts)}."[:ALT_TEXT_MAX]
    if visual_type is VisualType.STACKED_BAR:
        row = _mark_text(channels[EncodingRole.CATEGORY][0], known, max_length=None)
        series = channels[EncodingRole.SERIES]
        stacked_unit = DISPLAY_UNIT_SYMBOLS.get(figures[0].unit or "", figures[0].unit or "")
        unit_suffix = f" {stacked_unit}" if stacked_unit else ""
        facts = [
            f"{_mark_text(series[index], known, max_length=None)} "
            f"{format(figure.value.normalize(), ',f')}{unit_suffix}"
            for index, figure in enumerate(figures)
        ]
        return f"Stacked bar chart. {row}: {'; '.join(facts)}."[:ALT_TEXT_MAX]
    if visual_type is VisualType.PIE:
        if declared_whole is None:
            raise CompileError("a pie has no declared whole to read out")
        categories = channels[EncodingRole.CATEGORY]
        facts = [
            f"{_mark_text(categories[index], known, max_length=max_label_characters)} "
            f"{format(figure.value.normalize(), ',f')}{unit}"
            for index, figure in enumerate(figures)
        ]
        return (
            f"Pie chart. Declared total: {declared_whole.text}. "
            f"{'; '.join(facts)}."
        )[:ALT_TEXT_MAX]
    if visual_type is VisualType.HISTOGRAM:
        facts = []
        for index, value in enumerate(channels[EncodingRole.BINS]):
            derived = value.derived
            if derived is None or derived.bin_lower is None or derived.bin_upper is None:
                raise CompileError("a histogram bin has no recorded edges")
            closing = "]" if index == len(channels[EncodingRole.BINS]) - 1 else ")"
            facts.append(
                f"[{derived.bin_lower}, {derived.bin_upper}{closing} "
                f"{figures[index].stated}"
            )
        unit_suffix = f" {DISPLAY_UNIT_SYMBOLS.get(histogram_unit or '', histogram_unit or '')}"
        return f"Histogram chart. {'; '.join(facts)}{unit_suffix}."[:ALT_TEXT_MAX]

    times = [
        _mark_text(value, known, max_length=max_label_characters)
        for value in channels[EncodingRole.TIME]
    ]
    entities = channels[EncodingRole.ENTITY]
    series = channels[EncodingRole.SERIES]
    if visual_type is VisualType.LINE:
        facts = []
        for index, figure in enumerate(figures):
            name = (
                f"{_mark_text(series[index], known, max_length=max_label_characters)}: "
                if series
                else ""
            )
            facts.append(
                f"{name}{times[index]} "
                f"{format(figure.value.normalize(), ',f')}{unit}"
            )
        return f"Line chart. {'; '.join(facts)}."[:ALT_TEXT_MAX]
    facts = []
    for index in range(len(figures) // 2):
        label = (
            _mark_text(entities[index], known, max_length=max_label_characters)
            if entities
            else _mark_text(series[index], known, max_length=max_label_characters)
        )
        family = (
            f" ({_mark_text(series[index], known, max_length=max_label_characters)})"
            if entities and series
            else ""
        )
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
