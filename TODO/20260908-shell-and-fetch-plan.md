# Shell And Fetch - one document, every panel fetched, nothing that grows with the archive

**Last Updated**: 2026-09-08
**Level**: 5 (core design, persisted contracts, and the trust boundary). Design consultation is
complete; section 0a records the eleven owner rulings and no row re-opens one.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 2; honor the ESCALATE triggers in section 0.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The build carries what no reader gets: 110.65 MB across 751 files growing 1.69 MB and 5.71 documents a published day, one operator page inlining 3,374 KB of ledger rows, 22.59 MiB of encoder weights in git, and eleven functions reading the whole archive on every build |
| Hard scope - in | One document serving every URL; the console fetching windowed payloads instead of inlining rows; the verdict band as its own first payload; three distinct states for quiet, missing and unreachable; bounding every read whose cost rises when a run appends a day; the model weights leaving the repository behind a digest manifest; deleting the two global build stamps; the gate and CI changes all of that forces; and the five build-cost findings of the superseded `20260908-build-reuse-plan.md` draft |
| Hard scope - out | A prerendered document for any dated or topic route. Any deployment, build or commit manifest. Any all-time count on any surface. The 20.64 MiB ONNX runtime under `frontend/static/assist/wasm/` - Hugging Face is a model hub and does not host it, so it stays same-origin. Caching the built site between CI runs (section 24 row 1). A reader-facing first-paint measurement (owner, 2026-09-08) |
| ESCALATE triggers | 1. Row 8's inventory finds a console dataset whose browser-safe projection needs a product decision about what a panel means. 2. Row 15 cannot read a GitHub Release asset cross-origin from a real browser, which kills the failover leg. 3. Row 15 cannot resolve a 40-hex commit SHA for the upstream encoder repository, which kills `assist.model_revision`. 4. Row 18 finds the `browser` CI job past 70 pct of its 25-minute timeout. 5. Any row would make a green certify a tree it did not test |
| Chosen strategy | Measure first, bound what exists, mint every contract before any consumer, then migrate. Every row ships green alone. Fowler ruled the row split and the dispatch map; Carmack ruled the cost model; Andre ruled the encoder sequence; Susan ruled the console surface |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2. Section 1a is the dispatch map and section 1b proves no two rows in one group touch one file |

## 0a. Owner rulings this plan executes

| # | Ruling | Date |
| --- | --- | --- |
| D1 | No prerendered document for any dated or topic route | 2026-09-08 |
| D2 | Shell plus fetch is the golden principle and admits no special case, on the home page and the console alike. Overrides Susan's veto on the verdict band; row 11 carries the agreed mitigation | 2026-09-08 |
| D3 | No spinner. Reserved boxes plus one late shimmer, in phase across every panel | 2026-09-08 |
| D4 | An empty chart draws its frame and ticks and no numbers | 2026-09-08 |
| D5 | Panels fill in document order, never arrival order | 2026-09-08 |
| D6 | A window spanning present and absent data plots what exists and marks the rest. Quiet, missing and unreachable are three states | 2026-09-08 |
| D7 | The console carries one line saying its panels need JavaScript, removed on mount | 2026-09-08 |
| D8 | No commit stamp, no build date, no manifest to fetch one from | 2026-09-08 |
| D9 | No all-time count of anything, anywhere | 2026-09-08 |
| D10 | The model weights fetch from Hugging Face at a pinned revision with our own GitHub Release asset as failover | 2026-09-08 |
| D11 | Losing the link preview card is accepted. A dated URL reached by in-app navigation never touches the server, so client-side routing is unaffected; only a cold direct load takes the fallback, and it renders. Search-engine indexing of dated URLs is accepted as lost - this project is built for readers, not crawlers | 2026-09-08 |

## 0b. What changed in this revision

Fowler audited the previous draft against the source and found thirty-five defects that would have
made a worker produce a wrong or broken result, plus forty facts the draft sent a worker away to
discover. All are folded in. The five that would have cost the most:

| # | The defect | What it would have cost |
| --- | --- | --- |
| 1 | Row 4 said to delete the `assertBuild` call at line 332. That line is the **only** assignment to `testedBuild` | `test:changed` throws `The build changed while browser checks were running.` on every browser run and writes no build record. The row's own stated saving was 16 s; the cost was the developer loop |
| 2 | Rows 11 and 12 both edit `frontend/src/routes/console/+layout.svelte`, which **does not exist** | Two workers invent two different files in one parallel group |
| 3 | Row 6 said `console/model/` and `console/machine/` were already correct and must not be touched. Both call `evalRows()` and `itemHealthRows()`, which read every shard | Either the row fails `npm run check` or its own oracle fails, because the pages still read the whole ledger and filter afterwards |
| 4 | Row 10 moves 32 charts to the browser and named none of the seven browser specs that assert chart markup is in the prerendered document | Seven specs go red at once and the row cannot ship green alone |
| 5 | Rows 2 and 3 sat in one parallel group and both edit `.github/workflows/digest.yml` | Two worktrees rebasing one YAML file - the exact hazard row 7 was split out to avoid |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Measure the migrated tree and the two wire costs | - | A | LANDED | - | #527 | worker |
| 2 | The parcel carries the day, not the archive | - | A | LANDED | - | #523 | worker |
| 4 | One verification call, and it is the one that assigns | - | A | LANDED | - | #524 | worker |
| 5 | Stage only what changed | - | A | LANDED | - | #526 | worker |
| 3 | Rebuild only when the push was rebased | 2 | B | PENDING | - | - | - |
| 6 | Bound the eleven archive reads | - | B | IN-FLIGHT | yi-s06-bound | - | worker |
| 13 | The page carries nothing a later run can change | - | B | IN-FLIGHT | yi-s13-stamps | #531 | worker |
| 15 | Publish the Release asset, pin the revision, prove it cross-origin | 1 | B | PENDING | - | - | - |
| 7 | The console stops claiming "never" | 6 | C | PENDING | - | - | - |
| 8 | Inventory and mint every console payload contract | 6 | C | PENDING | - | - | - |
| 9 | The producer writes the console its payloads | 8 | D | PENDING | - | - | - |
| 10 | The console fetches instead of inlining | 9 | E | PENDING | - | - | - |
| 16 | Two origins, a digest manifest, and one guard that still works | 8, 15 | E | PENDING | - | - | - |
| 11 | The verdict band arrives first and alone | 10 | F | PENDING | - | - | - |
| 12 | The console surface: reserved shape and three states | 10, 11 | G | PENDING | - | - | - |
| 14 | One document serves every date | 13 | G | PENDING | - | - | - |
| 17 | Delete the committed weights | 16 | G | PENDING | - | - | - |
| 18 | The gates measure a shell, not a document | 12, 14, 17 | H | PENDING | - | - | - |
| 19 | Record what was decided and what it cost | 1-18 | I | PENDING | - | - | - |

## 1a. Dispatch map

One PR per row. The orchestrator creates the worktree, the branch and the PR from this table and
invents none of the three. Re-read this plan from `origin/main` after every merge.

| # | Worktree | Branch | PR title |
| --- | --- | --- | --- |
| 1 | `yi-s01-measure` | `perf/measure-migrated-tree` | Measure the migrated tree and the two wire costs |
| 2 | `yi-s02-parcel` | `perf/visuals-artifact-carries-the-day` | The visuals parcel carries the day, not the archive |
| 4 | `yi-s04-verify` | `perf/one-verification-call` | One verification call, and it is the one that assigns |
| 5 | `yi-s05-stage` | `perf/stage-only-what-changed` | Stage only the files that changed |
| 3 | `yi-s03-rebuild` | `perf/rebuild-only-when-rebased` | Rebuild the site only when the push was rebased |
| 6 | `yi-s06-bound` | `perf/bound-the-archive-reads` | Bound the eleven reads that grow with the archive |
| 13 | `yi-s13-stamps` | `fix/page-carries-nothing-mutable` | The page carries nothing a later run can change |
| 15 | `yi-s15-origin` | `feat/encoder-failover-origin` | Publish the encoder release asset and pin the revision |
| 7 | `yi-s07-window` | `fix/console-claims-the-window` | The console claims the window, not the record |
| 8 | `yi-s08-contracts` | `feat/console-payload-contracts` | Mint a contract for every console payload |
| 9 | `yi-s09-producer` | `feat/console-payload-producer` | The producer writes the console its payloads |
| 10 | `yi-s10-fetch` | `feat/console-fetches-its-payloads` | The console fetches instead of inlining |
| 16 | `yi-s16-weights` | `feat/fetch-weights-with-a-digest` | Fetch the weights from two origins behind a digest manifest |
| 11 | `yi-s11-band` | `feat/verdict-band-arrives-first` | The verdict band arrives first and alone |
| 12 | `yi-s12-surface` | `feat/console-reserved-shape` | Reserved shape and three data states for the console |
| 14 | `yi-s14-shell` | `feat/one-document-every-date` | One document serves every date |
| 17 | `yi-s17-delete` | `feat/delete-committed-weights` | Delete the committed encoder weights |
| 18 | `yi-s18-gates` | `fix/gates-measure-a-shell` | The gates measure a shell, not a document |
| 19 | `yi-s19-docs` | `docs/shell-and-fetch-closure` | Record what the shell migration decided and what it cost |

## 1b. Collision proof

No two rows in one parallel group touch one file. This table is the evidence, and a row that grows
its file list past this table must re-check it before dispatch.

| Group | Rows | Files each row owns, exclusively within the group |
| --- | --- | --- |
| A | 1, 2, 4, 5 | 1: `.github/workflows/measure-migrated-tree.yml` (new), `docs/reference/measurements.md`. 2: `.github/workflows/digest.yml`, `backend/tests/test_workflows.py`. 4: `frontend/scripts/run-checks.ts`. 5: `frontend/scripts/copy-visuals.mjs` |
| B | 3, 6, 13, 15 | 3: `.github/workflows/digest.yml`, `.github/scripts/commit-and-push.sh`, `backend/tests/test_workflows.py`. 6: `frontend/src/lib/server/payload.ts`, `console-shell.ts`, the three console `+page.server.ts`. 13: `frontend/src/routes/+layout.server.ts`, `SiteFooter.svelte`, `vite.config.ts`, three components, two specs, three docs. 15: a GitHub Release, `docs/reference/measurements.md` |
| C | 7, 8 | 7: `console/+page.svelte`, `console/+page.server.ts`, `console-shell.ts`, three console specs. 8: `backend/idhazh/contracts/`, `schemas/`, `config/idhazh.json`, `frontend/src/lib/server/config.ts`, `appearance-config.spec.ts` |
| D | 9 | sole row |
| E | 10, 16 | 10: the three console `+page.server.ts`, `console/+layout.server.ts`, `console-shell.ts`, `console/+page.svelte`, `chart-render.ts`, `frontend/src/lib/charts/`, seven specs. 16: `frontend/src/lib/assist/`, `svelte.config.js`, `asset-base.js`, `embed.py`, `assemble.py`, `service-worker.ts`, `ArchiveSearch.svelte`, three specs, `search-index.schema.json`, `config/idhazh.json` |
| F | 11 | sole row. Creates `frontend/src/routes/console/+layout.svelte` |
| G | 12, 14, 17 | 12: `app.css`, the style tokens, `WindowControl.svelte`, `console/+layout.svelte`, `config/appearance.json`, `appearance_config.py`, `console-window.spec.ts`. 14: `frontend/src/routes/` outside `console/`, `svelte.config.js`, `prerender-guard.js`, `service-worker.ts`, `config/idhazh.json`, ten specs. 17: `frontend/static/assist/models/`, `backend/tests/test_embed.py` |
| H | 18 | sole row |
| I | 19 | sole row |

