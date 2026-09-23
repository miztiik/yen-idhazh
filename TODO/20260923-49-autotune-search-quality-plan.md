# Search quality gets a reading, and the reading gets written down

**Last Updated**: 2026-09-23

**Level**: 5. Row 4 mints a persisted contract and a new committed store, so it stops before its pull request opens. Rows 1, 2 and 3 are Level 2 or 3 and run AUTO once the user authorizes.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 1 row in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

**One row is one place.** Everything a worker needs for a row - the shapes, the exact names, the file list, the gates, the oracle - is in that row's own section. No row sends a worker to another row to find its own contract.

**The source material is [docs/architecture/publishing/autotune-search-quality.md](../docs/architecture/publishing/autotune-search-quality.md), already on `main`.** It holds the research. This plan holds the work. A worker reads that page before its row and does not re-measure what it states.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Nobody records what search returned on the day it returned it. Retention deletes the published day, so a reading not taken that day can never be recomputed, and no bar can ever be argued from evidence. |
| Hard scope - in | The entity-query floor stops being a literal and becomes a knob. Precision at the filled slots becomes a gated number beside recall, on the frozen key where it has a baseline. The self-hydrating key gains a caller over the window a reader actually searches, reading the day payloads so the tags survive. The pipeline writes one reading per question per run into a new committed store after the index is built. |
| Hard scope - out | Table A below. Six things, each with what leaving it out costs and what would bring it in. |
| Runner budget | Section 0d. Measured 2026-09-23: the whole reading is 11.0 s to 29.1 s of compute on the authoring laptop, which is 0.05 to 0.14 percent of the 6 h job. The site moves by zero bytes, because `state/` is not published. |
| ESCALATE triggers | Row 4 is Level 5 and stops before its pull request opens. Row 2 carries one question back to the owner (Table C). Any row that would set a bar on the self-hydrating number STOPS. Any row that would move `assist.similarity_floor` STOPS. |
| Chosen strategy | Build the instrument bottom-up and let it write for two weeks before anybody argues a bar. Fowler ruled the order and ruled that no shape is frozen ahead of its writer. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` One, because every row edits `backend/tests/test_retrieval_eval.py` and three of the four edit `backend/idhazh/contracts/knobs/assist.py`. Rows that share one surface do not parallelise, and a claimed width here would buy four hand resolutions. |

### Section 0a - The first step of every row

**Before the first edit, a worker re-derives its own file list by census and stops if the result differs from what the row says.** One `git grep` per named symbol. Report the difference, correct the row, then implement.

**Cite symbols, not line numbers.** Every file list below was taken on 2026-09-23 against `origin/main` at `b31e8a537`. Where a citation and the tree disagree, the symbol wins.

`grep_search` with a regular expression times out on this repository. Use `git grep -n <pattern> -- <paths>` from a terminal, or `Select-String` with an absolute path.

### Section 0b - What is in flight, and what it will do to these rows

**`live_corpus` in `backend/tests/test_retrieval_eval.py` is still on `origin/main` at `b31e8a537`, in four places.** The research page says it is deleted and that the deletion is the only part of that page shipping today. It is not deleted on the trunk; it is on a branch somebody else is carrying. Both states are fine for this plan: no row here reads `live_corpus`, `live_report`, or the whole-archive figure.

**What a worker does about it.** Rebase on `origin/main` before the first edit. If `live_corpus` is gone, nothing in these rows changes. If it is still there, nothing in these rows changes either. What must not happen is a blind conflict resolution inside that file - every row below names the symbols it touches, and a hunk outside those symbols belongs to the other branch.

### Section 0c - Table A: hard scope, out

| id | What is out | What leaving it out costs | What would bring it in |
| --- | --- | --- | --- |
| A1 | A model judge that scores whether a returned story actually answers its question | Precision counts every unjudged slot as wrong, so the reading understates quality by exactly the unjudged share - 10.0 percent on the self-hydrating key, 66.6 percent on the frozen one. Nothing can propose a floor. | Two weeks of committed readings, plus a council night's budget. The venue, the damping and the clamp shapes already exist ([llm-council.md](../docs/architecture/publishing/llm-council.md), `backend/idhazh/contracts/fitted_similarity_threshold.py`). |
| A2 | A console panel that draws the series | The numbers are committed and no operator sees them without opening a CSV. | A series long enough to draw. Two weeks of rows is the same precondition A1 has. |
| A3 | A bar on the self-hydrating number | A drop in live search quality is invisible until somebody reads the rows. | Two weeks of rows and a baseline argued from them. The number is ceiling-bound today - a question with 705 correct answers and ten slots cannot be lost - so a bar set now would measure the ceiling. |
| A4 | Moving `assist.similarity_floor` off 0.35 | The floor may be leaving recall on the table; the tightest off-domain probe has 0.055 of margin under it. | A judged reading (A1). The wall is the measured same-domain noise at 0.2716, and the floor may never cross it downward. |
| A5 | Making the published month shard carry entity tags | Row 3's window reader opens the day payloads, a second read of data the index already summarises. Measured 1.54 s to 2.71 s for 22 days. | A measurement showing that read costs something on the runner. The span the pipeline already records answers it. |
| A6 | Keeping the hand-written 60-question key current | It measures one frozen week for ever. Every one of its 297 judgements falls between 2026-08-21 and 2026-08-26. | A person willing to judge new days. No agent may write, rank or select a judgement - the summarizer is part of what is measured. |

### Section 0d - Table B: the runner budget, measured

**Measured 2026-09-23** on the authoring machine: a Windows laptop running seven other agents' test suites at the same time. That contention is the whole of the spread below, and it is named rather than averaged away.

| id | Step | Reading 1 | Reading 2 |
| --- | --- | --- | --- |
| B1 | Open the 22 day payloads the window covers | 1.54 s | 2.71 s |
| B2 | Build the 30 questions from the tags | 0.02 s | 0.06 s |
| B3 | Encode the 30 questions | 0.94 s | 4.10 s |
| B4 | Rank 30 questions over 7,185 vectors | 8.52 s | 22.18 s |
| B5 | All four together | 11.0 s | 29.1 s |

**Against the 6 h job that is 0.05 to 0.14 percent.** The conclusion holds at both ends, so the spread does not need narrowing (Guardrail #10).

**What is not measured, and it is labelled an estimate.** Nobody has run this on a stock `ubuntu-latest` 4 vCPU runner. The work is single-threaded pure Python, so a fourth core does not help it, and a runner core is usually slower than this laptop's. The estimate is one to three times the slower reading - **30 s to 90 s, still under 0.5 percent of the job**. **The measurement that settles it:** the first scheduled run after row 4 lands records its own step span in `state/span-rollup`, which already exists. No new instrument is needed, and no row here adds one.

**What the cost scales with.** The question count and `assist.search_months`, never the archive (Guardrail #12). Ranking is linear in the question count: 30 questions cost 8.52 s, so 100 questions would cost about 28 s on the same box, and that extrapolation is labelled one.

**The site moves by zero bytes.** `state/` is not published and no console page reads it yet (A2), so the 1 GB Pages cap is untouched. The checkout grows by an estimated 22.5 KB a day - 30 questions times five runs at about 150 B a row - and that estimate is settled by the size of the first committed file.

### Section 0e - The one pause

**Row 4 mints a persisted contract and a new committed store, so it stops before its pull request opens** (CLAUDE.md section 6, Level 5). It is cheap to write and expensive to reverse: a shape a run has already written is a shape every later correction has to migrate.

**A worker reaching it stops and reports**: the fields it wrote and what each one lets somebody decide, the bytes a day costs, what a later correction would cost, and the one design decision the research page left open (Section 5c, decision 3). It does not open the pull request. The owner rules, and the ruling lands as a dated `## Design rationale` line in the living doc the row edits.

