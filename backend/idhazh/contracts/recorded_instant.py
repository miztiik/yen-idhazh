"""Which UTC interval does a saved whole-second or millisecond instant establish?"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Final

from pydantic import AfterValidator, StringConstraints

RECORDED_INSTANT_PATTERN: Final = (
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$"
)
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_MILLISECONDS_PER_SECOND: Final = 1000
_SECONDS_PER_DAY: Final = 86400


def validate_recorded_instant(value: str) -> str:
    """Validate the calendar without changing the saved text or its precision."""
    if re.fullmatch(RECORDED_INSTANT_PATTERN, value) is None:
        raise ValueError("recorded instant must use whole seconds or milliseconds in UTC")
    datetime.fromisoformat(value)
    return value


RecordedInstant = Annotated[
    str,
    StringConstraints(pattern=RECORDED_INSTANT_PATTERN),
    AfterValidator(validate_recorded_instant),
]


def instant_bounds(value: str) -> tuple[int, int]:
    """The lower-inclusive, upper-exclusive UTC interval, in epoch milliseconds."""
    delta = datetime.fromisoformat(value) - _EPOCH
    lower = (
        (delta.days * _SECONDS_PER_DAY + delta.seconds) * _MILLISECONDS_PER_SECOND
        + delta.microseconds // _MILLISECONDS_PER_SECOND
    )
    return lower, lower + (1 if "." in value else _MILLISECONDS_PER_SECOND)


def definitely_after(later: str, earlier: str) -> bool:
    """Only non-overlapping recorded intervals prove that one check was later."""
    return instant_bounds(later)[0] >= instant_bounds(earlier)[1]
