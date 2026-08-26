# Config

**Last Updated**: 2026-08-26

Where tunable behaviour lives, and the rule that separates a knob from an identifier. Config-driven with sane defaults is a project principle ([principles.md](principles.md), Rule #6): a fresh clone runs on the defaults, and no threshold, cap or source list is hardcoded in code.

## What `config/` is

`config/` holds **human-edited, schema-validated tunable knobs**. Both sides read it: `backend/` at build time, and `frontend/` wherever a published surface needs one. Every config file conforms to a typed model in `backend/idhazh/contracts/` before the logic that reads it exists, and to the schema generated from it ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)). A config file that fails its schema fails the build (`CLAUDE.md` section 1a).

Config is a **persisted contract like any other**: it is version-stamped and changelogged, and a breaking change ships with its read-side migration in the same commit (`CLAUDE.md` section 11). A knob is not exempt from the contract discipline just because a human types it.

## What belongs in a knob

The test is simple: **would a reasonable operator ever want a different value without changing behaviour that is a fact rather than a preference?**

Knobs, by the surface they tune:

- **Sources** - which feeds or listings are consulted, and the filters a candidate link must survive.
- **Extraction** - the truncation cap, the retry budget, backoff, what counts as an oversized body, shape-signal thresholds, shape enforcement switches, and paywall fallback markers.
- **Model** - which model reference and quantisation, the context size, thread count, and the sampling parameters that pin determinism.
- **Summarize** - the length bands, title range, key-point range and quote cap.
- **Evaluation** - the confidence band thresholds, the truncation-gap threshold, the brief compression ceiling, the word gate, and the spot-check sample size ([evaluation.md](evaluation.md)).
- **Run shape** - the safety ceiling, the batch size, per-job timeouts, and concurrency ([pipeline-loop.md](pipeline-loop.md)).
- **Retention** - the image age window, the dry-run switch, the deletion fuse, and the published-site alarm point ([../architecture/publishing/layout.md](../architecture/publishing/layout.md)).
- **Drift** - the alert thresholds and the schedule ([evaluation.md](evaluation.md)).
- **Logging** - the level, and which events emit ([telemetry.md](telemetry.md)).
- **Console** - the telemetry viewport's default window, today anchor, pan step,
  zoom factor, minimum denominator for rate bars, and chart height.

These are the *surfaces*, not a field list. The field-level truth is `schemas/app-config.schema.json`, generated from the model - read it there rather than restating it here, because a list copied into prose is a list that goes stale.

The knobs are spread across four files rather than one, along the line of who edits them and how often: `config/idhazh.json` for behaviour, and `config/taxonomy.json`, `config/sources.json` and `config/watchlist.json` for the source model ([../architecture/sources/discovery.md](../architecture/sources/discovery.md)). Curating a feed list and tuning a threshold are different activities with different review cadences, and putting them in one file means every feed addition touches the file that also holds the decoding parameters.

Every knob ships a sane default. The only values with no default are the model references, because there is no honest default for "which weights" - a wrong guess would silently run the wrong model rather than failing. A reference names the repository, the file, and the `revision` those bytes were uploaded in; the revision is what makes the recorded `sha256` mean anything, because a download that named a branch would get whatever was uploaded last. No workflow keeps a copy of any of it: `digest.yml`, `measure.yml` and `validate.yml` each read `models.summarize` and `models.route` from here and republish them as job outputs, including into the weights cache key ([../reference/github-actions.md](../reference/github-actions.md)).

Extraction has three shape and access control groups:

- `extract.prose_sentence_min`, `extract.prose_sentence_words_min`,
  `extract.prose_line_count_min` and `extract.prose_line_ratio_min` decide when
  text carries `not_prose`.
- `extract.boilerplate_ratio_max` decides when sibling-shared lines carry
  `boilerplate`.
- `extract.paywall_markers` is the fallback when JSON-LD does not declare a
  paywall.

