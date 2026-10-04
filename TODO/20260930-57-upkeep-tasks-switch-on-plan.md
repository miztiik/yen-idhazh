# Plan 57 - The upkeep tasks switch on, each with the person's approval

**Last Updated**: 2026-10-02

**Level**: 4 (CLAUDE.md section 6). A file a live task deletes is gone for good once the history squash passes its commit (CLAUDE.md section 8), and a workflow run or artifact it deletes is gone at once. So a wrong switch costs more to undo than to make.

**Status**: written 2026-09-30, and no row has started. Rows 1 and 2 wait on rows of other plans (section 3).

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Every upkeep task only reports, except the corpus squash and the closed-day folds of four tasks. So the console's three packed ledgers stop at 2026-09-28, old traces and raw files stay, and no plan owns switching the rest on |
| Hard scope - in | - `dry_run: false` for `compact-scores` (row 1), and for `compact-gardener`, `compact-visual-prunes` and `compact-feed-retirements` (row 2).<br>- `dry_run: false` for each report-only retention or collection task the person approves (row 3).<br>- Each switch's `LIVE_BY_DECISION` entry, and every doc sentence the switch makes false |
| Hard scope - out | the table below |
| ESCALATE triggers | 1. A `dry_run` moving from `true` to `false`, or a window, series or `monthly_window` moving from `forever` to a bounded value, before the person approves that task. The first deletion a tree ever sees is the person's call, never an agent's ([docs/concepts/config/idhazh-gardener.md](../docs/concepts/config/idhazh-gardener.md)).<br>2. A row's precondition is false at dispatch.<br>3. The first scheduled wake after a merge fails the row's oracle. The owner sets that switch back to `true` in a pull request at once, then reports |
| Chosen strategy | Every switch is approved by the person first and read at the first upkeep wake after its merge. Packing lands in two pull requests, and each retention window in one of its own. The person, 2026-09-30 |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Every row edits `backend/tests/contracts/test_gardener_config.py` and `docs/concepts/config/idhazh-gardener.md`, and rows in flight may share no file, so one row is in flight at a time. Merge by hand: GitHub refuses auto-merge on this repository |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Packing `item-health` and `host-fingerprint` | Nothing to implement here: #1177 is merged | Row 2 still requires its first live wake to be read before more ledgers follow |
| The `visual-prune` switch | The rendered-chart cleanup keeps only reporting | Plan 13's row "The fuse comes out, and one run is watched" |
| A new window value, or a window moving from `forever` to bounded | A window the person thinks wrong stays as committed | The person names the new value in the answer to row 3's table, and that task's pull request carries it (ESCALATE trigger 1) |
| Known defect 53: eight flat trace files the `traces` task cannot date | They stay after `traces` goes live | Defect 53 in [20260823-known-defects-plan.md](20260823-known-defects-plan.md): one commit of eight renames |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The eval ledger is packed live, and every scores window stays forever | - | A | PENDING | - | - | - |
| 2 | The upkeep record, the picture cleanup's record and the feed retirements are packed live | - | A | PENDING | - | - | - |
| 3 | The retention windows the person approves go live, one task a pull request | - | A | PENDING | - | - | - |

Rows 1 and 2 also wait on rows of other plans (section 3). The plan-queue reader, `backend/utilities/plan_status.py`, cannot follow a pointer by title, so the owner checks those rows at dispatch.

## 2. How a switch is approved, landed and read

1. **Approval.** Before a row's branch is cut, the owner sends the person one message in the CLAUDE.md section 0c shape, with one lettered table. One line a task: what it owns, its window, what a live pass would delete at the next wake, and a recommendation. The numbers are the task's own row in the newest upkeep record - `selected`, `deleted`, `bytes_freed` and `until`, in the files of the newest day under `state/raw/gardener/`. The person answers by row id. No answer, no branch.
2. **One pull request a row, and one a task in row 3.** It holds each declaration's `dry_run`, its entry in `LIVE_BY_DECISION` in `backend/tests/contracts/test_gardener_config.py` with the reason in plain words and no plan number, and every doc sentence the switch makes false. The pull request body names the approval and its date. Step 5 of "Turning state cleanup on" in `docs/how-to/run-the-pipeline.md` asks for a commit that changes nothing else; it is older than that test, and the first row to merge corrects it.
3. **The doc sentences** are the hits of `git grep -n -i -E "report-only|only reports?\b|dry_run: true|ships in dry run|until a person turns|until they run live" -- docs` that name the task, re-run at dispatch.
4. **Merge window.** No `idhazh-gardener.yml` run is queued or running (`gh run list --workflow idhazh-gardener.yml --repo miztiik/yen-idhazh`), so the next wake is the first to read the switch.
5. **The oracle** is read in the commits of the first scheduled wake after the merge (`cron: '40 0 * * *'` in `.github/workflows/idhazh-gardener.yml`; GitHub often starts it later). A row is DONE at its merge, and a failed oracle reopens it under ESCALATE trigger 3.
6. **Ledger rows are read with `load_days`** in `backend/idhazh/ledger/ledger_files.py`, which reads each day from the one file that holds it: raw, day or month. A wake's commit for a task is the commit of the shard that ran it.

