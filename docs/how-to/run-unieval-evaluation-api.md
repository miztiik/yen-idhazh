# Run the local UniEval API

**Last Updated**: 2026-11-04

How to prepare the named resources, start the real evaluator and retain its
actual four-score response. This is separate from workflow generation.
The [reference](../reference/unieval-api.md) owns request fields and modes.

## Prepare offline-check resources

From `services/summary_evaluator`, use the existing CPython 3.12 environment:

```powershell
uv sync --frozen --group dev
uv run --frozen python .\scripts\prepare-unieval-resources.py --root '..\..'
```

This prepares the pinned tokenizer and English sentence rules without
Torch or model weights. Tests download nothing and open no HTTP listener.
Missing resources fail with preparation instructions; they do not skip.
The [gate guide](run-the-gates.md#independent-python-service-contracts)
owns the normal lint/type commands and the Windows asyncio/socket-guard
limitation.

## Run the actual model

Use a separate environment so ordinary model-free checks remain separate:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) 'var\unieval-model-venv'
uv sync --frozen --extra model --group dev
uv run --frozen --extra model python .\scripts\prepare-unieval-resources.py --root '..\..' --include-weights
uv run --frozen --extra model python -m summary_evaluator --root '..\..' --settings '..\..\config\summary-evals\hhem-evaluator\settings.json' --routes unieval
```

The shared config owns the loopback address. This invocation loads no HHEM
model and starts no native llama process. Check UniEval's component health,
not only its listening socket.

Write a bounded JSON request with the exact source, generated summary and
independently supplied reference summary. Send that file as JSON data to the
named UniEval operation. Do not place any text into a shell expression,
destination or path.

Retain the complete native response even with an error HTTP status. Check
all four fields, actual loaded identity, selected consistency mode, source
spans and planned/completed counts. Missing work is not zero, and fewer than
four valid scores is not complete.

## Capture real offline predictions

In the model environment, run:

```powershell
uv run --frozen --extra model python .\scripts\capture-unieval-recordings.py --root '..\..'
```

The command reads only the named project-authored fixture inputs. It records
actual predictions with source-prompt hashes and loaded identity; it never
invents a result for a missing prompt. Commit only those bounded authored
inputs and actual JSON recordings, not downloaded assets, caches or model
environments.

Recorded responses prove offline API composition and reduction. They do
not prove live workflow integration, resource capacity or judging accuracy.

## See also

- [../reference/unieval-api.md](../reference/unieval-api.md) - requests, results and error meanings.
- [../architecture/evaluation/unieval-api.md](../architecture/evaluation/unieval-api.md) - complete-source calculation.
- [../reference/summary-evaluator-api.md](../reference/summary-evaluator-api.md) - shared listener and logging.
- [run-the-gates.md](run-the-gates.md) - normal selected checks.
