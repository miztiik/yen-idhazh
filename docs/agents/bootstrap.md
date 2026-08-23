# Agent Bootstrap

**Last Updated**: 2026-08-20

Every persona - whether invoked through Claude Code (`.claude/skills/bootstrap`) or through VS Code Copilot Chat (`.github/agents/*.agent.md`) - runs this loading ritual before answering. The duplicated "read CLAUDE.md, read docs/architecture, read the plan-doc..." preamble that used to live in every agent file has moved here so there is one place to update it.

This is the *what to load*. The companion doc [`guardrails.md`](guardrails.md) is the *what not to do*. Bootstrap loads guardrails as one of its steps.

When editing agent/customization Markdown, use ASCII only: "-", "->", ">=", "section".

## The ritual (in order)

1. **Read [`CLAUDE.md`](../../CLAUDE.md) end-to-end.** It is the engineering contract. Identify which Holy Laws (#1-#11) are load-bearing for the current task and be ready to cite them by number. Sections 1a (architecture principles) and 1b (logging) constrain almost every design answer.
2. **Read [`guardrails.md`](guardrails.md).** Holy Laws restated, project-level non-goals, git hygiene and stop conditions, escalation rules. These constrain every recommendation you make.
3. **Read the relevant subsystem doc(s) under `docs/architecture/<area>/`.** Pick the area that matches the task surface - e.g. `docs/architecture/contracts/` for a schema or persisted-payload change, `docs/architecture/pipeline/` for a stage, `docs/architecture/site/` for the published surface. Do not critique what you have not read.
4. **Read the relevant concept doc(s) under `docs/concepts/`.** [`vision.md`](../concepts/vision.md) for what this project is and is not, [`pipeline-loop.md`](../concepts/pipeline-loop.md) for the stages and what each owns, [`evaluation.md`](../concepts/evaluation.md) for how quality is measured, [`config.md`](../concepts/config.md) for the tunable surface, [`digest.md`](../concepts/digest.md) for the published shape, [`telemetry.md`](../concepts/telemetry.md) for the event envelope and logging doctrine, [`design-system.md`](../concepts/design-system.md) for the visual language. Design rationale and rejected alternatives live on these pages as `## Design rationale` / `## Rejected alternatives` sections.
5. **Read the active plan-doc under `TODO/`** if the task touches work it covers, for in-flight scope and open questions.
6. **Skim recent git history** (`git log --oneline -20`) for in-flight work that overlaps the task.
7. **State, in your first paragraph back to the user, which Holy Laws and which docs are load-bearing for this answer.** This makes the load explicit and easy to challenge.

## When bootstrap is mandatory

- Any persona invocation (custom agents) - they all start here.
- Any default-agent task that crosses a subsystem boundary (touches >= 2 of `backend/`, `frontend/`, `config/`, `schemas/`, `state/`).
- Any task escalated to Correction Level 2 or higher (`CLAUDE.md` section 6).

## When bootstrap is optional

- Level-0 / Level-1 changes inside a single file (typo, comment, log string, isolated bug fix).
- Pure read questions ("where is X defined?") that do not propose any change.

## Why this exists as a doc, not duplicated in every agent file

`CLAUDE.md` and `docs/` are agent memory, and duplication is forbidden (Holy Law #4). An agent file carries its own worldview; the loading ritual is shared, so it lives once, here.

## Autonomous plan execution - AUTO is the default

When a user authorises an agent to execute a plan-doc autonomously (verbatim mandates like "run autonomous", "merge the PRs to main and move onto the next step until the end of the plan"), the default stance is:

- **AUTO** every row: execute the work, run the Definition of Done (`CLAUDE.md` section 9), `gh pr merge --squash --delete-branch`, advance to the next row. No DRAFT-PR-and-wait state. No mid-row CONSULT-USER pause.
- **Personas** (custom agents) MAY be dispatched as subagents to gather facts; their verdicts inform the agent's action - they are not a request-for-approval surface.
- **ESCALATE only** for genuine triggers: a new architecture-decision proposal (a `## Design rationale` that would change a contract), an unresolved persona conflict, a Level-5 trigger (`CLAUDE.md` section 6), or a 3x cost overrun. Otherwise AUTO.
- **When the user is unavailable mid-execution**, stay in scope, progress the in-flight mandate, do not invent new scope or contract existing scope.

This stanza is the canonical reference for the autonomy POLICY (AUTO by default, when to escalate). The step-by-step orchestrator MECHANICS (subagent-PR topology, worktree isolation, parallel fan-out, closure) live in [`../how-to/execute-a-plan.md`](../how-to/execute-a-plan.md). Plan-docs cite these docs rather than re-explaining.

## See also

- [`guardrails.md`](guardrails.md) - the rules every persona must honour.
- [`../how-to/author-a-plan.md`](../how-to/author-a-plan.md) - authoring an execution-ready plan-doc.
- [`../how-to/execute-a-plan.md`](../how-to/execute-a-plan.md) - the orchestrator execution contract.
- [`../concepts/pipeline-loop.md`](../concepts/pipeline-loop.md) - the stages and what each one owns.
- [`../../.github/agents/`](../../.github/agents/) - the five persona advisors that run this ritual.
- [`../../CLAUDE.md`](../../CLAUDE.md) - the engineering contract.
