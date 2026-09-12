# Agent Bootstrap

**Last Updated**: 2026-09-12

What to read before answering. Not a ritual - a routing table. Read the page
that owns what you are about to change, and stop.

ASCII only in agent markdown: `-`, `->`, `>=`, "section".

## Start at the change

Start at the file, the behaviour, or the failing check you were given. Material
already in front of you counts as read; re-reading it to prove you did costs the
user the answer they asked for.

Then read the one page that owns the thing you are changing.

| What you are changing | What owns it |
| --- | --- |
| A persisted shape - a payload, a ledger, a config, a schema | `CLAUDE.md` section 11, then the model under `backend/idhazh/contracts/` |
| A published page | [`../concepts/design-system.md`](../concepts/design-system.md), and the surface's own code |
| A prompt, a model, or anything fetched text reaches | `CLAUDE.md` Guardrail #11, then `docs/architecture/summarize/` |
| A workflow, a gate, or what CI runs | [`../how-to/run-the-gates.md`](../how-to/run-the-gates.md) |
| Anything whose cost grows as the repository grows | [`../concepts/growing-reads.md`](../concepts/growing-reads.md) |
| Anything you cannot place | [`../reference/documentation-structure.md`](../reference/documentation-structure.md) says who owns what |

[`CLAUDE.md`](../../CLAUDE.md) is the contract. Read the section that bears on
the change. The whole file is not a prerequisite for a one-line fix, and
treating it as one is how a small change costs an hour.

## What every answer owes

- Plain language, the answer first (`CLAUDE.md` section 0b).
- A decision request carries options, each with its cost, and one recommendation
 (section 0c).
- A limitation named with no next move is unfinished: do it, price it, or say
 what would settle it (section 0d).
- Cite a rule where it changed the decision. A list of rules you honoured is not
 an answer, and writing one is how an answer gets longer without getting
 better.

## When a specialist is worth calling

When two defensible answers would lead to different code and the difference
matters. Not as a gate, not for coverage, and not one per surface touched. The
seven and what each one rules are in `CLAUDE.md` section 14.

## See also

- [`../how-to/author-a-plan.md`](../how-to/author-a-plan.md) - authoring a plan-doc.
- [`../how-to/execute-a-plan.md`](../how-to/execute-a-plan.md) - the execution contract.
- [`../how-to/run-the-gates.md`](../how-to/run-the-gates.md) - what to run locally and what to leave to CI.
- [`../../.github/agents/`](../../.github/agents/) - the seven persona advisors.
- [`../../CLAUDE.md`](../../CLAUDE.md) - the engineering contract; section 1 is the guardrails and section 14 the authority assignment.
