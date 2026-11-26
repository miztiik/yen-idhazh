"""Does the native host fixture retain the authoritative row's columns and types?"""

from __future__ import annotations

import json
from typing import Any, Final

import pytest
from pydantic import ValidationError
from support.paths import REPO_ROOT, read_text

from idhazh.contracts.host_fingerprint import (
    HOST_HARDWARE_VERSION,
    HostFingerprintRow,
    HostHardwareRow,
)
from idhazh.ledger.arrow_schema import ColumnType, columns_of

pytestmark = pytest.mark.contract

_REMOVED: Final = {"job_seconds", "model_load_ms", "server_prompt_tokens", "server_prompt_seconds"}


def _snapshot() -> dict[str, Any]:
    snapshot: object = json.loads(read_text(
        REPO_ROOT / "tests" / "fixtures" / "host-fingerprints" / "host-schema.json"
    ))
    assert isinstance(snapshot, dict)
    return snapshot


def test_native_host_snapshot_matches_the_authoritative_contract() -> None:
    snapshot = _snapshot()
    columns = columns_of(HostFingerprintRow)
    assert all(isinstance(column.type, ColumnType) for column in columns)
    assert list(snapshot["columns"].items()) == [
        (column.name, str(column.type)) for column in columns
    ]
    assert snapshot["required"] == [column.name for column in columns if not column.nullable]
    assert snapshot["row"]["version"] == HostFingerprintRow.schema_version()
    row = HostFingerprintRow.model_validate(snapshot["row"])
    assert row.model_dump(mode="json") == snapshot["row"]


def test_current_capture_keeps_native_hardware_and_requires_its_own_dated_shape() -> None:
    snapshot = _snapshot()
    record = snapshot["row"]
    hardware = (
        {key: value for key, value in record.items() if key not in _REMOVED}
        | {"version": HOST_HARDWARE_VERSION, "job": "record-hardware"}
    )
    captured = HostHardwareRow.model_validate(hardware)
    assert captured.model_dump(mode="json") == hardware
    assert captured.fingerprint == record["fingerprint"]
    assert [(column.name, str(column.type)) for column in columns_of(HostHardwareRow)] == [
        (name, type_) for name, type_ in snapshot["columns"].items() if name not in _REMOVED
    ]
    for field in ("version", "pipeline_name", "task_name"):
        with pytest.raises(ValidationError, match=field):
            HostHardwareRow.model_validate({k: v for k, v in hardware.items() if k != field})
    for field in _REMOVED:
        with pytest.raises(ValidationError, match=field):
            HostHardwareRow.model_validate({**hardware, field: None})
    with pytest.raises(ValidationError, match="version"):
        HostHardwareRow.model_validate({**hardware, "version": record["version"]})
    with pytest.raises(ValidationError, match="shard"):
        HostHardwareRow.model_validate({**hardware, "shard": str(hardware["shard"])})

    normalized = HostFingerprintRow.model_validate({**hardware, "job": None})
    assert HostFingerprintRow.from_csv_row(normalized.csv_row()) == normalized
