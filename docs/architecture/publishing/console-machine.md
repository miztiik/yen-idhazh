# What the Hardware route draws

**Last Updated**: 2026-11-12

`/console/machine/` asks what machine the work actually got, whether its two
clocks agree, and how much resource headroom that work left.
[console.md](console.md) owns the standing band and shared window;
[console-charts.md](console-charts.md) owns chart frames and readouts.
[The machine drawing rules](../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md)
own what may not be pooled.

## The publication boundary

The prerendered page carries configuration and words only. Its route load returns
`machineConfig`; the shared layout supplies the standing band and settings-change
words. With scripts off, all ten titled panels remain, each with an empty
reserved axis frame. No run, host, article, cost or refusal is embedded in HTML
or route page data.

In the browser, declared questions in `console/queries/machine.ts` ask the native
`item-health`, `host-fingerprint` and `run-shards` ledgers through `sliceOnce`.
The common end is the oldest successful through-day of those families, never
the browser clock. Following panels use the chosen preset; snapshot panels use
the newest day and name their newest recorded run rather than falling back to
an older successful one. The bounded widest host population supplies canonical
full-identity palette slots and name qualifiers, so narrowing a window cannot
recolour or rename a machine. Identity is fingerprint version plus digest;
name-only evidence and missing identity remain separate.

`RouteStatus` owns one delayed shimmer and one reserved standing sentence.
Loading is not an answer. Quiet says `Nothing recorded.`, missing says
`Not published yet.`, and an unsuccessful fetch says `Did not arrive.`.
The standing retry re-asks only unsuccessful questions and keeps successful reads.
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

## Four groups, ten comparisons

Membership and order live in `config/console/machine.json`.

| Group | Panel id | Drawing and grain |
| --- | --- | --- |
| What the machine was doing | `two-clocks` | One ranked gap percentage per shard of the newest recorded run, with the allowed-disagreement rule; the item and independent server readings are printed together |
| | `slower-machines` | Separate Reading and Writing rankings of comparable work by machine kind |
| | `platform-mix` | Shipped placement counts: one square a job below the configured floor, otherwise stacked day bars; never a probability of the next draw |
| Where the time went | `tail-trend` | Existing five percentile subplots, one mark a qualified run and one shared scale |
| How close we are to the limits | `closest-to-memory` | Dated articles ranked by memory held; the empty remainder ends at total machine memory |
| | `memory-held` | Existing memory split and overlapping process brackets, for the newest day |
| | `context-headroom` | Label and summary request distributions on one logarithmic domain, with recorded context and cut-request rules |
| What the model spends | `article-cost` | Existing processor-time, model-time and incremental-memory tracks over the chosen window |
| | `prompt-reuse` | Daily median label tokens held beside median summary tokens read fresh, plus the independent server-share check |
| | `read-against-written` | Two run-sequence token lines; Run total or actual Median per article over one paired cohort, with measured/recorded coverage |

The two clocks open the route because a disagreement decides whether the rates
below may be quoted. Every settled panel has one largest lede, one comparison,
one model-rule declaration and a plot on the panel's own ground.

### What may not be pooled

Refusal is still the existing `mergeHost`/`machineCounters` rule: disagreeing
dates, missing or invalid shard identities, unreadable host versions, conflicting
host cells, too many reported shards, and an index outside the recorded count
refuse the run rather than publish half of it. The bounded widest host question
includes measured `cpu_logical_processors` and `model_load_ms` for exact refusal
parity, alongside versioned identity and independent server counters. Its four
legacy columns are finite migration inputs only. No private manifest inputs are
added. A conflicting count file is a visible unreachable record, never a
reactive page crash.

Slower machines chooses the kind with most qualifying articles as reference,
with a deterministic name tie-break. Each article's read or write milliseconds
per token is divided by its own run's reference median, then priced in the
reference kind's typical seconds. The upper-middle nearest rank supplies the
middle; the slowest-tenth notch uses `ceil(0.9*n)-1`. The configured ten-article
floor and kind cap apply independently to each list. Runs without a reference
reading and articles lacking comparable work are counted and printed. Reading
and writing never become one total.