Two files are touched by rows in different groups, which is sequential and safe: `docs/reference/measurements.md` (rows 1, 15, 18, 19) and `config/idhazh.json` (rows 8, 14, 16, 18, 19). `frontend/svelte.config.js` and `frontend/src/service-worker.ts` are touched by row 16 in group E and row 14 in group G, in that order.

---

## 2. Measured baseline

Figures dated 2026-09-08 against `main` at `e89d6d8f`. Runner figures come from the GitHub Actions
API on `ubuntu-latest`. Laptop figures are Intel Core i7-1265U / Windows 11 / node 24.12.0, warm,
n = 1. Laptop overstates the runner by about 4.1x on a whole build (99.4 s against 24 s), and by
more on a file walk; no row may reason across the two arms without naming which it measures.

| Fact | Value |
| --- | --- |
| Built site | 110.65 MB / 751 files at 19 published days; 87 MB / 36 pages at 5 days |
| Growth | 1.69 MB and 5.71 documents per published day |
| Dated and topic documents | 110 files, 9.54 MB - 0.502 MB per published day of the slope |
| `frontend/static/assist/` total | 45,328,441 B = 43.23 MiB, 8 files, all tracked |
| - `assist/models/` | 23,687,938 B = 22.59 MiB, 6 files. Leaves, minus `PROVENANCE.md` at 2,766 B |
| - `assist/wasm/` | 21,640,503 B = 20.64 MiB, 2 files. **Stays.** `loader.ts` points `wasmPaths` at `${base}/assist/wasm/`; Hugging Face does not host our ONNX runtime |
| Post-migration site, estimate | 110.65 - 9.54 - 22.59 = **about 78.5 MB**. Row 1 replaces this with a measurement |
| Post-migration slope, estimate | **1.19 MB/day**. Byte growth does not stop; document growth does |
| Days to the 800 MB alarm | 408 today; about 606 after. **The win is roughly 200 days of runway**, not a percentage of the artifact |
| `console/index.html` | 3,726 KB - inlined payload 3,374 KB (90.6 pct), markup 351 KB, 32 inline SVG 139 KB (3.7 pct) |
| Inside that payload | `source` 28,486 times, `stage` 9,490, `run_id` 9,383 - about 9,400 telemetry rows |
| First-search wire cost today | 21.6 MB gzipped from one origin - 16.22 model + 0.21 tokenizer + 5.18 runtime |
| Site builds per publish | 3: 21 s, 19 s, 24 s. Only the third is published |
| Pages build step over time | 8.5 s at 2 published days, 13 s at 5, 21 s at 11, 24 s at 19 |
| `assertBuild()` | 16.2 s - 3.23 s input over 66.55 MB, 12.93 s output over 222.4 MB / 1,589 files |
| Output hash composition | sha256 on this class of CPU runs at 1 to 2 GB/s, so hashing 222.4 MB is about 0.2 s. **The other 98 pct is per-file syscall cost**, and `hashFiles` opens each path twice |
| Input hash scope | 66.55 MB, of which corpus 13.44, state 17.72, `frontend/public` 29.75. `inputFingerprint` **already** uses `git ls-files --cached --others --exclude-standard -z` at line 48 |
| Live artifact storage | **594.4 MB across 332 artifacts, 19 pct over the 500 MB figure in Rule #2** |
| Actions cache | 9,892 of 10,240 MB, 96.6 pct full. Restores measured 41, 44, 46 and 73 s against a 21 to 24 s build |
| `browser` CI job | 460 to 554 s of a 1,500 s timeout - 37 pct used, before six rows add specs |
| Telemetry month caps, already present | `monthCeiling(30)` = 2 files; `monthCap` holds a session to 15; `public_telemetry_keep_months` = 14 |
| Unbounded retention knobs | `item_health_aggregate_keep_months` and `score_archive_keep_months` are both `null` |
| Day payload projection | Staged copy is 468.58 bytes an item against the committed 792.65 - 40.9 pct less. 2026-08-31, 11 days, 3,733 items, gzip -9 |

## 2a. Pre-resolved facts every row may quote without checking

Verified against the working tree on 2026-09-08. A worker uses these and does not re-derive them.

**Window presets** - `config/appearance.json`, `console` block: `window_presets` is `[1, 7, 14, 30, 90]`, `default_window_days` is `30`, `min_window_days` is `1`, `max_window_days` is `366`. All three console routes share one `WindowControl.svelte`, so **the widest preset is 90 on every console surface.** `max_window_days` = 366 bounds only `monthCap` at `console/+page.svelte` L117 and is **not** a read window.

**Page ceilings** - `config/idhazh.json` `page_weight.ceilings_bytes` is `{"/404": 1706, "/archive/": 7553, "/console/": 335051, "/console/machine/": 44706, "/console/model/": 56385, "/evals/": 3279}`. There is no entry for `/` and none for any dated route, which is why the migration removes no key. `frontend/scripts/bundle-gate.mjs` L120 compresses at `{ level: 9 }`; every value above was measured at -9.

**Retention knobs** - `config/idhazh.json` `observability`: `feed_health_keep_months` 14, `public_telemetry_keep_months` 14, `item_health_aggregate_keep_months` **null**, `score_archive_keep_months` **null**.

**The commit allow-list** - `.github/workflows/digest.yml`, the `Commit the day` step, env var `REFRESH_PATHS`, currently ten entries: `${{ needs.plan.outputs.day_dir }}/digest.json`, `${{ needs.plan.outputs.day_dir }}/run.json`, `frontend/public/telemetry`, `frontend/public/assist/index`, `frontend/public/source-health.json`, `state/published`, `state/scores`, `state/score-index`, `state/item-health`, `state/runtime-counters.csv`. The identical list is mirrored in `backend/tests/test_workflows.py` as `COMMIT_REFRESH_PATHS['assemble']` and asserted by exact list equality. **Both copies move together or the row is red.**

**`payload.ts` reads, by line.** Growing: `publishedDates` L84, `latestDate` L144, `evalRows` L354, `readShards` L363, `itemHealthRows` L378, `telemetryMonths` L500, `indexMonths` L513, `feedResults` L604, `loadManifests` L730, `publishedItems` L786, `publishedCharts` L815. Already bounded and the pattern to copy: `dayMetrics(dates, root)` L449, `telemetryRows(root, windowDays)` L557 - both cite Rule #12 in their own comments. Constant and out of scope: `loadDay` L117, `dayShell` L244, `readCsv` L338, `itemHealthForDay` L395, `sourceHealthView` L666.

**The encoder on disk** - `frontend/static/assist/models/all-minilm-l6-v2-quantized/2026-08-22/`. Upstream is `Xenova/all-MiniLM-L6-v2`, derived from `sentence-transformers/all-MiniLM-L6-v2`, Apache-2.0, fetched 2026-08-22. **`PROVENANCE.md` records no commit SHA**, which is why row 15 has to resolve one and ESCALATE trigger 3 exists. SHA-256, computed 2026-09-08 and to be written verbatim into `assist.model_digests`:

  | Path under the version directory | Bytes | SHA-256 |
  | --- | --- | --- |
  | `config.json` | 650 | `7135149f7cffa1a573466c6e4d8423ed73b62fd2332c575bf738a0d033f70df7` |
  | `special_tokens_map.json` | 125 | `b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3` |
  | `tokenizer_config.json` | 366 | `9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3` |
  | `tokenizer.json` | 711,661 | `da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0` |
  | `onnx/model_quantized.onnx` | 22,972,370 | `afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1` |

**The three loader lines that make a remote fetch impossible today** - `frontend/src/lib/assist/loader.ts` L155 `transformers.env.allowRemoteModels = false`, L156 `allowLocalModels = true`, L157 `localModelPath = ${base}/assist/models/`. `cachedEncoder()` is L108. `DOWNLOAD_MB = 43` is L55.

**The reduced-motion rule** - `frontend/src/styles/app.css` L394, `@media (prefers-reduced-motion: reduce)` sets `animation-duration: 0.01ms !important` and `transition-duration: 0.01ms !important` on `*`, `*::before` and `*::after`.

**The motion and state names already written down** - `docs/concepts/design-system.md` L23 names the state classes `loading`, `empty`, `degraded`, `truncated`, `low-confidence`; L471 names the whole motion set `fadeIn`, `shimmer`, `toastIn`, with `shimmer` glossed "skeleton while a payload parses". Neither `shimmer` nor `loading` exists in CSS today.

**Strings this plan deletes or rewrites, quoted from source.**

  | Where | Line | Current text |
  | --- | --- | --- |
  | `SiteFooter.svelte` | 33 | `` `Charts older than ${facts.retention_window_months} months are deleted.` `` |
  | `SiteFooter.svelte` | 34 | `'Nothing is deleted.'` |
  | `SiteFooter.svelte` | 52-63 | `Built from git ... deployed {builtOn}. {retention}` |
  | `SiteFooter.svelte` | 67 | `Every summary is checked against the article it came from.` |
  | `WindowControl.svelte` | 46 | `` `This control needs JavaScript. Every windowed section below is showing ${days} days.` `` |
  | `console/+page.svelte` | 580 | aria-label `{noun} each day over {windowDays} days, {grouped(strip.total)} in all, ...` |
  | `console/+page.svelte` | 961 | `which read every feed the ledger has ever carried.` |
  | `console/+page.svelte` | 1106 | `{data.feedRecord.clean.length} of {data.feedRecord.checked} feeds have never failed a read,` |
  | `console/+page.svelte` | 1118 | `feeds have'} never been read at all - a rest or the site's own rules held` |
  | `console/+page.svelte` | 1127 | `Name the {data.feedRecord.ineligible.length} the pipeline has never read` |
  | `console/+page.svelte` | 1132 | `feeds that never failed reported a source we have never read as a reliable one.` |
  | `console/+page.server.ts` | 189-190 | `label: 'never read'` and `withheld: 'nothing from it has ever reached the digest'` |

**Route wiring** - `export const prerender = true` lives at `[date]/+page.server.ts` L5, `[date]/[vertical]/+page.server.ts` L5, `console/+layout.server.ts` L3, `console/+page.server.ts` L40, `console/machine/+page.server.ts` L30, `console/model/+page.server.ts` L32. The root `+layout.server.ts` and `+page.server.ts` declare neither. `frontend/src/routes/evals/` holds **only** `+page.svelte` - there is no `+page.server.ts` to put a flag in. `frontend/src/routes/console/` holds **only** `+layout.server.ts` - there is no `+layout.svelte`.

**The growing-reads convention** - `docs/concepts/growing-reads.md`: `-1` is the only sentinel for a read a person chose not to bound, and the inventory table near L207 is where a new entry goes.

---

## 3. Row #1 - Measure the migrated tree and the two wire costs

- **Scope:** Replace the two estimates this plan rests on with measurements taken on the runner, before any contract is written.
- **Files touched:**
  - `.github/workflows/measure-migrated-tree.yml` - **a new file, never `digest.yml`.** Rows 2 and 3 edit `digest.yml`; three worktrees on one YAML file is the hazard section 1b exists to prevent. Row 19 deletes this file
  - `docs/reference/measurements.md` - the results
