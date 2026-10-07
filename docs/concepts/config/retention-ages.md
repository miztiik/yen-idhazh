# Instrument switches and cleanup ages

**Last Updated**: 2026-10-07

live in one JSON block - `observability` in `config/idhazh.json` - with the ages
a publisher reads, because a switch that stops a record being written and an age
that stops it being kept are the two ends of the same question. **The age of a
ledger under `state/` is not in that block.** It is the window of the gardener
task that deletes the ledger, in that task's own `config/gardener/<task>.json`,
because the task is the only thing that reads the number. What a knob is, and
why these are knobs rather than constants, is [../config.md](../config.md).

## Observability surface

`observability` is the block that decides which instruments run at all:

| Knob | Default | What it switches off |
| --- | --- | --- |
| `evaluation_enabled` | `true` | The faithfulness scorer, and so every row in the eval ledger. |
| `telemetry_publish` | `true` | The copy into `frontend/public/telemetry/<YYYY-MM>.csv`. |
| `tracing_enabled` | `true` | The span tree. False writes no trace under `state/traces/` and no span rollup. |
| `sample_rate` | `1.0` | Nothing. It is the fraction of runs whose scorer runs. |
| `visuals_full_grain_months` | `14` | Where `state/visuals/` stops being kept attempt by attempt. Past it a month folds to the eight-term group in `state/visual-aggregate/` and the shard is deleted. |
| `visual_aggregate_keep_months` | `null` | Nothing by default. Null means a folded visual month is never removed. |
| `cost_currency` | `"USD"` | Nothing. It is the ISO 4217 code the console prints a counterfactual cost in. |
| `cost_input_per_million` | `0.20` | Nothing. It is what a hosted provider would charge for a million prompt tokens. |
| `cost_output_per_million` | `0.60` | Nothing. The same, for a million written tokens. |

**Four switches and not one master switch.** Collection, scoring, publishing and
tracing fail in different ways: the eval ledger empties when the scorer will
not load, the published telemetry file stops when a run does not publish, and
the counters file is silent when llama-server was gone before it was read. Under
one switch a reader sees three absences and cannot say which instrument went
dark, so cannot say whether to fix the model, the publish step or the server.

