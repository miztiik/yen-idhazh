"""Which tables of names and figures does one article hold?

A table is what a reader would copy out of the article into a list: "Denmark approved 1,200 MW.
Germany approved 900 MW." gives Denmark 1,200 MW and Germany 900 MW. Code finds them with no
model, so the model is shown real rows and asked only whether a chart of them is worth drawing.

**A wrong pairing is worse than a missed one.** A chart of Germany beside Denmark's figure is
made of true numbers, so nothing downstream can refuse it. So a name takes the figures that follow
it up to the next name, its block, and a table of one unit forms only where every name in a run of
sentences has exactly one figure of that unit in its block. A name with none, a name with two, a
figure before the first name, a name that overlaps a figure: the sentence pairs nothing for that
unit. There is no distance limit and no figure-before-name reading: each would be a new rule, to
add only when a check over real articles shows tables lost without it.

**Each unit is read on its own.** "AEM climbed 4.1% to $6.58, UMS rose 2.4% to $1.68" gives a table
of percentages and a table of prices over the same names, and the model chooses between them.

**A repeat of a name counts although it is not an element.** The element table keeps one element
per distinct name, at its first occurrence, so a later "Germany" is invisible in it and
"Denmark said Germany built 1,200 MW" would read as Denmark's figure. The names are searched for
again in the text, as whole words in any case, so every mention is seen. A row cites the first
occurrence's element, which holds the same characters.

**A table is a run of consecutive sentences** that each pair for the unit, whose names are all
different, and whose rows number no fewer than `visuals.min_chart_points` and no more than the
smaller of `visuals.max_chart_points` and the plan's limit on ids in one channel. Over the ceiling
the run is refused whole and never trimmed: a chart of the first eight rows of a list of twelve is
a different claim. A run is refused as well when the sentence just before or just after it names
something and holds a figure of its unit that it could not pair, because the list may go on there;
a sentence naming nothing is not a list. A run holding a cell
the compiler would refuse - more than one line, a `|`, anything `sanitize` changes - or two names
that the compiler's cut makes equal is refused whole, because a table missing a row is not the
article's.

**The model is shown the label the chart will draw.** A name longer than
`visuals.max_label_characters` is cut the way the compiler cuts it, so what the model reads is
what a reader sees.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import pairwise
from types import MappingProxyType
from typing import Final, NamedTuple

from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.element import Element, ElementKind, ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import MAX_IDS_PER_ROLE, VisualPurpose, VisualType
from idhazh.contracts.visual_decision import VisualKind
from idhazh.elements import SpanDriftError, sentence_starts
from idhazh.sanitize import sanitize
from idhazh.text_fit import fit_source_span

#: What a table of one name and one figure per mark can be drawn as, and what the reader is asked
#: to do with it. Only the forms whose channels are a name and a figure and that need no separately
#: stated whole belong here: a pie or a stacked bar would need one, and code cannot find it.
TABLE_FORMS: Final[Mapping[VisualType, VisualPurpose]] = MappingProxyType(
    {
        VisualType.BAR: VisualPurpose.COMPARISON,
        VisualType.DOT: VisualPurpose.COMPARISON,
    }
)


class FigureRow(NamedTuple):
    """One row: a name, the label a chart draws for it, and the figure stated beside it."""

    code: str
    label: str
    name: Element
    figure: Element


class FigureTable(NamedTuple):
    """The rows of one table, in the order the article states them."""

    rows: tuple[FigureRow, ...]


class _Occurrence(NamedTuple):
    """One place a name stands in the text, and the element that holds its words."""

    start: int
    end: int
    name: Element


class _Item(NamedTuple):
    start: int
    end: int
    subject: _Occurrence | Element


class _Sentence(NamedTuple):
    """One sentence read as a name, then the figures up to the next name, and so on.

    `blocks` is `None` when two things in it run into each other, and then nothing in it pairs.
    """

    units: frozenset[str]
    named: bool
    leading: tuple[Element, ...]
    blocks: tuple[tuple[_Occurrence, tuple[Element, ...]], ...] | None


_Pair = tuple[_Occurrence, Element]


def forms_on_offer(visuals: VisualsConfig) -> tuple[VisualType, ...]:
    """The chart forms a table may be offered as under this configuration, or none.

    Charts switched off, or neither form selected, means no table is built at all, so nothing
    asks the model about a chart nobody can publish.
    """
    if VisualKind.CHART not in visuals.enabled_kinds:
        return ()
    selected = visuals.select_types()
    return tuple(form for form in TABLE_FORMS if form in selected)


def tables_of_figures(
    text: str, table: ElementTable, *, visuals: VisualsConfig
) -> list[FigureTable]:
    """Every table of names and figures in `text`, which is the string `table` indexes.

    Reads the table's names and figures and the text around them, and nothing else: no model,
    no network, and no word of the article decides anything but where a name stands. A table
    built over a different string than `text` is refused, because every offset in it would point
    into a document the rows were not read from.
    """
    if derive_text_digest(text) != table.source_text_hash:
        raise SpanDriftError(
            f"{table.item_id}: the table indexes a different string than the text read"
        )
    if not forms_on_offer(visuals):
        return []
    names = _outermost(
        _occurrences(
            text,
            [e for e in table.elements if e.kind in (ElementKind.ENTITY, ElementKind.PLACE)],
        )
    )
    figures = [e for e in table.elements if e.kind is ElementKind.QUANTITY]
    names, figures = _settled(names, figures)

    starts = sentence_starts(text)
    found: dict[int, list[_Item]] = defaultdict(list)
    for occurrence in names:
        found[bisect_right(starts, occurrence.start)].append(
            _Item(occurrence.start, occurrence.end, occurrence)
        )
    for figure in figures:
        found[bisect_right(starts, figure.span_start)].append(
            _Item(figure.span_start, figure.span_end, figure)
        )
    sentences = {index: _read(items) for index, items in found.items()}

    runs: list[list[_Pair]] = []
    for unit in sorted({figure.unit for figure in figures if figure.unit is not None}):
        runs.extend(_runs_of(sentences, unit))
    runs.sort(key=lambda run: run[0][1].span_start)

    tables: list[FigureTable] = []
    number = 0
    for run in runs:
        labels = _labels(run, visuals)
        if labels is None:
            continue
        rows = []
        for (occurrence, figure), label in zip(run, labels, strict=True):
            number += 1
            rows.append(FigureRow(f"r{number}", label, occurrence.name, figure))
        tables.append(FigureTable(tuple(rows)))
    return tables


def _occurrences(text: str, names: Sequence[Element]) -> list[_Occurrence]:
    """Every place each name's words stand in the text, whole words in any case."""
    found: list[_Occurrence] = []
    for name in names:
        words = name.span_excerpt.split()
        if not words:
            continue
        pattern = re.compile(
            r"(?<!\w)" + r"\s+".join(re.escape(word) for word in words) + r"(?!\w)",
            re.IGNORECASE,
        )
        found.extend(_Occurrence(m.start(), m.end(), name) for m in pattern.finditer(text))
    return found


