# Execution order across the five open plans

**Last Updated**: 2026-09-12

**What this is.** One schedule over the five plan-docs that are open at once. Each of them proves its own rows do not collide; **nothing proved they do not collide with each other**, and nothing said what an orchestrator may dispatch on any given morning. This document is that answer and nothing else.

**What this is not.** It decides no design, moves no decision, and owns no row. Every row still belongs to its own plan and is executed from there per [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md). Where this document and a plan disagree about a row's dependencies or its files, **the plan wins and the row that noticed fixes this page in the same pull request**.

**Why it lives in `TODO/` and not in `docs/` or `AGENTS.md`.** It is a schedule over five working documents and it is deleted the day the last of them closes, so it is working material by `CLAUDE.md` section 3's own definition. `docs/` is the memory and a page there that named five `TODO/` files would outlive every one of them. `AGENTS.md` is a derived cache and is explicitly not authoritative, so a schedule there would be the source of truth for nothing. The research record is a frozen reading of one design conversation about classification, and four of these five plans are not classification. **A worker opens the plan it was dispatched from, and every one of the five links to this page from its own "See also"** - which is the only test that matters.

---

## 0. The five plans, and the numbers this page is derived from

Derived 2026-09-11 in a worktree at `origin/main`, by parsing each row's own `Files touched` bullet and each plan's own Status Reckoner. **It is derived rather than authoritative**: a worker checks a pair by diffing the two rows' lists, never by trusting a table here.

| Plan | Rows | Live rows | Groups | Parallel N it declares |
| --- | --- | --- | --- | --- |
| [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md) | 8 | 4 | 8 | 1 |
| [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) | 28 | 28 | 16 | 2 |
| [`20260910-24-day-sharded-ledgers-plan.md`](20260910-24-day-sharded-ledgers-plan.md) | 8 | 8 | 6 | 2 |
| [`20260910-25-placement-plan.md`](20260910-25-placement-plan.md) | 15 | 14 | 9 | 2 |
| [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md) | 4 | 4 | 2 | 2 |

**58 live rows.** A row is live unless its own plan marks it DONE, RETIRED or DEFERRED - so plan 11's three merged rows and its deferred row #3c are out, and plan 25's retired row #9b is out.

**The within-plan group discipline still holds, re-proved after this page was written.** Every group of every plan was re-checked by intersecting the rows' own file lists: **zero collisions in 41 groups across the five plans.**

---

## 1. Why the opening wave was seven

**The dispatch list is not here, and no list of ready rows is.** [`STATUS.md`](STATUS.md) is generated from the Reckoners on every merge and cannot go stale; run `python backend/utilities/plan_status.py --ready` for the same answer plus drift. What is worth reading on this page is the REASONING a generator cannot produce: **which rows write the same file**, why a wave is the size it is, and what it costs. [`20260911-handover.md`](20260911-handover.md) is the entry point for an agent arriving with no context.

**Nineteen rows had every dependency satisfied when this was derived on 2026-09-11, and the recommended opening wave of seven has since landed in full** - plan 23 row `#P1` as pull request #608, plan 24 row `#1` as #609, plan 11 row `#4` as #612, plan 26 row `#2` as #613, plan 26 row `#3` as #614, plan 24 row `#2` as #615 and plan 25 row `#11` as #616. **Not one of the seven updated its own Reckoner line**, which is why [`20260911-handover.md`](20260911-handover.md) makes that update part of the row rather than a step after the merge; #610 flipped the first two and #617 flipped the other five. **The table of ready rows that stood here has been deleted rather than corrected**, because a list of what can start is re-derivable every time it is asked and a page cannot keep it true. The counts below are the counts as derived, and they are kept because the arithmetic about the wave rests on them.

**Nineteen were unblocked; seven could run at once.** The other twelve were blocked by a *file*, not by a dependency, and section 3 is where that is proved. **Exactly one of the nineteen collided with nothing else in the set: plan 26 row #2.**

