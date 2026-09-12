# How to execute a plan-doc (the execution contract)

**Last Updated**: 2026-09-12

The mechanics for running a `TODO/<YYYYMMDD>-<slug>-plan.md` that [author-a-plan.md](author-a-plan.md) produced. Authoring writes the plan; this doc runs it, and owns the autonomy policy it runs under (section "Escalation").

ASCII only in agent/customization Markdown: "-", "->", ">=", "section".

## The model

The agent that runs a plan **owns** it. It carries a row itself, or delegates the row to a **worker subagent** (`runSubagent`) when delegation buys something: the row is independent of what the owner already holds, or the owner's context is filling up.

**Delegation costs a hand-off.** A worker starts cold and returns a report the owner then reads. It pays when two rows can be built at once, or when the owner cannot hold another row's detail without losing the plan. It does not pay for a row the owner is already inside.

## The owner
1. Read the queue before adding to it: what is already half-done, and what the tables say is done. Adopt or close it first (below).
2. Read the plan-doc Section 0 (operating contract) + Section 1 (Status Reckoner).
3. Keep `Parallel N` rows in flight, and refill a slot the moment one returns. A row is ready when every `Depends-on` is `DONE` and it shares no `Files touched` entry with a row already running. Dispatch the next ready row straight away - do not wait for the rest of a group, for a sibling's checks, or for a merge. None of those is a dependency.
4. For a row you are delegating, or one that will run beside another, create an isolated git worktree off `origin/main` and a named branch. Never share a worktree between rows or with a parallel agent (worktree contamination silently sweeps one row's edits into another's change). Fill the Status Reckoner `Worktree`. A row you carry yourself, with nothing running beside it, needs no second checkout.
5. Dispatch a worker subagent (`runSubagent`, default agent) with a self-contained brief (below) for each row delegation buys. Fill `Subagent`; mark `Status = IN-FLIGHT` under the condition below.
6. Receive the worker's report. Verify its test records and the merge candidate's CI checks against the Definition of Done (CLAUDE.md section 9) and [ship-a-pr.md](ship-a-pr.md). Do not repeat an unchanged worker check. If a merge changes the tested inputs, select checks for those changed inputs. On green gates, remove the row's worktree and then AUTO-merge (`gh pr merge --squash --delete-branch`). **Merging is a step of a row, never a gate on the pool**: the slot freed when the worker returned, so the next ready row is already running while this one's checks, merge and deploy finish.
7. Confirm the merged diff carried the row's own Reckoner line (below); unblock dependents.
8. Repeat until every row is `DONE` or `COLLAPSED`; then close the plan.

**Step 1, adopt or close, comes before anything else.** An interrupted run leaves a checkout with edits in it and a branch nobody proposed, and its row still reads `IN-FLIGHT`. List the worktrees and branches on the box, ask which row each belongs to, and ask the pull request host whether its pull request is open, merged or absent. Then adopt the work or remove it. The project's plan-queue reader answers all three in one command; without such a tool it is `git worktree list`, a branch list and one query for open pull requests, read against the Reckoners.

**Mark a row `IN-FLIGHT` on the trunk before the branch is cut, when more than one agent is working the plan.** A status written only on the row's own branch is invisible until that branch merges, which is the window the mark exists to cover. With one agent there is nobody to collide with, so the mark buys nothing and costs a push - record the status in the change that does the work instead.

**Between selecting a row and dispatching it, check the row against the tree.** Both checks are searches, not an entry into the row's implementation, and the fix for either is an edit to the plan-doc.

1. **Every symbol the row names has to exist.** Search the tree for each identifier, path and command the row quotes. A row naming something renamed, moved or never written sends a worker looking for it, and the worker either invents a substitute or stops and asks. Correct the row before dispatching, and say what it was corrected from.

2. **The row's check has to be able to fail for the reason the row exists.** Run it against the base tree first. An oracle that already passes measures something other than the row, so the work reports a green that proves nothing. **Where the row's whole value is that behaviour does not change** - a refactor, a move, a rename - the check passes at both ends by design, and what must be able to fail is the property the change could break. Say which of the two the row is, and do not invent a failing check to satisfy a rule.

