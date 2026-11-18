"""Why does recovery refuse one retained input?

Each reason names one cause and carries the sentence an operator reads, so a caller or a test
matches the cause and never the wording. A message that used to name its subject now carries
that subject in `paths`.
"""

from __future__ import annotations

from enum import StrEnum

from utilities.publication_request import IntegrityError


class RefusalReason(StrEnum):
    """One cause a retained recovery input is refused, valued by its operator-facing sentence."""

    # The platform's own listings and downloads.
    RUN_ID_NOT_POSITIVE = "source run must be a positive platform run ID"
    PLATFORM_LIST_MISSING = "platform response has no list for the requested inventory"
    PAGINATION_ENDED_EARLY = "platform pagination ended before its declared count"
    ARTIFACT_EXPIRED_FOREIGN_OR_AMBIGUOUS = "source artifacts are expired, foreign or ambiguous"
    NO_PLAN_ARTIFACT = "source run has no retained plan artifact"
    ANOTHER_SOURCE_RUN = "platform returned another source run"
    NO_SUCCESSFUL_PLAN_JOB = "source attempt has no successful planning job"
    CHECKSUM_DIFFERS_FROM_DIGEST = "downloaded artifact checksum differs from platform digest"

    # One downloaded archive.
    NOT_A_ZIP_ARCHIVE = "source artifact is not a readable ZIP archive"
    UNSAFE_OR_DUPLICATE_FILE = "artifact contains an unsafe or duplicate file"
    CORRUPT_FILE_BYTES = "source artifact has corrupt file bytes"

    # The saved plan.
    NON_LEDGER_PLAN_FILE = "plan artifact contains a non-ledger file"
    PLAN_FILENAME_NOT_FILE_IDENTITY = "plan filename does not match its native file identity"
    PLAN_NOT_RAW_OUTPUT = "plan artifact is not raw planning output"
    PLAN_WRITER_MISMATCH = "source plan has mismatched writer identity"
    PLAN_FILE_NOT_ONE_PLAN = "source plan file must contain one plan"
    PLAN_RUN_DATE_OR_SHARDS_MISMATCH = "source plan has mismatched run, date or missing shard count"
    NO_ONE_SOURCE_ATTEMPT_PLAN = "artifact must retain exactly one compatible source-attempt plan"

    # The saved worker output.
    PLAN_HAS_NO_SHARD_COUNT = "source plan has no dispatched shard count"
    UNDISPATCHED_SHARD_ARTIFACT = "items artifact names an undispatched shard"
    SUCCESSFUL_WORKER_ARTIFACT_MISSING = "successful worker has no retained items artifact"
    WORKER_PAYLOAD_INVALID = "worker payload does not validate against its contract"
    PAYLOAD_NAMES_ANOTHER_ITEM = "worker payload identifies another planned item"
    PAYLOAD_ADDRESS_MISMATCH = "worker payload does not match its planned address"
    RECORD_FROM_ANOTHER_RUN = "worker record belongs to another source run"
    RECORD_FROM_ANOTHER_SHARD = "worker record belongs to another shard"
    UNPLANNED_WORKER_FILE = "artifact contains an unplanned worker file"
    SHARED_BYTES_DISAGREE = "worker artifacts disagree on shared bytes"
    SOURCE_ARTICLE_MISSING = "worker output has no saved source article"

    # Restoring into the checkout and authorizing the original plan.
    NO_WORKER_OUTPUT = "source run has no retained worker output"
    FOREIGN_ITEM_DIRECTORY_FILES = "recovery item directory contains foreign files"
    FOREIGN_STAGED_INPUT = "restore would touch foreign staged input"
    FOREIGN_LOCAL_BYTES = "restore would replace foreign local bytes"
    RESTORED_PLAN_BYTES_CHANGED = "restored source plan bytes changed"
    RESTORED_PLAN_IDENTITY_CHANGED = "restored plan no longer matches source identity"


class RecoveryRefusalError(IntegrityError):
    """A recovery input was refused for `reason`; `paths` names the offending files or keys."""

    def __init__(self, reason: RefusalReason, paths: tuple[str, ...] = ()) -> None:
        super().__init__(reason.value, paths)
        self.reason = reason