### The opening wave, recommended

**Seven rows, and no other ready row could join them.** Verified by intersecting the seven file lists pairwise, and then by testing every one of the other twelve against the set - each is refused by a named file.

| Row | Why it is in the opening wave |
| --- | --- |
| 23 #P1 | **The longest pole.** 18 of the 58 live rows wait on it, and it is three prose files. **Landed as #608; the wave is five rows now** |
| 24 #1 | The second pole at 17, and it creates `backend/idhazh/day_partition.py`, which four rows of plan 23 wait on. **Landed as #609; the wave is five rows now** |
| 11 #4 | The third pole at 15. It heads plan 11's only remaining chain, and that chain gates plan 23 row #7b, which gates eleven more rows. **Landed as #612** |
| 24 #2 | Five files. Plan 24 row #8 waits on it and nothing else does. **Landed as #615** |
| 25 #11 | Thirteen files, all console. Both of plan 25's tab rows wait on it. **Landed as #616** |
| 26 #2 | Collides with nothing anywhere in the set. **Landed as #613** |
| 26 #3 | Four files, all prose and one test. **Landed as #614** |

**The wave ran serially rather than seven at once, and that was not a compromise.** An orchestrator dispatches a worker and waits for its report, so the seven were dispatched one at a time in pole order and each pull request was merged before the next worker cut its worktree. **Every file collision the wave was composed to avoid therefore could not arise**, and none did: seven pull requests, zero conflicts, every one green on its first push. The disjointness proof above is what would have mattered had the dispatches overlapped, and it stays here because the next wave may.

**What this wave costs, named rather than hidden.** It contains **no reader-visible change**. Plan 25 row #5 is the one ready row a reader could see (section 5) and it cannot be in this wave: it and plan 24 row #1 both write `docs/architecture/publishing/layout.md`. **Running row #5 instead of plan 24 row #1 buys a visible change and delays the second-heaviest pole in the project by one wave.** The recommendation is to take the pole and run row #5 in the second wave, because nothing plan 24 row #1 blocks is reachable before the third wave and a day spent on it there is a day the schedule does not get back.

**Plan 23 row #1a is deliberately not in it, and it is the reason the wave is seven and not more.** It writes 26 files, and it is the refusing row for nine of the twelve rows that cannot join: `CLAUDE.md`, `backend/idhazh/cli.py`, `backend/tests/test_contracts.py`, `backend/idhazh/assemble.py`, `backend/idhazh/contracts/app_config.py` and `docs/architecture/contracts/schemas.md` each put it against a different sibling. **It is the widest ready row and it pairs with almost nothing, so it wants a wave of its own** - and the second wave is where it fits, beside plan 25 row #5.

---

## 2. The critical path, and the longest pole

**Nine waves of dependency, and one chain that is all nine.**

| Wave | Row | What it is |
| --- | --- | --- |
| 1 | 23 #P1 | The property `CLAUDE.md` section 0a names, restated |
| 2 | 23 #2 | Every label vocabulary becomes config |
| 3 | 23 #3 | Lens and event ids become slugs |
| 4 | 23 #6 | The desk is a new field |
| 5 | 23 #7b | The two calls become a DAG |
| 6 | 23 #8 | Call 1 labels: desk, lenses, article kind |
| 7 | 23 #14 | The classification ledger, and the day file the console reads |
| 8 | 25 #12 | `Judgement` - what the model made of each article |
| 9 | 23 #15 | The console tab, at `/console/judgement/` |

**The last two steps cross a plan boundary in both directions**, which is why no single plan could have found this chain. Plan 25 row #12 waits on plan 23 row #14 for its figures; plan 23 row #15 then waits on plan 25 row #12 for the producer and the payload. **Two plans, four edges between them, and the longest chain in the project runs through all four.**

### The longest pole

**Ranked by how many live rows wait on each, directly or through another row.**

