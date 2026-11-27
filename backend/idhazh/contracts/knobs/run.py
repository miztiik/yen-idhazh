"""What one run of the pipeline is allowed to do."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, Slug
from idhazh.contracts.knobs.removed import refuse_a_removed_knob


class RunConfig(Model):
    safety_ceiling_per_run: int = Field(
        default=80,
        ge=1,
        description=(
            "What one run may hand the workers. It protects a worker from its own "
            "timeout: this number sizes the worst case a work shard and the route "
            "stage have to finish, and a worker killed at run.shard_timeout_minutes "
            "uploads nothing, so the items it held are lost. It is a guardrail and it "
            "only ever refuses - it never chooses content, ranks it, or reorders it. "
            "It began as a crash guard against a mis-parsed feed and supply overtook "
            "it: items_planned has matched this ceiling on every run since "
            "2026-08-25. The configured value is in config/idhazh.json. What it is "
            "NOT is a bound on the day - use safety_ceiling_per_day for that, "
            "configured in the same file."
        ),
    )
    safety_ceiling_per_day: int = Field(
        default=640,
        ge=1,
        description=(
            "What the whole day may publish, across every run of it. The configured "
            "value is in config/idhazh.json. A guardrail like its neighbour - it only "
            "ever refuses, and a day under it is untouched. It counts what earlier "
            "runs of this date actually put in front of a reader, so a run that failed "
            "to publish costs the day nothing. Lowering it is an editorial decision "
            "about how long a day should be, and it is the maintainer's."
        ),
    )
    shard_size: int = Field(
        default=5,
        ge=1,
        description=(
            "URLs per worker VM. Set by measured model-load amortization, not by "
            "taste. It does not decide the fan-out on its own and has not since the "
            "run ceiling came down: the fan-out is "
            "min(ceil(safety_ceiling_per_run / shard_size), max_parallel), so this "
            "setting changes the shard size only when it limits that calculation. "
            "The committed settings are in config/idhazh.json. Re-derived on "
            "2026-09-14 against the two-span item; a worker carrying more items is "
            "the opposite of what a longer item wants."
        ),
    )
    max_parallel: int = Field(
        default=8,
        ge=1,
        description=(
            "The most workers a run may derive for itself. The workflow supports "
            "the configured width for scheduled runs and bounds the manual choices."
        ),
    )
    shard_timeout_minutes: int = Field(
        default=200,
        ge=1,
        description=(
            "The work job's own timeout, which digest.yml reads from config/idhazh.json. A backstop, "
            "never a budget: a worker has no clock of its own, and one killed at this "
            "bound uploads nothing, so the run loses every item that worker held. It "
            "was increased as headroom for a planned second model call per item, "
            "not because any worker got slower. The pipeline has made one call per "
            "item since 2026-11-17, and the timeout was not lowered with it. It is "
            "sized from the worst measured shard, not the median; the measurements "
            "are documented in docs/reference/pipeline-cost.md. A slow worker is "
            "still answered by lowering safety_ceiling_per_run, never by raising "
            "this."
        ),
    )
    shard_wrap_up_minutes: int = Field(
        default=12,
        ge=0,
        description=(
            "How much of shard_timeout_minutes the worker keeps back for itself, so "
            "it stops on its own clock instead of being killed on the platform's. A "
            "worker killed at shard_timeout_minutes uploads nothing, so every item it "
            "had already finished dies with the ones it had not started: on 2026-09-15 "
            "two of four shards went that way and the day published 66 stories against "
            "a plan of 80.\n\n"
            "What the worker does with it: once the time left is less than the slowest "
            "item this shard has already finished, it starts no more. That needs no "
            "estimate and calibrates itself to whichever processor the shard drew, "
            "which is worth 24 percent between an EPYC and a Xeon. This reserve covers "
            "what happens after the last item - writing the records, the manifest, and "
            "the artifact upload. It is the one number here that is not derived: raise "
            "it if an upload is ever cut off, and never lower it to fit one more story."
        ),
    )
    success_floor_pct: int = Field(
        default=70, ge=0, le=100, description="Below this, the run additionally opens an issue."
    )
    trial_state_dirname: Slug | None = Field(
        default=None,
        description=(
            "Where a trial run's ledgers go, under `state/`. Null is production and is "
            "the default, so a run that says nothing writes where it always did. Set it "
            "and every day shard this run appends lands under `state/<name>/`, or under "
            "`state/<name>/<case>/` when `run.trial_case_dirname` is set - the seen "
            "ledger, feed health, item health, the published ledger, the traces and the "
            "rollups, all of them, because a run that split them would put half a trial "
            "in the published series. Maintainer decision, 2026-09-15: a run that "
            "exists to exercise production's code path must not be readable as a "
            "production day. The gardener's trials task is what empties it again."
        ),
    )
    trial_case_dirname: Slug | None = Field(
        default=None,
        description=(
            "A separately validated child under `run.trial_state_dirname`. Null keeps "
            "the trial root itself, as the bench does. A case name without a trial "
            "root is refused, and a configured case is appended only below that root."
        ),
    )
    @model_validator(mode="after")
    def _a_trial_case_requires_a_trial_root(self) -> Self:
        """A case slug is meaningful only below an explicitly named trial root."""
        if self.trial_case_dirname is not None and self.trial_state_dirname is None:
            raise ValueError(
                "run.trial_case_dirname requires run.trial_state_dirname"
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def _a_removed_knob_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("run", data, SUPERSEDED_RUN_NAMES)


#: The `run` knobs this block used to carry. Three sized or switched the visual
#: planner stage, deleted with the model it ran, so there is no knob answering
#: the same question and the value is empty.
#: `route_budget_minutes` is the older spelling of the budget and is refused
#: here rather than migrated: it used to be read as `visual_planner_budget_minutes`,
#: which would now migrate an operator's number onto a key nothing reads.
#: The judging shard's bound is the fourth and it did not die - it moved out of
#: this block entirely, so its replacement is spelled as a whole path.
#: `settled_fold_after_days` is the fifth. It moved to the gardener's closed-day
#: fold, and the fold went with the CSV day trees it settled, so nothing
#: replaces it.
SUPERSEDED_RUN_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "judge_shard_timeout_minutes": "council.shard_timeout_minutes",
        "route_budget_minutes": "",
        "settled_fold_after_days": "",
        "two_calls_per_item": "",
        "visual_planner_budget_minutes": "",
    }
)
