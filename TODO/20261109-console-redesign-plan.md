# Compact-ledger console recovery and redesign

**Last Updated**: 2026-11-13
**Level**: 5 - resolve design gates before implementation.
**Status**: Rows 1-7 and Rows 8a-8e are complete. Row 8f moves N1/N2 without changing their measurements or endpoint groups. N4/N5 remain queued for separate delivery; H14's nullable-flag design is complete and follows those remaining moves.

## 0. Operating contract

Table A

| ID | Field | Value |
| --- | --- | --- |
| A1 | Goal | Reduce clutter, fix retained charts and diagnose compact-data publication lag. |
| A2 | In scope | - Permanently remove charts and actually move retained charts between pages once their individual dispositions are settled.<br>- Replace the full console palette, typography, navigation, controls, status hierarchy and chart styling.<br>- Reimagine the retained read/write-token comparison as per-run lines with Run total / Median per article.<br>- Retain compact Parquet, DuckDB-Wasm and D3.<br>- Diagnose publication lag without changing compaction eligibility, cadence or retention. |
| A3 | Out of scope | Table B. |
| A4 | Governing pages | [Console delivery](../docs/architecture/publishing/console.md), [chart data](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md), [window rules](../docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md), [compaction](../docs/architecture/publishing/ledger-compaction.md), [design system](../docs/concepts/design-system.md). |
| A5 | Architecture | Compact Parquet -> shared DuckDB-Wasm reader -> typed result -> presentation adapter -> D3. No chart exports. Fowler supports retaining this path. |
| A6 | ESCALATE | 1. Unsettled persisted shape, publication permission or protected-contract change.<br>2. An unchosen permanent cut, move, diagnostic loss or token anomaly/baseline rule.<br>3. Current-day or uncommitted data required.<br>4. New source, engine, component framework or arbitrary SQL network access.<br>5. An unresolved gate or file inventory for the affected row, not unrelated rows.<br>6. Publication fix without an established root cause. |
| A7 | Execution | One nested session per PR; parallel N = 1 because shell, roster, window and config edits overlap. Row 1 defines the handoff; Table L assigns each remaining gate to its implementation row. |

Execute per docs/how-to/execute-a-plan.md: one nested session per PR; parallel N = 1; merge after required CI passes; pause only the row whose design gate is unresolved.

Table B

| ID | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Raw discovery, raw indexes and raw/compact settlement | Unpacked work remains unavailable. | Separate discovery, consistency, retry, permission and retention design. |
| B2 | Partial current-day packing or another snapshot layer | The open UTC day remains unavailable. | A current-day requirement and partial-coverage contract. |
| B3 | Chart exports or rendering-only ledger columns | Presentation adapters remain. | A missing native measurement, not a chart convenience field. |
| B4 | Publishing private inputs or changing the ordinary-panel origin | Existing publication clocks remain. | A source/permission decision; registration is not consent. |
| B5 | Reader-site redesign | Reader pages retain their current layout and theme. | Resolve L1 and revise the file inventory. |
| B6 | Historical backfills or telemetry rewrites | Missing or incorrect historical readings remain unresolved. | Independent historical evidence and a migration design. |
| B7 | New accessibility audit tooling or per-panel browser coverage | Existing behavioral coverage and design review remain. | A changed project requirement. Labels, keyboard access and visible focus remain in scope. |

## 1. Status Reckoner

Table C

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Define console redesign and chart changes | - | A | DONE | `reimagined-bassoon` | - | App session `5a68b1fe-c1ab-4f8d-b706-ef758cc38288`; branch `console-design-contract` |
| C2 | 2 | Diagnose compact-data publication lag | 1 | B | DONE | `urban-couscous` | - | App session `8605dbb5-0bdf-4a83-8948-d7c58ff90891`; branch `diagnose-compact-publication-lag` |
| C3 | 3 | Replace the full console visual system and share window behavior | 1 | C | DONE | `vigilant-funicular` | - | App session `758b5e38-010f-4ba5-9945-399a21883402`; branch `console-visual-rebuild` |
| C4 | 4 | Remove the duplicate refusal view and redraw run token volume | 1 | D | DONE | `cuddly-doodle` | - | App session `68c70212-4ac7-4a55-883e-f76bf3f4945c`; branch `settled-console-charts` |
| C5 | 5 | Correct retained chart readings and evidence windows | 4 | E | DONE | `redesigned-system` | - | App session `1981e1da-00bf-456b-a4db-13554ac3fb87`; branch `chart-readings-and-windows` |
| C6 | 6 | Restore collection needed by retained hardware diagnostics | 4 | F | DONE | `animated-fiesta` | - | App session `7e6961ce-76c2-4e78-ad8c-f4991bad6ce5`; branch `restore-hardware-telemetry` |
| C7 | 7 | Make retained explorer answers directly reachable and drawable | 1 | G | DONE | `ubiquitous-doodle` | - | App session `735f58fd-23bf-4189-9efb-d08402988c46`; branch `explorer-reliability` |
| C8 | 8 | Deliver selected cuts, page moves and the queued token flag | 1 | H | IN-FLIGHT | - | - | M8/M9 are implemented in Row 8e; Row 8f delivers N1/N2. N4/N5 remain selected for separate delivery, followed by H14's settled design. |
| C9 | 8a | Simplify selected Pipelines visual diagnostics | 1, 5 | I | DONE | `psychic-goggles` | - | App session `3932eb6c-014c-40e4-9e51-5617ff2c30f0`; branch `pipelines-visual-diagnostics` |
| C10 | 8b | Remove the Pipelines written-type diagnostic | 8a | J | DONE | `legendary-garbanzo` | - | App session `da0bfe17-ef48-4e8f-93d2-7c92c1dd13ce`; branch `remove-written-type-diagnostic` |
| C11 | 8c | Remove the Summaries model-change comparison | 8b | K | DONE | `jubilant-happiness` | - | App session `705cdced-00f1-4c51-bbe0-ae3c6079063b`; branch `remove-model-change-comparison` |
| C12 | 8d | Refine machine history, align console colours and move the article ranking | 8c | L | DONE | `supreme-winner` | #2038 | App session `740c1208-b227-45bf-9307-f57983e73022`; branch `refine-hardware-move-latency` |
| C13 | 8e | Remove the hypothetical runner-price and watchlist-catch panels | 8d | M | DONE | `automatic-system` | - | App session `d8f596b7-628e-4abf-824a-7d507083ba36`; branch `automatic-system` |
| C14 | 8f | Move model timing to Summaries and summary duration to Pipelines | 8e | N | DONE | `legendary-parakeet` | - | App session `2a328b2e-5dfd-49e5-879a-a1950dd5d975`; branch `legendary-parakeet` |

## 2. Row #1 - Define console redesign and chart changes

- **Scope:** Define the full visual replacement, concrete cut/move proposals and row-scoped readiness without treating undecided losses as selected.
- **Files touched:**
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: verify current F-K rosters and displayed titles, price every proposed cut, distinguish settled dispositions from proposals, and assign each remaining gate and inventory to its affected row. CI: docs-only checks. Row 1 completion does not close Row 3's contract gate or select Row 4's remaining changes.
- **Oracle:** Every current panel has one disposition and each changed chart has a concrete title, source page and destination or named loss. A roster match does not establish metric equivalence or settle a loss.

### Decisions

Table D

| ID | Decision | Authority |
| --- | --- | --- |
| D1 | Native panels already query Parquet with SQL; many aggregates remain in TypeScript. Retain A5. | `data/engine.ts`, `slice-query.ts`, `console/queries/window.ts`; Fowler. |
| D2 | Build-time exceptions remain: Pipelines manifests/item facts/day metrics; Summaries cards/item decisions; Voices source decisions; Judgement judging/holdout evidence. | Console delivery contract. |
| D3 | Page purposes: Pipelines - delivery/stage latency; Summaries - quality/model rates; Hardware - constraints/resources; Voices - sources; Judgement - merges. Tables M/N propose permanent cuts and actual moves; F-K track each current panel. | Current queries/reducers; page-purpose review. |
| D4 | Full console replacement: warm-neutral light/dark canvas, teal controls, labelled left navigation, new type hierarchy, compact status and shared chart styling. Reader styling and data meanings stay unchanged. | Susan's complete visual specification and integration ruling. |
| D5 | Use the existing flat route rosters for presence and order. A cut deletes the chart, not hides it; a move mounts it on its destination page, not behind a link on its old page. No presentation metadata, stamped roster format or generic composition framework. | Permanent-removal and relocation scope. |
| D6 | Table O is selective defect triage, not a mandatory fix bundle. | Plan scope. |
| D7 | The inspected Hardware viewport contains chrome and repeated status before chart evidence. Put a useful comparison in the first viewport; do not shrink chart text. | Browser/source inspection; Susan. |
| D8 | `AppearanceConfig.console_style` owns the replacement's colors, type and spacing. The existing CSS generator emits them before paint over the entire operator page, including its canvas and header; no runtime theme fetch or new assets. The JSON below declares design defaults, not measured findings. | Fowler contract ruling; Susan visual defaults. |
| D9 | The style model is defaulted and rejects unknown fields. Colors are lowercase six-digit hex; categorical arrays have eight distinct entries and remain separate from confidence/movement roles. Fonts are `inter`, `system-sans` or `system-mono`. Missing blocks/leaves use native defaults; arrays replace whole; explicit null is legal only for `grid_dash_px`. | Native contract before consumption; additive read compatibility. |
| D10 | Finite strict style numbers: type size 0.75-4 rem, leading from size to twice size, weight integer 100-900, tracking -0.1 to 0.2 em; gaps/padding 0-4 rem, rail 8-18 rem, header 3-5 rem, primary targets 2.75-4 rem, radii 0-2 rem, wide columns integer 1-2. Shadows: y 0-16 px, blur 0-32 px, alpha 0-0.2. Axis/grid strokes 0.5-2 px, series 0.5-4 px, grid opacity >0 to 1, dash null or two 0.5-16 px values, caps `butt`, `round` or `square`. Reject booleans/strings as numbers and invalid values rather than emitting CSS. | Bounded style construction; existing primary-control floor. |
| D11 | Version/changelog only the appearance contract, current appearance file and its existing fixture when Row 3 implements the block. AppConfig and ConsoleConfig remain unchanged. Bind the small frontend copy/defaults and vocabularies to the native model; use the existing generated CSS file, not a new theme framework. | Fowler; one native appearance authority. |
| D12 | Console label size/leading must reach actual frame/axis measurement through existing ChartConfig and optional geometry inputs. Use computed CSS-pixel size for spacing and label thinning; preserve reader defaults. CSS-only enlargement over old 10px arithmetic is invalid. | Existing frame/axis consumers; Susan integration ruling. |
| D13 | Optional window storage belongs to mounted layout state, shared through the window slot. Keep the existing key/preset encoding; validate presets; warn on read/write failure; retain the in-memory choice across routes. Queries never wait for storage. | Existing window behavior; storage defect. |
| D14 | Moves preserve source query columns, scope and endpoint groups: Hardware latency uses item/host/run-shards reach, while the fixed-work comparison keeps item/quality reach. Destination-page reach must not replace either. Keep means, medians, per-run tails, rates and token volumes distinct. | Direct query/consumer inspection. |

