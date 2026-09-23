# Glossary

**Last Updated**: 2026-09-22

The words this project uses for its own machinery, and where each one is defined.

> A **run** turns the pipeline once. It plans **items**, splits them into
> **shards**, and each shard writes a **segment** into the day it records.
> Segments are what a **ledger** is made of, and a ledger is the only memory the
> next run has. A
> **trial run** does all of that with its ledgers off to one side.

That paragraph is the whole machine in four sentences. The table below is for
arriving with one word and wanting the page that owns it.

[taxonomy.md](taxonomy.md) is the sibling of this page and owns the other half
of the vocabulary: the words this project puts on a **story** - vertical, desk,
lens and event. They are not repeated here.

## This page is an index, not a second definition

A word here carries one line and a link. **The link is the definition; this page
is the way in.** A row that grows into a paragraph has started duplicating the
page it points at, and duplication of a term defined elsewhere is the one thing
the concept tier forbids ([../reference/documentation-structure.md](../reference/documentation-structure.md)).

Some words had no written definition anywhere when this page was made - they
lived in a docstring or a field description and nowhere else. Those rows point
at the code, because that is where the definition genuinely is. Moving one into
a doc is a fine change to make; moving it into *this* page is not.

## The words

| Word | What it means | Defined in |
| --- | --- | --- |
| **bench** | One `measure.yml` dispatch that measures a model's raw speed and latency, before any question about its quality | [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md); the knobs are the `bench` block in [config.md](config.md) |
| **canary** | One of five planted prompt-injection attacks, run against the model to prove the sanitizer holds. The **canary day** is a published day built from them, so the browser suite can attack a real page instead of a fixture | `backend/idhazh/stages/qualify_canaries.py`, `backend/utilities/build_canary_day.py` |
| **candidate** | A model being judged before it may replace the one in use | [qualification.md](qualification.md) |
| **compaction** | The `compact` stage. Once a day is closed it folds that day's segments into one `settled.csv` and deletes them, which saves files and changes no answer | `backend/idhazh/stages/compact.py` |
| **council** | The nightly workflow where models judge borderline same-story pairs and fit the merge line | [../architecture/publishing/llm-council.md](../architecture/publishing/llm-council.md) |
| **dispatch** | A workflow run somebody started by hand, rather than one the schedule started | [../reference/github-actions.md](../reference/github-actions.md) |
| **drift gate** | The check that regenerates the schemas and the frontend types from the Pydantic models and fails if what is committed differs | [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) |
| **fold** | One of the four retention policies: keep the durable total, drop the per-item grain. Compaction uses the same word for what it does to a closed day | [adaptive-pruning.md](adaptive-pruning.md) |
| **holdout** | Labelled pairs kept out of fitting, so a fitted threshold is scored against something it has never seen | [../how-to/label-the-similarity-holdout.md](../how-to/label-the-similarity-holdout.md) |
| **item** | One source URL and everything derived from it. The atom of the whole system | [pipeline-loop.md](pipeline-loop.md) |
| **ledger** | A committed file under `state/` that one run writes so a later run can read a fact it found. The pipeline has no memory of its own: every run starts on a fresh machine with a fresh checkout | `backend/idhazh/ledger.py` |
| **partition** | One file holding one period of a collection that grows. The directory is the collection and the filename says the period | [partitions.md](partitions.md) |
| **qualification** | The gates a candidate model must clear before it may be adopted, and what clearing them proves | [qualification.md](qualification.md) |
| **run** | One turn of the pipeline. The schedule turns it five times a day | [pipeline-loop.md](pipeline-loop.md) |
| **scratch config** | A copy of `config/` with the model pointer moved, so a candidate can be measured without editing the committed tree. Two keys may differ and no third | `backend/utilities/candidate_pointer.py` |
| **seen store** | The ledger that answers "how old is this?" for an article whose feed carried no date | [pipeline-loop.md](pipeline-loop.md) |
| **segment** | The rows one writer commits, at `state/<ledger>/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv`. Two writers never share a filename there, so a lost push race cannot stack two copies of a row | `backend/idhazh/ledger.py`, `backend/idhazh/day_shards.py` |
| **shard** | The batch of items handed to one worker, so a day's work runs in parallel. `run.shard_size` is URLs per worker | `backend/idhazh/contracts/knobs/run.py` |
| **span** | One timed operation in the telemetry tree | [telemetry.md](telemetry.md) |
| **span rollup** | A month of spans folded to one row per date, run, shard and span name | [telemetry.md](telemetry.md) |
| **stage** | One step of the loop, invocable on its own with a file in and a file out | [pipeline-loop.md](pipeline-loop.md) |
| **trial run** | A run that takes production's exact code path and writes its ledgers to `state/<name>/` instead of `state/`, so it can never be read as a published day. `retention.trial_state_days` is what empties it again | `backend/idhazh/contracts/knobs/run.py`, the `run.trial_state_dirname` field |
| **work order** | One URL that survived deduplication and was chosen for the day. It is `PlannedItem` in code, and nothing but this row calls it a work order | `backend/idhazh/contracts/run_plan.py` |

## Design rationale

**A glossary looks like the register Guardrail #4 forbids, and is not one.**
That guardrail bans a standalone record of a *decision*, because a decision
filed away from the thing it governs is read by nobody. This page files no
decision and defines almost nothing. It answers a question no other page
answers - "I met this word, where do I go?" - which the routing table in
[../agents/bootstrap.md](../agents/bootstrap.md) cannot answer, because that
table routes by what you are changing and a reader holding a strange word does
not yet know what they are changing.

**The one-line-and-a-link rule is what keeps it from rotting.** A register rots
when it becomes the easier place to write. Held to a pointer, this page has
nothing to drift from: if a row disagrees with the page it links to, the row is
wrong and the fix is one line.

**Why the machinery words needed this and the story words did not.** The words
put on a story already had an owner page ([taxonomy.md](taxonomy.md)) because a
model is told what each one means, so they had to be written down to be useful.
The machinery words never got that forcing function. When this page was made,
`shard`, `segment`, `ledger`, `canary`, `work order` and `trial run` had no
definitional sentence anywhere in `docs/` - each lived in one docstring, found
only by somebody who already knew which file to open.

## See also

- [taxonomy.md](taxonomy.md) - the other half: the words put on a story.
- [pipeline-loop.md](pipeline-loop.md) - the stages the machinery words describe.
- [partitions.md](partitions.md) - how a growing collection is laid out on disk.
- [../reference/documentation-structure.md](../reference/documentation-structure.md) - which page a new statement belongs on.
