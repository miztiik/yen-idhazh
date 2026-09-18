---
name: next-item
description: Take one item from a to-do list and drive it to an execution-ready plan - settle what the user actually wants, find the best way to achieve it, declare the contracts that way needs, then hand the sequence to prepare-plan. Use when the user says "take the next item", "work this item", "what does this need", or points at a list and asks what to do with a line on it.
---

# next-item

A thin wrapper. The procedure lives in [`docs/how-to/take-an-item-to-plan.md`](../../../docs/how-to/take-an-item-to-plan.md). Read it and follow it - there is one source of truth (the docs), not a copy embedded here.

The order is the whole point: intent, then the best way, then the contracts, then the sequence ([`CLAUDE.md`](../../../CLAUDE.md) section 0d). A plan written before the contracts are settled hands a worker a scope it has to invent.

## What you must do

1. Ask which list and which item, unless the user named both.
2. Open [`docs/how-to/take-an-item-to-plan.md`](../../../docs/how-to/take-an-item-to-plan.md) and follow its four steps in order. Do not start a step whose gate has not passed.
3. Find every fact yourself before asking anything, and put a whole round of questions in one message (`CLAUDE.md` section 0c).
4. Hand step 4 to [`prepare-plan`](../prepare-plan/SKILL.md). Do not write the feature's code.
5. When editing agent/customization Markdown, use ASCII only: "-", "->", ">=", "section".

## See also

- [`docs/how-to/take-an-item-to-plan.md`](../../../docs/how-to/take-an-item-to-plan.md) - the procedure this wrapper points to.
- [`prepare-plan`](../prepare-plan/SKILL.md) - step 4, which writes the plan-doc.
- [`bootstrap`](../bootstrap/SKILL.md) - which page owns what.
