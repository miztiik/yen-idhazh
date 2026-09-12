# 25 - Where a story goes, decided by arithmetic an editor set

**Last Updated**: 2026-09-11
**Level**: 5 (the ranker, the reading order and a published surface)

**Chain**: previous [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md), which named this work in its section 26 and left it. Plan 23 decides what a story **is**; this plan decides where it **goes**.

Execute per [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md): the orchestrator dispatches one worktree-isolated worker per row; workers consult personas on ambiguity; AUTO-merge on green gates; **parallel N = 2**; honour the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Nothing decides the reading order on purpose. `rank_score` decides which stories enter the day and which five lead it, and then the browser throws its order away and re-sorts by time. The backend publishes a desk-blocked order no surface draws. So a story's position is the residue of two systems disagreeing, and the arithmetic that could express an editorial intent is spent on admission only. This plan gives the ranker the stream, puts a frame around it that a person sets, and deletes the ordering work nobody reads |
| Hard scope - in | The three docstrings that defend a retired requirement; one order over the whole day; a desk cap and a feed cap over the head; the score's terms and their order; carriage as a tie-break; the time rail retired and the timestamp placed; the topic pills ordered by what is running; a desk floor and a desk ceiling; cross-filing to a second desk; **the placement terms on plan 23's counterfactual ledger**; the `assemble` consolidation; **the console strip taking five tabs**; **the `Judgement` tab**; **the `Voices` tab and the feed half moved onto it**; **the per-feed reliability factor drawn for the first time**; **a target distribution over the published day and the divergence from it** |
| Hard scope - out | **The read desk.** Deciding a story's subject by reading it is plan 23 row #6 and is not deferred by anything here - this plan works on whatever field names the desk. **The five month-sharded ledgers**, which are plan 24. **The visual planner's call structure**, which is plan 11. **The weights loop itself**, which is plan 23 row #17 - this plan supplies the evidence it reads and adapts nothing (section 11). **Personalisation of any kind**: there is one published order and every reader gets it. **Computing a classification**: every figure the `Judgement` tab draws is produced by plan 23, and this plan draws them and computes none. **Feed scoring**: `ledger.reliability` is read and never modified |
| ESCALATE triggers | 1. **Day-over-day desk churn above 1 item in 10** that a weight change rather than supply accounts for. A reader cannot tell "the world changed" from "our weights changed", and past that rate they stop trying. 2. **Any single desk or lens above roughly a third of the day when supply does not put it there.** 3. A row proposes to **rebuild the day whole** - the arithmetic that refuses it is in section 0.3 and a row may not re-open it without new measurement. 4. Any workflow in this plan gains a push to `main`. 5. A removal row proposes to leave a test, a config key, a schema field or a doc paragraph behind. 6. **A row of this plan proposes a weights loop of its own.** Plan 23 row #17 is the loop, it runs every run, and row #9b here was retired for proposing a second one on a second cadence (section 11). 7. A console row proposes a **sixth tab**, a **second window control**, or a **mass fetch** over a growing collection. 8. The divergence of row #14 is **wired into the ranker** rather than reported - it is a quality number about the page, and a target a score optimises against stops being a measurement of it |
| Chosen strategy | Delete the false justification first, then build the frame, then give the score the stream inside it, then the desk rules, then the loop that moves a weight, then the consolidation that removes the dead work. Every ordering change lands in the backend and is published; the frontend stops sorting in the last row rather than the first |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

**The governing line, and it is what keeps a derived number out of a committed file.** **A knob a person owns is never written to `config/` by a run; a fact about the world is derived inside the run from a bounded window and thrown away.** `ledger.reliability` is the model to copy: it reads the trailing `collect.reliability_window_days` of feed health, reduces each feed to a factor clamped between `collect.reliability_floor` and 1.0, and writes nothing - the number lives for the length of one run. A feed's recent record is a fact about the world. `repetition_weight` is a knob a person owns, and what a loop may learn beside it is a **multiplier in `state/`**, never an edit to the committed weight.

**An earlier form of this line read "a knob a person owns is adapted by a pull request", and the owner overturned it on 2026-09-11**: of the sibling loop in plan 23 row #17, *"It should work automatically without human. Why weekly - this scoring should be every run."* What survives the ruling is the half that was load-bearing - a run never writes `config/` - and what went with it is the weekly pull request. Plan 23 row #17 carries the shape that replaced it: `config/` holds the human-set weight, the floor and the ceiling; `state/` holds the learned multiplier; the effective weight is the product. **A row here that blurs the two has broken this plan's one rule; a row that proposes a second loop has hit ESCALATE trigger 6.**

### 0.1 Standing rules, and they bind every row

**Deliver the intent, not the letter.** A structural fix matters more than a small diff. Where a row cannot be done correctly inside its stated file list, **expand the scope and say so in the pull request** - do not ship a band-aid to stay inside a list somebody wrote before the code was read. `CLAUDE.md` Rule #5 is the authority; a row's file list reads like a fence and is meant to read like a start.

**No prisoners.** Every removed feature takes its code, its tests, its fixtures, its config keys, its schema fields, its docs and its `state/` writers with it, **in the same commit**. Git is the backup. A row that removes something and leaves a dead test, an orphan config key or a doc paragraph describing the removed thing has not finished, and its acceptance gate says so.

**Verify every fact in your row against the tree before you act on it.** This plan was written on 2026-09-11 against a tree that moves several times an hour. A count, a line number, a percentage or an "exists today" answer in any row below is a reading of that morning, and three of the figures this plan inherited from its own brief had already moved by the time they were re-derived. Re-run the grep. Where the tree disagrees, **the tree wins and the row is corrected in the same pull request**, with a line saying what it was corrected from.

**One order, and the backend owns it.** Every ordering decision in this plan is taken at assemble time and published. Nothing re-orders in the browser. That is not a style preference: a re-order at read time makes a shared link show the recipient a different page from the one the sender saw, and `frontend.md` already refuses a reader-facing sort control for exactly that reason. The frontend's current re-sort is the thing row #10 removes, not a precedent.

**A frame is a standing editorial decision expressed as arithmetic, and it is checked by a test.** Nobody reads the digest before it publishes and it publishes five times a day. So an editor's judgement can only reach a reader as a rule that runs without one: how much of the head one desk may hold, how much one feed may hold, what a desk may not fall below. Every such rule in this plan lives in `config/`, has a sane default, and has a test that fails when the rule is broken.

**A human read can refuse a rank change; only a measurement can authorise one.** Refusing on judgement is safe, because the digest we already publish is the fallback and the cost of a refusal is one unchanged day. Authorising on judgement is not, because a subsidised theme reorders every future day and nothing on the page says why. Every row that raises a weight names the measurement; every row that lowers one may cite a read.

