# Config

**Last Updated**: 2026-08-30

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
- **Evaluation** - the confidence band thresholds, the brief compression ceiling, the copy reject ceiling, the word gate, the faithfulness window and its overlap, and the spot-check sample size ([evaluation.md](evaluation.md)).
- **Run shape** - the safety ceiling, the batch size, per-job timeouts, and concurrency ([pipeline-loop.md](pipeline-loop.md)).
- **Retention** - the image age window, the dry-run switch, the deletion fuse, and the published-site alarm point ([../architecture/publishing/layout.md](../architecture/publishing/layout.md)). `retention.site_budget_mb` is read by `idhazh site-weight`, which runs after the site is built and measures the built bundle - never the committed payload tree, which is a different tree eighteen times smaller.
- **Drift** - the alert thresholds and the schedule ([evaluation.md](evaluation.md)).
- **Logging** - the level, and nothing else ([telemetry.md](telemetry.md)).
- **Observability** - which instruments run, how often the scorer runs, and how long a ledger stays at full grain ([telemetry.md](telemetry.md)).
- **Console** - the telemetry viewport's default window, today anchor, pan step,
  zoom factor, minimum denominator for rate bars, and chart height.

These are the *surfaces*, not a field list. The field-level truth is `schemas/app-config.schema.json`, generated from the model - read it there rather than restating it here, because a list copied into prose is a list that goes stale.

The knobs are spread across five files rather than one, along the line of who edits them and how often: `config/idhazh.json` for pipeline behaviour, `config/appearance.json` for everything the published surface is drawn from, and `config/taxonomy.json`, `config/sources.json` and `config/watchlist.json` for the source model ([../architecture/sources/discovery.md](../architecture/sources/discovery.md)). Curating a feed list and tuning a threshold are different activities with different review cadences, and putting them in one file means every feed addition touches the file that also holds the decoding parameters.

## `config/appearance.json` - the published surface's own file

Split off `config/idhazh.json` on 2026-08-29 on the same argument the source model was split on, one surface later: curating a reading surface and pinning a decode temperature have different review cadences, and one file meant every appearance edit touched the file that holds the sampler seed.

Its blocks:

| Block | What it tunes |
| --- | --- |
| `digest` | The day page. Formerly `idhazh.json`'s `ui` block, unchanged in shape. |
| `console` | The operator viewport. Formerly `idhazh.json`'s `console` block. |
| `assist` | On-device archive search. Formerly `idhazh.json`'s `assist` block. |
| `frame` | The frame maximums, the reading measure, the gutter range, and the three breakpoints. |
| `theme` | Whether gradients, elevation and the display face are drawn, and how strongly a panel takes a tint. |
| `chart` | Drawn height and server-side width, whether a chart answers a pointer and how wide that readout may be, the palette, tick density, and the sparkline and donut geometry. |
| `icons` | Icon size, whether an icon takes the hue of what it means, and whether a topic carries a mark. |
| `motion` | The two durations, and one switch. `prefers-reduced-motion` sits above the switch and is deliberately not configurable. |

The contract is `backend/idhazh/contracts/appearance_config.py`, and it imports `UiConfig`, `ConsoleConfig` and `AssistConfig` from `app_config` rather than copying them: the file moved, the contract did not fork. `AppConfig` keeps the three moved blocks, and the frontend loader merges three layers - defaults, then the legacy block, then the new file - so a checkout that has not been migrated resolves to exactly what it resolved to before (`CLAUDE.md` section 11). The legacy block is a middle layer rather than a discarded one so a partly migrated file cannot snap a knob back to a default nobody chose.

### Why a frame width is a knob, when a 2026-08-28 ruling said it should not be

The objection was that a config able to set the frame to 300px would need a code change to still look right. That is true of an unvalidated number and false of a validated one. **`frame.reading_max_px` cannot be set below 960 or above 1600; `measure_ch` cannot leave 52 to 80; `breakpoints_px` must be exactly three ascending, distinct widths; and `console_max_px` may not be narrower than `reading_max_px`.** A validator refuses a document that breaks any of them, so no reachable value breaks the design. The contract is the answer to the objection rather than a refusal of the knob, and `backend/tests/test_appearance_config.py` asserts every bound in both directions.

One cross-block rule is worth naming because it is the one that bites in production rather than in review: `chart.width_px` may not exceed `frame.console_max_px`. The server prerenders every chart at `width_px` because a prerendered chart has no element to measure, and the client re-measures once a script runs. Draw wider than the container can ever be and every first paint is wrong and then visibly snaps - on the one kind of site whose whole premise is that the page is finished before any script runs.

