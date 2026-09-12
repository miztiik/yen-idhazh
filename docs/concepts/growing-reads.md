# Growing Reads

**Last Updated**: 2026-09-12

One question, asked of every read:

> **Does this read cost more when a run appended more?**

If it does, the read says what it covers. If the honest cover is everything we
hold, the declaration is `-1` and a sentence beside it saying why. `-1` is not a
default anybody inherits. It is a person saying out loud that they chose not to
bound this one.

This page is not a second rule. [`CLAUDE.md`](../../CLAUDE.md) Guardrail #12 already
refuses a cost that rises when nobody wrote any code, and it names review as the
only control - which is a person remembering to ask. A cover written in
`config/` or on the line above the code is the same agreement, moved to where a
diff can see it, a schema can bound it and a test can name it. **That is all
this page adds: the escape hatch now has an address.**

[partitions.md](partitions.md) is the companion. That page says what
a layout obliges a **writer** to do. This one says what a growing collection
obliges a **reader** to declare. Why a collection partitions at all is
[the shard rule](../architecture/contracts/schemas.md#a-ledger-partitions-only-when-its-read-carries-a-window),
and the two compose: a cover is what makes a partition worth having, because a
read with no cover opens every shard anyway.

## Deciding it for a collection this page does not list

The inventory below is dated examples. The rule is these three questions, and
they work on a collection nobody has invented yet.

**1. Does a run append to it?** Not "is it big", and not "is it in `state/`".
Source a person writes grows at review speed and is not this. A collection a
scheduled job adds to is - published days, ledger rows, shards, pictures,
vectors, receipts, corpus rows, and the one nobody has created yet.

**2. Does the read's cost follow what was appended?** Open the read and ask what
it would do tomorrow if today's run wrote and nobody touched the code. If the
answer is "one more file, one more row, one more directory", the answer to the
question at the top is yes.

**3. Then name the smallest honest cover, and write it where the code is.** Not
where the doc is - a doc is not consulted at the call site. Three shapes are
available and they are set out below. **Reach for the clock last**, because a
clock is the shape most often wrong: it is only right when the question itself
has a time bound.

If no cover is honest, that is a legitimate answer and Guardrail #12 permits it. Say
what the read opens, how the cost grows, and why a bounded input cannot answer
the question - and have a person agree. What is forbidden is a growing cost
nobody chose.

## The three answers

Every read here gives one of them.

### 1. A span of days

The cover is a number of days, set in `config/` or as a named constant, and the
reader opens only the partitions in range. This is the right shape when the
question itself has a time bound: *is this source still working*, *how old is
this address*.

`ledger.shards_in_window` turns the span into a list of stems, so a plan run
opens one or two month files instead of every month the project has written.

**The worked example is the one that ships open.** `ledger.load_published`
answers *have we published this address before*, and it takes `today` and
`within_days`. Given a finite cover it asks for the dates in range and opens
those day files and no others. Given `-1` it walks `state/published/`, naming
every entry it meets and refusing one it cannot place. The committed
`collect.published_window_days` is **`-1`**, so today's answer is every address
ever published - the guarantee the guard has always given. The machinery landed;
turning it down is a later decision on evidence, and
[freshness.md](../architecture/sources/freshness.md#the-published-ledger-files-by-day-and-the-read-carries-a-cover)
carries the reasoning and the day grain.

**Equal is a hole, not a bound.** `CollectConfig` accepts `-1` or a value
strictly greater than `collect.seen_window_days`, and refuses everything between
including equal. At 90 and 90 both stores forget the same address on the same
day: an undated address whose first-sighting row has just expired reads as
first-seen-today and republishes as new. The check is a cross-field validator,
so raising the sight window past a finite cover fails the config rather than
opening the hole quietly.

**`-1` is the only sentinel.** Not `0`, not `null`, and not a very large number -
a large number is a cover that silently becomes finite the day the archive
outgrows it.

### 2. A cover that is not a clock

Sometimes a clock would answer a different question from the one asked. Then the
answer is a cheaper cover, not a shorter memory. Three shapes, all in service
today.

**The files this run staged.** `cli.stage_dedupe_ledgers` settles the keyed
ledgers after a push race merged two sides of a CSV. A run appends only to the
shard its own date routes to, so a repeat can only be in a file that run wrote.
The ordinary pass reads **six files whether the archive holds one month or
sixty**; it used to glob every feed-health, item-health and score shard and find
nothing, because a finished month was settled when it was written. Nothing here
is a clock: an older month is skipped because this run did not write it, not
because it is old, so the bound does not weaken when a run runs long or crosses
midnight. The full pass survives as `idhazh dedupe-ledgers --every-shard`, and
the command **refuses to run with neither flag** - a step that named neither
would get the unbounded pass by accident.

**One run, or one date.** `ledger.load_runtime_counters` already asked
about one run and then read the lifetime file to find it; it streams now, and its
cover is the run id it was handed. `ledger.load_settled_failures` and
`ledger.load_source_counts` take a date and open that day's shard.
`corpus.scored_from_items` reads one run's own items directory. These are bounded
by construction - the input never had a clock, and putting one on it could only
lose work the run just did.

**An identity set cheaper than the rows.** `evals.writer.recorded_observations`
answers *do we already hold this measurement*. `OBSERVATION_KEY` is address,
pipeline fingerprint, output digest and scorer version, and it carries **no date,
deliberately** - the same address, pipeline, output and scorer is the same
measurement whenever it is re-taken. A cover in days would let a January
observation back in February and turn *how many measurements do we hold* into
*how many times did the pipeline look*, which is the one thing the eval ledger
promises it is not. So the memory stayed complete and the representation got
cheaper: `state/score-index/<YYYY-MM>.csv` holds one 76-byte digest an
observation beside the shard it describes. Counted over the committed shards on
2026-09-07 - 7,636 measurements, 819.6 bytes a row - that is 566.8 KB against
6,111.8 KB, so the read is **10.8 times smaller and 90.7 percent of it is gone**,
exact, with nothing forgotten. Counting committed bytes is deterministic, so the
spread is zero. `fingerprint.append_new` is the same shape one size down: it
carries digests rather than built rows, and the set stops growing when the inputs
stop changing.

**A receipt, where the thing read cannot change.** `cli.stage_validate_days`
opened every committed day on every publication. A published day is frozen - the
only thing that can happen to it is deletion - so what invalidates a pass is a
move in the rules, not the passage of time. `state/day-validations.csv` records
the day, the payload's length and digest, and the validator's identity. A later
run skips a day whose receipt names this validator and whose recorded length
still matches `os.stat`, and never opens the payload. Change the validator and
every receipt stops matching, so the archive is re-validated **once**, not on a
window. Measured 2026-09-08 on a developer machine over 18 committed days and
19,867,266 bytes: 0.45 s median over three runs against 0.02 s with every receipt
current. **What is left is honest and small**: the pass still lists the days and
stats each one, so it still costs one `stat` a day, for ever. It says so.

### 3. Unbounded, on purpose, and it says so

This is Guardrail #12's escape hatch taken in writing. Each of these reads opens
everything it holds, and each carries a line naming what it reads and why a
bounded input cannot answer the question.

**A retirement is permanent.** `ledger.load_retirements` declares `-1`. Any cover
in days would forget the oldest, and the run would ask a dead server again
tomorrow.

**A report about a whole series has no time bound.** `ledger.load_visual_prunes`
answers *is the picture backlog shrinking*, which is a question about every pass
on record.

**A rolling window is already bounded, by its writer.** `corpus.read_rows` is
unbounded in code and bounded by design: `roll` evicts the oldest on every
harvest, so the file this opens does not grow however long the project runs. A
cover here would only hide a `roll` that stopped evicting. The same mechanism
bounds `state/traces/`: `retention.prune_traces` deletes whole files past
`observability.trace_window_days`, so there is at most a week of traces on disk
and no read to cover. **A cover can be enforced on the store instead of on the
read**, and where it is, the read needs nothing.

**A validator cannot skip what it has not read.** `contracts.base.Contract.read`
opens one file, never a collection, and half a payload validated is a payload
reported good on the half that happened to be first.

**And three whole-tree walks that stayed.** `assemble.site_size` and
`retention.measure` read the size of every file in the tree;
`retention.count_published_items` parses every staged day payload. Each says so
at the top of its own docstring with the measurement beside it: over
`frontend/public/digest/` at 443 files and 25,070,521 bytes, 2026-09-07 on an
a developer machine, `site_size` took 300.4 ms best and 563.4 ms worst over five
runs and `measure` took 276.8 ms best and 352.3 ms worst - in a job that runs for
hours. The reason they stayed is in
[what did not land](#two-rows-did-not-land-what-was-asked-and-the-page-is-more-useful-for-saying-so)
below.

## The inventory, 2026-09-08

**This table is examples, not the rule.** The rule is the question at the top of
this page. A table of paths is what the deleted archive guard was, and
[Guardrail #12's design rationale](../../CLAUDE.md) records why that failed: it
enumerated the hazard instead of the property, so it covered two collections out
of nineteen and looked finished, and its own upkeep grew with the other
seventeen. Read the rows below to see the three answers in service. Do not read
them as the set of places the rule applies.

**Twenty-one reads over a collection a run appends to**, each with the cover or
the bound its own code declares. A helper that opens one named file is not
listed: its cover is its argument. These are `backend/`'s;
[the site's are below](#the-site-reads-the-same-collections-2026-09-09).

### A cover that is a span of days

| Read | What it opens | Its cover |
| --- | --- | --- |
| `ledger.load_seen` | month shards of `state/seen/` | `collect.seen_window_days`, committed at 90 |
| `ledger.load_health` | month shards of `state/feed-health/` | `ledger.HEALTH_WINDOW_DAYS`, 31 |
| `ledger.load_item_health` | month shards of `state/item-health/` | the caller's `within_days` |
| `ledger.reliability` | the feed-health shards in range | `collect.reliability_window_days` |
| `ledger.load_published` | day files of `state/published/` | `collect.published_window_days`, **committed at `-1`** |

### A cover that is not a clock

| Read | What it opens | Its cover |
| --- | --- | --- |
| `evals.writer.recorded_observations` | `state/score-index/` and `state/score-archive/` | every observation identity, as 76-byte digests |
| `cli.stage_dedupe_ledgers`, via `ledger.keyed_paths` | six files on the ordinary pass | the files this run staged |
| `cli.stage_validate_days` | one `stat` a day, plus `state/day-validations.csv` | a receipt on payload length, digest and validator identity |
| `ledger.load_settled_failures` | one item-health shard | one date |
| `ledger.load_source_counts` | one item-health shard | one date |
| `ledger.load_runtime_counters` | streams `state/runtime-counters.csv` | one run |
| `fingerprint.append_new` | streams `state/fingerprints.csv` | the identities on record, not the file |
| `corpus.scored_from_items` | one run's items directory | one run |

### Unbounded, and it says so

| Read | What it opens | Why no cover |
| --- | --- | --- |
| `ledger.load_retirements` | `state/feed-retirements.csv` | a retirement is permanent; forget one and the run asks a dead server again |
| `ledger.load_visual_prunes` | `state/visual-prunes.csv` | the report is about the whole series |
| `corpus.read_rows` | `corpus/corpus.jsonl` | already rolling, capped at `finetune.corpus_rows` |
| `contracts.base.Contract.read` | one payload | a validator cannot skip what it has not read |
| `assemble.site_size` | every file under `frontend/public/digest/` | three jobs write the tree, so no one process can carry the total |
| `retention.measure` | every file under the built tree | it is the independent audit a maintained total is checked against |
| `retention.count_published_items` | every staged day payload | bytes and items have to come from one corpus |
| `retention._dated_days` | the expired day directories only | it grows with the **backlog**, not with the archive, and shrinks as the prune works |

**Six of these carry the word `Cover:` on the line that declares them** -
`ledger.py` twice, `corpus.py` twice, `fingerprint.py` and `contracts/base.py`.
The rest declare it in the sentence the docstring opens with, or in the signature
itself, and either is enough. What is not enough is nothing.

### The console payload producers, 2026-09-09

Seven producers write the console's own payloads at publication
([console-payloads.md](../architecture/publishing/console-payloads.md)). They
are listed apart because their cover is a **store** bound rather than a read
bound: each published directory is pruned to its own
`observability.public_*_keep_months`, so it holds at most fourteen files however
long the project runs, and every later listing of it is bounded by that. This is
the shape the note above calls "a cover enforced on the store instead of on the
read".

| Read | What it opens | Its cover |
| --- | --- | --- |
| `publish_console.published_months` | one listing of a published directory | the directory's own knob, so at most `keep_months` entries |
| `publish_scores.publish`, `publish_feed_health.publish`, `publish_span_rollup.publish` | the state shard for the month named | the month the run appended to |
| `publish_day_metrics.publish_public` | one month of `state/day-metrics/<YYYY>/<MM>/` | one month, which is at most 31 records for ever |
| `publish_run_days.publish` | one month of committed `run.json` and `digest.json` | one month, which is at most 31 days for ever |
| `publish_console_band.publish` | the newest `months_a_window_can_touch(widest)` run-day shards | `max(console.window_presets)`, committed at 90 |

**Two of them list a tree to learn which months exist**, and that residue is
named rather than hidden: `publish_run_days.months_published` and
`publish_day_metrics.months_recorded` cost one directory entry a year plus one a
month, for ever. Deriving the newest stem from today's date instead would answer
nothing at all for a tree whose last run was two months ago - the same reason
`payload.readShards` lists its own directory.

**One is unbounded on purpose.** `publish_machine.months_on_file` streams
`state/runtime-counters.csv`, which is one appended file with no shards and no
prune, so a run that wants September's rows walks every row ever appended to
find them. No cover in days, no cover in months and no identity set answers
"which rows are September's" more cheaply than reading them. It costs **one file
handle** whatever it holds - the same handle `ledger.load_runtime_counters`
already opens for one run - and what it WRITES is bounded: a row below
`public_machine_keep_months` is dropped on the way through rather than written
into a file the prune would delete on the next pass.

### The oracle, and what it caught

Measured 2026-09-09 against a built fixture of twenty months - twenty state
shards a ledger, twenty day payloads, twenty run manifests - by counting the
files each pass opens with a `sys.addaudithook` hook rather than by timing it.
A stopwatch on this box cannot tell one month from twenty: a sibling row
measured 16.6 percent run-to-run variance on identical work, which is more than
nineteen months of fixture could ever cost. What the reads open is arithmetic
and has no spread at all.

The first pass reads every month, because every target is missing. The second
names the month it appended to and reads **that month and no other**, which is
what `backend/tests/test_console_payloads_producer.py` asserts on the set of
month stems opened.

**The oracle found a defect the design did not.** The missing-file rule and the
prune disagreed about the boundary: the prune deleted the six months past
fourteen, the next pass found them missing and wrote them, and the prune deleted
them again - every run, for ever, on months no console window can reach.
`months_to_write` now refuses a month below `oldest_month_kept`, and the second
pass reads one month rather than seven.

## The site reads the same collections, 2026-09-09

Everything above is `backend/`. The published site reads the committed tree too -
at build time, in the same CI job - and until 2026-09-09 eleven of its reads
opened everything on disk and filtered afterwards. The three answers are the same
three; only the language they are written in changed.

**The cover is a constant in `payload.ts` and not a config read.** `config.ts`
imports `REPO_ROOT` from `payload.ts`, so importing the config reader back would
close a cycle. `ARCHIVE_WINDOW_DAYS` is 90 because that is where
`console.window_presets` ends, and `LEDGER_WINDOW_MONTHS` is `shardMonths(90)`
rather than a second number, so the two covers cannot drift apart. Every console
route works out its own widest preset from the config and converts it with the
same `shardMonths`, so raising the preset widens both reads together; the
constants are what a caller with no window of its own inherits.

**`shardMonths` rounds up and says so.** A month is at least 28 days, so it
returns `ceil(days / 28) + 1` - five for 90, where the calendar allows only four,
because the three shortest consecutive months run to 89 days. One shard too many
costs a file; one too few costs a panel a day it should have drawn.

**The window is anchored on the newest day found, never on today.** A clock
anchor would answer with nothing at all for a corpus that stopped publishing
three months ago, and `latestDate` is `publishedDates(root)[0]` - so the home
page and the root layout would go blank on a quiet quarter rather than showing
the last day there was.

### A cover that is a span of days

| Read | What it opens | Its cover |
| --- | --- | --- |
| `payload.publishedDates` | the day directories the window reaches, newest first, then stops | `ARCHIVE_WINDOW_DAYS`, 90 |
| `payload.latestDate` | the first entry of the above | the same 90, and it only needs the first |
| `payload.loadManifests` | one `run.json` a day in range | its caller's `windowDays` |
| `payload.publishedItems` | one day payload a day in range | its caller's `windowDays` |
| `payload.publishedCharts` | one day payload a day in range | its caller's `windowDays` |
| `payload.telemetryRows` | the telemetry shards the span touches | its caller's `windowDays` |

### A cover that is not a clock

| Read | What it opens | Its cover |
| --- | --- | --- |
| `payload.readShards` | the newest `months` shards of a month-sharded ledger | `LEDGER_WINDOW_MONTHS`, which is `shardMonths(90)` and so 5 |
| `payload.evalRows`, `payload.itemHealthRows`, `payload.feedResults` | through `readShards`, over `state/scores/`, `state/item-health/` and `state/feed-health/` | the same 5 |
| `span-rollup.loadSpanRollup` | through `readShards`, over `state/span-rollup/` | the same 5, and the caller wants the newest entry |
| `runtime-counters.loadMachineCounters` | one file, plus item-health through `readShards` | the shard cover, and `state/runtime-counters.csv` is one file |
| `payload.itemHealthForDay` | one item-health shard | one date |
| `payload.dayMetrics` | one record a date | the dates handed in |
| `payload.telemetryMonths`, `payload.indexMonths` | one directory listing, sliced to the newest months | `LEDGER_WINDOW_MONTHS`, where the caller takes it |

**Two residues are named rather than hidden.** `publishedDates` lists the root
once to find the newest year, which costs one directory entry a year for ever.
`readShards`, `telemetryMonths` and `indexMonths` list their directory to learn
which shards are newest, which costs one entry a month for ever. Neither opens a
file it does not need, and deriving the newest stem from today's date instead
would answer nothing at all for a ledger whose last run was two months ago.

### Unbounded, and it says so

| Read | What it opens | Why no cover |
| --- | --- | --- |
| `routes/archive` -> `publishedDates(root, -1)` and `loadDay` | every committed day payload | this page **is** the archive: the calendar names every published day, the topic pills count stories across all of them, and a cover would delete the older half of the page rather than make it cheaper to draw |
| `routes/archive` -> `indexMonths(root, -1)` | the index directory listing | it is the list of months a reader may ask for, so a cover hides the older ones |
| `routes/console` -> `telemetryMonths(root, -1)` | the telemetry directory listing | it is how far the operator can pan, which is a different question from how far a panel can draw; it opens no file, and what crosses is seven characters a month |

**Two entries retired on 2026-09-09, and they were the two the build paid for
every run.** `routes/[date]` and `routes/[date]/[vertical]` each took a `-1`
because `entries` is the list of pages the build writes, and a cover there
stops writing them past it - the calendar would link to nothing and a dated link
would 404. Neither route is prerendered any more. One document answers every
dated URL and the browser fetches the day it names, so there is no list of pages
to build and nothing to cover: the build reads the digest tree for `/` and
`/archive/` and for nothing else. **The uncovered read did not move somewhere
cheaper - it stopped existing**, which is the only way one of these entries is
ever meant to leave this page. What replaced it is one bounded read a reader's
own browser makes: one date, one payload, decided by the address they asked for.

### What the cover bought

Measured 2026-09-09 on a developer machine, Node 24.12.0, over a synthetic
digest tree of 410 published days and 15 month shards, 214,632,096 bytes. Both
covers run alternately in one process, nine passes each, so page cache and
machine load are the same for both.

The ten reads together took **9,570.5 ms uncovered and 2,657.8 ms covered** -
**3.6 times faster, and 72.2 percent of the time is gone**. The four that cost
the most: the score ledger 2,124.0 ms against 604.5 ms, the shard primitive
1,615.0 ms against 597.8 ms, the article counts 1,724.4 ms against 356.7 ms, the
chart counts 1,718.4 ms against 367.9 ms. Spread was wide on the uncovered arm
and narrow on the covered one - the score ledger ran 2,003.8 to 2,817.4 ms
uncovered and 503.4 to 726.5 ms covered.

**The clock cannot answer the question the cover exists for, and this box proves
it.** The same covered arm on the same 410-day tree measured 2,657.8 ms inside
the paired run and 3,099.3 ms standalone a few minutes later - 16.6 percent apart
on identical work, which is more than ten days of archive could ever cost. So the
oracle is taken on what the reads open, which is arithmetic over the tree and has
no spread at all:

| Tree on disk | Days it holds | Bytes it holds | Files the cover opens | Bytes the cover opens |
| --- | --- | --- | --- | --- |
| before | 420 | 224,223,165 | 195 | 53,328,670 |
| ten days later | 430 | 227,199,355 | 195 | 53,328,670 |

Ten more published days, 2,976,190 more bytes on disk, and **the same 195 files
and the same 53,328,670 bytes read - equal to the byte**. Every count the reads
return is identical too: 90 dates, 20,550 score rows, 26,135 item-health rows, 90
manifests, 90 day payloads, 5 telemetry months. That is what Guardrail #12 asks for,
and it is why the answer is a count of files rather than a stopwatch.

## The developer loop reads the built tree, 2026-09-10

The three reads below are neither `backend/`'s nor the site's. Two belong to
`frontend/scripts/build-state.ts`, which decides whether a test result may
certify a tree, and they are here because **the shell-and-fetch plan left them
growing and said so rather than fixing them** (Carmack, 2026-09-08). A plan that
bounded nineteen reads and left two of its own is worth recording exactly that
way.

| Read | What it opens | Why no cover |
| --- | --- | --- |
| `build-state.outputFingerprint` | every file under `frontend/build` and `frontend/.svelte-kit/output` | a fingerprint that skipped a file cannot say the tree did not change, which is the only thing it is for |
| `build-state.inputFingerprint` | every tracked and untracked file `git ls-files` names, minus the test-only paths | the same, from the other side: an input it did not hash is an input that can move under a green result |

**Both still grow with the archive after the migration, and the reason is the
part of the tree the migration did not touch.** Row #14 deleted 116 dated
documents, so `frontend/build` no longer gains an HTML file and a `__data.json`
per published day - but `frontend/public/digest/` gains a day payload and its
rendered pictures every run, `copy-visuals.mjs` stages them into the build, and
both hashed trees carry them. Measured 2026-09-08 on a developer machine:
`assertBuild` costs 16.2 s, of which 3.23 s hashes 66.55 MB of inputs and 12.93 s
hashes 222.4 MB across 1,589 output files. **The dominant term is per-file, not
per-byte**: sha256 on that class of CPU runs at 1 to 2 GB/s, so the bytes are
about 0.2 s and the other 98 percent is syscalls, and `hashFiles` opens each path
twice.

**The cost of leaving it, stated rather than hidden.** It is a developer-loop
cost and zero in CI, which runs each check once in its own job and never
re-certifies a tree. It rises by whatever a published day adds to
`frontend/public/digest/` - about 0.96 MB and its share of the files, at the
slope measured on 2026-09-10
([../reference/measurements.md](../reference/measurements.md)). Nothing here is a
per-reader or per-run pipeline cost.

**Why no cover was written, and what it would take.** The honest cover is not a
window: it is hashing a manifest the build already writes instead of walking the
tree it produced. That is a new persisted artefact and a new agreement about what
"the same tree" means, so it is a person's decision rather than a tidy-up. Until
somebody takes it, these two are the escape hatch in use.

**The re-encode migration is the third, and it is a person running it once.** A
later encoder swap re-embeds every published day, so its cost is the whole
archive by construction (row #17 decision 3 of the shell-and-fetch plan, Andre,
2026-09-08). It is legal here for the reason the hatch exists: a human runs it,
once, on a swap, and it is never a per-run cost. **It degrades progressively
rather than atomically** - `build_search_index` takes its header from the newest
day carrying vectors and demotes every day that disagrees to
browsable-but-not-searchable, on one log warning. So a half-finished re-encode
leaves the archive readable and the search scope short, rather than leaving it
broken.

## Two rows did not land what was asked, and the page is more useful for saying so

**The site-size total shipped its retraction half only.** `retention.SiteSize.minus`
carries the total forward where one process both writes and deletes, so an
ordinary deletion pass no longer re-reads the whole tree to learn a number it is
already holding. The three walks above stayed, and the reason is structural
rather than an excuse: **three separate jobs write `frontend/public/digest/`** -
the visuals job renders, the assembly job writes the day payload, the cleanup
pass deletes - so a total one of them accumulated would silently miss what the
other two did, in the number that feeds the site-size card. Carrying one between
three jobs means writing it down, which is a new persisted contract and a
person's decision. So the three walks declare their growth instead.

**The state-prune row's premise was measured and refuted, so nothing was
optimised.** The row asked for the dated walk that `retention._dated_days` gave
the visual tree to be given to the state prunes as well, on the premise that they
list and sort every partition directory on every pass. Counted rather than timed
on 2026-09-08, on a developer machine: a not-due pass makes **5 directory
opens and 0 shard stats**, and the 5 does not move when the tree holds forty-six
times more. **A month partition is a file, not a directory**, so there was no
partition directory for a dated walk to skip, and the sort the premise objected
to is a sort of names already in hand. Guardrail #10 says the design changes when a
measurement contradicts it, so the optimisation was not written. The row shipped
the defect the measurement uncovered instead: three month-name recognisers
disagreed, and one was deleting files the other two protected. The rule they now
share is [what counts as a month name](partitions.md#what-counts-as-a-month-name),
and the full working is
[in the layout doc](../architecture/publishing/layout.md#the-state-prunes-were-already-constant-cost-and-the-premise-that-said-otherwise-was-wrong-2026-09-08).

Both are worth more on this page than a clean sweep would have been. A rule whose
inventory only records the reads that bent to it teaches nothing about the ones
that will not.

## What a walk over the archive costs a test

`CLAUDE.md` section 13 says a test's cost belongs to the code it checks, never
to what the pipeline has piled up. This is the measurement behind that
sentence, and it is the reason the rule is worded as a refusal rather than as
advice.

Measured 2026-09-05 on an Intel Core i7-1265U, over 16 published days and 6,539
stories: reading and parsing the whole archive cost 0.15 s, and running the
function under test on every story cost a further 0.02 s. The two frontend
checks that assert once per published story cost 270 s and 93 s. So the work
was never the archive - it was the same handful of cases re-checked tens of
thousands of times. Those 6,539 stories carried six distinct cases between
them, which means the corpus stopped teaching anything on about day one while
the bill went on arriving every four hours.

Two consequences follow, and both are rules in section 13 rather than advice
here. A per-item rule is driven from a bounded fixture, because a bounded
fixture can also carry the case the archive has never produced - eleven failure
causes with a 529-to-1 spread, or a source sitting exactly on a display cap.
And where the question really is about the whole tree, it is asked once and
asserted on the total, because the producer already validated every payload at
write time and a frozen day cannot grow a fault later.

## Design rationale

**The declaration is the deliverable, not the saving.** Five of the reads above
open materially less than they did: the eval writer reads a digest index instead
of the rows, settlement reads six files instead of every shard, day validation
stats a file instead of parsing it, the visual cleanup lists 261 directories
instead of 417, and an ordinary deletion pass walks the tree once instead of
twice. **The other sixteen still read the same rows they always read** -
including the published guard, whose rows moved into day files and whose answer
did not. What changed for those is that each now says what it covers, so the next
person to widen one has to argue with a sentence rather than with silence. A read
that quietly grew was never refused by anybody, because nobody was looking at it.

**It is stated as a property because a list expires.** The archive guard deleted
on 2026-09-06 held every test against two hand-written path patterns. It failed
three ways and all three are the same failure: it enumerated the hazard rather
than the safe set, so it covered two collections and looked complete; its own
upkeep grew with the collections it did not cover, which is the defect it existed
to catch; and being a list, the only way past it was to edit it, which made a
judgement call look like a permission slip. The question at the top of this page
survives a collection nobody has invented yet.

**A cover is not always a clock, and the eval writer is why that had to be
written down.** A clock is the shape a reader reaches for first, and it is wrong
whenever the question has no time in it. Reaching for one there does not just
cost bytes - it changes the answer, quietly, into an answer to a different
question.

**`-1` is a value and not an absence.** A missing cover and an unbounded cover
look the same in a running program and are opposites in review. One means nobody
decided; the other means somebody did. The sentinel exists so a diff can tell
them apart.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A test that scans the tree for unbounded reads | It is the archive guard again. A guard over a hazard list is wrong the day after it is written, and its own cost grows with the collections it does not cover. Review is the control, and the reviewer's question is the one at the top of this page. |
| A finite default for `collect.published_window_days` | Every case where forgetting helps happens within days; every case where it hurts happens after months. A finite value is a later decision on the evidence the guard now records, and it is an escalation for any agent. |
| `0` or `null` as the unbounded sentinel | `0` is a legitimate finite cover and `null` is indistinguishable from a knob nobody set. Neither says a person chose. |
| A very large number instead of `-1` | A cover that silently becomes finite the day the archive outgrows it, with no diff and no error at the moment it starts forgetting. |
| A clock on the eval writer's dedupe | It would let a January observation back in February, turning a count of measurements into a count of times the pipeline looked. The cheaper representation keeps the answer and drops 90.7 percent of the bytes. |
| Re-validating published days on a window | A frozen day cannot stop matching a contract on its own, so a window would re-read the same bytes to reach the same verdict, on a schedule. What a rule change needs is one full sweep, which is what the receipt gives. |
| Windowing the retirement, corpus and contract reads for consistency | Each would lose something real - a dead endpoint woken again, a census computed off part of its own window, a payload passed on the half that was read first. Consistency is not a reason to make a read wrong. |

## See also

- [partitions.md](partitions.md) - the companion: what a layout obliges a writer to do, the freeze rule, and what counts as a month name.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md#a-ledger-partitions-only-when-its-read-carries-a-window) - why a ledger partitions at all, and which reads carry a window.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md#the-published-ledger-files-by-day-and-the-read-carries-a-cover) - the published cover, the day grain, and the argument it reversed.
- [../architecture/publishing/retention.md](../architecture/publishing/retention.md#what-bounds-the-committed-state-tree) - what bounds each committed collection, and the state-prune measurement.
- [telemetry.md](telemetry.md#the-committed-traces-briefly) - a store bounded by its prune rather than by a read.
- [../reference/data-growth-audit.md](../reference/data-growth-audit.md) - the audit these reads were found in, and what each finding cost.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #12, which this page is the address of, and Guardrail #10 on what a measurement obliges.
