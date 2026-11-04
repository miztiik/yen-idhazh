# Summary evaluation workflow

**Last Updated**: 2026-11-04

Which inputs, saved results and process outcomes belong to the manual
`summary-eval-tests.yml` workflow. Its task programs live in
`.github/scripts/summary-eval-tests/`; evaluator calculations remain native API
operations.

## One model and one generated answer

The form requires `source_text`. Optional `models_file` is a JSON path relative
to `config/`, such as `models/ornith-1.5-9b-q5km.json`. The form default matches
`config/idhazh.json.models_file`; blank uses that committed pointer. The existing
model validator and declaration loader refuse invalid paths, missing assets and
settings declared for different weights before model startup.

One dispatch selects one summarizer. A comparison is another dispatch with a
different declaration, not a matrix, model loop or shared-default edit. The
declaration supplies the actual pinned weights, companions, revisions, hashes,
native flags, sampling and template settings. It does not select HHEM's model.
`config/summary-eval-tests.json` holds the fixed generation instruction.

There is no supplied-summary input. Source text enters only the user-data turn;
it never selects a shell argument, filename, model destination or system
instruction. The selected model's request builder constrains the response to
title and summary fields. The final-answer reader excludes reasoning and
refuses missing, empty, invalid or unfinished answers, including output stopped
by its token limit. HHEM receives the validated summary field unchanged.

## Visible tasks and owned children

Table A - Task order

| Id | Task | Work and ownership |
| --- | --- | --- |
| A1 | Prepare | Install frozen Bun and Python model dependencies, validate inputs, copy named configuration inputs into the disposable run directory, and acquire the pinned native executable and declared files. |
| A2 | Generate | Start the actual native model and FastAPI's llama-only component, verify their identities, generate through FastAPI, atomically save the answer, then close and reap both. |
| A3 | Evaluate | Re-read the same bounded platform event and saved generation. Require the current run, attempt, revision, source, model and confirmed native shutdown before starting HHEM. Score exactly that saved pair through FastAPI. |
| A4 | Report | Read saved results only. Write combined JSON and escaped Markdown; append that exact Markdown to the step summary. Do not start a server or repeat generation. |
| A5 | Retain | Upload available results/report on success or failure. Upload server diagnostics after errors or cancellation, with platform-default retention. |

Only the preparation step receives the standard `GITHUB_TOKEN` secret. The
existing runtime utility requires it for the pinned release lookup; public
archive and model-byte downloads keep their existing header-free path. The
token is neither persisted nor sent to generation, evaluation or reporting.
Missing authentication fails before network or asset work with
`ASSET_AUTH_MISSING`.

Both active phases use the shared Hono server's `machine` group for the actual
fingerprint and task-profile HTTP operations. TypeScript owns collection;
Python owns only HTTP orchestration and the small native result projection.
Named schema checks bind the consumed field types, requiredness, nullability
and vocabularies to the actual TypeScript models.

Run-local configuration copies enable the existing whole-machine CPU/RAM
instruments without changing committed defaults. Reads name only their required
files; there is no configuration-tree scan or second collector.
The native Hono supervisor verifies its startup nonce, spawned PID, uncached
health and enabled module group. FastAPI's private readiness and shared health
must identify the actual application instance and selected component. Native
readiness checks the owned process's listening socket and its observed
model path and alias against the verified selected files.

Each phase keeps its service handles through request and cleanup. Early exits,
signals and broken parent pipes stop owned work. The platform's existing
`setpriv` command arms the native child's parent-death signal. A small same-PID
bootstrap then verifies that its parent still matches the expected launching
PID before it executes the native binary. A parent lost before protection was
armed therefore cannot leave an adopted model running. No detached production
launcher, PID database,
process-name kill, separate per-API listener or cross-step ownership is used.
The native model is stopped before HHEM loads.

## Same-run files and status

`summary_eval_pipeline/contracts.py` owns version `2026-11-04` of these
disposable native results. Readers accept the current shape only; these files
are not committed ledgers or restart stores.

Table B - Named output under `backend/var/summary-eval-tests/`

