# Evaluation

**Last Updated**: 2026-08-21

How a summary is judged, why one number is never enough, and the rule that keeps the measurement honest. This page fixes the vocabulary; the concrete metric implementations, thresholds and the golden-set contents are owned by the plan-doc and the eval subsystem doc, and the tunable bands live in [config.md](config.md).

## The problem being solved

Every summary reads equally confident. A wrong one is not visibly different from a right one - that is what makes generated text useful and what makes it dangerous. A reader cannot audit it, and the person who built the pipeline stops reading the output within a week. So the system has to measure its own work on every item, continuously, and the measurement has to be committed rather than recomputed on demand.

The failure this guards against is not dramatic. It is a slow one: extraction quietly breaks on a site redesign, summaries start describing navigation chrome, and every score stays healthy because the summary is perfectly faithful to the garbage it was given.

## Faithfulness, scored twice

The primary measure is **faithfulness**: does the summary assert things the source actually said? It is scored twice on purpose:

- against the text the model **actually saw** (post-truncation), and
- against the **full article**.

A single score cannot distinguish "the model invented something" from "the model faithfully summarized the half of the article we gave it". The **gap between the two** is the cost of truncation, and it is invisible unless you measure both. A large gap flags the item as a truncation artifact rather than a hallucination - a different defect with a different fix.

## Why faithfulness alone is not enough

Faithfulness measures **consistency with the source, not informativeness**. Two failure modes score beautifully on it:

- *"This article discusses technology."* Perfectly faithful. Says nothing.
- A verbatim quote of the first three paragraphs. Perfectly faithful. Has not summarized anything.

Optimising for faithfulness alone therefore drives the system toward bland copying. It is paired with deterministic counterweights that see what it cannot:

| Counterweight | What it catches |
| --- | --- |
| **Coverage** | Whether the named entities and numbers in the source survived into the summary. This is the direct instrument for *selective omission* - the thing faithfulness structurally cannot see, because omitting a fact is perfectly consistent with the source. |
| **Compression** | Whether the summary is a plausible fraction of the source. Outside the expected band it is either a copy or a headline. |
| **Extractiveness** | How much of the summary is lifted verbatim. High extractiveness *plus* high faithfulness means copying, not summarizing. |

These are deterministic and cost effectively nothing, which is why they are preferred over an additional model pass.

## Two rules that are easy to break by accident

**1. The metric that selects can no longer alarm.** It is tempting to generate several candidate summaries and keep the one that scores best. Doing so destroys the score's value as a monitor: once it is the selector, it can no longer tell you that outputs are getting worse, because it is being optimised against by construction. This is Goodhart's law with a concrete cost. The selector and the alarm stay separate.

**2. The model does not grade the model.** LLM-as-judge is a project non-goal ([../../CLAUDE.md](../../CLAUDE.md) section 0a). A judge built from the same technology shares the failure modes of the thing it is judging, and agrees with it for exactly the reasons you needed an independent check. The substitute is a purpose-built scorer, plus the deterministic counterweights above, plus a small recurring human spot-check whose only job is to keep the automated scores calibrated.

## Bands, not raw numbers

Scores are bucketed into a small number of confidence bands, and the band - not the number - is what drives behaviour: what gets retried, what publishes with a visible low-confidence marker, and what a reader sees. Bands are tunable ([config.md](config.md)) and are re-calibrated against the human spot-checks rather than being fixed by taste.

A low-confidence item still publishes, marked. Hiding it would make the digest look better than it is, which is the opposite of the point.

## Per-item scores cannot see drift

Per-item scores measure variance *within a day*. Drift is a movement *across months*: the model runtime changed, a source redesigned its pages, a prompt was edited. Those are invisible in single-item scores and require a second instrument - a fixed set re-run on a schedule, producing a dated row, with alert thresholds on the aggregate.

Two design consequences:

- **Every drift row is version-stamped** with the runtime build, the model file hash and the scorer version. A deterministic output can change because the runtime changed, not because the model did, and a benchmark that cannot tell those apart raises false alarms.
- **The fixed set is refreshed on a schedule.** A frozen golden set stops representing the live corpus and quietly becomes a museum.

A drift detector that has never fired has not been shown to work; it is tested by replaying the set against a deliberately degraded input and confirming the alert fires.

## The ledger

Every item produces one row, appended to a committed CSV. It is appended by CI, read by the dashboard, and never recomputed at read time (Holy Law #1). The row shape is a contract like any other, versioned and changelogged ([../../CLAUDE.md](../../CLAUDE.md) section 11).

Committing the scores rather than deriving them is what makes a claim about last quarter a lookup instead of a re-run against a model that has since changed.

**The row is self-describing.** It carries the date, the source link and the title, not only the scores - so that a row still means something after the day it describes has been pruned from the published site. Those columns exist from the first row, because adding them after a prune cannot recover what was already lost.

**Run-level facts are not ledger rows.** How many items a run planned, finished and failed is a property of the run, not of any item, and it lives in the run manifest - which is committed, dated and published alongside the day. Widening the per-item row to carry a second kind of row would leave every item row with columns that are blank for it and would break the dashboard's one honest question: group the rows by band and count them.

**An item whose inputs did not change writes no row at all.** A re-run that changed nothing measured nothing, and a ledger padded with re-observations of the same summary makes every trend a function of how often the job ran. What counts as unchanged is the pipeline fingerprint ([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)), which is stamped on every row so a trend can be attributed to the inputs that produced it.

## See also

- [pipeline-loop.md](pipeline-loop.md) - where the Evaluate stage sits.
- [digest.md](digest.md) - how a confidence band reaches a reader.
- [config.md](config.md) - the band thresholds and retry budget.
- [principles.md](principles.md) - principle 6, the belief this page implements.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the eval-row contract.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - the stamp every row carries, and why an unchanged item writes none.
- [../../.github/agents/andre.agent.md](../../.github/agents/andre.agent.md) - the persona who owns metric choice.
