"""How are independent GLiNER operations dispatched and awaited before cleanup?"""

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass


@dataclass(frozen=True)
class Outcome:
    result: dict[str, object] | None = None
    error: str | None = None
    incomplete: bool = False


async def collect_gliner_operations(
    ner: Awaitable[Outcome], classification: Awaitable[Outcome]
) -> tuple[Outcome, Outcome]:
    """Start both operations and finish both even if one raises unexpectedly."""
    ner_result, classification_result = await asyncio.gather(
        ner, classification, return_exceptions=True
    )
    if isinstance(ner_result, BaseException):
        raise ner_result
    if isinstance(classification_result, BaseException):
        raise classification_result
    return ner_result, classification_result
