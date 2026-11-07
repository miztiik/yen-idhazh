# Capture source-coverage calls

**Last Updated**: 2026-11-07

How to retain actual legacy dimension calls before comparing a relocated
calculation. This page contains project bindings: the named scorer, resource
configuration and recording contracts are specific to this repository.

## Prepare the real model environment

Use CPython 3.12 and the evaluator's frozen manifest. Keep the model extra in
a separate environment so ordinary checks do not inherit Torch or weights.
From the repository root:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) 'services\summary_evaluator\var\model-venv'
uv sync --project .\services\summary_evaluator --frozen --extra model --group dev
uv run --project .\services\summary_evaluator --frozen --extra model python .\services\summary_evaluator\scripts\prepare-coverage-resources.py --root . --include-weights
```

`config/summary-evals/unieval-evaluator/coverage.json` declares the immutable
legacy code, model and tokenizer resources, named sentence files and exact
preparation defaults. Preparation checks the upstream code digests and
sentence archive before extracting only the named files.

The upstream loader accepts a repository name but not a revision argument.
Preparation binds that name to the verified snapshot in its private cache.
Loading requires offline resolution and checks the observed model revision;
it must never silently follow a newer model revision.

Rank BM25 supplies the existing evidence retrieval. Prettytable satisfies the
upstream import instead of an in-memory stub. These dependencies add small
library installations to model-free checks, not Torch or model weights.

## Capture genuine calls

Commit the concrete model-call boundary before capture. Its actual repository
revision and file digest are provenance, not a claim about a different checkout.
Then run with the already-prepared resources:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTHONPATH = 'backend'
uv run --project .\services\summary_evaluator --frozen --extra model python .\services\summary_evaluator\scripts\capture-coverage-recordings.py --root .
```

The utility reads only
`tests/fixtures/summary-evaluation/coverage-recording-inputs.json` and writes
`tests/fixtures/summary-evaluation/coverage-model-recording.json` atomically.
The backend recording contract owns the date-stamped current-only family.
It declares finite input allowances, UTC capture time, actual producer and
resource identities, runtime/platform observations, effective settings,
ordered dimension-call inputs/results and final metrics.

A final HTTP response is only wire or historical-readback evidence. It cannot
replace the actual model-call recording, and scores must not be inferred or
back-calculated from it. A failed preparation, model call or validation writes
no success-shaped recording.

## Check the evidence separately

Replay recorded model calls through the real preparation, retrieval and
reduction. Exact valid metrics and sentence/chunk evidence establish
calculation parity, not model quality or fresh-run numerical reproducibility.
The real capture does not replace the complete model-free Linux suites or
ordinary CI described in the [gate guide](run-the-gates.md).

Verify the real owned child after integration without overwriting the retained
before-calculation recording:

```powershell
uv run --project .\services\summary_evaluator --frozen --extra model python .\services\summary_evaluator\scripts\verify-coverage-worker.py --root .
```

This bounded utility reads one named input, starts the actual coverage worker
over private byte pipes, validates readiness/completion and confirms its owned
exit. It opens no HTTP listener and reports actual observations, not a Linux
model-free inference claim.

Commit only the named inputs and validated recording. Do not commit caches,
weights, environments or raw upstream diagnostics. In a fresh shell, ordinary
checks use the evaluator's default model-free environment again.

## See also

- [../reference/unieval-api.md](../reference/unieval-api.md) - the independent native method.
- [../reference/summary-evaluator-api.md](../reference/summary-evaluator-api.md) - shared listener and component selection.
- [run-the-gates.md](run-the-gates.md#independent-python-service-contracts) - model-free verification and Linux evidence.
