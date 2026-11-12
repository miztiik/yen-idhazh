"""Which printed candidate, date and citation addresses may a label request select?"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from idhazh.contracts.element import ElementKind, ElementTable


def bind_label_reference_choices(
    schema: dict[str, Any],
    table: ElementTable,
    sentences: Sequence[str],
) -> None:
    """Narrow a fresh native schema without changing its saved reply model."""
    definitions = schema["$defs"]
    lists = schema["properties"]
    labels = definitions["ElementLabel"]["properties"]
    candidates = [element.element_id for element in table.elements]
    if candidates:
        labels["element_id"]["enum"] = candidates
    else:
        lists["labels"]["maxItems"] = 0
    labels["time_element_id"]["enum"] = [
        *(element.element_id for element in table.elements if element.kind is ElementKind.DATE),
        "",
    ]
    addresses = list(sentences)
    if addresses:
        definitions["Citation"]["properties"]["sentence_id"]["enum"] = addresses
    else:
        for name in ("proposed", "entity_mentions", "place_mentions"):
            lists[name]["maxItems"] = 0
