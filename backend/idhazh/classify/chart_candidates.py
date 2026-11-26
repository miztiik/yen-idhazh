"""Offer bounded local snippets with distinct quantity and date occurrence IDs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal, NamedTuple

from idhazh.ask_text_analysis import Sentence
from idhazh.contracts.element import Element, ElementKind, ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualType
from idhazh.sanitize import BLOB_PLACEHOLDER, LINK_PLACEHOLDER, sanitize, untrusted_block

# Fixed presentation window for each 1-line reading snippet within its verified sentence.
_SNIPPET_CONTEXT_WORDS: Final = 5


class ChartCandidate(NamedTuple):
    evidence_id: str
    element: Element
    sentence: Sentence


def evidence_forms(
    forms: tuple[VisualType, ...], candidates: Sequence[ChartCandidate],
) -> tuple[VisualType, ...]:
    quantities = sum(entry.element.kind is ElementKind.QUANTITY for entry in candidates)
    if quantities < 2:
        return ()
    dates = bool(time_candidates(candidates))
    return tuple(
        form for form in forms
        if (dates or form not in (VisualType.LINE, VisualType.SLOPE))
        and (quantities >= 4 or form is not VisualType.SLOPE)
    )


def time_candidates(candidates: Sequence[ChartCandidate]) -> tuple[ChartCandidate, ...]:
    dates: dict[int, set[str]] = {}
    for candidate in candidates:
        element = candidate.element
        if element.kind is ElementKind.DATE and element.value is not None:
            dates.setdefault(len(element.value), set()).add(element.value)
    return tuple(
        candidate for candidate in candidates
        if candidate.element.kind is ElementKind.DATE
        and candidate.element.value is not None
        and len(dates[len(candidate.element.value)]) >= 2
    )


def plain_chart_words(text: str) -> bool:
    return (
        bool(text)
        and text == sanitize(text)
        and "\n" not in text
        and not any(mark in text for mark in (LINK_PLACEHOLDER, BLOB_PLACEHOLDER, "<", ">"))
    )


def _snippet_side(text: str, *, side: Literal["left", "right"]) -> str:
    if not text:
        return ""
    tokens = text.split()
    if not tokens:
        return ""
    glued = not (text[-1].isspace() if side == "left" else text[0].isspace())
    gap = "" if glued else " "
    edge = tokens[-1] if side == "left" else tokens[0]
    limit = _SNIPPET_CONTEXT_WORDS + (1 if glued and not any(ch.isalnum() for ch in edge) else 0)
    if side == "left":
        if len(tokens) > limit:
            return "... " + " ".join(tokens[-limit:]) + gap
        return " ".join(tokens) + gap
    if len(tokens) > limit:
        return gap + " ".join(tokens[:limit]) + " ..."
    return gap + " ".join(tokens)


def _local_snippet(candidate: ChartCandidate) -> str:
    sentence = candidate.sentence
    element = candidate.element
    start = element.span_start - sentence.start_char
    end = element.span_end - sentence.start_char
    before = sentence.text[:start]
    excerpt = " ".join(sentence.text[start:end].split())
    after = sentence.text[end:]
    if "\n" in before or "\n" in after:
        line_before = before.rsplit("\n", 1)[-1]
        line_after = after.split("\n", 1)[0]
        if any(ch.isalnum() for ch in line_before) or any(ch.isalnum() for ch in line_after):
            before, after = line_before, line_after
    return f"{_snippet_side(before, side='left')}[{excerpt}]{_snippet_side(after, side='right')}"


def candidate_block(candidates: Sequence[ChartCandidate]) -> str:
    lines = ["Source evidence (untrusted local snippets; bracketed text is each reading):"]
    for candidate in candidates:
        lines.append(f"{candidate.evidence_id}: {_local_snippet(candidate)}")
    return "\n\n" + untrusted_block("\n".join(lines))


def chart_candidates(
    table: ElementTable,
    text: str,
    sentences: Sequence[Sentence],
    *,
    visuals: VisualsConfig | None = None,
) -> tuple[ChartCandidate, ...]:
    """Keep complete verified sentences in source order, never cut off a qualifier."""
    knobs = visuals or VisualsConfig()
    valid: set[Sentence] = set()
    for sentence in sentences:
        if not (
            0 <= sentence.start_char < sentence.end_char <= len(text)
            and text[sentence.start_char:sentence.end_char] == sentence.text
        ):
            continue
        passage = sentence.text.strip()
        if passage:
            start = sentence.start_char + len(sentence.text) - len(sentence.text.lstrip())
            valid.add(Sentence(passage, start, start + len(passage)))
    selected: list[ChartCandidate] = []
    seen: set[str] = set()
    for sentence in sorted(valid, key=lambda span: (span.start_char, span.end_char)):
        proposed = list(selected)
        for element in sorted(table.elements, key=lambda item: (item.span_start, item.span_end)):
            if element.kind not in (ElementKind.QUANTITY, ElementKind.DATE):
                continue
            if element.element_id in seen or not (
                sentence.start_char <= element.span_start < element.span_end <= sentence.end_char
                and text[element.span_start:element.span_end] == element.span_excerpt
            ):
                continue
            prefix = "ev" if element.kind is ElementKind.QUANTITY else "dt"
            proposed.append(ChartCandidate(f"{prefix}{len(proposed) + 1}", element, sentence))
        if len(proposed) == len(selected):
            continue
        if len(proposed) > knobs.evidence_max_readings or (
            len(candidate_block(proposed)) > knobs.evidence_max_chars
        ):
            continue
        selected = proposed
        seen.update(candidate.element.element_id for candidate in selected)
    return tuple(selected)