### Row #1 - The eval ledger is packed live, and every scores window stays forever

- **Scope:** `dry_run` in `config/gardener/compact-scores.json` becomes `false`, so the console's eval panels reach past 2026-09-28. Its `monthly_window` and `window` stay `forever`.
- **Precondition:** the person's approval (section 2). Plan 56's row "The score month summary is retired, and no eval row is ever deleted" must be complete, with `monthly_window` and `window` kept `forever`. Packing (#1177) and publication (#1169) are complete (section 3), and `config.load_gardener()` must accept that declaration. Year packing supports the published `forever` window; #1182 removed the publication-specific minimum wait after year reads gained fresh addresses, not by loosening a retention setting. Section 2's first-wake check still applies.
- **Files touched:** `config/gardener/compact-scores.json`; `backend/tests/contracts/test_gardener_config.py`; `docs/concepts/config/idhazh-gardener.md`; `docs/architecture/publishing/idhazh-gardener.md`; `docs/architecture/publishing/ledger-compaction.md`; `docs/how-to/run-the-pipeline.md`; `docs/concepts/config/retention-ages.md`; `docs/concepts/evaluation.md`; this plan's Reckoner line.
- **Acceptance gates:** local: the checks `npm --prefix frontend run test:changed -- --list` selects, which include `pytest backend/tests/contracts/test_gardener_config.py` (its `test_a_switch_ships_in_dry_run_unless_a_named_decision_put_it_live` is red until the entry is added), and `python backend/utilities/doc_load.py` with all touched Markdown paths passed as arguments, before and after. CI: the full suite.
- **Oracle:** the first scheduled wake after the merge moves `through` in `state/compact/scores/daily/watermark.json` past 2026-09-28. For every day that wake packed or absorbed, `load_days` returns the same rows at the task's commit as at its parent, and no raw file of that day is left. Today it fails: the task only reports, so `through` stays at 2026-09-28. It cannot settle a later wake; the first wake that absorbs a month is read the same way.
- **Merge window:** section 2, item 4.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | No eval row is deleted. Packing deletes only raw and day files whose rows it has already written into a coarser file, and with every scores window `forever` it drops no month | Plan 56 ruling R1, the person, 2026-09-30 |
| 2 | If plan 56's rename row lands first, the ledger is `summary-quality-evals` wherever this row says `scores`: the task, its file and its folders. If this row lands first, the rename carries the switch with the file | Plan 56 ruling R2 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Switch it on now, with `monthly_window` at 15 months as on main | A live pass would drop each month file 15 months after it packs it | Every eval row of every month the window drops | Plan 56 ruling R1 |

### Row #2 - The upkeep record, the picture cleanup's record and the feed retirements are packed live

- **Scope:** `dry_run` becomes `false` in `config/gardener/compact-gardener.json`, `compact-visual-prunes.json` and `compact-feed-retirements.json`, so their raw files are packed into one file a day and then one a month. Their month windows stay as committed.
- **Precondition:** the person's approval (section 2). It covers the month windows as committed, because they say when each ledger's first rows go, and a ledger the person does not approve stays report-only. Packing #1177 is merged; its first live wake must have packed `item-health` and `host-fingerprint` without failure before these three follow (section 3).
- **Files touched:** the three declarations above; `backend/tests/contracts/test_gardener_config.py`; `docs/concepts/config/idhazh-gardener.md`; `docs/architecture/publishing/idhazh-gardener.md`; `docs/architecture/publishing/ledger-compaction.md`; `docs/how-to/run-the-pipeline.md`; `docs/concepts/config/retention-ages.md`; this plan's Reckoner line.
- **Acceptance gates:** as row 1.
- **Oracle:** the first scheduled wake after the merge gives `state/compact/gardener/`, `state/compact/visual-prunes/` and `state/compact/feed-retirements/` each an `index/daily.json` and a `daily/watermark.json`. For every day it packed, `load_days` returns the same rows at the task's commit as at its parent, and no raw file of that day is left. Today it fails: none of the three folders exists. A wake packs at most `max_periods_per_run` days, so a watermark reaches the newest due day over several wakes. It cannot settle `feed-retirements`, which has no raw file yet: its first wakes pack quiet days only, and its first real move is read at the first wake after a retirement row lands.
- **Merge window:** section 2, item 4.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The row waits for the first live wake of #1177 to be read on two ledgers before three more follow, and these three start with both indexes; a merge alone is not that check | The person, 2026-09-30 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the three report-only | Every wake adds a raw file a shard to the upkeep record, and nothing ever packs them (Guardrail #12) | A file count under `state/raw/` that grows at every wake, for good | The person, 2026-09-30 |
| 2 | A pull request a ledger | Packing drops no row it has not copied, and each ledger's result is read in its own folders, so two more pull requests buy only two more reverts | Two more merge windows and approvals | The person, 2026-09-30 |

### Row #3 - The retention windows the person approves go live, one task a pull request

- **Scope:** the owner first sends the person section 2's message for every report-only retention and collection task, then switches on only the tasks the person approves, one pull request a task, one at a time.
- **Precondition:** the person's answer. A task the person does not approve stays report-only. Each pull request leaves the row `IN-FLIGHT`, and the last approved task's pull request marks it `DONE`.
- **Files touched, a pull request:** `config/gardener/<task>.json`; `backend/tests/contracts/test_gardener_config.py`; `docs/concepts/config/idhazh-gardener.md`; `docs/how-to/run-the-pipeline.md`; `docs/concepts/config/retention-ages.md`; this plan's Reckoner line; and the pages that say that task only reports: `docs/how-to/prune-a-collection.md` and `docs/architecture/publishing/idhazh-gardener.md` for `workflow-artifacts` and `workflow-runs`, that second page for the four tasks with a fold, `docs/architecture/sources/health.md` for `feed-health`, `docs/architecture/publishing/telemetry-series.md` and `docs/concepts/growing-reads.md` for `telemetry-aggregate`, and `docs/concepts/evaluation.md` for `scores`.
- **Acceptance gates:** as row 1, for each pull request.
- **Oracle, a task:** at the first scheduled wake after its merge, its row in the upkeep record reads `dry_run: false`, and the task's commit deletes the files its row counts in `deleted` and `bytes_freed`. For a collection task, the members that run's log names as deleted are gone from GitHub's list. Today it fails: every such row reads `dry_run: true`, and the files stay. It cannot settle whether a window is the right age; the person's answer does.
- **Merge window:** section 2, item 4, for each pull request.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The table lists every declaration under `config/gardener/` of kind `retention` or `collection` that is `active`, whose own `dry_run` is `true` and that is not `visual-prune`, read from the tree at dispatch. On 2026-09-30: `traces`, `seen`, `feed-health`, `counterfactual-scores`, `digest-fragments`, `telemetry-aggregate`, `trials`, `span-rollup`, `scores`, `workflow-artifacts` and `workflow-runs` | The person, 2026-09-30 |
| 2 | A task whose report takes nothing is recommended to stay report-only until a pass names a file: switched on sooner, its first deletion lands with nobody reading the list. A task whose window is `forever` takes nothing live, and the table says so | `docs/how-to/run-the-pipeline.md`, "Turning state cleanup on", step 1 |
| 3 | Beside `traces`, the table says that its eight flat files of 2026-09-22 stay after it goes live | Known defect 53 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One pull request for every approved task | One revert would undo every switch, and one wake's commits would mix every task's deletions | No time; it gives up a revert and an oracle reading a task | The person, 2026-09-30 |

## 3. Dependencies on other plans

A pointer names the other plan's row by its title. Where a row here and a row there edit one file, whichever merges second takes main in first.

| Plan | Row | What it means here |
| --- | --- | --- |
| Completed #1177 | Packed-ledger indexes and daily packing for `item-health` and `host-fingerprint` | The code prerequisite is complete; row 2 still waits for its first live wake to be read, and every switch keeps its own section 2 oracle. [The query reader](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md) owns the published index and missing-file behavior |
| Completed #1169 | Three-ledger publication | The publication prerequisite is complete; the obsolete publication-specific wait was removed by #1182 after fresh year-file addresses. Row 1 keeps its `forever` retention declaration and loader check |
| [56](20260930-56-summary-quality-evals-plan.md) | "The score month summary is retired, and no eval row is ever deleted" | Row 1 waits for it: it sets the `compact-scores` `monthly_window` to `forever` |
| [56](20260930-56-summary-quality-evals-plan.md) | "The shared packing gains a year period"; "The eval ledger becomes `summary-quality-evals`, and its ID files stop growing" | Year packing supports `forever` without an unbounded month index; the rename changes row 1's file (row 1, decision 2). #1182 later removed the publication-specific wait after fresh year-file addresses. Every live switch still needs the person's approval |
| [13](20260905-13-switch-on-deletion-plan.md) | "The fuse comes out, and one run is watched" | It owns `visual-prune`, which row 3 leaves out, and edits the same test and config page as every row here |
| [52](20260926-52-fifty-panels-move-and-six-projections-go-plan.md) | "The `telemetry` and `run-timeline` projections go" | It edits `config/gardener/telemetry-aggregate.json`, so row 3's pull request for that task waits while it is in flight |
| [Known defects](20260823-known-defects-plan.md) | Defect 53 | It matters from the day row 3 switches `traces` on |
