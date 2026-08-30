# Agent Bootstrap

**Last Updated**: 2026-08-30

What to load before answering. The companion doc [`guardrails.md`](guardrails.md)
is what not to do.

Every persona runs this - through Claude Code (`.claude/skills/bootstrap`) or VS
Code Copilot Chat (`.github/agents/*.agent.md`). ASCII only in agent markdown:
`-`, `->`, `>=`, "section".

## The ritual

1. **[`CLAUDE.md`](../../CLAUDE.md), end to end.** The contract. Know which of
   Rules #1-#11 are load-bearing here and cite them by number.
2. **[`guardrails.md`](guardrails.md).** Non-goals, git hygiene, stop
   conditions, escalation.
3. **The subsystem doc for the surface you are touching**, under
   `docs/architecture/<area>/`. Do not critique what you have not read.
4. **The concept doc that owns the idea**, under `docs/concepts/`. Design
   rationale and rejected alternatives live on those pages, not in a decisions
   folder.
5. **The active plan-doc under `TODO/`**, if the task touches it.
6. **`git log --oneline -20`**, for in-flight work that overlaps.
7. **Say which Rules and which docs are load-bearing**, in your first paragraph.
   That makes the load explicit and easy to challenge.

## When it is mandatory

Any persona invocation. Any task crossing two or more of `backend/`,
`frontend/`, `config/`, `schemas/`, `state/`. Anything at Correction Level 2 or
higher (`CLAUDE.md` section 6).

Skip it for a Level-0 or Level-1 change inside one file, and for a read-only
question that proposes nothing.

## Autonomous execution - AUTO is the default

When a user authorises autonomous execution of a plan-doc:

- **AUTO every row.** Do the work, run the Definition of Done (`CLAUDE.md`
  section 9), `gh pr merge --squash --delete-branch`, take the next row. No
  draft-and-wait, no mid-row pause for approval.
- **Do not idle on checks.** A ready independent row dispatches while sibling
  checks are still running. Merges stay green-gated and one at a time.
- **Personas gather facts.** Their verdicts inform the action; they are not an
  approval surface.
- **ESCALATE only** for a contract-changing design proposal, an unresolved
  persona conflict, a Level-5 trigger, or a 3x cost overrun.
- **If the user goes quiet**, stay in scope. Do not invent scope and do not
  quietly shrink it.

This is the autonomy policy. The orchestration mechanics - worktrees, fan-out,
closure - are in [`../how-to/execute-a-plan.md`](../how-to/execute-a-plan.md).

## See also

- [`guardrails.md`](guardrails.md) - the rules every persona must honour.
- [`../how-to/author-a-plan.md`](../how-to/author-a-plan.md) - authoring a plan-doc.
- [`../how-to/execute-a-plan.md`](../how-to/execute-a-plan.md) - the execution contract.
- [`../how-to/run-the-gates.md`](../how-to/run-the-gates.md) - what to run locally and what to leave to CI.
- [`../../.github/agents/`](../../.github/agents/) - the seven persona advisors.
- [`../../CLAUDE.md`](../../CLAUDE.md) - the engineering contract.
