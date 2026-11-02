# Run one manual HHEM evaluation

**Last Updated**: 2026-11-02

How to send supplied source and summary text to the independent CPU evaluator
and inspect its score and whole-machine measurements. This procedure is
project-specific because it uses the committed model selection, named workflow
and existing host instrument. It does not fetch an article or make a summary.

## Prepare and register

The [API reference](../reference/hhem-evaluation-api.md) owns fields and limits.
For local development, use CPython 3.12, uv and Bun. From the repository root:

```powershell
bun install --frozen-lockfile --cwd .\services\host-probes
bun install --frozen-lockfile --cwd .\services\host-fingerprints
bun install --frozen-lockfile --cwd .\packages\common-contracts
bun install --frozen-lockfile --cwd .\packages\ledger-file-writer
uv sync --frozen --group dev --project .\services\hhem-evaluator
```

The [gate guide](run-the-gates.md#independent-python-service-contracts) includes
the native compatibility checks. The model extra is not part of ordinary CI.

The first hosted run has two steps. First merge the fully checked feature PR
that adds `.github/workflows/hhem-evaluation-api-test.yml` to the default
branch. Then dispatch a branch or tag containing the merged change.
A feature-branch `--ref` cannot register a workflow that has never existed on
the default branch.
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
The CLI selects a branch or tag. Use `main` for the delivery run and record
its actual `headSha`.

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
'@ | python - | gh workflow run hhem-evaluation-api-test.yml --ref main --json
```

The platform creates and retains the dispatch event. **Both texts also appear
in the expandable Markdown summary and report artifact.** Do not supply
credentials or private material. The caller reads only the named
`GITHUB_EVENT_PATH`, within its declared byte allowance. Neither text enters
a command, environment expression, URL or log. The API result and JSON
evidence remain body-free.

## Inspect the real run

Find the run and confirm its `headSha` is the intended commit:

```powershell
gh run list --workflow hhem-evaluation-api-test.yml --limit 5 --json databaseId,headSha,status,conclusion,url
gh run view <run-id> --log
gh run download <run-id> --name summary-eval-hhem-report --dir <evidence-directory>
```

The artifact contains only `evaluation.json` and `report.md`. Report Creator
writes one Markdown file and appends the same file to the summary. Its model
configuration, actual-work and hardware tables show the loaded revision,
score, seconds rounded upward to three decimal places, machine readings and
worker details. Expand each text disclosure to check the supplied pair.
`summary-eval-unieval` must say it was not run and have no numeric score or time.
The JSON retains the actual terminal request event ID for comparison with logs.

Normal enabled evidence requires a complete evaluation, an explicit
uninterrupted profile stop, actual machine CPU and sampled RAM, and
confirmed clean owned shutdown. An unavailable reading alone does not complete
the hosted proof, even if scoring succeeded.

CPU is a share of the whole machine, from zero to 100 percent. Background
work is included. This is not HHEM process usage or percent of one core.
Stored RAM counters use KiB; the summary shows closing machine use in MiB,
not peak memory. Actual hardware and UTC
measurement endpoints appear beside it.
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

Cancelled or interrupted measurement is not complete coverage. Missing
readings retain exact native reasons. Worker replacement remains an API
failure concern, not a reason to relabel machine readings as worker usage.

The caller owns only the two services it starts. A private startup packet and
matching evaluator health prevent adoption of an occupied listener. The host
helper uses the existing TypeScript hardware API and task-profile SDK.
It selects whole-machine CPU/RAM while leaving shared host configuration
files unchanged. Hardware ledger files stay disposable; there is no Git
commit or push. Both launchers close on parent-pipe EOF.
The API launcher's protocol channels are not inherited by model-library
helpers. Raw runtime diagnostics cannot become control packets or native events.
Finally, the caller stops the profile, then joins both owned services with
bounded escalation. The host collector closes before the API worker.
It neither detaches helpers nor kills processes by name.
An unconfirmed shutdown is a failure, not successful delivery.

## See also

- [../reference/hhem-evaluation-api.md](../reference/hhem-evaluation-api.md) - native fields, bounds and report meanings.
- [../reference/summary-evaluation-workflow.md](../reference/summary-evaluation-workflow.md) - report format and host measurement ownership.
- [../reference/host-probe-api.md](../reference/host-probe-api.md) - existing pinned-process commands.
- [run-the-gates.md#independent-python-service-contracts](run-the-gates.md#independent-python-service-contracts) - offline preparation and checks.
- [../architecture/evaluation/hhem-evaluation-api.md](../architecture/evaluation/hhem-evaluation-api.md) - the actual scoring controller and lifetime boundary.