| Row | Wave | Live rows it blocks | What it is |
| --- | --- | --- | --- |
| 23 #P1 | 1 | 18 | The property section 0a names, restated. **Landed as #608** |
| 24 #1 | 1 | 17 | One answer to what a day file is. **Landed as #609** |
| 23 #2 | 2 | 17 | Every label vocabulary becomes config |
| 23 #3 | 3 | 16 | Lens and event ids become slugs |
| 11 #4 | 1 | 15 | The reachability gate and the downgrade ladder |
| 11 #5 | 2 | 14 | One chart, drawn end to end |
| 23 #P4 | 1 | 13 | What one more call costs on the runner |
| 23 #7a | 1 | 13 | The classification code gets its own package. **Landed as #629** |
| 11 #6 | 3 | 13 | The small model, its job and its cache go |

**The longest pole is plan 23 row #P1, and it is three prose files.** It blocked 18 of the 58 live rows and it writes `CLAUDE.md`, `AGENTS.md` and `docs/agents/guardrails.md` - no code, no contract, no schema. **It was the cheapest row on this page and the most expensive one to leave alone.** Second is plan 24 row #1 at 17, and third is plan 23 row #2 at 17, which waits only on #P1. **The first two of those landed on 2026-09-11, as #608 and #609**, which puts plan 23 row #2 and the four plan 23 rows waiting on `day_partition.py` at the head of the queue.

**Two of the top five belong to plan 11, which is four live rows.** `11 #4` blocks 15 rows and `11 #5` blocks 14, because plan 11 row 6 is what plan 23 row #7b waits on and eleven rows wait on that. **Plan 11 is the smallest open plan and the second-heaviest constraint in the project.**

**One number on this page moved on 2026-09-12, and it moved the wrong way.** Plan 11 gained a row - **#5b, "Call 1 and call 2 run in the pipeline"** - sitting between `11 #5` and `11 #6`, and `11 #6` now waits on it. The worker dispatched on `11 #6` found that no stage dispatches call 1 or call 2, so the row's own precondition was unmet and the flag its scope opens by flipping was never built. So plan 11 is **five live rows, not four**, and the chain that gates plan 23 row #7b is **one wave longer**: every row that waited on `11 #6` now waits on `11 #5b` as well, and `11 #5b` waits on `11 #3b`, which was outside the chain until today. The derived counts above are left as derived, per this page's own rule; what is corrected is the shape of the chain, which is what a schedule is for. Nothing else on this page moves - no file list changed, so section 3's collision arithmetic stands.

---

## 3. Where two plans write one file

**Every pair of rows in different plans was intersected.** 84 files are written by rows in more than one plan, and 391 cross-plan row pairs share at least one of them. The count is not the useful part - the shape is.

**A glob hides a collision rather than avoiding one, and this page has the measurement.** Plan 11's rows named `backend/tests/**`, `schemas/*.schema.json`, `docs/**` and five more. Replacing those eight globs with the files the rows actually write **raised** the cross-plan pair count from 346 to 391 and the shared-file count from 79 to 84. The collisions were always there; a glob is simply a file list nobody can diff. Measured 2026-09-11, before and after that one edit.

### The hot files

