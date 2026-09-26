# Plan 54 - Check-publication, the live ledger hook, and the day-validation decommission

**Last Updated**: 2026-09-26

**Level**: 5 for the decision, and per-row 3 except R4 which is 5 (CLAUDE.md section 6). Level 5 because R4 removes a persisted contract (`DayValidationReceipt`) and deletes a committed tree (`state/day-validations/`), and because the whole change restructures the one gate that stands between a broken published payload and a reader's browser.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

**Chain** (CLAUDE.md section 0d). **Intent**: a run validates everything it published through one discovered, extensible gate, and keeps no write-only receipt to skip that gate. **Contract**: section 4 declares every type, signature and destination a worker must not invent. **Code**: the six rows.

| Field | Value |
| --- | --- |
| Why this plan exists | `validate-days` bundles five checks and a write-only byte-count receipt under a name that describes one of them. This renames it `check-publication`, turns each check into a discovered plugin file, ships the plugin ledger hook live with reconciliation as its first real consumer, and decommissions the day-validation receipt the owner ruled wasteful. |
| Hard scope - in | see the bullets below |
| Hard scope - out | see the table below |
| ESCALATE triggers | see the enumerated list below |
| Chosen strategy | Rename to a discovered plugin framework, land the reconciliation ledger and its reader as the live hook's real consumer, then decommission the receipt end to end. Ruled by Fowler (CLAUDE.md section 14); the Level-5 forks are the owner's, dated 2026-09-26. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. **Parallel N = 2.** The critical path is R1 -> (R2 -> R4) -> R3 -> R5 -> R6; R2 and R4 share three files (`ledger.py`, `retention.py`, `stages/prune_state.py`) so they run serial, and the one disjoint pair is R3 and R4 after R2 lands (section 1). |
| Blocks | **Plan 53's row titled "One `LedgerName` for one ledger".** That row collapses `SegmentLedger` into `LedgerName` and cannot leave day-validations out of its registry while a `SegmentLedger.DAY_VALIDATIONS` writer still exists. Plan 54 R2 and R4 land first, so plan 53 reads a `SegmentLedger` that already dropped day-validations and gained reconciliation (section 4.5). A cross-plan pointer cites that plan's row by TITLE, never its number. |

### Hard scope - in

- `backend/idhazh/stages/validate_days.py` becomes the package `backend/idhazh/publication_checks/`: a discovered registry, a runner, and each check a plugin module under `checks/`.
- The verb `validate-days` becomes `check-publication` in `cli.py` and its three workflow callers, atomically.
- The standalone day-shape check is removed; the framework's per-day `DigestDay` parse is the guarantee (section 4.3, R1).
- The `Check.ledger` hook ships live, exercised by the reconciliation check writing one row a day (B2 decision, owner, 2026-09-26).
- The census check is renamed `planned-items-reconciliation` and gains a persisted per-day row and an operator reader.
- The day-validation receipt is decommissioned end to end: contract, ledger member, retention, prune, CLI surface, and the committed `state/day-validations/` tree.

### Hard scope - out

