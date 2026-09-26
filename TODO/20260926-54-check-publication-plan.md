# Plan 54 - Check-publication: a discovered validation framework, the day-validation decommission, and the run-yield chart

**Last Updated**: 2026-09-26

**Level**: 5 for the decision; per PR-group 3, except D1 (the receipt decommission) which is 5 - it removes a persisted contract and deletes a committed tree (CLAUDE.md section 6).

Execute per docs/how-to/execute-a-plan.md as a **workpool**: a group is ready when its `Depends-on` (intra- and cross-plan) are DONE and its files are disjoint from every in-flight group; **Parallel N = 2** (section 1). Cross-plan dependencies name a plan-53 row by TITLE, never number. AUTO-merge on green gates. Honour the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

**Chain** (CLAUDE.md section 0d). **Intent**: a run validates everything it published through one discovered, extensible gate; keeps no write-only receipt; proves the gate's ledger hook with live, un-mocked code; and the console shows delivered-against-planned per day instead of one window-wide ratio. **Contract**: section 4 declares every type, signature, body and destination a worker must not invent. **Code**: the four PR-groups.

| Field | Value |
| --- | --- |
| Why this plan exists | `validate-days` bundles five checks and a write-only byte-count receipt under a name that describes one of them, and the console's run-health donut collapses a month into one ~83% ratio blind to any single day. This renames it `check-publication` as a discovered plugin framework, decommissions the day-validation receipt (which also fixes a live double-prune-claim), proves the plugin ledger hook with one integration test, and replaces the donut with a per-date delivered-vs-planned chart read from `day_metrics`. |
| Hard scope - in | see the bullets below |
| Hard scope - out | see the table below |
| ESCALATE triggers | see the enumerated list below |
| Chosen strategy | Decommission the receipt early and delete-only (unblocks nothing it must wait for); rename to a discovered framework once `LedgerName` exists; draw the chart from already-published `day_metrics`. No new ledger. Ruled by Fowler (architecture, sequencing), Susan (the chart), Carmack (the sweep cost); owner decisions dated 2026-09-26. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md, as a workpool. **Parallel N = 2** - D1 (backend) and D3 (frontend) are file-disjoint; D2 is single-threaded behind plan 53's `LedgerName` row and D1. Most of the calendar is the wait for that row, not plan-54 fan-out. |
| Blocks / blocked-by | **Blocked-by** plan 53 rows, by title: D1 lands **after** "`ledger.py` becomes the package, and its docstring becomes a page" (do not race its open PR) and **before** "The ledger registry moves to `config/ledgers.json`"; D2 lands **after** "One `LedgerName` for one ledger". **De-risks** plan 50's row "The payload ledger, the two roots, and the arrow mapping" by keeping it purely additive (section 2), but does not unblock it. |

### Hard scope - in

- `backend/idhazh/stages/validate_days.py` becomes the discovered package `backend/idhazh/publication_checks/`: a registry, a runner, and each check a plugin under `checks/`.
- The verb `validate-days` becomes `check-publication` in `cli.py` and its three workflow callers, atomically.
- The standalone day-shape check is removed; the runner's per-day `DigestDay` parse is the writer-independent guarantee (section 4.2).
- The census check is renamed `planned-items-reconciliation` and stays **fault-only** - it reads the day payload and persists nothing (no ledger).
- The `Check.ledger` hook ships live and is proven by one un-mocked integration test (owner B2, 2026-09-26). No production check declares a ledger.
- The day-validation receipt is decommissioned end to end, which also removes the live double-prune-claim (section 2).
- The console's run-health donut is replaced by a per-date planned/published/failed + yield chart read from `day_metrics` (section 4.6).

### Hard scope - out