- **Method, arm 1:** on `ubuntu-latest`, check out `main`, then:
  - `rm -rf frontend/static/assist/models`
  - `npm --prefix frontend run build`
  - `find frontend/build -maxdepth 1 -type d -regex '.*/[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}' -exec rm -rf {} +`
  - `python -m idhazh site-weight --site-tree build` with **`working-directory: frontend`**. `backend/tests/test_workflows.py::test_the_site_gate_measures_the_tree_the_deploy_uploads` derives the expected path from `working-directory` plus `--site-tree`; without the working directory the call reads a `build/` that is not there and the job dies
  - `find frontend/build -type f | wc -l`, and the same two over `frontend/.svelte-kit/output`
- **Method, arm 2:** `curl -sI -H 'Accept-Encoding: gzip' 'https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx/model_quantized.onnx'` and record `Content-Encoding` and `Content-Length`. `main` is acceptable **for this measurement only**; row 15 resolves the pinned SHA that ships.
- **Do not:** add this job to `SITE_WEIGHT_JOBS` in `backend/tests/test_workflows.py`. It deliberately measures a mutilated tree, and the gate that guards the real one must not learn about it.
- **Acceptance gates:** local - none. CI - the dispatch job runs green.
- **Oracle:** `docs/reference/measurements.md` carries a post-migration site size, file count and slope with hardware, date and n stated, plus a Hugging Face `Content-Encoding` value.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The 23.8 MB figure of the superseded draft double-counted. The day payloads, month index and telemetry are fetched from our own Pages origin, so fetching them does not remove them from the artifact | Carmack, 2026-09-08 |
| 2 | The plan's claim becomes runway in days, not a percentage of the artifact. A percentage of a number that keeps growing is not a result | Carmack, 2026-09-08 |
| 3 | Arm 2 decides whether a searching reader pays 21.6 MB or 28.9 MB. If Hugging Face serves a 23 MB octet-stream identity, that is 6.75 MB a reader does not pay today and it belongs in D10's cost record | Carmack, 2026-09-08 |
| 4 | Taken on the runner, not the laptop, because the dominant term is per-file syscall cost and that is the term differing most between the two machines | Carmack, 2026-09-08 |
| 5 | Its own workflow file, not a job inside `digest.yml`. A measurement harness that shares a file with the daily pipeline can break the daily pipeline | Fowler, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Take the measurement on the laptop | 4.1x off on a whole build and worse on a file walk | Carmack |
| 2 | Defer both measurements to the end | Row 18 and row 19 would inherit a wrong premise and close the fingerprint work on it | Carmack |

---

## 4. Row #2 - The parcel carries the day, not the archive

- **Scope:** The `visuals` artifact uploads the whole 454-file digest tree when one day is new; upload the run's day.
- **Files touched:**
  - `.github/workflows/digest.yml` - the `visuals` job `upload-artifact` `path:` block, and the `assemble` job `download-artifact` that consumes it
  - `backend/tests/test_workflows.py` - `test_the_visuals_artifact_collects_the_file_the_stage_writes` reads the `path:` block line by line and asserts the items glob survives
- **The exact change:** the `path:` block keeps **both** lines. `backend/var/run/${{ needs.plan.outputs.date }}/items/*.visual.json` is unchanged. Only `frontend/public/digest/` narrows, to `${{ needs.plan.outputs.day_dir }}/`. The `visuals` job already declares `needs: [plan, work]`, so `day_dir` resolves.
- **Why both lines stay:** a worker who rewrites the block as one narrowed line drops the items glob. The test goes red, and worse, `assemble` receives no visual decisions and the day publishes with no pictures on an otherwise green run.
- **The download side does not move:** `assemble`'s `download-artifact` uses `path: .` and the artifact root stays the repository root, because the items glob still anchors the least-common-ancestor there.
- **Acceptance gates:** local - `python -m pytest backend/tests/test_workflows.py`. CI - a full `digest.yml` dispatch produces a day identical in shape to the previous run's.
- **Oracle:** the `visuals` artifact byte size falls and the assembled day's file list is unchanged.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Sequenced first in group A. Live artifact storage is 594.4 MB against the 500 MB figure in Rule #2 - the only budget in this plan already over | Carmack, 2026-09-08 |
| 2 | The items glob is load-bearing and stays. The narrowing applies to the digest tree only | Fowler, 2026-09-08 |

---

## 5. Row #3 - Rebuild only when the push was rebased

- **Scope:** `digest.yml` builds the site before the commit and again after it; skip the second when the push was not rebased.
- **Depends on row 2** because both edit `.github/workflows/digest.yml`.
- **Files touched:**
  - `.github/workflows/digest.yml` - the `Commit the day` step (L1141) gains an `id:`; the `Rebuild the site against the tree that was pushed` step (L1265) gains an `if:`
  - `.github/scripts/commit-and-push.sh` - it writes the outcome
  - `backend/tests/test_workflows.py` - `test_the_weight_gate_reads_a_build_of_the_tree_that_was_pushed` gains the conditional case
- **The step names, verbatim, so an `if:` can be keyed off one:** `Build the site` (L1105), `Measure the built site against the Pages cap`, `Commit the day` (L1141, **no `id:` today**), `Rebuild the site against the tree that was pushed` (L1265), `Bundle gate - encoder and page ceilings` (L1280).
- **The mechanism, because none exists today:** `commit-and-push.sh` writes nothing to `$GITHUB_OUTPUT`. It only prints `push rejected, rebasing (attempt $attempt)` to stdout, and stdout is not a contract. The script gains, immediately before its `exit 0`, a write of `rebased=true|false` to `$GITHUB_OUTPUT`, guarded by `[ -n "${GITHUB_OUTPUT:-}" ]` so the pytest harness that drives it in a temp clone still runs. The rebuild step then carries `if: steps.<commit-step-id>.outputs.rebased == 'true'`.
- **The bundle gate does not move.** It stays after the commit.
- **Acceptance gates:** local - `python -m pytest backend/tests/test_workflows.py`. CI - a dispatch with no rebase skips the rebuild; a dispatch that rebases runs it.
- **Oracle:** the `assemble` job step list shows the rebuild absent on a clean push and present after a rebase.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | About 19 s per publish, five publishes a day. The pre-commit and Pages builds use different `BASE_PATH` values, so neither is ever reusable as the published artifact | Measured 2026-09-08 |
| 2 | **The gate's position does not move.** The previous draft moved it ahead of the commit; `test_the_build_gates_the_publish_and_the_weight_gate_runs_after_it` asserts `commit < gate`, and digest.yml L1268-1278 records the severity ruling that put it there. Moving it makes a page one byte over its ceiling cost the reader the whole day and the two to three hours that built it. The gate reads whichever build is newest; when the rebuild is skipped that is the pre-commit build, which is the same tree | Fowler, 2026-09-08, reversing the previous draft |
| 3 | Depends on row 2 rather than sharing group A with it. Two worktrees rebasing one YAML file is what row 7 was split out to avoid | Fowler, 2026-09-08 |

---

## 6. Row #4 - One verification call, and it is the one that assigns

- **Scope:** `run-checks.ts` calls `assertBuild` on two adjacent lines. Remove the redundancy **without** removing the assignment.
- **Files touched:** `frontend/scripts/run-checks.ts` - lines 322 and 327.
- **What the previous draft got wrong, and it would have been expensive:** it said to delete line 332. Line 332 in that draft's numbering is `testedBuild = assertBuild(root, opts.mode, env)`, the **only** assignment to `testedBuild`, which is declared at L284 and read at L341 and L351. Deleting it leaves `testedBuild` undefined, so L341 compares `JSON.stringify(undefined)` against a real record and throws `The build changed while browser checks were running.` on **every** browser run, and L351's `build: () => testedBuild` writes no build record. `test:changed` would be dead. This is ESCALATE trigger 5 - a green that certifies a tree it did not test.
- **The exact replacement:** fold the assignment into the try, and delete the bare call.

  ```
  try { testedBuild = assertBuild(root, opts.mode, env); }
  catch {
    if (opts.mode === 'canary') await run('canary fixtures', python, ['backend/utilities/build_canary_day.py']);
    await run(`${opts.mode} build`, process.execPath, [npm, 'run', opts.mode === 'canary' ? 'build:canary' : 'build'], frontend);
    testedBuild = assertBuild(root, opts.mode, env);
  }
  ```

- **The throw is preserved** because the `catch` still fires on a fresh checkout, which is the case the first call exists to detect.
- **Acceptance gates:** local - `npm --prefix frontend run test:changed -- --list`, then the selected checks, and one full `test:changed` run that reaches the browser group so L341 and L351 both execute. CI - none new.
- **Oracle:** a warm `test:changed` run issues one fewer `assertBuild` and its total falls by about 16 s, **and** the run still writes a build record.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **This is a developer-loop saving and zero in CI.** `run-checks.ts` is `test:changed`; `ci.yml` calls `check`, `test:tooling`, `test:logic`, `build`, `bundle-gate` and `test:browser` directly and never reaches it | Carmack, 2026-09-08 |
| 2 | The redundant call is the bare one, not the assigning one. Keep the assignment, keep the throw, delete the bare call | Fowler, 2026-09-08, reversing the previous draft |

---

## 7. Row #5 - Stage only what changed

- **Scope:** `copy-visuals.mjs` deletes and re-copies every staged file on every build; copy what differs.
- **Files touched:** `frontend/scripts/copy-visuals.mjs` - the three `rmSync` calls at L105 (`target`), L106 (`telemetryTarget`) and L107 (`indexTarget`), and the recursive `walk(relative)` at L140-176 that follows.
- **Acceptance gates:** local - the shared test selector. CI - none new.
- **Oracle:** two consecutive builds with no new day stage zero files on the second, and the staged tree is byte-identical to a full re-stage.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | 5.82 s locally and **zero in CI** - every CI job starts with `static/digest` absent, so the first stage is always a full one | Measured 2026-09-08 |
| 2 | The projection stays. The staged day is 468.58 bytes an item against the committed 792.65; serving the committed shape would send 40.9 pct more bytes to every reader | Measured 2026-08-31 |

---

## 8. Row #6 - Bound the eleven archive reads

- **Scope:** Give every read in `payload.ts` whose cost rises with the archive a bounded input, and update every call site.
- **Files touched:**
  - `frontend/src/lib/server/payload.ts` - the eleven reads listed in section 2a
  - `frontend/src/lib/server/console-shell.ts` - L416 `loadManifests()`, L421 `feedResults()`, L425 `publishedItems()`
  - `frontend/src/routes/console/+page.server.ts` - L551 `evalRows()`, L552 `itemHealthRows()`, L582 `loadManifests()`, L597 `feedResults()`, L615 `publishedCharts()`, L651 `publishedItems()`, L747 `telemetryMonths()`
  - `frontend/src/routes/console/model/+page.server.ts` - L79 `publishedDates()`, L113 `evalRows()`, L114 `itemHealthRows()`
  - `frontend/src/routes/console/machine/+page.server.ts` - L130 `itemHealthRows()`, L303 `evalRows()`
- **The previous draft said the model and machine pages were already correct and must not be touched. That is false.** Their "bounded to the widest preset" comments describe what is carried **into the document**, not what is read **from disk**. Both call `evalRows()` and `itemHealthRows()`, which read every shard and filter afterwards. Those comments stay true and describe a different thing; leave the comments, fix the reads.
- **The new signatures, written out so nobody designs them twice:**

  ```
  publishedDates(root, windowDays = 90)
  readShards(dir, months)          <- the bounded primitive
  evalRows(months)                 <- thin wrapper over readShards
  itemHealthRows(months)           <- thin wrapper over readShards
  feedResults(months)
  loadManifests(root, windowDays)
  publishedItems(root, windowDays)
  publishedCharts(root, windowDays)
  telemetryMonths(root, months)
  indexMonths(root, months)
  ```

