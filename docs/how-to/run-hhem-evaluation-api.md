# Generate and evaluate one summary

**Last Updated**: 2026-11-09

How to dispatch `summary-eval-tests.yml` and inspect the generated answer,
actual HHEM and applicable UniEval scores, machine readings and owned-process cleanup. This procedure
is project-specific because it uses committed model declarations and the
named shared services.

## Register before dispatch

Register a new workflow on the default branch before dispatching it by name.
An already registered workflow can run an immutable candidate revision through
its feature-branch `--ref`. A feature-branch ref cannot register a workflow
that has never existed there. This is the platform's
[manual-dispatch requirement](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

Keep live verification pending until a real model run has been inspected.
Registration, offline recordings and green PR checks do not prove live
generation, evaluator loading, host observations or cleanup.

## Select one model and supply the source

The form requires `source_text`. The optional reference is independently written
`reference_summary_text` for that source. Select `evaluate_relevance` explicitly
to evaluate agreement; its false default does not depend on reference presence.
The exactly empty form reference means absent; whitespace-only text is invalid.
Leave optional string `consistency_source_mode` blank to follow scorer
configuration, whose default is `full_source_prompt`. Enter that spelling or
`all_source_windows` for an explicit override; every other nonempty value is
invalid. Full-source consistency still compares individual summary sentences.
An oversized input is not retried in another mode or clipped. Explicit
consistency windows do not make oversized full-source coherence fit.
When supplied, the reference is captured before
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
input, not command arguments. It explicitly selects its four-score, windowed journey
without changing the fixture's source or reference.
Use the intended verified ref and retain its actual
`headSha` with the result.

```powershell
$inputs = Get-Content -Raw .\tests\fixtures\unieval-evaluator\workflow-inputs.json |
  ConvertFrom-Json -AsHashtable
$inputs["consistency_source_mode"] = "all_source_windows"
$inputs | ConvertTo-Json -Compress |
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
reference hash when present, even if unused. A reference-free run requires all
three applicable UniEval scores, the authorized skip reason, no relevance
comparisons and confirmed API/worker cleanup. A failed generation must leave both evaluators not run, without
a zero score or numeric duration.

For the explicitly opted-in named fixture, require its four-score journey.
Its explicit window selection requires multiple tokenizer-sized source spans. With the
pinned tokenizer, even its complete source-only coherence prompt exceeds the
upstream scorer's configurable constructor default. Inspect the actual generated answer's native
coherence prompt: it must exceed that default and fit the configured resource
allowance without clipping. Require all four actual scores, every planned
sentence/window comparison, source spans from zero through the source's final
character, both independently stopped API processes and their joined worker exits. Three completed dimensions, an
unexercised larger setting or an offline recording cannot close live proof.

For the default full-source mode, require one complete original-source span
and one consistency comparison per native summary sentence, not a single
whole-summary score. Check the report's actual mode against the submitted
override or resolved scorer configuration. The
[native token-policy rationale](../architecture/evaluation/unieval-api.md#design-rationale)
owns the distinction between resource allowance and model metadata.

The report contains separate phase and server outcomes, actual startup times,
shutdown results and log names. An unavailable observation remains unavailable.
Normal completion needs a complete HHEM result and every applicable UniEval dimension,
actual hardware and
whole-machine CPU/RAM, explicit uninterrupted profile close and clean confirmed
shutdown. A valid relevance skip is not a failure. A supplied but unused reference
must be labelled unused. A score alone does not close live verification.
For a native size failure, read the affected score's complete-input token count,
configured allowance and comparison index. Missing measurements are not
estimated. A window-geometry refusal describes unavailable source progress
and overlap, not an oversized-input count. Completed siblings and HHEM
outcomes must remain in the saved response and report.

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
