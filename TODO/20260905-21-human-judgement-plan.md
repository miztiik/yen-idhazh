# 21 - Human judgement

**Last Updated**: 2026-09-05
**Level**: 4 (a new review surface, a persisted label contract, and the fitting machinery whose guardrails are its whole defence)

**Chain**: previous [`20260905-20-visual-console-plan.md`](20260905-20-visual-console-plan.md) | next [`20260905-22-distil-and-close-plan.md`](20260905-22-distil-and-close-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O12, O16, O41, rows 64, 65, 66, 67, 68, sections 12.10, 12.13 G34, G38, 12.14 G41, G42, G44, E1, M6.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Every gate in the group is machine judgement, and nothing has checked the machine against a person. This is the ground truth: whether a visual a human would keep is the visual the machine kept. It **gates nothing** - no publish decision reads a label - and that is deliberate |
| Hard scope - in | The review harness as a build artifact; `label_source` and `model_id` on the label contract; absolute and pairwise review modes; weight fitting with its four guardrails and its release rule; the timed comprehension arm with its validity conditions; the four-phase operating manual |
| Hard scope - out | Any label feeding a publish decision. Pooling machine verdicts with human ones. Summary faithfulness labelling by a model - that stays human-only. Shipping `review/` with the site |
| ESCALATE triggers | 1. A label reaches a publish gate. 2. Machine and human verdicts land in one ledger. 3. Weight fitting is proposed without all four guardrails - **a fitter without them is a number that moves every month with no way to separate improvement from noise.** 4. `components_version` and `weight_version` would move in the same release |
| Chosen strategy | Build the surface, then the contract that keeps machine and human apart, then the modes, then the fitting - each with the guardrail that makes it honest rather than merely present |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**The risk this plan carries and does not hide.** As of the source document's own measurement, **0 of 60 drawn rows carried a human label.** Two advisors proposed deferring the fitter, the pairwise page and the timed arm on exactly that ground and were overruled on scope. The labelling capacity is therefore the standing risk, and the four-phase manual in row 6 is what makes it visible rather than discovered late.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A place to look at a visual, that never ships with the site | - | A | PENDING | - | - | - |
| 2 | A machine verdict and a human one, never in the same column | 1 | B | PENDING | - | - | - |
| 3 | Two ways to ask, and the question locked before the verdict | 2 | C | PENDING | - | - | - |
| 4 | Weights that cannot quietly get worse | 3 | D | PENDING | - | - | - |
| 5 | Did the reader actually understand it faster | 4 | E | PENDING | - | - | - |
| 6 | How this loop knows when it is done | 5 | F | PENDING | - | - | - |

---

## 2. Row #1 - A place to look at a visual, that never ships with the site

- **Scope:** `review/` renders - published, rejected, config-B and the `none` arm - produced as a build artifact.
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
| 5 | All four populations are queued: published, rejected, config-B and the `none` arm | Section 12.7 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ship `review/` with the site | Its only argument was that it is the cheapest distribution, and it puts an internal surface on a public origin | Fowler, row 68 |

---

## 3. Row #2 - A machine verdict and a human one, never in the same column

- **Scope:** `label_source` and `model_id` on the label contract, plus a separate ledger for machine verdicts.
- **Files touched:** `backend/idhazh/contracts/label_row.py`, `schemas/label-row.schema.json`, `state/labels.csv` (header committed), a machine-verdict ledger and its schema, `tests/fixtures/contracts/label-row/*.json`, `backend/idhazh/evals/labels.py`, `backend/tests/**`, `CLAUDE.md` (section 0a amendment), `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** **All four guardrails asserted separately.** A machine row without `label_source` fails; a machine row in the human ledger fails; a keep rate computed over pooled rows fails; and no publish gate reads either ledger, asserted by a call-graph check. **Implementing three of the four silently creates the deviation the compliance audit says does not exist.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A model may grade a finished visual, and that is not a deviation** - a quality verdict reaches no reader and selects nothing to publish. The four guardrails are the ruling, not a recommendation: this plan merges with all four or it does not merge | O41, E1 |
| 2 | This is **not** the same act as a model assigning what a number means. That is Deviation A, accepted as permanent. The two share the word "label" and nothing else | O41 |
| 3 | Summary faithfulness labelling stays **human-only** | O41, E1 |
| 4 | `LabelRow` lives in `backend/idhazh/contracts/label_row.py` and carries **neither** field today, so both are new fields on a persisted contract - a schema stamp, a changelog entry and a fixture round trip each | C22, verified 2026-09-05 |
| 5 | `state/labels.csv` is **never deleted** by any retention policy. It is the only ground truth | Section 9.3 |
| 6 | `CLAUDE.md` section 0a is amended in the same commit, narrowly | O12, E1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One ledger with a flag | A flag is dropped by the first join somebody writes in a hurry, and then the ground truth is contaminated with no way to separate it again | Fowler |
| 2 | No machine verdicts at all | Then the queue is bounded by human hours from day one, which is the risk M6 already names | Owner, O12 |

---

## 4. Row #3 - Two ways to ask, and the question locked before the verdict

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

- **Scope:** The timed comprehension arm and its validity conditions.
- **Files touched:** `review/**`, `backend/utilities/review_queue.py`, `backend/idhazh/contracts/label_row.py`, `backend/tests/**`, `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Every question in the arm is derived from the **elements**, and a question derived from the visual is refused by the generator. **A timed arm whose questions are written from the visual measures nothing while still producing a number.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The question is authored from the elements, never from the visual. That is the condition the whole arm rests on | 12.13 G38, P.5.4.3 |
| 2 | It is called **offline paired evaluation**, never A/B testing. That names a mechanism Rule #1 forbids, and the numbers would eventually be quoted as if readers produced them | Row 66 |
| 3 | The standing arm is visual against no-visual; a config comparison rides on top | P.D9, P.L16 |
| 4 | The `none` arm carries a **floor above zero** and a frozen window, so it cannot be quietly switched off | P.D10 |
| 5 | `human_visual_gain` gets a home here. It is one of only eight human measures and the one asking whether comprehension materially improved | 12.13 G39 |
| 6 | Evaluation cost is reported separately, with a sample-rate cap enforced inside the shard budget | P.R15 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ask reviewers whether the visual helped | A preference, not comprehension. The whole point of a timed arm is that it measures something the reviewer cannot introspect | Andre |

---

## 7. Row #6 - How this loop knows when it is done

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
