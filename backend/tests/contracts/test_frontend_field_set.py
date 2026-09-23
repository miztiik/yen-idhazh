"""Does the frontend's hand-written host-fingerprint row still name the contract's columns?

`frontend/src/lib/server/host-fingerprint.ts` types the machine record by hand,
because a generator that ran on every contract change served six names in two
files. This is half the control that replaces it: the field set AND the type of
each field, so a column copied as `string` that the model declares a number
fails here rather than reaching a chart as a string somebody sorts
alphabetically.

The expected types are computed from `HostFingerprintRow.json_schema()` by the
narrow mapper below, which covers the node kinds this one row uses and refuses
every other kind by name. A field declared with a shape the mapper has not met
fails this test instead of passing it - which is what stops the mapper quietly
becoming the thing it is checking.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.host_fingerprint import HostFingerprintRow

pytestmark = pytest.mark.contract

READER: Final[Path] = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "host-fingerprint.ts"

#: What a JSON Schema scalar becomes. Both JSON number kinds are one TypeScript
#: type, because JavaScript has one.
SCALARS: Final[dict[str, str]] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
}

_DEF_PREFIX: Final = "#/$defs/"
_CELL = re.compile(r"^\t(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<mark>\??): (?P<type>[^;]+);$")


def ts_type(node: dict[str, Any]) -> str:
    """The TypeScript one schema node describes, for the kinds this row uses."""
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith(_DEF_PREFIX):
        return ref[len(_DEF_PREFIX) :]
    branches = node.get("anyOf")
    if isinstance(branches, list):
        parts: list[str] = []
        for branch in branches:
            part = ts_type(branch)
            if part not in parts:
                parts.append(part)
        return " | ".join(parts)
    kind = node.get("type")
    if isinstance(kind, str) and kind in SCALARS:
        return SCALARS[kind]
    raise AssertionError(
        f"this check cannot read the schema node {node!r}. It covers a $ref, an anyOf "
        f"and the scalars {sorted(SCALARS)}; widen it in the same change that adds the "
        "field, or the frontend copy is unchecked for that column."
    )


def contract_cells() -> dict[str, str]:
    """Each column of the Pydantic row, as the TypeScript line that states it."""
    schema = HostFingerprintRow.json_schema()
    required = set(schema.get("required", []))
    return {
        name: f"{name}{'' if name in required else '?'}: {ts_type(node)}"
        for name, node in schema["properties"].items()
    }


def reader_cells(text: str) -> dict[str, str]:
    """Each column the frontend's own `HostFingerprintRow` declares."""
    _, opened, rest = text.partition("export interface HostFingerprintRow {\n")
    assert opened, f"{READER.name} no longer declares a HostFingerprintRow interface"
    body, closed, _ = rest.partition("\n}")
    assert closed, f"{READER.name} leaves HostFingerprintRow unclosed"
    cells: dict[str, str] = {}
    for line in body.split("\n"):
        found = _CELL.match(line)
        assert found, f"{READER.name} declares a cell this check cannot read: {line!r}"
        cells[found["name"]] = f"{found['name']}{found['mark']}: {found['type']}"
    return cells


def test_the_frontend_row_names_every_column_the_contract_declares() -> None:
    """No more, no fewer: a column added to the model is a column the page gains."""
    theirs = reader_cells(read_text(READER))
    ours = contract_cells()

    missing = sorted(set(ours) - set(theirs))
    extra = sorted(set(theirs) - set(ours))
    assert not missing, f"{READER.name} never copied: {', '.join(missing)}"
    assert not extra, f"{READER.name} names columns the contract does not declare: {extra}"


def test_the_frontend_row_copies_every_column_with_the_contract_s_type() -> None:
    """The half a field-name check cannot see: `string` where the model says number."""
    theirs = reader_cells(read_text(READER))
    ours = contract_cells()

    wrong = [
        f"  the page says `{theirs[name]}`, the contract says `{stated}`"
        for name, stated in ours.items()
        if name in theirs and theirs[name] != stated
    ]
    assert not wrong, f"{READER.name} copied a column with the wrong type:\n" + "\n".join(wrong)


def test_the_columns_are_copied_in_the_contract_s_own_order() -> None:
    """Two lists that read the same top to bottom are two lists a person can diff."""
    assert list(reader_cells(read_text(READER))) == list(contract_cells())