- **`readShards(dir)` at L363 is exported and is the shared primitive** behind `evalRows` L354 and `itemHealthRows` L378. Bound it, or two callers get bounded and the exported helper stays unbounded for the next caller.
- **`latestDate()` at L144 is `publishedDates(root)[0]`** and needs no window of its own once `publishedDates` has one.
- **The pattern to copy, already in this file:** `telemetryRows(root, windowDays)` L557 and `dayMetrics(dates, root)` L449. Both take a bound and both cite Rule #12 in their own comments.
- **The default is 90 days / 4 months**, the widest preset any console surface offers (section 2a), so no panel loses a day it draws today.
- **Acceptance gates:** local - the shared test selector; `npm --prefix frontend run check`. CI - browser smoke on all four console routes.
- **Oracle:** build against a fixture digest root, record the console routes' wall clock, add ten days to the fixture, build again. **The time must not move.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each read's default is the widest preset its surface offers, which section 2a resolves to 90 on every console surface | This plan |
| 2 | `publishedDates()` survives row 14 - `/` builds a seven-day `recent` list from it, and `latestDate()` and the archive call it - so this row is not made dead by the shell | Fowler, 2026-09-08 |
| 3 | Row 8 depends on this one: the windows settled here decide what row 9's producer publishes | Fowler, 2026-09-08 |
| 4 | Where a read cannot be bounded, it gets an entry in `docs/concepts/growing-reads.md` naming what it reads, how the cost grows and why a bounded input cannot answer it - never a silent exception. `-1` is the only sentinel; not `0`, not `null`, not a very large number | Rule #12, and `growing-reads.md` L87 |
| 5 | Retitled from "the four archive walks". There are eleven, and a title that undercounts by seven is how seven get missed | Fowler, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Cache the walk between builds | Every CI job is a cold start, so a cache saves nothing on the authoritative arm, and it hides the growth rather than removing it | Carmack |
| 2 | Defer until the shell lands, since the console stops calling these | The work moves to the producer in row 9 and must be bounded there. Bounding here first means row 9 copies a correct function | Fowler |
| 3 | Leave the model and machine pages alone | They read the whole ledger and filter afterwards, so the row's own oracle would fail | Fowler |

---

## 9. Row #7 - The console stops claiming "never"

