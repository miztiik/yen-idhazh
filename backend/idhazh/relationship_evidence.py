"""Can each relationship point trace its measures to one named entity?"""

from collections.abc import Mapping, Sequence
from decimal import Decimal

from idhazh.contracts.element import Element, ElementKind
from idhazh.contracts.visual import EncodingRole, VisualPlan, VisualPurpose, VisualType


def refuse_relationship(
    plan: VisualPlan, channels: Mapping[EncodingRole, Sequence[Element]]
) -> str | None:
    """Refuse incomplete or ambiguous source triples, never infer links from order."""
    visual_type = plan.type
    name = visual_type.value if visual_type is not None else "relationship visual"
    if plan.purpose is not VisualPurpose.RELATIONSHIP:
        return f"a {name} requires relationship purpose"
    entities = channels.get(EncodingRole.ENTITY, ())
    horizontal = channels.get(EncodingRole.QUANTITY_X, ())
    vertical = channels.get(EncodingRole.QUANTITY, ())
    sizes = channels.get(EncodingRole.SIZE, ())
    series = channels.get(EncodingRole.SERIES, ())
    presentation = plan.presentation
    count = len(presentation.entity) if presentation is not None else len(entities)
    series_count = len(presentation.series) if presentation is not None else len(series)
    if not count or count != len(horizontal) or count != len(vertical):
        return f"a {name} needs one entity and both positions for every point"
    if visual_type is VisualType.BUBBLE and len(sizes) != count:
        return "a bubble needs one size measure for every point"
    if series_count and series_count != count:
        return f"a {name} needs one series label for every point"
    if any(size.value is None or Decimal(size.value) <= 0 for size in sizes):
        return "a bubble size measure must be positive"
    if presentation is not None:
        if len(set(presentation.entity)) != count:
            return f"a {name} needs distinct point labels"
        if len({e.element_id for e in (*horizontal, *vertical, *sizes)}) != (
            len(horizontal) + len(vertical) + len(sizes)
        ):
            return f"a {name} needs separate source readings across channels"
        return None
    names = [element.entity for element in entities]
    if any(element.kind not in (ElementKind.ENTITY, ElementKind.PLACE) for element in entities):
        return f"a {name} point needs a source entity or place element"
    if None in names or len(set(names)) != len(names):
        return f"a {name} needs distinct source-labelled entities"
    for index, (entity, x, y) in enumerate(zip(entities, horizontal, vertical, strict=True)):
        measures = [x, y]
        if visual_type is VisualType.BUBBLE:
            measures.append(sizes[index])
        if any(measure.entity != entity.entity for measure in measures):
            return f"{name} measures cover different entities or lack source entity links"
        if len({measure.element_id for measure in measures}) != len(measures):
            return f"a {name} needs separate source measures for every channel"
    return None
