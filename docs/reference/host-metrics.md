# What the pipeline records about the machine it ran on

**Last Updated**: 2026-09-20

Every column of the host fingerprint, what it means, and what it is for. One row
a job, by every job that draws its own runner - written in two halves, one at job
start and one at job end.

Read this when a number surprises you and you want to know which machine
produced it. Why the record exists at all, and what the fleet does to a reading,
is [the processor lottery](benchmarks/the-processor-lottery.md).

**Three panels on the operator console read it, from 2026-09-17.** The machines
one run drew, the reading-against-writing split repeated once per machine, and
the count of what the platform has been giving us over a window. What each may
draw and what it may never draw is
[../concepts/console-design.md](../concepts/console-design.md). The whole column
set is still operator-only: the console reads it at build time under
`$lib/server/` and no cell of it crosses to a reader.

## Where it lives

| | |
| --- | --- |
| Contract | [`backend/idhazh/contracts/host_fingerprint.py`](../../backend/idhazh/contracts/host_fingerprint.py) |
| Generated schema | [`schemas/host-fingerprint-row.schema.json`](../../schemas/host-fingerprint-row.schema.json) |
| Store | `state/host-fingerprint/<YYYY>/<MM>/<DD>.csv` for the daily run; `state/pipeline-tests/host-fingerprint/<YYYY>/<MM>/<DD>.csv` for a bench dispatch |
| In transit | `state/segments/host-fingerprint/<run>-<attempt>-<job>-<shard>.csv` - one file a job, folded into the store above and deleted |
| Producer | `idhazh fingerprint` and `idhazh job-clock`, through [`backend/idhazh/telemetry/silicon.py`](../../backend/idhazh/telemetry/silicon.py). The store above is written by `idhazh compact` and by nothing else |
| Read by | `/console/machine/`, at build time through `frontend/src/lib/server/host-fingerprint.ts` |
| Key | `date`, `run_id`, `job`, `shard` - one row a job |
| Switch | `observability.host_fingerprint` |
| Committed | **from 2026-09-16.** Each job's own commit step stages its ledger; every row taken before that date was deleted with its runner |
| Published to a reader | **no.** Operator surface only |

**Every job of `digest.yml` writes a row, from 2026-09-17.** `plan`, `work` and
`assemble` each draw their own runner, so a run that measured one of them could
not say what the other two cost. The `work` shards had the record from the start
because they hold the model server; the two jobs either side of them spent time
nobody could attribute to a processor.

**No job writes the day file, from 2026-09-17.** Each writes its own segment and
the fold in `assemble` is the one writer of the day. Ten writers on one path is
what emptied 2026-09-16; the design rationale below says what it cost and why a
merge driver was never going to settle it.

**The row arrives in two halves, from 2026-09-18, and neither is ever edited.**
The probe runs before the job's heaviest step, because the bandwidth reading
wants a gigabyte and an idle machine. What the job cost - its wall clock, and
what opening the weights cost before the first item - is only knowable once the
job is over. So `idhazh job-clock` writes a second row of the same shape into the
same segment, carrying those two cells and repeating nothing, and the fold takes
the union. **A job that dies between the two leaves a usable half-row with two
empty cells**, which is the degrade path rather than a failure - and an empty
cell is what says the reading was not taken, where a zero would claim a job that
cost nothing.

The two halves share one segment because the path grammar names the job and not
the step: `<run>-<attempt>-<job>-<shard>.csv` has no element two steps of one job
could differ in. They are two rows of the file that job owns.

**A bench dispatch writes into a tree of its own.** `measure.yml` redirects its
whole state root with `run.trial_state_dirname`, so its rows land under
`state/pipeline-tests/`. The reason is in the design rationale below.

