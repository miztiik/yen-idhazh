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

`compile_bar` takes one validated `VisualPlan` and one article's element table
and returns what a reader gets: the sentence a screen reader hears, and the
marks a browser draws. It compiles **one type**. A second type is plan 12's, and
a type this build cannot compile is refused by name rather than approximated - a
chart that is nearly the plan is a chart nobody asked for.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final, NamedTuple

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
from idhazh.derived_values import resolve_displayed_values
from idhazh.sanitize import sanitize

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

    It carried a third member, the Vega-Lite spec, until the renderer went. One
    resolution is still the rule, and now there is nothing left for a second one
    to drift from.
    """

    alt_text: str
    data: VisualData


class _Figure(NamedTuple):
    """One bar's length and what it measures, read off a resolved plan.

    `stated` is the characters the source writes and `value` is the number they
    mean. Both, from one branch, because the alt text is written from the number
    and the published data carries the characters - and a second function
    reaching for the same figure is the drift that would let the sentence and
    the picture disagree.
    """

    stated: str
    value: Decimal
    unit: str | None


def compile_bar(plan: VisualPlan, table: ElementTable, *, visuals: VisualsConfig) -> CompiledChart:
    """One `bar` plan and one article's elements become the data that draws them.

    **Every number in the returned data came out of the article.** The plan
    carries element references and no figure at all - the shape refuses one
    (`contracts/visual.py`) - so a bar can only ever be as long as an element
    the extractor cut out of the article's own characters, or as long as a
    derived value with a chain back to several of them. That is a property of
    the pipe rather than a hope about the prompt, and
    `backend/tests/test_render.py` re-derives the published lengths from the
    element table to say so.

    **Category `i` names quantity `i`.** The resolver returns each channel in
    the plan's own order, so the pairing is the plan's and not a rule invented
    here. A plan whose two channels are different lengths pairs into nothing and
    is refused - and the published shape can still say one, which is why the
    reader's page runs the same check over what it fetched.

    **One type, and a second is refused by name.** `bar` is what this build
    compiles; the rest of the vocabulary is plan 12's. Compiling a `line` plan
    into bars because bars are what we have would publish a picture nobody
    planned.

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
    naming = [value for value in resolved.values if value.role is EncodingRole.CATEGORY]
    measuring = [value for value in resolved.values if value.role is EncodingRole.QUANTITY]
    names = [_mark_name(value, known) for value in naming]
    figures = [_figure(value, known) for value in measuring]
    if not names or len(names) != len(figures):
        raise CompileError(f"{len(names)} names and {len(figures)} figures do not pair into bars")
    # A bar nobody can name is a bar nobody can read, and it is a real route
    # rather than a defensive one: a span excerpt that is only a comment, only
    # invisible characters or only a fence marker sanitizes to nothing.
    if not all(names):
        raise CompileError("a bar whose name is nothing after sanitizing cannot be drawn")

    # The channel is one scale by construction - the resolver converts anything
    # that is not - so any spelling in it names the same axis, and the first is
    # the plan's own order rather than a rule minted here.
    unit = figures[0].unit
    data = _bar_data(table.item_id, names, naming, figures, measuring)
    return CompiledChart(_alt_text(names, figures, unit), data)


def _bar_data(
    item_id: str,
    names: Sequence[str],
    naming: Sequence[DisplayedValue],
    figures: Sequence[_Figure],
    measuring: Sequence[DisplayedValue],
) -> VisualData:
    """The same bars as data: one mark a name, one mark a length, and the channels.

    Marks are a flat pool and the encoding says which fill which channel, so the
    two channels have lengths of their own - which is the only shape in which "a
    chart with four names and three figures" can be said at all, and the drawing
    code has to be able to refuse one.

    Nothing here is drawn. No width, no colour, no font and no title: the plan
    carries none of those and publishing the compiled result must not become the
    hole one gets through (owner, 2026-09-13).
    """
    marks: list[VisualMark] = []
    category: list[str] = []
    quantity: list[str] = []
    for name, value in zip(names, naming, strict=True):
        marks.append(
            VisualMark(
                mark_id=f"m{len(marks)}",
                text=name,
                value=None,
                unit=None,
                element_id=value.element_id,
                derived=value.derived,
            )
        )
        category.append(marks[-1].mark_id)
    for figure, value in zip(figures, measuring, strict=True):
        marks.append(
            VisualMark(
                mark_id=f"m{len(marks)}",
                text=None,
                value=figure.stated,
                unit=figure.unit,
                element_id=value.element_id,
                derived=value.derived,
            )
        )
        quantity.append(marks[-1].mark_id)
    return VisualData(
        version=VisualData.schema_version(),
        item_id=item_id,
        type=VisualType.BAR,
        renderer_version=RENDERER_VERSION,
        marks=marks,
        encoding=VisualEncoding(
            category=category,
            quantity=quantity,
            quantity_x=[],
            time=[],
            series=[],
            size=[],
            bins=[],
            entity=[],
            event_label=[],
        ),
    )


def _mark_name(value: DisplayedValue, known: Mapping[ElementId, Element]) -> str:
    """What names one bar: the element's own characters, cut and sanitized.

    A category is not a measured channel, so the resolver never derives one and
    `element_id` is always set. Fetched text is data (Guardrail #11), so it is
    sanitized here, where the text is cut - not where it is later carried. The
    browser writes it as a text node now rather than inlining it as markup, and
    a carrier that happens to be safe is not a control.
    """
    if value.element_id is None:  # pragma: no cover - a category is never derived
        raise CompileError("a bar's name has to be an element the article wrote")
    return sanitize(known[value.element_id].span_excerpt)[:MARK_NAME_MAX]


def _figure(value: DisplayedValue, known: Mapping[ElementId, Element]) -> _Figure:
    """How long one bar is: the element's stated figure, or the converted one."""
    if value.derived is not None:
        return _Figure(value.derived.value, Decimal(value.derived.value), value.derived.unit)
    element = known[value.element_id] if value.element_id is not None else None
    if element is None or element.value is None:  # pragma: no cover - the resolver refuses first
        raise CompileError("a bar's length has to be a figure the article states")
    return _Figure(element.value, Decimal(element.value), element.unit)


def _alt_text(names: Sequence[str], figures: Sequence[_Figure], unit: str | None) -> str:
    """What a screen reader gets. The picture is never the only carrier of a fact.

    It states the figures the bars are drawn at, so the sentence says what the
    picture says. Where a bar is Tier 1 that is the article's own number; where
    a bar was converted onto the axis it is the converted one, because that is
    what a reader reads off the axis.

    **It is also the whole of what a reader with JavaScript off receives.** The
    drawing is built in the browser from 2026-09-13, so on a page that never
    runs a script the figure carries this sentence and nothing else.
    """
    tail = f" {unit}" if unit else ""
    parts = [
        f"{name} {format(figure.value.normalize(), ',f')}{tail}"
        for name, figure in zip(names, figures, strict=True)
    ]
    return f"Bar chart. {'; '.join(parts)}."[:ALT_TEXT_MAX]
