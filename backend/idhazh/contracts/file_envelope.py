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
`docs/architecture/contracts/persistence.md`. `RowIdentity` declares those
columns: the cells every row carries about the writer that first filed it,
which a compact file keeps as they were.

Every instant here is UTC: `written_at_ms` is epoch milliseconds and `covers` is
a UTC day, month or year (CLAUDE.md section 2).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, ClassVar, Final, Literal, Self, assert_never, cast

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    DATE_PATTERN,
    MONTH_PATTERN,
    YEAR_PATTERN,
    ChangelogEntry,
    CommitSha,
    Contract,
    DateStamp,
    JobName,
    Model,
    PeriodStamp,
    PipelineName,
    RunId,
    SchemaVersion,
    ServerJob,
    Sha256,
    TaskName,
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
    YEARLY = "yearly"


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
#: file cover one UTC day; a monthly file covers one UTC month; a yearly file
#: covers one UTC year.
_DAY: Final = re.compile(DATE_PATTERN)
_MONTH: Final = re.compile(MONTH_PATTERN)
_YEAR: Final = re.compile(YEAR_PATTERN)

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
    "pipeline_name",
    "task_name",
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

#: A generic writer has pipeline/task identity and no legacy job key.
_OPTIONAL_KEYS: Final = frozenset(
    {"job", "period", "built_from", "pipeline_name", "task_name"}
)
_ENVELOPE_VERSIONS: Final = frozenset(
    {
        "2026-10-20",
        "2026-10-14",
        "2026-09-25",
        "2026-09-27",
        "2026-09-28",
        "2026-09-30",
        "2026-10-01",
        "2026-10-01T16:50",
        "2026-10-06",
        "2026-10-10",
        "2026-10-12",
    }
)


def covers_fits(covers: str, *, tier: Tier, period: Period | None) -> bool:
    """Whether a period stamp has the shape this kind of file covers.

    A raw file and a daily file cover a UTC day; a monthly file covers a UTC
    month; a yearly file covers a UTC year. Asked by the envelope when it
    validates and by the door before it builds a path, so the two cannot
    disagree about what a period looks like.
    """
    if tier is Tier.RAW or period is None:
        return _DAY.fullmatch(covers) is not None
    match period:
        case Period.DAILY:
            shape = _DAY
        case Period.MONTHLY:
            shape = _MONTH
        case Period.YEARLY:
            shape = _YEAR
        case _:
            assert_never(period)
    return shape.fullmatch(covers) is not None


class WriterIdentity(Model):
    """Which run, attempt, task, shard and module wrote a file, and from which tree."""

    run_id: RunId = Field(description="The run that wrote the file: `<YYYY-MM-DD>-<execution>`.")
    attempt: int = Field(
        ge=1,
        description=(
            "Which try at that run, from 1. GitHub keeps the run id across a re-run, so "
            "this is the only field that tells two attempts apart, and it is what the "
            "union ranks on: the highest attempt at one work unit wins."
        ),
    )
    job: ServerJob | JobName | None = Field(
        description="The legacy workflow job name, absent for a generic pipeline/task identity."
    )
    pipeline_name: PipelineName | None = Field(
        default=None, description="The pipeline that wrote a generic telemetry record."
    )
    task_name: TaskName | None = Field(
        default=None, description="The task within a generic telemetry pipeline."
    )
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

    @model_validator(mode="after")
    def _has_one_job_identity(self) -> Self:
        if (self.pipeline_name is None) != (self.task_name is None):
            raise ValueError("writer identity requires both pipeline_name and task_name")
        if self.task_name is None and self.job is None:
            raise ValueError("writer identity requires a legacy job or pipeline and task")
        if self.task_name is not None and self.job not in (None, self.task_name):
            raise ValueError("generic writer job must be absent or match its task")
        return self

    @property
    def task_key(self) -> str:
        """A string key for callers that need one name for either identity form."""
        if self.job is not None:
            return str(self.job)
        if self.pipeline_name is None or self.task_name is None:
            raise ValueError("writer identity has no task key")
        return f"{self.pipeline_name}-{self.task_name}"

    @classmethod
    def for_pipeline_task(
        cls,
        *,
        run_id: RunId,
        attempt: int,
        pipeline_name: PipelineName,
        task_name: TaskName,
        shard: int,
        producer: str,
        git_sha: CommitSha,
    ) -> Self:
        """Build a reusable identity without requiring a workflow-job enum."""
        return cls(
            run_id=run_id,
            attempt=attempt,
            job=None,
            pipeline_name=pipeline_name,
            task_name=task_name,
            shard=shard,
            producer=producer,
            git_sha=git_sha,
        )


