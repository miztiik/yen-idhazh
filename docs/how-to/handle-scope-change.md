# How to handle a scope change

**Last Updated**: 2026-08-20

What to do when work in flight turns out to be different work. This is the STOP-AND-SURFACE procedure that [CLAUDE.md](../../CLAUDE.md) section 10 names as its first anti-pattern, and the escape hatch that [execute-a-plan.md](execute-a-plan.md) and [author-a-plan.md](author-a-plan.md) hand off to.

This runbook is **domain-neutral** so it can be copied between projects unchanged (CLAUDE.md section 5).

## The rule

**An agent may not silently reinterpret, downgrade, substitute, or narrow an instruction the user gave explicitly.** Discovering that the named approach is wrong, expensive, or impossible is a legitimate and frequent outcome. Quietly shipping a different thing instead is not.

The failure this prevents is specific: the user asked for A, the agent found A hard, the agent shipped A-minus, and nobody noticed until A-minus was load-bearing.

## When this triggers

Any one of these, on its own:

- The named source, library, model, dataset or approach does not work, does not exist, or costs far more than assumed.
- The work turns out to need a change to a persisted contract, and that was not the stated scope.
- Delivering what was asked would break a rule in `CLAUDE.md` - most often a Holy Law or a stated non-goal.
- The correction level was assessed at 2 and the work is really a 4 (CLAUDE.md section 6).
- Cost - time, runner minutes, bytes, dependencies - is running about 3x the estimate.
- Two named authorities disagree and the disagreement is not resolvable from the docs.

Note what is **not** on the list: work being merely harder than expected, or a better idea occurring mid-task. Those are executed as scoped, not surfaced.

## The procedure

### 1. Stop at a clean boundary

Finish the current file edit so nothing is left half-written. Do not start the next unit. Do not "just try one more approach" - that is how a 20-minute surface becomes a two-hour detour.

### 2. Leave the work recoverable

Commit what is complete and coherent on its branch, or leave it uncommitted but intact. Never discard, reset, stash-and-forget, or clean the tree to "start fresh" (CLAUDE.md section 8). The half-done work is the evidence for the conversation you are about to have.

### 3. Write the surface

Five parts, in this order. Keep it short - this is a decision request, not a report:

| Part | Content |
| --- | --- |
| **What was asked** | The instruction, quoted or closely paraphrased. Not your interpretation of it. |
| **What was found** | The specific, checkable fact that changed the picture. Name the file, the error, the measurement, the rule by number. |
| **Why it changes scope** | One or two sentences connecting the finding to the instruction. |
| **Options** | Two or three, each with its cost and what it forecloses. Include "do nothing / drop this" whenever it is genuinely available. |
| **Recommendation** | One option, named, with the reason. Take a position; an options list with no recommendation pushes the whole analysis back onto the user. |

### 4. Stop and wait

Do not begin the recommended option. The point of surfacing is the decision, and pre-empting it defeats the purpose.

If the user is unavailable and the mandate was autonomous: stay strictly in the original scope, progress only what is unambiguous, and leave the surface at the top of the plan-doc for whoever arrives next. Do not invent new scope and do not contract existing scope (see [../agents/bootstrap.md](../agents/bootstrap.md), autonomous execution).

### 5. Record the outcome

Once the user rules:

- **Scope confirmed as-is** - continue; add a line to the plan-doc noting the finding, so it is not rediscovered.
- **Scope changed** - update the plan-doc row (or the relevant living doc) in the same commit as the first piece of the new work. A scope change that lives only in chat is lost.
- **Rule changed** - if the ruling conflicts with a rule in `CLAUDE.md`, amend that rule in the same commit (CLAUDE.md section 0). User approval supersedes the contract, but the contract has to be told.
- **Work dropped** - delete the branch, mark the row, and say what would make it live again.

## Anti-patterns

- Substituting a source, library or model and mentioning it in passing in a summary.
- Presenting a narrowed deliverable as complete.
- Surfacing everything, including ordinary difficulty. A surface that cries wolf gets waved through, which is worse than not having one.
- Surfacing without a recommendation.
- Continuing to work while the surface is open, so the decision arrives after it no longer matters.

## See also

- [execute-a-plan.md](execute-a-plan.md) - the orchestrator contract that hands off to this.
- [author-a-plan.md](author-a-plan.md) - where ESCALATE triggers are written down in advance.
- [../agents/bootstrap.md](../agents/bootstrap.md) - the autonomy policy and what ESCALATE means.
- [../../CLAUDE.md](../../CLAUDE.md) - section 6 (correction levels), section 8 (git hygiene), section 10 (anti-patterns).
