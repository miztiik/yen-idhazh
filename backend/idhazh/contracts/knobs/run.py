"""What one run of the pipeline is allowed to do."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from pydantic import Field, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.knobs.removed import refuse_a_removed_knob


class RunConfig(Model):
    safety_ceiling_per_run: int = Field(
        default=80,
        ge=1,
        description=(
            "What sizes a run. It began as a crash guard against a mis-parsed feed and "
            "supply overtook it: items_planned has been exactly this number on every run "
            "since 2026-08-25, so it is the cap whatever it is called. Owner decision, "
            "2026-09-05: it comes down to 80 from 160 - the day publishes half as many "
            "stories, and the gain is that those 80 slots go to articles worth reading "
            "rather than to a second copy of one already chosen or to a feed that has "
            "been publishing badly. It is an editorial choice about the day now, not a "
            "crash guard. It is also what sizes the worst case a work shard and the "
            "route stage have to finish - a smaller run makes a smaller worst case - and "
            "a worker killed at run.shard_timeout_minutes uploads nothing."
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

    @model_validator(mode="before")
    @classmethod
    def _a_removed_knob_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("run", data, SUPERSEDED_RUN_NAMES)


#: The `run` knobs this block used to carry. Both sized or switched the visual
#: planner stage, which plan 11 row #6 deleted with the model it ran, so there
#: is no knob answering the same question and the value is empty.
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
