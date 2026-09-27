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
| Chosen strategy | Decommission the receipt early and delete-only; rename to a discovered framework once `LedgerName` exists; draw the chart from already-published `day_metrics`. No new ledger. Ruled by Fowler (architecture, sequencing), Susan (the chart), Carmack (the sweep cost); owner decisions dated 2026-09-26. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md, as a workpool. **Parallel N = 2** - D1 (backend) and D3 (frontend) are file-disjoint; D2 is single-threaded behind plan 53's `LedgerName` row and D1. N=2 buys "D3 lands early", not a speedup - the calendar is the wait for that plan-53 row (Carmack). |
| Blocks / blocked-by | **Blocked-by** plan 53 rows, by title: D1 lands **after** "`ledger.py` becomes the package, and its docstring becomes a page" (do not race its PR) and **before** "The ledger registry moves to `config/ledgers.json`"; D2 lands **after** "One `LedgerName` for one ledger". **De-risks** plan 50's row "The payload ledger, the two roots, and the arrow mapping" by keeping it purely additive (section 2), but does not unblock it. |

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
| Bounding the committed digest tree | The full-sweep re-parse grows one day a day (documented Guardrail #12 read, section 4.7); measured to fit the 6 h job with 360-1440x margin | A separate retention design |

### ESCALATE triggers

1. **D1 begins** - a persisted contract is removed and a committed tree is deleted (Level 5). Pause for owner sign-off before the first deletion.
2. **D1 is about to merge before plan 53's package row lands, or after its config-registry row.** D1 must sit in that gap (section 1). Stop and resequence.
3. **D2 types `Check.ledger` as `LedgerName`.** Plan 53 row 3 has landed, so `LedgerName` lives in `backend/idhazh/contracts/ledger_name.py` and `SegmentLedger` is gone. D2's blocker is cleared (compliance rule, section 4.8).
4. **Any plan-54 diff would make plan 53 rename one more symbol** (rule B1, section 4.8). Forbidden reintroduction - use the post-53 name and add the cross-plan dependency, or stop.
5. **A committed-day writer is found that does not go through a validated `DigestDay`.** The runner parse still catches it at publication, but a validated-write row is then owed at that writer - surface it.

## 1. Status Reckoner

One PR-group is one pull request. **Four: two backend, one frontend, one close.** Docs fold into the group that makes them true (CLAUDE.md section 9).

| # | Row (PR group) | Depends-on (intra) | Depends-on (cross-plan, by title) | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The day-validation receipt is decommissioned end to end | - | after "`ledger.py` becomes the package...", before "The ledger registry moves to `config/ledgers.json`" | A | PENDING | - | - | - |
| 2 | The `check-publication` framework, the rename, and the live hook | 1 | after "One `LedgerName` for one ledger" | B | PENDING | - | - | - |
| 3 | The run-yield chart replaces the donut | - | none | A | PENDING | - | - | - |
| 4 | Closure and distillation | 1, 2, 3 | - | C | PENDING | - | - | - |

**Critical path: D1 -> D2 -> D4, with D3 parallel to D1.** D1 (backend decom) and D3 (frontend chart) share no files and run together (N=2). D2 is single-threaded behind both D1 and plan 53's `LedgerName` row - it types the hook `LedgerName` and never `SegmentLedger`. **D1 is delete-only, so it needs no `LedgerName` and lands in the gap between plan 53's package row and its config-registry row.** Wall-clock is gated by plan 53's progress to the `LedgerName` row, not by plan-54 fan-out (Carmack).

**Every group stamps its own Reckoner line in its own change** (execute-a-plan.md).

## 2. The facts the contracts stand on

Verified against `origin/main` at the current checkout (`fd4bc55ea`) and the live PR list:

- **There is no hand-coded set of ledger directories any more.** Plan 53's row 5 has landed: the set of ledgers, each one's lifecycle state and where it sits are `config/ledgers.json`, validated at load against `LedgerName`, and `_trial_roots` derives its protected set from `ledger.claimed_roots()`. Every earlier name for that set is gone.
- **`class SegmentLedger` is gone**; plan 53 row 3 landed and `LedgerName` replaced it, with `DAY_TREES` as the typed subset a writer files a segment into. Plan 53 row 2 landed too, so the module is `backend/idhazh/ledger/__init__.py`. D2 types the hook on `LedgerName` and waits for nothing; D1 still names its ledger targets by symbol, because plan 53 rows 5 and 6 relocate them again (section 4.5).
- **The discovered-plugin pattern is the house pattern, not a new invention.** `backend/idhazh/council/registry.py` already discovers modules by `importlib.import_module` over `pkgutil.iter_modules`, raising on a wiring fault. `check-publication` follows it; the named beneficiary is consistency with council and the four (soon more) checks a plain list would hand-register.
- **The day-validation double-prune-claim is closed, and D1 stays delete-only.** `state/day-validations/` was claimed by `_prune_day_validation_shards` (its proper 14-month pass) and by `_prune_trial_shards` (the strays sweep), because the old hand-coded set left it out - so the 90-day trial sweep emptied it before its 14-month window. Plan 53 row 5 closed that by consequence: the registry claims every ledger it knows, `day-validations` included. **D1 now has one more thing to delete**: its `config/ledgers.json` entry, alongside `LedgerName.DAY_VALIDATIONS` and its `DAY_TREES` membership. Deleting the tree and its writer means `state.iterdir()` never yields it, so `_trial_roots` still needs no edit.
- **On plan 50:** the double-claim lives in `_trial_roots`, which plan 50's row "The payload ledger, the two roots, and the arrow mapping" edits to register `state/raw` and `state/compact`. D1 does not unblock that row; it keeps it purely additive, and plan 50's own line "`day-validations` - No task. Plan 54 deletes this ledger" stands. What blocks plan 50's critical path is plan 54 feeding plan 53's `LedgerName`, not this prune bug.
- **`day_metrics` already carries the chart's data.** `items_planned`, `items_published`, `items_failed` are required non-null ints on every committed `state/day-metrics/<Y>/<M>/<D>.json`, published to `frontend/public/day-metrics/`, but not yet exposed by the frontend `dayMetrics()` reader. D3 widens that reader by three cells already in the JSON; no new ledger, no backend contract change.
- **planned, published and failed are not a clean partition** - `items_planned` and `items_failed` are per-run sums, `items_published` is the deduped day set, and skipped items belong to neither. So the chart uses grouped bars, never a stack, and its yield axis is not guaranteed <=100% (section 4.6).
- **There are two writers of a committed `digest.json`** - `assemble.py` (validated) and `backfill_vectors.py` (`model_copy(update=...)`, not validated at the write) - so the runner's parse is the day-shape guarantee, not a trust in the writers.

## 3. The shape this plan builds

```
backend/idhazh/
    publication_checks/
        __init__.py           the facade the CLI reaches (run_publication_checks, PublicationCheckError)
        registry.py           Check, CheckScope, CommittedDay, DayContext, TreeContext, CheckResult; discover(), validate_registry()
        runner.py             run_publication_checks(): parse each day once; run every check; honour the ledger hook
        checks/
            projection.py     DigestView.project per day        (was check 2; DAY - dates its faults)
            pictures.py       picture collisions/missing/orphans (was check 3; DAY - dates its faults)
            reconciliation.py planned-items reconciliation FAULT (was census, check 4; DAY; ledger=None, no row)
            console.py        console payloads via their shapes  (check 5; TREE - moves verbatim)

frontend/src/
    lib/charts/run-yield.ts       the per-date geometry helper (RunYieldLoad), like glance.ts::failureLoad - NOT an EChartsOption
    lib/components/RunYield.svelte a re-parameterised FailurePanels: grouped bars + fixed-axis yield line + readout
    lib/server/payload.ts         dayMetrics() widened by itemsPlanned/itemsPublished/itemsFailed
    routes/console/+page.svelte    the donut removed, RunYield placed full-width in "At a glance"

removed by D1:
    backend/idhazh/contracts/day_validation.py        DayValidationReceipt
    state/day-validations/                            the committed receipts (51 files)
    backend/tests/pipeline/test_frozen_days.py        receipt-only tests
removed by D2:
    backend/idhazh/stages/validate_days.py            the stage (the day-shape check dies with it)
    frontend/src/lib/charts (runHealth + donut)       dead after the donut swap (section 4.6)
```

No `contracts/reconciliation.py`, no reconciliation ledger, no operator reader - `day_metrics` is the single source (section 2).

## 4. The contracts a worker must not invent

### 4.1 The plugin interface - `backend/idhazh/publication_checks/registry.py`

Plain code, not a `contracts/` model. `Check.ledger` types `LedgerName` (plan 53's vocabulary), so this module lands in D2, after the `LedgerName` row. Full file:

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
from idhazh.contracts.ledger_name import LedgerName        # plan 53 mints this in "One LedgerName for one ledger"
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

def _declared(module: ModuleType) -> tuple[Check, ...]:
    found = [c for c in (getattr(module, "CHECK", None),) if isinstance(c, Check)]
    found += [c for c in getattr(module, "CHECKS", ()) if isinstance(c, Check)]
    if not found:                                                        # failure 2
        raise PublicationCheckError(f"{module.__name__} declares no CHECK/CHECKS of type Check")
    return tuple(found)

def discover() -> tuple[Check, ...]:
    from idhazh.publication_checks import checks as pkg
    bound: dict[str, Check] = {}
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{pkg.__name__}.{info.name}")  # failure 1: import raises -> propagate
        for check in _declared(module):
            if check.name in bound:                                      # failure 3: duplicate name
                raise PublicationCheckError(
                    f"two modules declare check {check.name!r}: "
                    f"{bound[check.name].run.__module__} and {module.__name__}")
            bound[check.name] = check
    return tuple(bound[name] for name in sorted(bound))

def validate_registry(registry: Sequence[Check]) -> None:
    for check in registry:
        if check.ledger is None:
            continue
        try:
            segment_contract(check.ledger)                               # failure 4: no tree-shape entry
        except KeyError as error:
            raise PublicationCheckError(
                f"{check.name} names ledger {check.ledger!r} with no tree-shape entry") from error
```

### 4.2 The runner - `backend/idhazh/publication_checks/runner.py`

Parses each committed day into `DigestDay` once (the day-shape guarantee), runs every check, and persists a check's rows only when it declares a ledger AND the run is day-scoped (`only` non-empty) AND `state_dir` is set - so a full sweep writes nothing. Reaches `write_segment` through `idhazh.ledger` (rule B3). Exit `0`/`1`/`2`. Full file:

```python
from __future__ import annotations
import json
from collections.abc import Sequence
from pathlib import Path
from pydantic import ValidationError
from idhazh import ledger, run_context
from idhazh.contracts.base import ServerJob
from idhazh.contracts.digest_day import DigestDay
from idhazh.publication_checks.registry import (
    CheckScope, CommittedDay, DayContext, TreeContext, discover, validate_registry,
)
from idhazh.stages.common import LOG, published_days

WHOLE_ARCHIVE_SHARD = 0   # one writer, one job, no fan-out

def _day_of(path: Path) -> str:
    parts = path.parts[-4:-1]
    return "-".join(parts) if len(parts) == 3 else path.as_posix()

def _parse_committed_days(root: Path, only: Sequence[str]) -> tuple[list[CommittedDay], list[str]]:
    """Every day in scope, parsed once, plus framework faults from days that will
    not parse. Reader-parses rather than trusting the writers."""
    wanted, parsed, faults = set(only), [], []
    for path in published_days(root):
        date = _day_of(path)
        if only and date not in wanted:
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            faults.append(f"{date} cannot be read: {error.strerror or error}"); continue
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as error:
            faults.append(f"{date} is not JSON: {error}"); continue
        if not isinstance(raw, dict):
            faults.append(f"{date} is a {type(raw).__name__}, not a day"); continue
        try:
            day: DigestDay | None = DigestDay.model_validate(raw)
        except ValidationError as error:
            faults.append(f"{date} fails digest-day.schema.json: {error.error_count()} problems\n{error}")
            day = None
        parsed.append(CommittedDay(date=date, path=path, payload=payload, raw=raw, day=day))
    return parsed, faults

def run_publication_checks(root: Path, only: Sequence[str] = (), *, state_dir: Path | None = None, run_id: str) -> int:
    committed = published_days(root)
    if not committed:
        LOG.error("check-publication found no digest.json under %s - a run over nothing passes "
                  "every contract", root.as_posix())
        return 1
    if only:
        missing = sorted(set(only) - {_day_of(p) for p in committed})
        if missing:
            LOG.error("check-publication was asked for days that are not committed: %s", missing); return 1
    registry = discover(); validate_registry(registry)          # failures 1-4 -> PublicationCheckError -> exit 2 in cli
    parsed, faults = _parse_committed_days(root, only)
    day_ctx = DayContext(digest_root=root, public_root=root.parent, days=tuple(parsed))
    tree_ctx = TreeContext(root=root, months=frozenset(d[:7] for d in only) if only else None)
    scoped = bool(only)
    for check in registry:
        result = check.run(day_ctx if check.scope is CheckScope.DAY else tree_ctx)
        faults.extend(result.faults)
        if check.ledger is None:
            assert not result.rows, f"{check.name} declares no ledger but emitted rows"
            continue
        if state_dir is not None and scoped:
            ledger.write_segment(state_dir, check.ledger, result.rows, run_id=run_id,
                                 attempt=run_context.run_attempt(), job=ServerJob.ASSEMBLE, shard=WHOLE_ARCHIVE_SHARD)
    for fault in faults:
        LOG.error("check-publication %s", fault)
    return 1 if faults else 0
```

The CLI facade `publication_checks/__init__.py` re-exports `run_publication_checks` and `PublicationCheckError`; `cli.py` catches the latter and returns 2 (section 4.5).

### 4.3 The four checks - `checks/*.py`

Each declares `CHECK = Check(name=..., scope=..., run=..., ledger=None)` and moves its fault logic from `validate_days.py`. **The runner logs faults generically and `CheckResult.faults` carries no date**, so the DAY checks must **prefix every fault with the day**, which the current `validate_days` loop does via `LOG.error("%s %s", date, fault)`:

- `projection.py` (DAY): for each `d in ctx.days` with `d.raw`, run `DigestView.project(d.raw)`; each fault is `f"{d.date} {message}"`.
- `pictures.py` (DAY): for each `d in ctx.days` with `d.day`, run `_picture_faults(ctx.public_root, d.day)` and `assets_in_day`; each fault `f"{d.date} {message}"`.
- `reconciliation.py` (DAY): fault-only, already date-prefixed:

```python
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

- `console.py` (TREE): moves `_console_payload_faults(ctx.root, ctx.months)` **verbatim** (it already carries the dataset path in each fault).

**Parity bar:** the set of fault *messages* `check-publication` emits over the canary day equals what `validate-days` emitted; only the log prefix (`check-publication` vs `validate-days`) changes.

### 4.4 The live hook, proven by one integration test

The hook is real code - the runner branch in 4.2 - exercised by exactly one un-mocked integration test, its named consumer. No production check declares a ledger. The row is a `SpanRollupRow` (a `DAY_TREES` member written through `write_segment`; a `RollupSpan.ROBOTS` row is unambiguously valid because `unattributed_ms` defaults `None` and only the `item` span may carry it). `backend/tests/pipeline/test_publication_hook.py`:

```python
from pathlib import Path
import pytest
from idhazh import day_shards, ledger
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.publication_checks import registry, runner

def test_a_declared_ledger_row_is_written_and_read_back(tmp_path: Path, monkeypatch) -> None:
    """The Check.ledger hook is live: a check that declares a ledger has its rows
    persisted through the real write_segment and read back byte-equal - no mock."""
    day = "2026-09-20"
    row = SpanRollupRow(version=SpanRollupRow.schema_version(), date=day, run_id="2026-09-20-1",
                        shard=0, span_name=RollupSpan.ROBOTS, count=1, total_ms=5)   # unattributed_ms=None
    probe = registry.Check(
        name="probe", scope=registry.CheckScope.DAY,
        run=lambda ctx: registry.CheckResult(rows=(row,)),
        ledger=LedgerName.SPAN_ROLLUP)                         # a DAY_TREES member (A11)
    monkeypatch.setattr(runner, "discover", lambda: (probe,))  # the only seam; the write path is fully real
    monkeypatch.setattr(runner, "validate_registry", lambda _reg: None)

    digest_root = tmp_path / "public" / "digest"
    # Seed one committed day so published_days() finds it; use the canary builder.
    from backend.utilities.build_canary_day import write_canary_day   # or the project's canary helper
    write_canary_day(digest_root, day)
    state_dir = tmp_path / "state"

    assert runner.run_publication_checks(digest_root, only=[day], state_dir=state_dir, run_id="2026-09-20-1") == 0
    read = [SpanRollupRow.from_csv_row(cells) for cells in day_shards.settled_rows(
        ledger.tree_root(state_dir, LedgerName.SPAN_ROLLUP), ledger.SPAN_ROLLUP_KEY, SpanRollupRow, days=UNBOUNDED_WINDOW)]
    assert read == [row]
```

Patching `discover` (and `validate_registry`, which would otherwise walk the real registry) is the honest single seam - the `write_segment` -> day-shard -> `settled_rows` path is fully real (not a Guardrail #7 mock). The worker confirms the canary helper's exact name/signature in `backend/utilities/build_canary_day.py`; if it does not take a target root, write one minimal validated `DigestDay.to_json()` to `digest_root/2026/09/20/digest.json` instead.

### 4.5 The day-validation decommission (D1) - delete-only, by symbol

Remove, in one PR, using whatever spelling exists at merge time (rule B2). **Name targets by symbol, not by file** - D1 lands after plan 53's "`ledger.py` becomes the package" row, which relocates `DAY_VALIDATION_KEY`/rule/tree-shape into `ledger/keys.py` (plan 53 section 3):

- `DayValidationReceipt` (`backend/idhazh/contracts/day_validation.py`); its import + `CONTRACTS` tuple + `__all__` entries in `contracts/__init__.py`; the fixture dir `tests/fixtures/contracts/day-validation-receipt/` (confirm it exists before scripting the delete).
- Wherever they now live: `DAY_VALIDATION_KEY`, `_day_validation_rule`/`DAY_VALIDATION_RULE`, the preference-map entry, `LedgerName.DAY_VALIDATIONS` and its `DAY_TREES` membership, the tree-shape entry. **The `day-validations` entry in `config/ledgers.json` goes too** - the registry is a bijection with `LedgerName`, so removing the member without the entry stops the build, and removing both is what closes the double-claim for good. No edit to `_trial_roots`.
- `retention.prune_day_validations`; the `day_validation_keep_months` knob on `RetentionConfig`; swap the committed key out of `config/idhazh.json` and out of `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`.
- `stages/prune_state.py`: `_prune_day_validation_shards` and its call. No edit to `_prune_trial_shards`/`_trial_roots`.
- The receipt-write path in `validate_days.py` (`_receipts_for`/`_proved`/`_record_receipts` and their calls) - so nothing writes the tree after D1; the stage file itself is deleted in D2.
- `backend/tests/test_migrate_to_day_shards.py` asserts on `day-validations` (a sample tree name) - re-point it to a surviving day tree.
- The committed `state/day-validations/` tree (51 files); `backend/tests/pipeline/test_frozen_days.py` (receipt-only, confirmed).
- **Docs/comments:** `docs/architecture/contracts/schemas.md`, `docs/concepts/{partitions,growing-reads,telemetry,adaptive-pruning}.md`, `docs/reference/agent-notes/gates-and-builds.md`; comment refs in `contracts/visual_data.py`, `render/write.py`. Leave `docs/archive/` and the benchmark record untouched.

### 4.6 The run-yield chart (D3) - built, not sketched

The retiring donut is an ECharts option; **the replacement is an inline-SVG component**, because its craft (a printed `ChartReadout`, hatched `coverageRegions` gaps, a fixed SVG right axis, keyboard nav, an `sr-only` list) is `frame.ts`/SVG machinery an `EChartsOption` cannot deliver. It is a re-parameterised `FailurePanels.svelte`, reusing that shape verbatim. Two files build it plus a reader widening and a page edit.

**`frontend/src/lib/charts/run-yield.ts`** - a geometry helper like `glance.ts::failureLoad`, not an option:

```ts
export interface RunYieldDay {
	date: string; planned: number; published: number; failed: number;
	/** published/planned, or null where planned === 0 (a broken line, never a zero dot). */
	yield: number | null;
}
export interface RunYieldLoad {
	columns: RunYieldDay[];
	peak: number;      // max of planned/published/failed across the window - the left-axis peak
	empty: boolean;    // no column with planned > 0
}
export function runYield(days: readonly DayMetrics[], window: TimeWindow): RunYieldLoad
```

**`frontend/src/lib/server/payload.ts`** - widen `interface DayMetrics` (after `date`) and the reader. These three are required non-null ints on every committed record (section 2), so they join the strict triple and `throw` on absence, not the lenient-band `null`:

```ts
	itemsPlanned: number;    // items_planned
	itemsPublished: number;  // items_published
	itemsFailed: number;     // items_failed
```
In the reader `try` block: read `parsed.items_planned/items_published/items_failed`, `throw new TypeError(...)` if any is not a number, and add `itemsPlanned/itemsPublished/itemsFailed` to the `found.set(date, {...})` literal.

**`frontend/src/lib/components/RunYield.svelte`** - a re-parameterisation of `FailurePanels.svelte`, reusing verbatim from `$lib/charts/frame` (`frame`, `chartWidth`, `linearAxis`, `coverage`, `coverageRegions`, `coverageRegionTitle`, `coverageSentence`, `dayTicks`, `observeWidth`, `pointerReadout`, `readoutMarks`, `notMeasuredRow`, `type DayReadout`), the `ChartReadout` and `Panel` components, `grouped` from `$lib/charts/series`, and `daysBetween`/`TimeWindow` from `$lib/charts/viewport`. The deltas from `FailurePanels` - the only things the worker changes:

| # | Element | The craft (Susan) |
| --- | --- | --- |
| 1 | Bars | **grouped, not stacked**: three bars per day at `centre(i) - g/2 + k*(g/3)`, `g = max(3, min(30, slot - 2))`, height `volume.scale(0) - volume.scale(v)`, min 1px |
| 2 | Colours | categorical, **not** the confidence/fill ramp: planned = `--chart-axis`, published = `--chart-2`, failed = `--chart-8` (all in `tokens.css`) |
| 3 | Yield line | on the fixed right axis (reuse `RATE_TICKS`/`rateY`/`segments`); `--chart-marker`, 1.75px, ~5px dot; **break where `planned === 0`** |
| 4 | Right axis | **fixed [0,1]** (0-100%); a day over 100% draws at the ceiling with its true value in the readout, never clamped |
| 5 | Readout | `ChartReadout` per day: Planned N, Published N, Failed N (counts) + Yield `P%` (or `too few`/`-` at planned 0), each with its swatch; `at` rests on the last column; keyboard Left/Right/Escape; `sr-only` per-day list |
| 6 | Coverage | `columns.map(c => c.planned > 0)` feeds `coverage`/`coverageRegions`/`coverageSentence('No run recorded on')`; a missing day is a hatched gap, never a zero bar |
| 7 | Titles | left `Items`, right `Yield, %`; no legend (the readout names each series) |
| 8 | Placement | a **full-width `Panel`** in "At a glance" below the two `KpiCard`s, replacing the donut; not the 17rem grid cell |
| 9 | Phone | below ~480px collapse to the yield line + a single planned bar, counts in the readout |

**`frontend/src/routes/console/+page.svelte`** - remove `runHealth` from the `$lib/charts/glance` import list (it is one name in a shared import, not a whole line); delete `const runsChart = $derived(runHealth(...))`; delete the `{#if !runsChart.empty}<figure data-glance-chart="runs">...</figure>{/if}` block; below the `data-glance` auto-grid of `KpiCard`s add `<figure class="panel mt-4" data-glance-chart="run-yield"><RunYield days={<the day-metrics window the page already derives>} window={viewport} width={0} height={220} tickDensity={tickDensity} /></figure>` (`width={0}` lets `observeWidth` measure full width).

Data path stays bounded (Guardrail #12): `dayMetrics()` opens exactly one file per windowed date, never a glob; D3 is a three-cell widening of that read - 0 new files, 0 new bytes (Carmack).

### 4.7 The growing read (Guardrail #12), with the number

`published_days()` globs the whole committed tree and no prune deletes a `digest.json`, so the full sweep parses every committed day - documented beside `run_publication_checks` because a contract change can invalidate any frozen day. Measured 0.45 s / 18 days / 19.87 MB (2026-09-08, i7-1265U) = 44 MB/s; today 36 days / 30.5 MB -> ~0.69 s; at the 727-day 1 GB-Pages-cap horizon ~645 MB -> ~15 s laptop, ~30-60 s on the 4-vCPU runner = **360-1440x margin** against the 6 h job. `digest.yml` is `--day`-scoped and parses one day; only `ci.yml` and `backfill.yml` sweep, and `ci.yml` already runs the full backend suite, so the sweep is noise (Carmack). Add the entry to `docs/concepts/growing-reads.md` in D2.

### 4.8 The plan-53 compliance rule

Three rules; first match wins; the worker never chooses. The test: **does the plan-54 diff make plan 53 rename one more symbol, or one fewer?**

- **B1 - adds or keeps** a read/write/type/member of a symbol plan 53 renames or removes: **forbidden.** Use the post-53 name and add a cross-plan `Depends-on` on the row that mints it (why D2 types `Check.ledger: LedgerName` and waits for "One `LedgerName` for one ledger").
- **B2 - only deletes** the symbol (the D1 decom): **allowed, no dependency.** Delete whichever spelling exists at merge time; name targets by symbol (section 4.5), because the package row may have relocated them.
- **B3 - uses a name plan 53 keeps** (`write_segment`, `segment_contract`, `day_shards.settled_rows`): **free.** Reach it through the `idhazh.ledger` / `idhazh.day_shards` facade; never a private tree-shape map across the boundary.

## 5. The PR groups

### D1 - The day-validation receipt is decommissioned end to end [Level 5]

- **Scope:** remove the receipt, its ledger member/key/rule, retention, prune, and the committed `state/day-validations/` tree; stop the stage writing it. This also removes the live double-prune-claim (section 2). Delete-only (rule B2), by symbol (section 4.5).
- **Files touched:** section 4.5's list.
- **Acceptance gates:** local - the shared selector over `backend/tests/contracts`, the ledger/retention/prune tests, the schema-drift gate, `doc_load.py`; CI - full suite. **Level 5: owner sign-off before the first deletion (ESCALATE #1).**
- **Oracle:** a whole-tree search (`backend/`, `frontend/`, `config/`, `docs/`) finds zero `DayValidationReceipt`/`DAY_VALIDATION*`/`day-validations`/`LEDGER_DIRNAMES` references; the schema-drift gate is green; a prune test proves `state/day-validations/` is neither swept nor mis-claimed (it is gone). Cannot settle an out-of-tree consumer - there is none.
- **Decisions:** 1 Delete-only fixes the double-claim, no `_trial_roots` edit (Fowler). 2 Lands after plan 53's package row, before its config-registry row (Fowler; owner B3). 3 Level 5 (CLAUDE.md section 6).
- **Rejected alternatives:** 1 Add day-validations to `LEDGER_DIRNAMES` to fix the claim - the tree is being deleted; registering it is churn plan 53 reverts (cost: a one-line add plan 53 undoes) (Fowler). 2 Let plan 53's config-registry row remove it - it cannot leave the registry while the writer exists (cost: a circular cross-plan dependency) (Fowler; owner).

### D2 - The `check-publication` framework, the rename, and the live hook

- **Scope:** `validate_days.py` becomes the discovered `publication_checks/` package (4.1-4.4); the four checks move in (reconciliation fault-only; DAY checks date their faults); the day-shape check is dropped; `validate-days` becomes `check-publication` in `cli.py` and the three workflow callers atomically; the hook plus its one integration test (4.4).
- **Files touched:** `backend/idhazh/publication_checks/**` (new); `backend/idhazh/stages/validate_days.py` (deleted); `backend/idhazh/cli.py` (dispatch -> `run_publication_checks`, map `PublicationCheckError` to exit 2, drop the receipt-pairing guard); `.github/workflows/{ci,digest,backfill}.yml` (verb; keep `digest.yml`'s `--day`), `pages.yml` (comment); `backend/tests/workflows/_harness.py` (`VALIDATE_DAYS_CALL`/`VALIDATE_DAYS_JOBS`), `test_publish_ordering.py`; `backend/tests/contracts/test_committed_days.py`, `backend/tests/test_day_census.py`, `backend/tests/test_published_assets.py`; **`frontend/tests/malformed-day.spec.ts` (runs the verb live - line 211)**; comment-only refs in `test_two_calls.py`, `test_article_and_eval.py`, `test_eval_ledger.py`, `test_evals.py`, `test_render.py`, `frontend/scripts/build-state.ts`, `frontend/src/lib/assist/day.ts`, `frontend/src/lib/server/payload.ts`, `backend/idhazh/stages/rebuild_score_index.py`, `backend/utilities/migrate_to_day_shards.py`; docs `docs/architecture/publishing/frontend.md`, `docs/how-to/run-the-gates.md`, `docs/reference/github-actions.md`, the one-visual-one-file page, and the new publication-checks page + `docs/concepts/growing-reads.md`.
- **Acceptance gates:** local - the selector over `backend/tests/pipeline`, `backend/tests/workflows`, `backend/tests/contracts` and the moved checks' tests, plus the `malformed-day` spec; CI - full suite. Parity bar: fault messages identical over the canary day (section 4.3).
- **Oracle:** discovery bijection - `discover()` binds exactly `{projection, pictures, planned-items-reconciliation, console}`; the integration test lands and reads back one real `SpanRollupRow` through `write_segment` (the hook is live); a whole-tree search finds no `validate-days` reference.
- **Decisions:** 1 Day-shape check removed; runner per-day parse is the guarantee (Fowler; owner B4). 2 Hook kept, proven by one integration test; no production ledger consumer (owner). 3 `Check.ledger: LedgerName`; waits for "One `LedgerName` for one ledger" (rule B1). 4 Drop the CLI `--state-root`/`--digest-root` guard (Fowler). 5 Discovery follows the `council/registry.py` precedent (Carmack).
- **Rejected alternatives:** 1 Drop the hook - retires owner ruling B2 (cost: loses a proven-live capability; ~4 lines saved) (owner). 2 Type the hook `SegmentLedger` and land before the `LedgerName` row - reintroduces a symbol plan 53 removes (cost: a throwaway edit + a broken-tree window) (rule B1). 3 Register the four checks in a plain list - loses consistency with council and the discovery failures (cost: 4 hand-registrations that drift) (Fowler; Carmack).

### D3 - The run-yield chart replaces the donut

- **Scope:** widen `dayMetrics()` by three cells; add `run-yield.ts` (geometry) and `RunYield.svelte` (render); swap the donut for the full-width panel; delete the now-dead `runHealth`/`donut` (4.6). Frontend-only; no backend contract, no ledger vocabulary - independent of D1/D2 and both plans.
- **Files touched:** `frontend/src/lib/server/payload.ts`; `frontend/src/lib/charts/run-yield.ts` (new); `frontend/src/lib/components/RunYield.svelte` (new); `frontend/src/routes/console/+page.svelte`; `frontend/src/lib/charts/glance.ts` (delete `runHealth`) and `donut.ts` + its test (dead after the swap, or state why they stay); the `run-yield` logic test; the `dayMetrics` reader test.
- **Acceptance gates:** local - the frontend logic tests; CI - full suite. **Published-site change - owes the browser smoke (CLAUDE.md section 12), including the render-on-empty-`day_metrics` case.**
- **Oracle:** `runYield()` over a fixture window asserts one group per date, a broken line on a zero-planned day, the yield axis fixed [0,1], and a hatched gap on a missing day. Cannot settle whether the visual is good enough - Susan ruled it (met); Jony confirms on the page.
- **Decisions:** 1 One chart only (B1); grouped bars; fixed yield axis; readout not tooltip; built to the FailurePanels template (Susan). 2 Full-width panel below the KPI cards (Susan). 3 A new `run-yield.ts`/`RunYield.svelte` rather than extending the 726-line `glance.ts` (Carmack; per-chart module precedent). 4 Reads `day_metrics` via a three-cell widening; no new ledger (Fowler).
- **Rejected alternatives:** 1 Stacked bars - not a partition, a stack lies (cost: a misleading chart) (Fowler; Susan). 2 Add B2/B3/B4 here - three more cards make it a dashboard (cost: clutter) (Susan). 3 An ECharts option like the donut - cannot deliver the readout/gaps/keyboard (cost: reinventing FailurePanels' SVG) (Fowler).

### D4 - Closure and distillation

- **Scope:** stamp the Reckoner, distill any finding no page owns, delete the plan-doc.
- **Files touched:** this plan-doc (deleted at closure); any living doc a distilled finding lands on.
- **Acceptance gates:** local - `doc_load.py`; CI - full suite. Every Reckoner row `DONE`.
- **Oracle:** the Reckoner is all `DONE`, the plan-doc is gone, each distilled finding is on a living doc.
- **Decisions:** 1 Distillation is a row with a pull request (docs/how-to/distill-a-plan.md).
- **Rejected alternatives:** 1 Leave the plan-doc in `TODO/` - a closed plan rots against `docs/` (cost: a second source of truth) (CLAUDE.md section 10).

Execution stamp: run per docs/how-to/execute-a-plan.md as a workpool at Parallel N = 2; honour the cross-plan dependencies by title (section 1); D1 sits between plan 53's package row and its config-registry row; D2 waits for the `LedgerName` row; AUTHOR-AND-STOP until the user authorizes.