class EnvelopeWriterIdentity(WriterIdentity):
    """The immutable identity nested inside a file envelope."""

    model_config = ConfigDict(frozen=True, revalidate_instances="always")

    def __eq__(self, other: object) -> bool:
        """Keep identity equality structural across the mutable/immutable boundary."""
        if isinstance(other, WriterIdentity):
            return self.model_dump() == other.model_dump()
        return NotImplemented


#: A version 5 UUID in its canonical lower-case spelling: a row's `unit_id` cell.
_UNIT_ID_PATTERN: Final = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class RowIdentity(Model):
    """The cells the ledger door stamps on every row: which writer filed it, and which try.

    Columns rather than footer keys, because a query groups on them: a union
    keeps the highest `attempt` per `unit_id`, and a bad run is traced by
    filtering on `run_id`. A row whose own contract declares one of these names
    carries its own value there. A compact file keeps every row's cells as the
    raw file that first held it had them, never the compaction's, so a re-run
    that lands after a day was compacted can still replace its first attempt.
    """

    __column_versions__: ClassVar[Mapping[str, str]] = MappingProxyType({
        "pipeline_name": "2026-10-12",
        "task_name": "2026-10-12",
    })

    ledger: LedgerName = Field(description="The ledger the row was filed into.")
    covers: DateStamp = Field(
        description="The UTC day the raw file that first held the row covers."
    )
    run_id: RunId = Field(description="The run that filed the row.")
    attempt: int = Field(
        ge=1, description="Which try at that run filed it. The union keeps the highest."
    )
    job: ServerJob | JobName | None = Field(
        description="The legacy workflow job name, absent for a generic pipeline/task identity."
    )
    pipeline_name: PipelineName | None = Field(default=None)
    task_name: TaskName | None = Field(default=None)
    shard: int = Field(ge=0, description="Which shard of that job, from 0.")
    unit_id: Annotated[str, StringConstraints(pattern=_UNIT_ID_PATTERN)] = Field(
        description=(
            "The work unit the row belongs to, as the raw file's `unit_id` spells it. "
            "The same for every attempt at that unit."
        )
    )

    @model_validator(mode="after")
    def _has_one_job_identity(self) -> Self:
        if (self.pipeline_name is None) != (self.task_name is None):
            raise ValueError("row identity requires both pipeline_name and task_name")
        if self.task_name is None and self.job is None:
            raise ValueError("row identity requires a legacy job or pipeline and task")
        if self.task_name is not None and self.job not in (None, self.task_name):
            raise ValueError("generic row job must be absent or match its task")
        return self