**Every oracle is driven from a fixture, never from the committed archive** (`CLAUDE.md` Rule #12 and section 13). A per-item rule is proved on `backend/var/canary/` or on `tests/fixtures/`, both fixed in size and both able to carry a case the archive has never produced - `time_source: unknown` has never once happened in 8,550 committed items and row #5 has to render it. A question genuinely about the whole tree is asked once, on the total, by `idhazh validate-days`, and not by pytest.

**Additive contract fields are stamped in the commit that adds them.** Every row that adds a field to a persisted model names its `version` date-stamp and its `changelog` entry in its own acceptance gate, per `CLAUDE.md` section 11.

**Every chart carries a heading and one plain sentence saying what it means and what good looks like** - more is better, or less is better. **A chart that needs more than a sentence has failed**, and the row replaces the chart rather than adding a paragraph. Every console row here fetches by window, fetches nothing before it is needed except the first panel, walks no growing collection, and **reuses the shared window control** rather than adding a second one. Those are the console's own standing rules and they are restated here so a worker reading one row does not have to find them ([`../docs/concepts/console-design.md`](../docs/concepts/console-design.md), [`../docs/architecture/publishing/console.md`](../docs/architecture/publishing/console.md)).

**Prerender is legacy in one half and a live decision in the other, and no row here adds a claim to either.** Six routes are prerendered - `/`, `/archive/`, `/evals/` and the three console routes - and the two dated reading routes are not. **No row in this plan asserts that prerendered output is byte-identical, and no row removes prerendering.** It is owned since 2026-09-11 by [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md), which rules that the six routes stay and that `frontend/prerender-guard.js` goes; before that it was named in section 18 as a gap nobody owned. **The console rows below inherit the ruling and prerender nothing new.**

### 0.1a The gate sets, written out once so a row can name one

Every row's acceptance gate names one or more of these sets **and then lists what that row adds**. The commands are the literal ones from [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md), copied here on 2026-09-11 so a worker reading one row in an isolated worktree does not have to open another file to know what to type. Where the two disagree, the gate guide wins and the row that noticed fixes this block.

**`GATE-PY`** - every row that changes a `.py` file. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/<the modules this row names>
```

**`GATE-SCHEMA`** - every row that edits a model under `backend/idhazh/contracts/`. This is the contract drift gate and a non-empty diff fails it:

```powershell
.\.venv\Scripts\python.exe -m idhazh.contracts.export
git diff --exit-code -- schemas/
```

**`GATE-SUITE`** - the whole backend suite, which is what CI runs. Run it locally only when you cannot push:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

**`GATE-SHELL`** - every row that touches `.github/`. **No row of this plan does, since row #9b retired on 2026-09-11.** It is kept here because this block is the gate guide's own list rather than a list of what this plan happens to use:

```powershell
.\.venv\Scripts\shellcheck.exe --severity=style (Get-ChildItem .github/scripts/*.sh).FullName
```

**`GATE-WEB`** - every row that changes anything under `frontend/src/`. From `frontend/`:

```powershell
npm run check
npm run build
npm run bundle-gate
python -m idhazh site-weight --site-tree build
```

**`GATE-BROWSER`** - every row that changes what a reader or an operator sees. The canary day is the fixture; the real digest is not:

```powershell
.\.venv\Scripts\python.exe backend\utilities\build_canary_day.py
cd frontend
npm run test:logic
npm run build:canary
npm run test:browser
```

**`GATE-DAYS`** - every row that changes a published payload shape:

```powershell
python -m idhazh validate-days --day 2026-08-30 --day 2026-08-31
```

**Not a gate, in this plan or anywhere in this repository: `ruff format`.** It rewrites dozens of files nobody in this plan authored. Format the files you wrote, or leave formatting alone.

### 0.2 The claim three docstrings make, and the two render paths that retire it

**`assemble.build_day` says an already-published item keeps its place because the order is part of what a shared link shows.** `cli.already_published` and `cli.stage_visual_planner` repeat it. **Both render paths throw that order away.** `frontend/src/lib/server/payload.ts:335` calls `orderByTime(day.items)` before it cuts the seed, and `frontend/src/lib/components/DigestList.svelte:90` calls the same function over the whole day. `payload.ts` says so in its own comment on the line above: the head has to be the head of the order the page draws, not of the published one. Verified 2026-09-11.

**So the published order reaches no reader, and three docstrings defend it.** That is the highest-value finding this plan carries, because the next person to read them designs against a constraint that does not exist - and two of the three sit in the module a later row of this plan rewrites.

**The code stays, and the reason nobody wrote down is crash consistency.** `build_day`'s `already` set is what makes a run replayable, not what preserves an order. In `cli.stage_assemble`, `write_atomic(target / "digest.json", ...)` and `ledger.append_published(...)` are **42 lines apart** (measured 2026-09-11: lines 3167 and 3209), with the search-index rebuild, `site_size`, `build_manifest`, `write_atomic(run.json)`, the eval-row append and the fingerprint append between them. A run that dies inside that window leaves a committed day whose items are not in the published ledger, and the plan-time `url_key` guard would re-plan every one of them on the next run. `already_published` is the second half of the same defence and it is what keeps the visual planner from re-deciding five times a day: measured on the five finished runs of 2026-09-09, run 5 introduced 75 items into a day of 360, so without it that run would re-decide 285 items it had already paid for.

**Row #1 corrects the sentence and removes nothing.** Row #10 resolves the consistency model the sentence was hiding.

### 0.3 The numbers this plan is priced against

Derived 2026-09-11 in this worktree from the committed archive under `frontend/public/digest/`, the committed ledgers under `state/`, and `config/`. Every figure names what it was read from, so a later row can re-run it rather than inherit it.

| Figure | Value | Read from |
| --- | --- | --- |
| Committed archive | **8,550 items over 21 days**, 2026-08-21 to 2026-09-10 | `frontend/public/digest/**/digest.json` |
| Published a day, since the ceiling halved | **282 to 387**, median 365 over the six days 2026-09-05 to 2026-09-10 | same |
| Runs a day | **4 or 5** | the `runs` array on each day |
| What one run introduces | 2026-09-09: **73, 69, 73, 70, 75 = 360**. 2026-09-10: 72, 76, 74, 71, 72 = 365 | same |
| Days carrying `carried_by` at all | **10** - 2026-09-01 to 2026-09-10, 4,464 items. It is null on the 3,596 items published before the field landed and a reader of the payload may not default it | same |
| `carried_by >= 2` | **246 of 4,464 - 5.51 percent** of the days that carry the field; 268 of all 8,550 - 3.13 percent | same |
| `carried_by >= 3` | **17** - one item in 263 | same |
| Top 20 of the day by `rank_score` that are carried | **120 of 200 - 60.0 percent**, over the same 10 days | same |
| Published leads that are carried | **17 of 50** | same |
| `time_source` absent | **3,733 items** - every day published before the field landed, and the count is frozen. It was 79.2 percent of the archive when `layout.md` recorded it on 2026-09-02 and is **43.7 percent** of today's 8,550 | same |
| `time_source: unknown` | **0. It has never happened**, so only the canary day can drive it | same |
| Per-item summarize cost | mean **137.3 s**, median 113.0, p90 241.7, over the **1,459** rows dated 2026-09-06 to 2026-09-09 with outcome `ok` | `state/item-health/*.csv` |
| Worst shard since the ceiling halved | **66.9 minutes**; shard timeout 200, escalate trigger 180 | plan 23 section 0.3, from `state/runtime-counters.csv` |
| The score's terms | `repetition_weight` 1.0, `recency_weight` 0.6, `recency_half_life_hours` 18.0, `watchlist_bonus` 0.5, `front_page_bonus` 0.4; the heaviest lens weight in `config/taxonomy.json` is 0.3 | `config/idhazh.json`, `config/taxonomy.json` |
| Reliability, which already self-adapts | `reliability_window_days` **30**, `reliability_floor` **0.5** | `config/idhazh.json` |
| Feeds, and what they carry | **151**, each with exactly one `vertical`, one `tier`, one `weight`. **No syndication or wire-relationship field exists** | `config/sources.json` |
| Desks | **5** - `ai` (feed floor 35), `energy`, `business-economy`, `world`, `india` (21 each) | `config/taxonomy.json` |
| Rail markers today | `rail_group_minutes` **60**; recorded 2026-09-02 over 12 days and 4,713 stories: **907 markers**, so 80.8 percent of stories carry no label | `frontend/src/lib/day-shape.ts` docstring; `config/appearance.json` |
| Topic pills | `topic_pills_max` **8**, and `splitPills` already cuts by story count and folds the overflow into a disclosure | `config/appearance.json`, `frontend/src/lib/day-shape.ts` |
| Lenses that fire against lenses that count | The four active lenses at weight **0.0** - `markets` 911, `china` 833, `war` 365, `cyber` 234 - fired **2,343** times against **650** for the two that carry 0.3, `trade` 382 and `chips` 268. **3.6 times as often.** They tag an article and move no story. `ai-roi` is retired and fired 18 times before it was | `frontend/public/digest/**/digest.json`, `config/taxonomy.json` |
| Desk shares of the published day | `india` **31.7 percent**, `world` 26.4, `ai` 15.2, `energy` 13.8, `business-economy` 12.9. The largest sits within two points of ESCALATE trigger 2, on supply alone | `frontend/public/digest/**/digest.json` |
| What a feed says it is | `reporting` **7,227**, `analysis` 416, `announcement` 382, `research` 283, `community` **139**, `government` **103**. Six values, and the feed declares them | same; `SourceKind` in `backend/idhazh/contracts/taxonomy.py` |
| The confidence already on every item | `band` reads `high` on **4,993**, `medium` on 2,275, `low` on **1,282**. `/console/model/` already draws the `low` count, as `Marked "not sure"` | same; `docs/concepts/console-design.md` |
| The watchlist, and whether it goes quiet | **30 active entries, and all 30 fired.** The `entities` field starts 2026-08-27, so the record is 15 finished days; over 7, 14 and 15 days **none is silent**. Quietest: `asml` 10, `adani` 14, `ftc` 25, `mistral` 28, `iea` 30. `watchlist_hit` is a **boolean**, not an entry id, and it is true on 1,066 items - 12.5 percent | `config/watchlist.json`, `frontend/public/digest/**/digest.json` |
| Feeds by tier | **151 feeds**: 40 institution, 100 trade press, **11 community**. These are addresses; the 103 and the 139 two rows up are published items | `config/sources.json` |
| The console today | **three routes**, `page_weight.ceilings_bytes` naming only `/404` and `/evals/` since 2026-09-10, and `payload_ceilings_bytes` naming `console/band.json` at 2,000 B and `telemetry/` at 1,100,000 | `config/idhazh.json`, `frontend/src/lib/console/band.ts` |

**What the carriage figures mean, said next to them.** `reach = 1.0 + repetition_weight * (carried_by - 1)` at `repetition_weight` 1.0 **doubles the authority term at two carriers**. That single step is larger than the recency bonus at full strength (0.6), larger than the watchlist bonus (0.5), larger than the front-page vote (0.4) and larger than the heaviest lens (0.3) - and it is a multiplier where all four of those are additions. The consequence is measured, not argued: **under 6 percent of the pool holds 60 percent of the day's top 20**. And what the number measures is **syndication, not agreement** - `layout.md` already says `carried_by` counts feeds carrying **one address**, so two outlets writing their own piece produce two addresses and both read 1. `docs/concepts/digest.md` refuses to print the agreement claim in words ("never 'three sources covered this': that is a different claim and the number does not support it") while the ranker makes it in arithmetic. Row #4 is that contradiction closed.

**Rebuilding the day whole is refused, and this is the arithmetic.** Today `assemble` rebuilds parts of the day whole on every run - `collapse_same_story` over every item, `leading_stories` over every item, the whole month's search index, every desk reference - while the per-item work stays incremental. A row that extended that to the per-item work would spend, on 2026-09-09: run 1 processes 73, run 2 processes 142, run 3 215, run 4 285, run 5 360. **Item-passes go from 360 to 1,075 - 2.99x** - and run 5 alone goes from 75 items to 360, **4.8x**. Applied to the worst shard on record that is 66.9 minutes to about **321 minutes, 60 percent past the 200-minute timeout**, and a shard that times out uploads no artifact, so the day publishes nothing rather than publishing late. Row #10 resolves the two consistency models by making the whole-day passes cheap enough to keep, never by making the per-item work whole-day.

### 0.4 What blocks what, and what does not

**No row of this plan is blocked on plan 23, and three of them ship a branch that does nothing until it lands.** Row #7 is the row that reads most naturally as classification work and it is not: the desk floor and the desk ceiling are built against whatever field names the desk, and today that field is the feed's declared `vertical`. What plan 23 row #6 changes is the **failure mode** the floor exists to catch, and section 8 of this plan's row #7 says so. **But three rows do ship a surface that is empty until plan 23 arrives**, and the plan says so rather than implying otherwise:

| Row | What is empty until plan 23 lands |
| --- | --- |
| #6 | The rule that an auto-created desk may be folded away. Auto-created verticals arrive from plan 23 row #16 and do not exist today, so the branch is driven by a fixture |
| #8 | The secondary desk. It comes from the same source the primary does, which is the feed's declared vertical today - so it is empty on almost every item and the ceiling's overflow has nowhere to go until plan 23 row #6 |
| #12 | Every figure on the `Judgement` tab. Its own text says most of them are absent on the day it lands, which is why its Reckoner row now depends on plan 23 row #14 |

**Row #9a is blocked on plan 23 row #21**, which creates the counterfactual ledger it adds columns to (section 10). **An earlier form of this section read "Nothing in this plan is blocked on plan 23"**, which row #12's own text already contradicted; the correction is that no row is blocked on plan 23 for its *design*, and two rows are blocked on it for their *data*.

**Neither `state/scores` nor `state/item-health` carries a counterfactual** - verified 2026-09-11 by reading both headers, which name 36 and 29 columns and no candidate score at any weight but the committed one. A loop that adapts without one is adapting on the outcome, which is a loop reading its own past decisions and calling them evidence.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Three docstrings defend a requirement the page retired | - | A | PENDING | - | - | - |
| 5 | The rail goes and the time lands under the heading | - | A | PENDING | - | - | - |
| 2 | One order over the whole day, inside a frame a person set | 1 | B | PENDING | - | - | - |
| 3 | `rank_score` orders the stream, and its terms are the editor's | 2 | C | PENDING | - | - | - |
| 6 | The topic pills order by what is running | 2 | C | PENDING | - | - | - |
| 4 | Carriage becomes a tie-break | 3 | D | PENDING | - | - | - |
| 7 | A desk floor and a desk ceiling | 2 | D | PENDING | - | - | - |
| 8 | A story cross-files to a second desk | 7 | E | PENDING | - | - | - |
| 9a | The placement terms on the counterfactual ledger plan 23 creates | 3, plan 23 row #21 | E | PENDING | - | - | - |
| 9b | RETIRED - plan 23 row #17 is the weights loop | - | - | RETIRED | - | - | - |
| 10 | The `assemble` consolidation | 2, 5, 7, 8 | F | PENDING | - | - | - |
| 11 | The console strip takes five tabs | - | G | PENDING | - | - | - |
| 14 | A target distribution, and the day's distance from it | 7 | G | PENDING | - | - | - |
| 12 | `Judgement` - what the model made of each article | 11, plan 23 row #14 | H | PENDING | - | - | - |
| 13 | `Voices` - who supplied the day, and what it is worth | 11 | I | PENDING | - | - | - |

**What a parallel group means, stated so a worker can check it.** **Within one group, no two rows may write the same file.** A glob counts as every file it covers, so `backend/tests/**` and `schemas/**` collide with any named file underneath them - and a row that edits any model under `backend/idhazh/contracts/` counts as writing every schema its edit regenerates, because the drift gate fails on a byte. **So there are no globs in this plan.** Every row's `Files touched` list names files. **A row that widens its file list during execution re-checks its own group before it opens a pull request**, and section 0.1 expects that widening to happen.

**Fourteen rows, nine groups, four singletons.** Row #2 is the first: it creates `backend/idhazh/placement.py`, which rows #7, #8 and #10 all read and two of them extend, and it is the row that decides there is one order at all. A second row landing beside it would be building against a shape that is still moving.

**Row #10 is the second singleton, and it was not one until 2026-09-11.** It shared group F with row #9b, which is now retired - plan 23 row #17 is the weights loop (section 11). Row #10 is the widest row in the plan at 16 files and the one most likely to widen further, so it keeps the group to itself rather than taking a partner it would have to re-check.

**Rows #12 and #13 are the other two singletons, and the reason is the four console doc pages.** A console change goes to the page that owns the question - the payload shape to `console-payloads.md`, the chart choice to `console-charts.md`, the tab and its worst state to `console.md`, the sufficiency argument to `console-design.md` - so **both tab rows write all four**, and two rows writing one page is the collision this section exists to refuse. Splitting the pages between them was rejected: it would put the `Voices` chart argument on the page that owns tabs, which is the routing defect, not a way round it. Every other group holds two.

**Row #11 has no predecessor and both tab rows depend on it**, because it owns the three files a fifth tab moves - the strip's geometry, the route list, and the severity the band ranks a route by. Two tab rows each editing `ConsoleNav.svelte` and `band.ts` would be the same collision one group later.

**Row #5 has no predecessor on purpose, and the reason is a defect it would otherwise inherit.** The rail groups stories by time and `day-shape.ts` states in its own docstring that a rail over an order it did not sort reopens groups further down and prints numbers that jump as the reader scrolls. Row #2 replaces the time order with a scored one. So the rail has to go **before** row #2, not after it, and a schedule that put row #5 late would ship a run of days where the rail was visibly wrong.

### The file sets, which are what prove it

Derived from the rows' own `Files touched` lists on 2026-09-11. **It is derived rather than authoritative**: a worker checks a group by diffing the two rows' lists in the sections below, never by trusting this table ([`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)).

| Group | Rows | What the first row writes | What the second row writes | Where they come closest |
| --- | --- | --- | --- | --- |
| A | 1, 5 | `backend/idhazh/assemble.py`, `backend/idhazh/cli.py`, `backend/tests/test_pipeline.py`, `docs/architecture/publishing/visuals.md`, `docs/architecture/sources/discovery.md` | `frontend/src/lib/components/{DigestItem,DigestList,TimeRail}.svelte`, `frontend/src/lib/{day-shape,format}.ts`, `backend/idhazh/contracts/appearance_config.py`, `schemas/appearance-config.schema.json`, `config/appearance.json`, `frontend/tests/{time-rail,item-card,item-zones,reading-page}.spec.ts`, `docs/concepts/ui-shell.md`, `docs/architecture/publishing/layout.md` | Both write a `docs/architecture/publishing/` page. Row #1 writes `visuals.md`; row #5 writes `layout.md`. Row #1 opens no frontend file and row #5 opens no pipeline module. **Row #5 gained `reading-page.spec.ts` on 2026-09-11** - it is the second spec reading `[data-rail-note]` - and row #1 opens no spec, so the group holds |
| B | 2 | singleton - it creates `placement.py`, which four later rows read | - | - |
| C | 3, 6 | `backend/idhazh/rank.py`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_rank.py`, `docs/architecture/sources/discovery.md` | `frontend/src/lib/day-shape.ts`, `frontend/src/lib/components/FilterBar.svelte`, `backend/idhazh/contracts/appearance_config.py`, `schemas/appearance-config.schema.json`, `config/appearance.json`, `frontend/tests/{filter-bar,topics}.spec.ts`, `docs/architecture/publishing/frontend.md` | Both add a config key, edit a contract model and regenerate one schema. **Two different config files, two different contract modules, two different schema files**, so the drift gate sees two disjoint diffs |
| D | 4, 7 | `backend/idhazh/rank.py`, `config/idhazh.json`, `backend/tests/test_rank.py`, `docs/architecture/sources/discovery.md`, `docs/architecture/publishing/layout.md` | `backend/idhazh/placement.py`, `backend/idhazh/contracts/taxonomy.py`, `schemas/taxonomy.schema.json`, `config/taxonomy.json`, `backend/tests/{test_placement,test_contracts}.py`, `docs/concepts/placement.md` | Both write a file in `config/`. Row #4 writes `idhazh.json` and row #7 writes `taxonomy.json`. Row #4 adds no contract field, so it regenerates no schema |
| E | 8, 9a | `backend/idhazh/placement.py`, `backend/idhazh/contracts/{article,digest_day,digest_view}.py`, `schemas/{article,digest-day,digest-view}.schema.json`, `frontend/src/lib/payload/types.ts`, `backend/tests/{test_placement,test_contracts}.py`, `docs/concepts/placement.md` | `backend/idhazh/{rank,cli,ledger}.py`, `backend/idhazh/contracts/counterfactual_score.py`, `schemas/counterfactual-score.schema.json`, `backend/tests/test_ledger.py`, `docs/concepts/growing-reads.md` | Both edit a contract and regenerate a schema. Three named schema files against one, all four distinct. Row #8 opens no ledger and row #9a opens no published payload model. **Row #9a's contract and schema are plan 23 row #21's, extended rather than minted** (section 10), and it dropped `backend/tests/test_marks.py` with the module it no longer creates |
| F | 10 | singleton at 16 files - row #9b retired on 2026-09-11 and left it alone | - | - |
| G | 11, 14 | `frontend/src/lib/components/ConsoleNav.svelte`, `frontend/src/lib/console/band.ts`, `backend/idhazh/publish_console_band.py`, `backend/idhazh/contracts/console_band.py`, `schemas/console-band.schema.json`, `tests/fixtures/contracts/console-band/newest-day.json`, `backend/tests/test_console_payloads_producer.py`, `frontend/tests/{console-nav,console-title,console-band}.spec.ts`, `docs/architecture/publishing/console.md` | `backend/idhazh/diversity.py`, `backend/idhazh/assemble.py`, `backend/idhazh/contracts/{app_config,day_metrics}.py`, `schemas/{app-config,day-metrics}.schema.json`, `config/idhazh.json`, `backend/tests/{test_diversity,test_contracts,test_marks}.py`, `docs/concepts/placement.md` | Both regenerate a schema. **Two different contract modules, two different schema files, two different fixtures**, so the drift gate sees two disjoint diffs. The one file that could bring them together is `backend/tests/test_contracts.py`: row #14 lists it and row #11 does not, so row #11 re-checks this group before it opens a pull request if it finds it needs one |
| H | 12 | singleton at 18 files - it writes all four console doc pages | - | - |
| I | 13 | singleton at 19 files, the widest row in the plan - it writes all four console doc pages, and it is the only row that edits the Pipelines route | - | - |

### Why the frame is a module and not a longer `build_day`

**`backend/idhazh/assemble.py` is 1,316 lines today** (measured 2026-09-11) and it already carries the day builder, the duplicate pass, the lead chooser, the search index, the embeddings, the manifest and the site-size reader. Adding one order, two head caps, a desk floor, a desk ceiling and a cross-file rule to it would make five rows of this plan write one file, which is the collision plan 23 spent a whole section undoing after the fact.

**`placement.py` is created by row #2 and filled by rows #7 and #8, which is Tidy First read literally**: the module arrives with the code that needs it and never ahead of it, so it is not the pre-created empty module `CLAUDE.md` section 10 names. What it buys, counted rather than asserted: rows #7 and #8 pair with rows #4 and #9a instead of queueing behind row #2, and row #10's consolidation has one module to move ordering **out of** rather than a longer function to reason about.

**It also draws the line this plan's title is about.** `rank.py` scores one story. `placement.py` decides what the day looks like given every story's score - which desk may hold how much of the head, which feed may not repeat, which desk may not go dark. Those are different questions and they have been one function.

---

## 2. Row #1 - Three docstrings defend a requirement the page retired

- **Scope:** The link-stability justification is deleted from `assemble.build_day`, `cli.already_published` and `cli.stage_visual_planner`, and replaced with the reason the code actually has - crash consistency between the day write and the ledger append. Behaviour-free. No line of executable code changes.
- **Files touched:** `backend/idhazh/assemble.py`, `backend/idhazh/cli.py`, `backend/tests/test_pipeline.py`, `docs/architecture/publishing/visuals.md`, `docs/architecture/sources/discovery.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_pipeline.py`, `GATE-SUITE`. Plus, in this row:
  - `git grep -n "shared link"` returns no hit in `backend/` that is about the item order;
  - `docs/architecture/sources/discovery.md` line 259 keeps its tie-break rule and loses its false reason (decision 2);
  - the two frontend sentences named in decision 3 are read and left alone, and the pull request says they were read.
- **Oracle:** **A run that dies between the day write and the ledger append re-plans nothing the committed day already carries.** Driven from `backend/var/canary/`: build a day, write `digest.json`, skip `append_published`, run the plan stage again, and assert the second plan's `items` is empty of anything the day holds. It fails today if `build_day`'s `already` set is removed and passes if only the docstring changes - which is what tells a reviewer the sentence and the set are different things. **The oracle must fail against the base tree**, and it does, because no test names this window: `git grep -n "append_published" -- backend/tests` finds the ledger's own round trip and not the gap.
- **What this row does not do:** it removes no code, changes no order, and does not touch `frontend/`. The `already` set stays and row #10 decides what happens to it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The sentence goes; the set stays.** They were one thing in the docstring and are two things in the code. Deleting the set on the strength of the sentence being wrong would remove the replay defence section 0.2 measures | Fowler |
| 2 | **`discovery.md`'s tie-break rule keeps its text and loses its reason.** "Ties break on the canonical address" is still right and still load-bearing - two runs over identical feeds must not disagree - but the reason is determinism of a re-run, not what a shared link shows | Fowler |
| 3 | **`LeadingStories.svelte` and `readstate.ts` keep their sentences unchanged.** Both say re-ranking in the browser would break a shared link, and both are **true**: the leading block is drawn in the published order and read state is per-reader by design. Only the three pipeline docstrings make a claim the render path contradicts | Verified 2026-09-11 |
| 4 | This row is **Level 0** and runs first, because the next person to read those docstrings designs against a constraint that does not exist - and two of the three sit in the module row #10 rewrites | `CLAUDE.md` section 6 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Make the frontend honour the published order instead, so the docstrings become true again | The published order is desk-blocked - the whole of one desk, then the whole of the next - and `day-shape.ts` records what that cost: a reader met the same desk ninety times before the next one started. Restoring it is a worse page. Rows #2 and #3 replace it with an order worth honouring | Jony; `frontend/src/lib/day-shape.ts` |
| 2 | Delete the `already` set along with the sentence | It is the replay defence. Without it run 5 of 2026-09-09 would have re-decided 285 items it had already paid for, at a measured mean of 137.3 s each | Section 0.2 |
| 3 | Leave the docstrings and note the contradiction in `layout.md` | A note on a page a reader may not open does not stop the next person reading the module. `CLAUDE.md` section 5: a section a later one corrects is deleted, not labelled | `CLAUDE.md` section 5 |

---

## 3. Row #2 - One order over the whole day, inside a frame a person set

- **Scope:** `backend/idhazh/placement.py` - one order over the whole day, published, plus two head caps: no desk holds more than `placement.max_desk_in_head` of the first `placement.head_items`, and no feed holds more than one of the first `placement.head_no_repeat`. Config-driven, defaulted, tested.
- **Files touched:** `backend/idhazh/placement.py`, `backend/idhazh/assemble.py`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_placement.py`, `backend/tests/test_marks.py`, `docs/concepts/placement.md`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/{test_placement,test_marks}.py`, `GATE-SCHEMA`, `GATE-SUITE`, `GATE-DAYS`. Plus, in this row:
  - `schemas/app-config.schema.json` carries today's `version` and a `changelog` entry naming the `placement` block;
  - `backend/tests/test_marks.py` passes, so the new module is classified;
  - `docs/concepts/placement.md` exists and is linked from `docs/architecture/publishing/layout.md` and `docs/reference/documentation-structure.md`.
- **Oracle:** **The frame holds on a day built to break it, and the day is not one story shorter for it.** A built fixture where one desk supplies 18 of the top 20 by score and one feed supplies 9 of the top 10; assert no desk holds more than the cap in the head, no feed repeats inside `head_no_repeat`, **and `len(out) == len(in)`**. The length assertion is half the oracle and is the half a cap gets wrong: a cap that drops rather than displaces shortens the day, and a reader cannot see what was left out. **Built rather than sampled**, because no committed day has that shape and this plan needs the day that has not happened yet.
- **What this row does not do:** it changes no score. `rank_score` still means what it means today and row #3 changes that. It does not remove the frontend's re-sort either - row #10 does, and until then the page draws its own order over a payload that now has a defensible one.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A cap displaces; it never shortens.** Every slot a cap takes back is offered to the best candidate the cap held down. This is the rule `rank._take` already follows for `day_ceiling` and it is copied rather than re-invented | `backend/idhazh/rank.py`; Editor |
| 2 | **The head is a count, not a share** - the first 20 and the first 10. What a reader sees before deciding whether to scroll does not grow with the day: a share of a 731-story day is a head nobody reaches | Jony |
| 3 | **The order is computed in the backend and published.** The frontend's sort is removed in row #10 and not before, so no row of this plan ships a day with no order at all | Section 0.1 |
| 4 | Both caps are `config/idhazh.json` keys with sane defaults and a schema bound. A fresh clone runs on the defaults | `CLAUDE.md` Rule #6 |
| 5 | **This is what replaces the editor.** Nobody reads the digest before it publishes and it publishes five times a day, so a standing editorial decision can only reach a reader as arithmetic that runs without one. The page that says so is `docs/concepts/placement.md` and it is written here rather than left implicit | Editor; owner |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Interleave the desks round-robin | That is a cap of one in five with no editorial input, and on a heavy-AI day it publishes four thin desks ahead of the day's actual story. A cap bounds a desk's share of the head; it does not promise every desk an equal share of it | Editor |
| 2 | Leave the ordering in the browser and drop it from the backend | Two orders where one is enough, and the browser's cannot express a desk cap: it has the day but not the plan, not the desk shortfalls and not the run boundary. It also puts an editorial rule on the reader's device, where a slow phone decides when it applies | Carmack |
| 3 | Apply the caps at plan time, in `rank.plan_vertical` | The caps are about the head of the assembled day, and plan time runs one desk at a time and cannot see it. `day_ceiling` already carries the only cross-desk fact plan time needs and adding a second was refused for the same reason | Fowler |

---

## 4. Row #3 - `rank_score` orders the stream, and its terms are the editor's

- **Scope:** `rank_score` stops being an admission score and becomes the stream's order. Its terms, in the editor's stated order: authority times the feed's weight; decayed recency at an 18-hour half-life; the feed's reliability; a watchlist subject. `RANK_VERSION` bumps.
- **Files touched:** `backend/idhazh/rank.py`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_rank.py`, `docs/architecture/sources/discovery.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_rank.py`, `GATE-SCHEMA`, `GATE-SUITE`. Plus, in this row:
  - `rank.RANK_VERSION` is bumped and the run manifest records the new string;
  - `schemas/app-config.schema.json` carries today's `version` and a `changelog` entry;
  - the term order in `docs/architecture/sources/discovery.md` matches the code, term for term.
- **Oracle:** **Every term the score names moves the order on its own, and no term it does not name moves it at all.** A built pool of paired candidates identical but for one term; assert each pair flips, and assert a pair differing only in a field the score does not read - `source_form`, `title` length, `item_id` - does not. **The second half is what catches a term nobody declared**, and it is the half a sampled test cannot do, because the archive never holds two stories identical but for one field.
- **What this row does not do:** it does not touch carriage, which is row #4, and it adds no new input. **All four terms are buildable today**: `authority()` already multiplies tier by feed weight by reliability, `recency_bonus()` already decays at `collect.recency_half_life_hours`, `ledger.reliability` already exists, and `watchlist_bonus` is already a term. This row decides their **order and their relative size**, and gives the result the stream.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Reliability is already the model this whole plan copies and it needs no new machinery.** `ledger.reliability` reads the trailing `collect.reliability_window_days` - 30 - of feed health, clamps each feed between `collect.reliability_floor` - 0.5 - and 1.0, treats a feed with no evidence as 1.0, and writes nothing to `config/`. It is a fact about the world derived inside the run from a bounded window, which is exactly the half of section 0's governing line that is not a pull request | Verified 2026-09-11; owner |
| 2 | **Recency stays a bonus and never becomes a filter.** A cutoff cannot tell a strong old story from a weak fresh one; `too_old` already decides what may be admitted and this term decides only the order of what passed | `backend/idhazh/rank.py`; [`../docs/architecture/sources/freshness.md`](../docs/architecture/sources/freshness.md) |
| 3 | **`RANK_VERSION` bumps in this commit.** A published order that moved for a reason nobody recorded is a published order nobody can defend, and `RunRecord.rank_version` is where the shape is written down | `backend/idhazh/rank.py` |
| 4 | The relative sizes are **config, and they are estimates until row #9a can price them**. Every one is stamped as an estimate in `config/idhazh.json`'s own comment block and in `discovery.md`, per Rule #10 | `CLAUDE.md` Rule #10 |
| 5 | **A term may reorder; it may never admit.** A weight that could pull an item past a gate it failed is a weight that publishes something the gate refused, and no amount of tuning makes that safe | Editor |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the time order and add a separate "important" band above it | Two orders on one page with nothing telling the reader which governs, which is the contradiction plan 23's standing rule already forbids for two marks on one line | Jony |
| 2 | Order by a model's judgement of importance | A model verdict that selects what a reader sees first is a model selecting what publishes, in every sense that matters. `CLAUDE.md` section 0a | `CLAUDE.md` section 0a |
| 3 | Normalise the score to 0-1 and print it | A number beside a story implies a scale we would owe the reader an explanation for. `digest.md` already refuses numerals in the lead block for the same reason | Reader; [`../docs/concepts/digest.md`](../docs/concepts/digest.md) |

---

## 5. Row #4 - Carriage becomes a tie-break

- **Scope:** `carried_by` stops multiplying authority and becomes one step in the score: carried or not carried, no count, worth less than one tier step.
- **Files touched:** `backend/idhazh/rank.py`, `config/idhazh.json`, `backend/tests/test_rank.py`, `docs/architecture/sources/discovery.md`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_rank.py`, `GATE-SUITE`. Plus, in this row:
  - `docs/architecture/sources/discovery.md`'s score block is rewritten - the published formula there is the multiplier this row removes;
  - `docs/architecture/publishing/layout.md`'s `carried_by` row says what the field now buys, which is less than it bought;
  - **`rank.RANK_VERSION` is bumped, or the pull request says why the scoring shape did not move.** Row #3 bumps it and says why; this row turns a multiplier into an additive step, which moves the order of every carried story. `RunRecord.rank_version` is the only place a later reader can see that two days were ordered by different arithmetic (found 2026-09-11);
  - no schema changes, because the field is already published and its meaning is unchanged. Only its weight moves.
- **Oracle:** **The carriage step cannot outrank one tier step.** Asserted twice: as an invariant over the config (`placement.carriage_step` is strictly less than the smallest gap between two `collect.tier_weights` values, and the test reads both from config rather than from literals), and as a case - a single-carrier institution story beats a two-carrier community story on a built pool. **It fails against the base tree**, where the multiplier makes the two-carrier story win by construction.
- **What this row does not do:** it does not remove `carried_by` from the payload, does not change how it is counted, and does not implement the independence test. Decision 3 says why and what ships instead.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **One step, not a count.** Three carriers is not three times the story. The step fires at `carried_by >= 2` and never grows, so the 17 items in 4,464 that reached three carriers gain nothing over the 246 that reached two | Measured 2026-09-11; Editor |
| 2 | **It ranks below a tier step, and the oracle enforces it.** Today it doubles the authority term at two carriers, which is a bigger move than the recency bonus, the watchlist bonus, the front-page vote and the heaviest lens - and it is a multiplier where every one of those is an addition | Section 0.3 |
| 3 | **The independence half does not ship, and the row says so on the page rather than implying otherwise.** Independent carriage needs to know which of 151 feeds are wire customers of the same original, and `config/sources.json` has no syndication field - verified 2026-09-11. So what ships is a step on "more than one of our feeds carried this address", and `discovery.md` and `layout.md` both say that is **syndication, not agreement**. Adding a `syndicates_from` relation to the source contract is named in section 14 as work nobody owns | Verified 2026-09-11; Andre |
| 4 | **This closes a contradiction rather than opening one.** `docs/concepts/digest.md` already refuses to print "three sources covered this" because the number does not support the claim. The ranker was making that claim in arithmetic while the page refused it in words | [`../docs/concepts/digest.md`](../docs/concepts/digest.md) |
| 5 | The step's size is an **estimate**, and it moves under plan 23 row #17's per-run loop like every other weight, with the oracle's ceiling as its hard bound | `CLAUDE.md` Rule #10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Lower `repetition_weight` from 1.0 to something small and keep the multiplier | A multiplier scales with authority, so the same weight buys a big move on an institution and a small one on a community feed - the opposite of what a tie-break should do. And it stays uncapped: a story on six feeds would still take the day | Andre |
| 2 | Remove carriage from the score entirely | It is real signal, it is one of the four why-lines the leading block can print, and 60 percent of today's top 20 carries it. Removing it would change the day more than the multiplier does and in a direction nobody measured | Editor |
| 3 | Build the independence test now, from the registrable domain | Two feeds on one domain are already one feed for `max_per_source` purposes. What the test needs is wire relationships **across** domains, which the domain cannot answer | Fowler |

---

## 6. Row #5 - The rail goes and the time lands under the heading

- **Scope:** `TimeRail.svelte` is deleted. Every story prints its own published time in small type beside its heading. `time_source` decides how it is drawn.
- **Files touched:** `frontend/src/lib/components/DigestItem.svelte`, `frontend/src/lib/components/DigestList.svelte`, `frontend/src/lib/components/TimeRail.svelte` (deleted), `frontend/src/lib/day-shape.ts`, `frontend/src/lib/format.ts`, `backend/idhazh/contracts/appearance_config.py`, `schemas/appearance-config.schema.json`, `config/appearance.json`, `frontend/tests/time-rail.spec.ts` (deleted), `frontend/tests/item-card.spec.ts`, `frontend/tests/item-zones.spec.ts`, `frontend/tests/reading-page.spec.ts`, `docs/concepts/ui-shell.md`, `docs/architecture/publishing/layout.md`
- **`frontend/tests/reading-page.spec.ts` is in the list and was not before.** `git grep -n data-rail-note -- frontend/tests` returns **two** specs, not one: `time-rail.spec.ts:299` and `:312`, which this row deletes with the component, and **`reading-page.spec.ts:296`, which it does not** (measured 2026-09-11). Deleting `TimeRail.svelte` takes that locator's target with it, so the row's own no-prisoners rule reaches a second file. **Row #10 also names `reading-page.spec.ts` and it is in group F**, so group A still holds.
- **Acceptance gates:** `GATE-WEB`, `GATE-BROWSER`, `GATE-SCHEMA`, `GATE-SUITE`, and the `CLAUDE.md` section 12 browser smoke. Plus, in this row:
  - `rail_group_minutes` and `railRows` and `RailRow` go in the same commit as the component (section 0.1, no prisoners);
  - **`Times shown in UTC.` renders exactly once on a day page and the assertion moves with it**, not deleted with `time-rail.spec.ts`. `reading-page.spec.ts:296` already reads `[data-rail-note]` and keeps doing so against the day's head;
  - `schemas/appearance-config.schema.json` carries today's `version` and a `changelog` entry naming the removed key;
  - the sufficiency checks in [`../docs/concepts/design-system.md`](../docs/concepts/design-system.md) pass, or a `## Design rationale` entry says why not.
- **Oracle:** **The eyebrow still holds four children at every width and the time is one of them.** Driven from the canary day, which plants a story of every `time_source` state on purpose - including `unknown`, which has **never happened in 8,550 committed items** and which no archive-driven test can reach. The assertion is on the count and on the fourth child's identity, at each breakpoint the spec already drives. It fails against the base tree, where the fourth child is the day link and the time is on a rail.
- **What this row does not do:** it changes no order and no payload field. `published_at` and `time_source` are already published and already correct.

### What the placement has to answer, and the answers

Ruled by Susan, 2026-09-11, with Jony on what may leave the page.

| Question | Answer |
| --- | --- |
| Where exactly | The eyebrow, as its fourth and last child, immediately before the heading. It is a fact a reader uses to decide whether to read at all, which is what that zone is for |
| What it replaces | **The day link, on a day page only.** `DigestItem.svelte` records that the day link survived the 2026-09-02 move because a search result list has no rail and the date is how a reader tells which day a found story is from. On a dated page the date **is** the page, so the link is a fact the reader already has. In a search result the day link stays and the time does not appear |
| What size | The eyebrow's own type, colour and weight. Not smaller, not lighter, not a new step on any scale |
| An item with no publisher time | The stamp is drawn unattributed - no mark, no word. That is the render `layout.md` already rules for the 3,733 items whose `time_source` is absent, and it is the honest one: printing it as a feed time is a claim the run never recorded, and refusing to print it deletes a fact from 44 percent of the archive |
| `time_source: first_seen` | The clock with the existing mark. `format.ts` already owns that mark and it moves with the time |
| `time_source: unknown` | Nothing is drawn. There is no number to print, and the canary day is what proves the branch renders |
| What stops 627 timestamps becoming wallpaper | **Nothing about the timestamp - it is the fourth of four facts in a line that already repeats on every item, and it is drawn in the same type as the other three.** A fifth typographic weight on that line would be the wallpaper. The rail's own arithmetic is the argument: measured 2026-09-02 over 12 days and 4,713 stories at the 60-minute default, it printed 907 markers, so **80.8 percent of stories carried no time at all**, and on 2026-09-01 that is 31 labels across 627 stories (re-counted 2026-09-11: that day holds **627** items). The choice is not "33 timestamps or 627"; it is "596 stories with no time, or every story with its own" |
| **What happens to `Times shown in UTC.`** | **It moves to the day's head, once per page, and it is not deleted.** `TimeRail.svelte:34` draws it as `<p class="note" data-rail-note>Times shown in UTC.</p>` - one caption for the whole column - and it is the reason `railTime` prints bare digits at all: the function's own docstring says `Yesterday`, `First seen` and `No time given` are gone because "the column already says `Times shown in UTC` once, above itself". **Delete the component and that sentence stops being true**, and 627 bare clocks a day carry no zone. So the caption lands in the day's chrome above the stream, in the day's chrome type, **once** |
| Why not a suffix on each stamp | 627 repetitions of `UTC` on a page to state one fact that is true of every stamp on it. The caption is a property of the **page**, not of a story, and it is drawn where page-level facts are drawn. `docs/concepts/ui-shell.md:79` already rules this - "Not a suffix on 359 labels" - and this row moves the sentence rather than overturning it |

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The rail is deleted, not kept beside the timestamp.** Two marks for one thing on one line is the contradiction plan 23's standing rule already forbids, and it is the exact duplicate the rail was built in 2026-09-02 to remove | Jony; plan 23 section 0.1 |
| 2 | **Hovering to reveal the time is refused.** It is unreachable on the surface most readers use, and a fact worth having is a fact worth drawing | Owner, 2026-09-11 |
| 3 | The time is **the item's own, to the minute**, never a rounded or grouped one. Grouping is what the rail did and it is what left 80.8 percent of stories unlabelled | Susan |
| 4 | **Susan rules the slot; Jony rules what leaves it.** The day link's removal on a day page is Jony's call under the four-fact cap and it is recorded above with what the reader loses, which is nothing they do not already have from the URL | `CLAUDE.md` section 14 |
| 5 | This row lands **before** row #2. The rail groups by time; row #2 replaces the time order with a scored one; a rail over an order it did not sort reopens groups further down, which `day-shape.ts` already states in its own docstring | Section 1 |
| 6 | **The zone caption survives the component that drew it.** It is the fact that makes every bare clock on the page readable, `railTime`'s docstring names it as the reason the clocks are bare, and it is asserted in two specs. Deleting the rail without moving the caption is the no-prisoners rule applied to the wrong noun: the rail was the duplicate, and the caption was the thing the rail happened to be carrying. **`docs/concepts/ui-shell.md` is rewritten in this commit** so the page that states the rule states where the sentence now lives | Susan, 2026-09-11; section 0.1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the rail and add a per-item time under it | The duplicate the rail exists to remove, and a reader with two times on one story has nothing telling them which is the story's | Jony |
| 2 | Keep the rail and re-sort the stream by time inside each score band | It buys the rail back at the cost of the frame: a band boundary is invisible, so a reader sees a time order that resets for no reason they can see | Susan |
| 3 | Print a relative time - "2 hours ago" | It is wrong the moment the page is cached, and the site is static with a service worker. A clock is a fact; "2 hours ago" is a fact about when the bytes were built | Reader |

---

## 7. Row #6 - The topic pills order by what is running

- **Scope:** The topic pill row orders by how much of the day each desk holds, refreshed at every publish, with a margin that stops a desk swapping places for one story. The fold threshold moves from 8 to 5.
- **Files touched:** `frontend/src/lib/day-shape.ts`, `frontend/src/lib/components/FilterBar.svelte`, `backend/idhazh/contracts/appearance_config.py`, `schemas/appearance-config.schema.json`, `config/appearance.json`, `frontend/tests/filter-bar.spec.ts`, `frontend/tests/topics.spec.ts`, `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `GATE-WEB`, `GATE-BROWSER`, `GATE-SCHEMA`, `GATE-SUITE`, and the section 12 browser smoke. Plus:
  - `schemas/appearance-config.schema.json` carries today's `version` and a `changelog` entry;
  - `splitPills`'s docstring is rewritten rather than contradicted (decision 1).
- **Oracle:** **The row is a pure function of the payload, and a desk does not move for a margin below the threshold.** Two assertions on a built payload: rendering the same day twice gives the identical order, and a payload where two desks differ by fewer than `digest.pill_move_min` stories keeps them in their previous order. **The second is the row's whole risk** and it needs a fixture carrying the previous order, which no committed day does.
- **What this row does not do:** it does not build the pill row, the disclosure or the count-based cut. **All three already exist**: `FilterBar.svelte` draws the pills, `splitPills` already cuts by story count, and the overflow already folds into a disclosure whose summary says how many. What this row changes is the **order**, the **threshold**, and the rule that stops the order twitching.

### The recorded refusal this row overturns

`splitPills`'s own docstring refuses exactly this change: *order is the payload's, in both halves, never the count order the cut used - re-sorting by size would move a topic between two days for a reason a reader cannot see.* That objection is correct and it is not answered by wanting the feature. **What answers it is a margin.** A desk moves only when it is ahead by `digest.pill_move_min` stories, so the reason a desk moved is always a difference a reader can see in the counts on the pills themselves. The row rewrites the docstring to say that, rather than leaving a refusal above code that no longer honours it (`CLAUDE.md` section 5).

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A margin, not raw count order.** Without it the row reorders between a reader's breakfast and their lunch, and a control that moves under the pointer is read as instability whatever caused it | Susan; `frontend/src/lib/day-shape.ts` |
| 2 | **The active desk stays on the row**, folded or not. It is the one pill the reader came for and the only mark saying where they are. This rule exists today and is kept verbatim | `frontend/src/lib/day-shape.ts` |
| 3 | **A curated desk is never folded away; an auto-created one may be.** They rank on the same number in the **order** and on different rules in the **fold**. A desk a person put in `config/taxonomy.json` is a promise the site makes; a desk a model proposed is a suggestion, and hiding a suggestion costs a reader nothing. Auto-created verticals arrive from plan 23 row #16 and **do not exist today**, so this row writes the rule and the branch is driven by a fixture | Editor; owner |
| 4 | **The threshold is config, not code.** 8 today, 5 after this row, in `config/appearance.json` | `CLAUDE.md` Rule #6 |
| 5 | The order is computed at build time and published. Measuring the row in the browser was refused for a reason the conclusion does not need: a row that measures itself is wrong until a script runs, on any route. **The reason this decision used to give was that "every page here is prerendered", and that is false** - `frontend/src/routes/[date]/+page.ts:22` and `frontend/src/routes/[date]/[vertical]/+page.ts:11` both set `export const ssr = false`, so the two dated reading routes render in the browser (verified 2026-09-11). **The real reason is that one order is computed in the backend and published** (section 0.1), so a measurement taken on the reader's device could disagree with the order the payload carries | `frontend/src/lib/day-shape.ts`; corrected 2026-09-11 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Order by count with no margin | `splitPills`'s recorded objection, unanswered: a topic moves between two days for a reason a reader cannot see | Jony |
| 2 | Animate the reorder so the movement is legible | It makes the twitch prettier and no less frequent, and it adds motion to a control on the surface a phone loads first | Susan |
| 3 | Order by a trend over several days rather than by today's count | The pill row is a way into **today**. A desk that was busy yesterday and is quiet now would sit at the front of a row whose counts contradict it | Editor |

---

## 8. Row #7 - A desk floor and a desk ceiling

- **Scope:** No desk publishes fewer than `taxonomy.<desk>.floor` stories where supply allows, and no desk holds more than `taxonomy.<desk>.ceiling` of the day. Overflow goes to the story's second-best desk, which is row #8.
- **Files touched:** `backend/idhazh/placement.py`, `backend/idhazh/contracts/taxonomy.py`, `schemas/taxonomy.schema.json`, `config/taxonomy.json`, `backend/tests/test_placement.py`, `backend/tests/test_contracts.py`, `docs/concepts/placement.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/{test_placement,test_contracts}.py`, `GATE-SCHEMA`, `GATE-SUITE`, `GATE-DAYS`. Plus:
  - `schemas/taxonomy.schema.json` carries today's `version` and a `changelog` entry naming both keys;
  - **both keys are optional with a default, and the schema does not require them.** Every desk in the committed `config/taxonomy.json` carries a floor and a ceiling in the same commit, so nothing ships without one - but a **taxonomy fixture** written by another plan must still validate. Plan 23 writes three: `tests/fixtures/taxonomy/definitions-a.json`, `definitions-b.json` and `retired-event.json`, none of which carries a floor or a ceiling, and a required key would turn this row into three failing tests in somebody else's plan. **This is the rule plan 23 row #2 decision 3 already states** - the schema gates shape, never contents - and requiring these two would be the first exception to it (found 2026-09-11).
- **Oracle:** **A day where every story reads AI still publishes five desks, and the floor never admits a story that failed a gate.** Two halves, both on built fixtures: a pool whose every item names one desk, asserting five desks present and none above its ceiling; and a pool where the only candidate left for a thin desk is one `too_old` or `below_feed_floor` rejected, asserting the desk stays thin and says so rather than being filled. **The second half is the one that matters** - a floor that can promote a rejected story is a floor that publishes what a gate refused.
- **What this row does not do:** it does not decide which desk a story belongs to. That field is the feed's declared `vertical` today and becomes the read desk under plan 23 row #6; this row is indifferent to which.

### Why this is required rather than optional, and what changes under plan 23

**Today five desks cannot go empty, and nothing in the code guarantees it.** A feed sits on exactly one desk (`config/sources.json`, 151 feeds, one `vertical` each), and a desk's `min_feeds` floor counts feeds rather than stories - 35 for `ai`, 21 for the other four. So the five desks are held up by the shape of the feed list, not by a rule. **Plan 23 row #6 breaks that link**: the desk becomes what the article says it is.

**And the failure is not the obvious one.** The obvious risk is a desk going empty. The measured risk is the opposite: **on a heavy-AI day, classification concentrates where feeds distributed.** Three AI-adjacent stories arriving on an Energy feed, a Business feed and a World feed are three desks today and one desk after plan 23 - so the five-desk digest becomes a one-desk digest with four thin rails, on exactly the day a reader most needs the other four. The ceiling is what stops it and the floor is what fills the gap it leaves.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The ceiling displaces to a second desk, not to the bin.** A ceiling with nowhere to put the overflow is a rule that shortens the day, which decision 1 of row #2 already forbids. Row #8 is the pressure valve and this row does not land usefully without it | Editor |
| 2 | **A floor never admits a story a gate refused.** `too_old`, `below_feed_floor`, a failed extraction and a failed summary all stand. A thin desk publishes thin and says why - the sentence already exists and `desk_ref` already carries the shortfall | Fowler; `backend/idhazh/assemble.py` |
| 3 | **Per-desk, not global.** `ai` has 35 feeds and a floor of 21 would mean something different there than on `india`. Both numbers sit beside `min_feeds` in `config/taxonomy.json`, where the desk's other bounds already are | `CLAUDE.md` Rule #6 |
| 4 | **The ceiling is a share of the day, the floor is a count.** A ceiling that is a count is a moving share - ten items is 3 percent of a 365-story day and a quarter of a 40-story one - and `rank.day_source_ceiling` already makes exactly this argument for the per-feed case. A floor is a count because a floor is about whether a desk is worth opening at all | `backend/idhazh/rank.py` |
| 5 | This row is **not blocked on plan 23**. It is built against whatever field names the desk | Section 0.4 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave it to the feed list, as today | The feed list stops guaranteeing it the day plan 23 row #6 lands, and a guarantee that depends on nobody changing an unrelated config file is not one | Fowler |
| 2 | Fill a thin desk from a previous day | It publishes yesterday under today's date. `lead_max_yesterday` already bounds the one place a previous day may appear, and it bounds it at one | Editor |
| 3 | Drop a desk from the row when it is thin | The desk exists in `config/taxonomy.json` and a reader who chose it yesterday would find it gone with no explanation. `desk_ref` and the thin-desk sentence exist so a thin desk can be shown as thin | Reader |

---

## 9. Row #8 - A story cross-files to a second desk

- **Scope:** A story carries one primary desk and at most one secondary. The ceiling's overflow lands on the secondary. The story is drawn once in the stream and counted on both desks.
- **Files touched:** `backend/idhazh/placement.py`, `backend/idhazh/contracts/article.py`, `backend/idhazh/contracts/digest_day.py`, `backend/idhazh/contracts/digest_view.py`, `schemas/article.schema.json`, `schemas/digest-day.schema.json`, `schemas/digest-view.schema.json`, `frontend/src/lib/payload/types.ts`, `backend/tests/test_placement.py`, `backend/tests/test_contracts.py`, `docs/concepts/placement.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/{test_placement,test_contracts}.py`, `GATE-SCHEMA`, `GATE-WEB`, `GATE-SUITE`, `GATE-DAYS`. Plus:
  - all three schemas carry today's `version` and a `changelog` entry;
  - the new field is **optional and absent reads as unknown**, because 8,550 committed items do not carry it and none of them is rewritten;
  - `frontend/src/lib/payload/types.ts` regenerates byte-identical.
- **Oracle:** **A story is in the stream once and on at most two desks, and every desk's `count` equals the stories that name it either way.** Asserted on a built day where three stories cross-file: `len(stream) == len(set(item_id))`, no item names more than two desks, and each `DigestVerticalRef.count` reconciles. **The count reconciliation is the half that catches the real defect**, which is a desk page showing 40 and listing 37.
- **What this row does not do:** it does not draw a second chip on the item. The eyebrow's cap is four and it is full (row #5). A story's secondary desk is why it appears on that desk's page; it is not a fact the item's own line prints.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **One secondary, never a list.** A story on four desks is a story on no desk, and the fourth chip is where a tagging system stops being editorial | Editor |
| 2 | **The stream is one order, so the story is drawn once.** Cross-filing changes which **desk page** a story is on, never how many times it appears in the day | Row #2 decision 3 |
| 3 | **The field is optional and an absent value reads as unknown**, never as "no secondary". Every plausible default is a claim about 8,550 items nobody made. This is the rule `layout.md` already states for the five rank fields | `CLAUDE.md` section 11; `docs/architecture/publishing/layout.md` |
| 4 | **The second desk comes from the same source the first does.** Today that is the feed's declared vertical, so the secondary is empty on almost every item and the ceiling's overflow has nowhere to go - **which is the honest state of this row until plan 23 row #6 lands**, and the row says so in `placement.md` rather than shipping a valve that is closed and looks open | Verified 2026-09-11 |
| 5 | A desk's `count` counts primary and secondary alike, because it is the count on the pill and the pill is a promise about what the desk page holds | Reader |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Duplicate the item under both desks in the payload | It doubles the story's bytes on the heaviest surface and makes read state, the leading block and every count ambiguous. Measured on the archive, the heaviest committed day already runs to 1.9 MB | Carmack |
| 2 | Let the ceiling drop the overflow | A rule that shortens the day, which row #2 decision 1 forbids and which a reader cannot see | Editor |
| 3 | Draw a second chip so the reader sees the cross-file | The eyebrow's cap is four at every width and it is full. A fifth fact takes a slot from the source name | Jony |

---

## 10. Row #9a - The placement terms on the counterfactual ledger plan 23 creates

- **Scope:** The plan stage records, for the candidates it scored, what each candidate's score would have been with each tunable **placement** term at zero. **It extends the ledger [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) row #21 creates; it mints no contract and no schema of its own.**
- **Depends on:** plan 23 row #21. Nothing may add a column to a ledger that does not exist.
- **Files touched:** `backend/idhazh/rank.py`, `backend/idhazh/cli.py`, `backend/idhazh/ledger.py`, `backend/idhazh/contracts/counterfactual_score.py`, `schemas/counterfactual-score.schema.json`, `backend/tests/test_ledger.py`, `docs/concepts/growing-reads.md`
- **`backend/idhazh/contracts/placement_counterfactual.py` and `schemas/placement-counterfactual-row.schema.json` are gone from this row, and the reason is arithmetic rather than tidiness.** Until 2026-09-11 this row minted a second counterfactual ledger beside plan 23 row #21's, writing **one row per candidate the run scored**. Plan 23 row #21 prices exactly that shape from a live replay: **4,843 candidates from 144 feeds on 2026-09-10, about 3.6 MB a day and 1.3 GB a year** - sixty times the whole of `state/` - and calls it a plan-sized mistake. This row also named no `retention.py` and added no prune, so it would have created an unbounded growing collection while plan 23's row bounded its own. **One contract, one schema, one ledger, one prune, and they are plan 23 row #21's**: every item the run took plus `lens_weights.counterfactual_refused_per_desk` refused candidates a desk, about 180 rows a run. The placement terms arrive as columns on that row. Found 2026-09-11; neither plan named it before.
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_ledger.py`, `GATE-SCHEMA`, `GATE-SUITE`. Plus:
  - `schemas/counterfactual-score.schema.json` carries today's `version` and a `changelog` entry naming the placement columns, **declared optional against the rows plan 23 row #21 has already written**;
  - the `docs/concepts/growing-reads.md` declaration plan 23 row #21 wrote is **extended with the wider row**, not duplicated.
- **Oracle:** **A candidate the run scored and did not publish carries a placement counterfactual as well as a lens one.** Asserted on a built pool where the safety ceiling cuts half the candidates: every scored candidate inside the bound appears, published or not, and each carries one counterfactual per tunable term of both kinds. **The unpublished half is the whole point** - a ledger of what published can only tell a loop that what it promoted got promoted, which is the runaway plan 23 row #17 decision 4 names.
- **What this row does not do:** it changes no score, moves no weight and reads nothing. It widens a row shape and writes.

### Why neither existing ledger can answer it

Verified 2026-09-11 by reading both headers. `state/scores/*.csv` carries 36 columns and is the **eval** ledger - one row per published item, about faithfulness. `state/item-health/*.csv` carries 29 columns and is the **cost and outcome** ledger - one row per attempted item. Neither carries a candidate that was never planned, and neither carries a score at any weight but the committed one. So a loop built on either would be reading its own past decisions, which is the runaway plan 23 row #17 decision 4 bans.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **One counterfactual ledger, and it is plan 23 row #21's.** `state/counterfactual-scores/<YYYY>/<MM>/<DD>.csv`, day-sharded through `backend/idhazh/day_partition.py`, bounded by config, with a prune in the commit that created it. This row adds columns | Fowler, 2026-09-11 |
| 2 | **It records; it decides nothing.** No stage reads it, no gate fails on it, and a run that cannot write it publishes anyway | Section 1a, degrade do not fail |
| 3 | **The pool is the bounded one, not every candidate.** Plan 23 row #21 decision 2 takes every item the run took plus the highest-scoring refused candidates in each desk - the ones sitting at the cut, where a weight decides. A weight change that would move an item outside that band is a change so large the step limit refuses it anyway. **An earlier draft of this row wrote a row for every candidate**, which is 4,843 a run and 1.3 GB a year | Plan 23 row #21; `CLAUDE.md` Rule #12 |
| 4 | The cost is bounded by config, never by the archive. It is written at plan time, where every candidate is already in memory and already scored | `CLAUDE.md` Rule #12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Widen `state/scores` with the counterfactual columns | It is the eval ledger, it has one row per **published** item, and widening it would put a placement fact in a faithfulness record. It is also `merge=union` under git, so a header migration cannot survive a rebase | Fowler; [`../docs/reference/agent-notes/git-and-github.md`](../docs/reference/agent-notes/git-and-github.md) |
| 2 | Recompute the counterfactual later from the published day | The pool is gone. The day holds what published, and the question is about what did not | Andre |
| 3 | Skip it and let a weights loop adapt on the outcome | That is the runaway: a term is rewarded for the stories its own bonus promoted, and it converges quietly on whatever it already preferred | Andre |
| 4 | **A second ledger of this plan's own, beside plan 23 row #21's** | Two contracts, two schemas, two prunes and two `growing-reads.md` declarations for one question, written by two rows that both edit `rank.py` and `cli.py`. The second one also had no prune and no bound. **This was the shape until 2026-09-11** | Fowler, 2026-09-11 |

---

## 11. Row #9b - RETIRED. The weights loop runs every run and has no person in it

**This row is deleted, and nothing replaces it in this plan.** It built `.github/workflows/placement-weights.yml`, `backend/utilities/propose_placement_weights.py` and `docs/how-to/tune-the-placement-weights.md`: a weekly workflow that read a bounded window of the counterfactual ledger, proposed placement weights and opened a pull request a person merged.

**The owner ruled otherwise on 2026-09-11**, of the sibling loop in [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) row #17: *"It should work automatically without human. Why weekly - this scoring should be every run."* That row was rewritten to run every run, with no pull request and no person in the loop, and its own rejected-alternatives table records the weekly shape as the thing it reversed - 52 pull requests a year against a pipeline that runs five times a day, and a staleness alarm invented for the queue it would build.

**Two loops adapting two weight sets on two cadences is two answers to one question.** Both read the same counterfactual ledger, both write `backend/idhazh/contracts/app_config.py` and `config/idhazh.json`, and one of the two cadences has been overturned. **Plan 23 row #17 is the loop that survives**; a placement weight it does not cover is a row somebody writes against its shape, not a second workflow. Found 2026-09-11.

**What the nine guardrails below are for.** They are an editorial ruling rather than a workflow detail, and deleting the row would delete them. **They bind plan 23 row #17 and any later row that moves a placement weight**, and they are kept here as the record of where they came from.

| # | Guardrail |
| --- | --- |
| 1 | The signal is **scarcity, not score** - a term earns weight where the day is short of what it names, never where it already wins |
| 2 | **A person sets the floor and the ceiling.** The loop moves inside them and cannot widen them |
| 3 | A weight moves **at most once a day** and by a **bounded step** |
| 4 | **A weight never moves during a run.** The day records the weights as they ran, and a weight that changed mid-run makes that record a lie |
| 5 | A weight **may reorder and may never admit** an item that failed a gate |
| 6 | **The day records every weight as it ran**, in the run manifest beside `rank_version` |
| 7 | **A retired lens stays at zero and the adapter may not raise it.** Retirement is a person's decision and an adapter that can undo it is not an adapter |
| 8 | **Breadth outranks the weight.** The desk ceiling of row #7 applies after every weight, so no proposal can produce a one-desk day |
| 9 | **A person can pin any weight**, and a pinned weight is skipped and named as pinned wherever the loop reports |

**Branch protection on `main` is still off, and it is still nobody's row.** The retired row named it: "permissions that permit a pull request and not a push" is not a thing GitHub's token model expresses, `contents: write` is what lets an action create a branch and the same scope lets it push to `main`, and the control that would actually stop a push is branch protection - a repository setting that interacts with `prune.yml`'s scheduled force-push (`CLAUDE.md` section 8's one exception). Section 18 carries it as a gap. **Plan 23 row #17 opens no pull request and runs no workflow of its own, so this plan adds nothing to that surface.**

---

## 12. Row #10 - The `assemble` consolidation

- **Scope:** One consistency model in `assemble`. The backend's ordering work stops being dead: the frontend draws the published order and `orderByTime` goes.
- **Files touched:** `backend/idhazh/assemble.py`, `backend/idhazh/cli.py`, `frontend/src/lib/server/payload.ts`, `frontend/src/lib/components/DigestList.svelte`, `frontend/src/lib/day-shape.ts`, `backend/tests/test_pipeline.py`, `backend/tests/test_same_story.py`, `backend/tests/test_leading_stories.py`, `frontend/tests/dated-day.spec.ts`, `frontend/tests/day-list.spec.ts`, `frontend/tests/day-seam.spec.ts`, `frontend/tests/reading-page.spec.ts`, `frontend/tests/readstate.spec.ts`, `frontend/tests/topic-day.spec.ts`, `frontend/tests/whole-day.spec.ts`, `docs/architecture/publishing/layout.md`
- **`orderByTime` has two callers in `src/` and is named in eight specs, so this row is wider than it looks.** Measured 2026-09-11: `git grep -ln orderByTime -- frontend/tests` returns `dated-day`, `day-list`, `day-seam`, `reading-page`, `readstate`, `time-rail`, `topic-day` and `whole-day`. **`time-rail.spec.ts` is not on this row's list because row #5 deletes it**, and the other seven are here because section 0.1 does not let a removal leave a test behind. A worker that finds a ninth widens the list freely: **group F holds this row alone** since row #9b retired on 2026-09-11.
- **Acceptance gates:** `GATE-PY` with `backend/tests/{test_pipeline,test_same_story,test_leading_stories}.py`, `GATE-WEB`, `GATE-BROWSER`, `GATE-SUITE`, `GATE-DAYS`, and the section 12 browser smoke. Plus:
  - `orderByTime`, its type `RailRow` if row #5 left it, and every one of its specs go in the same commit as its last caller (section 0.1);
  - the two writes `stage_assemble` makes 42 lines apart are either adjacent or the gap is documented with what a crash inside it now costs.
- **Oracle:** **The page draws the payload's order, unchanged.** Assert that the array `DigestList` renders is element-for-element identical to `day.items`, on the canary day and on a built day whose score order and time order differ - which is the case the archive cannot supply, because until row #3 they are the same order. It fails against the base tree, where `orderByTime` re-sorts.
- **What this row does not do:** it does not change the score, the caps or the desk rules. It removes the second order and resolves the two consistency models that produced it.

### The two consistency models, and which one wins

**`assemble` rebuilds parts of the day whole on every run** - `collapse_same_story` over every item, `leading_stories` over every item, `rebuild_search_index` over the whole month, `desk_ref` over every desk - **while the per-item work stays incremental**, guarded by `build_day`'s `already` set and `cli.already_published`. Two models in one function, and the docstring that explained the boundary was explaining something else (row #1).

**Incremental wins for the per-item work and whole-day wins for the passes**, and the arithmetic in section 0.3 is why: making the per-item work whole-day multiplies item-passes by 2.99 across a day and by 4.8 on the last run, which puts the worst shard 60 percent past its timeout. The passes stay whole-day because they are cheap and because a later run can publish a story an earlier one could not weigh. **What this row fixes is that the boundary is now stated in the code rather than inferred**, and that the whole-day passes stop producing an order nobody draws.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`orderByTime` is deleted, not left unused.** It has two callers and both go in this commit. A sort function left in `day-shape.ts` is the second order coming back | Section 0.1 |
| 2 | **The `already` set stays and its reason is now written down** (row #1). The gap between the day write and the ledger append is either closed or documented with its cost | Fowler |
| 3 | The whole-day passes stay whole-day. They are bounded by the day, and the day is bounded by the safety ceiling times the runs | Carmack |
| 4 | `payload.ts`'s seed comment is rewritten, not deleted: the head of the page order and the head of the published order are now the same thing, and the sentence saying they are not is what a later reader would design against | `CLAUDE.md` section 5 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | **Rebuild the day whole on every run**, so there is one model and no `already` set | The arithmetic, measured 2026-09-11 on the five runs of 2026-09-09 (73, 69, 73, 70, 75): item-passes go from 360 to 1,075, **2.99x**, and run 5 alone from 75 items to 360, **4.8x**. Against the worst shard on record that is 66.9 minutes to about **321**, which is 60 percent past the 200-minute timeout - and a shard that times out uploads no artifact, so the day publishes nothing rather than late | Carmack; section 0.3 |
| 2 | Keep `orderByTime` behind a flag while the new order is watched | Two orders and a flag deciding which, with nothing on the page telling a reader which they got. The fallback for a bad order is a config change and a re-publish, which takes one run | Fowler |
| 3 | Move the whole-day passes into a separate stage | They read the assembled day, so a separate stage reads it back off disk and re-validates it for no gain. The stage boundary that would help is the one row #9a's ledger already crosses | Carmack |

---

## 13. Row #11 - The console strip takes five tabs

- **Scope:** The console becomes five routes. `Judgement` and `Voices` join `Pipelines`, `Summaries` and `Hardware`; the strip holds five on a phone; and the band learns what an editorial fault is worth against a failed run.
- **Files touched:** `frontend/src/lib/components/ConsoleNav.svelte`, `frontend/src/lib/console/band.ts`, `frontend/src/routes/console/judgement/+page.svelte`, `frontend/src/routes/console/voices/+page.svelte`, `backend/idhazh/publish_console_band.py`, `backend/idhazh/contracts/console_band.py`, `backend/idhazh/cli.py`, `backend/utilities/build_canary_day.py`, `schemas/console-band.schema.json`, `tests/fixtures/contracts/console-band/newest-day.json`, `backend/tests/test_console_payloads_producer.py`, `frontend/tests/console-nav.spec.ts`, `frontend/tests/console-title.spec.ts`, `frontend/tests/console-band.spec.ts`, `docs/architecture/publishing/console.md`, `docs/concepts/ui-shell.md`. **Widened from thirteen to sixteen during execution (2026-09-12), and none of the three collides with row #14.** `cli.py` and `build_canary_day.py` hand the run's already-folded source-health rows to the band producer, which is what makes the third `Voices` candidate reachable without a second read; `ui-shell.md` carried the sentence "three prerendered routes", which this row is what makes false.
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_console_payloads_producer.py`, `GATE-SCHEMA`, `GATE-WEB`, `GATE-BROWSER`, `GATE-SUITE`, and the `CLAUDE.md` section 12 browser smoke. Plus, in this row:
  - `schemas/console-band.schema.json` carries today's `version` and a `changelog` entry naming the two new route ids;
  - both new routes answer 200, carry their own heading and print a named absence - **a tab in a strip whose page does not exist is a strip that lies**, and rows #12 and #13 land later;
  - **no page ceiling is added.** `page_weight.ceilings_bytes` has named only `/404` and `/evals/` since 2026-09-10, because the four it used to name grew every time the pipeline published. The two payload directories are priced under `payload_ceilings_bytes` by rows #12 and #13, beside `console/band.json` at 2,000 B.
- **Oracle:** **Five tabs stand on no more than two rows at 1440px and no more than three at 360px, and no tab's box overlaps another's.** Geometric, read off the built page rather than off the rule. **Corrected 2026-09-12: this row said "at the widths `console-nav.spec.ts` already drives" and that spec drives none** - it had no `setViewportSize` call at all, so the two widths are added by this row. **A third width, 320px, was added on measurement**: the basis that cleared 360 still stacked five deep there, which is the same defect one screen narrower. **It fails against the base tree in both directions**: three tabs cannot produce five boxes, and five tabs at the committed basis produce five rows on a phone rather than three.
- **What this row does not do:** it draws no panel, and it opens no file the pipeline does not already open. **Corrected 2026-09-12: it said "reads no ledger the console does not already read", which read as a ban on the `Voices` candidate that needs a judged-item count.** The count is on the source-health view, which `cli.py` folds 78 lines before it publishes the band and `build_canary_day.py` folds for the canary, so handing those rows over costs one parameter and no second read.

### The geometry, and the basis is the thing that moves

`.tab-slot` is `flex: 1 1 14rem` and `.tab-line` is the description under each label (`ConsoleNav.svelte`, verified 2026-09-11 and again 2026-09-12). **A 14rem basis is 224px at a 16px root** - `app.css` sets no root size, so it is the browser's 16px - so on a 360px phone one tab fills the row and five tabs stack five deep, directly above the band, which is the first thing an operator reads. Three tabs already cost three rows there, and the component's own comment records that as why its padding is charged three times.

Two changes, about six lines. **Drop `.tab-line` below the wide breakpoint**, and **cut the basis**. **Both numbers this section proposed were wrong and both were corrected by measuring the built page on 2026-09-12.**

| Proposed | Shipped | What the measurement said |
| --- | --- | --- |
| basis `9rem` (144px) | **`8rem`** (128px) | `9rem` cleared 360 and still stacked **five deep at 320px**, the narrowest screen still in use - the same defect one screen narrower. `8rem` puts two in the 288px content box of a 320px phone |
| line hidden below `40rem` | **shown from `1024px`**, the breakpoint three other components already use | At the narrow breakpoint the strip was **168px at 800px against 86px at 768px**, so widening the window made the chrome taller. At 1024 each tab is 186px and the line costs 50px once, then falls back as the tabs widen |
| "three rows at 360 and **two at 390 and above**" | three rows at 360, 390 and 414; **two from 480**; one from 768 | 390 has a 358px content box and three tabs need 400px, so 390 is three rows, not two |

Measured 2026-09-12 off the built page in headless Chromium, `window.innerWidth` read inside the page: 320 -> 3 rows, strip 215px. 360 -> 3, 199. 414 -> 3, 199. 480 -> 2, 162. 640 -> 2, 138. 768 -> 1, 86. 900 -> 1, 86. 1024 -> 1, 136. 1440 -> 1, 80, five boxes of 269px at one top with no overlap.

**The description is not lost.** It is already the anchor's `title`, and the page it opens prints it in full. What a hidden line costs is the one-line summary a reader gets before choosing, which is what the label has to carry instead - and that is why the labels are one word each.

### The severity an editorial fault is worth

`band.ts` ranks a route's worst state `BROKEN` 3, `WORTH_A_LOOK` 2, `WORTH_KNOWING` 1, `CLEAR` 0, and `publish_console_band.py` writes the same four numbers. The band prints the one worst thing across every route, so a new route with a loud rule would take the band away from a failed run.

**A `Judgement` or `Voices` fault caps at `WORTH_A_LOOK`.** A skewed day still published; a failed run did not.

**One exception, at `BROKEN`: a decline rate at either end on any gating kind.** That is not a skew. **Zero** means a gate that never declines - a classifier stamping everything it is shown - and **one** means a gate that declines on everything, which is the same instrument reading dead from the other side. Both make every other figure on the tab fiction, including the figures a reader would use to decide the day was fine. **The rule is two-sided because the failure is**: the row carried only the zero end until 2026-09-11, and a classifier that had stopped answering would have printed a reassuring tab. The two bounds are `console.decline_rate_floor` and `console.decline_rate_ceiling` with sane defaults, because a bare 0 and a bare 1 are thresholds in code (`CLAUDE.md` Rule #6). **They land in `config/idhazh.json` under row #12, not this row, and the reason is group G**: row #14 already writes `config/idhazh.json`, `backend/idhazh/contracts/app_config.py` and `schemas/app-config.schema.json`, so adding them here would put three files on both sides of this pair. Row #12 is a singleton, already edits all three, and is the row that draws the fractions. **This row encodes the rule in `publish_console_band.py` and reads the two keys through their defaults until row #12 commits them**, which costs nothing because the fraction itself is `null` until plan 23 row #10 lands. The fraction arrives with plan 23; this row encodes the rule and the producer writes `null` until it does.

### `Voices` has a worst state too, and these are its candidates

**A tab with no worst state on its label is the thing `console.md` warns about in its own words**: *"Without it a route is where a metric goes to die: nobody opens a page to find out whether it was worth opening."* The rule above caps `Voices` at `WORTH_A_LOOK` and then names nothing for it to be in, so the label would read `Voices` for ever. The page already sets the precedent for what to do instead - it lists `Machine`'s three candidates by name and says which is ranked lowest and why - so `Voices` gets the same treatment here rather than in row #13.

| Rank | Candidate | Why it is at this rank |
| --- | --- | --- |
| `WORTH_A_LOOK` | **A feed sitting at `collect.reliability_floor`** - the multiplier clamped at 0.5, which is as far down as it goes | It is the one state where the ranker is actively discounting a feed and nothing on any page says so. It is also the panel row #13 exists to draw, so a label that never points at it points at nothing |
| ~~`WORTH_KNOWING`~~ | ~~**The count of feeds that answered nothing in the window**~~ - **DROPPED 2026-09-12 on measurement** | A feed that answered nothing scores zero productive reads, which `feed_reliability` clamps to the floor - so it is a **strict subset** of the row above and `worst_of` could never surface it. Read off the committed tree that day: 15 feeds sit at the floor and 14 of them answered nothing. Redefining it as the feeds not read at all was refused too, because that is the same predicate `FeedTrouble.unread` already carries on Pipelines. The count becomes a figure row #13 draws, which is where this section's own closing paragraph already put it. Authority: Susan, 2026-09-12 |
| `WORTH_KNOWING` | **A feed below `collect.source_yield_alarm_min_decisions`** - under 30 addresses it decided, so its quality figures print a dash | Row #13 draws a dash for it and a dash is invisible at a glance. It is ranked below the floor case on purpose: too little evidence is not the same as bad evidence, and ranking it higher would publish a judgement the record cannot carry. **The denominator is `SourceHealthRow.decisions` and never `opportunities`** - a model that would not answer, a rate limit and a robots refusal all cost an opportunity and none is the publisher's doing |

**The label carries a count where the state has one, and this section said the opposite.** It read "the label never carries a count", which is false about the surface it describes: all eleven candidates already shipped carry a count or a ratio, and the committed band prints `18 feeds resting` and `28 items failed`, both normally non-zero. What it would have cost is `Voices` alone among five tabs naming a state and not its size, so an operator could not tell one feed at the floor from fifteen without opening the page - which is the one thing a worst-state fragment exists to prevent. The fragment carries its denominator with it (`68 of 151 sources too thin to judge`, not `68`), and rank is what stops the large number shouting: the at-floor candidate outranks it, so it only reaches the label on a day nothing worse is true. Corrected 2026-09-12; authority: Susan.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Five routes, still real anchors, still no hidden panels.** `console.md` records why the strip is anchors rather than script-driven tabs, and nothing about a fourth or fifth route changes that argument | `docs/architecture/publishing/console.md` |
| 2 | **The strip still never takes the health ramp.** A route is a noun. `console-nav.spec.ts` reads the computed style of every tab and fails on any of the six verdict tokens, and it now reads five | `docs/architecture/publishing/console.md` |
| 3 | **`Judgement` is singular, and the singular is the ruling.** The other three name a place; this one names an act. `Judgements` would be a count of things and the tab is not a list | Susan, 2026-09-11 |
| 4 | **`Voices` over `Sources`, by owner override.** Susan proposed `Sources` and her reasoning is in the Rejected alternatives below, recorded rather than re-argued | Owner, 2026-09-11, `CLAUDE.md` section 0 |
| 5 | **The two new routes are opened empty by this row.** A strip that names a page nobody can reach is worse than three tabs, and the alternative - landing the strip with its two tab rows - would put three rows on `ConsoleNav.svelte` in one group. **Each empty route names the row that fills it**, so a reader of the strip can find the specification: `Judgement` points at row #12 and at plan 23 row #15, `Voices` at row #13 | Section 1 |
| 6 | **An editorial fault caps at `WORTH_A_LOOK`, with one `BROKEN` exception.** Stated above, and the producer is where it is enforced, because the band is derived once and read everywhere | Carmack; `backend/idhazh/publish_console_band.py` |
| 7 | **`Voices` has its own worst-state candidates, named here and not in row #13.** The band is derived once in the producer this row already edits, so the ranking belongs beside the cap rather than one group later, and a tab whose label is always the same word is the failure `console.md` names. **The two decline bounds the `BROKEN` rule reads are row #12's config keys**, for the group-G reason stated above; this row adds no file to its list | Susan, 2026-09-11; `docs/architecture/publishing/console.md` |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | **`Sources` rather than `Voices`.** Susan's case, verbatim in substance: `Voices` appears nowhere in this repository, `Publishers` is false for part of the set, and the project's own word is already `source_id`, `config/sources.json` and `source-health.json` | **Overridden by the owner on 2026-09-11.** The reasoning stands and is recorded here rather than deleted. **One of its numbers was wrong and the correction is worth keeping**: the 103 and the 139 are **published items** carrying `source_kind: government` and `source_kind: community` over the 21 finished days, not entries in a source list. The address list is 151 feeds - 40 institution, 100 trade press, 11 community (measured 2026-09-11). `Publishers` is still false, for a smaller set than the number suggested | Owner, 2026-09-11; measured |
| 2 | Fold `Hardware` into `Pipelines` to keep the strip at four | It would undo a split that already happened for the reason this plan is repeating - a route answering three questions answers none of them first. Nothing folds | Section 15 |
| 3 | Put the two new tabs behind a `More` disclosure | A disclosure is where a control goes to be forgotten, and the two tabs being added are the two an operator has never been able to open at all | Susan |
| 4 | Let a `Judgement` fault take the band at `BROKEN` | Then a skewed day and a failed run print the same sentence, and the band stops being the thing that answers "did it work" | Carmack |

---

## 14. Row #12 - `Judgement`, what the model made of each article

- **Scope:** The fourth tab. **What the model made of each article, how sure it was, and where it disagreed with us.** Eight panels and one line, and the third clause is the reason the tab exists.
- **Files touched:** `frontend/src/routes/console/judgement/+page.svelte`, `frontend/src/routes/console/judgement/+page.server.ts`, `frontend/src/lib/console/judgement.ts`, `backend/idhazh/publish_console_judgement.py`, `backend/idhazh/contracts/console_judgement.py`, `schemas/console-judgement.schema.json`, `tests/fixtures/contracts/console-judgement/newest-day.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_console_judgement.py`, `backend/tests/test_contracts.py`, `backend/tests/test_marks.py`, `frontend/tests/console-judgement.spec.ts`, `docs/architecture/publishing/console.md`, `docs/architecture/publishing/console-payloads.md`, `docs/architecture/publishing/console-charts.md`, `docs/concepts/console-design.md`
- **Depends on:** row #11, and **plan 23 row #14**. See the section below.
- **Acceptance gates:** `GATE-PY` with `backend/tests/{test_console_judgement,test_contracts,test_marks}.py`, `GATE-SCHEMA`, `GATE-WEB`, `GATE-BROWSER`, `GATE-SUITE`, and the section 12 browser smoke. Plus, in this row:
  - both schemas carry today's `version` and a `changelog` entry;
  - `config/idhazh.json` gains a `payload_ceilings_bytes` entry for the tab's own payload directory, and `npm run bundle-gate` holds it;
  - **the page renders complete with its payload directory emptied**, which is the oracle below run as a gate;
  - **no string on the tab uses the word "confidence" bare** (decision 6), asserted by the spec over the rendered text.
- **Oracle:** **Every panel that cannot be computed says which figure is missing, by name, and the page logs no error and no 404.** Driven by pointing the route at an emptied payload directory in the browser and reading the page console. **A panel that white-screens on missing data fails on exactly the day an operator most needs it**, and on this tab that is not a hypothetical: every figure it draws is produced by plan 23, so **the honest state on the day this row lands is that most of them are absent**.
- **What this row does not do:** it computes no classification, fills no decline fraction and changes no score. Plan 23 produces every figure here.

### The relationship with plan 23, stated rather than left to collide

**Plan 23 carries a console row for the same surface, and until 2026-09-11 the two rows disagreed about the route id, the producer, the contract and the payload.** Both cannot create one route. The rule, so whichever is dispatched first can act without asking:

| Piece | Owner | Address |
| --- | --- | --- |
| The route and the page | whichever row lands first creates it, the other extends it | `frontend/src/routes/console/judgement/` |
| The producer | **this row** | `backend/idhazh/publish_console_judgement.py` |
| The contract and its schema | **this row** | `backend/idhazh/contracts/console_judgement.py`, `schemas/console-judgement.schema.json` |
| The payload directory and its `payload_ceilings_bytes` entry | **this row** | `frontend/public/console/judgement/`, `config/idhazh.json` |
| The instruments module | whichever row lands first creates it, the other extends it | `frontend/src/lib/console/judgement.ts` |
| The spec | shared, extended by each | `frontend/tests/console-judgement.spec.ts` |
| The classification figures the panels draw | plan 23 row #15 supplies them; this row draws them | - |

- **The address is `/console/judgement/` and the label is `Judgement`.** **Owner ruling, 2026-09-11**: `judgement` wins, and plan 23 row #15 was re-addressed to it in the same pull request that recorded this - its decision 6.
- **The producer, the contract and the schema are this row's, ruled 2026-09-11.** Plan 23 row #15 published the tab from `backend/idhazh/publish_day_metrics.py` with no new contract. **A tab payload is not day metrics**: the day-metrics record answers "what did this day look like" and a console tab's payload answers "what does this page draw", and folding the second into the first would put a panel's shape inside a record four other rows of plan 23 already write. Plan 23 row #15 decision 6a records the same ruling from the other side.
- **This row depends on plan 23 row #14**, which writes the classification ledger and the day roll-up every panel here reads. The scope section already says most of the figures are absent on the day this row lands; the dependency is what makes that a schedule fact rather than a warning. **An earlier draft had no dependency at all**, and section 0.4 said nothing in this plan was blocked on plan 23 while this row's own text said its figures were not there.

This was recorded here rather than in plan 23 because a worker may not edit another plan's doc mid-flight; the owner's ruling lifted that, and both plans now carry it. It is also a **cross-plan** collision rather than a within-group one, so section 1's disjointness rule does not catch it and nothing else would.

### The panel set, ruled by Susan on 2026-09-11 with the owner amending two

| # | Panel | Shape | Why |
| --- | --- | --- | --- |
| 1 | **The political gate, as three decline fractions** - `opinion`, `analysis`, government `announcement` | three figures, each with its denominator beside it | **It leads the tab.** It is the number that says whether the intelligence is real or flattering itself. Every other figure on the page is downstream of a classifier that might be stamping |
| 2 | **Declared against read** | **two grids: 5 by 5 for the desk, 6 by 5 for the kind.** The diagonal is drawn at low weight and **only the off-diagonal is tinted** | Put the diagonal in the colour scale and it is one bright stripe with the interesting cells invisible beside it. The disagreement is the instrument |
| 3 | **Lens firing rate** | **one diverging bar per lens** - keyword-only left, model-only right, agreed as a centre block - **ordered by total**, with **the lens's weight printed as a word at the row end** | A grouped bar loses the sign and the sign is the meaning. The weight at the row end is what makes the measured finding legible: **the four lenses at weight 0.0 fired 2,343 times against 650 for the two that carry weight, 3.6 times as often** (section 0.3). They tag an article and move no story, and a reader of this row can see that without doing arithmetic |
| 4 | **Label confidence** | a histogram, and the owner's override in the section below decides what goes in it | Kept |
| 5 | **Sentiment states** | **four counts on one row - positive, negative, judged-and-neutral, and not judged - with the not-judged count drawn immediately beside judged-and-neutral and in the same type** | Kept, and now specified. `a panel` was the whole entry until 2026-09-11, which is not a shape. **The two neutral-looking states are the point**: plan 23 row #11's oracle exists to stop judged-and-neutral and not-judged being the same pixel on a reader's page, and a console that puts them at opposite ends of a row undoes that on the operator's. They are adjacent, and the gap between them is the figure worth reading. The kappa that used to sit here is one line (decision 5) |
| 6 | **Viewpoint** | **five rows, one per stance field: two opposed poles about a balance point, with that field's own `not_applicable` count printed beside it** | The highest-stakes drawing on the console. Its own section below |
| 7 | **Events** | a `RankedList` | Kept. It is a ranking, and `RankedList` is what this console draws a ranking with |
| 8 | **Watchlist entries the day did not reach** | a short list, ranked by how long since each last fired | Replaces the entities panel. See below |
| 9 | **Proposed verticals** | **one line, not a panel** | A count that is normally zero does not earn a frame |

**Folded, not dropped.** The day-made-of-five-kinds panel folds into the declared-against-read kind grid, and keyword-only-against-model-only folds into the lens diverging bar. **Susan found the owner's paired bar cannot be drawn at all**: the model produces five kinds and the feed declares six, the declared set adding `government` and `community` and holding no `opinion`, so **three of eleven values have no counterpart** and a paired bar would pair them with nothing. The grid has a cell for every pair and a row and column for the three that stand alone.

**Refused from this tab: the desk mix against its floor and its ceiling.** It is an editorial knob rather than a judgement the model made, so it goes to `Pipelines` as one `TargetBar` per desk. **Row #14 ships it**, because a `TargetBar` needs a threshold to mark and row #14 is the row that owns the target.

### The contract carries a field for every figure, and that is what makes the panel set checkable

**Plan 23 row #15 names three charts, twelve numbers and one generated sentence; this row writes the contract those arrive in.** Until 2026-09-11 that sentence was the whole specification on both sides: plan 23 counted twelve and listed nine, and this row's contract was described by its panels rather than by its fields. **A figure with no field is a figure the page cannot draw**, because this tab's producer reads the day file and never a shard (plan 23 row #14's oracle).

So `backend/idhazh/contracts/console_judgement.py` carries, at minimum:

- **One field for each of the twelve numbers plan 23 row #15 now enumerates**, by the same names, each **optional with an absent value reading as not computed** - never zero, because most of them are absent on the day this row lands and a zero decline rate is the `BROKEN` state of row #11's band.
- **One field per chart**: the 5 by 5 desk grid, the 6 by 5 kind grid, and the per-lens diverging bar's three parts.
- **One field per panel above** that is not already covered - the sentiment four-count row, the five viewpoint rows with their five `not_applicable` counts, the events ranking, the quiet-watchlist list, and the proposed-vertical count.
- **`headline_sentence`**, a string that is never null and never empty (below).
- **`logprob_mode`**, stamped on the confidence panel, so a reader knows which decode produced the figure.

**A contract test asserts every panel the page draws has a field and every field has a panel.** Neither half is decoration: a field with no panel is a number nobody reads and a panel with no field is the white screen the oracle exists to prevent.

### The generated sentence, and it is a field rather than a flourish

**One sentence, at the top of the tab, above the political gate.** Plan 23 row #15 specifies what it computes, its wording template and its empty states; this row carries it as **`headline_sentence`** and draws it. Three properties bind here:

- **It is computed in the producer, never in the browser.** Two derivations of one verdict is two verdicts - the rule `band.ts` already establishes and row #13 decision 4 restates.
- **It is never null and never empty.** Where nothing is out of bound it says so; where figures are absent it counts them. A sentence that disappears when the news is good is a sentence a reader stops looking for.
- **It carries no adjective and no verdict word.** The figure and its bound, which is what `console-design.md` requires of every other string here.

**`Voices` gets one too, on the same rule and in row #13.** A generated sentence on one of two new tabs is a pattern half-introduced, and the next person has to guess whether it was deliberate.

### The watchlist panel, and the measurement that shaped it

**A ranked list of named organisations is a different kind of claim from a count of `release` events**, so the entities panel is refused in that form. What replaces it is the silence: **watchlist entries the window did not reach.**

**Measured 2026-09-11, that list is empty.** The `entities` field starts on 2026-08-27, so the record is 15 finished days, and over 7, 14 and 15 days **all 30 active entries fired**. The quietest are `asml` at 10 items, `adani` 14, `ftc` 25, `mistral` 28, `iea` 30. So the panel as the ruling words it would print its empty state every day.

**That is not a reason to drop it and it is a reason to shape it.** The console already carries one counter expected to read zero - `Too long to send` - and says in its own words why: it is on the page so that the day the cap moves, the number that catches it is already being printed. This panel is the same shape. **It ranks by how long since each entry last fired and always draws the quietest few with their counts**, so it is never blank, and its alarm state is a non-empty silent list.

`watchlist_hit` cannot drive it: it is a **boolean**, true on 1,066 of 8,550 items - 12.5 percent - and it says that something matched, never what. The `entities` list is what names the entry.

### The viewpoint panel, and it is the highest-stakes drawing on this console

**The hazard, stated in the row so no worker has to rediscover it.** *The digest is 60 percent progressivism* is a claim about **the world**, not about this pipeline, and a chart that can be read that way will be screenshotted out of the page that explains it. **The drawing has to make that reading impossible**, and no caption can do that job - a caption does not travel with an image.

**The vocabulary this panel draws, re-derived 2026-09-11, because the design below was written against one that no longer exists.** Plan 23 row #10 ships **five independent fields, each with two poles and its own `not_applicable`** - ten poles in all, not eight values in one field - and its **decision 3 folded `none` and `undetermined` into that single `not_applicable` per axis**, because five axes each carrying two decline values was ten ways to say nothing. **This row named `none` and `undetermined` in four places, including its own oracle, and "a ranked bar of eight" in two.** Neither vocabulary exists. The design below is the same design against the words that do.

**The five rows, and the panel is nothing else.**

| Row | Left pole | Right pole | Printed beside it |
| --- | --- | --- | --- |
| `stance_on_change` | `conservatism` | `progressivism` | its own `not_applicable` count |
| `stance_on_economic_power` | `socialism` | `libertarianism` | its own `not_applicable` count |
| `stance_on_state_power` | `statism` | `constitutionalism` | its own `not_applicable` count |
| `stance_on_borders` | `nationalism` | `internationalism` | its own `not_applicable` count |
| `stance_on_personal_sphere` | `civil_libertarianism` | `communitarianism` | its own `not_applicable` count |

**The four rules that make the screenshot reading impossible**, and they are rules rather than a caption because a caption does not travel with an image:

1. **No row may be summed with another.** The five are independent fields; nothing stacks, nothing shares an axis, and no total is drawn anywhere on the panel.
2. **Every row prints its own `not_applicable` count, on the row, always.** That number is the denominator: it says how much of the day the question was not asked of. A pole drawn without it is a share of an unstated set, which is the one drawing that can be screenshotted into a claim about the world.
3. **No row is ranked against another**, by size or by anything else. Ranking implies one scale across five questions.
4. **The axis is counts, not shares.** A percentage invites the sum that rule 1 forbids.

**What the panel refuses to draw, listed so nobody adds one back:** a ranked bar over all ten poles; a stacked bar of any kind; a single "lean" figure for the day; a trend line over days; a share that omits `not_applicable`; and any total, anywhere.

**Its empty state, and it is the ordinary state on the day this row lands.** Where a field has no data at all, **the row still draws** - both pole labels, the balance point, and the words `not measured` where its counts would be. Where the gate closed on every item, the row draws with `not_applicable` at the full count and both poles at zero, which is a true and useful picture rather than a blank. **The panel never renders fewer than five rows**, because a missing row reads as a question nobody asked rather than a question with no answer yet.

**Its own oracle: every one of the five rows prints its own `not_applicable` count in every state the panel can render, including the empty one.** A pole with no denominator beside it is the defect this panel exists to avoid, and a test that only checked the poles would pass on the day the denominator stopped rendering.

### The confidence panel is drawn, and the noise is taken out of it

**Susan ruled the panel should refuse to draw under `logprob_mode = post_mask`.** A grammar-constrained decode reports 1.000 at any position the grammar narrows to one token, so the histogram piles at 100 percent and means nothing.

**The owner overrode it on 2026-09-11**: we surface the correct signal so it can be read correctly, and failing to is a failure of charting rather than a reading problem. So the row works out how to separate the signal from the noise, and plots it.

- **Plot the figure plan 23 row #9 records: the product of the renormalised probabilities over the label's whole span, where a position the grammar left no choice at contributes exactly 1.000.** A forced position carries no information and is the entire source of the pile-up; because it multiplies by one, it drops out of the product rather than having to be excluded from it. **This bullet said \"the probability at the discriminating position\" until 2026-09-11**, and plan 23 row #9 retired that rule on the same day: measured against the pinned model, four of its vocabularies have no position where the grammar's legal set maps one-to-one onto the labels, because a one-letter token fits two of their values.
- **Show beside the histogram the count and the share of labels whose `contested_positions` is zero** - the ones the grammar left no choice at anywhere in the span. That number is itself a finding about the vocabulary: a label the grammar could only reach one way was never a choice. It reads straight off the ledger column plan 23 row #14 carries; nothing here recomputes it.
- **Stamp `logprob_mode` on the panel**, so a reader knows which decode produced the figure.
- **The axis is in whole percent.** `console-design.md` forbids a value between zero and one reaching the screen.
- **The median and the 5th percentile rule over the values, never a mean and never read off a bar.** A mean over a renormalised distribution is pulled by the forced-adjacent positions that survive the filter, and a percentile read out of a bin is a guess at where inside it the value fell.

**Its own oracle: a run where the grammar forced every position produces no histogram and one number**, and the panel says so by name rather than drawing an empty frame. Driven from a built fixture, because a decode where every position is forced is a case the archive cannot supply.

**`logprob_mode` does not exist in the tree** - verified 2026-09-11, `git grep logprob` finds it only inside plan 23's text. So this panel is designed against a field plan 23 creates and prints its named absence until it does.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The political gate leads the tab.** It is the only figure that says whether every other figure means anything | Susan, 2026-09-11 |
| 2 | **The tab is `Judgement`, singular.** The other three name a place; this one names an act | Susan, 2026-09-11 |
| 3 | **The confidence panel is drawn, by owner override.** The design is in the section above and this row implements it | Owner, 2026-09-11, `CLAUDE.md` section 0 |
| 4 | **The viewpoint panel is five rows, one per stance field, each with its own `not_applicable` count printed beside its two poles.** Never a ranked bar over the ten poles, never a stack, never a total. The section above is the whole reason, and it is written against the vocabulary plan 23 row #10 ships - **this decision named `none` and `undetermined` until 2026-09-11 and plan 23 row #10 decision 3 folded both into one `not_applicable` per axis** | Susan, 2026-09-11; owner; corrected 2026-09-11 |
| 5 | **Kappa is one line, not a chart.** It is measured once over 60 items and never moves, so a chart where a sentence would do. **It stays on the console rather than in a pull-request body, because the day it fires it should fire in public** | Susan, 2026-09-11 |
| 6 | **The tab never uses the word "confidence" bare.** `band` - high, medium, low - is already on every published item and `/console/model/` already draws its low count as `Marked "not sure"`. Measured 2026-09-11: high 4,993, medium 2,275, low 1,282 over 8,550 items. This tab's figure is **label confidence** in every string, and the spec asserts it | Susan, 2026-09-11 |
| 7 | **No chart on this tab is stuffed into `Summaries`.** That route is about a published summary and every figure here is about a label | Owner, 2026-09-11 |
| 8 | Every panel that cannot be computed prints **which figure is missing, by name**. Most of them cannot on the day this row lands | `CLAUDE.md` section 1a, degrade rather than fail |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A paired bar of declared kind against read kind | **It cannot be drawn.** Three of eleven values have no counterpart. Susan found it; the grid is what replaces it | Susan, 2026-09-11 |
| 2 | A separate panel for the day's five kinds | It is the kind grid's own column totals, drawn twice. A fact stated twice on one screen reads as two facts | `docs/concepts/console-design.md` |
| 3 | A separate panel for keyword-only against model-only | It is the diverging bar's two sides, and splitting them loses the comparison that is the point of it | Susan, 2026-09-11 |
| 4 | A ranked list of named organisations | It is a different kind of claim from a count of events, and the tab already carries the count | Susan, 2026-09-11 |
| 5 | The desk mix against its floor and ceiling, on this tab | An editorial knob is not a judgement the model made. It goes to `Pipelines` under row #14 | Susan, 2026-09-11 |
| 6 | A kappa chart | One number that is measured once and never moves. A chart there claims a series that does not exist | Susan, 2026-09-11 |

---

## 15. Row #13 - `Voices`, who supplied the day and what it is worth

- **Scope:** The fifth tab. **Who supplied the day, how often they answer, and what that is worth to the ranking.** The feed half of `Pipelines` moves onto it, and `ledger.reliability` is drawn for the first time.
- **Files touched:** `frontend/src/routes/console/voices/+page.svelte`, `frontend/src/routes/console/voices/+page.server.ts`, `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/+page.server.ts`, `backend/idhazh/publish_source_health.py`, `backend/idhazh/contracts/source_health_view.py`, `schemas/source-health-view.schema.json`, `tests/fixtures/contracts/source-health-view/four-facts.json`, `config/idhazh.json`, `backend/tests/test_publish_source_health.py`, `frontend/tests/console-sources.spec.ts`, `frontend/tests/console-feeds.spec.ts`, `frontend/tests/console-source-cuts.spec.ts`, `frontend/tests/console-voices.spec.ts`, `docs/architecture/publishing/console.md`, `docs/architecture/publishing/console-payloads.md`, `docs/architecture/publishing/console-charts.md`, `docs/concepts/console-design.md`, `docs/architecture/sources/health.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_publish_source_health.py`, `GATE-SCHEMA`, `GATE-WEB`, `GATE-BROWSER`, `GATE-SUITE`, and the section 12 browser smoke. Plus, in this row:
  - `schemas/source-health-view.schema.json` carries today's `version` and a `changelog` entry naming the new field;
  - **`headline_sentence` is present and non-empty on every built payload**, including one built from an empty window (decision 8);
  - **the moved panels keep their own specs**, renamed rather than rewritten, and `Pipelines` keeps none of them (section 0.1, no prisoners);
  - `config/idhazh.json` gains a `payload_ceilings_bytes` entry for the tab's payload.
- **Oracle:** **Every source panel is on exactly one route, and the reliability factor the page draws equals the one the ranker used.** Two halves, **both driven from the canary build and from built feed-health rows, never from the committed ledger** (Rule #12). The first counts each moved panel's own data attribute across all five built routes and asserts one. The second re-derives `feed_reliability` over the rows the payload was built from and holds the drawn value to it, to three decimal places. **The second half is the one that matters**: a console figure that is a second derivation of a ranking factor is two verdicts, and the day they disagree neither is trustworthy.
- **What this row does not do:** it changes no feed score and writes no new ledger. `ledger.reliability` is read.

### The fifth tab is a split, not an addition

**`Pipelines` answers three questions today** - did the runs work, which feeds broke, and what each stage cost - and its own route description says exactly that. **The feed half is already four panels**: `Four facts about every source we may ask`, `Sources cut short most often`, the failure list, and the clean-read count under it. Moving them leaves `Pipelines` answering one question.

**So `Voices` costs one new panel and one new persisted field, not six.** The new panel is the reliability factor. The new field carries it onto the published source-health view so the page reads the producer's number rather than computing a second one.

### The panel nobody has ever seen

**`ledger.reliability` is the only self-adjusting number in this project and it is drawn nowhere.** It is the per-feed multiplier the ranker applies to authority, recalculated every run from the trailing `collect.reliability_window_days` - 30 - of feed health, clamped to `[collect.reliability_floor, 1.0]` - `[0.5, 1.0]` - and reading 1.0 for a feed with no evidence in the window. It writes nothing to `config/` and it lives for the length of one run.

**Verified 2026-09-11: no file under `frontend/` reads it.** `frontend/src/lib/feed-health.ts` exports a function of the same name and it is a different quantity - a clean-read census over feeds, returning `clean`, `checked`, `failed`, `ineligible` and `runs`. Two things called reliability, one drawn and one invisible, and it is the invisible one that moves a story up the page.

**It is the panel that makes the tab worth having**, and it is a `TargetBar` per feed: the track at 1.0, the fill at the factor, and the marker at the floor, which is the same shape the truncation cap and the quarantine threshold already draw with.

### A lean needs a denominator, and a thin one gets a dash

**A feed under about 30 judged items shows a dash, not a lean.** A lean computed on four articles is a libel with axes.

The threshold is **config, and the project already has the number**: `collect.source_yield_alarm_min_decisions` is 30 and it exists for exactly this - a per-source figure that may not be read as a rate until the source has decided enough. This row reuses it rather than minting a second 30.

**The item count sits beside every quality figure**, which is the console's own standing rule and not a new one.

**A single combined quality score is refused.** `Pipelines` already argues this for source health, in its own words on the page: *a single score across the four would tell you something is wrong and nothing about what to do.* Four facts stay four facts.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`Voices`, by owner override.** Susan's case for `Sources` is recorded under row #11 | Owner, 2026-09-11 |
| 2 | **A split, not an addition.** The four feed panels move; `Pipelines` keeps none of them, and its route description loses the feed clause | Editor |
| 3 | **Nothing folds.** Folding `Hardware` into `Pipelines` to keep the count down would undo the split of 2026-08-30 for the same reason this row is making one | Editor; `docs/architecture/publishing/console.md` |
| 4 | **The reliability factor is published on the source-health view, not recomputed in the browser.** Two derivations of one verdict is two verdicts, and the console already learned this when the band moved to a producer | `frontend/src/lib/console/band.ts` |
| 5 | **A feed under `collect.source_yield_alarm_min_decisions` judged items prints a dash.** Reusing the existing 30 rather than minting a second threshold | `CLAUDE.md` Rule #6; `config/idhazh.json` |
| 6 | **No single combined score.** Four facts, four figures | `frontend/src/routes/console/+page.svelte` |
| 7 | **This plan reads `ledger.reliability` and never modifies it.** Feed scoring belongs to another plan | Owner, 2026-09-11 |
| 8 | **This tab carries a `headline_sentence` on the same rule row #12's does.** One sentence at the top, computed in the producer, never null, never empty, no adjective: the worst of this tab's figures against its own bound, or `Nothing on this page is outside its bound.`, or a count of the figures not computed yet. **A generated sentence on one of two new tabs is a pattern half-introduced**, and the next person cannot tell whether the other tab was an omission or a decision. `schemas/source-health-view.schema.json` carries the field | Susan, 2026-09-11; row #12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave the feed panels on `Pipelines` and give `Voices` only the reliability panel | Then two routes both answer "which feeds broke" and neither owns it. The split is what pays for the tab | Editor |
| 2 | Compute the reliability factor in `+page.server.ts` from the feed-health shards | It is a second derivation of a ranking factor, on the other side of a boundary, and it would walk the shards at build time. The producer already has the number | Carmack; `CLAUDE.md` Rule #12 |
| 3 | One combined source score, ranked | It would tell an operator something is wrong and nothing about what to do - the page's own sentence, and the reason the census is four facts | `docs/architecture/publishing/console.md` |
| 4 | Print a lean on every feed, thin record and all | A lean over four articles is a claim the record cannot carry, and a chart is the most convincing way to make one | Andre |

---

## 16. Row #14 - A target distribution, and the day's distance from it

- **Scope:** A target distribution over desks, kinds, lenses and viewpoints that **a person writes into `config/`**, and a **divergence** of the published day against it, recorded per day and drawn on `Pipelines` as one `TargetBar` per desk.
- **Files touched:** `backend/idhazh/diversity.py`, `backend/idhazh/publish_day_metrics.py`, `backend/idhazh/contracts/day_metrics.py`, `schemas/day-metrics.schema.json`, `tests/fixtures/contracts/day-metrics/full.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_diversity.py`, `backend/tests/test_day_metrics_producer.py`, `backend/tests/test_contracts.py`, `backend/tests/test_marks.py`, `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/+page.server.ts`, `frontend/tests/console-desk-mix.spec.ts`, `docs/concepts/placement.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/{test_diversity,test_day_metrics_producer,test_contracts,test_marks}.py`, `GATE-SCHEMA`, `GATE-WEB`, `GATE-BROWSER`, `GATE-SUITE`, `GATE-DAYS`. Plus, in this row:
  - both schemas carry today's `version` and a `changelog` entry, and the day-metrics fields are **optional**, because 22 committed day records do not carry them;
  - `backend/tests/test_marks.py` passes, so the new module is classified;
  - `docs/concepts/placement.md` gains the target and the divergence, on the page row #2 created.
- **A second plan writes the same three files, and so do three more rows of it.** [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) row #14 adds a `DayTaxonomy` block to `backend/idhazh/contracts/day_metrics.py`, `schemas/day-metrics.schema.json` and `backend/idhazh/publish_day_metrics.py`, and a block to the same `state/day-metrics/<YYYY>/<MM>/<DD>.json`. **Its rows #13, #1a and #1b also edit that model and that schema** - the encoder alarm's counter, the fingerprint relaxed, the fingerprint removed - which an earlier form of this note did not say. **Neither plan blocks the other and every one of the five rows may land**, because the blocks are disjoint and each is declared optional against the day files already on disk. **Whichever lands after another re-runs `python -m idhazh.contracts.export` and reads the previous `changelog` entry before adding its own**, because the drift gate fails on a byte and two entries dated the same day need the minute form (`CLAUDE.md` section 11). Found 2026-09-11; neither plan named it before.
- **Oracle:** **A day drawn exactly to the target scores zero, and moving one story from the largest desk to the smallest strictly lowers the score.** Both halves on a built fixture. The first is the identity every divergence must satisfy and it catches a normalisation that is off; the second is monotonicity and it catches a measure that rewards the concentration it is meant to report. **Built rather than sampled**, because no committed day is drawn to a target that did not exist when it published.
- **What this row does not do:** **it changes no order.** It reports. The divergence reaches no score, and ESCALATE trigger 8 fires on a row that wires it into the ranker.

### Why a target and not a learned score

**The field with this project's constraint does not build a learned importance score; it builds a target distribution and measures the divergence from it.** Our constraint is the same one that literature works under: no clicks, editorial values that a person states rather than infers, and a list to publish rather than a feed to personalise.

| Work | What it gives this row |
| --- | --- |
| RADio - Rank-Aware Divergence Metrics to Measure Normative Diversity in News Recommendations, Vrijenhoek, Benedict, Gutierrez Granada, Odijk, de Rijke ([arXiv 2209.13520](https://arxiv.org/abs/2209.13520), RecSys 2022) | A **rank-aware Jensen-Shannon divergence**: it accounts for a reader's falling attention down a list and it compares whole distributions rather than point estimates. Both matter here, because this plan just gave the day one order and the head is where a skew is felt |
| D-RDW - Diversity-Driven Random Walks for News Recommender Systems, Li, Heitz, Inel, Bernstein ([arXiv 2508.13035](https://arxiv.org/abs/2508.13035), RecSys 2025) | **Customizable target distributions of article properties**, so an editor can put norms into the process transparently. That is this row's shape exactly: a person writes the target, the arithmetic reports the distance |
| Recommenders with a mission: assessing diversity in news recommendations, Vrijenhoek, Kaya, Metoui, Moller, Odijk, Helberger ([arXiv 2012.10185](https://arxiv.org/abs/2012.10185)) | The five normative concepts the metrics are grounded in, and the argument that click-based evaluation measures the wrong thing |
| Leveraging Media Frames to Improve Normative Diversity in News Recommendations, Dattawad, Daffara, Ceron ([arXiv 2509.02266](https://arxiv.org/abs/2509.02266), INRA at RecSys 2025) | Frames as a controllable aspect beside category and sentiment - which is what this plan's lenses and viewpoints are, under a different name |

**Read on the open web and verified against arXiv on 2026-09-11.** They are cited for their shape, not for a number: nothing here adopts a threshold from any of them.

**This is the first quality number about the page rather than about a summary, and it needs no labels.** Every existing quality figure in this repository - faithfulness, the confidence band, hedges, verbatim runs - judges one summary against one article. This one judges the day against what a person said the day should look like, and it can be computed from the published payload alone.

### What it measures, and what a person writes

- **Four target distributions**, one per vocabulary: desk, kind, lens, viewpoint. Each is a set of shares that sum to 1.0, written into `config/idhazh.json` with a sane default and a schema bound, per Rule #6. **Each one names the denominator it sums over, because the four do not share one and "shares that sum to 1.0" was the whole specification until 2026-09-11.**

| Vocabulary | Shares sum over | Why it is not the same as the one above it |
| --- | --- | --- |
| Desk | **published items in the day** | One desk an item, every item has one. This is the only one of the four where the obvious denominator is the right one, and it is why the other three went unnoticed |
| Kind | **published items in the day** | One `article_kind` an item, never absent, with the feed's kind as the fallback. Same shape as desk |
| Lens | **lens firings, not items** | A lens is **multi-label** and most items carry none: measured over 8,478 committed items, keyword lenses reach **27.0 percent**, so **73.0 percent carry no lens at all** (plan 23 row #19 decision 3). Shares over items cannot sum to 1.0 and shares over firings can. **The `no lens` share is published beside the distribution as its own figure** - it is 73 percent of the day and a target that cannot see it is a target over a quarter of the digest |
| Viewpoint | **five separate distributions, one per stance field** | Plan 23 row #10 ships **five independent fields**, not one. A single viewpoint target cannot be written down: a piece arguing two things at once is on two axes, so the ten poles do not compete for one total. **Each axis's target is three shares over the gate-opened items - its two poles and its own `not_applicable`** - and a target that omits `not_applicable` is a target over a set nobody stated |

**So the config holds eight distributions behind the word "four", and the divergence is reported per vocabulary rather than pooled.** Pooling them would add a lens firing to an item count, which is two units in one sum.
- **`docs/concepts/placement.md` states which denominator each uses, in the same words.** A divergence whose denominator is only in the code is a number nobody can check, and this is the row that writes the page.
- **The divergence is reported per day** on the existing day-metrics record, which is already day-sharded under `state/day-metrics/<YYYY>/<MM>/<DD>.json` and already published as a monthly projection. **No new ledger, no new shard, no new prune.**
- **The desk one is drawn** on `Pipelines`, as one `TargetBar` per desk: the track at the desk's target share, the fill at the day's, and the marker where row #7's ceiling sits. Five bars and one number, which is what a `TargetBar` is for.
- **Where a vocabulary does not exist yet, its target is absent and its divergence is null.** Viewpoint arrives with plan 23. An absent target reads as "nobody has said what this should look like", never as "it should be flat".

**The starting targets are estimates and are config because they are.** Measured 2026-09-11 over the 21 finished days, the day is `india` 31.7 percent, `world` 26.4, `ai` 15.2, `energy` 13.8, `business-economy` 12.9 - so the largest desk already sits within two points of ESCALATE trigger 2 on supply alone, and a target set to today's shape would ratify that rather than measure it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A target a person writes, never a target the pipeline learns.** A target the system derives from what it published is the runaway plan 23 row #17 decision 4 names, one level up | Andre; section 0 |
| 2 | **It reports and decides nothing.** No stage reads the divergence, no gate fails on it, and a run that cannot compute it publishes anyway | Section 1a, degrade rather than fail |
| 3 | **Rank-aware, because this plan gave the day one order.** A flat count over 365 stories says nothing about the head, and the head is the only part most readers reach | [arXiv 2209.13520](https://arxiv.org/abs/2209.13520) |
| 4 | **It rides on the existing day-metrics record.** A per-day quality number about the page is what that record is; a second day-sharded ledger would be a second prune and a second growing-reads declaration for one number a day | `CLAUDE.md` Rule #12; `backend/idhazh/publish_day_metrics.py` |
| 5 | **The desk mix's `TargetBar` lands here, not on `Judgement`.** A `TargetBar` needs a threshold to mark and this is the row that owns it. Row #12 records the refusal and points here | Susan, 2026-09-11 |
| 6 | Every field added to `DayMetrics` is **optional and an absent value reads as unknown**, because 22 committed day records do not carry it and none of them is rewritten | `CLAUDE.md` section 11 |
| 7 | **Each target names its denominator, and the four do not share one.** Desk and kind sum over published items; lens sums over **firings**, because 73.0 percent of items carry no lens and a share over items cannot reach 1.0; viewpoint is **five distributions**, one per stance field, each over that axis's gate-opened items including its own `not_applicable`. **A divergence whose denominator is unstated is not a measurement**, and "shares that sum to 1.0" was the whole specification until 2026-09-11 | Andre, 2026-09-11; `CLAUDE.md` Rule #10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Learn an importance score from what readers opened | There are no clicks, by design - no accounts, no telemetry, no runtime call home. The literature's own answer to that constraint is a target distribution | `CLAUDE.md` Rule #1 |
| 2 | Set the target to the trailing average of what we published | It measures the pipeline against itself and reports zero for ever. A target is a statement about what should be, and only a person can make it | Andre |
| 3 | Wire the divergence into `rank_score` as a term | A measurement a score optimises against stops measuring. ESCALATE trigger 8 fires on it | Owner; section 0 |
| 4 | A single diversity number for the day | Four vocabularies collapse to one figure that says something is off and not which. It is the same refusal `Voices` makes about a combined source score | Editor |
| 5 | A new day-sharded ledger of its own | One number a day, on a record that already exists, already shards by day and already publishes a monthly projection | Carmack |

---

## 17. The docs each row writes

**Every "exists today" answer in this table was run against the tree on 2026-09-11**, not carried from a draft. **Every page here is written by the row that owns the question, and where two rows write one page they are in different parallel groups** - which is the second half of section 1's check.

| Doc | Exists today | Row | What it must say |
| --- | --- | --- | --- |
| `docs/concepts/placement.md` | **no** - created by whichever of row #2 and plan 23 row #20 lands first | 2 writes the frame; 7, 8, 14 extend; **plan 23 rows #20 and #17 write the order and the learned lens multiplier onto it** | What a frame is, what a cap does, what a floor and a ceiling are, the target distribution, and the one sentence that makes it all legal: nobody reads the digest before it publishes, so an editorial decision reaches a reader as arithmetic or not at all. **Plan 23 row #20 wrote this to `docs/concepts/the-order-of-the-day.md` until 2026-09-11**, which was a second page for the same question with four of the same citations on it |
| `docs/concepts/growing-reads.md` | yes, 546 lines | 9a | The counterfactual ledger's cover, **extended rather than written** - plan 23 row #21 declares it when it creates the ledger, and this row widens the row shape |
| `docs/architecture/sources/discovery.md` | yes, 798 lines | 1, 3, 4 | Row #1 corrects the tie-break's reason; row #3 rewrites the term list and its order; row #4 rewrites the published score block, which is the multiplier row #4 removes |
| `docs/architecture/publishing/layout.md` | yes | 4, 5, 10 | Row #4 rewrites the `carried_by` row to say what the field now buys; row #5 replaces the rail section with the eyebrow's fourth fact; row #10 records that there is one order and the page draws it |
| `docs/architecture/publishing/visuals.md` | yes | 1 | **Rewritten** where it cites the shared-link reason for keeping a published decision |
| `docs/architecture/publishing/frontend.md` | yes | 6 | The pill row's order, its margin, and why a curated desk is never folded |
| `docs/concepts/ui-shell.md` | yes, 170 lines | 5 | Extended: where the time sits, at what size, and what is drawn for each `time_source` state |
| `docs/reference/documentation-structure.md` | yes | 2 | One row routing `placement.md`, added by whichever row creates the page |
| `docs/architecture/publishing/console.md` | yes, 1,669 lines | 11, 12, 13 | Row #11 rewrites `The console is three routes` as five and records the severity cap; rows #12 and #13 each add their own tab and its worst state |
| `docs/architecture/publishing/console-payloads.md` | yes, 412 lines | 12, 13 | One payload shape each |
| `docs/architecture/publishing/console-charts.md` | yes, 493 lines | 12, 13 | The chart choices, including the two Susan folded and the one the owner reinstated |
| `docs/concepts/console-design.md` | yes, 681 lines | 12, 13 | The sufficiency argument for each tab, and the rule that this console never prints the word "confidence" bare |
| `docs/architecture/sources/health.md` | yes | 13 | Where the reliability factor is published and which panel draws it |

**One page is created by this plan, and it may be created by another.** `docs/concepts/placement.md` is written by whichever of row #2 here and plan 23 row #20 lands first, and extended by the other. **`docs/how-to/tune-the-placement-weights.md` was on this table until 2026-09-11 and is not created by anything**: row #9b is retired and plan 23 row #17 documents its loop on `placement.md`. Everything else exists and is extended or corrected. **No row writes a page an existing page already owns**, and the four console pages are shared by three rows that sit in three different parallel groups for that reason.

---

## 18. Open gaps nobody owns

Named here so they are not mistaken for work this plan is doing.

| Gap | What it is | Why it is not a row here |
| --- | --- | --- |
| Wire relationships between feeds | `config/sources.json` has 151 feeds and no field saying which are customers of the same original. Without it "carried by two of our feeds" cannot be narrowed to "carried by two independent publishers" | It is a source-contract change and a research problem - somebody has to establish the relationships before a field can hold them. Row #4 ships without it and says so on the page |
| Branch protection on `main` | It is off, and it is the only control that would actually stop a workflow pushing to the default branch. **No workflow in this plan pushes anything** - row #9b, which would have opened a pull request, is retired - so nothing here needs it, and it is named because the next row that adds a workflow will | It interacts with `prune.yml`'s scheduled force-push, which is `CLAUDE.md` section 8's one exception. It is a repository setting and a decision about the whole repository |
| A reader-visible reason for a story's position | The leading block explains its five; the other 355 stories have a position and no sentence. `digest.md` refuses numerals for good reasons and those reasons apply here too | It needs a vocabulary this plan does not have. Naming it is not the same as owning it |
| `events` and `entities` rendered nowhere | Inherited from plan 23 section 26 and still true | Owned by no row of any plan. Row #12 draws both on the **operator** console, which is a different surface from the page a reader opens |
| Retiring prerender from the app shell | Six routes are prerendered and the two dated reading routes are not. **Owned since 2026-09-11** | [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md) took it. That plan rules the six routes stay and the build-time guard goes, and prices the reversal. Section 0.1 still forbids any row here from asserting byte identity over prerendered output or from removing prerendering |
| A second derivation of `ledger.reliability` | `frontend/src/lib/feed-health.ts` exports a `reliability` that is a clean-read census, and `backend/idhazh/ledger.py` exports a `reliability` that is the ranking multiplier. Two names, two quantities | Row #13 draws the second and renames neither. A rename crosses `backend/` and `frontend/` for no behaviour, and naming the collision is what stops the next reader assuming they agree |

---

## See also

- [`20260911-handover.md`](20260911-handover.md) - how to pick this queue up with no context: the queue reader, the reading order, and the standing traps.
- [`20260911-execution-order.md`](20260911-execution-order.md) - the schedule across the five open plans. **Row #5 here is the shortest path to something a reader can see**, and row #12 is on the critical path in both directions: it waits on plan 23 row #14 and plan 23 row #15 waits on it.
- [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) - the plan that named this work and left it; its row #6 changes what names a desk and its row #16 is where an auto-created vertical comes from. **Four edges run between the two plans**: its row #21 owns the counterfactual ledger row #9a here extends; its row #17 is the weights loop that retired row #9b here; its row #15 supplies the classification figures row #12 here draws, and its row #14 is what row #12 waits on; and its rows #20 and #17 write `docs/concepts/placement.md`, which row #2 here creates.
- [`20260910-24-day-sharded-ledgers-plan.md`](20260910-24-day-sharded-ledgers-plan.md) - the five month-sharded ledgers, moved to day files. Nothing in this plan writes one of them, and its row #1 is what plan 23's four new ledgers - including the one row #9a here extends - take their day-tree rule from.
- [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md) - the plan that took the prerender gap out of section 18, and the ruling section 0.1 now inherits.
- [`20260911-classification-research-record.md`](20260911-classification-research-record.md) - the decision and research record for the conversation this plan split out of; its section 4 is the finding that a list like this one is graded against a target distribution rather than a learned score.
- [`../docs/concepts/digest.md`](../docs/concepts/digest.md) - the leading block, the four why-lines, and the claim about carriage that the page refuses and the ranker made.
- [`../docs/architecture/sources/discovery.md`](../docs/architecture/sources/discovery.md) - the score as it stands, and the section rows #1, #3 and #4 rewrite.
- [`../docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md) - the published item's five rank fields, and the rail this plan retires.
- [`../docs/architecture/publishing/console.md`](../docs/architecture/publishing/console.md) - the three routes this plan takes to five, the strip, the band and the severity ranking.
- [`../docs/concepts/console-design.md`](../docs/concepts/console-design.md) - how a console figure is worded, coloured, ranked and drawn, and the rules rows #11 to #14 work inside.
- [`../docs/architecture/sources/freshness.md`](../docs/architecture/sources/freshness.md) - `ledger.reliability`, its window, its floor, and why it can only ever reduce a score.
- [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - what a read over a growing collection must declare.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row, and where the no-two-rows-one-file rule comes from.
- [`../docs/how-to/author-a-plan.md`](../docs/how-to/author-a-plan.md) - the shape every row above is written in.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every gate set in section 0.1a.
