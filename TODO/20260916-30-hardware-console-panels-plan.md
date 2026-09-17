# Plan 30 - The hardware console has no panel for the machine it ran on

**Created**: 2026-09-16
**Status**: shipped 2026-09-17. Three panels landed, two were refused, and each
refusal names what the reader loses.
**Owner decision**: taken. Susan ruled on section 3 on 2026-09-17; the ruling is
recorded as a `## Design rationale` in
[../docs/concepts/console-design.md](../docs/concepts/console-design.md), which
is the page that owns how a console figure is allowed to read on screen.

## What shipped, and what was refused

| id | Proposal | Outcome |
| --- | --- | --- |
| P1 | Deepen "The host under the newest run" | **Shipped, split in two.** The old panel keeps its four server rows and is retitled **What the server did outside the model call**. The machines became a panel of their own, **The machines this run drew**: one card a machine, the normalised name, family/model/stepping, all twelve watched flags as present-or-absent chips, L3 and the bandwidth reading in one sentence with its buffer, how many jobs drew it, and a `<details>` holding the platform's placement and the microcode |
| P2 | Colour "Reading against writing" by machine | **Shipped first, and it is a correction rather than a feature.** The pooled rate was deleted. One group a machine, each with its own read rate, write rate and multiple; one headline, attributed to the machine that read the most tokens |
| P3 | The fleet, over the window | **Shipped, gated at `console.fleet_min_rows` (160).** Under the gate it is a list with a sentence and no bar at all |
| P4 | Bandwidth against decode | **Refused, with a trigger.** See below |
| P5 | A processor detail table | **Refused, five columns bought back.** See below |

**What the reader loses to the P4 refusal.** The only on-screen test of whether
decode is really bandwidth bound, which is the hypothesis the bandwidth probe was
built for - so the probe's reading is a number nothing is plotted against. What
buys it back for now is P1, which prints that reading in words on each machine's
card: the fact is on the page and only the correlation is missing. **It ships
when `console.fleet_min_rows` rows exist and `console.bandwidth_min_kinds` (3)
distinct kinds carry a bandwidth reading.** Two points define a line, so a
scatter of two is a claim.

**What the reader loses to the P5 refusal.** The ability to read a raw column
value off the console. Five of the twenty-seven were bought back inside P1's
card: `vm_size`, `vm_location`, `vm_zone`, `vm_fault_domain` and `microcode` -
the last being the cell `host-metrics.md` calls the one that moves without
anything else moving, and so the only explanation left for a speed change with
no other change. Behind a native `<details>`, closed by default, so the
attention cost is zero. The other twenty-two stay on
[../docs/reference/host-metrics.md](../docs/reference/host-metrics.md), which is
the reference page's job.

**What the whole route loses.** The pooled `Nx` write-cost headline, which was
the most quotable number on the page. It is replaced by the same multiple
attributed to one named machine. That is the price of it being true.

## The measurement that decided the order

Taken 2026-09-17 over `state/runtime-counters.csv` - 380 rows, 95 runs, 19 dates.

- **86 of the 90 runs that name a processor drew more than one kind.** One kind
 on 4 runs, two on 39, three on 43, four on 4.
- Inside one run the read rate between the fastest and the slowest machine runs
 **1.00x to 6.08x, median 2.32x**; 45 of the 86 exceed 2x. Run
 `2026-09-12-34689544296` read at 59.71 tokens a second on one shard's machine
 and 9.83 on another's.
- 24 of the 380 rows carry no processor name at all.

So P2 shipped first: it was the only row that removed a wrong number from a live
page, and that number was wrong on 95.6 percent of runs.