Two knobs in that block decide what a chart's axis and its readout look like, and both exist because a number written into a component is a number nobody can move. **`chart.tick_density` is the most date labels an x axis may carry** - a ceiling and never a target, because the axis then measures those labels against the room the plot actually has and drops more of them until none touch. So a month of columns gets six dates on a desktop rather than one span string, three on a phone rather than six overlapping ones, and a column whose date was dropped keeps its tick mark. **`chart.readout_max_share` is the widest the readout strip under a plot may be, as a share of that plot** - 0.33, bounded above 0 and at or below 1. The strip sits below the plot, so no value here can cover a mark; the cap is what stops it becoming a paragraph. The floating box it replaced was measured on 2026-08-29 at 88 to 121px over a 220px plot, which is 40 to 55 percent of the chart it was explaining.

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

`evaluation.verbatim_reject_ceiling` is 0.75, and it is deliberately a different
number from `evaluation.brief_compression_ceiling`. The compression ceiling is a
gate: it reads the scores a run wrote and fails the run when a brief copied too
much. The reject ceiling is a rule inside the summarize stage: above it the item
is refused and never scored at all. Give the two one value and the gate has
nothing left to read, because every item it could have failed was dropped before
it looked - and a gate that stops failing reads exactly like a pipeline that
stopped copying. An `EvaluationConfig` validator refuses any reject ceiling at or
below the gate's, so an operator cannot collapse them by editing one line.