### Rejected alternatives

Table E

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Replace the engine or add a component framework for the sidebar | Does not fix duplication, freshness or bad readings. | Port Svelte controls, price added assets and identify a missing capability. | Fowler, Susan. |
| E2 | Fix every panel before pruning | Repairs presentations that may leave the default view. | Implement and verify the full old inventory. | Jony. |
| E3 | Delete visually similar charts | Similar charts can use different clocks or cohorts. | Prove metric parity or name the diagnostic loss. | Jony. |
| E4 | Replace permanent removal/moves with disclosure metadata | Hides charts or leaves them on their old pages instead of delivering the requested change. | A different capability and a new config contract; not this plan. | Presence/order stays in existing flat rosters. |

### Panel-by-panel dispositions

Table F - Pipelines; source: `config/console/pipelines.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| F1 | `at-a-glance` | Published output | KEEP; totals, not attempt rates. |
| F2 | `run-health` | Plan versus delivery by day/run | KEEP; exposes individual failures. |
| F3 | `site-cost-per-item` | Storage growth per published article | KEEP; bytes, not latency or money. |
| F4 | `failure-mix` | Failures by stage/rule | KEEP as the canonical failure view. |
| F5 | `item-time-split` | Stage contribution to elapsed time | KEEP; complete-cohort means and signed overlap remain distinct from medians. |
| F6 | `slower-on-same-work` | Fixed-work latency trend | SELECTED MOVE to Hardware; N5. Separate follow-up preserves normalization/reference cohort and original endpoint. Still on Pipelines in Row 8e. |
| F7 | `stage-timings` | Daily stage medians | KEEP; each stage has its own timed cohort. |
| F8 | `item-cost` | Model read/write latency | MOVE to Summaries in Row 8f; N1. Independent clock distributions, per-token costs and item-health-only endpoint remain unchanged. |
| F9 | `run-timeline` | Newest-run work, waits and overlap | KEEP; run scheduling, not window averages. |
| F10 | `chart-drawing` | Visual delivery versus cost | KEEP; Row 8a carries the existing stage colours into the flow without changing published-item denominators. |
| F11 | `pipeline-funnel` | Where visual attempts stop | REMOVE permanently in Row 8a; M1 names the lost stage-by-class diagnostic. |
| F12 | `downgrade-funnel` | Replacement-search outcomes | REMOVE permanently in Row 8a; M2 names the lost draft outcomes and search depth. |
| F13 | `visual-refusals` | First plan-check refusals | RETAIN on Pipelines as daily lines in Row 8a; M3. Preserve all reasons, including attempts later written. |
| F14 | `visual-written-types` | Requested versus written types | REMOVE permanently in Row 8b; M4 names the lost planned-to-written type comparison. |
| F15 | `extraction` | Extraction integrity and chartable yield | REMOVE permanently in Row 8a; M10 names the distinct extraction class/flag/yield diagnostic loss. |
| F16 | `article-age` | Source age at work start | KEEP; Row 5 corrects the publication-age title, not the recorded clock. |

Table G - Summaries; source: `config/console/model.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| G1 | `model-cards` | Summary outcome status | KEEP; preserve instruments and evidence dates. |
| G2 | `model-throughput` | Read/write rates | KEEP; distinct from elapsed-time distributions. |
| G3 | `call-ending` | Normal endings versus truncation | KEEP; calls are not failed items. |
| G4 | `refusing-rule` | Model reply refusals | REMOVE permanently in Row 4; M5. Pipelines retains failed-rule metrics and model-stage access. No hidden chart or second query. |
| G5 | `doubt-reasons` | Published summary band reasons | KEEP; distinct from request failures. |
| G6 | `faithfulness` | Score median/spread versus bands | KEEP; counts alone miss distribution changes. |
| G7 | `source-doubts` | Quality by source | KEEP; distinct from feed/fetch reliability. |
| G8 | `write-cost` | Summarizing latency distribution | MOVE to Pipelines in Row 8f; N2. Positive-clock distribution, median/p95, untimed count and common item-health/evaluation endpoint remain unchanged. |
| G9 | `score-cost` | Checker latency | KEEP; not model-writing time. |
| G10 | `summary-length` | Output length versus requested bands | KEEP; distinct from context and source cuts. |
| G11 | `model-change` | Before/after model change | REMOVE permanently in Row 8c; M6 names the lost observational comparison across different article populations. |

Table H - Hardware; source: `config/console/machine.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| H1 | `two-clocks` | Rate-instrument agreement | KEEP first; independent clocks versus tolerance. |
| H2 | `processor-lost` | CPU contention | REMOVE permanently in Row 8d; M11 names the lost processor-steal view. Collection and stored readings remain. |
| H3 | `disk-reads` | Paging/re-read activity | REMOVE permanently in Row 8d; M12 names the lost model paging/re-read view. O2's retained memory/process consumers remain. |
| H4 | `machine-cards` | Newest-run machine constraints | REMOVE permanently in Row 8d; M13 names the lost newest-run hardware detail. Host identity and raw/compact records remain. |
| H5 | `slower-machines` | Relative machine performance | KEEP; distinct from a daily fixed-work trend. |
| H6 | `platform-mix` | Observed job placement | KEEP AND REFINE in Row 8d; M7. Stable categorical identity gradients, compact framing/hover and complete selected-day details; original counts, folds and endpoint remain. |
| H7 | `slowest-articles` | Newest-run latency outliers | MOVE to Pipelines in Row 8d; N3. Preserve original run-wide ranking and independent endpoint group. |
| H8 | `tail-trend` | Summarizing latency tails | SELECTED MOVE to Pipelines; N4. Separate follow-up preserves per-run percentiles and original endpoint. Still on Hardware in Row 8e. |
| H9 | `closest-to-memory` | Article memory headroom | KEEP; each article uses its own machine total. |
| H10 | `memory-held` | OS/process memory composition | KEEP; retain OS, process and swap readings. O2 restores process collection. |
| H11 | `context-headroom` | Prompt size versus slot limit | KEEP; repair O3 rather than invent a limit. |
| H12 | `article-cost` | Per-article resource use | KEEP; distinguish CPU seconds, model time and incremental memory. |
| H13 | `prompt-reuse` | Cache reuse versus prompt growth | KEEP; per-call held/fresh counts differ from token totals. |
| H14 | `read-against-written` | Input/output token volume per run | RETAIN AND REIMAGINE on Hardware; L6. Two per-run lines; Run total / Median per article radios, default totals; exact actual-run readout and measured/recorded article coverage. |
| H15 | `counterfactual-cost` | Token-price scenario | REMOVED permanently in Row 8e; M8 names the lost editable hypothetical totals. H14 retains the shared token query and paired-run calculations. |

Table I - Judgement; source: `config/console/judgement.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| I1 | `merged-stories` | Published merges | KEEP; outcomes, not eligible pairs. |
| I2 | `merge-line` | Calculated/proposed/applied boundaries | KEEP; preserve meanings and dates. |
| I3 | `judge-agreement` | Swapped-input consistency | KEEP; not human agreement. |
| I4 | `record-gates` | Why fitting is blocked | KEEP; preserve cumulative counts and day strip. |
| I5 | `verdict-split` | Judged pairs versus applied boundary | KEEP; eligibility is not publication. |
| I6 | `holdout-margin` | Human-marked negative-pair margin | KEEP; independent from judge self-agreement. |

