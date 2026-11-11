"""Which visual forms can current and historical typed plans name?"""

from enum import StrEnum


class VisualType(StrEnum):
    """The complete vocabulary retained for reading current and historical plans.

    Committed configuration selects the active new-request types. Keeping an
    abandoned name readable neither offers it to production planning nor
    promises a future compiler. Native validation and configured replacement
    remain separate from that request selection.
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
