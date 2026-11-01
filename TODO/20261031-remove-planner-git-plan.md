# Remove planner Git outside checkout and delivery

**Last Updated**: 2026-10-31
**Level**: 5 - execution-input authority and the planner maintenance interface.

## 0 - Operating contract

Table A

| ID | Field | Value |
| --- | --- | --- |
| A1 | Purpose | Remove Git from planner input discovery, startup, history reads and computation without replacing it with another database or saved file catalog. |
| A2 | Git boundaries | Initial `actions/checkout@v6` obtains code and required saved data at the same ref. Final data delivery may fetch its destination, check collisions and commit/push or retry. No other planner stage invokes Git or a remote Git data API. |
| A3 | Input design | Load the required saved evidence using files, validate it, and retain one fixed in-memory input set per run. Do not copy inputs into another directory or persist the input set. Keep current work separate from the immutable baseline. |
| A4 | Scope | Feed-planner workflow adapters, standalone entry points, every planning API and history consumer, planner-ledger maintenance and its scheduler handoff, directly related tests and current documentation. Do not move removed Git work into another helper or language. |
| A5 | Input coverage | Initial checkout includes registered raw files (individual saved observations), compact files (combined-period observations), published-URL and item-health files and the existing publication inventory. Load health, discovery, publication exclusions, settled failures and selected-metadata linkage before the first fetch. Include existing request-report windows and supported UTC boundary adjustments. |
| A6 | Preserved behavior | Current-format native validation; registered roots and regular-file checks; complete named-day membership; honest empty, missing, corrupt and partial evidence; valid sibling use; existing raw/compact merge rules; all required feed/article work; real HTTP stages; current clocks, policies, counters and outputs. |
| A7 | Removed guarantee and cost | Readers no longer independently prove that local files match an arbitrary Git commit or reject a file solely because it is untracked. The initial checkout or explicit caller input directory is the input authority. Later remote commits are not adopted during the run. Initial checkout acquires more saved data up front. |
| A8 | Identity | Use the initial checkout's `GITHUB_SHA`, validated with `CommitShaSchema`, or the existing explicitly supplied runtime identity. Missing or invalid identity fails before writes. Do not query `HEAD`, invent a revision or add identity to public plan controls. |
| A9 | External prerequisite | Deliver the outcome titled `Remove planner SQLite and add failure-only raw-document output` in `TODO/20261031-planner-sqlite-removal-plan.md` before editing overlapping execution-state code. Preserve that work; do not reopen SQLite removal or restore delivery-only checksums. |
| A10 | Execution | Implement one outcome per nested PR. Parallel N = 1 because the deliveries share history helpers, documentation and workflow integration. |
| A11 | Escalation | Stop before changing `CLAUDE.md`, another ledger family's formats or execution rules, history rewriting, source permissions, required collection scope, retention policy, configured limits, or adding a persisted input store. Surface any caller that still needs arbitrary-revision reads or saved-request recovery. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan; keep parallel N = 1 because the deliveries share inputs and documentation; honor the escalation triggers in section 0.

Table B

| ID | Out of scope | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | SQLite removal and delivery-checksum removal | This work waits for the external outcome in A9 rather than duplicating its implementation. | A concrete unresolved dependency reported by that delivery. |
| B2 | Other ledger families and the scheduled history-rewrite job | Their separate data-acquisition and maintenance rules remain unchanged; this plan does not claim repository-wide Git removal. | A separately defined pipeline scope and its affected contracts. |
| B3 | Restart replay, successful raw-document archives and cross-process feed reservations | A restarted process starts a new execution; independent runs can observe the same earlier data. | A separate recovery, retention or coordination requirement. |
| B4 | New libraries, benchmarks, compatibility modes and private input artifacts | Use existing filesystem and native validation code; no additional storage lifecycle or dependency cost. | A named correctness gap that existing mechanisms cannot cover. |

## 1 - Status reckoner

Table C

| ID | Row | Title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Make planner execution use fixed file-loaded evidence | - | A | DONE | musical-doodle | - | Planner file inputs |
| C2 | 2 | Restrict acquisition and maintenance Git to delivery boundaries | 1 | B | PENDING | - | - | - |

## 2 - Input and contract changes

Table D