Table J - Voices; source: `config/console/voices.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| J1 | `source-health` | Source permission, availability and yield | KEEP; preserve producer-owned decisions. |
| J2 | `feeds-failed` | Failed source responses | KEEP; separate feed and article-fetch denominators. |
| J3 | `fetch-time` | Source fetch latency | KEEP; distinct from failure rate. |
| J4 | `retiring` | Pending source retirement | KEEP; preserve rule, dwell and dates. |
| J5 | `source-cuts` | Source truncation | KEEP; distinct from context occupancy and output compression. |
| J6 | `ranking-discount` | Applied reliability penalty | KEEP; retain its recorded window, not the page window. |
| J7 | `why-chosen` | Newest-day selection scores | KEEP; preserve the actual candidate cohort. |
| J8 | `watchlist` | Distinct watchlist hits | REMOVED permanently in Row 8e; M9 names the lost distinct hits, dates and front-page counts. Selection-score bonuses remain distinct. |

Table K - Data explorer; source: `config/console/data-explorer.json`

| ID | Section | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| K1 | `data-explorer-ask` | Query editing/saving | KEEP; workbench input, not a chart. |
| K2 | `data-explorer-rows` | Exact query result | KEEP as the default answer. |
| K3 | `data-explorer-shape` | Result visualization | KEEP as optional; automatic selection is L4. |

### Construction decisions and remaining gates

Table L

| ID | Decision | Construction | State / boundary |
| --- | --- | --- | --- |
| L1 | Full visual replacement | Row 3 uses the complete console-only style family below: palette, type, rail, controls, status, panels and drawings. No reader recoloring. | Defaulted additive appearance family; native validation precedes CSS production. Missing blocks/leaves use role defaults, arrays replace whole, and only the chart dash accepts null. No dependency on L3 or L6. |
| L2 | Closed-day eligibility/cadence | Keep `compact_after_days = 1` for item-health, summary-quality-evals, host-fingerprint and run-shards; retain validator >=1, cadence and retention. | RESOLVED: the extra whole-day wait remains. Row 2 diagnoses publication only; no freshness gain is assumed. |
| L3 | Permanent cuts and page moves | Row 4 removes G4. Row 8a removes F11/F12/F15 and retains F13 as daily lines; Row 8b removes F14; Row 8c removes G11/M6. Row 8d retains/refines H6/M7, removes H2/H3/H4 and moves H7/N3 once to Pipelines. Row 8e removes M8/M9; Row 8f moves N1/N2. N4/N5 remain selected for separate follow-up. | N1/N2 retain their clocks, cohorts and original endpoint groups. N4/N5 and then H14's settled flag remain separate deliveries. No hidden charts, replacement disclosures or query-contract schema. |
| L4 | Automatic explorer chart choice | Count valid readings through existing role/shape validation and floors; a small named grouped result can rank instead of selecting an undrawable scatter. | Row 7 construction settled; preserve manual choices, typed-date refusals and reporting floors. Independent of L1/L3/L6. |
| L5 | SQL aggregation | Keep existing named column/date queries and reducers for these changes. No new aggregate API is required. | RESOLVED: placement, units, window labels and publication diagnosis do not require a query-contract migration. No transfer-saving claim. |
| L6 | Hardware run read/write comparison | Compact item-health, settled by UTC date/run/item, supplies two per-run lines. Run total sums paired finite nonnegative input/output; Median per article takes each side's actual median over that identical cohort. Default totals; input includes cached prompts and recorded model calls. | Run-aware geometry, numeric run order, distinct same-day positions and known unmeasured gaps; no daily roll-up, fake timestamps or refetch on metric switch. Actual-run pointer/tap/keyboard readout includes full ID, UTC date and measured/recorded articles. Row 8 defines the settled nullable flag, queued after the four selected moves. |

#### L1 - Console-only appearance settings for Row 3

```json
{
  "console_style": {
    "colors": {
      "light": {
        "canvas": "#f2f1ed", "inset": "#e9e7e1", "surface": "#fffefa", "raised": "#ffffff",
        "text": "#25251f", "text_secondary": "#625e55", "text_tertiary": "#746f64",
        "rule": "#dad6cb", "rule_strong": "#b6afa0", "accent": "#0b746e",
        "accent_hover": "#085d58", "on_accent": "#ffffff", "focus": "#0b746e",
        "selected": "#dcedea", "chart_axis": "#b6afa0", "chart_grid": "#dad6cb",
        "categorical": ["#356a9a", "#7d53a0", "#167f99", "#a3427c", "#5968af", "#29739e", "#995aab", "#777268"]
      },
      "dark": {
        "canvas": "#191917", "inset": "#151513", "surface": "#22221f", "raised": "#2b2b27",
        "text": "#f0ede5", "text_secondary": "#c1bcb1", "text_tertiary": "#a39c8f",
        "rule": "#393932", "rule_strong": "#565348", "accent": "#6bc7be",
        "accent_hover": "#94d9d0", "on_accent": "#122722", "focus": "#6bc7be",
        "selected": "#263d38", "chart_axis": "#565348", "chart_grid": "#393932",
        "categorical": ["#8bbce5", "#bea2df", "#72c6d9", "#e6a1c9", "#a4b1e8", "#83bfdc", "#cea4e0", "#b0aa9e"]
      }
    },
    "typography": {
      "ui_face": "inter", "heading_face": "inter", "data_face": "inter",
      "small": {"size_rem": 0.75, "leading_rem": 1, "weight": 400, "tracking_em": 0},
      "body": {"size_rem": 0.875, "leading_rem": 1.25, "weight": 400, "tracking_em": 0},
      "control": {"size_rem": 0.875, "leading_rem": 1.25, "weight": 500, "tracking_em": 0},
      "panel_title": {"size_rem": 1, "leading_rem": 1.5, "weight": 600, "tracking_em": -0.01},
      "page_title": {"size_rem": 1.5, "leading_rem": 2, "weight": 600, "tracking_em": -0.02},
      "value": {"size_rem": 1.75, "leading_rem": 2, "weight": 600, "tracking_em": -0.02}
    },
    "layout": {
      "rail_width_rem": 12, "header_min_height_rem": 3.5,
      "rail_padding_rem": 1, "rail_gap_rem": 0.5, "content_gap_rem": 1.5,
      "control_min_height_rem": 2.75, "control_padding_inline_rem": 0.75,
      "control_padding_block_rem": 0.25, "control_gap_rem": 0.5,
      "panel_padding_rem": 1, "panel_gap_rem": 1, "group_gap_rem": 1.5, "columns_wide": 2
    },
    "radii": {"control_rem": 0.25, "panel_rem": 0.5},
    "elevation": {
      "light": {"panel": {"y_px": 1, "blur_px": 2, "alpha": 0.06}, "floating": {"y_px": 6, "blur_px": 16, "alpha": 0.12}},
      "dark": {"panel": {"y_px": 0, "blur_px": 0, "alpha": 0}, "floating": {"y_px": 0, "blur_px": 0, "alpha": 0}}
    },
    "chart": {"axis_width_px": 1, "grid_width_px": 1, "line_width_px": 2, "grid_opacity": 1, "grid_dash_px": null, "linecap": "round"}
  }
}
```

### Permanent cut list

Table M

| ID | Displayed title / panel ID | Current -> destination | State and diagnostic cost |
| --- | --- | --- | --- |
| M1 | Where visual attempts stopped, by potential class / `pipeline-funnel` | Pipelines `/console/` -> removed | SETTLED permanent cut in Row 8a: loses stage-by-stage attempt attrition by potential class. Published visual coverage is not equivalent. |
| M2 | How drafted visual plans ended, by potential class / `downgrade-funnel` | Pipelines `/console/` -> removed | SETTLED permanent cut in Row 8a: loses draft-only outcomes and replacement-search depth. |
| M3 | Recorded refusal reasons over time / `visual-refusals` | Pipelines `/console/` -> retained daily lines | SETTLED retention in Row 8a: replaces the long per-day list, not first failed checks or any recorded reason. Includes attempts later written; unknown days are not zero. |
| M4 | Planned and successfully written visual types / `visual-written-types` | Pipelines `/console/` -> removed | SETTLED permanent cut in Row 8b: loses the visible planned-to-written type comparison and substitutions; written is not published, and the retained overview does not replace it. |
| M5 | Which rule refused a reply / `refusing-rule` | Summaries `/console/model/` -> removed | SETTLED permanent cut: same failed-rule query/ranking and model-stage readings remain on Pipelines. Loses the Summaries shortcut/default summarize selection, not a unique metric. |
| M6 | What the model change moved / `model-change` | Summaries `/console/model/` -> removed | SETTLED permanent cut in Row 8c: loses the combined observational before/after comparison across different article populations. Individual metric trends and setting-change markers remain but do not replace it. |
| M7 | Which machines ran our jobs, day by day / `platform-mix` | Hardware `/console/machine/` -> retained | SETTLED retention/refinement in Row 8d. Full-identity categorical gradients replace the speed-colour encoding; compact hover preserves exact counts, and dated details retain speeds and actual jobs. |
| M8 | What the runner's work would have cost elsewhere / `counterfactual-cost` | Hardware `/console/machine/` -> removed | SETTLED permanent cut in Row 8e: loses editable hypothetical price totals and per-article scenarios, not a real bill. H14 retains its shared token query and paired-run calculations. Persisted pricing settings remain. |
| M9 | What the watchlist caught / `watchlist` | Voices `/console/voices/` -> removed | SETTLED permanent cut in Row 8e: loses distinct watchlist hits, hit dates and front-page counts. Selection scores are different; their watchlist bonus, native fields, historical rows and persisted configuration remain. |
| M10 | What the extractor found / `extraction` | Pipelines `/console/` -> removed | SETTLED permanent cut in Row 8a: loses extraction classes, integrity/found-fact counts, recorded flags, published chartable share and yield. The visual overview is not equivalent. |
| M11 | How much of the processor went to somebody else / `processor-lost` | Hardware `/console/machine/` -> removed | SETTLED permanent cut in Row 8d: loses the processor-steal diagnostic. Historical machine mix is not equivalent. |
| M12 | Whether the machine took the model's memory back / `disk-reads` | Hardware `/console/machine/` -> removed | SETTLED permanent cut in Row 8d: loses the model paging/re-read view. Raw/compact readings and retained runtime collection remain. |
| M13 | Which machines this run was given / `machine-cards` | Hardware `/console/machine/` -> removed | SETTLED permanent cut in Row 8d: loses newest-run hardware-detail cards, including constraints, flags, clocks, copy/cache and location presentation. History does not replace them. |

### Actual page-move list

Table N

| ID | Displayed title / panel ID | Current -> destination | State and preserved reading |
| --- | --- | --- | --- |
| N1 | What one item cost the model / `item-cost` | Pipelines `/console/` -> Summaries `/console/model/` | Relocation in Row 8f: independent read/write clocks, time/token normalization, raw distributions and item-health-only endpoint. No substitution with tokens/s. |
| N2 | What one summary cost / `write-cost` | Summaries `/console/model/` -> Pipelines `/console/` | Relocation in Row 8f: positive-clock distribution, median/p95, untimed count and original common item-health/evaluation endpoint. |
| N3 | Which articles took longest in the last run / `slowest-articles` | Hardware `/console/machine/` -> Pipelines `/console/` | SETTLED relocation in Row 8d: mount once after the timeline; retain run-wide newest-run selection, item/source identities, recorded item_total_ms, stage/queue/missing/overlap semantics and original three-family endpoint. |
| N4 | Whether the slowest articles are getting slower / `tail-trend` | Hardware `/console/machine/` -> Pipelines `/console/` | SELECTED for separate follow-up: per-run percentiles and original endpoint, not daily medians. |
| N5 | Whether a run is getting slower on the same work / `slower-on-same-work` | Pipelines `/console/` -> Hardware `/console/machine/` | SELECTED for separate follow-up: fixed-work normalization, reference-machine cohort and original endpoint. |

### Enumerated defect triage

Table O

| ID | Original cause | Evidence and consequence | Disposition |
| --- | --- | --- | --- |
| O1 | Percentage units | Geometry uses 0-100; the component multiplies readout/ARIA shares by 100 again. | Row 5: fix retained distributions once. |
| O2 | Missing process identity | Work omits `--server-pid`; server RSS/major faults are absent while worker/OS readings exist. | Row 6 if H3/H10 remain. No backfill. |
| O3 | Flag alias mismatch | Long config flags versus short lookups lose slot limits, requested pinning and fingerprint changes. | Row 6 for retained consumers; fix shared interpretation. |
| O4 | Window mismatch | Pipelines reanchors private evidence on compact reach. Summaries correctly keeps two anchors but does not make their different dates clear. | Row 5: fix selection and label both windows without unifying them. |
| O5 | Publication lag | Deployment preceded packing. One failed Pages run has no jobs, checks or failed-job log; cause remains unknown. | Row 2: diagnosis only. Keep the extra-day wait; prescribe no workflow fix or freshness gain. |
| O6 | Explorer direct open | Server layout data is absent from static fallback output. | Row 7: remove runtime server-data dependency. |
| O7 | Undrawable default | Paired was selected for seven rows against a 160-reading floor; Ranked worked. | Row 7 applies L4 without lowering floors or removing manual types. |
| O8 | Text date example | Day-by-day SQL omits the date cast. | Row 7: fix the example, not the ledger schema. |
| O9 | Preference failure | Storage exceptions block loading or leave chart/control windows inconsistent. | Row 3 applies D13; no separate hardening project. |
| O10 | Conditional query rejection | Unexpected rejections can leave loading unresolved; ordinary boundary failures are already typed. | Row 5: fix demonstrated retained paths, not hypothetical failures. |
| O11 | Expected missing readings | Frequency collection is disabled; other readings are absent or await packing/publication. | Explain absence; invent no values and enable no unused collectors. |
| O12 | Mislabelled age clock | `article-age` measures source publication to item start, but the route heading claims age at publication. | Row 5: correct the heading; retain its cohort and exclusions. |

## 3. Row #2 - Diagnose compact-data publication lag

- **Scope:** Diagnose O5 from normal compaction, publication and deployment evidence. Keep eligibility, cadence, retention and writers unchanged.
- **Files touched:**
  - `TODO/20261109-console-redesign-plan.md`
- **Read-only inputs:** `.github/workflows/idhazh-gardener.yml`, `.github/workflows/pages.yml`, `backend/utilities/publish_decision.py`, `frontend/scripts/stage-publication.mjs`, the four L2 compaction configs and one selected normal run/deployment chain.
- **Acceptance gates:** Local: verify evidence against its source commits and UTC instants; confirm the four configs still use 1 and the validator still requires >=1. CI: docs-only checks. Record an evidence-backed cause or the precise missing evidence and bounded next observation. No production dispatch, workflow edit or eligibility change as a test.
- **Oracle:** Trace a selected compact endpoint through its committed input, normal publication run and deployment result. Separate an expected eligibility wait from packing and deployment. Missing jobs or logs establish an evidence gap, not a workflow defect. This diagnosis cannot promise a freshness gain or deployment SLA.

### Decisions

Table P

| ID | Decision | Authority |
| --- | --- | --- |
| P1 | Retain `compact_after_days = 1` and validator >=1 for all four L2 ledgers. No schema expansion or zero-setting work. | Current compaction contract. |
| P2 | Record each required ledger's endpoint; the oldest available endpoint still limits the route. Do not change data to make endpoints agree. | Window contract. |
| P3 | Preserve retention, packing ownership, raw writers, compact shapes and late-arrival handling. | Compaction contract. |
| P4 | Track eligibility, job cadence and deployment separately. A green compaction does not refresh staged panels. | Reader bindings; O5. |
| P5 | Retain cadence and retention. Any fix suggested by the diagnosis needs a named cause, exact files and a separate scope decision. | Existing serialized gardener workflow; diagnosis scope. |

### Rejected alternatives

Table Q

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Q1 | Change eligibility or cadence | Not part of publication diagnosis and does not establish a cause for the observed failure. | A separate config/schedule decision; the current extra-day wait otherwise remains. | L2; diagnosis scope. |
| Q2 | Another packer or raw index | Adds ownership, coverage and cleanup complexity. | Separate B1/B2 design. | B1/B2. |
| Q3 | Move ordinary panels to another origin | Changes source policy, not existing publication. | Source/permission design and protected-contract changes. | B4. |

### Current publication finding

The deployed source predates the latest packing: the live console is one
coverage day behind the newest eligible, committed compact day. This establishes
a deployment/source gap. It does not establish a workflow-code defect or a
rendering failure.

The single current reading is `2026-11-11T08:50:01Z` UTC, against canonical
commit `bc38fe090be48f60561fc64a2adef16faa3d1bd6`. Each source is the named
`state/compact/<ledger>/index/daily.json`, produced by the gardener:

- `item-health`: committed endpoint `2026-11-09`; live endpoint `2026-11-08`.
- `summary-quality-evals`: committed endpoint `2026-11-09`; live endpoint `2026-11-08`.
- `host-fingerprint`: committed endpoint `2026-11-09`; live endpoint `2026-11-08`.
- `run-shards`: committed endpoint `2026-11-09`; live endpoint `2026-11-08`.

All four live index requests returned HTTP 200. Their complete parsed contents
match the indexes at the last listed Pages source,
`84a90776e191c45642f1cc76db67b43ce2b8b76d`, not the newer canonical indexes.
The oldest required endpoint therefore remains `2026-11-08` on the live site;
changing a chart or its window cannot supply the missing compact day.

**Eligibility:** With the retained `compact_after_days = 1`, Nov 9 ends at
`2026-11-10T00:00:00Z` and becomes eligible at `2026-11-11T00:00:00Z`.
Nov 10 remains ineligible until `2026-11-12T00:00:00Z`. This is the expected
whole-day wait, separate from whether an eligible day has been packed or deployed.
The four L2 configs still use 1, and
`backend/idhazh/contracts/knobs/gardener.py:492-499` still requires >=1.

**Normal deployment:** Scheduled Pages run `42944055275` started at
`2026-11-11T02:09:37Z` with source `84a90776e191c45642f1cc76db67b43ce2b8b76d`.
Its `decide` job `130272467984` accepted CI evidence for that code; `build`
job `130272897083` checked out that exact source and completed staging.
Its `deploy` job `130273519490` succeeded at `2026-11-11T02:12:38Z`;
the run completed at `2026-11-11T02:12:40Z`. That committed input ended on
Nov 8 for every required ledger. The deployment could not include Nov 9's
later packing, and the live indexes reproduce its input rather than showing
an additional staging loss.

**Normal packing:** Scheduled gardener run `42976505486` used source
`28540ca58328188d4e74c591a94a53a5991b1e39`, started at
`2026-11-11T07:01:41Z` and completed successfully at `2026-11-11T07:05:58Z`.
Its task events selected Nov 9 as the newest eligible day, finished all four
live compactions and recorded successful shard landings:

- Quality job `130376780018` produced commit
  `034101e8dd7124243bcacc5d0446fcd4ec26b832` at `2026-11-11T07:02:59Z`.
- Item-health job `130376779837` produced commit
  `05a658df4a81231f30382c00849c30b6041c7643` at `2026-11-11T07:03:55Z`.
- Host/run-shards job `130376779846` produced commit
  `8a2362f660b7bb761a2faff8c3d45d2bf80e4366` at `2026-11-11T07:04:38Z`.

Those commits are in the canonical source and advance all required endpoints
to Nov 9. The declared gardener wake is 00:40 UTC daily; this run's observed
start was later. The metadata does not explain that difference.

**Publication boundary and uncertainty:** `pages.yml` schedules publication
every 30 minutes or accepts a dispatch; a gardener commit itself does not
deploy. `publish_decision.py` checks code evidence but selects the scheduled
commit, and `stage-publication.mjs` stages that committed compact input rather
than packing raw data. These named inputs, both workflows, the four configs
and the validator are unchanged between the selected run sources and the
canonical commit. The bounded default-branch run list contains no later Pages run, so
there is no post-packing decision or deployment to diagnose. That absence
does not establish a scheduler, permission, CI-gate or workflow-code cause.
Historical Pages run `42673624810` still has no established cause for its
failure before jobs started; this successful chain does not explain it.

**Bounded next observation:** Read only the newest normal Pages run after
the packing above: its source commit, `decide` reason, `build` and `deploy`
results, then the same four live indexes once. Compare its committed indexes
with the deployed result. If no such run or job evidence is available, retain
that precise gap rather than dispatching a test or prescribing a workflow fix.
Eligibility, cadence, retention, writers and compact contracts remain unchanged;
this finding promises neither a freshness gain nor a deployment deadline.

## 4. Row #3 - Replace the full console visual system and share window behavior

- **Scope:** Replace the entire console visual system and optional-preference handling without selecting chart removals, destinations or H14's representation.
- **Files touched:**
  - `backend/idhazh/contracts/appearance_config.py`
  - `config/appearance.json`
  - `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json`
  - `frontend/src/lib/server/config.ts`
  - `frontend/scripts/build-frame-css.mjs`
  - `frontend/src/styles/frame.generated.css`
  - `frontend/src/routes/console/+layout.svelte`
  - `frontend/src/lib/components/SiteHeader.svelte`
  - `frontend/src/lib/components/ThemeToggle.svelte`
  - `frontend/src/lib/components/ConsoleNav.svelte`
  - `frontend/src/lib/components/ConsoleBand.svelte`
  - `frontend/src/lib/components/Panel.svelte`
  - `frontend/src/lib/components/PanelGroup.svelte`
  - `frontend/src/lib/components/KpiCard.svelte`
  - `frontend/src/lib/components/StatusChip.svelte`
  - `frontend/src/lib/components/ChartReadout.svelte`
  - `frontend/src/lib/components/ChoiceTiles.svelte`
  - `frontend/src/lib/components/RouteStatus.svelte`
  - `frontend/src/lib/components/Reserved.svelte`
  - `frontend/src/lib/components/RankedList.svelte`
  - `frontend/src/lib/components/WindowControl.svelte`
  - `frontend/src/lib/components/WindowControlSource.svelte`
  - `frontend/src/lib/components/WindowStatus.svelte`
  - `frontend/src/lib/components/RunSquares.svelte`
  - `frontend/src/lib/components/RunYield.svelte`
  - `frontend/src/lib/components/RunLengths.svelte`
  - `frontend/src/lib/components/SourceCutRange.svelte`
  - `frontend/src/lib/components/StageTimings.svelte`
  - `frontend/src/lib/components/SwapDots.svelte`
  - `frontend/src/lib/components/ThroughputTrend.svelte`
  - `frontend/src/lib/components/TimeHistogram.svelte`
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/src/lib/charts/d3/axis.ts`
  - `frontend/src/lib/charts/d3/dateSeries.ts`
  - `frontend/src/lib/charts/d3/distribution.ts`
  - `frontend/src/lib/charts/d3/pairedScatter.ts`
  - `frontend/src/lib/charts/d3/partsOfOne.ts`
  - `frontend/src/lib/charts/d3/tileStrip.ts`
  - `frontend/src/lib/charts/d3/flow.ts`
  - `frontend/src/lib/charts/d3/rankedList.ts`
  - `frontend/src/lib/charts/d3/DateSeries.svelte`
  - `frontend/src/lib/charts/d3/Distribution.svelte`
  - `frontend/src/lib/charts/d3/EmptyState.svelte`
  - `frontend/src/lib/charts/d3/Flow.svelte`
  - `frontend/src/lib/charts/d3/PairedScatter.svelte`
  - `frontend/src/lib/charts/d3/PartsOfOne.svelte`
  - `frontend/src/lib/charts/d3/TileStrip.svelte`
  - `frontend/src/lib/console/machine/FleetDots.svelte`
  - `frontend/src/lib/console/machine/MachineCharts.svelte`
  - `frontend/src/lib/console/machine/TailTrendPanel.svelte`
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte`
  - `frontend/src/routes/console/judgement/VerdictSplit.svelte`
  - `frontend/src/routes/console/judgement/HoldoutMargin.svelte`
  - `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte`
  - `frontend/src/routes/console/judgement/MergeLinePlot.svelte`
  - `frontend/src/lib/console/explorer/AnswerTable.svelte`
  - `frontend/src/lib/console/explorer/ColumnList.svelte`
  - `frontend/src/lib/console/explorer/ColumnPicker.svelte`
  - `frontend/src/lib/console/explorer/ColumnType.svelte`
  - `frontend/src/lib/console/explorer/CopyAnswer.svelte`
  - `frontend/src/lib/console/explorer/HistoryList.svelte`
  - `frontend/src/lib/console/explorer/LedgerList.svelte`
  - `frontend/src/lib/console/explorer/QueryEditor.svelte`
  - `frontend/src/lib/console/explorer/QuestionStrip.svelte`
  - `frontend/src/lib/console/explorer/RunStatus.svelte`
  - `frontend/src/lib/console/explorer/ShapePanel.svelte`
  - `frontend/src/lib/console/window-slot.ts`
  - `frontend/src/lib/console/window-preference.ts` (new optional-storage boundary)
  - `frontend/src/lib/console/strip.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/voices/+page.svelte`
  - `frontend/src/routes/console/judgement/+page.svelte`
  - `frontend/src/routes/console/data-explorer/+page.svelte`
  - `frontend/src/styles/app.css`
  - `backend/tests/test_appearance_config.py`
  - `backend/tests/contracts/test_console_style_binding.py` (new field/default/vocabulary and producer binding)
  - `frontend/tests/appearance-config.spec.ts`
  - `frontend/tests/tokens.spec.ts`
  - `frontend/tests/console-nav.spec.ts`
  - `frontend/tests/console-band.spec.ts`
  - `frontend/tests/console-shell.spec.ts`
  - `frontend/tests/console-window.spec.ts`
  - `frontend/tests/console-frame.spec.ts`
  - `frontend/tests/console-date-axis.spec.ts`
  - `frontend/tests/console-readout-data.spec.ts`
  - `frontend/tests/console-machine-journey.spec.ts`
  - `frontend/tests/console-data-explorer-still.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `docs/concepts/config/appearance.md`
  - `docs/concepts/design-system.md`
  - `docs/concepts/console-design.md`
  - `docs/concepts/ui-shell.md`
  - `docs/concepts/console-design/the-rules-every-console-chart-obeys.md`
  - `docs/architecture/publishing/what-sits-above-every-console-route.md`
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Settle L1's appearance contract first; L3/L6 do not gate this row. Local: selector, lint/types, native/default/old-input and frontend binding cases, deterministic generated CSS, nondefault label-size geometry and throwing-storage cases. CI: merge-candidate gates. Browser: representative populated Hardware view, cross-route/reader smoke and absent/empty data; review the wide and narrow layout plus both changed palettes with Susan. No per-panel matrix.
- **Oracle:** A legal nondefault style value changes generated and computed console styling, with matching chart measurement and no reader-style change. The first viewport includes route identity, window, evidence date and a useful comparison/readout; this proves no chart's editorial value.

