"""A plan becomes a spec, and a spec becomes an SVG - no browser, no runtime JavaScript.

`vl-convert` bundles the Vega toolchain as a Rust extension, so the render is a
function call rather than a subprocess plus a headless Chromium. Measured on the
development machine (Windows 11, 8 vCPU, 2026-08-22): 2568 ms for the first
render in a process, 49 ms warm, 7 KB of SVG. The cold cost is engine boot and
is paid once per run, not once per item.

SVG rather than PNG: a bar chart is a dozen paths, so the vector is smaller than
any raster of it, stays sharp on a phone, and costs the retention budget less.

`compile_bar` is the half above it: one validated `VisualPlan` and one article's
element table become the spec drawn here. It is the only thing in this
repository that turns a plan into a picture, and it draws **one type**. A second
type is plan 12's, and a type this build cannot draw is refused by name rather
than approximated - a chart that is nearly the plan is a chart nobody asked for.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Final, NamedTuple

from idhazh.contracts.app_config import VisualsConfig
from idhazh.contracts.derived import DisplayedValue
from idhazh.contracts.element import Element, ElementId, ElementTable
from idhazh.contracts.visual import EncodingRole, PlanDecision, VisualPlan, VisualType
from idhazh.derived_values import resolve_displayed_values
from idhazh.sanitize import sanitize

SUFFIX: Final = ".svg"

#: How many of an element's own characters name one bar. The drawn label is the
#: article's text, so it is cut rather than reworded.
MARK_NAME_MAX: Final = 40
#: How many characters of the plan's title are drawn above the bars.
TITLE_MAX: Final = 120
#: What a screen reader gets, and the same cap `UntrustedLine` holds the
#: decision's `alt_text` to.
ALT_TEXT_MAX: Final = 300

#: The margins a bar chart needs outside its plotting area: the category names to
#: the left and the axis plus the title above and below. Subtracted from the
#: canvas so the drawn SVG is the size `visuals.canvas_width` asks for, which is
#: the box the reading page reserves.
_NAME_GUTTER: Final = 120
_AXIS_AND_TITLE: Final = 90

#: What the renderer bakes into every bar. The page repaints it from `--chart-1`
#: (`frontend/src/lib/components/ItemVisual.svelte`), so this is the colour of a
#: drawing opened outside the site and never the colour a reader sees.
_BAR_COLOUR: Final = "#4c6ef5"

_VEGA_LITE: Final = "https://vega.github.io/schema/vega-lite/v5.json"


class RenderError(RuntimeError):
    """The spec did not become a picture. The item still publishes."""


class CompileError(RenderError):
    """The plan did not become a spec. The item still publishes.

    A subclass rather than a sibling, because the caller's answer is the same
    one either way and `render_visual` already degrades on `RenderError`. What
    separates them is where the fault is: a `RenderError` is a spec the Vega
    toolchain refused, and a `CompileError` is a plan this build cannot draw.
    """


class CompiledChart(NamedTuple):
    """What a plan becomes: the spec that is drawn, and the words a reader hears.

    Both, from one call. The alt text is assembled from the same figures the
    spec carries, so the sentence and the picture cannot disagree - which is the
    reason `alt_text` is not a field the model may write
    (`docs/architecture/publishing/visuals.md`).
    """

    spec: dict[str, Any]
    alt_text: str


def render_chart(spec: str | dict[str, Any]) -> bytes:
    """Render a Vega-Lite spec. Raises `RenderError` and never returns a broken file."""
    import vl_convert

    text = spec if isinstance(spec, str) else json.dumps(spec)
    try:
        json.loads(text)
    except json.JSONDecodeError as error:
        raise RenderError(f"the chart spec is not valid JSON: {error.msg}") from error
    try:
        svg = vl_convert.vegalite_to_svg(text)
    except Exception as error:  # vl_convert raises its own error types
        raise RenderError(f"vega-lite rejected the spec: {type(error).__name__}") from error
    if not svg.strip().startswith("<svg"):
        raise RenderError("the renderer returned something that is not an SVG")
    return svg.encode("utf-8")


class _Figure(NamedTuple):
    """One bar's length and what it measures, read off a resolved plan."""

    value: Decimal
    unit: str | None


