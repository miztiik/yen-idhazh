"""What a ledger file under `state/raw/` or `state/compact/` says about itself, inside itself.

A filename carries identity, never meaning. Everything a reader needs to know
about one file - which ledger, which period, which writer, which shape its rows
are - travels in the file, so the file can be renamed, moved or re-partitioned
and every reader still knows what it holds. A filename that is parsed is a
schema nobody declared, versioned or validated.

`FileEnvelope` is that record. In a parquet file it is the footer's key-value
metadata; in a JSON-lines file it is the first line. Both are bytes to bytes in
the end, so `as_metadata` is the one place a value becomes a string and
`from_metadata` the one place it comes back.

**A field is also a column only when a query filters or groups on it**, because
row-group statistics then let a reader skip a whole file without decompressing
anything. The door writes those as columns on every row; everything else is
footer only, where it is provenance a person reads after the fact and costs
nothing per row. The measurement behind that line is in
`docs/architecture/contracts/persistence.md`.

Every instant here is UTC: `written_at_ms` is epoch milliseconds and `covers` is
a UTC day or month (CLAUDE.md section 2).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    DATE_PATTERN,
    MONTH_PATTERN,
    ChangelogEntry,
    CommitSha,
    Contract,
    Model,
    PeriodStamp,
    RunId,
    SchemaVersion,
    ServerJob,
    Sha256,
)
from idhazh.contracts.ledger_name import LedgerName


class Tier(StrEnum):
    """Which of the two roots under `state/` a file sits in."""

    RAW = "raw"  # data as a writer left it
    COMPACT = "compact"  # what a compaction left behind


class Period(StrEnum):
    """How much time one compact file covers. Also the directory name."""

    DAILY = "daily"
    MONTHLY = "monthly"


class Format(StrEnum):
    """Which container a ledger file is: columnar parquet, or JSON lines a person can read."""

    PARQUET = "parquet"
    JSON = "json"


class Compression(StrEnum):
    """How a file's rows were compressed when it was written.

    `none` is what a JSON-lines file records, because it is written as plain
    text; it is also a legal parquet setting, which writes the rows uncompressed.
    The key says what was done to the file, never what the config asked for.
    """

    SNAPPY = "snappy"
    ZSTD = "zstd"
    NONE = "none"


#: What `covers` must look like for each kind of file. A raw file and a daily
#: file cover one UTC day; a monthly file covers one UTC month.
_DAY: Final = re.compile(DATE_PATTERN)
_MONTH: Final = re.compile(MONTH_PATTERN)

#: The module that wrote a file, as a dotted name inside the ledger package.
_WRITER_PATTERN: Final = r"^idhazh\.ledger\.[a-z_]+$"

#: The keys `as_metadata` writes, in the order the envelope's table lists them.
#: A key outside this set is refused on the way back in, the way `extra="forbid"`
#: refuses an unknown field.
_KEYS: Final = (
    "envelope_version",
    "schema_version",
    "tier",
    "ledger",
    "covers",
    "period",
    "written_at_ms",
    "run_id",
    "attempt",
    "job",
    "shard",
    "producer",
    "unit_id",
    "file_id",
    "content_sha256",
    "git_sha",
    "writer",
    "writer_version",
    "compression",
    "built_from",
)

#: The keys that may be absent: a raw file names no period and read no sources.
_OPTIONAL_KEYS: Final = frozenset({"period", "built_from"})


def covers_fits(covers: str, *, tier: Tier, period: Period | None) -> bool:
    """Whether a period stamp has the shape this kind of file covers.

    A raw file and a daily file cover a UTC day; a monthly file covers a UTC
    month. Asked by the envelope when it validates and by the door before it
    builds a path, so the two cannot disagree about what a period looks like.
    """
    if tier is Tier.RAW or period is Period.DAILY:
        return _DAY.fullmatch(covers) is not None
    return _MONTH.fullmatch(covers) is not None


class WriterIdentity(Model):
    """Which run, attempt, job, shard and module wrote a file, and from which tree.

    No field is nullable and none has a default: an identity with a hole in it
    cannot mint a name.
    """

    run_id: RunId = Field(description="The run that wrote the file: `<YYYY-MM-DD>-<execution>`.")
    attempt: int = Field(
        ge=1,
        description=(
            "Which try at that run, from 1. GitHub keeps the run id across a re-run, so "
            "this is the only field that tells two attempts apart, and it is what the "
            "union ranks on: the highest attempt at one work unit wins."
        ),
    )
    job: ServerJob = Field(description="The workflow job that wrote the file.")
    shard: int = Field(ge=0, description="Which shard of that job, from 0.")
    producer: str = Field(
        min_length=1,
        description=(
            "The dotted name of the module that wrote the file, plus `:<part>` when one "
            "module writes one record as two files. It is what keeps two producers of "
            "one ledger in one job apart inside `unit_id`, and it survives a re-run "
            "unchanged."
        ),
    )
    git_sha: CommitSha = Field(
        description="The commit the writing run checked out: what ties a file to the code."
    )


class FileEnvelope(Contract):
    """What one ledger file holds, written inside the file so its name is never parsed."""

    __schema_stem__: ClassVar[str] = "file-envelope"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-25",
            change="Initial shape: the keys a raw or compact ledger file carries about itself.",
            why="A parquet file must say what it holds without its filename being parsed.",
        ),
    )

    row_schema_version: SchemaVersion = Field(
        description=(
            "The version stamp of the row contract the rows were written under, kept "
            "under the key `schema_version`. The envelope's own stamp is `version`, kept "
            "under `envelope_version`, so the envelope can change shape without the rows "
            "doing so."
        )
    )
    tier: Tier = Field(description="`raw` or `compact`. The copy that survives a move.")
    ledger: LedgerName = Field(description="Which ledger the rows belong to.")
    covers: PeriodStamp = Field(
        description=(
            "The UTC day (`2026-09-23`) a raw or daily file covers, or the UTC month "
            "(`2026-08`) a monthly file covers. Never the day the file was written."
        )
    )
    period: Period | None = Field(
        default=None,
        description="`daily` or `monthly` on a compact file. Absent on a raw file.",
    )
    written_at_ms: int = Field(
        ge=0,
        description=(
            "When the file was written, epoch milliseconds, UTC. The clock inside "
            "`file_id`, so a listing sorts by time."
        ),
    )
    identity: WriterIdentity = Field(description="Which writer produced the file.")
    unit_id: uuid.UUID = Field(
        description=(
            "Which work unit the file records: a version 5 UUID of ledger, covers, run, "
            "job, shard and producer, with no clock and no attempt in it. Identical for "
            "every attempt at one unit, so a union keeps the highest attempt per unit."
        )
    )
    file_id: uuid.UUID = Field(
        description=(
            "The name of this one file: a version 8 UUID, clock first, different for "
            "every file ever written. It is the filename's stem."
        )
    )
    content_sha256: Sha256 = Field(
        description=(
            "SHA-256 over the rows as canonical JSON lines, whatever the container, so "
            "two files can be told apart after a rename and a copy proven a copy."
        )
    )
    writer: Annotated[str, StringConstraints(pattern=_WRITER_PATTERN)] = Field(
        description=(
            "The ledger module that wrote the file. A parquet footer's own `created_by` "
            "names the engine, not this project."
        )
    )
    writer_version: str = Field(
        min_length=1,
        description=(
            "The version of the engine that rendered the bytes, because a file is not "
            "byte-stable across engine versions."
        ),
    )
    compression: Compression = Field(description="How the rows were compressed.")
    built_from: int | None = Field(
        default=None,
        ge=0,
        description="On a compact file, how many files were read to make it. Absent on raw.",
    )

    @model_validator(mode="after")
    def _the_period_fits_the_tier(self) -> Self:
        """A raw file names no period and read no sources; a compact one names its period.

        And `covers` has the shape of that period, so a monthly file cannot claim
        one day and a raw file cannot claim a month.
        """
        if (self.tier is Tier.COMPACT) != (self.period is not None):
            raise ValueError(
                f"a {self.tier.value} file {'needs' if self.tier is Tier.COMPACT else 'names no'} "
                "period: a compact file covers a daily or monthly period and a raw file "
                "covers the day its writer filed it under"
            )
        if self.tier is Tier.RAW and self.built_from is not None:
            raise ValueError("a raw file was read from nothing, so it carries no built_from")
        if not covers_fits(self.covers, tier=self.tier, period=self.period):
            raise ValueError(
                f"covers {self.covers!r} is not the shape a {self.tier.value} "
                f"{self.period.value + ' ' if self.period else ''}file covers: a raw or "
                "daily file covers YYYY-MM-DD and a monthly file covers YYYY-MM"
            )
        return self

    @model_validator(mode="after")
    def _each_identifier_is_its_own_kind(self) -> Self:
        """`unit_id` is a version 5 UUID and `file_id` a version 8 one, so a swapped pair fails."""
        if self.unit_id.version != 5 or self.file_id.version != 8:
            raise ValueError(
                "unit_id must be a version 5 UUID and file_id a version 8 one, got "
                f"versions {self.unit_id.version} and {self.file_id.version}"
            )
        return self

    def as_metadata(self) -> dict[bytes, bytes]:
        """Every key as UTF-8 bytes, the one place a value becomes a string.

        `attempt` and `shard` are zero-padded to two digits; `period` and
        `built_from` are left out when they are absent. Two fields are kept under a
        key of another name: `version` as `envelope_version`, because the file's
        rows have a version of their own, and `row_schema_version` as
        `schema_version`.
        """
        values: dict[str, str | None] = {
            "envelope_version": self.version,
            "schema_version": self.row_schema_version,
            "tier": self.tier.value,
            "ledger": self.ledger.value,
            "covers": self.covers,
            "period": self.period.value if self.period is not None else None,
            "written_at_ms": str(self.written_at_ms),
            "run_id": self.identity.run_id,
            "attempt": f"{self.identity.attempt:02d}",
            "job": self.identity.job.value,
            "shard": f"{self.identity.shard:02d}",
            "producer": self.identity.producer,
            "unit_id": str(self.unit_id),
            "file_id": str(self.file_id),
            "content_sha256": self.content_sha256,
            "git_sha": self.identity.git_sha,
            "writer": self.writer,
            "writer_version": self.writer_version,
            "compression": self.compression.value,
            "built_from": str(self.built_from) if self.built_from is not None else None,
        }
        return {
            key.encode("utf-8"): value.encode("utf-8")
            for key, value in values.items()
            if value is not None
        }

    @classmethod
    def from_metadata(cls, mapping: Mapping[bytes, bytes]) -> Self:
        """The envelope back from the bytes `as_metadata` wrote, or a refusal naming the key.

        A key this shape does not declare is refused, the way `extra="forbid"`
        refuses an unknown field; a required key that is missing is refused too.
        Every value is then validated by the fields themselves.
        """
        text = {key.decode("utf-8"): value.decode("utf-8") for key, value in mapping.items()}
        unknown = sorted(set(text) - set(_KEYS))
        if unknown:
            raise ValueError(f"the envelope carries keys it does not declare: {unknown}")
        missing = sorted(set(_KEYS) - _OPTIONAL_KEYS - set(text))
        if missing:
            raise ValueError(f"the envelope is missing required keys: {missing}")
        return cls.model_validate(
            {
                "version": text["envelope_version"],
                "row_schema_version": text["schema_version"],
                "tier": text["tier"],
                "ledger": text["ledger"],
                "covers": text["covers"],
                "period": text.get("period"),
                "written_at_ms": int(text["written_at_ms"]),
                "identity": {
                    "run_id": text["run_id"],
                    "attempt": int(text["attempt"]),
                    "job": text["job"],
                    "shard": int(text["shard"]),
                    "producer": text["producer"],
                    "git_sha": text["git_sha"],
                },
                "unit_id": text["unit_id"],
                "file_id": text["file_id"],
                "content_sha256": text["content_sha256"],
                "writer": text["writer"],
                "writer_version": text["writer_version"],
                "compression": text["compression"],
                "built_from": int(text["built_from"]) if "built_from" in text else None,
            }
        )
