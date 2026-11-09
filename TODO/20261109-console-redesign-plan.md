# Compact-ledger console recovery and redesign

**Last Updated**: 2026-11-09
**Level**: 5 - resolve design gates before implementation.
**Status**: Row 1 is in flight. L2 and L3 remain open; implementation rows stay pending.

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
| C1 | 1 | Settle panel purposes and the console design contract | - | A | IN-FLIGHT | `../reimagined-bassoon` | - | App session `5a68b1fe-c1ab-4f8d-b706-ef758cc38288`; branch `console-design-contract` |
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
- **Acceptance gates:** Local: verify Tables F-K against the six named route configs, resolve every Table L gate and verify the downstream inventories. CI: docs-only checks. Do not mark this row DONE while L2 or L3 is open.
- **Oracle:** Each configured panel appears once; consolidation preserves grain, denominator, clock, evidence dates and old anchors. A roster match does not establish metric equivalence.

### Decisions

Table D

| ID | Decision | Authority |
| --- | --- | --- |
| D1 | Native panels already query Parquet with SQL; many aggregates remain in TypeScript. Retain A5. | `data/engine.ts`, `slice-query.ts`, `console/queries/window.ts`; Fowler. |
| D2 | Build-time exceptions remain: Pipelines manifests/item facts/day metrics; Summaries cards/item decisions; Voices source decisions; Judgement judging/holdout evidence. | Console delivery contract. |
| D3 | Default ownership: Pipelines - delivery/stage latency; Summaries - quality/model rates; Hardware - constraints/resources; Voices - sources; Judgement - merges. F-K retain every diagnostic; L3 gates the composition mechanism. | Jony; roster reconciliation. |
| D4 | Console-only shell: intrinsic-width labelled left rail, compact route header/window control, existing neutral surfaces and control accent. Preserve reader styling and chart/status color semantics. | Susan; L1 construction below. |
| D5 | Put secondary diagnostics behind named disclosure or detail links. Keep native panels, queries and evidence on their original routes. No nested disclosure chains or metric substitution. | Jony; publication contract. |
| D6 | Table M is selective triage, not a mandatory nine-fix bundle. | Plan scope. |
| D7 | The inspected Hardware viewport contains chrome and repeated status before chart evidence. Put a useful comparison in the first viewport; do not shrink chart text. | Browser/source inspection; Susan. |

### Rejected alternatives

Table E

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Replace the engine or add a component framework for the sidebar | Does not fix duplication, freshness or bad readings. | Port Svelte controls, price added assets and identify a missing capability. | Fowler, Susan. |
| E2 | Fix every panel before pruning | Repairs presentations that may leave the default view. | Implement and verify the full old inventory. | Jony. |
| E3 | Delete visually similar charts | Similar charts can use different clocks or cohorts. | Prove metric parity or name the diagnostic loss. | Jony. |

### Panel-by-panel dispositions

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
| F8 | `item-cost` | Model read/write latency | DETAIL linked from Summaries `model-throughput`; native panel stays on Pipelines. Preserve seconds/token and independent clocks. |
| F9 | `run-timeline` | Newest-run work, waits and overlap | KEEP; run scheduling, not window averages. |
| F10 | `chart-drawing` | Visual delivery versus cost | KEEP as visual-production entry point; retain published-item denominators. |
| F11 | `pipeline-funnel` | Where visual attempts stop | DISCLOSE under `chart-drawing`; attempts are not publications. |
| F12 | `downgrade-funnel` | Replacement-search outcomes | DISCLOSE beside F11; retain draft denominators and search depth. |
| F13 | `visual-refusals` | First plan-check refusals | DISCLOSE beside F11; a later attempt can succeed. |
| F14 | `visual-written-types` | Requested versus written types | DISCLOSE beside F11; written is not published/accepted. |
| F15 | `extraction` | Extraction integrity and chartable yield | KEEP; distinct from final visual coverage. |
| F16 | `article-age` | Source age at work start | KEEP; Row 5 corrects the publication-age title, not the recorded clock. |