- **Scope:** Replace six all-time claims with the same fact over the window on screen.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte` - L580, L961, L1106, L1118, L1127, L1132, all quoted in section 2a
  - `frontend/src/routes/console/+page.server.ts` - L188-190, the `never_asked` entry in `AVAILABILITY_FACTS`
  - `frontend/src/lib/server/console-shell.ts` - the band and the strip render on all three console routes, so the fields behind those strings live here too
  - `frontend/tests/console.spec.ts` - L759 (`the disclosed names are exactly the feeds that never failed`) and L807
  - `frontend/tests/console-feeds.spec.ts` - L622, L639, L663
  - `frontend/tests/console-sources.spec.ts`
- **`sourceHealthView` is already windowed. Change nothing in it.** `SourceHealthView.min_complete_days` is `collect.source_yield_min_complete_days` = 30 and `backend/idhazh/contracts/source_health_view.py` L286 refuses `complete_dates > min_complete_days`. The `sources.reduce(...)` totals over `opportunities`, `publications` and `source_failures` on `console/+page.server.ts` are therefore already a 30-day window; "fixing" them would double-window a windowed figure and print a wrong number.
- **`view.runsRead` on the machine page already counts the window.** `machine/+page.server.ts` L158 sets `runsRead: runs.length` from a `MachineWindow` built at L201-215 over `spans = [default_window_days, ...window_presets]`, bounded at L214 to `widest` = 90. No change needed.
- **The aria-label at L580 is arithmetic that is already right and wording that is wrong.** `{grouped(strip.total)} in all` sits inside `{noun} each day over {windowDays} days`, so the total is already the window's. Change `in all` to `over the window`; do not touch the sum.
- **Replacement shape for the rest:** `No feed failed a read in these 30 days.` The window is named in the sentence and comes from the control, never hard-coded.
- **Acceptance gates:** local - the shared test selector. CI - browser smoke on all three console routes.
- **Oracle, stated mechanically because "reader-facing" cannot be graded:** a new Node-side spec beside `frontend/tests/payload-weight.spec.ts`, which already walks the build the same way, reads `build/console/index.html`, `build/console/model/index.html` and `build/console/machine/index.html`, strips `<script>` elements and every attribute value except `aria-label`, and asserts none of `never`, `ever`, `all time`, `in all` remains. Code comments and test titles are out of the stripped text by construction, which is why the previous draft's oracle could not be executed - `console.spec.ts` L702-703 and L807 carry all four words legitimately.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A sentence that can only be true by reading everything is a growing read in different clothes. Rule #12 binds what a page says, not only what it reads | Owner D9, 2026-09-08 |
| 2 | The windowed sentence is more useful, not less: a feed that broke once in August and has been clean since is permanently disqualified by "never failed", and the operator's question is whether anything is broken now | This plan |
| 3 | Separated from row 6 into group C. Both rows edit `console/+page.server.ts`, and at N = 2 that is two worktrees on one file | Fowler, 2026-09-08 |
| 4 | Six strings, not four. The previous draft missed the aria-label and the availability fact | Fowler, 2026-09-08 |

---

## 10. Row #8 - Inventory and mint every console payload contract

- **Scope:** Name every dataset the console must fetch, and mint the contract, schema and forbidden-cell list for each, before any producer or consumer is written.
- **Why this row exists:** the console loader and `console-shell.ts` between them read **ten** datasets. `telemetryRows` is one panel's data; the other nine come from `state/`, which `payload.ts` says is never served, and `PublicTelemetryRow.FORBIDDEN_COLUMNS` exists because crossing that boundary needs a contract each time.
- **The ten:**

  | Dataset | Source | Existing shape |
  | --- | --- | --- |
  | Telemetry rows | `state/telemetry/<YYYY-MM>.csv` | `schemas/public-telemetry.schema.json` **already exists** at version `2026-09-05T20:00` |
  | Verdict band | derived in `console-shell.ts` | none |
  | `evalRows` | `state/scores/` | none |
  | `itemHealthRows` | `state/item-health/` | none |
  | `feedResults` | `state/feed-health/` | none |
  | `loadManifests` | per-day `run.json` | none |
  | `publishedItems` | per-day `digest.json` | none |
  | `publishedCharts` | per-day visuals | none |
  | `sourceHealthView` | `frontend/public/source-health.json` | already published |
  | `loadMachineCounters` | `state/runtime-counters.csv` | none |

- **Files touched:**
  - `backend/idhazh/contracts/` - one model per dataset with no published shape, each with an explicit forbidden-cell list copying the named pattern in `backend/idhazh/contracts/public_telemetry.py` (`FORBIDDEN_COLUMNS`)
  - `schemas/` - generated. **Amend `public-telemetry.schema.json`; do not fork it.** New schemas stamp `version` `2026-09-08` and open a `changelog`
  - `config/idhazh.json` under `observability` - one retention knob per new monthly dataset, **each with a non-null default.** `item_health_aggregate_keep_months` and `score_archive_keep_months` are `null` today, and decision 5 exists to stop that spreading
  - `backend/idhazh/contracts/app_config.py` and `backend/idhazh/contracts/appearance_config.py` - the config models behind those knobs
  - `schemas/app-config.schema.json` **and** `schemas/appearance-config.schema.json` - both re-stamped `version: 2026-09-08` with one `changelog` entry each naming the fields added and why. `app_config.py` L3506 records that the two move together
  - `frontend/src/lib/server/config.ts` - its L209 comment states that a key in `config/appearance.json` not declared there is **dropped**. A new knob unread by the frontend is a silent no-op
  - `frontend/tests/appearance-config.spec.ts` - L132 pins the key set to a literal `DECLARED` array, asserted at L144
  - `frontend/src/contracts/` - regenerated
- **Not in this row:** the `assist.*` keys and the `search-index.schema.json` stamp. Both moved to row 16, where `model_id` actually changes meaning, so the schema's `version` is dated by the commit that changed the semantics rather than by one four rows earlier.
- **Acceptance gates:** local - `npm --prefix frontend run check`; the shared test selector; the regeneration is `python -m idhazh.contracts.export` plus the frontend half, and `run-checks.ts` L301-307 fingerprints `schemas/` before and after and throws on a diff. CI - the contract drift gate regenerates byte-identical.
- **Oracle:** `git diff --exit-code` after a regeneration run, and every dataset in the table above resolves to exactly one schema file.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The inventory is a row, not a paragraph inside the producer row. Without it, rows 9, 10, 11 and 18 each guess at the same missing list | Fowler, 2026-09-08 |
| 2 | Config owns the **origin** only. `ENCODER_ID` stays a contract constant in `encoder.ts`, which says in terms that a knob there is a way to turn the guard off by accident | Fowler and Andre, converging, 2026-09-08 |
| 3 | `item_health_aggregate_keep_months` and `score_archive_keep_months` are `null` today. Any dataset given a month payload here gets a retention knob **with a non-null default** in the same commit, or the producer grows for ever | Carmack, 2026-09-08 |
| 4 | `console.shimmer_after_ms` is minted in row 12, where it gets its measured value, not here where nothing reads it for four rows | Fowler, 2026-09-08 |
| 5 | A config knob is three artifacts, not one: the JSON, the Pydantic model plus its regenerated schema with a fresh `version` and `changelog`, and the frontend declaration in `config.ts`. Miss the third and the knob reads as absent | Fowler, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Shrink row 10's scope to telemetry and leave the nine aggregates prerendered | That is a special case, and D2 says there are none | Fowler |
| 2 | Fork a new telemetry schema rather than amend the existing one | Two schemas for one shape, and the committed shards validate against the old one | Fowler |
| 3 | Move `model_id` from constant to config, as the superseded draft proposed | It makes the guard a constant compared against a constant, and it moves the writer's string off `EMBEDDER_ID`, which is the one string `test_embed.py` pins to the TypeScript constant | Andre |
| 4 | Mint the `assist.*` keys here | Row 15 has not resolved the pinned SHA yet, and decision 2 of row 16 refuses anything but a 40-hex value. The knob would be minted empty | Fowler |

---

## 11. Row #9 - The producer writes the console its payloads

- **Scope:** The backend writes every payload row 8 minted, bounded, with nothing yet consuming them.
- **Files touched:**
  - `backend/idhazh/` - one producer module per dataset, each writing under `frontend/public/`
  - `backend/idhazh/publish_telemetry.py` - the `migrate()` carve-out named in decision 2
  - `frontend/scripts/copy-visuals.mjs` - stages the new payloads as it already stages the day payloads
  - `.github/workflows/digest.yml` - the `REFRESH_PATHS` env var on the `Commit the day` step. Its current ten entries are quoted in section 2a; the new payload roots are added beneath them
  - `backend/tests/test_workflows.py` - `COMMIT_REFRESH_PATHS['assemble']` (around L466-478) mirrors that list verbatim and is asserted by exact list equality (around L2284). **Both copies move in the same commit**
  - `backend/tests/` - producer tests from built fixtures
- **Every new payload directory ships with a committed seed file in the same commit.** `commit-and-push.sh` runs `git add "$@"` under `set -euo pipefail`, so a path that does not exist aborts the whole commit step and takes every sibling ledger staged in the same call with it. `test_every_path_the_day_stages_exists_in_a_fresh_checkout` exists for exactly this and is extended to cover the new roots. The pattern to copy is `state/feed-retirements.csv`, which ships with its header and no rows.
- **Every new payload root is derived from `DIGEST_ROOT`,** the way `INDEX_ROOT` and `SOURCE_HEALTH_PATH` are at `payload.ts` L63-79. A hard-coded `frontend/public/...` path is a defect: it makes a canary build read the real tree, and every canary assertion becomes non-deterministic.
- **Acceptance gates:** local - `python -m pytest backend/tests/test_workflows.py backend/tests/<the new tests>`. CI - `idhazh validate-days` passes; every payload validates against its schema.
- **Oracle:** run the producer twice against a fixture holding twenty months. The second run opens one month, not twenty. **Assert on file handles, not wall clock.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Monthly, not daily and not per-window. The state shards are already monthly, so the unit exists and a 30-day window is at worst two files | Read from `state/telemetry/` |
| 2 | A frozen month is written once. **Carve-out: `publish_telemetry.migrate()` may still rewrite a committed shard**, because it is what repairs a short header today. Without the carve-out every pre-migration month renders as unreachable in row 12, with a `Try again` that can never work | Fowler, 2026-09-08 |
| 3 | `parseTelemetryCsv` gains a short-header tolerance proved against a committed fixture shard, so a new bundle reads a frozen shard one column short instead of refusing the whole month. The row names the missing column, the fixture path, and what a row missing it reads as | Fowler, 2026-09-08 |
| 4 | One month per run, never a walk. The run knows which month it just wrote | Rule #12 |
| 5 | The allow-list has two copies and they are asserted equal. A payload absent from either builds locally and never reaches the site | Fowler, 2026-09-08 |

---

## 12. Row #10 - The console fetches instead of inlining

- **Scope:** The console stops serialising rows into its document and fetches the payloads row 9 writes.
- **Files touched:**
  - `frontend/src/routes/console/+page.server.ts`, `console/model/+page.server.ts`, `console/machine/+page.server.ts` - drop the ten dataset readers
  - `frontend/src/routes/console/+layout.server.ts` - the **sole** `consoleShell()` call site, and it carries its own `export const prerender = true`. That flag **stays**: it is what keeps all three console routes real documents after row 14
  - `frontend/src/lib/server/console-shell.ts` - the band's derivation moves to the producer
  - `frontend/src/routes/console/+page.svelte` - `loadVisibleMonths()`, the pending-month set and the month cap already exist. **Promote them from "widen the window" to "load the page."** This is a reuse. Fetch URLs take the `${base}/...` form L164 already uses for `${base}/telemetry/${month}.csv`
  - `frontend/src/lib/server/chart-render.ts`, `frontend/src/lib/charts/` - charts render in the browser from fetched rows
  - **The seven specs that assert chart and readout markup is in the prerendered document**, each moving from "the string is in `index.html`" to "the node is in the DOM after the payload lands": `frontend/tests/charts.spec.ts` L41 and L54, `frontend/tests/console-published.spec.ts` L302-310, `frontend/tests/console-readout.spec.ts` L339-343, `frontend/tests/console-charts-arm.spec.ts` L403, `frontend/tests/console-nav.spec.ts` L191, `frontend/tests/console-frame.spec.ts` L19, `frontend/tests/console-machine-page.spec.ts` L239
- **`console-machine-page.spec.ts` L239 carries a comment - "a prerendered operator page owes a reader every mark before a script" - that D2 overrides.** Rewrite the comment; do not delete it. A deleted rationale reads as an oversight to the next agent.
- **`console/+page.server.ts` L612 and L636 `telemetryRows(...)` are already bounded** and are the two the shell replaces last.
- **Acceptance gates:** local - the shared test selector; `npm --prefix frontend run check`. CI - browser smoke on all four console routes, each with its payload present and absent.
- **Oracle:** `console/index.html` is under 400 KB **uncompressed on disk, measured with `stat`**. It is 3,726 KB today and 351 KB of that is markup, so the target is markup plus shell and nothing else. This is a different measure from the `page_weight` gzip ceiling and does not replace it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The months list moves into the band payload.** `telemetryMonths` crosses in the document today; a shell cannot ask for a month until it knows which months exist, so leaving it out makes it a fifth serial hop | Carmack, 2026-09-08 |
| 2 | The cold-load chain is at most four hops: document, entry JS, band including the months list, month payload. Row 18 enforces it | Carmack, 2026-09-08 |
| 3 | The 32 charts move to the browser. They are 139 KB of 3,726 KB, so this is not where the bytes are - it moves because a chart drawn from fetched rows is the only way the window control can mean anything | Measured 2026-09-08 |
| 4 | First load fetches two month files and never more, whatever the archive holds. `monthCeiling(30)` = 2 and `monthCap` = 15 already enforce it | Carmack, 2026-09-08 |
| 5 | Seven browser specs assert chart markup is in the prerendered document. This is the largest ripple in the plan and it is named here rather than discovered by a worker | Fowler, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A request-count ceiling | Satisfied by merging files and says nothing about the wait. Chain depth and transferred bytes are the two that bound the experience | Carmack |

---

## 13. Row #11 - The verdict band arrives first and alone

- **Scope:** The band that answers "is the pipeline working" becomes its own small payload, fetched before anything else.
- **Files touched:**
  - `frontend/src/routes/console/+layout.svelte` - **create it. It does not exist today; the console directory holds only `+layout.server.ts`.** This row creates it, renders the band and `{@render children()}`, and row 12 later adds the no-script line above the panels to the same file
  - `frontend/src/lib/server/console-shell.ts`
  - the band payload from row 9, at `frontend/public/console/band.json`, fetched at `${base}/console/band.json`
  - `frontend/tests/console-band.spec.ts` - new
- **Acceptance gates:** local - the shared test selector. CI - browser smoke; the band renders its own unreachable state per row 12.
- **Oracle:** the band payload is at most 8 KB measured as `gzipSync(readFileSync(path), { level: 5 }).length`, and in a Playwright trace taken with `page.on('request')` it is the first request the console issues after the document and the entry bundle - asserted on its index in the ordered request list.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Susan ruled the band should stay prerendered and named a fetched band as the one way this change is a net loss. The owner overruled on consistency - one mental model, no special case, because a special case makes every future page ask which kind it is | Owner D2, over Susan, 2026-09-08 |
| 2 | This row is the mitigation both sides accepted: the band is the smallest payload on the site and the first request the page makes, so the operator's answer arrives in one round trip rather than after the page settles | Owner and Susan, 2026-09-08 |
| 3 | 8 KB rather than the 5 KB first proposed, because the months list from row 10 decision 1 rides here | Carmack, 2026-09-08 |
| 4 | This row creates the console layout component. The previous draft had two rows in one group editing a file neither had checked existed | Fowler, 2026-09-08 |

---

## 14. Row #12 - The console surface: reserved shape and three states

- **Scope:** The loading experience and the three data states, as one surface, reviewed once.
- **Depends on rows 10 and 11.** Row 11 creates `console/+layout.svelte`; this row adds to it.
- **Files touched:**
  - `frontend/src/styles/app.css` and the token files - the `loading` state class and the `shimmer` animation. Both are already named in `docs/concepts/design-system.md` (L23 and L471); **neither exists in CSS today.** `shimmer` is glossed there as "skeleton while a payload parses"
  - `frontend/src/lib/charts/` - reserved boxes, axis frame and ticks, the missing-span mark
  - `frontend/src/lib/components/WindowControl.svelte` - L46's status line, which becomes untrue the day this lands. Current text: `` `This control needs JavaScript. Every windowed section below is showing ${days} days.` ``
  - `frontend/tests/console-window.spec.ts` - L658-700 asserts the prerendered document opens on the configured window and says it needs a script rather than offering a control
  - `frontend/src/routes/console/+layout.svelte` - the no-script line above the panels
  - `config/appearance.json` under `console` - `shimmer_after_ms`. **Not `config/idhazh.json`.** Every console drawing knob lives in `appearance.json`; `window_presets` is there and absent from `idhazh.json`
  - `backend/idhazh/contracts/appearance_config.py` - `ConsoleConfig`, shared with `app_config.py`
  - `schemas/appearance-config.schema.json` **and** `schemas/app-config.schema.json` - both re-stamped `version` with a `changelog` entry
  - `frontend/src/contracts/` - regenerated
  - `frontend/src/lib/server/config.ts` - the `ConsoleConfig` interface (L153) and `CONSOLE_DEFAULTS` (L339). An undeclared key is dropped at read (L209)
- **What ships:**
  - Every panel titled and sized in the document. Charts reserve their box by aspect ratio and never change height
  - An empty chart draws its axis frame and tick marks and **no numbers**
  - The shimmer starts after `console.shimmer_after_ms`, so a fetch that lands first never animates
  - **Every skeleton shares one timeline, in phase.** Out of phase, twelve sweeping boxes read as twelve broken things
  - Under `prefers-reduced-motion`, a flat tinted block with **no gradient**. `app.css` L394 zeroes `animation-duration` and `transition-duration` to `0.01ms !important` on `*`, `*::before` and `*::after`, which would freeze a moving gradient mid-sweep and leave a bright band nobody chose. The flat block has to override that rule, not sit under it
  - Panels fill in document order; a panel that finishes early waits its turn
  - One status line for all background work, in words and files: `Fetching 2 months.`
  - Three states, each with the sentence it prints:

    | State | Means | Shows |
    | --- | --- | --- |
    | Quiet | The window is genuinely empty | Neutral tint, a sentence saying what is true, and the one preset that would change it |
    | Missing | We never had data for those dates | The span marked on the chart, dates named in the caption. No alarm |
    | Unreachable | The fetch did not arrive | Warn tint, names the month, says what it does have, `Try again` scoped to that panel |

  - A 92-day window where June has data, part of July is missing and August is fine plots June, marks the July span, and plots August
- **The worker writes the three sentences and the button label and Susan rules on them.** The table above gives the shape; the words are a design decision this row makes, not one it inherits.
- **Never:** move anything above the scroll position; dim a panel that already has data; print bytes or a percentage; block a control; scroll, steal focus, raise a toast or count a number up; announce every arrival.
- **Acceptance gates:** local - the shared test selector; a reduced-motion spec. CI - browser smoke; one spec per state.
- **Oracle:** the console's panel bounding boxes are identical at first paint and at settled. A built fixture with a hole mid-window renders a marked span; a built fixture whose fetch is blocked renders a visibly different thing.
- **Design gate:** Susan reviews before merge, per CLAUDE.md section 9.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Merged from two rows. A reserved box with no failure state lies, and a failure state with no reserved box shifts the layout - Susan reviews them together or she reviews half a thing | Fowler, 2026-09-08 |
| 2 | No spinner. A spinner suits one wait, a blank page and a person who cannot act; the console has a dozen waits and an operator who can act from the first frame | Susan, accepted as D3 |
| 3 | Today a failed month draws an unmarked gap, so **a quiet pipeline and a broken fetch are the same picture** - which is the exact thing this page exists to tell apart | Susan, 2026-09-08 |
| 4 | **`console.shimmer_after_ms` ships at 400 as a declared estimate** with a `## Design rationale` note saying so. Row 19 re-derives it from the measured median payload arrival. A user-interface row is not a measurement harness, and the previous draft made it both | Fowler, 2026-09-08, and Rule #10 |
| 5 | The knob goes in `config/appearance.json`, not `config/idhazh.json`. Every console drawing knob is already there, and a knob split across two files drifts | Fowler, 2026-09-08 |

---

## 15. Row #13 - The page carries nothing a later run can change