### Decisions

Table R

| ID | Decision | Authority |
| --- | --- | --- |
| R1 | Apply D8-D12 and the L1 style defaults as one full replacement, not a rail on the old skin. Keep reader frame maximums and configured gutters; the console defaults to the full window while existing numeric console caps retain their meaning. Keep theme preference, motion/display-face behavior and structural breakpoints. Use existing font and glyph assets; add no framework or engine. | Shared shell and appearance contracts. |
| R2 | Wide layout: labelled glyph rail with active-route group anchors and a larger matching title glyph. Keep metadata in page evidence, reuse the homepage wordmark without a Console label, and move theme control beside footer links. Title/window/reach share one measured sticky band; narrow screens use a native days select. The brand scrolls away naturally. Back-to-top stays outside readings, in the wide rail corner or narrow title band. Preserve source order and wide/verdict spans. | Shared shell contract; configured breakpoints. |
| R3 | Keep latest-day verdict, worst issue and site size as compact facts on a neutral surface. Put native reach/fetch state beside the window; keep private and newest-run dates beside their readings. Preserve run-verdict access, required recording/refused-run notes and all denominators. | Window/status contract. |
| R4 | Generate operator-only CSS over the whole page, including body canvas and outer chrome; never change reader palette/type tokens. Rebind dependent series aliases inside the operator scope. Preserve semantic confidence/movement/absence roles, neutral panels and non-hover readings. Every measured console chart adds the shared typed hover tooltip, without changing reader-chart behavior. Honor the existing elevation toggle. | Shared chart and native style contracts. |
| R5 | Apply D13/O9 independently of the appearance change. Keep control/query state synchronized even if preference storage throws. | Existing shared window behavior. |
| R6 | Preserve explorer editor/result regions and working controls; apply the same new skin and rail without a duplicate band. H14 keeps its existing representation during this row; L6 belongs to Row 4. | Workbench and row boundaries. |
| R7 | Reuse the existing CSS generator with a callable renderer for in-memory checks. Update only the appearance contract family, fixture and bindings. No new route-roster fields, generic presentation component, runtime theme fetch or unused projection. | Fowler construction ruling. |

