"""Which printed references and anchorable source ranges may a label request select?"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from idhazh.contracts.article import UNTRUSTED_LINE_MAX
from idhazh.contracts.element import ElementKind, ElementTable


def bind_label_reference_choices(
    schema: dict[str, Any],
    table: ElementTable,
    text: str,
    sentences: Sequence[tuple[str, int, int]],
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
    addresses = [address for address, _, _ in sentences]
    if addresses:
        definitions["Citation"]["properties"]["sentence_id"]["enum"] = addresses
        lists["lede_sentence_ids"]["items"]["enum"] = addresses
    else:
        for name in ("proposed", "entity_mentions", "place_mentions", "lede_sentence_ids"):
            lists[name]["maxItems"] = 0

    native_range = definitions["SentenceRange"]
    properties = native_range["properties"]
    branches = []
    for index, (first, start, _) in enumerate(sentences):
        ends = []
        for last_index in range(index, len(sentences)):
            last, _, end = sentences[last_index]
            excerpt = text[start:end].strip()
            if len(excerpt) > UNTRUSTED_LINE_MAX:
                # Extending the same source slice cannot reduce its trimmed length.
                break
            if excerpt:
                ends.append(last)
        if ends:
            branches.append(
                native_range
                | {
                    "properties": properties
                    | {
                        "sentence_start_id": properties["sentence_start_id"] | {"enum": [first]},
                        "sentence_end_id": properties["sentence_end_id"] | {"enum": ends},
                        "speaker": {"$ref": "#/$defs/LabelRangeSpeaker"},
                    }
                }
            )
    if branches:
        definitions["LabelRangeSpeaker"] = properties["speaker"].copy()
        definitions["SentenceRange"] = {"anyOf": branches}
    else:
        for name in ("quotes", "claims"):
            lists[name]["maxItems"] = 0
