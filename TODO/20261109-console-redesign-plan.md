# Compact-ledger console recovery and redesign

**Last Updated**: 2026-11-09
**Level**: 5 - resolve design gates before implementation.

## 0. Operating contract

Table A

| ID | Field | Value |
| --- | --- | --- |
| A1 | Goal | Reduce clutter, fix retained charts and improve compact-data freshness. |
| A2 | In scope | - Review each panel.<br>- Triage fixes against retained capabilities.<br>- Redesign console navigation and chart presentation.<br>- Retain compact Parquet, DuckDB-Wasm and D3.<br>- Evaluate earlier closed-day compaction and fix publication lag. |
| A3 | Out of scope | Table B. |
| A4 | Governing pages | [Console delivery](../docs/architecture/publishing/console.md), [chart data](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md), [window rules](../docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md), [compaction](../docs/architecture/publishing/ledger-compaction.md), [design system](../docs/concepts/design-system.md). |
| A5 | Architecture | Compact Parquet -> shared DuckDB-Wasm reader -> typed result -> presentation adapter -> D3. No chart exports. Fowler supports retaining this path. |
| A6 | ESCALATE | 1. Unsettled persisted shape, publication permission or protected-contract change.<br>2. Loss of a distinct metric, denominator or diagnostic.<br>3. Current-day or uncommitted data required.<br>4. New source, engine, component framework or arbitrary SQL network access.<br>5. Unresolved Table L decision or file inventory.<br>6. Publication fix without an established root cause. |
| A7 | Execution | One nested session per PR; parallel N = 1 because shell, roster, window and config edits overlap. Row 1 settles the design. |

Execute per docs/how-to/execute-a-plan.md: one nested session per PR; parallel N = 1; merge after required CI passes; stop at unresolved design gates.

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
| C1 | 1 | Settle panel purposes and the console design contract | - | A | PENDING | - | - | - |
| C2 | 2 | Reduce closed-day data delay without another writer | 1 | B | PENDING | - | - | - |
| C3 | 3 | Replace oversized console chrome and share window behavior | 1 | C | PENDING | - | - | - |
| C4 | 4 | Consolidate repeated chart entry points | 1, 3 | D | PENDING | - | - | - |
| C5 | 5 | Correct retained chart readings and evidence windows | 4 | E | PENDING | - | - | - |
| C6 | 6 | Restore collection needed by retained hardware diagnostics | 4 | F | PENDING | - | - | - |
| C7 | 7 | Make retained explorer answers directly reachable and drawable | 3 | G | PENDING | - | - | - |

## 2. Row #1 - Settle panel purposes and the console design contract

- **Scope:** Settle panel dispositions, visual scope and config contracts before implementation.
- **Files touched:**
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: verify Tables F-K against route configs, resolve Table L and complete downstream file/config inventories. CI: docs-only checks.
- **Oracle:** Each configured panel appears once; each merge preserves grain, denominator and window. This does not settle visual preference or justify losing a diagnostic.

### Decisions

Table D

| ID | Decision | Authority |
| --- | --- | --- |
| D1 | Native panels already query Parquet with SQL; many aggregates remain in TypeScript. Retain A5. | `data/engine.ts`, `slice-query.ts`, `console/queries/window.ts`; Fowler. |
| D2 | Build-time exceptions remain: Pipelines manifests/item facts/day metrics; Summaries cards/item decisions; Voices source decisions; Judgement judging/holdout evidence. | Console delivery contract. |
| D3 | Default ownership: Pipelines - delivery/stage latency; Summaries - quality/model rates; Hardware - constraints/resources; Voices - sources; Judgement - merges. | Jony; Tables F-K are proposals. |
| D4 | Proposed shell: slim left rail, compact route header/window control, neutral surfaces and one control accent. Keep chart/status color semantics distinct and navigation labels accessible without hover. | Susan; scope is L1. |
| D5 | Put secondary diagnostics behind named disclosure or detail links; retain their data. No nested disclosure chains. | Jony. |
| D6 | Table M is selective triage, not a mandatory nine-fix bundle. | Plan scope. |
| D7 | The inspected Hardware viewport contains chrome and repeated status before chart evidence. Put a useful comparison in the first viewport; do not shrink chart text. | Browser/source inspection; Susan. |