**Rows 1, 2 and 3 do not pause.** Row 2 carries a question to the owner in its report (Table C) without stopping: the work it ships is complete on its own.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The entity-query floor becomes a knob | - | A | PENDING | - | - | - |
| 2 | Precision at the filled slots becomes a gated number | 1 | A | PENDING | - | - | - |
| 3 | The self-hydrating key gets a caller over the window a reader searches | 2 | A | PENDING | - | - | - |
| 4 | The reading gets a shape, a home and a writer | 3 | B | PENDING | - | - | - |

### Section 1a - Four pull requests, one at a time

| PR | Row | Level | Waits for | Why it cannot run beside its neighbour |
| --- | --- | --- | --- | --- |
| P1 | 1 | 2 | nothing | - |
| P2 | 2 | 3 | P1 | Both edit `backend/idhazh/contracts/knobs/assist.py`, `config/idhazh.json` and `backend/tests/test_retrieval_eval.py`. |
| P3 | 3 | 3 | P2 | Both edit `backend/idhazh/evals/retrieval.py` and `backend/tests/test_retrieval_eval.py`. |
| P4 | 4 | 5, PAUSE | P3 | It calls what row 3 wrote. |

**The dependency chain is a file chain, not a logic chain.** Row 2 does not need row 1's knob and row 3 does not need row 2's gate. They are serial because they write the same four files, and dispatching two of them at once buys a hand resolution nobody reviewed.

### Section 1b - Table D: what was measured for this plan, so no row re-measures it

Taken 2026-09-23 against `origin/main` at `b31e8a537`, with the committed config and the committed encoder.

| id | Reading | Value |
| --- | --- | --- |
| D1 | The window a reader searches | `2026-09` alone; 22 days reachable; 7,186 items, 7,185 carrying a vector |
| D2 | Tag coverage over that window | 2,949 of 7,186 items, which is 41.0 percent |
| D3 | The self-hydrating key over that window | 30 questions, 5,269 answers; smallest 14, largest 705 |
| D4 | Precision at the filled slots, self-hydrating key | 0.900 - 226 of 251 filled slots held a tagged answer; 49 of the 300 slots stayed empty |
| D5 | Recall at ten, capped, self-hydrating key | 0.753 +/- 0.053; weakest question `entity-ftc` at 0.100 |
| D6 | Unjudged share of filled slots, self-hydrating key | 10.0 percent |
| D7 | The frozen key over the pinned corpus (`2026-08-26`) | 2,235 of 2,237 items carry a vector; 60 questions, every one filled at least one slot |
| D8 | Recall at ten, capped, frozen key | 0.756 +/- 0.037 - the number `assist.recall_min` of 0.68 gates |
| D9 | Precision at the filled slots, frozen key | 0.3447 +/- 0.0225; two standard errors below is 0.2997 |
| D10 | Unjudged share of filled slots, frozen key | 66.6 percent |

**D9 read against D10 is the finding that shapes row 2.** Precision on the frozen key is 0.345 because two thirds of every filled slot holds a story nobody judged, and an unjudged story counts as wrong. The number is still the right instrument for the failure the owner named - a change that fills slots with junk drives it down and drives recall up - but the bar it can carry is 0.30, and that bar is two-thirds blind.

