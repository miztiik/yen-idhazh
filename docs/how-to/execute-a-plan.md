# How to execute a plan-doc (the orchestrator contract)

**Last Updated**: 2026-09-02

The step-by-step MECHANICS for running a `TODO/<YYYYMMDD>-<slug>-plan.md` that [author-a-plan.md](author-a-plan.md) produced. Authoring writes the plan; this doc runs it. The autonomy POLICY (AUTO by default, when to ESCALATE) lives in [../agents/bootstrap.md](../agents/bootstrap.md); this doc is the HOW.

Run the `bootstrap` skill first. When editing agent/customization Markdown, use ASCII only: "-", "->", ">=", "section".

## The model: an orchestrator that never codes, and disposable workers that do

The agent that runs a plan is an **orchestrator**, not an implementer. It holds only the plan-doc and one report per row, and it NEVER writes feature code inline. Every row's real work is delegated to a **worker subagent** (via `runSubagent`) that runs in its own isolated context and its own git worktree, does the row end-to-end, and returns a structured report. The orchestrator then gates, merges, flips the Status Reckoner, and advances.

Why the split exists: the orchestrator's context is the scarce resource. If it implemented rows inline, its context would fill with per-row detail and it would lose the plan. Delegation keeps the orchestrator lean - it only ever holds the plan + per-row reports, never the full implementation transcript. This is context protection, and it is the whole point.

```
orchestrator (main thread)                 worker subagent (one per row)          persona custom agents
  read plan-doc + Status Reckoner            runSubagent(default) per row            runSubagent("Fowler ...") etc.
  pick next dispatchable row(s)      ---->   bootstrap; implement the row    ---->   resolve ONE ambiguity,
  create worktree + branch                   code + tests + docs                     return a written ruling
  dispatch worker; mark IN-FLIGHT            run Oracle + acceptance gates           (an input, not an approval)
  receive structured report        <----     consult personas on ambiguity  <----
  run DoD + ship-a-pr; merge on green        return report (does NOT merge)
  flip Status DONE #pr; distill; advance
```

## Roles

### The orchestrator (main thread) does exactly this, and only this
1. Bootstrap; read the plan-doc Section 0 (operating contract) + Section 1 (Status Reckoner).
2. Select the next dispatchable row(s): every `Depends-on` is `DONE`; rows sharing a `Parallel-group` dispatch together, up to `Parallel N`. Waiting for checks is not a dependency.
3. Create an isolated git worktree off `origin/main` + a named branch per row. Never share a worktree between rows or with a parallel agent (worktree contamination silently sweeps one row's edits into another's PR). Fill the Status Reckoner `Worktree`.
4. Dispatch one worker subagent per row (`runSubagent`, default agent) with a self-contained brief (below). Set `Status = IN-FLIGHT`; fill `Subagent`.
5. Receive the worker's report. Run the Definition of Done (CLAUDE.md section 9) and [ship-a-pr.md](ship-a-pr.md); on green gates, AUTO-merge (`gh pr merge --squash --delete-branch`). If checks or publish/deploy jobs are still running for one independent row, keep dispatching other ready rows instead of idling.
6. Remove the row's worktree once its pull request is merged: detach it first, then remove it. A merged row's checkout is finished work, and the removal is the orchestrator's because the worker has already returned.
7. Flip `Status = DONE #<pr>`; unblock dependents; [distill](distill-a-plan.md) the closed row.
8. Repeat until every row is `DONE` or `COLLAPSED`; then close the plan.

The orchestrator does NOT open the row's source files, write its code, or run its inner test loop inline - that is the worker's job. The orchestrator's own edits are limited to the Status Reckoner and the merge.