- **Scope:** Delete the two global stamps that make every page's bytes move on every build, and show nothing in their place.
- **Files touched:**
  - `frontend/src/lib/components/SiteFooter.svelte` - the build line (L52-63), the verification sentence (L67) and the retention sentence (L31-34), all quoted in section 2a
  - `frontend/src/routes/+layout.server.ts` - returns `{ ui }` only; the `latestDate` and `loadDay` imports go, and so does `footer`
  - `frontend/vite.config.ts`, `frontend/src/app.d.ts` - `__BUILD_COMMIT__`, `__BUILD_DATE__`
  - `frontend/src/lib/components/EmptyDay.svelte` (L18, L32-34), `DigestList.svelte` (L34, L41, L228), `MoreDays.svelte`, and the consumers `+page.svelte` (L15, L18), `[date]/+page.svelte` (L105), `[date]/[vertical]/+page.svelte` (L113) - the `latest` prop
  - `frontend/tests/footer-facts.spec.ts` - it pins the deleted sentences by regex at **L63 and L65** and the layout's source line at **L167** (`'footer: day ? { retention_window_months: day.retention_window_months }'`). A worker who only removes the regexes leaves L167 red
  - `frontend/tests/empty-day.spec.ts` - it asserts the literal source strings `latest={data.latest}` (L71) and `day?.date ?? latest` (L80)
  - `docs/architecture/publishing/frontend.md`, `docs/architecture/publishing/layout.md`, `docs/concepts/design-system.md` - all three repeat the retention promise
- **Acceptance gates:** local - `npm --prefix frontend run check`; the shared test selector. CI - browser smoke on a dated page, an empty day, the archive and the console.
- **Oracle:** record the sha256 of `build/2026-08-21/index.html`. Publish a new day into the digest root. Build again. **The hash must be identical.** Today `2026-09-08` appears twice in that file - once in the footer, once as `latest` in the layout data.
- **Oracle prerequisite:** both builds run with `BUILD_VERSION` set to one constant. `kit.version.name` defaults to `Date.now()` and lands in every prerendered document, so without the pin the oracle can never pass. `frontend/svelte.config.js` already documents the mechanism.
- **Second oracle:** `+layout.server.ts` imports nothing from `$lib/server/payload`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | No commit stamp, no build date, no manifest to fetch one from. The owner considered a fetched manifest and reversed: the commit is not worth a file, a schema, a request and a cleanup story | Owner D8, 2026-09-08 |
| 2 | The verification sentence goes with the footer. Reader argued it should be kept and moved beside the day; the owner ruled against | Owner, 2026-09-08 |
| 3 | The site stops promising that nothing is deleted, and does not replace it with a promise to delete either | Owner, 2026-09-08 |
| 4 | Ordered before row 14 and not after. After the shell there is one document, so there is nothing left to measure this row's claim on | Fowler, 2026-09-08 |
| 5 | `footer-facts.spec.ts` pins a **source line** as well as two sentences. The previous draft described it as regexes only | Fowler, 2026-09-08 |

---

## 16. Row #14 - One document serves every date

- **Scope:** The 110 dated and topic documents stop being written; one document serves every URL.
- **Files touched:**
  - `frontend/src/routes/+layout.server.ts` - **`export const prerender = true` lives here and cascades to every route.** Flipping it is the actual mechanism; this is not a per-route flag change
  - `frontend/src/routes/+page.server.ts`, `frontend/src/routes/archive/+page.server.ts` - **keep `/` and `/archive/` prerendered explicitly.** Without this the site root stops emitting `index.html` and GitHub Pages answers `/` with the fallback at HTTP 404
  - `frontend/src/routes/evals/+page.ts` - **create it**, carrying `export const prerender = true`. The directory holds only `+page.svelte` today, so there is no server file to put a flag in, and `bundle-gate.mjs` L225 fails when the `/evals/` ceiling names no route in the build
  - `frontend/src/routes/[date]/+page.server.ts`, `[date]/[vertical]/+page.server.ts` - **deleted and rewritten as `+page.ts` with `ssr = false`**
  - `frontend/src/lib/payload/project.ts`, `frontend/src/lib/payload/drawing.ts` - the browser-safe halves the new loaders call
  - `frontend/svelte.config.js` - the prerender block, `handleUnseenRoutes`, the `serviceWorker.files` predicate at L44-50, and the comment describing the seed-plus-fetch arrangement this row ends
  - `frontend/prerender-guard.js` and `frontend/tests/prerender-guard.spec.ts` (L84-89) - see the disposition below
  - `frontend/src/service-worker.ts` - the shell it caches is now the whole site
  - `config/idhazh.json` `page_weight.ceilings_bytes` - `/404` is held to 1706 bytes and after this row `404.html` is the document that serves every dated URL. **Re-measure and raise it in the same commit**; row 18 re-derives the rest
  - **The ten specs that read a dated or topic document out of `build/`:** `frontend/tests/payload-weight.spec.ts` (L107 and L163, where `expect(reading.length, 'the build has no dated route, so this proves nothing').toBeGreaterThan(0)` fails on an empty list **by design**), `dated-day.spec.ts` L175, `topic-day.spec.ts` L78, `reading-page.spec.ts` L451 and L485, `day-seam.spec.ts`, `malformed-day.spec.ts`, `filter-bar.spec.ts` L409, `footer-facts.spec.ts` L31-32, `prerender-guard.spec.ts` L84-89
- **`+page.ts` may import nothing from `$lib/server/`.** SvelteKit refuses to bundle that directory for the browser, and the deleted `+page.server.ts` imports `loadDay`, `dayShell` and `publishedDates` from `$lib/server/payload` plus `shellSeedItems` from `$lib/server/config`. The new loader fetches `${base}/digest/<YYYY>/<MM>/<DD>/digest.json`, applies `$lib/payload/project.ts` and `$lib/payload/drawing.ts` in the browser, and turns a non-200 or an unreadable payload into the same designed screen `loadDay` produces today. **There is no seed and no `dayShell` split on a client-rendered route**; `awaiting` becomes zero and its consumers drop it.
- **`console/+layout.server.ts` already declares `prerender = true` and cascades to all three console routes. It stays exactly as it is.** Do not add a per-route flag, and do not remove it thinking the root flag was the only one - `/console/` would start answering at HTTP 404 from the fallback.
- **Spec dispositions:** `payload-weight.spec.ts` loses its dated-route arm entirely, because the guard it replaced is gone with the documents. `prerender-guard.spec.ts` follows whatever `prerender-guard.js` becomes. The rest move from reading `build/<date>/index.html` to driving the route in a browser.
- **`prerender-guard.js` narrows rather than goes.** After this row nothing marks `/[date]` prerenderable, so `handleUnseenRoutes` can never be called with it; its remaining job is `/archive/`, `/evals/` and the console. `prerender-guard.spec.ts` narrows with it.
- **The service worker caches `404.html` as part of the shell,** and `svelte.config.js`'s `serviceWorker.files` predicate at L44-50 is the one place that list is written.
- **The fallback is already configured:** `adapter({ fallback: '404.html', strict: false })`.
- **Acceptance gates:** local - `npm --prefix frontend run check`; the shared test selector. CI - browser smoke on `/`, a dated page, a topic page, the archive, `/evals/` and all four console routes, each with its data file present and absent.
- **Oracle:** `build/` contains no `index.html` under a dated directory, `build/index.html` exists and is served at HTTP 200, and the document count does not move when a day is added.
- **Second oracle:** the built `404.html` and the kept documents each carry the `connect-src` meta tag. `frontend/tests/asset-base.spec.ts` asserts the config source today, not the output.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Delete the documents rather than shrink them to a head. A file per day is still a file per day | Owner D1, 2026-09-08 |
| 2 | In-app navigation never requests a dated URL from the server, so client-side routing is unaffected. Only a cold direct load takes the fallback, and it renders | Owner D11, 2026-09-08 |
| 3 | The link preview card and search-engine indexing of dated URLs are both accepted losses. This project is built for readers, not crawlers | Owner D11, 2026-09-08 |
| 4 | `withDrawing()` runs `refusedDrawing()` in Node today for seeded drawings. The same module and rule move to the browser, so the guarantee holds - but the build stops refusing a bad SVG anywhere, and row 19 records that | Fowler, 2026-09-08 |
| 5 | The `/404` ceiling is raised in this row, not deferred to row 18. The row must ship green alone, and after it `404.html` is the busiest document on the site | Fowler, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Shrink each dated document to a head - title, date, first summary | Keeps the preview card and 98 pct of the bytes, but a file per day is still a file per day | Owner |
| 2 | Keep `[date]/+page.server.ts` and only remove the prerender flag | A route that is not prerendered has no server on a static adapter. The file has to go | Fowler |

---

## 17. Row #15 - Publish the Release asset, pin the revision, prove it cross-origin

- **Scope:** Stand up the failover origin, resolve the pin, and prove a browser can read it, before anything leaves git.
- **Files touched:** a GitHub Release carrying the five weight files; `docs/reference/measurements.md` for the results.
- **Resolve the pin. `PROVENANCE.md` records no commit SHA** - only `Xenova/all-MiniLM-L6-v2`, Apache-2.0, fetched 2026-08-22. Row 16 decision 2 refuses anything but a full 40-hex commit SHA, so this row reads the upstream repository's commit history, picks the commit whose file digests match the five SHA-256 values in section 2a, and records it. **If no upstream commit matches those digests, ESCALATE trigger 3 fires** - the bytes we hold are then not reproducible from the hub and D10's primary origin cannot be pinned to them.
- **The release:** tag `encoder-2026-08-22`. A Release asset name cannot contain `/`, so the five assets are flat: `config.json`, `special_tokens_map.json`, `tokenizer_config.json`, `tokenizer.json`, `model_quantized.onnx`. `assist.model_fallback_url` is built from the flat names and row 16 maps them back to their paths.
- **What must be proved, from a real browser, not curl:**
  - A `fetch()` from the Pages origin to each release asset URL succeeds cross-origin. **CORS is a second gate that `connect-src` does not cover**, and this is the failover leg - the one that only runs when the primary is already down
  - The redirect chain is recorded. `github.com/<owner>/<repo>/releases/download/...` redirects to an object host, and **CSP matches every redirect hop against the source list**
  - The same for the Hugging Face LFS path: a `resolve/<40-hex>/` URL for a 23 MB file redirects to a CDN
- **How:** a one-off Playwright script under `backend/utilities/`, run by hand against a deployed preview, with its output pasted into `docs/reference/measurements.md`. It is not a CI spec and it does not join any suite - Rule #7 forbids a test that touches the network.
- **Acceptance gates:** local - none. CI - none. This row produces a published asset, a resolved SHA and a recorded result.
- **Oracle:** a recorded browser trace showing a successful cross-origin `fetch()` of every weight file from the release asset, with the full redirect chain and every host that appears in it, plus a 40-hex SHA recorded for `assist.model_revision`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Split from rows 16 and 17. Standing up two origins and deleting 43 MiB in one row means recovery is reverting a commit that deleted the weights | Andre, 2026-09-08 |
| 2 | **`connect-src` needs four to six origins, not two.** Listing only `huggingface.co` and `github.com` passes the small JSON files and blocks the 23 MB weights - the worst failure shape there is, because the pipeline half-loads and errors somewhere unrelated | Andre, 2026-09-08 |
| 3 | At least two of those hostnames are vendor-owned and can change without telling us. Row 19 records that as a standing maintenance cost | Andre, 2026-09-08 |
| 4 | This row resolves the pinned SHA, which is why row 16 depends on it and why row 8 no longer mints the `assist.*` keys | Fowler, 2026-09-08 |

---

## 18. Row #16 - Two origins, a digest manifest, and one guard that still works

