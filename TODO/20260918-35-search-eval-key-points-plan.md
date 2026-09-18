# Search, key_points, and the eval console - execution plan

**Last Updated**: 2026-09-18
**Level**: mixed, up to 5 (published `DigestItem`/`DigestViewItem`; `EvalRow` ledger; summariser decode shape)

**Status: decisions resolved; ready to size once the two ESCALATE rows are acknowledged.** The owner
resolved all four K-items and the five flags on 2026-09-18 (sections 0b, 0c), overruling advisors
where noted; the 2026-09-18 convergence debate (Andre, Carmack, Fowler) settled the eval design. The
auto-tuning feedback loop is split OUT to a separate plan (#36, section 0d) per Fowler; this plan
does the cleanup, the search, the chart, and the recorded-only scorers.

**Execution stamp** (per [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)):

```
Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.
```

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Raise the read cap, fully retire `key_points` and the deterministic metrics built on it, give the live page instant + semantic search, redesign and re-label the faithfulness chart, and add recorded-only coherence + coverage scorers reusing models already loaded. |
| Hard scope - in | `extract.truncation_cap_tokens`; `key_points` (published + internal decode + corpus); live-day search (instant + semantic); `lead_coverage`, `new_fact_rate`, `key_point_weight`; the faithfulness console chart + metric naming + a docs glyph-link; coherence + coverage scorers (recorded-only). |
| Hard scope - out | the auto-tune loop, adaptive bands, publish gate and G-Eval council (all -> plan #36); UniEval (a new runtime beside llama.cpp); RAGAS retriever metrics (no retriever here); see table below |
| ESCALATE triggers | (1) F1 - Row 4 removes internal `Summary.key_points`, retiring the facts-first decode and reshaping the corpus. (2) F2 - Row 6 removes `key_point_weight`, a committed field on plan #34's `StorySimilarityDistribution`. (3) any `EvalRow`/published-payload field removal (Level 5, section 11). |
| Chosen strategy | Cleanup + search + recorded-only scorers here; the closed loop (fold/fit/gate/G-Eval) is plan #36, after #34, reusing its `Fit` and `LLM-JUDGES` workflow. Owner + convergence debate, 2026-09-18. |
| Execution | Parallel N = 4 default; the running-pool orchestration + 5-PR wave grouping is section 0e. Stamp above; AUTHOR-AND-STOP until the user authorizes. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Auto-tune bands, publish gate, G-Eval council | This plan measures but does not yet act; no item is withheld yet | Plan #36, after #34 lands |
| UniEval (T5-base ~220 MB) | No multi-dimension learned judge | The cheap proxies + G-Eval failing to separate good from bad; and a GGUF/llama.cpp path (it is an encoder-decoder, not a drop-in) |
| RAGAS Context Precision / Recall / Answer Relevance | No retriever/QA labels on the chart | A retriever or a query, neither of which a summariser has |
| Replacing HHEM | Nothing - HHEM stays the faithfulness owner | A measured HHEM failure |

### Section 0b - resolved decisions (owner, 2026-09-18)

| # | Decision | Ruling | Advisor overruled |
| --- | --- | --- | --- |
| K0 | `truncation_cap_tokens` | 20000 -> 30000. Fits: model `n_ctx` is 65536, so 30000 + prompt + output leaves >50% headroom (Carmack). | - |
| K1 | `key_points` | FULL removal - published, internal decode, corpus. Served only search; production tags entities from title+body, and key points derive from the body, so they add nothing there. | Fowler |
| K2 | Live-day search | BUILD BOTH - instant substring + semantic (reuse month vectors + 43 MB encoder). | Fowler + Carmack |
| K3 | `lead_coverage` | REMOVE - many articles/blogs start slow, so lead survival is not a quality signal. | Andre |
| K4 | `new_fact_rate` + `key_point_weight` | REMOVE both. | Andre + Fowler |
| K5 | Chart metric names | SummEval labels: `Faithfulness` (HHEM), `Coverage` (ROUGE-recall), `Coherence` (MiniLM), `Fluency` (G-Eval, plan #36). RAGAS terms do not fit (no retriever, no query); say so on the chart. | - |

### Section 0c - flags, now resolved

| # | Flag | Resolution (owner + debate, 2026-09-18) |
| --- | --- | --- |
| F1 | Facts-first decode retires | CONFIRMED full removal. At ~4 tok/s decode, dropping the `key_points` decode saves ~21 s/item typical (up to ~140 s), ~1.75 h off a 300-item day (Carmack) - a real throughput win, not just bytes. Corpus row becomes `[title, summary]` (re-harvest). |
| F2 | Plans #29/#34 lose the key-point signal | CONFIRMED. Do NOT modify #29/#34 beyond a one-line comment that `key_points` and `key_point_weight` are gone. Row 6 also retires the committed `key_point_weight` field on #34's `StorySimilarityDistribution` (a cross-plan contract PR, sequenced after #34 lands). |
| F3 | "Needs human labels" | WITHDRAWN. No human labelling. Bands are a percentile of each metric's own rolling distribution, folded and fitted daily like plan #34's line (block p01, watch p05, damped, gated), self-correcting on sane defaults. This is plan #36. |
| F4 | G-Eval placement | Council-only, next-day, judging FLUENCY only, on a stratified sample of ~30 summaries/day. Not per-item, not in the digest job. Plan #36. |
| F5 | Read cap vs context window | Fits (n_ctx 65536). Row 1 pins the cap check to the model's `n_ctx` rather than a bare literal, so a future 32 k model swap fails loudly. |

### Section 0d - what moves to plan #36 (the auto-tune loop)

Fowler's ruling: the closed loop is one coherent Level-5 surface and gets its own plan, after #34,
reusing #34's `Fit` core (extracted, direction-parameterised) and the `LLM-JUDGES` workflow. Design of
record: [`docs/concepts/summary-quality-autotune.md`](../docs/concepts/summary-quality-autotune.md).
Plan #36 rows: the fixed-size `MetricScoreDistribution`, the `FittedMetricBand` (block/watch floors),
the publish gate (`publish_decision` on the item, flag off, record-only first), and the G-Eval fluency
council. Cheapest loop that closes first: `hhem` -> one distribution -> one band -> gate; coherence,
coverage and G-Eval are data-parameterised additions via a `metric` field.

### Section 0e - round-2 review corrections (Fowler + Carmack, 2026-09-18)

Two custom agents reviewed this plan against the tree. Every coupling below was verified with
`git grep`, not read off the plan text. The plan's strategy held; the row file-lists undercounted the
landed surface, and the eval work serializes on two shared files. The corrections bind the rows.

**Table A - correctness + coverage corrections (each names the row it fixes)**

| id | Correction | Why it bites |
| --- | --- | --- |
| C1 | **`output_digest` depends on `key_points` (Level-5 landmine).** `derive_output_digest(summary, key_points, title)` at [base.py:532](../backend/idhazh/contracts/base.py) / [summary.py:204](../backend/idhazh/contracts/summary.py). Row 4 must decouple the digest input from the retired decode field - derive the digest text from the body at digest time, or pin it to `[summary, title]` and ship a read-side migration. | Removing `key_points` from the formula makes every committed `Summary` fail its `output_digest` recompute on read - a contract break, release blocker (section 11). |
| C2 | **Row 4 undercounts the retire surface.** It must ALSO touch: frontend `payload/project.ts` ITEM_FIELDS + `payload/types.ts` (or the drift gate fails); the 12 browser specs naming `key_points` + a browser smoke; the decode knobs `key_points_min/max` in `knobs/summarize.py` + `config/idhazh.json` + `app-config.schema.json`; the 3 prompt files (`summarize.txt`, `summarize_and_plan_visual.txt`, `write_about_the_item.txt`) + their committed classify fixtures + the pipeline fingerprint move; `stages/common.py`, `stages/work.py`, `telemetry/spans.py`. The frontend `key_points` ownership is Row 4's, not Row 5's. | As written Row 4 fails its own contract-drift gate and leaves orphaned frontend/prompt/decode surface. |
| C3 | **Row 6 undercounts the `key_point_weight` coupling.** Beyond stamps.py/placement.py/fold.py/`without_retired_keys` (already named), ALSO the landed #34 stages [judge_draw.py:73](../backend/idhazh/stages/judge_draw.py) and [judge_fit.py:190](../backend/idhazh/stages/judge_fit.py) (both read it), `evals/archive.py`, the `new_fact_rate` name in `day_metrics.py`, and 6 similarity test modules. **D5:** `assemble.py` and `judge_fit.py` recompute `cosine*cw + key_point*kpw` and must drop the second term in lockstep or crash. Browser smoke for the removed panel. | Runtime `AttributeError` on landed #34 code; the weight-sum validator rewrite (decision 2) is incomplete without the recompute sites. |
| C4 | **Row 7 undercounts the `lead_coverage` coupling.** Beyond corpus.py/qualify.py/`scorer_version` (already named), ALSO `day_metrics.py` (`lead_missing` field + the sum validator -> a `day-metrics.schema.json` change if the bucket goes), `qualification.py` (`lead_coverage` field), `stages/assemble.py` and `stages/qualify.py` (both pass `lead_coverage=`), `telemetry/publish/day_metrics.py`. Browser smoke for the removed panel. | Payload-parse failure on committed day-metrics; orphaned writers. |
| C5 | **Row 1 (cap) coupling.** The cap is a `PipelineInputs` field ([fingerprint.py](../backend/idhazh/contracts/fingerprint.py)) - 20000->30000 **moves `pipeline_fingerprint`** (name the move + the re-harvest it implies). Reuse the existing `n_ctx` fit check at [classify/dag.py:241](../backend/idhazh/classify/dag.py), do not write a second. Band word-counts derive from the cap ([knobs/summarize.py:156](../backend/idhazh/contracts/knobs/summarize.py)) - confirm they still hold. VERIFY the committed `models.summarize.inference.n_ctx` is 65536 before asserting it (F5 pin). | An unstated fingerprint move silently re-runs the whole day; an unverified `n_ctx` makes the F5 pin a guess. |
| C6 | **The `EvalRow` CSV needs a header-migration, not the JSON popper.** `without_retired_keys` is a Pydantic `mode=before` JSON hook - right for the 3 committed #34 JSON payloads, but the `EvalRow` removals drop CSV **columns** from committed day-shards, which needs a tolerant read / DROPPED-cell path. Name it in the eval-core PR. | A width change read back under `extra=forbid` fails the shard parse. |
| C7 | **Browser smokes missing.** Rows 3, 6, 7, 8 each change a published console surface and name no browser smoke (section 12). The eval-core PR carries one smoke for the two removed + two added panels; the chart PR carries Row 3's. | Section-12 gate cannot be satisfied without them. |

**Table B - orchestration corrections (the worker-pool shape)**

| id | Correction | Ruling |
| --- | --- | --- |
| C8 | **Collapse the `EvalRow` churn into one PR.** Rows 6, 7, 8 all mutate `eval_row.py` (column add/remove), its changelog (at the 5-entry cap -> head+tail edits), `score.py` `to_eval_row`, `metrics.py` `METRICS_VERSION`, and `eval-instruments.ts` + the model page. They cannot parallelise. Ship them as ONE eval-core PR: one changelog entry, one `version` bump, one schema regen, one ledger-width change. | Both advisors. Turns a 3-hop backend chain into 1. Cost: the PR is Level-5 and inherits F2 ack + #34; harder to revert one metric. No wall-clock cost - the path is already #34-gated via Row 6. |
| C9 | **`state/**/*.csv` is `merge=union` - a silent-stack hazard.** Two branches that change the `EvalRow` width union into mixed-width rows with NO conflict raised. Hard carve-out: any row changing the ledger width waits for its predecessor on `main`, never branch-stacked. This is the second reason eval-core is one PR, not three stacked branches. | Carmack (verified in .gitattributes). |
| C10 | **Optimistic-dispatch rule (kills CI-idle).** A slot frees when the worker RETURNS its report, not when the PR merges. Disjoint rows (search vs all; cap vs all but eval-core's config edit) dispatch off `main` at once. A shared-file successor whose predecessor's SHAPE is settled dispatches off the predecessor's BRANCH tip pre-merge. A successor gated by ESCALATE / Level-5 / an owner ack, or cross-plan un-landed (#34), waits on `main`. The one test: can the predecessor's shape still change after the worker returns? No -> optimistic; yes -> pessimistic. | Carmack + execute-a-plan.md. Only Rows 4 and 6 ever legitimately idle on a merge, and both are ack-gated anyway. |

## Section 1 - Status Reckoner

The round-2 review regroups the eight rows into **five PRs across two waves**. A row's `Parallel-group`
names its PR; rows sharing a PR ship together. Readiness is computed from `Depends-on` + a `Files
touched` disjointness check, never the letter (execute-a-plan.md).

**PR grouping**

| PR | Wave | Rows | Ships as | Gate it inherits |
| --- | --- | --- | --- | --- |
| cap | A | 1 | one PR | - (independent) |
| search | A | 5 | one PR | - (independent frontend island) |
| eval-core | A | 6, 7, 8 | ONE PR (C8) | Level-5 + F2 ack + #34 landed |
| chart | B | 2, 3 | one PR, after eval-core | eval-instruments serialization (C10) |
| retire-key-points | B | 4 | one PR, after search + eval-core | F1 ack; Level-5 (output_digest, C1) |

**Dispatch order** (Carmack): dispatch **search (Row 5) first** - the longest single row and the only
file-independent island - then cap, then eval-core. Peak pool width is **3** (search + cap + one eval
row) in the opening window, sustained **2**, collapsing to **1** on the serial spine
`eval-core -> chart -> retire-key-points`. Provision 2 workers, allow 3; a 4th idles. A row that MEASURES
(Row 1 prefill note, Row 8 runner-cost note) runs alone.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Raise `truncation_cap_tokens` to 30000, pin to `n_ctx` (+ fingerprint move, C5) | - | A / cap | PENDING | - | - | - |
| 5 | Live-day search - instant + semantic (+ frontend `key_points` owner, C2) | - | A / search | PENDING | - | - | - |
| 6 | Remove `new_fact_rate` + `key_point_weight` (+#34 field, judge stages, C3) | #34 | A / eval-core | PENDING (F2 ack) | - | - | - |
| 7 | Remove `lead_coverage` (+ day-metrics bucket + qualification, C4) | - | A / eval-core | PENDING | - | - | - |
| 8 | Add coherence + coverage scorers (recorded-only) | - | A / eval-core | PENDING | - | - | - |
| 2 | Redesign + re-label the faithfulness chart; docs glyph-link | 8 | B / chart | PENDING | - | - | - |
| 3 | Reword recorded-only copy; relabel `compression` | 8 | B / chart | PENDING | - | - | - |
| 4 | Retire `key_points` (published + internal + corpus + `output_digest`, C1/C2) | 5, 6, 7 | B / retire | PENDING (F1 ack) | - | - | - |

## Section 2 - Row detail

### Row #1 - Raise `truncation_cap_tokens` to 30000, pinned to `n_ctx`

- **Scope:** the read cap rises 20000 -> 30000, with a build-time assertion that it fits the model's
  `n_ctx` minus the prompt and output budget.
- **Files touched:** `config/idhazh.json`; the extract or config validator that reads the cap.
- **Acceptance gates:** config schema validates; an assertion fails if `truncation_cap_tokens + system
  + max_output` exceeds `n_ctx`. Record a prefill-time note on a long fixture (Carmack: real feeds
  never reach 15000 words, so the practical delta is ~zero).
- **Oracle:** a test shows a 30000-token body passes uncut and the fit assertion catches a cap set
  past `n_ctx`; it cannot settle runtime cost on a pathological input (the request timeout backstops it).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | 30000, pinned to `n_ctx` not a bare literal | owner (K0), Carmack (F5) |

### Row #2 - Redesign + re-label the faithfulness chart; docs glyph-link

- **Scope:** rework the "How closely a summary matched its article" panel - plain copy, adaptive
  y-axis, the real 0.80/0.50 reference lines, horizontal legend, a tooltip with both percents + count,
  the SummEval metric name, and a tiny glyph linking to the metrics doc.
- **Files touched:** `frontend/src/routes/console/model/+page.svelte`,
  `frontend/src/lib/console/eval-instruments.ts`, `frontend/src/lib/charts/*` (TBD on read),
  `frontend/src/routes/console/model/+page.server.ts`, the browser oracle spec.
- **Acceptance gates:** frontend `test:changed`; browser smoke - reference lines draw, tooltip shows
  both percents + count, the glyph links to the doc, no console errors.
- **Oracle:** the browser oracle re-derives the drawn median and lower-quartile per day; it cannot
  settle whether it reads better (Susan's sufficiency check).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Title "Summary faithfulness, day by day"; intro names HHEM/Faithfulness; "higher is better" | Susan, Andre (K5) |
  | 2 | Two lines = day median + day lower-quartile of the HHEM score, relabelled plainly | Susan |
  | 3 | Adaptive y-axis floor = clamp(round_down_5(min-5), 50, 75); ceiling fixed 100 | Susan |
  | 4 | Draw the real 0.80 reference + tint, 0.50 edge caption; drop the "guess wearing a measurement's clothes" copy | Susan, Andre |
  | 5 | Horizontal legend; tooltip shows both percents + that day's count | Susan |
  | 6 | A tiny glyph in the panel links to `docs/concepts/summary-quality-autotune.md` for the metric definitions | Susan |

### Row #3 - Reword recorded-only copy; relabel `compression`

- **Scope:** replace "A day here is that day's middle summary"; relabel `compression` as a length
  covariate.
- **Files touched:** `frontend/src/routes/console/model/+page.svelte`,
  `frontend/src/lib/console/eval-instruments.ts`, `docs/concepts/evaluation.md`.
- **Acceptance gates:** frontend `test:changed`; doc load check.
- **Oracle:** the instrument spec reads the new note; it cannot settle readability (Susan).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | "Each dot is one day's middle score: half of that day's summaries scored higher, half lower." | Susan |
  | 2 | Keep `compression`, relabel as a length covariate | Andre |

### Row #4 - Retire `key_points` (published + internal + corpus) - ESCALATE F1

- **Scope:** `key_points` leaves the published payload, the summariser decode shape, and the corpus
  row. Decode stops producing it (facts-first retires); corpus row becomes `[title, summary]`.
- **Files touched:** `backend/idhazh/contracts/digest_day.py`, `digest_view.py`, `summary.py`
  (+ regen schemas, version + changelog + read-side tolerance), `backend/idhazh/summarize.py`
  (`SummaryDraft`, prompt), `backend/idhazh/classify/calls.py`, `backend/idhazh/corpus.py`,
  `backend/tests/test_corpus_contract.py`, `docs/how-to/fine-tune-a-model.md`,
  `backend/utilities/build_canary_day.py`, `backend/utilities/data_wrangler.py`,
  `backend/utilities/entity_gap.py`.
- **Acceptance gates:** contract drift gate; backend `test:changed` over corpus/summarize/contract;
  a fixture-driven read of an old `digest.json` that still carries `key_points` (tolerated, not
  required). Easy path per owner: make the field optional, stop writing, tolerate old - no historical
  delete-migration.
- **Oracle:** a contract test proves a payload without `key_points` validates and one with it still
  reads; it cannot settle whether summary quality moved without the facts-first scaffold (unmeasured).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Full removal; optional-then-stop-writing; tolerate old | owner (K1, F1) |
  | 2 | Decode stops producing key points | owner (F1); Carmack confirms the decode saving is real |

### Row #5 - Live-day search: instant + semantic

- **Scope:** one search field, two tiers - instant substring narrowing on keystroke (title+summary,
  no `key_points`), and semantic search on Enter reusing the archive's 43 MB encoder and per-month
  vectors, returning cross-day related stories.
- **Files touched:** `frontend/src/lib/components/DigestList.svelte`, a semantic control mirroring
  `frontend/src/lib/components/ArchiveSearch.svelte`, `frontend/src/lib/day-shape.ts`,
  `frontend/src/lib/assist/day.ts`, the day-page loader (fetch the month `.bin`),
  `frontend/src/lib/assist/search.ts`, the affected tests.
- **Acceptance gates:** frontend `test:changed`; browser smoke - instant narrows with no request;
  semantic loads with a byte-counted progress state, returns cross-day results, degrades to the intact
  day list when the model/vectors are absent (section 12).
- **Oracle:** a spec proves instant narrowing matches title+summary only and semantic returns the
  expected ranked ids; it cannot settle whether the common instant path now feels heavier (Susan).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One field, two tiers; instant on keystroke, semantic on Enter; caption is the mode tell | Susan |
  | 2 | 0 ms debounce on the narrow, 120 ms on the count/hint; min 2 chars; `<mark>` by node-slicing, never `{@html}` (Guardrail #11) | Susan |
  | 3 | 43 MB load is a byte-counted phase machine reused from ArchiveSearch; field stays live while it warms | Susan, Carmack |
  | 4 | Early-month empty state nudges to the archive | Susan |

  Biggest risk (Susan): the common "filter today" path must stay instant and download-free; semantic is
  additive, never a gate on the reading route.

### Row #6 - Remove `new_fact_rate` + `key_point_weight` - ESCALATE F2

- **Scope:** drop `new_fact_rate` (metric + `EvalRow` column + console panel) and `key_point_weight`
  (the `assemble.py` term, the config knob, and the committed field on plan #34's
  `StorySimilarityDistribution` and fitted-threshold row). `key_point_weight` is threaded through more
  of plan #34's LANDED code than F2 first named (found by the 2026-09-18 plan-34 critical review), so
  the coupling below is load-bearing.
- **Files touched:** `backend/idhazh/evals/metrics.py`, `backend/idhazh/evals/score.py`,
  `backend/idhazh/contracts/eval_row.py` (+ schema + changelog), `backend/idhazh/assemble.py`,
  `config/idhazh.json`, `backend/idhazh/contracts/story_similarity_pair.py` and the distribution/
  fitted contracts (retire `key_point_weight`),
  `backend/idhazh/contracts/knobs/placement.py` (the `key_point_weight` field AND the
  `_the_weights_sum_to_one` validator that sums it),
  `backend/idhazh/similarity/stamps.py` (`ScorerStamp.key_point_weight` and the
  `same_story.key_point_weight` read),
  `backend/idhazh/similarity/fold.py` (the `inputs_changed`/`empty_record` term comparing
  `record.key_point_weight`),
  `frontend/src/lib/console/eval-instruments.ts` + the model page, the affected tests; one-line
  comments in `TODO/20260914-29-found-once-plan.md` and `TODO/20260917-34-similarity-autotune-plan.md`
  (no other edits, F2).
- **Acceptance gates:** contract drift gate; backend + frontend `test:changed`. **Three committed
  plan #34 payloads carry the field under `extra="forbid"`** - `state/story-similarity/score-distribution.json`
  (read on every fold), the seed `fitted-thresholds` CSV and the seed `scored-pairs` CSV - so each
  shrunk contract opts into `without_retired_keys(data, "key_point_weight")` (a `mode="before"` popper,
  `backend/idhazh/contracts/base.py`) in the SAME commit, or the first post-removal fold fails to parse
  them (CLAUDE.md section 11). Prove the migration with a fixture that omits the key. Sequenced AFTER
  #34 fully lands (cross-plan field).
- **Oracle:** a contract test proves the shrunk rows validate, an old payload carrying
  `key_point_weight` still reads through the popper, and the fold parses the committed record; it
  cannot settle the #29/#34 cosine-only impact (owner-accepted, F2).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Remove both; #29/#34 continue cosine-only, comment-only | owner (K4, F2) |
  | 2 | With `key_point_weight` gone, cosine is the only same-story weight, so `_the_weights_sum_to_one` (`placement.py`) trivially holds and pins `cosine_weight` at 1.0; rewrite it to assert `cosine_weight == 1.0` rather than reference the removed field | owner, Fowler |
  | 3 | Decide whether the `key_point` VALUE column also leaves `StorySimilarityPair` (its composite validator recomputes `cosine*cosine_weight + key_point*key_point_weight`); if the value stays, the validator drops only the `key_point*key_point_weight` term | Fowler |

### Row #7 - Remove `lead_coverage`

- **Scope:** drop `lead_coverage` as a banding input, an `EvalRow` column, a corpus counterweight, a
  qualification gate input and a console panel. Like Row 6, `lead_coverage_min` is threaded through
  more landed code than first named (found by the 2026-09-18 review).
- **Files touched:** `backend/idhazh/evals/metrics.py` (`lead_coverage`, `lead`, AND the `;lead=<min>`
  component of the `scorer_version` string at ~line 548), `backend/idhazh/evals/score.py` (`verdict`
  LEAD_MISSING), `backend/idhazh/contracts/eval_row.py` + `knobs/evaluation.py` (`lead_coverage_min`),
  `backend/idhazh/corpus.py` (`keeps_its_counterweights` reads `row.coverage >= lead_coverage_min` -
  the corpus rejection filter), `backend/idhazh/evals/qualify.py` (`thin_lead` and the
  `below_lead_coverage_min_share` gate), `docs/how-to/fine-tune-a-model.md`,
  `frontend/src/lib/console/eval-instruments.ts` + the model page + `frontend/src/lib/bands.ts`,
  the affected tests.
- **Acceptance gates:** contract drift gate; backend + frontend `test:changed`; a fixture read of an
  old shard carrying `coverage` and an item carrying `band_reason=lead_missing` (tolerated). **The
  `scorer_version` string changes** (it drops `;lead=<min>`), which restarts the run-day band gate and
  is exactly why plan #36's faithfulness seed must key on the HHEM instrument sub-identity, not the
  whole `scorer_version` - flag it to #36.
- **Oracle:** a `verdict` test proves a lead-dropping summary is no longer downgraded and
  `keeps_its_counterweights` no longer references coverage; it cannot settle the coverage gap until
  Row 8 lands.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Remove; coverage re-owned by Row 8 (ROUGE-recall), recorded-only | owner (K3) over Andre |
  | 2 | `keeps_its_counterweights` DROPS the coverage criterion rather than switching to `semantic_coverage` - Row 8's coverage is recorded-only and unproven, and the corpus keeps only its copy-proof counterweights (`hedge_dropped`, `unsupported_numbers`, `extractiveness`, `compression`, `determinism_violation`) | Andre |
  | 3 | Dropping `;lead=` from `scorer_version` restarts the run-day gate; #36's seed keys on HHEM instrument identity so it survives (cross-ref #36 Row 5) | Andre |

### Row #8 - Add coherence + coverage scorers (recorded-only)

- **Scope:** add coherence (MiniLM mean adjacent-sentence cosine, summary-only) and coverage
  (ROUGE-recall, needs the source) to the eval row and the console, recorded-only, no band. Both run
  same-day in the digest job (coverage needs the source).
- **Files touched:** new `backend/idhazh/evals/embedding_metrics.py`, `backend/idhazh/evals/score.py`
  (`to_eval_row`), `backend/idhazh/contracts/eval_row.py` (add `coherence`, `semantic_coverage` -
  NOT `coverage`, a shifted meaning - nullable, + schema + changelog + `METRICS_VERSION` bump),
  `frontend/src/lib/console/eval-instruments.ts` + the model page (two recorded-only panels).
- **Acceptance gates:** unit tests reproduce a hand-worked cosine and ROUGE-recall on a fixture;
  contract drift gate; a runner-cost note (MiniLM already loaded, ~0.16 s/item).
- **Oracle:** the scorers reproduce a fixture's hand-computed values; human correlation is out of
  scope here - the loop that acts on these numbers is plan #36.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Coherence = mean adjacent-sentence cosine, raw [-1,1], null for one sentence; monitor only | Andre |
  | 2 | Coverage = ROUGE-recall [0,1], new column `semantic_coverage` | Andre, Fowler (name collision guard) |
  | 3 | Recorded-only; no band, no gate (that is plan #36) | Andre, Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | UniEval T5-base | New encoder-decoder runtime beside llama.cpp + a GGUF path; a prior not measured here | Only if the cheap proxies + G-Eval fail to separate good from bad | Andre, Carmack |
  | 2 | Reuse the column name `coverage` | Shifted meaning vs the removed lead-coverage; old shards sit on a different scale | - | Fowler |

## Section 3 - Answered by investigation (no row needed)

| Question | Answer (2026-09-18) |
| --- | --- |
| Search: two tiers, and is instant powered by key_points? | Instant = plain-text substring over title + summary only, on keystroke, no download. NO key_points. Semantic = vectors on Enter, 43 MB encoder. |
| G-Eval input? | The summary ONLY (fluency is summary-only), which is what lets it run next-day when the article is gone. |
| Can UniEval run on the runner? | Not as a drop-in - it is a T5 encoder-decoder needing a GGUF/llama.cpp path or a second runtime; we are not using it (reuse the summariser for G-Eval). |
| Where do metrics run? | HHEM + coverage + coherence same-day in the digest job (coverage needs the source; article bodies are gone next-day). G-Eval fluency next-day in the council, sampled. |
| Feedback-loop contracts? | Extend `EvalRow`; new fixed-size `MetricScoreDistribution` + per-day `FittedMetricBand` (mirror #34's `Fit`); a `publish_decision` stamp on the item. All in plan #36. |
| Model context fit for 30000? | `n_ctx` 65536 - fits with >50% headroom. |
| Decode saving from dropping key_points? | Real at 4 tok/s: ~21 s/item typical, ~1.75 h off a 300-item day. |
