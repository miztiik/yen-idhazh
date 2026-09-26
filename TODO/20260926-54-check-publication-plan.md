# Plan 54 - Check-publication: a discovered validation framework, the live ledger hook, and the day-validation decommission

**Last Updated**: 2026-09-26

**Level**: 5 for the decision, and per PR-group 3 except PR-2 which is 5 (CLAUDE.md section 6). Level 5 because PR-2 removes a persisted contract (`DayValidationReceipt`) and deletes a committed tree (`state/day-validations/`), and because the whole change restructures the one gate that stands between a broken published payload and a reader's browser.

Execute per docs/how-to/execute-a-plan.md as a **workpool**: a group is ready when its `Depends-on` are DONE and its files are disjoint from every in-flight group; realistic **Parallel N = 1** (section 1). Consult a persona only where two answers lead to different code. AUTO-merge on green gates. Honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

**Chain** (CLAUDE.md section 0d). **Intent**: a run validates everything it published through one discovered, extensible gate, keeps no write-only receipt to skip that gate, and proves the gate's ledger hook with live, real, un-mocked code. **Contract**: section 4 declares every type, signature, body and destination a worker must not invent. **Code**: the four PR-groups.

| Field | Value |
| --- | --- |
| Why this plan exists | `validate-days` bundles five checks and a write-only byte-count receipt under a name that describes one of them. This renames it `check-publication`, turns each check into a discovered plugin file, ships the plugin ledger hook live, and decommissions the day-validation receipt the owner ruled wasteful. |
| Hard scope - in | see the bullets below |
| Hard scope - out | see the table below |
| ESCALATE triggers | see the enumerated list below |
| Chosen strategy | Extract a discovered plugin framework (structural), then swap the day-keyed ledger atomically and wire the live hook (behavioural), then a reader, then close. Ruled by Fowler (CLAUDE.md section 14); the Level-5 fork in section 0a is the owner's, dated 2026-09-26. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md, as a workpool. **Parallel N = 1.** The critical path funnels through `ledger.py` and the contract registry, so no two groups have disjoint file sets once PR-2 folds the ledger swap; N=2 buys no wall-clock on one 4-vCPU box and each PR pays one full CI run. |
| Blocks | **Plan 53's row titled "One `LedgerName` for one ledger".** That row collapses `SegmentLedger` into `LedgerName` and cannot leave day-validations out of its registry while a `SegmentLedger.DAY_VALIDATIONS` writer still exists. PR-1 and PR-2 land first, so plan 53 reads a `SegmentLedger` that already dropped day-validations and gained reconciliation. A cross-plan pointer cites that plan's row by TITLE, never its number. |

### Hard scope - in

- `backend/idhazh/stages/validate_days.py` becomes the discovered package `backend/idhazh/publication_checks/`: a registry, a runner, and each check a plugin under `checks/`.
- The verb `validate-days` becomes `check-publication` in `cli.py` and its three workflow callers, atomically.
- The standalone day-shape check is removed; the runner's per-day `DigestDay` parse is the writer-independent guarantee (section 4.2).
- The `Check.ledger` hook ships live and real - no mock, no deferral (owner B2, 2026-09-26) - subject to the one shape decision in section 0a.
- The census check is renamed `planned-items-reconciliation`.
- The day-validation receipt is decommissioned end to end: contract, ledger member, retention, prune, CLI guard, and the committed `state/day-validations/` tree.

### Hard scope - out

