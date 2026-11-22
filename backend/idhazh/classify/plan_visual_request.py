"""Which numeric forms may this build offer in a chart request?"""

from idhazh.contracts.element import ElementKind, ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualType
from idhazh.contracts.visual_decision import VisualKind
from idhazh.render import can_compile


def chart_capabilities(visuals: VisualsConfig) -> tuple[VisualType, ...]:
    """Only operator selection and compiler capability decide the forms."""
    if VisualKind.CHART not in visuals.enabled_kinds:
        return ()
    return tuple(form for form in visuals.select_types() if can_compile(form))


def chart_forms(table: ElementTable, *, visuals: VisualsConfig) -> tuple[VisualType, ...]:
    """Ask about a chart only if the item has the minimum number of readings."""
    if sum(element.kind is ElementKind.QUANTITY for element in table.elements) < 2:
        return ()
    return chart_capabilities(visuals)
