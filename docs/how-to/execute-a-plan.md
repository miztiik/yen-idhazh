# How to execute a plan-doc (the orchestrator contract)

**Last Updated**: 2026-09-12

The step-by-step MECHANICS for running a `TODO/<YYYYMMDD>-<slug>-plan.md` that [author-a-plan.md](author-a-plan.md) produced. Authoring writes the plan; this doc runs it, and owns the autonomy policy it runs under (section "Escalation").

When editing agent/customization Markdown, use ASCII only: "-", "->", ">=", "section".

## The model: one owner, who delegates when delegation pays

The agent that runs a plan **owns** it. It may carry a row itself, and it delegates a row to a **worker subagent** (via `runSubagent`) when delegation buys something: the row is genuinely independent of what the owner is already holding, or the owner's own context is filling up.

**Delegation is context protection, and it costs a hand-off.** A worker starts cold, reads its way back to where the owner already was, and returns a report the owner then has to read. That is worth paying when two rows can be built at the same time, or when the owner cannot hold another row's detail without losing the plan. It is not worth paying for a row the owner is already inside: a one-file edit in a surface it just changed lands faster and better if the owner does it.

The diagram below shows the delegated path, because that is the one with moving parts. Where delegation is not bought, the owner is both columns.

```
orchestrator (main thread) worker subagent (when delegated) persona custom agents
 read the queue; adopt or close runSubagent(default) per row runSubagent("Fowler...") etc.
 read plan-doc + Status Reckoner bootstrap; implement the row resolve ONE ambiguity,
 pick next dispatchable row(s) ----> code + tests + docs ----> return a written ruling
 create worktree + branch stamp its OWN Reckoner line (an input, not an approval)
 dispatch worker; mark IN-FLIGHT run Oracle + acceptance gates
 receive structured report <---- consult personas on ambiguity <----
 run DoD + ship-a-pr; merge on green return report (does NOT merge)
 confirm the line landed; distill; advance
```

## Roles

### The orchestrator (main thread) does exactly this, and only this
1. Read the queue before adding to it: what is already half-done, and what the tables say is done. Adopt or close it first (below).
2. Read the plan-doc Section 0 (operating contract) + Section 1 (Status Reckoner).
3. Keep `Parallel N` rows in flight, and refill a slot the moment one returns. A row is ready when every `Depends-on` is `DONE` and it shares no `Files touched` entry with a row already running. Dispatch the next ready row straight away - do not wait for the rest of a group, for a sibling's checks, or for a merge. None of those is a dependency.
4. For a row you are delegating, or one that will run beside another, create an isolated git worktree off `origin/main` and a named branch. Never share a worktree between rows or with a parallel agent (worktree contamination silently sweeps one row's edits into another's change). Fill the Status Reckoner `Worktree`. A row you carry yourself, with nothing running beside it, needs no second checkout.
5. Dispatch a worker subagent (`runSubagent`, default agent) with a self-contained brief (below) for each row delegation buys. Fill `Subagent`; mark `Status = IN-FLIGHT` under the condition below.
6. Receive the worker's report. Verify its test records and the merge candidate's CI checks against the Definition of Done (CLAUDE.md section 9) and [ship-a-pr.md](ship-a-pr.md). Do not repeat an unchanged worker check. If a merge changes the tested inputs, select checks for those changed inputs. On green gates, remove the row's worktree and then AUTO-merge (`gh pr merge --squash --delete-branch`). **Merging is a step of a row, never a gate on the pool**: the slot freed when the worker returned, so the next ready row is already running while this one's checks, merge and deploy finish.
7. Confirm the merged diff carried the row's own Reckoner line (below); unblock dependents.
8. Repeat until every row is `DONE` or `COLLAPSED`; then close the plan.