def _outermost(found: list[_Occurrence]) -> list[_Occurrence]:
    """A name standing inside a longer name is not a second name.

    A partial overlap is kept on purpose: two names that run into each other leave their
    sentence unreadable, and nothing in it pairs.
    """
    kept: list[_Occurrence] = []
    reach = -1
    for occurrence in sorted(found, key=lambda o: (o.start, -o.end)):
        if occurrence.end <= reach:
            continue
        kept.append(occurrence)
        reach = occurrence.end
    return kept


def _settled(
    names: list[_Occurrence], figures: list[Element]
) -> tuple[list[_Occurrence], list[Element]]:
    """Whichever of a name and a figure belongs to the other gives way.

    "MW" labelled as an organisation inside "1,200 MW" is part of the figure. A figure that starts
    inside a name, the 225 of "Nikkei 225" with the word after it, is part of the name.
    """
    kept_names = [
        n
        for n in names
        if not any(f.span_start <= n.start and n.end <= f.span_end for f in figures)
    ]
    kept_figures = [
        f for f in figures if not any(n.start <= f.span_start < n.end for n in kept_names)
    ]
    return kept_names, kept_figures


def _read(items: list[_Item]) -> _Sentence:
    ordered = sorted(items, key=lambda item: (item.start, item.end))
    units = frozenset(
        item.subject.unit
        for item in ordered
        if isinstance(item.subject, Element) and item.subject.unit is not None
    )
    named = any(isinstance(item.subject, _Occurrence) for item in ordered)
    if any(left.end > right.start for left, right in pairwise(ordered)):
        return _Sentence(units, named, (), None)
    leading: list[Element] = []
    blocks: list[tuple[_Occurrence, list[Element]]] = []
    for item in ordered:
        if isinstance(item.subject, _Occurrence):
            blocks.append((item.subject, []))
        elif blocks:
            blocks[-1][1].append(item.subject)
        else:
            leading.append(item.subject)
    return _Sentence(units, named, tuple(leading), tuple((o, tuple(f)) for o, f in blocks))


def _pairs_for(sentence: _Sentence, unit: str) -> list[_Pair] | None:
    """The pairs of this unit a sentence makes, or nothing when any name cannot be paired."""
    if sentence.blocks is None or any(figure.unit == unit for figure in sentence.leading):
        return None
    pairs: list[_Pair] = []
    for occurrence, block in sentence.blocks:
        mine = [figure for figure in block if figure.unit == unit]
        if len(mine) != 1:
            return None
        pairs.append((occurrence, mine[0]))
    return pairs or None


def _runs_of(sentences: dict[int, _Sentence], unit: str) -> list[list[_Pair]]:
    """The runs of consecutive sentences that pair for one unit, none with a broken neighbour."""
    paired: dict[int, list[_Pair]] = {}
    broken: set[int] = set()
    for index, sentence in sentences.items():
        pairs = _pairs_for(sentence, unit)
        if pairs is not None:
            paired[index] = pairs
        elif unit in sentence.units and sentence.named:
            broken.add(index)
    groups: list[list[int]] = []
    for index in sorted(paired):
        if groups and index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    return [
        [pair for index in group for pair in paired[index]]
        for group in groups
        if group[0] - 1 not in broken and group[-1] + 1 not in broken
    ]


def _is_plain_cell(words: str) -> bool:
    return len(words.splitlines()) == 1 and "|" not in words and sanitize(words) == words


def _labels(run: list[_Pair], visuals: VisualsConfig) -> list[str] | None:
    """The labels the chart would draw for this run, or nothing when it cannot be offered."""
    ceiling = min(visuals.max_chart_points, MAX_IDS_PER_ROLE)
    if not visuals.min_chart_points <= len(run) <= ceiling:
        return None
    if not all(
        _is_plain_cell(occurrence.name.span_excerpt) and _is_plain_cell(figure.span_excerpt)
        for occurrence, figure in run
    ):
        return None
    labels = [
        fit_source_span(occurrence.name.span_excerpt, max_characters=visuals.max_label_characters)
        for occurrence, _ in run
    ]
    return labels if len({label.casefold() for label in labels}) == len(labels) else None
