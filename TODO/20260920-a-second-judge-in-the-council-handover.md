# Handover: a second judge in the council

**Last Updated**: 2026-09-20

A research-and-plan brief. **Nothing here is decided.** The deliverable is an
execution-ready plan-doc under `TODO/`, not code.

## The decision that produced this

The merge line now fits itself against judge verdicts
([`docs/architecture/publishing/autotune-content-similarity.md`](../docs/architecture/publishing/autotune-content-similarity.md)).
The owner was asked how the holdout benchmark stays current as content drifts,
and chose: **the pipeline surfaces candidate pairs automatically, and a
different authority labels them.** The rejected option was letting the council
label its own benchmark, because that makes the floor a copy of the line it is
meant to police.

That choice needs a second judge. This brief is the research that has to happen
before anyone writes one.

## Three couplings, and why this is not a nice-to-have

**The judge is the writer.** `ModelRole` has exactly two members today,
`SUMMARIZE` and `VISUAL_PLANNER` (`backend/idhazh/contracts/run_manifest.py`).
There is no judge role. The model that writes every summary is the model that
then reads two summaries and says whether they are one story. The similarity
score is built from title plus summary, so a blind spot in the writer is
invisible to the judge by construction - they are the same weights.

**The floor would become a copy of the line.** The holdout exists to catch the
fitted line when it drifts wrong. Its authority comes entirely from being
labelled by something the fit does not consume. The fit consumes council
verdicts. Label the holdout with council verdicts and the floor can never fire.
It would still render, still look healthy, and mean nothing.

**Judging twice is not a second opinion.** Each pair is judged in both orders -
`verdict` and `verdict_swapped` - and `usable` is true when the two agree. That
is a position-bias control. Same model, same weights, same prompt, temperature
`0.0`. Agreement between them measures order-sensitivity and nothing else, and
it reads like corroboration, which is the trap.

## What exists today

| Thing | Where | State |
| --- | --- | --- |
| The workflow | `.github/workflows/llm-council.yml` | Cron `0 22 * * *`, plus `workflow_dispatch`. Four shards that never confer |
| The judge's model | Inherited from the `summarize` role | No judge role exists to point elsewhere |
| Per-pair output | `verdict`, `verdict_swapped`, `usable`, `first_token_margin`, `judge_model`, `prompt_digest`, `grammar_digest` | Written per pair |
| Run gates | `disagreement_max` `0.15`, `unclear_max` `0.35` | A run past either is not usable |
| Budget knobs | `pair_budget` `200`, `shards` `4`, `judge_shard_timeout_minutes` `200` | In `config/idhazh.json` under `assemble.same_story.adaptive_dedup_threshold` |
| Model registry | `config/models/` | Five entries: two Gemma-4-E4B-QAT variants, `ornith-1.5-9b-q5km`, two Qwen3.5-9B-Q4KM variants |
| The benchmark | `state/story-similarity/holdout-pairs.csv` | 200 labelled pairs. Written only by `backend/utilities/sample_sheet.py`, an operator tool. No pipeline path appends to it |
| The runbook | [`docs/how-to/label-the-similarity-holdout.md`](../docs/how-to/label-the-similarity-holdout.md) | How a sheet is drawn, labelled and harvested |

**The council has never run.** `state/story-similarity/fitted-thresholds/` and
`state/story-similarity/scored-pairs/` each hold one file and both are headers
with zero data rows. Every number below about judging comes from the design, not
from a run, and the first scheduled run is what turns any of it real.

## Measured facts a plan must not contradict

