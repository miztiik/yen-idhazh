# Models

**Last Updated**: 2026-09-14

One row a model. Each row points at that model's **dossier** - the page holding
that model's identity and its one current reading of every quantity, with the
hardware that took it, the date and the spread.

| Model | Status | Role | Dossier |
| --- | --- | --- | --- |
| Qwen3.5-9B-Q4_K_M | `incumbent` | summarizer | [models/qwen3.5-9b-q4km.md](models/qwen3.5-9b-q4km.md) |

Today there is one. The table is short because a swap is rare, not because it is
incomplete.

## What the status word means

A dossier's status line is **the only place a model's lifecycle is written**. It
holds one of three words, and nothing else in the repository carries a second
copy of it.

| Word | What is true |
| --- | --- |
| `evaluated` | it has been qualified and has never served a published item |
| `incumbent` | it serves its role now, and the readings on its dossier are the ones in force |
| `superseded` | it served the role and something else does now; its dossier is a historical record and its figures may not be quoted as current |

An adopt moves one model to `incumbent` and the model it replaced to
`superseded`, and a revert moves both back. Because the word lives in one place,
the two edits are the whole of the change.

## What earns a dossier

A model earns a page here when it is a **candidate for a role the pipeline
runs** - today that is the summarizer. Qualifying a model produces a verdict, and
a verdict with nowhere to live is a verdict nobody finds again.

**A model that ran and has no page here is not missing; its readings are.** Three
are in that position: the retired Qwen3-8B-Q4_K_M summarizer, the Qwen3-4B-Q4_K_M
visual planner whose job retired on 2026-09-13, and the
`vectara/hallucination_evaluation_model` faithfulness scorer, which grades
offline and never touches a published summary. Their figures stay where they were
taken, in [measurements.md](measurements.md), each labelled with whose they are.
Writing them a dossier would move readings nothing reads; the rule that would
bring one here is a model taking a live role.

## What the model in force actually is

`config/idhazh.json` carries one line naming which model file is active -
`models_file` - and that file holds the whole entry. This page and the dossier it
points at are a description of it, so when the two disagree the config is right
and the dossier is stale. Two commands print what is in force:

```text
git grep -n '"models_file"' -- config/idhazh.json
git grep -n -E '"(id|file|sha256)"' -- config/models/
```

The first names the active file; the second prints the configuration id, the
weight file and the SHA-256 the runtime checks the downloaded bytes against.

## A dossier is not a benchmark record

The two classes sit next to each other in `docs/reference/` and answer different
questions, so a figure belongs to exactly one of them.

| | A dossier | A benchmark record |
| --- | --- | --- |
| Organised by | the subject - one page a model | the question - one page a measurement |
| Carries | every quantity for one model, one current reading each | one run: its conditions, method, arms and raw figures |
| A re-run | replaces the reading on the dossier | replaces the whole page |
| Answers | "what is this model?" | "what did that run settle?" |

A dossier links to every record taken against its model. A record names the
weights it ran on and does not restate the dossier.
[documentation-structure.md](documentation-structure.md) carries both class
definitions.

## See also

- [models/qwen3.5-9b-q4km.md](models/qwen3.5-9b-q4km.md) - the configured summarizer.
- [measurements.md](measurements.md) - the instrument log: everything measured that is not a property of one model.
- [documentation-structure.md](documentation-structure.md) - where each kind of page lives, and what a dossier may not hold.
- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - measure a candidate, adopt it in one line, and put the old one back in the same line.
- [../architecture/summarize/model-boundary.md](../architecture/summarize/model-boundary.md) - what a swap invalidates, and what has to be retaken.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #2 (the runner is the architecture) and Guardrail #10 (one current reading a quantity).
