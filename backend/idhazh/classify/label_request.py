"""Which printed quantity addresses may a label request select?"""

from __future__ import annotations

from typing import Any, Final

from idhazh.contracts.element import ElementKind, ElementTable

SENTENCE_ID_PREFIX: Final = "s"


def sentence_id(index: int) -> str:
    """A code-authored sentence address for source presentation and historical reads."""
    return f"{SENTENCE_ID_PREFIX}{index}"


def bind_label_reference_choices(
    schema: dict[str, Any],
    table: ElementTable,
) -> None:
    """Narrow a fresh native schema without changing its saved reply model."""
    definitions = schema["$defs"]
    lists = schema["properties"]
    labels = definitions["ElementLabel"]["properties"]
    candidates = [
        element.element_id for element in table.elements if element.kind is ElementKind.QUANTITY
    ]
    if candidates:
        labels["element_id"]["enum"] = candidates
    else:
        lists["labels"]["maxItems"] = 0