### Rejected alternatives

Table E

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Replace the engine or add a component framework for the sidebar | Does not fix duplication, freshness or bad readings. | Port Svelte controls, price added assets and identify a missing capability. | Fowler, Susan. |
| E2 | Fix every panel before pruning | Repairs presentations that may leave the default view. | Implement and verify the full old inventory. | Jony. |
| E3 | Delete visually similar charts | Similar charts can use different clocks or cohorts. | Prove metric parity or name the diagnostic loss. | Jony. |

### Proposed panel-by-panel dispositions

Table F - Pipelines; source: `config/console/pipelines.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| F1 | `at-a-glance` | Published output | KEEP; totals, not attempt rates. |
| F2 | `run-health` | Plan versus delivery by day/run | KEEP; exposes individual failures. |
| F3 | `site-cost-per-item` | Storage growth per published article | KEEP; bytes, not latency or money. |
| F4 | `failure-mix` | Failures by stage/rule | KEEP as the canonical failure view. |
| F5 | `item-time-split` | Stage contribution to elapsed time | DISCLOSE under `stage-timings`; preserve complete-cohort means and signed overlap. |
| F6 | `slower-on-same-work` | Fixed-work latency trend | DISCLOSE under `stage-timings`; preserve normalization/reference cohort. |
| F7 | `stage-timings` | Daily stage medians | KEEP; each stage has its own timed cohort. |
| F8 | `item-cost` | Model read/write latency | DETAIL from Summaries `model-throughput`; preserve seconds/token and independent clocks. |
| F9 | `run-timeline` | Newest-run work, waits and overlap | KEEP; run scheduling, not window averages. |
| F10 | `chart-drawing` | Visual delivery versus cost | KEEP as visual-production entry point; retain published-item denominators. |
| F11 | `pipeline-funnel` | Where visual attempts stop | DISCLOSE under `chart-drawing`; attempts are not publications. |
| F12 | `downgrade-funnel` | Replacement-search outcomes | DISCLOSE beside F11; retain draft denominators and search depth. |
| F13 | `visual-refusals` | First plan-check refusals | DISCLOSE beside F11; a later attempt can succeed. |
| F14 | `visual-written-types` | Requested versus written types | DISCLOSE beside F11; written is not published/accepted. |
| F15 | `extraction` | Extraction integrity and chartable yield | KEEP; distinct from final visual coverage. |
| F16 | `article-age` | Source age at work start | REVIEW; current title incorrectly claims publication age. |

Table G - Summaries; source: `config/console/model.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| G1 | `model-cards` | Summary outcome status | KEEP; preserve instruments and evidence dates. |
| G2 | `model-throughput` | Read/write rates | KEEP; distinct from elapsed-time distributions. |
| G3 | `call-ending` | Normal endings versus truncation | KEEP; calls are not failed items. |
| G4 | `refusing-rule` | Model reply refusals | MERGE into Pipelines `failure-mix`; preserve stage access and old anchor. |
| G5 | `doubt-reasons` | Published summary band reasons | KEEP; distinct from request failures. |
| G6 | `faithfulness` | Score median/spread versus bands | KEEP; counts alone miss distribution changes. |
| G7 | `source-doubts` | Quality by source | KEEP; distinct from feed/fetch reliability. |
| G8 | `write-cost` | Summarizing latency distribution | DETAIL from Pipelines `stage-timings`; preserve positive-clock distribution and tail. |
| G9 | `score-cost` | Checker latency | DISCLOSE under `faithfulness`; not model-writing time. |
| G10 | `summary-length` | Output length versus requested bands | KEEP; distinct from context and source cuts. |
| G11 | `model-change` | Before/after model change | DISCLOSE under `model-cards`; unmatched cohorts do not establish causality. |