Table G - Summaries; source: `config/console/model.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| G1 | `model-cards` | Summary outcome status | KEEP; preserve instruments and evidence dates. |
| G2 | `model-throughput` | Read/write rates | KEEP; distinct from elapsed-time distributions. |
| G3 | `call-ending` | Normal endings versus truncation | KEEP; calls are not failed items. |
| G4 | `refusing-rule` | Model reply refusals | ALIAS to Pipelines `failure-mix`; preserve the old Summaries anchor and all existing stage/rule readings. No second query or new stage filter. |
| G5 | `doubt-reasons` | Published summary band reasons | KEEP; distinct from request failures. |
| G6 | `faithfulness` | Score median/spread versus bands | KEEP; counts alone miss distribution changes. |
| G7 | `source-doubts` | Quality by source | KEEP; distinct from feed/fetch reliability. |
| G8 | `write-cost` | Summarizing latency distribution | DETAIL linked from Pipelines `stage-timings`; native panel stays on Summaries. Preserve positive-clock distribution and tail. |
| G9 | `score-cost` | Checker latency | DISCLOSE under `faithfulness`; not model-writing time. |
| G10 | `summary-length` | Output length versus requested bands | KEEP; distinct from context and source cuts. |
| G11 | `model-change` | Before/after model change | DISCLOSE under `model-cards`; unmatched cohorts do not establish causality. |

Table H - Hardware; source: `config/console/machine.json`

| ID | Panel | Operator question | Proposed disposition and cost |
| --- | --- | --- | --- |
| H1 | `two-clocks` | Rate-instrument agreement | KEEP first; independent clocks versus tolerance. |
| H2 | `processor-lost` | CPU contention | KEEP; distinct slowdown cause. |
| H3 | `disk-reads` | Paging/re-read activity | KEEP; M2 restores the missing process readings. Absence is not zero. |
| H4 | `machine-cards` | Newest-run machine constraints | DISCLOSE under `two-clocks`; preserve identity, quota, topology and location. |
| H5 | `slower-machines` | Relative machine performance | KEEP; distinct from a daily fixed-work trend. |
| H6 | `platform-mix` | Observed job placement | DISCLOSE under `slower-machines`; history, not prediction. |
| H7 | `slowest-articles` | Newest-run latency outliers | DETAIL linked from Pipelines `run-timeline`; native panel stays on Hardware. Preserve stage and queue evidence. |
| H8 | `tail-trend` | Summarizing latency tails | DETAIL linked from Pipelines `stage-timings`; native panel stays on Hardware. Preserve per-run percentiles versus daily medians. |
| H9 | `closest-to-memory` | Article memory headroom | KEEP; each article uses its own machine total. |
| H10 | `memory-held` | OS/process memory composition | DISCLOSE under `closest-to-memory`; retain OS, process and swap readings. M2 restores process collection. |
| H11 | `context-headroom` | Prompt size versus slot limit | KEEP; repair M3 rather than invent a limit. |
| H12 | `article-cost` | Per-article resource use | KEEP; distinguish CPU seconds, model time and incremental memory. |
| H13 | `prompt-reuse` | Cache reuse versus prompt growth | KEEP; per-call held/fresh counts differ from token totals. |
| H14 | `read-against-written` | Input/output token mix | KEEP at its current placement; token totals are not prompt-cache reuse or throughput. Retain its query for H15. |
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

The six named configs contain exactly the F-K rosters: Pipelines 16, Summaries
11, Hardware 15, Judgement 6, Voices 8 and Data explorer 3. All 59 panel IDs
appear once. The current judged set contains 58 IDs because
`data-explorer-ask` is an input, not a judged answer. L3 would remove only the
alias `refusing-rule` from `judged`; it removes no recorded measurement.

### Construction decisions and remaining gates

Table L

| ID | Decision | Construction | State / boundary |
| --- | --- | --- | --- |
| L1 | Console versus site-wide redesign | Console-only labelled rail and compact status; use intrinsic sizing and existing tokens, breakpoints and defaults. | RESOLVED construction; no new appearance fields, icons, theme palette or reader-layout change. |
| L2 | Closed-day eligibility/cadence | Propose zero for item-health, summary-quality-evals, host-fingerprint and run-shards, retaining cadence and retention. | OPEN config-contract gate: `CompactionPolicy` currently requires >=1. Execution permission does not change it. |
| L3 | Panel composition | Retain F-K through the stamped, legacy-readable metadata proposal below. | OPEN config-contract gate. The current flat parser cannot express these relationships; no convention-based substitute. |
| L4 | Automatic explorer chart choice | Count valid readings against existing floors; allow a small named grouped result to rank instead of selecting an undrawable scatter. | RESOLVED construction below. Preserve manual choices, table answers, date refusals and reporting floors. |
| L5 | SQL aggregation | Keep existing named column/date queries and reducers for these changes. No new aggregate API is required. | RESOLVED: placement, units, window labels and eligibility do not require a query-contract migration. No transfer-saving claim. |

#### L1 - Shell and window construction

- At `frame.breakpoints_px[1]` and above, use a text-labelled rail sized by
  its contents and existing spacing tokens. Below it, use one native navigation
  disclosure with the active route named while closed. Labels never depend on
  hover. No new route icons or icon mappings.
- Reuse existing surface, rule, accent, focus, type and spacing tokens. Scope
  compact header and panel styling to the operator surface; leave global token
  values, reading routes, URLs, theme preference and header controls unchanged.
  Keep the existing frame maximums and chart text sizes.
- Keep publication completion, native-record reach and newest-run scope
  separate. The compact band retains its three facts and run-verdict access.
  Workbench chrome retains its own controls and usable result area, without a
  duplicate console band.
- Add `window-preference.ts` as a small optional-storage boundary. The mounted
  console layout owns the in-memory choice; routes receive that choice through
  `window-slot.ts` and `WindowControlSource.svelte`. Read storage on mount only.
  Keep the existing key and integer-preset encoding; validate against configured
  presets. A failed read uses the configured choice, a failed write retains the
  chosen span across route changes, and both warn. Storage never gates queries.

#### L2 - Closed-day proposal

The scheduler already supports zero. At `2026-11-09T12:00:00Z`, the current
one-day wait admits at most `2026-11-07`; zero admits `2026-11-08`, not the open
UTC day. The proposed change removes 24 hours of eligibility delay, not job or
deployment delay. Keep positive historical values readable and reject negatives.
Stamp the changed native schema and state its read compatibility in Row 2.

Only the four named ordinary-panel ledgers change. Voices' browser queries use
item-health; its feed census and source decisions remain private build-time
inputs. Data explorer can query feed-health, but this proposal does not change
that ledger's cadence, source or permission.

Publication diagnosis remains Row 2 work. The inspected failed Pages run
produced no jobs or check runs and no failed-job log; that evidence does not
identify a repository defect. Read the next normal run and deployment result,
without dispatching production as a test. No publication-code fix is selected.
If diagnosis requires one, name its cause and exact files before expanding the
row; do not infer a workflow fix from the absence of logs.

#### L3 - Panel-presentation proposal

Keep the flat roster as the identity/order source. The TypeScript parser remains
the sole route-config authority. Propose this optional metadata, keyed by an
existing panel ID:

```ts
type PanelPresentation =
  | { kind: 'disclosure'; parent: string; label: string }
  | { kind: 'detail'; from: string; label: string }
  | { kind: 'alias'; target: string; label: string };
