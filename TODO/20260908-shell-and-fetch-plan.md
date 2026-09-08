# Shell And Fetch - one document, every panel fetched, nothing that grows with the archive

**Last Updated**: 2026-09-08
**Level**: 5 (core design, persisted contracts, and the trust boundary). Design consultation is
complete; section 0a records the eleven owner rulings and no row re-opens one.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 2; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The build carries what no reader gets: 110.65 MB across 751 files growing 1.69 MB and 5.71 documents a published day, one operator page inlining 3,374 KB of ledger rows, 43.23 MiB of encoder in git, and four functions walking the whole archive on every build |
| Hard scope - in | One document serving every URL; the console fetching windowed payloads instead of inlining rows; the verdict band as its own first payload; three distinct states for quiet, missing and unreachable; bounding every read whose cost rises when a run appends a day; the model weights leaving the repository behind a digest manifest; deleting the two global build stamps; the gate and CI changes all of that forces; and the five build-cost findings of the superseded `20260908-build-reuse-plan.md` draft |
| Hard scope - out | A prerendered document for any dated or topic route. Any deployment, build or commit manifest. Any all-time count on any surface. The 20.64 MiB ONNX runtime under `frontend/static/assist/wasm/` - Hugging Face is a model hub and does not host it, so it stays same-origin. Caching the built site between CI runs (section 22 row 1). A reader-facing first-paint measurement (owner, 2026-09-08) |
| ESCALATE triggers | 1. Row 8's inventory finds a console dataset whose browser-safe projection needs a product decision about what a panel means. 2. Row 15 cannot read a GitHub Release asset cross-origin from a real browser, which kills the failover leg. 3. Row 18 finds the `browser` CI job past 70 pct of its 25-minute timeout. 4. Any row would make a green certify a tree it did not test |
| Chosen strategy | Measure first, bound what exists, mint every contract before any consumer, then migrate. Every row ships green alone. Fowler ruled the row split; Carmack ruled the cost model; Andre ruled the encoder sequence; Susan ruled the console surface |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2. |

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

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Measure the migrated tree and the two wire costs | - | A | PENDING | - | - | - |
| 2 | The parcel carries the day, not the archive | - | A | PENDING | - | - | - |
| 3 | Rebuild only when the push was rebased | - | A | PENDING | - | - | - |
| 4 | Delete the duplicate verification call | - | A | PENDING | - | - | - |
| 5 | Stage only what changed | - | A | PENDING | - | - | - |
| 6 | Bound the four archive walks | - | B | PENDING | - | - | - |
| 13 | The page carries nothing a later run can change | - | B | PENDING | - | - | - |
| 15 | Publish the Release asset and prove it cross-origin | 1 | B | PENDING | - | - | - |
| 7 | The console stops claiming "never" | 6 | C | PENDING | - | - | - |
| 8 | Inventory and mint every console payload contract | 6 | C | PENDING | - | - | - |
| 9 | The producer writes the console its payloads | 8 | D | PENDING | - | - | - |
| 10 | The console fetches instead of inlining | 9 | E | PENDING | - | - | - |
| 16 | Two origins, a digest manifest, and one guard that still works | 8, 15 | E | PENDING | - | - | - |
| 11 | The verdict band arrives first and alone | 10 | F | PENDING | - | - | - |
| 12 | The console surface: reserved shape and three states | 10 | F | PENDING | - | - | - |
| 14 | One document serves every date | 13 | G | PENDING | - | - | - |
| 17 | Delete the committed weights | 16 | G | PENDING | - | - | - |
| 18 | The gates measure a shell, not a document | 14, 17 | H | PENDING | - | - | - |
| 19 | Record what was decided and what it cost | 1-18 | I | PENDING | - | - | - |

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

---

## 3. Row #1 - Measure the migrated tree and the two wire costs

- **Scope:** Replace the two estimates this plan rests on with measurements taken on the runner, before any contract is written.
- **Files touched:**
  - `.github/workflows/` - a `workflow_dispatch` job, deleted again in row 19
  - `docs/reference/measurements.md` - the results
