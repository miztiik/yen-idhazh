# Item Health

**Last Updated**: 2026-08-31

What every planned item did on every run, where that record lives, and which
failures count against a source. This is item-grain evidence. Feed health is
source-grain evidence.

## Every item, every run, one row

`state/item-health/<YYYY-MM>.csv`. One row is written for each planned item on
each run, whether the item succeeds or fails. Two stages write it: a worker
commits the rows for its own items as each one settles, and Assemble writes the
whole day's census afterwards.

The row carries:

`version, date, run_id, item_id, url_key, canonical_url, vertical, source_id, stage, outcome, code, http_status, source_chars, source_words, summary_words, detail, fetch_ms, extract_ms, summarize_ms, prefill_ms, decode_ms, input_tokens, output_tokens, cached_tokens, source_words_before_cap, shard`

The file is append-only and never pruned. The 30-day window is a read-side
parameter. Monthly shards follow `state/seen/` and `state/feed-health/`.

## The structure

Three files carry one item-health row, and each owns one thing:

| Where | What it owns |
| --- | --- |
| `backend/idhazh/contracts/item_health.py` | the shape: field order, types, enums, the validator, and `csv_columns()` |
| `schemas/item-health-row.schema.json` | the generated schema. Never hand-edited (Rule #3) |
| `backend/idhazh/ledger.py` | the append, the header guard, and the monthly shard path |

**One definition of the column list.** `ItemHealthRow.csv_columns()` returns
`tuple(model_fields)`, so the CSV header IS the contract's field order. A writer
and a reader cannot disagree, and there is no second list to forget.

**The file layout.** One directory, one file per calendar month of the `date`
column, named `YYYY-MM.csv`. A row is placed by the digest date it describes,
not by the clock when it was written, so a run that publishes just after
midnight UTC still files under the day it published. Header on line 1, `\n`
endings, `utf-8`, no quoting beyond what `csv` needs.

**Every cell is a string.** `csv_row()` writes `""` for an absent optional and
`from_csv_row()` reads `""` back as `None`. There is no sentinel number and no
`NULL` literal, because both of those get averaged by accident one day.

The 26 columns, in file order:

| Column | Type | Present when | What it answers |
| --- | --- | --- | --- |
| `version` | date-stamp | always | which contract wrote this row (section 11) |
| `date` | `YYYY-MM-DD` | always | the digest day, and the shard this row files under |
| `run_id` | `<date>-<execution>` | always | which execution wrote it. The trailing field is the CI run id, and a small ordinal on rows written before 2026-08-31 |
| `item_id` | slug | always | `<vertical>-<ten digits>`, derived from the address. Stable across a day's runs, but see the caveat below |
| `url_key` | sha256 | always | the stable article key. Join on this, not `item_id` |
| `canonical_url` | URL | always | the address, after a run artifact has expired |
| `vertical` | slug | always | which topic queue it was planned into |
| `source_id` | slug | always | which feed contributed it |
| `stage` | enum | always | where it stopped: `plan`, `fetch`, `extract`, `summarize`, `publish` |
| `outcome` | enum | always | `ok` or `failed` |
| `code` | enum | on failure, or as an `ok` extract signal | the typed cause |
| `http_status` | 100-599 | `fetch` rows only | what the server said |
| `source_chars` | int | once extract ran | article size before summarizing |
| `source_words` | int | once extract ran | the denominator of compression |
| `summary_words` | int | once summarize succeeded | the numerator of compression |
| `detail` | <= 200 chars | `code = unknown` only | our own one-line reason. Never source text |
| `fetch_ms` | int | once fetch ran | wall-clock for the HTTP read |
| `extract_ms` | int | once extract ran | wall-clock for text extraction |
| `summarize_ms` | int | once the model replied | wall-clock for the whole model request |
| `prefill_ms` | int | when the runtime reports it | the model reading the prompt |
| `decode_ms` | int | when the runtime reports it | the model writing the reply |
| `input_tokens` | int | when the runtime reports it | prompt tokens, cached ones included |
| `output_tokens` | int | when the runtime reports it | tokens written |
| `cached_tokens` | int | when the runtime reports it | prompt tokens reused instead of read |
| `source_words_before_cap` | int | once extract ran, from 2026-08-28 | how long the body was before the cap cut it |
| `shard` | int | a worker wrote the row, from 2026-08-30 | which of the run's workers produced it |

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
cut  <=>  source_words_before_cap > source_words
by   =    source_words_before_cap - source_words
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

## Which worker wrote the row

A run splits into as many as eight `work` jobs, each on its own disposable
machine. `shard` is the number `cli.shard_of` gave the job that produced this
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

Only a worker writes it. `cli.stage_record` stamps its own number on every row
it files, which is the one moment the number is known. `cli.stage_assemble` runs
once for the whole day, so the census rows it adds - the items no worker reached
- leave the cell empty rather than naming a machine that may never have started.
An empty cell means no worker claimed the row, and it is also what every row
written before 2026-08-30 holds. **It is never shard 0.**

`shard` is not in the published projection
([../publishing/telemetry-series.md](../publishing/telemetry-series.md)). Which
machine ran an item is an operator's question, and the page that asks it reads
`state/` at build time rather than fetching it in the browser.

## Stages and outcomes

An item can terminate at one of five stages:

`plan`, `fetch`, `extract`, `summarize`, `publish`

The outcome is either `ok` or `failed`. A failed row has one failure code that
belongs to its stage. A successful row usually has no code, but may carry an
extract signal: `too_short`, `not_prose` or `boilerplate`.

`route` and `render` are not terminal item-health stages. A render failure
degrades an item and never fails it.

## Failure codes

| Stage | Codes |
| --- | --- |
| `plan` | `not_attempted` |
| `fetch` | `robots_denied`, `robots_unreachable`, `blocked_address`, `http_client_error`, `http_rate_limited`, `http_server_error`, `network_error` |
| `extract` | `no_text`, `too_short`, `not_prose`, `boilerplate`, `paywalled`, `unsupported_form` |
| `summarize` | `model_unreachable`, `context_exceeded`, `output_truncated`, `bad_shape`, `length_out_of_range`, `copied_source`, `leaked_address` |
| any failed stage | `unknown` |

`detail` is `str | None`, max 200 characters, and is populated only when
`code = unknown`. It is written by the classifier, never copied from an article
or summary payload. The write path sanitizes it, strips any spreadsheet formula
prefix, collapses whitespace, and truncates it. A non-empty `detail` means "mint
a better enum member".

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

Fifteen codes never count against a source:

`not_attempted`, `robots_denied`, `robots_unreachable`, `blocked_address`,
`http_rate_limited`, `too_short`, `not_prose`, `boilerplate`,
`model_unreachable`, `context_exceeded`, `output_truncated`, `bad_shape`,
`length_out_of_range`, `copied_source`, `leaked_address`

The remaining seven can count against the source:

`http_client_error`, `http_server_error`, `network_error`, `no_text`,
`paywalled`, `unsupported_form`, `unknown`

The contract carries this as data on the enum side, not as prose only, because a
later source-health reader uses it.

`model_unreachable` records our local model server being down. It is
infrastructure failure. It never counts against a source.

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
refuses any header that is not the contract's column list exactly. The month
shard the pipeline is currently appending to already exists with the old header,
so the first run after the contract widens raises:

```text
2026-08.csv has 19 columns and the contract has 24.
Migrate the ledger before appending to it.
```

That is a failed scheduled run, not a failed lint. The migration ships in the
same commit (`CLAUDE.md` section 11):

1. Append the new columns at the **end** of the model, never in the middle. The
   guard compares the whole list, and a reader maps by name, so the only reason
   order matters is that an appended column leaves the old header a prefix of the
   new one - which is what makes step 2 mechanical and reviewable.
2. Rewrite each existing shard under `state/` with the widened header and an
   empty cell for every new column on every old row. Empty is correct: those
   runs measured nothing, and `from_csv_row` reads an empty cell as `None`.
3. Read every migrated row back through `from_csv_row` before committing. A
   header that widened without its rows widening is worse than a raised error.

**A check on the migration reads rows, never shards.** Step 2 rewrites the
shards that exist on the day it runs, so a shard the pipeline opens afterwards
holds no migrated row at all - and it opens one on the first of every month. Two
tests asked every committed shard for a row older than the column and went red
on 2026-09-01, when `state/item-health/2026-09.csv` arrived with 63 rows and
none of them older than either column. The population a migration check is about
is the ledger, and so is the guard that stops the check passing on an empty
list.

Expect a merge conflict on the shard, because the pipeline appends to it several
times an hour. Resolve it by taking the upstream file whole and re-running the
migration on it - never by keeping your copy, which would drop the rows the
pipeline wrote while the branch was open.

The guard is deliberate and stays. Widening it to tolerate a prefix would let a
column land silently in the wrong position on a shard nobody re-read.

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

**Route and render are not here.** An item that got a chart and an item that got
nothing write the same row. A render failure degrades an item and never fails
it, so the two are indistinguishable in this ledger by design. What the router
spent lives in the run manifest (`items_routed`, `items_prefiltered`,
`route_ms`) and in the digest payload's per-item `visual`.

**A row can never be corrected.** The file is append-only, so a row written with
a wrong code stays. A reclassification is a new row under a later `run_id`, and
a reader that wants "the latest verdict per item" has to say so. Nothing in the
pipeline does that today.

**`item_id` is stable, but not guaranteed stable.** `rank.item_id` derives it
from the address - `<vertical>-<ten digits>` off the `url_key` - so a later run
of the same day recognises the work an earlier one did. It was a rank position
once, which renumbered every story on run 2 and published anything that moved a
place twice. The residual risk is `assign_ids`: two addresses landing on the same
ten digits are resolved by stepping the second one forward, so a colliding id
depends on the day's pool rather than on the address alone. `url_key` has no such
case. Join on `url_key`.

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

Measured 2026-08-25 on the committed repository.

| Quantity | Value | How |
| --- | --- | --- |
| Rows in `state/item-health/2026-08.csv` | 1200 | `Import-Csv` count |
| File size | 354,465 bytes | `stat` |
| Mean row | **295 bytes** | size / rows |
| Rows on a full day | **800** | 2026-08-26: 5 runs x the 160-item `safety_ceiling_per_run` |
| Published projection `frontend/public/telemetry/2026-08.csv` | 103,004 bytes, 10 of the 24 columns | `stat` |
| Mean published row | 85.8 bytes raw, **13.8 bytes gzipped** (6.2x) | gzip at maximum level |
| Blob versions of the shard in git so far | 14, 1.44 MB uncompressed | `git rev-list --objects` then `git cat-file -s` |
| Whole repository pack | 26.09 MiB | `git count-objects -vH` |

Projected forward at the current cadence and ceiling:

| Horizon | Ledger shard | Served projection (gzipped) |
| --- | --- | --- |
| a day | 236 KB | 11 KB |
| a month (one shard) | **7.1 MB** | **330 KB** |
| a year (12 shards) | 85 MB | 4.0 MB |

Three limits, in the order they will actually bite:

1. **The reader's download, first.** The console fetches a whole month shard.
   330 KB gzipped at the end of a busy month is already more than the rest of
   the page. The lever is the projection, not the ledger: the served file
   carries 10 columns today and could carry fewer, or become a pre-aggregated
   day-grain file with the per-item rows kept for the operator only. Nothing
   here is measured against a slow connection yet, so that is the next
   measurement rather than the next change.
2. **Git history, second.** Every run rewrites the whole shard as a new blob, so
   the repository grows with `commits x shard size`, not with rows: five commits
   a day against a shard averaging half its final size is roughly 530 MB of
   uncompressed blob a month. Delta compression on an append-only file is
   cheap - 14 versions and 1.44 MB sit inside a 26 MiB pack - but "cheap" is not
   a measured number here and must not be quoted as one. The lever if it bites
   is a shorter shard period (weekly, `YYYY-Www.csv`), which the reader already
   handles because it globs the directory.
3. **The 1 GB published site, last and least.** `state/` is never served, so it
   does not count against that cap at all. Only the projection under
   `frontend/public/telemetry/` does, and at 4.0 MB gzipped a year it is not the
   thing that fills a gigabyte - the day payloads and their SVG assets are.

What is deliberately **not** planned: pruning. The ledger is the only durable
record of what a bad day did, and a retention pass over it would delete exactly
the evidence it exists to keep. Windows are applied on read.

## Design rationale

A failure-only file cannot produce a rate. The ledger writes successes and
failures in one file so a chart can divide failures by all planned items.
Authority: Fowler.

Shape is evidence, not a verdict. `too_short`, `not_prose` and `boilerplate`
can appear on an `ok` row because the item published and the signal still matters
to the editor. They never count against a source by default. Only a paywall, an
unsupported form, or genuine missing text stops extract. Authority: Owner
override O3.

The row stores both `url_key` and `item_id`. `item_id` is derived from the
address, so it survives a re-plan, but `assign_ids` steps a colliding id forward
and that depends on the day's pool. `url_key` is the key with no such case.
Authority: Fowler.

The row stores `canonical_url`. About 80 bytes buys back the URL that otherwise
expires with a run artifact. Authority: Fowler.

A worker commits the rows for its own items, and Assemble writes the rest.
Assemble was the only writer until 2026-08-27, to keep a diagnostic append out of
a rebase race with the publish commit. What that reasoning missed is where the
rows live in between: a shard's verdicts leave the runner only inside its
`items-<shard>` artifact, which is kept for one day and is not uploaded at all
when a job is cancelled. A run stopped between the workers and the publish had
measured every item and recorded none of it - and a bad day is exactly the day
worth measuring. The race the old rule avoided is answered instead by the two
things that already existed for it: `merge=union` on `state/**/*.csv`, and the
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
| Keep the worker's rows in the `items-*` artifact and raise its retention | The artifact is not uploaded at all when a job is cancelled, so a longer retention protects nothing in the case that loses the rows. |
| Let a worker record every item it was planned, not only the settled ones | An item the shard was interrupted on would be filed as a failure, and an append-only ledger cannot take that back. |
| Add a route or render outcome column | Route is not a terminal item stage: a render failure degrades an item, never fails it. The run manifest and the day payload already carry what the router did. |

## See also

- [health.md](health.md) - the feed-grain ledger.
- [../summarize/throughput.md](../summarize/throughput.md) - what the two model rates mean, and why the spread inside a run is wide.
- [../publishing/visuals.md](../publishing/visuals.md) - what the router spends, which this ledger deliberately does not carry.
- [trust-boundary.md](trust-boundary.md) - how fetched bytes become sanitized text.
- [../contracts/schemas.md](../contracts/schemas.md) - the contract and schema rules.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - logs as evidence, ledgers as records.
- [../../reference/measurements.md](../../reference/measurements.md) - the sizes and rates quoted above.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3, Rule #11, and section 11.