0.75 is a starting point and not a calibrated threshold (Rule #10). It is the
midpoint of the empty band that eight brief items left on 2026-08-26 (run
33016222069): seven scored at or below 0.241 and the eighth scored 1.000, so
every value between those two selects the same single item and nothing in the
data prefers one over another. The floor is fixed at 0.5 by the validator above.
Eight items is not a distribution.

Every `min_source_words` in this file - `extract.min_source_words` and each
`summarize.bands[].min_source_words` - counts the **source body**, before
`extract.truncation_cap_tokens` cuts it. One name, one meaning. Reading the top
band off the post-cap count is what left it empty until 2026-08-26, because at
the cap of 2500 committed then that count stopped at `int(2500 / 1.3) = 1923`
words and that band started at 2000
([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)).
The ladder gained a fifth rung at 3000 words on 2026-08-29, and no rung floor
may ever sit above `int(truncation_cap_tokens / 1.3)` - the model is handed that
many words and a rung above it would ask for a summary of text it never saw.

**The published surface keeps a second copy of that ladder, and it drifted.**
`SUMMARIZE_DEFAULTS` in `frontend/src/lib/server/config.ts` is the value the
console falls back to when `config/idhazh.json` cannot be read, and those bands
draw the compression plot's target zone and set its y axis. Until 2026-08-29 it
carried **three** rungs against the real five, and the first of them started at
0 words asking for 50 to 90:

| | `config/idhazh.json` | `SUMMARIZE_DEFAULTS` before 2026-08-29 |
| --- | --- | --- |
| rungs | 5 | 3 |
| first rung | 0 words -> 30-45 | 0 words -> 50-90 |
| brief band | present | **absent** |
| top rung | 3000 words -> 150-230 | 2000 words -> 110-200 |

So under the fallback a 30-word note was asked for 50 to 90 words - more words
than the article holds - and the two longest rungs collapsed into one. It had
never fired, because the file it stands in for is committed and read at build
time, which is exactly why nothing noticed.

**This is the drift the rejected-alternatives table below already forbids**, in
the row that refuses copying config into the published directory because two
copies of one file are free to drift with nothing gating them. The copy is in
code rather than in a published file, so no gate caught it. The five rungs are
corrected as of 2026-08-29, and the copy is now pinned:
`backend/tests/test_contracts.py::test_the_console_fallback_bands_match_the_committed_ladder`
reads the committed bands and the `SUMMARIZE_DEFAULTS` literal and fails when
they disagree, printing both ladders. The guard sits with the writer because a
frontend test cannot import that module without dragging in the SvelteKit
runtime - it reads `node:fs`.

**Whether the fallback should exist at all is still open.** Section 1a of
`CLAUDE.md` says a fresh clone runs on the defaults, so it stays. One question
settles it: does any build ever run with `config/idhazh.json` unreadable? If the
answer is no, `summarizeConfig()` should throw rather than guess, and the
defaults go with it - a value pinned to the file it stands in for is a
consolation prize next to not needing the copy.

`evaluation.qualification_pool_multiple` sizes how wide a qualification shard
casts before it selects. It is a floor and not a cap: a shard whose slice has not
yet offered every length tier keeps walking. Raising it buys fetch seconds and
never model minutes, because the model still sees `corpus_per_shard` articles.

`config.sources` can declare `form: "abstract"` on a feed. That is a curator's
fact about the feed, not a detector over page text. NBER uses it; arXiv and SSRN
should use the same field if those feeds are added.

`collect.blocked_url_markers` is a list of case-insensitive substrings that keep
an address out of the candidate pool. It defaults to empty, because the entries
are a source-curation decision and belong in `config/` rather than in the
contract (Rule #6). What it is for, and why the control cannot live at the
faithfulness score, is
[../architecture/sources/discovery.md](../architecture/sources/discovery.md).

## Training-corpus surface

The `finetune` block sizes a file CI commits and two schedules that maintain it.
Nothing in it runs a training step - the runner has no GPU (`CLAUDE.md` section
0a) - and `teacher` and `student` name a **key in `models`**, never a model, so
swapping the summarizer is still one block.

Two pairs of knobs look like one knob each and are not:

- **`corpus_rows` is the window; `train_rows` is the sample.** They price
  differently. The window costs storage and git history, measured 2026-08-27 at
  2.9 KB compressed per row. The sample costs wall-clock on somebody's GPU. So
  window 2000 with sample 1000 is strictly better than window 1000 with sample
  1000: the same training time, twice the pool to draw a diverse 1000 from.
  `train_rows` is a ceiling rather than a demand, because a 600-row corpus
  satisfies `min_rows: 500` and cannot satisfy `train_rows: 1000`, and a session
  that silently trained on 600 while every note said 1000 produces a result
  nobody can attribute.
- **`prune_every_days` is how often the prune fires; `prune_keep_days` is how far
  back it keeps.** "Prune quarterly" names neither on its own. The first costs one
  force-push each time; the second costs storage, and it is also how far
  `git blame` reaches afterwards.

`harvest_every_days`, `prune_every_days` and `prune_keep_days` are the clearest
case in this project of a knob that **cannot** be workflow syntax.
`on.schedule` is parsed by GitHub Actions before any step runs, so no value in
`config/` can reach a cron line at all - and 5-field cron has no every-N-days
field to write one with. Each cadence is therefore a due-check in a step, reading
durable state out of `corpus/corpus.meta.json`. The cron lines that remain are
wake-ups, not schedules.

`models.<role>.hf_base_repo` is optional and sits on the model entry rather than
in `finetune`, because training reads the safetensors repository while the
pipeline reads the GGUF one. Held in two blocks a model swap moves one string and
leaves the other, and a LoRA adapter loads onto a mismatched base without
raising.

See [../how-to/fine-tune-a-model.md](../how-to/fine-tune-a-model.md).

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
each `work` job, keeps the raw body in that shard's runtime artifact, and
commits the counters that matter as one row of `state/runtime-counters.csv` -
the artifact keeps them for two days and the row keeps them forever, which is
what makes the read rate on
[../architecture/summarize/throughput.md](../architecture/summarize/throughput.md)
checkable rather than merely reported.

Turning `metrics` off is therefore not free any more. It costs the log lines it
always did, and it also leaves every later run's counter row empty, so the
reconciliation has nothing to hold the ledger against.

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
([Parallel decode on 4 vCPU](../archive/measurements-2026-08.md#parallel-decode-on-4-vcpu)).

No sweep flag is adopted merely because the knob exists. A candidate becomes the
runtime only after a runner measurement records hardware, date and spread in
[../reference/measurements.md](../reference/measurements.md).

### The run shape, and who reads each number

All three run-shape knobs are now enforced. `digest.yml` derives the worker
count from the planned day as
`min(ceil(items / run.shard_size), run.max_parallel)` from 2026-08-26, and reads
the `work` job's own timeout out of `run.shard_timeout_minutes` from 2026-08-27.
That last one had no reader at all while the workflow set the job to 330
minutes, so config said 150 and production ran 330.

The derivation is the automatic path; an operator dispatching the workflow names
a count instead, up to the eight the workflow's own guard allows.

Treating a worker as five items is still false, and for the opposite reason:
`shard_size` decides how few workers a small day is worth, and a full day at the
item ceiling gives a worker 40. A model adoption measures the actual worker
population and its own worst worker. It does not divide by five, and it does not
assume this bound already fits it
([../reference/measurements.md](../reference/measurements.md#what-a-work-shard-costs)).

## Console surface

The console knobs are:

- `console.default_window_days`
- `console.window_presets`
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

`window_presets` is the list of spans the console's window control offers, and
one control sets the span for every section that follows it. Four presets rather
than a free number, because a wider window fetches a month file per month it
reaches back into - so every value is a distinct transfer cost, and the values
between these four cannot be told apart on the page. `default_window_days` must
be one of them, or the page would open on a window its own control cannot name,
and every preset must sit between `min_window_days` and `max_window_days`. All
three rules are in the contract, so a config that breaks one fails the build
rather than the page.

`zoom_factor` has had no reader since the presets landed: the `+` and `-` keys
step to the next preset instead of scaling the span, because a free span is the
thing the presets exist to prevent. The knob is still in the contract, and
retiring it is a removal with a read-side migration behind it (section 11).

## Observability surface

`observability` is the block that decides which instruments run at all:

| Knob | Default | What it switches off |
| --- | --- | --- |
| `evaluation_enabled` | `true` | The faithfulness scorer, and so every row in `state/scores.csv`. |
| `telemetry_publish` | `true` | The copy into `frontend/public/telemetry/<YYYY-MM>.csv`. |
| `runtime_counters_scrape` | `true` | The llama-server `GET /metrics` read, and so every row in `state/runtime-counters.csv`. |
| `tracing_enabled` | `false` | Already off. True builds a span tree under `backend/var/traces/`. |
| `sample_rate` | `1.0` | Nothing. It is the fraction of runs whose scorer runs. |
| `keep_months` | `13` | Nothing. It is where a month stops being kept at full grain. |
| `hard_delete_after_months` | `null` | Nothing by default. Null means a downsampled month is never removed. |
| `cost_currency` | `"USD"` | Nothing. It is the ISO 4217 code the console prints a counterfactual cost in. |
| `cost_input_per_million` | `0.20` | Nothing. It is what a hosted provider would charge for a million prompt tokens. |
| `cost_output_per_million` | `0.60` | Nothing. The same, for a million written tokens. |

**Four switches and not one master switch.** Collection, scoring, publishing and
tracing fail in different ways: the score ledger empties when the scorer will
not load, the published telemetry file stops when a run does not publish, and
the counters file is silent when llama-server was gone before it was read. Under
one switch a reader sees three absences and cannot say which instrument went
dark, so cannot say whether to fix the model, the publish step or the server.

**`tracing_enabled` is the only one that is off unconfigured**, because it is
the only instrument nothing reads: no page renders a span, no gate consults one,
and every rate the console prints keeps its denominator with tracing off. It is
for a developer looking at one slow item, and it is described in
[telemetry.md](telemetry.md#the-span-tree).

**The item-health census is not on that list and is not going to be.** Every
rate the console and the dashboard print divides by it, so switching it off does
not thin a measurement - it makes every other measurement unreadable. A failure
rate with no denominator beside it is the defect the census exists to prevent. A
contract test asserts the switch list holds exactly four names, so adding a
fifth has to be argued for rather than typed. The three cost knobs are not on
that list because none of them is a boolean and none of them switches an
instrument: they are a price, and they are described below.

## The cost rate is the operator's to set, and it is not a bill

`cost_currency`, `cost_input_per_million` and `cost_output_per_million` are the
only knobs in this block a published page reads. `/console/machine/` multiplies
a run's committed token counts by them and prints **what that run would have
cost at a hosted provider's price**. Nothing bills us - Actions minutes are free
on a public repository (Rule #2) - so the figure is a counterfactual, and it is
labelled one everywhere it appears. What it answers is the question wall clock
cannot: whether four hours of runner time was a good trade.

CLAUDE.md Rule #10 carries the owner's carve-out for it, on one condition: the
page prints the rate it used and says where the rate came from. The operator may
type a different pair into the panel, which is kept in `localStorage` and read on
mount only, so the first paint always matches the prerendered document.

**The committed pair is a documented starting point and nobody has set it.**
`0.20` and `0.60` US dollars per million tokens are representative of a hosted
provider's price for an 8-to-9-billion-parameter open-weights model, with output
at three times input, taken from published list prices in August 2026. They are
not a quote anybody gave this project, and they are the first thing to correct
when the owner names a rate - a one-line edit to `config/idhazh.json`, with no
code change and no migration. Input and output are priced apart because a
provider prices them apart; one blended rate would understate a run that wrote a
lot and overstate one that read a lot.

**An instrument that did not run writes an empty cell, never a zero.** A switch
here decides whether a row is written; it never changes the shape of a row. The
rule is stated twice already - in `RuntimeCountersRow.csv_row` ("Empty is not
zero") and in the degrade rules of
[../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md)
("`<1`, never `0`") - and this block is bound by both rather than restating them
a third time.

**`sample_rate` is a rate over runs, and it is refused at zero.** A run scores
every item or none, so a sampled day's rows are never a partial sample of that
day and a per-day rate stays honest. Zero is refused because `evaluation_enabled`
already says off, and two ways of saying off is how the two end up disagreeing.
The draw itself - a digest of the run id, recorded on the run manifest - is
described once, in
[../concepts/evaluation.md](evaluation.md#the-scorer-is-sampled-by-run-and-nothing-else-is).

`hard_delete_after_months` defaults to null - never - and that is a decision
rather than an omission. `console.max_window_days` is 366, so a shard has to stay
readable for a year, and the downsampled aggregate costs roughly 219 KB a year.
Set it, and it must sit above `keep_months`, or a month would be deleted before
it was ever downsampled; the contract refuses the pair otherwise.

**What `keep_months` actually governs is `state/item-health/`, and nothing
else.** Past the window a month is folded to one row per `(date, stage)` in
`state/telemetry-aggregate/<YYYY-MM>.csv` and the full-grain shard is deleted, by
`idhazh prune-state` in the assemble job - after the day is committed, never
before it. What survives is every count and every timing total; what goes is the
per-item detail, which is what the console's failure list offers and no rate
needs. Folding the committed `state/item-health/2026-08.csv` on 2026-08-30 turned
4,167 rows and 1,270,452 bytes into 24 rows and 1,531 bytes - **829.8 times
smaller**, and 93,136 bytes a year against the shard's 77,285,830.

The 219 KB a year the `hard_delete_after_months` description quotes was an
estimate at five stages and 120 bytes a row. Measured it is **63.8 bytes a row
over four stages**, because `plan` wrote no row in that month - so 93 KB a year,
2.4 times cheaper than the estimate. The description keeps the estimate's
conclusion, which the measurement only strengthens.

The two ledgers the fold does not reach were named here rather than left to be
discovered, and one of them has since been answered. `state/seen/` was 5,166,315
bytes on 2026-08-30 - 54 percent of `state/` - and `state/scores.csv` was
2,359,230, against `state/item-health/`'s 1,270,452. On 2026-08-31 `state/seen/`
took the decision its own shape asked for: it is a lookup rather than a
measurement, so an out-of-window shard is deleted rather than folded, and the
address column that no reader opened came off with it - together 49.1 percent of
the file and a 90-day ceiling where there had been none. `state/scores.csv` is
still one file with no `stage` and four readers, so it still needs a decision of
its own. See
[../architecture/publishing/layout.md](../architecture/publishing/layout.md#what-bounds-the-committed-state-tree).

## Reader surface

`ui.items_per_topic` is how many of a topic's stories the all-topics page shows
before it links to the rest. It is a hierarchy knob, never a cap: nothing is
removed, hidden or re-ranked, and the whole topic is one prerendered click away.
A day that ran to a single topic ignores it, because a lone heading over the
whole page states what the page already says.

`ui.archive_page_size` (25) is how many stories the archive's list adds each
time a reader asks for more. The day page pages at twelve because a day is short
and the reader came to read it; the archive holds thousands and the reader came
to find one, so it opens on the same twenty-five the console's failure list
does. Like `items_per_topic` it hides nothing - every story is one more click
away, and the order is the published one.

The `assist` block is on-device search. The runner embeds the day and commits
the vectors; a reader's tab embeds only the query. The first two knobs say how
much of an item the encoder is allowed to read, and the last two say how much of
the archive a search reads at all. All four are set from what was measured
rather than from taste.

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
- `assist.search_months` (1) is how many month shards a search always reads,
  newest first. The reader waits on the download and never on the arithmetic: one
  month is a 2.53 MB vector file beside a 518 KB browse index, about 2.1 seconds
  on a 10 Mbit line at the rate the committed days ran, against 74 to 159
  milliseconds of ranking. The fetch is 9 to 30 times the ranking at every scope,
  so this knob buys download seconds and never compute seconds, and three months
  is a 14.4 second wait before the first result. One month is the only scope
  whose first search starts inside about five seconds.
- `assist.search_min_days` (7) is the fewest days of published stories a search
  tries to reach, and it is what stops a calendar shard being mistaken for a
  window. On 31 August the newest shard held 31 days; on 1 September it held one,
  so the same search reached 31 times less for a reason no reader could see, and
  finding nothing looked exactly like a story we never published. Below this
  floor a search reads one more shard, and one more only, so the cost is bounded
  at a single extra fetch. Seven days because a week is already this site's unit
  for what a reader still has in mind - `ui.read_mark_days` keeps a read mark for
  seven days and `console.min_window_days` will not draw a narrower window. The
  extra fetch fires on the first 6 days of a month, 20 percent of them, and only
  when the shard already being read is small, so the bytes a search moves are
  levelled across the month rather than doubled. Widening either knob is visible
  to a reader rather than silent: the page prints the days it searched under the
  box.

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

- `run.safety_ceiling_per_run` (160) **was** a crash guard and is now a cap, and the name is the last thing that has not caught up. `items_planned` has been exactly the ceiling on every run since 2026-08-25, so supply overtook the guard and what it bounds today is the size of a run. Owner decision, 2026-08-29: it stays at 160 rather than rising, and the gain comes from spending those 160 slots on articles that can be read - see [../architecture/sources/discovery.md](../architecture/sources/discovery.md). Raising it is a separate question with a separate risk, because a worker killed at `run.shard_timeout_minutes` uploads nothing. It is still the worst case every downstream bound is checked against, which is what would decide any new number - see [Design rationale](#design-rationale).
- `models.inference.max_output_tokens` (900) is a **crash guard**. It stops a runaway decode from burning a shard's whole timeout. It is not a length target: the length a summary should be is set by the word bands in `summarize.bands`, which is the knob a person actually wants ([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)). It was 250, and at 250 the reply ran out of budget mid-object and failed as a *shape* error - which named the wrong cause and sent the reader of that failure looking at the decoder. It now sits well above any summary we would want.
- `models.inference.request_timeout_minutes` (22.1) is a **per-request guard**. It limits one summarizer POST, not the shard. It protects the day from one local model request that accepts a connection and never replies: that item records `model_unreachable`, and the worker continues. The default is sized from the authoritative runner measurements in [../reference/measurements.md](../reference/measurements.md): the worst 8B long article plus one cold prompt prefix, doubled. `run.shard_timeout_minutes` stays the outer bound for the whole shard.
- `run.shard_timeout_minutes` (150) is a **job backstop**, and it is the outer bound the previous line hands off to. The `work` job reads it, so this is the only place the number is written. It is not a budget: the stage has no clock of its own, and a worker killed here uploads nothing, so the run loses every item that worker held rather than the tail it could not reach. It is half again the slowest worker ever measured at the current item ceiling - 94.5 minutes on 2026-08-26 - and still above the 117.5-minute worst of 2026-08-24, when a day handed a worker 50 items instead of 40 ([../reference/measurements.md](../reference/measurements.md#what-a-work-shard-costs)). A worker that runs long is answered by lowering `run.safety_ceiling_per_run`, never by raising this (Rule #2).
- `collect.settled_failure_codes` is a **memory**, not a guard. It names the failure codes that will not change before tomorrow, and an address that failed today with one of them is not planned again today. Absent from it - and therefore retried - are the codes that can change within a day: a rate limit, a network error, a server error, an unreachable model. Measured over 2026-08-24 to 2026-08-29, 403 same-day repeats of a settled failure bought 2 items ([../architecture/sources/freshness.md](../architecture/sources/freshness.md)). An empty list restores the old behaviour exactly.
- `run.route_budget_minutes` (40) is a **stage budget**, and it is the one number here that a person is meant to move. It says how long the route stage may spend before it stops asking the model and leaves the rest of the day unrouted. It is sized *below* the route job's 50-minute timeout on purpose: a job killed at its timeout skips its upload step, so the run loses every decision it had already made rather than the tail it could not reach. The 10 minutes between the two are the fixed cost the stage clock never sees. Measured 2026-08-24/25, the per-item cost is 20.7 s on a fast runner host and 40.3 s on a slow one, so what fits inside the budget changes run to run - which is exactly why the bound is a clock rather than an item count ([../architecture/publishing/visuals.md](../architecture/publishing/visuals.md)).
- `retention.site_budget_mb` (800) is an **alarm**, which is weaker than a guard because it stops nothing. Above it a run logs a warning naming the headroom left, and that is the whole effect: no build fails, and no byte is deleted. The warning rides the run log CI already keeps (section 1b); promoting it to a GitHub issue is a workflow step not yet built. It sits 224 MB below the platform's own 1 GB Pages ceiling, and the size of that gap is the entire design - 224 MB is 26 days of warning at the fastest growth this project has measured, against a 14-day target. The target is a judgement about one maintainer reading one issue, not a measurement, and it is labelled as one where it is derived. The arithmetic, the growth rates it rests on, and why the number is neither 900 nor 600 are in [../reference/measurements.md](../reference/measurements.md#where-the-alarm-fires-and-what-it-buys). Deleting anything is a different knob and ships off: `retention.image_months` is -1 and `retention.dry_run` is true ([../architecture/publishing/layout.md](../architecture/publishing/layout.md)).
- `page_weight.ceilings_bytes` is a **limit**, and the only one on this list. It says how heavy each named prerendered page may be on the wire, gzipped, and `frontend/scripts/bundle-gate.mjs` fails the build above it. The object is the single source - the `PageWeightConfig` default in the contract is empty, so a number lives here and nowhere else (Rule #6). A route earns a ceiling when somebody has priced its growth, not when it has none. `/404` and `/evals/` move only when the source does, so each one is the heaviest of three builds plus the 64-byte noise floor and nothing else. `/archive/` grows by one day link a published day since it stopped inlining the day payloads, so its ceiling is the heaviest build plus a measured year of that growth plus the same noise floor - headroom that shrinks 12 to 17 bytes on every publish and expires by design, so the gate gets stricter on its own and the answer when it finally fires is to re-measure rather than add a digit. `/console/` earned its ceiling on 2026-08-29, sized against the regression it has to catch rather than in days of headroom, and it stopped being a page that grows with the ledger on the same day - the compression plot now reads one window of the published telemetry shards instead of every row ever scored, so the page settles once the window fills. Since 2026-08-30 there are **three console keys**, one per prerendered route, because one key over three surfaces still fails when any of them grows and then cannot say which one did - so the operator raises the shared number and the next regression lands under it. That is also the decisive argument for splitting the console into routes rather than tabs. A day page is still out, and for the reason both used to be out: a fixed ceiling on a page whose weight is whatever the day published fails on an ordinary publish rather than catching a regression, which is what happened to `/archive/` when it carried the corpus - the ceiling fired on every publish and was raised twice in a day before it was removed ([../reference/measurements.md](../reference/measurements.md#the-prerendered-page-on-the-wire)). The gate reports a route the object does not name without failing it, and the class those data-driven routes belong to is covered by the marker count in `frontend/tests/payload-weight.spec.ts`.

A guard set near the working range is the worst of both. It fires on good runs, gets raised to stop the noise, and stops guarding anything. That is the failure the token cap actually had.

### The other failure: a vocabulary with no way to be applied

A knob nothing reads has a mirror image, and it is harder to see. `taxonomy.json` declared four lenses and nine event types from the first commit, and every one of them carried an `id`, a `display_name` and **no way to say what assigns it**. So nothing ever did: measured 2026-08-26, 0 of 2,121 committed items carried a lens or an event. The file read as a working vocabulary and was a list of labels.

The fix, on 2026-08-26, was a `keywords` list on each lens and each event, holding the curated terms that assign it ([../architecture/sources/discovery.md](../architecture/sources/discovery.md) owns the rule and its measured coverage). Two things about that field are deliberate:

- **It is a config field and not a code constant** (Rule #6), because it is a curated artifact that gets tuned. The first draft over-tagged: bare `research` and `study` put the `research` event on 34.7 percent of real articles, which is not a filter. Tuning it must not be a code change.
- **An empty list is legal and assigns nothing.** That is what makes the field additive - a taxonomy written before it still validates - and it is also exactly the silence that let the vocabulary ship unwired for five days. A test now asserts every committed lens and event carries terms, so the empty state cannot come back unnoticed.

The lesson generalises past this file: **a config entry that declares a thing must also declare how the thing is decided, or it is decoration.** An id and a display name describe a label. They never describe a rule.

The same day found the third shape of the same failure, and it is the worst of them: **a knob that is read, but always against an empty input.** `collect.watchlist_bonus` was read on every planned item and added to the score under `if watchlist_hit`, and it could never fire, because `watchlist_hit` was tested against a `watchlist_keys` the caller hardcoded to the empty set. Nothing here was dead code and nothing was unread config, and the term still never moved a number. A test asserting "the bonus lifts the score" passed the whole time, because the test supplied the flag itself. Fixed 2026-08-26: `config/watchlist.json` carries 30 entities and the flag comes from their aliases. The test now pins each term's **size** against its knob rather than only its direction, which is the check that would have caught it.

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

**`run.safety_ceiling_per_run` moved from 200 to 160 on 2026-08-26.** A guard is still sized, and this one is sized by the slowest thing that has to finish a full day of it. Two bounds disagreed with 200. An automatic run derives `min(ceil(items / run.shard_size), run.max_parallel)` = four shards, so 200 hands a worker 50 items; against the Qwen3.5-9B candidate that derives to 318 minutes one way and 345 the other, over a 330-minute job timeout that nobody may raise (Rule #2). At 160 the same arithmetic gives 40 items, 254 and 276 minutes, and clears both. The route stage says the same thing from the other side: its measured slow-host capacity is 166 items in a 50-minute budget, so 200 and the router never agreed and 160 does. The largest day ever planned is 149 items, so the move removes nothing a reader has ever had. The lever was the ceiling rather than the timeout, because the timeout is the platform; and rather than the shard count, because `run.max_parallel` is four until the three conditions under [Eight work shards](../archive/measurements-2026-08.md#eight-work-shards) are met, and `route` is unsharded either way ([../reference/measurements.md](../reference/measurements.md)). Authority: Carmack.

**That paragraph's 9B arithmetic no longer clears the bound, and it was never a measurement.** The `work` job's bound is 150 minutes from 2026-08-27, not 330, so a 40-item 9B worker at 254 or 276 derived minutes does not fit it. A third derivation on the same page, taken from a live production observation rather than from length interpolation, puts the same worker at about 130 minutes and does fit. All three are estimates of a model this project has never run a day on, so none of them may hold a live bound open (Rule #10). **The adoption did not settle this.** Qwen3.5-9B-Q4_K_M became the configured summarizer on 2026-08-27 without a production worker ever being measured on it - the 95.2-minute figure the qualification recorded is a replay job under a different bound, not a worker ([../reference/measurements.md](../reference/measurements.md#the-qualification-budget-derived-2026-08-26)). `run.shard_timeout_minutes` therefore still rests on the retired incumbent's worker population. The first scheduled day the configured model runs is what may move it; if that number needs the ceiling to move instead, the ceiling is still the lever.

**That day ran on 2026-08-27, and it left both numbers where they are.** Run `33073809079` is the first scheduled day on Qwen3.5-9B-Q4_K_M: four workers, 40 items each, slowest worker **85.6 minutes** - inside the 83.5-to-94.5 minutes the retired 8B took at the same load, and 1.75x inside the 150-minute bound ([../reference/measurements.md](../reference/measurements.md#the-first-scheduled-day-on-the-configured-model-2026-08-27)). So none of the three estimates was needed and none is vindicated: the measurement is 85.6, the closest estimate said 130, and the other two said 254 and 276. One run does not move a bound either way (Rule #10), and this one gives the next one something to be compared against.

**`run.max_parallel` and the workflow's eight-shard ceiling are different numbers on purpose.** `digest.yml` lets an operator dispatch up to eight workers, and one such run halved the slowest worker. `run.max_parallel` is the most a run derives *for itself*, and it stays at four because no eight-shard day has yet published. The dispatch ceiling is the escape hatch; the config knob is the automatic path a reader depends on, and an unmeasured number may not move that path (Rule #10). Authority: Carmack.

**One dispatch at eight was authorized, fired and published.** Authority: the owner, 2026-08-27. What had blocked the raise was a run that lost its day at the commit step to an asset-name conflict, and that cause was removed the same day ([../architecture/publishing/visuals.md](../architecture/publishing/visuals.md)). Run `33114410534` then published the 2026-08-27 day at eight workers, against the four-worker run of the same date and the same model: **the slowest worker fell from 85.6 to 53.4 minutes, which is 1.60x**, and the day landed with every chart it names present ([../reference/measurements.md](../archive/measurements-2026-08.md#eight-work-shards-paired-2026-08-27)).

**`run.max_parallel` still reads 4, and what holds it there is now a judgement rather than a missing number.** Eight workers make the day ready about half an hour sooner and cost more machine time, which a public repository does not pay for. They do nothing for `route`, which is unsharded, starts after every worker has finished, and cannot observe the worker count - it spends its whole 40-minute budget on 10 of the 11 runs on record whatever the fan-out is ([../reference/measurements.md](../archive/measurements-2026-08.md#the-route-stages-per-item-cost-over-every-run)). Sharding `route` is the lever that would help and it is unmeasured. Whoever moves this knob moves it in its own commit, naming the run it rests on.

**The `work` job's bound came down from 330 to `run.shard_timeout_minutes` on 2026-08-27, and the config number did not move.** Neither 330 nor 150 had a recorded basis, so the direction was decided by reading the wall-clock of all 106 `work` jobs the repository has: across 16 full days at four workers the slowest worker of a run took 83.5 to 117.5 minutes, and at today's 40-item ceiling the worst was 94.5. 150 is half again that; 330 was 3.5x it, and more than half the six-hour platform maximum. So the workflow's number was the wrong one and it now reads this one - the same shape `run.route_budget_minutes` has always had, where the number lives in config and the job bound sits above it with the reason written in the workflow. A bound above about 165 minutes could not be honoured in any case: the scheduled runs are four hours apart and share one concurrency group with `cancel-in-progress: false`, so at 330 a single hung worker delayed the next two digests ([../reference/measurements.md](../reference/measurements.md#what-a-work-shard-costs)). Authority: Carmack.

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
| Raising the `work` job's `timeout-minutes` so a bigger item ceiling fits | The budget is the platform, not a preference (Rule #2). The ceiling is the knob; the timeout is not. Since 2026-08-27 there is no `timeout-minutes` to raise - the job reads `run.shard_timeout_minutes`, and raising that needs a measured worker that does not fit. | Carmack |
| Leaving the work fan-out a fixed four | It made `run.shard_size` read as configuration and behave as decoration, and it paid the weights restore four times on a day that needed one worker. | Fowler |
| Deleting `run.shard_timeout_minutes` because nothing read it | It is the one number a model adoption sizes a worker against, so the fix was a reader, not a funeral. The knob-nothing-reads rule above deletes a knob that describes a mechanism which does not exist; this one described a mechanism that did exist and was hardcoded somewhere else. | Fowler |
| Raising `run.shard_timeout_minutes` to 330 so config matched the workflow | The same defect facing the other way. 330 was not measured either, it is more than half the six-hour platform maximum, and it is longer than the gap between two scheduled runs. | Carmack |
| Page ceilings anywhere but `config/` | A ceiling is a limit a person chose and raises on purpose, which is what `config/` is for. The one alternative that existed - `frontend/bundle-baseline.json`, beside the recorded JavaScript weights - was deleted with that file on 2026-08-30. | Fowler |
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
