"""Fit source spans to a display limit without changing their wording."""

from __future__ import annotations


def fit_source_span(source_span: str, *, max_characters: int) -> str:
    """Keep the span intact or show its exact opening characters plus `...`."""
    ellipsis = "..."
    if max_characters < len(ellipsis) + 1:
        raise ValueError("max_characters must leave room for one source character and `...`")
    if len(source_span) <= max_characters:
        return source_span
    return f"{source_span[: max_characters - len(ellipsis)]}{ellipsis}"
