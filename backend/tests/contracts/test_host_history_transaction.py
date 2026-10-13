"""Do generated history transactions preserve their exact binding and recovery phases?"""

from __future__ import annotations

import hashlib
import json
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from idhazh.contracts.base import Contract
from idhazh.contracts.host_history_transaction import (
    JOURNAL_VERSION,
    HistoryApplyApproval,
    HistoryMaintenanceOwner,
    HistoryTransactionEvent,
    HistoryTransactionPlan,
)
from idhazh.contracts.host_migration import HistorySource
from idhazh.telemetry.host_history_apply import (
    _ApplyBatch,
    _event_bytes,
    _Replacement,
    _transaction_plan,
)

pytestmark = pytest.mark.contract

CONTRACTS = (
    HistoryTransactionPlan,
    HistoryTransactionEvent,
    HistoryApplyApproval,
    HistoryMaintenanceOwner,
)
FILE_PHASES = ("planned", "replaced", "verified", "restored", "rollback-verified")
GLOBAL_PHASES = (
    "plan-created",
    "evidence-verified",
    "backups-verified",
    "staged-verified",
    "reconciled",
    "complete",
    "rollback-started",
    "rolled-back",
)
FILE_FIELDS = ("index", "path", "old_sha256", "new_sha256")


@pytest.fixture
def batch() -> _ApplyBatch:
    manifest_hash = hashlib.sha256(b"generated manifest").hexdigest()
    scope_hash = hashlib.sha256(b"generated scope").hexdigest()
    report_hash = hashlib.sha256(b"generated report").hexdigest()
    transaction_id = hashlib.sha256(
        f"{manifest_hash}\0{scope_hash}\0{report_hash}".encode("ascii")
    ).hexdigest()
    return _ApplyBatch(
        manifest=None,
        report=None,
        manifest_sha256=manifest_hash,
        scope_hash=scope_hash,
        report_evidence_hash=report_hash,
        transaction_id=transaction_id,
        transaction_root=f"backend/var/generated/d17-transactions/{transaction_id}",
        replacements=(
            _Replacement(
                path="generated/raw/day.json",
                kind="raw",
                old_sha256=hashlib.sha256(b"old row").hexdigest(),
                old_bytes=len(b"old row"),
                new_bytes=b'{"row":"corrected"}\n',
            ),
            _Replacement(
                path="generated/view.json",
                kind="view",
                old_sha256=hashlib.sha256(b"old view").hexdigest(),
                old_bytes=len(b"old view"),
                new_bytes=b'{"view":"corrected"}\n',
            ),
        ),
        evidence={"manifest.json": b"generated manifest", "report.json": b"generated report"},
    )


def dated_document(data: bytes) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(data)
    document["version"] = JOURNAL_VERSION
    return document


def plan_document(batch: _ApplyBatch) -> dict[str, Any]:
    staged_bytes = sum(len(item.new_bytes) for item in batch.replacements)
    evidence_bytes = sum(len(data) for data in batch.evidence.values())
    return dated_document(
        _transaction_plan(
            batch,
            max_files=len(batch.replacements),
            max_bytes=staged_bytes + evidence_bytes,
        )
    )


def document_for(contract: type[Contract], batch: _ApplyBatch) -> dict[str, Any]:
    if contract is HistoryTransactionPlan:
        return plan_document(batch)
    if contract is HistoryTransactionEvent:
        return dated_document(_event_bytes(batch, "plan-created"))
    binding = {
        "version": JOURNAL_VERSION,
        "manifest_sha256": batch.manifest_sha256,
        "scope_hash": batch.scope_hash,
        "report_evidence_hash": batch.report_evidence_hash,
        "target_device": 0,
        "target_inode": 0,
    }
    if contract is HistoryApplyApproval:
        return binding | {
            "authority": "unattended_user",
            "authorized_at": "2026-10-13T12:00:00Z",
            "d16_revision": "a" * 40,
            "d7_revision": "b" * 40,
        }
    if contract is HistoryMaintenanceOwner:
        return binding | {
            "nonce": "acb17836-ad03-4dca-b44c-438ef5982d12",
            "pid": 1,
            "process_created_at": "2026-10-13T11:59:00Z",
            "git_head": "c" * 40,
            "git_index_sha256": None,
        }
    raise ValueError("no generated fixture for this contract")


@pytest.mark.parametrize("contract", CONTRACTS)
def test_generated_document_round_trip_and_dated_schema(
    contract: type[Contract], batch: _ApplyBatch
) -> None:
    document = document_for(contract, batch)
    model = contract.model_validate_json(json.dumps(document))
    assert model.model_dump(mode="json") == document
    assert contract.from_json(model.to_json()) == model
    schema = contract.json_schema()
    assert schema["properties"].keys() == document.keys()
    assert schema["$id"] == contract.schema_filename()
    assert schema["version"] == schema["changelog"][0]["version"] == JOURNAL_VERSION
    assert schema["properties"]["version"]["const"] == JOURNAL_VERSION
    assert schema["additionalProperties"] is False
    assert schema["changelog"][0]["change"] and schema["changelog"][0]["why"]
    with pytest.raises(ValidationError, match="frozen_instance"):
        model.version = JOURNAL_VERSION