```

- Legacy files keep exactly `panel_groups`, `judged` and `knobs` and normalize
  to empty presentation metadata. Changed files add a supported date-only
  `version`, newest-first `changelog` and `presentation`; unstamped new keys,
  unknown versions and unknown fields fail. An empty map preserves flat
  rendering. Follow section 10 for changelog bounds and compatibility.
- Keys must belong to their route roster. References resolve against the six
  globally unique rosters. A disclosure names a primary parent in the same
  group; detail and alias targets are primary native panels. Reject self-links,
  secondary parents, alias chains and empty labels. No arbitrary URL or filter
  fields. Use each F-K operator-question phrase as its initial control label;
  retain the native panel heading.
- Same-route disclosures follow their parent in roster order. Cross-route
  detail panels stay at their native route position, initially closed; reverse
  `from` to derive one related link on the primary panel. No second relationship
  list. Generate paths from the fixed route mapping and encoded panel fragment.
- Keep native children mounted so closing a disclosure cannot reset query
  status, instrument bindings or editable prices. The shared renderer composes
  snippets; route/native components still execute their own queries and draws.
  An alias mounts no query and is excluded from query-status tallies and
  `judged`. Legacy flat configs still render the original native panel.
- Emit each old panel anchor once. Initial hashes, client navigation and history
  changes open the relevant disclosure, then scroll and focus its summary.
  Preserve group anchors. `/console/model/#refusing-rule` becomes a labelled
  link to `/console/#failure-mix`, retaining the existing stage/rule table.
  No new stage-filter protocol.
