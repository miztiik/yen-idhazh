# What the Hardware route draws

**Last Updated**: 2026-10-12

`/console/machine/` asks what machine the work actually got, whether its two
clocks agree, and what would change the cost of that work.
[console.md](console.md) owns the standing band and shared window;
[console-charts.md](console-charts.md) owns chart frames and readouts.
[The machine drawing rules](../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md)
own what may not be pooled.

## The publication boundary

The prerendered page carries configuration and words only. Its route load returns
`machineConfig`; the shared layout supplies the standing band and settings-change
words. With scripts off, all fifteen titled panels remain, each with an empty
reserved axis frame. No run, host, article, cost or refusal is embedded in HTML
or route page data.

In the browser, declared questions in `console/queries/machine.ts` ask the native
`item-health`, `host-fingerprint` and `run-shards` ledgers through `sliceOnce`.
The common end is the oldest successful through-day of those families, never
the browser clock. Following panels use the chosen preset; snapshot panels use
the newest day and name their newest recorded run rather than falling back to
an older successful one. The widest host population supplies one machine-colour
ramp, so narrowing a window cannot recolour a machine.

`RouteStatus` owns one delayed shimmer and one reserved standing sentence.
Loading is not an answer. Quiet says `Nothing recorded.`, missing says
`Not published yet.`, and an unsuccessful fetch says `Did not arrive.`.
The standing retry re-asks only unsuccessful questions and keeps successful reads.
An incompatible index remains unavailable until reload, as the native door requires.
Changing the window cannot allow a late answer from the old request to replace
the new one. Redraws and resizes reuse query rows.

### A narrow recorded shard count

The owner approved A1 at 14:30 Europe/Berlin on 2026-10-11, after the actual
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
Before reader merge, the owner rechecks live coverage and newest data within
three days. Count foundation delivery alone does not deliver this reader.

Observed host count, maximum shard index, current settings and workflow matrix
size are never substitutes for `shards`. The CLI currently recomputes the count
recorded in the final manifest; it can differ from the workflow dispatch matrix.
Preserving that exact historical and future manifest value is this change's
contract. Correcting dispatch-versus-assembly semantics requires a separate
priced issue, fixture and owner decision, not a correction hidden here.

## Four groups, fifteen comparisons

Membership and order live in `config/console/machine.json`.

| Group | Panel id | Drawing and grain |
| --- | --- | --- |
| What the machine was doing | `two-clocks` | One ranked gap percentage per shard of the newest recorded run, with the allowed-disagreement rule; the item and independent server readings are printed together |
| | `processor-lost` | Two tile strips: one day and one shard of the newest run; unrecorded is not a zero |
| | `disk-reads` | Daily disk-wait and disk-copy strips; first-on-shard weight loads are excluded and counted |
| | `machine-cards` | Existing cards, one machine of the newest run, retaining flags, cache, copy-speed, clock, uptime and native location disclosure |
| | `slower-machines` | Separate Reading and Writing rankings of comparable work by machine kind |
| | `platform-mix` | Shipped placement counts: one square a job below the configured floor, otherwise stacked day bars; never a probability of the next draw |
| Where the time went | `slowest-articles` | Longest elapsed articles of the newest run, with measured stages and queue context |
| | `tail-trend` | Existing five percentile subplots, one mark a qualified run and one shared scale |
| How close we are to the limits | `closest-to-memory` | Dated articles ranked by memory held; the empty remainder ends at total machine memory |
| | `memory-held` | Existing memory split and overlapping process brackets, for the newest day |
| | `context-headroom` | Label and summary request distributions on one logarithmic domain, with recorded context and cut-request rules |
| What the model spends | `article-cost` | Existing processor-time, model-time and incremental-memory tracks over the chosen window |
| | `prompt-reuse` | Daily median label tokens held beside median summary tokens read fresh, plus the independent server-share check |
| | `read-against-written` | Read and written token totals over the same qualified dated run population |
| | `counterfactual-cost` | Running dated total, four editable-price figures; a counterfactual, never a bill |

The two clocks open the route because a disagreement decides whether the rates
below may be quoted. Every settled panel has one largest lede, one comparison,
one model-rule declaration and a plot on the panel's own ground.

### What may not be pooled

Refusal is still the existing `mergeHost`/`machineCounters` rule: disagreeing
dates, missing shard identities, conflicting host cells, too many reported
shards, and an index outside the recorded count refuse the run rather than
publish half of it. `cores` and `model_load_ms` are already published host
cells; the widest host question explicitly includes them for that exact parity.
No private manifest inputs are added. A conflicting count file is a visible
unreachable record, never a reactive page crash.

Slower machines chooses the kind with most qualifying articles as reference,
with a deterministic name tie-break. Each article's read or write milliseconds
per token is divided by its own run's reference median, then priced in the
reference kind's typical seconds. The upper-middle nearest rank supplies the
middle; the slowest-tenth notch uses `ceil(0.9*n)-1`. The configured ten-article
floor and kind cap apply independently to each list. Runs without a reference
reading and articles lacking comparable work are counted and printed. Reading
and writing never become one total.

Slowest articles stacks only complete nonnegative fetch, extract, summarize
and checking measurements with a positive recorded stage gap as `Other`.
A negative gap draws one whole elapsed bar and prints the overlap. Queue wait
sits outside elapsed time. Nothing recorded is not a zero stage.

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

### The retained measurements

Article processor cost is the busy share times **threads**, not cores, times
the article's elapsed clock. Missing or disagreeing thread readings stay absent.
Model time is `prefill_ms + decode_ms`. Incremental model memory is the step
between neighbouring item indexes of the same shard, never across a restart or
a missing index. Its signed track keeps zero. It cannot attribute memory to
read versus written tokens without a call-boundary measurement.
Both joins retain `date`, `run_id`, machine job and machine shard. An unknown
shard is unmatched, never shard zero. Card rows carry only their declared
public cells; they do not invent a job or shard or fill private unasked inputs.

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
Cards retain `data-machine-record` and its existing reasons.
Processor and disk ledes count marked days against recorded days. A marked day
below the separate naming threshold remains marked; it is never described as
a quiet machine. The original recording and threshold detail remains beside it.

## Validation and rejected substitutions

`console-machine-journey.spec.ts` follows one production-built Hardware journey:
native index and Parquet arrival, a dated readout, and a carried window across
the Pipelines tab. Its two context distributions must contain readings and fit
their cells; the clock-rule names and whole document must fit at desktop and
390 pixels. Independent cases check failed-host-only retry, unpublished
indexes, and the actual scriptless prerendered document. Pure native oracles in
`console-machine.spec.ts` retain count refusal, unknowns, identity, signed
timings, paired measurements and null semantics. Backend count tests retain
the twelve compact-plus-pending-raw correction cases.

The shipped representative-browser policy replaces repetitive panel, width,
theme, layout, readout and mode matrices. Deleted charts-ready and panel-driver
frameworks stay deleted. Retained production components and ECharts remain
until Row 11's approved retirement; test integration does not remove them.

Rejected: whole manifest or plan publication; fetching whole GitHub manifests
from the browser; substituting observed counts for unknown planned counts;
first-wins count corrections; one read/write total; fake stages or empty marks
standing for measured zero; a previous successful run substituted for the
newest refused run; lost-state claims derived from a fetch failure.

## See also

- [console.md](console.md) - the shared route frame.
- [console-charts.md](console-charts.md) - the drawing and readout contract.
- [The machine drawing rules](../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) - why machines and calls stay separate.
