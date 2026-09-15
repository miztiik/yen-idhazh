"""What layout does a hand-curated config keep, and what stops the next edit drifting off it?"""

from __future__ import annotations

import difflib
import json
from typing import Any

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh.contracts import canonical_json
from idhazh.contracts.base import Contract, records_json
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

pytestmark = pytest.mark.contract

#: The three registries a person writes by hand. Each is lists of short records
#: read together or not at all, so each is written one record a line. Every
#: other payload here is written by a program and keeps the field-a-line
#: layout, which is the right shape for reading down a single record.
CURATED: dict[str, type[Contract]] = {
    "sources.json": Sources,
    "taxonomy.json": Taxonomy,
    "watchlist.json": Watchlist,
}


def first_difference(committed: str, rewritten: str) -> str:
    lines = difflib.unified_diff(
        committed.splitlines(), rewritten.splitlines(), "on disk", "as the writer would", n=0
    )
    return "\n".join(list(lines)[:12])


@pytest.mark.parametrize("name", sorted(CURATED), ids=lambda n: n)
def test_a_curated_registry_survives_a_read_and_a_rewrite(name: str) -> None:
    """A hand-edited config re-serializes to the bytes on disk.

    This is what holds the layout still. Without it a curator's next edit
    arrives buried in a whole-file reshuffle and the diff stops showing what
    changed - and there is nothing to notice the drift, because every layout
    parses to the same payload.
    """
    text = read_text(CONFIG_DIR / name)
    rewritten = CURATED[name].from_json(text).to_json()
    assert rewritten == text, (
        f"config/{name} is not written the way the contract writes it. Keys are "
        f"sorted, every field is spelled out even at its default, and each record "
        f"sits on one line:\n{first_difference(text, rewritten)}"
    )


@pytest.mark.parametrize("name", sorted(CURATED), ids=lambda n: n)
def test_a_curated_registry_holds_one_record_a_line(name: str) -> None:
    """Which layout, said in the file's own bytes.

    The round trip above passes against any layout the writer is consistent
    about, so on its own it would not notice the day the writer went back to a
    field a line. This reads the committed text and counts.
    """
    text = read_text(CONFIG_DIR / name)
    payload: dict[str, Any] = json.loads(text)
    expected = [
        record
        for _, value in sorted(payload.items())
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
        for record in value
    ]
    assert expected, f"config/{name} holds no records, so this proves nothing"

    found = [
        json.loads(line.strip().rstrip(","))
        for line in text.splitlines()
        if line.startswith("    {")
    ]
    assert found == expected, f"config/{name} does not hold one record a line"


def test_a_payload_with_no_record_list_is_written_exactly_as_canonical_json() -> None:
    """The writer is `canonical_json` plus one rule. This is everything but the rule.

    Sorted keys, two-space indent, ASCII, one trailing newline - all of it
    unchanged, so the three properties the one serialization buys are intact.
    """
    payload = {"b": {"d": [1, 2], "c": None}, "a": [[1], []], "e": "x"}
    assert records_json(payload) == canonical_json(payload)


def test_a_list_of_objects_is_written_one_object_a_line() -> None:
    """And this is the rule. The space after a colon is the only one a record keeps."""
    text = records_json({"feeds": [{"b": 1, "a": 2}, {"a": 3, "b": 4}]})
    assert text == '{\n  "feeds": [\n    {"a": 2,"b": 1},\n    {"a": 3,"b": 4}\n  ]\n}\n'
