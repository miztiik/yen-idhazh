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
| Hard scope - in | The three docstrings that defend a retired requirement; one order over the whole day; a desk cap and a feed cap over the head; the score's terms and their order; carriage as a tie-break; the time rail retired and the timestamp placed; the topic pills ordered by what is running; a desk floor and a desk ceiling; cross-filing to a second desk; the counterfactual ledger; the weekly weights loop; the `assemble` consolidation |
| Hard scope - out | **The read desk.** Deciding a story's subject by reading it is plan 23 row #6 and is not deferred by anything here - this plan works on whatever field names the desk. **The five month-sharded ledgers**, which are plan 24. **The visual planner's call structure**, which is plan 11. **Personalisation of any kind**: there is one published order and every reader gets it |
| ESCALATE triggers | 1. **Day-over-day desk churn above 1 item in 10** that a weight change rather than supply accounts for. A reader cannot tell "the world changed" from "our weights changed", and past that rate they stop trying. 2. **Any single desk or lens above roughly a third of the day when supply does not put it there.** 3. A row proposes to **rebuild the day whole** - the arithmetic that refuses it is in section 0.3 and a row may not re-open it without new measurement. 4. A weights proposal is **auto-merged**, or any workflow in this plan gains a push to `main`. 5. A removal row proposes to leave a test, a config key, a schema field or a doc paragraph behind. 6. Row #9b is dispatched before row #9a has committed a counterfactual row - the loop would then adapt on the outcome, which decision 4 of row #9b bans |
| Chosen strategy | Delete the false justification first, then build the frame, then give the score the stream inside it, then the desk rules, then the loop that moves a weight, then the consolidation that removes the dead work. Every ordering change lands in the backend and is published; the frontend stops sorting in the last row rather than the first |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

**The governing line, and it is what makes the weights loop legal.** **A knob a person owns is adapted by a pull request; a fact about the world is derived inside the run from a bounded window and never written to `config/` at all.** `ledger.reliability` is the model to copy: it reads the trailing `collect.reliability_window_days` of feed health, reduces each feed to a factor clamped between `collect.reliability_floor` and 1.0, and writes nothing - the number lives for the length of one run. A feed's recent record is a fact about the world. `repetition_weight` is a knob a person owns. The two are adapted by different machinery on purpose, and a row that blurs them has broken this plan's one rule.

### 0.1 Standing rules, and they bind every row

**Deliver the intent, not the letter.** A structural fix matters more than a small diff. Where a row cannot be done correctly inside its stated file list, **expand the scope and say so in the pull request** - do not ship a band-aid to stay inside a list somebody wrote before the code was read. `CLAUDE.md` Rule #5 is the authority; a row's file list reads like a fence and is meant to read like a start.

**No prisoners.** Every removed feature takes its code, its tests, its fixtures, its config keys, its schema fields, its docs and its `state/` writers with it, **in the same commit**. Git is the backup. A row that removes something and leaves a dead test, an orphan config key or a doc paragraph describing the removed thing has not finished, and its acceptance gate says so.

**Verify every fact in your row against the tree before you act on it.** This plan was written on 2026-09-11 against a tree that moves several times an hour. A count, a line number, a percentage or an "exists today" answer in any row below is a reading of that morning, and three of the figures this plan inherited from its own brief had already moved by the time they were re-derived. Re-run the grep. Where the tree disagrees, **the tree wins and the row is corrected in the same pull request**, with a line saying what it was corrected from.

**One order, and the backend owns it.** Every ordering decision in this plan is taken at assemble time and published. Nothing re-orders in the browser. That is not a style preference: a re-order at read time makes a shared link show the recipient a different page from the one the sender saw, and `frontend.md` already refuses a reader-facing sort control for exactly that reason. The frontend's current re-sort is the thing row #10 removes, not a precedent.

