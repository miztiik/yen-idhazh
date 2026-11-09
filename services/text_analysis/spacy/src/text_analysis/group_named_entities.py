"""How are native mentions grouped without losing original spellings or occurrences?"""

from text_analysis.declare_api_contracts import (
    EntitiesData,
    EvidenceSpan,
    NamedEntitiesData,
    NamedEntityRecord,
)
from text_analysis.declare_service_settings import NamedEntitiesSettings


def group_named_entities(
    data: EntitiesData,
    settings: NamedEntitiesSettings,
) -> NamedEntitiesData:
    """Group by configured name normalization and mapped presentation type."""
    groups: dict[tuple[str, str], list[EvidenceSpan]] = {}
    for mention in sorted(data.mentions, key=lambda item: (item.start_char, item.end_char)):
        kind = settings.label_map.get(mention.label)
        if kind is None:
            continue
        name = mention.text.casefold() if settings.ignore_case else mention.text
        groups.setdefault((name, kind), []).append(
            EvidenceSpan.model_validate(mention.model_dump(exclude={"label"}))
        )
    return NamedEntitiesData(
        entities=tuple(
            NamedEntityRecord(
                text=occurrences[0].text,
                type=kind,
                occurrences=tuple(occurrences),
            )
            for (_name, kind), occurrences in groups.items()
        )
    )
