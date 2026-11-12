"""Which printed quantity and citation addresses may a label request select?"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from idhazh.contracts.element import ElementKind, ElementTable

SENTENCE_ID_PREFIX: Final = "s"


def sentence_id(index: int) -> str:
    """A sentence's printed address, copied rather than counted by the model."""
    return f"{SENTENCE_ID_PREFIX}{index}"


def bind_label_reference_choices(
    schema: dict[str, Any],
    table: ElementTable,
    sentences: Sequence[str],
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
    addresses = list(sentences)
    if addresses:
        definitions["Citation"]["properties"]["sentence_id"]["enum"] = addresses
    else:
        for name in ("proposed", "named_mentions"):
            lists[name]["maxItems"] = 0