- **Scope:** The browser fetches the weights from Hugging Face, verifies them, falls back to our asset, and the `model_id` guard keeps meaning something.
- **Files touched:**
  - `config/idhazh.json` - `assist.model_base_url`, `assist.model_revision`, `assist.model_fallback_url`, `assist.model_digests`, `assist.model_fetch_deadline_ms`. **Minted here, not in row 8**, because row 15 resolves the revision this row consumes
  - `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/appearance_config.py` - `AssistConfig` is shared, so both schemas move
  - `schemas/app-config.schema.json`, `schemas/appearance-config.schema.json`, `schemas/search-index.schema.json` - each re-stamped `version` with a `changelog` entry. `search-index.schema.json` is stamped **here**, in the commit that changes what `model_id` means
  - `frontend/src/lib/server/config.ts` - the `AssistConfig` interface and `ASSIST_DEFAULTS`; an undeclared key is dropped at L209
  - `frontend/tests/appearance-config.spec.ts` - the `DECLARED` array at L132
  - `frontend/src/lib/assist/loader.ts` - the fetch and the failover. **L155 `allowRemoteModels = false`, L156 `allowLocalModels = true` and L157 `localModelPath` are what make a remote fetch impossible today**; a failover leg added without changing them is code transformers.js never reaches, and CI goes green with the weights still local-only. `wasmPaths` at L159-161 is unchanged and stays same-origin. **`cachedEncoder()` at L108 keys on `${base}/assist/models/...` and will report `absent` for a reader who already holds the weights**, telling them to pay 43 MB again for ever
  - `frontend/src/lib/assist/encoder.ts` - `ENCODER_ID` stays a contract constant. **`ENCODER_VERSION` becomes the 40-hex `assist.model_revision`**, so different weights remain a different URL once the dated directory is gone
  - `frontend/src/lib/assist/search.ts` - the guard at L107 already refuses a `model_id` mismatch; it must keep doing so against something that can actually differ
  - `frontend/svelte.config.js`, `frontend/asset-base.js` - `connect-src` gains every host row 15 recorded, derived from config
  - `frontend/tests/asset-base.spec.ts` - it asserts `connectSources(assetBaseUrl())` equals exactly `['self']` at L43 and pins the config source line at L42. That equality becomes "self plus exactly the hosts the config names", asserted against the config rather than against a literal
  - `backend/idhazh/embed.py`, `backend/idhazh/assemble.py` - `assemble.py` takes `model_id` from the newest day carrying vectors, not from a writer default; it is load-bearing and the superseded draft named neither file
  - `backend/tests/test_embed.py` - `test_the_versioned_directory_is_the_one_on_disk` asserts the model directory exists and goes red in row 17
  - `frontend/tests/filter-bar.spec.ts` - counts requests under the model directory; **it must not become a network test.** The mechanism is a Playwright `page.route()` interception serving the committed fixture bytes, not a second static server and not the real hub
  - `frontend/src/service-worker.ts` - the cache decision
  - `frontend/src/lib/components/ArchiveSearch.svelte` - the download notice and the privacy sentence
