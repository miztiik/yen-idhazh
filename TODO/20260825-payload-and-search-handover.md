# Handover - what the published site loads, and what should index the search

**Last Updated**: 2026-08-25

Research brief. Non-authoritative working material (`CLAUDE.md` section 3). This is NOT an execution-ready plan: it carries findings, open questions and the measurement that would settle each. The next agent researches, then authors a plan per [`../docs/how-to/author-a-plan.md`](../docs/how-to/author-a-plan.md).

Run the bootstrap ritual in [`../docs/agents/bootstrap.md`](../docs/agents/bootstrap.md) first. If this file and `docs/` disagree, `docs/` wins (Rule #4).

**Independent of the console-charts work, which shipped 2026-08-25 in PRs #89, #92, #93, #94 and #97.** That work moved first-load JS; this one moves HTML weight. Their file sets overlapped only at `frontend/tests/console.spec.ts`. The byte ceiling it left behind in `frontend/scripts/bundle-gate.mjs` is scoped to first-load JS for exactly this reason, so it does not gate the HTML this handover is about.

---

## 1. The measured problem

All figures taken 2026-08-25 on this repository: `npm run build` in `frontend/`, then `gzip -9` over each route's HTML and its preloaded modules.

| Route | HTML gz | First-load JS gz |
| --- | --- | --- |
| `/console/` | 268.9 KB | 52.9 KB |
| `/` | 192.8 KB | 48.0 KB |
| `/2026-08-25/` | 374.7 KB | 47.9 KB |
| `/2026-08-25/ai/` | 372.5 KB | 48.0 KB |
| **`/archive/`** | **873.1 KB** | 43.4 KB |

Whole build 133.8 MB over 123 files, against the 1 GB Pages cap (Rule #2).

### Two different causes wearing one coat

**Cause A - the console pays for a payload it never reads.** [`frontend/src/routes/+layout.server.ts`](../frontend/src/routes/+layout.server.ts) returns `day: loadDay(latest)`, which SvelteKit inlines into every prerendered page. [`frontend/src/routes/console/+page.svelte`](../frontend/src/routes/console/+page.svelte) references only `data.ui` - `data.day` appears nowhere in it. Pure waste, roughly 1.3 MB of HTML per page.

**Cause B - the archive is eager on purpose, and it does not scale.** [`frontend/src/routes/archive/+page.server.ts`](../frontend/src/routes/archive/+page.server.ts) returns `payloads: loaded` - every published day, whole - with a comment saying why: the vectors inside them are what let the search run without the browser embedding anything but the query. The page renders `data.days` (date, item count, partial) as a list, then passes `data.payloads` to `<AssistSearch>`.

### The growth curve

Measured over the five published days, 1182 items: **520.7 KB raw / 140.6 KB gz per day.**

| Days on `/archive/` | raw | gzipped |
| --- | --- | --- |
| 5 (today) | 2.5 MB | 703 KB |
| 30 | 15.3 MB | **4.1 MB** |
| 90 | 45.8 MB | 12.4 MB |
| 365 | 185.6 MB | **50.1 MB** |

Linear, on one page, paid by every visitor on every visit.

Per-day detail, because one number hides the shape:

| Day | raw KB | gz KB | items | vectors KB | vector share |
| --- | --- | --- | --- | --- | --- |
| 2026-08-21 | 11.3 | 4.2 | 4 | 2.1 | 18.2% |
| 2026-08-22 | 27.3 | 10.5 | 10 | 5.2 | 18.9% |
| 2026-08-23 | 369.6 | 117.3 | 147 | 71.8 | 19.4% |
| 2026-08-24 | 1533.7 | 386.8 | 731 | 76.0 | 5.0% |
| 2026-08-25 | 661.8 | 184.3 | 290 | 76.0 | 11.5% |

**The embedding vectors are not the problem.** 8.9% of the bytes overall, and they plateau near 76 KB a day. The items are the weight, and a day accumulates items across its five runs - 2026-08-24 holds 731.

**Cause C - the console receives its telemetry rows twice.** [`frontend/src/routes/console/+page.server.ts`](../frontend/src/routes/console/+page.server.ts) returns `telemetryRows: publicRows`, [`+page.svelte`](../frontend/src/routes/console/+page.svelte) passes them as `initialRows={data.telemetryRows}`, and [`Viewport.svelte`](../frontend/src/lib/components/Viewport.svelte) also fetches the monthly telemetry CSVs at runtime.

**Cause D - retention is not running.** `config/idhazh.json` has `retention.dry_run: true` and `retention.image_months: -1` against a `site_budget_mb` of 800. Nothing is being pruned, so every curve above is unbounded.

---

## 2. Verified, do not re-derive

| Claim | Evidence |
| --- | --- |
| The console never reads `data.day` | grep of `frontend/src/routes/console/+page.svelte` - only `data.ui` |
| The archive ships whole payloads for search only | `archive/+page.server.ts` returns `payloads`, `+page.svelte` uses `data.days` for the list and `data.payloads` for `<AssistSearch>` |
| The search is a dot product, not SQL | [`frontend/src/lib/assist/search.ts`](../frontend/src/lib/assist/search.ts) - base64 int8 to unit vector, then dot products. Vectors computed on the runner and committed in the day payload |
| The encoder is 43 MB and reader-initiated | `DOWNLOAD_MB = 43`, `MODEL_ID = 'all-MiniLM-L6-v2'` in [`frontend/src/lib/assist/loader.ts`](../frontend/src/lib/assist/loader.ts); `allowRemoteModels = false`, served same-origin |
| Heavy things are already kept off the first-load path | [`frontend/scripts/bundle-gate.mjs`](../frontend/scripts/bundle-gate.mjs) greps `entry/` and `nodes/` for `@huggingface/transformers`, `onnxruntime-web`, `ort-wasm`. It has no byte ceiling |
| No CDN is possible | [`frontend/svelte.config.js`](../frontend/svelte.config.js) ships `script-src: ['self', 'wasm-unsafe-eval']`; and the HTTP cache is partitioned by top-level site in Chrome 86+, Firefox 85+ and Safari, so a cross-site cache hit cannot happen |
| DuckDB-WASM costs 34.1 MB raw / 7.8 MB gzipped | `gzip -9` over `duckdb-eh.wasm` in yen-gov's `node_modules`. Siblings: `duckdb-mvp.wasm` 39.2 MB, `duckdb-coi.wasm` 33.8 MB |

---

## 3. The cheap wins, which need no research at all

These are deletions. They can ship before any of the questions below are answered, and they should.

1. **Stop inlining `day` into routes that do not read it.** Either move it out of the root layout into the routes that use it, or make it lazy. This is the single largest byte win on the site.
2. **Stop sending the console its telemetry rows twice.** Pick the inline copy or the runtime fetch; the viewport already merges what it fetches.
3. **Decide whether `retention.dry_run` stays true.** Every projection above assumes nothing is ever pruned, which is the current behaviour.

---

## 4. The open question

**The archive is eager because search needs every payload. So: what should index the search?**

Everything else follows from that answer. If the search has its own index, the archive page carries a list - about 60 bytes a day - and fetches a day's committed `digest.json` only when a reader opens it. Rule #1 explicitly permits fetching our own committed files at runtime, and every day payload is already a static file on the origin.

### The owner's hypothesis, to be tested rather than assumed

- DuckDB-WASM, accepting a high one-time load.
- A monthly archive index; the last N days (N-1 or N-7) served directly, everything older queried through wasm.
- One index per month, searched in the browser.
- The same machinery may serve the chat/search interface that is still pending.

### What has to be settled before a plan can be written

| # | Question | What settles it |
| --- | --- | --- |
| 1 | **Is DuckDB the right shape for THIS search?** The current search is a dot product over 384-dim int8 vectors - a nearest-neighbour problem. DuckDB gives SQL and columnar scans, not an ANN index. | Write the query both ways over the committed vectors for 90 days of items and compare recall and latency. If DuckDB's answer is "full scan with a dot product in SQL", it has bought nothing the current code lacks. |
| 2 | **When does DuckDB pay for itself?** Its 7.8 MB gzipped fixed cost equals about 56 days of the current 140.6 KB/day archive growth. Below that horizon it is more bytes, not fewer - but it is a one-time cost against a per-visit linear one, so the comparison depends on repeat-visit behaviour we do not measure and will not (Rule #1 forbids telemetry). | Reason it explicitly on stated assumptions, and write the assumptions down. An unstated assumption here is what makes the whole decision unfalsifiable. |
| 3 | **What is the cheapest thing that works?** Candidates, all of which must be priced: a committed per-month index file (JSON or a compact binary) fetched on demand; `sql.js` or `wa-sqlite` (roughly an order of magnitude smaller than DuckDB); or no database at all - fetch the one day file the reader asked for. | Byte cost per first visit at 30, 90 and 365 days for each, plus query latency on a mid-range phone. |
| 4 | **Does the console want the same tool as the archive?** They are different problems. The console reads a wide CSV and aggregates by day, which is what a columnar engine is genuinely good at. The archive does nearest-neighbour over vectors, which it is not. | Decide them separately, and say so, even if one tool ends up serving both. |
| 5 | **What does the chat/search interface actually need?** It is named as pending but not specified anywhere in `docs/`. | Specify it before letting it justify a dependency. A pending feature is not a beneficiary (Rule #8). |
| 6 | **Does a monthly shard boundary match how a reader searches?** A month is how `state/` is sharded, which is a writer's convenience. | State the reader behaviour the sharding serves, or pick a boundary that does. |

---

## 5. Constraints the research must honour

- **Rule #1.** Static-first. Fetching our own committed files at runtime is allowed and is how an interactive view reads its data. A third-party asset is judged on its bytes, its licence and its privacy behaviour. No service, no telemetry, no runtime call home.
- **Rule #2.** 1 GB published site. The build is 133.8 MB today; committing a 34 MB wasm binary spends 3.4% of the cap and must be counted, not waved through.
- **Rule #8.** Every dependency names a beneficiary feature and its cost. "It may help the chat interface" is not a beneficiary until the chat interface is specified.
- **Rule #10.** Measured, not estimated. Every byte figure in this file carries its method; keep that standard.
- **`bundle-gate.mjs` keeps heavy things off the first-load path.** Whatever lands must be reader-initiated the way the encoder already is, and the gate must be extended to name it.
- **Self-host.** The CSP is `script-src 'self'`, and the partitioned HTTP cache means a CDN saves nothing.

---

## 6. Settled, do not re-litigate

| Decision | Why it is closed |
| --- | --- |
| No library from a public CDN | Partitioned cache since 2020 makes a cross-site hit impossible, and our CSP blocks it before the cache is consulted |
| No canvas charting library | Cannot prerender, cannot inherit a CSS custom property. `uplot` was carried and removed in #57 |
| The embedding vectors stay in the day payload | They are 8.9% of the weight; removing them saves 9% and costs the search its only input |

---

## See also

- [`../docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the console-charts work that first recorded these findings; it shipped 2026-08-25 and its rules live here now.
- [`../docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - what the published surface loads today.
- [`../docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md) - what Assemble writes and the retention rules.
- [`../docs/reference/measurements.md`](../docs/reference/measurements.md) - where any new number belongs.
- [`../docs/how-to/author-a-plan.md`](../docs/how-to/author-a-plan.md) - the format for the plan this research produces.