- **Method, arm 1:** on `ubuntu-latest`, check out `main`, `rm -rf frontend/static/assist/models`, `npm --prefix frontend run build`, delete every `build/<YYYY-MM-DD>/` directory, then `python -m idhazh site-weight --site-tree build`, `find build -type f | wc -l`, and the same two over `frontend/.svelte-kit/output`.
- **Method, arm 2:** `curl -sI -H 'Accept-Encoding: gzip' <the pinned Hugging Face resolve URL for model_quantized.onnx>` and record `Content-Encoding` and `Content-Length`.
- **Acceptance gates:** local - none. CI - the dispatch job runs green.
- **Oracle:** `docs/reference/measurements.md` carries a post-migration site size, file count and slope with hardware, date and n stated, plus a Hugging Face `Content-Encoding` value.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The 23.8 MB figure of the superseded draft double-counted. The day payloads, month index and telemetry are fetched from our own Pages origin, so fetching them does not remove them from the artifact | Carmack, 2026-09-08 |
| 2 | The plan's claim becomes runway in days, not a percentage of the artifact. A percentage of a number that keeps growing is not a result | Carmack, 2026-09-08 |
| 3 | Arm 2 decides whether a searching reader pays 21.6 MB or 28.9 MB. If Hugging Face serves a 23 MB octet-stream identity, that is 6.75 MB a reader does not pay today and it belongs in D10's cost record | Carmack, 2026-09-08 |
| 4 | Taken on the runner, not the laptop, because the dominant term is per-file syscall cost and that is the term differing most between the two machines | Carmack, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Take the measurement on the laptop | 4.1x off on a whole build and worse on a file walk | Carmack |
| 2 | Defer both measurements to the end | Row 18 and row 19 would inherit a wrong premise and close the fingerprint work on it | Carmack |

---

## 4. Row #2 - The parcel carries the day, not the archive

- **Scope:** The `visuals` artifact uploads the whole 454-file digest tree when one day is new; upload the run's day.
- **Files touched:** `.github/workflows/digest.yml` - the `visuals` job `upload-artifact` `path:` and the `assemble` job `download-artifact` that consumes it.
- **Acceptance gates:** local - none. CI - a full `digest.yml` dispatch produces a day identical in shape to the previous run's.
- **Oracle:** the `visuals` artifact byte size falls and the assembled day's file list is unchanged.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Sequenced first in group A. Live artifact storage is 594.4 MB against the 500 MB figure in Rule #2 - the only budget in this plan already over | Carmack, 2026-09-08 |

---

## 5. Row #3 - Rebuild only when the push was rebased

- **Scope:** `digest.yml` builds the site before the commit and again after it; skip the second when the push was not rebased.
- **Files touched:** `.github/workflows/digest.yml` - the `Build the site` step, the `Rebuild the site against the tree that was pushed` step, and the `Bundle gate` step that follows.
- **Acceptance gates:** local - none. CI - a dispatch with no rebase skips the rebuild; a dispatch that rebases runs it.
- **Oracle:** the `assemble` job step list shows the rebuild absent on a clean push and present after a rebase.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | About 19 s per publish, five publishes a day. The pre-commit and Pages builds use different `BASE_PATH` values, so neither is ever reusable as the published artifact | Measured 2026-09-08 |
| 2 | The bundle gate moves ahead of the commit so it still guards a tree that was actually built | This plan |

---

## 6. Row #4 - Delete the duplicate verification call

- **Scope:** `run-checks.ts` calls `assertBuild` on two adjacent lines with nothing between them.
- **Files touched:** `frontend/scripts/run-checks.ts` - the call at line 332, which duplicates line 327 on the happy path.
- **Acceptance gates:** local - `npm --prefix frontend run test:changed -- --list`, then the selected checks. CI - none new.
- **Oracle:** a warm `test:changed` run issues one fewer `assertBuild` and its total falls by about 16 s.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **This is a developer-loop saving and zero in CI.** `run-checks.ts` is `test:changed`; `ci.yml` calls `check`, `test:tooling`, `test:logic`, `build`, `bundle-gate` and `test:browser` directly and never reaches it | Carmack, 2026-09-08 |
| 2 | Line 332 is only a duplicate on the happy path - in a fresh checkout line 327 throws, the build runs, and 332 is the single verification. Keep the throw; delete the second call | Carmack, 2026-09-08 |

---

## 7. Row #5 - Stage only what changed

- **Scope:** `copy-visuals.mjs` deletes and re-copies every staged file on every build; copy what differs.
- **Files touched:** `frontend/scripts/copy-visuals.mjs` - the `rmSync` calls on `static/digest`, `static/telemetry` and `static/index`, and the walk that follows.
- **Acceptance gates:** local - the shared test selector. CI - none new.
- **Oracle:** two consecutive builds with no new day stage zero files on the second, and the staged tree is byte-identical to a full re-stage.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | 5.82 s locally and **zero in CI** - every CI job starts with `static/digest` absent, so the first stage is always a full one | Measured 2026-09-08 |
| 2 | The projection stays. The staged day is 468.58 bytes an item against the committed 792.65; serving the committed shape would send 40.9 pct more bytes to every reader | Measured 2026-08-31 |

