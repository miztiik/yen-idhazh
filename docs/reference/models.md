# Models

**Last Updated**: 2026-09-21
One row per model. Each row points at a model's dossier - the page holding that
model's identity and measured properties, with the hardware that took each
reading, the date and the spread.

| Model | Role | Dossier |
| --- | --- | --- |
| Qwen3.5-9B-Q4_K_M | summarizer | [models/qwen3.5-9b-q4km.md](models/qwen3.5-9b-q4km.md) |
| Gemma-4-E4B-it-qat-UD-Q4_K_XL | summarizer candidate | [models/gemma-4-e4b-qat.md](models/gemma-4-e4b-qat.md) |
| Ornith-1.5-9B-Q5_K_M | summarizer candidate | [models/ornith-1.5-9b-q5km.md](models/ornith-1.5-9b-q5km.md) |

A bench records speed and memory. Qualification is the separate judgement of
whether a candidate writes summaries well enough to publish.

**A number on one dossier may not be divided by a number on another.** GitHub
places each job where it likes, and seventeen bench dispatches have landed on four
different processors - EPYC 7763, EPYC 9V45, EPYC 9V74 and Intel Xeon Platinum
8573C. The same weights read up to 3.9 times faster on the fastest of those than
on the slowest, which is far more than any gap between these three models. Every
table says which machine took it, and a comparison that ignores that is measuring
the fleet, not the model. What each machine is worth:
[benchmarks/the-processor-lottery.md](benchmarks/the-processor-lottery.md).

## What earns a dossier

A model earns a page here when it is a **candidate for a role the pipeline
runs** - today that is the summarizer. Qualifying a model produces a verdict, and
a verdict with nowhere to live is a verdict nobody finds again.

**A model that ran and has no page here is not missing; its readings are.** Three
are in that position: the retired Qwen3-8B-Q4_K_M summarizer, the Qwen3-4B-Q4_K_M
visual planner whose job retired on 2026-09-13, and the
`vectara/hallucination_evaluation_model` faithfulness scorer, which grades
offline and never touches a published summary. Their figures stay where they were
taken, in [pipeline-cost.md](pipeline-cost.md), each labelled with whose they are.
Writing them a dossier would move readings nothing reads; the rule that would
bring one here is a model taking a live role.

**One model can have more than one file, and two models do.**
`qwen3.5-9b-q4km-thinking.json` is a configuration file with
`turns.thinking_close` declared, so the same weights reason before they answer.
`gemma-4-e4b-qat-no-draft.json` is the candidate's file with its
`companion_files` list empty, so the same weights run without the
multi-token-prediction head its publisher ships - which is the control that
measures what the head is worth
([benchmarks/what-the-draft-head-is-worth.md](benchmarks/what-the-draft-head-is-worth.md)).
Each pair carries one `sha256`, so the same digest identifies both entries for
its weights. Config selects one file and the runtime follows that entry
([../architecture/summarize/model-boundary.md](../architecture/summarize/model-boundary.md)).

**A second file earns no second dossier.** This index is organised by subject -
one page a model - so a file that names weights already on a page is described
there rather than given a page of its own. The test is the `sha256`: same digest,
same page. Two files over one set of weights share one dossier.

## A dossier is not a benchmark record

The two classes sit next to each other in `docs/reference/` and answer different
questions, so a figure belongs to exactly one of them.

| | A dossier | A benchmark record |
| --- | --- | --- |
| Organised by | the subject - one page a model | the question - one page a measurement |
| Carries | every quantity for one model, one current reading each | one run: its conditions, method, cases and raw figures |
| A re-run | replaces the reading on the dossier | replaces the whole page |
| Answers | "what is this model?" | "what did that run settle?" |

A dossier links to every record taken against its model. A record names the
weights it ran on and does not restate the dossier.
[documentation-structure.md](documentation-structure.md) carries both class
definitions.

## See also

- [models/qwen3.5-9b-q4km.md](models/qwen3.5-9b-q4km.md) - Qwen3.5 model dossier.
- [models/gemma-4-e4b-qat.md](models/gemma-4-e4b-qat.md) - a benched candidate.
- [models/ornith-1.5-9b-q5km.md](models/ornith-1.5-9b-q5km.md) - a benched candidate.
- [pipeline-cost.md](pipeline-cost.md) - the instrument log: everything measured that is not a property of one model.
- [documentation-structure.md](documentation-structure.md) - where each kind of page lives, and what a dossier may not hold.
- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - measure a candidate, adopt it in one line, and put the old one back in the same line.
- [../architecture/summarize/model-boundary.md](../architecture/summarize/model-boundary.md) - what a swap invalidates, and what has to be retaken.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #2 (the runner is the architecture) and Guardrail #10 (one current reading a quantity).
