# Instrument switches and cleanup ages

**Last Updated**: 2026-09-23

Which instruments run at all, and how long what they write is kept. One JSON
block holds both - `observability` in `config/idhazh.json` - because a switch
that stops a record being written and an age that stops it being kept are the
two ends of the same question. What a knob is, and why these are knobs rather
than constants, is [../config.md](../config.md).

## Observability surface

`observability` is the block that decides which instruments run at all:

| Knob | Default | What it switches off |
| --- | --- | --- |
| `evaluation_enabled` | `true` | The faithfulness scorer, and so every row in `state/scores.csv`. |
| `telemetry_publish` | `true` | The copy into `frontend/public/telemetry/<YYYY-MM>.csv`. |
| `tracing_enabled` | `true` | The span tree. False writes no trace under `state/traces/` and no span rollup. |
| `sample_rate` | `1.0` | Nothing. It is the fraction of runs whose scorer runs. |
| `item_health_full_grain_months` | `14` | Nothing. It is where `state/item-health/` stops being kept item by item. |
| `item_health_aggregate_keep_months` | `null` | Nothing by default. Null means a folded month is never removed. |
| `feed_health_keep_months` | `14` | Nothing. It is where `state/feed-health/` stops keeping a month, and past it the month is deleted rather than summarised. |
| `host_fingerprint_keep_months` | `null`, committed `14` | Nothing by default. Null means `state/host-fingerprint/` never loses a month, and the committed file names the window one step ahead of the default. Set, it may not sit below `public_machine_keep_months`. |
| `scores_full_grain_months` | `14` | Where `state/scores/` stops being kept item by item. Past it a month becomes `state/score-archive/<YYYY-MM>.json` and the shard is deleted. |
| `score_archive_keep_months` | `null` | Nothing by default. Null means a summarised score month is never removed. |
| `visuals_full_grain_months` | `14` | Where `state/visuals/` stops being kept attempt by attempt. Past it a month folds to the eight-term group in `state/visual-aggregate/` and the shard is deleted. |
| `visual_aggregate_keep_months` | `null` | Nothing by default. Null means a folded visual month is never removed. |
| `public_telemetry_keep_months` | `14` | Nothing. It is where `frontend/public/telemetry/` stops keeping a shard, and it must equal `item_health_full_grain_months`. |
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

## Every store names its own cleanup age

Until 2026-09-02 one knob decided when a month stopped being kept at full grain
- and it decided it for `state/item-health/` and nothing else.
`state/feed-health/`, `state/scores/` and `frontend/public/telemetry/` had no
cleanup age at all, so three stores grew with nothing to stop them while the
fourth was tuned by a number that said nothing about them.

