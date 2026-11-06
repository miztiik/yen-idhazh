"""Fail when the consumed host schema drifts in type, requiredness, nullability or vocabulary."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest
from summary_eval_pipeline.host_reader import HardwareRow, HonoServerReader, MachineUsage
from summary_evaluator_cases.contract_examples import REPOSITORY


def required_bun() -> str:
    bun = shutil.which("bun")
    dependency = REPOSITORY / "services" / "host-probes" / "node_modules" / "zod" / "package.json"
    if bun is None or not dependency.is_file():
        pytest.fail(
            "Prepare Bun and the existing locked host package with "
            "bun install --frozen-lockfile --cwd services/host-probes; "
            "host schema compatibility never skips missing preparation."
        )
    return bun


def bridge_path() -> Path:
    return Path(__file__).with_name("host-profile-bridge.ts")


def mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return cast(dict[str, object], value)


def resolve(node: object, root: dict[str, object]) -> dict[str, object]:
    value = mapping(node)
    while "$ref" in value:
        reference = value["$ref"]
        assert isinstance(reference, str) and reference.startswith("#/")
        current: object = root
        for part in reference[2:].split("/"):
            current = mapping(current)[part]
        value = mapping(current)
    return value


def variants(node: dict[str, object]) -> list[object] | None:
    kinds = node.get("type")
    if isinstance(kinds, list):
        return [{**node, "type": kind} for kind in kinds]
    value = node.get("oneOf", node.get("anyOf"))
    assert value is None or isinstance(value, list)
    return value


def literals(node: dict[str, object]) -> list[object] | None:
    if node.get("type") == "null":
        return [None]
    if "const" in node:
        return [node["const"]]
    value = node.get("enum")
    assert value is None or isinstance(value, list)
    return value


def branch_key(node: object, root: dict[str, object]) -> str:
    value = resolve(node, root)
    properties = mapping(value.get("properties", {}))
    for name in ("status", "reason"):
        if name in properties:
            field = resolve(properties[name], root)
            return name + json.dumps(literals(field) or field.get("type"), sort_keys=True)
    return str(value.get("type"))


def compare_projection(
    native_node: object,
    reader_node: object,
    native_root: dict[str, object],
    reader_root: dict[str, object],
    path: str,
) -> None:
    native, reader = resolve(native_node, native_root), resolve(reader_node, reader_root)
    native_union, reader_union = variants(native), variants(reader)
    if reader_union is not None:
        assert native_union is not None, path
        native_branches = {branch_key(item, native_root): item for item in native_union}
        reader_branches = {branch_key(item, reader_root): item for item in reader_union}
        assert native_branches.keys() == reader_branches.keys(), path
        for key, branch in reader_branches.items():
            compare_projection(native_branches[key], branch, native_root, reader_root, path + key)
        return
    assert native_union is None, path
    assert native.get("type") == reader.get("type"), path
    assert literals(native) == literals(reader), path
    if reader.get("type") == "object":
        native_properties = mapping(native.get("properties", {}))
        reader_properties = mapping(reader.get("properties", {}))
        native_required, reader_required = native.get("required", []), reader.get("required", [])
        assert isinstance(native_required, list) and isinstance(reader_required, list)
        for name, child in reader_properties.items():
            assert name in native_properties, path + "." + name
            assert (name in native_required) == (name in reader_required), path + "." + name
            compare_projection(
                native_properties[name], child, native_root, reader_root, path + "." + name
            )
        if "additionalProperties" in reader and isinstance(reader["additionalProperties"], dict):
            compare_projection(
                native["additionalProperties"],
                reader["additionalProperties"],
                native_root,
                reader_root,
                path + ".*",
            )
    elif reader.get("type") == "array":
        compare_projection(native["items"], reader["items"], native_root, reader_root, path + "[]")


def test_consumed_host_fields_match_actual_native_schemas() -> None:
    result = subprocess.run(
        [required_bun(), "run", "--no-install", str(bridge_path()), "schemas"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        "The native host schema export failed; prepare its locked dependencies. " + result.stderr
    )
    native = mapping(json.loads(result.stdout))
    for name, contract in (
        ("hardware", HardwareRow),
        ("machine", MachineUsage),
        ("server", HonoServerReader),
    ):
        native_schema = mapping(native[name])
        reader_schema: dict[str, object] = contract.model_json_schema()
        compare_projection(native_schema, reader_schema, native_schema, reader_schema, name)


@pytest.mark.parametrize("change", ["type", "required", "nullability", "vocabulary"])
def test_parity_check_rejects_each_consumed_shape_drift(change: str) -> None:
    reader: dict[str, object] = {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["complete", "failed"]}},
    }
    native = mapping(json.loads(json.dumps(reader)))
    if change == "required":
        native["required"] = []
    else:
        field = mapping(mapping(native["properties"])["status"])
        if change == "type":
            field["type"] = "integer"
        elif change == "nullability":
            mapping(native["properties"])["status"] = {
                "anyOf": [dict(field), {"type": "null"}],
            }
        else:
            field["enum"] = ["complete", "partial", "failed"]
    with pytest.raises(AssertionError):
        compare_projection(native, reader, native, reader, "status")
