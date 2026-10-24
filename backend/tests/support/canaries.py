"""Named readers for the committed injection-canary fixtures."""

from __future__ import annotations

from typing import Final, Literal

from conftest import FIXTURES_DIR, read_text

from idhazh.contracts.base import Model

CANARY_NAMES: Final = (
    "direct-instruction-override",
    "encoded-payload",
    "exfiltration-via-url",
    "fake-system-delimiter",
    "page-title-instruction",
    "tool-call-injection",
)
CANARY_DIR = FIXTURES_DIR / "canaries"


class Canary(Model):
    """One planted attack and the text its fixture declares."""

    name: str
    attack: str
    neutralised_by: Literal["framing", "sanitizer", "schema"]
    source_url: str
    raw_title: str
    raw_text: str
    must_not_survive: list[str]
    must_survive: list[str]
    forbidden_output: dict[str, object]


def load_canary(name: str) -> Canary:
    if name not in CANARY_NAMES:
        raise ValueError(f"unknown canary fixture: {name}")
    return Canary.model_validate_json(read_text(CANARY_DIR / f"{name}.json"))
