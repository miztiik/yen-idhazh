"""Does the native host fixture retain the authoritative row's columns and types?"""

from __future__ import annotations

import json

import pytest
from support.paths import REPO_ROOT, read_text

from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.ledger.arrow_schema import ColumnType, columns_of

pytestmark = pytest.mark.contract


def test_native_host_snapshot_matches_the_authoritative_contract() -> None:
    snapshot = json.loads(read_text(
        REPO_ROOT / "tests" / "fixtures" / "host-fingerprints" / "host-schema.json"
    ))
    columns = columns_of(HostFingerprintRow)
    assert all(isinstance(column.type, ColumnType) for column in columns)
    assert list(snapshot["columns"].items()) == [
        (column.name, str(column.type)) for column in columns
    ]
    assert snapshot["required"] == [column.name for column in columns if not column.nullable]
    assert snapshot["row"]["version"] == HostFingerprintRow.schema_version()
    row = HostFingerprintRow.model_validate(snapshot["row"])
    assert row.model_dump(mode="json") == snapshot["row"]
