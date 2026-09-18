# Item Health

**Last Updated**: 2026-09-17

What every planned item did on every run, where that record lives, and which
failures count against a source. This is item-grain evidence. Feed health is
source-grain evidence. The
[source lifecycle flow](health.md#from-item-outcome-to-feed-rest-or-retirement)
shows where item evidence stops and feed quarantine or retirement begins.

**This ledger is the pipeline's spine.** It is the most granular record the
pipeline keeps, and every other telemetry surface is derived from it - the
browser's month mirror under `frontend/public/telemetry/`, the day aggregate in
`state/day-metrics/`, and the operator console. Owner decision, 2026-09-14: new
telemetry lands here first and is projected outward, rather than each surface
growing its own store.

## Every item, every run, one row

`state/item-health/<YYYY>/<MM>/<DD>.csv`. One row is written for each planned
item on each run, whether the item succeeds or fails. Two stages write it: a
worker commits the rows for its own items as each one settles, and Assemble
writes the whole day's census afterwards. A worker also leaves its own copy of
the row beside the item's other payloads, which is
[the file below](#the-row-on-the-shard-before-the-ledger-has-it).

The row carries 119 columns. `ItemHealthRow.csv_columns` in
`backend/idhazh/contracts/item_health.py` is the list, and this page does not
restate it - a second copy of 119 names is a second thing to keep in step, and
it drifts. [item-health-columns.md](item-health-columns.md) is the generated
answer to "where does this cell come from": every column, the eight questions
they group into, which module puts a value under each name, whether that value
reaches this row, and whether any committed row carries it. The columns a
reader asks about most are described one by one further down.

**`stage_gap_ms` is the one to watch.** It is `item_total_ms` minus every named
stage. Unattributed time is the only column that can catch a regression in a
stage nobody has thought to name yet, which is how a five-fold slowdown ran for
six days in September 2026 without any surface reporting it.

### What actually fills today

**Most of these columns are empty on every committed row**, and the count is on
[item-health-columns.md](item-health-columns.md) beside the column it is about,
so it moves when the wiring does rather than needing this paragraph edited.
Read an absence as "nothing carries this into the row" rather than "this item
had no value": the columns landed with the instrument that measures them, and
the producer wiring that carries the same value into the ledger row did not
land with them.

The file is append-only inside its own day. It is not kept for ever: a month
older than `observability.item_health_full_grain_months` (14) is folded to one
row per `(date, stage)` in `state/telemetry-aggregate/<YYYY-MM>.csv` and that
month's day files are deleted, by `idhazh prune-state` after the day is
committed. The browser's copy of that same month under
`frontend/public/telemetry/` goes in the same step. Until 2026-09-03 this page
said the ledger was never pruned, which was true when it was written and stopped
being true when the fold landed.

**The boundary is still a month and only the files below it are days.** The fold
is where the two grains meet: it reads a month's day files - at most 31 - writes
one aggregate, reads it back, and only then unlinks them.

**The step ships in dry run.** It logs every file a live run would remove and
removes none of them, because `.github/workflows/prune.yml` force-pushes `main`
on a schedule and a deleted state file stops being recoverable from history once
that prune passes over it (`CLAUDE.md` section 8). Turning the deletion on is a
one-line commit taken after a scheduled run has printed the list. Measured on
this checkout on 2026-09-02, the earliest a live run would touch this ledger is
**2027-10-01**, when `state/item-health/2026/08/` falls below the window.

The 30-day window on this page is a read-side parameter and is unrelated to that
age. Day files follow `state/published/`, and `state/seen/` and
`state/feed-health/` followed it too in the days after - owner instruction,
2026-09-10, and the reason is in
[../../concepts/partitions.md](../../concepts/partitions.md#a-store-and-its-mirror-may-file-at-different-grains).
What the fold keeps, what it costs and why fourteen is
[../publishing/retention.md](../publishing/retention.md#what-bounds-the-committed-state-tree).

## The structure

Three files carry one item-health row, and each owns one thing:

| Where | What it owns |
| --- | --- |
| `backend/idhazh/contracts/item_health.py` | the shape: field order, types, enums, the validator, and `csv_columns` |
| `schemas/item-health-row.schema.json` | the generated schema. Never hand-edited (Guardrail #3) |
| `backend/idhazh/ledger.py` | the append, the header guard, and the day file path |

**One definition of the column list.** `ItemHealthRow.csv_columns` returns
`tuple(model_fields)`, so the CSV header IS the contract's field order. A writer
and a reader cannot disagree, and there is no second list to forget.

**The file layout.** One file per calendar day of the `date` column, nested
`<YYYY>/<MM>/<DD>.csv`. A row is placed by the digest date it describes, not by
the clock when it was written, so a run that publishes just after midnight UTC
still files under the day it published. Header on line 1, `\n` endings, `utf-8`,
no quoting beyond what `csv` needs. `day_partition.day_files` is the walk, and it
refuses a name it cannot place rather than skipping it - a file the reader cannot
place is how it starts missing rows.

**Every cell is a string.** `csv_row` writes `""` for an absent optional and
`from_csv_row` reads `""` back as `None`. There is no sentinel number and no
`NULL` literal, because both of those get averaged by accident one day.

The columns a reader asks about most, in file order. This is the subset the
prose below turns on, not the whole list, and nothing here counts them - a
count of a subset is one more number to keep in step.
[item-health-columns.md](item-health-columns.md) is every column, grouped by
the question it answers:

| Column | Type | Present when | What it answers |
| --- | --- | --- | --- |
| `version` | date-stamp | always | which contract wrote this row (section 11) |
| `date` | `YYYY-MM-DD` | always | the digest day, and the file this row lives in |
| `run_id` | `<date>-<execution>` | always | which execution wrote it. The trailing field is the CI run id, and a small ordinal on rows written before 2026-08-31 |
| `item_id` | slug | always | `<vertical>-<ten decimal digits>` on a row written before 2026-09-12 and `<vertical>-<sixteen base32 symbols>` after it, derived from the address either way. Join on `url_key`, and see below |
| `url_key` | sha256 | always | the stable article key. Join on this, not `item_id` |
| `canonical_url` | URL | always | the address, after a run artifact has expired |
| `vertical` | slug | always | which topic queue it was planned into |
| `source_id` | slug | always | which feed contributed it |
| `stage` | enum | always | where it stopped: `plan`, `fetch`, `extract`, `summarize`, `publish`. The schema lists `visual` because the enum is inlined; this column refuses it |
| `outcome` | enum | always | `ok` or `failed` |
| `code` | enum | on failure, or as an `ok` extract signal | the typed cause |
| `http_status` | 100-599 | `fetch` rows only | what the server said |
| `source_chars` | int | once extract ran | article size before summarizing |
| `source_words` | int | once extract ran | the denominator of compression |
| `summary_words` | int | once summarize succeeded | the numerator of compression |
| `detail` | <= 2,000 chars, one line of printable ASCII | any failed row, from 2026-09-15 | our own reason, usually the exception message. Never source text |
| `fetch_ms` | int | once fetch ran | wall-clock for the HTTP read |
| `extract_ms` | int | once extract ran | wall-clock for text extraction |
| `summarize_ms` | int | once the model replied | wall-clock for the whole model request |
| `prefill_ms` | int | when the runtime reports it | the model reading the prompt, added over every call below |
| `decode_ms` | int | when the runtime reports it | the model writing the reply, added over every call below |
| `input_tokens` | int | when the runtime reports it | prompt tokens, cached ones included, added over every call below |
| `output_tokens` | int | when the runtime reports it | tokens written, added over every call below |
| `cached_tokens` | int | when the runtime reports it | prompt tokens reused instead of read, added over every call below |
| `source_words_before_cap` | int | once extract ran, from 2026-08-28 | how long the body was before the cap cut it |
| `shard` | int | a worker wrote the row, from 2026-08-30 | which of the run's workers produced it |
| `span_integrity` | bool | the item carried text, from 2026-09-08 | did every element span cut its own characters out of the article |
| `elements_found` | int | `span_integrity` is true, from 2026-09-08 | Tier 1 elements the candidate pass kept |
| `element_class` | enum | `span_integrity` is true, from 2026-09-08 | `chartable`, `narrative` or `unclassified` |
| `model_calls` | int | a split was recorded, from 2026-09-12 | how many calls the five cells above add up over |
| `label_kind` | enum | a split was recorded, from 2026-09-12 | `summarize`, `visual_plan`, `label` or `summarize_and_plan` |
| `label_*` | int | a split was recorded, from 2026-09-12 | the first call's own five, same names and same order |
| `summary_kind` | enum | a second call ran, from 2026-09-12 | which call ran second |
| `summary_*` | int | a second call ran, from 2026-09-12 | the second call's own five |
| `truncation_cap_tokens` | int | the body was cut, from 2026-09-14 | which cap did the cutting |

Seventy more columns landed on 2026-09-15. Every one is nullable, every one is
empty on a row an earlier run wrote, and each one's own description is on the
field in
[`backend/idhazh/contracts/item_health.py`](../../../backend/idhazh/contracts/item_health.py)
rather than repeated here - the table above is long enough that a second copy of
it would be the thing that goes stale. Which question each of them answers, and
what fills it, is [item-health-columns.md](item-health-columns.md).

**`stage_gap_ms` is the load-bearing one.** It is `item_total_ms` minus every
named stage, and it is the only column that can catch a regression in a stage
nobody named - every other timing column can only report on work somebody
already thought to measure. It is signed on purpose: a negative value means two
named stages overlapped, or two clocks disagreed, and clamping it to zero would
hide exactly the thing it exists to report.

**A call slot fills whole or not at all, and the five flat cells are their sum.**
The contract refuses a row that records one call and leaves the totals at that
call's numbers, which is what lets every reader that pools these cells stay
pooled and stay correct. Read the cache per call rather than off the total: a
second call replays the first call's prompt and is answered for it, so
`cached_tokens` over the item is non-zero on every item that took two calls and
says nothing about either
([the split](../summarize/throughput.md#each-call-is-charged-on-its-own-and-the-item-is-their-sum)).
**The picture costs nothing extra here**: the summarize-and-plan call writes the summary and the plan
in one reply, so what a picture cost is already inside the cells above and there
is no second call to account for.

**The row is a census, not an error log.** Successes and failures share one file
because a rate needs its denominator beside its numerator.

**A row is one planned item on one run.** `(date, run_id, item_id)` is the
identity, and `ledger.append_item_health` filters on it before it writes. That is
what lets two stages write the file: the second one to see an item has nothing
new to say.

**That filter reads a frozen file, so it is only half the guarantee.**
`actions/checkout` pins a job to the commit its run was triggered at, so a second
attempt at the same work cannot see the rows the first attempt pushed afterwards
and appends them again; `merge=union` then keeps the lines from both sides rather
than collapsing them. The other half runs after that merge, on the merged file:
`ledger.drop_repeated_rows`, called by the work job's commit step through
`DROP_REPEATED_ROWS_COMMAND`, keeps the first row for each key and drops the rest.
Before-the-write and after-the-merge are two different moments and the file needs
both - measured 2026-08-31, `2026-08-29-3` held 44 repeated keys here because
only the first existed.

**A worker records only settled items.** It writes an article payload for every
item it reaches and a summary payload for every item that got as far as the
model, so an accepted article with no summary beside it means the shard stopped
mid-item. Assemble classifies that item later. A row filed at the moment of an
interruption would record it as a failure, and this file cannot correct a row.

**Assemble owns the denominator.** It is the one stage that sees every planned
item, so it is the only one that writes a `not_attempted` row for an item no
worker reached.

**Nothing under `state/` is served.** The console reads a narrow projection of
this file - see [Scaling](#scaling) - and a reader gets figures, never the file.

## Two word counters, and the one thing they say together

`source_words_before_cap` is how long the extracted body was. `source_words` is
how long it still was after `extract.truncation_cap_tokens` cut it. Both come
from the same `Article`, at the same moment, off the same string: `extract`
reads the page once, counts the whole body into `Article.source_word_count`,
truncates, and counts what is left into `Article.word_count`.

So the test for a cut is the comparison and nothing else:

```text
cut <=> source_words_before_cap > source_words
by = source_words_before_cap - source_words
```

The alternative was `source_words == int(truncation_cap_tokens / 1.3)`. That
number moves whenever the cap moves, so a window spanning a cap change mixes
two cut points and any value written down goes wrong silently. It also calls an
article cut when its body happens to end on the boundary. A comparison between
two cells on one row has neither failure.

The pre-cap **text** is not kept, here or anywhere. This is a count, and a count
of our own extraction - the same class of cell as `source_words`, which is why
the published projection carries it too
([../publishing/telemetry-series.md](../publishing/telemetry-series.md)).

The cell is empty on every row a run wrote before 2026-08-28, and empty again on
any row whose article payload predates `Article.source_word_count` (2026-08-26).
Empty means the run never measured it. Nothing recomputes it later, because the
body it would have to count is gone.

## The row on the shard, before the ledger has it

`backend/var/run/<date>/items/<item_id>.health.json`. The work stage writes it
the moment the recorder seals an item, through `telemetry.record.persist`, with
the same temp-file-then-rename every per-item payload uses. The payload is
`ItemHealthRow` and nothing else, so there is no second shape to version.

**It exists because the row used to die with the shard.** The recorder validates
all 119 cells an item at a time, and until 2026-09-15 the only place they went
was a log line - a CI artifact with its own expiry. The durable row was rebuilt
afterwards from the article and the summary payloads, which between them cannot
carry most of those cells, so a cell the shard measured correctly still reached
this ledger empty.

**It travels on the artifact the other payloads already travel on.** A shard
uploads `items-<shard>` rooted at the whole items directory and assemble
downloads `items-*` back into the same place, so no workflow step names this
file and none had to change for it to arrive.
`tests/workflows/test_worker_ledgers.py` holds both sides to the directory,
because narrowing either one to a list of suffixes would strand the next payload
on the runner that wrote it without failing anything.

**What it costs**: 3,103 to 3,119 bytes an item, mean 3,111 over the five items
of the committed fixture plan (Windows 11, Python 3.14.2, 2026-09-16). One shard
is `run.shard_size` items, five today, so a shard carries about 15.6 KB of it -
0.003 percent of the 500 MB artifact ceiling - and a run at the 80-item
`run.safety_ceiling_per_run` carries about 249 KB. None of it is committed and
none of it is published: `backend/var/` is run scratch, and this ledger under
`state/` is still the durable copy.

**The census reads it, and prefers it.** `telemetry.census_row` is the door both
writers go through. Where this file exists the committed row IS this row, cell
for cell; where it does not, `telemetry.classify_item` rebuilds what the article
and the summary payloads can say. Preferring the file took the fixture day from
40 filled columns to 71, and the three cells it does not cover are named in the
next paragraph. The file is also still the evidence a reader can open when a
committed row and a shard's log disagree.

**Three cells are laid over it rather than taken from it**: `span_integrity`,
`elements_found` and `element_class`. The work stage does not measure them - the
element count is taken after the summary is accepted, by the stage that is about
to publish - so the census supplies its own reading for those three and takes
everything else from the shard. The list is read off `ExtractionHealth._fields`
rather than written out, so a fourth cell joins it the day it is added.

**What preferring it costs.** A committed row grew by 206.8 bytes on the fixture
day (Windows 11, Python 3.14.2, 2026-09-16; five items, 3,495 to 4,529 bytes over
the five). Against a published day's `state/` - 480 item-health rows at the
median, 18.7 percent of the 28.2 MB tree measured on 2026-09-16 - that is
8.1 percent more `state/` a day, and the fixture cannot reach 18 of the columns
a real run fills, so the production figure is an estimate of 15 to 17 percent.
The estimate is what a per-cell width from `state/runtime-counters.csv` and the
published `rank_score` widths give; a measurement on the first real day replaces
it. Plan 32's decision 3 priced this at 3.2 percent before the columns were
counted, which was about three times low.

## Which worker wrote the row

A run splits into as many as eight `work` jobs, each on its own disposable
machine. `shard` is the number `stages.common.shard_of` gave the job that produced this
row. `state/runtime-counters.csv` carries `shard` and `shards` for the same run,
so `(run_id, shard)` joins the two files: the cells here say what the work cost,
and the row there says which host paid it.

The column exists because the hosts are not alike. Measured over the seven runs
in `state/runtime-counters.csv` on 2026-08-30, the fastest shard of a run read
the prompt between **1.10x and 4.19x** faster than the slowest shard of the same
run. The worst was run `2026-08-27-2`, where eight shards ranged from 9.75 to
40.89 prompt tokens a second on one day. Pooled over the run that difference
disappears, and until this column existed pooling was the only read available -
so a slow day and a slow machine looked the same.

Only a worker knows it. `stages.work` reads the number once a shard and notes it
on every item it seals, so the cell travels with the row in
`<item_id>.health.json` and reaches the ledger through whichever writer files it
first. `stages.record.stage_record` runs per shard and
`stages.assemble.stage_assemble` runs once for the whole day, and since
2026-09-16 that difference no longer shows in this column: both prefer the
sealed row, so assemble's rows name the machine that ran the item rather than
leaving the cell empty. An empty cell means no worker sealed a row for the item
- it was planned and never reached - and it is also what every row written
before 2026-08-30 holds. **It is never shard 0.**

`shard` is not in the published projection
([../publishing/telemetry-series.md](../publishing/telemetry-series.md)). Which
machine ran an item is an operator's question, and the page that asks it reads
`state/` at build time rather than fetching it in the browser.

## Which machine read it, and what that machine was

`job` is the workflow job whose machine took this row's readings - never which
job wrote the row. It reads `work` on every row a shard sealed, because that is
the job the model server runs in, and `assemble` never fills it: that stage runs
once for the whole day on a machine that read none of these items.

**With `shard` it is the whole of `ledger.HOST_FINGERPRINT_KEY`**, which is
`date`, `run_id`, `job`, `shard` - the key
`state/host-fingerprint/<YYYY>/<MM>/<DD>.csv` files one row a job under
([../../reference/host-metrics.md](../../reference/host-metrics.md)). So the
question "which processor summarized this item, and what could it do" is one
equality:

```sql
SELECT ih.item_id, hf.fingerprint, hf.cpu_model, hf.microcode, hf.flags
FROM item_health ih
JOIN host_fingerprint hf
  ON hf.date = ih.date AND hf.run_id = ih.run_id
 AND hf.job  = ih.job  AND hf.shard  = ih.shard
```

**Three of the four columns are not a key, and that is why `job` exists.**
`plan`, `work`, `assemble` and `runtime` each draw their own machine and each
write shard 0, so a lookup on `date`, `run_id` and `shard` alone finds every job
of the run. The item row could spell three of the four and stopped there.

**The rule is one-directional: a row that names a job names a shard too, and not
the converse.** A job with no shard is half a key and resolves to every shard
that job ran, so the contract refuses it. A shard with no job is what every row
written before 2026-09-17 holds, and `ledger.append_item_health` reads those
rows back through `from_csv_row` before it appends - so a two-directional rule
would refuse the whole archive on the first run after the column landed.

### What the machine had, against what a process held

Eight memory and processor cells on this row are about a PROCESS - the model
server's resident set, the worker's, the job's cgroup peak. **None of them can
say what was left.** llama.cpp maps the weights with no `-lm`, so their resident
pages are file-backed and evictable and count in every RSS figure, and a page
two processes share is counted twice. Adding the marks up and subtracting from
16 GB is a number this project has already withdrawn
([../../reference/measurements.md](../../reference/measurements.md)).

Six `os_` columns are the kernel's own account instead, read from
`/proc/meminfo` by the same watch that fills `cpu_busy_max`:

| Column | What it is |
| --- | --- |
| `os_mem_available_bytes` | What the kernel says a new allocation could have, at the end of the item. This is headroom |
| `os_mem_total_bytes` | What the machine has. Constant inside a job, recorded per item so a row means something alone |
| `os_mem_cached_bytes` | Page cache. Most of the weights sit here, so a fall is the kernel evicting what the next item re-reads |
| `os_swap_free_bytes` | Swap left. A fall here is the machine in trouble before the cgroup kill |
| `os_swap_total_bytes` | Swap the machine has. Without it a free figure of zero says "no swap here" and "swap consumed" equally |
| `os_mem_available_min_bytes` | The lowest headroom seen while the model worked on THIS item |

**The last one is the only cell taken over a window rather than at an instant,
and the window is the reason it is worth having.** The watch opens when the
model starts on an item and closes when it stops. Selecting samples on
`item_started_at .. item_ended_at` instead would be the queue window, which
measured nine times longer, with 19 items of 20 open at the same instant - so
almost every row would carry the whole job's low-water mark rather than its own
(Carmack, 2026-09-17, against `state/item-health/2026/09/16.csv`).

**An item whose machine never answered records six nulls, never six zeros.**
`/proc/meminfo` does not exist on the machines this project is written on, and a
zero in the headroom cell would read as a machine with no memory left.

## Stages and outcomes

An item can terminate at one of five stages:

`plan`, `fetch`, `extract`, `summarize`, `publish`

The outcome is either `ok` or `failed`. A failed row has one failure code that
belongs to its stage. A successful row usually has no code, but may carry an
extract signal: `too_short`, `not_prose` or `boilerplate`.

**`ItemStage` holds a sixth name and this column refuses it.** `visual` is the
step that plans and draws a picture, and it is a stage the pipeline can name
rather than a place an item can stop: an item whose picture failed still reaches
the digest, so it leaves a `publish` row. `contracts.item_health.TERMINAL_STAGES`
is the five this column accepts and a validator raises on anything else, so a
row carrying `visual` cannot be written rather than being merely unusual. The
same enum types `telemetry.event(src=...)`, which names the step that wrote a
log line, and `DayStageTiming.stage`, which names the step a clock was read at -
neither of those two means an ending. Before 2026-09-14 there was no name at
all, and a render failure was silent.

**A successful item leaves a `publish` row, so `summarize` rows are a failure
count and nothing else.** The stage on the row is where the item STOPPED, not
the last stage it passed through, so filtering on `stage == "summarize"` selects
only the calls that failed or degraded. Over `state/item-health/2026-09.csv` on
2026-09-09 that filter returned 42 rows across nine days; the pipeline had
summarized 4,117 articles. The honest filter for per-item timings, token counts
and lengths is `stage == "publish"`.

Column coverage is the cheap check before trusting any stage filter. On the same
shard, `input_tokens` is present on 4,117 rows and every one of them is
`publish`. A stage that carries none of the columns you are measuring is not the
stage that did the work.

## Failure codes

| Stage | Codes |
| --- | --- |
| `plan` | `not_attempted` |
| `fetch` | `robots_denied`, `robots_unreachable`, `blocked_address`, `http_client_error`, `http_rate_limited`, `http_server_error`, `network_error` |
| `extract` | `no_text`, `no_title`, `too_short`, `not_prose`, `boilerplate`, `paywalled`, `unsupported_form` |
| `summarize` | `model_unreachable`, `model_refused`, `model_timed_out`, `shard_out_of_time`, `context_exceeded`, `output_truncated`, `labels_truncated`, `bad_shape`, `length_out_of_range`, `copied_source`, `leaked_address` |
| any failed stage | `unknown` |

`detail` is `str | None`, at most 2,000 characters of printable ASCII on one
line, and belongs on any failed row. A row coded `unknown` must carry one and
an `ok` row may not. It is written by the classifier, never copied from an
article or summary payload: the write path sanitizes it, strips any spreadsheet
formula prefix, collapses whitespace, and truncates it. Two hundred characters
was the cap until 2026-09-15, which cut an exception message off before the
part that said what broke. A non-empty `detail` beside `unknown` means "mint a
better enum member".

`http_status` belongs only on `fetch` rows.

`fetch_ms`, `extract_ms`, and `summarize_ms` are nullable. Null means the stage
did not run, or the row predates timing capture. It is not zero. A zero would be
a measurement.

## What the model cost

`summarize_ms` is wall-clock for the whole request. `prefill_ms` and `decode_ms`
split it the way the runtime charges it: prefill is the model reading the
prompt, decode is it writing the reply, and decode runs at roughly half the
prefill rate because it produces one token at a time. A blended figure cannot
say which of the two made a slow day slow.

All five columns come straight from the runtime's own reply, so nothing here is
our arithmetic. A runtime that reports no timings leaves them null, and the item
still publishes.

A rate needs its token count beside its milliseconds, so both are on the row:

| Read | From |
| --- | --- |
| Prompt tokens the model actually read | `input_tokens - cached_tokens` |
| Prefill tokens per second | `(input_tokens - cached_tokens) / (prefill_ms / 1000)` |
| Decode tokens per second | `output_tokens / (decode_ms / 1000)` |
| Prompt cache hit rate | `cached_tokens / input_tokens` |

`cached_tokens` is what the runtime reused instead of reading. Leaving it in the
prefill count reports a rate the machine never ran at, which is why the console
subtracts it.

**A day is the sum of its rows, never the median of their rates.** A rate is a
ratio, and the workers each did a share of one day: averaging per-item rates
weighs a 60-word release note the same as a 2000-word feature.

The **spread** of the per-item rates is a different statistic and is kept too.
The console draws it as a candle per day, because the worker summarises short
articles before long ones and the two ends of a day drift apart on purpose. Why
that happens, and what a change in either rate is allowed to prove, is
[../summarize/throughput.md](../summarize/throughput.md).

## What counts against a source

Eighteen codes never count against a source:

`not_attempted`, `robots_denied`, `robots_unreachable`, `blocked_address`,
`http_rate_limited`, `too_short`, `not_prose`,
`model_unreachable`, `model_refused`, `model_timed_out`, `shard_out_of_time`,
`context_exceeded`, `output_truncated`,
`labels_truncated`, `bad_shape`, `length_out_of_range`, `copied_source`,
`leaked_address`

`boilerplate` left that list on 2026-09-17, and it is the only code that ever
has. It was neutral because it could not be anything else: nothing fed the
comparison, so the ratio divided by an empty set and answered 0.0 on every page
we ever fetched - zero `boilerplate` cells in 12,277 committed rows.
`state/chrome.csv` gives the comparison its other side
([../extraction/chrome.md](../extraction/chrome.md)), and once the signal can
fire it is a fact about the source: this host served a page that was mostly its
own furniture.

The remaining nine can count against the source:

`boilerplate`, `http_client_error`, `http_server_error`, `network_error`,
`no_text`, `no_title`, `paywalled`, `unsupported_form`, `unknown`

The contract carries this as data on the enum side, not as prose only, because a
later source-health reader uses it.

`model_unreachable` records nothing answering at our local model server's
address - the process is gone, the port is closed, the connection was refused.
It is infrastructure failure. It never counts against a source.

`model_timed_out` records the server taking the request and not answering inside
`request_timeout_minutes`. **It is a different finding from `model_unreachable`
and the difference is where an operator should look**: unreachable sends them to
the process, and this sends them to the output budget, because a call that times
out is almost always decoding more tokens than the clock admits. The two were
one code until 2026-09-15, because a socket timeout is a `TimeoutError` and
`TimeoutError` subclasses `OSError`, so the handler caught the parent - 30 items
across three days were filed as a dead server that was serving their neighbours
fine.

`shard_out_of_time` records the worker stopping on its own clock before this
item's model work began. The item was planned, fetched and extracted, and the
shard declined to start work it could not finish. Distinct from `not_attempted`,
which is the run's plan never reaching the item at all: one is a supply problem
and the other is a throughput problem.

`model_refused` records the server answering with an error it could not explain
as a context overflow. The server is up; the request is what it would not take -
a flag the entry declares, a grammar, a body. It was `model_unreachable` until
2026-09-15, which sent an operator to a process that was running: Gemma named a
speculation kind its draft head could not drive, and five items of five reported
a network fault against a healthy server. It never counts against a source
either.

`context_exceeded` records the served context window refusing a prompt. The
article was long, and the window, the truncation cap and the prompt overhead are
all ours - so it is our budget, not a publisher writing at length.

`copied_source` and `leaked_address` record a reply we refused after it parsed:
one that copied the article instead of summarizing it, and one that carried an
address into our own words. The article was fine both times and the model wrote
the words, so counting either against the feed would quarantine a wire service
for a defect we own.

## Adding a column is a two-part change

A new column on this row is not finished when the contract and the schema agree.
`ledger._append` calls `require_matching_header` before it writes, and that
refuses any header that is not the contract's column list exactly. The day file
the pipeline is currently appending to already exists with the old header, so
the first run after the contract changes would raise:

```text
2026-09-17.csv has 113 columns and the contract has 113.
Migrate the ledger before appending to it.
```

**The two counts are equal there and it still raised**, which is the clearest
thing this message says: the guard compares the whole tuple. That is the real
shape of the 2026-09-17 change - one column added, one retired - and a check on
the width alone would have called it clean.

That is a failed scheduled run, not a failed lint. **This is the one ledger that
migrates itself, and the reason is that it is the one that has retired a
heading.** `ledger.append_item_health` reads line 1 before it writes; where the
header is not the contract's it calls `ledger.migrate_header`, which re-files
every row through `ItemHealthRow.from_csv_row` and writes the file back under
the current column list. The migration ships in the same commit as the contract
(`CLAUDE.md` section 11) because that function IS the migration, not because a
utility has to be run by hand.

Three things follow, and the first is the one most often got wrong:

1. **A column may be filed beside the one it relates to.** `migrate_header` maps
 by name, never by position, so an appended column buys nothing here. Order
 still matters for `FeedHealthRow` and the other eight ledgers, which reach
 `_append` with no migration of their own - that is where
 `backend/tests/contracts/test_repo_structure.py::test_the_feed_health_ledger_columns_are_defined_once`
 spells the appending rule and why.
2. **An added column costs no code at all.** `from_csv_row` reads each field
 with `row.get(name, "")`, so a file written before the widening reads the new
 cell as absent. Empty is correct: those runs measured nothing.
3. **A removed column must be named in `ledger.ITEM_HEALTH_CARRIED`, in the same
 commit.** `migrate_header` refuses any heading that is neither a current
 column nor one the reader carries, rather than dropping cells silently - so a
 retired column with no entry there raises on the first append to every
 committed day file, and takes every ledger staged beside it down with it.
 `runner_name` is in that set for exactly this reason.

**The committed day files are not rewritten by the pull request.** Each one is
re-filed by the first run that appends to it. `state/**/*.csv` is `merge=union`
in `.gitattributes`, so a branch that rewrote a day file whole would have every
line of it stacked against the lines the pipeline wrote while the branch was
open - a clean merge and a doubled file.

**A check on the migration reads rows, never day files.** A day file the
pipeline opens after the migration holds no pre-migration row at all, and it
opens a new one every day. Two tests asked every committed file for a row older
than the column and went red on 2026-09-01, when a fresh file arrived with 63
rows and none of them older than either column. The population a migration check
is about is the rows, and the way to get one that cannot age out is to build the
older generation rather than to look for it
(`backend/tests/test_ledger.py::A_RETIRED_GENERATION`).

The guard in `_append` is deliberate and stays. Widening it to tolerate a prefix
would let a column land silently in the wrong position on a file nobody re-read.

## Caveats

Everything here is a property of the ledger, not a bug in it. Read them before
quoting a number off this file.

**A row is one item-run, not one item.** The day runs five times and every run
writes a row for every item it planned. Measured on the committed
`state/item-health/2026-08.csv` at 1200 rows (2026-08-25): 1067 distinct
`url_key`, so 1.12 rows per address. `COUNT(*)` over-counts anything a person
would call "articles". Group by `url_key`, and pick a run with `run_id` when the
question is about one attempt.

**A null is not a zero.** Empty means the stage did not run, or the row predates
the column. Measured on the same file: `summarize_ms` is present on 879 of 1200
rows (73%) and `prefill_ms` on 145 (12%), because the token columns landed on
2026-08-24 and every earlier row is legitimately blank. A mean taken over the
whole column with blanks read as zero is wrong by the share of blanks.

**A failed row is not a free row.** A reply the summarize stage refused was
still read and still written, so since 2026-09-13 a failed summarize row carries
the five cost cells and the call slots exactly as an ok row does. Before that
date it carried none of them: 93 of 93 failed summarize rows in the committed
ledger are blank, and `reconcile_prefill` skips a blank rather than pooling it,
so the model server counted those requests and this ledger counted none of them
([../summarize/throughput.md](../summarize/throughput.md#a-reply-the-stage-refused-used-to-be-missing-from-one-side-of-this-check)
has the size). The cells stay blank only where no call returned, which is the
one failure that really was free.

**Timings come from the runtime, not from us.** `prefill_ms`, `decode_ms` and
the three token counts are copied out of the model server's own reply. A runtime
that reports nothing leaves them null and the item still publishes. Nothing on
this row is our arithmetic, which is the point - see
[../summarize/throughput.md](../summarize/throughput.md).

**A copied field is one instrument, and there is now a second.** Each `work`
shard also commits what its server counted for the whole shard, as one row of
`state/runtime-counters.csv`. `backend/utilities/reconcile_prefill.py` pools both
sides of a run and prints the gap, which is how a rate quoted off this file stops
being an assertion. Measured on run `2026-08-26-5`: 11.1755 tok/s from this
ledger against 11.1796 from the server, 0.037 percent apart
([../../reference/measurements.md](../../reference/measurements.md)).

**Visual planning and rendering are not here.** An item that got a chart and an item that got
nothing write the same row. A render failure degrades an item and never fails
it, so the two are indistinguishable in this ledger by design. What the planner
spent lives in the run manifest (`items_routed`, `items_prefiltered`,
`route_ms`) and in the digest payload's per-item `visual`.

**A row can never be corrected.** The file is append-only, so a row written with
a wrong code stays. A reclassification is a new row under a later `run_id`, and
a reader that wants "the latest verdict per item" has to say so. Nothing in the
pipeline does that today.

**`item_id` is stable, and since 2026-09-12 it carries no caveat.** `rank.item_id`
derives it from the address - `<vertical>-<sixteen Crockford base32 symbols>` off
the `url_key` - so a later run of the same day recognises the work an earlier one
did. It was a rank position once, which renumbered every story on run 2 and
published anything that moved a place twice. It was ten decimal digits until
2026-09-12, and 33 bits collided often enough that a collision had to be
resolved: the loser stepped forward past whatever else the run had already
planned, so a colliding id depended on the day's pool rather than on the address
alone. Eighty bits do not collide, so nothing steps. **Rows written before
2026-09-12 keep the decimal id and were not rewritten**, so an id does not join
across that date. `url_key` is one shape for every row ever written. Join on
`url_key`.

**The failed share is not the source failure rate.** 324 of the 1200 committed
rows are `failed`, but twelve of the nineteen codes never count against a
source - `model_unreachable` is our own server being down, `robots_denied` is a
publisher's stated wish. Filter on `counts_against_source` before calling
anything a source's fault.

**Shape signals ride on `ok` rows.** `too_short`, `not_prose` and `boilerplate`
appear with `outcome = ok` because the item published and the signal still
matters. `WHERE code IS NOT NULL` is not the same query as `WHERE outcome =
'failed'`.

**A merge conflict on the shard is normal.** The pipeline appends to it several
times an hour, so any branch open for more than a run will conflict. Resolve by
taking the upstream file whole and re-applying your change - never by keeping
your copy, which drops the rows the pipeline wrote while the branch was open.

## Scaling

Measured 2026-09-17 on the committed repository, and the row moved again the
same day: six `os_` columns landed, so it carries **119**. Every byte figure
below was taken against the 113-column row, which makes each one a floor rather
than a reading of today's width - what the six add is on its own line under the
table. The previous reading was taken on 2026-09-15 against a row that has since
moved twice, so it was a stale reading rather than history and has been replaced
(Guardrail #10).

| Quantity | Value | How |
| --- | --- | --- |
| Day files in `state/item-health/` | 24, 12,837 rows | `rglob` count |
| Ledger on disk | 5,639,488 bytes | `stat` |
| Mean row | **439.3 bytes** | size / rows |
| Widest day, `2026/08/25.csv` | 1,000 rows, 396,015 bytes | `stat` |
| Rows on a full day | **800** | 5 runs x the 160-item `safety_ceiling_per_run` |
| A full day at the current width | **~351 KB** | 800 x 439.3 |
| Published projection `frontend/public/telemetry/2026-09.csv` | 1,373,976 bytes, 49 of the 119 columns | `stat` |
| Mean published row | 180.5 bytes raw, **41.3 bytes gzipped** (4.4x) | gzip at maximum level |

What the 2026-09-17 column change costs the archive, one time, on the first
append to each day file:

| Move | Bytes | How |
| --- | --- | --- |
| `job` added | **+12,933** | one comma on each of 12,837 rows, plus `,job` on 24 headers |
| `runner_name` dropped | **-23,194** | 12,837 commas, 399 filled values totalling 10,069 characters, and `,runner_name` off 24 headers |
| Net | **-10,261 bytes** | the row gets narrower, not wider |

The six `os_` columns are the next one-time cost, measured the same day against
a ledger one run wider - 25 day files and 13,157 rows: **+82,267 bytes**, six
commas on each row plus the six names on each header. Every cell is empty until
a run writes one, so this is the cost of the columns existing rather than the
cost of what they hold.

Projected forward at the current cadence and ceiling:

| Horizon | Ledger | Served projection (gzipped) |
| --- | --- | --- |
| a day | 351 KB | 33 KB |
| a month | **10.5 MB** | **991 KB** |
| a year | 128 MB | 12 MB |

Three limits, in the order they will actually bite:

1. **The reader's download, first.** The console fetches a whole month shard.
 991 KB gzipped at the end of a busy month is far more than the rest of the
 page. The lever is the projection, not the ledger: the served file carries 49
 of the row's 119 columns and could carry fewer, or become a pre-aggregated
 day-grain file with the per-item rows kept for the operator only. Nothing
 here is measured against a slow connection yet, so that is the next
 measurement rather than the next change.
2. **Git history, second.** A day file is appended to several times a day and
 each append rewrites it as a new blob, so the repository grows with
 `appends x file size` rather than with rows. Day sharding is what keeps that
 bounded: an append rewrites one day and not the month. The lever if it bites
 is the projection width again, or a shorter retention on the ledger itself.
3. **The 1 GB published site, last and least.** `state/` is never served, so it
 does not count against that cap at all. Only the projection under
 `frontend/public/telemetry/` does, and at 10 MB gzipped a year it is not the
 thing that fills a gigabyte - the day payloads and their SVG assets are.

What is deliberately **not** planned: pruning. The ledger is the only durable
record of what a bad day did, and a retention pass over it would delete exactly
the evidence it exists to keep. Windows are applied on read.

## A cell is fitted to its column, by the column

Most of what lands in this row is not ours. `cpu_model` comes from a kernel
file, `summary_finish_reason` and
`label_finish_reason` from the runtime, `model_quantisation` from committed
config, and `detail` from whatever went wrong - which, whenever a Pydantic
`ValidationError` is what went wrong, quotes the value it refused. A page title
with a curly quote in it therefore arrives inside the message that says the
title was refused.

Every one of those columns declares what a value may be made of. `detail` and
`cpu_model` take printable ASCII on one line; the token
columns take a lowercase name. So a character outside the class made the row
raise - and the row that raised was the one reporting the failure. The evidence
and the item were lost together, over a dash.

The column closes that itself. `base.fits_its_column` puts `base.fit_cell`
inside validation, so the fold runs for whoever built the row - the stage, a
re-file reading an old heading, a test harness, a writer nobody has written yet.
It reads the class and the length off the column being written, folds Western
punctuation to its ASCII spelling, replaces each run of anything left with a
single `?`, and returns a stated floor rather than an empty string where nothing
survives. There is no door to miss because there is no door.

**A helper a producer has to remember is the shape this replaced, and it had
already been forgotten.** The fold lived at `ItemRecorder.note`, which builds a
log line; the census row is constructed in `telemetry.classify_item`, which
never called it. So the hardening covered the log and left the CSV as it was.

Two things the fold will not do. It never folds a column whose rule names an
identity: `item_id`, `url_key`, `canonical_url`, `vertical` and `source_id` have
no foreign value to rescue, and a fold that satisfied `^[0-9a-f]{64}$` would
have invented a digest. And it never returns nothing: `detail` has
`min_length=1`, so an empty cell raises, and a detail that cannot be printed
becomes `unspecified failure` while a reading that could not be printed becomes
`unprintable`. An empty `cpu_model` keeps its own meaning - the probe was not
taken.

What a reader loses: the exact characters. A Cyrillic headline quoted inside a
refusal message reads as `?` in the ledger. The trade is one `?` against a
missing row, and `backend/tests/contracts/test_cell_shapes.py` holds it.

**The fold does not reach a column whose vocabulary is ours.** `time_source`
says which clock a story's time came off, and the three answers - `feed`,
`first_seen`, `unknown` - are minted in this repository rather than read off
somebody's page. So the column is the `TimeSource` enum and not a token shaped
like one: a producer selects a member, and a fourth spelling is refused at the
boundary instead of being folded into a legal-looking cell nobody declared.
Folding here would keep the row and lose the answer, which is the opposite trade
to `detail`. A reader loses nothing by it, because there was never a foreign
value in this column to rescue. `backend/tests/contracts/test_closed_vocabularies.py`
holds that.

## Design rationale

A failure-only file cannot produce a rate. The ledger writes successes and
failures in one file so a chart can divide failures by all planned items.
Authority: Fowler.

Shape is evidence, not a verdict. `too_short`, `not_prose` and `boilerplate`
can appear on an `ok` row because the item published and the signal still matters
to the editor. They never count against a source by default. Only a paywall, an
unsupported form, or genuine missing text stops extract. Authority: Owner
override O3.

Each of the three has a switch that closes it, all three false
([../../concepts/config.md](../../concepts/config.md)). O3 is what the DEFAULT
says, not what the code can express, and the difference matters: a curator who
turns one on is taking a decision O3 left them, not overriding it.
`reject_too_short` additionally never fires on a feed registered as `abstract`,
because short is the property that feed was registered for.

The row stores both `url_key` and `item_id`. `item_id` is derived from the
address, so it survives a re-plan - but it was ten decimal digits until
2026-09-12 and is sixteen base32 symbols after it, and rows either side of that
date were not rewritten. `url_key` is one shape for every row ever written.
Authority: Fowler.

The row stores `canonical_url`. About 80 bytes buys back the URL that otherwise
expires with a run artifact. Authority: Fowler.

A worker commits the rows for its own items, and Assemble writes the rest.
Assemble was the only writer until 2026-08-27, to keep a diagnostic append out of
a rebase race with the publish commit. What that reasoning missed is where the
rows live in between: a shard's verdicts leave the runner only inside its
`items-<shard>` artifact, which expires and is never committed. A run stopped
between the workers and the publish had measured every item and recorded none of
it - and a bad day is exactly the day worth measuring. The race the old rule
avoided is answered instead by the two things that already existed for it:
`merge=union` on `state/**/*.csv`, and the
rebase loop in `.github/scripts/commit-and-push.sh` that the plan job has always
used for the same reason. The double-write the old rule also avoided is answered
by the row identity above. Authority: Fowler, over Carmack's original ruling.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Two files, one for failures and one for word counts | Two schemas and two parses for one row's facts. |
| Store `compression` | It is derived from `summary_words / source_words`. The chart can divide. |
| Reuse `state/scores.csv` | It holds items the scorer measured, not all planned items. |
| Put stage timings on `EvalRow` | `EvalRow` is written only for the scored subset. Slow or failed items would disappear from the operator's timing view. |
| Persist free-text failure detail as the signal | A chart cannot group free text. |
| A `skipped` code | A skip is not one cause. The row records the typed cause instead. |
| Add `attempt`, `recorded_at`, `title`, or `source_url` | No query needs them. `date` and `run_id` already address the row. |
| Parse the throughput out of the runtime log | The log is a CI artifact kept for two days, and a rate nobody can recompute later is not a measurement. The reply already carries the numbers. |
| Store the rates instead of the counts | A stored rate cannot be re-aggregated across a day, a week, or the four workers. Store what was measured; divide on read. |
| Prune the ledger on a retention schedule | The rows worth keeping longest are the ones from the worst days, and those are the first a size-driven prune would take. Windows are a read-side parameter instead. |
| Serve `state/item-health/` directly to the console | The row carries `canonical_url`, `url_key` and `detail`, none of which belongs in a browser. The narrow projection under `frontend/public/telemetry/` exists so the forbidden columns are absent by construction rather than filtered on read. |
| One row per item, updated as the item progresses | An update is a read-modify-write over the whole history, and two runs racing on that lose rows. Append is what makes the file safe for five runs a day. |
| Keep the worker's rows in the `items-*` artifact and raise its retention | The artifact is never committed and expires, so a longer retention delays the loss rather than preventing it. The committed row is what a later run and the console read. |
| Let a worker record every item it was planned, not only the settled ones | An item the shard was interrupted on would be filed as a failure, and an append-only ledger cannot take that back. |
| Add a visual-planning or render outcome column | Neither is a terminal item stage: a render failure degrades an item, never fails it. The run manifest and the day payload already carry what the planner did. |
| Record a render failure as a `visual` row here | It would say the item stopped where it did not - the item publishes, shorter - and it would take one off the `publish` count that `day_metrics` and the console read. The failure is loud from 2026-09-14 as the `item.visual.failed` event, whose `src` is the stage that broke rather than the stage the item ended at. |

## See also

- [item-health-columns.md](item-health-columns.md) - every column, the eight
  questions they group into, which module fills each one, and whether anything
  carries it into this row.
- [health.md](health.md) - the feed-grain ledger.
- [../summarize/throughput.md](../summarize/throughput.md) - what the two model rates mean, and why the spread inside a run is wide.
- [../publishing/visuals.md](../publishing/visuals.md) - what the picture costs, which this ledger deliberately does not carry.
- [trust-boundary.md](trust-boundary.md) - how fetched bytes become sanitized text.
- [../contracts/schemas.md](../contracts/schemas.md) - the contract and schema rules.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - logs as evidence, ledgers as records.
- [../../reference/measurements.md](../../reference/measurements.md) - the sizes and rates quoted above.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #3, Guardrail #11, and section 11.
