# 13 - Deletion switched on

**Last Updated**: 2026-09-05
**Level**: 4 (structural: the first configuration in this repository that deletes committed files on a schedule)

**Chain**: previous [`20260905-12-readable-visuals-plan.md`](20260905-12-readable-visuals-plan.md) | next [`20260905-14-sufficiency-bar-plan.md`](20260905-14-sufficiency-bar-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O8, O9, section 9 whole, rows 59, 61, 62, E3, E4.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 04 measured the growth, moved the cap into config and made the cleanup report its backlog - and left the fuse in. This plan takes it out. It sits **here** rather than at the end because the Pages cap is the first budget the group breaches: plan 12 changed the renderer and plans 15 to 18 each add a visual family, so from here the drawings pile up faster than anything removes them |
| Hard scope - in | The adaptive-pruning concept doc and its compliance register, written against deletion that runs; `retention.image_months` given a value derived from plan 04's measurement; `retention.dry_run` set to false; the first real deletion watched |
| Hard scope - out | Any change to what is drawn. Any ledger fold beyond what already exists. Deleting anything that is not a rendered visual - the day payload, the eval ledger and the labels are never deleted by age |
| ESCALATE triggers | 1. A dry run's candidate list contains any path that is not a rendered visual. 2. The candidate count on the first real run exceeds `max_deletes_per_run`, meaning the backlog is larger than one run can clear and the window needs re-deriving before the fuse comes out. 3. The measured rate says the alarm is under 30 published days away - that is an incident, and deletion by age is the wrong instrument for it |
| Chosen strategy | Write the doc against behaviour that runs, set the window, then flip the fuse and watch one real run. **The new renderer must already have shipped**, or flipping the fuse deletes a year of drawings from an engine that has been replaced, with a 200-item cap the only bound |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Age-based deletion is an archive policy, not a cap defence, and this plan does not pretend otherwise.** The defences that act on the cap's timescale are the coverage rate, the per-visual byte cap in plan 14, and the off-bundle base URL plan 04 built. Thirteen months of retention is about published day 395; the console page crosses its own ceiling on published day 16. The two problems only look related.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The rules, and which rule governs every file this project writes | - | A | PENDING | - | - | - |
| 2 | The window takes a value, and nothing is deleted yet | 1 | B | PENDING | - | - | - |
| 3 | The fuse comes out, and one run is watched | 2 | C | PENDING | - | - | - |

---

## 2. Row #1 - The rules, and which rule governs every file this project writes

- **Scope:** `docs/concepts/adaptive-pruning.md`: the five properties, the four policies, the rule that decides which applies, and the register naming every artefact this project writes.
- **Files touched:** `docs/concepts/adaptive-pruning.md` (new), `docs/reference/documentation-structure.md`, `docs/concepts/config.md`, `backend/idhazh/retention.py` (docstrings only)
- **Acceptance gates:** the full suite; a docs cross-link check on every page this one links to.
- **Oracle:** Every directory under `state/`, `corpus/` and `frontend/public/` that this project writes appears in the register exactly once with a named policy - asserted by a test that walks the tree and compares it to the register, so a new store added later fails rather than being forgotten.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The module keeps the name `retention.py`. The **design concept** is documented as adaptive pruning. "Intelligent" claims a property the code does not have when it merely reads a date, and "compaction" is borrowed from log-structured storage where it means something else | O9, section 0b |
| 2 | One rule decides everything: **a ledger folds, an asset deletes, a lookup deletes** | Section 9.2, Q9 |
| 3 | **`observability.keep_months` and `hard_delete_after_months` no longer exist.** Six named per-store windows replaced them, and a config still spelling either old name fails validation. Any sentence naming them is naming nothing | Section 9.2 correction, verified 2026-09-05 |
| 4 | The definition of a ledger narrows to what the folds actually do: **append-only within its window, folding to a durable aggregate, never edited in place at full grain.** The glossary's "never edited in place" was false as written | Section 9.2, 15.4a |
| 5 | `state/labels.csv` is the only ground truth and is **never deleted**. The day payload records that a day happened and is never deleted | Section 9.3 |
| 6 | Sharding is what makes a fold a single-file atomic operation, and an atomic fold is what makes deletion safe enough to enable at all. That relationship is the reason this row precedes row 3 | Section 9.4 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Write this doc in plan 04 | A doc describing a switched-off policy is the stale clutter this repository already deletes on sight | Fowler |
| 2 | A new module rather than widening `retention.py` | It already reasons about all four policies: the alarm, the visual prune, the ledger fold and the lookup prune | Row 59 |

---

## 3. Row #2 - The window takes a value, and nothing is deleted yet

- **Scope:** `retention.image_months` moves from `-1` to a real window derived from plan 04's measurement, with `dry_run` still `true`.
- **Files touched:** `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/tests/test_retention.py`, `docs/concepts/adaptive-pruning.md`, `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch producing a dry-run report.
- **Oracle:** The dry run lists candidates and **every listed path is a rendered visual under a dated directory older than the window** - asserted by pattern over the whole candidate list, with the list's length printed. A dry run that lists nothing proves nothing, so a non-empty list is part of the oracle.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The committed value is `-1`, not 13.** So this is the first time an age window exists at all, not a tightening from one window to another | C20, verified 2026-09-05 |
| 2 | The window is derived from plan 04's measured rate, and the derivation is committed beside the number | Rule #10 |
| 3 | Age only, never size. **A size-triggered prune deletes most on the day the reader has most to read** | Section 9.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Set the window and flip the fuse together | Then the first evidence of what the window selects arrives after the deletion | Fowler |

---

## 4. Row #3 - The fuse comes out, and one run is watched

- **Scope:** `retention.dry_run` becomes `false`; one scheduled run is watched end to end and its numbers recorded.
- **Files touched:** `config/idhazh.json`, `tests/fixtures/contracts/app-config/tuned.json`, `docs/concepts/adaptive-pruning.md`, `docs/reference/measurements.md`
- **Acceptance gates:** the full suite; one dispatch; `idhazh site-weight` before and after; `idhazh validate-days`.
- **Oracle:** After the run, **every published day still validates and every item that names a visual still has one** - the existing published-assets test, run over the whole corpus. Deletion that orphans a reference is the failure this row exists to avoid, and the site-size delta is the evidence it did something.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This lands **after** the new renderer. Flipping the fuse while the old drawings are the only assets on disk deletes a year of visuals with `max_deletes_per_run: 200` the only bound | Row 61, O8 |
| 2 | It lands **here** rather than at the end of the group, because the Pages cap is the first budget the chain breaches and every plan from 15 to 18 adds a family of drawings | Carmack, 2026-09-05 |
| 3 | `skipped_by_fuse` is watched, not `deleted`. `deleted` is capped at 200, so it reads the same on a healthy run and a runaway one | Row 62 |
| 4 | Both figures are re-measured after the run and written into `docs/reference/measurements.md` with the date and the corpus they were taken over | Rule #10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave `dry_run` true indefinitely | Then the whole retention subsystem is a report nobody acts on, and the cap arrives anyway | Carmack |
| 2 | Raise `max_deletes_per_run` to clear the backlog in one run | The fuse exists so that an off-by-one in a date parse cannot eat the archive. Clearing a backlog over several runs is the fuse working | Carmack |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-12-readable-visuals-plan.md`](20260905-12-readable-visuals-plan.md) - the previous plan.
- [`20260905-14-sufficiency-bar-plan.md`](20260905-14-sufficiency-bar-plan.md) - the next plan.
- [`20260905-04-site-cap-defence-plan.md`](20260905-04-site-cap-defence-plan.md) - where the measurement and the reporting were built.
