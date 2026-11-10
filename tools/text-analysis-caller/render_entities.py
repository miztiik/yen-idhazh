"""How are native entity groups projected without changing their evidence?"""

from dataclasses import dataclass

from render_tables import (
    read_integer,
    read_list,
    read_object,
    read_score,
    read_text,
    render_cell,
    render_table,
)


@dataclass(frozen=True)
class EntityGroup:
    text: str
    kind: str
    occurrences: tuple[dict[str, object], ...]
    order: int


def read_span(value: object, source: str, *, label: bool = False) -> dict[str, object]:
    keys = {"text", "start_char", "end_char", "sentence_index"}
    if label:
        keys.add("label")
    span = read_object(value, keys)
    text = read_text(span["text"])
    start = read_integer(span["start_char"])
    end = read_integer(span["end_char"])
    read_integer(span["sentence_index"])
    if not text or start >= end or source[start:end] != text:
        raise ValueError("Evidence span does not match the source")
    if label:
        read_text(span["label"], nonblank=True)
    return span


def render_offset(span: dict[str, object]) -> str:
    return f"[{span['start_char']}, {span['end_char']})"


def render_evidence(span: dict[str, object]) -> str:
    return f"{render_cell(span['text'])} ({render_offset(span)}, sentence {span['sentence_index']})"


def _position(span: dict[str, object]) -> tuple[int, int]:
    return read_integer(span["start_char"]), read_integer(span["end_char"])


def project_spacy_groups(items: object, source: str) -> list[EntityGroup]:
    groups = []
    for order, value in enumerate(read_list(items), 1):
        item = read_object(value, {"text", "type", "occurrences"})
        text = read_text(item["text"], nonblank=True)
        kind = read_text(item["type"], nonblank=True)
        occurrences = [read_span(span, source) for span in read_list(item["occurrences"])]
        if not occurrences or occurrences[0]["text"] != text:
            raise ValueError("Grouped evidence must retain its first source spelling")
        groups.append(EntityGroup(text, kind, tuple(sorted(occurrences, key=_position)), order))
    return groups


def project_gliner_groups(
    items: object, source: str, labels: list[str] | None
) -> list[EntityGroup]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for value in read_list(items):
        item = read_object(value)
        if not {"text", "label"}.issubset(item) or item.keys() - {
            "text", "label", "score", "start_char", "end_char",
        }:
            raise ValueError("Invalid GLiNER entity evidence")
        text = read_text(item["text"], nonblank=True)
        label = read_text(item["label"], nonblank=True)
        if "score" in item:
            read_score(item["score"], confidence=True)
        if "start_char" in item or "end_char" in item:
            start, end = _position(item)
            if start >= end or end > len(source) or source[start:end] != text:
                raise ValueError("GLiNER span does not match the source")
        if labels is not None and label not in labels:
            raise ValueError("GLiNER entity label was not requested")
        grouped.setdefault((text, label), []).append(item)
    return [
        EntityGroup(
            text, label,
            tuple(sorted(spans, key=_position)) if all("start_char" in span for span in spans)
            else tuple(spans),
            order,
        )
        for order, ((text, label), spans) in enumerate(grouped.items(), 1)
    ]


def _table_letter(prefix: str, index: int) -> str:
    suffix = ""
    while True:
        index, remainder = divmod(index, 26)
        suffix = chr(ord("A") + remainder) + suffix
        if not index:
            return prefix + suffix
        index -= 1


def render_native_evidence(span: dict[str, object]) -> str:
    parts = [render_offset(span)] if "start_char" in span else []
    if "score" in span:
        parts.append("score " + render_cell(span["score"]))
    return "; ".join(parts)


def render_entity_tables(
    groups: list[EntityGroup],
    types: list[str] | None,
    *,
    prefix: str,
    state: str | None = None,
    gliner: bool = False,
) -> str:
    """Retain configured types and sort only the display, never the native payload."""
    if state is not None and groups:
        raise ValueError("Unavailable entity tables cannot contain successful groups")
    if types is None:
        types = list(dict.fromkeys(group.kind for group in groups))
    elif any(group.kind not in types for group in groups):
        raise ValueError("Returned entity type is absent from the saved selection")
    if not types:
        return render_table(
            prefix,
            "Named entities",
            [],
            [],
            empty=state or "No entity types were recorded in the saved configuration/request.",
        )
    titles = {"organization": "Organizations", "location": "Locations", "person": "People"}
    sections = []
    for index, kind in enumerate(types):
        selected = sorted(
            (group for group in groups if group.kind == kind),
            key=lambda group: (
                -len(group.occurrences),
                min(
                    (read_integer(span["start_char"]) for span in group.occurrences
                     if "start_char" in span),
                    default=float("inf"),
                ),
                group.order,
            ),
        )
        metadata = not gliner or any(
            "start_char" in span or "score" in span
            for group in selected for span in group.occurrences
        )
        rows = []
        for group in selected:
            positions = [
                render_native_evidence(span)
                if gliner
                else render_evidence(span)
                for span in group.occurrences
            ]
            row = [render_cell(group.text), str(len(group.occurrences))]
            if metadata:
                row.append("<br>".join(positions))
            rows.append(row)
        sections.append(
            render_table(
                _table_letter(prefix, index),
                titles.get(kind, kind),
                ["Original entity text", "Returned occurrence count"] + (
                    ["Native evidence" if gliner else "Source positions"] if metadata else []
                ),
                rows,
                empty=state or "No results were returned for this requested type.",
                row_ids=[group.order for group in selected],
            )
        )
    return "\n\n".join(sections)