### Rejected alternatives

Table S

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| S1 | Hover-only navigation labels | Ambiguous on touch or with unfamiliar icons. | Add visible labelled access. | Susan. |
| S2 | Text rail or recoloring on the old skin | Omits the requested type, controls, status and chart replacement. | Accept an incomplete visual result; not this scope. | Full replacement scope. |
| S3 | CSS-only chart font growth | Leaves old axis arithmetic and can collide labels. | Update measured geometry with the style, preserving reader defaults. | D12. |

## 5. Row #4 - Remove the duplicate refusal view and redraw run token volume

- **Scope:** Permanently remove G4/M5 and implement L6/H14 only. No other cut, page move, source change, collector or anomaly/baseline rule belongs to this delivery.
- **Files touched:**
  - `config/console/model.json`
  - `config/console/machine.json` (initial token metric in the existing numeric knobs)
  - `frontend/src/lib/console/route-console.ts` (validate and project that metric)
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/lib/console/queries/model.ts`
  - `frontend/src/lib/console/queries/machine.ts`
  - `frontend/src/lib/console/model/panels.ts`
  - `frontend/src/lib/console/model/Panels.svelte`
  - `frontend/src/lib/console/model/refusing-rule.ts` (delete; its only application consumer is removed)
  - `frontend/src/lib/console/model/slice.ts`
  - `frontend/src/lib/console/machine/MachineCharts.svelte`
  - `frontend/src/lib/console/machine/ReadWritePanel.svelte` (new native H14 consumer)
  - `frontend/src/lib/console/machine/run-axis.ts` (thin repeated dates by UTC identity, not formatted text)
  - `frontend/src/lib/charts/machine.ts`
  - `frontend/src/lib/charts/d3/runSeries.ts` (new typed run-sequence geometry)
  - `frontend/src/lib/charts/d3/RunSeries.svelte` (new shared drawing/readout consumer)
  - `frontend/src/lib/charts/readout.ts` (truthful runSeries type literal)
  - `backend/tests/contracts/test_panel_queries.py`
  - `tests/fixtures/console/machine/readAgainstWrittenQuery.json` (regenerate the existing native answer with article identity)
  - `frontend/tests/appearance-config.spec.ts`
  - `frontend/tests/console-model-ledgers.spec.ts`
  - `frontend/tests/console-panel-queries.spec.ts`
  - `frontend/tests/console-machine.spec.ts`
  - `frontend/tests/chart-vocabulary.spec.ts`
  - `frontend/tests/console-machine-journey.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `frontend/tests/support/console-expect/console-built-page/model.ts`
  - `frontend/tests/support/console-expect/console-chrome/machine.ts`
  - `docs/architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md`
  - `docs/architecture/publishing/console-machine.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
  - `docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: selector, lint/types, native query binding, permanent G4 absence with Pipelines model-stage access, same-day/numeric run ordering, totals versus actual medians, identical cohorts, missing/zero/partial readings and run-aware geometry/vocabulary binding. Extend the representative Hardware/Summaries-to-Pipelines journeys for metric switching without fetch and actual-run pointer/keyboard readout. CI owns the full merge candidate. Integrated browser: real dense-run chart in the merged visual system, both metrics, run selection, missing/empty data and cross-route smoke; Susan reviews the rendered chart.
- **Oracle:** G4 has no roster/judged entry, renderer or Summaries query; Pipelines still ranks model-stage refusals. H14 draws every recorded run at a distinct numeric-ordered position, takes both metrics from one paired cohort and reads exact actual-run values without another fetch. Other charts and endpoint groups retain their semantics.

### Decisions

Table T

