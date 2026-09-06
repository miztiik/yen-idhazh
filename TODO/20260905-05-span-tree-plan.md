# 05 - Where the time actually goes

**Last Updated**: 2026-09-05
**Level**: 3 (a new committed ledger, a workflow toggle, an operator panel)

**Chain**: previous [`20260905-04-site-cap-defence-plan.md`](20260905-04-site-cap-defence-plan.md) | next [`20260905-06-fewer-better-articles-plan.md`](20260905-06-fewer-better-articles-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O23, O30, O31, section 14.4, 14.4a, 12.13 G36.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Ten span call sites are already instrumented and every one is thrown away, because tracing is off in CI. The question nobody can answer is whether the model is idle for most of a shard - and if it is, more shards is the wrong lever and the whole two-call design is being sized against a fiction |
| Hard scope - in | A per-shard rollup that becomes the committed record; raw traces on a short rolling window so an operator can drill into a recent run; the reconciliation that makes the timing self-checking; switching tracing on; one console panel |
| Hard scope - out | Any new span for a stage that does not exist yet (plans 08 and 11 add their own). Any third-party host - the file sink stays the only sink CI runs. Any change to what a stage computes |
| ESCALATE triggers | 1. The committed rollup would restate a column an existing ledger already holds - that is the fourth-record objection and it is a stop. 2. A span attribute would carry free text, which `telemetry.attribute` and Rule #11 refuse. 3. Turning tracing on costs a shard more than 1 percent of its wall clock |
| Chosen strategy | Build the fold first and flip the switch last. The file sink writes into gitignored `backend/var/`, so tracing on before the fold exists is runner seconds spent writing a file nobody opens |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A rollup that holds only what no ledger holds | - | A | DONE #449 | span-r1 (removed) | #449 | worker |
| 2 | Raw traces, briefly, so a recent run can be opened | 1 | B | DONE #452 | span-r2 (removed) | #452 | worker |
| 3 | Every second of a shard is accounted for | 1 | C | DONE #450 | span-r3 (removed) | #450 | worker |
| 4 | Tracing switches on | 2, 3 | D | DONE #456 | span-r4 (removed) | #456 | worker |
| 5 | Where the time went, drawn | 4 | E | DONE #457 | span-r5 (removed) | #457 | worker |

---

## 2. Row #1 - A rollup that holds only what no ledger holds

- **Scope:** `SpanRollupRow` and the fold that writes one row per `(date, run_id, shard, span_name)` into `state/span-rollup/<YYYY-MM>.csv`.
- **Files touched:** `backend/idhazh/contracts/span_rollup.py` (new), `schemas/span-rollup-row.schema.json` (generated), `backend/idhazh/telemetry.py`, `backend/idhazh/ledger.py`, `state/span-rollup/` (header committed), `.github/scripts/commit-and-push.sh`, `backend/tests/test_telemetry.py`, `backend/tests/test_contracts.py`, `docs/concepts/telemetry.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; `shellcheck`; the full suite.
- **Oracle:** A contract test asserts the rollup's column set is **disjoint, outside the key, from the column set of every committed ledger** - `state/item-health/`, `state/scores/`, `state/runtime-counters.csv` and `state/visuals/` when it exists. Testing against item-health alone is not enough: a collision was already found in a different store by exactly that gap.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Only five spans are committed - `robots`, `tag`, `render_prompt`, `parse_reply`, `item`. Every other duration and every token count is already a column in item-health, and restating one is the fourth record the doctrine refuses | Fowler 2026-08-30, section 14.4a |
| 2 | Stage `state` whole in the commit script, never a new subdirectory - `git add` under `set -euo pipefail` aborts the step in a fresh checkout where the directory does not exist yet | Recorded trap |
| 3 | The committed row is **derived from** the spans, so it is not a second account of the same events | Section 14.4 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Commit the raw spans as the record | A fourth record of one run, free to disagree with the other three | Fowler, `docs/concepts/telemetry.md` |
| 2 | Send spans to a hosted collector | Rule #1, and it collects nothing we do not already hold - the client sends our own span unchanged | Section 14.4 |

---

## 3. Row #2 - Raw traces, briefly, so a recent run can be opened

- **Scope:** Raw spans committed to `state/traces/<YYYY>/<MM>/<DD>-<run>-<shard>.jsonl` on a short rolling window.
- **Files touched:** `backend/idhazh/telemetry.py`, `backend/idhazh/retention.py`, `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `.github/workflows/digest.yml`, `.github/scripts/commit-and-push.sh`, `backend/tests/**`, `docs/concepts/adaptive-pruning.md` or `docs/concepts/telemetry.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; `shellcheck`; the full suite; `idhazh site-weight`.
- **Oracle:** After a simulated run past the window, the oldest trace file is gone and the newest is present, and the directory's total bytes are bounded by the window times the measured per-run size - stated as a number, not as an intent.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A trace is a **lookup**, so by section 9.2's own rule it deletes rather than folds. Folding it would invent a total nobody reads | O31, section 9.2 |
| 2 | Raw traces are evidence with a short life; the rollup is the record. That split is what satisfies the fourth-record objection while still giving an operator something to open | Section 14.4 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep traces only as a CI artifact | Artifacts expire in days and cannot be read from a page | Carmack |
| 2 | Keep them for ever | Unbounded growth against a 1 GB cap plan 04 has just measured | Carmack |

---

## 4. Row #3 - Every second of a shard is accounted for

- **Scope:** `unattributed_ms` on the rollup, plus the assertion that the stage timings sum to the shard's wall clock.
- **Files touched:** `backend/idhazh/contracts/span_rollup.py`, `backend/idhazh/telemetry.py`, `backend/tests/test_telemetry.py`, `docs/concepts/telemetry.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** On a fixture run, the summed stage times plus `unattributed_ms` equal the recorded wall clock exactly. A timing set that does not reconcile is how an invisible cost survives, and an unreconciled set must fail rather than round.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This plan's headline argument is unaccounted shard wall clock, so it must ship the invariant that makes the number self-checking. Building the mechanism and dropping the invariant is gap G36 | 12.13 G36 |
| 2 | The residual is **reported**, never silently absorbed into the nearest stage | Andre |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Report stage times without a residual | Then "nobody knows where the time goes" stays true with more decimal places | Carmack |

---

## 5. Row #4 - Tracing switches on

- **Scope:** `observability.tracing_enabled` becomes `true`; the file sink stays the only sink CI runs.
- **Files touched:** `config/idhazh.json`, `backend/tests/test_telemetry.py` (the two assertions that are about the committed file and must be deselected or re-pointed), `docs/concepts/telemetry.md`, `docs/reference/measurements.md`
- **Acceptance gates:** the full suite in both switch positions; one `workflow_dispatch` of `digest.yml`; `idhazh site-weight`.
- **Oracle:** The live dispatch writes a rollup row per shard per span, **and** the shard's measured wall clock is within 1 percent of the same shard's clock on the previous run. Turning an instrument on must not move the thing it measures.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The flip lands **after** rows 1 to 3, not before. The file sink writes into gitignored `backend/var/`, which dies with the checkout | Section 14.4a |
| 2 | The attribute vocabulary stays closed and the sentinel test keeps running, so turning tracing on makes the Rule #11 guard run in every CI job instead of on a developer's box | Section 14.4 |
| 3 | The flip date is a discontinuity every new panel must name, or a sub-step series starting that day reads as a sudden slowdown | Section 14.4b |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Sample the collection | Measured at 1 part in 128,000 of a shard. There is nothing to save | Carmack |

---

## 6. Row #5 - Where the time went, drawn

- **Scope:** A console panel over the rollup: time per stage per shard, and the unattributed residual beside it.
- **Files touched:** `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/machine/**`, `frontend/tests/console-machine-*.spec.ts`, `config/idhazh.json` (the ceiling this grows), `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; the section 12 smoke including a truncated-ledger arm.
- **Oracle:** The drawn residual is re-derived in the spec from the committed rollup and compared to the drawn attribute, and the panel's named empty state is reached by a rollup truncated to its header.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The residual is drawn beside the stages, not hidden. It is the number the whole plan exists to surface | Carmack |
| 2 | No alarm threshold here. Record-only until a corpus month exists to set one from | M5 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A flame graph | A per-shard aggregate cannot reconstruct nesting, and the raw traces that can are a drill-down, not a page | Carmack |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-04-site-cap-defence-plan.md`](20260905-04-site-cap-defence-plan.md) - the previous plan.
- [`20260905-06-fewer-better-articles-plan.md`](20260905-06-fewer-better-articles-plan.md) - the next plan.
