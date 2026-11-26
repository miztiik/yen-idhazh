# What the Hardware route draws

**Last Updated**: 2026-11-26

`/console/machine/` asks what machine the work actually got and how much
resource headroom that work left.
[The shared shell](what-sits-above-every-console-route.md) owns navigation,
the route title/window and on-demand UTC date metadata;
[console-charts.md](console-charts.md) owns chart frames and readouts.
[The machine drawing rules](../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md)
own what may not be pooled.

## The publication boundary

The prerendered page carries configuration and words only. Its route load returns
`machineConfig`; the shared layout supplies navigation, the route title/window
and the closed `Data dates (UTC)` disclosure. That metadata keeps native record
reach and the last console update distinct. The shared payload retains
settings-change metadata for the dated panel rules. With scripts off, all nine
titled panels remain, each with an empty
reserved axis frame. No run, host, article, cost or refusal is embedded in HTML
or route page data.

In the browser, declared questions in `console/queries/machine.ts` ask the native
`item-health`, `host-fingerprint` and `run-shards` ledgers through `sliceOnce`.
The common end is the oldest successful through-day of those families, never
the browser clock. The fixed-work trend separately keeps its item-health-only
endpoint and first-day clamp; its own UTC bounds print beside its readings.
Neither group moves the other's endpoint. Following panels use the chosen preset; snapshot panels use
the newest day and name their newest recorded run rather than falling back to
an older successful one. The bounded widest host population supplies canonical
L3 capacity colour positions and full-identity name qualifiers, so narrowing a
window cannot recolour a capacity or rename a machine. Identity is fingerprint version plus digest;
name-only evidence and missing identity remain separate.

`RouteStatus` owns one delayed shimmer and reserved route-read status, not a
global metric or verdict band. Successful Hardware reads retain their measured
run count; a healthy shared completion adds no standing paragraph. Loading is
not an answer. Reserved panel frames keep their explicit states: quiet says
`Nothing recorded.`, missing says
`Not published yet.`, and an unsuccessful fetch says `Did not arrive.`.
The route retry re-asks only unsuccessful questions and keeps successful reads.
The `run-shards` question that supplies the run count belongs to no panel, so
its own answer joins the route status: a failed read of it offers the same retry
rather than quietly dropping the count. The shared line counts parts of the
record, never panels, so a failed count alone reads `1 part of the record did
not arrive.` and claims no blank panel.
An incompatible index remains unavailable until reload, as the native door requires.
Changing the window cannot allow a late answer from the old request to replace
the new one. Redraws and resizes reuse query rows.

### A narrow recorded shard count

The maintainer approved A1 at 14:30 Europe/Berlin on 2026-10-11, after the actual
Fowler consultation. `run-shards` has only `date`, `run_id` and nullable positive
`shards`, beside the inherited contract version and writer envelope. It is not
a copy of the run plan or manifest. The publisher copies whole Parquet files,
so this narrow schema, not a browser column selection, is the privacy boundary.

Future rows come from the exact final `RunManifest.RunRecord.shards` immediately
after the atomic manifest write in assemble. Historical migration reads only
named `frontend/public/digest/YYYY/MM/DD/run.json` files, one UTC day at a time,
over explicit inclusive bounds. It does not glob the archive or walk its tree.
Only those count cells are validated; legacy duplicate run records therefore
remain readable. The last numeric count per run wins, and a later unknown never
erases a recorded number. Historical null is unknown, not zero.

Repeating a manifest read compares its mappings with the named day's compact
rows and pending raw corrections, settled together using their original filing
provenance. Unchanged mappings file nothing, before or after compaction. A
correction back to the packed value still files when a different count is
pending. Corrections file only changed counts in new immutable raw files. An
unknown cannot demote a numeric count. A rerun therefore cannot grow the ledger
without changed evidence.

Fresh-base publication keeps all completed count files unchanged. If rebuilding
the final manifest corrects its count, the native writer emits one new immutable
file for that UTC day. Publication checks its original invocation identity and
refuses an existing target; it never treats raw count files as derived output.
Further preparation retains that completed correction rather than filing it again.

Native settlement keeps the latest numeric record in the original envelope's
`written_at_ms`, then `file_id` order. Those two existing provenance cells are
retained beside the count row during packing; they are not business fields.
The compact file's new clock cannot promote an old correction. This makes
settlement independent of file order and packing schedule. It is ledger-specific:
`run-plan` keeps its existing first-wins policy even though its business key is
also `(date, run_id)`. Daily packing and reopened months preserve the answer.

