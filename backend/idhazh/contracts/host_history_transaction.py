"""What exact history replacement, approval and maintenance owner may a later run read?"""

from __future__ import annotations

import hashlib
from typing import ClassVar, Final, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from idhazh.contracts.base import ChangelogEntry, CommitSha, Contract, RelPath, Sha256, Timestamp
from idhazh.contracts.host_migration import HistoryModel, Nonnegative, Positive

__all__ = [
    "JOURNAL_VERSION",
    "HistoryApplyApproval",
    "HistoryMaintenanceOwner",
    "HistoryTransactionEvent",
    "HistoryTransactionEvidence",
    "HistoryTransactionFile",
    "HistoryTransactionPlan",
]

JOURNAL_VERSION: Final = "2026-10-13"
_STRICT: Final = ConfigDict(strict=True, frozen=True, allow_inf_nan=False)
_JOURNAL_CHANGELOG = (
    ChangelogEntry(
        version=JOURNAL_VERSION,
        change="Declare dated, bound history transaction plans and recovery events.",
        why="Later runs must validate the exact replacement and recovery record.",
    ),
)
_FILE_PHASES: Final = frozenset(
    ("planned", "replaced", "verified", "restored", "rollback-verified")
)


class HistoryTransactionFile(HistoryModel):
    model_config = _STRICT

    index: Nonnegative
    path: RelPath
    kind: Literal["raw", "compact", "raw_index", "compact_index", "view", "receipt", "set_aside"]
    old_sha256: Sha256
    old_bytes: Nonnegative
    new_sha256: Sha256
    new_bytes: Nonnegative
    backup: RelPath
    stage: RelPath


class HistoryTransactionEvidence(HistoryModel):
    model_config = _STRICT

    path: RelPath
    sha256: Sha256
    bytes: Nonnegative


class _TransactionBinding(HistoryModel):
    model_config = _STRICT

    transaction_id: Sha256
    manifest_sha256: Sha256
    scope_hash: Sha256
    report_evidence_hash: Sha256

    @model_validator(mode="after")
    def _bound_transaction(self) -> Self:
        expected = hashlib.sha256(
            f"{self.manifest_sha256}\0{self.scope_hash}\0{self.report_evidence_hash}".encode("ascii")
        ).hexdigest()
        if self.transaction_id != expected:
            raise ValueError("transaction id does not bind the exact manifest, scope and evidence")
        return self


class HistoryTransactionPlan(_TransactionBinding, Contract):
    __schema_stem__: ClassVar[str] = "host-history-transaction-plan"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _JOURNAL_CHANGELOG
    model_config = _STRICT

    version: Literal["2026-10-13"]
    # The inherited version validator passes decoded JSON arrays to these fields.
    files: tuple[HistoryTransactionFile, ...] = Field(strict=False)
    evidence: tuple[HistoryTransactionEvidence, ...] = Field(strict=False)

    @model_validator(mode="after")
    def _unique_indexed_paths(self) -> Self:
        if any(file.index != index for index, file in enumerate(self.files)):
            raise ValueError("transaction file indexes must be contiguous from zero")
        if len({file.path for file in self.files}) != len(self.files):
            raise ValueError("transaction repeats a source path")
        if len({item.path for item in self.evidence}) != len(self.evidence):
            raise ValueError("transaction repeats an evidence path")
        return self


class HistoryTransactionEvent(_TransactionBinding, Contract):
    __schema_stem__: ClassVar[str] = "host-history-transaction-event"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _JOURNAL_CHANGELOG
    model_config = _STRICT

    version: Literal["2026-10-13"]
    phase: Literal[
        "plan-created",
        "evidence-verified",
        "backups-verified",
        "staged-verified",
        "planned",
        "replaced",
        "verified",
        "reconciled",
        "complete",
        "rollback-started",
        "restored",
        "rollback-verified",
        "rolled-back",
    ]
    index: Nonnegative | None = None
    path: RelPath | None = None
    old_sha256: Sha256 | None = None
    new_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def _phase_fields(self) -> Self:
        fields = (self.index, self.path, self.old_sha256, self.new_sha256)
        if self.phase in _FILE_PHASES:
            if any(value is None for value in fields):
                raise ValueError("per-file phase requires index, path, old_sha256 and new_sha256")
        elif any(value is not None for value in fields):
            raise ValueError("global phase forbids per-file fields")
        return self


class HistoryApplyApproval(HistoryModel, Contract):
    __schema_stem__: ClassVar[str] = "host-history-apply-approval"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=JOURNAL_VERSION,
            change="Declare operator-issued approval bound to evidence and a target checkout.",
            why="A maintenance reader must not substitute evidence or a different target.",
        ),
    )
    model_config = _STRICT

    version: Literal["2026-10-13"]
    authority: Literal["unattended_user"]
    authorized_at: Timestamp = Field(description="When the operator issued approval, in UTC.")
    manifest_sha256: Sha256
    scope_hash: Sha256
    report_evidence_hash: Sha256
    d16_revision: CommitSha
    d7_revision: CommitSha
    target_device: Nonnegative
    target_inode: Nonnegative


class HistoryMaintenanceOwner(HistoryModel, Contract):
    __schema_stem__: ClassVar[str] = "host-history-maintenance-owner"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=JOURNAL_VERSION,
            change="Declare the maintenance process, target checkout and exact Git state.",
            why="A later run must distinguish the owner and the checkout it claimed.",
        ),
    )
    model_config = _STRICT

    version: Literal["2026-10-13"]
    # The version validator also passes a JSON UUID to field parsing as text.
    nonce: UUID = Field(strict=False)
    pid: Positive
    process_created_at: Timestamp = Field(description="When the owner process started, in UTC.")
    target_device: Nonnegative
    target_inode: Nonnegative
    manifest_sha256: Sha256
    scope_hash: Sha256
    report_evidence_hash: Sha256
    git_head: CommitSha
    git_index_sha256: Sha256 | None
