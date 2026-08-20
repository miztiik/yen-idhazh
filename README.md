# yen-idhazh

**Last Updated**: 2026-08-21

*idhazh* is Tamil for a journal or magazine. **yen-idhazh** is "my journal": a daily, self-evaluating article digest that reads the open web, summarizes it with a small language model, scores every summary for faithfulness, and publishes the result as static pages.

Nothing runs at read time. The whole pipeline executes in GitHub Actions on a stock runner, commits what it produced, and the published site is plain files.

## What it does

Once a day, in CI:

1. **Collect** candidate links from configured public sources.
2. **Extract** readable text from each page, sanitizing it at the trust boundary. The article body is never republished - only the link and our own summary.
3. **Summarize** each article with an open-weights model running on CPU under constrained decoding, so the output shape is pinned by a schema rather than by hope.
4. **Score** every summary twice for faithfulness - against the text the model actually saw, and against the full article - plus deterministic counterweights that faithfulness alone cannot see. Every score is appended to a committed ledger.
5. **Illustrate** an item only where a visual earns its place: numbers become a chart specification, a process becomes a diagram, and anything else gets nothing rather than a decorative picture with invented labels.
6. **Publish** a digest and an eval dashboard as static pages.

A failed item degrades and records why. It never takes down the run.

## Why it is built this way

Three constraints do most of the shaping, and they are stated in full in [CLAUDE.md](CLAUDE.md):

- **Static-first.** What reaches a reader is a static bundle. No backend, no runtime inference, no accounts, no telemetry, no calls home.
- **The runner is the architecture.** 4 vCPU, no GPU, a 6 h job cap and a 10 GB cache decide which model can be used and how work is sharded. The budget is the platform, not a preference.
- **Measured, not estimated.** Every throughput, cost and quality claim carries the hardware it was measured on, the date, and the spread. When a measurement contradicts the design, the design changes - and it already has once.

The evaluation loop is not a reporting afterthought. A summarizer whose faithfulness nobody measures is a machine for producing confident, plausible, wrong text; the ledger and the drift benchmark are what make the output trustworthy over months rather than on the day it was demonstrated.

## Layout

| Path         | What lives there                                                                                   |
| ------------ | -------------------------------------------------------------------------------------------------- |
| `backend/`   | The Python producer. Runs in CI and locally, never as a service. `backend/idhazh/contracts/` holds the Pydantic models that are the source of truth for every persisted shape. |
| `frontend/`  | The published static site - the digest and the eval dashboard - plus generated TypeScript contracts. |
| `config/`    | Human-edited tunable knobs, schema-validated. A fresh clone runs on the defaults.                   |
| `schemas/`   | JSON Schema generated from the Pydantic models. Never hand-edited.                                  |
| `evals/`     | The committed eval ledger the dashboard reads.                                                      |
| `docs/`      | Canonical knowledge, in Diataxis tiers.                                                             |
| `TODO/`      | Active plan-docs.                                                                                   |

Model weights and llama.cpp binaries are downloaded, not committed - see [docs/how-to/set-up-local-inference.md](docs/how-to/set-up-local-inference.md).

## Getting started

```
python -m venv .venv
.venv/bin/pip install -e ".[dev]"       # .venv/Scripts/pip on Windows
.venv/bin/python -m pytest              # tests
.venv/bin/python -m ruff check .        # lint
.venv/bin/python -m mypy                # strict type check
.venv/bin/python -m idhazh.contracts.export   # regenerate schemas/ from the models
```

`schemas/` is generated from the Pydantic models in `backend/idhazh/contracts/` and is never hand-edited; a test regenerates it and fails on any diff. Change the model, run the export, commit both.

The build plan is [TODO/20260815-digest-pipeline-plan.md](TODO/20260815-digest-pipeline-plan.md). Read [CLAUDE.md](CLAUDE.md) before changing anything.

## See also

- [CLAUDE.md](CLAUDE.md) - the engineering contract.
- [AGENTS.md](AGENTS.md) - the pointer coding agents start from.
- [docs/concepts/vision.md](docs/concepts/vision.md) - what this is and what it is not.
- [docs/concepts/pipeline-loop.md](docs/concepts/pipeline-loop.md) - the stages and what each one owns.
- [docs/concepts/evaluation.md](docs/concepts/evaluation.md) - how a summary is scored and why.
