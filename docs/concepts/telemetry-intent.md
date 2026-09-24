# Telemetry Intent

**Last Updated**: 2026-09-24

What must be true about telemetry once this workstream is done - how a measurement is written, where it sits, how it reaches a browser, and how it is drawn. A thing that contradicts one of the eleven below is not a trade-off, it is a defect.

"Intent" is [`CLAUDE.md`](../../CLAUDE.md) section 0d's word: what the user wants to be true when the work is done. Intent sits above the contract and the contract sits above the code, so where this page and the tree disagree, **the tree is what changes**. That is also the warning label: several of these are not true yet, and a reader must not take a row here as a description of what the pipeline does today. For today's shape read [telemetry.md](telemetry.md), [partitions.md](partitions.md) and [../architecture/publishing/console-payloads.md](../architecture/publishing/console-payloads.md).

## The eleven

| # | Intent | What it replaces |
| --- | --- | --- |
| N1 | **Parquet is the telemetry format at rest. CSV is retired.** PyArrow writes it. | Every `.csv` under `state/`, and the `migrate_header` complex that exists only because a column moved |
| N2 | **DuckDB-Wasm parses it in the browser.** | Node reading CSV at build time |
| N3 | **The browser fetches its own data.** Every chart pulls the bytes it needs, at view time, over HTTP. | Data baked into HTML by the build |
| N4 | **Prerendering is an anti-pattern here.** No new prerendered data page, and the existing ones come off it. | `export const prerender = true` on every console route |
| N5 | **d3.js is the only charting library. ECharts is retired.** | `echarts`, `Chart.svelte`, `engine.ts`, `core.ts`, and the server-side SVG renderer that exists only to serve them |
| N6 | **Single-Writer & Immutable Paths.** One writer per path; bytes never change after that writer closes the file. | Shared day files, in-place rewrites, `merge=union` |
| N7 | **`state/` is the console's only source. No telemetry projection survives in `frontend/`.** The console reads the ledgers, not nine pre-shaped views of them. | The nine projections under `frontend/public/` |
| N8 | **`frontend/` holds UI code, not production artefacts.** Telemetry does not live there in git. | `frontend/public/telemetry/`, `machine/`, `span-rollup/`, `run-timeline/`, `run-days/`, `day-metrics/`, `console/band.json` |
| N9 | **A file is named `<uuid8>.parquet`.** One token: a millisecond clock in the high bits, a hash of the unit of work in the rest. Sorts by arrival, carries identity, and nothing reads it. | `<date>-<run>-<attempt>-<job>-<shard>.csv` |
| N10 | **`state/` splits into `state/raw/` and `state/compact/`.** Writers only ever append to `raw`; `compact` is derived and may be rebuilt from it. | One `state/` tree where a writer's file and a folded file sit together |
| N11 | **Every tree under `state/` is sharded to one pattern, with no exceptions:** `state/raw/<dataset>/<YYYY>/<MM>/<DD>/<uuid8>.parquet`, where the date is `covers_date` - the day the rows describe - and `<uuid8>` is N9. One file per writer per unit of work. A tree where two writers still share a path is a tree not yet migrated. | `merge=union` on nine trees, the flat `feed-retirements.csv`, and every remaining shared-path append |

## When one of these meets a limitation

A guardrail, a budget, a schema, a dependency or a design already shipped is a cost to price, never an answer on its own. Three moves are legitimate and "we cannot, because X" is not one of them: do it and say what it moved; price it and recommend; or name the measurement that would settle it and the smallest step that makes progress meanwhile. [`CLAUDE.md`](../../CLAUDE.md) section 0d is canonical.

Two things do not bend to this page. The 6 h job cap and the 1 GB published site are GitHub's rather than ours ([`CLAUDE.md`](../../CLAUDE.md) Guardrail #2), so a design that does not fit is a design failure and the next move is to name the design that does. And fetched article text stays data rather than instruction (Guardrail #11), whatever a format or a reader wants.

## What this page is not

It is not a queue. It carries no row status, no owner and no order of work - a plan-doc under [`TODO/`](../../TODO/) carries those, in its own Status Reckoner, and a second list somebody retypes is a list that rots ([`AGENTS.md`](../../AGENTS.md)). This page says what has to be true; a plan says who does what next.

It is not a measurement either. Every figure that prices one of these - what a Parquet shard weighs, what DuckDB-Wasm costs a reader, what a prerendered route costs today - belongs in the reference tier with its hardware and its date ([`CLAUDE.md`](../../CLAUDE.md) Guardrail #10).

## See also

- [principles.md](principles.md) - the beliefs these eleven are an application of.
- [vision.md](vision.md) - what the project is and is not.
- [telemetry.md](telemetry.md) - the instrument as it stands: the event vocabulary, the span tree, and where each record lands.
- [partitions.md](partitions.md) - what a layout obliges a writer to do, and the grains in force today.
- [growing-reads.md](growing-reads.md) - what a read over a growing collection has to declare.
- [../architecture/publishing/console-payloads.md](../architecture/publishing/console-payloads.md) - what the console reads today and where each payload comes from.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - the published series N7 and N8 retire.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - how a persisted shape is declared, stamped and migrated.
- [../../CLAUDE.md](../../CLAUDE.md) - the contract; section 0d is intent, contract, code.
