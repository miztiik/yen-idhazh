"""What evidence and independent authority does one publication need?"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.publication_paths import IntegrityError as IntegrityError
from idhazh.publication_paths import contains as contains
from idhazh.publication_paths import relative as relative
from idhazh.publication_paths import safe_file as safe_file

PLAIN_MODE = "100644"
_BROAD = {"state", "state/raw", "state/compact"}


@dataclass(frozen=True, slots=True)
class Entry:
    mode: str
    oid: str


@dataclass(frozen=True, slots=True)
class Write:
    sha256: str
    baseline: Entry | None
    immutable: bool = False
    mode: str = PLAIN_MODE
    baseline_tip: str | None = None


@dataclass(frozen=True, slots=True)
class Delete:
    baseline: Entry
    completed: bool


@dataclass(frozen=True, slots=True)
class PublicationRequest:
    identity: WriterIdentity
    message: str
    source_tip: str
    write_permissions: tuple[str, ...]
    delete_permissions: tuple[str, ...]
    writes: Mapping[str, Write]
    deletions: Mapping[str, Delete] = field(default_factory=dict)
    preparation_scopes: tuple[str, ...] = ()
    prepare: Callable[[str, PublicationRequest], PublicationRequest] | None = None

    def validate(self, repo: Path) -> None:
        WriterIdentity.model_validate(self.identity.model_dump())
        if not self.message.strip() or not re.fullmatch("[0-9a-f]{40,64}", self.source_tip):
            raise IntegrityError("missing message or resolved source revision")
        for scope in (*self.write_permissions, *self.delete_permissions, *self.preparation_scopes):
            relative(scope)
            if scope in _BROAD:
                raise IntegrityError("broad state permission is refused", (scope,))
        both = set(self.writes) & set(self.deletions)
        if both:
            raise IntegrityError("write and delete sets overlap", tuple(sorted(both)))
        for path, write in self.writes.items():
            if write.baseline_tip is not None and not re.fullmatch(
                "[0-9a-f]{40,64}", write.baseline_tip
            ):
                raise IntegrityError("unresolved write baseline revision", (path,))
            if not any(contains(scope, path) for scope in self.write_permissions):
                raise IntegrityError("write is outside independent declaration", (path,))
            if write.mode != PLAIN_MODE or (
                write.baseline is not None and write.baseline.mode != PLAIN_MODE
            ):
                raise IntegrityError("mode conversion is refused", (path,))
            target = safe_file(repo, path, exists=True)
            if hashlib.sha256(target.read_bytes()).hexdigest() != write.sha256:
                raise IntegrityError("completed write bytes changed", (path,))
        for path, delete in self.deletions.items():
            if not any(contains(scope, path) for scope in self.delete_permissions):
                raise IntegrityError("deletion is outside independent declaration", (path,))
            if not delete.completed or delete.baseline.mode != PLAIN_MODE:
                raise IntegrityError("deletion has no plain source and completion proof", (path,))
            if safe_file(repo, path, exists=False).exists():
                raise IntegrityError("completed deletion still exists", (path,))
