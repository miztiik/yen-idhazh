"""Does the frontend's hand copy of the compact index still say what the contract says?

`frontend/src/lib/data/compact-index.ts` types `CompactEntry` and `CompactIndex`
by hand and carries the stamp it reads, because the query door runs in a browser
that cannot import a Pydantic model. This holds that copy in step: each shape's
field set, each field's TypeScript type and their order, the stamp against
`CompactIndex.schema_version()`, and the periods against `Period`. It also
holds three names the door carries beside the copy: every ledger it may query is
a `LedgerName`, the cell it filters days on is the ledger's own date cell, and
the four faults it names a missing file with are the backend's `LedgerFault`, in
the same order, so the gardener's logs say what the console says.

The expected types are computed from `CompactIndex.json_schema()` by the narrow
mapper below, which covers the node kinds these two shapes use and refuses every
other kind by name - so a field declared with a shape the mapper has not met
fails here rather than passing unchecked.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_fault import LedgerFault
from idhazh.contracts.ledger_index import CompactIndex, RawDayIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.keys import DATE_CELL

pytestmark = pytest.mark.contract

DOOR: Final[Path] = REPO_ROOT / "frontend" / "src" / "lib" / "data"
COPY: Final[Path] = DOOR / "compact-index.ts"

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
    """The TypeScript one schema node describes, for the kinds these shapes use."""
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith(_DEF_PREFIX):
        return ref[len(_DEF_PREFIX) :]
    for key in ("anyOf", "allOf"):
        branches = node.get(key)
        if isinstance(branches, list):
            parts: list[str] = []
            for branch in branches:
                part = ts_type(branch)
                if part not in parts:
                    parts.append(part)
            return " | ".join(parts)
    kind = node.get("type")
    if kind == "array" and isinstance(node.get("items"), dict):
        return f"{ts_type(node['items'])}[]"
    if isinstance(kind, str) and kind in SCALARS:
        return SCALARS[kind]
    raise AssertionError(
        f"this check cannot read the schema node {node!r}. It covers a $ref, an anyOf, an "
        f"array and the scalars {sorted(SCALARS)}; widen it in the same change that adds "
        "the field, or the frontend copy is unchecked for that field."
    )


def contract_cells(schema: dict[str, Any]) -> dict[str, str]:
    """Each field of one schema object, as the TypeScript line that states it."""
    required = set(schema.get("required", []))
    return {
        name: f"{name}{'' if name in required else '?'}: {ts_type(node)}"
        for name, node in schema["properties"].items()
    }


def copied_cells(text: str, interface: str) -> dict[str, str]:
    """Each field one hand-written TypeScript interface declares."""
    _, opened, rest = text.partition(f"export interface {interface} {{\n")
    assert opened, f"{COPY.name} no longer declares an interface {interface}"
    body, closed, _ = rest.partition("\n}")
    assert closed, f"{COPY.name} leaves {interface} unclosed"
    cells: dict[str, str] = {}
    for line in body.split("\n"):
        found = _CELL.match(line)
        assert found, f"{COPY.name} declares a field this check cannot read: {line!r}"
        cells[found["name"]] = f"{found['name']}{found['mark']}: {found['type']}"
    return cells


def constant(text: str, name: str, where: Path) -> str:
    """The single-quoted value of one exported TypeScript string constant."""
    found = re.search(rf"^export const {name} = '([^']*)';$", text, re.MULTILINE)
    assert found, f"{where.name} no longer exports {name} as one quoted string"
    return found[1]


def constant_list(text: str, name: str, where: Path) -> list[str]:
    """The values of one exported TypeScript list of quoted strings, in order."""
    found = re.search(rf"^export const {name} = \[([^\]]*)\] as const;$", text, re.MULTILINE)
    assert found, f"{where.name} no longer exports {name} as a list of quoted strings"
    return re.findall(r"'([^']*)'", found[1])


def schemas() -> dict[str, dict[str, Any]]:
    """The two shapes' schemas, the entry read out of the index's own definitions."""
    index = CompactIndex.json_schema()
    return {"CompactIndex": index, "CompactEntry": index["$defs"]["CompactEntry"]}


@pytest.mark.parametrize("interface", ["CompactIndex", "CompactEntry"])
def test_the_copy_names_every_field_with_the_contract_s_type_in_its_order(interface: str) -> None:
    """No field more, none fewer, none retyped, none moved."""
    theirs = copied_cells(read_text(COPY), interface)
    ours = contract_cells(schemas()[interface])
    assert list(theirs.items()) == list(ours.items()), (
        f"{COPY.name} copies {interface} as {list(theirs.values())}, "
        f"and the contract declares {list(ours.values())}"
    )


def test_the_stamp_the_door_reads_is_the_one_the_contract_declares() -> None:
    """A stamp one day behind would refuse every index the gardener writes as newer."""
    stamp = constant(read_text(COPY), "COMPACT_INDEX_STAMP", COPY)
    assert stamp == CompactIndex.schema_version(), (
        f"{COPY.name} reads compact indexes stamped {stamp} or older, and the contract is at "
        f"{CompactIndex.schema_version()}"
    )


def test_the_periods_are_the_contract_s_own() -> None:
    """A period is also a directory name, so a misspelt one addresses nothing."""
    assert constant_list(read_text(COPY), "COMPACT_PERIODS", COPY) == [p.value for p in Period]


def test_every_ledger_the_door_may_query_is_a_ledger() -> None:
    """The written-question door names every declared ledger, and no other."""
    shapes = DOOR / "slice-shapes.ts"
    names = constant_list(read_text(shapes), "LEDGER_NAMES", shapes)
    expected = [ledger.value for ledger in LedgerName]
    assert names == expected, f"{shapes.name} names {names}, and LedgerName declares {expected}"


def test_the_raw_day_index_copy_names_the_contract_fields_and_requires_bytes() -> None:
    """The browser copy requires bytes because the site build fills them before it stages a listing."""
    copy = DOOR / "raw-day-index.ts"
    fields = copied_cells(read_text(copy), "RawDayIndex")
    schema = contract_cells(RawDayIndex.json_schema())
    assert fields["bytes"] == "bytes: number[]"
    assert set(fields) == set(schema)
    assert constant(read_text(copy), "RAW_DAY_INDEX_STAMP", copy) == RawDayIndex.schema_version()


def test_the_door_filters_days_on_the_ledger_s_own_date_cell() -> None:
    """Every compacted row carries its UTC day in one cell, and the door filters on that cell."""
    query = DOOR / "slice-query.ts"
    assert constant(read_text(query), "DATE_COLUMN", query) == DATE_CELL


def test_the_four_missing_file_faults_are_one_list_on_both_sides() -> None:
    """The door names a missing file with these words, and the gardener's logs with the same."""
    shapes = DOOR / "slice-shapes.ts"
    names = constant_list(read_text(shapes), "LEDGER_FAULTS", shapes)
    assert names == [fault.value for fault in LedgerFault], (
        f"{shapes.name} names the faults {names} and LedgerFault in "
        f"backend/idhazh/contracts/ledger_fault.py names {[fault.value for fault in LedgerFault]}"
    )