- Keep `DRAWN_BY` receivers unchanged, including `score_ms -> score-cost`.
  `ItemTimeSplit.svelte` and `VerdictSplit.svelte` already contain disclosures:
  show their inner records inline when the panel itself is disclosed, while
  preserving flat-mode behavior. Do not create a nested disclosure chain.

This proposal changes an authored config contract even though telemetry shapes
stay unchanged. Row 4 remains blocked on L3.

#### L4 - Explorer opening policy

Keep typed-date precedence and its existing missing/duplicate/unplaceable-day
refusals. For non-date answers, retain the current candidate order where it can
draw. Evaluate candidates through `resolveRoles` and `chartShape`, using finite
numeric readings and distinct subjects rather than raw row count. A scatter or
distribution must satisfy its existing configured floors. If a small result has
one text label and two numeric columns, try Ranked on the first numeric column;
retain its existing unique-name, nonnegative and nonzero checks. Otherwise keep
the table and an explicit refusal. Never silently group duplicate labels.

Manual chart types and role choices remain available and keep their current
floor/refusal behavior. Cast the scored-per-day example's date in SQL. Direct
open reuses the already typed `__UI_CONFIG__.number_format` in the universal
console layout; delete its number-format-only server load. No new define,
serialized field, fallback document, reader or source is needed.

### Enumerated defect triage

Table M

| ID | Original cause | Evidence and consequence | Disposition |
| --- | --- | --- | --- |
| M1 | 1 - percentage units | Geometry uses 0-100; the component multiplies readout/ARIA shares by 100 again. | Row 5: fix retained distributions once. |
| M2 | 2 - missing process identity | Work omits `--server-pid`; server RSS/major faults are absent while worker/OS readings exist. | Row 6; H3/H10 are retained. No backfill. |
| M3 | 3 - flag alias mismatch | Long config flags versus short lookups lose slot limits, requested pinning and fingerprint changes. | Row 6; H11 is retained. Fix shared interpretation. |
| M4 | 4 - window mismatch | Pipelines reanchors private evidence on compact reach. Summaries correctly keeps two anchors but does not make their different dates clear. | Row 5: fix Pipelines selection; label both evidence windows without unifying them. |
| M5 | 5 - publication lag | Deployment preceded packing. One failed Pages run has no jobs, checks or failed-job log; cause remains unknown. | Row 2: distinguish packing from deployment and diagnose before any publication-code change. |
| M6 | 6 - explorer direct open | Server layout data is absent from static fallback output. | Row 7: remove runtime server-data dependency. |
| M7 | 7 - undrawable default | Paired was selected for seven rows against a 160-reading floor; Ranked worked. | Resolve L4, then Row 7; manual chart types remain. |
| M8 | 8 - text date example | Day-by-day SQL omits the date cast. | Row 7: fix retained example, not the ledger schema. |
| M9 | 9 - preference failure | Storage exceptions block loading or leave chart/control windows inconsistent. | Row 3: share optional-preference handling; no separate hardening project. |
| M10 | Conditional query rejection | Unexpected rejections can leave loading unresolved; ordinary boundary failures are already typed. | Row 5: fix demonstrated retained paths, not hypothetical failures. |
| M11 | Expected missing readings | Frequency collection is disabled; other readings are absent or await packing/publication. | Explain absence; do not invent values or enable unused collectors. |
| M12 | Mislabelled age clock | `article-age` measures source publication to item start, but the route heading claims age at publication. | Row 5: correct the heading and retain the existing successful-item cohort and exclusions. |

## 3. Row #2 - Reduce closed-day data delay without another writer

