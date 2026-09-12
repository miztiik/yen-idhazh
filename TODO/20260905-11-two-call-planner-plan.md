# 11 - One model, two calls

**Last Updated**: 2026-09-11
**Level**: 5 (the model pick, the trust boundary, and the call structure every later plan rests on)

**Chain**: previous [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md) | next [`20260905-12-readable-visuals-plan.md`](20260905-12-readable-visuals-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O3, O17, O37, O43, rows 4, 5, 9, 10, 11, 17, 50, sections 10.1, 10.1a, 10.1b, 10.2, 10.3, 10.3a, 10.6, 11.3, 11.4, 14.5, E5, 12.6 G1 G2 G4, 12.7 G8.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The visual is drafted today by a small model reading a lossy summary. This is the architectural change the whole group exists for: one capable model reads the **article**, labels what code already found, points at what code missed, and then summarises and plans against the elements rather than against prose. It also retires a whole model, a whole CI job and 2.33 GiB of cache |
| Hard scope - in | The planner module; call 1 and the four model-anchored element producers; call 2 appended to call 1's message array; the reachability gate; the downgrade ladder; retiring the small model with its job in the same commit as the flag flip; one chart drawn end to end |
| Hard scope - out | The renderer swap (plan 12). Any new visual type. Any human review surface. **A third call** - splitting call 2 into two requests needs a measured timeout rate first, and until that measurement exists it is out of scope, not open |
| ESCALATE triggers | 1. `cached_tokens` on call 2 is below call 1's prompt token count - the prompt was built in the wrong order and the whole cost model is wrong. 2. The worst shard passes 180 minutes against the 200-minute timeout. 3. A retry is proposed that perturbs nothing. 4. Any design that lets the model emit a character a reader sees |
| Chosen strategy | Behind a flag, off, until the whole path works - then one commit flips it, deletes the job and retires the role together. The small model may not retire before call 2 works, because call 2 is what replaces it |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Exactly two model calls per item. Always.** Call 1 labels; call 2 writes the summary **and** the plan. Call 2 runs for every item that publishes, because it is the call that writes the summary - a gate may suppress the plan fields inside it and may never skip it. The deterministic pass before call 1 is **the candidate pass**, never "call 0"; a document that spells three things "call" cannot say "two calls" and be counted.

### 0.1 Standing rules, and they bind every row

Added 2026-09-11. The three merged rows did not have these written down; the four that remain do.

**Deliver the intent of this plan, not the letter of a row.** A structural fix matters more than a small diff. Where a row cannot be done correctly inside its stated scope, **expand the scope and say so in the pull request** - do not ship a band-aid to stay inside a file list somebody wrote before the code was read. `CLAUDE.md` Rule #5 is the authority; a row's file list reads like a fence and is meant to read like a start.

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
| 3b | Every call reports its own cost | 3 | C2 | PENDING | - | - | - |
| 3c | Own the prompt bytes | 6 | - | DEFERRED | - | - | - |
| 4 | The gate that refuses before the plan is drafted, and the ladder that steps down | 3 | D | DONE #612 | p11-r4 | #612 | worker |
| 5 | One chart, drawn end to end | 4 | E | DONE #621 | p11-r5 | #621 | worker |
| 6 | The small model, its job and its cache go | 5 | F | PENDING | - | - | - |

**Three rows are live and four are merged.** Rows 1, 2, 3 and 4 shipped; row 3c is deferred until the first daily run after row 6. **`parallel N = 1`, so no two rows of this plan run at the same time** - rows 4, 5 and 6 are one chain and row 3b is the only row that could have run beside one of them.

**This plan is three live rows and the second-heaviest constraint in the project.** Row #5 blocks 14 of the 58 live rows across the five open plans, because row #6 is what [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) row #7b waits on, and eleven rows wait on that. Measured 2026-09-11 over the five plans' own Reckoners; the working is in [`20260911-execution-order.md`](20260911-execution-order.md) section 2. **Row #6 is what row #5 unblocks, and nothing else in this plan is waiting on anybody to start it.**

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

- **Scope:** Two model calls per item currently fold into one set of flat `Summary` fields, so the row keeps one call's `cached_tokens`, `prefill_ms`, `decode_ms`, `input_tokens` and `output_tokens` and does not say which. Record them per call, so the operator console can plot call 1 against call 2.
- **Files touched:** `backend/idhazh/contracts/summary.py`, `backend/idhazh/contracts/item_health.py`, `backend/idhazh/contracts/public_telemetry.py`, `schemas/summary.schema.json`, `schemas/item-health-row.schema.json`, `schemas/public-telemetry.schema.json`, `backend/idhazh/summarize.py`, `backend/idhazh/visual_planner.py`, `backend/idhazh/publish_day_metrics.py`, `frontend/src/lib/console/item-cost.ts`, `backend/tests/test_contracts.py`, `backend/tests/test_summarize.py`, `backend/tests/test_visual_planner.py`, `backend/tests/test_telemetry.py`, `docs/architecture/summarize/throughput.md`. **Named rather than globbed on 2026-09-11**; the four globs this row carried - `schemas/*.schema.json`, `frontend/src/**`, `backend/tests/**`, `docs/architecture/summarize/**` - covered all 44 schema files, the whole published site and both summarize pages, which is not what the row writes.
- **Acceptance gates:** `GATE-PY` over `test_contracts.py`, `test_summarize.py`, `test_visual_planner.py` and `test_telemetry.py`; `GATE-SCHEMA`; `GATE-WEB`; `GATE-BROWSER`. This row adds: the `version` date-stamp and the `changelog` entry on all three contracts, in this commit.
- **Oracle:** One published item carries two `cached_tokens` figures and they differ - call 1 caches nothing on a cold slot, call 2 caches the whole article. One folded field cannot show that difference, which is the whole reason to split it. **Driven from `backend/var/canary/`**, which can carry the cold-slot case the committed archive may never have produced.
- **What this row does not do:** it changes no prompt, no call structure and no gate. It splits five recorded numbers into two sets of five and draws neither - the console panel that plots call 1 against call 2 is somebody else's row.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The two calls are not one measurement. Call 1 prefills the article and caches nothing; call 2 caches the article and decodes several times more. A single field holding one of them, unlabelled, is a number nobody can read | Owner, 2026-09-10, section 0 |
| 2 | The new fields are additive and defaulted, so a row written before this lands still validates. `version` stamped and `changelog` appended in the same commit | CLAUDE.md section 11 |

---

## 4b. Row #3c - Own the prompt bytes

- **Scope:** Send a rendered completion instead of a chat completion, so cache reuse is true by construction and the oracle becomes an offline byte assertion rather than a live-server measurement.
- **Files touched:** `backend/idhazh/llm/server.py`, `backend/idhazh/visual_planner.py`, `backend/idhazh/prompts/summarize_and_plan_visual.txt`, `backend/idhazh/prompts/label_article_elements.txt`, `backend/tests/test_visual_planner.py`, `backend/tests/test_summarize.py`, `docs/architecture/summarize/prompt.md`. **Named rather than globbed on 2026-09-11**; `backend/idhazh/prompts/**` is four files today and this row writes two of them.
- **Acceptance gates:** `GATE-PY` over `test_visual_planner.py` and `test_summarize.py`; `GATE-SCHEMA`, which must produce an empty diff because this row edits no contract.
- **Oracle:** Call 2's rendered prompt starts with call 1's rendered prompt, byte for byte. That is a string comparison over two files and needs no server, where today's oracle needs a running model and a warm cache slot. **The fixture is the two rendered prompts, written to `tests/fixtures/prompts/` by the row and compared offline.**
- **What this row does not do:** it changes no reply shape, no contract and no schema, and it does not remove the chat-completion path for any other caller. It changes how one call site renders its prompt.
- **Deferred until:** the first daily run after row 6 prices the 209 re-prefilled tokens on the runner. The figure that argues for this row was taken on a developer laptop against the retired weights, one run and no spread, so it cannot yet say the work is worth doing.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The four-token gap is `<think>\n\n</think>\n\n` from Qwen3's chat template. It writes an empty think block into the generation prompt under `enable_thinking: false` and drops it when the same turn is replayed as history, so the two renderings diverge there. Nothing in this repository renders it | Owner, 2026-09-10 |
| 2 | Deferred, not refused. A prefix cache reuses a prefix, so those four tokens end the reuse and 209 tokens re-prefill per item. Whether that is worth owning the prompt bytes is a runner measurement nobody has taken | Owner, 2026-09-10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Write the empty think block into call 1's history ourselves, so the two renderings agree | A band-aid on one template's private behaviour. It patches a symptom of a template we do not control, and the next model ships a different template | Owner, 2026-09-10; CLAUDE.md Rule #5 |

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
- **Oracle:** A published item's drawn bar heights are re-derived in the test from the committed element table and compared to the drawn attributes - so the chart is proved to be showing the article's numbers rather than merely showing numbers. **Driven from the canary day built by `backend/utilities/build_canary_day.py`**, never from the committed archive, per `CLAUDE.md` Rule #12.
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

## 7. Row #6 - The small model, its job and its cache go

- **Scope:** The flag flips, the small model's role leaves config, the CI job is deleted, the prompt file goes, and `finetune.student`/`teacher` are re-pointed - **all in one commit**.
- **Files touched:** `config/idhazh.json`, `.github/workflows/digest.yml`, `backend/idhazh/prompts/visual_planner.txt`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/tests/test_workflows.py`, `backend/tests/test_contracts.py`, `backend/tests/test_visual_planner.py`, `docs/architecture/summarize/prompt.md`, `docs/architecture/summarize/throughput.md`, `docs/how-to/fine-tune-a-model.md`. **Named rather than globbed on 2026-09-11**; `docs/**` was the whole documentation tree and `backend/idhazh/prompts/**` is four files, of which this row deletes one.
- **Acceptance gates:** `GATE-SUITE`; `GATE-SHELL`; `GATE-SCHEMA`; one dispatch of `digest.yml` end to end; `python -m idhazh site-weight`. **`GATE-SUITE` rather than `GATE-PY` here**, because this row deletes a workflow job and a config role and the blast radius is not a list of modules.
- **Oracle:** The dispatched run completes with **no** job between `work` and `assemble`, the repo cache falls from roughly 82 percent of the 10 GB ceiling to roughly 57, and the worst shard stays under 180 minutes. Three independent numbers, because a retirement that only removes a config key has not retired anything. **The first two are read from the dispatched run; the third is read from `state/runtime-counters.csv` over the seven days after it**, not from the table in any plan.
- **What this row does not do:** it changes no prompt text that survives, adds no field and draws nothing. It removes a model, a job, a cache role, a prompt file and four config keys, and it re-points two more.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The small model may not retire before call 2 works**, because call 2 is what replaces it. This is the last row for that reason | Carmack, 2026-09-05 |
| 2 | Retired completely: config entry, cache role, workflow job, env vars, prompt file, tests. **No half job** | O17 |
| 3 | `finetune.student` is `route` and `finetune.teacher` is `summarize` today - a distillation setup for the model being retired. That configuration is dead the moment this row lands and must be re-pointed in the same commit | Section 10.4 |
| 4 | `run.route_budget_minutes` is re-derived or deleted here. It exists because the old job ran 51 to 60 minutes against a 60-minute bound, and folding into `work` invalidates the number | Row 69 |

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