def test_plan_keeps_serializer_fields_and_declared_source_kinds(batch: _ApplyBatch) -> None:
    document = plan_document(batch)
    plan = HistoryTransactionPlan.model_validate_json(json.dumps(document))
    assert isinstance(plan.files, tuple)
    assert isinstance(plan.evidence, tuple)
    assert set(type(plan.files[0]).model_fields) == set(document["files"][0])
    assert set(type(plan.evidence[0]).model_fields) == set(document["evidence"][0])
    schema = HistoryTransactionPlan.json_schema()
    file_schema = schema["$defs"]["HistoryTransactionFile"]
    assert file_schema["properties"]["kind"]["enum"] == list(
        get_args(HistorySource.model_fields["kind"].annotation)
    )
    assert file_schema["additionalProperties"] is False
    assert schema["$defs"]["HistoryTransactionEvidence"]["additionalProperties"] is False
    for nested in (plan.files[0], plan.evidence[0]):
        with pytest.raises(ValidationError, match="frozen_instance"):
            nested.path = nested.path


def test_contract_does_not_invent_caller_budgets(batch: _ApplyBatch) -> None:
    document = plan_document(batch)
    document["files"] = []
    document["evidence"] = []
    plan = HistoryTransactionPlan.model_validate_json(json.dumps(document))
    assert plan.files == ()
    assert plan.evidence == ()
    document = plan_document(batch)
    document["files"][0]["old_bytes"] = 2**64
    document["files"][0]["new_bytes"] = 2**64
    HistoryTransactionPlan.model_validate_json(json.dumps(document))
    for name in ("files", "evidence"):
        schema = HistoryTransactionPlan.json_schema()["properties"][name]
        assert "minItems" not in schema and "maxItems" not in schema


@pytest.mark.parametrize("phase", (*GLOBAL_PHASES, *FILE_PHASES))
def test_every_serializer_phase_has_the_exact_shape(phase: str, batch: _ApplyBatch) -> None:
    index = 0 if phase in FILE_PHASES else None
    document = dated_document(_event_bytes(batch, phase, index))
    event = HistoryTransactionEvent.model_validate_json(json.dumps(document))
    assert event.model_dump(mode="json") == document
    assert event.index == index


@pytest.mark.parametrize("contract", (HistoryTransactionPlan, HistoryTransactionEvent))
@pytest.mark.parametrize(
    "field", ("transaction_id", "manifest_sha256", "scope_hash", "report_evidence_hash")
)
def test_changed_transaction_binding_is_refused(
    contract: type[Contract], field: str, batch: _ApplyBatch
) -> None:
    document = document_for(contract, batch)
    document[field] = "0" * 64
    with pytest.raises(ValidationError, match="does not bind"):
        contract.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("contract", CONTRACTS)
@pytest.mark.parametrize("version", (1, "2026-10-12", "2099-01-01"))
def test_unsupported_version_is_refused(
    contract: type[Contract], version: object, batch: _ApplyBatch
) -> None:
    document = document_for(contract, batch)
    document["version"] = version
    with pytest.raises(ValidationError):
        contract.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("fault", ("start", "gap", "duplicate", "order"))
def test_noncontiguous_file_indexes_are_refused(fault: str, batch: _ApplyBatch) -> None:
    document = plan_document(batch)
    if fault == "start":
        document["files"][0]["index"] = 1
    elif fault == "gap":
        document["files"][1]["index"] = 2
    elif fault == "duplicate":
        document["files"][1]["index"] = 0
    else:
        document["files"].reverse()
    with pytest.raises(ValidationError, match="contiguous from zero"):
        HistoryTransactionPlan.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("collection", ("files", "evidence"))
def test_duplicate_paths_are_refused(collection: str, batch: _ApplyBatch) -> None:
    document = plan_document(batch)
    document[collection][1]["path"] = document[collection][0]["path"]
    with pytest.raises(ValidationError, match="repeats"):
        HistoryTransactionPlan.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("field", ("kind", "old_sha256", "new_sha256"))
def test_undeclared_kind_and_invalid_file_hashes_are_refused(field: str, batch: _ApplyBatch) -> None:
    document = plan_document(batch)
    document["files"][0][field] = "unknown"
    with pytest.raises(ValidationError):
        HistoryTransactionPlan.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("location", ("path", "backup", "stage", "evidence", "event"))
@pytest.mark.parametrize(
    "path", ("../state", "C:/state", "/state", "state\\raw", "state//raw", "state/./raw")
)
def test_nonportable_paths_are_refused(location: str, path: str, batch: _ApplyBatch) -> None:
    contract: type[Contract] = HistoryTransactionPlan
    document = plan_document(batch)
    if location == "event":
        contract = HistoryTransactionEvent
        document = dated_document(_event_bytes(batch, "planned", 0))
        document["path"] = path
    elif location == "evidence":
        document["evidence"][0]["path"] = path
    else:
        document["files"][0][location] = path
    with pytest.raises(ValidationError):
        contract.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("phase", FILE_PHASES)