| ID | Decision | Authority |
| --- | --- | --- |
| T1 | G4 is a permanent duplicate-view removal, not a hidden/disclosed chart. Remove its roster/judged entry and dead model query/rendering path; retain shared failed-rule metrics, Pipelines ranking and model-stage selection. | Shared query and FailureList inspection. |
| T2 | Keep moved IDs stable and change actual destination mounting, route queries and flat rosters. Plain old-fragment links may preserve moved addresses and the duplicate G4 shortcut; they mount no chart or query and need no alias framework. Other permanent cuts retire their own chart fragments. | Actual relocation scope; stable address compatibility. |
| T3 | Apply D14 for every move. Hardware latency cannot adopt the Pipelines endpoint, and the fixed-work comparison cannot adopt the Hardware endpoint. Show distinct evidence dates instead of manufacturing one date. | Native reach/query contracts. |
| T4 | Delete only truly unused UI readers/helpers. Keep `platformMixQuery` for retained cards/clocks/colors and the shared token query for H14. Cut no native ledger fields, producers, historical rows or persisted config keys as a chart side effect. | Direct surviving-consumer search. |
| T5 | Keep `DRAWN_BY` ownership truthful, including `score_ms -> score-cost`. Retire obsolete chart cases with their invariant preserved in the retained query/component or representative journey; update the named test inventory if a spec is deleted. | Instrument contract; test policy. |
| T6 | H14 stays on Hardware. One builder returns Run total and actual Median per article over the same paired finite nonnegative item cohort, plus recorded/measured counts. Read includes cached prompt tokens and totals all recorded model calls; neither metric is a rate, words or uncached compute. Preserve cost helpers' dated semantics. | L6; native item-health grain. |
| T7 | Use native runSeries geometry, not duplicate dates or fake IDs in dateSeries. Numeric run sequence has one position per known run; thin repeated UTC labels, never run points. Known unmeasured runs break paths; do not invent scheduled runs. | Shared run-axis and compareRuns contracts. |
| T8 | Read is solid and Written dashed on one token scale. Monotone-X interpolation passes through actual readings without invented extrema; it is not statistical smoothing. Mark only selected/isolated values. Existing ChartReadout snaps to actual runs and shows exact values, full ID, UTC date and measured/recorded coverage; rest and Escape use the last known run, even if unmeasured. | Shared chart vocabulary and readout; Susan drawing ruling. |
| T9 | Metric radios redraw the same in-memory answer. The existing numeric route knob `read_write_default_metric` selects the initial mode: 0 = Run total (shipped default), 1 = Median per article; reject other values at the config boundary. Runtime selection remains in memory. No anomaly flag is implemented in this delivery. | Settled baseline feature; the flag is queued after the selected moves in Row 8. |

### Rejected alternatives

Table U

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| U1 | Merge all timing metrics | Changes cohorts and meaning. | Prove unit/cohort parity or name the lost diagnostic. | Existing reducers. |
| U2 | Delete ledger fields with charts | Turns a presentation change into an archive migration. | Persisted-contract design and historical reader support. | B6. |
| U3 | Replace private attempt views with explorer queries | Explorer cannot read unpublished inputs. | Publication permission and source delivery. | D2/B4. |
| U4 | Call a link a page move, or a closed disclosure a permanent cut | Leaves the original chart mounted or merely hidden. | Perform the actual removal/relocation and verify its query ownership. | Required chart scope. |

## 6. Row #5 - Correct retained chart readings and evidence windows

- **Scope:** Fix retained unit/window errors and demonstrated unresolved loading.
- **Files touched:**
  - `frontend/src/lib/charts/d3/Distribution.svelte`
  - `frontend/src/lib/charts/d3/distribution.ts`
  - `frontend/src/lib/components/RouteStatus.svelte`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/model/+page.server.ts`
  - `frontend/src/lib/console/model/Cards.svelte`
  - `frontend/src/lib/console/model/cards.ts`
  - `frontend/src/lib/console/model/Query.svelte`
  - `frontend/src/lib/console/pipelines/Extraction.svelte`
  - `frontend/src/lib/console/pipelines/ArticleAge.svelte`
  - `frontend/src/lib/console/pipelines/article-age.ts`
  - `frontend/tests/console-readout-data.spec.ts`
  - `frontend/tests/console-pipelines-window-page.spec.ts`
  - `frontend/tests/console-pipelines-reserved.spec.ts`
  - `frontend/tests/console-model-nothings.spec.ts`
  - `frontend/tests/console-model-builder.spec.ts`
  - `frontend/tests/console-model-ledgers.spec.ts`
  - `frontend/tests/support/console-expect/console-built-page/model.ts`
  - `docs/architecture/publishing/console-charts.md`
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md`
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Inventory check:** The current native consumers remain ArticleAge, MachineCharts and explorer ShapePanel. Private card availability needs the existing typed read metadata carried through the Summaries load. Voices and the native query door retain their typed failure paths; no unexpected rejection has been demonstrated.
- **Acceptance gates:** Local: lint/types and focused readout/window/query specs. CI: merge-candidate gates. Browser: retained distribution readout and window/date behavior.
- **Oracle:** Geometry, readout and ARIA agree on 0-100 shares; panels select and label their actual evidence window. This cannot supply uncollected or unpacked data.

### Decisions

Table V

| ID | Decision | Authority |
| --- | --- | --- |
| V1 | Fix O1 in `Distribution.svelte` readout and mark ARIA without rescaling 0-100 shares. Reserve share-axis label room once for ArticleAge, MachineCharts and explorer ShapePanel. | Geometry/component and consumer inspection. |
| V2 | Native comparisons keep their declared endpoint groups; build-time evidence keeps its published-day anchor. Preserve moved-panel provenance and label differing scope. | Window contract; O4. |
| V3 | Missing is not zero. Do not backshift empty build-time windows or invent endpoints from the browser clock. | Window/missing-data contract. |
| V4 | Fix O10 only on a demonstrated retained path. Preserve explicit failures and usable siblings; do not swallow programmer errors. | Query failure contract. |
| V5 | For O12 use `Source age at work start`; retain feed-stated times, successful-item selection, inferred/future exclusions and the logarithmic-axis zero note. | `pipelines/article-age.ts`; O12. |

### Rejected alternatives

Table W

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| W1 | Use the newest endpoint everywhere | Implies absent evidence exists. | Redesign comparison/partial coverage. | Window contract. |
| W2 | Export dates, percentages or chart payloads again | Duplicates native answers. | Another contract and synchronization path. | A5/B3. |
| W3 | Catch all route errors | Can misreport defects as quiet results. | Preserve classification and diagnostics. | Error contract. |

## 7. Row #6 - Restore collection needed by retained hardware diagnostics

- **Scope:** Restore process identity and shared flag interpretation only for the diagnostics and provenance consumers retained by L3.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/idhazh/config.py`
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/llm/server_flags.py` (new shared recorded-help adapter)
  - `tests/fixtures/runtime/b10598-llama-server-help.txt` -> `backend/idhazh/llm/b10598-llama-server-help.txt` (move unchanged)
  - `backend/idhazh/fingerprint.py`
  - `backend/idhazh/stages/work.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_server_argv.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/contracts/test_model_registry.py`
  - `backend/tests/council/_imports.py` (name the shared adapter in the bounded import inventory)
  - `backend/tests/test_host_readings.py`
  - `backend/tests/test_item_records.py`
  - `backend/tests/pipeline/test_work_health_payload.py`
  - `frontend/src/lib/console/machine/DiskReadsPanel.svelte` (requested-locking caption only)
  - `frontend/src/lib/console/machine/disk-reads.ts` (requested-setting comments only)
  - `frontend/tests/console-readout-data.spec.ts` (same-run mixed-setting helper/render regression)
  - `frontend/tests/console-machine-journey.spec.ts`
  - `docs/architecture/sources/item-health.md`
  - `docs/architecture/publishing/console-machine.md`
  - `docs/concepts/config/model-file.md`
  - `docs/reference/ci-model-runtime.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Inventory check:** H3 `disk-reads`, H10 `memory-held`, H11 `context-headroom` and fingerprint/provenance consumers remain. Shared interpretation also reaches the required-context config preflight. The existing help recording moves unchanged into the installed package; no alias table or persisted shape is added. Disk-read captions currently claim applied locking and must instead name the recorded request. Empty shards and disabled host/memory collection must not require a controller identity; an active collector without one must report that absence.
- **Acceptance gates:** Name L3's retained consumers first; collapse unneeded collection work only against the explicit cut list. Local: shared selection, lint/types and focused flag/argv/host/recording/historical-read tests. Browser: requested-locking caption, cross-page and absent-data smoke. CI: merge-candidate gates. Inspect the next normal production record; no production dispatch or workflow-file tests.
- **Oracle:** Long/short flag aliases yield identical settings/fingerprints; work recording with a process identity captures process readings. This cannot recover history or prove requested locking was applied.

### Decisions

Table X

| ID | Decision | Authority |
| --- | --- | --- |
| X1 | If H3/H10 remain, pass the model process identity already produced by the workflow. Do not discover a process by name. | Final retained consumers; work recorder. |
| X2 | Fix O3 in shared flag interpretation used by settings and fingerprints; use the aliases in the existing recorded server-help contract. Preserve canonical recorded keys and verbatim runtime arguments. | `llm/server.py`, `fingerprint.py`, recorded runtime help. |
| X3 | Requested load mode does not prove applied locking. Historical missing parallel counts remain unknown. | Native field contracts. |
| X4 | Leave disabled frequency collection unchanged. | O11. |

### Rejected alternatives

Table Y

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Y1 | Backfill from current config | Invents historical settings. | Independent evidence and a reader migration. | B6. |
| Y2 | Enable unused collectors | Adds runtime cost without a diagnostic consumer. | Identify the beneficiary and operating cost. | Scope. |

## 8. Row #7 - Make retained explorer answers directly reachable and drawable

- **Scope:** Fix explorer direct navigation, retained examples and automatic chart selection.
- **Files touched:**
  - `frontend/src/routes/console/+layout.server.ts`
  - `frontend/src/routes/console/+layout.ts`
  - `frontend/src/lib/console/explorer/shape.ts`
  - `config/appearance.json`
  - `frontend/tests/console-data-explorer-shape.spec.ts`
  - `frontend/tests/console-data-explorer-examples.spec.ts`
  - `frontend/tests/console-data-explorer-still.spec.ts`
  - `docs/architecture/publishing/data-explorer-state.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: lint/types and address/shape/example specs. CI: existing journey plus the distinct direct-open/reload boundary. Browser: direct open, navigation, reload and missing/empty answers; no per-chart suite.
- **Oracle:** Direct open/reload matches in-app behavior; retained automatic examples draw or explicitly decline while retaining the table. This does not infer arbitrary SQL semantics.

### Decisions

Table Z

| ID | Decision | Authority |
| --- | --- | --- |
| Z1 | Read the existing `__UI_CONFIG__.number_format` in universal layout success and absence paths; delete its server-only number-format load. No Vite, global-type or payload change is needed. | Existing typed build-time define; static fallback contract. |
| Z2 | Preserve client fallback, manual charts, table answers and publication consent. No new prerendered data document. This row can proceed without L1/L3/L6; serialize shared-file edits through the existing N=1 execution rule. | Explorer delivery contract; independent failure boundary. |
| Z3 | Apply L4 through `resolveRoles`/`chartShape`: keep typed-date precedence and missing/duplicate/unplaceable-day refusals. For non-date answers use valid finite readings and distinct subjects against existing floors; a small one-label/two-number result may rank on its first number only if unique-name, nonnegative and nonzero checks pass. Otherwise retain the table and explicitly decline. Manual types/roles keep their existing behavior. | O7; existing shape functions and reporting floors. |
| Z4 | Cast the retained example date in SQL; keep the ledger schema unchanged. | O8. |

