"""Which visual forms can current and historical typed plans name?"""

from enum import StrEnum
from typing import Final


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


# Compiler-supported numeric forms, not an operator-tunable vocabulary.
NUMERIC_TYPES: Final[tuple[VisualType, ...]] = (
    VisualType.BAR,
    VisualType.DOT,
    VisualType.LINE,
    VisualType.SCATTER,
    VisualType.BUBBLE,
    VisualType.SLOPE,
    VisualType.STACKED_BAR,
    VisualType.PIE,
    VisualType.HISTOGRAM,
)