| Written by | Plans | File | What it means for a wave |
| --- | --- | --- | --- |
| 19 rows | 11, 23, 25 | `backend/tests/test_contracts.py` | Every row that adds a contract field |
| 18 rows | 11, 23, 24, 25 | `backend/idhazh/cli.py` | The single busiest module in the project. Assume any two rows collide here until their lists say otherwise |
| 15 rows | 11, 23, 25 | `backend/idhazh/contracts/app_config.py` | Every row that adds a knob, and it regenerates a schema |
| 15 rows | 11, 23, 25 | `config/idhazh.json` | The same rows |
| 14 rows | 11, 23, 25 | `schemas/app-config.schema.json` | The drift gate fails on one byte, so this is a hard collision and never a soft one |
| 13 rows | 23, 24, 25 | `backend/tests/test_marks.py` | Every row that adds a backend test module |
| 12 rows | 23, 24, 25 | `docs/concepts/growing-reads.md` | Every row that reads a collection a run appends to |
| 8 rows | 23, 24, 25 | `backend/tests/test_pipeline.py` | - |
| 7 rows | 11, 23 | `backend/idhazh/visual_planner.py` and `backend/tests/test_visual_planner.py` | **Resolved inside plan 23 on 2026-09-12 by its row #7a, which landed as #629**, and still not resolved between the two plans |
| 7 rows | 23, 24 | `backend/idhazh/retention.py` and `backend/tests/test_retention.py` | The collision plan 23 section 0.1 already names |
| 7 rows | 23, 24 | `docs/architecture/contracts/schemas.md` | - |
| 7 rows | 23, 24, 25 | `docs/architecture/publishing/layout.md` | - |
| 7 rows | 23, 25 | `backend/idhazh/rank.py` and `config/taxonomy.json` | - |
| 7 rows | 23, 24, 25 | `backend/idhazh/ledger.py` and `backend/tests/test_ledger.py` | - |

**`schemas/app-config.schema.json` is the one to watch.** A schema is generated, the drift gate compares bytes, and thirteen rows across three plans regenerate this one. Two such rows in one wave do not merge - they produce two diffs of one file and the second rebases onto a schema that moved.

### What a wave actually costs

**The dependency graph is nine waves. Dispatching it without breaking a file collision takes twenty-six.** That is the number this page exists to produce, and no plan could have found it.

| Wave | Rows | Sub-waves needed | The clique that forces it |
| --- | --- | --- | --- |
| 1 | 19 | 5 | `backend/idhazh/cli.py`, `backend/tests/test_marks.py`, `docs/reference/measurements.md`, and plan 23 row #1a against nine siblings |
| 2 | 9 | 3 | `config/idhazh.json` and `schemas/app-config.schema.json` across 23 #1b, 23 #21, 25 #2 |
| 3 | 9 | 4 | **Plan 24 rows #5, #6, #7 and #8 all write `retention.py`, `ledger.py` and `cli.py`.** Four rows, every pair collides, so four sub-waves and no arrangement does better |
| 4 | 7 | 4 | 23 #6 collides with four of the other six |
| 5 | 2 | 2 | `backend/idhazh/cli.py` |
| 6 | 1 | 1 | - |
| 7 | 2 | 1 | 23 #12 and 23 #14 are already a legal pair |
| 8 | 8 | 5 | `config/idhazh.json`, `app_config.py`, `test_classify.py`, `classify/labels.py` |
| 9 | 1 | 1 | - |

**Wave 3's four is a floor, not an estimate.** Plan 24's rows #5 to #8 are four rows where every pair shares a file, so no ordering runs two of them together. Their own plan already says this - it is why they are four singletons in four groups. **The other rows are an upper bound taken by one assignment**; a different arrangement may do better and may not do worse than the cliques above.

### The pairs that look safe and are not

These are the ones a person composing a wave by reading two plan titles would get wrong.

| Pair | Shared file | Why it is not obvious |
| --- | --- | --- |
| 23 #P1 x 26 #1 | `CLAUDE.md` | A classification rule restatement and a prerender measurement. Nothing connects them but the contract file |
| 23 #P4 x 26 #3 | `backend/tests/test_workflows.py` | A runner measurement and a prose correction |
| 11 #4 x 25 #1 | `docs/architecture/publishing/visuals.md` | A downgrade ladder and three docstrings |
| 23 #1a x 25 #11 | `backend/tests/test_console_payloads_producer.py` | A fingerprint removal and a console strip |
| 23 #5 x 25 #1 | `docs/architecture/publishing/visuals.md` | An item-id widening and three docstrings |
| 24 #1 x 25 #5 | `docs/architecture/publishing/layout.md` | A day-partition module and a time rail |
| 24 #6 x 25 #13 | `docs/architecture/sources/health.md` | A ledger migration and a console tab |
| 25 #6 x 26 #2 and 26 #4 | `docs/architecture/publishing/frontend.md` | Plan 26 already splits its own two writers across groups; plan 25 row #6 is a third writer in a different plan |

