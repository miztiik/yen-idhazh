"""Does the frontend's run-record reader still read keys the run record writes?

`frontend/src/lib/server/recorded-line.ts` reads two keys of each record in a
published day's `run.json`: the line that build grouped the day at, and when
the build finished. It names them once, in `RECORD_KEYS`. A key renamed in
`RunRecord` would leave that reader finding no line, and the Judgement page
would work the line out from the fitted rows with no error. So this holds each
name, and the kind of value the reader takes from it, to the contract.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.run_manifest import RunManifest

pytestmark = pytest.mark.contract

READER: Final[Path] = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "recorded-line.ts"

#: What the reader takes from each key, as a JSON Schema kind: the line is a
#: number, and the finishing time is text it compares.
TAKES: Final[dict[str, str]] = {"line": "number", "finishedAt": "string"}

_KEY = re.compile(r"^\t(?P<role>[A-Za-z]+): '(?P<key>[a-z_]+)',?$")


def reader_keys(text: str) -> dict[str, str]:
    """Each value the reader takes, and the record key it reads it from."""
    _, opened, rest = text.partition("export const RECORD_KEYS = {\n")
    assert opened, f"{READER.name} no longer names its keys in RECORD_KEYS"
    body, closed, _ = rest.partition("\n}")
    assert closed, f"{READER.name} leaves RECORD_KEYS unclosed"
    keys: dict[str, str] = {}
    for line in body.split("\n"):
        found = _KEY.match(line)
        assert found, f"{READER.name} names a key this check cannot read: {line!r}"
        keys[found["role"]] = found["key"]
    return keys


def record_properties() -> dict[str, Any]:
    """Each key a run record is written with, and its schema."""
    properties: dict[str, Any] = RunManifest.json_schema()["$defs"]["RunRecord"]["properties"]
    return properties


def kinds(node: dict[str, Any]) -> set[str]:
    """The JSON Schema kinds one property allows, one `anyOf` deep."""
    return {branch["type"] for branch in node.get("anyOf", [node]) if "type" in branch}


def test_every_key_the_reader_reads_is_a_key_the_run_record_writes() -> None:
    """A key the record stopped writing is a line the page silently stops reading."""
    keys = reader_keys(read_text(READER))
    assert set(keys) == set(TAKES), (
        f"{READER.name} reads {sorted(keys)}, and this check knows {sorted(TAKES)}"
    )

    properties = record_properties()
    missing = sorted(key for key in keys.values() if key not in properties)
    assert not missing, f"RunRecord writes no {', '.join(missing)}, which {READER.name} reads"


def test_each_key_holds_the_kind_of_value_the_reader_takes() -> None:
    """The half a name check cannot see: a line written as text reads as no line."""
    properties = record_properties()
    wrong = [
        f"  {key} holds {sorted(kinds(properties[key]))}, and the reader takes a {TAKES[role]}"
        for role, key in reader_keys(read_text(READER)).items()
        if key in properties and TAKES[role] not in kinds(properties[key])
    ]
    assert not wrong, "RunRecord changed what a key the reader reads holds:\n" + "\n".join(wrong)