| ID | Surface | Final contract |
| --- | --- | --- |
| D1 | Named planner days | Retain `day` and complete `raw_files`; remove `raw_revision` and Git-specific proofs. Check supplied membership against the exact local UTC-day directory. Retain existing generic raw/compact indexes for non-planner evidence. |
| D2 | Filesystem membership | Use one registered UTC-day directory or explicitly named compact period at a time. Derive dates and paths from validated configuration and existing period metadata. No recursive archive walk, root-level discovery scan or replacement raw-day index. Ignore historical regular `index.json` files; refuse unsafe paths and unsupported members explicitly. |
| D3 | Live input set | Derive typed health, discovery, exclusion and publisher-publication evidence from existing readers. Retain these records in the existing live execution state from A9. Later stages apply current work and their existing clocks without reopening historical input. No new HTTP input or persisted payload is needed. |
| D4 | Health semantics | Preserve represented-day selection, independent calculation/report windows, supported saved zeroes/nulls, field-specific gaps, and raw/compact duplicate settlement. Missing report-only evidence must not prevent collection. |
| D5 | Publication linkage | Capture the current-day published, item-health and selected metadata needed for genuine publisher linkage. Selected counts never become publication evidence. Missing linkage retains the existing explicit fallback. |
| D6 | Code identity | Carry A8 through startup, host metadata and final output verification. Compare recorded identity with supplied execution identity, not a locally queried commit. Existing writer `git_sha` fields remain metadata. |
| D7 | Maintenance request/result | Remove `revision` and `revision-changed` from the transient maintenance interface and both callers. Stamp and changelog the TypeScript request/result schemas together. Reject obsolete interface input explicitly; do not introduce a compatibility branch. |
| D8 | Persisted data | No planner row or file-envelope shape changes. Preserve native schema, filename, ledger, date and canonical-content checks. Existing maintenance source/target content checks are not delivery-only checksum arguments and must not be removed accidentally. |
| D9 | Lifetime | Bound retained input with existing execution/batch limits and release it with that execution's retained batch lifetime. Do not evict a live required capture silently or add a listener-wide run queue. |

Table E

| ID | Control order | Data and Git behavior |
| --- | --- | --- |
| E1 | Initial checkout | Obtain code and saved ledger inputs once; no later sparse-checkout expansion or history import. |
| E2 | Input load and `/collections` | Resolve and validate required local evidence before feed eligibility and fetching; retain D3. |
| E3 | `/fetch` and `/parse` | Fetch permitted source content and parse live responses; reuse D3 and add only actual current work. |
| E4 | `/select-articles` and `/feed-health-state` | Use D3 and current work; preserve complete collection, selection-clock and partial-data rules. |
| E5 | `/partition-articles` and `/persist-selected-articles` | Assign workers and write completed local output; no repository operations. |
| E6 | Finalization | Feed-planner Git output uses one `safe_persist_data` batch. Gardener output keeps its existing final shard publisher, including compact replacement and deletion support. Reports and artifact upload invoke no Git. |

## 3 - Row 1 - Make planner execution use fixed file-loaded evidence

- **Scope:** Deliver a functional file-only planning and history path with one retained input set for every live execution.
- **Files touched:**
  - `packages/ledger-file-writer/src/read-planner-day-files.ts` (new shared filesystem membership helper)
  - `packages/ledger-file-writer/src/index.ts`
  - `packages/ledger-file-writer/test/planner-day-files.test.ts` (replace the reader-specific Git fixture coverage)
  - `services/feed-ingest-plan/src/read-ledger-history/read-run-history.ts` (new narrow composition of existing evidence readers)
  - `services/feed-ingest-plan/src/read-ledger-history/resolve-health-days.ts` (move the useful file-based represented-day selection here)
  - `services/feed-ingest-plan/src/read-ledger-history/read-planner-history.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-health-capture.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-feed-health-fields.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-discovered-evidence.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-request-history.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-exclusion-evidence.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-publisher-publication.ts`
  - `services/feed-ingest-plan/src/config/service-settings.ts`
  - `services/feed-ingest-plan/src/index.ts`
  - `services/feed-ingest-plan/src/api/document-state.ts`
  - `services/feed-ingest-plan/src/api/collection-operation.ts`
  - `services/feed-ingest-plan/src/api/prepare-planning-health.ts`
  - `services/feed-ingest-plan/src/api/feed-offers.ts`
  - `services/feed-ingest-plan/src/api/feed-health-state-operation.ts`
  - `services/feed-ingest-plan/src/api/selection-operation.ts`
  - `services/feed-ingest-plan/src/select-articles.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-history.ts`
  - `services/feed-ingest-plan/test/plan-recordings.ts`
  - `services/feed-ingest-plan/test/publication-recordings.ts`
  - `services/feed-ingest-plan/test/raw-day-members.test.ts`
  - `services/feed-ingest-plan/test/ledger-history.test.ts`
  - `services/feed-ingest-plan/test/history-window.test.ts`
  - `services/feed-ingest-plan/test/health-fields.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle-history.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle-http.test.ts`
  - `services/feed-ingest-plan/test/logical-completion.test.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-cli.test.ts`
  - `services/feed-ingest-plan/test/planning-health.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/planner-feed-history.md`
  - `docs/reference/feed-planner-ledgers.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/20261031-feed-ledger-simplification-plan.md` (only unresolved references affected by this removal; retain completed history)
  - `TODO/20261031-remove-planner-git-plan.md`
