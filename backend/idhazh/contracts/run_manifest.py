"""What ran, against which model, at which commit (`.../run.json`).

One manifest per published date, with an append-only `runs[]`. A day may be
built several times; each run appends a record and never rewrites an earlier
one. No run identifier appears in a data path or a reader URL - it lives here
and in the page footer.

`site_bytes` and `site_files` are recorded on every run from the first one, long
before any retention policy exists. Measuring the ceiling is what makes the
policy a decision rather than a reaction (Rule #10 applied to storage).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.app_config import ModelRef
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    RelPath,
    RunId,
    Sha256,
    Slug,
    Timestamp,
)

CommitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]


class RunStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ModelRole(StrEnum):
    SUMMARIZE = "summarize"
    ROUTE = "route"


class ModelUse(Model):
    role: ModelRole
    model_ref: ModelRef


class VerticalCount(Model):
    id: Slug
    planned: int = Field(ge=0, description="Items this run planned for this vertical.")
    published: int = Field(
        ge=0,
        description="Items this run introduced into the day payload for this vertical.",
    )
    below_feed_floor: bool = Field(
        default=False, description="A vertical under its floor is collected but not rendered."
    )

    @model_validator(mode="after")
    def _published_fits_inside_planned(self) -> Self:
        if self.published > self.planned:
            raise ValueError("a vertical cannot publish more items than it planned")
        return self


class ConfigDigest(Model):
    """Which config bytes a run read. A silently edited knob changes every output."""

    path: RelPath
    sha256: Sha256


class RunRecord(Model):
    run_id: RunId
    n: int = Field(ge=1, description="Run sequence within the date. 1 is the morning run.")
    started_at: Timestamp
    completed_at: Timestamp | None = None
    status: RunStatus
    commit_sha: CommitSha
    runner: str = Field(
        min_length=1, description="The hardware this run's numbers were measured on."
    )
    source_list_stale: bool = Field(
        default=False, description="Source discovery failed and yesterday's list was reused."
    )
    models: list[ModelUse] = Field(default_factory=list)

    items_planned: int = Field(ge=0)
    items_succeeded: int = Field(ge=0)
    items_failed: int = Field(ge=0)
    items_skipped: int = Field(default=0, ge=0)
    items_routed: int = Field(
        default=0, ge=0, description="Items the router reached. Zero when the route job died."
    )
    route_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "What the router spent on this day, summed over its items. Read against "
            "items_routed and against the job's own wall-clock: a stage total far below "
            "the job total says the fixed cost is the problem, not the model."
        ),
    )
    verticals: list[VerticalCount] = Field(default_factory=list)

    pipeline_fingerprints: list[Sha256] = Field(
        default_factory=list, description="The distinct stamps this run wrote under."
    )
    determinism_violations: int = Field(
        default=0,
        ge=0,
        description="Recorded, not raised. A gate that fires on a CPU class gets switched off.",
    )

    site_bytes: int = Field(ge=0)
    site_files: int = Field(ge=0)
    config_digests: list[ConfigDigest] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def _counts_reconcile(self) -> Self:
        accounted = self.items_succeeded + self.items_failed + self.items_skipped
        if accounted != self.items_planned:
            raise ValueError("succeeded + failed + skipped must equal planned")
        if self.status is RunStatus.COMPLETED and self.completed_at is None:
            raise ValueError("a completed run records when it completed")
        return self


class RunManifest(Contract):
    """`frontend/public/digest/<YYYY>/<MM>/<DD>/run.json`."""

    __schema_stem__: ClassVar[str] = "run-manifest"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-24T11:15",
            change="Added optional items_routed and route_ms to a run.",
            why=(
                "The route job lands between 51 and 60 minutes against a 60-minute bound, "
                "and no committed artifact said what it spent or how many items it spent it "
                "on. The budget cannot be argued from an estimate (Rule #10). Both default "
                "on a manifest written before they existed."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T00:30",
            change="Pinned RunRecord vertical published counts to the run that wrote them.",
            why=(
                "A later run appends to the day payload. Counting the accumulated day "
                "against this run's plan rejected valid second and later runs."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T02:00",
            change="Added optional pipeline_fingerprints and determinism_violations to a run.",
            why="A run that cannot say which stamps it wrote under cannot be audited later.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: append-only runs for one date, with counts and site size.",
            why="Contracts before logic - a partial day is a recorded fact from run one.",
        ),
    )

    date: DateStamp
    runs: list[RunRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def _runs_are_append_only_and_addressed_by_date(self) -> Self:
        for index, record in enumerate(self.runs, start=1):
            if record.n != index:
                raise ValueError("runs are append-only and numbered from 1 without gaps")
            if record.run_id != f"{self.date}-{record.n}":
                raise ValueError("run_id must be <date>-<n>")
        return self