class FileEnvelope(Contract):
    """What one ledger file holds, written inside the file so its name is never parsed."""

    model_config = ConfigDict(frozen=True, revalidate_instances="always")
    __schema_stem__: ClassVar[str] = "file-envelope"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-20",
            change="Read the shared TypeScript Parquet writer provenance.",
            why="Compatible readers precede files emitted by the shared TypeScript writer.",
        ),
        ChangelogEntry(
            version="2026-10-14",
            change="Store generic pipeline and task names without a legacy job value.",
            why="Shared ledgers group reusable telemetry by its separate identity columns.",
        ),
        ChangelogEntry(
            version="2026-10-12",
            change="Add generic pipeline and task writer identity.",
            why="Shared telemetry must not require a closed workflow-job list.",
        ),
        ChangelogEntry(
            version="2026-10-10",
            change="Read corrected host history with its recorded file envelope.",
            why="Previously published host rows remain readable after collector retirement.",
        ),
        ChangelogEntry(
            version="2026-10-01",
            change="Earlier changes are in this file's git history.",
            why="Git is the archive for older shape changes.",
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
            "The UTC day (`2026-09-23`) a raw or daily file covers, the UTC month "
            "(`2026-08`) a monthly file covers, or the UTC year (`2026`) a yearly file "
            "covers. Never the day the file was written."
        )
    )
    period: Period | None = Field(
        default=None,
        description="`daily`, `monthly` or `yearly` on a compact file. Absent on a raw file.",
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
    writer: Literal[
        "idhazh.ledger.parquet",
        "idhazh.ledger.json_lines",
        "idhazh_rust.ledger.parquet",
        "idhazh_rust.ledger.json_lines",
        "idhazh_typescript.ledger.parquet",
    ] = Field(
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

    @model_validator(mode="before")
    @classmethod
    def _freeze_writer_identity(cls, data: object) -> object:
        if isinstance(data, Mapping):
            identity = data.get("identity")
            if isinstance(identity, WriterIdentity):
                identity = identity.model_dump()
            if isinstance(identity, Mapping):
                declared = cast("type[WriterIdentity]", cls.model_fields["identity"].annotation)
                target = EnvelopeWriterIdentity if declared is WriterIdentity else declared
                return dict(data) | {"identity": target.model_validate(identity)}
        return data

    @model_validator(mode="after")
    def _the_period_fits_the_tier(self) -> Self:
        """A raw file names no period and read no sources; a compact one names its period.

        And `covers` has the shape of that period, so a monthly file cannot claim
        one day and a raw file cannot claim a month.
        """
        if (self.tier is Tier.COMPACT) != (self.period is not None):
            raise ValueError(
                f"a {self.tier.value} file {'needs' if self.tier is Tier.COMPACT else 'names no'} "
                "period: a compact file covers a daily, monthly or yearly period and a raw "
                "file covers the day its writer filed it under"
            )
        if self.tier is Tier.RAW and self.built_from is not None:
            raise ValueError("a raw file was read from nothing, so it carries no built_from")
        if not covers_fits(self.covers, tier=self.tier, period=self.period):
            raise ValueError(
                f"covers {self.covers!r} is not the shape a {self.tier.value} "
                f"{self.period.value + ' ' if self.period else ''}file covers: a raw or "
                "daily file covers YYYY-MM-DD, a monthly file covers YYYY-MM and a yearly "
                "file covers YYYY"
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

    @model_validator(mode="after")
    def _writer_scope_is_finite(self) -> Self:
        if self.version not in _ENVELOPE_VERSIONS:
            raise ValueError("unrecognized file envelope version")
        if self.writer == "idhazh_typescript.ledger.parquet" and self.version < "2026-10-20":
            raise ValueError("TypeScript writer requires envelope version 2026-10-20 or later")
        if self.writer.startswith("idhazh_rust.") and (
            self.version != "2026-10-10"
            or self.row_schema_version != "2026-10-10"
            or self.ledger is not LedgerName.HOST_FINGERPRINT
            or self.tier is not Tier.RAW
            or self.identity.producer != "telemetry.silicon"
        ):
            raise ValueError("historical host writer requires its recorded raw host contract")
        if self.writer.endswith(".json_lines") and self.compression is not Compression.NONE:
            raise ValueError("JSON lines must record compression none")
        return self

    def validate_container(self, container: Format) -> Self:
        """Validate provenance against the container detected from the file bytes."""
        container = Format(container)
        expected = ".parquet" if container is Format.PARQUET else ".json_lines"
        if not self.writer.endswith(expected):
            raise ValueError("writer does not match the observed container")
        return self

    def as_metadata(self) -> dict[bytes, bytes]:
        """Every key as UTF-8 bytes, the one place a value becomes a string.

        `attempt` and `shard` are zero-padded to two digits; `period` and
        `built_from` and the legacy `job` key are left out when absent. Two
        fields are kept under a key of another name: `version` as
        `envelope_version`, because the file's
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
            "job": str(self.identity.job) if self.identity.job is not None else None,
            "pipeline_name": self.identity.pipeline_name,
            "task_name": self.identity.task_name,
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
        for key in (b"attempt", b"shard", b"written_at_ms", b"built_from"):
            if key in mapping and re.fullmatch(rb"[0-9]+", mapping[key]) is None:
                raise ValueError(f"{key.decode()} metadata must be ASCII decimal")
        text = {key.decode("utf-8"): value.decode("utf-8") for key, value in mapping.items()}
        unknown = sorted(set(text) - set(_KEYS))
        if unknown:
            raise ValueError(f"the envelope carries keys it does not declare: {unknown}")
        missing = sorted(set(_KEYS) - _OPTIONAL_KEYS - set(text))
        if missing:
            raise ValueError(f"the envelope is missing required keys: {missing}")
        job: ServerJob | str | None = text.get("job")
        if job is not None and not text.get("pipeline_name") and not text.get("task_name"):
            try:
                job = ServerJob(job)
            except ValueError:
                pass
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
                    "job": job,
                    "pipeline_name": text.get("pipeline_name"),
                    "task_name": text.get("task_name"),
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