The shipped count foundation owns the native files and publication inventory.
Its daily and monthly live indexes were verified on UTC October 12 with no
holes from August 21 through October 9 and newest packed daily October 10.
The first date comes from the actual August Parquet date column, not the
monthly file's name. The reader does not backfill or replace those files.
Before reader merge, the maintainer rechecks live coverage and newest data within
three days. Count foundation delivery alone does not deliver this reader.

Observed host count, maximum shard index, current settings and workflow matrix
size are never substitutes for `shards`. Since 2026-10-12, the value is the
count decided by the plan and dispatched by its matrix, including an operator's
choice. A partial re-run reuses that plan and count. A full re-run that plans
again records its newer plan's count, and settlement keeps the newer numeric
count. A manifest written before 2026-10-12 keeps the count assembly recomputed
from its plan. This is the maintainer's ruling of 2026-10-12.

## Four groups, nine comparisons

Membership and order live in `config/console/machine.json`.

| Group | Panel id | Drawing and grain |
| --- | --- | --- |
| What the machine was doing | `slower-machines` | Separate prefill and decode rankings for the same estimated workload by CPU; measured phase means by CPU and L3 in a disclosure |
| | `platform-mix` | Recorded jobs grouped across vendors by exact reported L3 capacity: one square a job below the configured floor, otherwise stacked day bars; never unique physical-machine counts or a probability of the next draw |
| Where the time went | `slower-on-same-work` | One dated seconds reading for a fixed typical article on one reference machine |
| How close we are to the limits | `closest-to-memory` | Dated articles ranked by minimum available memory, least GiB first |
| | `memory-held` | Existing memory split and overlapping process brackets, for the newest day |
| | `context-headroom` | Daily summary-prompt p90 and stepped configured slot capacity, with the space before the reply between them |
| What the model spends | `article-cost` | Existing processor-time, model-time and incremental-memory tracks over the chosen window |
| | `prompt-reuse` | Summary and label calls on the same UTC calendar, with cached and fresh prompt tokens as shares and dashed settings changes on their actual dates |
| | `read-against-written` | Two run-sequence token lines; Run total or actual Median per article over one paired cohort, with measured/recorded coverage |

Every settled panel has one largest lede, one comparison,
one model-rule declaration and a plot on the panel's own ground.

### What may not be pooled

Refusal is the `hostHalvesConflict`/`machineCounters` rule: disagreeing
dates, missing or invalid shard identities, unreadable host versions, conflicting
hardware cells, too many reported shards, and an index outside the recorded
count refuse the run rather than publish half of it. The bounded widest host
question includes measured logical processors and versioned identity. Its four
legacy CPU columns are finite migration inputs only. Serving evidence does not
participate in hardware conflicts or run counts. A conflicting count file is a
visible unreachable record, never a reactive page crash.