Table H - Hardware; source: `config/console/machine.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| H1 | `two-clocks` | Rate-instrument agreement | KEEP first; independent clocks versus tolerance. |
| H2 | `processor-lost` | CPU contention | KEEP; distinct slowdown cause. |
| H3 | `disk-reads` | Paging/re-read activity | REVIEW before M2; removal loses paging diagnosis. |
| H4 | `machine-cards` | Newest-run machine constraints | DISCLOSE under `two-clocks`; preserve identity, quota, topology and location. |
| H5 | `slower-machines` | Relative machine performance | KEEP; distinct from a daily fixed-work trend. |
| H6 | `platform-mix` | Observed job placement | DISCLOSE under `slower-machines`; history, not prediction. |
| H7 | `slowest-articles` | Newest-run latency outliers | DETAIL from Pipelines `run-timeline`; preserve stage and queue evidence. |
| H8 | `tail-trend` | Summarizing latency tails | DETAIL from Pipelines `stage-timings`; preserve per-run percentiles versus daily medians. |
| H9 | `closest-to-memory` | Article memory headroom | KEEP; each article uses its own machine total. |
| H10 | `memory-held` | OS/process memory composition | REVIEW as disclosure under `closest-to-memory`; process readings require M2. |
| H11 | `context-headroom` | Prompt size versus slot limit | KEEP; repair M3 rather than invent a limit. |
| H12 | `article-cost` | Per-article resource use | KEEP; distinguish CPU seconds, model time and incremental memory. |
| H13 | `prompt-reuse` | Cache reuse versus prompt growth | KEEP; per-call held/fresh counts differ from token totals. |
| H14 | `read-against-written` | Input/output token mix | REMOVE-CANDIDATE; available as a saved query. Retain the query for H15. |
| H15 | `counterfactual-cost` | Token-price scenario | DISCLOSE under `article-cost`; retain editable prices and hypothetical label. |

Table I - Judgement; source: `config/console/judgement.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| I1 | `merged-stories` | Published merges | KEEP; outcomes, not eligible pairs. |
| I2 | `merge-line` | Calculated/proposed/applied boundaries | KEEP; preserve meanings and dates. |
| I3 | `judge-agreement` | Swapped-input consistency | KEEP; not human agreement. |
| I4 | `record-gates` | Why fitting is blocked | DISCLOSE under `merge-line`; preserve cumulative counts and day strip. |
| I5 | `verdict-split` | Judged pairs versus applied boundary | DISCLOSE under `merge-line`; eligibility is not publication. |
| I6 | `holdout-margin` | Human-marked negative-pair margin | KEEP; independent from judge self-agreement. |