| Not here | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Hardening `backfill_vectors`' `model_copy(update=...)` to a validated construction | A day written by backfill is not re-validated at the write; a malformed one is caught at publication by the runner parse instead of at the write | Its own one-line pull request; it is defense-in-depth, not a gate |
| Enforcing `public_telemetry_keep_months` (the one unbounded console directory the console check reads) | The console check keeps reading one growing directory | Its own retention pull request; pre-existing, not this plan's question |
| Changing the projection, picture or console checks' logic | Each moves verbatim into its plugin file; the fault sentences are unchanged (the PR-1 parity bar) | A separate defect pull request if one is wrong |
| A per-check config declaration file | A publication check has no runtime knob; the directory is the list | A check that needs a tunable, declared on the line that adds it (Guardrail #6) |
| The plan-53 `LedgerName` / `config/ledgers.json` vocabulary | Plan 54 uses today's `SegmentLedger`; plan 53 rewires it in its row-3 sweep | Nothing - this is the deliberate ordering |
| Bounding the committed digest tree | The full-sweep re-parse cost grows one day per day (a documented Guardrail #12 read, section 4.9); measured to fit the 6 h job with 35-100x margin | A separate retention design; the tree's real ceiling is the 1 GB Pages cap, not this plan |

### ESCALATE triggers

1. **Section 0a is unresolved when PR-2 is ready to open.** The owner has not chosen between shipping the reconciliation ledger (option A, baked) and proving the hook with a live integration write and no production ledger (option B, recommended). PR-2's shape depends on it - pause.
2. **PR-2 begins** - a persisted contract is removed and a committed tree is deleted. Pause for owner sign-off before the first deletion (Level 5).
3. **A committed-day writer is found that does not go through a validated `DigestDay`.** The runner parse still catches it at publication, but a validated-write row is then owed at that writer - surface it.
4. **Plan 53's row "One `LedgerName` for one ledger" is about to land before plan 54 PR-1 and PR-2.** The ordering constraint is violated - stop and resequence.
5. **The reconciliation write is about to persist on a full sweep** (any run without `--day`). The persist discriminator is `only` (the `--day` list), never `state_dir`; a full-sweep persist writes one file per committed day and `backfill.yml`/`digest.yml` stage `state` whole - an archive-sized committed diff (Guardrail #12). Section 4.2's runner is the guard.

## 0a. Open owner decision - the hook's live consumer (resolve before PR-2)

**Situation.** The owner ruled the `Check.ledger` hook ships live, real, no mock, today (B2), and the earlier draft chose the reconciliation check as its consumer, persisting one row a published day and reading it back through an operator report.

**Problem.** `DayMetrics` already persists `items_published`, `items_planned` and `items_failed` per published day - one committed JSON file per day, windowed and console-read ([backend/idhazh/contracts/day_metrics.py](../backend/idhazh/contracts/day_metrics.py)). The reconciliation row's persisted columns reduce to `(version, date, planned, published, failed)` - those three numbers plus a stamp, and nothing novel (`balances` is derived, section 4.4). So the ledger is a second writer of three numbers already committed, and the reader is a second reader of a fact `DayMetrics` already serves. The census **fault** is genuinely needed and is not in question; only the persisted **row** and its reader are.

**Impact.** Option A ships a contract, a ledger, a `LEDGER_DIRNAMES` entry, a preference rule, a retention knob, a prune path and an operator reader to persist data that already exists. Option B ships the hook's persist path as real, exercised, un-mocked code proven by one integration test, and defers the first production consumer until a check needs a fact `DayMetrics` lacks.

| Table A - the hook's live consumer | id | What ships | Honours "live, real, no mock, today" | Cost |
| --- | --- | --- | --- | --- |
| baked default | A1 | reconciliation writes one row a published day + the operator reader (PR-2 + PR-3) | Fully - a production row on every daily run | A ledger that is a strict subset of `DayMetrics`; two writers of three numbers that can drift; a nullable-CSV `failed`; ~14 months of redundant rows. The reader is mandatory - dropping it while keeping the write is the write-only day-validations mistake (ESCALATE #1 of the receipt era) |
| **recommended** | A2 | the runner persist path (real) + one integration test writing a real row through `write_segment` and reading it back; reconciliation stays `ledger=None` (fault only); first production consumer deferred | Yes - the persist path is real, exercised, proven today; no stub | No production row yet. Narrows "reconciliation writes daily" to "an integration test writes." Removes the duplicate ledger, its reader and the drift surface. **The narrowing is the owner's to make** (section 0d) |

**Recommendation: A2** (Fowler, Carmack converged). The cheapest consumer is the one not built; a capability earns a production consumer when a check needs to persist a fact `DayMetrics` lacks. **Baked in this plan: A1**, the owner's standing ruling, so the plan is executable as written. **If the owner takes A2:** delete `contracts/reconciliation.py`, the `PLANNED_ITEMS_RECONCILIATION_*` ledger constants/member/shape/rule/`LEDGER_DIRNAMES` entry, the retention knob and prune, and PR-3 entirely; keep section 4.1-4.2 and add the one integration test from section 4.7. PR count drops 4 -> 3.

## 1. Status Reckoner

One PR-group is one pull request. **Four (baked A1): two that change code, one reader, one that closes.** Docs fold into the group that makes them true (CLAUDE.md section 9), so there is no standalone docs PR.

| # | Row (PR group) | Depends-on | Files-disjoint-from | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The framework, the rename, and the three workflows | - | - | PENDING | - | - | - |
| 2 | The day-keyed ledger swap (reconciliation in, receipt out) | 1 | - | PENDING | - | - | - |
| 3 | The reconciliation reader | 2 | - | PENDING | - | - | - |
| 4 | Closure and distillation | 3 | - | PENDING | - | - | - |

**The critical path is 1 -> 2 -> 3 -> 4, serial.** PR-2 folds what a naive split would call two rows (add reconciliation, remove the receipt): they share seven files (`ledger.py`, `retention.py`, `knobs/retention.py`, `prune_state.py`, `contracts/__init__.py`, `config/idhazh.json`, the fixtures), so they were never a disjoint pair, and folding is the only shape in which the `("date",)` key collision (section 4.5) is never committed. **Workpool with N=1**: each group runs when the previous merges; N>1 buys nothing because every group funnels through `ledger.py` or the contract registry, and each PR pays one full CI run regardless.

**Every group stamps its own Reckoner line in its own change** (execute-a-plan.md), so the plan-doc is in every group's real file set and is excluded from the disjointness diff.

## 2. The facts the contracts stand on

Verified against the tree at the current checkout:

- **The digest tree is unbounded.** `published_days()` globs `*/*/*/digest.json` with no window, and no prune deletes a `digest.json`. The full sweep is a Guardrail #12 growing read, priced and documented (section 4.9); its ceiling is the 1 GB Pages cap (~727 days), not the 6 h job.
- **The CLI never passes `state_dir=None`.** `cli.py` sets `state_dir = common.STATE_ROOT if args.state_root is None else args.state_root`. What keeps a CI full sweep from committing state is that **CI does not commit** - not a `None` gate. So the reconciliation persist discriminator is `only` (the `--day` list), never `state_dir` (section 4.2).
- **There are exactly two writers of a committed `digest.json`:** `assemble.py` (the normal path and the `previous_day` passthrough, both validated) and `backfill_vectors.py` (`model_copy(update=...)`, which does not run validators). So "all writers validate" is false; the runner's parse is the guarantee (section 4.2).
- **`DayMetrics` already carries `items_published`/`items_planned`/`items_failed` per published day**, committed, windowed, console-read - which is what makes section 0a a real decision.
- **`DigestDay.items_failed` is `int | None`** (`None` = the pre-2026-08-21 shape). The reconciliation row mirrors that nullability and round-trips an empty CSV cell (section 4.4).
- **`SegmentLedger` values are `*_DIRNAME` constants, not string literals**, and a ledger must be in `LEDGER_DIRNAMES` or the trial-root pruner empties it at 90 days. `day-validations` is itself absent from `LEDGER_DIRNAMES` today - a latent bug PR-2 erases by removing the ledger (section 4.5).
- **`BY_STEM` is auto-derived** from `CONTRACTS`; adding or removing a contract needs a committed byte-identical fixture directory, no manual `BY_STEM` edit (section 4.7).
- **Three workflows call `validate-days`** (`ci.yml`, `digest.yml`, `backfill.yml`); `pages.yml` only names it in a comment. The frontend never reads `day-validations`.

## 3. The shape this plan builds

```
backend/idhazh/
    publication_checks/
        __init__.py           the facade the CLI reaches (binds run_publication_checks, PublicationCheckError)
        registry.py           Check, CheckScope, CommittedDay, DayContext, TreeContext, CheckResult; discover(), validate_registry()
        runner.py             run_publication_checks(): parse each day once; run every check; honour the ledger hook
        checks/
            projection.py     DigestView.project per day      (was check 2)
            pictures.py       picture collisions/missing/orphans (was check 3)
            reconciliation.py planned-items reconciliation      (was census, check 4; emits a row under option A1)
            console.py        console payloads via their shapes (check 5)
    contracts/
        reconciliation.py     PlannedItemsReconciliationRow          (A1 only)
backend/utilities/
    reconciliation_report.py  the bounded-window operator reader      (A1 only; PR-3)

removed by PR-1:
    backend/idhazh/stages/validate_days.py            the stage (its receipt code dies here)
    backend/tests/pipeline/test_frozen_days.py        receipt-only tests
removed by PR-2:
    backend/idhazh/contracts/day_validation.py        DayValidationReceipt
    state/day-validations/                            the committed receipts
```

The day-shape check (check 1) has no plugin file: the runner's per-day `DigestDay` parse replaces it (section 4.2).

## 4. The contracts a worker must not invent

Paste-ready. Every block is grounded in the file it derives from.

### 4.1 The plugin interface - `backend/idhazh/publication_checks/registry.py`

Plain code, not a `contracts/` model (the interface is in-process wiring, not a persisted payload).

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
from idhazh.ledger import CsvRecord, SegmentLedger, segment_contract

class PublicationCheckError(RuntimeError):
    """A framework wiring fault, raised before any check runs; the CLI maps it to exit 2."""

class CheckScope(StrEnum):
    DAY = "day"     # run(DayContext): the parsed committed days in scope
    TREE = "tree"   # run(TreeContext): the whole published tree, once

@dataclass(frozen=True)
class CommittedDay:
    date: str                 # YYYY-MM-DD off the path
    path: Path
    payload: bytes            # read once
    raw: dict[str, Any]       # json.loads(payload) - what DigestView.project reads
    day: DigestDay | None     # the validated model, or None when the JSON object fails digest-day

@dataclass(frozen=True)
class DayContext:
    digest_root: Path
    public_root: Path         # digest_root.parent - what _picture_faults reads
    days: tuple[CommittedDay, ...]

@dataclass(frozen=True)
class TreeContext:
    root: Path
    months: frozenset[str] | None   # {d[:7] for d in only} or None on a full sweep

class CheckResult(NamedTuple):
    faults: tuple[str, ...] = ()
    rows: tuple[CsvRecord, ...] = ()          # write_segment takes CsvRecord; empty unless the check declares a ledger

@dataclass(frozen=True)
class Check:
    name: str
    scope: CheckScope
    run: Callable[[DayContext | TreeContext], CheckResult]
    ledger: SegmentLedger | None = None       # plan 53 rewires the type to LedgerName

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
            segment_contract(check.ledger)                               # failure 4: no _TREE_SHAPES entry
        except KeyError as error:
            raise PublicationCheckError(
                f"{check.name} names ledger {check.ledger!r} with no _TREE_SHAPES entry") from error
```

### 4.2 The runner - `backend/idhazh/publication_checks/runner.py`

The persist gate keys on `only` (the `--day` list), never `state_dir`. Exit codes: `0` clean, `1` any fault, `2` a wiring fault (caught in `cli.py`).

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
    """The day-shape guarantee: every day in scope, parsed once, plus framework faults from
    days that will not parse. Reader-parses rather than trusting the writers."""
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
        # Persist only on a day-scoped run: digest.yml (--day) writes one row; the CI and backfill
        # full sweeps re-validate every day and persist nothing, so no archive-sized diff.
        if state_dir is not None and scoped:
            ledger.write_segment(state_dir, check.ledger, result.rows, run_id=run_id,
                                 attempt=run_context.run_attempt(), job=ServerJob.ASSEMBLE, shard=WHOLE_ARCHIVE_SHARD)
    for fault in faults:
        LOG.error("check-publication %s", fault)
    return 1 if faults else 0
```

### 4.3 The four checks as plugins

`projection.py`, `pictures.py`, `console.py` move their bodies verbatim from `validate_days.py` (`_picture_faults`+`assets_in_day`, `DigestView.project`, `_console_payload_faults`), each iterating `ctx.days` (DAY) or reading `ctx.root`/`ctx.months` (TREE) and prefixing every fault with the date - so fault sentences are byte-identical (the PR-1 parity bar). `console.py` calls `_console_payload_faults(ctx.root, ctx.months)`. Each declares `CHECK = Check(name=..., scope=..., run=..., ledger=None)`.

Reconciliation is the only changed body (option A1 - under A2 it stays `ledger=None` and emits no row):

```python
# backend/idhazh/publication_checks/checks/reconciliation.py
from idhazh.contracts.reconciliation import PlannedItemsReconciliationRow
from idhazh.ledger import SegmentLedger
from idhazh.publication_checks.registry import Check, CheckResult, CheckScope, DayContext

def _run(ctx: DayContext) -> CheckResult:
    faults, rows = [], []
    for d in ctx.days:
        if d.day is None:
            continue
        row = PlannedItemsReconciliationRow(
            version=PlannedItemsReconciliationRow.schema_version(),
            date=d.date, planned=d.day.items_planned or 0,
            published=len(d.day.items), failed=d.day.items_failed)
        rows.append(row)
        if not row.balances:
            faults.append(f"{d.date} planned {row.planned} stories and accounts for none of them: "
                          f"nothing published and nothing failed")
    return CheckResult(faults=tuple(faults), rows=tuple(rows))

CHECK = Check(name="planned-items-reconciliation", scope=CheckScope.DAY, run=_run,
              ledger=SegmentLedger.PLANNED_ITEMS_RECONCILIATION)
```

### 4.4 `PlannedItemsReconciliationRow` - `backend/idhazh/contracts/reconciliation.py` (A1 only)

`balances` is a derived property, not a column: the persisted columns are `(version, date, planned, published, failed)`. `failed` round-trips an empty CSV cell as `None`.

```python
from typing import ClassVar, Self
from pydantic import Field
from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp

class PlannedItemsReconciliationRow(Contract):
    """One published day's plan against what it published, for an operator to read back."""
    __schema_stem__: ClassVar[str] = "planned-items-reconciliation-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(version="2026-09-26",
            change="Initial shape: a day's planned and published counts, its failed count, and whether they balance.",
            why="The census check gained a persisted row so the Check.ledger hook has a live consumer."),
    )
    date: DateStamp = Field(description="The published day this row is about.")
    planned: int = Field(ge=0, description="DigestDay.items_planned - stories the day's runs planned.")
    published: int = Field(ge=0, description="len(DigestDay.items) - stories in the published set.")
    failed: int | None = Field(default=None, ge=0,
        description="DigestDay.items_failed - planned stories that never reached the digest. "
                    "None mirrors DigestDay: a day written before 2026-08-21 did not record it, and None is not zero.")

    @property
    def balances(self) -> bool:
        return not (self.planned > 0 and self.published == 0 and (self.failed or 0) == 0)

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {n: ("" if payload[n] is None else str(payload[n])) for n in self.csv_columns()}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        cells = {n: row[n] for n in cls.model_fields}
        if cells.get("failed") == "":
            cells["failed"] = None
        return cls.model_validate(cells)
```

### 4.5 The ledger swap - `backend/idhazh/ledger.py` (A1 only)

Add (mirrors the day-validation constants PR-2 removes):

```python
PLANNED_ITEMS_RECONCILIATION_DIRNAME: Final = "planned-items-reconciliation"
PLANNED_ITEMS_RECONCILIATION_KEY: Final = ("date",)
def _planned_items_reconciliation_rule(later: dict[str, str], kept: dict[str, str]) -> bool:
    return bool(later) or not kept   # newest wins: settlement walks a day's files oldest first
PLANNED_ITEMS_RECONCILIATION_RULE: Final[Preference] = _planned_items_reconciliation_rule
```

- `SegmentLedger`: add `PLANNED_ITEMS_RECONCILIATION = PLANNED_ITEMS_RECONCILIATION_DIRNAME` (value is the `*_DIRNAME` constant, per the enum's own rule).
- `_TREE_SHAPES`: add `SegmentLedger.PLANNED_ITEMS_RECONCILIATION: _TreeShape(PLANNED_ITEMS_RECONCILIATION_KEY, PlannedItemsReconciliationRow)`.
- `_PREFERENCES`: add `PLANNED_ITEMS_RECONCILIATION_KEY: PLANNED_ITEMS_RECONCILIATION_RULE`.
- `LEDGER_DIRNAMES`: **add** `PLANNED_ITEMS_RECONCILIATION_DIRNAME`, or the trial-root pruner empties `state/planned-items-reconciliation/` at 90 days.

PR-2 removes, in the same commit: the `DayValidationReceipt` import, `DAY_VALIDATIONS_DIRNAME`, `DAY_VALIDATION_KEY`, `_day_validation_rule`/`DAY_VALIDATION_RULE`, the `_PREFERENCES` entry, `SegmentLedger.DAY_VALIDATIONS`, and the `_TREE_SHAPES` entry. `day-validations` is not in `LEDGER_DIRNAMES`, so nothing is removed there.

**The `("date",)` collision:** `DAY_VALIDATION_KEY` and reconciliation's key are both `("date",)`, and `_PREFERENCES` is keyed by the tuple. Folding the add and the remove into PR-2 means `_PREFERENCES` never carries `("date",)` twice - the decisive reason PR-2 is one PR.

### 4.6 Retention and prune (A1 only)

- `knobs/retention.py`: replace `day_validation_keep_months` with `planned_items_reconciliation_keep_months: int = Field(default=14, ge=1, description="Months of reconciliation rows to keep; the operator report reads a bounded window of them.")`.
- `retention.py`: rename `prune_day_validations` -> `prune_planned_items_reconciliation`, swapping the dirname and knob; body otherwise identical.
- `prune_state.py`: rename `_prune_day_validation_shards` -> `_prune_planned_items_reconciliation_shards` and its call site.
- `config/idhazh.json`: swap the committed key. Swap it too in `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, whose invariant is that every knob differs from committed, or `test_app_config` goes red.

### 4.7 Contracts registry and fixtures

`BY_STEM` is auto-derived from `CONTRACTS` - no manual edit.
- **Add (A1, PR-2):** import `PlannedItemsReconciliationRow` in `contracts/__init__.py`, add it to `CONTRACTS` and `__all__`; create `tests/fixtures/contracts/planned-items-reconciliation-row/one.json` - a byte-identical round-trip fixture with a valid `version` and all fields, including a `failed` case that exercises the empty-cell round-trip.
- **Remove (PR-2):** delete the `DayValidationReceipt` import, its `CONTRACTS` and `__all__` entries, and `tests/fixtures/contracts/day-validation-receipt/`.
- **The live-hook integration test (both A1 and A2):** run the reconciliation check (A1) or a fixture check declaring the reconciliation ledger (A2) over a fixture day with a scratch `state_dir`; assert a real row lands under `state/planned-items-reconciliation/<Y>/<M>/<D>/<name>.csv` through a real `write_segment`, and reads back byte-equal through `day_shards.settled_rows`. No mock. This is the proof the hook is live.

### 4.8 CLI dispatch - `backend/idhazh/cli.py`

Replace the `validate-days` block. **Drop the `--state-root`/`--digest-root` pairing guard** - its reason (a receipt settling a scratch copy without opening it) dies with the skip. Keep the `--day`/`--digest-root`/`--state-root` args; rename their help text off `validate-days`.

```python
if args.stage == "check-publication":
    state_dir = common.STATE_ROOT if args.state_root is None else args.state_root
    try:
        return publication_checks.run_publication_checks(
            args.digest_root, args.day, state_dir=state_dir,
            run_id=plan_stage._run_id(args.date or _today(), args.execution))
    except publication_checks.PublicationCheckError as error:
        LOG.error("check-publication cannot run: %s", error); return 2
```

### 4.9 The growing read (Guardrail #12)

`published_days()` globs the whole committed tree, and no prune deletes a `digest.json`, so the full sweep parses every committed day. Document it beside `run_publication_checks`: it reads every committed day **because a contract change can invalidate any frozen day and a reader's browser fetches any of them, so a bounded input cannot answer "does every published day still match its contract."** The daily path scopes to `--day`. Cost record: fits the 6 h job with 35-100x margin at the 727-day site-cap horizon (~3-6 min). Add the entry to `docs/concepts/growing-reads.md` in PR-2's doc edits.

## 5. The PR groups

### PR-1 - The framework, the rename, and the three workflows

- **Scope:** `validate_days.py` becomes the discovered `publication_checks/` package (4.1, 4.2); the four checks move into `checks/` verbatim (4.3, reconciliation with `ledger=None`); the day-shape check is dropped (runner parse replaces it); `validate-days` becomes `check-publication` in `cli.py` and the three workflow callers atomically; the receipt-only `test_frozen_days.py` is deleted here, where the receipt code dies.
- **Files touched:** `backend/idhazh/publication_checks/**` (new); `backend/idhazh/stages/validate_days.py` (deleted); `backend/idhazh/cli.py` (dispatch 4.8, minus the reconciliation import until PR-2 - PR-1 lands reconciliation with `ledger=None` so no contract import yet); `.github/workflows/ci.yml`, `digest.yml` (keep `--day`), `backfill.yml`; `.github/workflows/pages.yml` (comment); `backend/tests/workflows/_harness.py` (`VALIDATE_DAYS_CALL`/`VALIDATE_DAYS_JOBS`), `test_publish_ordering.py`; `backend/tests/contracts/test_committed_days.py` (import + calls + verb), `backend/tests/test_day_census.py`, `backend/tests/test_published_assets.py` (imports -> checks + runner); comment-only refs in `test_two_calls.py`, `test_article_and_eval.py`, `test_eval_ledger.py`, `test_evals.py`, `test_render.py`; `backend/tests/pipeline/test_frozen_days.py` (deleted); the publication-checks framework doc page.
- **Acceptance gates:** local - the shared selector over `backend/tests/pipeline`, `backend/tests/workflows`, `backend/tests/contracts` and the moved checks' tests; CI - full suite. Parity bar: `check-publication` over the canary day is fault-identical to `validate-days` over that day.
- **Oracle:** discovery bijection - `discover()` binds exactly `{projection, pictures, planned-items-reconciliation, console}`, and `check-publication` over the canary day is fault-identical to the pre-change verb. Cannot settle whether a future check is discovered.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Day-shape check removed; runner per-day parse is the guarantee (writer-independent) | Fowler; owner (B4) |
  | 2 | Verb `check-publication`, package `publication_checks` | owner (A1/B1) 2026-09-26 |
  | 3 | Rename touches `cli.py` and all three workflows atomically; `pages.yml` comment with them | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep the day-shape check as a plugin | Re-validates what the runner parse proved | A redundant plugin + fault path | Fowler |
  | 2 | Split the rename across PRs | Leaves the tree non-compiling between them | A broken intermediate `main` | Fowler |

### PR-2 - The day-keyed ledger swap (reconciliation in, receipt out) [Level 5]

- **Scope (option A1):** add `PlannedItemsReconciliationRow` and its ledger member/shape/rule/`LEDGER_DIRNAMES` entry/retention/prune; wire `reconciliation.py` to emit its row and the runner to persist it on a day-scoped run; **remove the day-validation receipt end to end** and delete `state/day-validations/`. One atomic swap of the day-keyed ledger surface. **(Option A2: drop the reconciliation contract/ledger/knob/prune/reader; keep only the runner persist path + the live integration test; still remove the receipt.)**
- **Files touched:** `backend/idhazh/contracts/reconciliation.py` (new, A1); `backend/idhazh/contracts/day_validation.py` (deleted); `backend/idhazh/contracts/__init__.py`; `backend/idhazh/ledger.py`; `backend/idhazh/contracts/knobs/retention.py`; `backend/idhazh/retention.py`; `backend/idhazh/stages/prune_state.py`; `backend/idhazh/publication_checks/runner.py` and `checks/reconciliation.py`; `backend/idhazh/cli.py` (add the reconciliation import); `config/idhazh.json`; `tests/fixtures/contracts/planned-items-reconciliation-row/one.json` (new), `tests/fixtures/contracts/day-validation-receipt/` (deleted), `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`; `backend/tests/contracts/test_committed_days.py` (remove receipt assertions), `test_migrate_to_day_shards.py` (re-point the sample ledger name), the ledger closed-world and retention/prune tests; `state/day-validations/` (deleted); `docs/architecture/contracts/schemas.md`, `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/concepts/telemetry.md`, `docs/concepts/adaptive-pruning.md`, `docs/reference/agent-notes/gates-and-builds.md`; comment refs in `contracts/visual_data.py`, `render/write.py`.
- **Acceptance gates:** local - the selector over `backend/tests/contracts`, the ledger, retention and prune tests, plus the schema-drift gate and `doc_load.py`; CI - full suite. **Level 5: pause for owner sign-off (ESCALATE #1, #2) before the first deletion.**
- **Oracle:** the live-hook integration test - a real row written through `write_segment` reads back byte-equal through `day_shards.settled_rows`, and a re-encoded day supersedes it (newest wins); plus a repository search finding zero `DayValidationReceipt`/`DAY_VALIDATION*`/`day-validations` references in `backend/`, `config/`, `docs/`. Cannot settle the CI full-sweep cost (priced in 4.9).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `balances` is derived, not a column; persisted columns are `(version,date,planned,published,failed)` | Fowler |
  | 2 | `run` returns `(faults, rows)`; persist gate keys on `only`, not `state_dir` | Fowler |
  | 3 | Fold add + remove into one PR (the `("date",)` collision is never committed) | Fowler |
  | 4 | Drop the CLI `--state-root`/`--digest-root` guard (its reason dies with the skip) | Fowler |
  | 5 | Remove the receipt here, before plan 53's `LedgerName` collapse | owner (B3) 2026-09-26 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Persist `balances` as a column | A derived value is a drift surface | A stored bool to keep in step with three fields | Fowler |
  | 2 | Keep the receipt as a skip cache | Owner ruled it wasteful; committed growth for a ~0s CI saving | The write-only ledger this plan removes | owner 2026-09-26 |
  | 3 | Let plan 53 remove day-validations | It cannot leave the registry while its writer exists | A circular cross-plan dependency | Fowler; owner |

### PR-3 - The reconciliation reader (A1 only; removed under A2)

- **Scope:** `backend/utilities/reconciliation_report.py`, a read-only operator report printing per-day planned/published/failed/balances over a bounded window, so the ledger is never write-only.
- **Files touched:** `backend/utilities/reconciliation_report.py` (new); its test under `backend/tests`.
- **Acceptance gates:** local - the selector over the new test; CI - full suite. The report opens only the day files inside its window.
- **Oracle:** the report over a fixture state dir reads a bounded window and opens only the day files that window names, never the whole tree. Cannot settle operator usefulness.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Ship a reader so the ledger is not write-only (mandatory under A1) | owner (A1) 2026-09-26 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Ship the ledger with no reader | The write-only day-validations mistake renamed | Zero code now, a ledger nothing reads | Fowler; owner |
  | 2 | Read `day_metrics` instead of a new ledger | Under A1 the ledger exists; under A2 this is the point (section 0a) | Reopens section 0a | Carmack |

### PR-4 - Closure and distillation

- **Scope:** stamp the Reckoner, distill any finding no page owns onto its living doc, delete the plan-doc.
- **Files touched:** this plan-doc (deleted at closure); any living doc a distilled finding lands on.
- **Acceptance gates:** local - `doc_load.py`; CI - full suite. Every Reckoner row `DONE`.
- **Oracle:** the Reckoner is all `DONE`, the plan-doc is gone, each distilled finding is on a living doc. Cannot settle a finding nobody wrote down.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Distillation is a row with a pull request (docs/how-to/distill-a-plan.md) | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave the plan-doc in `TODO/` | A closed plan is a cache that rots against `docs/` | A second source of truth | CLAUDE.md section 10 |

Execution stamp: run per docs/how-to/execute-a-plan.md as a workpool at Parallel N = 1; resolve section 0a before PR-2; AUTHOR-AND-STOP until the user authorizes.
