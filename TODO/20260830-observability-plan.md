# Observability plan - app, model and machine, with a viewer that surfaces signal

**Last Updated**: 2026-08-30
**Level**: 5 (mints a config surface, widens two persisted contracts, adds a third-party instrumentation dependency, and amends CLAUDE.md by owner exception)

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md): orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 4; honour the ESCALATE triggers in section 0.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The project has three committed instrument ledgers and renders one of them. `state/runtime-counters.csv` holds 29 rows and no page reads a single cell, so for four days every throughput number this project quoted was taken on hardware whose read speed varied 2.30x inside one run with no surface on which anyone could notice. Separately, the pipeline has no span-level view, no cost view, no percentile view, no CPU or memory reading, and no way to turn measurement off or thin it. |
| Hard scope - in | A new `observability` config block with three toggles and one sample rate; run-level sampling of the faithfulness scorer; a retention prune with a date threshold; the site-size estimator; the `drift.yml` silent-pass fix; a `shard` column on `ItemHealthRow`; three new cells on `RuntimeCountersRow`; Langfuse instrumentation behind a toggle with a no-text guard; the `/console/` route split into three; every panel and chart named in rows 13-18; the counterfactual cost panel and the CLAUDE.md amendment it requires. |
| Hard scope - out | The reader-facing digest, archive, `/evals/` and `/404`. OpenTelemetry adopted directly (rejected; see row 9 - Langfuse's own SDK carries it). Any LLM-graded quality metric (CLAUDE.md section 0a). Publishing any prompt or completion body anywhere (Rule #11). Deleting `attempt`, `hhem_delta`, `compression` or `truncation_flagged` - the owner refused all four on 2026-08-30. |
| ESCALATE triggers | (a) The lazy chart chunk exceeding 200,000 B gzipped - it stands at 197,561 B, so ONE new echarts registration crosses it and every chart in this plan is designed to avoid one. (b) Any Langfuse span attribute carrying article text, at any point, for any reason - stop the row. (c) A published telemetry column being added; nothing here needs one and a proposal to add one is a separate decision. **A crossed page-weight ceiling is NOT an escalate trigger and never was - see the byte ruling below.** |
| Chosen strategy | Keep the ledgers as the record and add the four facts they lack. Split the page by layer so each layer can be sized and read on its own. Give every threshold a drawn marker, every figure its denominator, and every panel a sentence saying what to read off it. |
| Owner exceptions | **Cost in currency ships**, over Rule #10 and over the section 0a "Actions minutes are free" reasoning, by owner decision 2026-08-30 under CLAUDE.md section 0. It is framed as a counterfactual against an operator-set rate, never as a bill. Row 10 amends the contract in the same commit, which is what section 0 requires. |
| Execution | autonomous orchestrator per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md). Parallel N = 4. |

### The byte ruling - owner, 2026-08-31

**No approved feature in this plan is removed, deferred or shrunk because of a page-weight ceiling or a byte budget. If a ceiling binds, the ceiling is re-derived and the reason recorded. The feature ships.**

This is an owner decision under CLAUDE.md section 0 and it overrides the byte instinct every persona on this project has. It applies to every remaining row.

What it does and does not change:

| Still true | Now settled |
| --- | --- |
| Rule #2's **1 GB Pages cap** is a platform limit, not a preference. It is not waivable by this ruling, and nothing here comes close to it - the site sits at 141.1 MB with 119 published days of runway at the measured rate. | `page_weight.ceilings_bytes` for `/console/`, `/console/model/` and `/console/machine/` is a **ratchet, not a budget**. A crossed ceiling means re-measure and re-record the number, with the reason, in the same commit. It never means cut a panel. |
| The **lazy chart chunk** trigger stands, and it is not a byte argument. It stands because a new echarts registration is a design decision about the chart vocabulary, and every chart in this plan was chosen to need none. If a row genuinely needs a new chart type, that is a design question to raise - not a size question. | The `/console/` ceiling was re-derived **tighter** by PR #298, from 301,580 B to **259,908 B**. Three routes plus the panels in rows 13-19 will not fit under a number derived from one route. Expect to raise it, and record what it bought. |
| Rule #10 still binds: every re-derived ceiling carries the hardware, the date and the spread, taken from **five builds, heaviest per route**, never a mean. | `/console/` is `noindex` and operator-facing. It is not on any reader's critical path, so transfer size there costs a reader nothing. |

**The rejected alternative, recorded because it is what would otherwise have happened by default:** shrink or defer a panel to stay under a recorded number. That is how a console becomes six vetoes and no demand - the failure Susan was added to this project to prevent, and the one measured on 2026-08-28 as a page using 40.6 percent of a 1536px screen. Authority: owner, 2026-08-31.

### Owner decisions, 2026-08-30

Seven answers taken directly. Each one closes a question this plan was authored around.

| # | Question | Ruling |
| --- | --- | --- |
| 1 | Where Langfuse sends spans | **A local file sink by default.** A host - cloud or self-hosted - is opt-in through an environment variable. No secret in CI, no third party receives span data, and the pipeline is correct with no host reachable. Row 9. |
| 2 | The three route labels | **`Pipelines` / `Model` / `Machine`**, taken verbatim as the owner wrote them. Each carries a description line under the strip and the same text as its tooltip. `What the model did` survives verbatim as the h2 on the Model page. Row 11. |
| 3 | The default cost rate | **US dollars.** The rate pair itself is UNRESOLVED - the owner's answer named a model whose name did not transcribe cleanly. Row 16 does not start until a rate is named. It is the last row in its wave, so nothing waits on it. |
| 4 | Retention threshold | **13 months at full grain, then downsample to one row per (date, stage) and keep the aggregate forever.** Never hard-delete: `console.max_window_days` is 366, so a shard must stay readable for 366 days, and an aggregate at ~219 KB a year is what keeps a year-over-year comparison possible at all. Row 3. |
| 5 | Contract widenings | **All three authorised.** `shard` on `ItemHealthRow` (row 7); `cpu_busy_pct`, `peak_rss_bytes`, `model_load_ms` on `RuntimeCountersRow` (row 8); `sample_rate` and the toggle states on `RunRecord` (rows 1 and 2). All are appends at the end, so no committed row breaks and an empty cell reads as unknown. |
| 6 | Execution mode | **Autonomous.** Worktree-isolated workers, PRs, merge on green, escalate only on the named triggers. |
| 7 | Whether the console-signal plan had merged | The owner did not know and asked for it to be checked. It has **not**. See the section below - it re-sequences this plan. |

### Sequencing against the console-signal plan (checked 2026-08-30 at `origin/main` 1762be8)

**[TODO/20260830-console-signal-plan.md](20260830-console-signal-plan.md) is live, and its own Status Reckoner is stale.** The reckoner reports all 17 rows PENDING. The tree disagrees, and the tree is right.

| Evidence | What it means |
| --- | --- |
| `RankedList.svelte`, `TargetBar.svelte`, `Sparkline.svelte`, `Viewport.svelte`, `chart-flow.ts`, `rank.ts`, `viewport.ts` all present on `origin/main` | Its wave A - rows 1, 2 and 3 - has **merged**. |
| Live worktrees `yi-c04`, `yi-c05`, `yi-c06`, `yi-c07` on `feat/console-timing-axis-and-readout`, `feat/console-throughput-axis-and-readout`, `feat/console-run-health-panel`, `feat/console-failure-rate-against-volume` | Its rows **4, 5, 6 and 7 are being written right now** by sibling agents. |
| `Runs and site size` is still an h2; `totalRows` and `itemHealthRows` are still computed in `+page.server.ts` | Its rows 8 and 9 have **not** landed. |
| Open PR #259 `feat/lens-chips-on-the-item` in `yi-pill` | An unrelated sibling, but it touches the frontend. |

**Consequence, and it is the whole reason this section exists.** Rows 11 to 19 of this plan edit `frontend/src/routes/console/+page.svelte` and the components around it. Four sibling agents hold that file open, and ten more of their rows will edit it again. Splitting the route out from under them would conflict on every one of those rows.

**Ruling: this plan runs its backend waves now and holds its frontend waves.**

- **Waves A and B (rows 1-10 and 20) start immediately.** They touch `config/`, `backend/`, `schemas/`, `.github/workflows/` and `docs/`. Not one console frontend file. They cannot conflict with the sibling agents.
- **Waves C, D and E (rows 11-19) wait for the console-signal plan's row 17 to merge.** That row is its closure and its own re-baseline; starting before it means re-deriving three route ceilings against a moving target.
- **One deliberate narrowing to keep the two plans apart:** `shard` is written to `state/item-health/` and is **not** added to `PUBLIC_COLUMNS` or to `TELEMETRY_COLUMNS`. Row 15 reads it at build time under `$lib/server/`, the way `model-work.ts` already reads `state/scores.csv`. That keeps row 7 out of `frontend/src/lib/charts/series.ts`, which four of their rows edit, and it also means this plan adds **no published telemetry column** - so their ESCALATE trigger (a) never fires.


### Measured baseline (verified 2026-08-30 against `origin/main`, this box unless stated)

