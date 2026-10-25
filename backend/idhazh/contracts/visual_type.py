"""Which visual forms may a typed request name, whether or not they can be drawn?"""

from enum import StrEnum


class VisualType(StrEnum):
    """The full native vocabulary, independent of article and item-health contracts."""

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