- **Acceptance gates - local:** Inspect the shared changed-test selection per `docs/how-to/run-the-gates.md`. Run `bun run check` in the affected TypeScript packages/service. In `packages/ledger-file-writer`, select `test/planner-day-files.test.ts`. In `services/feed-ingest-plan`, combine `test/collection-http.test.ts`, `test/ledger-history.test.ts`, `test/history-window.test.ts`, `test/health-fields.test.ts` and `test/plan-cli.test.ts` in one Bun invocation; add any further cases selected for the actual changed inputs. Use generated filesystem data and existing recorded source responses; no reader test initializes a Git repository, mocks a process or touches the external network.
- **Acceptance gates - CI:** Existing full merge-candidate gates remain authoritative. No live feed run or committing workflow dispatch is a gate.
- **Oracle:** With Git absent from the execution environment, a real recorded HTTP collection reaches selection and local persistence from raw/compact fixture files; changing or adding historical files after the capture leaves that execution's decisions unchanged. This does not prove that initial input is the newest remote data or restore process-restart recovery.

Table F

| ID | Decision | Authority |
| --- | --- | --- |
| F1 | Implement D2 once in the existing shared writer package; use native filesystem APIs and existing path/date/Parquet validators. Do not build another parser, catalog framework or persisted inventory. | A3, A6; existing writer ownership |
| F2 | Load all D3 categories before the first fetch, including standalone document executions. Stage references without their required live capture fail explicitly rather than reopening old input. | A5; settled live execution boundary |
| F3 | Keep baseline records immutable. Existing reducers derive current results from that baseline and current work; later feed parses add only new sightings. | D3-D5 |
| F4 | Known empty, omitted input, missing referenced files, unsupported format and invalid identity remain distinct. Use existing diagnostics and valid sibling evidence; unexpected errors propagate. | D4; field-read contract |
| F5 | Update the current workflow adapter when D1 changes so the first delivery remains runnable. The existing acquisition path is removed in the next dependent delivery, not replaced by a temporary compatibility mode. | C1-C2; coordinated reader/caller change |
| F6 | Move real-Git fixture setup out of general planner recordings. Retain it only for tests of final Git delivery, not as a prerequisite for ordinary planning. | A2; test tier matching the boundary |

Table G

| ID | Rejected alternative | Why rejected | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| G1 | Cache Git calls or move them to another reader helper | Still requires Git during computation and leaves different consumers on different revisions. | Continuing process and proof coordination across every consumer. | A2-A4 |
| G2 | Another raw-day JSON catalog or input-proof ledger | Recreates mutable membership state and its concurrent writer/retention obligations. | New persisted contract, publisher integration and consistency checks. | A1, A3 |
| G3 | Copy all input files into a private input directory | Not needed when required validated records are already retained. | Extra file copying, path handling, disk use and cleanup. | A3 |
| G4 | Remove Git but stop reading historical selected metadata | Changes a genuine publication-linkage consumer rather than its file access. | Loss of publisher evidence and a separate selection-contract change. | D5 |

## 4 - Row 2 - Restrict acquisition and maintenance Git to delivery boundaries

