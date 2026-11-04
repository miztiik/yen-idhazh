# Generate and evaluate one summary

**Last Updated**: 2026-11-04

How to dispatch `summary-eval-tests.yml` and inspect the generated answer,
actual HHEM score, machine readings and owned-process cleanup. This procedure
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

## Select one model and supply the source

The form requires `source_text`. Optional `models_file` is the committed JSON
path relative to `config/`, not a repository identifier or a `config/`-prefixed
path. Its prefilled value matches `config/idhazh.json.models_file`. Blank uses
that pointer. The [model reference](../concepts/config/model-file.md) owns
declaration validation and pinned file semantics.

One run selects one summarizer. To compare declarations, dispatch separate
runs with the same source. The generation instruction stays fixed in
`config/summary-eval-tests.json`; neither dispatch changes the shared pointer.
There is no manual summary input or model matrix.

This command sends the named, project-authored source fixture through standard
input, not command arguments. Use the intended merged ref and retain its actual
`headSha` with the result.

```powershell
@'
import json
from pathlib import Path

path = Path("tests") / "fixtures" / "hhem-evaluator" / "model-inputs.json"
cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
case = next(value for value in cases if value["id"] == "supported")
print(json.dumps({
    "source_text": case["source_text"],
    "models_file": "",
}))
'@ | python - | gh workflow run summary-eval-tests.yml --ref main --json
```

The platform retains the source event. **The source and generated summary also
appear in the expandable report; the generated summary is in its declared
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
that exact same-run answer after confirmed native-model shutdown. A failed
generation must leave HHEM not run, without a zero score or numeric duration.
UniEval remains explicitly not run until its separate integration lands.

The report contains separate phase and server outcomes, actual startup times,
shutdown results and log names. An unavailable observation remains unavailable.
Normal completion needs a complete HHEM result, actual hardware and
whole-machine CPU/RAM, explicit uninterrupted profile close and clean confirmed
shutdown. A score alone does not close live verification.

If work fails, available results and the report still upload. The
`summary-eval-tests-server-logs` artifact retains available role logs after
errors or cancellation with the platform's default retention. Original and
cleanup errors remain separate, and completed generation/evaluation is not
erased by later reporting or measurement failures. A hard runner termination
cannot guarantee final upload.

Do not treat a terminal log line as model proof. Inspect the validated
generation/evaluator results and actual owned-process exits. No task adopts an
occupied listener, detaches a model or kills a process by name.

## Local checks and execution

Use the [gate guide](run-the-gates.md#independent-python-service-contracts) for
model-free checks. The workflow itself uses CPython 3.12, pinned Bun dependencies
and `uv --frozen --extra model --no-dev`. Its native executable and assets target
the stock Ubuntu runner. Do not relax ordinary test socket guards to run the
Linux ASGI coverage on Windows.

The visible tasks prepare named native assets, generate once through FastAPI,
stop the native model, evaluate through FastAPI and create the report.
The [Python](../reference/fastapi-server.md) and
[TypeScript](../reference/typescript-api-server.md) references own listener,
readiness and process controls. The published site needs neither server.

## See also

- [Summary workflow fields](../reference/summary-evaluation-workflow.md)
- [HHEM API](../reference/hhem-evaluation-api.md)
- [Whole-machine measurements](../reference/host-metrics.md)
- [Gate commands](run-the-gates.md)