**A frame is a standing editorial decision expressed as arithmetic, and it is checked by a test.** Nobody reads the digest before it publishes and it publishes five times a day. So an editor's judgement can only reach a reader as a rule that runs without one: how much of the head one desk may hold, how much one feed may hold, what a desk may not fall below. Every such rule in this plan lives in `config/`, has a sane default, and has a test that fails when the rule is broken.

**A human read can refuse a rank change; only a measurement can authorise one.** Refusing on judgement is safe, because the digest we already publish is the fallback and the cost of a refusal is one unchanged day. Authorising on judgement is not, because a subsidised theme reorders every future day and nothing on the page says why. Every row that raises a weight names the measurement; every row that lowers one may cite a read.

**Every oracle is driven from a fixture, never from the committed archive** (`CLAUDE.md` Rule #12 and section 13). A per-item rule is proved on `backend/var/canary/` or on `tests/fixtures/`, both fixed in size and both able to carry a case the archive has never produced - `time_source: unknown` has never once happened in 8,550 committed items and row #5 has to render it. A question genuinely about the whole tree is asked once, on the total, by `idhazh validate-days`, and not by pytest.

**Additive contract fields are stamped in the commit that adds them.** Every row that adds a field to a persisted model names its `version` date-stamp and its `changelog` entry in its own acceptance gate, per `CLAUDE.md` section 11.

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

**`GATE-SHELL`** - every row that touches `.github/`:

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

**What the carriage figures mean, said next to them.** `reach = 1.0 + repetition_weight * (carried_by - 1)` at `repetition_weight` 1.0 **doubles the authority term at two carriers**. That single step is larger than the recency bonus at full strength (0.6), larger than the watchlist bonus (0.5), larger than the front-page vote (0.4) and larger than the heaviest lens (0.3) - and it is a multiplier where all four of those are additions. The consequence is measured, not argued: **under 6 percent of the pool holds 60 percent of the day's top 20**. And what the number measures is **syndication, not agreement** - `layout.md` already says `carried_by` counts feeds carrying **one address**, so two outlets writing their own piece produce two addresses and both read 1. `docs/concepts/digest.md` refuses to print the agreement claim in words ("never 'three sources covered this': that is a different claim and the number does not support it") while the ranker makes it in arithmetic. Row #4 is that contradiction closed.

**Rebuilding the day whole is refused, and this is the arithmetic.** Today `assemble` rebuilds parts of the day whole on every run - `collapse_same_story` over every item, `leading_stories` over every item, the whole month's search index, every desk reference - while the per-item work stays incremental. A row that extended that to the per-item work would spend, on 2026-09-09: run 1 processes 73, run 2 processes 142, run 3 215, run 4 285, run 5 360. **Item-passes go from 360 to 1,075 - 2.99x** - and run 5 alone goes from 75 items to 360, **4.8x**. Applied to the worst shard on record that is 66.9 minutes to about **321 minutes, 60 percent past the 200-minute timeout**, and a shard that times out uploads no artifact, so the day publishes nothing rather than publishing late. Row #10 resolves the two consistency models by making the whole-day passes cheap enough to keep, never by making the per-item work whole-day.

### 0.4 What blocks what, and what does not

**Nothing in this plan is blocked on plan 23.** Row #7 is the row that reads most naturally as classification work and it is not: the desk floor and the desk ceiling are built against whatever field names the desk, and today that field is the feed's declared `vertical`. What plan 23 row #6 changes is the **failure mode** the floor exists to catch, and section 8 of this plan's row #7 says so.

**Row #9b is blocked inside this plan, on row #9a, and the block is real.** Neither `state/scores` nor `state/item-health` carries a counterfactual - verified 2026-09-11 by reading both headers, which name 36 and 29 columns and no candidate score at any weight but the committed one. A loop that adapts without one is adapting on the outcome, which is a loop reading its own past decisions and calling them evidence.

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
| 9a | The counterfactual the loop cannot run without | 3 | E | PENDING | - | - | - |
| 9b | The weekly loop proposes a pull request and commits nothing | 9a | F | PENDING | - | - | - |
| 10 | The `assemble` consolidation | 2, 5, 7, 8 | F | PENDING | - | - | - |

**What a parallel group means, stated so a worker can check it.** **Within one group, no two rows may write the same file.** A glob counts as every file it covers, so `backend/tests/**` and `schemas/**` collide with any named file underneath them - and a row that edits any model under `backend/idhazh/contracts/` counts as writing every schema its edit regenerates, because the drift gate fails on a byte. **So there are no globs in this plan.** Every row's `Files touched` list names files. **A row that widens its file list during execution re-checks its own group before it opens a pull request**, and section 0.1 expects that widening to happen.

**Eleven rows, six groups, one singleton, and the singleton is row #2.** It creates `backend/idhazh/placement.py`, which rows #7, #8 and #10 all read and two of them extend, and it is the row that decides there is one order at all. A second row landing beside it would be building against a shape that is still moving. Every other group holds two.

**Row #5 has no predecessor on purpose, and the reason is a defect it would otherwise inherit.** The rail groups stories by time and `day-shape.ts` states in its own docstring that a rail over an order it did not sort reopens groups further down and prints numbers that jump as the reader scrolls. Row #2 replaces the time order with a scored one. So the rail has to go **before** row #2, not after it, and a schedule that put row #5 late would ship a run of days where the rail was visibly wrong.

### The file sets, which are what prove it

Derived from the rows' own `Files touched` lists on 2026-09-11. **It is derived rather than authoritative**: a worker checks a group by diffing the two rows' lists in the sections below, never by trusting this table ([`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)).

| Group | Rows | What the first row writes | What the second row writes | Where they come closest |
| --- | --- | --- | --- | --- |
| A | 1, 5 | `backend/idhazh/assemble.py`, `backend/idhazh/cli.py`, `backend/tests/test_pipeline.py`, `docs/architecture/publishing/visuals.md`, `docs/architecture/sources/discovery.md` | `frontend/src/lib/components/{DigestItem,DigestList,TimeRail}.svelte`, `frontend/src/lib/{day-shape,format}.ts`, `backend/idhazh/contracts/appearance_config.py`, `schemas/appearance-config.schema.json`, `config/appearance.json`, `frontend/tests/{time-rail,item-card,item-zones}.spec.ts`, `docs/concepts/ui-shell.md`, `docs/architecture/publishing/layout.md` | Both write a `docs/architecture/publishing/` page. Row #1 writes `visuals.md`; row #5 writes `layout.md`. Row #1 opens no frontend file and row #5 opens no pipeline module |
| B | 2 | singleton - it creates `placement.py`, which four later rows read | - | - |
| C | 3, 6 | `backend/idhazh/rank.py`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_rank.py`, `docs/architecture/sources/discovery.md` | `frontend/src/lib/day-shape.ts`, `frontend/src/lib/components/FilterBar.svelte`, `backend/idhazh/contracts/appearance_config.py`, `schemas/appearance-config.schema.json`, `config/appearance.json`, `frontend/tests/{filter-bar,topics}.spec.ts`, `docs/architecture/publishing/frontend.md` | Both add a config key, edit a contract model and regenerate one schema. **Two different config files, two different contract modules, two different schema files**, so the drift gate sees two disjoint diffs |
| D | 4, 7 | `backend/idhazh/rank.py`, `config/idhazh.json`, `backend/tests/test_rank.py`, `docs/architecture/sources/discovery.md`, `docs/architecture/publishing/layout.md` | `backend/idhazh/placement.py`, `backend/idhazh/contracts/taxonomy.py`, `schemas/taxonomy.schema.json`, `config/taxonomy.json`, `backend/tests/{test_placement,test_contracts}.py`, `docs/concepts/placement.md` | Both write a file in `config/`. Row #4 writes `idhazh.json` and row #7 writes `taxonomy.json`. Row #4 adds no contract field, so it regenerates no schema |
| E | 8, 9a | `backend/idhazh/placement.py`, `backend/idhazh/contracts/{article,digest_day,digest_view}.py`, `schemas/{article,digest-day,digest-view}.schema.json`, `frontend/src/lib/payload/types.ts`, `backend/tests/{test_placement,test_contracts}.py`, `docs/concepts/placement.md` | `backend/idhazh/{rank,cli,ledger}.py`, `backend/idhazh/contracts/placement_counterfactual.py`, `schemas/placement-counterfactual-row.schema.json`, `backend/tests/{test_ledger,test_marks}.py`, `docs/concepts/growing-reads.md` | Both add a contract and regenerate a schema. Four named schema files against one, all five distinct. Row #8 opens no ledger and row #9a opens no published payload model |
| F | 9b, 10 | `.github/workflows/placement-weights.yml`, `backend/utilities/propose_placement_weights.py`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_workflows.py`, `tests/fixtures/workflows/placement-weights-widened-permissions.yml`, `docs/how-to/tune-the-placement-weights.md`, `docs/concepts/growing-reads.md` | `backend/idhazh/{assemble,cli}.py`, `frontend/src/lib/server/payload.ts`, `frontend/src/lib/components/DigestList.svelte`, `backend/tests/{test_pipeline,test_same_story,test_leading_stories}.py`, `frontend/tests/day-list.spec.ts`, `docs/architecture/publishing/layout.md` | Nothing. Row #9b writes no pipeline module and no frontend file; row #10 writes no workflow, no utility and no contract |

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
| 5 | The step's size is an **estimate** and moves under row #9b like every other weight, with the oracle's ceiling as its hard bound | `CLAUDE.md` Rule #10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Lower `repetition_weight` from 1.0 to something small and keep the multiplier | A multiplier scales with authority, so the same weight buys a big move on an institution and a small one on a community feed - the opposite of what a tie-break should do. And it stays uncapped: a story on six feeds would still take the day | Andre |
| 2 | Remove carriage from the score entirely | It is real signal, it is one of the four why-lines the leading block can print, and 60 percent of today's top 20 carries it. Removing it would change the day more than the multiplier does and in a direction nobody measured | Editor |
| 3 | Build the independence test now, from the registrable domain | Two feeds on one domain are already one feed for `max_per_source` purposes. What the test needs is wire relationships **across** domains, which the domain cannot answer | Fowler |

---

## 6. Row #5 - The rail goes and the time lands under the heading

- **Scope:** `TimeRail.svelte` is deleted. Every story prints its own published time in small type beside its heading. `time_source` decides how it is drawn.
- **Files touched:** `frontend/src/lib/components/DigestItem.svelte`, `frontend/src/lib/components/DigestList.svelte`, `frontend/src/lib/components/TimeRail.svelte` (deleted), `frontend/src/lib/day-shape.ts`, `frontend/src/lib/format.ts`, `backend/idhazh/contracts/appearance_config.py`, `schemas/appearance-config.schema.json`, `config/appearance.json`, `frontend/tests/time-rail.spec.ts` (deleted), `frontend/tests/item-card.spec.ts`, `frontend/tests/item-zones.spec.ts`, `docs/concepts/ui-shell.md`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `GATE-WEB`, `GATE-BROWSER`, `GATE-SCHEMA`, `GATE-SUITE`, and the `CLAUDE.md` section 12 browser smoke. Plus, in this row:
  - `rail_group_minutes` and `railRows` and `RailRow` go in the same commit as the component (section 0.1, no prisoners);
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
| What stops 627 timestamps becoming wallpaper | **Nothing about the timestamp - it is the fourth of four facts in a line that already repeats on every item, and it is drawn in the same type as the other three.** A fifth typographic weight on that line would be the wallpaper. The rail's own arithmetic is the argument: measured 2026-09-02 over 12 days and 4,713 stories at the 60-minute default, it printed 907 markers, so **80.8 percent of stories carried no time at all**, and on 2026-09-01 that is 31 labels across 627 stories. The choice is not "33 timestamps or 627"; it is "596 stories with no time, or every story with its own" |

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The rail is deleted, not kept beside the timestamp.** Two marks for one thing on one line is the contradiction plan 23's standing rule already forbids, and it is the exact duplicate the rail was built in 2026-09-02 to remove | Jony; plan 23 section 0.1 |
| 2 | **Hovering to reveal the time is refused.** It is unreachable on the surface most readers use, and a fact worth having is a fact worth drawing | Owner, 2026-09-11 |
| 3 | The time is **the item's own, to the minute**, never a rounded or grouped one. Grouping is what the rail did and it is what left 80.8 percent of stories unlabelled | Susan |
| 4 | **Susan rules the slot; Jony rules what leaves it.** The day link's removal on a day page is Jony's call under the four-fact cap and it is recorded above with what the reader loses, which is nothing they do not already have from the URL | `CLAUDE.md` section 14 |
| 5 | This row lands **before** row #2. The rail groups by time; row #2 replaces the time order with a scored one; a rail over an order it did not sort reopens groups further down, which `day-shape.ts` already states in its own docstring | Section 1 |

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
| 5 | The order is computed at build time and published. Measuring the row in the browser was already refused: every page here is prerendered, so a row that measures itself is wrong until a script runs | `frontend/src/lib/day-shape.ts` |

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
  - every desk in `config/taxonomy.json` carries a floor and a ceiling, and the schema requires them.
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

## 10. Row #9a - The counterfactual the loop cannot run without

- **Scope:** The plan stage records, for every candidate it scored, what that candidate's score would have been with each tunable term at zero. One day-sharded ledger, written once a run, read by nothing in the pipeline.
- **Files touched:** `backend/idhazh/rank.py`, `backend/idhazh/cli.py`, `backend/idhazh/ledger.py`, `backend/idhazh/contracts/placement_counterfactual.py`, `schemas/placement-counterfactual-row.schema.json`, `backend/tests/test_ledger.py`, `backend/tests/test_marks.py`, `docs/concepts/growing-reads.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/{test_ledger,test_marks}.py`, `GATE-SCHEMA`, `GATE-SUITE`. Plus:
  - `schemas/placement-counterfactual-row.schema.json` carries today's `version` and a first `changelog` entry;
  - a `docs/concepts/growing-reads.md` declaration for the shard's cover, naming the window and who set it;
  - `backend/tests/test_marks.py` passes, so the new module is classified.
- **Oracle:** **A candidate the run scored and did not publish has a row.** Asserted on a built pool where the safety ceiling cuts half the candidates: every scored candidate appears, published or not, and each carries one counterfactual per tunable term. **The unpublished half is the whole point** - a ledger of what published can only tell the loop that what it promoted got promoted, and that is the runaway decision 4 of row #9b names.
- **What this row does not do:** it changes no score, moves no weight and reads nothing. It writes.

### Why neither existing ledger can answer it

Verified 2026-09-11 by reading both headers. `state/scores/*.csv` carries 36 columns and is the **eval** ledger - one row per published item, about faithfulness. `state/item-health/*.csv` carries 29 columns and is the **cost and outcome** ledger - one row per attempted item. Neither carries a candidate that was never planned, and neither carries a score at any weight but the committed one. So a loop built on either would be reading its own past decisions, which is what decision 4 of row #9b bans.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Day-sharded, with a declared cover.** Every read of it in row #9b names a trailing window by date arithmetic and never walks the directory | `CLAUDE.md` Rule #12; [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) |
| 2 | **It records; it decides nothing.** No stage reads it, no gate fails on it, and a run that cannot write it publishes anyway | Section 1a, degrade do not fail |
| 3 | **One row per candidate per run, not per published item.** The pool is what the loop needs and the pool is bigger than the day: the safety ceiling is 80 items a run against a considered pool several times that | `backend/idhazh/rank.py` |
| 4 | The cost is bounded by the run's own pool, never by the archive. It is written at plan time, where every candidate is already in memory and already scored | `CLAUDE.md` Rule #12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Widen `state/scores` with the counterfactual columns | It is the eval ledger, it has one row per **published** item, and widening it would put a placement fact in a faithfulness record. It is also `merge=union` under git, so a header migration cannot survive a rebase | Fowler; [`../docs/reference/agent-notes/git-and-github.md`](../docs/reference/agent-notes/git-and-github.md) |
| 2 | Recompute the counterfactual later from the published day | The pool is gone. The day holds what published, and the question is about what did not | Andre |
| 3 | Skip it and let row #9b adapt on the outcome | That is the runaway: a term is rewarded for the stories its own bonus promoted, and it converges quietly on whatever it already preferred | Andre |

---

## 11. Row #9b - The weekly loop proposes a pull request and commits nothing

- **Scope:** A weekly workflow reads a bounded window of the counterfactual ledger, proposes placement weights, and **opens a pull request**. It merges nothing and commits nothing.
- **Files touched:** `.github/workflows/placement-weights.yml`, `backend/utilities/propose_placement_weights.py`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_workflows.py`, `tests/fixtures/workflows/placement-weights-widened-permissions.yml`, `docs/how-to/tune-the-placement-weights.md`, `docs/concepts/growing-reads.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_workflows.py`, `GATE-SCHEMA`, `GATE-SHELL`, `GATE-SUITE`. Plus:
  - `schemas/app-config.schema.json` carries today's `version` and a `changelog` entry naming the `placement_weights` block;
  - a `docs/concepts/growing-reads.md` declaration for the trailing-window read;
  - one manual dispatch - `gh workflow run placement-weights.yml` - that opens a pull request and merges nothing. **It cannot be run before the merge**: a `workflow_dispatch` resolves the workflow id from the default branch, so a dispatch-only workflow on a feature branch answers 404. The dispatch is the first thing the row's reviewer does after the merge, and the row says so.
- **Oracle:** **No step in the workflow pushes to the default branch.** Asserted by reading the workflow file in a test: the job's `permissions:` block is enumerated and matched against an expected set, and no step's `run:` line pushes to `main`. **Driven in both directions** - against the committed workflow for the passing arm, and against `tests/fixtures/workflows/placement-weights-widened-permissions.yml` for the failing one, which is the same file with one scope added. A rule that lives only in a code review is a rule until somebody is in a hurry, and a test with no failing fixture is a rule that has never been shown to bite.
- **What this row does not do:** it changes no weight. It opens a pull request; a person merges it or does not.

### What the oracle can and cannot carry, said plainly

"Permissions that permit a pull request and not a push" is not a thing GitHub's token model expresses: `contents: write` is what lets an action create the branch a pull request needs, and the same scope lets it push to `main`. So an assertion phrased as "the token cannot push to `main`" would assert something untrue of any token this workflow can hold. What the test really checks is that **the permissions block and the step list are the ones a reviewer agreed to**, so a later commit that widens either fails loudly. The control that would actually stop the push is branch protection on `main`, which is a repository setting rather than a file, and `docs/reference/github-actions.md` records that `main` is unprotected. This row does not turn it on, because protection interacts with `prune.yml`'s scheduled force-push - `CLAUDE.md` section 8's one exception. **The row's job is to name the gap rather than to imply the test closes it.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **It never commits, and auto-merge is banned on its pull requests. The merge IS the person in the loop.** A loop that tunes what a reader sees first, without a person reading the diff, is a model selecting what publishes | `CLAUDE.md` section 0a; owner |
| 2 | **Its own weekly workflow - `cron: '0 8 * * 0'` - chained to the last successful digest, never per run.** The signal is a 30-day window; adapting five times a day is reading a 30-day average five times a day and calling the difference a trend. A weekly job inside a four-hourly pipeline either runs 42 times too often or blocks the pipeline while it thinks | Carmack |
| 3 | **A new branch each fire, and it closes its own superseded pull request.** A standing branch would need a force-push, which `CLAUDE.md` section 8 forbids outside `prune.yml` | `CLAUDE.md` section 8 |
| 4 | **It adapts on the counterfactual, not the outcome.** What it compares is what the ranker **would have** selected at a candidate weight against what it **did** select at the committed one, over the same window. A weight that rises because its own term promoted the items is a loop reading its own decisions as evidence, and it converges quietly | Andre; `CLAUDE.md` Rule #10 |
| 5 | **Under-carriage is an eligibility gate, not a term in the score.** A term carried by too few items in the window has a weight nobody can estimate. Folding "too few items" in as a penalty produces a number that reads as a measurement and is a refusal wearing arithmetic. The term is **excluded and named as excluded in the pull request body**, with its item count. A lens whose median `carried_by` exceeds the day's median is ineligible for any positive weight | Andre |
| 6 | **A thin window produces a refusal, not a smaller adjustment.** Below `placement_weights.min_items_per_term` the workflow proposes nothing for that term and says so. A proposal computed from four items is not a smaller proposal; it is a different kind of thing | `CLAUDE.md` Rule #10 |
| 7 | **A staleness alarm on the open pull request.** A weekly job nobody merges opens 52 a year. If the previous proposal is still open when the next cycle fires, the run **comments on it and opens no second one**, and the console says a proposal is waiting. Without this the failure mode is silent accumulation and a loop that is dead while looking alive | Carmack |
| 8 | **It reads a bounded window by date arithmetic - at most two month shards - and never a directory walk**, with the cover declared in `growing-reads.md` | `CLAUDE.md` Rule #12 |
| 9 | **Three kill criteria, pre-committed here so none is chosen afterwards to fit the result.** (a) Two consecutive proposals rejected by a person. (b) A proposal moving any weight by more than `placement_weights.max_move_per_cycle`. (c) No proposal accepted in `placement_weights.max_idle_cycles`. **Any one of the three and the workflow is deleted** - code, config keys, tests and doc, in one commit. All three thresholds are **estimates** and live in `config/` for that reason | Section 0.1; `CLAUDE.md` Rules #6 and #10 |

### The editor's guardrails, as a list a reviewer can check

Every one of these is asserted by `backend/tests/test_workflows.py` or by the proposer's own tests, and a proposal that fails one is not written.

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
| 9 | **A person can pin any weight**, and a pinned weight is skipped and named as pinned in the pull request body |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Adapt inside the run, like `ledger.reliability` does | Reliability is a fact about the world derived from a bounded window and thrown away; a placement weight is an editorial knob a person owns. Section 0's governing line is exactly this distinction, and collapsing it would let the pipeline retune what a reader sees first, five times a day, with no diff anywhere | Owner; section 0 |
| 2 | Auto-merge the proposal when every guardrail passes | Then the guardrails are the person, and a guardrail is a rule somebody wrote before the situation existed. The merge is the only step in this loop a human is in | Owner |
| 3 | One standing pull request the workflow updates | It needs a force-push, which `CLAUDE.md` section 8 permits only to `prune.yml` | `CLAUDE.md` section 8 |
| 4 | Run it from `digest.yml` on a weekly condition | A step that is skipped 41 times out of 42 is a step nobody reads the logs of, and its failure would be indistinguishable from its being skipped | Carmack |

---

## 12. Row #10 - The `assemble` consolidation

- **Scope:** One consistency model in `assemble`. The backend's ordering work stops being dead: the frontend draws the published order and `orderByTime` goes.
- **Files touched:** `backend/idhazh/assemble.py`, `backend/idhazh/cli.py`, `frontend/src/lib/server/payload.ts`, `frontend/src/lib/components/DigestList.svelte`, `backend/tests/test_pipeline.py`, `backend/tests/test_same_story.py`, `backend/tests/test_leading_stories.py`, `frontend/tests/day-list.spec.ts`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/{test_pipeline,test_same_story,test_leading_stories}.py`, `GATE-WEB`, `GATE-BROWSER`, `GATE-SUITE`, `GATE-DAYS`, and the section 12 browser smoke. Plus:
  - `orderByTime` and its tests go in the same commit as its last caller (section 0.1);
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

## 13. The docs each row writes

**Every "exists today" answer in this table was run against the tree on 2026-09-11**, not carried from a draft. **Every page here is written by the row that owns the question, and where two rows write one page they are in different parallel groups** - which is the second half of section 1's check.

| Doc | Exists today | Row | What it must say |
| --- | --- | --- | --- |
| `docs/concepts/placement.md` | **no** | 2 creates; 7, 8 extend | What a frame is, what a cap does, what a floor and a ceiling are, and the one sentence that makes it all legal: nobody reads the digest before it publishes, so an editorial decision reaches a reader as arithmetic or not at all |
| `docs/how-to/tune-the-placement-weights.md` | **no** | 9b | What the weekly workflow proposes, who merges it, the nine guardrails and the three kill criteria |
| `docs/architecture/sources/discovery.md` | yes, 798 lines | 1, 3, 4 | Row #1 corrects the tie-break's reason; row #3 rewrites the term list and its order; row #4 rewrites the published score block, which is the multiplier row #4 removes |
| `docs/architecture/publishing/layout.md` | yes | 4, 5, 10 | Row #4 rewrites the `carried_by` row to say what the field now buys; row #5 replaces the rail section with the eyebrow's fourth fact; row #10 records that there is one order and the page draws it |
| `docs/architecture/publishing/visuals.md` | yes | 1 | **Rewritten** where it cites the shared-link reason for keeping a published decision |
| `docs/architecture/publishing/frontend.md` | yes | 6 | The pill row's order, its margin, and why a curated desk is never folded |
| `docs/concepts/ui-shell.md` | yes, 170 lines | 5 | Extended: where the time sits, at what size, and what is drawn for each `time_source` state |
| `docs/concepts/growing-reads.md` | yes, 546 lines | 9a, 9b | A declaration for the counterfactual shard and one for the loop's trailing-window read |
| `docs/reference/documentation-structure.md` | yes | 2 | One row routing `placement.md`, added by the row that creates the page |

**Two pages are created by this plan.** `docs/concepts/placement.md` and `docs/how-to/tune-the-placement-weights.md`. Everything else exists and is extended or corrected. **No row writes a page an existing page already owns.**

---

## 14. Open gaps nobody owns

Named here so they are not mistaken for work this plan is doing.

| Gap | What it is | Why it is not a row here |
| --- | --- | --- |
| Wire relationships between feeds | `config/sources.json` has 151 feeds and no field saying which are customers of the same original. Without it "carried by two of our feeds" cannot be narrowed to "carried by two independent publishers" | It is a source-contract change and a research problem - somebody has to establish the relationships before a field can hold them. Row #4 ships without it and says so on the page |
| Branch protection on `main` | It is off, and it is the only control that would actually stop a workflow pushing to the default branch | It interacts with `prune.yml`'s scheduled force-push, which is `CLAUDE.md` section 8's one exception. It is a repository setting and a decision about the whole repository |
| A reader-visible reason for a story's position | The leading block explains its five; the other 355 stories have a position and no sentence. `digest.md` refuses numerals for good reasons and those reasons apply here too | It needs a vocabulary this plan does not have. Naming it is not the same as owning it |
| `events` and `entities` rendered nowhere | Inherited from plan 23 section 26 and still true | Owned by no row of any plan |

---

## See also

- [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) - the plan that named this work and left it; its row #6 changes what names a desk and its row #16 is where an auto-created vertical comes from.
- [`../docs/concepts/digest.md`](../docs/concepts/digest.md) - the leading block, the four why-lines, and the claim about carriage that the page refuses and the ranker made.
- [`../docs/architecture/sources/discovery.md`](../docs/architecture/sources/discovery.md) - the score as it stands, and the section rows #1, #3 and #4 rewrite.
- [`../docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md) - the published item's five rank fields, and the rail this plan retires.
- [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - what a read over a growing collection must declare.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row, and where the no-two-rows-one-file rule comes from.
- [`../docs/how-to/author-a-plan.md`](../docs/how-to/author-a-plan.md) - the shape every row above is written in.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every gate set in section 0.1a.