| Not here | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| A `planned-items-reconciliation` ledger | Nothing - `day_metrics` already persists `items_planned`/`items_published`/`items_failed` per day, committed and console-read; a ledger would be a second writer of the same three numbers | A check that must persist a fact `day_metrics` does not hold |
| The truncation-rate and scoring-coverage charts (Fowler's B2/B3) | Two real per-date trends the console does not draw | Their own Model-page item - Susan ruled them off the run-health glance (they are content-quality and eval-coverage questions, not run health) |
| Re-pointing existing panels (bands, sources, timings) off their growing ledger walks onto `day_metrics` | Those panels keep reading growing walks (Guardrail #12) | Its own bounded-read refactor item; it draws nothing new |
| Hardening `backfill_vectors`' `model_copy(update=...)` to a validated construction | A backfilled day is validated at publication by the runner parse rather than at the write | Its own one-line pull request |
| Bounding the committed digest tree | The full-sweep re-parse grows one day a day (documented Guardrail #12 read, section 4.7); measured to fit the 6 h job with 35-100x margin | A separate retention design |

### ESCALATE triggers

1. **D1 begins** - a persisted contract is removed and a committed tree is deleted (Level 5). Pause for owner sign-off before the first deletion.
2. **D1 is about to merge before plan 53's package row lands, or after its config-registry row.** D1 must sit in that gap (section 1). Stop and resequence.
3. **D2 types `Check.ledger` as `LedgerName`.** Plan 53 row 3 has landed, so `LedgerName` exists in `backend/idhazh/contracts/ledger_name.py` and `SegmentLedger` is gone. D2's blocker is cleared (compliance rule, section 4.8).
4. **Any plan-54 diff would make plan 53 rename one more symbol** (rule B1, section 4.8). That is a forbidden reintroduction of a word plan 53 is removing - use the post-53 name and add the cross-plan dependency, or stop.
5. **A committed-day writer is found that does not go through a validated `DigestDay`.** The runner parse still catches it at publication, but a validated-write row is then owed at that writer - surface it.

## 1. Status Reckoner

One PR-group is one pull request. **Four: two backend, one frontend, one close.** Docs fold into the group that makes them true (CLAUDE.md section 9).

| # | Row (PR group) | Depends-on (intra) | Depends-on (cross-plan, by title) | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The day-validation receipt is decommissioned end to end | - | after "`ledger.py` becomes the package...", before "The ledger registry moves to `config/ledgers.json`" | A | PENDING | - | - | - |
| 2 | The `check-publication` framework, the rename, and the live hook | 1 | after "One `LedgerName` for one ledger" | B | PENDING | - | - | - |
| 3 | The run-yield chart replaces the donut | - | none | A | PENDING | - | - | - |
| 4 | Closure and distillation | 1, 2, 3 | - | C | PENDING | - | - | - |

**Critical path: D1 -> D2 -> D4, with D3 parallel to D1.** D1 (backend decom) and D3 (frontend chart) share no files and run together (N=2). D2 is single-threaded behind both D1 and plan 53's `LedgerName` row - it types the hook `LedgerName` and never `SegmentLedger`. **D1 is delete-only, so it needs no `LedgerName` and lands in the gap between plan 53's package row and its config-registry row** - early enough to keep plan 50's "two roots" row additive. Wall-clock is gated by plan 53's progress to the `LedgerName` row, not by plan-54 fan-out.

**Every group stamps its own Reckoner line in its own change** (execute-a-plan.md).

## 2. The facts the contracts stand on

Verified against `origin/main` at the current checkout (`07a18385d`) and the live PR list:

- **`STORE_DIRNAMES` no longer exists.** Plan 53 row 1, "The retired word leaves", has landed on `main` (PRs #1107, #1108, #1109); the frozenset is `ledger.LEDGER_DIRNAMES` now. Plan 54 uses `LEDGER_DIRNAMES` throughout, never `STORE_DIRNAMES`.
- **`class SegmentLedger` is gone**; plan 53 row 3 landed and `LedgerName` replaced it, with `DAY_TREES` as the typed subset a writer files a segment into. D2 types the hook on `LedgerName` and no longer waits (section 4.8).
- **The day-validation double-prune-claim is live, and D1's removal is the whole fix - delete-only.** `state/day-validations/` is claimed by `_prune_day_validation_shards` (its proper 14-month pass) and by `_prune_trial_shards` (the strays sweep), because `DAY_VALIDATIONS_DIRNAME` is not in `LEDGER_DIRNAMES` and not one of the four extra names `_trial_roots` subtracts (`traces`, `day-metrics`, `digest-fragments`, the score archive), so `_trial_roots` returns it and the 90-day trial sweep empties it before its 14-month window. Deleting the tree and its writer means `state.iterdir()` never yields it, so `_trial_roots` never returns it - the strays sweep loses its object with no edit to `_trial_roots`, `_prune_trial_shards` or `LEDGER_DIRNAMES`.
- **On plan 50:** the double-claim lives in `_trial_roots`, which plan 50's row "The payload ledger, the two roots, and the arrow mapping" edits to register `state/raw` and `state/compact`. D1 does not unblock that row - plan 50 could ship with day-validations present - but it keeps the row **purely additive**, and plan 50's own section 5.8 line "`day-validations` - No task. Plan 54 deletes this ledger" stands. What blocks plan 50's critical path is plan 54 feeding plan 53's `LedgerName`, not this prune bug.
- **`day_metrics` already carries the chart's data.** `items_planned`, `items_published`, `items_failed` are required fields on every committed `state/day-metrics/<Y>/<M>/<D>.json`, published to `frontend/public/day-metrics/`, but not yet exposed by the frontend `dayMetrics()` reader. D3 widens that reader by three cells already in the JSON; no new ledger, no backend contract change.
- **planned, published and failed are not a clean partition** - `items_planned` and `items_failed` are per-run sums, `items_published` is the deduped day set, and skipped items belong to neither. So the chart uses grouped bars, never a stack, and its yield axis is not guaranteed <=100% (section 4.6).
- **There are two writers of a committed `digest.json`** - `assemble.py` (validated) and `backfill_vectors.py` (`model_copy(update=...)`, not validated at the write) - so the runner's parse is the day-shape guarantee, not a trust in the writers.

## 3. The shape this plan builds

```
backend/idhazh/
    publication_checks/
        __init__.py           the facade the CLI reaches
        registry.py           Check, CheckScope, CommittedDay, DayContext, TreeContext, CheckResult; discover(), validate_registry()
        runner.py             run_publication_checks(): parse each day once; run every check; honour the ledger hook
        checks/
            projection.py     DigestView.project per day        (was check 2)
            pictures.py       picture collisions/missing/orphans (was check 3)
            reconciliation.py planned-items reconciliation FAULT (was census, check 4; ledger=None, emits no row)
            console.py        console payloads via their shapes  (check 5)

frontend/src/
    lib/charts/run-yield.ts   the per-date planned/published/failed + yield chart option (built to the FailurePanels template)
    lib/server/payload.ts     dayMetrics() widened by items_planned/items_published/items_failed
    routes/console/+page.svelte  the donut swapped for the full-width run-yield panel

removed by D1:
    backend/idhazh/contracts/day_validation.py        DayValidationReceipt
    state/day-validations/                            the committed receipts
    backend/tests/pipeline/test_frozen_days.py        receipt-only tests
removed by D2:
    backend/idhazh/stages/validate_days.py            the stage (the day-shape check dies with it)
```

No `contracts/reconciliation.py`, no reconciliation ledger, no operator reader - `day_metrics` is the single source (section 2).

## 4. The contracts a worker must not invent

### 4.1 The plugin interface - `backend/idhazh/publication_checks/registry.py`

Plain code, not a `contracts/` model. `Check.ledger` types `LedgerName` (plan 53's vocabulary), so this module lands in D2, after the `LedgerName` row.

```python
from __future__ import annotations
import importlib, pkgutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.ledger_name import LedgerName        # plan 53's home for the vocabulary
from idhazh.ledger import CsvRecord, segment_contract       # reached through the facade (rule B3)

class PublicationCheckError(RuntimeError):
    """A framework wiring fault, raised before any check runs; the CLI maps it to exit 2."""

class CheckScope(StrEnum):
    DAY = "day"
    TREE = "tree"

@dataclass(frozen=True)
class CommittedDay:
    date: str
    path: Path
    payload: bytes
    raw: dict[str, Any]        # json.loads(payload) - what DigestView.project reads
    day: DigestDay | None      # the validated model, or None when the JSON object fails digest-day

@dataclass(frozen=True)
class DayContext:
    digest_root: Path
    public_root: Path
    days: tuple[CommittedDay, ...]

@dataclass(frozen=True)
class TreeContext:
    root: Path
    months: frozenset[str] | None

class CheckResult(NamedTuple):
    faults: tuple[str, ...] = ()
    rows: tuple[CsvRecord, ...] = ()          # empty unless a check declares a ledger

@dataclass(frozen=True)
class Check:
    name: str
    scope: CheckScope
    run: Callable[[DayContext | TreeContext], CheckResult]
    ledger: LedgerName | None = None
```

`discover()` walks `checks/` at depth one (sorted), imports each non-underscore module, reads its `CHECK`/`CHECKS`, binds by `Check.name`. Four failures raise `PublicationCheckError` (exit 2): a module that raises on import; a module declaring no `Check`; two checks with one name; and, in `validate_registry()`, a `Check.ledger` whose `segment_contract(ledger)` has no entry. The bodies are as in the prior revision; the only change is the `LedgerName` type and the facade import.

### 4.2 The runner - `backend/idhazh/publication_checks/runner.py`

Parses each committed day into `DigestDay` once (the day-shape guarantee), runs every check, and persists a check's rows only when it declares a ledger AND the run is day-scoped (`only` non-empty) AND `state_dir` is set - so a full sweep writes nothing. Reaches `write_segment` through `idhazh.ledger` (rule B3). Exit `0`/`1`/`2`. Full body as in the prior revision, with `SegmentLedger` replaced by `LedgerName` and the persist gate keyed on `only`:

```python
if check.ledger is None:
    assert not result.rows, f"{check.name} declares no ledger but emitted rows"
    continue
if state_dir is not None and bool(only):
    ledger.write_segment(state_dir, check.ledger, result.rows, run_id=run_id,
                         attempt=run_context.run_attempt(), job=ServerJob.ASSEMBLE, shard=0)
```

### 4.3 The four checks - `checks/*.py`

`projection.py`, `pictures.py`, `console.py` move their bodies verbatim from `validate_days.py`. **`reconciliation.py` is fault-only** - it reads the parsed day and faults on the lost-plan case, declaring no ledger and emitting no row:

```python
# backend/idhazh/publication_checks/checks/reconciliation.py
from idhazh.publication_checks.registry import Check, CheckResult, CheckScope, DayContext

def _run(ctx: DayContext) -> CheckResult:
    faults = [
        f"{d.date} planned {d.day.items_planned} stories and accounts for none of them: "
        f"nothing published and nothing failed"
        for d in ctx.days
        if d.day is not None and d.day.items_planned and not d.day.items and not d.day.items_failed
    ]
    return CheckResult(faults=tuple(faults))

CHECK = Check(name="planned-items-reconciliation", scope=CheckScope.DAY, run=_run)   # ledger=None
```

### 4.4 The live hook, proven by one integration test

The hook is real code - the runner branch in 4.2 - and is exercised by exactly one un-mocked integration test, its named consumer (so it is not speculative generality). No production check declares a ledger.

- **Test:** a fixture check declared inside the test, `ledger=<an existing day-tree LedgerName>`, returns one real row; run over a fixture day with a scratch `state_dir` and a day-scoped `only`; assert the row lands under `state/<that ledger>/<Y>/<M>/<D>/<name>.csv` through a real `write_segment`, and reads back byte-equal through `day_shards.settled_rows`. No mock, no network; the fixture check lives in `tests/fixtures`, not in `checks/`, so `discover()` never binds it in production.

### 4.5 The day-validation decommission (D1) - delete-only

Remove, in one PR, using whatever spelling exists at merge time (rule B2 - deletion needs no plan-53 dependency):

- `backend/idhazh/contracts/day_validation.py` (`DayValidationReceipt`); its import + `CONTRACTS` + `__all__` entries in `contracts/__init__.py`; the fixture dir `tests/fixtures/contracts/day-validation-receipt/`.
- In `backend/idhazh/ledger/__init__.py`: `DAY_VALIDATIONS_DIRNAME`, `DAY_VALIDATION_KEY`, `_day_validation_rule`/`DAY_VALIDATION_RULE`, the `_PREFERENCES` entry, `SegmentLedger.DAY_VALIDATIONS` (or `LedgerName.DAY_VALIDATIONS` if the `LedgerName` row has landed by merge time), the `_TREE_SHAPES` entry. **`LEDGER_DIRNAMES` needs no edit** - day-validations was never a member.
- `retention.prune_day_validations`; the `day_validation_keep_months` knob on `RetentionConfig`; swap the committed key out of `config/idhazh.json` and out of `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`.
- `stages/prune_state.py`: `_prune_day_validation_shards` and its call. No edit to `_prune_trial_shards`/`_trial_roots`.
- The receipt-write in the stage (D2 deletes the stage entirely; D1 removes the ledger member so the stage stops writing - sequence the stage's write removal into D1 so nothing writes the tree after D1).
- The committed `state/day-validations/` tree; `backend/tests/pipeline/test_frozen_days.py` (receipt-only, confirmed).
- **Stale-text sweeps D1 owes:** any `STORE_DIRNAMES` reference in docs/comments -> `LEDGER_DIRNAMES`; and if D1 lands before the `LedgerName` row, plan 53's "nine day trees" prose in its section 4.1 becomes "eight" (the coverage oracle is git-computed, so only the prose drifts).

### 4.6 The run-yield chart (D3) - Susan's shippable spec

Built to the existing `frontend/src/lib/components/FailurePanels.svelte` bar+line template (fixed right axis, printed readout, hatched gaps, line-break under a thin denominator). Reuse it; do not invent a dual-axis component.

| # | Element | The craft |
| --- | --- | --- |
| 1 | Bars | three per day, **grouped, not stacked** (planned/published/failed are not a partition); `FailurePanels` bar math (group fills 0.8 of the day slot, min 1px) |
| 2 | Colours | categorical chart ramp, **not** the confidence/fill ramp: planned = `--chart-axis` (neutral - it is the denominator), published = `--chart-2`, failed = `--chart-8` |
| 3 | Yield line | `published/planned` per day; `--chart-marker`, 1.75px, one ~5px dot a day, the loudest mark; **break the line where `items_planned` = 0** (a gap, never a zero dot) |
| 4 | Right axis | **fixed 0-100%** (a fixed rate axis cannot invite the false-correlation read a co-scaled one would); a day over 100% draws at the ceiling with its true value in the readout, never silently clamped |
| 5 | Readout | a `ChartReadout` strip, not a lone tooltip: hovered/selected day shows date, Planned N, Published N, Failed N, Yield P%, each with its swatch; keyboard Left/Right/Escape, resting on the newest day; an `sr-only` per-day list for the description and the test oracle |
| 6 | Axis titles | left `Items`, right `Yield, %` (sentence case, unit lowercase, no full stop); no legend (the readout names each series) |
| 7 | Missing day | no bars and a broken line, under a hatched `coverageRegions` span with `coverageSentence` "No run recorded on <dates>" - a zero-height bar would falsely say "planned nothing" |
| 8 | Placement | a **full-width `Panel`** in the "At a glance" section, directly below the two KPI skyline cards, replacing the donut; **not** the 17rem grid cell (90 grouped bars in 260px is a grey wall). Nothing else leaves the section |
| 9 | Phone | below ~480px collapse to the yield line plus a single planned bar, counts in the readout |

- **Data:** widen `dayMetrics()` in `frontend/src/lib/server/payload.ts` by `items_planned`, `items_published`, `items_failed` (already in the committed `day-metrics` JSON). Yield is derived at read time; no stored rate.
- **Removed:** `runHealth` (the donut) and its render in `console/+page.svelte`.
- The visual survives Susan's sufficiency checks and is Jony's to confirm on the page before merge (CLAUDE.md section 14).

### 4.7 The growing read (Guardrail #12)

Unchanged from the prior revision: `published_days()` globs the whole committed tree and no prune deletes a `digest.json`, so the full sweep parses every committed day - documented beside `run_publication_checks` because a contract change can invalidate any frozen day. Cost fits the 6 h job with 35-100x margin at the 727-day site-cap horizon (Carmack). Add the entry to `docs/concepts/growing-reads.md` in D2.

### 4.8 The plan-53 compliance rule

Three rules; first match wins; the worker never chooses. The test behind them: **does the plan-54 diff make plan 53 rename one more symbol, or one fewer?**

- **B1 - adds or keeps** a read/write/type/member of a symbol plan 53 renames or removes: **forbidden.** Use the post-53 name and add a cross-plan `Depends-on` on the row that mints it. (This is why D2 types `Check.ledger: LedgerName` and waits for "One `LedgerName` for one ledger".)
- **B2 - only deletes** the symbol (the D1 decom): **allowed, no dependency.** Delete whichever spelling exists at merge time. Deletion shrinks the surface plan 53 renames; it never reintroduces the word.
- **B3 - uses a name plan 53 keeps** (`write_segment`, `extend_segment`, `segment_contract`): **free.** Reach it through the `idhazh.ledger` facade; never reach a private (`_TREE_SHAPES`) across the boundary.

## 5. The PR groups

### D1 - The day-validation receipt is decommissioned end to end [Level 5]

- **Scope:** remove the receipt, its ledger member/key/rule, retention, prune, and the committed `state/day-validations/` tree; stop the stage writing it. This also removes the live double-prune-claim (section 2). Delete-only (rule B2).
- **Files touched:** section 4.5's list; plus the `validate_days.py` receipt-write removal (the stage itself is deleted in D2); `docs/architecture/contracts/schemas.md`, `docs/concepts/{partitions,growing-reads,telemetry,adaptive-pruning}.md`, `docs/reference/agent-notes/gates-and-builds.md`; comment refs in `contracts/visual_data.py`, `render/write.py`.
- **Acceptance gates:** local - the selector over `backend/tests/contracts`, the ledger/retention/prune tests, the schema-drift gate, `doc_load.py`; CI - full suite. **Level 5: owner sign-off before the first deletion (ESCALATE #1).**
- **Oracle:** a repository search finds zero `DayValidationReceipt`/`DAY_VALIDATION*`/`day-validations`/`STORE_DIRNAMES` references in `backend/`, `config/`, `docs/`; the schema-drift gate is green; a prune test proves `state/day-validations/` is neither swept nor mis-claimed (it is gone). Cannot settle an out-of-tree consumer - there is none.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Delete-only fixes the double-claim; no `_trial_roots` edit | Fowler |
  | 2 | Lands after plan 53's package row, before its config-registry row | Fowler; owner (B3) |
  | 3 | Level 5 - persisted-contract removal + committed-tree deletion | CLAUDE.md section 6 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Fix the double-claim by adding day-validations to `LEDGER_DIRNAMES` | The tree is being deleted; registering it is churn plan 53 then has to undo | A one-line add plan 53 reverts | Fowler |
  | 2 | Let plan 53's config-registry row remove it | It cannot leave the registry while the writer exists; and it would first have to add it | A circular cross-plan dependency | Fowler; owner |

### D2 - The `check-publication` framework, the rename, and the live hook

- **Scope:** `validate_days.py` becomes the discovered `publication_checks/` package (4.1-4.3); the four checks move in (reconciliation fault-only); the day-shape check is dropped; `validate-days` becomes `check-publication` in `cli.py` and the three workflow callers atomically; the `Check.ledger` hook plus its one integration test (4.4).
- **Files touched:** `backend/idhazh/publication_checks/**` (new); `backend/idhazh/stages/validate_days.py` (deleted); `backend/idhazh/cli.py` (dispatch, drop the receipt-pairing guard); `.github/workflows/{ci,digest,backfill}.yml`, `pages.yml` (comment); `backend/tests/workflows/_harness.py`, `test_publish_ordering.py`; `backend/tests/contracts/test_committed_days.py`, `backend/tests/test_day_census.py`, `backend/tests/test_published_assets.py`; comment-only refs in `test_two_calls.py`, `test_article_and_eval.py`, `test_eval_ledger.py`, `test_evals.py`, `test_render.py`; the publication-checks doc page; `docs/concepts/growing-reads.md`.
- **Acceptance gates:** local - the selector over `backend/tests/pipeline`, `backend/tests/workflows`, `backend/tests/contracts` and the moved checks' tests; CI - full suite. Parity bar: `check-publication` over the canary day is fault-identical to `validate-days` over that day.
- **Oracle:** discovery bijection - `discover()` binds exactly `{projection, pictures, planned-items-reconciliation, console}`; the integration test lands and reads back one real row through `write_segment` (the hook is live). Cannot settle a future check.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Day-shape check removed; runner per-day parse is the guarantee | Fowler; owner (B4) |
  | 2 | Hook kept, proven by one integration test; no production ledger consumer | owner (keep) 2026-09-26 |
  | 3 | `Check.ledger: LedgerName`; waits for "One `LedgerName` for one ledger" (rule B1) | Fowler |
  | 4 | Drop the CLI `--state-root`/`--digest-root` guard (its reason died with the skip) | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Drop the hook entirely | Retires owner ruling B2 | Loses a proven-live capability; owner's call | Fowler; owner |
  | 2 | Type the hook `SegmentLedger` and land before the `LedgerName` row | Reintroduces a symbol plan 53 removes (rule B1) | A throwaway edit plan 53 rewrites, and a broken-tree window | Fowler |

### D3 - The run-yield chart replaces the donut

- **Scope:** widen `dayMetrics()` by three cells; add the per-date planned/published/failed + yield chart (4.6); swap it for the donut in "At a glance". Frontend-only; no backend contract, no ledger vocabulary - independent of D1/D2 and both plans.
- **Files touched:** `frontend/src/lib/server/payload.ts`; `frontend/src/lib/charts/run-yield.ts` (new); `frontend/src/routes/console/+page.svelte`; the chart's logic test; the `dayMetrics` reader test.
- **Acceptance gates:** local - the frontend logic tests; CI - full suite. **Published-site change - owes the browser smoke (CLAUDE.md section 12), including the render-on-empty-`day_metrics` case.**
- **Oracle:** the chart option is built from a fixture `day_metrics` window and asserts one group per date, a broken line on a zero-planned day, the yield axis fixed 0-100%, and a hatched gap on a missing day. Cannot settle whether the visual is good enough - that is Susan's ruling (met) and Jony's page confirmation.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One chart only (B1); grouped bars; fixed yield axis; readout not tooltip; built to the FailurePanels template | Susan |
  | 2 | Full-width panel below the KPI cards, replacing the donut | Susan |
  | 3 | Reads `day_metrics` via a 3-cell reader widening; no new ledger | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Stacked bars | planned/published/failed are not a partition; a stack draws a false part-to-whole | A misleading chart | Fowler; Susan |
  | 2 | Add B2/B3/B4 here too | Three more rate cards make this a dashboard, not a glance | Clutter; the six-shapes wall | Susan |
  | 3 | Keep the donut in the 17rem cell | 90 bars in 260px is a grey wall; the donut is the thing being retired | An unreadable chart | Susan |

### D4 - Closure and distillation

- **Scope:** stamp the Reckoner, distill any finding no page owns, delete the plan-doc.
- **Files touched:** this plan-doc (deleted at closure); any living doc a distilled finding lands on.
- **Acceptance gates:** local - `doc_load.py`; CI - full suite. Every Reckoner row `DONE`.
- **Oracle:** the Reckoner is all `DONE`, the plan-doc is gone, each distilled finding is on a living doc.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Distillation is a row with a pull request (docs/how-to/distill-a-plan.md) | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave the plan-doc in `TODO/` | A closed plan is a cache that rots against `docs/` | A second source of truth | CLAUDE.md section 10 |

Execution stamp: run per docs/how-to/execute-a-plan.md as a workpool at Parallel N = 2; honour the cross-plan dependencies by title (section 1); D1 sits between plan 53's package row and its config-registry row; D2 waits for the `LedgerName` row; AUTHOR-AND-STOP until the user authorizes.
