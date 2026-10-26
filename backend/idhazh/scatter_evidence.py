"""Can both scatter measures be traced to the same named entities?"""

from collections.abc import Mapping, Sequence

from idhazh.contracts.element import Element, ElementKind
from idhazh.contracts.visual import EncodingRole, VisualPlan, VisualPurpose


def refuse_scatter(
    plan: VisualPlan, channels: Mapping[EncodingRole, Sequence[Element]]
) -> str | None:
    """Refuse incomplete or ambiguous source pairs, never infer links from order."""
    if plan.purpose is not VisualPurpose.RELATIONSHIP:
        return "a scatter requires relationship purpose"
    entities = channels.get(EncodingRole.ENTITY, ())
    horizontal = channels.get(EncodingRole.QUANTITY_X, ())
    vertical = channels.get(EncodingRole.QUANTITY, ())
    series = channels.get(EncodingRole.SERIES, ())
    if not entities or len(entities) != len(horizontal) or len(entities) != len(vertical):
        return "a scatter needs one entity and both measures for every point"
    if series and len(series) != len(entities):
        return "a scatter needs one series label for every point"
    names = [element.entity for element in entities]
    if any(element.kind not in (ElementKind.ENTITY, ElementKind.PLACE) for element in entities):
        return "a scatter point needs a source entity or place element"
    if None in names or len(set(names)) != len(names):
        return "a scatter needs distinct source-labelled entities"
    for entity, x, y in zip(entities, horizontal, vertical, strict=True):
        if x.entity != entity.entity or y.entity != entity.entity:
            return "scatter measures cover different entities or lack source entity links"
        if x.element_id == y.element_id:
            return "a scatter needs two separate source measures for each entity"
    return None