**Step 6 is the one an interrupted run skips, so it cannot be the only defence.** A worker killed mid-row never reaches its own clean-up, and the orchestrator that would have removed the tree has moved on or died with it. Measured on one box on 2026-09-02: 38 abandoned checkouts holding 156,482 files, every one of them a row whose pull request had merged days earlier. `git worktree prune` does not help - it only clears the admin entry for a directory that is already gone, and never deletes a checkout. Pair this step with a sweep the project can run at any time (below).

**When the orchestrator reports to the user, it translates; it does not forward.** A worker writes in the vocabulary of the subsystem it just changed, which is correct for the doc that row updated and wrong for a person asking what happened. Say what each number means next to the number (`CLAUDE.md` section 0b). Forwarding a worker's phrasing is the single easiest way for an orchestrator to break the voice rule while every row underneath it is green.

### The worker subagent (one per row) does the actual work
Dispatched with `runSubagent` (default agent). Its brief is the row verbatim (Scope, Files touched, Acceptance gates, Oracle, Decisions, Rejected alternatives) plus the standing instruction: run bootstrap, honor CLAUDE.md, stay in scope, consult personas on ambiguity, return a report. The worker:
1. Runs bootstrap; reads the row + the docs its surface touches.
2. Implements the row end-to-end: code + tests at the tier that matches the surface (CLAUDE.md section 13) + the docs update.
3. Resolves ambiguity by consulting personas (below), baking the ruling into the code.
4. Runs the row's Oracle and every acceptance gate locally; iterates until green.
5. Turns every defect discovered during execution into explicit work: fix it in the row if it is in scope, or record a follow-up row / scope-change item. Do not bury defects in a footnote.
6. Returns a STRUCTURED report: files changed, gate + Oracle results, decisions taken (+ which persona ruled), any ESCALATE, and the branch / worktree state. **The report opens with one plain sentence saying what the row settled, before any table.** A report that opens with a table hands the orchestrator the subsystem's vocabulary, and the orchestrator then forwards it to a person who asked what happened (`CLAUDE.md` section 0b).
7. Does NOT merge, does NOT edit the Status Reckoner, does NOT start another row. Merge and closure are the orchestrator's.

### Persona custom agents resolve ambiguity (they are not an approval gate)
When a row is genuinely ambiguous - a design fork, a contested decision, a fact-finding sweep - the worker dispatches the relevant persona custom agent(s) **by their exact name as listed in CLAUDE.md section 14** (plus "Explore" for read-only breadth) via `runSubagent`. A persona returns a WRITTEN ruling the worker bakes into the row; it is an input to the worker's action, never a request-for-approval surface (bootstrap's AUTO policy). A contested decision runs the relevant personas in DEBATE to ONE ruling (author-a-plan.md step 3).

If the harness does not permit a worker to dispatch a nested subagent, the worker instead surfaces the ambiguity in its report; the orchestrator runs the persona consult and re-dispatches the row with the ruling appended to the brief. Either way personas are consulted - never skipped, never treated as a gate.

## The one-line stamp a plan-doc carries

Every plan-doc carries exactly one execution stamp (author-a-plan.md step 5). It is the line that makes "implement it" sufficient: the executing agent reads it, loads this doc, and follows the contract with no further instruction.

```
Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = <n>; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.
```

Drop the `AUTHOR-AND-STOP ...` clause once the user authorizes execution.

## Parallel fan-out

Rows in the same `Parallel-group` are mutually independent and dispatched concurrently, up to `Parallel N` workers, each in its own worktree. A ready row dispatches as soon as its `Depends-on` entries are `DONE`; it does not wait for sibling checks, nor for a long publish or deploy gate on another PR. The orchestrator parallelizes the WORK but serializes the MERGE - one PR at a time, re-checking the next worker's branch against the advanced `main` before its merge - so a green worker never lands on a stale base.