Two enforcement switches default to false: `extract.reject_not_prose` and
`extract.reject_boilerplate`. False means record the signal and publish. True
means reject the item as a listing. `extract.min_source_words` now marks the
brief tier. It does not reject the item.

The brief floor is derived, not chosen: `extract.min_source_words` is
`summarize.bands[0].target_words_min / evaluation.brief_compression_ceiling`.
With the defaults, that is `30 / 0.5 = 60`. An `AppConfig` validator refuses a
config where the three values disagree.

`config.summarize.bands` starts with the brief band `{0, 30, 45}`. The next band
starts at 60 words. `evaluation.summary_words_min` is 25, so the decoder's
summary floor is 125 characters. `evaluation.brief_compression_ceiling` is 0.5;
it caps `verbatim_run` for brief items and derives the floor above.
`evaluation.lead_coverage_min` is 0.30; a miss below it caps `high` at `medium`.
That lets a brief stop naturally instead of padding toward the old 40-word gate.

`config.sources` can declare `form: "abstract"` on a feed. That is a curator's
fact about the feed, not a detector over page text. NBER uses it; arXiv and SSRN
should use the same field if those feeds are added.

`collect.blocked_url_markers` is a list of case-insensitive substrings that keep
an address out of the candidate pool. It defaults to empty, because the entries
are a source-curation decision and belong in `config/` rather than in the
contract (Rule #6). What it is for, and why the control cannot live at the
faithfulness score, is
[../architecture/sources/discovery.md](../architecture/sources/discovery.md).

## Runtime sweep surface

`models.inference` holds both the ordinary deterministic decode knobs and the
flag-sweep knobs. The sweep surface is explicit so a measurement changes one
thing at a time through config, not through workflow literals:

- `n_ctx`, `n_threads`, `n_batch`, `n_ubatch`
- `n_parallel`, `n_threads_batch`
- `startup_warmup`
- `metrics`
- `flash_attention`
- `load_mode`
- `cache_type_k`, `cache_type_v`
- `priority`, `poll`
- `temperature`, `top_p`, `seed`, `thinking`, `max_output_tokens`
- `request_timeout_minutes`

`metrics` is on by default and emits `--metrics`, which makes llama-server
publish its counters on `/metrics`. Two of them are what a run is read by:
`llamacpp:n_tokens_max` is the highest context the server ever saw, so it says
how close the day came to `n_ctx`; `llamacpp:n_busy_slots_per_decode` is the
average number of slots busy per decode, so it says whether batching happened at
all. Without the second, a concurrency measurement that shows no gain cannot
separate "more slots did not help" from "more slots were never used". The
endpoint is llama-server's own loopback surface inside a CI job. No reader
reaches it, so Rule #1 is untouched. `digest.yml` reads it once at the end of
each `work` job and keeps the raw body in that shard's runtime artifact.

`n_parallel: null` and `n_parallel: 1` are not the same runtime. `null` omits
`-np`, so llama.cpp picks its own slot count and reports unified KV; any
explicit value passes `-np` and turns unified KV off. The context each request
gets is unchanged at `n_parallel: 1`, because non-unified KV divides `n_ctx` by
`n_seq_max` and `n_seq_max` is then 1. Source: llama.cpp `common/arg.cpp` and
the `-kvu` help text, read 2026-08-25; both behaviours appear in the run logs
recorded at [../reference/measurements.md](../reference/measurements.md).

**`n_parallel` above 1 is settled and dead.** Measured 2026-08-25 on a
GitHub-hosted `ubuntu-latest` (AMD EPYC 9V74, 4 vCPU, 15 GB), three repeats:
aggregate decode rises **1.055x** from one sequence to two, spread 0.022,
against a pre-registered 1.4x gate. Decode is 36.8 percent of model time, so
that is about 1.9 percent of a run's wall-clock. Four sequences reach 1.133x and
oversubscribe the 4 vCPU, so no level on this runner clears the gate. The knob
stays, because `null` and `1` still differ and both are in use - but no value
above 1 is a candidate here, and sweeping it again needs new hardware or a new
runtime, not a repeat
([Parallel decode on 4 vCPU](../reference/measurements.md#parallel-decode-on-4-vcpu)).

No sweep flag is adopted merely because the knob exists. A candidate becomes the
runtime only after a runner measurement records hardware, date and spread in
[../reference/measurements.md](../reference/measurements.md).

### Current run-shape gap

`run.shard_size` and `run.max_parallel` are enforced from 2026-08-26:
`digest.yml` derives the worker count from the planned day as
`min(ceil(items / run.shard_size), run.max_parallel)`. That is the automatic
path; an operator dispatching the workflow names a count instead, up to the
eight the workflow's own guard allows. `run.shard_timeout_minutes`
is still read by nothing in `digest.yml`, which sets the work job to 330 minutes.
Treating a worker as 150 minutes is therefore still false when sizing a model.
Treating a worker as five items is also still false, for the opposite reason:
`shard_size` decides how few workers a small day is worth, and a full day at the
ceiling gives a worker 40 items. A model adoption measures the actual worker
population.

## Console surface

The console knobs are:

- `console.default_window_days`
- `console.today_anchor`
- `console.pan_days`
- `console.zoom_factor`
- `console.min_window_days`
- `console.max_window_days`
- `console.min_attempts_for_rate`
- `console.chart_height`
- `console.failure_list_max`

The 30-day setting is a viewport. It never deletes rows. `failure_list_max` is
the same idea one level down: the failed-item list shows a page at a time and
offers the rest, so the charts above it stay reachable.

## Reader surface

`ui.items_per_topic` is how many of a topic's stories the all-topics page shows
before it links to the rest. It is a hierarchy knob, never a cap: nothing is
removed, hidden or re-ranked, and the whole topic is one prerendered click away.
A day that ran to a single topic ignores it, because a lone heading over the
whole page states what the page already says.

The `assist` block is on-device search. The runner embeds the day and commits
the vectors; a reader's tab embeds only the query. Both knobs say how much of an
item the encoder is allowed to read, so both are set from what the encoder can
do rather than from taste.

- `assist.max_tokens` (256) is how far into an item's text the encoder reads
  before it truncates. 512 is a hard ceiling because that is the encoder's
  position table, and 256 is the default because that is what the model was
  trained at. This is the one knob here that was moved out of code, and the
  move came with the measurement that says where to leave it: over the 1886
  embedded items of the six committed days, p95 is 217 tokens, p99 is 243 and
  the longest is 280, so 256 reads 99.95 percent of every token published. The
  0.58 percent of items that do run over lose a mean of 13 tokens off the end.
  Raising it would buy that 0.05 percent and re-date every committed vector, so
  it stays. `backend/utilities/token_budget.py` reproduces the sweep, and a test
  fails if a future day's p95 ever climbs above the cap.
- `assist.min_readable_letter_share` (0.5) is how much of an item's alphabet the
  encoder has to know before the item gets a vector at all. The committed
  weights carry an English uncased vocabulary. An item in another script still
  gets a vector out of that encoder - a confident, well-formed one, about which
  characters appeared rather than about the story, which no query a reader types
  will retrieve. Below this share the item gets no vector and the run logs why;
  the item still publishes and still reads normally. Half is a plain reading of
  "mostly not in our alphabet", and the corpus says the exact number does not
  matter: 3 of 1889 items score 0.0 and the next lowest scores 0.9975, so every
  threshold between 0.01 and 0.99 picks the same three items.

The browser keeps its own copy of the token cap in
`frontend/src/lib/assist/loader.ts`, because the config reader is server-only and
a query read further than the items it is matched against is a different
question asked silently. A backend test compares the two and fails when they
separate.

## What is NOT a knob

Not everything variable is tunable. Two categories stay out of `config/`:

- **Facts, not preferences.** The runner's core count, the 6 h job cap and the 10 GB cache ceiling are properties of the platform (Rule #2). Making them configurable would imply they can be chosen.
- **Identifiers.** Stage names, event names, route kinds and score-band names are schema-validated enums defined in the contracts. Code references them; they never change to match a label.

The distinction matters because a value in `config/` reads as an invitation to change it.

## A guard is not a limit, and its name has to say so

Some numbers in `config/` are not there to be tuned. They are there to stop a bug running for six hours, or to say out loud that something has changed. A guard, an alarm and a limit look identical in JSON, so the name and the comment carry the whole difference:

- `run.safety_ceiling_per_run` (160) is a **crash guard**. A normal run is nowhere near it. If a canonicalisation bug ever produces thousands of candidates, the run stops instead of discovering that slowly. Hitting it means find the bug, not raise the number. It replaced a daily item cap, which was a limit pretending to be a guard - see [../architecture/sources/freshness.md](../architecture/sources/freshness.md). It is also the worst case every downstream bound is checked against, which is what decides the number - see [Design rationale](#design-rationale).
- `models.inference.max_output_tokens` (900) is a **crash guard**. It stops a runaway decode from burning a shard's whole timeout. It is not a length target: the length a summary should be is set by the word bands in `summarize.bands`, which is the knob a person actually wants ([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)). It was 250, and at 250 the reply ran out of budget mid-object and failed as a *shape* error - which named the wrong cause and sent the reader of that failure looking at the decoder. It now sits well above any summary we would want.
- `models.inference.request_timeout_minutes` (22.1) is a **per-request guard**. It limits one summarizer POST, not the shard. It protects the day from one local model request that accepts a connection and never replies: that item records `model_unreachable`, and the worker continues. The default is sized from the authoritative runner measurements in [../reference/measurements.md](../reference/measurements.md): the worst 8B long article plus one cold prompt prefix, doubled. `run.shard_timeout_minutes` stays the outer bound for the whole shard.
- `run.route_budget_minutes` (40) is a **stage budget**, and it is the one number here that a person is meant to move. It says how long the route stage may spend before it stops asking the model and leaves the rest of the day unrouted. It is sized *below* the route job's 50-minute timeout on purpose: a job killed at its timeout skips its upload step, so the run loses every decision it had already made rather than the tail it could not reach. The 10 minutes between the two are the fixed cost the stage clock never sees. Measured 2026-08-24/25, the per-item cost is 20.7 s on a fast runner host and 40.3 s on a slow one, so what fits inside the budget changes run to run - which is exactly why the bound is a clock rather than an item count ([../architecture/publishing/visuals.md](../architecture/publishing/visuals.md)).
- `retention.site_budget_mb` (800) is an **alarm**, which is weaker than a guard because it stops nothing. Above it a run logs a warning naming the headroom left, and that is the whole effect: no build fails, and no byte is deleted. The warning rides the run log CI already keeps (section 1b); promoting it to a GitHub issue is a workflow step not yet built. It sits 224 MB below the platform's own 1 GB Pages ceiling, and the size of that gap is the entire design - 224 MB is 26 days of warning at the fastest growth this project has measured, against a 14-day target. The target is a judgement about one maintainer reading one issue, not a measurement, and it is labelled as one where it is derived. The arithmetic, the growth rates it rests on, and why the number is neither 900 nor 600 are in [../reference/measurements.md](../reference/measurements.md#where-the-alarm-fires-and-what-it-buys). Deleting anything is a different knob and ships off: `retention.image_months` is -1 and `retention.dry_run` is true ([../architecture/publishing/layout.md](../architecture/publishing/layout.md)).
- `page_weight.ceilings_bytes` is a **limit**, and the only one on this list. It says how heavy each named prerendered page may be on the wire, gzipped, and `frontend/scripts/bundle-gate.mjs` fails the build above it. Each number is the heaviest of three builds of one tree plus the 64-byte noise floor, and nothing beyond it: a ceiling above today's weight is a gate that never fires, and a ceiling inside its own noise floor is a coin toss. The object is the single source - the `PageWeightConfig` default in the contract is empty, so a number lives here and nowhere else (Rule #6). Only a route whose HTML does not grow with the published data is named: `/404` and `/evals/` today. A day page weighs what the day published, and `/archive/` (it inlines every committed day for the on-device search) and `/console/` (it grows with the ledger its charts read) grow the same way, so a fixed ceiling on any of them would fail on an ordinary publish rather than catch a regression. The gate reports a route the object does not name without failing it, and the class those data-driven routes belong to is covered by the marker count in `frontend/tests/payload-weight.spec.ts`. `/archive/` was capped and then uncapped on 2026-08-26 for exactly this - the ceiling fired on every publish and was raised twice in a day before it was removed ([../reference/measurements.md](../reference/measurements.md#the-prerendered-page-on-the-wire)).

A guard set near the working range is the worst of both. It fires on good runs, gets raised to stop the noise, and stops guarding anything. That is the failure the token cap actually had.

## A knob nothing reads is deleted

A knob that no code path reads is worse than clutter. It reads as a control, so the next person to open the file sizes the system by what the knobs claim - and eventually somebody changes one and waits for an effect that never arrives.

Three were removed this way, each describing a mechanism that does not exist:

- `collect.min_feeds_floor` claimed to be the default feed floor. The floor a vertical is actually held to is its own `min_feeds` in `taxonomy.json`. Nothing read the default.
- A per-feed `weight` on a salience feed. What an aggregator vote is worth is `collect.front_page_bonus`, one number for every aggregator. An aggregator has no subject taxonomy to be graded on, so there was nothing for a per-feed weight to express. **The feed weight on ordinary sources is untouched and load-bearing** - it multiplies the tier score ([../architecture/sources/discovery.md](../architecture/sources/discovery.md)).
- `Sources.live_feeds_for`, a method with no caller that also disagreed with the code doing the job: it honoured `retired_on` and ignored `status`, so it would have read a draft feed. One concept, one home.

### Removing a config field is breaking, and its migration is the file

Deleting a key is a breaking schema change like any other, so it ships a changelog entry and a version stamp (section 11).

The read-side migration is unusual and worth stating once: **for a config contract, the migration is the config edit in the same commit.** No run writes these files - a person does - so there is no back catalogue of old payloads to upgrade. There is one file per contract, and `extra="forbid"` fails loudly and by name if a stale key survives. A migration function would have nothing to migrate.

## Build-time config versus shipped config

Most knobs are read only by the producer and never reach a reader: source lists, model references, batch sizes, timeouts, retry budgets. Shipping those into the published bundle would be dead bytes and a muddled surface.

A knob is shipped **only** when a published surface genuinely needs it - for example, how the dashboard buckets the ledger it renders. When that happens the value is *imported into the bundle at build time*, never fetched at read time: it is tiny, it is needed before the first paint, and fetching it would put a round trip on the critical path for something that cannot change between builds.

## Design rationale

Keeping tunables in schema-validated files rather than in code exists so that tuning the system never requires reading it, and so that a change of threshold is a reviewable one-line diff with a date on it rather than an archaeological dig. Treating config as a versioned contract - rather than as "just a JSON file" - is what stops a silently-renamed key from failing a run at 6 a.m. on a Sunday. Authority: Fowler ([../../.github/agents/fowler.agent.md](../../.github/agents/fowler.agent.md)).

Excluding the runner's ceilings is the less obvious half. They look exactly like knobs and are not: a configurable job timeout invites someone to raise it rather than fix the batch size, which is precisely the reasoning Rule #2 exists to prevent. Authority: Carmack.

**`run.safety_ceiling_per_run` moved from 200 to 160 on 2026-08-26.** A guard is still sized, and this one is sized by the slowest thing that has to finish a full day of it. Two bounds disagreed with 200. An automatic run derives `min(ceil(items / run.shard_size), run.max_parallel)` = four shards, so 200 hands a worker 50 items; against the Qwen3.5-9B candidate that derives to 318 minutes one way and 345 the other, over a 330-minute job timeout that nobody may raise (Rule #2). At 160 the same arithmetic gives 40 items, 254 and 276 minutes, and clears both. The route stage says the same thing from the other side: its measured slow-host capacity is 166 items in a 50-minute budget, so 200 and the router never agreed and 160 does. The largest day ever planned is 149 items, so the move removes nothing a reader has ever had. The lever was the ceiling rather than the timeout, because the timeout is the platform; and rather than the shard count, because `run.max_parallel` is four until the three conditions under [Eight work shards](../reference/measurements.md#eight-work-shards) are met, and `route` is unsharded either way ([../reference/measurements.md](../reference/measurements.md)). Authority: Carmack.

**`run.max_parallel` and the workflow's eight-shard ceiling are different numbers on purpose.** `digest.yml` lets an operator dispatch up to eight workers, and one such run halved the slowest worker. `run.max_parallel` is the most a run derives *for itself*, and it stays at four because no eight-shard day has yet published. The dispatch ceiling is the escape hatch; the config knob is the automatic path a reader depends on, and an unmeasured number may not move that path (Rule #10). Authority: Carmack.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Fetch `config/*.json` from the published site at read time | A round trip on the critical path for about a kilobyte, plus a request that can fail, to load something that never changes between builds. | Carmack |
| Copy config into the published directory at build time | Two copies of one file, free to drift, with nothing gating them. | Fowler |
| Environment variables for pipeline tunables | Invisible in review, unversioned, and undiffable. A knob nobody can see the history of is a knob nobody can trust. | Fowler |
| Put the runner's ceilings in config | They are platform facts, not preferences, and making them editable invites raising the budget instead of simplifying the feature. | Carmack |
| Keeping a dead knob "in case it is wanted later" | It reads as a control. The next person sizes the system by what the knobs claim, and one of them is a lie. | Fowler |
| A daily item cap as the run-shape knob | It decides how many good articles a day may have before knowing what the day contains. The safety ceiling catches the failure a cap was accidentally also catching. | Reader |
| Using `max_output_tokens` as the summary length control | A length set by a token budget fails as a malformed object rather than as a long summary, so the error names the decoder instead of the prompt. | Andre |
| Raising the `work` job's `timeout-minutes` past 330 so a 200-item ceiling fits | The budget is the platform, not a preference (Rule #2). The ceiling is the knob; the timeout is not. | Carmack |
| Leaving the work fan-out a fixed four | It made `run.shard_size` read as configuration and behave as decoration, and it paid the weights restore four times on a day that needed one worker. | Fowler |
| Page ceilings in `frontend/bundle-baseline.json`, beside the JavaScript weights | That file is a record of what the bundler produced and is rewritten whenever it moves. A ceiling is the opposite: a limit a person chose and raises on purpose. Two kinds of number in one file would be edited as one kind. | Fowler |
| Comparing a second build against a second public tree, instead of a ceiling | Nobody costed it, and it doubles the prerender on every pull request. The marker count already answers the same question for a fraction of the work. | Carmack |
| A ceiling on the day pages too | A day page weighs what the day published, so the number would cap the news rather than catch a regression. | Reader |

## See also

- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - test and adopt different summary weights without bypassing config or measurements.
- [principles.md](principles.md) - config-driven with sane defaults.
- [pipeline-loop.md](pipeline-loop.md) - the stages these knobs tune.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md) - the run cadence and the scoring knobs under `collect`.
- [../architecture/sources/health.md](../architecture/sources/health.md) - what `quarantine_after_failures` decides.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - what `console.*` tunes.
- [evaluation.md](evaluation.md) - the bands and thresholds.
- [telemetry.md](telemetry.md) - the logging knobs.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the schema every config file conforms to.
- [../agents/guardrails.md](../agents/guardrails.md) - the identifier-and-config discipline.