- **Scope:** Apply the settled L2 choice through existing compaction; diagnose M5 without adding another writer.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/gardener.py`
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
- **Acceptance gates:** L2 must be resolved first. Local: shared selector, applicable lint/types and focused config/schedule/retry tests. CI: merge-candidate gates. Observe normal compaction and deployment separately; diagnose M5 before adding any publication-code edit. No production dispatch as a test.
- **Oracle:** The config boundary rejects zero on the base and accepts it after the selected contract expansion. Fixed UTC inputs preserve existing scheduling arithmetic, exclude today and retain late-arrival/retry behavior. This cannot guarantee scheduler latency or deployment inclusion.

### Decisions

Table N

| ID | Decision | Authority |
| --- | --- | --- |
| N1 | If L2 selects zero, expand and version the native validator before config uses it. Keep positive values readable; reject negatives. Scheduling arithmetic already handles zero and needs no source edit. | `CompactionPolicy`, `gardener/schedule.py`; Fowler. |
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
  - `frontend/src/routes/console/+layout.svelte`
  - `frontend/src/lib/components/ConsoleNav.svelte`
  - `frontend/src/lib/components/ConsoleBand.svelte`
  - `frontend/src/lib/components/WindowControl.svelte`
  - `frontend/src/lib/components/WindowControlSource.svelte`
  - `frontend/src/lib/components/WindowStatus.svelte`
  - `frontend/src/lib/console/window-slot.ts`
  - `frontend/src/lib/console/window-preference.ts` (new optional-storage boundary)
  - `frontend/src/lib/console/strip.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/voices/+page.svelte`
  - `frontend/src/routes/console/judgement/+page.svelte`
  - `frontend/src/styles/app.css`
  - `frontend/tests/console-nav.spec.ts`
  - `frontend/tests/console-shell.spec.ts`
  - `frontend/tests/console-window.spec.ts`
  - `frontend/tests/console-machine-journey.spec.ts`
  - `frontend/tests/console-data-explorer-still.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/what-sits-above-every-console-route.md`
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** Local: applicable lint/types and in-memory preference tests, including throwing storage and route handoff. Register the new source in the bounded support inventory. CI: existing console journey/layout coverage. Browser: populated route, cross-route navigation and missing/empty data; review narrow navigation and both themes with Susan. No panel matrix.
- **Oracle:** The first viewport shows a usable comparison, window and evidence date; storage errors do not block navigation or queries. This does not establish panel value.

### Decisions

Table P

| ID | Decision | Authority |
| --- | --- | --- |
| P1 | Apply L1 without new appearance fields, fixed rail dimensions or icon assets. Preserve URLs, theme preference, semantic navigation and keyboard access. | Susan; existing tokens and frame config. |
| P2 | Compact status without conflating publication, chart reach and newest-run scope. | Susan; window contract. |
| P3 | Share M9 handling in the mounted layout's preference state: storage failure warns but cannot block queries, lose the current choice on navigation or desynchronize windows. | Reproduction; existing guarded routes. |
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
  - `frontend/src/lib/console/route-console.ts`
  - `frontend/src/lib/components/ConsolePanels.svelte` (new presentation composition)
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/judgement/+page.svelte`
  - `frontend/src/routes/console/voices/+page.svelte`
  - `frontend/src/lib/console/pipelines/ItemTimeSplit.svelte`
  - `frontend/src/routes/console/judgement/VerdictSplit.svelte`
  - `frontend/tests/appearance-config.spec.ts`
  - `frontend/tests/console-model-instruments.spec.ts`
  - `frontend/tests/console-model-ledgers.spec.ts`
  - `frontend/tests/console-machine-journey.spec.ts`
  - `frontend/tests/console-pipelines-lifecycle.spec.ts`
  - `frontend/tests/console-judgement-nothings.spec.ts`
  - `frontend/tests/support/panel-tab.ts`
  - `frontend/tests/support/console-sources.ts`
  - `frontend/tests/support/console-expect/console-built-page/model.ts`
  - `docs/concepts/config/appearance.md`
  - `docs/architecture/publishing/console.md`
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md`
  - `docs/architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md`
  - `docs/architecture/publishing/console-machine.md`
  - `docs/architecture/publishing/who-supplied-the-day-and-which-feeds-failed.md`
  - `TODO/20261109-console-redesign-plan.md`
- **Acceptance gates:** L3 must be resolved first. Local: legacy/stamped config validation, reference/order/alias tests and existing model-panel, native-query and Voices regression coverage. Extend named support for disclosure opening; register the new component. CI: unchanged instrument bindings and merge-candidate gates. Browser: extend the existing journey for keyboard disclosure, direct hash, history and cross-route detail. No panel matrix or mechanical historical edits.
- **Oracle:** Each question has one default home; distinct readings and old anchors remain reachable. This does not prove cohort equivalence.

### Decisions

Table R

| ID | Decision | Authority |
| --- | --- | --- |
| R1 | G4 shares `failedRuleQuery` and the failure-list component with Pipelines. Preserve the existing all-stage readings through an alias; add no stage-filter protocol. | Query/consumer inspection; Jony. |
| R2 | Keep means, medians, distributions, per-run tails and normalized comparisons distinct. Consolidate navigation, not metrics. | Jony; existing reducers. |
| R3 | Preserve D2's publication boundary; relocation does not permit new exposure or cohort substitution. | Console delivery contract. |
| R4 | Preserve `DRAWN_BY` bindings for disclosed instruments; retain native fields and producers. | Instrument contracts. |
| R5 | Apply only the settled L3 contract. Keep native query dispatch and instrument ownership; aliases never enter query tallies. Do not edit the server loader or build-time envelope, which already carries `RouteConsole`. | L3; Fowler construction consultation. |

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
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/lib/console/model/Query.svelte`
  - `frontend/src/routes/console/voices/+page.svelte`
  - `frontend/src/lib/console/pipelines/ArticleAge.svelte`
  - `frontend/tests/console-readout-data.spec.ts`
  - `frontend/tests/console-pipelines-window.spec.ts`
  - `frontend/tests/console-pipelines-native.spec.ts`
  - `frontend/tests/console-pipelines-window-page.spec.ts`
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
| T1 | Fix M1 in `Distribution.svelte` readout and mark ARIA, not correct 0-100 geometry. Its native consumers are ArticleAge, MachineCharts and explorer ShapePanel. | Geometry/component and consumer inspection. |
| T2 | Native comparisons keep their common endpoint; build-time evidence keeps its published-day anchor. Label differing scope. | Window contract; M4. |
| T3 | Missing is not zero. Do not backshift empty build-time windows or invent endpoints from the browser clock. | Window/missing-data contract. |
| T4 | Fix M10 only on a demonstrated retained path. Preserve explicit failures and usable siblings; do not swallow programmer errors. | Query failure contract. |
| T5 | For M12 use `Source age at work start`; retain feed-stated times, successful-item selection, inferred/future exclusions and the logarithmic-axis zero note. | `pipelines/article-age.ts`; M12. |