**When a row is delegated, the owner does not also implement it.** The owner's edits are then limited to the plan-doc and the merge: correcting a row before dispatch, filling `Worktree` and `Subagent`, and marking `IN-FLIGHT`. A page derived from every Reckoner at once is not on that list either (worker step 7). Do not remove or alter a worker's checkout while its tests or build are running.

**Remove the row's worktree before the merge, and never by detaching it instead.** Removing it frees the branch, so the merge's own branch delete succeeds. Detaching frees the branch too and throws it away, and the branch is the only signal a later sweep can judge the leftover on ([git-and-github.md](../reference/agent-notes/git-and-github.md)). If the merge needs a fixup afterwards, one `git worktree add` brings the checkout back.

**Report to the user in the user's terms, not the subsystem's** (`CLAUDE.md` section 0b). Forwarding a worker's phrasing is the easiest way to break the voice rule while every row underneath it is green.

**A row's change updates that row's Reckoner line, inside that same change.** Not afterwards, and not by somebody else later. It edits one line of one table - its own row's `Status`, `Worktree` and `Subagent` - and nothing else in the Reckoner, so the merged diff is self-describing. The pull request number is not known while the branch is being written, so `PR` is read from the merge rather than written into the diff ([ship-a-pr.md](ship-a-pr.md)).

Step 7 above verifies that update rather than performing it, and the project's plan-queue reader fails when a merged pull request names a row that never learned it landed.

### The worker subagent, when a row is delegated
Dispatched with `runSubagent` (default agent). Its brief is the row verbatim (Scope, Files touched, Acceptance gates, Oracle, Decisions, Rejected alternatives) plus the standing instruction: read the page that owns the surface, honor CLAUDE.md, stay in scope, consult personas on ambiguity, return a report. The worker:
1. Reads the row, and the page that owns each surface it touches ([../agents/bootstrap.md](../agents/bootstrap.md) routes).
2. Implements the row end-to-end: code + tests at the tier that matches the surface (CLAUDE.md section 13) + the docs update.
3. Resolves ambiguity by consulting personas (below), baking the ruling into the code.
4. Runs the row's Oracle and the local checks selected by the project's gate guide. Leaves full-suite checks assigned to CI there; a list of acceptance gates is not an instruction to repeat every CI job locally. Records the tested inputs, selection, result and test counts. An active check is followed to completion, never launched again because its output is quiet.
5. Turns every defect discovered during execution into explicit work: fix it in the row if it is in scope, or record a follow-up row / scope-change item. Do not bury defects in a footnote.
6. Returns a STRUCTURED report: files changed, gate + Oracle results, decisions taken (+ which persona ruled), any ESCALATE, and the branch / worktree state. **The report opens with one plain sentence saying what the row settled, before any table.** A report that opens with a table hands the owner the subsystem's vocabulary, and the owner then forwards it to a person who asked what happened (`CLAUDE.md` section 0b).
7. Updates its OWN row's Reckoner line in its own pull request - `Status`, `Worktree`, `PR`, `Subagent` - and no other line of that table. Refreshes any derived page whose numbers this row invalidates, in the same pull request - **unless that page is derived from every row at once, in which case the worker never touches it.** Such a page has one writer per open branch, so two branches that each stamp a row then conflict on every line that moved. It is written once, after the merge, by the project's own job, and the gate guide says which pages those are and refuses a branch that carries one.
8. Does NOT merge, does NOT edit another row's line, does NOT start another row. Merge and closure are the owner's.

### Persona custom agents resolve ambiguity (they are not an approval gate)
When a row is genuinely ambiguous - a design fork, a contested decision, a fact-finding sweep - the worker dispatches the relevant persona custom agent(s) **by their exact name as listed in CLAUDE.md section 14** (plus "Explore" for read-only breadth) via `runSubagent`. A persona returns a WRITTEN ruling the worker bakes into the row; it is an input to the worker's action, never a request-for-approval surface (section "Escalation"). A contested decision runs the relevant personas in DEBATE to ONE ruling (author-a-plan.md step 3).