| Fact | Value | How it was taken |
| --- | --- | --- |
| `state/runtime-counters.csv` | 29 data rows, 6 runs, 4 days | `git show origin/main:state/runtime-counters.csv` |
| Frontend files reading it | **0** | `git grep -i 'runtime-counters\|runtime_counters' origin/main -- frontend/` returned nothing |
| `job_seconds` and `cpu_model` populated | 4 of 29 rows, **14 percent** | Both columns landed 2026-08-29 |
| `n_busy_slots_per_decode` | `1.0` on 29 of 29 rows | `n_parallel` is 1, so the counter is config read back |
| `n_decode_total` against tokens written | 1.009x to 1.013x on every row | Tokens written plus rounding |
| Read share of model time, run `2026-08-29-2` | 7,608.7 s reading vs 4,309.6 s writing - **63.8 percent is reading** | Committed rows |
| Read speed spread **inside one run** | 22.70 vs 9.86 prompt tokens/sec - **2.30x** | Same run, same day |
| Write speed spread, same run | 7.50 vs 5.71 tokens/sec - **1.31x** | Writing barely varies; reading is where the host lottery bites |
| Same-CPU-string spread | 3,086 s vs 2,785 s on two `EPYC 9V45` shards - **1.11x** | Committed rows |
| Longest sequence seen | 4,925 tokens of `n_ctx` 8,192 - **60 percent**, 3,267 spare | `n_tokens_max` |
| Slowest shard clock | 4,208 s = **70.1 min against a 150-min timeout, 47 percent** | `job_seconds`; a floor, not a ceiling |
| `ItemHealthRow` columns | **25, and none of them is `shard`** | Header of `state/item-health/2026-08.csv` |
| `RunManifest` fields | `date`, `runs` (list of `RunRecord`), `version` | `schemas/run-manifest.schema.json` |
| Config files | 5: `appearance`, `idhazh`, `sources`, `taxonomy`, `watchlist` | `git ls-tree config/` |
| `/console/` first-load JS | **79,230 B gzipped** (CI, node 22, run 33262132249) | `frontend/bundle-baseline.json` |
| `/console/` prerendered document | **164,246 B gzip -9** against a **301,580 B** ceiling - 137,334 spare, 54.5 percent used | Same record, CI 2026-08-30 |
| Lazy chart chunk | **197,561 B gzipped** (585,481 B raw) against a 200,000 B trigger - **1.2 percent of headroom** | Measured 2026-08-30 |
| `/console/` page height | 8,794px - 9.8 screens at a 900px viewport | 2026-08-30 |
| Built site | 128,064,853 B on 2026-08-27 = 122.13 MiB of a 1,024 MiB cap; growth 3.72 MiB a day at 160 items; **242-day runway** | `retention.measure()` |
| A per-item trace row, published | ~140 B raw, 0.0214 MiB a day, **1.4 days off a 242-day runway, 0.6 percent** | Derived from measured row widths |

**Correction carried into this plan.** An earlier reading of this file claimed two committed console measurements disagreed by 1.96x. They do not. **79,230 B is first-load JS and 164,246 B is the prerendered document** - two different quantities, both current, both from the same CI build. There is no dispute. What remains true and unmeasured is the growth extrapolation: the console inlines a `console.default_window_days` = 30 seed and the ledger currently holds about 6 days, so the document grows several times over as the window fills. Row 4 measures it rather than extrapolating it.

## 1 - Status Reckoner

Groups A and B are clear to run now. Groups C, D, E and F are **BLOCKED** until the console-signal plan's row 17 merges - see the sequencing section above.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The `observability` config block: three toggles, one sample rate | - | A | **DONE** | yi-o01 | #264 `e4fcd95` | - |
| 2 | Run-level sampling of the scorer, recorded on `RunRecord` | 1 | B | **DONE** | yi-o02 | #267 `c8a1318` | - |
| 3 | Retention: downsample an old shard, then delete it, on a date threshold | 1 | B | **DONE** | yi-o03 | #271 `fff5503` | - |
| 4 | The size estimator: name the directory, print the rate, print the runway | - | A | **DONE** | yi-o04 | #268 `6f562f8` | - |
| 5 | `drift.yml` stops reporting "no drift" when it compared nothing | - | A | **DONE** | yi-o05 | #260 `9122ce1` | - |
| 6 | Three measurements from data already committed | - | A | **DONE** | yi-o06 | #262 `b601b93` | - |
| 7 | `shard` on `ItemHealthRow` - the join a per-shard figure needs | - | A | **DONE** | yi-o07 | #261 `57a930e` | - |
| 8 | `RuntimeCountersRow` gains CPU busy, peak memory and model load time | - | A | **DONE** | yi-o08 | #266 `76cdc72` | - |
| 9 | Langfuse spans and generations, off by default, text never sent | 1 | B | **DONE** | yi-o09 | #269 `ca2929e` | - |
| 10 | Contract amendments: the cost exception and the event envelope | - | A | **DONE** | yi-o10 | #265 `76e1e3f` | - |
| 11 | Split `/console/` into three routes with a strip and a standing band | 4, console-signal row 17 | C | BLOCKED | - | - | - |
| 12 | `$lib/server/runtime-counters.ts` - the build-time reader | 7, 8, 11 | C | BLOCKED | - | - | - |
| 13 | The shard board | 11, 12 | D | BLOCKED | - | - | - |
| 14 | Machine page: reading against writing, cache, context headroom, clocks, batching | 11, 12 | D | BLOCKED | - | - | - |
| 15 | The percentile curve, per run | 7, 11 | D | BLOCKED | - | - | - |
| 16 | Tokens per run, and cost at a rate the operator sets | 10, 11, **a named rate** | D | BLOCKED | - | - | - |
| 17 | Model page: the eleven cards, per-item cost, the swap comparison, compression per run | 11 | D | BLOCKED | - | - | - |
| 18 | Chart chrome: a sentence per chart, a hover readout, and a shape switch where it is cheap | 13-17 | E | BLOCKED | - | - | - |
| 19 | Empty, partial and off states, written before the loaded one | 1, 11 | D | BLOCKED | - | - | - |
| 20 | Field descriptions for the four columns the owner kept | - | A | **DONE (backend half)** | yi-o20 | #270 `55ebbca` | - |
| 21 | Closure: re-baseline three routes, record every ruling, delete this plan | 1-20 | F | BLOCKED | - | - | - |

### Found during execution - four things that need a row and did not have one

Every one of these was measured by a worker, not predicted by this plan.

| # | Finding | Why it needs its own row |
| --- | --- | --- |
| A | **The `/console/` document crosses its 301,580 B ceiling on published day 16.** Measured by removing real days and rebuilding: the page is linear in ITEMS at 50.45 gzipped bytes an item, fitting an independent control to 0.03 percent. Row #3's retention prune cannot save it - a 13-month threshold is published day 395, and the compression scatter inlines every row `state/scores.csv` has ever held. | Two problems that share a file and share nothing else. This one belongs with Row #11, which is blocked. |
| B | **CLOSED, both halves, and the decision each half got is different.** `state/seen/` is a lookup, so it is deleted rather than folded: PR #305 shipped `retention.prune_seen` and shed the address column with it, and the shard fell 43.8 percent. `state/scores.csv` **stays unbounded on purpose** - `merge=union` makes an in-place fold unsound, and a month layout cannot be reached without `frontend/src/`. The arithmetic, the per-reader windows and what would change the answer are in [../docs/architecture/publishing/layout.md](../docs/architecture/publishing/layout.md#what-bounds-the-committed-state-tree). | Closed. Both figures above were stale within a day: re-measured 2026-08-31 the shares are `seen` 37.2 percent and `scores.csv` 34.6 percent. |
| C | **Duplicate ledger rows, diagnosed.** Run `2026-08-29-3` holds shards `[0,1,1,2,3,3]`. Two workflow runs computed the same `run_id`, and `actions/checkout` pins each to a frozen SHA - so the second run's in-Python dedup could not see rows the first pushed after that SHA, and `merge=union` concatenated both. `state/item-health/` carries 44 duplicates from the same cause. The general shape: **the dedup reads a frozen snapshot while the merge is line-based**, so the key can never catch a re-execution. | Any figure summed over a run is wrong today. One run reports -394 seconds, which is impossible. |
| D | **`score_ms` is still on the Pipelines route's critical-path timing table.** Row #20's decision 3 could not ship: four sibling agents hold `frontend/src/routes/console/+page.server.ts` open. | Rides with Row #11. |

### Corrections to this plan's own text, made by measurement

| This plan said | The tree says |
| --- | --- |
| `digest.yml` runs `bundle-gate` BEFORE it commits the day, so a crossed ceiling stops publishing | **False.** The order is build -> `Commit the day` (L1130) -> `bundle-gate` (L1198), and `test_workflows.py::test_the_build_gates_the_publish_and_the_weight_ratchet_runs_after_it` asserts it. A crossed ceiling reddens the job; the day publishes anyway. Severity is one notch lower than stated, in both places this plan claimed it. |
| The aggregate costs about 219 KB a year | **93,136 B a year**, measured by folding the real committed month: 24 rows, 1,531 B, 829.8x smaller than the shard. Four stages a day, not five - `plan` wrote no row that month. |
| Langfuse Python SDK v3 | **4.14.4.** Six of its eleven added distributions are OpenTelemetry. Install cost measured at 32,656,612 bytes and 260.9 s (spread 24.9, n=3), so it went in an optional extra. |
| Langfuse being OpenTelemetry underneath makes the file sink a configuration | **False.** The client wires to an OTLP HTTP exporter and a host; the file sink is about 30 lines of our own. |
| `peak_rss_bytes` can come from the cgroup `memory.peak` | **Dead on this runner** - it prints `unavailable`. `VmHWM` from the RSS sampler was the only readable instrument. |
| The read-speed spread is 2.30x | That is **one run**. Over seven committed runs the range is **1.10x to 4.19x**; the worst run ran 9.75 against 40.89 prompt tokens a second. |
| A negative clock residual is expected occasionally | **0 negatives in 2,317 items.** Median 79 ms against a median call of 122,432 ms - 0.066 percent. |
| `truncation_flagged` - nothing reads it | **False.** `model-work.ts` counts it through `CUT_FLAG_MEANS_A_CUT_FROM`, and `series.ts` plus `CompressionScatter.svelte` mark a cut point from it. |
| Every committed row predates the cut-flag boundary, so every day reads `-` | **430 rows are now on the new side**, 4 cut and all 4 flagged, agreeing with the word-count pair on 430 of 430. The count has returned. Two docs corrected. |