The job list shows **Speed**, independently measured prompt tokens per second.
The Task Performance writer files the digest model server's final totals under
`serve-summarizer`. The panel joins packed observations to `host-fingerprint`
by host unit, run and attempt, never by CPU or a missing host reference. A
matching new row replaces the historical pair entirely, even if it is incomplete.
Without a match, only a complete pair on the same stamped host row can supply
speed. A pair needs both totals and positive prompt seconds. The console band
and [prompt audit](../summarize/throughput.md#the-read-rate-is-checked-against-the-server-and-it-holds)
use the same rule. Missing or later-packed serving data does not move the
Hardware window or remove a job, an article panel or a count. The job list
does not display whole-CI duration.

That same bounded query selects `l3_cache_bytes` for placement aggregation.
`charts/fleet-cache.ts` groups normalized job rows by the exact byte value,
converting only the label to MiB. Missing L3 remains unmeasured, not zero.
The browser reuses the fetched rows for full CPU/job/L3 details and does not
fetch another ledger or infer L2 capacity. The host collector described in
[host metrics](../../reference/host-metrics.md) produces these measurements.

Slower machines chooses the kind with most qualifying articles as reference,
with a deterministic name tie-break. Each article's read or write milliseconds
per token is divided by its own run's reference median, then priced in the
reference kind's typical seconds. The upper-middle nearest rank supplies the
middle; the 90th percentile uses `ceil(0.9*n)-1`. The configured ten-article
floor and kind cap apply independently to each list. Runs without a reference
reading and articles lacking comparable work are counted and printed. Reading
and writing never become one total.

The fixed-work trend is a different comparison. `slower-on-same-work` chooses
one reference machine by qualifying article count, with a lexical name
tie-break, and one typical fresh-input/output token pair over the complete
qualifying window cohort. Each UTC date prices that same article using its
reference machine's upper-middle read and write milliseconds per token,
divided by 1000 and summed as seconds. It keeps its daily calendar, null gaps,
window median, reference details and unqualified/unnamed counts. It does not
borrow the machine ranking's per-run normalization or three-family endpoint.
The existing renderer is mounted inside one route-owned card in the timing
group, with settings rules over its own clamped item-health range.

The run-wide slowest-article ranking is mounted once on
[Pipelines](what-the-pipelines-route-draws.md#the-run-wide-article-ranking-keeps-its-original-evidence-endpoint).
Its source family group and newest-day clamp remain independent of Pipelines'
ordinary item-health endpoint.

Closest-to-memory uses the item's lowest recorded kernel `MemAvailable`, not
memory held or process resident memory. Only valid available/total pairs rank.
Repeated readings of one dated article contribute its lowest available reading,
with the larger total breaking ties. Capacity is printed beside each article.

The summary prompt chart compares positive `summary_input_tokens` with
`n_ctx_configured / n_parallel` from the same item-health row. Its headline
is the highest paired share across the selected window. For each UTC day and
slot size, the prompt trace uses the observed p90 (rank `ceil(0.9 * count)`).
The dashed capacity trace steps at the first observed day with a new slot
size. A mixed day breaks the traces and shows separate dots and paired
readings, not an average capacity or an implied order. Missing settings
leave gaps, with matched and recorded counts in the chart readout.

The shaded gap is the slot size minus prompt use, before reply tokens. It is
not evidence of extraction cuts or completed replies. The disclosure retains
the logarithmic distribution of positive summary prompt counts (even when
capacity is unavailable) and the count of explicitly recorded extraction cuts.
Too few readings leave the distribution empty instead of inventing marks.
Each CPU comparison labels the dashed reference once, with its workload and
unit, rather than repeating a processor name on every track.

Prompt reuse draws one stacked bar a UTC day per call, 0 to 100 percent. The
share is pooled - the day's cached tokens over its
prompt tokens - because a median of per-article shares is not stable here: over
the 26 days 2026-10-20 to 2026-11-14 the label call's per-article median is
exactly 0 on 7 days while its pooled share stays between 23.1 and 40.3 percent.
A row counts only when its prompt and cached cells are both present, finite and
cached is not above prompt; the remainder is 100 minus the cached share, so the
parts total exactly 100. The recorded `label_cache_pct` and `summary_cache_pct`
are those same two cells divided and rounded (`stages/summarize_one_item.py`), not an
independent reading, so the panel does not read them. Both plots share the exact
query's UTC calendar. A settings change can mark a dated gap on a populated
plot; it does not create a token reading or explain a change in cache use.
A wholly unmeasured call keeps its empty state; unavailable change history
is named once. The one-call pipeline has recorded no label calls since 2026-11-17.

Read/write token volume reads the settled compact item-health rows, one per
UTC date, run and article. Both sides require finite, nonnegative input and
output on the same row. Run total sums those rows; Median per article takes
each side's median within that run, never totals divided by article count or
medians summed by day. Input includes cached prompt tokens, and the recorded
totals include all model calls. These are token volumes, not words or uncached
compute. Measured versus recorded article counts qualify partial runs.

`readAgainstWritten` returns both metrics from that cohort and retains its
paired-run calculations. `ReadWritePanel` draws native
`runSeries` geometry, ordered by `compareRuns`: every known run has its own
position, including same-day runs and unmeasured gaps. No scheduled run or
elapsed timestamp is inferred. The numeric route knob
`config/console/machine.json` -> `knobs.read_write_default_metric` selects the
initial mode: 0 is Run total (the shipped default), 1 is Median per article.
The config boundary rejects other values. Runtime radio choices stay in memory
and redraw without a fetch; changing the initial mode is not persistence of a
reader's choice.

The token panel separately asks `tokenDeviations()` through the same staged
data door. Browser DuckDB returns a nullable warning for each real run, trace
and measure; presentation never calculates its statistics. The fixed input is
the configured widest console span, clamped to item-health's first day and
ending at this panel's original three-family endpoint. Display presets do not
change that input. Both measures arrive together, so switching radios does not
fetch or reassess.

Each Read or Written value compares with at most the last 30 earlier qualifying
matching runs, with at least 10 required:
`abs(value - prior_mean) > 3 * prior_sample_stddev`. The current run and every
later run are excluded. The comparison is strict and two-sided. The validated
numeric route knobs `read_write_history_runs`, `read_write_min_prior_runs` and
`read_write_stddev_multiplier` own those defaults; counts are whole numbers
at least two, the minimum cannot exceed the history count, and the multiplier
is positive and finite. Sample deviation zero stays zero: an unequal current
value flags, while an equal value does not.
Rule labels and readouts retain fractional multipliers rather than rounding
them as whole article counts.

Matching uses recorded model identity, quantisation, context, slots, threads,
batch, temperature, output budgets and visual-decision setting.
All measured articles in a run must have one known setup. Contiguous setup
changes reset the baseline, including a return to an older setup; an unknown
or unmeasured setup breaks that segment. The existing settings-change metadata
also resets comparisons, including prompt and configured truncation-cap changes.
An article's actual cut cap is an outcome, not its run's configured setup.
The metadata covers changes only by UTC day, not by run or
per-run prompt identity, so every run on a change day is unassessed. Dates
outside that metadata's comparison coverage are unassessed too. No historical
setting is reconstructed from current configuration.

Missing values, too little earlier matching history, missing or failed history,
unknown/mixed settings and unavailable baselines produce NULL, never FALSE.
A lost day or set-aside file anywhere in the fixed input withholds its
assessments. The raw selected-window read remains independent and still draws
available measurements. History is never expanded beyond its declared bound
to manufacture a baseline.

A hollow warning diamond uses the existing semantic warning role without
recolouring either categorical trace or changing its solid/dashed identity.
The same pointer, keyboard, touch and hover readout explains Read and Written
separately, naming the measured/recorded current cohort, actual prior runs and
their article coverage, mean, sample deviation and strict cutoff. It says
`Investigate; not proof of failure.`, `Not flagged.`, or the exact reason for
`Unassessed`; none changes run status or implies complete-run consumption.
The run readout retains its largest observed height at its current width.
Selecting a shorter explanation must not shrink a bottom-of-page viewport and
clear the shared hover; a width change measures the natural text again.

### The retained measurements

Host busy processor time is `cpu_busy_pct / 100 * cpu_logical_processors *
item_total_ms / 1000`. The busy share covers the whole host, not exclusive model
process work. Physical topology, target affinity, fractional quota and requested
threads are not logical-processor measurements. Missing or disagreeing logical
counts withhold cost, not the eligible item's coverage; recorded busy zero stays
zero. A runner-hour supplies the smallest distinct measured logical count times
3600, or remains unknown.
Model time is `prefill_ms + decode_ms`. Incremental model memory is the step
between neighbouring item indexes of the same shard, never across a restart or
a missing index. Its signed track keeps zero. It cannot attribute memory to
read versus written tokens without a call-boundary measurement.
Both joins retain `date`, `run_id`, machine job and machine shard. An unknown
shard is unmatched, never shard zero. Missing historical item machine job means
work only. Per-item costs remain independent of run-level clock refusal.

The native adapters reuse the declared host read migration. Legacy cores,
threads and maximum frequency remain unknown; a valid legacy probe frequency
can supply the observed average. Algorithm-2 identity does not prove equal
constraints across jobs. Removing a presentation deletes no host or item
measurement, producer collection or persisted contract.
Fingerprint identity is the algorithm and digest pair; equal text under
algorithms 1 and 2 never joins. Name-only evidence stays coarse.

The per-run percentile trend is mounted once on
[Pipelines](what-the-pipelines-route-draws.md#per-run-slow-article-percentiles-keep-their-own-window),
with its original cohort, floor and three-family endpoint.
Memory-held quotes the model server's resident bound as a share of
the whole machine, explicitly at most because its mapped pages overlap.
Every dated comparison names changed dates with no measured column, rather than
claiming nothing changed because no rule could be drawn. No-change and
unavailable-settings sentences come from the shared settings helper.

## Recording certainty

`recording.ts` supplies said-once recording-off, first-recorded and server-counter
notes. A failed or pending question cannot establish a lost day. A day before
host measurements began is not automatically destroyed evidence. Successful
item records without a host record, after host recording began or on an
explicitly lost day, are named **dated article records**, not published
articles: the approved item question does not select publication outcome.
The process watch still supplies measurements needed by retained memory and
cost readers. Missing readings stay unknown. Historical recording limits are described with
the [item-health producer](../sources/item-health.md#what-the-processors-did-and-what-was-taken-from-them);
neither this page nor the context panel fills missing historical settings from
current configuration.

## Validation and rejected substitutions

`console-machine-journey.spec.ts` follows one production-built Hardware journey:
native index and Parquet arrival, a dated readout, and a carried window across
the Pipelines tab. Machine hover projects the UTC day, qualified machine name
and exact count out of that day's recorded jobs. Selecting the day exposes all
machine counts, including known zeros, speed context and actual job identities.
Its two context distributions must contain readings and fit
their cells; the whole document must fit at desktop and
390 pixels. Independent cases check failed-host-only retry, unpublished
indexes, and the actual scriptless prerendered document. Pure native oracles in
`console-machine.spec.ts` retain count refusal, unknowns, identity, signed
timings, paired measurements and null semantics. Backend count tests retain
the twelve compact-plus-pending-raw correction cases.

The shipped representative-browser policy replaces repetitive panel, width,
theme, layout, readout and mode matrices. Deleted charts-ready and panel-driver
frameworks stay deleted. `MachineCharts.svelte`, `MemoryHeldPanel.svelte`,
`ArticleCostPanel.svelte` and `PromptReusePanel.svelte` remain live native
maintainers. Their declared queries, `records.ts`, `counters.ts`,
`article-cost.ts` and `prompt-reuse.ts` supply the actual answers.
Shared chart helpers retain only arithmetic and types used by live callers, not
board constructors or orphan panel wrappers. The finite host normalizer,
recorded counts and native provenance keep their existing semantics.

Rejected: whole manifest or plan publication; fetching whole GitHub manifests
from the browser; substituting observed counts for unknown planned counts;
first-wins count corrections; one read/write total; fake stages or empty marks
standing for measured zero; a previous successful run substituted for the
newest refused run; lost-state claims derived from a fetch failure.

## Design rationale

The hypothetical runner-price panel and its editable controls are permanently
absent, without a hidden or relocated replacement. This loses hypothetical
price totals and per-article scenarios, not a real bill. The shared token query,
paired-run calculations and read/write comparison remain unchanged.
The persisted observability price settings remain compatible; the route no
longer sends them to a drawing or reads a browser-stored price.

The history plot answers observed placement over time, not newest-run machine
constraints, processor contention or model paging. Those three diagnostic
panels are permanently absent, without disclosures or relocations. Historical
mix is retained but is not a substitute for their lost detail.

Placement history samples the shared Console palette by reported L3 capacity
over the widest host query. Reused colours never merge capacities; unmeasured
L3 stays neutral. The same flat colour appears on each capacity's marks and
swatches. Every UTC day orders its segments by that day's counts, largest at
the bottom. Below the placement floor, job squares use the same count order.
CPU names and identity qualifiers stay in the job details.

Framing is one context line and a compact identity key. Below the plot are only
the selected UTC day, its recorded-job total and a short selection hint. Full
dated counts and measured speeds remain in the keyboard/touch day details.

Cache shares stay separate by call because they move independently: between
2026-11-10 and 2026-11-11 the summary call's cached share fell from 95.4 to
77.7 percent while the label call's rose from 32.2 to 40.3. The headings identify
the calls; the same flat fills identify cached and fresh tokens in both.
The tooltip and keyboard readout print both shares, prompt tokens and article
counts. Read/prefill and write/decode keep their respective colours elsewhere
on Hardware. The memory partition keeps its violet available segment; the
[least-memory ranking](../../concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md#a-mark-with-two-named-ends-is-not-a-range-mark-and-it-says-which-end-is-which)
uses a continuous scale to show how little is left.

## See also

- [console.md](console.md) - the shared route frame.
- [console-charts.md](console-charts.md) - the drawing and readout contract.
- [The machine drawing rules](../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) - why machines and calls stay separate.
- [Host measurements](../../reference/host-metrics.md) - corrected cells and finite historical reads.