---

## 4. The cross-plan dependencies, verified against the plans

**All three are already written into the Reckoners that own them.** This page adds no edge; it names them in one place.

| Edge | Where it is declared | Verified |
| --- | --- | --- |
| Plan 23 row #7b waits on plan 11 row 6 | Plan 23 section 1 Depends-on, and its section 0.4 | Yes. **Naming row 6 is enough**: plan 11 row 6 waits on row 5, and row 5 on row 4, so the whole chain is implied by one edge |
| **Four** rows of plan 23 wait on plan 24 row #1 | Plan 23 section 0.1, and the Depends-on of rows #14, #16, #17 and #21 | Yes, and the count is four rather than five. Plan 23 creates four new day-sharded trees - `classifications`, `vertical-proposals`, `lens-weights` and `counterfactual-scores`. **Plan 25 creates none.** Its row #9a adds columns to plan 23 row #21's ledger and its row #14 writes the day-metrics record that already exists |
| Plan 25 row #12 waits on plan 23 row #14 | Plan 25 section 1, and its section 0.4 | Yes. And the return edge - plan 23 row #15 waits on plan 25 row #12 - is declared in plan 23 section 1 |

**A fourth edge is declared and is easy to miss.** Plan 23 rows #14, #16, #17 and #21 each add a prune to `backend/idhazh/retention.py`, which plan 24 rows #5 to #8 all rewrite. Neither side blocks the other; whichever lands second re-reads the file. Plan 23 section 0.1 says so.

**A fifth is outside these five plans.** Plan 24 row #1 renamed `docs/concepts/month-partitions.md` to [`../docs/concepts/partitions.md`](../docs/concepts/partitions.md), and [`20260907-growing-reads-window-plan.md`](20260907-growing-reads-window-plan.md) carried **four of the fourteen links** to it. That plan is open work and is not scheduled here. Plan 24 row #1 decision 2a names it. **The count said seven of seventeen until 2026-09-11**, which was counting mentions rather than links; row #1 re-measured both and repointed every link in the same commit.

---

## 5. The shortest path to something a reader can see - answered, and closed

**All three rows this section recommended have landed**, so it no longer recommends anything: plan 25 row #5 as #625, plan 11 row #4 as #612 and row #5 as #621. What it was for is recorded here in one line, because the judgement is reusable and the list is not.

**A wave of infrastructure rows can contain no visible change at all, and nobody notices until a reader asks what moved.** The opening wave of seven was exactly that. The one ready row a reader could see - plan 25 row #5, which retires the time rail and puts each story's time under its heading - was held out of it by a single shared file, `docs/architecture/publishing/layout.md`, and ran in the second wave where it was free. **When a wave is being composed, ask which of its rows a reader would be able to point at.** If the answer is none, that is a choice and it should be made deliberately rather than discovered.

---

## 6. The documentation set

**Every `docs/` page these five plans create.** Each plan routes its own pages and states whether the page exists; this table is the union, checked for two plans creating one page.

| Page | Created by | Tier | Status |
| --- | --- | --- | --- |
| `docs/concepts/taxonomy.md` | 23 #2 | concepts | New. Extended by 23 #3, #6, #19 |
| `docs/concepts/classification.md` | 23 #2 | concepts | New. Extended by 23 #8, #9, #10, #11, #13 |
| `docs/concepts/placement.md` | **23 #20 or 25 #2, whichever lands first** | concepts | New. Both plans say so, both name the other, and both extend it. **Resolved** |
| `docs/how-to/measure-a-classifier.md` | 23 #P2 | how-to | New. Extended by 23 #P3, #18 |
| `docs/how-to/promote-a-vertical.md` | 23 #16 | how-to | New |
| `docs/reference/benchmarks/` | **23 #P5 and 26 #1** | reference | **Created 2026-09-11 by 24 #1**, which wrote the day-window record. Two different records still to come. **See below** |
| `docs/concepts/partitions.md` | 24 #1 | concepts | **Renamed** from `month-partitions.md`, not created |
| `corpus/reference-dataset-1/README.md` | 23 #P2 | not `docs/` | New datasheet. Extended by 23 #P3 |