@pytest.mark.parametrize("field", FILE_FIELDS)
def test_per_file_phase_requires_all_file_fields(
    phase: str, field: str, batch: _ApplyBatch
) -> None:
    document = dated_document(_event_bytes(batch, phase, 0))
    del document[field]
    with pytest.raises(ValidationError, match="per-file phase requires"):
        HistoryTransactionEvent.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("phase", GLOBAL_PHASES)
def test_global_phase_forbids_file_fields(phase: str, batch: _ApplyBatch) -> None:
    document = dated_document(_event_bytes(batch, "planned", 0))
    document["phase"] = phase
    with pytest.raises(ValidationError, match="global phase forbids"):
        HistoryTransactionEvent.model_validate_json(json.dumps(document))


def test_partial_global_file_fields_and_unknown_phase_are_refused(batch: _ApplyBatch) -> None:
    for field in FILE_FIELDS:
        document = dated_document(_event_bytes(batch, "planned", 0))
        document = {
            name: value
            for name, value in document.items()
            if name not in FILE_FIELDS or name == field
        }
        document["phase"] = "complete"
        with pytest.raises(ValidationError, match="global phase forbids"):
            HistoryTransactionEvent.model_validate_json(json.dumps(document))
    document = dated_document(_event_bytes(batch, "plan-created"))
    document["phase"] = "unknown"
    with pytest.raises(ValidationError):
        HistoryTransactionEvent.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("value", (True, 1.0, "1", -1))
def test_counts_and_target_identity_are_strict_nonnegative(
    value: object, batch: _ApplyBatch
) -> None:
    for field in ("index", "old_bytes", "new_bytes"):
        document = plan_document(batch)
        document["files"][0][field] = value
        with pytest.raises(ValidationError):
            HistoryTransactionPlan.model_validate_json(json.dumps(document))
    document = plan_document(batch)
    document["evidence"][0]["bytes"] = value
    with pytest.raises(ValidationError):
        HistoryTransactionPlan.model_validate_json(json.dumps(document))
    document = dated_document(_event_bytes(batch, "planned", 0))
    document["index"] = value
    with pytest.raises(ValidationError):
        HistoryTransactionEvent.model_validate_json(json.dumps(document))
    for contract in (HistoryApplyApproval, HistoryMaintenanceOwner):
        for field in ("target_device", "target_inode"):
            document = document_for(contract, batch)
            document[field] = value
            with pytest.raises(ValidationError):
                contract.model_validate_json(json.dumps(document))


@pytest.mark.parametrize(
    ("contract", "field", "value"),
    (
        (HistoryApplyApproval, "authority", "signed_issuer"),
        (HistoryApplyApproval, "authorized_at", "2026-10-13T12:00:00+00:00"),
        (HistoryApplyApproval, "d16_revision", "a" * 39),
        (HistoryApplyApproval, "d7_revision", "main"),
        (HistoryMaintenanceOwner, "nonce", "not-a-uuid"),
        (HistoryMaintenanceOwner, "pid", 0),
        (HistoryMaintenanceOwner, "pid", True),
        (HistoryMaintenanceOwner, "pid", "1"),
        (HistoryMaintenanceOwner, "pid", 1.0),
        (HistoryMaintenanceOwner, "process_created_at", "2026-10-13T12:00:00"),
        (HistoryMaintenanceOwner, "git_head", "main"),
        (HistoryMaintenanceOwner, "git_index_sha256", "bad-hash"),
    ),
)
def test_invalid_approval_and_owner_fields_are_refused(
    contract: type[Contract], field: str, value: object, batch: _ApplyBatch
) -> None:
    document = document_for(contract, batch)
    document[field] = value
    with pytest.raises(ValidationError):
        contract.model_validate_json(json.dumps(document))


def test_owner_accepts_present_and_missing_git_index(batch: _ApplyBatch) -> None:
    for index_hash in (None, hashlib.sha256(b"generated git index").hexdigest()):
        document = document_for(HistoryMaintenanceOwner, batch)
        document["git_index_sha256"] = index_hash
        owner = HistoryMaintenanceOwner.model_validate_json(json.dumps(document))
        assert owner.git_index_sha256 == index_hash


@pytest.mark.parametrize("contract", CONTRACTS)
def test_unknown_document_fields_are_refused(contract: type[Contract], batch: _ApplyBatch) -> None:
    document = document_for(contract, batch) | {"extra": "not consumed"}
    with pytest.raises(ValidationError, match="extra_forbidden"):
        contract.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("collection", ("files", "evidence"))
def test_unknown_nested_fields_are_refused(collection: str, batch: _ApplyBatch) -> None:
    document = plan_document(batch)
    document[collection][0]["extra"] = "not consumed"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        HistoryTransactionPlan.model_validate_json(json.dumps(document))
