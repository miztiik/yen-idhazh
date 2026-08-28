---
name: bootstrap
description: Load project context before answering. Reads CLAUDE.md, guardrails, and the relevant subsystem and concept docs. Every persona (Reader, Editor, Jony, Susan, Andre, Fowler, Carmack) and every default-agent task crossing a subsystem boundary runs this first. Skip only for Level-0 / Level-1 single-file changes.
---

# bootstrap

This skill is a thin wrapper. The canonical procedure lives in [`docs/agents/bootstrap.md`](../../../docs/agents/bootstrap.md). Read that file in full and follow the ritual it specifies before producing any answer.

The wrapper exists so the `.claude/` harness can invoke the same loading behaviour that `.github/agents/*.agent.md` invokes via a one-line pointer. There is one source of truth - the doc - not two copies.

## What you must do

1. Open [`docs/agents/bootstrap.md`](../../../docs/agents/bootstrap.md).
2. Execute the ritual it specifies, in order.
3. In your first paragraph back to the user, name the Rules and docs that are load-bearing for the answer (the final step of the ritual).
4. When editing agent/customization Markdown, use ASCII only: "-", "->", ">=", "section".

## See also

- [`docs/agents/guardrails.md`](../../../docs/agents/guardrails.md) - the rules every persona must honour, loaded as part of bootstrap.
- [`docs/concepts/pipeline-loop.md`](../../../docs/concepts/pipeline-loop.md) - the stages and what each one owns.
- [`CLAUDE.md`](../../../CLAUDE.md) - the engineering contract.
