"""Builders the turn-envelope and run-shape modules share."""

from __future__ import annotations

from typing import Any


def turns_of(raw: dict[str, Any], role: str = "summarize") -> dict[str, Any]:
    block: dict[str, Any] = raw[role]["turns"]
    return block