## 2 - Row #1 - The `observability` config block: three toggles, one sample rate

- **Scope:** One block in `config/idhazh.json` carries every switch this plan adds, with a Pydantic contract and a generated schema.
- **Files touched:** `config/idhazh.json`; `backend/idhazh/contracts/app_config.py`; `schemas/app-config.schema.json`; `backend/idhazh/config.py`; `backend/tests/test_contracts.py`; `docs/concepts/config.md`; `tests/fixtures/contracts/app-config/*.json`.
- **Acceptance gates:** `ruff`, `mypy --strict`, contract drift byte-identical, full `pytest`, a fresh clone runs on the defaults.
- **Oracle:** Set each toggle false in turn and assert the corresponding writer produces no file and no row, while every other writer is unchanged. A toggle that switches off more than its own name is a failed row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The block is `observability` inside `config/idhazh.json`, not a sixth config file. A new file needs its own loader, schema, fixture, drift entry and doc page; a block needs none of those. Four keys do not earn a file. | Fowler |
  | 2 | Four keys: `score_items` (default true), `publish_telemetry` (default true), `scrape_server_counters` (default true), `sample_rate` (default 1.0, range 0.0 to 1.0 inclusive). | Owner, 2026-08-30 |
  | 3 | **The item-health census is not switchable and the config docstring says so.** It is the denominator under every rate on every page. Turning it off does not thin a measurement, it makes every other measurement unreadable. | Fowler |
  | 4 | An instrument that did not run writes an **empty cell**. A toggle changes whether a row is written, never the shape of a row. Two existing statements of this rule are cited rather than a third being invented: `RuntimeCountersRow.csv_row` ("Empty is not zero") and the degrade rules in `telemetry-series.md` ("`<1`, never `0`"). | Fowler |
  | 5 | The state of all four keys is written onto `RunRecord`, one fact per run. Off and broken are indistinguishable in a ledger of absences unless the run says which it was. | Fowler |
  | 6 | `sample_rate` is validated but not read by row 1. Row 2 reads it. Splitting them keeps the config commit revertible on its own. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | One master `observability.enabled` switch | Collection, scoring and publishing fail differently and a reader must behave differently for each. One switch means nobody can tell which instrument went dark. | Fowler |
  | 2 | A sixth config file | Five loaders, five schemas, five fixtures already exist. A fourth key does not justify a sixth of each. | Fowler |
  | 3 | Defaulting a missing measurement to `0` | Publishes an invented number, and it is the defect class the `truncation_flagged` migration already cost a doc section to fix. | Fowler |

## 3 - Row #2 - Run-level sampling of the scorer, recorded on `RunRecord`

- **Scope:** At `sample_rate` below 1.0 a whole run either scores every item or scores none, chosen deterministically, with the rate recorded on the run.
- **Files touched:** `backend/idhazh/cli.py`; `backend/idhazh/contracts/run_manifest.py`; `schemas/run-manifest.schema.json`; `backend/tests/test_pipeline.py`; `docs/concepts/evaluation.md`; `tests/fixtures/contracts/run-manifest/*.json`.
- **Acceptance gates:** `ruff`, `mypy --strict`, drift byte-identical, full `pytest`.
- **Oracle:** For a fixed `sample_rate`, run the selector over 1,000 synthetic `run_id` values and assert the selected share lands inside a stated tolerance of the rate, and that re-running the selector on the same ids gives byte-identical selections. A selector that is not reproducible cannot be audited a year later.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The unit sampled is the run, not the item and not the shard.** `1.0` is 100 percent of runs; `0.8` is 80 percent of runs. This is the owner's own model, taken over the per-item design proposed on 2026-08-30. | Owner, 2026-08-30 |
  | 2 | It follows that the rate is one fact per run, so it lands on `RunRecord` and **`EvalRow` is not touched.** The earlier "the rate must travel on the row" ruling was correct only for per-item sampling; per-run sampling makes per-run recording sufficient. The owner's coarser design removes a persisted-contract change and one Level-5 pause. | Fowler, conceding to Owner |
  | 3 | **Shards are never the sample unit.** A day with 3 of 4 shards scored has a wrong denominator for that day and nothing on the page could say so. A run either scores everything or nothing, so every day stays internally consistent. | Andre |
  | 4 | Selection is `sha256(run_id)` mapped to the unit interval and compared against the rate. Deterministic, reproducible from the committed id alone, and blind to the outcome - a selector that could see quality would bias the ledger. | Andre |
  | 5 | This is **collection-time sampling, not display-time sampling.** An unsampled run is never scored, so the rows do not exist. Nothing is thinned in the browser. | Owner, 2026-08-30 |
  | 6 | **Published rates are computed from the census only.** The sampled ledger publishes distributions - medians, spreads, histograms. Medians survive a sample; rates do not. This is a rule and not a scaling formula, because a formula is a thing somebody forgets to apply. | Fowler |
  | 7 | At any rate below 1.0 every affected panel prints the sentence from row 19 with its own count. `console.min_attempts_for_rate` = 5 already encodes the doctrine and is extended, not duplicated. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Sampling individual items inside a run | Needs `sample_rate` on `EvalRow`, which is a persisted-contract change, and it makes a day's quality figures a partial view of that day with no clean denominator. | Fowler |
  | 2 | Sampling shards | Breaks the day's denominator, which is the one thing sampling must not do. | Andre |
  | 3 | No sampling at all | Refused by the owner. The scorer costs about 2.0 s an item and 21-24 min a day, which is a real lever even though the trace-collection cost is not. | Owner |
  | 4 | Sampling the trace collection from row 9 | Collecting one timing row is about 1 part in 128,000 of a shard (0.0008 percent). There is nothing to buy. | Carmack |

## 4 - Row #3 - Retention: downsample an old shard, then delete it, on a date threshold

- **Scope:** A pipeline step that keeps recent telemetry at full grain, folds anything older into a per-day aggregate, and then deletes the full-grain shard.
- **Files touched:** `config/idhazh.json`; `backend/idhazh/contracts/app_config.py`; `schemas/app-config.schema.json`; `backend/idhazh/retention.py`; `backend/idhazh/cli.py`; `.github/workflows/digest.yml`; `backend/tests/test_retention.py`; `docs/concepts/config.md`; `docs/architecture/publishing/layout.md`.
- **Acceptance gates:** `ruff`, `mypy --strict`, drift byte-identical, full `pytest`, `shellcheck` on any changed workflow script.
- **Oracle:** Build a fixture `state/` tree spanning 20 months, run the prune at a 13-month threshold, and assert three things: every shard newer than the threshold is byte-identical, every shard older than it is gone, and the per-day totals recomputed from the aggregate equal the totals recomputed from the deleted shard. A prune that loses a total is a failed row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `observability.keep_months`, default **13**. `console.max_window_days` is 366, so a shard must stay readable for 366 days or the widest window preset silently lies. Thirteen covers 366 days plus the current partial month. | Carmack |
  | 2 | **Downsample before deleting, never delete outright.** One row per (date, stage) carrying count, p50, p90, max and sum is about 120 B; at five stages that is 600 B a day, **219 KB a year**. Deleting instead makes a year-over-year comparison unanswerable, and Rule #10 then forbids citing last year's number at all. | Carmack |
  | 3 | A second knob `observability.hard_delete_after_months` (default null) does delete the aggregate too, for the day the owner wants the bytes back. Null means never. | Owner, 2026-08-30 |
  | 4 | The prune runs in the digest workflow after the day is committed, never before. A prune that runs first and then fails leaves a hole no run refills. | Fowler |
  | 5 | The knob lives in `observability`, not in the existing `retention` block. That block governs the published visual prune and the site alarm on a different tree; a ledger shard's lifetime is a different decision. | Carmack |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Relying on `prune.yml` to bound it | That squashes git HISTORY, not the working tree. A 13-shard set survives it intact and an unbounded one is unbounded either way. | Carmack |
  | 2 | Deleting with no aggregate | Trades a permanent answer for 219 KB a year. | Carmack |
  | 3 | A separate weekly workflow | A second schedule to keep green, for a step that costs seconds inside one that already runs. | Fowler |

## 5 - Row #4 - The size estimator: name the directory, print the rate, print the runway

