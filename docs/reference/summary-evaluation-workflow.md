# Summary evaluation workflow

**Last Updated**: 2026-11-02

Which controls, measurements and report fields belong to the manual
`summary-eval-hhem` workflow, rather than the evaluator API.

## Ownership and steps

`.github/scripts/summary-eval-hhem/` owns orchestration and Report Creator.
The registered workflow remains `hhem-evaluation-api-test.yml`. It accepts
exactly two required text inputs. Its steps prepare locked dependencies,
start the existing API, check health, measure the machine during one HHEM
evaluation, stop owned work, create the report and upload the two named files.
The collection step uses named log groups for its live tasks.
`summary-eval-unieval` is explicitly not run; no second engine, score or
duration is fabricated.

The API operation is
`POST /api/2026-11-02/summary-eval-hhem`. HTTPX uses the committed loopback
address, disables environment proxies and redirects, and enforces time and
response limits. An error-status response still passes through the native
result reader. There is one request and no evaluation retry.

## Caller controls

Table A - `config/summary-eval-hhem.json`

| ID | Field | Meaning |
| --- | --- | --- |
| A1 | `event_envelope_bytes` | 65536 bytes (64 KiB) above the API body allowance when reading only `GITHUB_EVENT_PATH`. The encoded request must still fit the API allowance. |
| A2 | `max_response_bytes`, `control_max_bytes` | 2097152 bytes (2 MiB) per response or evidence read; 16384 bytes (16 KiB) per private control packet. |
| A3 | `http_connect_timeout_ms`, `poll_interval_ms` | 5000 milliseconds (five seconds) for connection; 100 milliseconds between readiness observations. The response deadline covers queue, evaluation and bounded worker cleanup, plus connection time. |
| A4 | `pipeline_name`, `task_name` | Committed labels, never derived from either text. The run identity uses the UTC day and platform run number. |
| A5 | `output_directory` | `backend/var/summary-eval-hhem`, one disposable run directory. Only `evaluation.json` and `report.md` are uploaded. |

Both texts remain data. They never enter shell, argument, environment,
destination or path expressions. Only Report Creator reads them again from
the bounded platform event, to put escaped literal text in the Markdown.
The API response, events and `evaluation.json` remain body-free.

## Existing host instruments

The owned Bun helper calls the existing TypeScript hardware API through
`captureLocalFingerprint`. Its normal native ledger writer persists under
the run's `host/` directory. No files are committed or pushed.
Shared controls remain `config/host-fingerprints.json`, `config/idhazh.json`
and `config/host-probes.json`; there is no evaluator-specific host config or
collector endpoint.

The helper selects task profiling and whole-machine RAM for this invocation.
Process RAM is off. Shared sampling and lifecycle bounds remain unchanged.
It awaits the opening observation before evaluation and explicitly closes
the profile before stopping the API. This excludes model download/loading
and includes background work on the machine. CPU is aggregate machine
utilization from zero to 100 percent, not percent of one worker core.
RAM use is the closing observation, displayed in MiB; native counters remain
in KiB. It is not a peak-memory claim.

The Python reader copies only consumed native fields. The named Bun bridge
checks their types, requiredness, nullability and vocabularies against the
real native schemas. Missing preparation fails instead of skipping.
Missing readings stay null with exact native reasons. Cancellation or an
interrupted profile is not complete coverage.

## Evidence and Markdown

`summary_eval_pipeline/contracts.py` owns `PipelineEvidence` and its
date-stamped schema metadata. `evaluation` is the actual native API result,
not another score model. `hardware` is the native hardware projection;
`machine` contains the native CPU observation, UTC interval, sampled machine
RAM minimum and retained machine observations. `shutdown` records
both owned services and explicit model-worker exit confirmation. `errors`
keeps original and cleanup failures separate. `unieval` is `not_implemented`.

Complete requires a complete evaluation, collected hardware, real CPU/RAM,
an uninterrupted explicit profile close and clean confirmed shutdown.
Partial retains a valid primary score when another requirement fails;
failed has no completed primary score. These are same-run artifacts, not
inputs to future runs. The retired worker-resource report is not read or
relabelled as machine evidence.

Report Creator writes one Markdown file, appends that exact file to
`GITHUB_STEP_SUMMARY` and publishes it as the report artifact. It does not
start services, collect metrics, evaluate text or deliver Git changes.
The report contains model configuration, actual work, hardware/worker
tables and separate expandable source and summary texts. Duration values
are seconds rounded upward to three decimal places. Unrun work has no
numeric score or timing. There is no runtime-digest section.

The [platform limits each step summary to 1 MiB](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#step-isolation-and-limits).
If escaped inputs make the full report too large, Report Creator fails
explicitly and retains the complete Markdown artifact. It never silently
truncates the supplied texts or reports successful summary publication.

## Design rationale

Scoring, orchestration and reporting answer different questions. Keeping
them separate leaves the API usable on its own and keeps report changes out
of the model process. Existing native host facilities supply hardware and
machine observations without another collector or duplicated host config.

Private control and event pipes are non-inheritable. Ordinary output stays
discarded through interpreter shutdown because model-library helpers can
otherwise corrupt a valid shutdown receipt. A service PID exiting is not
proof that its model worker exited: the supervisor must confirm its joined
exit. That confirmation survives a separate cleanup failure, but unclean or
unconfirmed shutdown still fails the workflow. Unexpected parent-pipe EOF
cancels host measurement rather than claiming success.

## See also

- [hhem-evaluation-api.md](hhem-evaluation-api.md) - evaluator fields and settings.
- [../how-to/run-hhem-evaluation-api.md](../how-to/run-hhem-evaluation-api.md) - dispatch and inspect a run.
- [host-metrics.md#whole-task-typescript-samples](host-metrics.md#whole-task-typescript-samples) - native measurement semantics.
- [../architecture/evaluation/hhem-evaluation-api.md](../architecture/evaluation/hhem-evaluation-api.md) - model process ownership.
