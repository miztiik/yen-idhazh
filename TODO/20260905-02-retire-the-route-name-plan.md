# 02 - "Route" leaves the repository

**Last Updated**: 2026-09-05
**Level**: 5 (persisted contracts: a schema stem, config keys, and an enum value that reaches published run manifests). **Owner sign-off is on record** - pseudo-plan O44, user instruction 2026-09-05: "this is a major breaking change accepted, the 'route' verb is completely incorrect, having it in the repo will cause technical debt. lets pay it early."

**Chain**: previous [`20260905-01-visible-chart-plan.md`](20260905-01-visible-chart-plan.md) | next [`20260905-03-console-backfill-plan.md`](20260905-03-console-backfill-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O2, O44, X4, C1, row 63, section 15.4a.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | "Route" names a dispatch decision. The thing it names is a planning decision. Every plan after this one writes new code, and each would write the wrong name and later pay a rename tax on code it had just written. Paying it now costs one mechanical pass; paying it later costs it twenty times |
| Hard scope - in | Every identifier: module, class, function, enum member, contract stem, schema file, config key, CLI verb, workflow job, prompt filename, test name, doc prose. Deleting the dead spec format and the Mermaid round trip that travel with it |
| Hard scope - out | **Any behaviour change at all.** No new field, no new logic, no retirement of the small model (plan 11 owns that), no change to what any stage computes. If a diff changes an output byte other than a name, it is out of scope |
| ESCALATE triggers | 1. A committed run manifest, digest payload or ledger row carries `route` as a **value** that a rename would invalidate. 2. `VisualKind.IMAGE` turns out to be used by a committed day. 3. The old config key cannot be accepted alongside the new one without a second config reader |
| Chosen strategy | Structural-only commits, never sharing a commit with behaviour (Beck's two hats, Fowler 2026-09-05). Rename the Python; keep every **wire value** that reaches a committed artifact |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**The rule that governs every row.** A **name** in code may change freely. A **value** written into a committed file may not, unless this plan also ships the read side that accepts both. Rows 1 and 3 exist entirely because of that distinction.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The config keys move, and the old ones still open | - | A | DONE #411 | yi-r01 | #411 | Fowler, Carmack - agent files read directly |
| 2 | The module and the contract take their real names | 1 | B | DONE #412 | yi-r02 | #412 | Fowler - agent file read directly |
| 3 | The stage keeps its wire value and loses its wrong name | 2 | C | DONE #413 | yi-r03 | #413 | Fowler - agent file read directly |
| 4 | The workflow job says what it does | 3 | D | PENDING | - | - | - |
| 5 | The dead spec format and the Mermaid round trip go | 2 | D | PENDING | - | - | - |
| 6 | The word leaves the prose | 4, 5 | E | PENDING | - | - | - |

---

## 2. Row #1 - The config keys move, and the old ones still open

- **Scope:** `models.route`, `run.route_budget_minutes` and the `finetune.student` value rename, with a read side that accepts the old key for one release.
- **Files touched:**
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json` (generated)
  - `tests/fixtures/contracts/app-config/tuned.json`
  - `frontend/src/lib/server/config.ts` (the TypeScript mirror)
  - `backend/tests/test_contracts.py`
  - `docs/concepts/config.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; `python -m idhazh.contracts.export` then `git diff --exit-code -- schemas/`; contracts and config test modules; the full suite in CI.
- **Oracle:** A config file spelling the **old** key loads and produces the same settings object as one spelling the new key - asserted by loading both and comparing the model, not by reading the code. And `git grep -n 'route' -- config/` returns nothing.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `config/` is a persisted surface, so a key rename is breaking and needs a schema stamp, a changelog entry and a read side accepting the old key - the thing X4 missed | Fowler, 2026-09-05; CLAUDE.md section 11 |
| 2 | `models.route` is **renamed, not deleted.** It still holds the small model, and deleting it here would leave nothing drafting a visual until plan 11 lands - a reader-visible regression for nine plans | Carmack, 2026-09-05 |
| 3 | The new identifier matches the module (`visual_planner.py`), carries no model size, vendor or revision, and takes the proposal's glossary term where one exists | O2, O38, section 15.4a |
| 4 | `run.route_budget_minutes` is renamed here and **re-derived or deleted in plan 11**, which is what folds the job into `work` and invalidates the number | Row 69 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rename the key with no old-key read side | A config written before the release stops loading, which is a release blocker under section 11 | Fowler |
| 2 | Leave `models.route` alone because plan 11 deletes it | Nine plans would write against a key named for the wrong thing, which is the debt this plan exists to clear | Owner, O44 |
| 3 | Keep the old key for ever | A permanent alias is a second source of truth for one setting | Fowler |

---

## 3. Row #2 - The module and the contract take their real names

- **Scope:** `backend/idhazh/route.py` becomes `visual_planner.py`; `backend/idhazh/contracts/route.py` takes the new stem; `schemas/route.schema.json` is regenerated under the new name with the old stem recorded in the new contract's first changelog entry.
- **Files touched:**
  - `backend/idhazh/route.py` -> `backend/idhazh/visual_planner.py`
  - `backend/idhazh/contracts/route.py` -> the new stem
  - `schemas/route.schema.json` -> the new stem (generated)
  - `backend/idhazh/cli.py` and every importer
  - `backend/tests/test_route.py` -> the new name
  - `tests/fixtures/contracts/route/*` -> the new stem
  - `docs/architecture/**` pages naming the module
- **Acceptance gates:** `ruff`; `mypy --strict`; `python -m idhazh.contracts.export` then `git diff --exit-code -- schemas/`; the full suite in CI; `python -m idhazh --help` still lists every verb.
- **Oracle:** `git grep -nc 'route' -- backend/idhazh/ schemas/` returns zero **outside** the wire values row 3 protects, and the pipeline runs end to end on the canary corpus producing a byte-identical digest payload to the base tree. **Byte identity is the whole proof that this row changed no behaviour.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **No read-side payload migration is needed.** `*.route.json` is written under `backend/var/`, which is gitignored, so no past run's payload is read by a later build. What is committed is `DigestVisual`, which carries no `spec` | X4 as corrected 2026-09-04; Fowler 2026-09-05 |
| 2 | The old stem is recorded in the new contract's first changelog entry, so a reader of the schema can find what it used to be called | CLAUDE.md section 11 |
| 3 | `RouteDraft` and `ChartPoint` are unversioned - they live in the module, not in `contracts/` - so they rename freely | C1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep `schemas/route.schema.json` as a deprecated copy | Nothing reads it; a generated artifact kept for sentiment is drift waiting to happen | Fowler |
| 2 | Write a read-side migration for `Route` payloads | There are no committed `Route` payloads to migrate. Building the migration would be inventing work | Fowler |

---

## 4. Row #3 - The stage keeps its wire value and loses its wrong name

- **Scope:** `StageName.ROUTE` renames in Python; the **string it serialises to stays `"route"`**, so every committed run manifest still validates.
- **Files touched:**
  - `backend/idhazh/contracts/run_manifest.py`
  - `schemas/run-manifest.schema.json` (generated)
  - `backend/idhazh/assemble.py` and every producer
  - `frontend/src/lib/server/payload.ts` if it reads the value
  - `backend/tests/test_contracts.py`, `backend/tests/test_assemble.py`
  - `docs/architecture/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a load of **every committed `run.json`** through the new model.
- **Oracle:** Every `run.json` under `frontend/public/digest/` parses through the new contract with no error, **and** the count of manifests carrying the stage is unchanged from the base tree. A rename that broke the wire value would drop that count to zero, which is the failure this row exists to prevent.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Run manifests are **published**, so the serialised value is frozen even though the Python member is not. The member renames; `"route"` stays on the wire | Fowler, 2026-09-05 - the second break X4 missed |
| 2 | The same test applies to `items_routed` and `route_ms` if they reach a committed manifest: rename the Python, keep the key | Fowler |
| 3 | The wire value is revisited only when a plan migrates every committed manifest, which is not this plan and may never be worth it | Fowler |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rename the wire value and migrate every committed manifest | A migration over every published day to change a string no reader sees, against a real risk of dropping a run from the record | Fowler |
| 2 | Leave the Python member named `ROUTE` too | Then the enum a developer reads still teaches the wrong word, which is the debt | Owner, O44 |

---

## 5. Row #4 - The workflow job says what it does

- **Scope:** The `route` job in `digest.yml` renames, along with its artifact names, its step names and the outputs downstream jobs read.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `.github/workflows/*.yml` naming the job or its artifacts
  - `backend/tests/test_workflows.py`
  - `docs/reference/github-actions.md`
- **Acceptance gates:** `shellcheck` on `.github/scripts/`; `backend/tests/test_workflows.py`; the full suite; one `workflow_dispatch` of `digest.yml` completing with the renamed job.
- **Oracle:** A live dispatch reaches `assemble` with the renamed job's outputs consumed - the job graph is only proved by running it, and `test_workflows.py` proves the shape but not the wiring.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The job is renamed, not removed. Plan 11 removes it when the second call replaces what it does | Carmack |
| 2 | `test_workflows.py` holds closed-world sets keyed by job name; each must be updated in the same commit or the rename passes every targeted gate and fails only the full suite | Recorded trap, agent-notes |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rename the job when plan 11 deletes it | Nine plans of workflow edits against a job named for the wrong thing | Owner, O44 |

---

## 6. Row #5 - The dead spec format and the Mermaid round trip go

- **Scope:** Delete `SpecFormat` whole, the `spec` field it types, `backend/idhazh/render/diagram.py`, and `VisualKind.IMAGE` if nothing committed uses it.
- **Files touched:**
  - `backend/idhazh/render/diagram.py` (deleted)
  - the renamed contract module (the `spec` and `spec_format` fields)
  - `backend/idhazh/contracts/digest_day.py` (`VisualKind`)
  - `schemas/*.schema.json` (generated - `VisualKind` is inlined by more than one)
  - `tests/fixtures/contracts/**` carrying the deleted keys
  - `backend/tests/test_render.py`, `backend/tests/test_route.py`
  - `docs/architecture/publishing/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `idhazh validate-days`.
- **Oracle:** **Before deleting `VisualKind.IMAGE`, a scan over every committed `digest.json` returns zero items carrying it** - printed as a count, with the count of days scanned beside it, so a zero cannot come from scanning nothing. Deletion proceeds only on that evidence.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The portability the Mermaid text was written for is worth zero: it lands in gitignored `backend/var/`, the artifact expires after a day, and the committed `DigestVisual` carries no `spec`. It is unreachable 24 hours after a run | Row 63 |
| 2 | The round trip loses data anyway - `parse_mermaid` discards edges, so order comes from a sort and two different graphs draw identically | Row 63 |
| 3 | Plan 10's `VisualPlan` carries nodes and edges natively, so serialising to `flowchart TD` and regexing it back would end with less than it began | Row 63 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the Mermaid emitter for a future exporter | Nothing reads it, it loses edges, and plan 10 needs structure it cannot express | Fowler, Carmack, Editor |
| 2 | Delete `VisualKind.IMAGE` without the scan | An enum member removed from a committed contract breaks every payload that used it, and nobody has counted | Fowler |

---

## 7. Row #6 - The word leaves the prose

- **Scope:** Every remaining occurrence in `docs/`, `README.md`, `AGENTS.md`, code comments, docstrings and test names, and the pseudo-plan's own section 15 index updated to name this group.
- **Files touched:**
  - `docs/**`
  - `README.md`, `AGENTS.md`
  - `TODO/20260902-visual-planner-pseudo-plan.md`
- **Acceptance gates:** `backend/tests/test_contracts.py` (the ASCII and LF check); a repo-wide link check on any heading this row renames; the full suite.
- **Oracle:** `git grep -in 'route'` over the whole tree returns only: the wire values row 3 protects, the changelog entries recording the old names, and ordinary English uses of the word ("en route" is not this domain). Every hit is enumerated in the PR body with a one-line reason - **a grep that returns nothing is not the goal; a grep whose every hit is explained is.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Renaming a `###` heading in `docs/` needs a repo-wide anchor check in the same commit | Recorded trap, agent-notes |
| 2 | The pseudo-plan's section 15 (the 13 plan-docs A to M) is superseded by this numbered group and is replaced with the index, so no reader executes the retired shape | Owner, 2026-09-05 |
| 3 | **The canonical glossary binds identifiers, never prose.** A module, class, contract field, telemetry value, config key or schema stem takes the glossary term verbatim; a plan-doc's sentences keep the plain register. This row is where that rule is written into `docs/`, because twenty more plans are about to mint names against it | O39, section 15.4a |
| 4 | Two names outrank the glossary and are recorded rather than re-litigated: `visual_planner.py`, because O2 names the file and the glossary names no file; and `density_floor`, because the owner rejected the glossary's term outright | Section 15.4a |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave the docs and rename only the code | The docs are the memory. Code and docs disagreeing about a name is worse than either name alone | CLAUDE.md Rule #4 |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-01-visible-chart-plan.md`](20260905-01-visible-chart-plan.md) - the previous plan.
- [`20260905-03-console-backfill-plan.md`](20260905-03-console-backfill-plan.md) - the next plan.
