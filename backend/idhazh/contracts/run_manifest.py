"""What ran, against which model, at which commit (`.../run.json`).

One manifest per published date, with an append-only `runs[]`. A day may be
built several times; each run appends a record and never rewrites an earlier
one. No run identifier appears in a data path or a reader URL - it lives here
and in the page footer.

`site_bytes` and `site_files` are the committed payload tree, recorded on every
run from the first one. They are **not** the published site and they are not
what the 1 GB Pages cap is measured against: the site is built after this stage
runs, and `idhazh site-weight` measures it there. Measured 2026-08-27, the two
trees differed by eighteen times.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Self

from pydantic import ConfigDict, Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    DateStamp,
    Model,
    RelPath,
    RunId,
    Sha256,
    Slug,
    Timestamp,
    without_retired_keys,
)
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.knobs.models import ModelRef


class RunStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ModelRole(StrEnum):
    SUMMARIZE = "summarize"
    #: The value stays `route` because a published manifest may carry it and this
    #: plan migrates no committed day (CLAUDE.md section 11).
    VISUAL_PLANNER = "route"


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
    eligible_feeds: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Feeds on this desk whose configured address this run was allowed to ask, "
            "as the plan counted them. Null on a manifest written before the count "
            "existed, which is unknown rather than a desk with no sources."
        ),
    )
    feed_floor: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The floor that count was measured against, so below_feed_floor can be "
            "checked against the two numbers that decided it rather than taken on "
            "trust. Null on a manifest written before it was recorded."
        ),
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
    #: Two fields carry a wire key the Python name no longer matches, so this
    #: model reads and writes by alias. The alias is split in two rather than
    #: written once as `alias=`, which would also rename the constructor keyword
    #: and put the old word back in every caller.
    model_config = ConfigDict(serialize_by_alias=True, validate_by_name=True)

    run_id: RunId = Field(
        description=(
            "The identity of the execution that made this record, as every ledger "
            "under state/ spells it. Addressed by the date and then by the CI run "
            "that produced it, so no second execution can compute the same one. "
            "Records written before 2026-08-31 carry the day's ordinal there "
            "instead, which is what two runs were able to share."
        )
    )
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
    items_decided: int = Field(
        default=0,
        ge=0,
        validation_alias="items_routed",
        serialization_alias="items_routed",
        description="Items the router reached. Zero when the route job died.",
    )
    items_prefiltered: int = Field(
        default=0,
        ge=0,
        description=(
            "Items the retired visual planner decided without asking the model, because "
            "no enabled visual kind could survive the checks. Counted separately so a "
            "chart rate is never quoted against items_routed alone. **Zero on every run "
            "since the planner retired**: the summarize-and-plan call writes the summary "
            "and the plan in one reply, so the model is asked on every item and the gate "
            "then decides what to do with the plan. Kept because the committed archive "
            "carries non-zero values a reader of an older day still needs."
        ),
    )
    decision_ms: int | None = Field(
        default=None,
        ge=0,
        validation_alias="route_ms",
        serialization_alias="route_ms",
        description=(
            "What the router spent on this day, summed over its items. Read against "
            "items_routed and against the job's own wall-clock: a stage total far below "
            "the job total says the fixed cost is the problem, not the model."
        ),
    )
    charts_drafted: int = Field(
        default=0,
        ge=0,
        description=(
            "Items whose planner reply asked for a chart, whatever the decision became. "
            "Subtract the day's published charts and the remainder is what the "
            "post-model checks rejected - the only number that separates a model that "
            "does not want charts from checks that refuse the ones it wants. Zero on a "
            "manifest written before it existed."
        ),
    )
    verticals: list[VerticalCount] = Field(default_factory=list)

    inputs: PipelineInputs | None = Field(
        default=None,
        description=(
            "What this run summarized with, named field by field: the weights and their "
            "digest, the llama.cpp build, the chat template, the prompt, the output "
            "schema, the truncation cap, every decode and runtime setting including "
            "n_ctx, the runner class, and the extractor and sanitizer versions. "
            "Recorded, never compared to decide anything - no run, no pool, no window "
            "and no published number turns on it, so a run whose inputs moved is "
            "counted, averaged and published exactly as one whose inputs held still. "
            "Read with config_digests beside it, which says which config bytes were "
            "read. Null on a manifest written before 2026-09-12, and on a run that "
            "summarized nothing."
        ),
    )
    determinism_violations: int = Field(
        default=0,
        ge=0,
        description="Recorded, not raised. A gate that fires on a CPU class gets switched off.",
    )

    site_bytes: int = Field(
        ge=0,
        description=(
            "Bytes under frontend/public/digest/ after this run - the committed payload "
            "tree, not the published site and not what the Pages cap is measured against."
        ),
    )
    site_files: int = Field(
        ge=0, description="Files under frontend/public/digest/ after this run."
    )

    evaluation_enabled: bool | None = Field(
        default=None,
        description=(
            "Whether observability.evaluation_enabled was on for this run. False is "
            "deliberately off; true with no scorer_version is an instrument that failed "
            "to load. Null on a manifest written before this was recorded - never "
            "false, because absent and off are different facts."
        ),
    )
    evaluation_sample_rate: float | None = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description=(
            "The fraction of runs the scorer was set to run on, recorded on EVERY run "
            "whether or not this one was drawn. Without it a year-old ledger cannot "
            "tell 800 rows of 1,000 from 800 rows of 800. Null on a manifest written "
            "before this was recorded."
        ),
    )
    evaluation_sampled: bool | None = Field(
        default=None,
        description=(
            "Whether this run was drawn at that rate. False is the third reason a run "
            "has no rows, beside switched off and failed to load, and none of the three "
            "can be read off an absence. Always true at a rate of 1.0."
        ),
    )
    scorer_version: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "The instrument that wrote this run's eval rows, as state/scores.csv spells "
            "it. Null when no row was written, which is what separates a run that "
            "measured nothing from one whose measurements are simply elsewhere. Null "
            "too on a manifest written before this was recorded."
        ),
    )
    rank_version: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "The scoring shape this run published under, as `idhazh.rank.RANK_VERSION` "
            "spells it. A published order that moved for a reason nobody recorded is a "
            "published order nobody can defend, and until this field existed the "
            "constant was read by nothing. Null on a manifest written before this was "
            "recorded, which is unknown rather than a claim about which shape ran."
        ),
    )

    config_digests: list[ConfigDigest] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _drop_retired_keys(cls, data: Any) -> Any:
        """Read-side migration for `pipeline_fingerprints`, removed 2026-09-13T22:00.

        Delete this when `git grep -l pipeline_fingerprints -- frontend/public/digest`
        returns nothing. That may never be true: all 23 committed `run.json`
        files carry the key and a published day is never rewritten, so the
        condition is written down as a fact somebody can check rather than as a
        date somebody guessed.
        """
        return without_retired_keys(data, "pipeline_fingerprints")

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
            version="2026-09-15T12:30",
            change="The embedded draft block's spec_type accepts a third value, draft-mtp.",
            why="It follows models-config, which is where the choice is declared.",
        ),
        ChangelogEntry(
            version="2026-09-14T07:00",
            change="The embedded ModelRef gained an optional draft block.",
            why="A run records the draft weights it used, or a later reader cannot repeat it.",
        ),
        ChangelogEntry(
            version="2026-09-14T06:00",
            change="The embedded ModelRef gained an optional byte_count.",
            why="It follows models-config, which is where the size is now declared.",
        ),
        ChangelogEntry(
            version="2026-09-14T04:00",
            change="inputs.turn_markers_sha256, optional: the turn envelope the prompts used.",
            why="A moved marker renders a prompt with no turn structure and raises nothing.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    date: DateStamp
    runs: list[RunRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def _runs_are_append_only_and_addressed_by_date(self) -> Self:
        seen: set[str] = set()
        for index, record in enumerate(self.runs, start=1):
            if record.n != index:
                raise ValueError("runs are append-only and numbered from 1 without gaps")
            if not record.run_id.startswith(f"{self.date}-"):
                raise ValueError("run_id must be addressed by this date")
            if record.run_id in seen:
                raise ValueError("two runs of a day cannot share a run_id")
            seen.add(record.run_id)
        return self