- **The failover rule, sharpened:** all-or-nothing, per source, with a deadline and a digest. Try Hugging Face for all five weight files against `assist.model_fetch_deadline_ms`; verify every SHA-256 against `assist.model_digests`; on any miss - a non-200, a truncation, a timeout, or a digest mismatch - discard the whole set and take all five from the release asset. **Never mix provenance across files.** The deadline is a config key and not a literal in `loader.ts` (Rule #6).
- **The expected `connect-src` host list**, which row 15's trace either confirms or amends: `huggingface.co`, the Hugging Face LFS CDN host, `github.com`, `objects.githubusercontent.com`. Row 16 ships whatever row 15 recorded, and the config is the source.
- **The drift gate:** a test asserting `assist.model_revision` and `ENCODER_VERSION` are the same 40-hex string. It replaces the guard the dated directory used to provide.
- **Acceptance gates:** local - the shared test selector; `python -m pytest backend/tests/test_embed.py`. CI - browser smoke with the model reachable, with Hugging Face blocked, and with both blocked; the drift gate; the contract drift gate.
- **Oracle:** a deliberately corrupted digest in a fixture causes the whole Hugging Face set to be discarded and all five files taken from the failover, and a mismatched `model_id` still collapses search scope to the days that match.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A committed SHA-256 manifest for the weight files, verified in the browser before the bytes reach transformers.js.** We hold the exact bytes today and section 2a carries all five. It costs five hex strings and one `crypto.subtle.digest` call, and it turns the revision pin from a reference into an assertion | Andre, 2026-09-08 - the one guard he would refuse to ship without |
| 2 | `assist.model_revision` is refused at the contract unless it is a full 40-hex commit SHA. A tag or a branch can be moved, so it pins nothing | Andre, 2026-09-08 |
| 3 | `ENCODER_ID` stays a constant and config owns only the origin. Moving it to config makes the guard a constant compared against a constant - it passes always and detects nothing | Andre and Fowler, converging, 2026-09-08 |
| 4 | **`ENCODER_VERSION` becomes the 40-hex revision**, and a drift gate asserts the two are equal. Its stated job is to make different weights a different URL, and that job outlives the dated directory | Fowler, 2026-09-08, resolving the open question in the previous draft |
| 5 | transformers.js tries **local first, then remote** when both flags are set. There is no built-in remote-first order, so the failover is our own code and this plan says so | Andre, 2026-09-08 |
| 6 | `filter-bar.spec.ts` runs against intercepted routes serving the committed fixture bytes. Rule #7 - no test touches the network - and the alternative is fetching 23.7 MB from Hugging Face inside CI | Andre and Carmack, converging, 2026-09-08 |
| 7 | The service worker does **not** cache the remote model. It refuses anything not same-origin GET and `frontend/tests/manifest.spec.ts` enforces that from source | Andre, 2026-09-08 |
| 8 | `ArchiveSearch.svelte` says what the first search will fetch and from where, before it starts. `DOWNLOAD_MB = 43` at loader.ts L55 becomes a two-origin split derived from the digest manifest, because its own comment says a figure that drifts from the download is worse than no figure | Andre and Carmack, converging, 2026-09-08 |
| 9 | The privacy sentence gains one clause: the first search sends the reader's IP, User-Agent and Origin to a third party. "Nothing you type leaves your browser" stays true and is no longer the whole truth | Andre, 2026-09-08 |
| 10 | The `connect-src` widening is **not** exploitable by a planted instruction: nothing fetched from the web reaches the encoder, item vectors are computed on the runner, and no code path builds a fetch URL from a payload field. The risk inverts instead - a second party can now put bytes into a reader's tab, and decision 1 is what bounds that | Andre, 2026-09-08 |
| 11 | `search-index.schema.json` is stamped in this row, not row 8. A schema whose `version` predates the commit that changed its semantics is a section 11 break in both rows | Fowler, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A single origin, ours only | Recommended and overruled by the owner for availability | Owner D10 |
| 2 | Trust a pinned revision without a digest | A pin is a reference, not an integrity check; we never verify what arrived | Andre |
| 3 | Per-file failover | Gives a tokenizer from one origin and weights from another | Andre |
| 4 | Delete `ENCODER_VERSION` with the dated directory | It is what makes different weights a different URL. Deleting it re-opens the silent-stale-cache failure the directory date was invented to close | Fowler |

---

## 19. Row #17 - Delete the committed weights

- **Scope:** The five weight files leave git, once the fetch that replaces them is proven in production.
- **Files touched:**
  - `frontend/static/assist/models/all-minilm-l6-v2-quantized/2026-08-22/` - `config.json`, `special_tokens_map.json`, `tokenizer_config.json`, `tokenizer.json`, `onnx/model_quantized.onnx`. **`PROVENANCE.md` stays**
  - `backend/tests/test_embed.py` - `test_the_versioned_directory_is_the_one_on_disk` goes, or changes to assert the manifest instead
- **Does not touch:** `frontend/static/assist/wasm/` - 21,640,503 B that stays same-origin.
- **Acceptance gates:** local - the shared test selector; `python -m pytest backend/tests/test_embed.py`. CI - browser smoke; the bundle gate.
- **Oracle:** the built site contains no `.onnx` **and** `frontend/static/assist/wasm/ort-wasm-simd-threaded.jsep.wasm` is still present and still served. Search works. With both model origins blocked, search says so and **every digest assertion still renders** - CLAUDE.md section 0a.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **22.59 MiB leaves; 20.64 MiB stays.** The superseded draft claimed 43.23 MiB and its oracle - "the built site contains no `.onnx`" - passed with the whole ONNX runtime still in place | Carmack, 2026-09-08 |
| 2 | Separated from row 16 so the deletion lands only after the replacement is proven in production, not alongside it | Andre, 2026-09-08 |
| 3 | A later encoder swap re-encodes every published day. That is a growing read, it is legal under Rule #12's escape hatch because a person runs it once, and it gets an entry in `docs/concepts/growing-reads.md`. It is never a per-run cost | Rule #12 |
| 4 | The re-encode degrades progressively, not atomically: `build_search_index` takes its header from the newest day carrying vectors and demotes every disagreeing day to browsable-not-searchable on one log warning. Row 19 records it | Andre, 2026-09-08 |

---

## 20. Row #18 - The gates measure a shell, not a document

- **Scope:** Re-aim every ceiling at what the migrated site is, and add the two that bound a fetched page.
- **Depends on rows 12, 14 and 17.** Four of its six ceilings measure things that do not exist until rows 10, 11 and 12 have landed.
- **Files touched:** `frontend/scripts/bundle-gate.mjs`, `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `.github/workflows/ci.yml`, `.github/workflows/pages.yml`, and a new Playwright network-trace spec.
- **What changes:**

  | Ceiling | Value | Basis |
  | --- | --- | --- |
  | One telemetry month payload | 1.1 MB gzip -5 | `telemetry/` is 1.12 MiB over about 2 months, so about 0.6 MB a month. Structural ceiling is `run.safety_ceiling_per_run` 80 x 5 cron slots x 31 days = 12,400 items against about 9,400 rows over 30 days, giving 0.8 MB. Plus 30 pct. Revisit when a sixth cron slot or a higher safety ceiling lands |
  | Verdict band | 8 KB gzip -5 | Row 11's oracle, plus the months list |
  | Cold console load, all payloads, default window | 3.0 MB gzip -5 | Two months plus the band plus headroom |
  | Cold console chain depth | at most 4 hops | Row 10 decision 2 |
  | Page ceilings | re-derived from the migrated tree | The current values guard a document that no longer exists |
  | Encoder ceiling | **kept, re-aimed at the digest manifest** | Deleting it means nothing catches an upstream `.onnx` that grew |

- **The gzip level change is atomic.** `bundle-gate.mjs` L120 compresses at `{ level: 9 }` and all six values in `page_weight.ceilings_bytes` were measured at -9. Moving to `{ level: 5 }` **and** re-measuring all six happen in one commit. Neither half ships alone: gzip -5 output is strictly larger, so flipping the level without re-deriving fails the gate on the first run.
- **The payload ceilings need somewhere to live.** `bundle-gate.mjs` walks only `index.html` and `404.html`, and a payload is neither. It gains a second pass over the set named at `config/idhazh.json` `page_weight.payload_ceilings_bytes` - a new key, so it needs a field on `app_config.py`, a regenerated `schemas/app-config.schema.json` with a fresh `version` and one `changelog` entry (Rule #3, section 11).
- **Chain depth is not a gate-script check.** It is asserted in a Playwright network-trace spec that counts serial round trips before the console's last panel resolves and requires `<= 4`.
- **Acceptance gates:** local - `npm --prefix frontend run bundle-gate` against a deliberately oversized fixture payload. CI - the gate fails on that fixture and passes on the real tree.
- **Oracle:** raise a fixture payload past its ceiling and CI goes red; lower it and CI goes green. Add a fifth serial hop to the console's cold load and CI goes red.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Ceilings are set in **gzip -5 bytes**, because that is what the reader pays. The project currently uses three units for one page: gzip -9 in the gate, gzip -5 on the wire, identity in the size report | Carmack, 2026-09-08 |
| 2 | The payload set is named in `config/`, not in the gate script. Rule #6 | Fowler, 2026-09-08 |
| 3 | Every ceiling value above is an estimate built from two measured points. Row 19 re-derives them from the migrated tree | Rule #10 |
| 4 | This row also re-measures the `browser` CI job. It sits at 37 pct of a 1,500 s timeout and six rows add specs to it; ESCALATE trigger 4 fires at 70 pct | Carmack, 2026-09-08 |
| 5 | Depends on row 12 as well as 14 and 17. The previous draft would have let this row measure four ceilings against things that did not exist yet | Fowler, 2026-09-08 |

---

## 21. Row #19 - Record what was decided and what it cost

- **Scope:** The documentation this plan owes, and the measurements that replace its estimates.
- **Files touched:**
  - `docs/concepts/ui-shell.md` - **the spinner ban survives on narrower ground.** Its stated reason is that a reader already has a readable frame, and that reason is false on a route shipping an empty shell on purpose. Write the narrower ground down or the next agent reads the ban as absolute again. State 4 also becomes untrue
  - `docs/reference/measurements.md` - the post-migration `site-weight` output with hardware, date and n; the Hugging Face `Content-Encoding` result beside the existing compression table; the re-derived ceilings; the `browser` job duration; the measured median payload arrival that settles `console.shimmer_after_ms`
  - `docs/archive/measurements-2026-08.md` - a Hugging Face row in the compression table so the two origins read against each other
  - `docs/architecture/publishing/` - the shell, the fetch shapes, the three states, the measured bytes, and the fact that the build no longer refuses a bad SVG
  - `docs/concepts/growing-reads.md` - the inventory table near L207 gains one row per read row 6 could not bound, each carrying its `-1` declaration and the sentence saying why; plus `outputFingerprint`, which walks a tree that gains files every published day and **still does after this plan**; plus the re-encode migration
  - `frontend/src/lib/assist/loader.ts` - the `DOWNLOAD_MB` docstring gains the two-origin split and the measured wire cost of each half
  - `config/appearance.json` - `console.shimmer_after_ms` moves from the declared 400 estimate to the measured value
  - `config/idhazh.json` - one line on `pages_hard_cap_mb` saying 1024 is MiB while the platform limit is 1 GB, a 7 pct optimistic gap
  - `CLAUDE.md` section 0a - "the bundle must render complete with the model directory deleted" now describes a permanent state rather than a test
  - `docs/reference/agent-notes.md` - any tool or environment quirk a worker hit
  - `.github/workflows/measure-migrated-tree.yml` - deleted
- **Acceptance gates:** documentation-only closure; no local application suite, per AGENTS.md item 5.
- **Oracle:** every estimate in section 2 of this plan is replaced by a measurement carrying hardware, date and spread, or is deleted.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`assertBuild` still grows with the archive after this plan.** `static/digest/` gains a payload and its rendered images every published day, and both hashed trees carry them. Row 14's oracle is true of `build/` HTML only. This is Rule #12 inside the plan and it is recorded rather than fixed | Carmack, 2026-09-08 |
| 2 | The output-fingerprint rework of the superseded draft is closed, not deferred. Bytes fall about 32 pct and files about 14 pct, and the dominant term is the one that falls less | Carmack, 2026-09-08 |
| 3 | `8.14 ms per file` is a derivation, not a measured constant - it is 12.93 s over 1,589 files, and the same run equally yields 17.2 MB/s. One data point cannot separate a per-file term from a per-byte term | Carmack, 2026-09-08 |
| 4 | Row 1's workflow file is deleted here rather than kept. A measurement harness nobody runs is a maintenance cost with no reader | This plan |
| 5 | This row settles `console.shimmer_after_ms`. Row 12 ships it as a declared estimate so a user-interface row does not have to be a measurement harness | Fowler, 2026-09-08 |

---

## 22. What each row must not do

A worker that finds itself doing one of these has left its row.

| # | Do not |
| --- | --- |
| 1 | Re-open a section 0a ruling. Eleven of them are settled and the owner settled them |
| 2 | Move the bundle gate ahead of the commit. Row 3 decision 2 reversed that and says why |
| 3 | Delete the `assertBuild` call that assigns `testedBuild`. Row 4 explains what breaks |
| 4 | Edit `.github/workflows/digest.yml` from any row but 2, 3 or 9, and never from two rows in one parallel group |
| 5 | Hard-code a payload path under `frontend/public/`. Derive it from `DIGEST_ROOT`, per row 9 |
| 6 | Add a config knob without its Pydantic model, its re-stamped schema and its `config.ts` declaration. Row 8 decision 5 |
| 7 | Let any test reach the network. Row 15's browser trace is a one-off run by hand, not a spec |
| 8 | Write an all-time count onto any surface, including an aria-label. Row 7 found one there |
| 9 | Grow a row's file list past section 1b without re-checking the collision proof |

---

## 23. Traceability - where each review finding landed

| Source | Finding | Landed in |
| --- | --- | --- |
| Carmack | The 23.8 MB headline double-counted; the honest claim is runway in days | Section 2, row 1 |
| Carmack | Only 22.59 MiB can leave; the ONNX runtime is ours and stays | Section 0 scope-out, row 17 decision 1 |
| Carmack | Row 4's saving is developer-loop only and zero in CI | Row 4 decision 1 |
| Carmack | Ceilings must be one unit, and gzip -5 is what the reader pays | Row 18 decision 1 |
| Carmack | Artifact storage is already 19 pct over the Rule #2 figure | Row 2 decision 1 |
| Fowler | Thirteen readers have no published shape; the inventory is a row | Row 8 |
| Fowler | `prerender` cascades from the root layout; flipping it 404s the site root | Row 14 |
| Fowler | The dated loads must be deleted and rewritten, not de-flagged | Row 14 decision, rejected alternative 2 |
| Fowler | New payloads need the workflow allow-list, and it has two copies | Row 9, section 2a |
| Fowler | Amend `public-telemetry.schema.json`; do not fork it | Row 8 rejected alternative 2 |
| Fowler | Row 4 would have broken `test:changed` outright | Row 4, section 0b |
| Fowler | `console/+layout.svelte` does not exist | Rows 11 and 12, section 0b |
| Fowler | The model and machine pages do read the whole ledger | Row 6, section 0b |
| Fowler | Seven browser specs assert chart markup is prerendered | Row 10, section 0b |
| Fowler | Rows 2 and 3 collide on one file | Section 1a, 1b, row 3 decision 3 |
| Fowler | `sourceHealthView` is already windowed; do not double-window it | Row 7 |
| Fowler | Row 18 must depend on row 12 | Status Reckoner, row 18 decision 5 |
| Andre | `connect-src` needs four to six origins, not two | Row 15 decision 2, row 16 |
| Andre | A pinned revision without a digest verifies nothing | Row 16 decision 1 |
| Andre | Failover is all-or-nothing per source, because transformers.js is local-first | Row 16 decision 5 |
| Andre | Moving `model_id` to config makes the guard detect nothing | Row 8 rejected alternative 3, row 16 decision 3 |
| Andre | `cachedEncoder()` breaks silently for a returning reader | Row 16 files touched |
| Andre | The privacy sentence becomes incomplete | Row 16 decision 9 |
| Reader | Keep the verification sentence beside the day | **Dismissed by the owner** - section 24 row 8 |
| Reader | Measure reader-facing first paint | **Dismissed by the owner** - section 24 row 9 |
| Susan | The verdict band should stay prerendered | Overruled by D2; mitigated by row 11 |
| Susan | A failed month and a quiet month draw the same picture | Row 12 decision 3 |

---

## 24. Refused, with the measurement that refused it

| # | Option | Why refused | Authority |
| --- | --- | --- | --- |
| 1 | Cache the built site between CI runs | A large cache restore costs 41 to 73 s against a build of 21 to 24 s, and the repo cache is 96.6 pct full so it evicts on LRU | Measured 2026-09-08 |
| 2 | Reuse prerendered pages between builds | Every CI job is a cold start | Measured 2026-09-08 |
| 3 | Fetch day payloads from `raw.githubusercontent.com` | Pages serves the identical file from our own origin with no rate limit. No benefit until the 1 GB cap binds, and that is about 600 days away | Owner, 2026-09-08 |
| 4 | Point SvelteKit's assets folder at `frontend/public/` to end the staging copy | The staged copy is a projection at 468.58 bytes an item against 792.65; serving the committed shape sends 40.9 pct more bytes to every reader | Measured 2026-08-31 |
| 5 | A deployment or build manifest carrying the commit and the newest day | Considered and reversed by the owner. `latest_day` is answered by data the page already fetches, and `published_days` is an all-time count | Owner D8, 2026-09-08 |
| 6 | Move the ONNX runtime off our origin with the weights | Hugging Face is a model hub and does not host it. 20.64 MiB stays same-origin | Carmack, 2026-09-08 |
| 7 | A single origin for the weights | Recommended and overruled for availability | Owner D10, 2026-09-08 |
| 8 | Keep the verification sentence and move it beside the day | Reader argued for it; the owner ruled against | Owner, 2026-09-08 |
| 9 | Measure reader-facing first paint before and after | Reader asked for it; the owner ruled it out of scope | Owner, 2026-09-08 |
| 10 | A guard listing the paths a test may not read | Tried and deleted 2026-09-06. It enumerated the hazard rather than the safe set, its upkeep grew with the collections, and a path list makes a judgement call look like a permission slip | CLAUDE.md Rule #12 |
| 11 | `git ls-files` as a new mechanism for `inputFingerprint` | It already does this, at line 48. The 3.23 s is reading and hashing 66.55 MB, and dropping `corpus/` saves about 0.65 s, not most of it | Verified 2026-09-08 |
| 12 | An ESCALATE trigger on the `model_id` guard | `search.ts` line 107 already refuses a mismatch. The trigger was answered before it was written | Verified 2026-09-08 |
| 13 | Move the bundle gate ahead of the commit to save the rebuild | A page one byte over its ceiling would then cost the reader the whole day and the hours that built it, and `test_the_build_gates_the_publish_and_the_weight_gate_runs_after_it` asserts the current order | Fowler, 2026-09-08 |
| 14 | Make row 12 measure the shimmer delay it ships | A user-interface row that is also a measurement harness ships neither well. It declares 400 as an estimate and row 19 settles it | Fowler, 2026-09-08 |

---

## See also

- [`CLAUDE.md`](../CLAUDE.md) - sections 0, 0a, 6, 9, 11, 12, 13, 14; Rules 1, 2, 3, 6, 7, 10, 11, 12.
- [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan stamps.
- [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every acceptance gate here.
- [`docs/how-to/ship-a-pr.md`](../docs/how-to/ship-a-pr.md) - the worktree, branch and PR ritual section 1a feeds.
- [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - where a chosen growing read is recorded.
- [`docs/concepts/design-system.md`](../docs/concepts/design-system.md) - the motion set and state classes row 12 first uses.
- [`docs/concepts/ui-shell.md`](../docs/concepts/ui-shell.md) - the five states and the spinner ban row 19 narrows.
