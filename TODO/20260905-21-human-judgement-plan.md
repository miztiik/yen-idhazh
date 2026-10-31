# 21 - Human judgement

**Last Updated**: 2026-10-31
**Level**: 2 for row 2 (a bounded report over an existing ledger). Row 4 is not execution-ready.

**Current scope**: No human input. Rows 3, 5 and 6 are abandoned; their original
descriptions below are retained for context, not execution. Row 2 produces
reports from existing measurements, with no new quality judge or ledger.
Row 4 still needs a machine-only design; its original score-weight fitting
depends on human comparisons that will not be collected.

**Chain**: previous [`20260905-20-visual-console-plan.md`](20260905-20-visual-console-plan.md) | next [`20260905-22-distil-and-close-plan.md`](20260905-22-distil-and-close-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O12, O16, O41, rows 64, 65, 66, 67, 68, sections 12.10, 12.13 G34, G38, 12.14 G41, G42, G44, E1, M6.

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Make existing visual-attempt measurements available as noninteractive reports, without human labels or new judgments |
| Hard scope - in | Row 2's read-only CSV report. Row 1 is already delivered; row 4 requires a separate design |
| Hard scope - out | See Table A below |
| ESCALATE triggers | 1. A persisted contract, ledger column or producer changes. 2. A report becomes input to a later pipeline run. 3. A model judgment, human label, publication decision or setting adjustment is added. 4. Row 4 is proposed for execution before its design is settled |
| Chosen strategy | Reuse the registered ledger reader and standard-library CSV writer; add no storage or evaluation machinery |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

**Table A - Scope exclusions**

| ID | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| A1 | Human labels and review modes | No measurement of human preference or comprehension | A separate human-review intent |
| A2 | New model judgments | Reports describe recorded outcomes, not visual usefulness | A defined quality question and a separate evaluation design |
| A3 | New ledgers, columns or committed summaries | Counts are computed when the report runs | A later consumer with a declared persisted contract |
| A4 | Automatic setting changes and publication gates | This report does not correct or tune the system | Row 4's settled measurement target and adjustment design |
| A5 | Console panels | This row produces CSV, not a page | Plan 20's "Refusal reasons and written visual type" outcome |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A place to look at a visual, that never ships with the site | - | A | DONE | p21-1 | #655 | worker |
| 2 | Existing measurements in a machine-written report | - | B | PENDING | - | - | - |
| 3 | Two ways to ask, and the question locked before the verdict | 2 | C | ABANDONED | - | - | - |
| 4 | Weights that cannot quietly get worse | TBD - machine-only design | D | PENDING | - | - | - |
| 5 | Did the reader actually understand it faster | 4 | E | ABANDONED | - | - | - |
| 6 | How this loop knows when it is done | 5 | F | ABANDONED | - | - | - |

---

## 2. Row #1 - A place to look at a visual, that never ships with the site

- **Scope:** `review/` renders - published, rejected, config-B and the `none` setup - produced as a build artifact.
- **Files touched:** `review/**` (gitignored), `backend/utilities/review_queue.py` (new), `.github/workflows/**`, `.gitignore`, `docs/concepts/adaptive-pruning.md` (the register row), `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; the full suite; `shellcheck`; one dispatch producing the artifact; `idhazh site-weight` unchanged.
- **Oracle:** After a build, `review/` exists on the runner and **nothing under `frontend/public/` or `frontend/build/` references it** - asserted by a path scan, because the failure mode is a review surface quietly becoming a published one.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `review/` is a **build artifact**: never committed, never under `frontend/public/`, bounded by the 500 MB artifact ceiling | Row 68, section 9.3 |
| 2 | Three of the source document's mechanisms were written for a **shipped** review surface and are now moot: excluding it from indexing, from sitemaps and from feeds. **Saying so is what stops a plan-doc implementing them** | 12.14 G44 |
| 3 | The reviewer now has to obtain the artifact, and how - artifact download, local build, or a manual dispatch - is this row's call. It was left unstated when the surface moved | 12.14 G44 |
| 4 | Ingestion still needs a source, and the source moved with the surface. A scheduled job validates and appends to the append-only ledger | 12.14 G44 |
| 5 | All four populations are queued: published, rejected, config-B and the `none` setup | Section 12.7 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ship `review/` with the site | Its only argument was that it is the cheapest distribution, and it puts an internal surface on a public origin | Fowler, row 68 |

---

## 3. Row #2 - Existing measurements in a machine-written report

- **Scope:** Read named UTC days from the existing visual-attempt ledger and produce a noninteractive CSV report of recorded outcomes, first validator rejections and requested versus written types.
- **Files touched:**
  - `backend/idhazh/evals/visual_attempt_report.py` (new): read and group the validated records.
  - `backend/utilities/visual_attempt_report.py` (new): parse arguments and emit CSV to stdout.
  - `backend/tests/test_visual_attempt_report.py` (new): bounded generated raw and compact fixtures and the real command.
  - `docs/how-to/report-visual-attempts.md` (new): command, columns and missing-data meaning.
  - `docs/concepts/telemetry.md`: link to the report guide without duplicating its column definitions.
  - `TODO/20260905-21-human-judgement-plan.md`: this row's delivery status.
- **Acceptance gates:** Local: changed-file Ruff and strict mypy, the focused test module and shared selection from `docs/how-to/run-the-gates.md`. CI: full suite on the merge candidate. Record the selected inputs and results; do not repeat unchanged checks.
- **Oracle:** The real command produces identical, correctly counted CSV from equivalent generated raw and compact fixtures, preserving unrecorded types and surfacing incomplete reads without changing source files. This proves recorded-outcome reporting, not visual quality, publication or improvement.

### Table B - Decisions

| ID | Decision | Basis |
| --- | --- | --- |
| B1 | Reuse `visual-design-attempts` and `VisualAttemptRow` unchanged, through `ledger.ledger_files.load_days` with `LedgerReadStatus`. Read only the requested UTC days and retain native settlement rules | `docs/architecture/contracts/ledger-registry.md`; existing contract and reader |
| B2 | Group by the existing dimensions and emit this header: `date,potential_primary,state,rejection_reason,planned_type,rendered_type,attempts`. The last column counts recorded attempts in each group. Sort deterministically; empty cells retain unrecorded values | Native attempt fields; no new measurement |
| B3 | A first validator rejection may accompany a later successful delivery. A written visual file does not prove publication. Do not rename these counts as human keep rates or final rejection rates | `VisualAttemptRow` field descriptions |
| B4 | Require repeatable `--date YYYY-MM-DD` arguments; allow `--state-dir` for an explicitly named local state root, defaulting to the repository's existing state location. Emit CSV to stdout with the standard-library writer; never prompt or fetch | Bounded local inputs; no new dependency |
| B5 | If read status is incomplete, report the problem and refuse CSV output. Dates with no recorded rows are named on stderr, not filled with invented zero counts. If the selection has no rows, refuse with a clear no-records result | Existing reader status; missing evidence is not zero |
| B6 | No persisted contract moves: the CSV is an on-demand report, not committed pipeline state and not input to a later run. Leave human label files, model configuration, ledger registration and producers unchanged | Current report-only scope; section 11 |
| B7 | Ship this complete command, report logic, tests and guide in one behavioral PR. Leave console presentation to Plan 20's "Refusal reasons and written visual type" outcome | One report capability; no duplicate collection or console work |

### Table C - Rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Basis |
| --- | --- | --- | --- | --- |
| C1 | Add source or model columns and a machine-verdict ledger | No new judgment is requested; metadata alone would not create one | A new evaluation implementation, persisted shape, writer and compatibility checks | Report-only scope |
| C2 | Convert native storage to CSV or persist a second summary ledger | The report can read the current records; another store would duplicate them | Storage and lifecycle changes, reader compatibility and additional tests | Existing native persistence |

---

## 4. Row #3 - Two ways to ask, and the question locked before the verdict

**Status**: ABANDONED. No human review modes will be built under this plan.

- **Scope:** Absolute and pairwise review modes behind a mode flag, with answer locking.
- **Files touched:** `review/**`, `backend/utilities/review_queue.py`, `backend/idhazh/contracts/label_row.py`, `schemas/label-row.schema.json`, `backend/tests/**`, `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A reviewer cannot change an earlier answer after committing a later one - asserted against the recorded sequence, not against the interface. **A reviewer who commits to keep first will rationalise every question after it to match.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Both modes ship behind a flag, and `mode` is mandatory on every row - a label whose mode is unknown cannot be pooled with anything | P.6.3.6, row 67 |
| 2 | Pairwise exists because **absolute ratings are unstable across reviewers**, and the fitter needs pairs | P.5.2.3 |
| 3 | **The reviewer is never shown the machine's reasoning.** The existing label flow already hides the machine score for the same reason | Row 65, P.R14 |
| 4 | `visual_id` from plan 19 is what manufactures overlap between reviewers, and **without overlap there is no agreement figure - so by this project's own rule, no keep rate is quotable** | 12.14 G41, Q5 |
| 5 | Every label carries its queue position, so an ordering effect is detectable rather than assumed absent | P.R13 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Absolute only | The fitter needs pairs, and absolute scores drift between reviewers and between sessions | Andre |
| 2 | Let a reviewer revise freely | Then the first answer sets every later one and the extra questions measure nothing | Andre, 12.13 G38 |

---

## 5. Row #4 - Weights that cannot quietly get worse

- **Scope:** The fitter, its four guardrails and its release rule.
- **Files touched:** `backend/utilities/fit_weights.py` (new), `backend/utilities/fit_priors.py` (new), `backend/utilities/select_exemplars.py` (new), `weights.json` / `priors.json` / `exemplars.json`, `backend/idhazh/evals/**`, `config/idhazh.json`, `backend/tests/**`, `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A refit that does **not** improve holdout ranking accuracy is **refused promotion**, asserted by feeding a deliberately worse fit and checking the incumbent survives. And a release moving both version fields together fails.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Four guardrails: hold out 20 percent of pairs; refuse promotion unless holdout ranking accuracy improves; clamp per-refit coefficient movement; keep the previous version for instant rollback. **They are the entire defence against a fitted model quietly getting worse** | 12.13 G34, P.5.2.3 |
| 2 | The release rule: **never change `components_version` and `weight_version` in the same release, or the entire score time series is lost.** Stated twice in the source document and absent from every carrier | 12.13 G34 |
| 3 | **The prior is the opposite of the weights and is the cheap half.** Weights score a finished visual and need about 200 labelled ones. The prior steers which type the planner picks, has a published empirical seed measured in the data range this project's visuals occupy, and **needs no labels at all** | 12.12 G22 |
| 4 | **The prior must be static within a shard.** Rendered into the system prompt once at startup it is free, because the system turn is prefix-cached. Injected per item it changes the prompt per item and destroys the cache reuse the whole two-call design rests on - and nothing else would look wrong | 12.12 G22 |
| 5 | `select_exemplars.py` has two committed consumers and no producer: the worked pair in the summary prompt, and the prompt loop's input. It carries the same static-within-a-shard constraint for the same reason | 12.14 G42 |
| 6 | The quality index stays a **diagnostic**. The fitter produces weights for a diagnostic | 12.7 G9 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Fit without a holdout | Then every refit looks like an improvement | Andre |
| 2 | Defer the prior with the weights | It needs no labels, so it is not blocked by the thing that blocks them, and it is the largest single lever on keep rate | 12.12 G22 |

---

## 6. Row #5 - Did the reader actually understand it faster

**Status**: ABANDONED. No human comprehension study will be built under this plan.

- **Scope:** The timed comprehension setup and its validity conditions.
- **Files touched:** `review/**`, `backend/utilities/review_queue.py`, `backend/idhazh/contracts/label_row.py`, `backend/tests/**`, `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Every question in the setup is derived from the **elements**, and a question derived from the visual is refused by the generator. **A timed setup whose questions are written from the visual measures nothing while still producing a number.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The question is authored from the elements, never from the visual. That is the condition the whole setup rests on | 12.13 G38, P.5.4.3 |
| 2 | It is called **offline paired evaluation**, never A/B testing. That names a mechanism Guardrail #1 forbids, and the numbers would eventually be quoted as if readers produced them | Row 66 |
| 3 | The standing setup is visual against no-visual; a config comparison rides on top | P.D9, P.L16 |
| 4 | The `none` setup carries a **floor above zero** and a frozen window, so it cannot be quietly switched off | P.D10 |
| 5 | `human_visual_gain` gets a home here. It is one of only eight human measures and the one asking whether comprehension materially improved | 12.13 G39 |
| 6 | Evaluation cost is reported separately, with a sample-rate cap enforced inside the shard budget | P.R15 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ask reviewers whether the visual helped | A preference, not comprehension. The whole point of a timed setup is that it measures something the reviewer cannot introspect | Andre |

---

## 7. Row #6 - How this loop knows when it is done

**Status**: ABANDONED. No human-label collection or reviewer phases will be built
under this plan.

- **Scope:** The four-phase operating manual, with an exit criterion per phase.
- **Files touched:** `docs/concepts/evaluation.md`, `backend/utilities/review_queue.py`, `docs/how-to/**`
- **Acceptance gates:** the full suite; the docs cross-link check.
- **Oracle:** Each phase's exit criterion is computable from the committed ledgers, asserted by computing all four over fixtures. A phase whose exit cannot be computed is a phase nobody ever leaves.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Four phases: bootstrap to about 200 stratified labelled visuals; calibrate on pairwise, exiting when holdout accuracy is stable across two refits; automate on a shrinking random sample, exiting on machine-to-human rank correlation; then steady state | 12.13 G38 |
| 2 | **The phases are what make the labelling-capacity risk actionable.** Start labelling in parallel and the rate reveals itself; the phases are what the revealed rate is measured against, and without them there is no exit criterion for any of it | M6, 12.13 G38 |
| 3 | Sampling rate, reviewer count and agreement target come from a reviewer-hours budget, and inter-reviewer agreement is published beside every keep rate or the keep rate is not quotable | Q5 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Label until it feels like enough | Then the loop never exits and the fitter is refit on a moving target for ever | Andre |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-20-visual-console-plan.md`](20260905-20-visual-console-plan.md) - the previous plan.
- [`20260905-22-distil-and-close-plan.md`](20260905-22-distil-and-close-plan.md) - the next plan.
