"""The bounded, transient chart proposal beside the summary."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from idhazh.contracts.base import Model
from idhazh.contracts.element import UNIT_MAX_LENGTH, VALUE_MAX_LENGTH
from idhazh.contracts.visual import MAX_IDS_PER_ROLE, TITLE_MAX_LENGTH, AxisTitles

# These are decoder bounds, not editorial targets. The pattern itself must
# bound the decode: the native grammar ignores maxLength when a pattern exists.
ChartWords = Annotated[str, StringConstraints(pattern=rf'^[^"\\\r\n<>]{{1,{TITLE_MAX_LENGTH}}}$')]
StatedNumber = Annotated[str, StringConstraints(pattern=rf"^[-0-9.,]{{1,{VALUE_MAX_LENGTH}}}$")]
StatedUnit = Annotated[str, StringConstraints(pattern=rf'^[^"\\\r\n<>]{{1,{UNIT_MAX_LENGTH}}}$')]


class Reading(Model):
    value: StatedNumber
    unit: StatedUnit | None


class NamedReading(Model):
    label: ChartWords
    reading: Reading


class CategoryReading(NamedReading):
    series: ChartWords | None = None


class DatedReading(Model):
    date: ChartWords
    reading: Reading
    series: ChartWords | None = None


class Change(Model):
    label: ChartWords
    start: Reading
    end: Reading


class Point(Model):
    label: ChartWords
    x: Reading
    y: Reading
    series: ChartWords | None = None


class SizedPoint(Point):
    size: Reading


class _Proposal(Model):
    title: ChartWords


class _AxisProposal(_Proposal):
    # New requests require it; recorded replies without titles can still be read.
    axis_titles: AxisTitles | None = None


class Comparison(_AxisProposal):
    type: Literal["bar", "dot"]
    rows: Annotated[list[CategoryReading], Field(min_length=2, max_length=MAX_IDS_PER_ROLE)]


class Line(_AxisProposal):
    type: Literal["line"]
    rows: Annotated[list[DatedReading], Field(min_length=2, max_length=MAX_IDS_PER_ROLE)]


class Slope(_AxisProposal):
    type: Literal["slope"]
    start_date: ChartWords
    end_date: ChartWords
    rows: Annotated[list[Change], Field(min_length=2, max_length=MAX_IDS_PER_ROLE // 2)]


class Scatter(_Proposal):
    type: Literal["scatter"]
    x_measure: ChartWords
    y_measure: ChartWords
    rows: Annotated[list[Point], Field(min_length=2, max_length=MAX_IDS_PER_ROLE)]


class Bubble(_Proposal):
    type: Literal["bubble"]
    x_measure: ChartWords
    y_measure: ChartWords
    size_measure: ChartWords
    rows: Annotated[list[SizedPoint], Field(min_length=2, max_length=MAX_IDS_PER_ROLE)]


class Pie(_Proposal):
    type: Literal["pie"]
    whole: NamedReading
    rows: Annotated[list[NamedReading], Field(min_length=2, max_length=MAX_IDS_PER_ROLE)]


class StackedBar(_AxisProposal):
    type: Literal["stacked_bar"]
    measure: ChartWords
    whole: NamedReading
    rows: Annotated[list[NamedReading], Field(min_length=2, max_length=MAX_IDS_PER_ROLE)]


class Histogram(_AxisProposal):
    type: Literal["histogram"]
    group: ChartWords
    rows: Annotated[list[Reading], Field(min_length=2, max_length=MAX_IDS_PER_ROLE)]


ChartProposal = Comparison | Line | Slope | Scatter | Bubble | Pie | StackedBar | Histogram
