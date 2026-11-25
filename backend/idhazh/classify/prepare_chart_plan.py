"""Prepare renderer channels without treating model wording as source evidence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from pydantic_core import PydanticCustomError

from idhazh.classify.chart_candidates import ChartCandidate, plain_chart_words, time_candidates
from idhazh.classify.chart_reply import (
    Bubble,
    ChartProposal,
    Comparison,
    Histogram,
    Line,
    Pie,
    Reading,
    Scatter,
    Slope,
    StackedBar,
)
from idhazh.contracts.element import ElementKind, ElementTable
from idhazh.contracts.visual import (
    AxisTitles,
    ChartPresentation,
    EncodingRole,
    PlanDecision,
    PlanEncodings,
    VisualPlan,
    VisualPurpose,
    VisualType,
)
from idhazh.elements import SpanDriftError
from idhazh.visual_vocabulary import PLAN_VOCABULARY_VERSION

_R = EncodingRole
_PURPOSES = {
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


def _refuse(field: str, reason: str) -> PydanticCustomError:
    return PydanticCustomError("chart_preparation_failed", reason, {"field": field})


class _Channels:
    def __init__(self, candidates: Sequence[ChartCandidate]) -> None:
        self.readings = {candidate.evidence_id: candidate.element for candidate in candidates}
        self.dates = {
            candidate.evidence_id: candidate.element for candidate in time_candidates(candidates)
        }
        self.interpretations: dict[str, str] = {}
        self.negative_ids: list[str] = []
        self.references: dict[EncodingRole, list[str]] = defaultdict(list)

    def take(self, reading: Reading) -> str:
        element = self.readings.get(reading.evidence_id)
        if element is None or element.kind is not ElementKind.QUANTITY:
            raise _refuse("rows", "each plot value needs a supplied quantity occurrence ID")
        previous = self.interpretations.setdefault(element.element_id, reading.interpretation)
        if previous != reading.interpretation:
            raise _refuse("rows", "one source occurrence must have one interpretation")
        if (
            reading.interpretation == "negative_magnitude"
            and element.element_id not in self.negative_ids
        ):
            self.negative_ids.append(element.element_id)
        return element.element_id

    def number(self, role: EncodingRole, reading: Reading) -> None:
        self.references[role].append(self.take(reading))

    def date(self, words: str) -> str:
        # Dates may name an axis position but are never supplied as numeric readings.
        element = self.dates.get(words)
        if element is None or element.kind is not ElementKind.DATE or element.value is None:
            raise _refuse("date", "a time role needs a supplied date occurrence ID")
        self.references[_R.TIME].append(element.element_id)
        return element.value


def _series(names: Sequence[str | None]) -> list[str]:
    present = [name for name in names if name is not None]
    if present and len(present) != len(names):
        raise _refuse("rows.series", "series labels must cover every row or none")
    return present


def prepare_chart_plan(
    choice: ChartProposal,
    forms: tuple[VisualType, ...],
    text: str,
    table: ElementTable,
    candidates: Sequence[ChartCandidate],
) -> VisualPlan:
    """Select actual source values; leave the model's names as display text."""
    form = VisualType(choice.type)
    if form not in forms:
        raise _refuse("type", "the renderer did not offer that form")
    if drift := table.span_drift(text):
        raise SpanDriftError(drift)
    channels = _Channels(candidates)
    whole: str | None = None
    presentation = ChartPresentation()
    if isinstance(choice, Scatter | Bubble):
        presentation.axis_titles = AxisTitles(
            x=choice.x_measure, y=choice.y_measure,
            size=choice.size_measure if isinstance(choice, Bubble) else None,
        )
        presentation.entity = [row.label for row in choice.rows]
        presentation.series = _series([row.series for row in choice.rows])
        for point in choice.rows:
            channels.number(_R.QUANTITY_X, point.x)
            channels.number(_R.QUANTITY, point.y)
        if isinstance(choice, Bubble):
            for point in choice.rows:
                channels.number(_R.SIZE, point.size)
    elif isinstance(choice, Comparison):
        presentation.axis_titles = choice.axis_titles
        presentation.category = [row.label for row in choice.rows]
        presentation.series = _series([row.series for row in choice.rows])
        for named in choice.rows:
            channels.number(_R.QUANTITY, named.reading)
    elif isinstance(choice, Line):
        presentation.axis_titles = choice.axis_titles
        presentation.series = _series([row.series for row in choice.rows])
        for dated in choice.rows:
            channels.date(dated.date)
            channels.number(_R.QUANTITY, dated.reading)
    elif isinstance(choice, Slope):
        presentation.axis_titles = choice.axis_titles
        start, end = channels.date(choice.start_date), channels.date(choice.end_date)
        if len(start) != len(end) or start >= end:
            raise _refuse("date", "a slope needs two ordered dates of the same precision")
        presentation.entity = [row.label for row in choice.rows]
        for change in choice.rows:
            channels.number(_R.QUANTITY, change.start)
            channels.number(_R.QUANTITY, change.end)
    elif isinstance(choice, Pie | StackedBar):
        whole = channels.take(choice.whole.reading)
        if isinstance(choice, StackedBar):
            presentation.axis_titles = choice.axis_titles
            presentation.category = [choice.whole.label]
            presentation.series = [row.label for row in choice.rows]
        else:
            presentation.category = [row.label for row in choice.rows]
        for part in choice.rows:
            channels.number(_R.QUANTITY, part.reading)
    else:
        assert isinstance(choice, Histogram)
        presentation.axis_titles = choice.axis_titles
        for reading in choice.rows:
            channels.number(_R.BINS, reading)

    axes = presentation.axis_titles
    names = [
        choice.title,
        *([choice.comparison_basis] if isinstance(choice, Comparison | Slope) else []),
        *(label for group in presentation.filled().values() for label in group),
        *([axes.x, axes.y, *([axes.size] if axes.size is not None else [])] if axes else []),
    ]
    if not all(plain_chart_words(name) for name in names):
        raise _refuse("title", "chart display wording must be plain text")
    if axes is not None and axes.size is not None and form is not VisualType.BUBBLE:
        raise _refuse("axis_titles", "only a bubble has a size measure")

    references = channels.references
    ids = dict.fromkeys(cited for channel in references.values() for cited in channel)
    if whole is not None:
        ids[whole] = None
    return VisualPlan(
        version=VisualPlan.schema_version(),
        decision=PlanDecision.VISUAL,
        purpose=_PURPOSES[form],
        type=form,
        declared_whole_element_id=whole,
        encodings=PlanEncodings(**{role.value: references[role] for role in EncodingRole}),
        element_ids=list(ids),
        negative_magnitude_element_ids=channels.negative_ids,
        presentation=presentation,
        why="Prepared from model wording and supplied source readings.",
        title=choice.title,
        caption=None,
        plan_version=PLAN_VOCABULARY_VERSION,
    )
