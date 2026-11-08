# Run the local UniEval API

**Last Updated**: 2026-11-08

How to prepare the named resources, start the real evaluator and retain its
actual applicable-score response. This is separate from workflow generation.
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
uv run --frozen --extra model python -m summary_evaluator --root '..\..' --routes unieval
```

The committed `listeners.unieval` configuration owns this API's loopback address,
with default port 3011. This invocation loads no HHEM
model and starts no native llama process. Check UniEval's component health,
not only its listening socket. Stopping this API does not stop a separately
running HHEM or coverage API or worker.

Write a bounded JSON request with the exact source and generated summary.
Omit the reference for ordinary evaluation. For reference agreement, supply the
independent reference and explicitly set `evaluate_relevance` true. A reference
alone does not enable relevance. Send that file as JSON data to the
named UniEval operation. Do not place any text into a shell expression,
destination or path.

Omit `consistency_source_mode` to use the committed `full_source_prompt`
default: every native summary sentence is compared with the complete source.
Select `all_source_windows` explicitly for sentence-by-window consistency,
or choose it in committed scorer configuration. Both existing mode spellings
are valid explicit controls. An oversized complete input has no automatic
retry or truncation; consistency windows do not shorten coherence's complete
source/summary input. The configured token allowance is a resource policy,
not a fixed model context maximum.

Retain the complete native response even with an error HTTP status. Check
all four fields, actual loaded identity, selected consistency mode, source
spans and planned/completed counts. Three applicable scores with an authorized
relevance skip and no errors are complete. Missing required work is not zero;
an attempted relevance failure is not a skip. Supplied but unused reference
bytes still have a hash.

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
- [../reference/summary-evaluator-api.md](../reference/summary-evaluator-api.md) - per-scorer listeners and logging.
- [run-the-gates.md](run-the-gates.md) - normal selected checks.