### Rejected alternatives

Table U

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| U1 | Use the newest endpoint everywhere | Implies absent evidence exists. | Redesign comparison/partial coverage. | Window contract. |
| U2 | Export dates, percentages or chart payloads again | Duplicates native answers. | Another contract and synchronization path. | A5/B3. |
| U3 | Catch all route errors | Can misreport defects as quiet results. | Preserve classification and diagnostics. | Error contract. |

## 7. Row #6 - Restore collection needed by retained hardware diagnostics

- **Scope:** Restore process identity for H3/H10 and shared flag interpretation for H11 and provenance.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/fingerprint.py`
  - `backend/idhazh/stages/work.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_server_argv.py`
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
| V1 | H3/H10 remain, so pass the model process identity already produced by the workflow. Do not discover a process by name. | Panel review; work recorder. |
| V2 | Fix M3 in shared flag interpretation used by settings and fingerprints; use the aliases in the existing recorded server-help contract. Preserve canonical recorded keys and verbatim runtime arguments. | `llm/server.py`, `fingerprint.py`, recorded runtime help. |
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
  - `frontend/src/lib/console/explorer/shape.ts`
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
| X1 | Read the existing `__UI_CONFIG__.number_format` in universal layout success and absence paths; delete its server-only number-format load. No Vite, global-type or payload change is needed. | Existing typed build-time define; static fallback contract. |
| X2 | Preserve client fallback, manual charts, table answers and publication consent. No new prerendered data document. | Explorer delivery contract. |
| X3 | Apply L4 through existing role/shape validation. Cover valid-reading and subject floors, the small grouped-result fallback and unchanged manual refusal behavior in the existing shape spec. | M7; `openingType`, `resolveRoles`, `chartShape`. |
| X4 | Cast the retained example date in SQL; keep the ledger schema unchanged. | M8. |

### Rejected alternatives

Table Y

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Y1 | Lower shared floors for the example | Changes unrelated reporting behavior. | Separate reporting-floor decision. | L4. |
| Y2 | Migrate the ledger date type | Archive migration for a query mistake. | Schema versioning and historical reader changes. | M8. |
| Y3 | Add explorer exports or a server endpoint | Duplicates data delivery. | New persisted/publication contract or hosting change. | A5/B3. |
