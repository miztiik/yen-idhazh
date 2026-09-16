# What the pipeline records about the machine it ran on

**Last Updated**: 2026-09-16

Every column of the host fingerprint, what it means, and what it is for. One row
a job, written once at job start.

Read this when a number surprises you and you want to know which machine
produced it. Why the record exists at all, and what the fleet does to a reading,
is [the processor lottery](benchmarks/the-processor-lottery.md).

## Where it lives

| | |
| --- | --- |
| Contract | [`backend/idhazh/contracts/host_fingerprint.py`](../../backend/idhazh/contracts/host_fingerprint.py) |
| Generated schema | [`schemas/host-fingerprint-row.schema.json`](../../schemas/host-fingerprint-row.schema.json) |
| Store | `state/host-fingerprint/<YYYY>/<MM>/<DD>.csv` |
| Producer | `idhazh fingerprint`, through `backend/idhazh/telemetry/silicon.py` |
| Key | `date`, `run_id`, `job`, `shard` - one row a job |
| Switch | `observability.host_fingerprint` |
| Committed | **from 2026-09-16.** The work job's commit step stages `state/host-fingerprint`; every row taken before that date was deleted with its runner |
| Published to a reader | **no.** Operator surface only |

**It is finer grained than `state/runtime-counters.csv` and it is partitioned
differently on purpose.** The counters file is one flat file the console reads
whole. This is a day tree, because it only earns its keep when somebody counts
across many days, and a day tree is the shape a bounded window can read
(Guardrail #12).

**The two tables join on the key, and no column is duplicated to make that
work.** Both carry `date`, `run_id`, `job`, `shard`, and a job runs on one
machine, so the key is the join. There is deliberately no `host_fingerprint`
column on the counters row: it would be a second copy of a value this table
already holds, and a second copy is a thing that can disagree.

## Identity

| Column | Type | What it is |
| --- | --- | --- |
| `version` | date stamp | The schema generation this row was written under |
| `date` | `YYYY-MM-DD` | The run's date |
| `run_id` | run id | The run |
| `job` | **enum**: `work`, `visuals` | Which workflow job drew this machine |
| `shard` | int, 0+ | The shard inside that job. A single-shard job writes 0 |
| `fingerprint` | 16 hex characters | A digest over the cells that cannot change inside a job |

**`fingerprint` is the column that makes the collection countable.** It digests
vendor, family, model, stepping, model name, cores, threads, L3 and flags - and
nothing else. Bandwidth, clock and uptime move between two jobs on identical
machines, so including them would give every job its own value and the column
would count nothing. Two draws of one kind of machine carry one id, which is what
lets a query ask "how often do we get this machine" without matching model-name
strings by hand.

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
| `l3_cache_bytes` | int? | L3 as the kernel reports it | Ranges 32 MiB to 480 MiB across the fleet. **Read it beside `memcpy_probe_mib`** |

**`flags` holds only the flags in `WATCHED_FLAGS`**, which is a fixed tuple in
the contract: the AMX, AVX-512, VNNI, FMA and SSE entries an inference runtime
dispatches on. A raw `flags` line is two hundred words and most of it says
nothing about throughput. Adding one to the watched set is a code change and not
a schema change, which is the trade: the column stays a fixed width, and the
vocabulary lives in the contract rather than in the schema.

**An empty `flags` is a reading, not a gap.** The machine we draw most, the EPYC
7763, reports none of the watched AVX-512 entries at all.

## What the machine was doing when we asked

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `mhz_max` | float? | `CPU max MHz` | The ceiling the host publishes, where it publishes one |
| `mhz_at_probe` | float? | Mean `cpu MHz` across processors at probe time | **Not a reading under load.** The probe runs before the model server, so this says what the machine idles at |
| `boot_seconds` | float? | Uptime when the probe ran | A small number is a freshly started machine; a large one was pooled and handed to us |
| `memcpy_gib_s` | float? | Large-block copy rate, bytes read plus written | **Decode is bandwidth bound and this is the only bandwidth reading anywhere** |
| `memcpy_probe_mib` | int? | The buffer each side of the copy used | Says whether `memcpy_gib_s` measured memory or cache |

**`memcpy_probe_mib` is why `memcpy_gib_s` can be trusted.** A buffer smaller
than `l3_cache_bytes` never leaves cache, and reads several times higher than
memory. The two columns sit side by side so nobody can read one for the other,
and `observability.host_fingerprint_bandwidth_mib` sets the buffer - **zero
switches the probe off and leaves the rate empty**, which is different from a
rate of zero.

The default buffer beats the largest L3 this project has drawn, 480 MiB. Raise it
when a drawn machine reports an L3 at or above the default.

## Where the platform put us

| Column | Type | What it is |
| --- | --- | --- |
| `vm_size` | string? | The platform's own name for this machine size |
| `vm_location` | string? | The region |
| `vm_zone` | string? | The availability zone, where one is published |
| `vm_fault_domain` | string? | The fault domain, which separates one rack from another |
| `runner_name` | string? | The runner label the platform gave the job |
| `measured_at` | timestamp | When the probe ran |

These four come from the host metadata service on a link-local address. **They
are the placement decision in the platform's vocabulary rather than ours**, which
is the only way to ask whether "a lottery" is really "which pools we draw from".
A machine that does not answer records nothing, which is every developer machine.

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
guard was correct and blind at the same time. A second guard now reads
`telemetry/silicon.py` the same way. **Scoping a drift guard to a file rather
than to a question is what let a second writer through**, and the two guards are
kept as two rather than merged, because each names the source it protects in the
message it fails with.

**A repeated row now settles, and it could not have before.** `ledger.keyed_paths`
is the registry the post-merge pass walks, and this ledger was not in it - which
cost nothing while nothing was committed and would have cost a double-counted
machine the moment something was. A job runs on one machine, so two rows under
one `(date, run_id, job, shard)` are one machine written down twice, and the
fleet distribution is the one question this record exists to answer. The first
row wins; there is nothing to choose between two attempts that read the same
host. Authority: Fowler, 2026-09-16.

## See also

- [../concepts/telemetry.md](../concepts/telemetry.md) - the instrument as a whole, and the two finer grains this sits beside.
- [benchmarks/the-processor-lottery.md](benchmarks/the-processor-lottery.md) - what the fleet does to a reading, and why this record exists.
- [measurements.md](measurements.md) - the instrument log.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #10 (a number carries its hardware) and Guardrail #12 (a growing read declares itself).