Taken 2026-09-19 on the committed 200-pair benchmark. These are readings, so
re-take them rather than quoting them if the file has moved (Guardrail #10).

- **196 one story, 4 two stories.** The four marked-apart pairs all come from a
  single news cluster - one lake being renamed. That is a thin basis for a floor,
  and widening it is part of what a second judge is for.
- **The labels interleave.** 0.9406 one story, 0.9407 two stories, 0.9409 one
  story. **No single threshold separates the two populations.** The highest
  two-story pair sits at 0.9407 against a floor of 0.94 - a margin of -0.0007.
- **Reading headlines instead of summaries flipped 8 of 12 two-story marks.**
  The score is built from title plus summary; a labeller who reads only
  headlines is not labelling what the score measures.
- **Cost, from the workflow's own note:** 200 pairs judged twice is 400 calls at
  77.6 seconds, which is 8.6 hours of model time across four shards.

## The questions to answer

Answer these in the plan-doc. Each needs a recommendation with its cost named,
not a survey (`CLAUDE.md` section 0c).

1. **Which second model, and what makes it independent?** A different
   quantisation of the same weights is not a second opinion. Name what has to
   differ - family, training data, size - and say how much independence each
   buys. Weigh a registry model against pulling a new one, including download
   and cache cost.
2. **Is one cosine number the wrong instrument?** This is the open question
   nobody has answered, and the interleave above is the evidence for asking.
   "Same event, different actor" may be unanswerable by a single scalar at any
   threshold. Research whether a structured judgement - same event, same actors,
   same day - separates the populations where one number cannot, and price it
   against the simpler fix.
3. **What does disagreement between two judges MEAN?** Tiebreak, veto,
   flag-for-a-person, or a weight. Each implies a different contract and a
   different failure when the two models disagree often. Say which, and what
   happens on the day they disagree about half the pairs.
4. **Does a second judge double the cost?** 400 calls becomes 800 on the naive
   design. The 6 h job timeout is GitHub's and ends the argument (Guardrail #2),
   so a design that does not fit must name what it trades - fewer pairs, a
   smaller model, a shorter context, more shards. Consider spending the second
   model only where it is worth it: pairs near the line, or the ones the first
   judge called unclear.
5. **Swap or second opinion?** Within budget, 400 calls buys the position swap
   OR a second model, not both. Say which is worth more and why. Dropping the
   swap means losing the only position-bias control there is.
6. **What labels the labeller?** If the second judge labels the holdout, the
   same independence argument applies one level up. Say where the regress stops
   and why stopping there is honest.

## Constraints that bind the answer

- **Guardrail #2, the 6 h job.** GitHub kills it. This is a boundary to design
  around, never to argue with. The 1 GB site is the other one. Every other
  number in that guardrail is a cost to price.
- **Guardrail #11, the trust boundary.** Article text reaching a judge prompt is
  the prompt-injection surface, and it is a reader-safety boundary that is not
  adapted. The schema and the sanitizer are the control; prompt wording is not.
- **Guardrail #3 and section 11.** Every persisted shape is a Pydantic model
  under `backend/idhazh/contracts/` before any logic reads it, `schemas/` is
  generated from it, the `version` is a date-stamp, the changelog gets one line,
  and a breaking change ships its read-side migration in the same commit. A
  second judge changes the judgement row and probably `ModelRole`.
- **Guardrail #10.** A number with no hardware, date and spread is an estimate
  and says so. An estimate is allowed to settle a decision provisionally when it
  names the measurement that would overturn it.
- **`CLAUDE.md` section 1a.** LLM-as-judge is primary evaluation here. A model
  verdict may run in production and may determine publication. Nothing in this
  brief needs a non-goal waiver.
- **The mantra.** Content quality decides this project's future. Where a choice
  trades a wrong merge against a missed merge, publish less.

## Who rules what

`CLAUDE.md` section 14 assigns these, and the split is what settles a stall.

- **Andre** owns whether a model is good enough, the prompt and schema shape,
  and which instrument measures a quality failure.
- **Carmack** owns whether it fits the runner - quantisation, throughput, shard
  economics, the job timeout - and the process boundary no model output crosses.
- **Editor** names the content failure; Andre chooses the instrument for it.
- **Fowler** owns the persisted contract and the test tiers.

A veto must name what the reader loses.

## Deliverable

An execution-ready plan-doc under `TODO/`, written with the `prepare-plan`
skill, that an autonomous agent can run end to end. Every row names its files,
its tests and the thing it must not do. Open questions stay in that plan-doc,
not in `docs/` and not here.

Delete this handover when that plan-doc exists.

## See also

- [`docs/architecture/publishing/autotune-content-similarity.md`](../docs/architecture/publishing/autotune-content-similarity.md) - the merge line, its rationale and the alternatives already rejected.
- [`docs/how-to/label-the-similarity-holdout.md`](../docs/how-to/label-the-similarity-holdout.md) - how the benchmark is drawn and labelled today.
- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - where LLM-as-judge sits in this project.
- [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - Guardrail #12's escape hatch, which a pair-harvesting path will meet.