| Not here | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Hardening backfill's `model_copy(update=...)` to a validated construction | A committed day written by `backfill-vectors` is not re-validated at the write; a malformed one is caught at publication by the framework parse instead of at the write (section 4.3, finding A3) | Its own one-line pull request; it is defense-in-depth, not a gate |
| Enforcing `public_telemetry_keep_months` (the one unbounded console directory) | The console-payload check keeps reading one growing directory | Its own retention pull request; it is a pre-existing defect, not this plan's question |
| Any change to the served-projection, picture, or console checks' logic | Each moves verbatim into its own plugin file; the fault sentences are unchanged | A separate defect pull request if one of them is wrong |
| A per-check config declaration file (the gardener two-file shape) | A publication check has no runtime knob, so the config half has no beneficiary; the directory is the list | A check that genuinely needs a tunable, declared on the line that adds it (Guardrail #6) |
| The plan-53 `LedgerName` / `config/ledgers.json` vocabulary | Plan 54 uses today's `SegmentLedger`; plan 53 rewires it in its row-3 sweep (section 4.5) | Nothing - this is the deliberate ordering (F1) |

### ESCALATE triggers

1. **R4 begins - a persisted contract is removed and a committed tree is deleted.** Pause for the owner sign-off recorded in section 5.4 before the first deletion (CLAUDE.md section 6, Level 5).
2. **The reconciliation ledger would ship with no reader.** If R3 (the operator reader) is cut, the ledger is a write-only store repeating the day-validation mistake - stop and reopen the B2 exerciser choice (section 5.3 decision, finding J1).
3. **A committed-day writer is found that does not go through a validated `DigestDay`.** The framework parse still catches it at publication, but a new validated-write row is owed at that writer - surface it (section 4.3, finding A3).
4. **Plan 53's row "One `LedgerName` for one ledger" is about to land before plan 54 R2 and R4.** The ordering constraint has been violated - stop and resequence (finding J3).
5. **The CI full-sweep cost after R4 does not fit the runner budget.** R4 removes the per-day skip, so `check-publication` re-parses every retained committed day on the full sweep. It is bounded by retention, not unbounded, but Carmack confirms the cost (finding J2) - a confirmation, not a blocker.

## 1. Status Reckoner

One row is one pull request. **Six: five that change code and docs, and one that distills and closes.**

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The framework, the rename, and the three workflows | - | A | PENDING | - | - | - |
| 2 | The reconciliation ledger and the live hook | 1 | B | PENDING | - | - | - |
| 3 | The reconciliation reader | 2 | C | PENDING | - | - | - |
| 4 | Decommission the byte-count receipt | 1 | C | PENDING | - | - | - |
| 5 | The docs | 1, 2, 3, 4 | D | PENDING | - | - | - |
| 6 | Closure and distillation | 5 | E | PENDING | - | - | - |

**The critical path is R1 -> (R2 -> R4) -> R3 -> R5 -> R6.** R2 and R4 both edit `ledger.py`, `retention.py` and `stages/prune_state.py`, so they are not a disjoint pair and run serial - the same finding plan 53 reached about its own rows. The one real parallel pair is **R3 and R4 after R2 lands**: R3 edits only `backend/utilities/` and a test, R4 edits the ledger and contract surface, and their file sets are disjoint.

**R1 stops writing the receipt, R4 removes it.** R1's new framework has no receipt machinery, so the moment it lands nothing writes `state/day-validations/` again; R4 then removes an already-dead store (a clean strangler: stop-writing, then remove).

**Every row stamps its own Reckoner line in its own change** (execute-a-plan.md), so the plan-doc is in every row's real file set and is excluded from the disjointness diff.

## 2. The facts the contracts stand on

Load-bearing facts a worker relies on, verified against the tree at the current checkout:

- **There are exactly two writers of a committed `digest.json`.** `stages/assemble.py` (the normal path and the `previous_day` passthrough) and `stages/backfill_vectors.py`. Every other match reads it. Both go through a `DigestDay`; only the backfill path skips validation at the write, because `model_copy(update=...)` does not run validators (section 4.3, finding A3).
- **The receipt write is already gated on `state_dir is not None`.** `validate_days` writes receipts only when a state root is passed, so the CI full sweep (a `--digest-root` copy, no `--state-root`) writes nothing into real `state/`. The live hook keeps that exact gate (section 4.4).
- **The census rule is `not day.items and day.items_planned and not day.items_failed`.** A day that planned stories but published none and failed none has lost its plan; on the page it is indistinguishable from a quiet day (`_census_faults`).
- **`DigestDay.items_failed` is `int | None`.** `None` means the pre-2026-08-21 shape where the count was not recorded. The reconciliation row mirrors that nullability (section 4.2).
- **Three workflows call `validate-days`, not four.** `ci.yml/gates`, `digest.yml/assemble`, `backfill.yml/backfill` (from `VALIDATE_DAYS_JOBS` in `backend/tests/workflows/_harness.py`). `pages.yml` does not invoke it.
- **The frontend never reads `day-validations`.** No frontend contract copy, field-set test or vocabulary test moves in R4.
- **The one door is `ledger.write_segment`.** It files a row under the day its own `date` cell names; the live hook writes through it and invents no path (section 4.4).

## 3. The shape this plan builds

```
backend/idhazh/
    publication_checks/
        __init__.py           the facade the CLI reaches
        registry.py           Check, CheckScope, CheckResult; discover() and bind()
        runner.py             parse each day once; run every check; honour the ledger hook
        checks/
            projection.py      DigestView.project per day  (was check 2)
            pictures.py        picture collisions/missing/orphans  (was check 3)
            reconciliation.py  planned-items reconciliation  (was census, check 4)
            console.py         console payloads read back through their shapes  (check 5)
    contracts/
        reconciliation.py     PlannedItemsReconciliationRow
backend/utilities/
    reconciliation_report.py   the bounded-window reader (R3)

removed by R4:
    backend/idhazh/contracts/day_validation.py        DayValidationReceipt
    state/day-validations/                            the committed receipts
    backend/tests/pipeline/test_frozen_days.py        the receipt's tests
```

The day-shape check (check 1) has no plugin file: the runner's per-day `DigestDay` parse is its replacement (section 4.3).

## 4. The contracts a worker must not invent

### 4.1 The plugin interface - `backend/idhazh/publication_checks/registry.py`

Plain code, not a `contracts/` model: the interface is in-process wiring, not a persisted payload (Guardrail #3 scopes contracts to persisted payloads).

```python
class CheckScope(StrEnum):
    DAY = "day"     # run(ctx: DayContext)  - once per committed day, on the parsed payload
    TREE = "tree"   # run(ctx: TreeContext) - once over the whole published tree

class CheckResult(NamedTuple):
    faults: list[str]
    rows: tuple[Contract, ...] = ()   # empty unless the check declares a ledger

@dataclass(frozen=True)
class Check:
    name: str                                     # self-descriptive, unique in the package
    scope: CheckScope
    run: Callable[[DayContext | TreeContext], CheckResult]
    ledger: SegmentLedger | None = None           # today's type; plan 53 rewires to LedgerName (4.5)
```

Each `checks/` module declares a module-level `CHECK: Final[Check]` (or `CHECKS` tuple). `discover()` does one sorted depth-one walk of `checks/`, imports each module, reads its declaration, and binds by `Check.name`. The directory is the list - no index module enumerates the checks. No config string resolves to a callable.

**The four discovery failures, all exit 2, all before any check runs:**

1. a `checks/` module raises on import - name it, re-raise the traceback.
2. a non-underscore `checks/` module declares no `Check` of the right type - name it.
3. two modules declare one `Check.name` - name the name and both modules; never last-one-wins.
4. a `Check.ledger` names a ledger with no `_TREE_SHAPES` entry (post-53: no `live` registry entry) - a mis-wired hook fails the build, not the write.

### 4.2 The reconciliation row - `backend/idhazh/contracts/reconciliation.py`

Mirrors `DayValidationReceipt`: same `Contract` base, same day-keyed CSV shape.

```python
class PlannedItemsReconciliationRow(Contract):
    # __schema_stem__ = "planned-items-reconciliation-row"
    date: DateStamp        # the UTC day this row is about, YYYY-MM-DD
    planned: int           # day.items_planned      (ge=0)
    published: int         # len(day.items)         (ge=0)
    failed: int | None     # day.items_failed; None mirrors DigestDay = count not recorded
    balances: bool         # NOT (planned > 0 and published == 0 and (failed or 0) == 0)
```

`version` is a single dated `__changelog__` entry, "new contract" (CLAUDE.md section 11). `csv_columns`/`csv_row`/`from_csv_row` mirror `DayValidationReceipt`.

### 4.3 The day-shape guarantee, writer-independent

The runner parses every committed day into `DigestDay` once, before any DAY check runs, and a parse failure is a framework-level fault. This subsumes the standalone day-shape check no matter how the bytes reached disk. It is stronger than trusting the writers: `backfill_vectors.py` writes through `model_copy(update=...)`, which does not run validators (finding A3), so "all writers validate" is false - "the reader parses" is what holds.

### 4.4 The live hook - `backend/idhazh/publication_checks/runner.py`

```python
registry = discover()
day_ctx = _parse_each_committed_day(digest_root)    # the day-shape guarantee (4.3)
for check in registry:
    result = check.run(day_ctx if check.scope is CheckScope.DAY else tree_ctx)
    faults.extend(result.faults)
    if check.ledger is not None and state_dir is not None:
        ledger.write_segment(
            state_dir, check.ledger, result.rows,
            run_id=run_id, attempt=run_attempt, job=ServerJob.ASSEMBLE, shard=0,
        )
    else:
        assert not result.rows        # a check with no ledger must return no rows
```

The persist path is gated on `state_dir is not None`, the exact gate the receipt write uses: the daily publish path (`--state-root` present) persists one row for `--day`; the CI full sweep (no `--state-root`) writes nothing. The write goes through the one door and invents no filename.

### 4.5 Reconciliation and day-validations in today's `SegmentLedger`

R2 and R4 edit today's `ledger.py`:

- R2 adds `SegmentLedger.PLANNED_ITEMS_RECONCILIATION = "planned-items-reconciliation"`, its `_TREE_SHAPES` entry `(("date",), PlannedItemsReconciliationRow)`, and a newest-wins `_PREFERENCES` rule mirroring `_day_validation_rule` (a re-encoded day supersedes its earlier reconciliation).
- R4 removes `SegmentLedger.DAY_VALIDATIONS`, its `_TREE_SHAPES` entry, `DAY_VALIDATION_KEY`, `DAY_VALIDATION_RULE` and `DAY_VALIDATIONS_DIRNAME`.

Both land before plan 53's `SegmentLedger` -> `LedgerName` collapse, so that collapse naturally drops day-validations and picks up reconciliation, and writes the `config/ledgers.json` entry at `state: live` (finding J3, F1).

### 4.6 Retention

R2 adds `planned_items_reconciliation_keep_months` (default 14, `ge=1`) to `RetentionConfig`, `retention.prune_planned_items_reconciliation`, and `prune_state._prune_planned_items_reconciliation_shards`, each mirroring the day-validation twin. R4 removes `day_validation_keep_months` and its prune. Net: one retention path swapped for a near-identical one, plus a config regen (the removed key).

## 5. The rows

### Row #1 - The framework, the rename, and the three workflows

- **Scope:** `validate_days.py` becomes the discovered `publication_checks/` package; the four surviving checks move into `checks/` verbatim; the day-shape check is removed (the runner parse replaces it); `validate-days` becomes `check-publication` in `cli.py` and the three workflow callers atomically. Reconciliation ships here with `ledger=None` (faults only).
- **Files touched:** `backend/idhazh/publication_checks/**` (new); `backend/idhazh/stages/validate_days.py` (deleted); `backend/idhazh/cli.py`; `.github/workflows/ci.yml`, `.github/workflows/digest.yml`, `.github/workflows/backfill.yml`; `backend/tests/workflows/_harness.py`, `backend/tests/workflows/test_publish_ordering.py`; the four checks' existing tests re-pointed at the new import paths.
- **Acceptance gates:** local - the shared test selector over `backend/tests/pipeline`, `backend/tests/workflows` and the moved checks' tests; CI - full suite. Behaviour parity is the bar: `check-publication` over the canary day returns the same faults `validate-days` did over the same day.
- **Oracle:** discovery bijection - `discover()` binds exactly the four checks in `checks/`, and `check-publication` over the canary day is fault-identical to `validate-days` over that day. It cannot settle whether a future check is discovered (only today's four exist).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The day-shape check is removed; the runner's per-day `DigestDay` parse is the guarantee | Fowler; owner (B4), 2026-09-26 |
  | 2 | The rename touches `cli.py` and all three workflows in one row, atomically | Fowler |
  | 3 | Verb `check-publication`, package `publication_checks` | owner (B1), 2026-09-26 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep the day-shape check as a plugin | It re-validates what the runner parse already proved | A redundant plugin file and one more fault path | Fowler |
  | 2 | A per-check `config/` declaration (gardener two-file shape) | A publication check has no runtime knob; the directory is the list | A config file per check with no reader | Fowler |
  | 3 | Rename the verb but leave the checks in one module | Reintroduces the file that answered five questions | The 1a smell this plan removes | Fowler |

### Row #2 - The reconciliation ledger and the live hook

- **Scope:** `PlannedItemsReconciliationRow`; today's `SegmentLedger.PLANNED_ITEMS_RECONCILIATION` with its tree-shape and newest-wins preference; the retention knob and prune; the `CheckResult` `(faults, rows)` return and the runner persist path; `reconciliation.py` sets `ledger=` and emits its row. B2 lands here - live, real, no mock.
- **Files touched:** `backend/idhazh/contracts/reconciliation.py` (new); `backend/idhazh/contracts/__init__.py`, the contract export/registry; `backend/idhazh/ledger.py`; `backend/idhazh/contracts/knobs/retention.py`; `backend/idhazh/retention.py`; `backend/idhazh/stages/prune_state.py`; `backend/idhazh/publication_checks/runner.py`, `backend/idhazh/publication_checks/checks/reconciliation.py`; `config/idhazh.json` (the new knob); the schema fixtures.
- **Acceptance gates:** local - the selector over `backend/tests/contracts`, `backend/tests/pipeline` and the retention tests; CI - full suite. The live persist path is proven by a real one-door write into a scratch state dir, no mock (Guardrail #7).
- **Oracle:** a reconciliation run over a fixture day writes a row that reads back byte-equal via `day_shards.settled_rows` through `write_segment`, and a second run over a re-encoded day supersedes it (newest wins). It cannot settle the CI full-sweep cost (finding J2).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `failed: int \| None`, mirroring `DigestDay.items_failed`; `balances` treats `None` as 0 | Fowler (B1) |
  | 2 | `run` returns `CheckResult = (faults, rows)`; a check with no ledger returns no rows | Fowler (D1) |
  | 3 | Key `("date",)`, newest-wins preference, retention knob default 14 | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | `failed: int` (coerce `None` to 0) | Loses "zero failures" vs "not recorded" | One irreversible read of old days as zero-failure | Fowler |
  | 2 | Carry a `validator_version` like the receipt | Reconciliation re-reads fresh every run; nothing to invalidate | A field with no reader | Fowler |
  | 3 | A second `Check.rows(...)` method beside `run` | Two call sites to keep in step for one parse | Duplicate wiring, no benefit | Fowler |

### Row #3 - The reconciliation reader

- **Scope:** `backend/utilities/reconciliation_report.py`, a read-only operator reporter printing per-day planned/published/failed/balances over a bounded window, so the ledger is never write-only.
- **Files touched:** `backend/utilities/reconciliation_report.py` (new); its test under `backend/tests`.
- **Acceptance gates:** local - the selector over the new test; CI - full suite. The reader opens only the day files inside its window.
- **Oracle:** the reporter over a fixture state dir reads a bounded window and opens only the day files that window names - never the whole tree (Guardrail #12). It cannot settle the reader's usefulness to a human operator.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Ship the ledger AND its reader (C1); the reader is the Guardrail-12 projection of "publish rate this month" that `digest.json` can only answer by a growing walk | owner (J1), 2026-09-26 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Ship the ledger with no reader (audit-by-hand) | It is the day-validation write-only mistake wearing a new name | Zero code now, a store nothing reads later | Fowler; owner |
  | 2 | Persist nothing, fault only | Removes the live consumer the owner chose to exercise the hook | Reopens the B2 exerciser choice | Fowler; owner |

### Row #4 - Decommission the byte-count receipt

- **Scope:** remove the day-validation receipt end to end: contract, ledger member, key, rule, dirname, retention, prune, the committed `state/day-validations/` tree, and the receipt tests.
- **Files touched:** `backend/idhazh/contracts/day_validation.py` (deleted); `backend/idhazh/contracts/__init__.py` and the contract export; `backend/idhazh/ledger.py`; `backend/idhazh/retention.py`; `backend/idhazh/stages/prune_state.py`; `backend/idhazh/contracts/knobs/retention.py`; `config/idhazh.json`; `state/day-validations/` (deleted); `backend/tests/pipeline/test_frozen_days.py` (deleted); the ledger closed-world tests (`test_worker_ledgers.py`, ledger-staging) that name day-validations; the schema fixtures.
- **Acceptance gates:** local - the selector over `backend/tests/contracts`, the retention and ledger tests; CI - full suite plus the schema-drift gate. **Level 5: pause for the owner sign-off in this row's decision before the first deletion.**
- **Oracle:** after the row, a repository search finds zero references to `DayValidationReceipt`, `DAY_VALIDATION*` or `day-validations` across `backend/`, `config/` and `docs/`, and the schema-drift gate is green. It cannot settle an out-of-tree consumer - there is none (the frontend never read it).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Remove the receipt in this plan, not plan 53; land before plan 53's `LedgerName` collapse (F1) | owner (B3), 2026-09-26 |
  | 2 | Level 5 - persisted-contract removal plus committed-tree deletion; sign off before deletion | CLAUDE.md section 6 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Let plan 53 remove day-validations | Day-validations cannot leave plan 53's registry until its writer is gone; contradicts plan 53's brief | A circular cross-plan dependency | Fowler; owner |
  | 2 | Keep the receipt as a skip cache | Owner ruled it wasteful; it is committed growth for a 0.45s save | The write-only store this plan removes | owner, 2026-09-26 |

### Row #5 - The docs

- **Scope:** the contracts register drops the receipt and adds the reconciliation row; a publication-checks page describes the framework; day-validation references in code comments are removed.
- **Files touched:** `docs/architecture/contracts/schemas.md`; `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/concepts/telemetry.md`, `docs/concepts/adaptive-pruning.md`; `docs/reference/agent-notes/gates-and-builds.md`; a new publication-checks page under the right tier; `backend/idhazh/contracts/visual_data.py` and `backend/idhazh/render/write.py` comment references.
- **Acceptance gates:** local - `python backend/utilities/doc_load.py` and the link check; CI - full suite. No doc references `validate-days` or `day-validations`.
- **Oracle:** `doc_load.py` is green and a search finds no surviving `validate-days`/`day-validations` reference in `docs/` or code comments. It cannot settle prose quality.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The publication-checks framework gets one new page; the receipt's pages are edited in place | Fowler; documentation-structure.md |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Fold the framework into an existing page | It answers a new question and earns its own page | A page answering two questions | documentation-structure.md |

### Row #6 - Closure and distillation

- **Scope:** stamp the Reckoner, distill any finding no page owns onto its living doc, delete the plan-doc (the plan-53 row-7 pattern).
- **Files touched:** `TODO/20260926-54-check-publication-plan.md` (deleted at closure); any living doc a distilled finding lands on.
- **Acceptance gates:** local - `doc_load.py`; CI - full suite. Every Reckoner row is `DONE`.
- **Oracle:** the Reckoner is all `DONE`, the plan-doc is gone, and each distilled finding is on a living doc. It cannot settle a finding nobody wrote down.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Distillation is a row with a pull request, per docs/how-to/distill-a-plan.md | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave the plan-doc in `TODO/` | A closed plan is a cache that rots against `docs/` | A second source of truth | CLAUDE.md section 10 |

Execution stamp: run per docs/how-to/execute-a-plan.md at Parallel N = 2; AUTHOR-AND-STOP until the user authorizes.