### Rejected alternatives

Table AA

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AA1 | Lower shared floors for the example | Changes unrelated reporting behavior. | Separate reporting-floor decision. | L4. |
| AA2 | Migrate the ledger date type | Archive migration for a query mistake. | Schema versioning and historical reader changes. | O8. |
| AA3 | Add explorer exports or a server endpoint | Duplicates data delivery. | New persisted/publication contract or hosting change. | A5/B3. |

## 9. Row #8 - Settle remaining permanent cuts, page moves and token anomaly rules

- **Scope:** M8/M9 are implemented in Row 8e. Row 8f delivers N1/N2; N4/N5 remain selected for separate delivery, preserving every source, cohort and endpoint requirement in Tables F-K and N. M1-M3 and M10 are settled in Row 8a; M4 in Row 8b; M6 in Row 8c; M7/M11-M13 and N3 in Row 8d. Deliver H14's settled nullable flag in its own increment after the selected moves.
- **Status:** Row 8f implements the two summary-timing moves. N4/N5 remain pending separate implementation. H14's design is complete and queued after them; neither those moves nor the flag is part of Row 8f.
- **Delivery inventory:** Row 8f implements N1/N2 below; narrow the remaining N4/N5/H14 inventory to its delivery before implementation:
  - `config/console/pipelines.json`, `config/console/model.json`, `config/console/machine.json`
  - `frontend/src/routes/console/+page.server.ts`, `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`, `frontend/src/routes/console/machine/+page.svelte`, `frontend/src/routes/console/machine/+page.server.ts`
  - `frontend/src/lib/console/queries/pipelines.ts`, `frontend/src/lib/console/queries/model.ts`, `frontend/src/lib/console/queries/machine.ts`
  - `frontend/src/lib/console/model/panels.ts`, `frontend/src/lib/console/model/Panels.svelte`, `frontend/src/lib/console/model/slice.ts`, `frontend/src/lib/console/eval-instruments.ts`
  - `frontend/src/lib/console/model/ItemCost.svelte`, `frontend/src/lib/console/model/item-cost.ts` (moved in Row 8f); `frontend/src/lib/console/pipelines/SlowerOnSameWork.svelte`
  - `frontend/src/lib/console/TimeCost.svelte` (shared writing/checking presentation extracted in Row 8f)
  - `frontend/src/lib/console/machine/MachineCharts.svelte`, `frontend/src/lib/console/machine/records.ts`, `frontend/src/lib/console/machine/TailTrendPanel.svelte`, `frontend/src/lib/console/machine/PlatformMixPanel.svelte`
  - `frontend/src/lib/server/ledger-rows.ts`, `frontend/src/lib/charts/machine.ts`
  - `backend/tests/contracts/test_panel_queries.py`
  - `frontend/tests/console-model-instruments.spec.ts`, `frontend/tests/console-model-panels.spec.ts`, `frontend/tests/console-model-reductions.spec.ts`, `frontend/tests/console-model-ledgers.spec.ts`, `frontend/tests/console-panel-queries.spec.ts`
  - `frontend/tests/console-item-cost.spec.ts`, `frontend/tests/console-pipelines-native.spec.ts`, `frontend/tests/console-pipelines-nothings.spec.ts`, `frontend/tests/console-pipelines-retained-item-cost.spec.ts`
  - `frontend/tests/console-canary-host-halves.spec.ts`, `frontend/tests/recorded-slices.spec.ts`, `frontend/tests/ledger-rows.spec.ts`, `frontend/tests/chart-vocabulary.spec.ts`, `frontend/tests/platform-mix.spec.ts`
  - `frontend/tests/console-visual-attempts.spec.ts`, `frontend/tests/console-machine-journey.spec.ts`, `frontend/tests/console-pipelines-lifecycle.spec.ts`
  - `frontend/scripts/test-groups.ts`, `frontend/tests/support/panel-tab.ts`, `frontend/tests/support/console-sources.ts`, `frontend/tests/support/console-window/server-panels.ts`
  - `frontend/tests/support/console-expect/console-built-page/model.ts`, `frontend/tests/support/console-expect/console-built-page/pipelines.ts`, `frontend/tests/support/console-expect/console-built-page/machine.ts`, `frontend/tests/support/console-expect/console-built-page/voices.ts`
  - `docs/architecture/publishing/console.md`, `docs/architecture/publishing/what-the-pipelines-route-draws.md`, `docs/architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md`, `docs/architecture/publishing/console-machine.md`, `docs/architecture/publishing/who-supplied-the-day-and-which-feeds-failed.md`
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md`, `docs/concepts/console-design/what-the-quality-and-source-panels-draw.md`, `docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Preserve D14/T2-T5 and the settled losses. Deliver the four selected moves separately from Row 8e, then use the H14 contract below in its own increment.
- **Oracle:** Selected removals are permanent, selected moves mount once at their actual destination, and retained native answers keep their original cohorts and endpoint groups. H14 remains unimplemented until its queued increment.

### H14 - Settled flag, queued after the four route moves

- **Delivery:** A simple nullable boolean flag computed by browser DuckDB.
  No H14 implementation belongs to Row 8e.
- **Measure:** Use the selected Run total or Median per article measure;
  evaluate read and write separately.
- **Cohort:** Match recorded model/token settings and reset at known settings
  changes. Use the last 30 earlier matching runs, with at least 10 required.
- **Rule:** Compare the current value only with that prior cohort's mean and
  sample standard deviation:
  `abs(value - prior_mean) > 3 * prior_sample_stddev`.
- **Exclusions:** No IQR or percentage guard, Python analytics or new tests.

## 10. Row #8a - Simplify selected Pipelines visual diagnostics

- **Scope:** Permanently remove `pipeline-funnel`, `downgrade-funnel` and
  `extraction`. Retain `visual-refusals` as complete daily lines and enrich
  `chart-drawing` with its existing categorical stage colours. The losses
  are M1, M2 and M10, not parity with the overview. Other cuts, moves and
  the queued H14 flag are tracked in Row 8.
- **Order:** Remove selected roster/judged entries and mounts; delete only
  unconsumed local presentation/query/load work and its retired tests.
  Keep the private attempt reader, per-day attempt counts, typed read metadata
  and written-type comparison. Implement daily refusal lines from those same
  inputs, then carry optional typed stage tokens through shared flow geometry.
  Update dependent ownership declarations without changing persisted shapes.
- **Files:** `config/console/pipelines.json`; both Pipelines route files;
  `console/queries/pipelines.ts`; the selected Pipelines components and
  adapters, including focused `VisualRefusals.svelte` / `visual-refusals.ts`;
  shared `charts/d3/flow.ts` / `Flow.svelte`; private `server/ledger-rows.ts`;
  evaluator/item read-ownership declarations; their named dependent tests and
  test inventories; the Pipelines, visual-overview and window owning docs.
- **Refusal contract:** One named line per recorded reason, with the same
  selected UTC calendar and count scale. Preserve every observed first failed
  check, even on a later-written plan. Complete observed zeros remain zeros;
  missing, lost, out-of-coverage and unreadable-period absences remain gaps.
  Preserve surviving partial counts and exact attempt readouts, notes and
  singleton dots. No smoothing, rate substitution, top-N cut or new alarm.
- **Colour contract:** Reuse the overview's existing stage-token mapping.
  Stage nodes use their own token; outgoing carried ribbons and loss
  ribbons/terminals use their source stage. Keep current opacities and normal
  text. The narrow ordered list adds decorative `--space-2` squares and keeps
  all counts/shares/indentation. Tokenless callers remain monochrome and
  unmarked. No reader recolouring, asset, palette or tuning-field change.
- **Acceptance:** Use the shared selector for the smallest relevant real
  behavior tests; lint and type checks before push. Integrated browser smoke
  covers Pipelines, one cross-route journey, console/HTTP failures and
  absent/empty data. Preserve real representative screenshots; native fixture
  and canary evidence are not production evidence. Review the rendered lines
  and overview once with Susan at wide/narrow widths and in both changed
  themes; correct meaningful findings.
- **Delivery:** One nested-session PR. Preserve a self-contained recovery
  report in session artifacts from first push, including exact head, selected
  files/semantics, actual check outcomes, smoke, design findings and remaining
  decisions. Follow required exact-head CI to its final result; parent review
  and merge remain separate. Keep worktree/artifacts and stop helpers.

## 11. Row #8b - Remove the Pipelines written-type diagnostic

- **Scope:** Permanently remove F14/M4 from the roster, judged list, title,
  mount and page anchors, without a hidden or relocated replacement. The
  capability loss is the visible planned-to-written type comparison and
  substitutions, not a publication reading; the retained overview is not
  equivalent.
- **Surviving consumers:** `VisualRefusals.svelte` and `visual-refusals.ts`
  still consume `visualAttemptDays` and `attemptNotes`. Preserve daily attempt
  counts, all first refusal reasons, UTC calendars, exact readouts, shared
  hover, typed coverage/loss/set-aside metadata and missing/empty/partial states.
  Remove only the written component, type-pair fields/reducers and the private
  reader's unconsumed state/type columns. The producer, `VisualAttemptRow`,
  compact contracts and stored records stay unchanged.
- **Files:** `config/console/pipelines.json`; both Pipelines route files;
  `console/pipelines/VisualAttempts.svelte` (delete) and `visual-attempts.ts`;
  `server/ledger-rows.ts`; the existing visual-attempt, lifecycle and nothing
  specs; their named build-time, source and window inventories; the native
  read-binding test; the Pipelines owning page and frontend routing link.
- **Acceptance:** Shared selector, smallest relevant local specs and applicable
  lint/types. Integrated Browser smoke covers Pipelines, one cross-route
  journey, console/HTTP failures and representative absent/empty data. One
  retained visual surface supplies Susan's rendered sufficiency review;
  fixture/canary evidence is labelled separately from production.
- **Delivery:** One focused PR, exact-head CI followed to its final outcome,
  with parent review and merge separate. Preserve the recovery report,
  worktree and browser evidence; stop helpers when no longer needed. Row 8
  tracks the remaining work.

## 12. Row #8c - Remove the Summaries model-change comparison

- **Scope:** Permanently remove G11/M6 from the roster, judged list, title,
  mount and anchors, with no hidden or relocated replacement. The lost
  capability is the combined observational before/after comparison across
  different article populations. Individual metric trends and dated
  setting/model-change markers remain but are not an equivalent replacement.
