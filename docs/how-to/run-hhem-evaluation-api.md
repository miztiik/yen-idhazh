# Generate and evaluate one summary

**Last Updated**: 2026-11-07

How to dispatch `summary-eval-tests.yml` and inspect the generated answer,
actual HHEM and four UniEval scores, machine readings and owned-process cleanup. This procedure
is project-specific because it uses committed model declarations and the
named shared services.

## Register before dispatch

Merge the checked implementation onto the default branch before dispatching
the new workflow by name. A feature-branch `--ref` cannot register a workflow
that has never existed there. This is the platform's
[manual-dispatch requirement](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

Keep live verification pending until a real model run has been inspected.
Registration, offline recordings and green PR checks do not prove live
generation, evaluator loading, host observations or cleanup.

## Select one model and supply the source and independent reference

The form requires `source_text` and an independently written
`reference_summary_text` for that source. The reference is captured before
generation and sent only to UniEval, not to the summarizer or HHEM.
Optional `models_file` is the committed JSON
path relative to `config/`, not a repository identifier or a `config/`-prefixed
path. Its prefilled value matches `config/idhazh.json.models_file`. Blank uses
that pointer. The [model reference](../concepts/config/model-file.md) owns
declaration validation and pinned file semantics.

One run selects one summarizer. To compare declarations, dispatch separate
runs with the same source and reference. The generation instruction stays fixed in
`config/summary-evals/workflow.json`; neither dispatch changes the shared pointer.
There is no manual summary input or model matrix.

This command sends the named, project-authored source/reference fixture through standard
input, not command arguments. Use the intended merged ref and retain its actual
`headSha` with the result.

```powershell
Get-Content -Raw .\tests\fixtures\unieval-evaluator\workflow-inputs.json |
  gh workflow run summary-eval-tests.yml --ref main --json
```

The platform retains the input event. **Source, generated summary and independent
reference appear in the expandable report; the generated summary is in its declared
result artifact.** Do not supply private material or credentials. Diagnostic
logs and evaluator JSON remain body-free.

## Inspect the actual result

```powershell
gh run list --workflow summary-eval-tests.yml --limit 5 --json databaseId,headSha,status,conclusion,url
gh run view <run-id> --log
gh run download <run-id> --name summary-eval-tests-report --dir <evidence-directory>
```

The [workflow reference](../reference/summary-evaluation-workflow.md) owns the
named artifacts and field meanings. Confirm that the report's selected
declaration, loaded model and answer match `generation.json`. HHEM must score
that exact same-run answer after confirmed native-model shutdown. UniEval must
score the identical source/answer pair and identify the independently supplied
reference hash. A failed generation must leave both evaluators not run, without
a zero score or numeric duration.

The named fixture requires multiple tokenizer-sized source windows. With the
pinned tokenizer, even its complete source-only coherence prompt exceeds the
original 1024-token cutoff. Inspect the actual generated answer's native
coherence prompt: it must exceed that cutoff and fit the configured total
allowance without clipping. Require all four actual scores, every planned
sentence/window comparison, source spans from zero through the source's final
character, both independently stopped API processes and their joined worker exits. Three completed dimensions, an
unexercised larger setting or an offline recording cannot close live proof.

The report contains separate phase and server outcomes, actual startup times,
shutdown results and log names. An unavailable observation remains unavailable.
Normal completion needs a complete HHEM result and all four UniEval dimensions,
actual hardware and
whole-machine CPU/RAM, explicit uninterrupted profile close and clean confirmed
shutdown. A score alone does not close live verification.

If work fails, available results and the report still upload. The
`summary-eval-tests-server-logs` artifact retains available role logs after
errors or cancellation with the platform's default retention. Original and
cleanup errors remain separate, and completed generation/evaluation is not
erased by later reporting or measurement failures. A hard runner termination
cannot guarantee final upload.

If preparation fails, inspect `run.json` and the report's Preparation row before
looking for a generation receipt. The original safe preparation error is kept;
generation and both evaluators remain not run. Missing server logs are expected before
server startup. `ASSET_AUTH_MISSING` means the preparation step did not receive
the platform token needed by the existing pinned-release lookup.

Do not treat a terminal log line as model proof. Inspect the validated
generation/evaluator results and actual owned-process exits. No task adopts an
occupied listener, detaches a model or kills a process by name.

## Local checks and execution

Use the [gate guide](run-the-gates.md#independent-python-service-contracts) for
model-free checks. The workflow itself uses CPython 3.12, pinned Bun dependencies
and `uv --frozen --extra model --no-dev`. Its native executable and assets target
the stock Ubuntu runner. Do not relax ordinary test socket guards to run the
Linux ASGI coverage on Windows.

The visible tasks prepare named native assets, generate once through the native server,
stop the native model, evaluate through separate scorer APIs and create the report.
Machine preparation installs shared hosting, fingerprinting and probes without
feed-ingest-plan or data-delivery. It copies only named machine configuration;
`config/hono-server.json` owns the listener and supervision waits.
The [evaluator](../reference/summary-evaluator-api.md) and
[pipeline API](../reference/serve-pipeline-apis.md) references own listener,
readiness and process controls. The published site needs neither server.

## See also

- [Summary workflow fields](../reference/summary-evaluation-workflow.md)
- [HHEM API](../reference/hhem-evaluation-api.md)
- [UniEval API](../reference/unieval-api.md)
- [Whole-machine measurements](../reference/host-metrics.md)
- [Gate commands](run-the-gates.md)