**One defect, and it is a sentence rather than a file.** `docs/reference/benchmarks/` **was created on 2026-09-11 by plan 24 row #1**, which put the day-window reading in it - so **three** rows now claim to write the first record there, and plan 23 row #P5 and plan 26 row #1 both carry a false sentence rather than only the later of the two. The records are different and none blocks another. The fix is one word in each of the two remaining rows: it writes *a* record, and the row that created the directory is plan 24 row #1. Found 2026-09-11; neither plan named it.

**No other page is created twice, and no page is created under two names.** Both such defects were found and fixed on 2026-09-11 inside the plans that carried them: plan 23 row #20 wrote `docs/concepts/the-order-of-the-day.md` for the question `docs/concepts/placement.md` answers, and two how-to pages for a weekly tuning loop that no longer exists - `tune-the-lens-weights.md` and `tune-the-placement-weights.md` - are created by nothing. Re-checked here and still clean.

**Plans 11 and 26 create no page.** Plan 11 names `docs/**` rather than a page, which section 7 below is about. Plan 26 writes one benchmark record and corrects four sentences in three existing pages.

---

## 7. What this page does not do

It schedules nothing outside these five plans. Measured 2026-09-11 with `python backend/utilities/plan_status.py`: **eighteen plan-docs under `TODO/` carry a live row, and this page covers five of them.** [`20260823-known-defects-plan.md`](20260823-known-defects-plan.md), [`20260827-summarizer-fine-tuning-plan.md`](20260827-summarizer-fine-tuning-plan.md) and [`20260907-growing-reads-window-plan.md`](20260907-growing-reads-window-plan.md) are open and are not on it; the one edge that reaches one of them is in section 4. Plans 12 to 22 are a chain behind plan 11 and are not on it either. Unscheduled is not closed.

It changes no decision, no oracle, no measurement and no vocabulary in any plan. It moves no row between groups. Where it disagrees with a plan, the plan wins.

**It does not stay true on its own, so refreshing it is part of the row that invalidated it.** Every number here is derived from the plans' Reckoners and file lists on 2026-09-11. A row that widens its file list invalidates section 3; a row that lands invalidates sections 0, 1 and 2. **The row that invalidated a section corrects that section in its own pull request** - saying in a pull request that this page is stale is not updating it, and the next agent reads the page, not the pull request. [`20260911-handover.md`](20260911-handover.md) lists which section goes stale on what.

---

## See also

- [`20260911-handover.md`](20260911-handover.md) - **start here with no context.** The queue reader, the reading order, the standing traps, and which section of this page a row has to refresh.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row, and where the no-two-rows-one-file rule comes from.
- [`../docs/how-to/author-a-plan.md`](../docs/how-to/author-a-plan.md) - the shape every row in the five plans is written in.
- [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md) - one model, two calls. Four live rows, and two of them are in the top five poles.
- [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) - what an article is about. 28 rows, and seven of the nine critical-path waves.
- [`20260910-24-day-sharded-ledgers-plan.md`](20260910-24-day-sharded-ledgers-plan.md) - five ledgers file by day. Its row #1 is a prerequisite of four rows in plan 23.
- [`20260910-25-placement-plan.md`](20260910-25-placement-plan.md) - where a story goes. Four edges run between it and plan 23.
- [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md) - the guard retires, the prerendering does not. The cheapest plan on this page.