---

## 8. Row #6 - Bound the four archive walks

- **Scope:** Give every read in `payload.ts` whose cost rises with the archive a bounded input.
- **Files touched:**
  - `frontend/src/lib/server/payload.ts` - `publishedDates()` is the root; `loadManifests()`, `publishedItems()` and `publishedCharts()` each loop over it; `itemHealthRows()` and `feedResults()` read every shard in a directory; `evalRows()` reads the whole eval ledger; `telemetryMonths()` and `indexMonths()` list directories
  - `frontend/src/lib/server/console-shell.ts` and the three console `+page.server.ts` files - the call sites that must now pass a window
- **The pattern to copy, already in this file:** `telemetryRows(root, windowDays)` and `dayMetrics(dates)` both take a bound and both cite Rule #12 in their own comments.
- **Do not touch:** `frontend/src/routes/console/model/+page.server.ts` and `frontend/src/routes/console/machine/+page.server.ts`. Both carry explicit "bounded to the widest preset" comments and are already correct.
- **Acceptance gates:** local - the shared test selector; `npm --prefix frontend run check`. CI - browser smoke on all four console routes.
- **Oracle:** build against a fixture digest root, record the console routes' wall clock, add ten days to the fixture, build again. **The time must not move.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each read's default is the widest preset its surface offers, so no panel loses a day it draws today | This plan |
| 2 | `publishedDates()` survives row 14 - `/` builds a seven-day `recent` list from it, and `latestDate()` and the archive call it - so this row is not made dead by the shell | Fowler, 2026-09-08 |
| 3 | Row 8 depends on this one: the windows settled here decide what row 9's producer publishes | Fowler, 2026-09-08 |
| 4 | Where a read cannot be bounded, it gets an entry in `docs/concepts/growing-reads.md` naming what it reads, how the cost grows and why a bounded input cannot answer it - never a silent exception | Rule #12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Cache the walk between builds | Every CI job is a cold start, so a cache saves nothing on the authoritative arm, and it hides the growth rather than removing it | Carmack |
| 2 | Defer until the shell lands, since the console stops calling these | The work moves to the producer in row 9 and must be bounded there. Bounding here first means row 9 copies a correct function | Fowler |

---

## 9. Row #7 - The console stops claiming "never"

