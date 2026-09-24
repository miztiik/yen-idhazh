# Search, key_points, and the eval console - execution plan

**Last Updated**: 2026-09-18
**Level**: mixed, up to 5 (published `DigestItem`/`DigestViewItem`; `EvalRow` ledger; summariser decode shape)

**Status: decisions resolved; execution authorized (owner, 2026-09-19).** The owner
resolved all four K-items and the five flags on 2026-09-18 (sections 0b, 0c), overruling advisors
where noted; the 2026-09-18 convergence debate (Andre, Carmack, Fowler) settled the eval design; and on
2026-09-19 the owner confirmed the complete `key_points` removal (0e C1) and authorized execution. The
autotuning feedback loop is split OUT to a separate plan (#36, section 0d) per Fowler; this plan
does the cleanup, the search, the chart, and the recorded-only scorers.

**Execution stamp** (per [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)):

```
Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.
```

## Execution handover (zero-context cold start)

Paste-ready brief for an agent that picks this plan up with zero prior context. It restates the
execution stamp above in operating detail; [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)
is the canonical contract, and the Onboarding subsection below lists the page that owns each surface a
row touches.

```text
You are the OWNER of this plan-doc (TODO/20260918-35-search-eval-key-points-plan.md).
You have zero prior context. Execute it end to end: keep four rows in flight, auto-merge on
green, never idle on CI, and pause only at the ESCALATE points below. Execution is
AUTHORIZED (owner, 2026-09-19); the plan is runnable now.

STEP 0 - COLD START. Read, in order: CLAUDE.md; docs/how-to/execute-a-plan.md (you are
"the owner" in it); docs/agents/bootstrap.md; docs/how-to/run-the-gates.md;
docs/how-to/ship-a-pr.md; then this plan's Section 0, its Onboarding subsection, Section 0e
(orchestration corrections C8-C10), and Section 1 (the Status Reckoner). Section 2 is the
per-row detail. Read the owning page for each surface a row touches (the Onboarding
subsection lists them).

STEP 1 - ADOPT OR CLOSE FIRST. Before dispatching: git worktree list, list branches,
gh pr list. Reconcile any half-done row against the Status Reckoner - adopt it or remove it
- before starting new work. Do not switch or edit the shared checkout; sibling agents may be
on other branches there. Work only in dedicated worktrees under the repo's sibling
.worktrees/ directory.

STEP 2 - RUN THE POOL. Parallel N = 4, running pool, not a wave. A slot is filled while a
worker WRITES a row and frees the moment the worker RETURNS its report - never when the PR
merges (Section 0e C10, optimistic dispatch). For each delegated or parallel row: an
isolated worktree off origin/main and a named branch, never shared. Brief the worker with
the row verbatim (Scope, Files touched, Acceptance gates, Oracle, Decisions, Rejected
alternatives) plus: read the owning page, honor CLAUDE.md, stay in scope, consult personas
only on genuine ambiguity, run the Oracle + the gate guide's selected local checks (leave
the full suite to CI), update only its own Reckoner line, return a structured report. The
worker does NOT merge and does NOT start another row. Before dispatch, run the two
pre-dispatch checks: every symbol/path the row names exists in the tree, and the row's check
can fail for the reason the row exists.

STEP 3 - DISPATCH ORDER (Section 1). Eight rows, five PRs:
  DISPATCH search (Row 5) FIRST - the longest row and the only file-independent island -
  THEN cap (Row 1). Both start at once off origin/main.
    search             Row 5       independent now         AUTO-merge on green
    cap                Row 1       independent now         AUTO-merge on green
    eval-core          Rows 6,7,8  Level-5 + F2 + #34       PAUSE (STEP 5)
    chart              Rows 2,3    after eval-core Row 8    AUTO-merge on green
    retire-key-points  Row 4       after search+eval-core   PAUSE (STEP 5)
  Readiness is computed: a row is ready when every Depends-on is DONE and it shares no
  Files-touched entry with a row in flight. chart and retire depend on eval-core's Row 8.
  A MEASURING row (Row 1 prefill note, Row 8 runner-cost note) runs ALONE.

STEP 4 - MERGE + REFILL. When a worker returns, dispatch the next ready row NOW; then verify
that row's CI + test records against the Definition of Done (CLAUDE.md section 9) and
ship-a-pr.md. On green: remove the row's worktree, THEN
gh pr merge <N> --squash --delete-branch. Merging is serialized but never blocks the pool; a
red or conflicting merge returns that row to you and the pool keeps running.

STEP 5 - ESCALATE (PAUSE that row, not the pool; default is AUTO). Surface with the
five-part decision shape (CLAUDE.md 0c) for:
  - F1: Row 4 removes internal Summary.key_points (retires the facts-first decode, reshapes
    the corpus) - Level 5.
  - F2: Row 6 removes key_point_weight, a committed field on plan #34's
    StorySimilarityDistribution - Level 5, cross-plan.
  - Any EvalRow / published-payload field removal (eval-core is exactly this) - Level 5.
  So search, cap and chart auto-merge; eval-core and retire-key-points pause for an owner ack.
  CROSS-PLAN GATE for eval-core: plan #34 is not fully closed (its plan-doc still exists).
  key_point_weight IS committed, but before dispatching Row 6 check #34's open rows + live
  worktrees for a file collision on the eval-core surface (story_similarity_distribution.py,
  story_similarity_pair.py, pick_item_pairs.py, set_merge_line.py, assemble.py, eval_row.py). And
  state/**/*.csv is merge=union: two branches that change the EvalRow width stack silently
  with NO conflict (C9) - never branch-stack an eval-row-width change; wait for main.

STEP 6 - PERSONAS resolve ambiguity; they are NOT an approval gate. Consult a persona custom
agent (exact CLAUDE.md section 14 name: Reader, Editor, Jony, Susan, Andre, Fowler, Carmack;
plus Explore for read-only breadth) ONLY when two defensible answers lead to DIFFERENT code
and the difference matters. A contested decision runs the relevant personas in DEBATE to one
ruling, baked into the code. Not for coverage, never as a gate.

STEP 7 - REPORT in plain English (CLAUDE.md 0b/0c): lead with what happened, lettered tables
with row-ids, no subsystem vocabulary forwarded, decisions as five-part requests.

CLOSURE. When every row is DONE/COLLAPSED: confirm the Reckoner is resolved, check nothing
durable lives only in this plan-doc (distill-a-plan.md says where leftovers go), delete the
plan-doc, then sweep the worktrees the plan created.

FIRST ACTION: STEP 1 (adopt-or-close), then dispatch search (Row 5) and cap (Row 1) into two
isolated worktrees off origin/main.
```

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Raise the read cap, fully retire `key_points` and the deterministic metrics built on it, give the live page instant + semantic search, redesign and re-label the faithfulness chart, and add recorded-only coherence + coverage scorers reusing models already loaded. |
| Hard scope - in | `extract.truncation_cap_tokens`; `key_points` (published + internal decode + corpus); live-day search (instant + semantic); `lead_coverage`, `new_fact_rate`, `key_point_weight`; the faithfulness console chart + metric naming + a docs glyph-link; coherence + coverage scorers (recorded-only). |
| Hard scope - out | the autotune loop, adaptive bands, publish gate and G-Eval council (all -> plan #36); UniEval (a new runtime beside llama.cpp); RAGAS retriever metrics (no retriever here); see table below |
| ESCALATE triggers | (1) F1 - Row 4 removes internal `Summary.key_points`, retiring the facts-first decode and reshaping the corpus. (2) F2 - Row 6 removes `key_point_weight`, a committed field on plan #34's `StorySimilarityDistribution`. (3) any `EvalRow`/published-payload field removal (Level 5, section 11). |
| Chosen strategy | Cleanup + search + recorded-only scorers here; the closed loop (fold/fit/gate/G-Eval) is plan #36, after #34, reusing its `Fit` and `LLM-JUDGES` workflow. Owner + convergence debate, 2026-09-18. |
| Execution | AUTHORIZED (owner, 2026-09-19); ready to run. Parallel N = 4 default; the running-pool orchestration + 5-PR wave grouping is section 0e. |
| Intent | `key_points` is fully retired and the read cap raised: the summariser stops producing key points, the published day and the corpus row drop them, the `output_digest` formula and the deterministic metrics built on them go, and the live page gains instant + semantic search - with the faithfulness chart re-labelled and recorded-only coherence + coverage added. The contracts each row names FOLLOW this intent; when a contract and the intent disagree, the contract changes, not the intent (CLAUDE.md 0d). |

### Onboarding (cold start - read these first, zero context assumed)

A worker picks up any row with no prior context by reading, in order: [`CLAUDE.md`](../CLAUDE.md) (the
engineering contract), [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) (how this plan
runs), [`docs/agents/bootstrap.md`](../docs/agents/bootstrap.md) (which page owns the surface a row
touches), and [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) (the gate commands). The
owning pages per surface: contracts + schema versioning -> [`docs/architecture/contracts/schemas.md`](../docs/architecture/contracts/schemas.md);
the summariser decode + prompt -> [`docs/architecture/summarize/prompt.md`](../docs/architecture/summarize/prompt.md);
the corpus + fine-tune -> [`docs/how-to/fine-tune-a-model.md`](../docs/how-to/fine-tune-a-model.md);
evaluation + the console chart -> [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). Every
row's `Files touched` is the exact surface; every persisted change stamps its schema `version` +
`changelog` (CLAUDE.md section 11).

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Autotune bands, publish gate, G-Eval council | This plan measures but does not yet act; no item is withheld yet | Plan #36, after #34 lands |
| UniEval (T5-base ~220 MB) | No multi-dimension learned judge | The cheap proxies + G-Eval failing to separate good from bad; and a GGUF/llama.cpp path (it is an encoder-decoder, not a drop-in) |
| RAGAS Context Precision / Recall / Answer Relevance | No retriever/QA labels on the chart | A retriever or a query, neither of which a summariser has |
| Replacing HHEM | Nothing - HHEM stays the faithfulness owner | A measured HHEM failure |

### Section 0b - resolved decisions (owner, 2026-09-18)

| # | Decision | Ruling | Advisor overruled |
| --- | --- | --- | --- |
| K0 | `truncation_cap_tokens` | **20000 -> 26000 (owner, 2026-09-24, superseding the 30000 this row was written with).** The original sum sized ONE model call. Production sends two, and the second replays the first call's prompt and reply, so the window has to hold the pair. Searching `dag.sequence_tokens` at `elements.max_per_article` 256 puts the largest cap whose pair fits the committed 65,536 window at 26,511, where the margin is 1 token; 26,000 is committed for a real margin, and its pair is 64,699 with 837 spare. No context window moves. The raise buys headroom, not coverage: 20000 has never cut an article - the longest one on record is 11,525 words and 20000 already admitted 14,675. | the plan's own one-call arithmetic (K0, F5) |
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
| F5 | Read cap vs context window | **Restated 2026-09-24.** "Fits with >50% headroom" sized one call. The two-call pair at the committed 26000 cap sizes at 64,699 against an `n_ctx` of 65536, so the headroom is 837 tokens, not half a window. Row 1 pins the cap check to the model's `n_ctx` rather than a bare literal, so a future 32 k model swap fails loudly. |

### Section 0d - what moves to plan #36 (the autotune loop)

Fowler's ruling: the closed loop is one coherent Level-5 surface and gets its own plan, after #34,
reusing #34's `Fit` core (extracted, direction-parameterised) and the `LLM-JUDGES` workflow. Design of
record: [`docs/architecture/publishing/autotune-summary-quality.md`](../docs/architecture/publishing/autotune-summary-quality.md).
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
| C1 | **RESOLVED (owner, 2026-09-19): complete removal, accept the narrow break.** The `output_digest` formula drops `key_points` -> `derive_output_digest(summary, *, title)` ([base.py:531](../backend/idhazh/contracts/base.py)). The ONLY recompute-against-committed-data is `published_is_the_scored_one` ([corpus.py:266](../backend/idhazh/corpus.py)), the corpus join, which returns `False` (no crash) for a pre-change `EvalRow` whose digest was taken with `key_points`. Every other committed carrier (`EvalRow`, `LabelRow`, `QualificationRow`, published `DigestItem`/`DigestViewItem`, `observation_index`) STORES the digest and never recomputes it, so committed reads do not break. `Summary` self-validates the digest but is a run intermediate, consistent within a run. Migration = rewriting every committed eval-row digest via a join = complicated, so per the owner's rule we MOVE FORWARD AS A BREAKING CHANGE: the corpus re-harvest resets to post-change days (the prune bounds the corpus anyway). A test pins the new formula and that a `key_points`-era digest no longer false-matches. | The break is narrow and does not crash - it silently stops joining pre-change eval rows, which Row 4 makes explicit. |
| C2 | **Row 4 undercounts the retire surface.** It must ALSO touch: frontend `payload/project.ts` ITEM_FIELDS + `payload/types.ts` (or the drift gate fails); the 12 browser specs naming `key_points` + a browser smoke; the decode knobs `key_points_min/max` in `knobs/summarize.py` + `config/idhazh.json` + `app-config.schema.json`; the 3 prompt files (`summarize.txt`, `summarize_and_plan_visual.txt`, `write_about_the_item.txt`) + their committed classify fixtures + the pipeline fingerprint move; `stages/common.py`, `stages/work.py`, `telemetry/spans.py`. The frontend `key_points` ownership is Row 4's, not Row 5's. | As written Row 4 fails its own contract-drift gate and leaves orphaned frontend/prompt/decode surface. |
| C3 | **Row 6 undercounts the `key_point_weight` coupling.** Beyond stamps.py/placement.py/fold.py/`without_retired_keys` (already named), ALSO the landed #34 stages [pick_item_pairs.py:73](../backend/idhazh/stages/pick_item_pairs.py) and [set_merge_line.py:190](../backend/idhazh/stages/set_merge_line.py) (both read it), `evals/archive.py`, the `new_fact_rate` name in `day_metrics.py`, and 6 similarity test modules. **D5:** `assemble.py` and `set_merge_line.py` recompute `cosine*cw + key_point*kpw` and must drop the second term in lockstep or crash. Browser smoke for the removed panel. | Runtime `AttributeError` on landed #34 code; the weight-sum validator rewrite (decision 2) is incomplete without the recompute sites. |
| C4 | **Row 7 undercounts the `lead_coverage` coupling.** Beyond corpus.py/qualify.py/`scorer_version` (already named), ALSO `day_metrics.py` (`lead_missing` field + the sum validator -> a `day-metrics.schema.json` change if the bucket goes), `qualification.py` (`lead_coverage` field), `stages/assemble.py` and `stages/qualify.py` (both pass `lead_coverage=`), `telemetry/publish/day_metrics.py`. Browser smoke for the removed panel. | Payload-parse failure on committed day-metrics; orphaned writers. |
| C5 | **Row 1 (cap) coupling.** The cap is a `PipelineInputs` field ([fingerprint.py](../backend/idhazh/contracts/fingerprint.py)) - 20000->26000 **moves `pipeline_fingerprint`** (name the move + the re-harvest it implies). Reuse the existing `n_ctx` fit check at [classify/dag.py:241](../backend/idhazh/classify/dag.py), do not write a second. Band word-counts derive from the cap ([knobs/summarize.py:156](../backend/idhazh/contracts/knobs/summarize.py)) - confirm they still hold. VERIFY the committed `models.summarize.inference.n_ctx` is 65536 before asserting it (F5 pin). | An unstated fingerprint move silently re-runs the whole day; an unverified `n_ctx` makes the F5 pin a guess. |
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
| 1 | Raise `truncation_cap_tokens` to 26000, pin to `n_ctx` (+ fingerprint move, C5) | - | A / cap | DONE | - | 1092 | Carmack |
| 5 | Live-day search - instant + semantic (+ frontend `key_points` owner, C2) | - | A / search | DONE | - | 1094 | Susan |
| 6 | Remove `new_fact_rate` + `key_point_weight` (+#34 field, judge stages, C3) | #34 | A / eval-core | IN REVIEW | p35eval | - | Carmack, Andre |
| 7 | Remove `lead_coverage` (+ day-metrics bucket + qualification, C4) | - | A / eval-core | IN REVIEW | p35eval | - | Andre |
| 8 | Add coherence + coverage scorers (recorded-only) | - | A / eval-core | IN REVIEW | p35eval | - | Carmack, Andre |
| 2 | Redesign + re-label the faithfulness chart; docs glyph-link | 8 | B / chart | PENDING | - | - | - |
| 3 | Reword recorded-only copy; relabel `compression` | 8 | B / chart | PENDING | - | - | - |
| 4 | Retire `key_points` completely (published + internal + corpus + `output_digest`) | 5, 6, 7 | B / retire | PENDING | - | - | - |

## Section 2 - Row detail

### Row #1 - Raise `truncation_cap_tokens` to 26000, pinned to `n_ctx`

- **Scope:** the read cap rises 20000 -> 26000 (K0, owner 2026-09-24), with a build-time assertion that
  it fits the model's `n_ctx` minus the prompt and output budget. No `--ctx-size` moves.
  `finetune.sequence_length` rises 32768 -> 49152, because the training window sizes the single call
  and the worst single call at 26000 is 35,970 tokens; that window is GPU memory on a machine that is
  not the runner.
- **Files touched:** `config/idhazh.json`; the extract or config validator that reads the cap.
- **Acceptance gates:** config schema validates; an assertion fails if `truncation_cap_tokens + system
  + max_output` exceeds `n_ctx`. No wall-clock reading: 20000 has never cut an article, so a higher
  ceiling reads no extra word and there is no prefill delta to measure (Guardrail #10).
- **Oracle:** a test shows a 26000-token body passes uncut and the fit assertion catches a cap set
  past `n_ctx`; it cannot settle runtime cost on a pathological input (the request timeout backstops it).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | 26000, pinned to `n_ctx` not a bare literal | owner (K0, 2026-09-24) |

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
  | 6 | A tiny glyph in the panel links to `docs/architecture/publishing/autotune-summary-quality.md` for the metric definitions | Susan |

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

### Row #4 - Retire `key_points` completely (published + internal + corpus + `output_digest`) - Level 5

- **Intent:** `key_points` is GONE everywhere (owner, 2026-09-19) - the field is removed, not made
  optional. The summariser stops producing key points, the published day and the corpus row drop them,
  and the `output_digest` formula drops them (C1). Nothing reads `key_points` afterwards, so nothing
  looks for it. The contracts below follow this intent (CLAUDE.md 0d).
- **Scope + files touched (the exhaustive surface; every site removes `key_points`):**
  - **Published contracts + the digest formula:** `backend/idhazh/contracts/base.py`
    (`derive_output_digest` signature + payload: drop `key_points` -> `(summary, *, title)`);
    `summary.py` (`Summary.key_points` + the `_output_digest_is_rebuilt_not_trusted` validator's call);
    `digest_day.py` (`DigestItem.key_points`); `digest_view.py` (`DigestViewItem.key_points`); regen the
    `summary` / `digest-day` / `digest-view` schemas; `version` + `changelog` on each (section 11).
  - **Internal decode + knobs:** `backend/idhazh/summarize.py` (`SummaryDraft.key_points`,
    `_distinct_key_points`, `key_point_rail`, the `Summary(...)` construction and its two
    `derive_output_digest(...)` sites); `contracts/knobs/summarize.py` (`key_points_min/max`, the
    `min <= max` validator, the five band presets + the band docstring); `config/idhazh.json` (the five
    band `key_points_min/max` pairs); `backend/idhazh/classify/calls.py` (`key_point_rail` use, the turn
    fields, the band union).
  - **Prompts (the pipeline fingerprint moves; state the re-run):** `backend/idhazh/prompts/summarize.txt`,
    `summarize_and_plan_visual.txt`, `write_about_the_item.txt` - drop the key-points instruction and the
    `$key_points_*` placeholders.
  - **Same-story terms + scored text (a behaviour change, not just a field drop):**
    `backend/idhazh/assemble.py` - the same-story terms come from `title + summary` instead of
    `key_points` ([assemble.py:777](../backend/idhazh/assemble.py)), and `DigestItem(... key_points=...)`
    drops it; `backend/idhazh/stages/common.py` (line 588) - the scored `reply` text becomes
    `title + summary`. Both change what clustering and scoring see; the row states it, does not hide it.
  - **Corpus:** `backend/idhazh/corpus.py` (`Published.key_points`, the `published_is_the_scored_one`
    digest call, `rescored`); the corpus row becomes `[title, summary]`; `backend/tests/test_corpus_contract.py`
    + `test_corpus_harvest.py` + the `corpus-row` fixture; `docs/how-to/fine-tune-a-model.md`.
  - **Frontend:** `frontend/src/lib/payload/types.ts` (the field + the projected-field union),
    `payload/project.ts` (`ITEM_FIELDS` + the defending comment), `lib/day-shape.ts` (the search
    index stops folding `key_points`), `lib/assist/day.ts` (the read-time check), `lib/server/config.ts`
    (`key_points_min/max` + the band defaults).
  - **Telemetry:** `backend/idhazh/telemetry/spans.py` (`AttrKey.KEY_POINTS` + the `span.set(...)`).
  - **Tests + canary:** `backend/tests/conftest.py`, `test_summarize.py` (the key-point count / floor /
    restatement tests go), `test_canaries.py`, `backend/utilities/build_canary_day.py`.
- **Acceptance gates:** contract drift gate (all three schemas regenerate byte-identical, versioned +
  changelogged); backend `test:changed` over contracts / summarize / corpus / assemble; a unit test that
  `derive_output_digest` no longer accepts `key_points` and that `published_is_the_scored_one` returns
  `False` for a `key_points`-era digest (the accepted break is intended, C1); the day still renders when
  an old `digest.json` carries a stray `key_points` (the published read path ignores extra keys); the
  frontend browser smoke that the day + search render with no `key_points` (section 12).
- **Oracle:** a contract test proves a payload with no `key_points` validates and `output_digest` is
  taken over `(summary, title)`; a corpus test proves the row is `[title, summary]`. It cannot settle
  whether summary quality moved without the facts-first scaffold (unmeasured; the eval loop watches it).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | COMPLETE removal - the field is gone, not optional; nothing reads `key_points` afterwards | owner (K1, 2026-09-19) |
  | 2 | `output_digest` drops `key_points`; the corpus-join break is ACCEPTED, not migrated (C1) | owner (2026-09-19) |
  | 3 | Decode stops producing key points (facts-first retires); the ~21 s/item decode saving is real | owner (F1); Carmack |
  | 4 | Same-story terms + scored text fall back to `title + summary`; the clustering/scoring change is stated, not hidden | Fowler |

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
    comments in `TODO/20260914-29-found-once-plan.md`
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
  | 3 | `key_point` goes EVERYWHERE - no prisoners (owner, 2026-09-19): the value column ALSO leaves `StorySimilarityPair`, and the composite validator drops the `key_point*key_point_weight` term entirely (it becomes `cosine*cosine_weight` = `cosine`). Schema, contract, tests and code all lose `key_point` | owner (over Fowler's earlier open question) |

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
  (ROUGE-recall, needs the source) to the eval row and the console, recorded-only, no band. **Coherence
  runs in the `assemble` job, where MiniLM is ALREADY loaded to build the search index and the
  summariser is NOT resident - so there is no 3-model peak.** (The `work` shard holds the summariser +
  HHEM; MiniLM lives only in the `plan`/`assemble` jobs.) Coverage (ROUGE-recall, no model) runs
  same-day; both are recorded-only.
- **Files touched:** new `backend/idhazh/evals/embedding_metrics.py`, `backend/idhazh/evals/score.py`
  (`to_eval_row`), `backend/idhazh/contracts/eval_row.py` (add `coherence`, `semantic_coverage` -
  NOT `coverage`, a shifted meaning - nullable, + schema + changelog + `METRICS_VERSION` bump),
  `frontend/src/lib/console/eval-instruments.ts` + the model page (two recorded-only panels).
- **Acceptance gates:** unit tests reproduce a hand-worked cosine and ROUGE-recall on a fixture;
  contract drift gate; a runner-cost note (MiniLM is already loaded in `assemble` for the search index,
  so coherence adds ~0.16 s/item and no new model load).
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
| Where do metrics run? | HHEM same-day in the `work` shard (per item, with the summariser). Coverage (ROUGE, no model) same-day. Coherence in the `assemble` job, reusing the MiniLM already loaded there for the search index - the summariser is gone by then, so no 3-model peak. G-Eval fluency next-day in the council, sampled. |
| Feedback-loop contracts? | Extend `EvalRow`; new fixed-size `MetricScoreDistribution` + per-day `FittedMetricBand` (mirror #34's `Fit`); a `publish_decision` stamp on the item. All in plan #36. |
| Model context fit for 26000? | The two-call pair sizes at 64,699 against an `n_ctx` of 65536 - 837 tokens spare. 26,511 is the largest cap that window holds. |
| Decode saving from dropping key_points? | Real at 4 tok/s: ~21 s/item typical, ~1.75 h off a 300-item day. |