**Step 1 exists because an interrupted run leaves no note.** A worker that is killed mid-row never writes its report, never opens a pull request, and never clears the `IN-FLIGHT` it was given, so the next agent to arrive sees a queue that looks idle and a box that is not. What it leaves behind is a checkout with edits in it and a branch nobody proposed - indistinguishable, at a glance, from a checkout somebody finished with. Before selecting any row, list the worktrees and branches on the box, ask which plan row each one belongs to, and ask the pull request host whether its pull request is open, merged or absent. Then decide per item: adopt the work, or remove it. Starting a fresh row beside an abandoned one is how the same row gets done twice, and how two branches end up writing the same file.

**When more than one agent is working the plan at once, mark the row `IN-FLIGHT` on the trunk before the branch is cut.** A status written only on the row's own branch is invisible until that branch merges, which is exactly the window the mark exists to cover - so a mark on the branch is not a mark. It is one line of one table, and the owner is already permitted this edit and no other. Measured on this project on 2026-09-12: thirteen rows had been dispatched and merged, and **no cell anywhere read `IN-FLIGHT`** - for a whole working session the only record of what was being worked was a chat log, which no later agent can read.

**When one agent is carrying the plan, that mark buys nothing and costs a push.** There is nobody to collide with, and a trunk commit for one table cell starts a round of checks for a cell. Record the row's status in the change that does the work.

The project's plan-queue reader answers all three questions in one command - what each Reckoner says, what can start now, and which worktrees and branches no row claims. Where the project has no such tool, the same answer is a `git worktree list`, a branch list, and one query for open pull requests, read against the Reckoners by hand.

**Between selecting a row and dispatching it, check the row against the tree. Two things, and both take seconds.**

A plan-doc is written before the work and read after the tree has moved under it. Both checks are searches against the current tree, not an entry into the row's implementation - the orchestrator still writes none of the row's code. Both belong to the orchestrator because the fix for either is an edit to the plan-doc, and the plan-doc is the orchestrator's to edit.

1. **Every symbol the row names has to exist.** Search the tree for each identifier, path and command the row's text quotes. A row that names something renamed, moved, or never written sends a worker looking for it, and the worker then either invents a substitute or stops and asks. Both cost a dispatch, and the substitute is the more expensive one because it arrives looking like finished work. When a name is wrong, correct the row before dispatching and say what it was corrected from.

2. **The row's check has to be able to fail for the reason the row exists.** Run it against the base tree before the work starts. Usually it fails, and an oracle that already passes is measuring something other than the row - the work will then report a green that proves nothing, so the row closes, the plan records it as settled, and nothing was checked. A row that retires a name is where this bites most often: an oracle phrased as a search for that name matches every place the name still is, so it answers the same before the work and after it, for two different reasons. **Where the row's whole value is that behaviour does not change** - a refactor, a move, a rename - the check passes at both ends by design, and what must be able to fail is the property the change could break. Say which of the two the row is. Do not invent a failing check to satisfy a rule.

Neither check makes a row correct. They establish only that the row can be acted on, and that its result can be told apart from its starting position - which is the same standard `CLAUDE.md` Guardrail #10 sets for any other measurement.

**When a row is delegated, the owner does not also implement it.** Opening the row's source files while a worker is inside them is how two versions of one change appear. For a delegated row its own edits are limited to the plan-doc and the merge: correcting a row before dispatch, filling `Worktree` and `Subagent`, and marking `IN-FLIGHT`. A page derived from the Reckoners is not on that list either, for the reason in the worker's step 7 - the line is the edit, and the generated page follows it on its own.

Do not remove or alter a worker's checkout while its tests or build are running.
Closing a plan does not invalidate an existing check. A documentation-only
closure uses documentation checks and CI, not a fresh local application suite.

**Remove the row's worktree BEFORE the merge, and never by detaching it instead.** Removing it first is what frees the branch, so the merge's own branch delete succeeds rather than failing on "cannot delete branch, used by worktree". Detaching frees the branch too, and that is the trap: it throws the branch away, and the branch is the only signal a later sweep can judge the leftover on - a detached checkout whose branch was squash-merged is not an ancestor of the trunk, so it reads as unmerged work and is kept for ever. Measured 2026-09-02, on the merge of the change that first wrote this step down: the tree had to be removed by hand afterwards. If the merge then needs a fixup, the branch is still on the remote and one `git worktree add` brings the checkout back.