**`tracing_enabled` is the only one that is off unconfigured**, because it is
the only instrument nothing reads: no page renders a span, no gate consults one,
and every rate the console prints keeps its denominator with tracing off. It is
for a developer looking at one slow item, and it is described in
[../telemetry.md](../telemetry.md#the-span-tree).

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
on a public repository (Guardrail #2) - so the figure is a counterfactual, and it is
labelled one everywhere it appears. What it answers is the question wall clock
cannot: whether four hours of runner time was a good trade.

CLAUDE.md Guardrail #10 carries the owner's carve-out for it, on one condition: the
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
rule is stated twice already - in `silicon.server_prompt_totals` ("empty is not
zero") and in the degrade rules of
[../../architecture/publishing/telemetry-series.md](../../architecture/publishing/telemetry-series.md)
("`<1`, never `0`") - and this block is bound by both rather than restating them
a third time.

**`sample_rate` is a rate over runs, and it is refused at zero.** A run scores
every item or none, so a sampled day's rows are never a partial sample of that
day and a per-day rate stays honest. Zero is refused because `evaluation_enabled`
already says off, and two ways of saying off is how the two end up disagreeing.
The draw itself - a digest of the run id, recorded on the run manifest - is
described once, in
[../evaluation.md](../evaluation.md#the-scorer-is-sampled-by-run-and-nothing-else-is).

## Every tree names its own cleanup age

Until 2026-09-02 one knob decided when a month stopped being kept at full grain
- and it decided it for `state/item-health/` and nothing else.
`state/feed-health/`, `state/scores/` and `frontend/public/telemetry/` had no
cleanup age at all, so three trees grew with nothing to stop them while the
fourth was tuned by a number that said nothing about them.

Now every tree has an age of its own, and each age is a value in a file rather
than a constant (Guardrail #6). **A ledger's age sits with whatever reads it.**
Where a gardener task deletes the ledger, the age is that task's window, and a
task that keeps several series of one tree - the rows, a summary of them, a
published copy - names each one under `series`. Where a publisher or the visual
fold reads the age, it is a knob in `observability`, and
`ObservabilityConfig.full_grain_months` returns the ones a console read opens so
`refuse_windows_shorter_than` can check them against what that read still
selects. `visuals_full_grain_months` is a full-grain window and is **not** in
| `state/visuals/` | 14 months | forever, in `state/visual-aggregate/` | `visuals_full_grain_months` and `visual_aggregate_keep_months` (null) in `observability` |
| the feed-health ledger, `state/raw/feed-health/` and `state/compact/feed-health/` | the 14-month `monthly_window` of its compaction | none - a per-feed-per-run record is not a total worth keeping | `config/gardener/compact-feed-health.json` |
| the host-fingerprint ledger, `state/raw/host-fingerprint/` and `state/compact/host-fingerprint/` | the 14-month `monthly_window` of its compaction | none - one job's silicon on one run, and a total over an old month names no machine | `config/gardener/compact-host-fingerprint.json`, which may not keep less than `public_machine_keep_months` |

And one for each published copy, because a reader fetches those and our own disk
is not what bounds them:

| Published copy | Age | Paired with |
| --- | --- | --- |
| `frontend/public/telemetry/` | 14 months, the `public-copy` series of `config/gardener/telemetry-aggregate.json` | the `full-grain` series of the same file, which it must equal |
| `frontend/public/run-days/` | `public_run_days_keep_months` (14) | nothing - the source is the day payloads, whose retention is the archive's |
| `frontend/public/day-metrics/` | `public_day_metrics_keep_months` (14) | nothing - `state/day-metrics/` has no age of its own |
| `frontend/public/machine/` | `public_machine_keep_months` (14) | the `monthly_window` of `config/gardener/compact-host-fingerprint.json`, which may not keep less than it - the shard is folded from the host-fingerprint and item-health ledgers |

**Two ages left this table on 2026-09-16.** `public_scores_keep_months` and
`public_feed_health_keep_months` bounded published copies of `state/scores/` and
`state/feed-health/` that no console route ever fetched, so the trees went and
the two knobs with them. A config file still spelling either is refused by name
rather than ignored, and it is sent nowhere: the two ledgers above keep their
own ages, which is a different number for a different ledger.

**Three more ledgers are bounded by a read, and a declaration that deletes what
the read opens is refused.** The seen ledger's compaction is held above
`collect.seen_window_days`, counterfactual scores above `lens_weights.window_days`,
and published addresses above `collect.published_window_days`, which is 730
days, or two years. All fourteen ledgers follow the
[yearly policy](idhazh-gardener.md#the-compaction-declarations-that-ship).
A forever reader is refused while finite yearly pruning is enabled.
Each floor belongs to the ledger and is held against
whichever declaration governs it - its retention task while it is on CSV, its
compaction once it moves - and a ledger no declaration governs is deleted by
nothing, so it meets every floor.

**Two are kept a short, fixed time because nothing sums them.** `state/traces/`
keeps 7 days, the window of `config/gardener/traces.json`. A trace is the
evidence an operator opens to see one recent run step by step, and the committed
record is the span rollup, so a trace past its window is deleted whole rather
than folded - a fold would invent a total nobody reads. Seven days covers a week
of runs and keeps the tree one size whatever the project's age (Guardrail #12).
`state/<run.trial_state_dirname>/` keeps 90 days, the window of
`config/gardener/trials.json`, and nothing reads those rows at all - no
published series, no gate, no console band. That age is about disk and about a
reader who opens `state/` and wonders what a directory is, so it needs no
full-grain window, no summary and no published pair. Ninety days is the artifact
retention this project already uses everywhere else, so a trial's rows outlive
the run's own artifacts by nothing.

**A summary is kept forever unless a value says otherwise, and a finite value
must sit above its own full-grain window.** The gardener loader refuses any
other pair for the one task that keeps series, and the `observability` contract
refuses it for the visual pair. Either way a month can never be deleted before
the thing that replaces it has been written.

**A published copy lasts as long as the ledger it is built from.** The loader
refuses a `public-copy` series that differs from the `full-grain` series of
`telemetry-aggregate`, in both directions: a published month whose source has
been folded away is a rate nobody can check, and a source month with no
published copy is a window the console cannot draw. The machine shard is folded
from the host-fingerprint ledger, so the declaration that governs that ledger -
its compaction, which is what deletes its rows now - is refused when it keeps
less than `public_machine_keep_months`. The other three copies have no
state ledger behind them and are bounded by their own knob alone.

**This block sets the ages. Which policy a tree is under - fold, delete or keep
- is [../adaptive-pruning.md](../adaptive-pruning.md)**, which is also where an age is
judged to be the wrong instrument for a tree rather than merely the wrong
number.

### Why 14 and not 13

Fourteen is not a year plus one. It is the number of month files a console read
can open, and the old value was one short.

`console.max_window_days` is 366 and `month_partition.shards_in_window` walks **367
inclusive days** - so a window ending on the first of a month starts on the last
day of another, and those days fall in **14 calendar months**. Anchor it on
2026-01-01: the read reaches back to 2024-12-31, which is `2024-12`, and
`2024-12` through `2026-01` is fourteen shards. At thirteen the fold would delete
`2024-12` on that day and the console would draw a gap that reads as a day the
pipeline did nothing.

The retired check compared the old age times 30 against `max_window_days` - `390
> 366` - which is arithmetic about days, not about the files a read selects. A
month is not thirty days. The check now compares against the shards, and
`backend/tests/contracts/` sweeps every end date in one 400-year
Gregorian cycle to prove it. The gardener loader makes the same comparison for
every declaration whose files a console read opens - the feed-health
compaction's `monthly_window`, the `full-grain` series of `telemetry-aggregate`, and the
`public-copy` series - and refuses a window under fourteen months by naming the
file. Measured 2026-09-02 over all **146,097** anchor
dates - arithmetic over the calendar, so the spread is zero by construction:
fourteen months keeps back at least as far as the console reads on every one of
them, and it is exactly tight on **3,636** of them, 2.5 percent. Those same
3,636 dates are where thirteen deletes a shard the console still opens.

### A config still carrying the old names

`keep_months` and `hard_delete_after_months` were read and dropped for a day, so
that the rows spending the new ages could land one at a time. Since 2026-09-03 a
file spelling either is **refused**, and the message names where the number that
governs the same ledger lives now: the `full-grain` and `aggregate` series of
`config/gardener/telemetry-aggregate.json`.

**Refused rather than ignored.** Every config model forbids unknown keys, so
both names already failed - with "extra inputs are not permitted", which does not
tell an operator where their number went. Ignoring the key would be worse: an
edit that takes no effect is a value somebody believes.

**Refused rather than honoured, too.** The old value was chosen against a check
that could not answer the question - it compared the age times 30 against the
console window instead of the shards that window selects - so carrying the
number forward would carry the defect forward.

`collect.quarantine_after_failures` was removed on the same day and behaves the
same way: refused, naming `availability_strikes_before_rest`.

**Eleven more names left `config/idhazh.json` on 2026-09-28, and no value
changed.** Each cleanup age moved into the declaration of the task that deletes
by it, so the one number a task reads is in the one file that task owns. A file
still spelling a moved name is refused the same way, naming the new place:

| Name in `config/idhazh.json` | Value | Where the value is now |
| --- | --- | --- |
| `observability.item_health_full_grain_months` | 14 | `series.full-grain` in `config/gardener/telemetry-aggregate.json` |
| `observability.item_health_aggregate_keep_months` | null | `series.aggregate` in `config/gardener/telemetry-aggregate.json`, as `forever` |
| `observability.public_telemetry_keep_months` | 14 | `series.public-copy` in `config/gardener/telemetry-aggregate.json` |
| `observability.scores_full_grain_months` | 14 | `monthly_window` in `config/gardener/compact-summary-quality-evals.json`, as `forever` since 2026-09-30 |
| `observability.score_archive_keep_months` | null | `monthly_window` in `config/gardener/compact-summary-quality-evals.json`, as `forever`: no month is summarised |
| `observability.feed_health_keep_months` | 14 | `monthly_window` in `config/gardener/compact-feed-health.json` |
| `observability.host_fingerprint_keep_months` | 14 | `monthly_window` in `config/gardener/compact-host-fingerprint.json` |
| `observability.trace_window_days` | 7 | `window` in `config/gardener/traces.json`, in days |
| `retention.trial_state_days` | 90 | `window` in `config/gardener/trials.json`, in days |
| `retention.max_deletes_per_run` | 200 | `max_deletes_per_run` in `config/gardener/visual-prune.json` |
| `retention.dry_run` | true | `dry_run` in every `config/gardener/<task>.json` |

A task that keeps series keeps its own `window` equal to its `full-grain`
series, so the two spellings of that number are refused unless they agree.
`backend/tests/gardener/tasks/test_every_window_moved_unchanged.py` reads each
old value from a frozen copy of the file as it was and checks the declaration
holds the same one, key by key. **One value changed later, on purpose.** The eval
rows' 14 months became `forever` when every eval row was kept for ever and
nothing summarised a month, so both score names now point at
the compaction window that keeps every row, and the test names that one change
with its reason.

**Validation reads `config/appearance.json`.** That file owns the console window
the published site really uses, and `AppConfig.console` is the layer under it, so
`config.load` runs the same check twice - once against each - and
`config.load_gardener` checks every declaration against the appearance file's
window. The appearance file's digest is not recorded on the run manifest,
because nothing in the run reads a value out of it.

The `aggregate` series of `telemetry-aggregate` is `forever`, and that is a
decision rather than an omission. A shard has to stay readable for a year, and
the folded aggregate costs a measured 63.8 bytes a row over four stages - about
93 KB a year against the shard's 77 MB. Give it a finite window, and it must sit
above the `full-grain` series, or a month would be deleted before it was ever
folded; the gardener loader refuses the pair otherwise.

**What the `full-grain` series of `telemetry-aggregate` governs is the
item-health ledger, and nothing else.** Past the window a month is summarised to
one row per `(date, stage)` in `state/raw/item-health-summary/` by the gardener's
`telemetry-aggregate` task, which reads the month through the ledger door and
files the summary through the same door. The rows themselves go later, when the item-health compaction's
`monthly_window` passes, so a month is always summarised before anything can take
its rows. What survives is every count and every timing total; what goes is the
per-item detail, which is what the console's failure list offers and no rate
needs. Folding the committed `state/item-health/2026-08.csv` on 2026-08-30 turned
4,167 rows and 1,270,452 bytes into 24 rows and 1,531 bytes - **829.8 times
smaller**, and 93,136 bytes a year against the shard's 77,285,830.

The 219 KB a year the old description quoted was an estimate at five stages and
120 bytes a row. Measured it is **63.8 bytes a row over four stages**, because
`plan` wrote no row in that month - so 93 KB a year, 2.4 times cheaper than the
estimate. The conclusion drawn from the estimate - keep the aggregate forever -
stands, and the measurement only strengthens it.

**Each of these ages is one task's own window, and that task spends it.** The
`telemetry-aggregate` task summarises an item-health month past its `full-grain`
series and unlinks the browser's copy of that month past its `public-copy`
series. The item-health, host-fingerprint and feed-health rows are deleted by each ledger's
compaction past its `monthly_window`, and the eval rows' compaction keeps every
month.

**Every eval row is kept, and nothing summarises a month.** The ledger is the
evidence behind every published quality claim, so its rows are kept for ever,
and a chart that wants a monthly figure computes it from the rows when it draws
([../evaluation.md](../evaluation.md#design-rationale)). The `monthly_window` of
`config/gardener/compact-summary-quality-evals.json` is `forever`, so its compaction may pack a
month and never drops one, and its `monthly_keep_days` packs a finished year's
months into one year file.

**Feed health is deleted and never summarised.** Its rows are per-feed-per-run
evidence, the quarantine reads 31 days, and the console reaches at most 366 - so
no older total has a reader, and writing one would persist a shape nothing
consumes. That is why the table above gives it a full-grain age and no summary
beside it. The seen ledger is not on that list at all because it is a lookup
rather than a measurement: its compaction's monthly window is what drops an
old month, and that window may not reach back fewer days than
`collect.seen_window_days`.

**And every retention task ships in dry run.** Each retention declaration carries
`dry_run: true`,
so a pass lists every file a live pass would remove and removes none of them.
The `history` job of `.github/workflows/idhazh-gardener.yml` squashes and force-pushes
`main` on a schedule, so a state file deleted here stops being recoverable from
history once that prune passes over it (`CLAUDE.md` section 8) - which makes
"read the list first" the only safe order. Turning one task's deletion on is a
change to that task's own declaration and its entry in the contract test's list
of live switches
([../../how-to/run-the-pipeline.md](../../how-to/run-the-pipeline.md#turning-state-cleanup-on)).
Measured on this checkout on 2026-09-13: a live run today
removes nothing, and the first files the fourteen-month rules take are the day
files under `state/item-health/2026/08/`, `frontend/public/telemetry/2026-08.csv`,
the day files under `state/feed-health/2026/08/` and the day files under
`state/scores/2026/08/`,
together, on **2027-10-01**.
Reading committed files against a fixed calendar is deterministic, so the spread
is zero. The item-health and eval rows have since moved to the ledger door, so
they no longer go on that date. The seen ledger moved too: its first day was to
go on 2026-11-22 under its old retention task, and its compaction's 2-month
window now only reports what it would delete. Feed health followed: its
compaction's 14-month window only reports, and its first month, August 2026,
would go at the first wake on or after 2027-12-16 once a person turns that
window live. The item-health rows go when the 15-month
`monthly_window` of their compaction passes, and that compaction packs live; no
eval row is ever deleted. A compaction's window has a switch of its own,
`month_deletes_dry_run`, so a ledger can pack live while its window only
reports what it would delete; the item-health and host-fingerprint windows are
live with their packing
([idhazh-gardener.md](idhazh-gardener.md#the-keys-of-a-compaction)).

## See also

- [../config.md](../config.md) - what a knob is, and what is not one.
- [idhazh-gardener.md](idhazh-gardener.md) - the fields of a gardener declaration, and every task that ships.
- [../adaptive-pruning.md](../adaptive-pruning.md) - which policy each tree is under, and the register of every artefact this project writes.
- [../telemetry.md](../telemetry.md) - the logging flags and what each instrument records.
- [../../architecture/publishing/retention.md](../../architecture/publishing/retention.md) - what the fold and the deletion actually do to the tree.
- [../../architecture/publishing/telemetry-series.md](../../architecture/publishing/telemetry-series.md) - the published series these ages bound.
- [../../how-to/prune-a-collection.md](../../how-to/prune-a-collection.md) - deleting the old members of one collection by hand, a ceiling at a time.
