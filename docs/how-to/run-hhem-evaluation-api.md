# Run one manual HHEM evaluation

**Last Updated**: 2026-11-02

How to send supplied source and summary text to the independent CPU evaluator
and inspect evidence from its actual scoring process. This procedure is
project-specific because it uses the committed model selection, named workflow
and existing host instrument. It does not fetch an article or make a summary.

## Prepare and register

The [API reference](../reference/hhem-evaluation-api.md) owns fields and limits.
For local development, use CPython 3.12, uv and Bun. From the repository root:

```powershell
bun install --frozen-lockfile --cwd .\services\host-probes
uv sync --frozen --group dev --project .\services\hhem-evaluator
```

The [gate guide](run-the-gates.md#independent-python-service-contracts) includes
the native compatibility checks. The model extra is not part of ordinary CI.

The first hosted run has two steps. First merge the fully checked feature PR
that adds `.github/workflows/hhem-evaluation-api-test.yml` to the default
branch. Then dispatch the exact merged ref. A feature-branch `--ref` cannot
register a workflow that has never existed on the default branch.
This is the platform's
[manual-dispatch requirement](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
Keep hosted verification pending until the real run succeeds; PR checks alone
do not prove model loading, socket startup or live CPU/RAM collection.

## Dispatch supplied text

The workflow has exactly two required string inputs: `source_text` and
`summary_text`. Its checked-out ref and committed settings select the model.
The source becomes the primary comparison; a second full-source comparison
is explicitly off. There is no model selector or engine matrix.

The following command sends the named, project-authored `supported` fixture
through standard input, not shell arguments or another text-bearing file.
Replace `<merged-ref>` with the merged commit to verify.

```powershell
@'
import json
from pathlib import Path

path = Path("tests") / "fixtures" / "hhem-evaluator" / "model-inputs.json"
cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
case = next(value for value in cases if value["id"] == "supported")
print(json.dumps({
    "source_text": case["source_text"],
    "summary_text": case["summary_text"],
}))
'@ | python - | gh workflow run hhem-evaluation-api-test.yml --ref <merged-ref> --json
```

The platform creates and retains the dispatch event. Do not put credentials in the
inputs. The caller reads only the named `GITHUB_EVENT_PATH`, with its declared
byte allowance, and makes no additional text-bearing file. Neither text is
inserted into a command, environment expression, URL, log, summary or artifact.

## Inspect the real run

Find the run and confirm its `headSha` is the selected ref:

```powershell
gh run list --workflow hhem-evaluation-api-test.yml --limit 5 --json databaseId,headSha,status,conclusion,url
gh run view <run-id> --log
gh run download <run-id> --name hhem-evaluation-report --dir <evidence-directory>
```

The artifact contains only `report.json` and `report.md`. The JSON uses the
native workflow-report reader; the Markdown gives a short, body-free view.
Inspect the score, loaded revisions and digests, scoring process ID (PID) and
kernel start-time counter, terminal event link, timings, resource interval and
owned shutdown.
The event link must name the actual emitted terminal request event.

Normal enabled evidence requires a complete evaluation, the same initial and
final worker, an explicit uninterrupted profile stop, actual process CPU and
sampled RAM, and clean shutdown. An unavailable reading alone does not complete
the hosted proof, even if scoring succeeded.

CPU is percent of one core, not a share of the whole machine. One busy core
means 100 percent; a process using several cores can exceed 100 percent.
Stored RAM uses Linux KiB; the summary also shows MiB. The sampled maximum is
the largest observed resident memory reading, not a promise to catch every
short peak. Actual host conditions and measured intervals appear beside it.
See the [host measurement reference](../reference/host-metrics.md#whole-task-typescript-samples)
for the instrument's meaning and limitations.

Profiling starts after model readiness and stops before the scoring worker.
Download and model loading are excluded. The caller does not impose affinity,
CPU quotas, memory caps or fixed compute thread counts. A supported fixture
proves execution and collection, not factual-accuracy calibration or a speed
threshold.

## Inspect failures and cleanup

A validated score remains in the report when measurement or shutdown fails.
Original failures and cleanup failures are separate. Error HTTP responses are
validated with the same native result reader, so completed partial scores
are not lost. Actual HTTP or operational failures make the workflow step fail.
Missing measurements remain null with the native reason, never invented zeroes.

An exited, reused or replaced worker makes resource coverage incomplete.
The existing handle is never moved to another process, and interrupted CPU
percentages or RAM peaks are never added into a claimed whole-run reading.
Disabled profiling is reported explicitly without preventing scoring.

The caller owns only the two services it starts. A private startup packet and
matching evaluator health prevent adoption of an occupied listener. The host
launcher uses `config/hhem-evaluator/host-probes.json`; it leaves the global
host configuration unchanged. Both launchers close on parent-pipe EOF.
The API launcher's protocol channels are not inherited by model-library
helpers. Raw runtime diagnostics cannot become control packets or native events.
Finally, the caller stops the profile, then joins both owned services with
bounded escalation. The host collector closes before the API worker, including
when a failed start or stop left no usable profile handle.
It neither detaches helpers nor kills processes by name.
An unconfirmed shutdown is a failure, not successful delivery.

## See also

- [../reference/hhem-evaluation-api.md](../reference/hhem-evaluation-api.md) - native fields, bounds and report meanings.
- [../reference/host-probe-api.md](../reference/host-probe-api.md) - existing pinned-process commands.
- [run-the-gates.md#independent-python-service-contracts](run-the-gates.md#independent-python-service-contracts) - offline preparation and checks.
- [../architecture/evaluation/hhem-evaluation-api.md](../architecture/evaluation/hhem-evaluation-api.md) - the actual scoring controller and lifetime boundary.