**This removal is the step an interrupted run skips, so it cannot be the only defence.** A worker killed mid-row never reaches its own clean-up, and the orchestrator that would have removed the tree has moved on or died with it. Measured on one box on 2026-09-02: 38 abandoned checkouts holding 156,482 files, every one of them a row whose pull request had merged days earlier. `git worktree prune` does not help - it only clears the admin entry for a directory that is already gone, and never deletes a checkout. Pair this step with a sweep the project can run at any time (below).

**When the orchestrator reports to the user, it translates; it does not forward.** A worker writes in the vocabulary of the subsystem it just changed, which is correct for the doc that row updated and wrong for a person asking what happened. Say what each number means next to the number (`CLAUDE.md` section 0b). Forwarding a worker's phrasing is the single easiest way for an orchestrator to break the voice rule while every row underneath it is green.

**A row's change updates that row's Reckoner line, inside that same change.** Not afterwards, and not by somebody else later. It edits one line of one table - its own row's `Status`, `Worktree` and `Subagent` - and nothing else in the Reckoner, so the merged diff is self-describing: the change and the record that it happened arrive together, and there is no window in which they disagree. The pull request number is not known while the branch is being written, so `PR` is read from the merge rather than written into the diff ([ship-a-pr.md](ship-a-pr.md)).

The cost of leaving it until afterwards is that nothing carries the update - it belongs to a step that runs after the only artefact anybody reviews has already merged, so an orchestrator that dies, is interrupted, or simply moves on leaves a row that is finished and a table that says it is not. Measured 2026-09-11: the first row executed under this contract merged in a pull request that touched no Reckoner line, and hours later that row still read `PENDING` with an empty `PR` column while the work was on the trunk. The instruction to flip it was written down and read by the agent that failed to do it, which is the finding worth keeping - **wording alone did not hold, so the update moved inside the diff that is reviewed.** Step 7 above verifies rather than performs it, and the project's plan-queue reader fails when a merged pull request names a row that never learned it landed.

### The worker subagent, when a row is delegated
Dispatched with `runSubagent` (default agent). Its brief is the row verbatim (Scope, Files touched, Acceptance gates, Oracle, Decisions, Rejected alternatives) plus the standing instruction: read the page that owns the surface, honor CLAUDE.md, stay in scope, consult personas on ambiguity, return a report. The worker:
1. Reads the row, and the page that owns each surface it touches ([../agents/bootstrap.md](../agents/bootstrap.md) routes).
2. Implements the row end-to-end: code + tests at the tier that matches the surface (CLAUDE.md section 13) + the docs update.
3. Resolves ambiguity by consulting personas (below), baking the ruling into the code.
4. Runs the row's Oracle and the local checks selected by the project's gate guide. Leaves full-suite checks assigned to CI there; a list of acceptance gates is not an instruction to repeat every CI job locally. Records the tested inputs, selection, result and test counts. An active check is followed to completion, never launched again because its output is quiet.
5. Turns every defect discovered during execution into explicit work: fix it in the row if it is in scope, or record a follow-up row / scope-change item. Do not bury defects in a footnote.
6. Returns a STRUCTURED report: files changed, gate + Oracle results, decisions taken (+ which persona ruled), any ESCALATE, and the branch / worktree state. **The report opens with one plain sentence saying what the row settled, before any table.** A report that opens with a table hands the orchestrator the subsystem's vocabulary, and the orchestrator then forwards it to a person who asked what happened (`CLAUDE.md` section 0b).
7. Updates its OWN row's Reckoner line in its own pull request - `Status`, `Worktree`, `PR`, `Subagent` - and no other line of that table. Refreshes any derived page whose numbers this row invalidates, in the same pull request, for the same reason - **unless that page is derived from every row at once, in which case the worker never touches it.** A page generated from the whole queue has one writer per open branch, and two branches that each stamp a row then conflict on every line that moved; regenerating to settle that is a band-aid (`CLAUDE.md` Guardrail #5). Such a page is written once, after the merge, by the project's own job, and the project's gate guide says which pages those are and refuses a branch that carries one.
8. Does NOT merge, does NOT edit another row's line, does NOT start another row. Merge and closure are the orchestrator's.