The run-wide slowest-article ranking is mounted once on
[Pipelines](what-the-pipelines-route-draws.md#the-run-wide-article-ranking-keeps-its-original-evidence-endpoint).
Its source family group and newest-day clamp remain independent of Pipelines'
ordinary item-health endpoint.

Closest-to-memory uses `total - minimum available`, not process resident
memory. Repeated readings of one dated article contribute its tightest held
reading, with a deterministic total-memory tie-break. Date remains in the label
so the same article measured on another day is not accidentally first-wins.
The total-memory endpoint is the machine's own, and article length is context.

Context distributions use positive readings only and share a logarithmic
domain. The reading rule is the smallest recorded `n_ctx_configured/n_parallel`;
other limits are named. A recorded truncation cap contributes the upper-middle
label-request rule. No cut rows means `No article was cut in this window.`
Too few readings keep an honest empty distribution instead of invented marks.
Each distribution measures its own shrinking grid cell. The share axis keeps
space for its percentage labels, including on a narrow screen.
Hardware's ranked rule names also stay inside their own tracks. A rule at the
maximum must not push its name beyond the document. The label's position uses
the same track fraction as the marker, offset by that fraction of its own width;
long names wrap within the track. The marker and numeric rule do not move.

Prompt reuse compares paired input and cached cells on the same article:
invalid, negative or over-input cache counts do not cross-pair with another
row. Our check is the pooled held share, the server's is its recorded middle
share, and the complete-reading denominator is printed. Held label text follows
article length; a summary-held count would mostly repeat that length because
the summary call reuses the label prompt. Fresh summary text answers the useful
second question instead.
Its lede quotes the upper-middle held count over requests in the selected
window, not a median of daily medians that would give a quiet day extra weight.
The dated lines still quote each day's own median.

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

The tail retains all five percentiles on one domain; under-floor runs are
printed rather than drawn. Settings-change rules cross the whole stack.
Its lede quotes the slowest tenth in seconds, not a ratio of the two extreme
percentiles. Memory-held quotes the model server's resident bound as a share of
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
their cells; the clock-rule names and whole document must fit at desktop and
390 pixels. Independent cases check failed-host-only retry, unpublished
indexes, and the actual scriptless prerendered document. Pure native oracles in
`console-machine.spec.ts` retain count refusal, unknowns, identity, signed
timings, paired measurements and null semantics. Backend count tests retain
the twelve compact-plus-pending-raw correction cases.

The shipped representative-browser policy replaces repetitive panel, width,
theme, layout, readout and mode matrices. Deleted charts-ready and panel-driver
frameworks stay deleted. `MachineCharts.svelte`, `MemoryHeldPanel.svelte` and
`ArticleCostPanel.svelte` remain live native maintainers. Their declared queries,
`records.ts`, `counters.ts` and `article-cost.ts` supply the actual answers.
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

Machine identity uses D3's built-in [PiYG scheme](https://d3js.org/d3-scale-chromatic/diverging#schemePiYG) through the existing
`chart.palette` selector, aligned with the rest of the console. Its widest built-in
scheme supplies the ordinal slots; reused slots never merge identities. Each known machine has the
same optional opaque lighter-to-base treatment, restarting inside its segment
or job square. Missing speed does not remove identity; missing identity stays
neutral. Top-kind selection and folded totals remain as compact legend groups.
Every UTC day orders its actual machine segments from largest count at the
bottom to smallest at the top, independently of other days. Folded identities
remain separate segments even when daily ranking parts them. Their counts still
sum exactly to the group total. The small-cohort job squares use the same daily
count ordering.

`d3-scale-chromatic` supplies the published colour schemes; no palette is
hand-authored here. Existing D3 scale/color dependencies are reused. Only named
schemes are imported, rather than another chart engine; its upstream complete
minified distribution is about 20 KB before tree shaking, not the browser delta.
Pale machine fills and their swatches retain a configured neutral edge, so a
stock midpoint remains visible without changing its D3 colour or count.

Framing is one context line and a compact identity key. Below the plot are only
the selected UTC day, its recorded-job total and a short selection hint. Full
dated counts and measured speeds remain in the keyboard/touch day details.

## See also

- [console.md](console.md) - the shared route frame.
- [console-charts.md](console-charts.md) - the drawing and readout contract.
- [The machine drawing rules](../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) - why machines and calls stay separate.
- [Host measurements](../../reference/host-metrics.md) - corrected cells and finite historical reads.