| Id | File | Meaning |
| --- | --- | --- |
| B1 | `run.json` | Platform run/attempt, UTC start, source revision, selected declaration identity and exact source hash captured before startup; preparation status and safe errors are atomically updated in this same file. |
| B2 | `generation.json` | The same identities, observed loaded model, exact source hash, validated final `summary_text`, its hash, generation status and safe errors. This is the one answer handoff. |
| B3 | `generation-phase.json` | Generation measurements, server observations, cleanup and errors, bound to the exact saved receipt. |
| B4 | `evaluation.json` | Body-free native HHEM result and evaluation-phase measurements, server observations and cleanup, bound to that same receipt. |
| B5 | `results.json`, `report.md` | Combined native outcome and its escaped human report. |
| B6 | `logs/` | Append-only per-role CloudEvents JSONL files and current native Hono server evidence. Not Git or site output. |

The combined result retains `run.json`'s selected declaration even when
generation never started. It does not label a selected model as loaded.

Preparation starts as `pending`, becomes `complete` only after declared asset
verification, and retains its original typed errors when `failed`. Both model
phases require completed preparation. Reporting can read failed or unfinished
preparation without requiring generation or evaluation files that were never
written; it shows those phases as not run, not as mismatched receipts. No server
logs are expected when preparation stops the run before either model phase.
Same-day snapshots without this preparation state are not assumed complete:
the disposable-file readers are current-only.

Generation saves the accepted answer before measurement or shutdown. Evaluation
checks the exact run, attempt, revision, source and declaration, the receipt's
answer hash and the generation phase's receipt hash. Failed, stale, absent or
incomplete generation cannot start a scorer. There is no regeneration,
supplied-answer fallback or zero score for work not run.

A completed score survives a later measurement, shutdown or report error.
Original API/process errors and cleanup failures remain separate. Combined
completion requires completed generation and HHEM work, collected hardware,
actual CPU/RAM observations, an uninterrupted explicit profile close and clean
confirmed shutdown. A retained primary score with any required failure is
partial; no completed primary score is failed. UniEval is explicitly not run:
its later integration adds no score or duration here.

Phase shutdown distinguishes `api_stopped`, the shared FastAPI application's
exit, from HHEM's `worker_exit_confirmed`. Generation starts no evaluator worker
and does not claim that one stopped.

Machine CPU is zero to 100 percent for the whole machine, including background
work. Stored RAM uses KiB; the report displays closing use in MiB, not peak use.
Measurements exclude acquisition/model loading and stop before API teardown.
Missing readings keep their native reasons, not invented zeroes.

## Diagnostics and disclosures

Roles write brief startup, readiness, stop and safe error facts to live stderr
and `{server_name}_{yyyy_mm_dd}_{run_id}_{attempt}.log`. The date is the UTC
run-start day. Restarting a role appends to its file. Private control packets
are separate. Source, prompts, model output and secrets never enter diagnostic
records; native raw output is suppressed with the configured quiet flags.

An unopenable or unwritable mirror warns and records that the log is unavailable.
It does not cancel useful model work. Actual worker, API or cleanup failures
still fail the task. There is no log-volume quota, rotation framework or custom
retention period. Hard runner termination cannot promise a final upload.

Only the declared generation result and escaped report contain the generated
summary. The report re-reads the bounded event for its source disclosure.
Both disclosures are literal text, not interpreted HTML. If their escaped
Markdown exceeds the platform's one-MiB step-summary limit, report publication
fails explicitly while retaining the complete report artifact.
Validated HTTP results and actual exits establish success, not terminal-log
matching.

The report leads with actual work and failures before detailed model and
hardware evidence. Each failure names its service and any observed HTTP status;
cleanup errors also name the generation or evaluation phase that owned them.
Beside server-log availability it directs failed or cancelled runs to
`Artifacts -> summary-eval-tests-server-logs`, using the matching filename in
the server table.

## Design rationale

Separate preparation, generation, evaluation and reporting keep model memory
lifetimes visible. One saved answer allows real service restarts without
changing what an evaluator sees. Named run-local configuration copies reuse
the current model and machine readers without editing shared defaults or
adding another server configuration authority.

The workflow adds no Python model binding, collector dependency or root
workspace. The shared FastAPI/Hono applications, frozen dependencies, native
asset tools and request/final-answer readers do the actual work.

The pinned native decoder refuses unanchored regular-expression patterns.
Generation therefore derives string-length constraints from its answer model;
the same model's final-text validator still refuses whitespace-only or invalid
UTF-8 answers without changing accepted text.

## See also

- [Run and inspect the workflow](../how-to/run-hhem-evaluation-api.md)
- [Shared Python API](fastapi-server.md)
- [Shared TypeScript API](typescript-api-server.md)
- [Model-file selection](../concepts/config/model-file.md)
- [Native HHEM operation](hhem-evaluation-api.md)
