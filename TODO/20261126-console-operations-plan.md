# Operations Console

**Last Updated**: 2026-11-26
**Level**: 3 - browser routes and published evidence

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Keep workflow execution and ledger upkeep visible without mixing either into digest production, judge verdicts or hardware measurements. |
| In | Operations navigation, one UTC window, the Gardener write calendar and a separate Council completion view for every recorded judge. |
| Out: live attempt census | Packed records cannot prove a missed, cancelled or unscheduled run. An independently published attempt roster would resolve it at the cost of another producer and retention contract. |
| Out: historical write and expiry counts | Replaced or expired packs cannot be recovered from current indexes. Exact totals require retained publication receipts. Do not change pruning or publication consent. |
| ESCALATE | Stop if correctness needs a new producer, persisted record shape, wider publication or a workflow dispatch. |
| Chosen strategy | Present existing packed fields in the browser. The Operations link is a browser destination, not a new verdict in the persisted Console band. |
| Execution | Autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1 because both rows share a route and its fixtures. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 because both rows share a route; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Show the Gardener write calendar in Operations | - | A | DONE | scaling-adventure | - | - |
| 2 | Show Council completion independently for each judge | 1 | B | DONE | scaling-adventure | - | - |

## 2. Row 1 - Show the Gardener write calendar in Operations

- **Scope:** Add Operations after Pipelines and before Hardware, use the work-bars glyph, and replace the maintenance menus and report walls with the approved calendar and dated outcomes.
- **Files touched:** `config/console/operations.json`, `config/console/pipelines.json`, `config/appearance.json`, `backend/idhazh/contracts/knobs/console_style.py`, `backend/idhazh/contracts/appearance_config.py`, `backend/tests/contracts/test_panel_queries.py`, `frontend/vite.config.ts`, `frontend/src/app.d.ts`, `frontend/src/lib/server/config.ts`, `frontend/src/lib/components/ConsoleNav.svelte`, `frontend/src/lib/components/WindowControlSource.svelte`, `frontend/src/lib/console/band.ts`, `frontend/src/lib/console/console-destinations.ts`, `frontend/src/lib/console/console-style.ts`, `frontend/src/lib/console/route-console.ts`, `frontend/src/lib/console/route-glyph.ts`, `frontend/src/lib/console/window-slot.ts`, `frontend/src/lib/icons/manifest.json`, `frontend/src/lib/icons/svg/operations.svg`, `frontend/src/lib/icons/generated.ts`, `frontend/src/lib/icons/PROVENANCE.md`, `frontend/src/lib/charts/d3/DateTileGrid.svelte`, `frontend/src/lib/console/queries/operations.ts`, `frontend/src/lib/console/queries/pipelines.ts`, `frontend/src/lib/console/pipelines/GardenerActivity.svelte`, `frontend/src/lib/console/pipelines/GardenerTaskReports.svelte`, `frontend/src/lib/console/pipelines/gardener-activity.ts`, `frontend/src/lib/console/operations/GardenerActivity.svelte`, `frontend/src/lib/console/operations/GardenerTaskReports.svelte`, `frontend/src/lib/console/operations/gardener-activity.ts`, `frontend/src/lib/console/operations/gardener-reports.ts`, `frontend/src/lib/data/compact-write-footer.ts`, `frontend/src/lib/data/compact-file-writes.ts`, `frontend/src/lib/data/ledger.ts`, `frontend/src/routes/console/+layout.svelte`, `frontend/src/routes/console/+page.server.ts`, `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/operations/+page.ts`, `frontend/src/routes/console/operations/+page.svelte`, `frontend/scripts/build-frame-css.mjs`, `frontend/src/styles/frame.generated.css`, `frontend/tests/appearance-config.spec.ts`, `frontend/tests/console-panel-queries.spec.ts`, `frontend/tests/console-nav.spec.ts`, `frontend/tests/ledger-door.spec.ts`, `frontend/tests/support/console-sources.ts`, `docs/architecture/publishing/console.md`, `docs/architecture/publishing/what-operations-draws.md`, `docs/architecture/publishing/what-the-pipelines-route-draws.md`, `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md`, `docs/concepts/config/appearance.md`, `docs/concepts/ui-shell.md`.
- **Acceptance gates:** Run the named frontend config, route, chart and disk query checks and Console type check locally. Check one desktop and one narrow view, changing the top window and rendering missing evidence. Require the selected application CI and confirm Pages after merge.
- **Oracle:** A monthly file that covers September and was written on a day in the 30-day window leaves the chart and its callout when the 7-day window excludes its write date. A short daily read leaves patterned days, not an empty calendar. This cannot recover removed file versions.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Use the shared top preset and mounted UTC day; all marks and callouts are clipped to that explicit interval. The read is still bounded by staged indexes and existing file and byte limits. | Console design and query door |
| 2 | A dated footer confirms a retained write; the receipt uses the index's row and byte counts and the footer's optional input-file count. The report's work-end timestamp, real stops and recovery notes are separate facts. | Ledger contracts |
| 3 | Use jade checks, rose crosses, gold deferral marks and neutral unknown patterns. Month and year have milestones, not a daily obligation. Cleanup stays a drill-down and previews never claim deletion. | Operations design |

| # | Rejected option | Why | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Increase the read cap or query the live workflow API | A write calendar needs evidence gaps, not unlimited history or a second source of truth. | More network and memory or a new runtime boundary and authorization policy. | Query door |

## 3. Row 2 - Show Council completion independently for each judge

- **Scope:** Move only Council execution to Operations and replace attempt counts and selectors with labelled per-judge completion tracks; keep published grouping and judge verdicts on Judgement.
- **Files touched:** `config/console/judgement.json`, `config/console/operations.json`, `backend/tests/contracts/test_panel_queries.py`, `frontend/src/lib/console/council-runs.ts`, `frontend/src/lib/console/queries/judgement.ts`, `frontend/src/lib/console/queries/operations.ts`, `frontend/src/routes/console/judgement/CouncilRunsPanel.svelte`, `frontend/src/routes/console/judgement/+page.svelte`, `frontend/src/routes/console/operations/CouncilRunsPanel.svelte`, `frontend/src/routes/console/operations/CouncilJudgeChart.svelte`, `frontend/src/routes/console/operations/+page.svelte`, `frontend/tests/appearance-config.spec.ts`, `frontend/tests/console-drawn-cells.spec.ts`, `frontend/tests/console-panel-queries.spec.ts`, `frontend/tests/support/console-expect/console-frame/judgement.ts`, `frontend/tests/support/console-sources.ts`, `docs/architecture/publishing/console.md`, `docs/architecture/publishing/what-operations-draws.md`.
- **Acceptance gates:** Extend the existing Council reducer case across judges, part counts, attempts, UTC boundaries and missing reports. Review the same Operations view; retain the Judgement smoke. Require CI before merge.
- **Oracle:** Two judges working the same digest and day with different declared widths render separate counts and combine marks. A part from another judge or retry cannot fill a missing slot. This cannot determine how many unreported attempts ran.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Group by judge, digest, run and attempt. Place each on its first recorded UTC step day. Keep exact part and combine outcomes in the shared keyboard and pointer readout. | Council record contract |
| 2 | Read the existing widest staged digest window, then clip execution days to the top window; retain a coverage note for old backfills outside the staged record. | Static query door |

| # | Rejected option | Why | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Pool judges into a total or ask for a judge in a dropdown | A total hides who did not finish and merges different declared work. A dropdown hides comparison. | More clicks or lost per-judge coverage. | Operations design |