If the harness does not permit a worker to dispatch a nested subagent, the worker surfaces the ambiguity in its report; the owner runs the consult and re-dispatches the row with the ruling appended to the brief. Reading a persona's file is not a consultation. What the harness needs configured first is in [shell-and-tools.md](../reference/agent-notes/shell-and-tools.md).

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

**Check every dispatch against the rows already in flight by diffing their `Files touched` lists.** A plan asserting that its parallel rows are disjoint is making a claim, not stating a fact ([git-and-github.md](../reference/agent-notes/git-and-github.md)). Where a ready row shares a file with one in flight, hold it and write the new `Depends-on` into the Status Reckoner, so the next dispatch reads it instead of re-deriving it.

### The workers are parallel; the machine is not

`Parallel N` bounds how many workers WRITE at once, not what they RUN. Each worker starts its own test suite, build and browser run, and on one machine those all land on the same cores. Serialise the expensive gates through the lock the project's gate doc names, and leave `Parallel N` at its default - the writing was never what saturates a box. A gate that finishes in seconds stays unwrapped.

**A gate that fails only under fan-out is a false red.** Re-run it alone before diagnosing it, and never buy the pass with a raised timeout, an added retry or a relaxed assertion ([gates-and-builds.md](../reference/agent-notes/gates-and-builds.md)).

**A row that MEASURES runs alone.** Any figure a plan produces is a claim about the machine as much as about the change, and a neighbour moves it. Give a measuring row a `Parallel-group` of its own, or hold its arms behind the same lock the gates take.

## Escalation (when to pause for the user)

AUTO is the default. PAUSE and surface only for: a Level-5 row (CLAUDE.md section 6), a new `## Design rationale` that would change a persisted contract, an unresolved persona conflict, a scope change (-> [handle-scope-change.md](handle-scope-change.md)), or a 3x cost overrun. Otherwise the owner advances without asking.

**If the user goes quiet, stay in scope.** Do not invent scope, and do not quietly shrink it. Silence is not a new instruction.

## Closure

When every row is `DONE` / `COLLAPSED`: confirm the Status Reckoner is fully resolved, check that nothing durable is written only in the plan-doc ([distill-a-plan.md](distill-a-plan.md) says where anything left over goes), and delete the plan-doc (git history is the ledger, per [../reference/documentation-structure.md](../reference/documentation-structure.md)). Closing a plan does not invalidate an existing check, and a documentation-only closure uses documentation checks and CI rather than a fresh local application suite.

**Then sweep the worktrees the plan created.** Keep a checkout only when all three agree: its pull request is merged, its branch is gone from the remote, and its own tree is clean. Remove the checkout and keep the branch whenever the branch still holds a commit the trunk does not - the directory is the disk cost, and the branch is the only copy of an unmerged commit. Why all three are needed, and what a detached checkout changes, is in [git-and-github.md](../reference/agent-notes/git-and-github.md).

Remove the checkout and keep the branch whenever the branch still holds a commit the trunk does not. The directory is the disk cost; the branch is free and is the only copy of an unmerged commit.

## See also

- [author-a-plan.md](author-a-plan.md) - authoring the plan this doc runs; the plan-doc structure + Status Reckoner columns (`Worktree`, `Subagent`) this contract fills.
- [../agents/bootstrap.md](../agents/bootstrap.md) - what to read before answering, and what every answer owes.
- [distill-a-plan.md](distill-a-plan.md) - where a finding goes when no page owns it yet.
- [handle-scope-change.md](handle-scope-change.md) - STOP-AND-SURFACE when scope shifts mid-row.
- [ship-a-pr.md](ship-a-pr.md) - the PR lifecycle the owner runs at merge.
- [../../CLAUDE.md](../../CLAUDE.md) - correction levels (section 6), Definition of Done (section 9), agent roster (section 14).
