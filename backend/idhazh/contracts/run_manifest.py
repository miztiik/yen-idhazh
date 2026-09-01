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
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.app_config import ModelRef
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
)


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
    items_routed: int = Field(
        default=0, ge=0, description="Items the router reached. Zero when the route job died."
    )
    items_prefiltered: int = Field(
        default=0,
        ge=0,
        description=(
            "Items the router decided without asking the model, because no enabled "
            "visual kind could survive the checks. Counted separately so a chart rate "
            "is never quoted against items_routed alone."
        ),
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
    charts_drafted: int = Field(
        default=0,
        ge=0,
        description=(
            "Items whose routing reply asked for a chart, whatever the decision became. "
            "Subtract the day's published charts and the remainder is what the "
            "post-model checks rejected - the only number that separates a model that "
            "does not want charts from checks that refuse the ones it wants. Zero on a "
            "manifest written before it existed."
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
            version="2026-09-01T12:00",
            change="Added optional rank_version to a run.",
            why=(
                "`idhazh.rank.RANK_VERSION` says which scoring shape decided the "
                "published order, and its own comment says an order that moved for "
                "a reason nobody recorded is an order nobody can defend. Nothing "
                "read the constant, so no run had ever recorded it and a bump would "
                "have recorded nothing. This is the wiring on its own: no scoring "
                "behaviour changes in this commit and the value written is the "
                "constant already in the tree. Null on every manifest written "
                "before today - 11 days when this landed, 2026-09-01 - and null "
                "reads as unknown, never as a claim that some particular shape ran "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31",
            change=(
                "run_id is the execution's own identity and no longer restates n. "
                "A record is still numbered from 1 without gaps and still addressed "
                "by the date, and no two records may share a run_id."
            ),
            why=(
                "n was read off the last committed manifest, and actions/checkout "
                "pins a job to the commit its run was triggered at - so a run that "
                "starts while another is still working reads a manifest that has "
                "never heard of it and counts the same number. On 2026-08-29 two "
                "runs did: 33270983446 dispatched at 19:29 and 33274853468 "
                "scheduled at 20:58 both derived 2026-08-29-3, and the ledgers keyed "
                "on that string ended up with six counter rows for four shards and "
                "44 repeated item-health keys. Summed naively that run's reading "
                "clock read 19,305.8 seconds against 11,810.3 - 63 percent high. The "
                "id now comes from the CI run, which GitHub allocates and no second "
                "execution can reproduce, and the day's ordinal stays on n where it "
                "was always the thing being asked for. Every committed manifest "
                "still validates: <date>-<n> is addressed by the date and unique "
                "within a day, so this relaxes the rule rather than breaking it."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T16:00",
            change=(
                "Added optional evaluation_enabled, evaluation_sample_rate, "
                "evaluation_sampled and scorer_version to a run."
            ),
            why=(
                "The faithfulness scorer is now sampled by run, so a day with no eval "
                "rows has four possible causes - switched off in config, not drawn at "
                "the rate, the weights would not load, or the run never reached the "
                "scorer - and an absence in state/scores.csv looks the same for all "
                "four. The rate lands here rather than on EvalRow because the unit "
                "sampled is the run: every row of a run shares one rate, so one cell "
                "per run says everything a per-row column would, and no persisted "
                "ledger widens. All four are nullable and default to null, because an "
                "older manifest does not know what it was configured to do and a "
                "concrete default would invent the answer - the same rule the "
                "observability block states as an empty cell is never a zero."
            ),
        ),
        ChangelogEntry(
            version="2026-08-28",
            change="The embedded ModelRef gained an optional hf_base_repo.",
            why=(
                "A manifest embeds the whole model entry, so a field added there lands "
                "here whether or not this document wanted it - the same way the optional "
                "revision did on 2026-08-26. Nothing a run writes changes and no manifest "
                "needs migrating; the emitted schema gained one optional property, and a "
                "stale schema fails the drift gate."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T11:00",
            change="site_bytes and site_files now say which tree they measure.",
            why=(
                "They always held the committed payload tree, and this document said they "
                "measured the ceiling. Measured 2026-08-27, that tree was 7,027,075 bytes "
                "while the published site was 128,064,853 - eighteen times larger. A field "
                "that reads as the site cap and holds a tree eighteen times smaller is how "
                "the alarm came to watch the wrong thing. No value changed and no payload "
                "needs migrating; only the description did."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T20:00",
            change="The embedded ModelRef gained an optional revision.",
            why=(
                "A manifest says which model ran. Until now it could not say which upload "
                "of that model, because the weights were fetched from a branch. The "
                "reason for the field is on the app-config schema; this entry exists "
                "because the manifest embeds the same shape and its own document changed "
                "with it. Optional, so every published manifest still validates "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25",
            change="Added optional charts_drafted to a run.",
            why=(
                "On 2026-08-25 the router drafted 17 charts and published 9, and no "
                "committed row said where the other 8 went. Without the drafted count a "
                "model that stops asking for charts and a set of checks that starts "
                "refusing them look identical, so the chart arm's kill line cannot be "
                "read from anything the run leaves behind. Defaults to zero on a "
                "manifest written before it existed."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T23:10",
            change="Added optional items_prefiltered to a run.",
            why=(
                "The router now decides an item without asking the model when no enabled "
                "visual kind could survive its own checks. Counting those separately keeps "
                "the denominator honest: after the gate the same charts sit over a much "
                "smaller routed set, so a chart rate quoted against items_routed alone "
                "would climb without a single extra chart existing. Defaults to zero on a "
                "manifest written before it existed."
            ),
        ),
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