## Section 2 - Row 1: the entity-query floor becomes a knob

**Level 2.** Runs first. Nothing waits on its logic; three later rows wait on its files.

**Why.** `entity_queries` takes `min_items` and every caller spells `3`. The knob has to exist before row 3 adds the first production caller, or that caller ships a literal (Guardrail #6).

### Section 2a - The shapes this row needs

**The knob.** `entity_query_min_items` joins `AssistConfig` in `backend/idhazh/contracts/knobs/assist.py`:

```python
entity_query_min_items: int = Field(default=3, ge=1, le=100, ...)
```

Its description says what it selects and what moving it does: how many published stories have to carry an entity name before that name becomes a question the free key asks. Three is the smallest count that is not one story's phrasing. Raising it drops thin questions and shrinks the key; lowering it admits questions whose reading swings on a single item. A name no story carries builds no question at any value, which is what keeps a name a person added early from reading as a search failure.

`config/idhazh.json` carries `"entity_query_min_items": 3` beside the other `assist` knobs.

**`ge=1` and `le=100`, and the reason for each.** One answer is a wide reading rather than a silent failure, so the floor does not refuse it. A hundred answers in ten slots is a question that measures the ceiling, so the ceiling is a typo guard. Neither bound can stop a value that empties the key, so the **emptiness check in Section 2c is the control** rather than the range.

**Which test reads the knob and which keeps its literal.** Two tests in `backend/tests/test_retrieval_eval.py` spell `3`, and they are not the same kind of test.

| id | Test | What happens to its `3` |
| --- | --- | --- |
| E1 | `test_the_entity_tier_needs_a_slug_on_enough_items` | **Keeps both literals.** It drives the pure function with `min_items=3` and `min_items=4` over a three-item hand-built corpus. They are the arguments under test. A unit test that read the config would test the config, and would go red the day somebody tuned a knob. |
| E2 | `test_the_entity_tier_builds_one_query_per_slug_that_clears_the_floor` | **Reads the knob in both places** - the `carried >= 3` comparison and the `min_items=3` argument - so the assertion follows what ships. It already takes a `corpus` fixture; it takes the `config` fixture beside it. |

**There is no generated layer to regenerate.** `schemas/` and `frontend/src/contracts/` went on 2026-09-23. `AppConfig` is the only copy of this shape, and `Contract.json_schema()` computes a schema from it on demand when one is wanted. What holds the frontend's hand-written copies in step is four tests under `backend/tests/contracts/`: `test_frontend_field_set.py`, `test_frontend_vocabularies.py`, `test_frontend_console_lists.py` and `test_no_generated_layer.py`.

**The appearance file does not declare it.** This knob is the measurement's, like `eval_corpus_through`, not the browser's. `config/appearance.json` and `AppearanceConfig` stay untouched. `backend/tests/contracts/_fixtures.py` carries the list of `assist` knobs the browser interface declares none of; the census in Section 0a says whether this name belongs on it.

**One fixture must move or a test fails.** `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json` asserts every knob differs from the committed value, so it gains an `entity_query_min_items` set away from 3.

### Section 2b - Files, measured 2026-09-23

`backend/idhazh/contracts/knobs/assist.py`, `config/idhazh.json`, `backend/tests/test_retrieval_eval.py`, `backend/tests/contracts/_fixtures.py`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `docs/concepts/config.md`.

### Section 2c - Acceptance gates

- Local: `ruff check backend`, `ruff format --check backend`, `mypy backend` clean.
- Local: `pytest backend/tests/test_retrieval_eval.py backend/tests/contracts backend/tests/test_appearance_config.py -q`. Named because they are the readers of the knob list.
- Local: `pytest backend/tests/contracts/test_frontend_field_set.py backend/tests/contracts/test_frontend_vocabularies.py backend/tests/contracts/test_frontend_console_lists.py backend/tests/contracts/test_no_generated_layer.py -q`. These four are what a generated layer used to do: they hold the frontend's hand copies against the contract, and refuse the generator coming back.
- Local: **the committed config builds a key that is not empty.** E2 asserts at least one question, so a value that empties the key fails by name rather than by a silent pass over zero questions.
- CI: the full suite.

### Section 2d - Oracle

**The one load-bearing check: the built question set follows the committed config and nothing else.** Set `"entity_query_min_items": 999` in `config/idhazh.json`, run E2, and confirm it fails saying the key is empty. Restore from the commit, never from the working tree.

**It can fail for the reason the row exists.** On the base tree that same edit changes nothing, because E2 spells `3`. The difference between those two outcomes is the row.

**What it cannot settle:** whether 3 is the right floor. The smallest question in today's key carries 14 answers (D3), so every value from 1 to 14 builds the same 30 questions, and only a vocabulary with a thin name would tell them apart.

### Section 2e - Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | E1 keeps its literals and only E2 reads the knob. A pure-function test that reads config tests the config. | Fowler |
| 2 | `ge=1`. A one-answer question is a wide reading, not a silent failure, and a name with no stories behind it builds no question at any value. | Fowler |
| 3 | `le=100`. Past a hundred answers in ten slots the question measures the ceiling. The emptiness check, not the range, is what catches a value that empties the key. | Andre |
| 4 | The name is `entity_query_min_items`, not `min_items`. `AssistConfig` also holds the browser's knobs, and `min_items` there does not say which items. | Fowler |

### Section 2f - Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the literal and have row 3's caller pass `3` | It is the hard-coded value Guardrail #6 refuses, one call site further on | Nothing today: the same edit one row later. The cost is that row 3 then ships a literal and needs a row of its own to remove it | Fowler |
| 2 | Reuse `assist.result_limit` as the floor | It answers a different question - how many slots a reader sees, not how much evidence makes a question worth asking | Nothing to take. The cost is that tuning a reader's list silently re-cuts the question set | Andre |
| 3 | Put the floor in the taxonomy beside the names | The taxonomy says what the vocabulary is; it does not say how much evidence a measurement needs | A taxonomy field, its schema, and a second place to look for the number | Fowler |

## Section 3 - Row 2: precision at the filled slots becomes a gated number

**Level 3.** Waits on row 1's files, not on its logic.

**Why.** Nothing gates precision today. Recall rewards showing more, so a change that drops the floor and fills every slot with near-misses raises the gated number and fails nothing. Precision at the filled slots is what falls when that happens, and the owner ruled it is the failure that matters: no results is fine, bad results are not.

### Section 3a - The shapes this row needs

**Two properties on the report, in `backend/idhazh/evals/retrieval.py`.**

`QueryOutcome.filled` is `found + unlabelled`, which is already how many slots the query filled - the module sets `unlabelled` to `len(hits) - len(found)`. `QueryOutcome.precision` is `found / filled`, and `0.0` when nothing filled.

`RetrievalReport.precision_at_filled` is the mean of `precision` over the outcomes that filled at least one slot, and `RetrievalReport.standard_error_precision` is its standard error, both built the way `recall_reachable` and `standard_error_reachable` already are. `RetrievalReport.filled_nothing` counts the excluded queries, and `summary()` prints the precision, its error, the excluded count and the existing `unlabelled_share` together.

**The bar.** `precision_min` joins `AssistConfig`, `Field(default=0.30, ge=0.0, le=1.0)`. Its description carries four things: that it is precision over the slots the search filled, scored against the corpus `eval_corpus_through` pins; that every unjudged slot counts as a wrong answer, so the number is a lower bound; that 0.30 is two standard errors below the measured 0.3447 +/- 0.0225 (D9), which is the rule `recall_min` was set by; and that the pin is what keeps it from expiring on the publishing rate.

**The gate.** `test_the_ranking_clears_its_bar` asserts the precision bar alongside the recall bar it already asserts. The failure message names both numbers and the unjudged share, because 0.30 read without 66.6 percent is a number that looks like a verdict on search.

### Section 3b - Table C: the half of the ruling this row holds for the owner

The owner ruled that precision becomes the gated number **and recall becomes reported-only**. This row ships the first half. It holds the second, because the measurement says what removing the recall gate costs, and that cost was not priced when the ruling was made. This is a finding handed back, not a ruling overturned (CLAUDE.md section 0d). **A worker does not resolve it by deleting the recall assertion.**

| id | Option | What it costs | What it gives up |
| --- | --- | --- | --- |
| C1 | **Recommended.** Keep `recall_min` gating and add `precision_min` beside it | Two bars on one frozen key; a merge candidate clears both | Nothing the ruling asked for. A bad result now fails a merge, which is the whole intent |
| C2 | Drop `recall_min` to reported-only as ruled, and gate precision alone | Eight more files: `config/appearance.json`, `AppearanceConfig`, two appearance artefacts, two fixtures, `docs/concepts/config.md`, `docs/reference/site-weight.md` | **The detection of a partial loss of answers.** A query whose list goes empty leaves the precision mean entirely, so precision does not move while recall falls. All 60 queries fill a slot today (D7), so the loss stays invisible until enough of them empty |
| C3 | Drop `recall_min` and score an empty list as precision 0 | One bar, and an empty list fails | The promise the empty state makes. "Nothing in the archive is close to that" becomes a failing grade, which inverts the ruling that shaped the whole loop |

**Recommended: C1.** It delivers the intent - a list full of junk now fails a merge - without paying for it with the one instrument that catches answers going missing.

### Section 3c - Files, measured 2026-09-23

`backend/idhazh/evals/retrieval.py`, `backend/idhazh/contracts/knobs/assist.py`, `config/idhazh.json`, `schemas/app-config.schema.json` and `frontend/src/contracts/app-config.ts` (both generated), `backend/tests/test_retrieval_eval.py`, `backend/tests/contracts/_fixtures.py`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `docs/concepts/search-quality.md`, `docs/concepts/evaluation.md`, `docs/concepts/config.md`.

Under C1 no appearance-side file moves. Under C2 the eight in Table C move too, which is why the choice is a scope question and not a one-line edit.

### Section 3d - Acceptance gates

- Local: `ruff check backend`, `ruff format --check backend`, `mypy backend` clean.
- Local: `pytest backend/tests/test_retrieval_eval.py backend/tests/contracts -q`. **The module carries `pytestmark = pytest.mark.slow`**, so name it by path rather than trusting the default selection.
- Local: no generated layer to regenerate - `schemas/` and `frontend/src/contracts/` went on 2026-09-23, and `Contract.json_schema()` computes a schema on demand. `backend/tests/contracts/test_frontend_field_set.py`, `test_frontend_vocabularies.py`, `test_frontend_console_lists.py` and `test_no_generated_layer.py` are what holds the frontend's hand copies in step, and `backend/tests/contracts` above already runs all four.
- Local: the printed summary names the precision, its standard error, the excluded query count and the unjudged share on one line.
- CI: the full suite.

### Section 3e - Oracle

**The load-bearing check: lowering the floor fails the new gate and passes the old one.** In a scratch copy of `config/idhazh.json` set `assist.similarity_floor` to `0.20`, run the gate test, and record both numbers. The claim this proves is two-sided:

- precision falls below 0.30 and the test names it, so the new gate bites;
- recall **rises** and its assertion still passes, so the gate that exists today could not have caught it.

Restore from the commit, never from the working tree, and put both numbers in the report. A one-sided result is a finding: say which side failed to move and stop.

**It can fail for the reason the row exists.** On the base tree the same edit turns nothing red at all, because no assertion reads precision.

**What it cannot settle:** whether precision counted with every unjudged slot as wrong matches what a reader would call a bad result. 66.6 percent of the filled slots are unjudged (D10). Only a judged sample settles it, and that is A1.

### Section 3f - Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The bar is 0.30 - two standard errors below the measured 0.3447 +/- 0.0225 over the pinned corpus, which is the rule `recall_min` was set by | Andre |
| 2 | The mean is macro over the queries that filled a slot. An empty list is excluded rather than scored zero, because the empty state is a promise rather than a failure, and the excluded count is printed | Andre |
| 3 | The unjudged share is printed on the same line as the precision figure. 0.30 read without 66.6 percent beside it reads as a verdict on search | Reader |
| 4 | `recall_min` keeps gating. The second half of the ruling is held for the owner in Table C, and a worker does not settle it by deleting the assertion | Andre priced it; the owner rules |
| 5 | The pin stays. `eval_corpus_through` is what stops either bar expiring on the publishing rate | Andre |

### Section 3g - Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Set the bar from the self-hydrating key's 0.900 (D4) instead | That key has no baseline and is ceiling-bound: a question with 705 answers and ten slots cannot be lost, so the bar would measure the ceiling | Two weeks of committed readings (A3), then the same arithmetic | Andre |
| 2 | Count an unjudged slot as a right answer | It turns precision into an upper bound and scores a list of pure junk at 1.000 | Nothing to take. The cost is a gate that cannot fail | Andre |
| 3 | Gate the micro figure (0.3345) rather than the macro mean | Micro weights a query that filled ten slots ten times as heavily as one that filled one, so one broad question carries the gate | Nothing - both are computed. The cost is a bar that moves when the question mix moves | Andre |
| 4 | Wait for the judge before gating anything | The failure the ruling names is unguarded today, and the judge is weeks away behind two weeks of rows | The judge's own plan (A1) | Andre |

## Section 4 - Row 3: the self-hydrating key gets a caller over the window a reader searches

**Level 3.** Waits on row 2's files, not on its logic.

**Why.** `entity_queries` has no production caller at all. Scored through the loader a reader's tab uses it returns nothing and always will: the published month shard carries `date`, `item_id`, `title`, `vector` and `vertical`, so `load_index_corpus` hard-codes the tag set empty. The key has to read the day payloads, bounded by the window a tab actually reads.

### Section 4a - The shapes this row needs

**One home for the scope rule.** `load_index_corpus` works out which shards a tab reads inside its own body. It comes out as `window_months(root, *, months, min_days, through=None) -> tuple[str, ...]`, returning the month stems newest first, and `load_index_corpus` calls it. The rule is unchanged: take `months` shards newest first, and if the days they can answer for fall under `min_days` take one more shard and one more only. **`through` keeps working** - it filters on the shard stem before any file is opened. Two copies of that rule is the drift the module's own docstring warns about, which is why this is an extraction and not a second implementation.

**The window reader.** `load_window_corpus(root, *, months, min_days) -> Corpus` opens the day payloads whose month is one the window named, decoded exactly as `load_corpus` decodes them, so `entities` survives. Its docstring carries the Guardrail #12 declaration: **the cover is `assist.search_months` and `assist.search_min_days`, never the archive.** It opens the days of one or two months whatever the archive holds, and the day-directory listing is the residue - the same sentence `load_corpus` already carries.

**The reading, in a new module `backend/idhazh/evals/search_quality.py`.** One question: what reading does today's search deserve? It builds the key from the window corpus, encodes it, ranks it, and returns a frozen dataclass.

| id | On the reading | What it holds |
| --- | --- | --- |
| F1 | the window | the month stems read, the days reachable, the items, the items carrying at least one tag |
| F2 | one entry per question | the question id, its answers, the slots it filled, the answers it found, its precision, its capped recall |
| F3 | the ruler | `ENCODER_REF` from `idhazh.embed`, plus the floor, the slot count and the entity-query floor that were in force |

**Nothing here is persisted and nothing gets a schema.** A shape with no writer makes every later correction a breaking change with a migration to write (CLAUDE.md section 11). Row 4 is where these fields are frozen, and it is the row that writes them.

**The aggregate is derived, never stored.** `precision_at_filled` over the whole reading is row 2's property applied to F2, so there is one definition of it and not two.

### Section 4b - Two sentences this row makes false, and kills in the same commit

| id | Where | What it says | What replaces it |
| --- | --- | --- | --- |
| G1 | the `entity_queries` docstring in `backend/idhazh/evals/retrieval.py` | "It yields nothing today... no published item carries an entity slug" | 2,949 of the 7,186 items in the window carry one, across 30 names (D2, D3). A deterministic tagger has written them since 2026-08-26 |
| G2 | `docs/concepts/search-quality.md`, the sentence reading "so the tier stays at zero and climbs as new days land" | the same stale claim | the same correction, with D2 and D3 as its evidence |

**One line joins the bounded-read inventory in `docs/concepts/growing-reads.md`**, beside `evals.retrieval.load_index_corpus, live`: `load_window_corpus` opens the day directories of `frontend/public/digest/` under the cover of `assist.search_months` and `assist.search_min_days`. It is a bounded read with a named cover, so it is an inventory line and **not** a declared growing read.

### Section 4c - Files, measured 2026-09-23

`backend/idhazh/evals/retrieval.py`, `backend/idhazh/evals/search_quality.py` (new), `backend/tests/test_search_quality.py` (new), `backend/tests/test_retrieval_eval.py`, `docs/concepts/search-quality.md`, `docs/concepts/growing-reads.md`.

### Section 4d - Acceptance gates

- Local: `ruff check backend`, `ruff format --check backend`, `mypy backend` clean.
- Local: `pytest backend/tests/test_search_quality.py backend/tests/test_retrieval_eval.py -q`, by path, because both modules are marked slow.
- Local: `git grep -n 'yields nothing today' -- backend docs` returns nothing.
- Local: `python backend/utilities/doc_load.py` before and after, and the two doc pages still pass their own tests.
- **No test walks a growing collection.** Every case below is driven from a fixture tree the test builds, fixed in size (CLAUDE.md section 13).
- CI: the full suite.

### Section 4e - Oracle

**The load-bearing check is a two-sided one on a single fixture tree**, and it is exactly the claim the research page makes.

Build a temporary tree with two months of day payloads - a newest month of 3 days and an older month of 10 - where several items carry entity tags. Call `assemble.rebuild_search_index` over it so the month shards are real rather than hand-written. Then, with `months=1, min_days=7`:

- `entity_queries(load_window_corpus(...), ...)` returns questions;
- `entity_queries(load_index_corpus(...), ...)` returns nothing at all over the same tree.

And the window rule holds: the newest month alone answers 3 days, under the floor, so exactly one more shard is read and a third is never opened.

**It can fail for the reason the row exists.** Point `load_window_corpus` at the shards instead of the day payloads and the first assertion goes red immediately, with no tags to build a question from.

**What it cannot settle:** whether 30 tag names are a good sample of what a reader types. The question here is the tag, so this key cannot say whether a reader's own phrasing finds the story. Only the hand-written key does that (A6).

### Section 4f - Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The scope rule is extracted to one function, not copied. Two copies of `readScope` in Python plus the one in `search.ts` is three things to keep in step | Fowler |
| 2 | The window reader opens the day payloads. The shard carries no tags, so a key scored through the reader's own loader is empty for ever and looks healthy doing it | Andre |
| 3 | The reading stays in memory in this row. No schema, no store, no writer - the freezing happens where the writing happens | Fowler |
| 4 | It gets its own module. `retrieval.py` answers whether search finds the right thing; what reading today's search deserves is a second question | Fowler |
| 5 | Capped recall is carried per question and never gated. A question with 705 answers and ten slots cannot be lost (A3) | Andre |

### Section 4g - Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Score the key through `load_index_corpus` | The shard carries no tags, so the key is empty for ever and the instrument reads zero while looking healthy | Nothing to take. The cost is an instrument that cannot fail | Andre |
| 2 | Put the tags in the published month shard so the shard can answer | It is a published payload change plus a re-emit of every shard, to save a read measured at 1.54 s to 2.71 s (B1) | A `search_index` schema change, a re-emit of every committed shard, and bytes on every reader's fetch. A5 names what would bring it in | Fowler |
| 3 | Read the whole archive instead of the window | It measures a collection nobody queries, and its cost rises with the archive (Guardrail #12) | Nothing to take - that read was deleted for this reason | Fowler |
| 4 | Sample the questions rather than score all of them | 30 questions cost 8.52 s to 22.18 s (B4), which is 0.05 to 0.14 percent of the job, and a sample makes two runs incomparable | Nothing today. The cost is that the vocabulary can outgrow it: 100 questions would be about 28 s of ranking, and that figure is an extrapolation rather than a reading | Carmack |

## Section 5 - Row 4: the reading gets a shape, a home and a writer

**Level 5. It stops before its pull request opens** (Section 0e).

**Why.** Nothing records a reading. Retention deletes the published day, so a reading not taken that day can never be recomputed, and nothing can draw a trend without re-running the encoder over an archive that no longer holds the window.

### Section 5a - The store, the filename, and the writer

**Where.** `state/search-quality/<YYYY>/<MM>/<DD>/`, named for the ranker rather than for one of its two surfaces. The same code serves the front page search box and the archive search, so `archive-search-quality` would claim half of what it measures. Owner ruling, 2026-09-23.

**The filename follows the one-writer-per-path rule.** `ledger.segment_name` spells `<run_id>-<attempt>-<job>-<shard>.csv` and `ledger.day_shard_path` builds the path. `idhazh.paths.is_written_once` reads it back, and it passes on `SEGMENT_NAME` alone with no list to join. **The mechanism may change later; this store follows whatever it becomes rather than inventing a second scheme.** Owner ruling, 2026-09-23.

**Who writes it.** `ledger.write_segment` from `stage_assemble`, with `job=ServerJob.ASSEMBLE` and `shard=ASSEMBLE_SHARD`, which is 0 because assemble runs once for the whole day. The call sits immediately after `assemble.rebuild_search_index` returns and before the manifest is built, because the reading is about the index this run just rebuilt.

**It degrades rather than failing.** No committed month shard, or no encoder on disk, records nothing and the day still publishes (section 1a). A missing row is visible in the series; a day lost to a measurement that would not run is gone.

**Not an operator verb and not a new workflow.** The window is gone after the prune, so a reading not taken on the day is lost, and the pipeline already loads this encoder in this job. Owner ruling, 2026-09-23.

### Section 5b - The shape, and the one decision the pause exists for

**The grain is one row per question per run**, the shape `state/item-health/` already takes.

**The research page lists `score_on_common` as a cell. It cannot be one.** A comparison between two readings cannot be stored by the earlier of them: the run writing today's row does not know which questions next month's run will carry. Storing the per-question reading makes that comparison computable between any two runs, at any distance, without re-running the encoder - and the run-level aggregate is then derived from the rows rather than stored a second time.

**What the grain costs.** 30 rows a run instead of 1, five runs a day. Estimated 22.5 KB a day and about 8 MB a year of checkout, from a 150 B row. That is an estimate from the cell count, **labelled one, and settled by the size of the first committed file.** `state/item-health/` already writes 400 rows a day on the committed ceiling, so this is a quarter of a store that already exists.

**What the alternative costs.** A per-run row carrying `queries_added`, `queries_dropped` and a digest of the question ids says whether the set moved and by how much. It can never say what the number would have been over the questions both runs carried, which is the one comparison the owner named as having to survive a moving vocabulary.

**This is what the worker reports at the pause.** It writes the per-question grain, and the owner rules before the pull request opens.

### Section 5c - The contract

`backend/idhazh/contracts/search_quality.py` declares `SearchQualityRow(Contract)` with `__schema_stem__ = "search-quality-row"`, one `__changelog__` entry, and the three CSV methods. **`backend/idhazh/contracts/day_validation.py` is the template** - same base, same three methods, same one-row-per-key shape. Nothing here invents a second pattern.

| id | Cell | What it lets somebody decide |
| --- | --- | --- |
| H1 | `date`, `run_id` | which day's archive was measured, and by which run |
| H2 | `query_id` | which question the row is about. With H1 it is the key |
| H3 | `answers` | how many published stories carry that name. Separates a weak question from a thin one |
| H4 | `filled`, `found` | how many slots it filled, and how many held an answer. Precision is `found / filled` and is derived rather than stored |
| H5 | `recall_capped` | reported, never gated (A3) |
| H6 | `window_months`, `window_days`, `window_items`, `items_tagged` | what was searched, so two readings compare, and whether a fall is search or fewer tagged stories |
| H7 | `encoder_ref` | the ruler. Two values inside one window is a change in the instrument rather than in search |
| H8 | `similarity_floor`, `result_limit`, `entity_query_min_items` | the three knobs that move the number while search stands still |
| H9 | the taxonomy and watchlist digests | whether the vocabulary moved at all. Read from `settings.digests`, which `stage_assemble` already hands to `build_manifest` as `config_digests` - **confirm the key spellings by census before writing them** |

H6 to H9 repeat on every row of one run. That is what `item-health` already does, and it is what makes one row readable without its siblings.

`SEARCH_QUALITY_KEY = ("date", "run_id", "query_id")`, the shape `ITEM_HEALTH_KEY` takes.

### Section 5d - Three declarations join a closed set, in one commit

`SEARCH_QUALITY_DIRNAME = "search-quality"` beside its siblings in `backend/idhazh/ledger.py`; `SegmentLedger.SEARCH_QUALITY`; and a `_TREE_SHAPES` entry pairing the key with the contract. The enum's own docstring says a ledger joins the set in the row that moves its writer and never before it. **This is that row.**

**What joining the set brings with no file to edit.** Worth naming, because a worker that does not know this goes looking for five more edits.

| id | What | Why it is free |
| --- | --- | --- |
| I1 | The closed day fold | `stages/compact.py` walks `SegmentLedger` |
| I2 | An operator's range prune | `telemetry/prune.py` derives `WRITER_OWNED_STORES` from `SegmentLedger` |
| I3 | No merge driver, which is correct | One writer per path leaves nothing to settle. `backend/tests/workflows/test_worker_ledgers.py` asserts `git check-attr merge` answers `unspecified` for every member |
| I4 | The path-class census | `backend/tests/contracts/test_path_classes.py` iterates the enum |
| I5 | Commit staging | `backend/tests/workflows/test_ledger_staging.py` requires every tree's folded day to be staged by some job, and **the assemble job stages `state` whole**. No workflow file moves |

**No scheduled prune, and the reason.** The reading IS the series, and deleting it deletes the trend the bar will be argued from. I2 already reaches it when an operator asks. What that costs: the store grows by an estimated 22.5 KB a day for ever. The row that adds a window is the one that adds the console panel (A2), because that is when somebody knows how much history a chart needs.

### Section 5e - Files, measured 2026-09-23

`backend/idhazh/contracts/search_quality.py` (new), `backend/idhazh/contracts/export.py`, `backend/idhazh/ledger.py`, `backend/idhazh/stages/assemble.py`, `backend/idhazh/evals/search_quality.py`, `schemas/search-quality-row.schema.json` (generated, new), the generated frontend contract if the exporter emits one for this model, `backend/tests/test_search_quality.py`, `docs/architecture/publishing/autotune-search-quality.md`.

**One census decides the rest of the doc list.** `git grep -n 'day-validations' -- docs` names every page that lists the committed stores one at a time. This store joins each of them and no others.

**The research page stops being research.** Its opening says nothing on it is built. Once this row lands, the reading, the store and the caller are built; the judge, the console panel and the bar are not. The page says which is which, and keeps the judge section as the research it is.

### Section 5f - Acceptance gates

- Local: `ruff check backend`, `ruff format --check backend`, `mypy backend` clean.
- Local: `pytest backend/tests/test_search_quality.py backend/tests/contracts backend/tests/test_ledger.py backend/tests/workflows/test_worker_ledgers.py backend/tests/workflows/test_ledger_staging.py -q`.
- Local: no generated layer to regenerate - `schemas/` and `frontend/src/contracts/` went on 2026-09-23, and `Contract.json_schema()` computes a schema on demand. `backend/tests/contracts/test_frontend_field_set.py`, `test_frontend_vocabularies.py`, `test_frontend_console_lists.py` and `test_no_generated_layer.py` are what holds the frontend's hand copies in step, and `backend/tests/contracts` above already runs all four.
- Local: a round trip - a row through `csv_row` and back through `from_csv_row` is the same row, float cells included.
- Local: `python backend/utilities/doc_load.py` before and after.
- **The run id in every fixture is production-shaped**, `<YYYY-MM-DD>-<execution>`, and matches `RUN_ID_PATTERN`. A made-up id passes a test against a filename production never writes.
- CI: the full suite.

### Section 5g - Oracle

**The one load-bearing check: exactly one file appears, at the path the producer names, and nobody else could have written it.**

Run the assemble stage over a fixture tree - row 3's tree with this run's inputs added - and assert:

- the day directory holds exactly one file;
- its name is what `ledger.segment_name` returns for this run, attempt, job and shard, **built by calling the producer and never spelled in the test**;
- `idhazh.paths.is_written_once` returns True for its relative path;
- it holds one row per question the reading carried, and `from_csv_row` reads every one of them back unchanged.

**Prove it can fail.** Name the file `<DD>.csv` instead: `is_written_once` returns False and the day-tree walk refuses the name rather than skipping it. Restore from the commit, never from the working tree.

**Prove the guard works.** Run the same stage over a tree with no committed month shard: the day publishes, no file is written, and the run records why.

**What it cannot settle:** that the numbers in the row are the numbers a reader's browser produces. The Python twin and `frontend/src/lib/assist/search.ts` are two implementations, and only the index-drift comparison in `backend/tests/test_retrieval_eval.py` puts them side by side.

### Section 5h - Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The store is `state/search-quality/`, named for the ranker rather than for one of its two surfaces | Owner, 2026-09-23 |
| 2 | The filename follows `SEGMENT_NAME`, not a bare `<DD>.csv`, and follows that mechanism wherever it goes | Owner, 2026-09-23 |
| 3 | One row per question per run, so the comparison over shared questions is computable between any two runs rather than stored by the earlier one. **This is the decision the pause exists for** | proposed by Fowler; the owner rules |
| 4 | The contract, the enum member and the writer land in one commit. A shape with no writer makes every later correction a breaking change with a migration to write | Fowler |
| 5 | The writer degrades: no shard or no encoder records nothing, and the day still publishes | Fowler |
| 6 | No scheduled prune. The reading is the series, and an operator's range prune already reaches it | Carmack |
| 7 | The write happens in the pipeline after the index, never in an operator verb and never in a workflow of its own | Owner, 2026-09-23 |

### Section 5i - Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One row per run with `score_on_common` as a cell | The earlier of two readings cannot know which questions the later one carries, so the cell would be a comparison against whatever happened to be on disk | Nothing to take today. The cost is that a comparison across a vocabulary change becomes impossible after the fact, which is the property the owner named | Fowler |
| 2 | One JSON document a day rather than CSV rows | Two runs of one day land on one path and a JSON document merges whole. The day tree exists because a row is settled a line at a time by a machine that has never read the file | Nothing. The cost is a rebase git cannot apply on any day two runs both wrote | Fowler |
| 3 | `<DD>.json`, one file a day | It is the scheme the one-writer rule replaced: a second attempt at one job writes the path the first attempt took | Nothing. The cost is a lost push race costing the rows instead of a merge | Owner ruling |
| 4 | An operator verb that takes the reading on demand | Retention deletes the published day, so the window is gone and the reading cannot be recomputed | Nothing to take. The cost is that every day nobody runs the verb is a day with no reading, permanently | Owner ruling |
| 5 | A workflow of its own | The pipeline already loads this encoder in this job | A second job, a second checkout, a second encoder load, and a second push racing the first | Carmack |
| 6 | Publish the reading under `frontend/public/` so a page can fetch it | Nothing draws it (A2), and a published payload nobody reads is bytes against the 1 GB cap plus a contract to keep for ever | A published-payload contract and the console row. A2 names what would bring it in | Jony |

## See also

- [../docs/architecture/publishing/autotune-search-quality.md](../docs/architecture/publishing/autotune-search-quality.md) - the research this plan implements, and the open questions it does not.
- [../docs/architecture/publishing/autotune-content-similarity.md](../docs/architecture/publishing/autotune-content-similarity.md) - the working precedent: a judged line that fits itself nightly.
- [../docs/concepts/search-quality.md](../docs/concepts/search-quality.md) - the measured baseline, the bar, and why the number is a lower bound.
- [../docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the contract the stamp at the top points at.