- **Surviving consumers:** Keep all underlying metrics, private measure cards,
  their coverage/absence behavior and the remaining Summaries panels. Preserve
  `modelByDate`, `pipelineChanges`, historical pipeline-fingerprint identities,
  shared paired-chart geometry and shared console hover. Only the comparison's
  queries, adapter, paired-dot renderer, local aggregation and retired tests
  have no surviving consumer. No producer, native/compact contract or
  historical record is removed.
- **Files:** `config/console/model.json`; the Summaries server type exports;
  `console/model/Panels.svelte`, `panels.ts`, `slice.ts`, `work.ts` and
  `model-change.ts` (delete); `console/queries/model.ts`;
  `components/SwapDots.svelte` (delete); the dependent instrument/read-ownership
  declarations, named test/source inventories and retired query snapshots;
  the Summaries and quality-presentation owning docs and their direct references.
- **Acceptance:** Shared selector, smallest relevant local specs and applicable
  lint/types. Reuse route-absence coverage and retain real metric/marker and
  historical-identity coverage. Integrated Browser smoke covers Summaries,
  one cross-route journey, console/HTTP failures and representative absent/empty
  inputs. One retained visual surface supplies Susan's rendered sufficiency
  review; label canary/fixture evidence separately from production.
- **Delivery:** One focused PR and exact-head CI followed to its final outcome;
  parent review and merge remain separate. Keep the recovery report, worktree
  and browser evidence; stop helpers when no longer needed. Row 8 tracks the
  remaining work.

## 13. Row #8d - Refine machine history and move the run-wide article ranking

- **Level:** 3 - shared presentation and cross-route query grouping.
- **Scope:** Keep `platform-mix` on Hardware with categorical identity gradients,
  compact framing and actual compact hover. Permanently remove H2/H3/H4, with
  no replacement disclosures or relocation. Move only N3 once to Pipelines,
  immediately after the retained timeline. No other cut, move or anomaly rule.
- **Consumer inventory:** `platformMixQuery` and host normalization still feed
  history, run counts and clock comparison; `runShardsQuery` retains recorded
  planned counts. Article-cost keeps its separate host join. Newest-run inference
  uses the retained full newest-day clock population, not removed card queries.
  Producer contracts, collection, raw/compact rows and host/run identities remain.
- **History contract:** Canonical full identities from the bounded widest host
  universe assign D3 built-in PiYG slots and same-name qualifiers. Palette reuse
  never merges machines. Top-kind selection and folded totals remain; each UTC
  day's segments rank its own counts largest at the bottom, including distinct
  folded identities. The existing gradient flag selects
  uniform opaque shading or the same flat category fill; the existing tint share
  is independent of speed. Missing speed keeps identity; missing identity stays
  neutral. UTC dates, exact counts, small-cohort switch and real day-job details
  remain. Hover projects only the selected machine/day count and daily total;
  keyboard/touch details retain all dated counts, known zeros and measured speeds.
- **Relocation contract:** The timeline's selected-shard article list and the
  summary-cost distribution are not equivalent to a run-wide identity ranking.
  Preserve newest-run selection and limiting, recorded item_total_ms, item/source
  identity, missing clocks, stage gaps, overlap and queue context. The original
  item-health + host-fingerprint + run-shards endpoint group is separate from
  ordinary Pipelines item-health reach. Print distinct evidence dates. Retain
  `config/console/machine.json` -> `knobs.slowest_articles_rows` and prior inputs.
- **Files:** Selected Hardware/Pipelines roster, route, query, presentation and
  adapter files; optional in-memory date-series gradient/hover projections;
  existing appearance selector's additive D3 vocabulary, aligned console colour roles
  and version metadata; named dependent
  source/query fixtures and tests; Hardware/Pipelines, machine-drawing, appearance
  and shared-hover owning docs. No new persisted field, hand-authored palette, engine, export,
  raw read, current-day packing, origin, model or workflow.
- **Console alignment:** PiYG also supplies the existing console category and
  readable text/line tokens, with matching action/focus/selection roles. Preserve
  neutral surfaces, reader colours, typography/layout, confidence/movement and
  the reserved eighth absence token. D3 and build-time colour utilities produce
  the stock-family shades; no hand-authored palette or runtime correction system.
- **Acceptance:** Shared selector, smallest real behavior/contract tests and
  applicable lint/types. Verify actual removed mounts and retained consumers,
  identity/count stability and folded conservation, compact-hover/detail parity,
  zero/unknown cases, destination-only mount, lagging-family endpoint independence
  and missing newest clocks. Integrated Browser covers actual Hardware/Pipelines,
  cross-page, console/HTTP and absent/empty inputs. Preserve before/after provenance;
  inspect desktop stacks and narrow opposite-theme small cohort, then obtain one
  rendered Susan judgment.
- **Delivery:** One nested-session PR, self-contained recovery artifacts from first
  push, exact-head CI followed to its final result. Parent review/merge is separate.
  Preserve worktree/evidence and stop owned helpers. Row 8 tracks the remaining
  work.

## 14. Row #8e - Remove the hypothetical runner-price and watchlist-catch panels

- **Level:** 2 - remove mounted consumers and check their named dependants;
  no persisted shape or data meaning changes.
- **Scope:** Permanently remove only M8/M9 from the route rosters, judged
  inventories, mounts, controls and anchors. No disclosure, relocation or
  substitute panel. The diagnostic losses remain the distinct ones in Table M.
- **Order:** Delete selected roster entries and mounted consumers, then remove
  their unconsumed local query, reduction, price-control and style code.
  Update the native read-ownership metadata and directly dependent inventories.
  Retain producer fields, historical records and persisted configuration.
- **Retained consumers:** Hardware keeps `readAgainstWrittenQuery`,
  `readAgainstWritten`, paired-run calculations and `ReadWritePanel`, including
  both token metrics, cached prompts, numeric run order and partial coverage.
  Voices keeps `whyChosenQuery`, `whyChosen` and the watchlist selection bonus.
  The private item-column list, watchlist registry and observability prices
  remain compatible. Shared price helpers have no other application consumer.
- **Files:** `config/console/machine.json`, `config/console/voices.json`;
  Hardware route load/page, `machine/MachineCharts.svelte`, `machine/records.ts`,
  `charts/machine.ts`, `charts/cost.ts` (delete), `components/RateControl.svelte`
  (delete); Voices page, `queries/voices.ts`, `voices/WatchlistPanel.svelte` and
  `voices/watchlist.ts` (delete); obsolete local series aliases; item-health
  read-ownership metadata; named roster, query, source, compile and browser
  expectation inventories and focused specs; owning Hardware/Voices docs and
  directly dependent pricing references.
- **Acceptance:** Reuse existing roster, query-binding and retained-token
  coverage with only necessary expectation updates; add no tests or helpers.
  Use applicable lint/types. Review useful retained grouping on Hardware/Voices,
  a cross-route journey, real missing/empty states and console/HTTP behavior. If integrated
  Browser tools are unavailable, preserve the certified exact build and preview
  fingerprints for the parent rather than claiming visual verification.
- **Boundary:** N1/N2/N4/N5 remain selected for separate delivery. H14's settled
  nullable flag stays queued after them and is not implemented here.
  Preserve shared chrome, UTC date disclosure, count/date axes, independent
  endpoints, machine identities/colours, missing-versus-zero states, reader
  styling, semantic roles, hover/keyboard/touch and compaction settings.
- **Delivery:** One focused PR, exact head reported for review and CI followed
  to its final result. Parent review and merge remain separate. Keep a
  self-contained recovery artifact from the first push, preserve the worktree
  and evidence, and stop owned helpers at handoff.

## 15. Row #8f - Move the two existing summary-timing panels

- **Level:** 2 - move mounted consumers and check their named dependants;
  no persisted fields, producers or measurement changes.
- **Scope:** N1 moves item-cost from Pipelines to Summaries, immediately after
  throughput. N2 moves write-cost from Summaries to Pipelines, immediately after
  stage timings. Each mounts once; neither is hidden, replaced or duplicated.
- **Original bounds:** N1 uses item-health's through and first day. N2 uses the
  oldest available through of item-health and summary-quality-evals, clamping
  its first day to item-health's own first day. Both use inclusive selected
  presets, not private published-day windows.
- **Order:** Move the exact declarations and ItemCost component/reducer; extract
  the existing writing/checking presentation into shared TimeCost; wire the
  independent destination reaches; update rosters, reader metadata and directly
  dependent source/compile/query expectations; check the retained readings.
- **Retained consumers:** model/cost.ts still serves score-cost and write-cost.
  Model Query/slice, score-cost and all other native panels remain. Pipelines'
  ordinary item-health endpoint and three-family slowest ranking stay unchanged.
  Native bounds print beside each moved panel; stale requests cannot replace
  the current preset, and retry does not move a successful endpoint.
- **Files:** config/console/pipelines.json and model.json; both route pages;
  queries/pipelines.ts and model.ts; pipelines/query-groups.ts; model/ItemCost.svelte
  and item-cost.ts (moved from pipelines), model/Panels.svelte, panels.ts,
  Query.svelte and slice.ts; console/TimeCost.svelte (extracted);
  components/TimeHistogram.svelte (route wording only);
  contracts/item_health.py (reader ownership only); the existing panel-query
  contract inventory, recorded-slice fixture-route bindings, appearance roster,
  item-cost imports, Summaries journey
  roster/selector, Pipelines waiting roster, retained fixture import and bounded
  source/window/state expectations; owning route/window/chart docs and this plan.
- **Acceptance:** Add no tests, cases, helpers, fixtures or coverage assertions.
  Update only bindings changed by the moves. Use existing selected checks,
  lint/types and manual SQL/browser inspection; no local full suite. CI must
  finish on the exact candidate. Inspect both affected routes, one cross-route
  interaction and representative missing/empty handling. If integrated Browser
  tools are absent, preserve a certified final-commit canary for parent review.
- **Boundary:** N4/N5 and H14 stay queued. Preserve all shared chrome, UTC
  dates, count axes, route handoff, machine identity/colour, hover/keyboard/touch,
  missing-value meanings and compaction/cadence/retention settings.
- **Delivery:** One focused PR; report its exact review head and final CI
  conclusion. Keep the recovery artifact from the first push, including endpoint
  and cohort inventories, check results, build/input fingerprints and image
  provenance. Stop owned helpers and preserve the worktree. Parent reviews and
  merges; this row does not merge or dispatch production work.
