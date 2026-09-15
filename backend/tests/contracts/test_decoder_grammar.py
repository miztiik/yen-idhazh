"""Does every schema we hand a constrained decoder bound its own decode length?

Not "is there a `maxLength`". `visual.unbounded_leaves` already asks that, and it
answered yes throughout 2026-09-14 while the decoder ran unbounded: llama.cpp's
schema-to-grammar converter honours a `pattern` or a length bound, never both, so
a `maxLength` beside `^[a-z]+-...$` is dropped and never reaches the grammar. The
question that could disagree with that one is whether the pattern bounds itself.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from idhazh.classify import calls

pytestmark = pytest.mark.contract

#: `{2,}` and friends. `{2}` and `{2,8}` are bounded and are not this.
_OPEN_REPEAT = re.compile(r"\{\d*,\}")

#: The pattern that cost 15.8 minutes of a 4 vCPU runner on 2026-09-14, kept as
#: the detector's own witness. A checker nobody has watched fail is a checker
#: nobody knows the polarity of.
RUNAWAY_PATTERN = r"^[a-z]+-[0-9]+-[0-9]+$"


def unbounded_quantifier(pattern: str) -> str | None:
    """The first quantifier in `pattern` that admits an unbounded repeat.

    Escapes and character-class interiors are skipped, because `+` inside `[...]`
    or behind a backslash is a literal character and repeats nothing.
    """
    index = 0
    inside_class = False
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if inside_class:
            inside_class = char != "]"
            index += 1
            continue
        if char == "[":
            inside_class = True
        elif char in "+*":
            return char
        elif char == "{":
            close = pattern.find("}", index)
            if close != -1 and _OPEN_REPEAT.fullmatch(pattern[index : close + 1]):
                return pattern[index : close + 1]
        index += 1
    return None


def _patterns(node: Any, path: str = "") -> list[tuple[str, str]]:
    """Every `pattern` anywhere in a JSON schema, with where it sits."""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        declared = node.get("pattern")
        if isinstance(declared, str):
            found.append((path or "<root>", declared))
        for key, child in node.items():
            if key != "pattern":
                found += _patterns(child, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for position, child in enumerate(node):
            found += _patterns(child, f"{path}[{position}]")
    return found


def _decoder_schemas() -> dict[str, dict[str, Any]]:
    """Every schema this pipeline sends a decoder, built the way the run builds it."""
    return {
        "label": calls.label_schema(),
        "summarize_and_plan": calls.summarize_and_plan_schema(plan=True),
        "summarize_only": calls.summarize_and_plan_schema(plan=False),
        "summarize_and_plan_brief": calls.summarize_and_plan_schema(plan=True, brief=True),
    }


def test_the_detector_fires_on_the_pattern_that_cost_us_the_runner() -> None:
    assert unbounded_quantifier(RUNAWAY_PATTERN) == "+"
    assert unbounded_quantifier(r"^[a-z]{1,8}-[0-9]{1,6}-[0-9]{1,6}$") is None
    assert unbounded_quantifier(r"^\d{4}(?:-\d{2}-\d{2})?$") is None
    assert unbounded_quantifier(r"^[a-z+*]{1,4}$") is None, "a quantifier char in a class is literal"
    assert unbounded_quantifier(r"^a\+{2,}$") == "{2,}", "an open repeat is unbounded"


@pytest.mark.parametrize("name", sorted(_decoder_schemas()))
def test_every_decoder_pattern_bounds_its_own_length(name: str) -> None:
    loose = [
        (path, pattern)
        for path, pattern in _patterns(_decoder_schemas()[name])
        if unbounded_quantifier(pattern) is not None
    ]
    assert not loose, (
        f"the {name} schema carries {len(loose)} pattern(s) a decoder can stay inside "
        f"forever: {loose}. A length bound beside a pattern does not reach the grammar, "
        "so the pattern is what has to bound the decode"
    )


def test_no_schema_builder_escapes_this_check() -> None:
    """A new call site cannot be added without this test noticing it."""
    built = {
        name
        for name, value in vars(calls).items()
        if name.endswith("_schema")
        and not name.startswith("_")
        and callable(value)
        and getattr(value, "__module__", None) == calls.__name__
    }
    covered = {"label_schema", "summarize_and_plan_schema"}
    assert built == covered, (
        f"{built - covered} builds a schema for the decoder and no arm above sends it "
        "through unbounded_quantifier"
    )
