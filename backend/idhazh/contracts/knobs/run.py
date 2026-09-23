"""What one run of the pipeline is allowed to do."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, Slug
from idhazh.contracts.knobs.removed import refuse_a_removed_knob


class RunConfig(Model):
    settled_fold_after_days: int = Field(
        default=7,
        ge=1,
        description=(
            "How many days behind the run's own date a day has to be before its "
            "writer files are folded into one settled file. Every job writes its "
            "own file under the day its rows name, which is what stops two jobs "
            "conflicting - and it leaves about a hundred small files in a busy "
            "day. Folding a day nobody will write again costs nothing and changes "
            "no answer, because a reader settles the rows either way. Seven days "
            "rather than one, because a day can still gain rows: a re-run reaches "
            "back, and a shard that died can be re-dispatched. Raise it if a late "
            "writer is ever seen landing in a folded day; lower it only to save "
            "files, and it saves none the day after it is lowered."
        ),
    )
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
            "docs/reference/pipeline-cost.md."
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
    push_deadline_seconds: int = Field(
        default=300,
        ge=1,
        description=(
            "How long a job may keep trying to push what it already committed. The "
            "loop was three attempts, and a fixed count is spent at once however high "
            "it is set once several runs commit together - an optimistic "
            "rebase-and-push converges at any commit rate and a counter does not. "
            "300 s is 25 percent of the assemble job's 20-minute timeout: measured on "
            "run 35701213155, that job used 1.8 of its 20 minutes, so 18.2 minutes "
            "were spare. The work shard does not read this number. Its commit step "
            "names 120 s in its own env block, because the whole of what it keeps back "
            "for everything after its last item is shard_wrap_up_minutes, which is 12 "
            "minutes - 300 s would be 5 of them. What would move this is the "
            "`push attempt` record the loop publishes, over twenty runs: a first-push "
            "success rate above 95 percent means the deadline is almost never spent "
            "and the number can rise, and below 80 percent means no deadline is the "
            "right answer for what is going wrong."
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
    qualification_repeats: int = Field(
        default=3,
        ge=3,
        le=10,
        description=(
            "How many times a qualification shard replays each item. Three is the "
            "smallest count that separates a model that is deterministic from one that "
            "happened to agree twice, and it is the floor rather than the default "
            "because a report built on fewer passes is a report that cannot fail. It "
            "used to be a dispatch input an operator typed per run, where `1` was legal "
            "and nothing downstream could refuse it. Ten is the ceiling because that is "
            "past any determinism question; a run that wants more edits this field. "
            "`idhazh qualify --repeats` overrides it for one invocation and is refused "
            "on the same floor."
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


#: The `run` knobs this block used to carry. Three sized or switched the visual
#: planner stage, deleted with the model it ran, so there is no knob answering
#: the same question and the value is empty.
#: `route_budget_minutes` is the older spelling of the budget and is refused
#: here rather than migrated: it used to be read as `visual_planner_budget_minutes`,
#: which would now migrate an operator's number onto a key nothing reads.
#: The judging shard's bound is the fourth and it did not die - it moved out of
#: this block entirely, so its replacement is spelled as a whole path.
SUPERSEDED_RUN_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "judge_shard_timeout_minutes": "council.shard_timeout_minutes",
        "route_budget_minutes": "",
        "two_calls_per_item": "",
        "visual_planner_budget_minutes": "",
    }
)
