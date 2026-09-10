# 23 - What an article is about, decided by reading it

**Last Updated**: 2026-09-10
**Level**: 5 (a persisted contract, the published vocabulary, the call structure and the trust boundary)

**Chain**: previous [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O40, O41, O43, O45, E1, E5.

Execute per [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md): the orchestrator dispatches one worktree-isolated worker per row; workers consult personas on ambiguity; AUTO-merge on green gates; **parallel N = 2**; honour the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | A story's subject is the feed's word for it today. `config/sources.json` declares a vertical and a kind per feed, and every article that feed carries inherits both, whatever it says. Measured over the 8,478 committed items, 84.4 percent are published as `reporting` because their feed said so, and 73.0 percent carry no lens at all. A model that has already read the whole article for the summary can answer these questions from the text, at the cost of a few hundred output tokens it is already paying to produce |
| Hard scope - in | The label vocabularies as config; the desk; the article kind; political viewpoint; sentiment; the quote gate; per-label confidence; the classification ledger and its day roll-up; the console tab; the vertical proposal channel; the encoder alarm; the reference dataset; deleting the pipeline fingerprint |
| Hard scope - out | **The five month-sharded ledgers.** Migrating `item-health`, `feed-health`, `scores`, `seen` and `score-index` from `<YYYY>-<MM>.csv` to a day shard is a future **plan 24**: 13-plus modules, three published mirrors and the shared window control, and not one line of it is about what an article is about. **Placement, the ranker, the time rail and the `assemble` consolidation** are a future **plan 25**. Neither is deferred by this plan's rows; both are simply somebody else's work |
| ESCALATE triggers | 1. **The running worst-shard total in section 0.3 passes 150 minutes at the slow tail** - 30 minutes short of the 180-minute trigger, and the point at which one more row cannot be absorbed. It fires on the **total**, never on one row's share, because four additions each under ten percent of the headroom sum to more than the headroom. The projection today is 120.9 to 147.5, so the next row that adds output tokens after this plan's 185 fires it. 2. A schema conditional is proposed as a control - llama.cpp skips `if`/`then`/`else` silently, so it is not one. 3. A label the model chose becomes a path segment, a filename, a URL or a search-index term before a person committed it. 4. A removal row proposes to leave a test, a config key, a schema field or a doc paragraph behind |
| Chosen strategy | Vocabulary and identity first, then one call structure, then one label at a time behind its own row, then the ledger, then the surfaces that read it. Every label lands recorded-only before anything renders it |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

### 0.1 Standing rules, and they bind every row

**Deliver the intent, not the letter.** A structural fix matters more than a small diff. Where a row cannot be done correctly inside its stated file list, **expand the scope and say so in the pull request** - do not ship a band-aid to stay inside a list somebody wrote before the code was read. `CLAUDE.md` Rule #5 is the authority; this sentence is here because a row's file list reads like a fence and is meant to read like a start.

**No prisoners.** Every removed feature takes its code, its tests, its fixtures, its config keys, its schema fields, its docs and its `state/` writers with it, **in the same commit**. Git is the backup. A row that removes something and leaves a dead test, an orphan config key or a doc paragraph describing the removed thing has not finished, and its acceptance gate says so.

**Every label vocabulary is config, not code.** One JSON file holds the id, the display name, the definition text the model is scored against, and any weight. Change the definition text and the model labels against the new text on the next run: no Python edit, no schema regeneration, no release. The schema constrains the file's **shape**; its **contents** are free. This binds verticals, lenses, events, article kinds, political viewpoints, sentiment, and every vocabulary added after this sentence was written. Row #2 builds it and every labelling row reads it.

**A classification is a label, not a grade.** Nothing here scores a summary, ranks a publisher or selects what publishes. A model verdict that reaches no reader and selects nothing to publish is not a `CLAUDE.md` section 0a deviation - the same reasoning E1 settled for model-assisted labelling. Where a label does reach a reader it reaches them as a word about the **article**, never as a judgement of the **newsroom**.

**Two Reader rules, and they are the reason half the labels render nothing.**

- **Label the exceptions, never the rule.** A chip that appears on nearly every item is wallpaper by item four. If 84 percent of items are reports, `report` renders nothing.
- **Describe who is talking, never what is missing.** "Unverified" describes an absence; an absence is somebody's fault; the reader decides the fault is the publisher's, and the chip becomes a verdict on a newsroom. "The company's own account" describes a presence. Same warning to the reader, no blame.

**Budgets are guardrails, not rules.** The posture is to consume and process more when we can. The levers, with their real names and today's values, are in section 0.3. A row moves one **when it binds**, never pre-emptively, and says in its pull request which number bound.

**Every oracle is driven from a fixture, never from the committed archive.** `CLAUDE.md` Rule #12 and section 13. A per-item rule is proved on `backend/var/canary/` or on `tests/fixtures/`, which are fixed in size and can carry a case the archive has never produced. A question genuinely about the whole tree is asked once, on the total, by the producer that writes the tree - `idhazh validate-days` - and not by pytest.

**Additive contract fields are stamped in the commit that adds them.** Every row that adds a field to a persisted model names its `version` date-stamp and its `changelog` entry in its own acceptance gate, per `CLAUDE.md` section 11. A field added without them is a release blocker, not a follow-up.

### 0.2 What leaves this plan, and why the fingerprint is the biggest of them

**The pipeline fingerprint is deleted as a gate and as the eval-window key.** Owner decision, 2026-09-10, under `CLAUDE.md` section 0.

`pipeline_fingerprint` was meant to do two jobs. The first was a skip-if-unchanged contract: do not re-do work whose inputs did not move. **It was never wired to anything** - `git grep` finds no `skip_if_unchanged` key, no caller and no branch. The second was an eval window: a quality number counts only after N consecutive run-days at one fingerprint. In a system where prompts, lenses, verticals and now label definitions change weekly, that window never opens. It turns evolution into a fault and makes measurement unreachable in exactly the weeks measurement matters.

**What replaces it is a recorded input manifest that gates nothing** - the model id, the binary build, the decode parameters and a digest per config file, written into the run record so anybody can ask later what produced a number. One alarm survives: **if the prose changed while the model and the binary did not, say so.** It reports; it never blocks, and it never withholds a number.

Deleting it removes work this plan would otherwise have carried: the blocking `response_format` measurement, every two-digest scheme, `output_vocabulary_sha256`, all enum-elision work, and the two blockers those raised.

**The behaviour goes here; the field goes in a later plan, and the split is the point.** `pipeline_fingerprint` is named in **144 files, 129 of them outside `backend/tests/`, and 9 of them in `docs/`** - measured 2026-09-10 in this worktree with `git grep -l`, superseding the 93 and the 66 an earlier draft of this plan carried. Of those 144: 21 are frozen published day records, 21 are committed day-metrics files, 19 are committed fixtures, 15 are backend tests, four are published or state CSV mirrors, and 12 are generated schemas. **Row #1a stops the gating and stops the reading**, which is the whole of what the owner decided. **Row #1b drops the field from the contracts**, and this plan names it as deferred rather than scheduling it.

**Why those cannot be one commit.** `backend/idhazh/contracts/base.py:148` sets `extra="forbid"` on every model in this repository (verified 2026-09-10), so a payload carrying a key the model no longer declares is **rejected at read time, not ignored**. Those bytes are already on 21 frozen published days and 21 committed day-metrics files; `retention.dry_run` is `true` in `config/idhazh.json`, so nothing prunes them; and a published day is never rewritten. Dropping the field therefore means writing and **keeping** a read-side migration that strips a key from every payload older than the commit - a permanent shape carried for ever, bought in exchange for removing a field nothing reads. That trade is worth taking deliberately, on its own evidence, in its own row. It is not what stopping the gate is for.

### 0.3 The numbers this plan is priced against

Re-derived 2026-09-10 from the committed ledgers and the committed archive in this worktree. Every figure below replaces one the earlier draft of this plan carried from a superseded era.

| Figure | Value | Read from | Rows |
| --- | --- | --- | --- |
| Safety ceiling | **80 items a run** | `config/idhazh.json` `run.safety_ceiling_per_run` | - |
| Items one worker draws | **20** - fan-out is `min(ceil(items / run.shard_size), run.max_parallel)`, so 80 items over `max_parallel` 4 | `config/idhazh.json` | - |
| Shard timeout | **200 minutes** | `run.shard_timeout_minutes` | - |
| Escalate trigger | **180 minutes** | plan 11 section 0 | - |
| Worst shard since the ceiling halved | **66.9 minutes** | `state/runtime-counters.csv`, 96 rows dated 2026-09-06 or later, 5 days | 96 |
| Shard wall clock, same window | median **48.2 min**, p05 30.2, p95 62.9 | same | 96 |
| **Escalate headroom, before this plan or plan 11 spends any of it** | **113 minutes** (180 - 66.9) | derived | - |
| Decode rate | median **5.45 tok/s**, min 3.27, max 7.53 | `state/runtime-counters.csv`, whole ledger, 15 days | 265 |
| Decode rate since the ceiling halved | median **5.49 tok/s**, min 3.49, max 7.07 | same, 2026-09-06 or later | 96 |
| Prefill rate | median **9.84 tok/s**, min 8.52, max 43.0 | same | 265 |
| Summarize call | median **114.6 s**, p95 **312.7 s**, longest **800.9 s** | [`../docs/reference/measurements.md`](../docs/reference/measurements.md), from `state/item-health/2026-09.csv` | 4,117 |
| Output tokens an item | median **249**, p95 356 | `state/item-health/*.csv` | 7,937 |
| Input tokens an item | median **1,669**, p95 3,371 | same | 7,937 |
| Source words an item | median **519**, p95 1,894 | same | 8,751 |
| Published a day | median **360**, range 282-387, over the five finished days 2026-09-05 to 2026-09-09 | `frontend/public/digest/**/digest.json` | 5 days |
| Committed archive | **8,185 items over 20 finished days**; 8,478 counting 2026-09-10, which the pipeline was still writing | same | 21 days |
| `state/` on disk | **20.67 MB** in total | `state/**` | - |
| Items carrying at least one lens | **2,291 of 8,478 - 27.0 percent** | committed archive | - |
| Feed-declared kind, as published | `reporting` 7,158 (**84.4 percent**), `analysis` 415, `announcement` 381, `research` 283, `community` 139, `government` 102 | committed archive | 8,478 |

**The token budget every labelling row is priced against.** A "shard" here is one worker's slice of a run - 80 items over `run.max_parallel` 4, so 20 items - and `run.shard_timeout_minutes` 200 is the timeout on that worker's job. Ten percent of the 113-minute escalate headroom is 11.3 minutes a shard, which over 20 items is **33.9 seconds an item**, and at the measured 5.45 tok/s that is **about 185 new output tokens an item, for all of this plan's labels together**. Every row that adds output tokens states its share against that figure.

**But 113 minutes is not the headroom this plan actually has, and no row may be priced as though it were.** The 113 is the gap between today's worst shard and the trigger, before plan 11 spends any of it - and plan 11's rows 4, 5 and 6 land first by section 0.4. Charged in order, in minutes of worst-shard wall clock:

| Line | At the median 5.45 tok/s | At the slow tail 3.27 tok/s |
| --- | --- | --- |
| Worst shard on record, 2026-09-06 or later | 66.9 | 66.9 |
| Plan 11 row 6: the visual plan moves from the 4B to the 9B | **+9.7** | **+20.8** |
| Plan 11 rows 4-6: the element table, about 140 output tokens an item | +8.6 | +14.3 |
| This plan: 185 label output tokens an item | +11.3 | +18.9 |
| **Subtotal, if the prefix cache holds across every call** | **96.5** | **120.9** |
| Re-prefill at the new call boundary, if it does not (row #7) | +16.4 | +26.6 |
| **Worst shard total** | **96.5 to 112.9** | **120.9 to 147.5** |

**So the margin against the 180-minute trigger is 33 minutes at the slow tail, not 113** - and this plan's own 185 tokens are 11.3 of those 33, about a third. **The ESCALATE trigger in section 0 fires on this total, not on a single row's output tokens**, because four separate additions each under ten percent of 113 sum to more than the whole of what is left.

**What is measured here and what is not.** 66.9, 5.45 and 3.27 are read from `state/runtime-counters.csv`. 140 and 185 output tokens are budgets this plan and plan 11 chose. The two plan-11 row-6 figures are **estimates and are the softest numbers in the table**: they scale the measured 21.0 s the visual-planner stage costs an item on the 4B by the ratio of the two `llama-bench` decode rates (13.00 and 5.45, or 13.00 and 3.27), which assumes the whole 21.0 s is decode. It is not - some of it is prefill and process overhead - so both are upper bounds. The re-prefill line is derived in row #7. **Row #P4 replaces the two estimates with a measurement, and this table is re-derived when it does.**

Two cautions on the rest of it. The escalate headroom is measured against the **9B** in the `work` job, while the model that runs `visual_planner.py` today is **Qwen3-4B in the `visuals` job**. **The 4B's runner decode rate is on record and this plan may cite it: 13.00 +/- 0.03 tok/s, `llama-bench`, `ubuntu-latest`, 2026-08-22**, with the visual-planner stage at **mean 21.0 s an item, min 8.1, max 56.0, over 148 gaps**, and one whole run deciding 149 items in 51.7 minutes - all in [`../docs/reference/measurements.md`](../docs/reference/measurements.md). An earlier draft of this plan said that rate had never been measured. It had. **What has never been measured is the `visuals` job writing a `RuntimeCountersRow`**: all 265 committed rows come from `work`, so the 4B has no `cached_tokens`, no `peak_rss_bytes` and no prefill rate taken in the live digest path - and `measurements.md` says of its own `llama-bench` table that those figures "are not the prompt-cache cost in the live digest path". Row #P4 is scoped to that and to nothing else. And the shard figures are the trailing five days; the trigger in section 0 is re-read against the trailing **seven** days at the time a row lands, not against this table.

### 0.4 The external dependency this plan cannot start without

Call 1 and call 2 live in `backend/idhazh/visual_planner.py`, which runs in the `visuals` job on the 4B, not on the 9B in `work`. Plan 11 **rows 4, 5 and 6 are PENDING**, and row 6 is the one that retires the small model and folds the work back into the capable one. **No labelling row of this plan may land before plan 11 row 6.** Rows #P1 through #5, #13 and the ledger rows do not touch a model call and are not blocked.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | The property section 0a names, restated | - | A | PENDING | - | - | - |
| P2 | The reference dataset, built so a number cannot flatter us | - | A | PENDING | - | - | - |
| P4 | What one more call costs on the runner | - | A | PENDING | - | - | - |
| 1a | The fingerprint stops gating and stops being read | - | B | PENDING | - | - | - |
| 5 | The item id becomes sixteen characters of base32 | - | C | PENDING | - | - | - |
| 2 | Every label vocabulary becomes config | P1 | D | PENDING | - | - | - |
| P3 | A person labels the dev split and the test split | P2 | D | PENDING | - | - | human |
| 3 | Lens and event ids become slugs, and a retired id keeps its tombstone | 2 | E | PENDING | - | - | - |
| 4 | An event gets a lifecycle | 3 | F | PENDING | - | - | - |
| 13 | The encoder alarm | 3 | F | PENDING | - | - | - |
| 6 | The desk is a new field, and the feed's word stays where it is | 3 | G | PENDING | - | - | - |
| 7 | As many calls as the DAG needs, adjacent per item | P4, 6, plan 11 row 6 | H | PENDING | - | - | - |
| 8 | Call A labels: desk, lenses, article kind | 7, 2 | I | PENDING | - | - | - |
| 14 | The classification ledger, and the day file the console reads | 8 | J | PENDING | - | - | - |
| 9 | Confidence is a masked log-probability at one token | 8, 14 | K | PENDING | - | - | - |
| 15 | The console tab | 14 | K | PENDING | - | - | - |
| 10 | Political viewpoint, behind a gate written in code | 8, 14 | L | PENDING | - | - | - |
| 17 | The weights loop proposes a pull request and commits nothing | 14 | L | PENDING | - | - | - |
| 11 | Sentiment about one named subject | 8, 14, P3 | M | PENDING | - | - | - |
| 12 | The quote: seven conditions, three checks, ten codes | 7, 8 | N | PENDING | - | - | - |
| 18 | The closing measurement: is a read desk better than a declared one | P3, 14, 6 | N | PENDING | - | - | - |
| 16 | A vertical is proposed into a channel and promoted by a person | 14, 6 | O | PENDING | - | - | - |
| 19 | The keyword lenses retire, or they do not | 14, 13, 8 | P | PENDING | - | - | - |
| 1b | The fingerprint field is dropped from the contracts | 1a | - | **DEFERRED - not scheduled by this plan** | - | - | - |

**What a parallel group means, stated so a worker can check it.** **Within one group, no two rows may write the same file.** A glob counts as every file it covers, so `backend/tests/**` and `schemas/**` collide with any named file underneath them - and a row that edits any model under `backend/idhazh/contracts/` counts as writing every schema its edit regenerates, because the drift gate fails on a byte. Where two rows in a group collide, **narrow the glob to named files first, and only then move the row to its own group.** Every group above satisfies this as the file lists stand. **A row that widens its file list during execution re-checks its own group before it opens a pull request**, and section 0.1 expects that widening to happen.

**Ten of the sixteen groups hold one row, and three files are why.** `backend/idhazh/visual_planner.py` is written by rows 7, 8, 9, 10, 11, 12 and 16 - seven rows, and no narrowing helps because they all edit the same module. `docs/concepts/classification.md` is written by rows 8, 9, 10, 11, 13 and 18. `schemas/**` regenerates under row 5, because `ITEM_ID_PATTERN` lives in `backend/idhazh/contracts/base.py` and `ItemId` is used across the contracts, so row 5 rewrites most of the directory and nothing may regenerate a schema beside it. **So "parallel N = 2" is what the orchestrator may dispatch, not what this plan sustains**: it holds through groups A, D, F, K, L and N and nowhere else. **The structural fix is worth naming and is not taken here**: if the labelling rows each added a module under a new `backend/idhazh/classify/` package instead of extending `visual_planner.py`, four of the ten singletons - rows 7, 8, 11 and 16 - would become pairable. That is a design change to plan 11's call structure, and it belongs to whoever revises row #7, not to a reviewer's note.

**Group J holds one row on purpose.** The classification ledger is what the eight rows after it read - 9, 10, 11, 15, 16, 17, 18 and 19 - and a second row landing beside it would be reading a shape that is still moving.

**Rows 9, 10 and 11 depend on row 14, and that edge is new.** Each of them records a value onto a classification row, and row 14 is what defines that row's shape. Scheduling them before it meant three rows writing into a contract that did not exist.

**This table is the schedule; the numbered sections below are the drafting order and are not.** Section 9 holds row #5 and section 19 holds row #14, but row #5 runs in group C and row #14 in group J. A worker takes its position from the Depends-on and Parallel-group columns above and never from a section number.

---

## 2. Row #P1 - The property section 0a names, restated

- **Scope:** `CLAUDE.md` section 0a is amended so it says what it is protecting, rather than naming one mechanism. Today the LLM-as-judge clause is a list of banned mechanisms with two carve-outs bolted on; a plan that adds ten model-written labels has to argue each one separately against a rule that never states its own property.
- **Files touched:** `CLAUDE.md`, `AGENTS.md`, `docs/agents/guardrails.md`
- **Acceptance gates:** ASCII-only; every cross-link resolves; the three copies of the rule agree word for word on the property. No application suite - this row is documentation.
- **Oracle:** Take the three verdicts the clause already rules on - the prompt loop's model judge, model-assisted labelling under E1, and a model grading a published summary - and check the amended property returns the same answer for each **without naming a mechanism**. If the new wording flips one of them, it is a rule change, not a restatement, and it stops for the owner.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The property is: **a model verdict that reaches no reader and selects nothing to publish is not a deviation.** That single sentence already produces every ruling the clause makes today, including both existing exceptions | E1, O41; owner |
| 2 | **The summary-faithfulness clause stays, explicitly and in the amended text.** A model may not grade a published summary. The earlier draft of this row claimed the clause survived and then dropped it from its own replacement wording, which is how a guardrail is lost - not by argument, by a rewrite that forgot it | Fowler, 2026-09-10 |
| 3 | The clause keeps its ban on a model **selecting** what publishes. A label decides what a story is called; it never decides whether the story runs | `CLAUDE.md` section 0a |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Add an eleventh carve-out for classification | The clause has two carve-outs and would grow one per plan. A rule that needs an exception for ordinary work stops being read - the same reason the fine-tuning clause was narrowed on 2026-08-27 | `CLAUDE.md` section 0a design rationale |
| 2 | Leave section 0a alone and argue each label in its own row | Ten separate arguments against a rule none of them fits, and a reviewer with no shared property to check them against | Fowler |

---

## 3. Row #P2 - The reference dataset, built so a number cannot flatter us

- **Scope:** `corpus/reference-dataset-1/` - the frozen article set every accuracy number in this plan is measured on. `README.md` is its datasheet: what it is, who built it, how the split was drawn, what it may and may not be used for. `dataset.jsonl` is one row an article. `splits/dev.txt` and `splits/test.txt` are committed lists of `url_key`. `articles/<url_key>.txt` holds the article text, one file each.
- **Files touched:** `corpus/reference-dataset-1/**`, `backend/idhazh/contracts/reference_dataset.py`, `schemas/reference-dataset-row.schema.json`, `backend/utilities/build_reference_dataset.py`, `backend/tests/test_reference_dataset.py`, `docs/how-to/measure-a-classifier.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; every `url_key` in a split resolves to a row and to an article file; no `url_key` appears in both splits; no registrable domain appears in both splits.
- **Oracle:** **No source domain appears on both sides of the split.** Asserted directly over the two committed lists, which are fixed in size, so the check costs the same next year as today. This is the assertion the whole dataset exists for: two articles from one outlet share boilerplate, a house style and often a wire original, so a random split puts near-duplicates on both sides and every number comes out flattering.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **There is no `train/`.** A train split in the same directory invites fine-tuning on the measurement set, and that contamination is silent - the numbers get better and nothing says why | Owner, 2026-09-10 |
| 2 | **Split by source domain, not at random.** See the oracle | Owner, 2026-09-10 |
| 3 | Splits are **committed as lists**, never recomputed from a seed. A recomputed split moves when the row order moves, and then last month's number and this month's number were taken on different sets | `CLAUDE.md` Rule #10 |
| 4 | Article text lives in its own file, not inside `dataset.jsonl`. Editing one label then re-emits one small line instead of re-emitting the article - which matters because `prune.yml` rewrites this range of history on a schedule | `CLAUDE.md` section 8 |
| 5 | **`author_kind` is dropped.** A larger teacher model writes the reference summaries, so the field is `model` on every row and says nothing | Owner, 2026-09-10 |
| 6 | **The human faithfulness ledger is dropped; its contract is kept.** A model-written summary is a legitimate reference for **classification labels a person confirmed**, and is **never** a faithfulness reference. Keeping the contract means the ledger can return without a schema argument | Owner, 2026-09-10 |
| 7 | **Krippendorff's alpha is dropped.** The only agreement figure this plan acts on is row #11's kill criterion, and that one is stated directly in the units it kills on | Owner, 2026-09-10 |
| 8 | The datasheet says in its own words that this repository is public, so every article text under `corpus/` is readable by anyone. That cost was taken on 2026-08-28 and is restated here rather than assumed | `CLAUDE.md` section 0a |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Measure against the committed archive instead of a frozen set | The archive is not labelled, it grows every four hours, and reading it once an item is a Rule #12 breach. A number taken over a moving set cannot be compared with itself | `CLAUDE.md` Rule #12 |
| 2 | A random split with a fixed seed | Same defect as any random split: it puts one outlet's near-duplicates on both sides. The seed makes it reproducible, not correct | Owner |

---

## 4. Row #P4 - What one more call costs on the runner

- **Scope:** One dispatched run that makes the `visuals` job write a `RuntimeCountersRow`. **The 4B's decode rate is not what is missing** - `docs/reference/measurements.md` records `Qwen3-4B-Q4_K_M` at **13.00 +/- 0.03 tok/s** on `ubuntu-latest`, 2026-08-22, and the visual-planner stage at **mean 21.0 s an item over 148 gaps**. What is missing is that job's own **live-path** figures: `cached_tokens`, `peak_rss_bytes`, `prompt_seconds_total` and `n_ctx_configured`, none of which a `llama-bench` run produces and all of which the labelling rows are priced against. All 265 committed counters rows come from `work`.
- **Files touched:** `.github/workflows/digest.yml`, `backend/idhazh/cli.py`, `backend/idhazh/contracts/runtime_counters.py`, `schemas/runtime-counters-row.schema.json`, `backend/tests/test_workflows.py`, `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `shellcheck`; one dispatch of `digest.yml`.
- **Oracle:** After one dispatch, `state/runtime-counters.csv` carries at least one row attributable to the `visuals` job, and its decode rate is a number, not an absence. A row that cannot say which job it came from proves nothing, so the job name is on the row.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This row is a prerequisite, not a nicety. **Two lines of section 0.3's running-total table are estimates derived by scaling a `llama-bench` ratio, and this row replaces them with a measurement.** `measurements.md` says of its own bench table that those figures "are not the prompt-cache cost in the live digest path", which is exactly the cost every labelling row spends | `CLAUDE.md` Rule #10 |
| 1a | **An earlier draft of this row said the 4B's runner decode rate had never been measured. It had**, on 2026-08-22. The correction matters because the wrong claim made this row look like a blocker on arithmetic the plan could already do, and hid the measurement that is genuinely absent | Carmack, 2026-09-10 |
| 2 | The new column is additive and defaulted, so a counters row written before this lands still validates. `version` stamped and `changelog` appended in the same commit | `CLAUDE.md` section 11 |
| 3 | If plan 11 row 6 lands first and the `visuals` job is gone, this row still runs - it then measures the labelling call inside `work`, which is the number that actually binds | Fowler |

---

## 5. Row #1a - The fingerprint stops gating and stops being read

- **Scope:** `pipeline_fingerprint` stops being a gate and stops being the eval-window key. Every writer stops setting it and every reader stops reading it. **The field itself stays on the contracts**, relaxed to `Sha256 | None = None` where it is required today. A recorded input manifest takes over the job it was meant to do. Exactly one alarm survives: prose changed, model and binary did not.
- **Files touched:** `backend/idhazh/fingerprint.py`, `backend/idhazh/contracts/{fingerprint,run_manifest,day_metrics,eval_row,label_row,observation_index,public_eval,score_archive,summary,evidence,qualification,app_config}.py`, `backend/idhazh/evals/{archive,evidence,labels,score,writer}.py`, `backend/idhazh/{assemble,cli,corpus,drift,fetch,summarize,publish_day_metrics}.py`, `schemas/{fingerprint-row,run-manifest,day-metrics,eval-row,label-row,observation-index-row,public-eval,score-archive,summary,evidence-item,qualification-report,qualification-shard,app-config}.schema.json`, `state/fingerprints.csv`, **`frontend/src/lib/console/eval-instruments.ts`, `frontend/src/lib/server/model-work.ts`, `frontend/src/routes/console/+page.server.ts`, `frontend/src/routes/console/machine/+page.server.ts`, `frontend/tests/console-model-instruments.spec.ts`, `frontend/tests/console-model-rule.spec.ts`, `frontend/tests/support/reduction-input.ts`**, `backend/utilities/{build_canary_day,label_queue,measure_ledgers}.py`, `backend/tests/**`, `CLAUDE.md`, and the nine docs pages that name it - `docs/architecture/contracts/{determinism,schemas}.md`, `docs/architecture/publishing/{console-charts,retention}.md`, `docs/architecture/summarize/prompt.md`, `docs/archive/measurements-2026-08.md`, `docs/concepts/{config,evaluation}.md`, `docs/reference/github-actions.md`.
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the browser suite; the browser smoke on both console routes that displayed it; **no module under `backend/idhazh/` and no module under `frontend/src/` reads the field, asserted by a test over the source tree** - which is a fixed-size read of code a person wrote, not of data a run appended.
- **Oracle:** A quality number is produced on a run whose prompt text changed that morning. Today that number is withheld until three consecutive run-days at one fingerprint; after this row it is produced, and the manifest says what produced it. The point of the row is that the number **exists**, so the oracle asserts a value where there used to be an absence.

### What the operator loses, named rather than implied

`frontend/src/lib/server/model-work.ts` draws the **model-change boundary panel**: it compares the same two rates either side of a swap, and it splits the ledger on a `pipeline_fingerprint` transition. `docs/architecture/publishing/console-charts.md` states the rule in one line - "the boundary is a `pipeline_fingerprint` transition, never a `model_id` one" - and that doc is rewritten in this commit.

**`model_id` cannot stand in for it, and the module says why in its own docstring: measured 2026-08-27 over 2,232 rows, the stamp moved four times while every row named one model.** So a `model_id` split would have found none of those four boundaries. Once writers stop setting the fingerprint, the field stops moving and the panel finds no transitions at all.

**This row therefore does one of two things and may not do neither.** Either it repoints the boundary at the recorded input manifest's `run_id` - which changes on the same four occasions and on more besides - or **it deletes the panel, its module, its two specs and its doc section in this commit**, per section 0.1. A panel left drawing a field nobody writes is the worst of the three outcomes: it reports "no model change" for ever and an operator believes it.

`frontend/tests/console-model-instruments.spec.ts` is the second breaking spec and it breaks for a different reason: it asserts that `DRAWN_BY` and `NOT_A_MEASUREMENT` between them name **every** column of the published scores CSV exactly once. `pipeline_fingerprint` is a column of `frontend/public/scores/2026-09.csv` and stays one, so the entry stays; what changes is which of the two maps it sits in.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Deleted as a gate and as the eval-window key.** The skip-if-unchanged half was never wired to anything; the window half makes measurement unreachable in a system whose prompts and vocabularies change weekly. It turns evolution into a fault | Owner, 2026-09-10, `CLAUDE.md` section 0 |
| 2 | The replacement **records and gates nothing**: model id, binary build, decode parameters, and a digest per config file, on the run record, keyed by `run_id` | Owner, 2026-09-10 |
| 3 | **One alarm survives.** Prose changed while the model and the binary did not - say so. It reports; it never blocks and never withholds a number | Owner, 2026-09-10 |
| 4 | **The field stays; its readers go.** `pipeline_fingerprint` is named in **144 files, 129 of them outside `backend/tests/`, and 9 of them in `docs/`** (measured 2026-09-10 with `git grep -l`, superseding the 93 and 66 an earlier draft carried). Of those, 21 are frozen published days, 21 are committed day-metrics files and 19 are fixtures - **none of which this row touches, because none of them is a reader.** "No prisoners" applies to every reader and every gate, which is what section 0.1 is about | Section 0.1; decision 5 |
| 5 | **Dropping the field is row #1b and is not scheduled by this plan.** `backend/idhazh/contracts/base.py:148` sets `extra="forbid"`, so removing the key rejects every older payload at read time unless a read-side migration strips it - and that migration is then kept for ever. `retention.dry_run` is `true`, so nothing prunes the 42 committed payloads carrying it, and a published day is never rewritten. Splitting the two lets the behaviour land this week and the shape argue its own case later | Fowler, 2026-09-10; `CLAUDE.md` section 11 |
| 6 | Where the field is **required** today it becomes `Sha256 \| None = None` - `DayMetricsRecord.pipeline_fingerprint` is the one verified case (`backend/idhazh/contracts/day_metrics.py:378`). That is a **relaxing** change: every payload already on disk still validates, and no read-side migration is needed. `version` stamped and `changelog` appended | `CLAUDE.md` section 11 |
| 7 | This deletion is what removes the blocking `response_format` measurement, every two-digest scheme, `output_vocabulary_sha256` and all enum-elision work from this plan. None of them is deferred; they had no purpose once the gate went | Owner, 2026-09-10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the fingerprint and widen the window from three run-days to seven | Widening a window that never opens makes it open less often. The defect is not the width | Owner |
| 2 | Drop the field in the same commit that stops the gate | **This was the earlier draft's plan and it is reversed here.** `extra="forbid"` turns the drop into a permanent read-side migration bought to remove a field nothing reads, and it puts 42 frozen committed payloads and 19 fixtures inside a row whose actual subject is a gate. Deferred to row #1b, not refused | Fowler, 2026-09-10 |
| 3 | Keep the field **and** keep its readers, changing only the eval window | Then the model-change panel goes on splitting on a stamp nobody advances, which is a wrong answer rather than a missing one | Decision 4 |

---

## 5a. Row #1b - The fingerprint field is dropped from the contracts

**DEFERRED. This plan names it so it is not mistaken for work being done, and does not schedule it.**

- **Scope:** `pipeline_fingerprint` is removed from every contract model, every generated schema, every fixture and every committed payload shape, with the read-side migration that lets an older payload still read.
- **Depends on:** row #1a. Nothing may drop a field that something still reads.
- **What it must price before it is scheduled:** the cost of carrying a read-side migration for ever against the cost of carrying an unread field for ever. The second is 42 committed payloads and 19 fixtures today and grows by two files a day; the first is one function that never gets deleted. Neither has been measured, and this plan does not measure it.

---

## 6. Row #2 - Every label vocabulary becomes config

- **Scope:** One JSON file that holds every label vocabulary this plan uses: id, display name, the **definition text the model is scored against**, and any weight. The contract constrains the shape; the contents are free. `config/taxonomy.json` already does this for verticals, lenses and events; this row extends it and adds the definition text those three never had.
- **Files touched:** `config/taxonomy.json`, `backend/idhazh/contracts/taxonomy.py`, `schemas/taxonomy.schema.json`, `backend/idhazh/config.py`, `backend/tests/test_contracts.py`, `tests/fixtures/**`, `docs/concepts/taxonomy.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Change one label's **definition text** in a fixture config and the prompt the builder produces changes, with **no Python edit and no schema regeneration**. Asserted by building the prompt twice against two fixture configs and comparing the two strings. A vocabulary that needs a code change to move its own definition is not config, whatever file it lives in.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The **definition text is the label**, as far as the model is concerned. An id and a display name tell the model nothing; `research` means whatever sentence we wrote next to it | Andre |
| 2 | Nothing is derived from an id or a display name. Deriving lens assignment from the id was measured at 88.2 percent of items, because `ai` sits inside `said` | `LensDef.keywords` docstring, measured 2026-08-26 |
| 3 | The schema gates **shape only** - required keys, id pattern, length bounds. It never enumerates the members, or adding a label becomes a schema change and a release | Owner, 2026-09-10 |
| 4 | `docs/concepts/taxonomy.md` is written in this row. **It does not exist today**, which is why nobody in three rounds of review could say what a vertical is as against a lens without re-deriving it | Section 12 |

---

## 7. Row #P3 - A person labels the dev split and the test split

- **Scope:** A human labelling pass over `corpus/reference-dataset-1/`. This is a **row with a person in it**, not a coding row, and it has its own PENDING state because four measurement rows cannot start until it is done.
- **Files touched:** `corpus/reference-dataset-1/dataset.jsonl`, `corpus/reference-dataset-1/README.md`, `backend/utilities/label_reference_dataset.py`
- **Acceptance gates:** every row in both splits carries a label for every field this plan measures; the datasheet records who labelled, when, and against which definition text.
- **Oracle:** A second person labels 60 items of the dev split independently, and the two labellings are compared. This is the row that produces the human-human agreement figure row #11's kill criterion is stated against - **if two people cannot agree on sentiment above 0.6, no model number on it means anything** and row #11 does not ship.
- **Subagent:** human. An agent may prepare the tooling and the sheet; an agent may not supply the labels.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The labels are taken **against the committed definition text**, and the datasheet records which version. A label taken against last month's definition is measuring a different question | Row #2 |
| 2 | This row is on the Reckoner with its own status because the earlier draft of this plan had measurement rows starting before any labelled data existed. A prerequisite that is not a row is a prerequisite nobody schedules | Fowler, 2026-09-10 |

---

## 8. Row #3 - Lens and event ids become slugs, and a retired id keeps its tombstone

- **Scope:** `LensId` and `EventType` stop being closed `StrEnum`s in Python and become `Slug`, validated against the committed vocabulary at read time. A retired id keeps rendering in the days that already carry it.
- **Files touched:** `backend/idhazh/contracts/taxonomy.py`, `backend/idhazh/contracts/{article,digest_day,digest_view}.py`, `schemas/**`, `backend/idhazh/tag.py`, `frontend/src/**`, `backend/tests/**`, `tests/fixtures/**`, `docs/concepts/taxonomy.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the browser smoke on a day carrying a retired lens.
- **Oracle:** **A fixture day carrying `ai-roi` still validates and still renders after the id is dropped from the active vocabulary.** `ai-roi` is real: it is retired in `config/taxonomy.json` with `retired_on` 2026-08-30, and it is carried on **18 published items across three committed days - 2026-08-27 (12 items), 2026-08-28 (3) and 2026-08-29 (3)**, measured 2026-09-10. **Copy one of those item records into `tests/fixtures/` and drive the oracle from the fixture** - reading the committed archive to find them is a Rule #12 breach, and the fixture also survives the day those three days age out of retention.
- **Frontend degradation:** an id with no committed display name renders as the raw slug. Not a blank, not a crash, not a dropped chip.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A closed Python enum means adding a lens is a code change, a schema regeneration and a release. That is the opposite of section 0.1's config rule, and it is why the vocabulary has not moved | Section 0.1 |
| 2 | **A retired id is tombstoned, never deleted.** The precedent is already set and already paid for: the taxonomy changelog of 2026-08-30 says "ai-roi is tombstoned rather than deleted so days that carry it stay valid" | `Taxonomy.__changelog__`, 2026-08-30 |
| 3 | This is a **breaking** retype on three published schemas. `version` stamped, `changelog` appended, read-side migration in the same commit | `CLAUDE.md` section 11 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the enums and regenerate on every vocabulary change | Ten minutes of build and a release for a word. It also puts the vocabulary in two places, and they drift | Fowler |
| 2 | Drop a retired id from old payloads on read | Then a published day silently changes what it said. The day is frozen; the vocabulary moved | `CLAUDE.md` section 11 |

---

## 9. Row #5 - The item id becomes sixteen characters of base32

- **Scope:** `item_id` becomes `<vertical>-<16 chars of Crockford base32 over bytes.fromhex(url_key)[:10]>`, for example `ai-3k7wq2m9x4hbn5tz`. Forward-only. `ITEM_ID_PATTERN` widens to accept both shapes and never contracts: `^[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{2,}$` today becomes `^[a-z0-9]+(?:-[a-z0-9]+)*-(?:[0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})$`, where the second branch is the 32-symbol Crockford alphabet with `i`, `l`, `o` and `u` excluded.
- **Files touched:** `backend/idhazh/rank.py`, `backend/idhazh/contracts/base.py`, **`schemas/**`**, `backend/tests/test_contracts.py`, `backend/tests/test_discover.py`, `backend/tests/test_rank.py`, `docs/architecture/publishing/layout.md`, `docs/architecture/publishing/visuals.md`, `docs/architecture/sources/freshness.md`
- **Why `schemas/**` and not one file:** `ITEM_ID_PATTERN` is what `ItemId` is built from in `backend/idhazh/contracts/base.py:39-64`, and `ItemId` is used across the contracts, so widening the pattern regenerates every schema that carries an item id. That is also why this row holds parallel group C alone.
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the browser smoke on a day carrying both id shapes.
- **Oracle:** **`assign_ids` is deleted and no test needs it.** The real prize is not the width. `assign_ids` resolves a collision by *stepping* the number, and the stepped id depends on which other addresses were in that run's pool - so a collided id is **not stable across the runs of one day**, which is the single property `item_id` exists to guarantee. The oracle drives two different candidate pools containing the same article and asserts the same id both times, which today is false for a collided item and cannot be made true while a collision loop exists.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Deterministic by construction**, because it is a slice of a digest the payload already carries. 80 bits. Crockford base32 excludes I, L, O and U, and lowercase is a subset of `[a-z0-9]`, so the slug grammar survives untouched | Owner, 2026-09-10 |
| 2 | **Not `uuid4`.** Two `item_id` guards are same-day: a random id makes run 2 mint a fresh id for run 1's article, and `build_day` then appends a second copy of the same story to the same page | Owner, 2026-09-10 |
| 3 | **Not `uuid5` or `uuid8`.** Both are 32 hex characters and trip the hex guard on every single item | Owner, 2026-09-10 |
| 4 | Collisions on ten decimal digits are otherwise a once-in-many-years event (estimate, order of magnitude only). The collision **loop** is the defect, not the collision rate | Owner, 2026-09-10 |
| 5 | **Forward-only.** Old ids are never rewritten. Nothing may ever sort ids across days once both shapes exist, because the two shapes do not order against each other | Owner, 2026-09-10 |
| 6 | Costs, stated: frontend zero, published payloads zero, observability zero, charting zero. Everything downstream treats `item_id` as an opaque string | Owner, 2026-09-10 |

### Two traps this row must clear

**`backend/tests/test_contracts.py::test_no_hash_appears_in_any_published_path` matches `[0-9a-f]{16,}`.** A 16-character base32 id whose every character happens to fall in `[0-9a-f]` matches it. That is a probability of about 2 to the power of -16 an item - **roughly one red build every 182 days, on a day nobody touched the code**, which is the worst kind of failure because there is nothing to bisect. The guard is widened to test the *shape* it means - a hex digest is 32 or 64 characters, and it is not the item id - and `backend/tests/test_discover.py::test_no_hash_appears_in_any_planned_item_id` gets the same treatment.

**`docs/architecture/publishing/layout.md` and `docs/architecture/publishing/visuals.md` currently forbid hash-like names, and both name the ten-digit id in the rule.** `layout.md` says "No hash appears in any path, filename or URL" and calls the id "`<vertical>-<ten digits>`... decimal and short enough to read back"; its rejected-alternatives table repeats it, and `visuals.md` cites the rule by test name. **All three passages are rewritten in this commit, not left standing.** A doc that contradicts the code is worse than a doc that is missing, because a reader believes it.

---

## 10. Row #4 - An event gets a lifecycle

- **Scope:** `EventDef` extends `Lifecycled`, so an event can be retired the way a lens and a vertical already can.
- **Files touched:** `backend/idhazh/contracts/taxonomy.py`, `schemas/taxonomy.schema.json`, `config/taxonomy.json`, `backend/tests/test_contracts.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A retired event in a fixture taxonomy validates, is not offered to the model, and still renders on a fixture day that carries it - the same three assertions row #3 makes for a lens, against the vocabulary that could not make them.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`EventDef` extends plain `Model` today** - no `status`, no `retired_on` - while `VerticalDef` and `LensDef` both extend `Lifecycled`. Verified 2026-09-10. So row #3's tombstone rule silently does not cover events, and the earlier draft of this plan claimed it did | Fowler, 2026-09-10 |
| 2 | **Its own row, separate from row #3.** This is a purely **additive** change with defaults; row #3 is a **breaking** retype. Bundling an expand into a break makes the break impossible to revert on its own | Fowler; `CLAUDE.md` section 11 |
| 3 | Additive with defaults, so a taxonomy written before this still validates. `version` stamped, `changelog` appended | `CLAUDE.md` section 11 |

---

## 11. Row #6 - The desk is a new field, and the feed's word stays where it is

- **Scope:** `desk` is a **new field beside `Article.vertical`**, written from the model's whole-article label. The digest groups by `desk`. `Article.vertical` keeps carrying the feed's declared word and is not repointed.
- **Files touched:** `backend/idhazh/contracts/article.py`, `backend/idhazh/contracts/{digest_day,digest_view}.py`, `schemas/**`, `backend/idhazh/{assemble,rank,cli}.py`, `frontend/src/**`, `backend/tests/**`, `docs/concepts/taxonomy.md`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the browser smoke on a day where a desk differs from its vertical; **no occurrence of the word `desk` is left in `backend/idhazh/contracts/digest_day.py` still meaning the vertical** (decision 7).
- **Oracle:** An item whose desk differs from its vertical validates, publishes, and renders under the desk - with its `item_id` still addressed `<vertical>-`. That combination is exactly what a repointed `vertical` makes impossible, so the oracle proves the choice rather than the code.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`Article.vertical` may not be repointed.** `Article._identity_is_rebuilt_not_trusted` asserts `item_id.startswith(f"{self.vertical}-")` (verified at `backend/idhazh/contracts/article.py:165`), so repointing it rejects, at read time, every item whose desk moved | Verified 2026-09-10 |
| 2 | **Classification is re-decided between runs, not frozen on first publish.** The world changes between runs even though it does not change during one | Owner, 2026-09-10 |
| 3 | **A re-decide path needs an explicit carve-out and will not fall out of existing behaviour.** `plannable_items` skips a published item **unconditionally** - `if item.item_id in published: continue`, verified at `backend/idhazh/cli.py:1398`. The carve-out is written in this row, with the ceiling it re-decides under | Verified 2026-09-10 |
| 4 | Costs, taken with eyes open: `energy-0483729104` can render under the AI desk, and a link shared in the morning can show the story on a different desk by evening | Owner, 2026-09-10 |
| 5 | **`DigestVerticalRef.count` keeps meaning the vertical count, and `desk_count` is added beside it** as `int \| None = None`. The frontend prefers `desk_count` where it is present and falls back to `count`. Redefining `count` in place was the earlier draft's plan and is refused: 21 frozen published days already carry it, a published day is never rewritten, and nothing in the payload would say which of the two meanings a given day's number holds. Contracting `count` is a later commit, once no day in the retention window still needs it | Fowler, 2026-09-10; `CLAUDE.md` section 11 |
| 6 | `considered`, `too_old` and `below_feed_floor` stay **vertical** facts, because collection is still per feed. Both `digest-day` and `digest-view` are stamped, and the changelog entry says which field is which | Fowler, 2026-09-10 |
| 7 | **`desk` already means the vertical in `backend/idhazh/contracts/digest_day.py`, sixteen times, and this row rewrites every one of them in the same commit.** `DigestVerticalRef`'s own docstring opens "One desk of the day"; the module docstring at line 37 says "`considered`, `too_old` and `below_feed_floor` on a desk are what the planning step already knew and threw away"; four field descriptions and two validator messages use it the same way. Introducing a `desk` field while that prose stands leaves one word meaning two things in one file, and the second reader is the one who gets it wrong | Fowler, 2026-09-10; section 0.1 |
| 8 | **The feed floor question is decided here, not left open.** `rank.plan_vertical` plans nothing when `eligible_feeds < min_feeds`, and `below_feed_floor` means "collected but not rendered" (verified at `backend/idhazh/rank.py:373-377`; `ai` has `min_feeds` 35, the other four 21). Grouping by desk lets an above-floor vertical's items land in a below-floor desk that renders while flagged as not rendering. **Ruled: an item whose desk is below its own floor falls back to its feed vertical.** The floor is a statement about supply, and supply is still collected per feed | Owner, 2026-09-10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Repoint `Article.vertical` to the model's label | Rejected at read time by the contract's own identity validator, on every item whose desk moved | Decision 1 |
| 2 | Freeze the desk on first publish | The world changes between runs. Freezing makes the label a fact about when we happened to see the story | Owner |
| 3 | Move the feed floor onto the desk | The floor counts feeds, and a feed declares a vertical, not a desk. Moving it means counting feeds for a group no feed belongs to | Decision 8 |
| 4 | Redefine `DigestVerticalRef.count` to mean the desk count | 21 frozen published days already carry it under the old meaning, and a published day is never rewritten. The same number would mean two things with nothing in the payload to say which | Decision 5 |

---

## 12. Row #7 - As many calls as the DAG needs, adjacent per item

- **Scope:** The call structure changes from two fixed calls to a DAG the code walks: elements, then every label and score, then the summary and the visual plan. The conditional political gate is **DAG code that inspects a reply and dispatches another call**, not a schema conditional.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/summarize.py`, `backend/idhazh/llm/server.py`, `backend/idhazh/prompts/**`, `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `backend/tests/test_contracts.py`, `backend/tests/**`, `docs/architecture/summarize/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a recorded-response replay with no network; one dispatch reading `cached_tokens` **on every call, not once**, and `peak_rss_bytes` at the raised window.
- **Oracle:** **Every call after the first reports `cached_tokens` at least equal to the first call's prompt token count.** One cache slot, one article, prefilled once. Plus: driving the same item twice, once with the gate firing and once without, produces the same first two calls byte for byte - which is what proves the gate is dispatch and not a different prompt.

### The window, and why it moves in this commit

**A third call does not get its own window. It extends the sequence in one slot**, and that sequence is already at 97 percent of the window today.

| Case | Sequence | Against `n_ctx` 16,384 |
| --- | --- | --- |
| Worst article on the ledger, two calls (plan 11 row 5, on record in `docs/reference/measurements.md`) | **15,889** | 97 percent, margin 1.03x |
| Same article, third call, instruction at its floor | 15,889 + 300 + 185 = **16,374** | 99.9 percent, margin **1.0006x** - ten tokens |
| Same article, third call, instruction at a realistic length | 15,889 + 600 + 185 = **16,674** | **overflows by 290 tokens** |

**300 is a floor, not an estimate.** The third call's instruction must carry the definition text of every vocabulary it labels against: 5 verticals, 6 active lenses, 5 article kinds, 8 political values and 3 sentiment values - **27 definition sentences** (counted from `config/taxonomy.json` and sections 14, 17 and 18, 2026-09-10). 300 tokens allows about 11 tokens a sentence. A definition text worth scoring against is longer than that, so the realistic row is the one to plan on.

**So this row raises `models.summarize.inference.n_ctx` in the same commit that adds the third call**, and it extends `backend/tests/test_contracts.py::test_the_longest_article_the_cap_allows_still_fits_the_window` to sum **every call in the DAG** rather than one. That test exists and today it sums exactly one prompt and one `max_output_tokens` (`backend/tests/test_contracts.py:1105`, verified 2026-09-10). Left alone it goes on passing while the real sequence overflows, which is the failure mode its own docstring was written about.

**The dispatch this row must run, and the result that changes the design.** Set `n_ctx` to 32,768, dispatch one run, and read `peak_rss_bytes` and the decode rate off the new `state/runtime-counters.csv` rows. **If peak RSS passes about 14.5 GB of the runner's 16 GB, or decode falls more than 10 percent, the third call is cut and the labels go into call 1 beside the elements** - which is rejected alternative 1, taken on evidence rather than on preference, at the cost the alternative names.

**What the ledger already says about that risk**, measured 2026-09-10 over `state/runtime-counters.csv`: at `n_ctx` 8,192 peak RSS was median **12.94 GB** (min 11.16, max 14.10, n=12); at 16,384 it was median **12.54 GB** (min 11.44, max 13.30, n=28). **Doubling the window did not raise the footprint** - the weights dominate it. That is evidence the second doubling is affordable, not proof, because the max at 8,192 came within 1.9 GB of the runner's memory and nothing has been run at 32,768.

### What the extra boundary costs in prefill

**Each new call boundary re-prefills, and the row states the cost per boundary rather than once.** The article and the shared system turn prefill once and stay cached. What may not stay cached is the **previous call's generated output**: call 3 re-renders call 2's answer as an assistant turn through the chat template, which adds wrapper tokens the model never generated, and if that re-render does not tokenise identically the common prefix ends there.

At the second boundary that is call 2's output plus the third instruction: **185 + 300 to 600 = 485 to 785 tokens**. At the measured prefill median of 9.84 tok/s that is **49 to 80 seconds an item, or 16.4 to 26.6 minutes a shard** - the line section 0.3's table charges, and on its own it is half the margin that table leaves.

**Plan 11 row 3c, "own the prompt bytes", becomes a candidate to land before this row.** It is DEFERRED today pending a runner measurement of 209 re-prefilled tokens ([`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md)). This row makes that measurement worth taking, because it adds a second boundary with the same defect and a bigger payload.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **O43 is amended.** It reads "Exactly two model calls per item. Always. No gate, no budget and no failure removes one." It becomes: **as many calls as the DAG needs, adjacent per item, sharing one cache slot.** What O43 was protecting survives untouched - the call that writes the summary runs for every item that publishes, and no gate, budget or failure removes it | Owner, 2026-09-10, `CLAUDE.md` section 0 |
| 2 | **Three calls is the shape this plan needs.** Elements; then all labelling and scoring; then the summary and the visual plan. **Labels decode before the summary**, so the summary can be written knowing what kind of piece it is summarising | Owner, 2026-09-10 |
| 3 | **Calls are adjacent per item.** `n_parallel` is 1 on both configured models (verified in `config/idhazh.json`), so there is one cache slot: running every call-1 and then every call-2 evicts the article's prefix on every single item, silently, with no error and no failed request | Plan 11 row #3 decision 1 |
| 4 | **A JSON-Schema conditional is not a control.** llama.cpp lists `if`, `then` and `else` as unsupported, and an unsupported keyword is **skipped with no error**, so a conditional schema looks like a gate in the source and is not one at runtime. Every conditional in this plan lives in Python | Andre; measured behaviour of the grammar converter |
| 5 | Plan 11's E5 recovery survives: on a reply cut by the output budget, code recovers the closed `summary` object, and a contract test asserts `summary` precedes `visual` in the generated schema. The new labelling call is **before** both, so a cut in it costs labels and not the summary | Plan 11 row #3 decision 5, E5 |
| 6 | The output budget is **derived** from the contract's bounds and re-derived whenever a bound changes, including every bound this plan adds | Plan 11 row #3 decision 6 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep two calls and put the labels in call 1 beside the elements | Then the labels decode before the model has been asked to reason about the article as a whole, and the summary cannot use them. The ordering is the point | Owner |
| 2 | Express the political gate as `if`/`then`/`else` in the response schema | It compiles to nothing. A control that is silently skipped is worse than no control, because the code reads as though one exists | Decision 4 |
| 3 | Run all first calls, then all second calls, to batch the prompts | One cache slot. Every item's article re-prefills, at a measured prefill median of 9.84 tok/s over a median 1,669 input tokens | Decision 3 |

---

## 13. Row #13 - The encoder alarm

- **Scope:** One committed `.bin` of **11 vectors - 5 active verticals and 6 active lenses - at 384 int8 dimensions, 4,224 bytes** - compared against the item vector `assemble` already writes. It publishes one counter. It never picks a label.
- **Files touched:** `backend/idhazh/assemble.py`, `backend/utilities/build_taxonomy_vectors.py`, `config/taxonomy-vectors.bin`, `backend/idhazh/contracts/day_metrics.py`, `schemas/day-metrics.schema.json`, `backend/tests/test_assemble.py`, `docs/concepts/classification.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** The run makes **zero new encoder passes** and adds **zero bytes an item**, asserted by counting calls to the embedder over a fixture day and comparing the day payload's byte length before and after. An alarm that costs a pass an item is not an alarm, it is a second classifier.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It stays. It is the best-behaved row in the plan: it reuses a vector we already compute, `cosine_int8` already exists at `backend/idhazh/assemble.py:316`, and 4,224 bytes is committed once | Owner, 2026-09-10, over Carmack's cut list |
| 2 | **Alarm on the delta, never on an absolute threshold.** The cosine between a 384-dimension int8 item vector and a label vector is uncalibrated and weak in absolute terms; a fixed threshold would be a number somebody picked. A change in the delta is a fact | Carmack |
| 3 | **It never picks a label.** One counter on the day file, read by the console. If it ever selects, it is a classifier and needs everything a classifier needs | Section 0.1 |
| 4 | The committed `.bin` carries a header with its dimension count, its vector count and **`taxonomy_digest`** - the same name row #14 decision 4 uses for the same value, so there is one word for it in this plan - **and a stale file fails loudly** rather than quietly comparing against last month's lenses | Fowler |
| 5 | **The vectors file lives in `config/`, not `state/`.** `state/` is what a run appends; this file is built by a person running `backend/utilities/build_taxonomy_vectors.py` and committed, exactly like `config/taxonomy.json` it is derived from. Putting it in `state/` would put it inside the retention and prune machinery that governs run output, where it does not belong | `CLAUDE.md` section 3 |
| 5 | It is **not** placed under `frontend/public/` unless a browser fetches it. A file in the served tree is a file in the page weight budget | `CLAUDE.md` Rule #2 |

### Rejected alternatives

| # | Option | Why rejected, with the arithmetic | Authority |
| --- | --- | --- | --- |
| 1 | Encode the full article and compare that | **Physically blocked.** MiniLM-L6 has a 512-position table, and a p50 article is about 1,277 tokens - five chunked passes, and fifteen at p90 | Carmack |
| 2 | Add a second per-article vector for the alarm | The honest comparison is against the **8 MB monthly vector budget**, not the 1.5 MB browse-index budget, and a second vector adds about 1.6 MB a month, so **it would fit**. It is rejected for the stronger reason: the alarm does not need it | Carmack, correcting the earlier draft's budget |

---

## 14. Row #8 - Call A labels: desk, lenses, article kind

- **Scope:** The labelling call. It returns a desk, a lens list and an article kind, each drawn from the committed vocabulary of row #2. Recorded only - nothing on this row renders.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/prompts/**`, `backend/idhazh/contracts/article.py`, `backend/idhazh/contracts/{digest_day,digest_view}.py`, `config/taxonomy.json`, `schemas/**`, `backend/tests/**`, `docs/concepts/classification.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a recorded-response replay; **the row's share of the label-token budget stated in the pull request, priced against the decode rate row #P4 records** and not against the 185 tokens section 0.3 derives from the 9B.
- **Oracle:** A reply naming a label that is not in the committed vocabulary is refused, and the item keeps its fallback rather than losing the field. Driven from a fixture reply, so it tests the refusal and not the model.

### The five article kinds, final

| Kind | Definition the model is scored against | What a reader sees |
| --- | --- | --- |
| `report` | A journalist described what happened and attributed the contested parts to named people | **nothing** |
| `analysis` | The piece explains why something happened, on a subject its publisher does not gain from | **nothing** |
| `research` | A study, a paper or a benchmark, stating a method a reader could check | a one-word chip |
| `announcement` | The organisation the story is about is publishing its own news, and nobody independent has checked it | `company's own account` or `government's own account` |
| `opinion` | A named author is arguing a position | a one-word chip |

**There is no `other`, the field is never absent, and the fallback is the feed's declared kind.** That fallback already exists and already has a distribution: measured over the 8,478 committed items, the feed prior is `reporting` on 7,158 (84.4 percent), `analysis` on 415, `announcement` on 381, `research` on 283, `community` on 139 and `government` on 102. The map from those six `SourceKind` members to these five kinds lives in `config/taxonomy.json` and not in Python.

**`report` and `analysis` render nothing** because between them they are almost every item, and section 0.1's first Reader rule says a chip on nearly every item is wallpaper.

**A warning that belongs to this row and no other.** `announcement` is the only label here that makes a reader **discount** a story. One false positive on a real piece of reporting kills the credibility of every chip on the page, including the ones that were right. **When the model is unsure, it emits nothing** - the fallback stands and the chip does not render.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Labels are drawn from the **committed** vocabulary only, by grammar. A word the model invents cannot be assigned, which is also what makes row #16's proposal channel safe | Section 0.1; row #16 |
| 2 | **The model writes `model_lenses`; `tag.tagged` keeps writing `Article.lenses`, and `Article.lenses` stays the published field.** Two writers, one published, until somebody has looked at the comparison | Fowler, 2026-09-10 |
| 3 | **The deletion criterion for the keyword lenses is a person, not a threshold.** Promotion happens when a person has read row #15's diverging bar and the owner says so. A threshold here is a number somebody picked, and it would decide a vocabulary question on arithmetic | Owner, 2026-09-10 |
| 4 | `desk`, `model_lenses` and `article_kind` are **additive with defaults** on `Article` and on both digest payloads. `version` stamped and `changelog` appended in the same commit, one line each in the pull request | `CLAUDE.md` section 11 |
| 5 | `source_kind` stops being an authority and becomes **`feed_prior_kind`**, marked non-authoritative on the contract, read only by the eval writer. It stays in `config/sources.json` under its existing key, `kind`. **If the model were the sole source of the label, no accuracy number would exist at all** - disagreement with the feed prior is a drift detector, never ground truth, and nobody tunes the model to match it | Owner, 2026-09-10 |

---

## 15. Row #12 - The quote: seven conditions, three checks, ten codes

- **Scope:** One pulled quote an item, or none. The model returns **sentence addresses and a speaker and never types the characters**; code slices the article and checks.
- **Files touched:** `backend/idhazh/elements.py`, `backend/idhazh/visual_planner.py`, `backend/idhazh/contracts/element.py`, `schemas/element-table.schema.json`, `frontend/src/**`, `backend/tests/{test_elements,test_visual_planner,test_contracts}.py`, `docs/architecture/extraction/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the browser smoke on an item carrying a quote and on an item carrying a failing code.
- **Oracle:** For every one of the ten codes, drive the condition that produces it from a fixture and assert the emitted code. The collected set must equal the enum exactly. **And: for every failing code, the article's quote text appears nowhere in the rendered DOM.**

**The seven conditions.** All of them, or no surface. The kind allows a quote (`report`, `analysis`, `opinion` only); the item is not truncated; the speaker is named and appears in text we actually read; the quote says something the summary does not; it is a complete sentence or a clean clause inside the word cap; there is one an item; the title and the summary's first line come first.

**The three checks.** The model names sentence addresses and a speaker, never characters. Code slices that span and compares by **string equality, whitespace-normalised only** - **no fuzzy match, because a quote that is 97 percent the same is a misquotation**. The speaker must appear verbatim in the text with `attribution` of `named` or `self_reported`.

**The ten codes**, a closed snake_case `StrEnum`: `verified`, `text_mismatch`, `span_not_found`, `speaker_absent`, `speaker_unnamed`, `quote_in_truncated_item`, `kind_refuses_quote`, `restates_summary`, `too_long`, `no_quote_offered`.

**Exactly three render a marker: `text_mismatch`, `span_not_found`, `speaker_absent`.** Those three are our extraction and our model reading the same page and disagreeing, which is a fact about the item. The other seven are our own editorial decisions, and a reader's page is not where we narrate our own machinery.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Never traded: a failing code never renders the quote text.** Not partially, not greyed, not blurred, not behind a click, not in a title attribute. This is the one line in the row with no trade-off attached to it | Owner, 2026-09-10 |
| 2 | The heuristic **chooser** is deleted; the string **gate** stays. Choosing which sentence is quotable is a judgement the model makes better; checking that the characters match is arithmetic the model cannot be trusted with | Andre |
| 3 | **`Element.attribution` is `UntrustedLine \| None` today** (verified at `backend/idhazh/contracts/element.py:280`), which is a free-text line. Check 3 compares it against `named` and `self_reported`, so **it must become an enum in this row or check 3 gates nothing** | Fowler, 2026-09-10 |
| 4 | **The enum already exists and is not written here - it is moved.** `backend/idhazh/visual_planner.py:712` declares `Attribution = Literal["named", "self_reported", "anonymous", "unattributed"]` and uses it at lines 768 and 817 (verified 2026-09-10). The refactoring is **Move Type**: lift it into `backend/idhazh/contracts/element.py`, import it back into `visual_planner.py`, and type `Element.attribution` with it. Writing a second four-member literal beside the first is how two vocabularies for one thing start | Fowler, 2026-09-10; `CLAUDE.md` section 4 |
| 5 | Sentence indices, never text. Exact search over a long string rejects a real quote over one changed word, silently | Plan 11 row #2 decision 3 |
| 6 | **This row depends on row #8, not on row #7 alone.** Condition 1 is "the kind allows a quote (`report`, `analysis`, `opinion` only)", and `article_kind` is the field row #8 creates. Scheduled beside row #8, condition 1 would gate on a field that does not exist yet, and the row would ship six conditions calling itself seven | Fowler, 2026-09-10 |

---

## 16. Row #9 - Confidence is a masked log-probability at one token

- **Scope:** A confidence figure per label, recorded on every classification row. Grammar-masked, renormalised log-probability at **one discriminating token position**.
- **Files touched:** `backend/idhazh/llm/server.py`, `backend/idhazh/visual_planner.py`, `backend/idhazh/contracts/**`, `schemas/**`, `config/idhazh.json`, `backend/tests/**`, `docs/concepts/classification.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a recorded-response replay carrying token probabilities.
- **Oracle:** **Every label in every vocabulary is token-prefix-free.** A unit test tokenizes every member of every committed vocabulary and fails loudly the day somebody adds `left_leaning` beside `left`, because at that moment the single discriminating position stops existing and every confidence figure silently becomes a different measurement.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **One discriminating token position, never a joint sum across tokens.** Labels of different lengths are not comparable by sum: a longer label accumulates more negative log-probability for being longer, and the figure then ranks by word length | Andre |
| 2 | **Never a model-emitted number.** A model asked to rate its own confidence produces a number shaped like a probability with none of the properties of one | Andre |
| 3 | **Record always, publish above a floor, never hedge.** A reader does not want "probably energy". The figure is an operator instrument | Jony; Reader rule 2 |
| 4 | **This is new request-path code.** `logprobs` and `n_probs` appear **nowhere** in this repository, verified 2026-09-10 across `backend/`, `frontend/` and `config/`. Nothing here is a matter of reading a field that is already arriving | Verified 2026-09-10 |

---

## 17. Row #10 - Political viewpoint, behind a gate written in code

- **Scope:** One viewpoint an item, asked only where the article kind warrants the question.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/prompts/**`, `config/taxonomy.json`, `backend/idhazh/contracts/{taxonomy,classification_row}.py`, `schemas/{taxonomy,classification-row}.schema.json`, `backend/tests/{test_visual_planner,test_contracts}.py`, `docs/concepts/classification.md`
- **Why the tests are named and not globbed:** this row shares parallel group L with row #17, and `backend/tests/**` would cover row #17's `backend/tests/test_workflows.py`.
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a recorded-response replay for both gate states.
- **Oracle:** An item whose kind does not open the gate carries `not_applicable`, and **no model call was dispatched for it** - asserted by counting dispatches over a fixture set. A gate that dispatches and then discards is not a gate, it is a cost.

### The eight values, in four opposed pairs

Every definition begins **"This piece argues that..."**.

| Pair | Values | The question the pair answers |
| --- | --- | --- |
| 1 | `conservatism` / `progressivism` | what to do about the existing arrangement |
| 2 | `socialism` / `libertarianism` | who should hold economic power |
| 3 | `statism` / `constitutionalism` | how much power the state may take |
| 4 | `nationalism` / `internationalism` | whether the answer is inside or outside the border |

Plus two outcomes that are always available: **`none`** - we looked and the piece takes no position, which is a finding - and **`undetermined`** - the gate opened and no sentence carried one. Both render nothing.

**The `-ism` forms, deliberately.** `conservative` and `democratic` read as party names in every country this digest covers, and would misfire daily on a story about a party rather than an argument. **`populism` was considered and cut**: the word is an insult in every relevant country, so a chip carrying it is a verdict, not a description.

**The codable tie-break:** the value is the one **the piece's own justification rests on**, not the one its subject matter suggests. A piece about a tariff is not `nationalism` because tariffs are national; it is `nationalism` if its argument is that the border is where the answer lives. Single-valued. Two values exactly equal is `undetermined`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The gate opens for `opinion`, `analysis`, and a government policy `announcement`. Never a company announcement** - a company arguing for its own product is not making a political argument | Owner, 2026-09-10 |
| 2 | **The gate lives in Python.** A JSON-Schema conditional is skipped silently by llama.cpp, so it would look like a gate and be nothing | Row #7 decision 4 |
| 3 | **Both decline values are always present in the vocabulary**, and keeping both apart is what makes the question "is this gate a rubber stamp?" answerable at all. Fold them into one and the answer is unmeasurable | Andre |
| 4 | **The hazard this row must measure.** Once `opinion` is in the model's context and you ask it for a viewpoint, it is primed to find one. **Watch the decline rate conditional on a gating kind. Near zero means rubber stamp**, and the row's own console number is that rate | Andre, 2026-09-10 |
| 5 | Recorded only in this row. Nothing renders a political label until a person has read the decline rate | Reader; Jony |

---

## 18. Row #11 - Sentiment about one named subject

- **Scope:** Three values and a fourth state, about the **story's main subject** - not the writer's mood.
- **Files touched:** `backend/idhazh/visual_planner.py`, `config/taxonomy.json`, `config/watchlist.json`, `backend/idhazh/contracts/{article,digest_day,digest_view}.py`, `schemas/**`, `frontend/src/**`, `backend/tests/**`, `docs/concepts/classification.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the browser smoke covering all four render states.
- **Oracle:** **Grey and absent are never the same pixel.** Asserted in the browser by reading the two states' computed styles on one fixture day and requiring them to differ. Judged-and-neutral and not-judged look identical to a reader unless somebody checks, and they mean opposite things.

**The four render states:** green `+` for positive, red `-` for negative, a **grey circle** for judged-and-neutral, and **nothing at all** when the item was not judged.

**The named-subject rule, stated so it can be coded.** The flag is about exactly one entity id that is already on the item's `entities` list **and** resolves to a non-retired `config/watchlist.json` entry. The pill renders only then, and the tooltip names the subject. No named subject, no pill.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Sentiment is the direction of the event for the story's main subject.** Not the tone of the prose. "Shares fell" is negative for the company whatever mood the sentence is in | Owner, 2026-09-10 |
| 2 | **The kill criterion is pre-committed here, in two parts.** Human-human agreement below **0.6 on 60 items** from row #P3, or model accuracy below the **majority-class baseline plus 10 points**. `neutral` will be the majority class, and an always-`neutral` model scores 60 to 70 percent and looks competent - which is why the baseline, not zero, is what it must beat | Owner, 2026-09-10; Andre |
| 3 | If either part of the kill criterion fires, **the row is deleted, not tuned** - code, config keys, schema fields, tests and docs, in one commit | Section 0.1 |
| 4 | The item's own subject comes from data already committed. This row adds no entity extraction and no watchlist work | Row scope |
| 5 | **This row depends on row #P3, and that edge is now on the Reckoner.** Decision 2's first kill criterion is human-human agreement over 60 items of the dev split, and row #P3 is the row that produces those labels. Scheduled without the edge, the row could reach its acceptance gate with a kill criterion nobody could evaluate - which is a pre-committed criterion in name only | Fowler, 2026-09-10 |

---

## 19. Row #14 - The classification ledger, and the day file the console reads

- **Scope:** `state/classifications/<YYYY>/<MM>/<DD>.csv`, **one row an item per classification field**. Rolled into a `DayTaxonomy` block on `state/day-metrics/<YYYY>/<MM>/<DD>.json`. The console reads the day file and never the shards.
- **Files touched:** `backend/idhazh/contracts/classification_row.py`, `backend/idhazh/contracts/day_metrics.py`, `backend/idhazh/contracts/run_manifest.py`, `backend/idhazh/contracts/app_config.py`, `schemas/**`, `backend/idhazh/cli.py`, `backend/idhazh/publish_day_metrics.py`, `backend/idhazh/retention.py`, `config/idhazh.json`, `backend/tests/**`, `docs/concepts/growing-reads.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a `growing-reads.md` declaration for every read this row adds.
- **Oracle:** **The console's payload producer opens one day file for each day in its window and opens no shard.** Asserted by counting file opens over a fixture window. This is the assertion that keeps the console's cost proportional to the window a reader chose rather than to how long the pipeline has been running.

### The shape

The day shard is not a new invention: `state/day-metrics/`, `state/published/` and `state/visual-prunes/` are already `<YYYY>/<MM>/<DD>` (verified 2026-09-10). The five month-sharded ledgers - `feed-health`, `item-health`, `score-index`, `scores`, `seen` - are the ones a future plan 24 migrates, and this row does not touch them.

`source` on each row is one of `model`, `keyword`, `feed`, `encoder`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A new classification is a new row, never a new column.** A header is a positional contract that every committed shard has already agreed to; a row is not | Fowler; `CLAUDE.md` section 11 |
| 2 | `csv_columns()` is **not** defined on `Contract`. It is defined independently on 18 classes under `backend/idhazh/contracts/` (verified 2026-09-10). **Copy `ItemHealthRow.csv_columns()`** - that is the pattern, and there is no base-class hook to override | Verified 2026-09-10 |
| 2a | **Do not assume `version` is a column.** It is column 0 of the state ledgers, and it is **not a column at all** of a published mirror: `PublicEvalRow.csv_columns()` returns `tuple(name for name in cls.model_fields if name != "version")`, and `frontend/public/scores/2026-09.csv` opens `date,run_id,...` where `state/scores/2026-09.csv` opens `version,date,...` (verified 2026-09-10). If this ledger ever gets a published mirror, it follows the mirror's rule and not the ledger's | Verified 2026-09-10 |
| 3 | `DayTaxonomy` is declared **`DayTaxonomy \| None = None`** on the day-metrics contract, so the 21 day files already on disk still validate | `CLAUDE.md` section 11 |
| 4 | **`prompt_digest` and `taxonomy_digest` move to the run manifest, keyed by `run_id`.** They are identical on every row of a run and about 128 of roughly 362 bytes a row, so on the row they are pure repetition | Owner, 2026-09-10 |
| 5 | **This row adds a prune, in the same commit that adds the ledger.** The plan otherwise creates a new growing ledger while citing the others having a fold. Note plainly, in the row and in the doc: **`retention.dry_run` is `true` in `config/idhazh.json`**, so every prune in this repository is a no-op today and this one will be too until somebody flips it | Fowler; verified 2026-09-10 |
| 6 | **`backend/idhazh/publish_day_metrics.py` is in the file list.** It exists, it is what writes the day file, and the earlier draft of this plan left it out - so the roll-up had no writer | Verified 2026-09-10 |

### What it costs, as arithmetic anybody can redo

At the measured 360 items a day and seven classification fields an item, the ledger writes about **2,520 rows a day**. At 234 bytes a row - that is 362 minus the 128 bytes decision 4 removes - that is **0.59 MB a day and about 215 MB a year**. With the two digests left on the row it is 332 MB a year, so decision 4 is worth about **100 MB a year, a third of the total**. Against a `state/` that is **20.67 MB in total today**, either figure is the largest thing in the directory by an order of magnitude, which is why decision 5 is in this row and not a later one. All three yearly figures are **estimates**: they assume today's publish rate holds and that seven fields is the final count.

---

## 20. Row #15 - The console tab

- **Scope:** Classification gets **its own console tab**, not a corner of the summaries panel. **Three charts, nine numbers, one generated sentence.**
- **Files touched:** `frontend/src/routes/console/**`, `frontend/src/lib/components/**`, `backend/idhazh/publish_day_metrics.py`, `frontend/public/console/**`, `frontend/tests/**`, `docs/architecture/publishing/console.md`, `docs/architecture/publishing/console-payloads.md`, `docs/architecture/publishing/console-charts.md`, `docs/concepts/console-design.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; the section 12 smoke; **the page renders complete with its data file absent**.
- **Oracle:** With the classification day files deleted, the tab renders, says it has no data, and logs no error. A console panel that white-screens on missing data fails on exactly the day an operator most needs it.

### The three charts

| Chart | Shape | Why this shape |
| --- | --- | --- |
| Desk disagreement | a 5 by 5 grid, **off-diagonal tinted, diagonal outlined with no fill** | Include the diagonal in the colour scale and it is one bright stripe with 20 near-invisible cells, identical every day. That is wallpaper, not an instrument. The interesting cells are the ones off it |
| Abstention and cap saturation | two lines on one plot, shared axis | They move against each other. Two plots side by side hide the relationship that is the whole reason to look |
| Keyword-only against model-only, per lens | a **diverging bar**, zero in the middle | A grouped bar loses the sign, and the sign is the meaning: which way a lens disagrees is the question |

**Every chart carries a heading and one plain-English sentence saying what it means and what good looks like - more is better, or less is better. If a chart needs more explanation than that, the chart has failed** and the row replaces it rather than adding a paragraph.

### The four numbers this plan was missing

Every metric in the earlier draft was about what the **model produced**. None was about what happened afterwards.

1. **What reached a reader** - of everything labelled, what published and what rendered.
2. **What it cost** - the tokens and the wall clock this plan's calls added.
3. **Disagreement per publisher.** This is the only panel here that produces an **action**: one feed miscategorising everything is a config fix, and it is invisible inside a 5 by 5 desk grid.
4. **Before and after a prompt change** - which is only answerable at all because row #1a deleted the window that withheld it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Windowed fetch only. **No mass fetch, no prerender**, lazy fetch for everything except the first panel, and it **reuses the existing shared window control** rather than adding a second one | Carmack; `CLAUDE.md` Rule #12 |
| 2 | **Colour on exactly two metrics: evidence drop and quote acceptance.** They are the only two with a right answer. Colour on a metric with no right answer tells a reader something is wrong when nothing is | Jony |
| 3 | **The test for whether a number earns a pixel**: name the verb somebody does today because of it; does it stay still when the pipeline is unchanged; can a single number say it. **And a surviving panel must name the panel it displaces** | Susan, 2026-09-10 |
| 4 | **The calibration panel ships only if its mechanism line can be filled in on the day the row lands.** Otherwise the tab carries one line reading `Calibration is not measured yet.` and no panel. A panel drawing a calibration curve nobody computed is a lie with axes | Susan |
| 5 | **`docs/architecture/publishing/console.md` exists** - 1,669 lines, last updated 2026-09-10 - and so do `docs/concepts/console-design.md`, `docs/architecture/publishing/console-payloads.md` and `docs/architecture/publishing/console-charts.md`. This row **extends** all four. The earlier draft of this plan said the page did not exist and scheduled writing it from scratch, and named two of the four not at all | Verified 2026-09-10 |

---

## 21. Row #16 - A vertical is proposed into a channel and promoted by a person

- **Scope:** The model may **propose** a new vertical into a channel. **Only a human commit changes the publish vocabulary.**
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/{cli,ledger}.py`, `state/vertical-proposals/<YYYY>/<MM>/<DD>.csv`, `backend/idhazh/contracts/vertical_proposal.py`, `schemas/vertical-proposal.schema.json`, `config/idhazh.json`, `backend/utilities/review_vertical_proposals.py`, `backend/tests/**`, `docs/concepts/taxonomy.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; an injection-canary fixture driven end to end.
- **Oracle:** **A proposed term appears in no rendered page, no URL, no filename and no search-index entry.** Driven from an injection canary that proposes a hostile term, then asserted across the built site. This is the row's whole safety case, so it is the row's oracle.

### The four controls that carry the weight

Of nine controls, four are load-bearing:

1. **The decoding enum comes from the committed taxonomy only.** An injected term can be *proposed*; it can never be *assigned*.
2. **A proposed term renders nowhere.** No page, no URL, no filename, no search index.
3. **The frequency floor counts independent items.** N items, across M distinct registrable domains, across D distinct days, with a per-domain cap. "Seen 12 times" is one hostile site publishing 12 pages; "12 items, 5 domains, 7 days, at most 2 a domain" is not.
4. **The proposal channel never feeds a prompt.** Untrusted text that re-enters the model is `CLAUDE.md` Rule #11 read backwards.

**Promotion is a pull request, never a console button.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Starting values to `config/`: **N=12 items, M=5 domains, D=7 days, cap 2 a domain.** All four are **estimates** and are config precisely because they are | Owner, 2026-09-10; `CLAUDE.md` Rule #6 |
| 2 | **The residual risk is stated rather than argued away.** A patient adversary with five real domains over seven days gets a term in front of a person. **That is the intended end state**: the attack terminates at a pull request instead of at a reader | Owner, 2026-09-10 |
| 3 | The proposal ledger is day-sharded from the first commit, following `state/published/` and `state/visual-prunes/`, and gets a prune in the same commit | Row #14 decision 5 |
| 4 | **`visual_planner.py` does not write the ledger. It puts the proposal on its reply payload, and `cli.py` writes the row through `ledger.py`.** The planner writes no file today - verified 2026-09-10, it names no `STATE_DIR` and opens nothing - and every state ledger in this repository is written by `cli.py`, `ledger.py`, `drift.py`, `retention.py`, `telemetry.py`, the two publishers or `evals/`. Giving the module that talks to the model a file handle puts untrusted text one bug away from disk, and it breaks the payloads-not-calls rule the whole pipeline is built on | `CLAUDE.md` section 1a; verified 2026-09-10 |

---

## 22. Row #17 - The weights loop proposes a pull request and commits nothing

- **Scope:** The adaptive lens-weight loop becomes **its own weekly workflow**. It reads the ledger, proposes weights, and **opens a pull request**.
- **Files touched:** `.github/workflows/lens-weights.yml`, `backend/utilities/propose_lens_weights.py`, `backend/tests/test_workflows.py`, `docs/how-to/tune-the-lens-weights.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; the full suite; `shellcheck`; one manual dispatch.
- **Oracle:** The workflow's token permissions permit opening a pull request and **do not permit pushing to `main`**, asserted by reading the workflow file in a test. A rule that lives only in a code review is a rule until somebody is in a hurry.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **It never commits, and auto-merge is banned on its pull requests.** A loop that tunes a published vocabulary without a person reading the diff is a model selecting what publishes | `CLAUDE.md` section 0a |
| 2 | Its own workflow, not a step in `digest.yml`. A weekly job inside a four-hourly pipeline either runs 42 times too often or blocks the pipeline while it thinks | Carmack |
| 3 | It reads a **bounded window** of the classification ledger - the trailing N days from config - and declares that read in `growing-reads.md` | `CLAUDE.md` Rule #12 |
| 4 | **It adapts on the counterfactual, not the outcome.** A weight that rises because the lens's items published is a loop reading its own past decisions and calling them evidence. What the proposal compares is what the ranker **would have** selected at a candidate weight against what it **did** select at the committed one, over the same window. Adapting on the outcome converges on whatever the loop already preferred, and it converges quietly | Andre; `CLAUDE.md` Rule #10 |
| 5 | **Under-carriage is an eligibility gate, not a term in the score.** A lens carried by too few items in the window has a weight nobody can estimate. Folding "too few items" in as a penalty produces a number that reads as a measurement and is a refusal wearing arithmetic. The lens is **excluded from the proposal and named as excluded in the pull request body**, with its item count | Andre |
| 6 | **A thin window produces a refusal, not a smaller adjustment.** Below `lens_weights.min_items_per_lens` in the window, the workflow proposes nothing for that lens and says so. A proposal computed from four items is not a smaller proposal; it is a different kind of thing | `CLAUDE.md` Rule #10 |
| 7 | **A staleness alarm on the open pull request.** A weekly job that opens a pull request nobody merges opens 52 a year. If this workflow's proposal is still open when the next cycle runs, the run **comments on the existing pull request and opens no second one**, and the console says a proposal is waiting. Without this the loop's failure mode is silent accumulation | Carmack |
| 8 | **Three kill criteria, pre-committed here so none is chosen afterwards to fit the result.** (a) Two consecutive proposals rejected by a person - the loop is proposing against a judgement it cannot see. (b) A proposal moving any weight by more than `lens_weights.max_move_per_cycle` - the window is too short or the signal is noise, and either way the arithmetic is not ready. (c) No proposal accepted in `lens_weights.max_idle_cycles` - the loop is producing review work and no value. **Any one of the three and the workflow is deleted**, code, config keys, tests and doc, in one commit. All three thresholds are **estimates** and live in `config/` for that reason | Section 0.1; `CLAUDE.md` Rules #6 and #10 |

---

## 23. Row #18 - The closing measurement: is a read desk better than a declared one

- **Scope:** The measurement this whole plan is judged by. **200 items from the test split**, model desk against human label, with the **feed's declared vertical as the baseline**.
- **Files touched:** `backend/utilities/measure_classification.py`, `docs/reference/measurements.md`, `docs/concepts/classification.md`, `backend/tests/test_measure_classification.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; the full suite. Not a CI gate - it is a measurement a person runs and records.
- **Oracle:** The measurement is run **against the baseline in the same pass**, so the two numbers come from one set of 200 items and one labelling. A model number quoted against a baseline measured last month is two numbers about two things.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The baseline is the feed's declared vertical**, which is what ships today. Anything that does not beat it is a cost with no benefit | Owner |
| 2 | **The proposed margin is 10 points**, and it is a proposal until this row is run. It is written down before the measurement so it cannot be chosen afterwards to fit the result | `CLAUDE.md` Rule #10 |
| 3 | The result is recorded with the date, the split, the definition-text version and the spread. Not a single percentage | `CLAUDE.md` Rule #10 |
| 4 | It cannot start before row #P3, because it needs human labels on the test split. That dependency is on the Reckoner | Fowler, 2026-09-10 |

---

## 24. Row #19 - The keyword lenses retire, or they do not

- **Scope:** The decision row for `Article.lenses`. Either `model_lenses` is promoted to the published field and `tag.tagged`'s lens half is deleted, or the model lenses are deleted and the keywords stand.
- **Files touched:** `backend/idhazh/tag.py`, `backend/idhazh/contracts/article.py`, `config/taxonomy.json`, `schemas/**`, `frontend/src/**`, `backend/tests/**`, `docs/concepts/taxonomy.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the browser smoke.
- **Oracle:** Whichever way it goes, **one writer remains**. Asserted by grepping for writers of the published field in a test over the source tree, which is a fixed-size read of code a person wrote, not of data a run appended.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A person decides, having read row #15's diverging bar. Not a threshold.** A threshold is a number somebody picked, and this is a question about whether a vocabulary reads well | Owner, 2026-09-10 |
| 2 | Whichever side loses is **deleted, not left behind a flag** - code, keywords in config, tests, docs, one commit | Section 0.1 |
| 3 | The starting position on record: keyword lenses reach **2,291 of 8,478 committed items, 27.0 percent**, up from 7.5 percent when keywords were introduced on 2026-08-26. That is the number the model has to beat, and it is not zero | Measured 2026-09-10 |

---

## 25. The docs each row writes

| Doc | Exists today | Row | What it must say |
| --- | --- | --- | --- |
| `CLAUDE.md` section 0a | yes | P1 | The property, with the summary-faithfulness clause kept explicitly |
| `docs/concepts/taxonomy.md` | **no** | 2, 3, 6, 16, 19 | What a vertical is, what a desk is, what a lens is, what an event is, and how they differ. Its absence is why this design needed three rounds of review |
| `docs/concepts/classification.md` | **no** | 8, 9, 10, 11, 13, 18 | Every label, its definition text, what renders and what does not, and the confidence rule |
| `docs/how-to/measure-a-classifier.md` | **no** | P2, P3, 18 | The dataset, the split rule, the labelling procedure, the baseline |
| `docs/architecture/publishing/console.md` | **yes**, 1,669 lines | 15 | **Extended**, not written. The new tab, panel by panel |
| `docs/architecture/publishing/console-payloads.md` | **yes** | 15 | Extended with the classification day file's published shape |
| `docs/architecture/publishing/console-charts.md` | **yes** | 1a, 15 | **Rewritten** where it says "the boundary is a `pipeline_fingerprint` transition, never a `model_id` one" - row #1a is what makes that line false. Extended by row #15 with the three new charts |
| `docs/concepts/console-design.md` | **yes** | 15 | Extended with the tinting rule and the two coloured metrics |
| `docs/architecture/publishing/layout.md` | yes | 5, 6 | **Rewritten** where it forbids hash-like names and calls the id ten decimal digits |
| `docs/architecture/publishing/visuals.md` | yes | 5 | **Rewritten** where it cites the hash rule by test name |
| `docs/concepts/growing-reads.md` | yes | 14, 16, 17 | A declaration for every new read over a collection a run appends to |
| `docs/reference/measurements.md` | yes | P4, 18 | The `visuals` job's first runtime-counters row - **not the 4B's decode rate, which is already on record at 13.00 +/- 0.03 tok/s** - and the closing measurement with its date and spread |
| The dataset datasheet | **no** | P2 | Who built it, how the split was drawn, what it may not be used for |
| `docs/how-to/tune-the-lens-weights.md` | **no** | 17 | What the weekly workflow proposes and who merges it |

---

## 26. Open gaps nobody owns

Named here so they are not mistaken for work this plan is doing.

| Gap | What it is | Why it is not a row here |
| --- | --- | --- |
| `backend/utilities/prompt_loop.py` | It still targets the **single-call summariser prompt**. Once the call structure is a DAG, it is tuning a prompt that no longer exists in that shape | It is owned by **no row of any plan**. It needs one, and it is not classification work |
| `events` and `entities` | Both are matched, stored, versioned and schema-gated - `release` fires on 1,546 committed items, `regulation` on 1,016 - and **rendered nowhere** | Either a row renders them or somebody says out loud that they are deliberate rent. Neither has happened |
| The five month-sharded ledgers | `feed-health`, `item-health`, `score-index`, `scores`, `seen` | A future plan 24. Section 0 |
| Placement, the ranker, the time rail, the `assemble` consolidation | - | A future plan 25. Section 0 |
| `retention.dry_run` | It is `true`, so **every prune in this repository is a no-op**, including the one row #14 adds | Flipping it is a decision about the whole repository, not about this plan |

---

## See also

- [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md) - the plan this one spawned from; its rows 4, 5 and 6 gate every labelling row here.
- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record O43, E1 and E5 come from.
- [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - what a read over a growing collection must declare.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every acceptance gate above.
