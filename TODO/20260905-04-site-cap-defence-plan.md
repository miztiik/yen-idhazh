# 04 - The site cannot fill up

**Last Updated**: 2026-09-05
**Level**: 3 (a config move, a measurement that four decisions rest on, and a release valve)

**Chain**: previous [`20260905-03-console-backfill-plan.md`](20260905-03-console-backfill-plan.md) | next [`20260905-05-span-tree-plan.md`](20260905-05-span-tree-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O7, O9, O14, section 6, section 9, section 13 (M2, M10), E3, E4, rows 60 and 62.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The published site has a 1 GB hard cap and **nobody knows how fast it is filling.** The two available readings differ by 18 times - 172 days of headroom, or 9.6. Every plan after this one adds drawings to the site. If the pessimistic reading holds and nothing changes, the deploy fails and the digest stops publishing entirely |
| Hard scope - in | Measuring the real growth rate and the repository's own growth; moving the hard cap into config bounded so it can only be lowered; a config-driven asset base URL as the release valve; making the cleanup report the backlog it did not clear |
| Hard scope - out | **Switching deletion on.** `retention.dry_run` stays `true` and `image_months` stays `-1` until plan 13, which lands after the new renderer. Flipping the delete fuse while the old drawings are the only assets on disk deletes a year of visuals with a 200-item cap the only bound |
| ESCALATE triggers | 1. The measured rate says the 800 MB alarm is under 30 published days away - that is a live incident, not a plan row. 2. Serving assets off the bundle needs a runtime call to anything that executes our logic (Rule #1). 3. `PAGES_HARD_CAP_MB` cannot be bounded in config such that a config edit can lower it and never raise it |
| Chosen strategy | Measure first, then build the valve, then leave the fuse alone. Age-based retention is an archive policy and not a cap defence; the defences that act on the right timescale are the coverage rate, the per-visual byte cap and moving bytes off the bundle | 
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | How fast is it actually filling | - | A | PENDING | - | - | - |
| 2 | The cap moves into config and can only be lowered | 1 | B | PENDING | - | - | - |
| 3 | A way to put bytes somewhere else | 1 | C | PENDING | - | - | - |
| 4 | The cleanup says what it did not clear | 2 | D | PENDING | - | - | - |

---

## 2. Row #1 - How fast is it actually filling

- **Scope:** Difference the site measurement across two committed dates to get one growth rate, and difference the repository pack size across the same two commits.
- **Files touched:**
  - `docs/reference/measurements.md`
  - `backend/idhazh/retention.py` (only if the measurement exposes a defect in what it counts)
- **Acceptance gates:** `ruff`; `mypy --strict`; the retention test module; the full suite if any code moved.
- **Oracle:** The recorded figure names the **built bundle** bytes and the **payload tree** bytes separately, with the item count taken from the **same tree** as the bytes, and a per-item rate beside the per-day rate. Two independent methods must land inside 10 percent of each other, or neither is recorded.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The two trees are 18 times apart and one cannot stand in for the other. A rate that pairs a byte total from one tree with a count from another is the defect this project has already shipped once | Section 16.6 |
| 2 | The **per-item** rate is the stable unit. Across seven measured days the per-day rate moved by a factor of six while the per-item rate held inside 15 percent | Section 16.6 |
| 3 | A level is not a rate, and only a rate answers "when". Two dates, differenced | Carmack |
| 4 | Repository pack growth rides along free and answers a different question: the prune bounds the past, and nothing bounds a growing present | M10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Extrapolate from the single committed reading | It is the reading that is 18x uncertain. Extrapolating it is how a "694 MB a year" figure came out 12x wrong once already | Carmack |
| 2 | Clone a day to synthesise growth | A cloned day reads 18 to 26 percent light, because gzip sees a near-copy of a block it already holds | Recorded method |

---

## 3. Row #2 - The cap moves into config and can only be lowered

- **Scope:** `PAGES_HARD_CAP_MB` moves from a module constant into `config/idhazh.json` under a bound that permits lowering and refuses raising.
- **Files touched:**
  - `backend/idhazh/retention.py`
  - `backend/idhazh/contracts/app_config.py`
  - `config/idhazh.json`
  - `schemas/app-config.schema.json` (generated)
  - `tests/fixtures/contracts/app-config/tuned.json`
  - `backend/tests/test_retention.py`, `backend/tests/test_contracts.py`
  - `docs/concepts/config.md`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A config setting the cap **above** 1024 fails validation with a message naming the bound; a config setting it below loads and the alarm fires earlier. Both arms asserted, because a bound only tested in the permitted direction is not a bound.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Bounded `le=1024` so config can lower it and never raise it. Rule #2's "the budget is the platform, not a preference" stays enforceable through the config file rather than by hoping nobody edits a constant | O7, rows 60 |
| 2 | The 800 MB alarm and the 1024 MB cap are different instruments and stay apart. One reports, one stops the deploy | Section 9.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave it a `Final` in code | A knob every operator wants to read should not need a source read, and the bound is what makes exposing it safe | Fowler |
| 2 | Make it a plain config number with no bound | Then the first tight release raises the cap, which is the failure Rule #2 names | Carmack |

---

## 4. Row #3 - A way to put bytes somewhere else

- **Scope:** `visuals.asset_base_url` in config, defaulting to same-origin, so drawings can be served from outside the published bundle without a code change.
- **Files touched:**
  - `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`
  - `frontend/src/lib/server/config.ts`
  - `frontend/src/lib/components/ItemVisual.svelte`
  - `tests/fixtures/contracts/app-config/tuned.json`
  - `frontend/tests/item-visual.spec.ts`
  - `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; the section 12 smoke; backend contract gates.
- **Oracle:** With the base URL left at its default, the built page is **byte-identical** to the base tree - a release valve that changes the default output is not a valve, it is a change.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The valve is built now and left shut. It exists so that if the measurement turns bad there is a config edit rather than a project | O14, E3 |
| 2 | Measured 2026-09-02: the candidate host serves `image/svg+xml` with a permissive cross-origin header, so an `img` carrier works. **It caches for five minutes**, so a repeat reader refetches - a real cost on a slow connection | Section 6 |
| 3 | **An SVG served off-origin through `img` cannot be themed**, so the valve and plan 01's themed carrier are mutually exclusive for any item that uses it. The valve is for the archive tail, never the seed | Section 6.1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Point it off-origin now | Nothing yet says the bytes must move, and it would cost every reader a refetch every five minutes | Carmack |
| 2 | Skip the valve and rely on deletion | Age-based retention is an archive policy acting on a yearly timescale. The cap is a monthly problem | E4 |

---

## 5. Row #4 - The cleanup says what it did not clear

- **Scope:** The cleanup run records `candidates_found`, `deleted`, `skipped_by_fuse`, `fuse_tripped`, `cutoff_date`, `oldest_kept`, `bytes_reclaimed`, the site size before and after, `dry_run` and the policy.
- **Files touched:**
  - `backend/idhazh/retention.py`
  - a contract for the cleanup row plus its generated schema
  - `state/` (the new ledger, header committed)
  - `.github/workflows/digest.yml` and `.github/scripts/commit-and-push.sh` (staging)
  - `backend/tests/test_retention.py`, `backend/tests/test_workflows.py`
  - `docs/concepts/adaptive-pruning.md` (new, or its stub)
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; `shellcheck`; the full suite; one dispatch of the workflow writing a row.
- **Oracle:** On a fixture backlog deliberately larger than `max_deletes_per_run`, the run reports `deleted` at the cap **and** `skipped_by_fuse` non-zero. `deleted` alone is capped at 200, so `deleted` can never show whether the backlog is shrinking - only the pair can.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `skipped_by_fuse` is the field that matters and it is the one nobody would have added, because `deleted` looks like the answer | Row 62 |
| 2 | Stage `state` whole in the commit script, never a new subdirectory - `git add` under `set -euo pipefail` aborts the whole step in a fresh checkout when a named directory does not exist yet | Recorded trap |
| 3 | Ship the new ledger with its header committed, for the same reason | Recorded trap |
| 4 | `observability.keep_months` and `hard_delete_after_months` **no longer exist**; six named per-store windows replaced them. Any row naming the old knobs is naming nothing | Section 9.2 correction, verified 2026-09-05 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Report only what was deleted | Capped at 200 by the fuse, so it is the same number on a healthy run and a runaway one | Carmack |
| 2 | Write the pruning concept doc here | It is written against deletion that runs, and deletion does not run until plan 13. A doc describing a switched-off policy is the stale clutter this repo already deletes | Fowler |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-03-console-backfill-plan.md`](20260905-03-console-backfill-plan.md) - the previous plan.
- [`20260905-05-span-tree-plan.md`](20260905-05-span-tree-plan.md) - the next plan.
- [`20260905-13-switch-on-deletion-plan.md`](20260905-13-switch-on-deletion-plan.md) - where `dry_run` becomes false.
