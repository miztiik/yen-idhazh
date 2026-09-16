# Plan 30 - The hardware console has no panel for the machine it ran on

**Created**: 2026-09-16
**Status**: not started. Contract first - no panel is built before its shape is agreed.
**Owner decision needed**: yes, on the panel list in section 3.

## The situation in one paragraph

`state/host-fingerprint/<YYYY>/<MM>/<DD>.csv` has been written since 2026-09-16
and **nothing reads it**. Every column is in
[host-metrics.md](../docs/reference/host-metrics.md); none of it reaches the
hardware console at `/console/machine/`, which today reads
`state/runtime-counters.csv`, the item-health census, the span rollup and the run
timeline. So the project now collects the answer to "which machine produced this
number" and an operator still cannot see it.

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

Each row is a proposal, not a decision. **The owner picks which ship.**

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

Nothing is drawn until this exists:

1. **A reader payload shape**, as a Pydantic contract under
   `backend/idhazh/contracts/`, generating its schema, the way every other
   console payload is built. The frontend reads a generated type, never a CSV
   column index - `series.ts` reading `cells[46]` is the failure mode to avoid.
2. **A stated window.** The page reads a bounded number of days (Guardrail #12),
   named in `config/` rather than in source.
3. **An empty state for every panel.** The fingerprint is behind a flag, so a
   deployment with it off must render a panel that says so rather than a blank
   box (`CLAUDE.md` section 12, point 5).
4. **A colour decision that survives both themes.** P2 assigns colour by machine
   kind; that needs a palette that works light and dark and does not imply an
   ordering between machines.

## 5. Tasks

| id | Task | Blocked on |
| --- | --- | --- |
| T1 | Owner picks from the P1-P5 table | nothing |
| T2 | Susan rules on the shape of each chosen panel, both themes, empty and degraded states | T1 |
| T3 | Write the payload contract and its schema | T2 |
| T4 | Build the panels against the contract | T3 |
| T5 | Browser smoke per `CLAUDE.md` section 12, including the data-absent arm | T4 |

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
