"""What an exact evaluation lookup records in its root, pages and replay receipts."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    Model,
    RelPath,
    Sha256,
    canonical_json,
    derive_text_digest,
)
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import WriterIdentity

DigestPrefix = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{0,64}$")]
DigestDigit = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]$")]
NodeKind = Literal["leaf", "page"]


class ObservationLookupNode(Model):
    """A content-addressed child, whose filename is derived rather than supplied."""

    kind: NodeKind
    sha256: Sha256


class ObservationLookupSettings(Model):
    """The byte bounds for a lookup leaf and its SQLite pages."""

    max_leaf_bytes: int = Field(default=262144, ge=16384)
    sqlite_page_bytes: Literal[4096, 8192, 16384, 32768, 65536] = 4096

    @model_validator(mode="after")
    def require_whole_pages(self) -> Self:
        if self.max_leaf_bytes < 4 * self.sqlite_page_bytes:
            raise ValueError("max_leaf_bytes must hold at least four SQLite pages")
        if self.max_leaf_bytes % self.sqlite_page_bytes:
            raise ValueError("max_leaf_bytes must be a multiple of sqlite_page_bytes")
        return self


class ObservationLookupRoot(Contract):
    """The fixed-size entry point for one complete evaluation lookup generation."""

    __schema_stem__: ClassVar[str] = "observation-lookup-root"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-02",
            change="Declare the bounded evaluation lookup root.",
            why="An ordinary measurement lookup must not reconstruct historical IDs.",
        ),
    )

    generation: Sha256
    key_fields: tuple[str, ...] = Field(min_length=1, max_length=16)
    node: ObservationLookupNode
    settings: ObservationLookupSettings


class ObservationLookupPage(Contract):
    """At most sixteen digest-prefix children, with no path supplied by a row."""

    __schema_stem__: ClassVar[str] = "observation-lookup-page"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-02",
            change="Declare bounded digest-prefix routing pages.",
            why="Finding one leaf must not load a growing partition catalogue.",
        ),
    )

    prefix: DigestPrefix
    children: dict[DigestDigit, ObservationLookupNode] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def require_remaining_digit(self) -> Self:
        if len(self.prefix) == 64:
            raise ValueError("a complete digest cannot have a routing child")
        return self


class ObservationLookupReceipt(Contract):
    """The accepted output of a batch whose input can be replayed after a crash."""

    __schema_stem__: ClassVar[str] = "observation-lookup-receipt"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-02",
            change="Bind an evaluation batch to its accepted output.",
            why="A retry must recognize an already committed batch without rewriting its rows.",
        ),
    )

    batch_id: Sha256
    payload_sha256: Sha256
    generation: Sha256
    accepted: int = Field(ge=0)
    output_paths: list[RelPath]

    @model_validator(mode="after")
    def require_output_for_accepted_rows(self) -> Self:
        if (self.accepted > 0) != bool(self.output_paths):
            raise ValueError("only a batch with accepted rows names output_paths")
        return self


class ObservationLookupEntry(Model):
    """One SQLite entry: either a measurement ID or an applied batch receipt."""

    namespace: Literal["observation", "batch"]
    identity: Sha256
    receipt: ObservationLookupReceipt | None = None

    @property
    def key(self) -> str:
        return derive_text_digest(canonical_json([self.namespace, self.identity]))

    @model_validator(mode="after")
    def require_matching_receipt(self) -> Self:
        if self.namespace == "observation" and self.receipt is not None:
            raise ValueError("an observation entry cannot carry a batch receipt")
        if self.namespace == "batch":
            if self.receipt is None or self.receipt.batch_id != self.identity:
                raise ValueError("a batch entry must carry its own receipt")
        return self


class ObservationLookupTransaction(Contract):
    """Only the nodes one interrupted update can have created or superseded."""

    __schema_stem__: ClassVar[str] = "observation-lookup-transaction"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-02",
            change="Declare bounded recovery for one evaluation index update.",
            why="Recovery must not discover orphan files by walking all history.",
        ),
    )

    before: Sha256 | None
    after: Sha256
    created: list[ObservationLookupNode]
    superseded: list[ObservationLookupNode]


class ObservationBatch(Contract):
    """One immutable incoming evaluation batch, independent of any index generation."""

    __schema_stem__: ClassVar[str] = "observation-batch"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-02",
            change="Preserve named evaluation input for atomic publication and replay.",
            why="A raced push must reapply original input against the winning index generation.",
        ),
    )

    identity: WriterIdentity
    rows: list[EvalRow] = Field(min_length=1)

    @property
    def payload_sha256(self) -> str:
        return derive_text_digest(
            canonical_json([row.model_dump(mode="json") for row in self.rows])
        )

    @property
    def batch_id(self) -> str:
        return derive_text_digest(
            canonical_json(
                {
                    "identity": self.identity.model_dump(mode="json"),
                    "payload_sha256": self.payload_sha256,
                }
            )
        )


class ObservationPreparation(Contract):
    """The immutable batches and derived paths owned by one job's commit attempt."""

    __schema_stem__: ClassVar[str] = "observation-preparation"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-02",
            change="Name the evaluation inputs and changed paths a push retry must replay.",
            why="The commit loop must restore only its own derived files before retrying.",
        ),
    )

    batches: list[Sha256]
    paths: list[RelPath]