Table J - Voices; source: `config/console/voices.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| J1 | `source-health` | Source permission, availability and yield | KEEP; preserve producer-owned decisions. |
| J2 | `feeds-failed` | Failed source responses | KEEP; separate feed and article-fetch denominators. |
| J3 | `fetch-time` | Source fetch latency | DISCLOSE under `feeds-failed`; distinct from failure rate. |
| J4 | `retiring` | Pending source retirement | DISCLOSE under `source-health`; preserve rule, dwell and dates. |
| J5 | `source-cuts` | Source truncation | KEEP; distinct from context occupancy and output compression. |
| J6 | `ranking-discount` | Applied reliability penalty | KEEP; retain its recorded window, not the page window. |
| J7 | `why-chosen` | Newest-day selection scores | KEEP; preserve the actual candidate cohort. |
| J8 | `watchlist` | Distinct watchlist hits | DISCLOSE under `why-chosen`; hits do not prove selection lift. |

Table K - Data explorer; source: `config/console/data-explorer.json`

| ID | Section | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| K1 | `data-explorer-ask` | Query editing/saving | KEEP; workbench input, not a chart. |
| K2 | `data-explorer-rows` | Exact query result | KEEP as the default answer. |
| K3 | `data-explorer-shape` | Result visualization | KEEP as optional; automatic selection is L4. |

### Decisions still required before implementation

Table L

| ID | Decision | Recommendation | What the next worker must not assume |
| --- | --- | --- | --- |
| L1 | Console versus site-wide redesign | Start with D4; preserve the reading layout. | Settle tokens, rail dimensions, icon mappings and config defaults before edits. No framework migration or implicit site-wide recoloring. |
| L2 | Closed-day eligibility/cadence | Remove the extra whole-day wait for retained public ledgers; retain serialized compaction and observe publication. | The validator currently rejects `compact_after_days = 0`. Faster cron alone changes no eligibility. No current-day or latency SLA. |
| L3 | Panel dispositions | Review G4, timing overlaps, visual-attempt detail, then optional Hardware diagnostics. | No bulk deletion. Preserve distinct cohorts and diagnostics. |
| L4 | Automatic explorer chart choice | Keep rows authoritative; automatic choice must fit valid readings. | Do not lower shared floors or remove manual chart types to rescue an example. |
| L5 | SQL aggregation | Add named aggregates only for retained consumers that benefit; reuse the reader. | No generic dashboard framework. Aggregation alone does not reduce whole-file transfers. |

### Enumerated defect triage

Table M

| ID | Original cause | Evidence and consequence | Disposition |
| --- | --- | --- | --- |
| M1 | 1 - percentage units | Geometry uses 0-100; the component multiplies readout/ARIA shares by 100 again. | Row 5: fix retained distributions once. |
| M2 | 2 - missing process identity | Work omits `--server-pid`; server RSS/major faults are absent while worker/OS readings exist. | Row 6 if consumed; no backfill. |
| M3 | 3 - flag alias mismatch | Long config flags versus short lookups lose context, pinning and fingerprint changes. | Row 6 if retained diagnostics consume them; fix shared interpretation. |
| M4 | 4 - window mismatch | Pipelines misanchors build-time evidence; Summaries mixes published-day and compact endpoints. | Row 5: preserve and label each evidence window. |
| M5 | 5 - publication lag | Deployment preceded packing. Run `42673624810` failed before jobs; cause unknown. | Row 2: diagnose before prescribing a workflow fix. |
| M6 | 6 - explorer direct open | Server layout data is absent from static fallback output. | Row 7: remove runtime server-data dependency. |
| M7 | 7 - undrawable default | Paired was selected for seven rows against a 160-reading floor; Ranked worked. | Resolve L4, then Row 7; manual chart types remain. |
| M8 | 8 - text date example | Day-by-day SQL omits the date cast. | Row 7: fix retained example, not the ledger schema. |
| M9 | 9 - preference failure | Storage exceptions block loading or leave chart/control windows inconsistent. | Row 3: share optional-preference handling; no separate hardening project. |
| M10 | Conditional query rejection | Unexpected rejections can leave loading unresolved; ordinary boundary failures are already typed. | Row 5: fix demonstrated retained paths, not hypothetical failures. |
| M11 | Expected missing readings | Frequency collection is disabled; other readings are absent or await packing/publication. | Explain absence; do not invent values or enable unused collectors. |

## 3. Row #2 - Reduce closed-day data delay without another writer

- **Scope:** Apply L2 through existing compaction and publication.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/gardener.py`
  - `backend/idhazh/gardener/schedule.py`
  - `config/gardener/compact-item-health.json`
  - `config/gardener/compact-summary-quality-evals.json`
  - `config/gardener/compact-host-fingerprint.json`
  - `config/gardener/compact-run-shards.json`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/gardener/test_schedule.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/concepts/config/idhazh-gardener.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: shared selector, applicable lint/types and focused config/schedule/retry tests. CI: merge-candidate gates. Observe normal compaction/publication; no production dispatch as a test. Diagnose M5 before expanding publication code changes.
- **Oracle:** Fixed UTC inputs select the newest eligible closed day, exclude today and preserve retries with fewer rows. This cannot guarantee scheduler latency or deployment inclusion.

### Decisions

Table N

| ID | Decision | Authority |
| --- | --- | --- |
| N1 | If L2 selects zero, expand the validator before config uses it. Keep positive values readable; reject negatives. | `CompactionPolicy`, `gardener/schedule.py`; Fowler. |
| N2 | Update required ledgers coherently; the oldest required endpoint still limits the route. | Window contract. |
| N3 | Preserve retention, packing ownership, raw writers, compact shapes and late-arrival handling. | Compaction contract. |
| N4 | Track eligibility, job cadence and deployment separately. A green compaction does not refresh staged panels. | Reader bindings; M5. |
| N5 | Keep cadence initially; do not run all retention/history tasks more frequently to fix eligibility. | Existing serialized gardener workflow. |

