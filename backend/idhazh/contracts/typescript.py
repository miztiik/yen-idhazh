"""Generate the frontend's TypeScript contracts from the same models `schemas/` comes from.

One-way and never reversed, exactly like the schema exporter beside it. A type
the frontend trusts and a shape the backend writes cannot disagree once both are
emitted from one model, and CI regenerates both and fails on any diff - which is
what turns "no hand-written mirror" from an instruction into a control.

The input is the generated JSON Schema rather than the model, so the TypeScript
and the schema can never describe two different shapes. A closed vocabulary is
emitted twice over: once as a frozen array, which a reader can narrow a cell
against at run time, and once as the union that array's members form. Without
the array a consumer has to retype the members to check one, and a retyped
vocabulary is the drift this module exists to remove.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from idhazh.contracts.base import Contract

#: What a JSON Schema scalar becomes. Both JSON number kinds are one TypeScript
#: type, because JavaScript has one.
SCALARS: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
}

_DEF_PREFIX = "#/$defs/"


def _screaming(name: str) -> str:
    """`ServerJob` -> `SERVER_JOB`. The array's name, beside the union's."""
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", spaced).upper()


def _literal(value: Any) -> str:
    """One enum member or one `const`, as TypeScript writes it."""
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    return json.dumps(value)


def _union(parts: list[str]) -> str:
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    return " | ".join(seen) if seen else "unknown"


def ts_type(node: Any) -> str:
    """The TypeScript a schema node describes.

    An unrecognised node becomes `unknown` rather than `any`: a shape this
    emitter cannot read is one a consumer must narrow before using, and `any`
    would let it through silently.
    """
    if not isinstance(node, dict):
        return "unknown"
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith(_DEF_PREFIX):
        return ref[len(_DEF_PREFIX) :]
    if "const" in node:
        return _literal(node["const"])
    if isinstance(node.get("enum"), list):
        return _union([_literal(member) for member in node["enum"]])
    if isinstance(node.get("anyOf"), list):
        return _union([ts_type(member) for member in node["anyOf"]])
    kind = node.get("type")
    if kind == "array":
        inner = ts_type(node.get("items", {}))
        return f"({inner})[]" if "|" in inner else f"{inner}[]"
    if kind == "object":
        return _object_type(node)
    if isinstance(kind, str):
        return SCALARS.get(kind, "unknown")
    return "unknown"


def _object_type(node: dict[str, Any]) -> str:
    """An object node: a fixed shape, or a map whose keys are open."""
    properties = node.get("properties")
    if isinstance(properties, dict) and properties:
        required = set(node.get("required", []))
        cells = [
            f"{_key(name)}{'' if name in required else '?'}: {ts_type(shape)}"
            for name, shape in properties.items()
        ]
        return "{ " + "; ".join(cells) + " }"
    patterned = node.get("patternProperties")
    if isinstance(patterned, dict) and patterned:
        return f"Record<string, {_union([ts_type(shape) for shape in patterned.values()])}>"
    extra = node.get("additionalProperties")
    if isinstance(extra, dict):
        return f"Record<string, {ts_type(extra)}>"
    return "Record<string, unknown>"


_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def _key(name: str) -> str:
    return name if _IDENTIFIER.fullmatch(name) else json.dumps(name)


def _doc(description: Any, indent: str) -> list[str]:
    """One JSDoc block, or nothing where the schema said nothing.

    `*/` inside a description would close the block early, so it is broken up.
    Every line is right-stripped: a trailing space fails the whitespace gate.
    """
    if not isinstance(description, str) or not description.strip():
        return []
    body = description.replace("*/", "*\\/").split("\n")
    if len(body) == 1:
        return [f"{indent}/** {body[0].strip()} */"]
    lines = [f"{indent}/**"]
    lines += [f"{indent} * {line}".rstrip() for line in body]
    lines.append(f"{indent} */")
    return lines


def _interface(name: str, node: dict[str, Any]) -> list[str]:
    required = set(node.get("required", []))
    lines = _doc(node.get("description"), "")
    lines.append(f"export interface {name} {{")
    properties = node.get("properties", {})
    for index, (field, shape) in enumerate(properties.items()):
        if index:
            lines.append("")
        lines += _doc(shape.get("description"), "\t")
        mark = "" if field in required else "?"
        lines.append(f"\t{_key(field)}{mark}: {ts_type(shape)};")
    lines.append("}")
    return lines


def _vocabulary(name: str, node: dict[str, Any]) -> list[str]:
    """A closed set, as the array a reader narrows with and the union it forms."""
    members = ", ".join(_literal(member) for member in node["enum"])
    array = _screaming(name)
    lines = _doc(node.get("description"), "")
    lines.append(f"export const {array} = [{members}] as const;")
    lines.append("")
    lines.append(f"export type {name} = (typeof {array})[number];")
    return lines


def _definition(name: str, node: dict[str, Any]) -> list[str]:
    if isinstance(node.get("enum"), list):
        return _vocabulary(name, node)
    if isinstance(node.get("properties"), dict) and node["properties"]:
        return _interface(name, node)
    return [*_doc(node.get("description"), ""), f"export type {name} = {ts_type(node)};"]


def module_filename(contract: type[Contract]) -> str:
    return f"{contract.__schema_stem__}.ts"


def module_text(contract: type[Contract]) -> str:
    """One contract's TypeScript, LF and ASCII, ready to be written."""
    schema = contract.json_schema()
    source = contract.__module__.replace(".", "/")
    lines = [
        f"// Generated from `backend/{source}.py` by `python -m idhazh.contracts.export`.",
        "// Never hand-edited: the drift gate regenerates it and fails on any diff",
        "// (CLAUDE.md section 1a). Edit the Pydantic model instead.",
        "",
    ]
    for name in sorted(schema.get("$defs", {})):
        lines += _definition(name, schema["$defs"][name])
        lines.append("")
    lines += _interface(contract.__name__, schema)
    return "\n".join(lines) + "\n"


def export(contracts: tuple[type[Contract], ...], target: Path) -> list[Path]:
    """Write one module per contract. LF regardless of the host's line endings."""
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for contract in contracts:
        path = target / module_filename(contract)
        path.write_text(module_text(contract), encoding="utf-8", newline="\n")
        written.append(path)
    return written