- **Scope:** Remove remaining planner Git imports and probes, acquire saved data in initial checkout, and give planner maintenance the same local-file authority without changing final publication capabilities.
- **Files touched:**
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `.github/workflows/idhazh-gardener.yml` (planner input acquisition and redundant setup only; not history rewriting)
  - `config/feed-ingest-plan-service.json`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-history.ts` (delete after its useful file logic moved)
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-outputs.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-current-files.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-deliver.ts`
  - `services/feed-ingest-plan/scripts/finalize-run-output.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/raw-day-members.ts` (delete)
  - `services/feed-ingest-plan/src/config/service-settings.ts`
  - `packages/common-contracts/src/schemas/planner-maintenance.schema.ts`
  - `packages/ledger-file-writer/src/read-planner-day-files.ts`
  - `packages/ledger-file-writer/src/planner-maintenance.ts`
  - `packages/ledger-file-writer/src/planner-maintenance-cli.ts`
  - `backend/idhazh/ledger/planner_maintenance.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/file_listing.py`
  - `backend/utilities/gardener_publish.py`
  - `packages/ledger-file-writer/test/planner-maintenance.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-delivery.test.ts`
  - `backend/tests/gardener/tasks/test_compaction_planner_siblings.py`
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/gardener/test_sparse_shard.py`
  - `backend/tests/workflows/test_gardener_workflow.py`
  - `docs/how-to/run-feed-ingest-plan-test.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/planner-feed-history.md`
  - `docs/architecture/publishing/committing.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/architecture/publishing/idhazh-gardener.md`
  - `docs/reference/feed-planner-ledgers.md`
  - `TODO/20261031-remove-planner-git-plan.md`
- **Acceptance gates - local:** Inspect the changed-test selection and run `bun run check` in the affected TypeScript packages/service. Select `test/planner-maintenance.test.ts` in `packages/ledger-file-writer`. Combine `test/feed-ingest-plan-workflow.test.ts`, `test/feed-ingest-plan-supervisor.test.ts`, `test/feed-ingest-plan-outputs.test.ts`, `test/feed-ingest-plan-finalization.test.ts` and `test/feed-ingest-plan-delivery.test.ts` in one service Bun invocation. Adapt existing scheduler tests where its planner handoff changes; retain their existing gate tier and add no Python planner model, test framework or helper package. Verify the named source inventory for removal of Git spawning, commit proofs, sparse expansion and remote Git data reads outside A2.
- **Acceptance gates - CI:** Existing full merge-candidate gates and real scheduler-to-TypeScript integration remain required. Preserve final publisher collision, deletion, permission and retry coverage. Do not dispatch a data-writing workflow as a repeatable gate.
- **Oracle:** A generated initial-checkout filesystem with no Git executable supports configuration loading, startup, HTTP planning, reporting and planner-maintenance computation; the only Git-dependent test phase is actual final data delivery. This cannot settle the elapsed time or download size of the platform's initial checkout.

Table H

| ID | Decision | Authority |
| --- | --- | --- |
| H1 | Extend each initial checkout with its required registered ledger namespaces and existing indexes/inventory. Replace custom acquisition with ordinary local input loading; no second checkout or fresh-main history fetch. | A2, A5; E1 |
| H2 | Delete acquisition-only helpers, Git blob proof/cache code, `sparseCheckoutPath`, stale digest-file staging and its unused `digest_root` setting. Preserve output inventory/report utilities still used by finalization. | A1; searched acquisition call sites |
| H3 | Carry A8 into host/run validation and finalizer callers. Remove all code-identity probes outside the publisher; missing metadata remains an explicit input error. | D6 |
| H4 | Apply D7 atomically to TypeScript schemas, the maintenance CLI and Python scheduler adapter. Python remains a scheduler and receipt reader, not a planner Parquet/model owner. | D7-D8; contract ownership |
| H5 | Replace planner-specific listing/widening/fetch callbacks in the scheduler handoff with local named-period metadata. Retain configured period/raw-file limits, dry-run parity, compact precedence, source/target refusals and deletion selection. Other-family paths remain unchanged. | A4, A6, A11 |
| H6 | Initial checkout data is already acquired when maintenance starts. Keep task-level transfer accounting truthful; do not label local reads as new network downloads, raise configured limits or invent checkout measurements. | A7, A11; measurement contract |
| H7 | Keep the final feed-planner delivery and existing gardener shard publisher separate. Do not route compact replacements/deletions through the immutable-append-only planner delivery API. | E6; existing publisher capabilities |
| H8 | Update current living rules and examples with the new file authority and two Git boundaries. Remove obsolete reader Git requirements/cases; keep final-publication Git checks and completed historical records. | A2; documentation ownership |

Table I

| ID | Rejected alternative | Why rejected | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| I1 | A preparatory Git import hidden inside a Python or TypeScript wrapper | Retains a third repository-operation role and defeats initial-checkout authority. | The same acquisition/proof machinery under another entry point. | A2-A4 |
| I2 | Use a remote Git data API instead of the Git executable | Still queries repository history during computation. | Network latency, credentials and another failure boundary. | A2 |
| I3 | Refresh input when another writer advances the destination | One execution would no longer use a fixed input set. | New consistency and replay policy across stages. | A3, A7 |
| I4 | Remove final publisher Git or its collision safeguards | Removes the required delivery mechanism instead of unnecessary planner operations. | A different publication platform and output-safety contract. | A2; E6 |
| I5 | Make a committing production run an acceptance gate | Repeating validation would create new data and side effects. | A controlled observation of the next ordinary run, not a reusable gate. | Acceptance contract |
