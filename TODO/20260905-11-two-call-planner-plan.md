# 11 - One model, two calls

**Last Updated**: 2026-09-12
**Level**: 5 (the model pick, the trust boundary, and the call structure every later plan rests on)

**Chain**: previous [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md) | next [`20260905-12-readable-visuals-plan.md`](20260905-12-readable-visuals-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O3, O17, O37, O43, rows 4, 5, 9, 10, 11, 17, 50, sections 10.1, 10.1a, 10.1b, 10.2, 10.3, 10.3a, 10.6, 11.3, 11.4, 14.5, E5, 12.6 G1 G2 G4, 12.7 G8.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The visual is drafted today by a small model reading a lossy summary. This is the architectural change the whole group exists for: one capable model reads the **article**, labels what code already found, points at what code missed, and then summarises and plans against the elements rather than against prose. It also retires a whole model, a whole CI job and **2,438,761,672 bytes of cache - 2.27 GiB, which is 22.7 percent of the 10 GiB repository ceiling** (read from the Actions caches API on 2026-09-12; the figure here read 2.33 GiB and named no source) |
| Hard scope - in | The planner module; call 1 and the four model-anchored element producers; call 2 appended to call 1's message array; the reachability gate; the downgrade ladder; retiring the small model with its job in the same commit as the flag flip; one chart drawn end to end |
| Hard scope - out | The renderer swap (plan 12). Any new visual type. Any human review surface. **A third call** - splitting call 2 into two requests needs a measured timeout rate first, and until that measurement exists it is out of scope, not open |
| ESCALATE triggers | 1. `cached_tokens` on call 2 is below call 1's prompt token count - the prompt was built in the wrong order and the whole cost model is wrong. 2. The worst shard passes 180 minutes against the 200-minute timeout. 3. A retry is proposed that perturbs nothing. 4. Any design that lets the model emit a character a reader sees |
| Chosen strategy | Behind a flag, off, until the whole path works - then one commit flips it, deletes the job and retires the role together. The small model may not retire before call 2 works, because call 2 is what replaces it |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Exactly two model calls per item. Always.** Call 1 labels; call 2 writes the summary **and** the plan. Call 2 runs for every item that publishes, because it is the call that writes the summary - a gate may suppress the plan fields inside it and may never skip it. The deterministic pass before call 1 is **the candidate pass**, never "call 0"; a document that spells three things "call" cannot say "two calls" and be counted.

### 0.1 Standing rules, and they bind every row

Added 2026-09-11. The three merged rows did not have these written down; the four that remain do.

**Deliver the intent of this plan, not the letter of a row.** A structural fix matters more than a small diff. Where a row cannot be done correctly inside its stated scope, **expand the scope and say so in the pull request** - do not ship a band-aid to stay inside a file list somebody wrote before the code was read. `CLAUDE.md` Guardrail #5 is the authority; a row's file list reads like a fence and is meant to read like a start.

**No prisoners.** Every removed feature takes its code, its tests, its fixtures, its config keys, its schema fields, its docs and its `state/` writers with it, **in the same commit**. Git is the backup. A row that removes something and leaves a dead test, an orphan config key or a doc paragraph describing the removed thing has not finished, and its acceptance gate says so. **Row #6 is the removal row this plan was written around**, and its decision 2 has said "no half job" since the first draft.

**Verify every fact this plan hands you against the tree before acting on it.** Plans have been wrong. A count, a line number or an "exists today" answer in any row below is a reading of the day it was written, and this tree moves several times an hour. Re-run the grep. **A row that discovers a wrong fact fixes the plan in the same pull request**, in the row that carried it, and says so in the body.

**A widened file list is re-checked before the pull request opens.** `parallel N = 1` here, so no two rows of this plan run at once - but four rows of this plan share files with plans 23, 24 and 25, which do run beside it. [`20260911-execution-order.md`](20260911-execution-order.md) section 3 carries the cross-plan intersection; a row that widens its list re-checks it there.

**Additive contract fields are stamped in the commit that adds them.** Every row that adds a field to a persisted model names its `version` date-stamp and its `changelog` entry in its own acceptance gate, per `CLAUDE.md` section 11. Row #3b already carries this as its decision 2.

### 0.1a The gate sets, written out once so a row can name one

Every row's acceptance gate below names one or more of these sets **and then lists what that row adds**. The commands are the literal ones from [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md), copied here on 2026-09-11 so a worker reading one row in an isolated worktree does not have to open another file to know what to type. Where the two disagree, the gate guide wins and the row that noticed fixes this block.

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

**`mypy --strict` is not the command, and three rows below said it was.** The repository invokes plain `mypy`; strictness is configured, not passed - `pyproject.toml:207` sets `strict = true` and line 69 says in its own comment that "`mypy --strict` needs no override". The behaviour a row wanted is what runs either way, so this is a wording fix rather than a weaker gate. Corrected 2026-09-11 in the four live rows; the three merged rows keep the wording they shipped with.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Call 1 reads the article and points at it | - | A | DONE #561 | yi-t11r1 | #561 | worker |
| 2 | The four kinds only a model can find | 1 | B | DONE #562 | yi-t11r2 | #562 | worker |
| 3 | Call 2 summarises and plans, and the article is read once | 2 | C | DONE #570 | yi-t11r3 | #570 | worker |
| 3b | Every call reports its own cost | 3 | C2 | DONE #636 | p11-3b | #636 | worker |
| 3d | The instrument says where every re-read token went | 3b | C3 | IN-FLIGHT | p11-3d | - | worker |
| 3c | Own the prompt bytes | 3d | C4 | PENDING | - | - | - |
| 3e | The instructions move in front of the article | 3c | C5 | PENDING | - | - | - |
| 4 | The gate that refuses before the plan is drafted, and the ladder that steps down | 3 | D | DONE #612 | p11-r4 | #612 | worker |
| 5 | One chart, drawn end to end | 4 | E | DONE #621 | p11-r5 | #621 | worker |
| 5b | Call 1 and call 2 run in the pipeline | 5, 3b, 3e | E2 | PENDING | - | - | - |
| 6 | The small model, its job and its cache go | 5b | F | BLOCKED | - | - | - |

**Six rows are live and five are merged.** Rows 1, 2, 3, 3b and 4 shipped. **`parallel N = 1`, so no two rows of this plan run at the same time.**

**The chain was re-ordered on 2026-09-12 and it is now one line: 3b -> 3d -> 3c -> 3e -> 5b -> 6.** Row #3b's first per-call reading showed that the two-call design's whole extra cost over a single call is prompt layout - about 896 tokens an item that call 2 reads and nobody asked for. Wiring the calls into the pipeline first would mean reading that decision through an instrument that cannot see three quarters of what it costs. So the layout is fixed before the wiring: row #3d makes the instrument report where every re-read token went, row #3c removes 209 tokens an item by owning the prompt bytes, row #3e removes about 670 more by moving the instructions in front of the article, and only then does row #5b wire it up. **Together those two rows take the overhead from 896 tokens an item to under 100** - about 10 seconds against 91 today, at the measured 9.85 tokens a second. Owner decision, 2026-09-12, on Andre's ruling; the full argument is in each row.

**Row #5b was added on 2026-09-12 by row #6's worker, and row #6 is BLOCKED behind it.** Row #6 was dispatched, and its first act was to check its own precondition - decision 1, "the small model may not retire before call 2 works". **Call 2 does not run.** No module under `backend/idhazh/` imports `classify.calls`; the only importers are three test modules and `backend/utilities/measure_two_calls.py`, and `calls.py`'s own docstring still says "no stage dispatches either yet". The flag this plan's strategy turns on, and row #6's scope opens by flipping, was never built - `config/idhazh.json` carries no such knob. Rows 1 to 5 built the two calls, the gate, the ladder and one renderer; **nobody built the stage that calls them**, and that missing work is row #5b. Retiring the small model before it lands would take the digest from 17 charts a day to none, which is row #6's own rejected alternative 1. Ruled independently by Carmack and Fowler, 2026-09-12; neither would take the widening.

**This plan is four live rows and the second-heaviest constraint in the project.** Row #5 blocks 14 of the 58 live rows across the five open plans, because row #6 is what [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) row #7b waits on, and eleven rows wait on that. Measured 2026-09-11 over the five plans' own Reckoners; the working is in [`20260911-execution-order.md`](20260911-execution-order.md) section 2. **Row #5b sits inside that chain, so every one of those counts is now one wave further away.**

---

## 2. Row #1 - Call 1 reads the article and points at it

- **Scope:** `visual_planner.py` builds call 1: the system rules, the title, the fenced article, and the candidate table indexed by `element_id`. The reply labels, proposes and names - and can emit no number at all.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/prompts/**`, `backend/idhazh/contracts/element.py`, `schemas/*.schema.json`, `backend/idhazh/cli.py`, `backend/tests/test_visual_planner.py`, `tests/fixtures/**`, `docs/architecture/extraction/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a recorded-response replay with no network.
- **Oracle:** **No field of call 1's schema accepts a number, a span or a character offset.** Asserted against the generated schema, so authorship is impossible by grammar rather than caught by a check downstream. Plus: a reply citing an unknown `element_id` drops that label and keeps its siblings.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Extraction first, summary second.** Using a lossy summary as the planner's source is the defect that produced this whole design | Owner, overruling Andre; section 10 |
| 2 | Field order is decode order. Labels are committed **before** the type is chosen, or the reason becomes a rationalisation of a choice already made - measured on this codebase once | Row 12 |
| 3 | `proposed` is the escape hatch for a figure the regex missed: the model names a **sentence**, code searches only that sentence, demands exactly one hit, and re-parses value and unit from the article's own bytes. Stamped `extractor="model_proposed"`, capped per article | Section 10.1a |
| 4 | A spelled-out number and a relative change stay refused - there is nothing for code to parse | Section 10.1a |
| 5 | The accepted extra signals are salience, attribution type, hedge marker, keyphrases and lede/quote indices - about 140 output tokens, 12.5 minutes of shard wall clock at 20 items. Question-answer pairs, coreference, sentiment and embeddings are refused, each for its own reason | Section 10.6 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | The model emits a verbatim surface for every element, adjudicated by exact search | A number the model types is a number the model authored. Exact search cannot tell a real number from a real number pointed at the wrong sentence | Andre, section 10.1a |
| 2 | Only the regex may discover a quantity | Closing authorship is right; closing discovery is not. The regex deletes the series a trend chart exists to show | Andre, section 10.1a |

---

## 3. Row #2 - The four kinds only a model can find

- **Scope:** The producers for `entity`, `place`, `quote` and `claim` - a different anchoring rule per kind.
- **Files touched:** `backend/idhazh/elements.py`, `backend/idhazh/visual_planner.py`, `backend/tests/test_elements.py`, `tests/fixtures/**`, `docs/architecture/extraction/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** For every surviving element of every kind, `article.text[span_start:span_end] == span_excerpt`. **And** no element's drawn label is ever its Tier 2 `name` - asserted by checking that the label equals one of the element's surviving mentions.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | An **entity name is never searched for.** An article writes "Vestas Wind Systems A/S" once and "Vestas" four times, and the canonical name may appear nowhere verbatim. The `name` is Tier 2 and a grouping key; the **mention** is Tier 1 and is what draws | Section 10.1a |
| 2 | Each mention's surface must occur **exactly once inside its own named sentence**. Ambiguity is a rejection rather than a coin toss. Zero surviving mentions drops the element | Section 10.1a |
| 3 | A quote or a claim is **sentence indices only, never text.** Exact search over a long string rejects a real quote over one changed word, silently, which is worse than no check | Section 10.1a |
| 4 | Every actor and object in an event or relation must resolve to a surviving entity element, or the row is dropped. An unanchored arrow is a claim the article did not make | Row 47 |
| 5 | A rejection is **per element, never per article** | Section 10.1b invariant 3 |
| 6 | Two failures no anchoring check can see are recorded rather than papered over: **mis-pointing** (the span is real, just the wrong one) and **mis-labelling** (right number, wrong meaning). This is Deviation A and it is accepted as permanent | O40, section 10.1a |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Exact search for every kind | Confuses a location with a label; it is precisely what a semantic model is good at and string matching is bad at | Andre |
| 2 | Model-supplied coreference chains | Exact and prefix matching over spans code already holds does most of it, and the model's version cannot be span-validated | Section 10.6 |

---

## 4. Row #3 - Call 2 summarises and plans, and the article is read once

- **Scope:** Call 2 appended to call 1's message array, emitting `{summary, visual}` in that order, with the output budget re-derived from the contract's own bounds.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/summarize.py`, `backend/idhazh/llm/server.py`, `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/*.schema.json`, `backend/tests/**`, `docs/architecture/summarize/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch reading `cached_tokens`.
- **Oracle:** Two assertions, because the two halves fail for different reasons. **The floor that must hold:** `cached_tokens` on call 2 is at least call 1's prompt token count - the system turn and the article are byte-identical and come first, so they prefill once or the prompt was built wrong. **The target that must be measured, not assumed:** whether call 1's *generated* tokens also cache, since call 2 re-renders them through the chat template. Record both.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The two calls are **adjacent per item**. `n_parallel` is 1, so there is one cache slot; running all call-1s then all call-2s evicts the prefix every time, with no error | Row 10 |
| 2 | Assert `cached_tokens`, never a `prefill_ms` ratio. A ratio confounds cache reuse with delta length and reads as partial success when the prompt was built in the wrong order | Row 11 |
| 3 | **The planner's source is the article and the element table, not the summary.** The summary is in context because decoding is autoregressive, so it *conditions* the plan; it cannot *source* it, because `element_ids` may cite only an anchored element | Section 10.3a |
| 4 | If `information_delta` collapses after the cutover, this ordering is the first suspect - a plan can drift toward illustrating the sentences | Section 10.3a |
| 5 | On a reply cut by the output budget, code recovers the closed `summary` object from the returned bytes and publishes the item with `decision = none`. Zero extra seconds, no second request. **A contract test asserts `summary` precedes `visual` in the generated schema**, because the recovery boundary is the property order | E5 |
| 6 | The output budget is **derived** from the contract's bounds, not picked, and re-derived whenever a bound changes | Row 13, section 11.3 |
| 7 | `context_exceeded` degrades to a **chunked read**, not to nothing. Element extraction is naturally chunkable because an element is local to its span | Row 20, section 11.4 |
| 8 | A retry must perturb the **input**. Where no input perturbation applies, do not retry - under greedy decoding a retry against identical input is bit-identical and costs a full decode | Row 17 |
| 9 | **The floor held.** Measured, call 2 cached 1,493 tokens against call 1's 1,497-token prompt, so the ESCALATE trigger fired on the letter - four tokens short. Ruled: the floor held. The trigger's own sentence names the failure it guards against, "the prompt was built in the wrong order", and call 1 caching 0 while call 2 cached the whole article and the whole system turn is the proof that did not happen. The four are the chat template's empty think block, which nothing here renders | Owner, 2026-09-10, section 0 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A different system prompt for call 2 | The common prefix would end at the template header and the whole article would re-prefill - roughly double | Section 10.2 |
| 2 | Three calls | Needs a measured timeout rate first. Out of scope until that measurement exists | O43, E5 |
| 3 | Temperature jitter on retry | Breaks the `seed: 0`, `temperature: 0.0` determinism contract - a re-run stops being a re-run | Row 17 |

---

## 4a. Row #3b - Every call reports its own cost

- **Scope:** Two model calls per item currently fold into one set of flat `Summary` fields, so the row keeps one call's `cached_tokens`, `prefill_ms`, `decode_ms`, `input_tokens` and `output_tokens` and does not say which. Record them per call, so the operator console can plot call 1 against call 2. **`summarize_ms` is deliberately not one of the five** and stays a stage clock: it is the wall time around every call the stage made, including the HTTP overhead no call reports (corrected 2026-09-12 in execution, on Carmack's reading).
- **Files touched:** `backend/idhazh/contracts/call_cost.py`, `backend/idhazh/contracts/summary.py`, `backend/idhazh/contracts/item_health.py`, `backend/idhazh/contracts/public_telemetry.py`, `schemas/summary.schema.json`, `schemas/item-health-row.schema.json`, `schemas/public-telemetry.schema.json`, `backend/idhazh/summarize.py`, `backend/idhazh/telemetry.py`, `backend/utilities/migrate_item_health.py`, `state/item-health/*.csv`, `frontend/public/telemetry/*.csv`, `frontend/src/lib/charts/series.ts`, `frontend/src/lib/console/item-cost.ts`, `frontend/scripts/build-canary.mjs`, `tests/fixtures/contracts/{summary,item-health-row,public-telemetry}/*.json`, `backend/tests/test_contracts.py`, `backend/tests/test_summarize.py`, `backend/tests/test_telemetry.py`, `backend/tests/test_publish_telemetry.py`, `frontend/tests/console-item-cost.spec.ts`, `docs/architecture/summarize/throughput.md`, `docs/architecture/sources/item-health.md`, `docs/architecture/publishing/telemetry-series.md`. **Named rather than globbed on 2026-09-11**; the four globs this row carried - `schemas/*.schema.json`, `frontend/src/**`, `backend/tests/**`, `docs/architecture/summarize/**` - covered all 44 schema files, the whole published site and both summarize pages, which is not what the row writes. **`classify/calls.py` and `test_classify.py` were added on 2026-09-12** and then **removed the same day, in execution**: plan 23 row #7a moved both call builders out of `visual_planner.py` in PR #629, but neither builder dispatches anything and neither holds a `Completion`, so there is no cost for this row to record in either file. `visual_planner.py` came off for the same reason - the 4B's cost is dropped a job boundary away from the census (see below). **Six files the row never named were unavoidable**: the new `call_cost.py`, `telemetry.py` (the only map from `Summary` to the census), `migrate_item_health.py` and the two `state/` shards (`require_matching_header` stops the next scheduled run otherwise), `series.ts` (the browser's positional copy of the header) and `build-canary.mjs` (its own hardcoded column list).
- **Acceptance gates:** `GATE-PY` over `test_contracts.py`, `test_summarize.py`, `test_visual_planner.py` and `test_telemetry.py`; `GATE-SCHEMA`; `GATE-WEB`; `GATE-BROWSER`. This row adds: the `version` date-stamp and the `changelog` entry on all three contracts, in this commit.
- **Oracle:** One published item carries two `cached_tokens` figures and they differ - call 1 caches nothing on a cold slot, call 2 caches the whole article. One folded field cannot show that difference, which is the whole reason to split it. **Driven from a built fixture**, which can carry the cold-slot case the committed archive may never have produced (`CLAUDE.md` Guardrail #12). **The row said `backend/var/canary/` and that is the vehicle for half of it, not all** (corrected 2026-09-12 in execution): the canary's cost cells are a hand-written tuple in `build-canary.mjs`, so a canary arm proves the column reaches the page and cannot fail if the pipeline gets the split backwards. The measured 0-against-1,493 case is built in `test_contracts.py` and in `console-item-cost.spec.ts`, and the canary carries one item whose two figures differ so the cells are drawn from a real build.
- **What this row does not do:** it changes no prompt, no call structure and no gate. It splits five recorded numbers into two sets of five and draws neither - the console panel that plots call 1 against call 2 is somebody else's row. **It does not record the small model's visual-planner call**, which is a real dropped measurement and cannot be fixed with a field: the `visuals` job runs after `work` committed the census row, so no per-item cell can reach it, and `state/runtime-counters.csv` has carried that job's cost at the run grain since PR #623. The gap closes on its own when row #5b puts both calls in `stage_work`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The two calls are not one measurement. Call 1 prefills the article and caches nothing; call 2 caches the article and decodes several times more. A single field holding one of them, unlabelled, is a number nobody can read | Owner, 2026-09-10, section 0 |
| 2 | The new fields are additive and defaulted, so a row written before this lands still validates. `version` stamped and `changelog` appended in the same commit | CLAUDE.md section 11 |
| 3 | **A call slot carries the kind of call it was, beside the numbers.** A slot says which call ran first; only the kind says what that call was, and the two stop agreeing the day the call structure moves - which is the day an operator is reading these numbers. It also makes the cells live on the day they land, because today's summarizer call fills slot 1 | Fowler, 2026-09-12 |
| 4 | **The five flat cells become the sum over the recorded calls, and a validator enforces it.** That is what lets `reconcile_prefill`, `publish_day_metrics`, `publish_console_band` and the console's pooled rates stay folded and stay correct with no edit of their own. `reconcile_prefill` compares this ledger against the server's own job totals inside 5 percent, and the server counts every call it answered | Carmack and Fowler, ruled independently, 2026-09-12 |
| 5 | **The projection publishes the first call and the total; the second is the remainder.** Fowler ruled twelve published cells and labelled his own byte figure an estimate, asking for the measurement first. Taken 2026-09-12 on the two committed shards with every timed row populated, twelve cells cost 72.9 and 80.1 percent more gzipped against 35.3 and 40.8 for the seven that ship, so the estimate was refused by the measurement (Guardrail #10). Nothing is lost: the totals are the sum, the arithmetic is integers, and `model_calls` stops a third call being absorbed in silence | Carmack, 2026-09-12, on a measurement taken in execution |
| 6 | **The console's cache figures move to the first call.** `readWhole` counts items whose prompt was read whole - 749 of 5,197 rows carrying a cache figure on 2026-09-12 - and a second call that replays the first call's prompt takes it to zero for ever with no code change. A live counter that silently becomes a constant is the defect this row exists to prevent, so this is inside the row rather than beside it | Carmack, 2026-09-12 |

---

## 4b. Row #3d - The instrument says where every re-read token went

**Added 2026-09-12, and it is the reason rows #3c and #3e come before the wiring.** Row #3b's first reading printed `FLOOR BROKEN - 4 tokens` while 670 tokens an item burned with no reading at all. That is not a floor set four too high. **It is an instrument carrying one yes-or-no answer where it needs three numbers, and the alarm fires on the good case, which teaches its reader to discount it on the bad one.** Ruled by Andre, 2026-09-12.

- **Scope:** `backend/utilities/measure_two_calls.py` stops reporting a pass or a fail and starts reporting a decomposition. Per item, the tokens call 2 had to read again, split by cause: because the article changed, which is irreducible; because the chat template broke the prefix, which is row #3c's target; because the trailing turn sits behind the article, which is row #3e's target. It runs **two items rather than one**, because one item cannot show the steady state and a shard is the steady state. And it refuses to run when the weights file does not hash to `inference.declared_for`.
- **Files touched:** `backend/utilities/measure_two_calls.py`, `backend/tests/test_marks.py` if a new test module arrives, a benchmark record under `docs/reference/benchmarks/`, and `docs/architecture/summarize/throughput.md` to link it.
- **Acceptance gates:** `GATE-PY` over any test module the row adds; `GATE-SCHEMA`, which must produce an empty diff because this row edits no contract. The run itself is the deliverable rather than a gate.
- **Oracle:** **The three causes sum to the re-read total, on both items, and the harness refuses a weights file it was not configured for.** A decomposition whose parts do not add up is a guess with three decimal places. The refusal half is checked by pointing it at the wrong file on purpose.
- **This row takes the reading, and the reading is the baseline. It is not a separate step.** Real article near the truncation cap, from the committed corpus; the configured weights; `--decode-cap` about 16, because every number this row is for is a prefill fact that lands before a token is decoded. One extra uncapped item gives call 1's real reply length, which is what sizes row #3c's saving. **No runner time: every number here is a token count, and a token count names the runtime rather than the processor** (Guardrail #10, as clarified 2026-09-12). The seconds are already measured at 9.85 tokens a second.
- **What this row does not do:** it changes no prompt, no call, no contract and no published surface. It changes what one developer-machine utility prints.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The reading row #3b produced was taken on the wrong model and cannot settle anything on its own.** It used `Qwen3-8B-Q4_K_M`, passed on the command line; `config/idhazh.json` sets `models.summarize` to `Qwen3.5-9B-Q4_K_M`. The four-token gap is a property of **Qwen3's** template under `enable_thinking: false`, and Qwen3.5's may render it differently or not at all. **If the gap is absent on the model that actually runs, row #3c's throughput argument disappears and only its oracle argument survives** | Andre, 2026-09-12 |
| 2 | The harness already reads the inference block and the prompts from config but takes the weights from `--weights`, and prints nothing when the two disagree. That is how the wrong-model reading happened without anybody noticing. Hash the file and compare | Andre, 2026-09-12 |
| 3 | **Two items, not one.** Item 2's call 1 should reuse the system prefix and should destroy the previous item's copy of call 2's question. **Nobody has seen either happen**, and if the system prefix does not reuse, every figure in rows #3c and #3e is wrong and the problem is larger than either row | Andre, 2026-09-12 |
| 4 | The rate to price everything against is a reading: **9.85 tokens a second, median**, slowest timed item 8.25, fastest 44.71, measured 2026-09-09 over 2026-09-01 to 2026-09-09 on GitHub-hosted `ubuntu-latest`, 4 vCPU, no GPU. The earlier arithmetic in this plan used the retired 8B's 10.95 and understated every cost by about 11 percent | `docs/architecture/summarize/throughput.md` |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the floor check and just subtract the template's four tokens | It leaves one boolean where three numbers are needed, and the four would live as a bare number inside a printed sentence (Guardrail #6). The bigger objection is that the boolean was never the problem: it was watching the smaller of two wastes | Andre, 2026-09-12 |
| 2 | Skip this row and read the wiring row's first shard instead | The first real run would then be read through the instrument that already missed three quarters of the cost. That is the specific outcome this ordering exists to avoid | Andre, 2026-09-12 |

---

## 4c. Row #3c - Own the prompt bytes

**Un-deferred 2026-09-12, and its oracle is stronger than the one it carried.** The deferral said this row waits for a daily run after row 6 to price it on the runner. **That reason was half wrong: this row needs no runner.** Every number that argues for it is a token count, and row #3d takes those on a developer machine in an afternoon. Ruled by Andre, 2026-09-12.

- **Scope:** Send a rendered completion instead of a chat completion, so cache reuse is true by construction and the oracle becomes an offline byte assertion rather than a live-server measurement.
- **Files touched:** `backend/idhazh/llm/server.py`, `backend/idhazh/classify/calls.py`, `backend/idhazh/prompts/summarize_and_plan_visual.txt`, `backend/idhazh/prompts/label_article_elements.txt`, `backend/tests/test_classify.py`, `backend/tests/test_summarize.py`, `docs/architecture/summarize/prompt.md`. **Named rather than globbed on 2026-09-11**; `backend/idhazh/prompts/**` is five files today and this row writes two of them. **`visual_planner.py` stood here until 2026-09-12**, when plan 23 row #7a moved both call builders to `classify/calls.py` in PR #629.
- **Acceptance gates:** `GATE-PY` over `test_classify.py` and `test_summarize.py`; `GATE-SCHEMA`, which must produce an empty diff because this row edits no contract.
- **Oracle:** **Call 2's rendered prompt starts with call 1's rendered prompt PLUS call 1's returned completion, byte for byte.** That is a string comparison over two files and needs no server, where today's oracle needs a running model and a warm cache slot. **The fixture is the two rendered prompts, written to `tests/fixtures/prompts/` by the row and compared offline.**
- **The oracle was strengthened on 2026-09-12 and the stronger form costs no more work.** It used to assert only that call 2's prompt starts with call 1's prompt. Once this row renders the bytes itself, call 2's prompt can be built as literally call 1's bytes, plus call 1's returned text, plus the suffix - so **the 209 re-prefilled tokens go to zero rather than to "four minus whatever the template did", and it stops being a per-template question for ever.** Andre, 2026-09-12.
- **What it saves, priced at the measured rate:** 209 tokens an item is **21 seconds an item, about 7 minutes of a 20-item shard**, at 9.85 tokens a second. The 209 is 4 tokens of empty think block plus roughly 205 tokens of call 1's reply sitting behind the break - **a four-token divergence does not cost four tokens, it costs everything behind it.**
- **What this row does not do:** it changes no reply shape, no contract and no schema, and it does not remove the chat-completion path for any other caller. It changes how one call site renders its prompt.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The four-token gap is `<think>\n\n</think>\n\n` from Qwen3's chat template. It writes an empty think block into the generation prompt under `enable_thinking: false` and drops it when the same turn is replayed as history, so the two renderings diverge there. Nothing in this repository renders it | Owner, 2026-09-10 |
| 2 | Confirmed against the measurement 2026-09-12, three ways rather than one: the break sits at 1,493 of call 1's 1,497 tokens, which is where the generation prompt lives; the four tokens are `<think>`, `\n\n`, `</think>`, `\n\n`, each one token in Qwen3's vocabulary; and call 2's 896 uncached tokens only reconcile if the break is there | Andre, 2026-09-12 |
| 3 | **This row goes before the instruction move, although it saves a third as much**, because it changes no prompt text. Land it and the instrument is clean; the instruction move is then measured against a floor that is not already off by 209 tokens | Andre, 2026-09-12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Write the empty think block into call 1's history ourselves, so the two renderings agree | A band-aid on one template's private behaviour. It patches a symptom of a template we do not control, and the next model ships a different template | Owner, 2026-09-10; CLAUDE.md Guardrail #5 |
| 2 | Turn on llama.cpp's `n_cache_reuse` instead, which rescues cached runs after a divergence | **It attacks the same 209 tokens this row does and loses on every axis.** The reuse is not exact: rotating a stored key to a new position is exact, but the hidden state behind it was computed with the dropped tokens still in front, so output can move with nothing in any log to say so - which breaks the determinism contract row #3 rejected temperature jitter to protect. It forces a fingerprint decision, because a knob that can move an output has to be digested, and digesting it moves every earlier work identity. And its threshold is a length gate on a length that varies: the value people copy from the documentation is 256, call 1's reply is about 205, so at the default it rescues nothing and reports no error. **This row gives the same saving exactly, with no flag and no unpinned build** | Andre, 2026-09-12 |

---

## 4d. Row #3e - The instructions move in front of the article

**Added 2026-09-12. This is the largest single waste in the two-call design and no plan named it until today.** Call 2's question is about 670 tokens and sits in a user turn **after** the article. It is byte-identical on every item - it names no article and quotes no sentence, by design - but the text in front of it differs per item, so a prefix cache cannot reach it and **all 670 tokens are read again on every single item, for ever.** A single-call design puts its instructions in the system turn, in front of the article, where they are read once per shard. This design converted that into a per-item cost. Found by Andre, 2026-09-12.

- **Scope:** Move the byte-identical bulk of call 2's question into the shared system turn, in front of the article, and reduce the trailing user turn to a short pointer.
- **What it saves, priced at the measured rate:** 670 tokens an item is **68 seconds an item, about 23 minutes of a 20-item shard**, at 9.85 tokens a second - **three times what the template gap costs.**
- **Files touched:** `backend/idhazh/classify/calls.py`, `backend/idhazh/prompts/summarize_and_plan_visual.txt`, `backend/idhazh/prompts/plan_visual.txt`, `backend/idhazh/prompts/label_article_elements.txt`, `backend/tests/test_classify.py`, `backend/tests/test_summarize.py`, `docs/architecture/summarize/prompt.md`, and a benchmark record under `docs/reference/benchmarks/`.
- **Acceptance gates:** `GATE-PY` over `test_classify.py` and `test_summarize.py`; `GATE-SCHEMA`, which must produce an empty diff because this row edits no contract.
- **Oracle:** **Two numbers, and the second is what makes this row safe.** First, row #3d's harness reports the "trailing turn behind the article" cause at under 100 tokens an item, down from about 670. Second, over a fixed set of real articles run through both layouts, **the per-kind element counts and the anchoring survival rate hold** - how many elements call 1 proposes, of each kind, and how many of them clear span validation. Those are deterministic counts over a model's output, not a model grading a model.
- **The risk is real and it is the only one of these rows that can change what the model says.** Call 1 would carry summariser instructions it does not need. Paid once per shard, that is cheap; the objection is not cost but **context dilution on the call least able to absorb it**, because call 1's entire output is addresses into the article. The oracle's second number is what settles it. Andre, 2026-09-12.
- **What this row does not do:** it moves text between turns and adds no instruction, removes none, and changes no contract, no reply shape and no published surface.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Not all 670 tokens move.** Part of call 2's turn is already per-item: `call_two_user_turn` substitutes `target_words_min/max` and `key_points_min/max` from `article.band_source_words`. Move the byte-identical bulk in front of the article and leave the band numbers in the trailing turn, where they belong | Andre, 2026-09-12 |
| 2 | The dilution risk is checked offline and deterministically. Anchoring is already validated by span equality under row #2's oracle, so an invalid element stays impossible by construction; what can move is **which** elements call 1 proposes. If the counts and the survival rate hold, this row is free. If they move, the question is bounded and `information_delta` is the downstream signal row #3 decision 4 already names as the first suspect | Andre, 2026-09-12 |
| 3 | This row goes after row #3c, not before. Row #3c changes no prompt text, so it lands the instrument clean; this row changes prompt text and needs a floor that is not already off by 209 tokens | Andre, 2026-09-12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Replace the two-call design rather than tune its layout | **The shape is right; the layout was wrong.** A single call reads the article once and writes about 532 tokens. Two calls cost the same, plus call 2's unread prompt - 896 tokens an item on the first reading, of which rows #3c and #3e remove 879. What is left is chat-template headers, a short pointer and the band numbers: **under 100 tokens an item, about 10 seconds, against 91 seconds today.** A design whose overhead is one percent of a single call's prompt is not one to replace | Andre, 2026-09-12 |
| 2 | Move the instructions and skip the element-count check | It is the only check standing between this row and a quiet regression in what call 1 points at, and it costs one scripted run over a fixed article set | Andre, 2026-09-12 |

---

## 5. Row #4 - The gate that refuses before the plan is drafted, and the ladder that steps down

- **Scope:** The reachability gate, `none_reason` as a typed enum, and the downgrade ladder with its four invariance rules.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/contracts/visual_decision.py`, `backend/idhazh/contracts/app_config.py`, `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/prompts/summarize_and_plan_visual.txt`, `backend/idhazh/prompts/plan_visual.txt`, `schemas/visual-decision.schema.json`, `schemas/app-config.schema.json`, `config/idhazh.json`, `backend/tests/test_visual_planner.py`, `backend/tests/test_visual_validator.py`, `tests/fixtures/contracts/**`, `docs/architecture/publishing/visuals.md`. **Named rather than globbed on 2026-09-11**; `docs/architecture/publishing/**` is eight pages today and this row writes one of them. **Corrected on 2026-09-11 by the row itself**: it was `backend/idhazh/contracts/visual.py` and `schemas/visual-plan.schema.json`, and neither moves. `none_reason` belongs on `VisualDecision`, because two of its four routes fire when no plan object exists at all - the gate takes the plan fields off the request and the budget cut loses the plan's bytes - so a field on `VisualPlan` would be unwritable on exactly the cases it is for (Fowler, 2026-09-11). The row widened by three files instead: `visual_vocabulary.py` holds the downgrade-edge allow-list beside the role table it is a sibling of, and the call-2 prompt splits in two so the plan half can be substituted out with the plan half of the grammar.
- **Acceptance gates:** `GATE-PY` over `test_visual_planner.py`, `test_visual_validator.py` and `test_contracts.py`; `GATE-SCHEMA`. This row adds: the `version` date-stamp and the `changelog` entry on `visual_decision.py`, and the new `none_reason` members listed in the schema diff.
- **Oracle:** Every route to `none` carries a distinct `none_reason`, asserted by driving each gate independently and collecting the set - it must equal the enum exactly. A gate whose refusal is indistinguishable from another's leaves the largest number on the console explaining nothing. **Each gate is driven from its own fixture under `tests/fixtures/visual-validator/plans/`**, which holds **eleven plan fixtures today, of which nine drive a refusal and `passes` drives two of them against two different tables** - the validator has nine checks, not eleven, and `declines` and `units-convert` refuse nothing. (Re-measured 2026-09-11; the row said "eleven, one per refusal".) This row adds no plan fixture: its four routes are driven from the committed plans, a table built by narrowing the committed one, and the committed cut reply, so the set is built from cases rather than read off a run.
- **What this row does not do:** it renders nothing and it retires nothing. The ladder steps a plan down to a depth that still validates; drawing the result is row #5 and removing the small model is row #6.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The gate suppresses the plan fields inside call 2; it never skips the call**, because call 2 writes the summary. What is saved is the plan's decode, not the call | O43, section 14.5 |
| 2 | The old "21 measured seconds" saving was for skipping a whole call, which cannot happen. **The figure is withdrawn** rather than re-used; the plan-decode saving is a different number and this row measures it. **Measured 2026-09-11**: tokenising the committed call-2 reply with `Qwen3-8B-Q4_K_M.gguf` through `llama-tokenize` gives 327 tokens whole, 152 for the summary alone and 176 for the plan half - 54 percent of an ordinary reply's decode, which is 29.3 s an item at the summarizer's measured 6.01 tok/s. One reply and not a distribution, because no stage dispatches call 2 yet | Section 14.5 |
| 3 | Four invariance rules on the ladder: element set unchanged, purpose survives, escalating floor, and **re-validation** - a downgraded plan re-enters the **same** validator and the **same** compiler, and a depth that fails falls to the next depth rather than publishing | Row 50, 12.7 G8 |
| 4 | Depths 2 and 3 need their percentiles named; the source document ships a ladder with one named rung | 12.6 G2 |
| 5 | A **static allow-list of legal downgrade edges**, or the ladder can walk a comparison into a timeline and record it as legal. The cross-family ban is what "purpose survives" implies and never states | 12.6 G4 |
| 6 | Floors are computed from depth-0 published visuals only | Row 50 |
| 7 | The ladder's kill criterion is pre-committed here: if downgraded visuals are kept materially less often than depth-0 ones, **the flag goes off and the ladder is deleted, not tuned** | 12.13 G30 |
| 8 | **The floor is a mark count, and never `confidence`.** The six quality components the source document's floors read do not exist, and the only per-plan number that does is one the contract says gates nothing, the model writes, and section 0a bars from selecting what publishes. The mark count is code's own count over code's own elements and is what `enough_data` already rules on. **A floor that cannot be computed is not cleared**, so with no depth-0 corpus every depth refuses and the ladder ships inert | Andre and Fowler, ruled independently, 2026-09-11 |
| 9 | **An annotation is required at every downgrade depth, not only at depth 2.** The source document states it both ways; the depth-1 version is the one with its reason attached, and row 30 already asks for an annotated mark on every visual | Andre and Fowler, 2026-09-11; 4.2.4, row 30 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A repair retry instead of a ladder | Chosen against already, and it is why no validator failure re-calls the model | P.L7 |
| 2 | Let a downgrade skip re-validation | Then a downgrade can publish the thing the original plan was refused for | 12.7 G8 |

---

## 6. Row #5 - One chart, drawn end to end

- **Scope:** One `bar` rendered from a compiled plan through an inline SVG path, so this plan ends with something visible rather than a contract nobody can see.
- **Files touched:** `backend/idhazh/render/chart.py`, `backend/idhazh/render/write.py`, `backend/idhazh/render/__init__.py`, `backend/utilities/build_canary_day.py`, `backend/tests/test_render.py`, `frontend/tests/item-visual.spec.ts`, `frontend/tests/canaries.spec.ts`, `docs/architecture/publishing/visuals.md`. **Corrected on 2026-09-12, in execution.** The list named `frontend/src/lib/components/ItemVisual.svelte` and `frontend/tests/charts.spec.ts` and neither needed a line: the compiled spec renders to the same SVG class vocabulary the hand-written one does, so the inline carrier plan 01 built already repaints it, and `charts.spec.ts` holds the console's prerendered flow rather than an item's drawing. Two files it did not name were needed instead - `build_canary_day.py`, because the oracle is driven from the canary day and the canary's first chart had to become a compiled one, and `canaries.spec.ts`, which asserts a figure out of that chart's alt text.
- **Acceptance gates:** `GATE-PY` over `test_render.py`; `GATE-WEB`; `GATE-BROWSER`; and the whole-day check from plan 01. **`CLAUDE.md` section 12 applies in full** - this row changes the published site, so it is smoke-tested in a real browser and the page is confirmed to render with its data file absent.
- **Oracle:** A published item's drawn bar heights are re-derived in the test from the committed element table and compared to the drawn attributes - so the chart is proved to be showing the article's numbers rather than merely showing numbers. **Driven from the canary day built by `backend/utilities/build_canary_day.py`**, never from the committed archive, per `CLAUDE.md` Guardrail #12.
- **What this row does not do:** it draws one `bar` and no second type, it adds no new visual vocabulary, and it changes no planner decision. The renderer swap and the rest of the chart types are plan 12.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This row exists because a plan contract with no rendered output delivers nothing a person can check. One type, end to end, is the smallest honest proof | Fowler, 2026-09-05 |
| 2 | It reuses plan 01's inline carrier rather than inventing a second one | Plan 01 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Wait for plan 12 to draw anything | Then plan 11 merges with no evidence the plan it emits can become a picture | Fowler |

---

## 6a. Row #5b - Call 1 and call 2 run in the pipeline

**Added 2026-09-12 by the worker dispatched on row #6, which could not start without it. It needs the owner's authorisation before anybody executes it** - this plan is Level 5 and rows 1 to 5 ran under an authorisation for rows that existed. Nothing below has been built.

- **Why it exists:** rows 1 to 5 built the two calls, the gate, the ladder and one renderer. **None of them is reachable from a stage.** `git grep 'build_call_two_request' -- backend/idhazh config .github` returns nothing, `downgrade` in `visual_planner.py` has no caller outside the tests, and `calls.py`'s own docstring still says "no stage dispatches either yet". The single-call 4B path in `stage_visual_planner` is still the only thing that draws a picture. This plan's strategy - "behind a flag, off, until the whole path works, then one commit flips it" - names a commit that nobody wrote, and this is it.
- **Scope:** `stage_work` dispatches call 1 and then call 2 adjacently per item against `models.summarize`, parses both replies into the `Summary` and the `VisualDecision` the pipeline already publishes, runs the reachability gate and the downgrade ladder between them, renders through row #5's path, and retires `_summarize_one` - **behind one config flag, default off, whose removal condition is row #6 and which is written on the line that declares it** (`CLAUDE.md` guardrail #6). The 4B, its job, its cache role and `run.visual_planner_budget_minutes` all stay, because the flag being off has to leave today's pipeline byte-for-byte unchanged.
- **Files touched:** `backend/idhazh/cli.py`, `backend/idhazh/classify/calls.py` (the docstring sentence that says no stage dispatches - true today, false the moment this lands), `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `config/idhazh.json`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `backend/tests/test_pipeline.py`, `backend/tests/test_classify.py`, `backend/tests/test_contracts.py`, `docs/architecture/summarize/throughput.md`, `docs/architecture/publishing/visuals.md`. `.github/workflows/digest.yml` only if the `work` job's timeout has to move, which is a measurement rather than a guess.
- **Acceptance gates:** `GATE-PY` over `test_pipeline.py`, `test_classify.py` and `test_contracts.py`; `GATE-SCHEMA`; `GATE-SUITE`; `GATE-SHELL` if the workflow moves. This row adds: the flag's `version` date-stamp and `changelog` entry on `app_config.py`, and a test that the flag off produces the same `Summary` bytes the single call produces today.
- **Oracle:** three numbers, and the first is an ESCALATE trigger rather than a target. **(1) Call 2's `cached_tokens` is at least call 1's prompt token count** - below it, the prefix cache is not answering for the article and the whole cost model is wrong (section 0, trigger 1). **(2) The worst `work` shard stays under 180 minutes** in `state/runtime-counters.csv`, read over the days the flag is on. **(3) One published item carries a `VisualDecision` the 4B never saw**, drawn from call 2's plan half. **The instrument for (1) is row #3b**, which is why this row depends on it: `prompt_tokens_cached_total` in the ledger today is a job total, not a per-call figure, so nothing in the repository can read that trigger.
- **The flag is off when this lands, so the reading needs the flag on.** How that happens is this row's first decision to take with the owner and not a detail: a `workflow_dispatch` of `digest.yml` with the flag on, or a one-line commit that turns it on and a scheduled day after it. **Row #6 is what deletes the flag, the old path and the model** - so this row is the first of two commits and never the only one.
- **What this row does not do:** it retires nothing. The 4B keeps running, the `visuals` job keeps running, and with the flag off a run behaves exactly as it does today. It adds no visual type, no prompt text and no contract field beyond the flag.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A flag, default off, and not a straight swap.** The new path changes what every item does. Landing it on by default puts a new call structure, the deletion of the only working chart producer and the deletion of the model in one unrevertable diff - and if the wiring is wrong there is no rollback that keeps charts | Carmack and Fowler, 2026-09-12 |
| 2 | **Row #3b is a hard dependency, not an optional extra.** Trigger 1 is the cheapest way this design fails, and today nothing can read it | Carmack, 2026-09-12 |
| 3 | Two commits, not one. Wiring is a behaviour change and retiring is a structural one; one commit cannot honestly be both | Fowler, 2026-09-12, citing Beck's two-hat rule |

### What the runtime price looks like before anybody runs it

Measured from `state/runtime-counters.csv`, 127 `work` rows stamped 2026-09-06 or later, on GitHub-hosted `ubuntu-latest` (4 vCPU, 16 GB), llama.cpp `b10598`, `Qwen3.5-9B-Q4_K_M`: a shard takes 47.7 minutes at the median, 59.9 at p90 and 72.9 at its worst, standard deviation 9.8, and decodes at 5.47 tok/s at the median. **The plan's 6.01 tok/s is above that, so every figure derived from it is about 10 percent optimistic.**

Adding call 1's 140-token label budget and call 2's 176-token plan half, plus the new turn's prefill, comes to roughly 78 to 88 seconds an item at the median rate - **about 26 to 29 minutes more on a 20-item shard**, landing near 74 minutes at the median and 113 at the worst. That is 67 minutes of room under the 180-minute bar. **Retiring the `visuals` job hands back its 50-minute timeout**, so the serial window between four-hourly runs gets wider rather than narrower.

**Two things nobody can compute without a run, and both can fail the row on their own.** Call 2's output budget is 4,694 tokens and the one measured reply was 327; a reply at half the budget is 429 seconds an item, which is 143 minutes of call 2 alone on a 20-item shard and past the bar before call 1 is counted. One reply is not a distribution. And if the prefix cache does not answer for the article, call 2 re-prefills up to the 10,000-token cap at the measured 9.84 tok/s - 17 minutes an item, which is past the job timeout and past the platform's 6-hour ceiling. Everything above assumes the cache holds, and trigger 1 is the check.

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Fold this into row #6 and ship wiring and retirement in one commit | A Level-5 behaviour change welded to a removal, with no rollback that keeps charts, and its first ESCALATE trigger has no instrument yet | Carmack and Fowler, ruled independently, 2026-09-12 |
| 2 | Let row #6 delete the 4B now and wire call 2 in a later plan | 17 charts a day to none for an unknown number of plans. This is row #6's own rejected alternative 1 | Carmack, 2026-09-05 and again 2026-09-12 |
| 3 | Ship the new path on by default and skip the flag | Guardrail #6 requires a feature under development behind a flag, and this plan's own strategy chose one | CLAUDE.md guardrail #6 |

---

## 7. Row #6 - The small model, its job and its cache go

**BLOCKED behind row #5b since 2026-09-12, and its `Depends-on` moved from 5 to 5b.** This row was dispatched and stopped on its own decision 1. **Call 2 does not run in the pipeline**, so it has replaced nothing and there is nothing to retire onto. Nothing under `backend/idhazh/` imports `classify.calls`; `stage_visual_planner` and the 4B are still the only producer of a `VisualDecision`, and they published 18 charts on 2026-09-10 and 17 on 2026-09-11. **The flag this row's scope opens by flipping does not exist** - `config/idhazh.json` carries no such knob and rows 1 to 5 never built one. Deleting the job today is this row's own rejected alternative 1. Ruled by Carmack and Fowler independently, 2026-09-12; both refused the widening as well as the deletion. Everything below is what this row still does, once row #5b lands.

- **Scope:** The flag goes off and then goes away, the small model's role leaves config, the CI job is deleted, the prompt file goes, and `finetune.student`/`teacher` are re-pointed - **all in one commit**. **The flag the scope named is row #5b's to create**; this row is the second of the two commits, which is what "one commit flips it" always meant.
- **Files touched:** `config/idhazh.json`, `.github/workflows/digest.yml`, `backend/idhazh/prompts/visual_planner.txt`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `backend/tests/test_workflows.py`, `backend/tests/test_contracts.py`, `backend/tests/test_visual_planner.py`, `docs/architecture/summarize/prompt.md`, `docs/architecture/summarize/throughput.md`, `docs/how-to/fine-tune-a-model.md`. **Named rather than globbed on 2026-09-11**; `docs/**` was the whole documentation tree and `backend/idhazh/prompts/**` is five files, of which this row deletes one. **The fixture was named `tuned.json` until 2026-09-12; no such file has ever existed and the directory holds one fixture, named above.** `backend/idhazh/visual_planner.py` is not in this list and has to be, because `PROMPT_PATH` at line 79 is what reads the prompt file this row deletes.
- **Acceptance gates:** `GATE-SUITE`; `GATE-SHELL`; `GATE-SCHEMA`; one dispatch of `digest.yml` end to end; `python -m idhazh site-weight`. **`GATE-SUITE` rather than `GATE-PY` here**, because this row deletes a workflow job and a config role and the blast radius is not a list of modules.
- **Oracle:** The dispatched run completes with **no** job between `work` and `assemble`, and the worst shard stays under 180 minutes. **Two numbers, not three** - the cache reading was the third until the owner retired it on 2026-09-12, for the reason the bullet below gives. **The first is read from the dispatched run and the second from `state/runtime-counters.csv` over the seven days after it**, not from the table in any plan. **The job is named `visuals`** - it declares `needs: [plan, work]` and `timeout-minutes: 50`, and it sits between `work` and `assemble` in `digest.yml` today (checked 2026-09-12 at `c16801f0`).
- **The cache is not an acceptance number and no row here reads one. Owner ruling, 2026-09-12, section 0.** GitHub Actions evicts the least-recently-used entry on its own when a repository passes the 10 GB ceiling, so the ceiling is a thing the platform manages rather than a thing this project defends. A cache figure quoted as a gate makes a passing run look like an achievement and a full cache look like a fault, and it is neither. **The reason to retire the small model is one model to qualify, pin, download and measure instead of two.** That reason does not need a byte count to hold. What was measured on 2026-09-12 is kept here as a fact and not as a bar: 7 entries held 9,130,060,863 bytes, and the small model's entry was 2,438,761,672 of them. The row's own estimates, "roughly 82 percent falling to roughly 57", were both wrong when checked - which is the second reason the number is gone rather than corrected. The duplicate `playwright-Linux-1.62.1` entry found the same day needs no row for the same reason: eviction reaches it before anybody does.
- **The cache reading, measured 2026-09-12** from `gh api repos/miztiik/yen-idhazh/actions/caches`, is recorded in the bullet above and gates nothing.
- **This row cannot close in one sitting, and that is scheduling rather than a defect.** The second number needs seven days of runs that have not happened yet, so a worker that waits for it never reports. **Land the row when the first number is in, and record the seven-day reading as owed** - the same shape plan 23 row #P4 used on 2026-09-12 for its own confirming dispatch. What is owed is one sentence: the worst shard in `state/runtime-counters.csv` over the seven days after the merge, against the 180-minute bar, with the merge date named. **A row left open waiting for a clock blocks the critical path** - eleven rows wait on plan 23 row #7b, which waits on this one. Ruled 2026-09-12.
- **Do not force the reading with a manual `gh workflow run digest.yml`.** That run takes hours and commits to `main`, so it races anything else merging. The schedule produces the same rows on its own.
- **What this row does not do:** it changes no prompt text that survives, adds no field and draws nothing. It removes a model, a job, a cache role, a prompt file and four config keys, and it re-points two more.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The small model may not retire before call 2 works**, because call 2 is what replaces it. This is the last row for that reason | Carmack, 2026-09-05 |
| 2 | Retired completely: config entry, cache role, workflow job, env vars, prompt file, tests. **No half job** | O17 |
| 3 | `finetune.student` is `visual_planner` and `finetune.teacher` is `summarize` today - a distillation setup for the model being retired. That configuration is dead the moment this row lands and must be re-pointed in the same commit. **The student was written here as `route` until 2026-09-12; the config has never carried that id** | Section 10.4 |
| 4 | **`run.visual_planner_budget_minutes`**, which is 40 today, is re-derived or deleted here. It exists because the job ran against its own bound, and folding into `work` invalidates the number. **This decision named `run.route_budget_minutes` until 2026-09-12; no such key exists** | Row 69 |
| 5 | **A removed key is refused by name, never dropped in silence.** Every model here sets `extra="forbid"`, so an old config carrying `models.visual_planner` already fails - with a message that does not say where the operator's value went. `refuse_a_removed_knob` (`app_config.py:340`) is this repository's answer and `SUPERSEDED_MODELS_NAMES` (`:376`) is already wired into `ModelsConfig` (`:833`); `RunConfig` needs the same pairing added ahead of its rename call at `:321`. Dropping the key quietly is how somebody comes to believe a number nothing reads | Fowler, 2026-09-12 |
| 6 | **Both rename maps rename INTO keys this row deletes, so both retire in the same commit.** `RENAMED_RUN_KEYS` maps `route_budget_minutes` to `visual_planner_budget_minutes` (`:362`) and `RENAMED_MODELS_KEYS` maps `route` to `visual_planner` (`:369`). Left standing, a config spelling `route` is migrated onto a key that no longer exists and then refused for a name the operator never typed | Fowler, 2026-09-12 |
| 7 | **The role is spelled as a value as well as a key, and that is a second migration.** `finetune.student: "visual_planner"` still satisfies the `ModelRole` string pattern and fails later in `_finetune_names_models_that_exist` (`:5699`), with a message that says what is legal without saying the role was retired. `FinetuneConfig._a_role_naming_a_renamed_key_still_opens` (`:2061`) is where the value-side migration already lives. **Re-pointing the student silently to `summarize` is refused** - teacher and student would then be one model, which is a distillation run training a model on itself | Fowler, 2026-09-12 |
| 8 | **The `version` stamp may not be a bare `2026-09-12`.** The newest changelog entry already carries it (`:3391`) and `contracts/base.py` enforces newest-first and distinct at class definition, so a second bare date raises `TypeError` at import. Use the minute form. **One changelog entry for all four keys**, because this row is one commit | CLAUDE.md section 11 |
| 9 | **Removing the model block leaves two `finetune` knobs unable to differ from the committed config.** `ModelsConfig` would carry one field, so `finetune.teacher` and `finetune.student` each have exactly one legal value. `every-knob-differs-from-the-committed-config.json` is named for an invariant those two can no longer meet - it holds `student: "visual_planner"` at line 160 and `teacher: "summarize"` at 161, and the teacher is already equal today. Edit the fixture by hand and record the exemption beside it; **do not re-serialise it from the model**, which brings a knob back at its default - the one value the fixture exists not to hold | Fowler, 2026-09-12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Retire the model in an earlier plan | Nothing would draft a visual until this plan lands - a reader-visible regression for several plans | Carmack |
| 2 | Keep the small model as a fallback | A second model to keep qualified, cached and measured, for a path the design says is replaced | Carmack |

---

## See also

- [`20260911-handover.md`](20260911-handover.md) - how to pick this queue up with no context: the queue reader, the reading order, and the standing traps.
- [`20260911-execution-order.md`](20260911-execution-order.md) - the schedule across the five open plans. **Rows #4 and #5 here are the fifth and sixth heaviest constraints in the project**, and section 3 there carries the cross-plan file collisions this plan's `parallel N = 1` cannot see.
- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md) - the previous plan.
- [`20260905-12-readable-visuals-plan.md`](20260905-12-readable-visuals-plan.md) - the next plan.
- [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) - spawned from this plan; it spends these calls on labels, and it amends O43 from two calls to as many as the DAG needs, adjacent per item. Its labelling rows are gated on rows 4, 5 and 6 above.