**A plan claiming its parallel rows touch different files is a claim, not a fact.** Compose every wave by diffing the rows' own `Files touched` lists, never by trusting a sentence that asserts they are disjoint. A 33-row plan stated the rule outright and was wrong on its first wave: three rows shared one stylesheet and three components, two more shared one config file, and a sixth row needed a component a row in a later group had not created yet. The evidence was in the plan the whole time - the file lists disagreed with the sentence above them. Where two ready rows do share a file, serialise them and write the new `Depends-on` into the Status Reckoner, so the next wave reads it instead of re-deriving it.

### The workers are parallel; the machine is not

`Parallel N` bounds how many workers WRITE at once. It does not bound what they RUN. Each worker starts its own test suite, its own build and its own browser run the moment it is ready, and on one developer machine those all land on the same cores. Serialise the expensive gates instead - one heavy gate at a time across every worktree, through a lock the project's gate doc names - and leave `Parallel N` where it is, because the writing was never what saturates a box. A gate that finishes in seconds stays unwrapped; serialising a cheap gate only adds waiting.

**A gate that fails only under fan-out is a false red.** A suite that times out while siblings hold the cores has measured the box, not the branch. The tell is that the failing test is byte-identical to the base branch and that the project's CI passed the same commit. Re-run it alone before diagnosing it, and never buy the pass with a raised timeout, an added retry or a relaxed assertion - that hides the contention, and the false red returns at the next fan-out.

**A row that MEASURES runs alone.** Any figure a plan produces - wall clock, throughput, bytes, memory - is a claim about the machine as much as about the change, and a neighbour moves it. Give a measuring row a `Parallel-group` of its own, or hold its arms behind the same lock the gates take. Interleave the arms - base, head, base, head - rather than running one arm and then the other, because box load drifts over the minutes between them and an unpaired comparison then reports the drift. Record what else was running beside the number: CLAUDE.md Rule #10 asks for hardware, date and spread, and on a shared machine the load belongs there too.

## Escalation (when to pause for the user)

AUTO is the default. PAUSE and surface only for: a Level-5 row (CLAUDE.md section 6), a new `## Design rationale` that would change a persisted contract, an unresolved persona conflict, a scope change (-> [handle-scope-change.md](handle-scope-change.md)), or a 3x cost overrun. Otherwise the orchestrator advances without asking.

## Closure

When every row is `DONE` / `COLLAPSED`: run [distill-a-plan.md](distill-a-plan.md) for each closed row, confirm the Status Reckoner is fully resolved, and delete the plan-doc once fully distilled (git history is the ledger, per [../reference/documentation-structure.md](../reference/documentation-structure.md)).

**Then sweep the worktrees the plan created**, with the tool the project's own worktree notes name. Judge each one on three signals and keep it unless all three agree: its pull request is merged, its branch is gone from the remote, and its own tree is clean. All three are needed. A squash merge leaves the branch a non-ancestor of the trunk, so ancestry cannot answer whether the row landed - which is why the pull request is asked. And a branch with no pull request at all is pending work rather than stale work; twice on this project such a branch held a real fix nobody had proposed yet. A detached worktree is the one case ancestry settles alone.

Remove the checkout and keep the branch whenever the branch still holds a commit the trunk does not. The directory is the disk cost; the branch is free and is the only copy of an unmerged commit.

## See also

- [author-a-plan.md](author-a-plan.md) - authoring the plan this doc runs; the plan-doc structure + Status Reckoner columns (`Worktree`, `Subagent`) this contract fills.
- [../agents/bootstrap.md](../agents/bootstrap.md) - the autonomy POLICY (AUTO default, escalation) this doc mechanizes.
- [distill-a-plan.md](distill-a-plan.md) - lifting findings into canonical docs after a row merges.
- [handle-scope-change.md](handle-scope-change.md) - STOP-AND-SURFACE when scope shifts mid-row.
- [ship-a-pr.md](ship-a-pr.md) - the PR lifecycle the orchestrator runs at merge.
- [../../CLAUDE.md](../../CLAUDE.md) - correction levels (section 6), Definition of Done (section 9), agent roster (section 14).