### Persona custom agents resolve ambiguity (they are not an approval gate)
When a row is genuinely ambiguous - a design fork, a contested decision, a fact-finding sweep - the worker dispatches the relevant persona custom agent(s) **by their exact name as listed in CLAUDE.md section 14** (plus "Explore" for read-only breadth) via `runSubagent`. A persona returns a WRITTEN ruling the worker bakes into the row; it is an input to the worker's action, never a request-for-approval surface (bootstrap's AUTO policy). A contested decision runs the relevant personas in DEBATE to ONE ruling (author-a-plan.md step 3).

In VS Code, enable `chat.subagents.allowInvocationsFromSubagents` in the active
user or workspace settings before asking a worker to delegate. Every custom
agent that delegates must include `agent` in its `tools` list. A prompt with its
own `tools` list must include it too, because that list takes precedence. If an
`agents` list is present, it must allow the requested delegate. Verify the setup
with one real, read-only nested invocation. See
[VS Code's nested-subagent documentation](https://code.visualstudio.com/docs/agents/run/subagents#_nested-subagents).

If the harness does not permit a worker to dispatch a nested subagent, the worker instead surfaces the ambiguity in its report; the owner runs the persona consult and re-dispatches the row with the ruling appended to the brief. Reading a persona's file is not a consultation.

**Consult when two defensible answers would lead to different code and the difference matters.** Not for coverage, not one per surface touched, and never as a gate. A consultation whose outcome cannot change what gets written is one to skip - running it anyway is how a row acquires an hour and a paragraph without acquiring a decision.

## The one-line stamp a plan-doc carries

Every plan-doc carries exactly one execution stamp (author-a-plan.md step 5). It is the line that makes "implement it" sufficient: the executing agent reads it, loads this doc, and follows the contract with no further instruction.

```
Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.
```

Drop the `AUTHOR-AND-STOP...` clause once the user authorizes execution.

A plan-doc carrying an earlier wording of this stamp is run under this doc as it stands. The stamp points here; it does not restate the contract.

## Parallel fan-out

**`Parallel N` is a running pool, not a wave.** Four slots means four rows in flight, and a slot refills the moment its worker returns - not four dispatched, then a wait for the slowest, then four more. A wave idles every finished slot until the last one lands, and that idle time is the whole of the difference. **The default is 4.**

**A slot frees when the worker returns its report, not when the row merges.** The writing is finished at that point; the merge is bookkeeping the owner does between dispatches. An owner sitting on a pull request is an owner that should be dispatching.

**Readiness is computed, not read off a letter.** A row is ready when every `Depends-on` is `DONE` and it shares no `Files touched` entry with a row already in flight. `Parallel-group` records which rows the author believed were independent; it is a hint, and the file lists are the fact (below).

Merging stays serialized - one at a time, re-checking the next branch against the advanced `main` - so a green branch never lands on a stale base. **A merge that conflicts or goes red returns that row to its owner, and the pool keeps running.** Reconcile it at the next dependency boundary rather than stopping the line for it.

Measured on this project on 2026-09-12: twelve of the seventeen live plans declared `Parallel N = 1` and the other five declared 2, so there was no pool to refill.

**A plan claiming its parallel rows touch different files is a claim, not a fact.** Check every dispatch against the rows already in flight by diffing their own `Files touched` lists, never by trusting a sentence that asserts they are disjoint. A 33-row plan stated the rule outright and was wrong on its first wave: three rows shared one stylesheet and three components, two more shared one config file, and a sixth row needed a component a row in a later group had not created yet. The evidence was in the plan the whole time - the file lists disagreed with the sentence above them. Where a ready row shares a file with one in flight, hold it and write the new `Depends-on` into the Status Reckoner, so the next dispatch reads it instead of re-deriving it.

### The workers are parallel; the machine is not

`Parallel N` bounds how many workers WRITE at once. It does not bound what they RUN. Each worker starts its own test suite, its own build and its own browser run the moment it is ready, and on one developer machine those all land on the same cores. Serialise the expensive gates instead - one heavy gate at a time across every worktree, through a lock the project's gate doc names - and leave `Parallel N` at its default, because the writing was never what saturates a box. A gate that finishes in seconds stays unwrapped; serialising a cheap gate only adds waiting.

**A gate that fails only under fan-out is a false red.** A suite that times out while siblings hold the cores has measured the box, not the branch. The tell is that the failing test is byte-identical to the base branch and that the project's CI passed the same commit. Re-run it alone before diagnosing it, and never buy the pass with a raised timeout, an added retry or a relaxed assertion - that hides the contention, and the false red returns at the next fan-out.

**A row that MEASURES runs alone.** Any figure a plan produces - wall clock, throughput, bytes, memory - is a claim about the machine as much as about the change, and a neighbour moves it. Give a measuring row a `Parallel-group` of its own, or hold its arms behind the same lock the gates take. Interleave the arms - base, head, base, head - rather than running one arm and then the other, because box load drifts over the minutes between them and an unpaired comparison then reports the drift. Record what else was running beside the number: CLAUDE.md Guardrail #10 asks for hardware, date and spread, and on a shared machine the load belongs there too.

## Escalation (when to pause for the user)

AUTO is the default. PAUSE and surface only for: a Level-5 row (CLAUDE.md section 6), a new `## Design rationale` that would change a persisted contract, an unresolved persona conflict, a scope change (-> [handle-scope-change.md](handle-scope-change.md)), or a 3x cost overrun. Otherwise the orchestrator advances without asking.

**If the user goes quiet, stay in scope.** Do not invent scope, and do not quietly shrink it. Silence is not a new instruction.

## Closure

When every row is `DONE` / `COLLAPSED`: confirm the Status Reckoner is fully resolved, check that nothing durable is written only in the plan-doc ([distill-a-plan.md](distill-a-plan.md) says where anything left over goes), and delete the plan-doc (git history is the ledger, per [../reference/documentation-structure.md](../reference/documentation-structure.md)).

**Then sweep the worktrees the plan created**, with the tool the project's own worktree notes name. Judge each one on three signals and keep it unless all three agree: its pull request is merged, its branch is gone from the remote, and its own tree is clean. All three are needed. A squash merge leaves the branch a non-ancestor of the trunk, so ancestry cannot answer whether the row landed - which is why the pull request is asked. And a branch with no pull request at all is pending work rather than stale work; twice on this project such a branch held a real fix nobody had proposed yet. A detached worktree is the one case ancestry settles alone.

Remove the checkout and keep the branch whenever the branch still holds a commit the trunk does not. The directory is the disk cost; the branch is free and is the only copy of an unmerged commit.

## See also

- [author-a-plan.md](author-a-plan.md) - authoring the plan this doc runs; the plan-doc structure + Status Reckoner columns (`Worktree`, `Subagent`) this contract fills.
- [../agents/bootstrap.md](../agents/bootstrap.md) - what to read before answering, and what every answer owes.
- [distill-a-plan.md](distill-a-plan.md) - where a finding goes when no page owns it yet.
- [handle-scope-change.md](handle-scope-change.md) - STOP-AND-SURFACE when scope shifts mid-row.
- [ship-a-pr.md](ship-a-pr.md) - the PR lifecycle the orchestrator runs at merge.
- [../../CLAUDE.md](../../CLAUDE.md) - correction levels (section 6), Definition of Done (section 9), agent roster (section 14).