### Rejected alternatives

Table O

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O1 | Cron-only change | Cannot change eligibility. | More executions with the same extra-day wait. | Eligibility predicate. |
| O2 | Another packer or raw index | Adds ownership, coverage and cleanup complexity. | Separate B1/B2 design. | B1/B2. |
| O3 | Move ordinary panels to another origin | Changes source policy, not existing publication. | Source/permission design and protected-contract changes. | B4. |

## 4. Row #3 - Replace oversized console chrome and share window behavior

- **Scope:** Replace console chrome and decouple window queries from preference storage.
- **Files touched:**
  - `config/appearance.json`
  - `backend/idhazh/contracts/appearance_config.py`
  - `backend/idhazh/contracts/knobs/console.py`
  - `frontend/src/lib/server/config.ts`
  - `frontend/src/routes/+layout.svelte`
  - `frontend/src/routes/console/+layout.svelte`
  - `frontend/src/lib/components/ConsoleNav.svelte`
  - `frontend/src/lib/components/ConsoleBand.svelte`
  - `frontend/src/lib/components/WindowControl.svelte`
  - `frontend/src/lib/components/WindowStatus.svelte`
  - `frontend/src/lib/console/window-slot.ts`
  - `frontend/src/lib/console/window-preference.ts` (new shared preference boundary, if extraction is needed)
  - `frontend/src/lib/console/strip.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/voices/+page.svelte`
  - `frontend/src/routes/console/judgement/+page.svelte`
  - `frontend/src/styles/app.css`
  - `frontend/src/styles/tokens.css`
  - `frontend/tests/console-nav.spec.ts`
  - `frontend/tests/console-shell.spec.ts`
  - `frontend/tests/console-window.spec.ts`
  - `frontend/tests/tokens.spec.ts`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/what-sits-above-every-console-route.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: applicable lint/types and in-memory preference tests. CI: existing console journey/layout coverage. Browser: populated route, cross-route navigation and missing/empty data; review narrow navigation and both themes with Susan. No panel matrix.
- **Oracle:** The first viewport shows a usable comparison, window and evidence date; storage errors do not block navigation or queries. This does not establish panel value.

### Decisions

Table P

| ID | Decision | Authority |
| --- | --- | --- |
| P1 | Resolve L1 before D4. Preserve URLs, theme preference, semantic navigation and keyboard access. | Susan. |
| P2 | Compact status without conflating publication, chart reach and newest-run scope. | Susan; window contract. |
| P3 | Share M9 handling: storage failure logs a warning but cannot block queries or desynchronize windows. | Reproduction; existing guarded routes. |
| P4 | Reuse Svelte components, native disclosure, tokens and icons. | Design system. |
| P5 | Retain explorer controls and workspace; omit redundant console status blocks. | Workbench contract. |

### Rejected alternatives

Table Q

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Q1 | Hover-only navigation labels | Ambiguous on touch or with unfamiliar icons. | Add visible labelled access. | Susan. |
| Q2 | Recolor existing chrome only | Leaves the hierarchy problem. | Accept less first-viewport evidence. | Susan. |
| Q3 | Shrink chart text to fit | Reduces legibility. | Justify the loss; prune default panels first. | Design system. |

## 5. Row #4 - Consolidate repeated chart entry points