**`console.fleet_min_rows` is a declared estimate, not a measurement**
(`CLAUDE.md` Guardrail #10). The rarest of six machine kinds held 11 of 356
committed counter rows, 3.1 percent - that part is measured - and 5 of those,
the floor `console.min_attempts_for_rate` already sets, needs about 162 rows.
A seventh machine kind lowers every share and raises the bar, so re-derive it
rather than argue with it.

## The situation in one paragraph

`state/host-fingerprint/<YYYY>/<MM>/<DD>.csv` has been written since 2026-09-16
and **nothing read it** until this plan shipped. Every column is in
[host-metrics.md](../docs/reference/host-metrics.md); none of it reached the
hardware console at `/console/machine/`, which read `state/runtime-counters.csv`,
the item-health census, the span rollup and the run timeline. So the project
collected the answer to "which machine produced this number" and an operator
still could not see it.

## Why this is a plan and not a commit

**Chart design is where an operator console goes wrong**, and it goes wrong
quietly: a panel that is added because the data exists rather than because a
question needed answering. Every panel costs a reader's attention whether or not
it earns it, and a panel nobody can act on is worse than a missing one, because
it teaches the reader to skim.

So this follows the repository's own rule: **contract before code**
(`CLAUDE.md` Guardrail #3, section 1a). The shape of each panel - what question
it answers, what it draws, what it must never draw - is agreed here before any
`d3` is written.

**This one is Susan's.** Jony rules what survives on a page; Susan rules whether
what survived is good enough to ship, and she is the only persona with a mandate
to fail a panel for being thin, cold or unloved (`CLAUDE.md` section 14). A
hardware page is exactly where that bites: six processor types and twenty-seven
columns is a page that can very easily become a spreadsheet with a title.

## 1. What the reader of this page is doing

The operator console has one reader: the person who just saw a number move and
wants to know whether the project changed or the machine did.

**Every panel proposed below has to answer that question or it does not ship.**
A panel that is merely interesting about hardware belongs in the benchmark
record, not on a console.

## 2. What already exists, so nothing is duplicated

| Panel on `/console/machine/` today | Reads | Would the fingerprint duplicate it? |
| --- | --- | --- |
| Shards of the newest run | runtime-counters | No - but it names a processor, and that name could become a link |
| Where a shard's clock went | span rollup | No |
| Where the run's time went, item by item | run timeline | No |
| Peak memory against the ceiling | runtime-counters | No |
| Reading against writing | runtime-counters | **Yes, partly.** This is the panel whose numbers the lottery makes uncomparable |
| Prompt cache, context headroom | runtime-counters | No |
| The two clocks, compared | runtime-counters | No |
| The host under the newest run | runtime-counters | **Yes.** This panel already exists and says only `cpu_model` |

**Two findings from that table, and they shape the whole plan.**

First, **"The host under the newest run" is the panel this data belongs in.** It
exists, it is about exactly this subject, and it currently says one string. The
default answer is to deepen it rather than to add a page.

Second, **"Reading against writing" is the panel that is currently misleading.**
It plots rates across runs, and the lottery says rates across runs are not
comparable unless the machine is the same. That is a correctness problem on a
panel that already ships, not a new feature.

## 3. The panels to decide on

Each row was a proposal. The outcome of each is in the table at the top of this
page; what follows is what was proposed, kept so a reader can see what the
ruling answered.

| id | Panel | The question it answers | What it draws | What it must never do |
| --- | --- | --- | --- | --- |
| P1 | **Deepen "The host under the newest run"** | What machine is this, and what can it do? | The model name, family/model/stepping, the watched flags as present-or-absent marks, L3, and the bandwidth reading | Print a codename. The host does not report one |
| P2 | **Colour "Reading against writing" by machine** | Is this run slower than that one, or just on a different machine? | The existing chart, with each mark carrying its `fingerprint` as colour | Invent a colour per run. The point is that two runs on one machine share a colour |
| P3 | **The fleet, over the window** | What are we actually being given? | One bar a machine kind, counted over the window, newest window only | Print a probability. Counts are what happened, not a rate |
| P4 | **Bandwidth against decode** | Is decode really bandwidth bound? | One point a job: `memcpy_gib_s` against that job's decode rate | Draw a fit line through five points |
| P5 | A processor detail table | - | - | **Proposed for rejection.** Twenty-seven columns is the reference page's job, and a console is not a schema browser |

**P1 and P2 are the two that answer the reader's actual question.** P2 may be the
most valuable thing here: it repairs a panel that currently invites a wrong
conclusion.

**P3 and P4 are honest but thin until there is data.** Four machine kinds over
twelve draws is not a distribution anybody should chart yet. Both should wait for
a stated number of rows.

**P5 is here to be refused**, and the refusal should be recorded: what the reader
loses is the ability to read a column value off the console, and what they gain
is a page that is still readable in six months.

## 4. The contract, before any code

Nothing was drawn until this existed, and it landed as the first commit:

1. **A reader payload shape**, as a Pydantic contract under
   `backend/idhazh/contracts/machine_panels.py`, generating
   `schemas/machine-panels.schema.json`. The frontend resolves the twelve flag
   names out of that generated schema rather than typing a copy, so the drift
   gate binds the page - `series.ts` reading `cells[46]` is the failure mode it
   avoids.
2. **A stated window.** The route already read `shardDays(max(console.window_presets))`,
   and the machine record takes the same cover (Guardrail #12). No new window
   knob was needed.
3. **An empty state for every panel.** Ten of them, one per condition, in the
   `## Design rationale` on
   [../docs/concepts/console-design.md](../docs/concepts/console-design.md).
4. **A colour decision that survives both themes.** `--chart-1` to `--chart-7`
   assigned ascending by machine key, `--chart-8` reserved for an unrecorded
   machine, the name in words on every row. **No token was added.**

## 5. Tasks

| id | Task | State |
| --- | --- | --- |
| T1 | Owner picks from the P1-P5 table | done, 2026-09-17 |
| T2 | Susan rules on the shape of each chosen panel, both themes, empty and degraded states | done, 2026-09-17 |
| T3 | Write the payload contract and its schema | done - `backend/idhazh/contracts/machine_panels.py`, `schemas/machine-panels.schema.json` |
| T4 | Build the panels against the contract | done - P2, then P1, then P3 |
| T5 | Browser smoke per `CLAUDE.md` section 12, including the data-absent arm | done - `frontend/tests/console-machine-panels.spec.ts` |

## 6. Not in scope

- **Publishing any of this to a reader.** It is an operator surface. The digest
  does not carry it and the published telemetry projection does not either.
- **A new console tab.** The subject already has a page. A tab per collection is
  how a console rots.
- **Charting the lottery itself.** That belongs to [the processor
  lottery](../docs/reference/benchmarks/the-processor-lottery.md), which is a
  record rather than a dashboard.

Each of those three is a dated decision rather than a law (`CLAUDE.md` section
0a): if a reason to move one appears, it gets priced and handed back.

## See also

- [../docs/reference/host-metrics.md](../docs/reference/host-metrics.md) - every column this plan would draw.
- [../docs/reference/benchmarks/the-processor-lottery.md](../docs/reference/benchmarks/the-processor-lottery.md) - why panel P2 is a correction rather than a feature.
- [../docs/concepts/design-system.md](../docs/concepts/design-system.md) - the sufficiency checks a panel has to pass.
