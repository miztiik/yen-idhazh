"""Do the native TypeScript copies still match the Python-owned contracts?"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, cast

import pytest
from pydantic import ValidationError
from support.paths import REPO_ROOT

pytestmark = pytest.mark.contract


@pytest.fixture(scope="module")
def typescript_schemas() -> dict[str, Any]:
    bun = shutil.which("bun")
    assert bun, "Install Bun to run the native contract binding gate"
    completed = subprocess.run(
        [bun, "run", "test/schema-binding.ts"],
        cwd=REPO_ROOT / "packages" / "common-contracts",
        text=True,
        capture_output=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(completed.stdout))


def normalized_shape(node: dict[str, Any], root: dict[str, Any]) -> Any:
    """Compare actual types, required keys, defaults and vocabularies recursively."""
    if "$ref" in node:
        ref = node["$ref"]
        assert ref.startswith("#/"), f"Unexpected external reference: {ref}"
        target = root
        for key in ref[2:].split("/"):
            target = target[key]
        return normalized_shape(target, root)
    if "const" in node:
        return ("enum", (json.dumps(node["const"]),), node.get("default", "<required>"))
    if "enum" in node:
        return (
            "enum",
            tuple(sorted(json.dumps(value) for value in node["enum"])),
            node.get("default", "<required>"),
        )
    branches = node.get("anyOf", node.get("oneOf"))
    if branches is not None:
        return (
            "union",
            tuple(sorted((normalized_shape(branch, root) for branch in branches), key=repr)),
            node.get("default", "<required>"),
        )
    kind = node.get("type")
    if isinstance(kind, list):
        return normalized_shape(
            {
                "anyOf": [{"type": value} for value in kind],
                **{key: value for key, value in node.items() if key != "type"},
            },
            root,
        )
    if kind == "object":
        if "patternProperties" in node:
            patterns = node["patternProperties"]
            if len(patterns) == 1:
                pattern, value = next(iter(patterns.items()))
                return ("record", pattern, normalized_shape(value, root), node.get("default", "<required>"))
            return (
                "record",
                tuple(sorted((pattern, normalized_shape(value, root)) for pattern, value in patterns.items())),
                node.get("additionalProperties", False),
                node.get("default", "<required>"),
            )
        if "properties" not in node and isinstance(node.get("additionalProperties"), dict):
            return (
                "record",
                node.get("propertyNames", {}).get("pattern"),
                normalized_shape(node["additionalProperties"], root),
                node.get("default", "<required>"),
            )
        assert node.get("additionalProperties") is False, "Objects must reject unknown fields"
        required = set(node.get("required", []))
        return (
            "object",
            {
                name: (name in required, normalized_shape(child, root))
                for name, child in node["properties"].items()
            },
            node.get("default", "<required>"),
        )
    if kind == "array":
        return ("array", normalized_shape(node["items"], root), node.get("default", "<required>"))
    assert kind in {"string", "integer", "number", "boolean", "null"}, node
    return (kind, node.get("default", "<required>"))


def test_native_typescript_shapes_match_the_python_owned_contracts(
    typescript_schemas: dict[str, Any],
) -> None:
    from idhazh.contracts import file_envelope
    from idhazh.contracts.feed_health import FeedHealthRow
    from idhazh.contracts.publication_inventory import PublicationEntry, PublicationInventory

    with pytest.raises(
        ValidationError,
        match="curated publisher identity requires its declared contract version",
    ):
        FeedHealthRow.model_validate({"version": "2026-10-23T18:50", "publisher_id": "recorded-publication"})

    native_schemas = {
        "FileEnvelope": file_envelope.FileEnvelope.json_schema(),
        "WriterIdentity": file_envelope.WriterIdentity.model_json_schema(),
        "RowIdentity": file_envelope.RowIdentity.model_json_schema(),
        "FeedHealthRow": FeedHealthRow.json_schema(),
    }
    for name, native in native_schemas.items():
        typescript = typescript_schemas[name]
        assert normalized_shape(typescript, typescript) == normalized_shape(native, native)

    assert typescript_schemas["__footer_keys"] == list(file_envelope._KEYS)
    assert set(typescript_schemas["__optional_footer_keys"]) == file_envelope._OPTIONAL_KEYS
    versions = typescript_schemas["__envelope_versions"]
    assert len(versions) == len(set(versions))
    assert set(versions) == set(file_envelope._ENVELOPE_VERSIONS)
    assert typescript_schemas["__file_envelope_version"] == file_envelope.FileEnvelope.schema_version()
    assert typescript_schemas["__row_identity_column_versions"] == dict(
        file_envelope.RowIdentity.__column_versions__
    )

    projections = typescript_schemas["__publication_inputs"]
    entry = PublicationEntry.model_json_schema()
    assert normalized_shape(projections["PublicationEntry"], projections["PublicationEntry"]) == normalized_shape(
        entry, entry
    )
    native_inventory = PublicationInventory.json_schema()
    projected_inventory = projections["PublicationInventory"]
    assert (
        typescript_schemas["__publication_input_versions"]["PublicationInventory"]
        == PublicationInventory.schema_version()
    )
    assert set(projected_inventory["properties"]) == {"version", "entries"}
    for name in projected_inventory["properties"]:
        native_field = native_inventory["properties"][name]
        typescript_field = projected_inventory["properties"][name]
        assert normalized_shape(
            {key: value for key, value in typescript_field.items() if key != "default"},
            projected_inventory,
        ) == normalized_shape(
            {key: value for key, value in native_field.items() if key != "default"},
            native_inventory,
        )
