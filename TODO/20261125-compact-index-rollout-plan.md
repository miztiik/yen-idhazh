# Make compact indexes list only live files

**Last Updated:** 2026-11-25

**Correction level:** 5 - changes the meaning of a persisted field shared by the gardener and its readers.

## 0 - Operating contract

**Table A - Scope and release order**

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | A compact index mixes files readers can open with periods that have no file. Make membership explicit without losing the difference between quiet periods, lost data and unexplained gaps. |
| A2 | Hard scope - in | Daily, monthly and yearly compact index contracts; readers and writers named below; compatibility, tests, deployment and the owning docs. |
| A3 | Hard scope - out | See Table B. |
| A4 | Chosen strategy | Fowler: split file membership from coverage inside the existing index JSON. Merge and deploy dual readers first; switch emission second; upgrade an index only when a normal operation next writes it. |
| A5 | ESCALATE triggers | 1. Pause before changing the contract under [section 6](../CLAUDE.md#6-correction-levels). 2. Pause the writer cutover if a required reader cannot be upgraded or reloaded, or if legacy writers cannot be kept out of the cutover. 3. Surface a requirement to rewrite idle indexes, change retention or raise a payload budget instead of adding it to this rollout. |
| A6 | Execution | Autonomous orchestrator per [execute-a-plan.md](../docs/how-to/execute-a-plan.md). Parallel N = 4; the writer row waits for the reader row to merge and deploy. |

**Table B - Work outside this plan**

| ID | Excluded work | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Bulk rewrite of existing compact indexes | An idle index can stay on the legacy layout indefinitely; dual readers must continue to accept it. | A requirement that every current index use the new layout by a fixed date. Use a separately scoped, bounded JSON-only rewrite over the registered indexes. |
| B2 | Parquet backfill, row or envelope migration, history rewrite, new control files or changes to config and retention | Existing retention and supported file formats do not change. No storage savings are credited to this rollout. | A separately identified data or retention requirement. |
| B3 | Support for a pre-cutover browser tab without reloading | A tab running the old frontend can refuse a newer index until it reloads. | A continuity requirement for old clients; price serving a matching version-pinned snapshot of the indexes and their files. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 1 - Status Reckoner

**Table C - Merge sequence**

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Merge and deploy compatible compact-index readers | - | A | DONE | improved-fortnight | - | - |
| 2 | Switch compact-index writers and verify the first normal write | 1 | B | PENDING | - | - | - |

## Row #1 - Merge and deploy compatible compact-index readers

- **Scope:** Teach all consumers to read both layouts without changing the format committed by the gardener or range prune.
- **Files touched:**
  - `backend/idhazh/contracts/ledger_index.py`
  - `backend/idhazh/gardener/ledger_marks.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/ledger/ledger_files.py`
  - `backend/idhazh/ledger/stored_output.py`
  - `backend/idhazh/telemetry/door_prune.py`
  - `backend/tests/contracts/test_ledger_index.py`
  - `backend/tests/contracts/test_frontend_index_shapes.py`
  - `backend/tests/contracts/test_page_ceilings.py`
  - `backend/tests/gardener/test_ledger_marks.py`
  - `backend/tests/ledger/test_ledger_files.py`
  - `backend/tests/ledger/test_stored_output.py`
  - `packages/common-contracts/src/schemas/ledger-index.schema.ts`
  - `packages/common-contracts/src/schemas/planner-publication.schema.ts`
  - `packages/common-contracts/test/ledger-index.test.ts`
  - `tests/fixtures/feed-ingest-plan/ledger-history.json`
  - `packages/ledger-file-writer/src/planner-publication.ts`
  - `packages/ledger-file-writer/test/planner-publication.test.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-period.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/resolve-health-days.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-outputs.ts`
  - `services/feed-ingest-plan/test/ledger-history.test.ts`
  - `services/feed-ingest-plan/test/planning-health.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `frontend/src/lib/data/compact-index.ts`
  - `frontend/src/lib/data/slice.ts`
  - `frontend/src/lib/data/slice-reader.ts`
  - `frontend/src/lib/data/ledger-reach.ts`
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/scripts/published-ledgers.mjs`
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/support/ledger-lifecycle.ts`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `docs/reference/feed-planner-ledgers.md`
- **Acceptance gates:** Local: select affected Python and frontend checks with `npm --prefix frontend run test:changed -- --list` and the [shared selector](../docs/how-to/run-the-gates.md#select-local-checks-and-let-ci-verify-the-change). Run the named contract, reader and staging cases above and Bun checks for the affected native packages and planner service. Smoke-test a console read, an Explorer query and a missing-data case with the integrated browser; check the console for new errors and 404s. CI: require the green merge candidate, including frontend field and vocabulary bindings, native checks, and the site build and payload ceilings. After merge, verify the Pages deployment is from a revision containing the dual reader and test a fresh load before starting Row 2.
- **Oracle:** Feed equivalent legacy and split indexes, including a mixed-tier set, to the real consumers. They must select the same files and preserve bounds, quiet/lost/gap results, recovery marks and planner history behavior; a real zero-row file still supplies columns, and a coverage-only period makes no payload fetch. Assert that repository writers still emit the old shape and stamp. This proves compatibility, not that any open tab has refreshed.

**Table D - Contract and consumer decisions**

| # | Decision | Authority |
| --- | --- | --- |
| D1 | `CompactIndex` in `backend/idhazh/contracts/ledger_index.py` owns the wire shape. Introduce a date-only version for the split and record its changelog in the same commit as the read migration; bind the browser and native TypeScript copies to it. Keep the same ledger, period and yearly-only `expired_through` keys and the same index paths. | [Schema rules](../docs/architecture/contracts/schemas.md#every-contract-carries-version-and-changelog) |
| D2 | The new `entries` list retains row/byte counts, optional digest and quality metadata, omitting fields with default values. Only packed members belong there, regardless of row count. The new `coverage` list is present even when empty; a record has `covers`, `state` (`empty` or `lost`), optional `lost_days` (default `[]`) and optional `set_aside` (default `0`). It cannot carry rows, bytes or a digest. `lost` remains daily-only; a month or year's lost days are in `lost_days` on its owning record. | Fowler; existing [index invariants](../docs/architecture/contracts/persistence.md#what-an-index-entry-says) |
| D3 | Validate the two lists in ascending order, with no duplicate period within or across them, correct UTC period stamps, and existing lost-day/count rules. A yearly expiry mark applies to both lists. Require the split stamp for `coverage`; do not accept malformed split indexes as legacy. Split validated older records on read by their file state, not their row count; a missing legacy entry state still means packed. Where the reader already accepts an unstamped index, treat it as legacy only if it has no `coverage` field. | Fowler; `CompactIndex` |
| D4 | Use one ordered view of both lists per runtime for coverage, marks and date precedence; use file membership for fetches and newest-file lookup. Python bounded reads, the verifier and the gardener keep existing missing/recovery behavior; the planner inventory and history readers keep existing expiry, late raw and coverage rules. A range prune selects files as before and must preserve coverage for the periods it rewrites. | Existing consumer behavior |
| D5 | Site staging trims both lists by the existing window and copies only live files. Its planner projection removes a refused file from the staged membership and records the existing lost outcome without rewriting its source. Preserve the input layout and version for each staged index, even when it is trimmed or projected. Test the staged payload budget with both lists. | [Panel staging](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door) |
| D6 | Keep the [legacy writer stamp](../backend/idhazh/contracts/ledger_index.py) (`2026-10-25` at planning time) and mixed wire list during this row. Distinguish supported reader version from emitted version in the shared serializer. Do not dual-write or introduce a config switch. | Fowler |

**Table E - Alternatives not taken**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Delete no-file records outright | The newest checked period could move back and quiet or lost dates could become false holes or raw fallbacks. | Replace the missing evidence with another progress/coverage mechanism or change reader behavior. | Fowler |
| E2 | Put coverage in a separate JSON file | One existing index can carry both facts; both are needed for a date-range answer. | An extra fetch and another file that must stay in sync across writes, staging and recovery. | Fowler |

## Row #2 - Switch compact-index writers and verify the first normal write

- **Scope:** Emit the split contract from normal compaction and named prune writes after the readers are deployed, without converting untouched indexes.
- **Files touched:**
  - `backend/idhazh/contracts/ledger_index.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/telemetry/door_prune.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `backend/tests/gardener/tasks/test_yearly_expiry.py`
  - `backend/tests/retention/test_prune_range.py`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/publishing/ledger-compaction.md`
- **Acceptance gates:** Local: use the shared selector and extend the named promotion, expiry and prune checks with legacy inputs and raw serialized output assertions. CI: require all checks green on the merge candidate. Before merging to `main`, verify the deployed dual reader, let active/queued legacy gardener runs finish and use fresh `main` runs and operator checkouts instead of legacy reruns. After merge, confirm the PR landed on remote `main`; on the next scheduled write, inspect the changed registered index and its named member paths in the same commit. If there is no write yet, leave the operational observation pending; do not force a live run as a merge gate.
- **Oracle:** Start with legacy indexes that name real files and no-file periods. Check the serialized indexes after daily-to-monthly and monthly-to-yearly promotion and after expiry and restart. Each retained worked period must have exactly one live file entry or a coverage record, not both; superseded entries and coverage must leave when the replacement lands, and loss metadata must survive at the coarser tier. Expiry removes the year from both lists without rewinding progress. The named-prune check must preserve unrelated coverage and keep a real zero-row file indexed. This does not prove that idle indexes have all upgraded.

**Table F - Write and release decisions**

| # | Decision | Authority |
| --- | --- | --- |
| F1 | Switch both repository writers to the declared current version and the shared serializer. Keep the existing write set, publication checks and atomic Git commit for compaction. Raw and compact Parquet codecs, paths, row identities, retention, and membership acquisition are unchanged. | Fowler; [compaction write order](../docs/architecture/publishing/ledger-compaction.md#a-day) |
| F2 | Roll up coverage on the same period boundary as file membership. Carry lost days and set-aside counts to the month or year, on its coverage record if it has no file. Drop expired coverage with its year; preserve the existing watermark. Keep the current handling of incomplete or missing indexes; file listings cannot reconstruct coverage. | `CompactIndex`; [yearly expiry](../docs/architecture/publishing/ledger-compaction.md#yearly-expiry) |
| F3 | Upgrade only JSON that normal work rewrites. Leave compatible readers deployed on rollback; revert the emission switch if necessary. Do not restore old indexes alone: the files they name may already have been replaced. | Fowler |
| F4 | Publish after required checks per [ship-a-pr.md](../docs/how-to/ship-a-pr.md). Treat a successful merge and the later observed scheduled output as separate facts. | Release procedure |

**Table G - Alternatives not taken**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Merge readers and writers together | A gardener wake can publish the new format while the deployed site still runs the old reader. | Coordinate a writer freeze or keep a compatible publication until deployment is confirmed. | Fowler |
| G2 | Rebuild all indexes from files | A file list cannot recover checked empty periods, lost periods or the expiry mark. | A lossless conversion from current JSON, not a file scan, with its own bounded work and publication checks. | Fowler |