**It files by day, and that is the shape the read wants.** A host record only
earns its keep when somebody counts across many days, and a day tree is the
shape a bounded window can read (Guardrail #12).

**Two tables join on the key, and no column is duplicated to make that work.**
This table and `state/item-health/<YYYY>/<MM>/<DD>.csv` both carry `date`,
`run_id`, `job` and `shard`, and a job runs on one machine, so the key is the
join. There is deliberately no `host_fingerprint` column on the item row: it
would be a second copy of a value this table already holds, and a second copy is
a thing that can disagree.

**The item row is the third from 2026-09-17, and it is the one that answers per
item.** It carried `shard` from 2026-08-30 and could spell three of the four
columns; `plan`, `work` and `assemble` all write shard 0, so three of the four
found every job of the run rather than the one that read the item. With `job`
beside it the question "which processor summarized this item, and what could it
do" is one equality:

```sql
SELECT ih.item_id, hf.fingerprint, hf.cpu_model, hf.microcode, hf.flags
FROM item_health ih
JOIN host_fingerprint hf
  ON hf.date = ih.date AND hf.run_id = ih.run_id
 AND hf.job  = ih.job  AND hf.shard  = ih.shard
```

**What a machine WAS is here; what it HAD at the moment is on the item row.**
This table is taken once a job and holds the parts - the processor, its cache,
its flags. Memory moves inside a job, so it is sampled per item instead: six
`os_` columns on `state/item-health/` carry what `/proc/meminfo` said, including
the lowest headroom seen while the model worked on that one item
([../architecture/sources/item-health.md](../architecture/sources/item-health.md#what-the-machine-had-against-what-a-process-held)).
Neither table repeats the other's cells.

## Identity

| Column | Type | What it is |
| --- | --- | --- |
| `version` | date stamp | The schema generation this row was written under |
| `date` | `YYYY-MM-DD` | The run's date |
| `run_id` | run id | The run |
| `job` | **enum**: `plan`, `work`, `assemble`, `visuals`, `runtime` | Which workflow job drew this machine |
| `shard` | int, 0+ | The shard inside that job. A single-shard job writes 0 |
| `fingerprint` | 16 hex characters? | A digest over the cells that cannot change inside a job |

**`fingerprint` is the column that makes the collection countable.** It digests
vendor, family, model, stepping, model name, cores, threads, L3 and flags - and
nothing else. Bandwidth, clock and uptime move between two jobs on identical
machines, so including them would give every job its own value and the column
would count nothing. Two draws of one kind of machine carry one id, which is what
lets a query ask "how often do we get this machine" without matching model-name
strings by hand.

**Every value of `job` is that job's own id in its workflow file, lowercase.** A
reader goes from a row to the steps that wrote it with nothing in between, and a
display name would drift from the thing it identifies. `visuals` is the one value
with no producer left: `digest.yml` ran that job until 2026-09-13, and the member
stays so the rows it wrote still read back. `runtime` is `measure.yml`'s bench
job, and its rows are in the other store.

## What the processor is

Every cell here is the host's own report from `/proc/cpuinfo`. None of it is a
codename anybody recognised.

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `cpu_model` | string? | The `model name` line | The label a person recognises |
| `cpu_vendor` | string? | `vendor_id` | Splits the fleet at the coarsest level |
| `cpu_family` | int? | `cpu family` | With model and stepping, names the part exactly |
| `cpu_model_number` | int? | `model` | The number, not the marketing name |
| `cpu_stepping` | int? | `stepping` | Two machines with one model name can differ here |
| `microcode` | string? | `microcode` | Moves under a fixed stepping, so a performance change with no other change shows up here |

**Two machines reporting the same `cpu_model` are not the same machine.** Four
draws all reporting AMD EPYC 7763 differed by 8.8 percent on decode. Family,
model and stepping are the columns that can say why, and `microcode` is the one
that moves without anything else moving.

## What the processor can do

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `flags` | string | The watched instruction-set flags, sorted, space joined | **The cell that tracks prefill.** llama.cpp dispatches to a different kernel when the wider instructions are there |
| `cores` | int? | Physical cores | Constant at 2 on every machine drawn so far |
| `threads` | int? | Logical processors | Constant at 4 so far |
| `l3_cache_bytes` | int? | L3 as the kernel reports it | Ranges 32 MiB to 480 MiB across the fleet, and **it is what sizes the bandwidth probe.** Read it beside `memcpy_probe_mib` |

**`flags` holds only the flags in `WATCHED_FLAGS`**, which is a fixed tuple in
the contract: the AMX, AVX-512, VNNI, FMA and SSE entries an inference runtime
dispatches on. A raw `flags` line is two hundred words and most of it says
nothing about throughput. Adding one to the watched set is a code change and not
a schema change, which is the trade: the column stays a fixed width, and the
vocabulary lives in the contract rather than in the schema.

**An empty `flags` is a reading, not a gap.** The machine we draw most, the EPYC
7763, reports none of the watched AVX-512 entries at all.

## What the processor will not tell us

**No cache hit rate, no cache miss rate, no cache occupancy.** The guest has no
hardware performance monitoring unit, so there is no counter to read. The gap is
in the machine, not in this record's column set.

Read on `ubuntu-latest` on 2026-09-20 by
[`.github/workflows/probe.yml`](../../.github/workflows/probe.yml), on three
draws of image `ubuntu-24.04` 20260907.300.1, kernel `6.17.0-1022-azure`. An AMD
EPYC 9V74 80-Core and an AMD EPYC 7763 64-Core answered all six reads
identically; an Intel Xeon Platinum 8573C answered the first two the same way.

```
$ cat /proc/sys/kernel/perf_event_paranoid
4

$ ls /sys/bus/event_source/devices/
breakpoint
kprobe
msr
software
tracepoint
uprobe

$ ls /sys/bus/event_source/devices/cpu/events/
-> no such directory

$ ls -d /sys/fs/resctrl
no resctrl

$ grep -om1 rdt_a /proc/cpuinfo
no rdt_a

$ grep -om1 cqm_occup_llc /proc/cpuinfo
no cqm
```

**The `cpu` event source is the one that decides it.** Every source the guest
does list is the kernel's own software instrumentation - a breakpoint, a probe
point, a tracepoint, a model-specific register - and none of them counts a cache
access. `cpu` is the entry a hardware unit publishes, and its directory is not
there at all. So the rule is: **an absent or empty
`/sys/bus/event_source/devices/cpu/events/` closes the question.** No profiling
toolchain reads what the host does not expose, and installing one only moves the
failure later.

**`perf_event_paranoid` at 4 sits beside that and is not the blocker.** It is a
sysctl, and the runner carries passwordless sudo, so it is adjustable. A missing
unit is not.

**Cache occupancy through the resource-director interface is gone the same way.**
`/sys/fs/resctrl` is not mounted and `/proc/cpuinfo` carries neither `rdt_a` nor
`cqm_occup_llc` - which is what a host keeps to itself when it isolates tenants.
Even where it answered, the reading would vary by draw, because the L3 sizes
recorded above span 32 MiB to 480 MiB, so it could not be compared across a run.

**What this reading cannot settle:** whether a different runner image, or a
different pool, would answer differently. It names the image and the kernel it
read, so the next person can tell whether they are asking the same machine.
Three draws across two vendors answering identically is the reason it is written
down once rather than retaken per draw.

## Why the model server's memory mark reads lower than it did

`llama_rss_peak_bytes` on the item row is `VmHWM` for the model server, and one
server serves a whole shard - so a figure that goes down from one item to the
next says something is wrong. It goes down in every shard. **Almost all of that
is the rows being read in an order the mark was never taken in, and the small
remainder is the kernel's own rule for what `VmHWM` prints.**

Measured 2026-09-20 over the whole committed `state/item-health/` tree by
[`backend/utilities/server_memory_mark.py`](../../backend/utilities/server_memory_mark.py)
- 1,250 rows carrying the mark, over 28 day files and 68 jobs. Exact counts over
committed files, so no spread.

| Rows read in this order | Pairs | Falls | Jobs with a fall |
| --- | --- | --- | --- |
| `item_started_at` - where the fetch loop reached the item | 1,182 | 277 | 68 of 68 |
| `item_ended_at` - where the mark was read | 1,182 | 15 | 13 of 68 |

**The row carries two clocks and they are two different orders.** The work stage
fetches every item and then runs the model over them sorted by source length, so
`item_started_at` is the fetch loop's order and the mark is read one statement
before `item_ended_at` is stamped. 1,144 of the 1,250 rows sit at a different
position under the two. Read on the fetch clock, 95 percent of the falls are an
item's mark compared against an item whose mark was taken later.

**The 15 that survive are the kernel, not a restart.** Every one of them has the
server holding within 0.75 percent of the resident set it held on the row
before - a restarted server has given the weights back and reads a fraction of
12 GB - and every drop is a whole number of 4 KiB pages, between 136 KiB and
620 KiB. Meanwhile the server's current resident set falls in 324 of the same
1,182 pairs, worst drop 566 MB, so the machine is taking pages back from it all
the time.

`VmHWM` is the larger of the current resident set and a stored mark the kernel
refreshes only when the process itself gives memory back. It never reclaims
into that stored mark. So a resident set that climbs, gets read, and is then
reclaimed before any unmap records it leaves the next read lower than the last
one. The archive shows the outside of that rule directly: the mark reads below
the current set on 0 of 1,250 rows, and equals it exactly on 298.

**What this reading cannot settle:** no row carries the server's process id, so
a restart is ruled out by the resident set rather than by identity. That
separates a restart from a reclaimed page; it cannot separate two processes that
happened to hold the same amount. It also says nothing about how much of the
mark is weights against working memory - there is no per-region reading here.

**The committed rows are not wrong; the column's description was.** Every value
is what `/proc/<pid>/status` printed at that item's two boundaries, highest of
the two. What was wrong was the sentence beside it, which said "peak resident
memory of the model server over the item" - it is not scoped to the item, and it
is not a peak that only rises.

## What the machine was doing when we asked

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `mhz_max` | float? | `CPU max MHz` | The ceiling the host publishes, where it publishes one |
| `mhz_at_probe` | float? | Mean `cpu MHz` across processors at probe time | **Not a reading under load.** The probe runs before the job's heaviest step, so this says what the machine idles at |
| `boot_seconds` | float? | Uptime when the probe ran | A small number is a freshly started machine; a large one was pooled and handed to us |
| `memcpy_gib_s` | float? | Large-block copy rate, bytes read plus written | **Decode is bandwidth bound and this is the only bandwidth reading anywhere** |
| `memcpy_probe_mib` | int? | The buffer each side of the copy used, as used rather than as configured | Says whether `memcpy_gib_s` measured memory or cache |

**`memcpy_probe_mib` is why `memcpy_gib_s` can be trusted.** A buffer that does
not clear `l3_cache_bytes` measures cache, and reads several times higher than
memory. The two columns sit side by side so nobody can read one for the other,
and `observability.host_fingerprint_bandwidth_floor_mib` sets the floor - **zero
switches the probe off and leaves the rate empty**, which is different from a
rate of zero.

**The probe sizes itself against the machine, from 2026-09-20.** The buffer is
the larger of that floor and twice the L3 this machine reports, so a part with
more cache than anybody has drawn cannot quietly turn the reading into a cache
reading. There is no longer a sentence here asking a person to raise a constant
when a bigger part arrives. What it costs: on a machine reporting 480 MiB the
probe holds two buffers of 960 MiB, so 1.9 GiB of the runner's 16 GB, taken
before the model server starts.

**A row divides `memcpy_probe_mib` by `l3_cache_bytes` to grade its own rate**,
and rows written before that date do not survive the division. Measured
2026-09-20 over the 60 rows then committed under `state/host-fingerprint/`,
exact counts over committed files and therefore carrying no spread:

| L3 reported | Buffer / cache | Rows | Rate, min / median / max GiB/s |
| --- | --- | --- | --- |
| 32 MiB, AMD EPYC 7763 | 16.00 | 52 | 29.40 / 40.39 / 48.57 |
| 48 MiB, Intel Xeon 8370C | 10.67 | 1 | 25.02 |
| 260 MiB, Intel Xeon 8573C | 1.97 | 4 | 21.96 / 23.17 / 26.42 |
| 480 MiB, Intel Xeon 6973P-C | 1.07 | 3 | 24.44 / 25.08 / 26.08 |

The buffer is 512 MiB on all 60, so the seven rows in the last two lines are the
ones a reader cannot grade. **Their rates are the seven slowest of the 60, not
the fastest**, which is the opposite of what a cache-resident buffer would do -
so the undersized margin is a reason to distrust those figures rather than
evidence that they were inflated. The likelier reading is that these two Xeon
parts are simply slower per allotted processor than the EPYC 7763, and the
probe cannot say so while its own buffer is in question.

## Where the platform put us

| Column | Type | What it is |
| --- | --- | --- |
| `vm_size` | string? | The platform's own name for this machine size |
| `vm_location` | string? | The region |
| `vm_zone` | string? | The availability zone, where one is published |
| `vm_fault_domain` | string? | The fault domain, which separates one rack from another |
| `runner_name` | string? | The runner label the platform gave the job |
| `measured_at` | timestamp? | When the probe ran |

These four come from the host metadata service on a link-local address. **They
are the placement decision in the platform's vocabulary rather than ours**, which
is the only way to ask whether "a lottery" is really "which pools we draw from".
A machine that does not answer records nothing, which is every developer machine.

`fingerprint` and `measured_at` are the two cells that carry a question mark
because of the second half: the half a job writes at its end measured no machine,
so it names none and stamps no probe time. A compacted row carries both, because
the probe's half is where they come from.

## What the job cost

The half written at job end. Every reading comes from the workflow - one from a
step that ran before the checkout existed, one from the log of the server this
job started, one from that server's own `GET /metrics` body - so a run of the
stage anywhere else records none of them.

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `model_load_ms` | float? | Milliseconds the server spent opening the weights before the first item | The fixed cost `run.shard_size` exists to amortise. Measured 1.1 to 1.5 percent of a work shard's fixed cost |
| `job_seconds` | int? | The job's own wall clock, first step to the clock write | **The cell the truncation-cap rollback reads.** Before it, that number lived only in the GitHub jobs API, which drops a job record when the run ages out |
| `server_prompt_tokens` | int? | Prompt tokens llama-server itself counted reading, cached tokens excluded | **The second instrument.** The item ledger's own answer is `sum(input_tokens) - sum(cached_tokens)`, and arithmetic over that ledger cannot check that ledger |
| `server_prompt_seconds` | float? | Seconds llama-server itself counted reading prompts | The other half. A rate is a ratio, and the 80 percent defect this check caught in August 2026 was in the numerator, so one cell alone could not see it |

**`job_seconds` is a floor on the job's wall clock and never a ceiling.** The
steps after it - the ledger push, two log summaries and the artifact uploads -
are outside the window. Only the `work` job stamps the clock its first step
reads, so only `work` rows carry these cells today.

**`server_prompt_tokens` and `server_prompt_seconds` are the only two cells on
the site that can disagree with the item ledger.** Everything else that answers
"how fast did this run read?" is arithmetic over `state/item-health/`, and a sum
over a ledger cannot tell you the ledger is wrong. These two come from a counter
the model server kept on its own, so the two answers are independent - which is
what let a 0.746 percent drift on one article be seen at all. The bound is 5
percent and it is not a `config/` knob: tuning it is how a failing check is made
to pass.

**These cells sit here and nowhere else, and that is on purpose.**
`state/runtime-counters.csv` carried a second copy of them until 2026-09-20. The
arithmetic and the wire-name table behind them now live once, in
[`backend/idhazh/telemetry/silicon.py`](../../backend/idhazh/telemetry/silicon.py),
beside the stage that writes the row - two subtractions of one pair of instants,
or two readings of one counter, are two things that can disagree.

## Why almost nothing here is an enum

**`job` is an enum. Nothing else is, and that is the rule rather than an
oversight.**

`job` is a name this project chose, in `.github/workflows/`. A closed set is
correct: a typo should be refused, because a third job nobody can group by is a
silent hole in every query.

Every other identifier is **a string a vendor or a cloud chose, and they change
it without telling us.** A vendor ships a new part, a cloud adds a machine size,
a microcode revision lands. If `cpu_vendor` or `vm_size` were closed sets, the
first unfamiliar value would fail validation and **the run would lose the very
reading that was worth having** - the new machine is exactly the case the
instrument exists to catch.

So the rule for this record is: **a value we author is an enum; a value the
machine reports is a string.** The cost is real and worth naming - a typo in a
host string cannot be caught by the schema, and a query grouping by `cpu_model`
will treat two spellings as two machines. `fingerprint` is the mitigation: it is
derived from the strings rather than typed by hand, so grouping by it is stable
even when a vendor changes how it spells a name.

`flags` is the one judgement call. Its vocabulary IS closed - `WATCHED_FLAGS` -
but it holds a set rather than one value, and a CSV cell holds a scalar. A joined
string keeps one column; the cost is that a reader of the schema cannot see the
closed set and has to open the contract.

## Design rationale

**Record every job, not a subset.** A run is only as fast as its slowest job, so
a run whose slowest job is unmeasured is a run whose cost nobody can attribute.
Until 2026-09-17 only the `work` shards wrote a row, because the probe was built
for the model server - and the two jobs either side of them, one of which builds
the whole site, spent time no processor could be named for. Every job that does
real work now runs the probe, and each job's own commit step stages the row it
wrote. Owner ruling, 2026-09-16.

The placement rule travels with it. The probe wants about a gigabyte and an idle
machine, so it runs before the job's heaviest step - ahead of the model server in
`work`, ahead of the embeddings and the site build in `assemble` - and after the
plan file exists in every job, because the row is filed under the run's own id.

**A bench dispatch writes under `state/pipeline-tests/`, not beside the
production rows.** A bench is dispatched ad hoc, many times a day, against
branches nobody merged. Mixing those rows into the ledger the console reads would
mean every panel filtering by job for ever - a cost paid on every read, by every
reader, to keep a few dispatches apart. The split pays it once instead. What it
costs is a join whenever somebody asks what machines GitHub has given us across
both, and that is a question asked rarely and by an operator. The mechanism is
the one that already existed: `run.trial_state_dirname` moves the whole state
root for a run, so one input on the candidate-config action puts every ledger
that run writes under the trial tree, and no second way of doing the same thing
was minted. Owner decision, 2026-09-16.

**Nothing staged this ledger until 2026-09-16, so there is no history to query
before that date.** The probe ran on every work shard, wrote its row into the
runner's own checkout, and no commit step named the path - so the file went with
the runner. `git ls-files state/host-fingerprint*` returned nothing at all, which
is the proof and also why nobody noticed: the instrument reported success, the
log line printed the machine, and the store stayed empty. Three things changed
together: the work job's commit step stages `state/host-fingerprint`, a
header-only day file is committed so `git add` under `set -euo pipefail` cannot
abort that step on a fresh clone, and assemble's refresh set names the path so a
lost push race hands it back to the tip rather than union-merging two copies.
Authority: Carmack, 2026-09-16.

**The guard that would have caught this was scoped to one source file.** A test
already compares the ledgers a stage writes against the paths its job stages, and
it reads `stages/work.py`. The probe is not there - it runs from `cli.py` as its
own subcommand, early, because the bandwidth reading wants an idle host. So the
guard was correct and blind at the same time. A second guard reading
`telemetry/silicon.py` shipped beside the fix and was retired on 2026-09-17: a
second file-scoped guard is the same defect a second time. **Scoping a
drift guard to a file rather than to a question is what let a second writer
through**, and what replaced both names no file - it charges each store to the
job whose `python -m idhazh <verb>` step reaches its writer, so a fourth job that
records a machine and stages nothing fails without an edit
([../architecture/publishing/committing.md](../architecture/publishing/committing.md#the-commit-steps-push-through-a-rebase-and-the-one-that-can-rebuild-rebuilds)).

**A repeated row now settles, and it could not have before.** `ledger.keyed_paths`
is the registry that pairs a ledger with what makes two of its rows one record,
and this ledger was not in it - which
cost nothing while nothing was committed and would have cost a double-counted
machine the moment something was. A job runs on one machine, so two rows under
one `(date, run_id, job, shard)` are one machine written down twice, and the
fleet distribution is the one question this record exists to answer. The first
row wins; there is nothing to choose between two attempts that read the same
host. Authority: Fowler, 2026-09-16.

**Staging the shared path was not enough, and 2026-09-16 is the file that proves
it.** The day was staged, committed and pushed by ten jobs of one run, and
`state/host-fingerprint/2026/09/16.csv` is header-only. Each job appended to one
path in its own checkout, the pushes raced, and a merge driver settling two
appends could not help: a rebase hands a job the tip, the job replays its own
append, and the last writer to win a race carries whatever its checkout held.
**A shared path is the defect; a settlement rule on top of it is a repair.**

So from 2026-09-17 no job opens the day file. Each writes
`state/segments/host-fingerprint/<run>-<attempt>-<job>-<shard>.csv`, which names
the run, the try at it, the job and the shard - four cells that make a filename
one writer's alone - and `idhazh compact` inside `assemble` folds them into the
day and deletes them. The `plan` job of the next run folds anything an `assemble`
that died left behind, so a segment waits at most one run.

**The attempt is in the name and in no column.** GitHub keeps the run id stable
across a re-run and increments the attempt, so without it a second try takes the
path its first try already wrote - in exactly the case where the two disagree,
because the first is the one that died. With it, both files reach the fold and
the higher attempt wins each cell the two fill differently.

**The row's shape did not change and neither did the day file's.** A segment
carries the head's own columns and the head's own contract, so there is no
version stamp, no migration and no second schema. A reader opens the same file it
opened before. Authority: Fowler, 2026-09-17.

**A bench dispatch folds its own segment.** `measure.yml` has no `assemble` job,
so the step after its probe runs `idhazh compact --config
backend/var/candidate-config` and the commit stages the day file as it always
did. It is the one state writer with no concurrency group at all, which is why it
gets the segment rather than being left on the shared path. Authority: Carmack,
2026-09-17.

## See also

- [../concepts/telemetry.md](../concepts/telemetry.md) - the instrument as a whole, and the two finer grains this sits beside.
- [benchmarks/the-processor-lottery.md](benchmarks/the-processor-lottery.md) - what the fleet does to a reading, and why this record exists.
- [pipeline-cost.md](pipeline-cost.md) - the instrument log.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #10 (a number carries its hardware) and Guardrail #12 (a growing read declares itself).