- **Scope:** Apply settled F-K dispositions; preserve diagnostics and anchors.
- **Files touched:**
  - `config/console/pipelines.json`
  - `config/console/model.json`
  - `config/console/machine.json`
  - `config/console/judgement.json`
  - `config/console/voices.json`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/judgement/+page.svelte`
  - `frontend/src/routes/console/voices/+page.svelte`
  - `frontend/src/lib/console/model/panels.ts`
  - `frontend/src/lib/console/model/Panels.svelte`
  - `frontend/src/lib/console/machine/MachineCharts.svelte`
  - `frontend/src/lib/console/eval-instruments.ts`
  - `frontend/tests/console-model-instruments.spec.ts`
  - `frontend/tests/console-model-panels.spec.ts`
  - `frontend/tests/console-model-ledgers.spec.ts`
  - `frontend/tests/console-panel-queries.spec.ts`
  - `frontend/tests/console-pipelines-native.spec.ts`
  - `frontend/tests/console-machine-journey.spec.ts`
  - `docs/architecture/publishing/console.md`
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md`
  - `docs/architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md`
  - `docs/architecture/publishing/console-machine.md`
  - `docs/architecture/publishing/who-supplied-the-day-and-which-feeds-failed.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: focused reducer/query coverage and consumer search for selected cuts; add affected test-support paths before dispatch. CI: instrument bindings and merge-candidate gates. Browser: existing entry-to-detail journey. Do not edit historical mentions mechanically.
- **Oracle:** Each question has one default home; distinct readings and old anchors remain reachable. This does not prove cohort equivalence.

### Decisions

Table R

| ID | Decision | Authority |
| --- | --- | --- |
| R1 | G4 shares `failedRuleQuery` and the failure-list component with Pipelines. Preserve model-stage access when merging the entry point. | Query/consumer inspection; Jony. |
| R2 | Keep means, medians, distributions, per-run tails and normalized comparisons distinct. Consolidate navigation, not metrics. | Jony; existing reducers. |
| R3 | Preserve D2's publication boundary; relocation does not permit new exposure or cohort substitution. | Console delivery contract. |
| R4 | Preserve `DRAWN_BY` bindings for disclosed instruments; retain native fields and producers. | Instrument contracts. |
| R5 | Settle composition metadata, config compatibility and consumer changes in Row 1 before adding components or config shapes. | L3; contracts before logic. |

### Rejected alternatives

Table S

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| S1 | Merge all timing metrics | Changes cohorts and meaning. | Prove unit/cohort parity or name the lost diagnostic. | Jony. |
| S2 | Delete ledger fields with charts | Turns a presentation change into an archive migration. | Persisted-contract design and historical reader support. | B6. |
| S3 | Replace private panels with explorer queries | Explorer cannot read unpublished inputs. | Publication permission and source delivery. | D2/B4. |

## 6. Row #5 - Correct retained chart readings and evidence windows

- **Scope:** Fix retained unit/window errors and demonstrated unresolved loading.
- **Files touched:**
  - `frontend/src/lib/charts/d3/Distribution.svelte`
  - `frontend/src/lib/charts/d3/distribution.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/lib/console/model/Query.svelte`
  - `frontend/src/routes/console/voices/+page.svelte`
  - `frontend/src/lib/console/queries/window.ts`
  - `frontend/src/lib/console/machine/MachineCharts.svelte`
  - `frontend/tests/console-readout-data.spec.ts`
  - `frontend/tests/console-pipelines-window.spec.ts`
  - `frontend/tests/console-model-nothings.spec.ts`
  - `frontend/tests/console-panel-queries.spec.ts`
  - `docs/architecture/publishing/console-charts.md`
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: lint/types and focused readout/window/query specs. CI: merge-candidate gates. Browser: retained distribution readout and window/date behavior.
- **Oracle:** Geometry, readout and ARIA agree on 0-100 shares; panels select and label their actual evidence window. This cannot supply uncollected or unpacked data.

### Decisions

Table T

| ID | Decision | Authority |
| --- | --- | --- |
| T1 | Fix M1 in shared formatting, not correct geometry. | Geometry/component inspection. |
| T2 | Native comparisons keep their common endpoint; build-time evidence keeps its published-day anchor. Label differing scope. | Window contract; M4. |
| T3 | Missing is not zero. Do not backshift empty build-time windows or invent endpoints from the browser clock. | Window/missing-data contract. |
| T4 | Fix M10 only on a demonstrated retained path. Preserve explicit failures and usable siblings; do not swallow programmer errors. | Query failure contract. |

### Rejected alternatives

Table U

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| U1 | Use the newest endpoint everywhere | Implies absent evidence exists. | Redesign comparison/partial coverage. | Window contract. |
| U2 | Export dates, percentages or chart payloads again | Duplicates native answers. | Another contract and synchronization path. | A5/B3. |
| U3 | Catch all route errors | Can misreport defects as quiet results. | Preserve classification and diagnostics. | Error contract. |

## 7. Row #6 - Restore collection needed by retained hardware diagnostics

- **Scope:** Restore producer inputs consumed by retained H3/H10/H11 diagnostics.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/fingerprint.py`
  - `backend/idhazh/stages/work.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_host_readings.py`
  - `backend/tests/test_item_records.py`
  - `backend/tests/pipeline/test_work_health_payload.py`
  - `docs/architecture/sources/item-health.md`
  - `docs/architecture/publishing/console-machine.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: lint/types and focused flag/recording tests. CI: merge-candidate gates. Inspect the next normal production record; no production dispatch or workflow-file tests.
- **Oracle:** Long/short flag aliases yield identical settings/fingerprints; work recording with a process identity captures process readings. This cannot recover history or prove requested locking was applied.

### Decisions

Table V

| ID | Decision | Authority |
| --- | --- | --- |
| V1 | M2 depends on H3/H10 retention. If dropped, name the diagnostic loss and collapse collection work only. | Panel review. |
| V2 | Fix M3 in shared config interpretation; runtime flags and provenance must agree. | Config/recorder inspection. |
| V3 | Requested load mode does not prove applied locking. Historical missing parallel counts remain unknown. | Native field contracts. |
| V4 | Leave disabled frequency collection unchanged. | M11. |

### Rejected alternatives

Table W

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| W1 | Backfill from current config | Invents historical settings. | Independent evidence and a reader migration. | B6. |
| W2 | Enable unused collectors | Adds runtime cost without a diagnostic consumer. | Identify the beneficiary and operating cost. | Scope. |

## 8. Row #7 - Make retained explorer answers directly reachable and drawable

- **Scope:** Fix explorer direct navigation, retained examples and automatic chart selection.
- **Files touched:**
  - `frontend/src/routes/console/+layout.server.ts`
  - `frontend/src/routes/console/+layout.ts`
  - `frontend/src/routes/console/data-explorer/+page.ts`
  - `frontend/src/lib/console/explorer/shape.ts`
  - `frontend/src/lib/console/explorer/ShapePanel.svelte`
  - `frontend/vite.config.ts`
  - `frontend/src/app.d.ts`
  - `config/appearance.json`
  - `frontend/tests/console-data-explorer-address.spec.ts`
  - `frontend/tests/console-data-explorer-shape.spec.ts`
  - `frontend/tests/console-data-explorer-examples.spec.ts`
  - `frontend/tests/console-machine-journey.spec.ts`
  - `docs/architecture/publishing/data-explorer-state.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: lint/types and address/shape/example specs. CI: existing journey plus the distinct direct-open/reload boundary. Browser: direct open, navigation, reload and missing/empty answers; no per-chart suite.
- **Oracle:** Direct open/reload matches in-app behavior; retained automatic examples draw or explicitly decline while retaining the table. This does not infer arbitrary SQL semantics.

### Decisions

Table X

| ID | Decision | Authority |
| --- | --- | --- |
| X1 | Supply validated number-format config to the universal/browser path through the existing build-time define mechanism; remove the server-data dependency. | `vite.config.ts`; static fallback contract. |
| X2 | Preserve client fallback, manual charts, table answers and publication consent. No new prerendered data document. | Explorer delivery contract. |
| X3 | Apply L4 using valid-reading counts and configured floors. A small grouped result may rank instead of scatter. | M7; `openingType`. |
| X4 | Cast the retained example date in SQL; keep the ledger schema unchanged. | M8. |

### Rejected alternatives

Table Y

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Y1 | Lower shared floors for the example | Changes unrelated reporting behavior. | Separate reporting-floor decision. | L4. |
| Y2 | Migrate the ledger date type | Archive migration for a query mistake. | Schema versioning and historical reader changes. | M8. |
| Y3 | Add explorer exports or a server endpoint | Duplicates data delivery. | New persisted/publication contract or hosting change. | A5/B3. |
