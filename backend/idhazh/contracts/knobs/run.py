"""What one run of the pipeline is allowed to do."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

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
            "it: items_planned has been exactly this number on every run since "
            "2026-08-25. Owner decision, 2026-09-05: 80, down from 160. What it is "
            "NOT is a bound on the day - the day runs five times, so 80 here publishes "
            "about 400. safety_ceiling_per_day is the one that answers that."
        ),
    )
    safety_ceiling_per_day: int = Field(
        default=400,
        ge=1,
        description=(
            "What the whole day may publish, across every run of it. The per-run "
            "ceiling could never answer this: the day runs five times, so anybody "
            "reading 80 and picturing an 80-item day is wrong by a factor of five. "
            "A guardrail like its neighbour - it only ever refuses, and a day under it "
            "is untouched. It counts what earlier runs of this date actually put in "
            "front of a reader, so a run that failed to publish costs the day nothing. "
            "The default is the arithmetic of the design that already ships - five "
            "runs at safety_ceiling_per_run - so turning it on changes no day that has "
            "ever been published and only refuses a runaway. Lowering it is an "
            "editorial decision about how long a day should be, and it is the owner's."
        ),
    )
    shard_size: int = Field(
        default=5,
        ge=1,
        description=(
            "URLs per worker VM. Set by measured model-load amortization, not by "
            "taste. It does not decide the fan-out on its own and has not since the "
            "run ceiling came down: the fan-out is "
            "min(ceil(safety_ceiling_per_run / shard_size), max_parallel), which is "
            "min(16, 4) at the committed numbers, so max_parallel binds and a worker "
            "draws 20 items. Re-derived on 2026-09-14 against the two-span item and "
            "left here: it would have to rise above 20 to move the fan-out at all, "
            "and a worker carrying more items is the opposite of what a longer item "
            "wants."
        ),
    )
    max_parallel: int = Field(
        default=4,
        ge=1,
        description=(
            "The most workers a run may derive for itself. It is four rather than the "
            "eight digest.yml lets an operator dispatch, because eight has never "
            "published a day; the three conditions that would move it are in "
            "docs/reference/measurements.md."
        ),
    )
    shard_timeout_minutes: int = Field(
        default=200,
        ge=1,
        description=(
            "The work job's own timeout, which digest.yml reads from here. A backstop, "
            "never a budget: a worker has no clock of its own, and one killed at this "
            "bound uploads nothing, so the run loses every item that worker held. It "
            "rose to 200 from 150 as headroom for the coming two-call summariser "
            "change, not because any worker got slower - at run.safety_ceiling_per_run "
            "of 80 a worker draws 20 items, half of the 40 it drew before, so the base "
            "work roughly halves. Sized from the worst measured shard, not the median: "
            "over 80 shard rows on 2026-09-02 the worst used 135.4 minutes of the old "
            "150-minute bound and the median used 78.5, and the second model call an "
            "item spends exactly that margin. **Re-derived on 2026-09-14 for the "
            "two-span item and left at 200.** The worst of those 80 rows carried 40 "
            "items, so the worst measured item is 203.1 s; each of the item's two "
            "calls now opens with a 256-token thinking span, which is 42.6 s a span at "
            "the measured 6.01 +/- 0.11 tokens a second (2026-08-23, ubuntu-latest, "
            "EPYC 9V74, llama.cpp b10598, three repeats), so the derived worst item is "
            "288.3 s and a 20-item worker's worst shard is 96.1 minutes. 200 is 56 "
            "percent of the six-hour platform ceiling, well inside Guardrail #2. A "
            "slow worker is still answered by lowering the ceiling, never by raising "
            "this."
        ),
    )
    judge_shard_timeout_minutes: int = Field(
        default=200,
        ge=1,
        le=350,
        description=(
            "How long one judging leg may run before GitHub kills it. 200 minutes is 2 "
            "hours 9 minutes of model time at the day's cap of 200 pairs over 4 legs, plus "
            "71 minutes of headroom against a fixed cost of about 6 minutes for the "
            "checkout, the weights cache restore and the server start. The model time is "
            "derived from 9.85 tokens a second measured on a stock runner on 2026-09-09, "
            "not from a judge call; row 17 measures one and replaces this arithmetic."
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
            "and every day shard this run appends lands under `state/<name>/` instead - "
            "the seen store, feed health, item health, the published ledger, the traces "
            "and the rollups, all of them, because a run that split them would put half "
            "a trial in the published series. Owner decision, 2026-09-15: a run that "
            "exists to exercise production's code path must not be readable as a "
            "production day. `retention.trial_state_days` is what empties it again."
        ),
    )
    # Remove this knob once one qualification has cleared `decide` on the production
    # path; the losing branch goes with it, and `_one_call` stays because the
    # injection canaries are the one caller that wants a single call.
    qualify_on_the_production_path: bool = Field(
        default=True,
        description=(
            "Whether `idhazh qualify` summarizes the way the digest does. True is the "
            "digest's own path: the article is labelled and then summarized, in two "
            "adjacent calls. False is the qualification's own single call, which is "
            "what it did until 2026-09-15 and what every shard before that date "
            "measured. True by default because a gate that clears a call path nothing "
            "publishes has cleared nothing, and the switch exists so a run that goes "
            "wrong on it can be put back without a code change. Moving it moves every "
            "per-item number in a shard, so `QualificationShard.calls_per_item` records "
            "which side produced one."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _a_removed_knob_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("run", data, SUPERSEDED_RUN_NAMES)


#: The `run` knobs this block used to carry. Both sized or switched the visual
#: planner stage, deleted with the model it ran, so there is no knob answering
#: the same question and the value is empty.
#: `route_budget_minutes` is the older spelling of the budget and is refused
#: here rather than migrated: it used to be read as `visual_planner_budget_minutes`,
#: which would now migrate an operator's number onto a key nothing reads.
SUPERSEDED_RUN_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "route_budget_minutes": "",
        "two_calls_per_item": "",
        "visual_planner_budget_minutes": "",
    }
)