Fourteen names replace it, each a knob and not a constant (Guardrail #6). Ten are
full-grain windows, returned together by `ObservabilityConfig.full_grain_months`
so `refuse_windows_shorter_than` can check every one of them against what a
console read still selects; three are the ages that govern what a fold leaves
behind; and one is `visuals_full_grain_months`, which is a full-grain window and
is **not** in that mapping yet, because no console read opens one of its shards
today ([../adaptive-pruning.md](../adaptive-pruning.md#the-visual-fold-key-is-eight-terms-and-it-could-not-wait)).

| Store | Full grain | Summary after it |
| --- | --- | --- |
| `state/item-health/` | `item_health_full_grain_months` (14) | `item_health_aggregate_keep_months` (null) |
| `state/scores/` | `scores_full_grain_months` (14) | `score_archive_keep_months` (null) |
| `state/visuals/` | `visuals_full_grain_months` (14) | `visual_aggregate_keep_months` (null) |
| `state/feed-health/` | `feed_health_keep_months` (14) | none - a per-feed-per-run record is not a total worth keeping |
| `state/host-fingerprint/` | `host_fingerprint_keep_months` (null by default, 14 committed) | none - one job's silicon on one run, and a total over an old month names no machine |

And one for each published copy, because a reader fetches those and our own disk
is not what bounds them:

| Published copy | Age | Paired with |
| --- | --- | --- |
| `frontend/public/telemetry/` | `public_telemetry_keep_months` (14) | `item_health_full_grain_months` |
| `frontend/public/run-days/` | `public_run_days_keep_months` (14) | nothing - the source is the day payloads, whose retention is the archive's |
| `frontend/public/day-metrics/` | `public_day_metrics_keep_months` (14) | nothing - `state/day-metrics/` has no age of its own |
| `frontend/public/machine/` | `public_machine_keep_months` (14) | `host_fingerprint_keep_months`, which may not sit below it - the shard is folded from that tree and from `state/item-health/` |
| `frontend/public/span-rollup/` | `public_span_rollup_keep_months` (14) | nothing |

**Two ages left this table on 2026-09-16.** `public_scores_keep_months` and
`public_feed_health_keep_months` bounded published copies of `state/scores/` and
`state/feed-health/` that no console route ever fetched, so the trees went and
the two knobs with them. A config file still spelling either is refused by name
rather than ignored, and it is sent nowhere: the two ledgers above keep their
own ages, which is a different number for a different store.

**Two more ages sit outside this block**, because each is a read cover first and
a cleanup age second: `observability.trace_window_days` bounds `state/traces/`,
and `collect.seen_window_days` bounds `state/seen/` by naming the day files the
reader opens.

**A third sits outside it for the opposite reason.** `retention.trial_state_days`
(90) bounds `state/<run.trial_state_dirname>/`, and nothing reads those rows at
all - no published series, no gate, no console band. The age is about disk and
about a reader who opens `state/` and wonders what a directory is, so it needs
no full-grain window, no summary and no published pair.

**Null keeps a summary indefinitely, and a finite value must sit above its own
full-grain window.** The contract refuses any other pair, so a month can never
be deleted before the thing that replaces it has been written.

**A published copy must last exactly as long as the ledger it copies, where
there is one.** The contract refuses any pair but equality for the three copies
that name a source, in both directions: a published month whose source has been
folded away is a rate nobody can check, and a source month with no published copy
is a window the console cannot draw. The other four have no state ledger behind
them and are bounded by their own knob alone.

**This block sets the ages. Which policy a store is under - fold, delete or keep
- is [../adaptive-pruning.md](../adaptive-pruning.md)**, which is also where an age is
judged to be the wrong instrument for a store rather than merely the wrong
number.

### Why 14 and not 13

Fourteen is not a year plus one. It is the number of month files a console read
can open, and the old value was one short.

`console.max_window_days` is 366 and `ledger.shards_in_window` walks **367
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
Gregorian cycle to prove it. Measured 2026-09-02 over all **146,097** anchor
dates - arithmetic over the calendar, so the spread is zero by construction:
fourteen months keeps back at least as far as the console reads on every one of
them, and it is exactly tight on **3,636** of them, 2.5 percent. Those same
3,636 dates are where thirteen deletes a shard the console still opens.

### A config still carrying the old names

`keep_months` and `hard_delete_after_months` were read and dropped for a day, so
that the rows spending the new ages could land one at a time. Since 2026-09-03 a
file spelling either is **refused**, and the message names the knob that governs
the same store: `item_health_full_grain_months` and
`item_health_aggregate_keep_months`.

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

**Validation reads `config/appearance.json`.** That file owns the console window
the published site really uses, and `AppConfig.console` is the layer under it, so
`config.load` runs the same check twice - once against each. The appearance
file's digest is not recorded on the run manifest, because nothing in the run
reads a value out of it.

`item_health_aggregate_keep_months` defaults to null - never - and that is a
decision rather than an omission. A shard has to stay readable for a year, and
the folded aggregate costs a measured 63.8 bytes a row over four stages - about
93 KB a year against the shard's 77 MB. Set it, and it must sit above
`item_health_full_grain_months`, or a month would be deleted before it was ever
folded; the contract refuses the pair otherwise.

**What `item_health_full_grain_months` governs is `state/item-health/`, and
nothing else.** Past the window a month is folded to one row per `(date, stage)`
in `state/telemetry-aggregate/<YYYY-MM>.csv` and the full-grain shard is deleted,
by `idhazh prune-state` in the assemble job - after the day is committed, never
before it. What survives is every count and every timing total; what goes is the
per-item detail, which is what the console's failure list offers and no rate
needs. Folding the committed `state/item-health/2026-08.csv` on 2026-08-30 turned
4,167 rows and 1,270,452 bytes into 24 rows and 1,531 bytes - **829.8 times
smaller**, and 93,136 bytes a year against the shard's 77,285,830.

The 219 KB a year the old description quoted was an estimate at five stages and
120 bytes a row. Measured it is **63.8 bytes a row over four stages**, because
`plan` wrote no row in that month - so 93 KB a year, 2.4 times cheaper than the
estimate. The description keeps the estimate's conclusion, which the measurement
only strengthens.

**Five of the six now decide something, and the same step spends them.** From
2026-09-03 `idhazh prune-state` folds `state/item-health/` past
`item_health_full_grain_months`, unlinks the browser's copy of that month past
`public_telemetry_keep_months`, deletes `state/feed-health/` past
`feed_health_keep_months`, and archives `state/scores/` past
`scores_full_grain_months` before deleting the shard. `score_archive_keep_months`
is the sixth and is null, so nothing has ever deleted an archive. From 2026-09-19
the same step also deletes `state/host-fingerprint/` past
`host_fingerprint_keep_months`, which was the one committed day-filed ledger with
no age at all.

**A score month is summarised before it is deleted, and it is the only store here
with a summary in front of the deletion.** The archive is
`state/score-archive/<YYYY-MM>.json`: the shard's SHA-256 and row count, one
digest per distinct measurement, and one cohort per (date, run, row version,
model, pipeline, scorer) carrying counts, ten faithfulness deciles, three bands,
the boolean signal counts, the cut counts, the premise-digest counts and
`{n, sum, sum_squares, min, max}` per numeric column. Two things make that
necessary rather than tidy: the ledger is the evidence behind every published
quality claim, and `evals.writer` refuses a repeat measurement by reading the
rows - so a shard deleted with no index would make every measurement in it
scoreable again as if it were new. **Measured 2026-09-03 over both committed
shards: 4,266,655 bytes of shard become 557,290 bytes of archive, 13.1 percent,
and three reads gave byte-identical results so the spread is zero.** What that
buys, in years, is in
[../../architecture/publishing/retention.md](../../architecture/publishing/retention.md#what-bounds-the-committed-state-tree).

**Feed health is deleted and never summarised.** Its rows are per-feed-per-run
evidence, the quarantine reads 31 days, and the console reaches at most 366 - so
no older total has a reader, and writing one would persist a shape nothing
consumes. That is why the table above gives it a full-grain age and no summary
beside it. `state/seen/` is not on that list at all because it is a lookup rather
than a measurement: an out-of-window day file is deleted through
`collect.seen_window_days`.

**And the step ships in dry run.** It prints every file a live run would remove
and removes none of them. `.github/workflows/prune.yml` squashes and force-pushes
`main` on a schedule, so a state file deleted here stops being recoverable from
history once that prune passes over it (`CLAUDE.md` section 8) - which makes
"read the list first" the only safe order. Turning the deletion on is a one-line
commit of its own. Measured on this checkout on 2026-09-13: a live run today
removes nothing, the first file any store loses is `state/seen/2026/08/23.csv` on
**2026-11-22**, and the first files the fourteen-month rules take are the day
files under `state/item-health/2026/08/`, `frontend/public/telemetry/2026-08.csv`,
the day files under `state/feed-health/2026/08/` and the day files under
`state/scores/2026/08/`,
together, on **2027-10-01**. The sight date was 2026-11-30 while that ledger
filed by month, because a whole month shard survived if any of its days was in
range; at day grain the file the window stops naming is the file that goes.
Reading committed files against a fixed calendar is deterministic, so the spread
is zero.

## See also

- [../config.md](../config.md) - what a knob is, and what is not one.
- [../adaptive-pruning.md](../adaptive-pruning.md) - which policy each store is under, and the register of every artefact this project writes.
- [../telemetry.md](../telemetry.md) - the logging flags and what each instrument records.
- [../../architecture/publishing/retention.md](../../architecture/publishing/retention.md) - what the fold and the deletion actually do to the tree.
- [../../architecture/publishing/telemetry-series.md](../../architecture/publishing/telemetry-series.md) - the published series these ages bound.
- [../../how-to/prune-a-collection.md](../../how-to/prune-a-collection.md) - running the step that spends these ages.