def compile_bar(
    plan: VisualPlan, table: ElementTable, *, visuals: VisualsConfig
) -> CompiledChart:
    """One `bar` plan and one article's elements become the spec that draws them.

    **Every number in the returned spec came out of the article.** The plan
    carries element references and no figure at all - the shape refuses one
    (`contracts/visual.py`) - so a bar can only ever be as long as an element
    the extractor cut out of the article's own characters, or as long as a
    derived value with a chain back to several of them. That is a property of
    the pipe rather than a hope about the prompt, and
    `backend/tests/test_render.py` re-derives the drawn lengths from the element
    table to say so.

    **Category `i` names quantity `i`.** The resolver returns each channel in
    the plan's own order, so the pairing is the plan's and not a rule invented
    here. A plan whose two channels are different lengths pairs into nothing and
    is refused.

    **One type, and a second is refused by name.** `bar` is what this build
    draws; the rest of the vocabulary is plan 12's. Drawing a `line` plan as
    bars because bars are what we have would publish a picture nobody planned.

    Raises `CompileError` on every route to no picture, and the caller degrades
    the item.
    """
    if plan.decision is not PlanDecision.VISUAL:
        raise CompileError("this plan asks for no picture, so there is nothing to compile")
    if plan.type is not VisualType.BAR:
        named = plan.type.value if plan.type is not None else "no type"
        raise CompileError(f"this build draws bar and nothing else, and the plan says {named}")

    resolved = resolve_displayed_values(plan, table, visuals=visuals)
    if resolved.refusal is not None:
        raise CompileError(f"{resolved.refusal.check.value}: {resolved.refusal.detail}")

    known = {element.element_id: element for element in table.elements}
    names = [
        _mark_name(value, known)
        for value in resolved.values
        if value.role is EncodingRole.CATEGORY
    ]
    figures = [
        _figure(value, known) for value in resolved.values if value.role is EncodingRole.QUANTITY
    ]
    if not names or len(names) != len(figures):
        raise CompileError(
            f"{len(names)} names and {len(figures)} figures do not pair into bars"
        )

    # The channel is one scale by construction - `_channel` converts anything
    # that is not - so any spelling in it names the same axis, and the first is
    # the plan's own order rather than a rule minted here.
    unit = figures[0].unit
    spec: dict[str, Any] = {
        "$schema": _VEGA_LITE,
        "width": visuals.canvas_width - _NAME_GUTTER,
        "height": visuals.canvas_height - _AXIS_AND_TITLE,
        "background": "transparent",
        "data": {
            "values": [
                {"label": name, "value": float(figure.value)}
                for name, figure in zip(names, figures, strict=True)
            ]
        },
        "mark": {"type": "bar", "cornerRadiusEnd": 3, "color": _BAR_COLOUR},
        "encoding": {
            "y": {
                "field": "label",
                "type": "nominal",
                # The plan's order, kept. Re-ranking the bars here would be this
                # module deciding what the comparison says.
                "sort": None,
                "axis": {"title": None, "labelLimit": 220},
            },
            "x": {
                "field": "value",
                "type": "quantitative",
                "axis": {"title": unit or None, "format": "~s"},
            },
        },
        "config": {
            "view": {"stroke": None},
            "axis": {"labelFont": "sans-serif", "titleFont": "sans-serif", "grid": False},
        },
    }
    title = sanitize(plan.title)[:TITLE_MAX] if plan.title else ""
    if title:
        spec["title"] = {"text": title, "anchor": "start", "fontSize": 14}
    return CompiledChart(spec, _alt_text(names, figures, unit))


def _mark_name(value: DisplayedValue, known: Mapping[ElementId, Element]) -> str:
    """What names one bar: the element's own characters, cut and sanitized.

    A category is not a measured channel, so the resolver never derives one and
    `element_id` is always set. Fetched text is data (Guardrail #11), so it is
    sanitized on the way into markup a reader's browser will parse.
    """
    if value.element_id is None:  # pragma: no cover - a category is never derived
        raise CompileError("a bar's name has to be an element the article wrote")
    return sanitize(known[value.element_id].span_excerpt)[:MARK_NAME_MAX]


def _figure(value: DisplayedValue, known: Mapping[ElementId, Element]) -> _Figure:
    """How long one bar is: the element's stated figure, or the converted one."""
    if value.derived is not None:
        return _Figure(Decimal(value.derived.value), value.derived.unit)
    element = known[value.element_id] if value.element_id is not None else None
    if element is None or element.value is None:  # pragma: no cover - the resolver refuses first
        raise CompileError("a bar's length has to be a figure the article states")
    return _Figure(Decimal(element.value), element.unit)


def _alt_text(names: Sequence[str], figures: Sequence[_Figure], unit: str | None) -> str:
    """What a screen reader gets. The picture is never the only carrier of a fact.

    It states the figures the bars are drawn at, so the sentence says what the
    picture says. Where a bar is Tier 1 that is the article's own number; where
    a bar was converted onto the axis it is the converted one, because that is
    what a reader reads off the axis.
    """
    tail = f" {unit}" if unit else ""
    parts = [
        f"{name} {format(figure.value.normalize(), ',f')}{tail}"
        for name, figure in zip(names, figures, strict=True)
    ]
    return f"Bar chart. {'; '.join(parts)}."[:ALT_TEXT_MAX]
