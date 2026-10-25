"""Which visual forms may a typed request name, whether or not they can be drawn?"""

from enum import StrEnum


class VisualType(StrEnum):
    """The full declarable vocabulary of forms a plan may ask for.

    Declarable is not renderable. A type with no compiler template can be named
    by a plan. Code tries only a supported replacement that preserves purpose
    and source facts and passes target validation; otherwise the item has no
    visual. Requested and delivered types show which template is worth building
    next without forcing an unsuitable drawing onto a reader.
    """

    BAR = "bar"
    DOT = "dot"
    LINE = "line"
    AREA = "area"
    SCATTER = "scatter"
    BUBBLE = "bubble"
    SLOPE = "slope"
    STACKED_BAR = "stacked_bar"
    PIE = "pie"
    HISTOGRAM = "histogram"
    TIMELINE = "timeline"
    TABLE = "table"
    FLOW = "flow"
    COMPARISON = "comparison"
    CALLOUT = "callout"
    QUOTECARD = "quotecard"
    WHOWHAT = "whowhat"
    KEYFACTS = "keyfacts"