- **Scope:** Replace four all-time claims with the same fact over the window on screen.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte` - `which read every feed the ledger has ever carried`; `{clean} of {checked} feeds have never failed a read`; `feeds have never been read at all`; `feeds that never failed reported a source we have never read`
  - `frontend/src/lib/server/console-shell.ts` - the band and the strip render on all three console routes, so the fields behind those strings live here, not only in `+page.server.ts`
  - `frontend/src/routes/console/+page.server.ts` - the `sources.reduce(...)` totals over `opportunities`, `publications` and `source_failures`
- **Verify, do not assume:** whether `sourceHealthView` is windowed at source; whether `view.runsRead` on the machine page counts the window or the ledger. Fix whichever is not.
- **Replacement shape:** `No feed failed a read in these 30 days.` The window is named in the sentence and comes from the control, never hard-coded.
- **Acceptance gates:** local - the shared test selector. CI - browser smoke on all three console routes.
- **Oracle:** no reader-facing string on any console route contains `never`, `ever`, `all time` or `in all` as a claim about the record rather than the window.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A sentence that can only be true by reading everything is a growing read in different clothes. Rule #12 binds what a page says, not only what it reads | Owner D9, 2026-09-08 |
| 2 | The windowed sentence is more useful, not less: a feed that broke once in August and has been clean since is permanently disqualified by "never failed", and the operator's question is whether anything is broken now | This plan |
| 3 | Separated from row 6 into group C. Both rows edit `console/+page.server.ts`, and at N = 2 that is two worktrees on one file | Fowler, 2026-09-08 |

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
  - `backend/idhazh/contracts/` - one model per dataset with no published shape, each with an explicit forbidden-cell list
  - `schemas/` - generated. **Amend `public-telemetry.schema.json`; do not fork it.** New schemas stamp `version` `2026-09-08` and open a `changelog`
  - `schemas/search-index.schema.json` - a `changelog` entry, because row 16 changes what `model_id` means
  - `config/idhazh.json` and its config model - `assist.model_base_url`, `assist.model_revision`, `assist.model_fallback_url`, `assist.model_digests`; a retention knob per new dataset; the payload ceilings row 18 enforces
  - `frontend/src/contracts/` - regenerated
- **Acceptance gates:** local - `npm --prefix frontend run check`; the shared test selector. CI - the contract drift gate regenerates byte-identical.
- **Oracle:** `git diff --exit-code` after a regeneration run, and every dataset in the table above resolves to exactly one schema file.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The inventory is a row, not a paragraph inside the producer row. Without it, rows 9, 10, 11 and 18 each guess at the same missing list | Fowler, 2026-09-08 |
| 2 | `assist.model_revision` is refused at the contract unless it is a full 40-hex commit SHA. A tag or a branch can be moved, so it pins nothing | Andre, 2026-09-08 |
| 3 | `assist.model_digests` carries a SHA-256 per weight file. We hold the correct bytes today, so the pin becomes an assertion rather than a reference | Andre, 2026-09-08 |
| 4 | Config owns the **origin** only. `ENCODER_ID` stays a contract constant in `encoder.ts`, which says in terms that a knob there is a way to turn the guard off by accident | Fowler and Andre, converging, 2026-09-08 |
| 5 | `item_health_aggregate_keep_months` and `score_archive_keep_months` are `null` today. Any dataset given a month payload here gets a retention knob in the same commit, or the producer grows for ever | Carmack, 2026-09-08 |
| 6 | `console.shimmer_after_ms` is minted in row 12, where it gets its measured value, not here where nothing reads it for four rows | Fowler, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Shrink row 10's scope to telemetry and leave the nine aggregates prerendered | That is a special case, and D2 says there are none | Fowler |
| 2 | Fork a new telemetry schema rather than amend the existing one | Two schemas for one shape, and the committed shards validate against the old one | Fowler |
| 3 | Move `model_id` from constant to config, as the superseded draft proposed | It makes the guard a constant compared against a constant, and it moves the writer's string off `EMBEDDER_ID`, which is the one string `test_embed.py` pins to the TypeScript constant | Andre |

---

## 11. Row #9 - The producer writes the console its payloads

- **Scope:** The backend writes every payload row 8 minted, bounded, with nothing yet consuming them.
- **Files touched:**
  - `backend/idhazh/` - one producer per dataset, writing to `frontend/public/`
  - `backend/idhazh/publish_telemetry.py` - the `migrate()` carve-out named in decision 2
  - `frontend/scripts/copy-visuals.mjs` - stages the new payloads as it already stages the day payloads
  - `.github/workflows/digest.yml` - **the explicit path allow-list on both the artifact upload and the `Commit the day` step.** A payload absent from that list builds locally and never reaches the site
  - `backend/tests/` - producer tests from built fixtures
- **Acceptance gates:** local - `python -m pytest backend/tests/<the new tests>`. CI - `idhazh validate-days` passes; every payload validates against its schema.
- **Oracle:** run the producer twice against a fixture holding twenty months. The second run opens one month, not twenty. **Assert on file handles, not wall clock.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Monthly, not daily and not per-window. The state shards are already monthly, so the unit exists and a 30-day window is at worst two files | Read from `state/telemetry/` |
| 2 | A frozen month is written once. **Carve-out: `publish_telemetry.migrate()` may still rewrite a committed shard**, because it is what repairs a short header today. Without the carve-out every pre-migration month renders as unreachable in row 12, with a `Try again` that can never work | Fowler, 2026-09-08 |
| 3 | `parseTelemetryCsv` gains a short-header tolerance with a fixture shard, so a new bundle reads a frozen shard one column short instead of refusing the whole month | Fowler, 2026-09-08 |
| 4 | One month per run, never a walk. The run knows which month it just wrote | Rule #12 |

---

## 12. Row #10 - The console fetches instead of inlining

- **Scope:** The console stops serialising rows into its document and fetches the payloads row 9 writes.
- **Files touched:**
  - `frontend/src/routes/console/+page.server.ts`, `console/model/+page.server.ts`, `console/machine/+page.server.ts` - drop the ten dataset readers
  - `frontend/src/lib/server/console-shell.ts` - the band's derivation moves to the producer
  - `frontend/src/routes/console/+page.svelte` - `loadVisibleMonths()`, the pending-month set and the month cap already exist. **Promote them from "widen the window" to "load the page."** This is a reuse
  - `frontend/src/lib/server/chart-render.ts`, `frontend/src/lib/charts/` - charts render in the browser from fetched rows
- **Acceptance gates:** local - the shared test selector; `npm --prefix frontend run check`. CI - browser smoke on all four console routes, each with its payload present and absent.
- **Oracle:** `console/index.html` is under 400 KB. It is 3,726 KB today and 351 KB of that is markup, so the target is markup plus shell and nothing else.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The months list moves into the band payload.** `telemetryMonths` crosses in the document today; a shell cannot ask for a month until it knows which months exist, so leaving it out makes it a fifth serial hop | Carmack, 2026-09-08 |
| 2 | The cold-load chain is at most four hops: document, entry JS, band including the months list, month payload. Row 18 enforces it | Carmack, 2026-09-08 |
| 3 | The 32 charts move to the browser. They are 139 KB of 3,726 KB, so this is not where the bytes are - it moves because a chart drawn from fetched rows is the only way the window control can mean anything | Measured 2026-09-08 |
| 4 | First load fetches two month files and never more, whatever the archive holds. `monthCeiling(30)` = 2 and `monthCap` = 15 already enforce it | Carmack, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A request-count ceiling | Satisfied by merging files and says nothing about the wait. Chain depth and transferred bytes are the two that bound the experience | Carmack |

---

## 13. Row #11 - The verdict band arrives first and alone

- **Scope:** The band that answers "is the pipeline working" becomes its own small payload, fetched before anything else.
- **Files touched:** `frontend/src/lib/server/console-shell.ts`, `frontend/src/routes/console/+layout.svelte`, and the band payload from row 9.
- **Acceptance gates:** local - the shared test selector. CI - browser smoke; the band renders its own unreachable state per row 12.
- **Oracle:** the band payload is at most 8 KB gzip -5, and in a Playwright network trace it is the first request the console issues after the document and the entry bundle.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Susan ruled the band should stay prerendered and named a fetched band as the one way this change is a net loss. The owner overruled on consistency - one mental model, no special case, because a special case makes every future page ask which kind it is | Owner D2, over Susan, 2026-09-08 |
| 2 | This row is the mitigation both sides accepted: the band is the smallest payload on the site and the first request the page makes, so the operator's answer arrives in one round trip rather than after the page settles | Owner and Susan, 2026-09-08 |
| 3 | 8 KB rather than the 5 KB first proposed, because the months list from row 10 decision 1 rides here | Carmack, 2026-09-08 |

---

## 14. Row #12 - The console surface: reserved shape and three states

- **Scope:** The loading experience and the three data states, as one surface, reviewed once.
- **Files touched:**
  - `frontend/src/styles/app.css` and the token files - `shimmer` and the `loading` state class. Both are named in `docs/concepts/design-system.md`; neither exists in CSS today
  - `frontend/src/lib/charts/` - reserved boxes, axis frame and ticks, the missing-span mark
  - `frontend/src/lib/components/WindowControl.svelte` - the status line, and its no-script string, which becomes untrue the day this lands
  - `frontend/src/routes/console/+layout.svelte` - the no-script line above the panels
  - `config/idhazh.json` - `console.shimmer_after_ms`
- **What ships:**
  - Every panel titled and sized in the document. Charts reserve their box by aspect ratio and never change height
  - An empty chart draws its axis frame and tick marks and **no numbers**
  - The shimmer starts after `console.shimmer_after_ms`, so a fetch that lands first never animates
  - **Every skeleton shares one timeline, in phase.** Out of phase, twelve sweeping boxes read as twelve broken things
  - Under `prefers-reduced-motion`, a flat tinted block with **no gradient**. The global rule in `app.css` zeroes durations, which would freeze a moving gradient mid-sweep and leave a bright band nobody chose
  - Panels fill in document order; a panel that finishes early waits its turn
  - One status line for all background work, in words and files: `Fetching 2 months.`
  - Three states:

    | State | Means | Shows |
    | --- | --- | --- |
    | Quiet | The window is genuinely empty | Neutral tint, a sentence saying what is true, and the one preset that would change it |
    | Missing | We never had data for those dates | The span marked on the chart, dates named in the caption. No alarm |
    | Unreachable | The fetch did not arrive | Warn tint, names the month, says what it does have, `Try again` scoped to that panel |

  - A 92-day window where June has data, part of July is missing and August is fine plots June, marks the July span, and plots August
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
| 4 | `console.shimmer_after_ms` default 400 is an estimate. This row measures the median shard read and settles it | Rule #10 |

---

## 15. Row #13 - The page carries nothing a later run can change

- **Scope:** Delete the two global stamps that make every page's bytes move on every build, and show nothing in their place.
- **Files touched:**
  - `frontend/src/lib/components/SiteFooter.svelte` - the build line, the verification sentence, the retention sentence
  - `frontend/src/routes/+layout.server.ts` - returns `{ ui }` only; the `latestDate` and `loadDay` imports go
  - `frontend/vite.config.ts`, `frontend/src/app.d.ts` - `__BUILD_COMMIT__`, `__BUILD_DATE__`
  - `frontend/src/lib/components/EmptyDay.svelte`, `DigestList.svelte`, `MoreDays.svelte` and the call sites - the `latest` prop
  - `frontend/tests/footer-facts.spec.ts` - it pins the deleted sentences by regex
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

---

## 16. Row #14 - One document serves every date

- **Scope:** The 110 dated and topic documents stop being written; one document serves every URL.
- **Files touched:**
  - `frontend/src/routes/+layout.server.ts` - **`export const prerender = true` lives here and cascades to every route.** Flipping it is the actual mechanism; this is not a per-route flag change
  - `frontend/src/routes/+page.server.ts`, `frontend/src/routes/archive/+page.server.ts`, `frontend/src/routes/evals/` - **keep `/`, `/archive/` and `/evals/` prerendered explicitly.** Without this the site root stops emitting `index.html` and GitHub Pages answers `/` with the fallback at HTTP 404
  - `frontend/src/routes/[date]/+page.server.ts`, `[date]/[vertical]/+page.server.ts` - **deleted and rewritten as `+page.ts` with `ssr = false`.** A route that is not prerendered has no server, so `error(404, ...)` and the `awaiting` count move to the browser
  - `frontend/svelte.config.js` - the prerender block, `handleUnseenRoutes`, and the comment describing the seed-plus-fetch arrangement this row ends
  - `frontend/prerender-guard.js` - its expectations change or it goes
  - `frontend/src/service-worker.ts` - the shell it caches is now the whole site
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

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Shrink each dated document to a head - title, date, first summary | Keeps the preview card and 98 pct of the bytes, but a file per day is still a file per day | Owner |

---

## 17. Row #15 - Publish the Release asset and prove it cross-origin

- **Scope:** Stand up the failover origin and prove a browser can read it, before anything leaves git.
- **Files touched:** a GitHub Release carrying the five weight files; `docs/reference/measurements.md` for the result.
- **What must be proved, from a real browser, not curl:**
  - A `fetch()` from the Pages origin to the release asset URL succeeds cross-origin. **CORS is a second gate that `connect-src` does not cover**, and this is the failover leg - the one that only runs when the primary is already down
  - The redirect chain is recorded. `github.com/<owner>/<repo>/releases/download/...` redirects to an object host, and **CSP matches every redirect hop against the source list**
  - The same for the Hugging Face LFS path: a `resolve/` URL for a 23 MB file redirects to a CDN
- **Acceptance gates:** local - none. CI - none. This row produces a published asset and a recorded result.
- **Oracle:** a recorded browser trace showing a successful cross-origin `fetch()` of every weight file from the release asset, with the full redirect chain and every host that appears in it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Split from rows 16 and 17. Standing up two origins and deleting 43 MiB in one row means recovery is reverting a commit that deleted the weights | Andre, 2026-09-08 |
| 2 | **`connect-src` needs four to six origins, not two.** Listing only `huggingface.co` and `github.com` passes the small JSON files and blocks the 23 MB weights - the worst failure shape there is, because the pipeline half-loads and errors somewhere unrelated | Andre, 2026-09-08 |
| 3 | At least two of those hostnames are vendor-owned and can change without telling us. Row 19 records that as a standing maintenance cost | Andre, 2026-09-08 |

---

## 18. Row #16 - Two origins, a digest manifest, and one guard that still works

- **Scope:** The browser fetches the weights from Hugging Face, verifies them, falls back to our asset, and the `model_id` guard keeps meaning something.
- **Files touched:**
  - `frontend/src/lib/assist/loader.ts` - the fetch and the failover; `wasmPaths` unchanged and same-origin; **`cachedEncoder()` at line 108 keys on `${base}/assist/models/...` and will report `absent` for a reader who already holds the weights**, telling them to pay 43 MB again for ever
  - `frontend/src/lib/assist/encoder.ts` - `ENCODER_ID` stays a contract constant; **`ENCODER_VERSION` needs a decision, because it is what makes different weights a different URL and it goes dead when the directory does**
  - `frontend/src/lib/assist/search.ts` - the guard at line 107 already refuses a `model_id` mismatch; it must keep doing so against something that can actually differ
  - `frontend/svelte.config.js`, `frontend/asset-base.js` - `connect-src` gains every host row 15 recorded, derived from config
  - `backend/idhazh/embed.py`, `backend/idhazh/assemble.py` - `assemble.py` takes `model_id` from the newest day carrying vectors, not from a writer default; it is load-bearing and the superseded draft named neither file
  - `backend/tests/test_embed.py` - `test_the_versioned_directory_is_the_one_on_disk` asserts the model directory exists and goes red in row 17
  - `frontend/tests/filter-bar.spec.ts` - counts requests under the model directory; **it must not become a network test**
  - `frontend/src/service-worker.ts` - the cache decision
  - `frontend/src/lib/components/ArchiveSearch.svelte` - the download notice and the privacy sentence
- **The failover rule, sharpened:** all-or-nothing, per source, with a deadline and a digest. Try Hugging Face for all five weight files against a wall clock; verify every SHA-256 against `assist.model_digests`; on any miss - a non-200, a truncation, a timeout, or a digest mismatch - discard the whole set and take all five from the release asset. **Never mix provenance across files.**
- **Acceptance gates:** local - the shared test selector. CI - browser smoke with the model reachable, with Hugging Face blocked, and with both blocked; the drift gate; `python -m pytest backend/tests/test_embed.py`.
- **Oracle:** a deliberately corrupted digest in a fixture causes the whole Hugging Face set to be discarded and all five files taken from the failover, and a mismatched `model_id` still collapses search scope to the days that match.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A committed SHA-256 manifest for the weight files, verified in the browser before the bytes reach transformers.js.** We hold the exact bytes today. It costs five hex strings and one `crypto.subtle.digest` call, and it turns the revision pin from a reference into an assertion | Andre, 2026-09-08 - the one guard he would refuse to ship without |
| 2 | `ENCODER_ID` stays a constant and config owns only the origin. Moving it to config makes the guard a constant compared against a constant - it passes always and detects nothing | Andre and Fowler, converging, 2026-09-08 |
| 3 | A config-to-constant drift gate replaces the guard the directory used to provide: `assist.model_revision` cannot move without `ENCODER_VERSION` moving | Andre, 2026-09-08 |
| 4 | transformers.js tries **local first, then remote** when both flags are set. There is no built-in remote-first order, so the failover is our own code and this plan says so | Andre, 2026-09-08 |
| 5 | `filter-bar.spec.ts` runs against a locally-served model fixture origin. Rule #7 - no test touches the network - and the alternative is fetching 23.7 MB from Hugging Face inside CI | Andre and Carmack, converging, 2026-09-08 |
| 6 | The service worker does **not** cache the remote model. It refuses anything not same-origin GET and `frontend/tests/manifest.spec.ts` enforces that from source | Andre, 2026-09-08 |
| 7 | `ArchiveSearch.svelte` says what the first search will fetch and from where, before it starts. `DOWNLOAD_MB = 43` becomes a two-origin split derived from the digest manifest, because its own comment says a figure that drifts from the download is worse than no figure | Andre and Carmack, converging, 2026-09-08 |
| 8 | The privacy sentence gains one clause: the first search sends the reader's IP, User-Agent and Origin to a third party. "Nothing you type leaves your browser" stays true and is no longer the whole truth | Andre, 2026-09-08 |
| 9 | The `connect-src` widening is **not** exploitable by a planted instruction: nothing fetched from the web reaches the encoder, item vectors are computed on the runner, and no code path builds a fetch URL from a payload field. The risk inverts instead - a second party can now put bytes into a reader's tab, and decision 1 is what bounds that | Andre, 2026-09-08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A single origin, ours only | Recommended and overruled by the owner for availability | Owner D10 |
| 2 | Trust a pinned revision without a digest | A pin is a reference, not an integrity check; we never verify what arrived | Andre |
| 3 | Per-file failover | Gives a tokenizer from one origin and weights from another | Andre |

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
- **Files touched:** `frontend/scripts/` (the bundle gate), `config/idhazh.json` (the ceiling values and the payload set), `.github/workflows/ci.yml`, `.github/workflows/pages.yml`.
- **What changes:**

  | Ceiling | Value | Basis |
  | --- | --- | --- |
  | One telemetry month payload | 1.1 MB gzip -5 | `telemetry/` is 1.12 MiB over about 2 months, so about 0.6 MB a month. Structural ceiling is `run.safety_ceiling_per_run` 80 x 5 cron slots x 31 days = 12,400 items against about 9,400 rows over 30 days, giving 0.8 MB. Plus 30 pct. Revisit when a sixth cron slot or a higher safety ceiling lands |
  | Verdict band | 8 KB gzip -5 | Row 11's oracle, plus the months list |
  | Cold console load, all payloads, default window | 3.0 MB gzip -5 | Two months plus the band plus headroom |
  | Cold console chain depth | at most 4 hops | Row 10 decision 2 |
  | Page ceilings | re-derived from the migrated tree | The current values guard a document that no longer exists |
  | Encoder ceiling | **kept, re-aimed at the digest manifest** | Deleting it means nothing catches an upstream `.onnx` that grew |

- **Acceptance gates:** local - `npm --prefix frontend run bundle-gate` against a deliberately oversized fixture payload. CI - the gate fails on that fixture and passes on the real tree.
- **Oracle:** raise a fixture payload past its ceiling and CI goes red; lower it and CI goes green. Add a fifth serial hop to the console's cold load and CI goes red.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Ceilings are set in **gzip -5 bytes**, because that is what the reader pays. The project currently uses three units for one page: gzip -9 in the gate, gzip -5 on the wire, identity in the size report | Carmack, 2026-09-08 |
| 2 | The payload set is named in `config/`, not in the gate script. Rule #6 | Fowler, 2026-09-08 |
| 3 | Every ceiling value above is an estimate built from two measured points. Row 19 re-derives them from the migrated tree | Rule #10 |
| 4 | This row also re-measures the `browser` CI job. It sits at 37 pct of a 1,500 s timeout and six rows add specs to it; ESCALATE trigger 3 fires at 70 pct | Carmack, 2026-09-08 |

---

## 21. Row #19 - Record what was decided and what it cost

- **Scope:** The documentation this plan owes, and the measurements that replace its estimates.
- **Files touched:**
  - `docs/concepts/ui-shell.md` - **the spinner ban survives on narrower ground.** Its stated reason is that a reader already has a readable frame, and that reason is false on a route shipping an empty shell on purpose. Write the narrower ground down or the next agent reads the ban as absolute again. State 4 also becomes untrue
  - `docs/reference/measurements.md` - the post-migration `site-weight` output with hardware, date and n; the Hugging Face `Content-Encoding` result beside the existing compression table; the re-derived ceilings; the `browser` job duration
  - `docs/archive/measurements-2026-08.md` - a Hugging Face row in the compression table so the two origins read against each other
  - `docs/architecture/publishing/` - the shell, the fetch shapes, the three states, the measured bytes, and the fact that the build no longer refuses a bad SVG
  - `docs/concepts/growing-reads.md` - `outputFingerprint` walks a tree that gains files every published day and **still does after this plan**; plus the re-encode migration, and any read row 6 could not bound
  - `frontend/src/lib/assist/loader.ts` - the `DOWNLOAD_MB` docstring gains the two-origin split and the measured wire cost of each half
  - `config/idhazh.json` - one line on `pages_hard_cap_mb` saying 1024 is MiB while the platform limit is 1 GB, a 7 pct optimistic gap
  - `CLAUDE.md` section 0a - "the bundle must render complete with the model directory deleted" now describes a permanent state rather than a test
  - `docs/reference/agent-notes.md` - any tool or environment quirk a worker hit
  - `.github/workflows/` - row 1's dispatch job is deleted
- **Acceptance gates:** documentation-only closure; no local application suite, per AGENTS.md item 5.
- **Oracle:** every estimate in section 2 of this plan is replaced by a measurement carrying hardware, date and spread, or is deleted.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`assertBuild` still grows with the archive after this plan.** `static/digest/` gains a payload and its rendered images every published day, and both hashed trees carry them. Row 14's oracle is true of `build/` HTML only. This is Rule #12 inside the plan and it is recorded rather than fixed | Carmack, 2026-09-08 |
| 2 | The output-fingerprint rework of the superseded draft is closed, not deferred. Bytes fall about 32 pct and files about 14 pct, and the dominant term is the one that falls less | Carmack, 2026-09-08 |
| 3 | `8.14 ms per file` is a derivation, not a measured constant - it is 12.93 s over 1,589 files, and the same run equally yields 17.2 MB/s. One data point cannot separate a per-file term from a per-byte term | Carmack, 2026-09-08 |
| 4 | Row 1's dispatch job is deleted here rather than kept. A measurement harness nobody runs is a maintenance cost with no reader | This plan |

---

## 22. Refused, with the measurement that refused it

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

---

## See also

- [`CLAUDE.md`](../CLAUDE.md) - sections 0, 0a, 6, 9, 11, 12, 13, 14; Rules 1, 2, 3, 6, 7, 10, 11, 12.
- [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan stamps.
- [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every acceptance gate here.
- [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - where a chosen growing read is recorded.
- [`docs/concepts/design-system.md`](../docs/concepts/design-system.md) - the motion set and state classes row 12 first uses.
- [`docs/concepts/ui-shell.md`](../docs/concepts/ui-shell.md) - the five states and the spinner ban row 19 narrows.