- **Scope:** The site-size instrument stops printing one number and starts printing a rate, a runway and a per-directory split.
- **Files touched:** `backend/idhazh/retention.py`; `backend/idhazh/contracts/` (the `SiteSize` shape); `backend/idhazh/cli.py`; `backend/tests/test_retention.py`; `docs/reference/measurements.md`; `docs/architecture/publishing/layout.md`.
- **Acceptance gates:** `ruff`, `mypy --strict`, full `pytest`, plus one real build whose reported figures are recorded with the commit sha and the ledger row count beside them.
- **Oracle:** Over a fixture tree of known sizes, assert `by_directory` sums exactly to the total, and assert `days_to_cap` equals headroom divided by the marginal rate computed independently in the test. Assert an empty tree is a failure and not a pass - a `measure()` that returns zero for a missing root makes an absent build clear every ceiling.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The measured tree is `frontend/build/`.** The 1 GB cap is on what `upload-pages-artifact` sends. Measured 2026-08-27, `frontend/public/digest/` was 7,027,075 B while the built site was 128,064,853 B - **18.2x apart**, so measuring the wrong tree gives a green light that cannot fire. | Carmack |
  | 2 | Three new fields: `by_directory` (top-level children of `build/`, so a growing directory can be named), `bytes_per_published_item` (the marginal number a design change moves), `days_to_alarm` and `days_to_cap` (the runway). | Carmack |
  | 3 | **Not a new gate.** `frontend/scripts/bundle-gate.mjs` already fails the build on a crossed per-route ceiling, before `digest.yml` commits the day. This row reports; it fails nothing new. | Carmack |
  | 4 | The row also settles the console growth question by measurement: build with the ledger seeded to 6 days and again to 30, and record both document sizes against the 301,580 B ceiling. The 2.49x extrapolation in circulation is derived from one point and must not size a decision. | Carmack |
  | 5 | Every figure recorded carries hardware, date and spread (Rule #10). | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A new gate that fails on the traces directory | The cap is on the whole tree. One directory's share does not give a date, and a second gate is a second thing to keep green. | Carmack |
  | 2 | Measuring `frontend/public/` | 18.2x smaller than the tree the cap is on. | Carmack |
  | 3 | Reporting a total only | A total gives no date. The runway is the number the ceiling question needs. | Susan |

## 6 - Row #5 - `drift.yml` stops reporting "no drift" when it compared nothing

- **Scope:** An empty comparison window becomes a loud failure instead of a green check.
- **Files touched:** `backend/idhazh/drift.py`; `.github/workflows/drift.yml`; `backend/tests/test_drift.py`; `docs/concepts/evaluation.md`.
- **Acceptance gates:** `ruff`, `mypy --strict`, full `pytest`, `shellcheck`.
- **Oracle:** Run the comparison with an empty recent window, an empty baseline window, and both empty. All three must exit non-zero with a message naming which side was empty. Bite-prove it by running the pre-fix code on the same fixtures and confirming it exits 0.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `compare([], [])` returns `[]` and the workflow reads `if not findings` and exits 0. **Turn the scorer off for a week and the only automated watchman for slow extraction failure reports "all clear" every day.** That is the worst defect this plan touches. | Andre |
  | 2 | A window with fewer than `n` rows on either side exits non-zero. "Nothing to compare" and "no drift" are different facts and must not share an exit code. | Andre |
  | 3 | `n` is a config value, not a literal (Rule #6). It lives beside the existing drift knobs. | Fowler |
  | 4 | The honest sentence is already printed into the step log. The fix is that it now prints under a red check somebody opens. | Andre |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Opening an issue instead of failing | An issue in a repository nobody watches daily is the same silence with more steps. | Andre |
  | 2 | Leaving it and documenting the trap | A documented trap still fires. | Fowler |

## 7 - Row #6 - Three measurements from data already committed

- **Scope:** Compute three quantities nobody has computed, from committed ledgers, and record them. No schema change.
- **Files touched:** `backend/utilities/` (one read-only reporter); `docs/reference/measurements.md`.
- **Acceptance gates:** `ruff`, `mypy --strict`, full `pytest`; every recorded figure carries hardware, date and spread.
- **Oracle:** Each figure is computed twice by two independent expressions over the same rows and must agree. A single expression cannot catch its own error.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Unaccounted shard wall-clock**: `job_seconds - sum(fetch_ms + extract_ms + summarize_ms)` per shard. This is the one thing a span tree would have surfaced that the ledger does not, and it is computable today. If the model is not busy for most of a shard, more shards is the wrong lever and nobody currently knows that. | Andre |
  | 2 | **The client-versus-server residual**: `summarize_ms - (prefill_ms + decode_ms)`. A residual of 40 ms is transport; a residual of 4,000 ms is time the server spent that its own timings block does not name. It decides whether a slow day is the model's fault or ours - today the model is blamed by default because it is the only thing measured. | Andre |
  | 3 | The residual is a **run-level assertion with a threshold, not a published figure**. It is a difference of two clocks, so it will occasionally print negative, and a negative "overhead" one line from a model-time figure invites an operator to add them together and get a wrong number. If the alarm fires more than once it earns a column. | Andre |
  | 4 | **Words to tokens at the new cap**: regress `input_tokens` on `source_words` over rows written after `truncation_cap_tokens` moved to 5000. Regress, never divide - over 104 items the slope is 1.387 tokens a word with a 951-token intercept (the fixed prompt), while the naive ratio reads 1.695 and looks past the 1.59 overflow threshold. | Andre |
  | 5 | Row 7 must land before per-shard versions of any of these are possible, because item-health has no `shard` column. Per-run versions work today and are what this row computes. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Adding an SDK to obtain these | All three are arithmetic over committed cells. | Carmack |
  | 2 | Publishing the residual per item on the console | See decision 3. | Andre |

## 8 - Row #7 - `shard` on `ItemHealthRow` - the join a per-shard figure needs

- **Scope:** One appended nullable column so a per-item row can be attributed to the machine that produced it.
- **Files touched:** `backend/idhazh/contracts/item_health_row.py`; `schemas/item-health-row.schema.json`; `backend/idhazh/telemetry.py`; `backend/idhazh/cli.py`; `backend/tests/test_contracts.py`; `frontend/scripts/build-canary.mjs`; `tests/fixtures/contracts/item-health-row/*.json`; `docs/architecture/sources/item-health.md`.
- **Acceptance gates:** `ruff`, `mypy --strict`, drift byte-identical, full `pytest`, and CI's `site` job green (the canary `.mjs` COLUMNS array is a third copy of this header).
- **Oracle:** Assert that for every run in a fixture, the set of shards seen in item-health equals the set of shards seen in `state/runtime-counters.csv` for the same run. Two ledgers that disagree about how many shards ran cannot be joined.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Appended at the end, nullable.** The frontend's `parseTelemetryCsv` header check is a PREFIX check, so an append is safe for a cached browser bundle and an insert anywhere earlier blanks every console chart. | Fowler |
  | 2 | Six files change, all known and all named above. Two of them are the traps that only the full suite catches: the 25-name literal in `test_the_item_health_ledger_columns_are_defined_once`, and the `COLUMNS` array in `frontend/scripts/build-canary.mjs`, which is JavaScript and restates the header a third time. | Fowler |
  | 3 | The column is **not** added to the published projection. Per-shard figures are drawn on route C, which reads `state/` at build time under `$lib/server/`. Publishing it would be ESCALATE trigger (c). | Fowler |
  | 4 | It is null on every row written before this lands, and null reads as unknown, never as shard 0. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Deriving the shard from `run_id` | `run_id` names the run, not the shard. Nothing in it identifies which of four workers wrote a row. | Fowler |
  | 2 | A separate shard-to-item mapping ledger | A fourth file to join, for one integer that belongs on the row. | Fowler |
  | 3 | Doing per-run percentiles only, and skipping the column | The measured spread is **2.30x between shards inside one run**. A per-run percentile averages exactly the variance the operator needs to see. | Susan |

## 9 - Row #8 - `RuntimeCountersRow` gains CPU busy, peak memory and model load time

- **Scope:** Three cells the owner asked for, all read at the scrape point that already exists.
- **Files touched:** `backend/idhazh/contracts/runtime_counters.py`; `schemas/runtime-counters-row.schema.json`; `backend/idhazh/cli.py`; `.github/workflows/digest.yml`; `backend/tests/test_contracts.py`; `backend/tests/test_workflows.py`; `tests/fixtures/contracts/runtime-counters-row/*.json`.
- **Acceptance gates:** `ruff`, `mypy --strict`, drift byte-identical, full `pytest`.
- **Oracle:** Parse a real captured `/proc` sample and a real `/metrics` capture from a downloaded run artifact, and assert each cell equals a value computed independently from the raw text. No hand-written fixture for the metrics body - the upstream README has been behind the binary before.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **`cpu_busy_pct`** - one number per shard per run. Measured 2026-08-23 on run `32672629352` the cgroup averaged 3.99 of 4 CPUs with zero throttling, so the expected value is at or near 100 and **a drop is the signal**. The owner asked for exactly this framing. | Owner, 2026-08-30 |
  | 2 | **`peak_rss_bytes`** - the high-water mark, from `VmHWM` or the cgroup `memory.peak`, at the scrape point. It answers whether a candidate model can be served on 16 GB at `n_ctx` 8192 with headroom. Today a run either survives or the runner OOM-kills it. | Andre and Carmack |
  | 3 | **`model_load_ms`** - the one metric from the external note's host list with a decision attached. Model load is the fixed cost `run.shard_size` exists to amortise. Per shard, never per item. | Carmack |
  | 4 | **Dropped, with the owner's agreement: `n_busy_slots_per_decode` as a chart.** It reads `1.0` on 29 of 29 rows because `n_parallel` is 1. The column stays; it earns one line of text on route C and a chart the day the knob moves. | Owner, 2026-08-30 |
  | 5 | Any new flag on the counters CLI step breaks `test_workflows.py::test_the_servers_own_counters_outlive_the_job_that_read_them`, which asserts the LAST 6 shlex tokens. Budget for it; do not be surprised by it. | Fowler |
  | 6 | A free-text cell needs a one-line constraint. `cpu_model` already carries `pattern=r"^[ -~]+$"` because `state/*.csv` merges line by line across eight shards and a newline in a cell splits the row. Any new string cell copies that. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | CPU and memory as time series | The host exists for 70 minutes and is destroyed. A series over its life answers nothing the peak and the mean do not. | Carmack |
  | 2 | `rss_mb` as well as peak | The same fact from two places. Two numbers for one thing is how a page starts disagreeing with itself. | Carmack |
  | 3 | `load_average` | On a shared VM it includes the neighbour. | Carmack |

## 10 - Row #9 - Langfuse spans and generations, off by default, text never sent

- **Scope:** Instrument the pipeline with Langfuse's span and generation API so a developer can see the nesting and the sub-stage split, under a toggle, with a hard guard that no article text ever leaves the process.
- **Files touched:** `pyproject.toml`; `backend/idhazh/telemetry.py`; `backend/idhazh/cli.py`; `backend/idhazh/summarize.py`; `backend/idhazh/fetch.py`; `backend/idhazh/extract.py`; `backend/tests/test_telemetry.py`; `backend/tests/test_canaries.py`; `docs/concepts/telemetry.md`; `docs/how-to/run-the-gates.md`.
- **Acceptance gates:** `ruff`, `mypy --strict`, full `pytest`, and the whole suite green with the toggle both on and off. No test touches the network (Rule #7).
- **Oracle:** **The guard is the row.** Build a span tree over a fixture article whose body contains a unique sentinel string, capture every attribute of every span and generation the instrumentation would send, and assert the sentinel appears in none of them and that no attribute exceeds a stated character limit. Run the same assertion over all five committed injection canaries. A single leaked character fails the row and stops the plan (ESCALATE trigger b).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Adopted, on the owner's reasoning rather than the personas'.** The three engineering personas judged it against this project alone and refused. The owner's argument is different and not one they were briefed on: the skill and the code transfer to a future repository, and that is worth paying for. | Owner, 2026-08-30 |
  | 2 | **A fact the owner should have: Langfuse's Python SDK v3 is built on OpenTelemetry.** "No OpenTelemetry, yes Langfuse" means "OpenTelemetry wearing a Langfuse API". That is not an objection - it means the transferable skill you get IS the OpenTelemetry skill, which is the better outcome - but the plan must not pretend the dependency is absent. | Andre |
  | 3 | **What a span buys that a column does not**, stated exactly so the row can be judged: start instants, nesting, and sub-stage granularity. `fetch_ms`, `extract_ms` and `summarize_ms` already give the split the owner asked about; what they cannot give is a robots-check span nested inside a fetch span, or the ordering of two things inside one stage. Instrument the sub-steps, or the row buys only a nicer view of what the row already holds. | Andre |
  | 4 | **A generation is a span subtype for a model call.** It carries the model reference, input and output token counts, and a completion-start time. **Prefill and decode cannot be child spans**: llama-server reports both as totals in the reply after the call finished, so they land as attributes on the generation. Nobody can nest a span around a duration that was reported retrospectively. | Andre |
  | 5 | **Text never leaves the process.** The `input` and `output` fields carry `source_digest`, `prompt_digest`, word counts and token counts - never a body, never a title, never a URL. This is the Rule #11 boundary and decision 4's oracle is what holds it. | Andre |
  | 6 | **The ledgers stay the record; Langfuse is evidence.** CLAUDE.md section 1b already draws this line. No page reads a Langfuse trace, no gate depends on one, and the pipeline runs correctly with the toggle off and the host unreachable. | Fowler |
  | 7 | Default **off in CI, on for a developer**. A CI run reaching a third-party host adds a secret, a free-tier dependency and a failure mode to a job whose whole point is to publish. | Carmack |
  | 8 | A local file sink is wired at the same time, so a developer with no Langfuse host still gets the tree. Langfuse v3 being OpenTelemetry underneath is what makes this a configuration rather than a second code path. | Carmack |
  | 9 | `prompt_digest` - SHA-256 of the exact rendered prompt bytes - lands on `Summary` and `EvalRow` in this row. It is 64 hex characters and no text, and it answers the one question a stored prompt would have answered: did we send the same bytes twice. `pipeline_fingerprint` covers the inputs to the prompt and nothing covers the rendered result, so a template edit currently fires `determinism_violation` and names the wrong cause. | Andre |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | The OpenTelemetry SDK directly | The owner asked for Langfuse and Langfuse carries it. Adopting both is one dependency too many for one span tree. | Owner |
  | 2 | Langfuse on by default in CI | A publish job that can fail on a third party's availability. | Carmack |
  | 3 | Sending `input` and `output` as the SDK intends | It is the default, it carries the article body, and this repository is public. This is ESCALATE trigger (b) and the single strongest argument against the SDK - which is why the guard is the row's oracle rather than a note. | Andre |
  | 4 | Making a Langfuse trace a committed record | A fourth record of the same run, free to disagree with the other three. `telemetry.md` already rejected that shape. | Fowler |

## 11 - Row #10 - Contract amendments: the cost exception and the event envelope

- **Scope:** Two amendments to the memory, both required by other rows, landing together so neither is a docs-only PR.
- **Files touched:** `CLAUDE.md`; `docs/concepts/telemetry.md`; `docs/agents/guardrails.md`; `AGENTS.md`; `backend/idhazh/cli.py`; `backend/idhazh/telemetry.py`; `backend/tests/test_telemetry.py`.
- **Acceptance gates:** `ruff`, `mypy --strict`, full `pytest`, ASCII-and-LF check green, every cross-link resolving.
- **Oracle:** Grep `docs/` and `CLAUDE.md` for every sentence asserting the project publishes no cost figure, and for every one of the 19 unemitted event names, and assert each hit is either corrected or deleted. A half-applied amendment is the failure mode - a corrected table with stale prose under it has happened here before.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The cost figure ships and CLAUDE.md is amended in the same commit.** Section 0 says user approval supersedes every rule and that a conflicting rule is amended in the same commit; this is that mechanism working as designed, not a rule being broken quietly. | Owner, 2026-08-30 |
  | 2 | The amendment is narrow and names its own reason: a counterfactual cost, computed from an operator-set rate, is permitted on the operator console, labelled as a counterfactual, and is never presented as a bill. Rule #10 continues to bind every other number on every other surface. | Owner and Fowler |
  | 3 | The reason recorded is the true one: Actions minutes are free, so the money figure answers "what would this have cost on a hosted provider" - which is a real question about whether the self-hosted design is worth its wall clock, and which no other figure on the site answers. | Owner, 2026-08-30 |
  | 4 | **`docs/concepts/telemetry.md` is corrected.** It claims the event envelope is "a persisted surface with its own schema", and there is no such model and no such schema. It lists 20 event names and **exactly one is emitted** (`item.summarize.failed`), from a hand-built dict literal in `_log_no_reply`. Delete the false sentence and the 19 unemitted names; keep the envelope. | Fowler |
  | 5 | The dict literal is lifted into one typed `event()` helper so a second emitter cannot invent a second shape. That is the behavioural half that stops this being a docs-only PR (CLAUDE.md section 5). | Fowler |
  | 6 | A `## Rejected alternatives` row is added to `telemetry.md` recording that the OpenTelemetry SDK was refused **directly** and arrives instead through Langfuse under row 9's conditions, with the reason and the authority. A future reader must not have to re-derive this. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Shipping the cost panel without amending the contract | Leaves the repository's own memory contradicting its published page, which is the failure mode Rule #4 exists to prevent. | Fowler |
  | 2 | Implementing the 19 missing event names | Builds 19 emitters into a store that expires in two days, when the ledgers already hold the fact. | Fowler |
  | 3 | Deleting the telemetry concept page | The envelope is real and has one emitter. Deleting the page loses the shape and invites the next emitter to invent a second one. | Fowler |

## 12 - Row #11 - Split `/console/` into three routes with a strip and a standing band

- **Scope:** One operator surface becomes three prerendered routes with a shared navigation strip and a band that is present on all three.
- **Files touched:** `frontend/src/routes/console/+page.svelte` and `+page.server.ts`; new `frontend/src/routes/console/model/` and `frontend/src/routes/console/machine/`; `frontend/src/lib/components/ConsoleNav.svelte` (new); `frontend/src/lib/components/ConsoleBand.svelte` (new); `config/idhazh.json` (`page_weight.ceilings_bytes`); `backend/idhazh/contracts/app_config.py`; `schemas/app-config.schema.json`; `frontend/tests/console-nav.spec.ts` (new); `docs/architecture/publishing/frontend.md`.
- **Acceptance gates:** `svelte-check` 0 errors, `npm run build`, `npm run bundle-gate`, browser smoke on all three routes in both themes, each route rendering complete with JavaScript disabled, each route rendering when its data file is absent.
- **Oracle:** With JavaScript disabled, assert each of the three routes returns its own complete document and that every navigation link is a real anchor that resolves. Assert `page_weight.ceilings_bytes` names all three routes - the gate already fails on a ceiling naming no route, and this catches the reverse.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Three routes, drawn as a tab strip.** Four personas ruled routes and one ruled tabs; the tab ruling's own condition was that the state live in the URL as a path segment, and a path segment that prerenders is a route. So this is the unanimous answer, not a casting vote. | Jony, Carmack, Fowler, Susan |
  | 2 | Paths `/console/`, `/console/model/`, `/console/machine/`. The first keeps its path because it is the one an operator types and the one every existing bookmark points at. | Jony |
  | 3 | **Labels are `Pipelines`, `Model`, `Machine`**, taken verbatim as the owner wrote them on 2026-08-30, each with a one-line description under the strip and the same text as a title attribute. The four name sets proposed differed **only** in wording - the panel-to-route assignment was identical in all four - so the choice is a copy choice, and a description line resolves the shortness the owner objected to. The protected `What the model did` copy survives unchanged as the h2 on the Model route. | Owner, 2026-08-30 |
  | 4 | **Every label carries its own worst state**, computed at build time: `Machine - 1 shard at 2.3x` beats `Machine (4)` and both beat `Machine`. This is the mechanism that stops a route being the place a metric goes to die. | Susan |
  | 5 | **A standing band above the strip, on all three routes**, carrying four things and nothing else: yesterday's verdict as a sentence; the one worst thing and which route it is on; site size against 1 GB with its runway; and the window control. A control below the thing it governs is read second. | Susan |
  | 6 | **Three cross-boundary carries**, one sentence each, no chart: on Pipelines, `The model spent 4 h 12 m of this. Model ->`; on Model, `This day ran on 3 different processors, 1.51x apart. Machine ->`; on Machine, `214 articles on this day.` These are what stop a route hiding the panel that explains another. | Jony |
  | 7 | Identity is **identical** across routes - type scale, space scale, radius, elevation, frame width, both colour ramps. Only a 3px accent rule under the active label differs, taken from the categorical ramp. **The health ramp never touches the strip**: green, amber and red on a label would say a route is failing, and a route is a noun. | Susan |
  | 8 | What tells an operator which route he is on without reading the label is the **silhouette of the first panel**: a per-day column skyline on Pipelines, a short stack of long horizontal bars on Model, four to eight thick rows with processor names on Machine. Each shape is the one its own question needs, so nothing is made distinctive for its own sake. | Susan |
  | 9 | `Model` and `Machine` share a first letter, which was the recorded cost of this name set. It is paid off by decision 8 - the silhouette, not the initial, is what an operator recognises - and by the description line under each label. | Jony |
  | 9 | Three ceiling keys in `page_weight.ceilings_bytes`. One key covering three surfaces means a blown budget cannot say which surface blew it, and that is the decisive argument for routes over tabs. | Fowler |
  | 10 | The shell entry chunk (42,841 B) and the chart engine chunk (197,561 B) are each one cached artifact across all routes, so splitting duplicates neither. What splits is the inlined seed and the markup - the terms that grow. | Carmack |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Tabs with the state in a query string | A prerendered page cannot vary by query string, so either every panel ships anyway or the hidden ones fetch at runtime. It also fails the JavaScript-disabled gate. | Jony |
  | 2 | Tabs with a hash | Same byte cost, and find-in-page stops at the hidden panels. | Jony |
  | 3 | Accordions | Collapsed markup still ships, and it hides the panel he needs on the day he needs it. | Jony |
  | 4 | Nine routes, one per section | The operator's job has three altitudes, not nine. Nine routes is a navigation tree and this site does not have one. | Jony |
  | 5 | Keeping one page | It is 8,794px - 9.8 screens. A figure 7,000px down is already hidden, and hidden without saying so. | Susan |

## 13 - Row #12 - `$lib/server/runtime-counters.ts` - the build-time reader

- **Scope:** The machine route gets its data the way the model section already gets its data: read at build time from `state/`, never published.
- **Files touched:** `frontend/src/lib/server/runtime-counters.ts` (new); `frontend/src/routes/console/machine/+page.server.ts`; `frontend/tests/console-machine-data.spec.ts` (new); `docs/architecture/publishing/telemetry-series.md`.
- **Acceptance gates:** `svelte-check` 0 errors, unit tests on the derivations, browser smoke, the route rendering with the ledger absent.
- **Oracle:** Assert the module is unreachable from any client bundle - the existing charts spec pattern - and assert that for a fixture ledger every derived figure equals a value recomputed independently in the test.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Zero new published telemetry columns.** `frontend/src/lib/server/model-work.ts` already reads `state/scores.csv` at build time under `$lib/server/`, which SvelteKit refuses to bundle for a browser. The same route serves this file, so no trust-boundary question arises and ESCALATE trigger (c) does not fire. | Susan |
  | 2 | The file is 29 rows today and reaches roughly 2,920 rows at 8 shards a day for a year - about 380 KB raw. **That is an estimate, not a measurement**, and row 21 measures it against the route's own ceiling. If it does not fit, the route fetches month shards through the existing viewport path. | Carmack |
  | 3 | `STATE_ROOT` is the existing redirect for a whole-tree read and is what a test uses to drive a degraded ledger. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Publishing the counters as a projection | A published column is a persisted contract and a trust-boundary decision, for data one build-time read already reaches. | Susan |
  | 2 | Fetching the CSV from the browser | It is in `state/`, which is not served. Serving it is decision 1 by another name. | Fowler |

## 14 - Row #13 - The shard board

- **Scope:** One panel, full frame width, one row per shard of the newest run, ranked by job clock.
- **Files touched:** `frontend/src/lib/components/ShardBoard.svelte` (new); `frontend/src/lib/components/DotStrip.svelte` (new); `frontend/src/routes/console/machine/+page.svelte`; `frontend/tests/console-shard-board.spec.ts` (new).
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke in both themes, the panel rendering with `cpu_model` null on every row (which is 86 percent of committed rows today).
- **Oracle:** Assert every bar's reading and writing segments sum to that shard's model seconds, and assert the job-clock marker sits at `shard_timeout_minutes` read from config rather than a literal.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **This is the highest-value single addition available and it ships first on the route.** It decides whether a slow day was the work or the machine - a question that is unanswerable today and that every other performance claim on the site depends on. | Susan |
  | 2 | Each row: shard number; a stacked horizontal bar of seconds reading against seconds writing; read speed in prompt tokens a second; the processor as **text**; and the job clock as a `TargetBar` against the 150-minute timeout. | Susan |
  | 3 | **The shard is a visible unit, not a tooltip and not a drill-down.** A per-run aggregate averages a measured 2.30x spread into one number and reports neither end of it. | Susan |
  | 4 | Reading and writing are never one bar and never one "model seconds" figure, at any level, anywhere on the site. Read time varies 2.30x, write time 1.31x, and reading is 63.8 percent of the total - they are two different machines. | Susan |
  | 5 | The processor is carried by **text plus a mark shape**, never by hue alone. Colour is one signal and never the only one. | Jony |
  | 6 | `DotStrip` is the only new component this plan adds: positioned marks with a shape channel and an optional pairing line. It serves this row and row 17's swap comparison. | Jony |
  | 7 | **No new echarts registration.** The board is markup and `d3-scale`, which is already carried. The chunk has 2,439 B of headroom and one registration crosses it. | Carmack |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A box plot across shards | A five-number summary of 8 points hides more than it shows, and the individual shard is the actionable unit. | Jony |
  | 2 | A per-run average speed figure | It is the number that hid a 2.30x spread for four days. | Susan |
  | 3 | A host inventory - uptime, disk, memory total | The host lives 70 minutes and is destroyed. The CPU part is the one host fact that changes an answer. | Susan |

## 15 - Row #14 - Machine page: reading against writing, cache, context headroom, clocks, batching

- **Scope:** Five more panels on the machine route, all from committed counters, all using registered chart types or markup.
- **Files touched:** `frontend/src/routes/console/machine/+page.svelte`; `frontend/src/lib/charts/series.ts`; `frontend/src/lib/charts/stacked.ts`; `frontend/tests/console-machine.spec.ts` (new).
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke both themes, every panel rendering its own empty state.
- **Oracle:** For each panel, recompute its figure independently in the test from the same fixture rows and assert equality. For the clocks panel, assert the two independently sourced totals are both drawn and that their difference is printed as a percentage, not implied.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Reading against writing**: two 100-percent stacked rows, `Seconds` and `Tokens`, each printing its absolute total. Reads as "reading took 63.8 percent of the seconds and runs at 12.05 tokens a second; writing runs at 4.88, so a written token costs 2.5 times a read one." **The mismatch between the two rows is the insight and one bar cannot show it.** | Jony |
  | 2 | **Prompt cache**: stacked bar per day of tokens read against tokens served from cache, **absolute tokens and not a share** - the decision is "would a bigger cache save wall clock", and a share over a shrinking prompt is not that. Measured 41.3 percent on `2026-08-29-2` against 44.9 percent two days earlier, and nothing shows it. | Jony |
  | 3 | **No threshold marker and no health tint on the cache panel.** Nobody has agreed a floor, and a tint would invent one and publish it. | Jony |
  | 4 | **Context headroom**: a `TargetBar` per run, track is `n_ctx`, fill is `n_tokens_max`, marker at the window. Reads as "the longest thing read was 4,925 of 8,192 tokens - 60 percent." This is the panel that says whether raising the truncation cap is even possible. | Jony |
  | 5 | **Do the two clocks agree**: grouped bar per shard, the item ledger's summed seconds against the server's own totals, gap printed as a whole percent. The runtime ledger was created for exactly this check and nothing performs it on screen. They agreed to 0.037 percent on 2026-08-27. | Jony |
  | 6 | **Batching is one line of text, not a chart**: `Batching is off; every decode served one request.` It reads `1.0` on 29 of 29 rows. It earns a chart the day `n_parallel` moves. | Owner, 2026-08-30 |
  | 7 | Every server figure ships with its ceiling drawn as a marker on its own track. A counter without its ceiling is not a measurement: 4,925 means nothing without 8,192. | Susan |
  | 8 | The machine route keeps **one explanatory sentence per panel** permanently. The general rule that a heading already says what a chart measures does not hold here, because these headings name things nobody on this site has seen before. | Jony |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Cache hit rate as a share | See decision 2. | Jony |
  | 2 | A single "model seconds" figure | See row 14 decision 4. | Susan |
  | 3 | KV-cache usage ratio | Scraped at job end it is a snapshot of an idle server; `n_tokens_max` answers the decision. | Carmack |

## 16 - Row #15 - The percentile curve, per run

- **Scope:** A curve per run showing the shape of its per-item latency distribution, with percentile on the horizontal axis.
- **Files touched:** `frontend/src/lib/charts/series.ts`; `frontend/src/routes/console/machine/+page.svelte`; `frontend/src/lib/server/runtime-counters.ts`; `frontend/tests/console-percentiles.spec.ts` (new).
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, the panel refusing to draw a run below the minimum-attempts floor.
- **Oracle:** Compute p50, p90, p95 and p99 independently in the test over the same fixture rows using a stated interpolation rule, and assert every plotted point matches. State the interpolation rule in the component - two percentile definitions differ by more than the signal at n below 100.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Percentiles ship. The earlier refusal was of a different chart.** What was refused was a time series of p95, which averages away the shard. What the owner specified - percentile on the horizontal axis, value on the vertical, one curve per run, never aggregated across runs - is a distribution shape, and comparing two runs as two curves shows a tail change that no single number shows. | Owner, 2026-08-30 |
  | 2 | Percentiles are computed **per shard where the data allows and per run otherwise.** Item-health has no `shard` column today (verified 2026-08-30), so per-shard curves are only possible for rows written after row 7 lands. Until then the panel draws per-run curves and says so. | Fowler |
  | 3 | The measured quantity is `summarize_ms` per item, with `fetch_ms` and `extract_ms` available behind the shape switch from row 18. | Owner, 2026-08-30 |
  | 4 | Points at p50, p75, p90, p95 and p99, each labelled with its value. A curve with unlabelled points is a shape nobody can quote. | Jony |
  | 5 | A run below `console.min_attempts_for_rate` draws no curve and prints its count. A p99 over 4 items is the fourth item. | Susan |
  | 6 | Line type is already registered. **No new registration.** | Carmack |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A time series of p95 per day | Averages the 2.30x between-shard spread into one number, which is the variance the operator needs. | Susan |
  | 2 | A single p95 headline figure | One number cannot show a tail changing shape, which is the whole point of the panel. | Owner |
  | 3 | Percentiles across all runs pooled | Pools a host lottery. Explicitly refused by the owner. | Owner |

## 17 - Row #16 - Tokens per run, and cost at a rate the operator sets

- **Scope:** Two token charts and one cost figure, with the price per thousand tokens editable in the page and remembered.
- **Files touched:** `config/idhazh.json`; `backend/idhazh/contracts/app_config.py`; `schemas/app-config.schema.json`; `frontend/src/routes/console/machine/+page.svelte`; `frontend/src/lib/components/RateControl.svelte` (new); `frontend/src/lib/charts/series.ts`; `frontend/tests/console-cost.spec.ts` (new); `docs/concepts/design-system.md`.
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, the page rendering the token charts correctly with JavaScript disabled and the cost figure showing its default rate.
- **Oracle:** Type a new rate into the control, assert every cost figure on the page redraws to `tokens * rate / 1000` within a stated rounding, reload the page and assert the typed rate survives. Assert the default comes from config and not from a literal.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Two charts, not one**: input tokens per run and output tokens per run, horizontal axis the run, vertical axis tokens. They are different quantities with different rates and a shared axis would lie about one of them. | Owner, 2026-08-30 |
  | 2 | **Cost ships, over Rule #10, by owner exception.** Row 10 amends CLAUDE.md in the same wave. | Owner, 2026-08-30 |
  | 3 | **It is labelled a counterfactual, never a bill**: what this run would have cost at a hosted provider's price. The wall clock is the real budget and it is drawn elsewhere; this figure answers whether the self-hosted design is worth that wall clock, which nothing else on the site answers. | Owner and Fowler |
  | 4 | Two default rates - one for input tokens, one for output tokens - live in `config/idhazh.json` under `observability`, per thousand tokens, with the currency named. No literal in the component (Rule #6). | Fowler |
  | 5 | The operator can type a different rate in the panel. It is stored in `localStorage`, read on mount and never during prerender, so first paint always matches the prerendered document. Every cost figure on the page redraws from one shared value. | Jony |
  | 6 | The control prints the rate it is using and where it came from - `Using your rate` or `Using the configured rate` - because a money figure whose basis is invisible is the exact thing Rule #10 is about. | Susan |
  | 7 | Cost is on the **Machine** route beside the token charts, not on Pipelines and not on Model. It is a property of the work the machine did. | Jony |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A hardcoded provider price | Prices move monthly and a stale price is a wrong number with no way to correct it. | Fowler |
  | 2 | Presenting it as a bill | We are not billed. A counterfactual is the true framing and the true framing is also the more useful one. | Owner |
  | 3 | Shipping it without amending the contract | Section 0 requires the amendment in the same commit. | Fowler |

## 18 - Row #17 - Model page: the eleven cards, per-item cost, the swap comparison, compression per run

- **Scope:** The model layer becomes its own route with the protected copy intact, plus three new panels.
- **Files touched:** `frontend/src/routes/console/model/+page.svelte` and `+page.server.ts`; `frontend/src/lib/server/model-work.ts`; `frontend/src/lib/components/CompressionScatter.svelte`; `frontend/src/lib/charts/series.ts`; `frontend/tests/console-model.spec.ts`.
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, all eleven labels present verbatim, the daily table reachable.
- **Oracle:** Assert the eleven card labels are byte-identical to the eleven strings in `COLUMNS`. Assert the compression panel draws exactly one low, one median and one high mark per run and no per-item marks at all.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The eleven measure cards move here as the route's front page. **The label copy is protected and ships verbatim**, all eleven lines. The daily table stays behind a `Show the daily figures` control. | Owner, prior ruling |
  | 2 | **Compression is drawn per run as low, median and high - never per item.** The 2,740-mark scatter renders its dense region as a solid block and hides the outliers, which are the only actionable marks on it. Three marks a run answers the question the block was hiding. | Owner, 2026-08-30 |
  | 3 | The target band's bounds print as numbers beside the chart. A shaded band with no printed bound cannot be checked. | Susan |
  | 4 | **Per-item cost distributed**: a log-binned histogram of time to write one summary, with a cumulative curve on a second axis and rules at the median and the 95th. Reads as "half the articles are written inside 41 s; one in twenty takes over 190." Bars and a line - **both already registered**. | Jony |
  | 5 | **Did a model swap move anything**: paired dot rows, one per measure, two dots joined by a line with an arrowhead at the "after" end, centred on 1.0 so seven different units share one axis. Direction is carried by the arrow, never by hue, and both absolute values print on the row label. | Jony |
  | 6 | A swap panel prints the article count on both sides and draws nothing when either side is below `console.min_attempts_for_rate`. Two models over two article sets is two measurements, not a trend. | Andre |
  | 7 | **No health tint on any card.** Copied-not-rewritten at 12 percent has no agreed threshold and a tint would invent one and publish it. | Susan |
  | 8 | `hhem` never prints as a number on any route. The band is its consequence and the band already prints. | Jony |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keeping the per-item compression scatter | A solid block of 2,740 marks in one colour. | Owner |
  | 2 | A single combined chart of all eleven measures | Eleven series with four different units is unreadable at any size. | Jony |
  | 3 | Dropping cards to narrow the page | Every measure is one the owner asked for. The container was wrong, not the count. | Susan |

## 19 - Row #18 - Chart chrome: a sentence per chart, a hover readout, and a shape switch where it is cheap

- **Scope:** Every chart on all three routes gains a one-sentence reading guide, a hover and keyboard readout, and - where and only where the data already fits both shapes - a control to switch between stacked bars and lines.
- **Files touched:** every console component touched by rows 13-17; `frontend/src/lib/charts/frame.ts`; `frontend/src/lib/components/ShapeSwitch.svelte` (new); `docs/concepts/design-system.md`.
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, keyboard traversal reaching every point, every chart retaining a non-empty accessible description.
- **Oracle:** Assert every chart has a visible sentence AND an `aria-label` or `aria-describedby` resolving to non-empty text. For every chart carrying the shape switch, assert both shapes render from the identical data array with no re-shaping step - the presence of a transform is the definition of "not cheap" and fails the row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Every chart carries one sentence saying what to read off it.** This is the sentence written in the chart tables of this plan, shipped as page copy, so a reader who cannot interpret the shape can read the answer. | Owner, 2026-08-30 |
  | 2 | Every chart carries a hover and keyboard readout showing the date and every series value at the hovered column at once. The existing `pointerReadout` helper already handles mouse, pen, touch and keyboard with nearest-by-x and is reused, not rewritten. | Fowler |
  | 3 | The readout is a fixed strip below the plot, never a floating box over it, and is capped at one third of the plot width. A floating box was measured at 40 to 55 percent occlusion of the chart it explains. | Jony |
  | 4 | **The shape switch ships only where the same array draws both shapes with no transform.** That is the token charts, the stage-time chart and the cache chart. Anywhere it would need the data massaged, it does not ship - that is the owner's own test and it is the acceptance rule. | Owner, 2026-08-30 |
  | 5 | One shared control, one shared state, per panel. Not a global preference and not one control per series. | Jony |
  | 6 | A tooltip is never the only place a value appears. The readout strip carries it, and a tooltip does not fire reliably on touch. | Jony |
  | 7 | Prose cut from any visible page still lives in the accessible description, so a screen-reader user loses nothing. | Jony |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A shape switch on every chart | A Sankey is not a line and a histogram is not a stacked bar. Forcing the control everywhere means massaging data to fit, which the owner ruled out. | Owner |
  | 2 | A floating tooltip that dodges the cursor | Dodging moves the thing being read. | Jony |
  | 3 | Scrubbing the explanatory sentences | On the machine route the headings name things nobody on this site has seen. | Jony |

## 20 - Row #19 - Empty, partial and off states, written before the loaded one

- **Scope:** Every panel on every route specifies what it shows when nothing was measured, when measurement was sampled, and when it was switched off.
- **Files touched:** every console component; `frontend/tests/console-degraded.spec.ts` (new); `docs/concepts/design-system.md`.
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke with each of the three toggles off in turn, browser smoke at a sample rate below 1.0, and the page rendering with `STATE_ROOT` pointed at an empty tree.
- **Oracle:** For every panel, drive each of the four states and assert the rendered text matches the specified string exactly. Assert **no panel prints `0` in any state where the ledger holds no answer** - grep the rendered DOM for a zero inside a figure slot whose source row is absent. That check is the row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The degraded state is the normal case, not the exception.** `job_seconds` and `cpu_model` are populated on 4 of 29 rows - 14 percent. If those states are not designed, most of the machine route is undesigned. | Susan |
  | 2 | **The empty state is the panel, not a replacement for it.** Heading and explanatory sentence stay; only the figure changes. A panel that vanishes teaches the operator the measurement does not exist. | Jony |
  | 3 | A dash where the ledger holds no answer, never a zero. `<1` where a real measurement rounds away. The denominator beside every share. All three already doctrine; this row applies them to the new panels. | Susan |
  | 4 | **Measurement off**, exact string: `Measurement is off. Nothing has been recorded since 29 Aug 2026, so the figures below stop on that day. Turn it back on in config/idhazh.json.` | Susan |
  | 5 | **Sampled below 1.0**, exact string: `Measured on 1 run in 4. These figures count the runs we measured and are not scaled up to stand for the rest.` Where the rate is not a clean fraction, the same sentence with a percentage. | Susan |
  | 6 | **Counters but no scores**, exact string: `The machine ran and we timed it. Nothing scored the summaries, so this day has no quality figure.` | Susan |
  | 7 | **Scores but no counters** - the state 86 percent of committed rows are in - exact string: `The summaries were scored, but the server's own counters were not written down for this day. The speed figures here come from the summariser, not the server.` | Susan |
  | 8 | **Recording started mid-window**, exact string: `Recording started on 29 Aug 2026. The 4 days before it have no server figures, and the gap in the chart is a gap in the recording, not a quiet day.` | Susan |
  | 9 | **The machine route ships mostly empty and that is correct.** It says so once at the top and every panel says its own version underneath. A route that hid itself until it had data would be a route nobody knew to check. | Susan |
  | 10 | No string is apologetic and none is styled as an error. Each states a fact about the recording, at body size, in the panel it governs - never a banner across the page. And no string names a config key as if it were a word - `Measurement is off`, never `score_items is false`. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Hiding a panel with no data | The operator cannot tell a missing panel from a measurement that does not exist. | Jony |
  | 2 | Printing `0` for an absent measurement | Zero says the thing happened and measured nothing. It is the one number nobody checks. | Susan |
  | 3 | One banner for the whole page | Three panels can be in three different states on one day. | Susan |

## 21 - Row #20 - Field descriptions for the four columns the owner kept

- **Scope:** Four columns stay. Each gains a description saying exactly what it holds and how it should be read, so the next reader does not have to re-derive it.
- **Files touched:** `backend/idhazh/contracts/eval_row.py`; `backend/idhazh/contracts/summary.py`; `schemas/eval-row.schema.json`; `schemas/summary.schema.json`; `docs/concepts/evaluation.md`; `docs/architecture/publishing/telemetry-series.md`; `frontend/src/routes/console/+page.server.ts`.
- **Acceptance gates:** `ruff`, `mypy --strict`, drift byte-identical, full `pytest`.
- **Oracle:** Assert every one of the four fields has a non-empty description naming its unit and its reader. Assert `score_ms` no longer appears in the Pipelines route's critical-path timing table and does appear on the Model route.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **`attempt` stays.** The owner may use it. Its description says plainly: the summarize attempt number for this row; it is `1` on every row ever written because no caller passes anything else, and it is reserved for a retry budget that does not exist yet. A reader must not mistake a constant for a measurement. | Owner, 2026-08-30 |
  | 2 | **`score_ms` stays, and here is what it is**: the milliseconds the faithfulness scorer spent on this one item, after the summary was written. It is not on the pipeline's critical path. Its stated purpose is to size one decision - whether the scorer can stay a census or has to become a sample - which is exactly the decision row 2 implements, so it is the instrument behind the sampling knob. | Owner and Andre |
  | 3 | `score_ms` **moves off the Pipelines route's timing table onto the Model route.** Sitting beside fetch, extract and summarize it implies the scorer is on the critical path, and a fourth bar makes it look like a constraint. Nothing is deleted. | Andre |
  | 4 | **`hhem_delta` stays.** Its description records that it is `hhem - hhem_full`, that a validator recomputes it on every read and raises if the stored cell disagrees, and that it is 0.0 on an uncut item by construction. It also records the open problem: a 3-window article scores 0.40 lower than the same article read whole, against bands at 0.80 and 0.50, so the window geometry is wider than the whole medium band and the number is confounded until that settles. | Owner and Andre |
  | 5 | **`truncation_flagged` stays as a column, and nothing reads it.** Here is the full answer the owner asked for, in plain terms. What it was meant to say: extract cut this article short before the model read it. What it actually said until 2026-08-29: the gap between two faithfulness scores crossed a configured threshold. Those are two different facts. Measured 2026-08-28 over all 2,683 committed rows: it is true on **0 of the 22 genuinely cut rows**, and true on exactly **one row in the whole ledger** - a row that read 748 words of a 748-word article and was never cut at all. **"Expensive" means this**: because it changed meaning on a fixed date, every reader must branch on the row's own `version` stamp, which costs a hard-coded `CUT_FLAG_MEANS_A_CUT_FROM` constant in the frontend, a section of `telemetry-series.md` to explain it, and a permanent trap for anybody who queries the column without the branch. The replacement costs nothing: `source_word_count > source_seen_word_count` is true exactly when the body was cut, on every row carrying both, with no branch. So the column is kept for history and the cut test reads the word-count pair. | Owner and Fowler |
  | 6 | The one caveat on decision 5, stated so nobody is surprised: 142 of 2,683 rows carry a null `source_word_count`, so the pair is unknown there too. Unknown is printed as unknown, not as uncut. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Deleting any of the four | Refused by the owner on 2026-08-30. Keeping a column nothing reads costs nothing; deleting one costs a migration and five fixtures. | Owner |
  | 2 | Leaving the descriptions as they are | The owner had to ask what two of them meant. That is the definition of a description that is not doing its job. | Fowler |

## 22 - Row #21 - Closure: re-baseline three routes, record every ruling, delete this plan

- **Scope:** Re-derive every byte number this plan moved, re-measure all three routes, and write the rulings into the living docs.
- **Files touched:** `frontend/bundle-baseline.json`; `config/idhazh.json`; `docs/concepts/design-system.md`; `docs/architecture/publishing/frontend.md`; `docs/architecture/publishing/telemetry-series.md`; `docs/concepts/telemetry.md`; `docs/reference/measurements.md`; `docs/reference/agent-notes.md`; `TODO/20260830-observability-plan.md` (deleted at closure).
- **Acceptance gates:** full `pytest`, `ruff`, `mypy --strict`, drift gate, `svelte-check`, full browser suite, page-weight gate green against three re-derived ceilings.
- **Oracle:** Build five times, take the **heaviest** per route, and assert the recorded baseline equals it. A mean fires on half of all builds; the heaviest is the only value a gate can hold.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Baselines are re-derived only after every sibling row has merged, with the merged sha recorded next to each number. A ceiling set from a stacked branch is stale the moment its parent lands, and that mistake has fired here before. | Carmack |
  | 2 | **The first-load ratchet is read from CI, never from a developer machine.** A local Windows build does not reproduce CI's Linux install inside the 64 B tolerance, in either direction. Push, read the number CI prints, commit that. | Carmack |
  | 3 | Three ceiling keys are set, and the machine route's inlined ledger is measured against its own. If it does not fit, the route moves to month-shard fetching through the existing viewport path. | Carmack |
  | 4 | Every number carries hardware, date and spread (Rule #10). The counterfactual cost figure carries its rate and the date the rate was taken. | Fowler |
  | 5 | Tool lessons that no row could file are written into `docs/reference/agent-notes.md` here. A worker cannot edit a file outside its row's list, so the lessons pile up in private memory and die there unless the closure pays them off. Every worker is briefed to report what it could not file. | Fowler |
  | 6 | The console page height is re-measured against the 8,794px baseline and reported honestly whether or not it improved, per route. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Re-baselining inside each row | Twenty partial baselines, nineteen of them wrong the moment the next row merges. | Carmack |
  | 2 | Measuring the ratchet locally | Measured both directions on this repository: local reads have been 40 to 46 B off CI's on the same commit. | Carmack |

## See also

- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan stamps.
- [docs/concepts/telemetry.md](../docs/concepts/telemetry.md) - the event envelope row 10 corrects and the no-network-sink doctrine row 9 works inside.
- [docs/concepts/evaluation.md](../docs/concepts/evaluation.md) - the counterweights and the census-versus-sample question row 2 answers.
- [docs/architecture/publishing/telemetry-series.md](../docs/architecture/publishing/telemetry-series.md) - the published projection this plan does not widen.
- [docs/concepts/design-system.md](../docs/concepts/design-system.md) - the figure-labelling and sufficiency rules rows 18 and 19 apply.
- [CLAUDE.md](../CLAUDE.md) - section 0 (owner approval and same-commit amendment), section 6 (correction levels), section 11 (schema versioning), Rules #1, #2, #6, #10, #11.
