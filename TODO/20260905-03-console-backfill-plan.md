# 03 - The console shows the numbers already in the repo

**Last Updated**: 2026-09-05
**Level**: 3 (a persisted contract widening, a republished projection, and four operator panels)

**Chain**: previous [`20260905-02-retire-the-route-name-plan.md`](20260905-02-retire-the-route-name-plan.md) | next [`20260905-04-site-cap-defence-plan.md`](20260905-04-site-cap-defence-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O11, O29, O34, section 14.4b, section 14.4d, C23.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Eight numbers per item have been committed on every run for weeks and the console cannot see one of them. The five sentences a reader is shown about a doubtful summary have **never** been plotted, so nobody can say whether summaries are improving or which defect dominates. Both are fixed by publishing what is already on disk - **and the fix backfills over every past run**, so the answer arrives with history rather than starting from today |
| Hard scope - in | Widening the published telemetry projection and republishing every month; per-item cost panels; a panel for the five doubt reasons over time; faithfulness and lead-coverage panels; re-recording the console page ceilings this plan grows |
| Hard scope - out | Any new measurement. Every number here is already committed. No span work (plan 05). No visual-stage metric (plan 19). No change to what the pipeline computes |
| ESCALATE triggers | 1. A widened column is not an integer or a closed name - `FORBIDDEN_COLUMNS` and Rule #11 bound what may be published and a free-text cell is a stop. 2. Republishing a month does not reproduce the committed shard byte-for-byte on the unwidened columns. 3. `/console/` cannot hold the new panels under its ceiling even after a re-record sized for seven publishes |
| Chosen strategy | Widen the contract, republish from `state/`, then draw. The projection is rewritten whole on every publish already, so a widening is additive and the backfill is a re-run rather than a migration |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Eight committed numbers become publishable | - | A | IN-FLIGHT #423 | yi-c01 | #423 | Carmack ruled the seed: the eight cost 176,753 gzipped bytes on `/console/` and no panel draws them, so the shard carries them and the prerendered seed does not |
| 2 | What an item cost, drawn | 1 | B | IN-FLIGHT #427 | yi-c02 | #427 | Carmack ruled the two clocks stay apart and both axes double; the plan's illustrative `0.72 to 0.90` cache range did not survive - measured 0.518 in the middle, 0.000 to 0.820 across the spread, and 667 of 6,104 items reused nothing. Drawn from a server-side reduction per preset, so the seed keeps its nulls |
| 3 | The five doubt reasons get a shape | 1 | C | PENDING | - | - | - |
| 4 | Faithfulness and lead coverage join them | 3 | D | PENDING | - | - | - |
| 5 | The ceilings are re-recorded by the plan that grew them | 2, 4 | E | PENDING | - | - | - |

---

## 2. Row #1 - Eight committed numbers become publishable

- **Scope:** `PublicTelemetryRow` gains `fetch_ms`, `extract_ms`, `summarize_ms`, `prefill_ms`, `decode_ms`, `input_tokens`, `output_tokens`, `cached_tokens`, and every committed month is republished from `state/item-health/`.
- **Files touched:**
  - `backend/idhazh/contracts/public_telemetry.py`
  - `schemas/public-telemetry.schema.json` (generated)
  - `backend/idhazh/publish_telemetry.py`
  - `tests/fixtures/contracts/public-telemetry/*.json`
  - `frontend/src/lib/charts/series.ts` (`TELEMETRY_COLUMNS`)
  - `frontend/scripts/build-canary.mjs` (the third copy of the header, in JavaScript)
  - `frontend/public/telemetry/*.csv` (republished)
  - `backend/tests/test_telemetry.py`, `backend/tests/test_contracts.py`
  - `docs/concepts/telemetry.md`, `docs/architecture/**/telemetry-series.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + `git diff --exit-code -- schemas/`; the full suite; the canary build (`build_canary_day.py` then `npm run build:canary`); `npm run build` and `bundle-gate`.
- **Oracle:** Re-running the publisher over the committed `state/` reproduces each republished shard such that **every pre-existing column is byte-identical cell by cell** and each row has gained exactly eight cells. Comparing whole files would pass on a file that lost a row; comparing cell by cell against the old header cannot.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **This is a contract change, not a tuple edit.** `PUBLIC_COLUMNS` is `PublicTelemetryRow.csv_columns()`, so it takes a schema stamp, a changelog entry, the fixture round trip and the canary writer | C23, verified 2026-09-05 |
| 2 | **Append at the end, always.** `parseTelemetryCsv` checks the header by prefix, so appending is safe for a browser on the old bundle and inserting anywhere earlier blanks every console chart | Recorded behaviour, `series.ts` |
| 3 | Every added cell is an integer, so the forbidden-column guard and Rule #11 do not move | Andre |
| 4 | An instrument that did not run writes an **empty cell, never a zero** | Section 14.4b |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Publish only from today forward | The whole value is that the answer arrives with history; a series starting today cannot show whether anything improved | Owner, O29 |
| 2 | Have the console read `state/item-health/` directly at build time | It already can, and that is how the band panels work - but the runtime viewport reads the projection, and a panel that only exists at the default window is half a panel | Fowler |

---

## 3. Row #2 - What an item cost, drawn

- **Scope:** The console draws per-item read time, write time and token counts, including how much of the prompt was reused from cache.
- **Files touched:** `frontend/src/routes/console/**`, `frontend/src/lib/console/**`, `frontend/src/lib/charts/series.ts`, `frontend/tests/console-*.spec.ts`, `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run check` 0/0; build; `bundle-gate`; the browser suite on the canary build; the section 12 smoke including the data-absent arm.
- **Oracle:** Each drawn figure is re-derived independently from the committed projection inside the spec and compared to the drawn attribute. **A spec that compares a drawn mark against the label printed beside it is a consistency check, not an oracle** - both come from one number.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Cache reuse is drawn as a share, and the share is named in words beside it. `0.72 to 0.90` means nothing to an operator without "roughly three quarters of the prompt was not re-read" | CLAUDE.md section 0b |
| 2 | The degraded arm is a truncated ledger under `STATE_ROOT` or `TELEMETRY_ROOT`, never an aborted request - the console fetches nothing at runtime at the default window, so an abort arm is a null result | Recorded behaviour |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One combined cost chart | Read time and write time differ by 1.6x per token and are acted on differently; pooling them hides which one moved | Carmack |

---

## 4. Row #3 - The five doubt reasons get a shape

- **Scope:** `band_reason` plotted over time - the share of items carrying each of the five reasons, per day, across the window.
- **Files touched:** `frontend/src/routes/console/model/**`, `frontend/src/lib/console/**`, `frontend/tests/console-model-*.spec.ts`, `docs/concepts/evaluation.md`, `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as row 2.
- **Oracle:** The five drawn series sum to the count of scored items with a reason, per day, re-derived in the spec from `state/scores/`. A stacked series whose parts do not sum to its own total is drawing something else.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **This is the single most actionable eval gap on the project.** The five sentences reach a reader on an item and have never been plotted, so nobody can say which defect dominates or whether a prompt change helped | O34 |
| 2 | The five reasons are drawn apart, never pooled into "doubtful". Pooling is what leaves an operator knowing the count and not the cause | Andre |
| 3 | Plan 07 steers by three of these five, so the panel must exist before the prompt loop has anything to read | Chain order |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A single doubt count | Already on the console, and it is the number that cannot answer any question | Andre |
| 2 | Wait for plan 07 to need it | Then the prompt loop's first run has no baseline to move against | Andre |

---

## 5. Row #4 - Faithfulness and lead coverage join them

- **Scope:** The faithfulness score and lead coverage get panels beside the doubt reasons, so every existing eval instrument reaches the console.
- **Files touched:** as row 3, plus `frontend/src/lib/server/payload.ts` if a new build-time read is needed.
- **Acceptance gates:** as row 2.
- **Oracle:** Every metric name the eval ledger writes appears on exactly one console panel, asserted by comparing the ledger's column set against a declared panel map - so a metric added later fails the test rather than going unnoticed.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every existing eval metric reaches the console, not a chosen few. The instruments exist; only the projection was missing | O11 |
| 2 | No alarm threshold is set here. Every alarm ships in record-only mode until a corpus month exists to set it from - an alarm set on a guess is worse than no alarm | M5, Carmack |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Set thresholds now from the committed window | The window is eight days and the design is about to change the summariser twice. Any threshold set here is wrong by plan 11 | Carmack |

---

## 6. Row #5 - The ceilings are re-recorded by the plan that grew them

- **Scope:** `page_weight.ceilings_bytes` for `/console/`, `/console/model/` and `/console/machine/` re-derived on this plan's tree, with headroom sized in published days.
- **Files touched:** `config/idhazh.json`, `backend/tests/test_contracts.py`, `docs/reference/measurements.md`, `docs/how-to/run-the-gates.md`
- **Acceptance gates:** `bundle-gate` green; the contracts module; the full suite.
- **Oracle:** The recorded ceiling equals the heaviest of at least five builds plus a stated number of published days at the measured per-day rate plus the tolerance, and the arithmetic is printed in the commit so the two terms can be checked to sum.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A ceiling is re-recorded by the change that grows it, not raised reactively when a later PR goes red. A ceiling raised in the PR that broke it is a ceiling nobody is enforcing | Carmack, section 14.1 |
| 2 | The per-day rate is measured by **removing a real mature day** from a copy of every ledger and rebuilding, never by cloning a day - a cloned day reads about 18 percent light because gzip sees a near-copy | Recorded method |
| 3 | Current committed values, verified 2026-09-05: `/console/` 277,195, `/console/machine/` 39,743, `/console/model/` 37,979. **Re-measure before using any of them** | Verified |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Re-baseline all the ceilings up front, before the panels exist | A ceiling recorded on a tree two plans old expires by design; the runway is what goes stale, not the number | Carmack |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-02-retire-the-route-name-plan.md`](20260905-02-retire-the-route-name-plan.md) - the previous plan.
- [`20260905-04-site-cap-defence-plan.md`](20260905-04-site-cap-defence-plan.md) - the next plan.
