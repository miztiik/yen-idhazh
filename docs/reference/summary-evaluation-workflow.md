# Summary evaluation workflow

**Last Updated**: 2026-11-07

Which inputs, saved results and process outcomes belong to the manual
`summary-eval-tests.yml` workflow. Its task programs live in
`.github/scripts/summary-eval-tests/`; evaluator calculations remain native API
operations.

Workflow tests live in the distinct `summary_eval_tests` package beside those
programs. Service tests remain under `services/summary_evaluator/tests`;
`summary_evaluator_cases` there contains their single shared recording and
process harness. The service pytest configuration names both suites in one
locked model-free environment. Tests keep the original fixture provenance.

## One model and one generated answer

The form requires `source_text` and `reference_summary_text`. Optional
`models_file` is a JSON path relative
to `config/`, such as `models/ornith-1.5-9b-q5km.json`. The form default matches
`config/idhazh.json.models_file`; blank uses that committed pointer. The existing
model validator and declaration loader refuse invalid paths, missing assets and
settings declared for different weights before model startup.

One dispatch selects one summarizer. A comparison is another dispatch with a
different declaration, not a matrix, model loop or shared-default edit. The
declaration supplies the actual pinned weights, companions, revisions, hashes,
native flags, sampling and template settings. It selects neither evaluator's model.
`config/summary-evals/workflow.json.generation_prompt_file` selects
`prompts/generate-evaluation-summary.txt` relative to this invocation's
`config/` root. Safe relative POSIX paths under `prompts/` are validated before
reading that one file; the caller preserves every UTF-8 space and newline.
The default has no final newline, matching its former inline value.
This authored settings family is version `2026-11-07`, current-only, without
an inline-instruction fallback. Resolution yields the existing effective
generation instruction; saved workflow/result contracts retain `2026-11-05`.
Neither scorer reads this workflow configuration.

The file also owns the input, generation-request and generation-response byte
allowances. Native sampling and server options remain open JSON from the
selected declaration; there is no second list of supported native fields.
Every generation call builds fresh system and source turns, without earlier
answers or conversation history. The digest's separate continuation flow is
unchanged.

Transport bounds, native/host startup and cleanup waits, output directories
and body-free native logging remain caller-owned settings. The selected model
still supplies all native JSON and server controls. Moving the instruction
adds no process, copy of the configuration tree or pipeline framework.

There is no supplied-summary input. Source text enters only the user-data turn;
it never selects a shell argument, filename, model destination or system
instruction. The selected model's request builder constrains the response to
title and summary fields. The final-answer reader excludes reasoning and
refuses missing, empty, invalid or unfinished answers, including output stopped
by its token limit. Both evaluators receive the validated summary field unchanged.

The operator supplies the reference independently for this source before
generation. The bounded event reader preserves its exact UTF-8 bytes and
preparation saves its SHA-256 identity. Its text goes only to UniEval and the
escaped report, never generation, HHEM, diagnostic logs or process controls.
Missing, invalid or oversized reference input blocks preparation; the input
object must fit the workflow's `max_input_bytes` allowance before generation. Independence comes from
input provenance, not string inequality: an independently supplied reference
may happen to equal the answer. There is no generated or substituted reference.

## Visible tasks and owned children

Table A - Task order

| Id | Task | Work and ownership |
| --- | --- | --- |
| A1 | Prepare | Install frozen Bun and Python model dependencies, validate source/reference/model inputs, capture the reference hash, copy named configuration inputs, and acquire pinned native and UniEval assets, tokenizer and sentence resources. |
| A2 | Generate | Start the native model and host collector, verify native health and loaded identity, call native generation directly, atomically save the answer, then close and reap both. No Python evaluation application starts. |
| A3 | Evaluate | Re-read the bounded event and generation. Require the current run, attempt, revision, source, answer, model, reference and confirmed native shutdown. Start HHEM and UniEval on the same FastAPI address; score the saved pair independently. |
| A4 | Report | Read saved results only. Write combined JSON and escaped Markdown; append that exact Markdown to the step summary. Do not start a server or repeat generation. |
| A5 | Retain | Upload available results/report on success or failure. Upload server diagnostics after errors or cancellation, with platform-default retention. |

Only the preparation step receives the standard `GITHUB_TOKEN` secret. The
existing runtime utility requires it for the pinned release lookup; public
archive and model-byte downloads keep their existing header-free path. The
token is neither persisted nor sent to generation, evaluation or reporting.
Missing authentication fails before network or asset work with
`ASSET_AUTH_MISSING`.

Both active phases use the probe package's machine application under shared
Hono hosting for the actual fingerprint and task-profile HTTP operations.
TypeScript owns collection; Python owns only HTTP orchestration and the small
native result projection. Preparation installs neither feed-ingest-plan nor
data-delivery and stages no feed configuration. The actual machine child and
the summary helper depend only on the common, hosting and machine packages.
Named schema checks bind the consumed field types, requiredness, nullability
and vocabularies to the actual TypeScript models.

The caller projects only the server's declared `run_id`, `attempt`,
`started_at` and operation `context`. Python's captured source revision stays
in the fingerprint writer's domain context, not in the strict listener-run
metadata. The shared server schema is not relaxed to accept extra fields.

Run-local configuration copies enable the existing whole-machine CPU/RAM
instruments without changing committed defaults. Reads name only their required
files; there is no configuration-tree scan or second collector.
`config/hono-server.json` supplies the machine listener controls and supervision waits,
including the helper's profile-stop cleanup allowance. There is no feed-settings
fallback.
The workflow settings own the host startup, shutdown, post-termination grace
and forced-stop waits. A ready helper receives its advertised lifecycle timeout
plus `host_stop_grace_ms`; a helper not yet ready receives
`host_shutdown_timeout_ms`. Termination and killing retain their separate
grace and forced-stop joins.
Invalid shared listener controls retain `MACHINE_API_STARTUP_INVALID`;
invalid probe settings retain `MACHINE_SETTINGS_INVALID`.
The native Hono supervisor verifies its startup nonce, spawned PID, uncached
health and enabled module group. During evaluation, FastAPI's private readiness and shared health
must identify the actual application instance and selected component. Native
readiness checks the owned process's listening socket and its observed
model path and alias against the verified selected files, as well as native
health. Template rendering and completion call that same committed origin.
Requests refuse redirects and environment proxies, bound response bytes and
encoding, and retain deadline and cancellation handling.
Generation reads neither evaluator listener settings nor scorer settings.

Each phase keeps its service handles through request and cleanup. Early exits,
signals and broken parent pipes stop owned work. The platform's existing
`setpriv` command arms the native child's parent-death signal. A small same-PID
bootstrap then verifies that its parent still matches the expected launching
PID before it executes the native binary. A parent lost before protection was
armed therefore cannot leave an adopted model running. No detached production
launcher, PID database,
process-name kill, separate per-API listener or cross-step ownership is used.
The native model is stopped before either evaluator loads. Each evaluator has
its own worker. Shared health keeps their states separate; one failed or
unfinished component does not prevent a ready sibling from returning its
actual result. A failed request does not cancel its sibling, retry scoring or
regenerate the answer.

If a later shared-health transport request fails, the caller retains its last
identity-validated component observations and records that actual failure.
Only a component already observed ready may score. Identity or response
validation failures remain hard refusals, and the health failure prevents
overall completion even when a sibling returns a score.

## Same-run files and status

`summary_eval_pipeline/contracts.py` owns version `2026-11-05` of these
disposable native results. Readers accept the current shape only; these files
are not committed ledgers or restart stores. The Bun machine bridge uses the
same workflow-control version and rejects earlier startup packets; native
machine-result versions remain independent.

Table B - Named output under `backend/var/summary-eval-tests/`

| Id | File | Meaning |
| --- | --- | --- |
| B1 | `run.json` | Platform run/attempt, UTC start, source revision, selected declaration, exact source and independent reference hashes captured before startup; preparation status and safe errors are atomically updated here. |
| B2 | `generation.json` | The same identities, observed loaded model, source/reference hashes, validated final `summary_text`, answer hash, generation status and safe errors. This is the one answer handoff. |
| B3 | `generation-phase.json` | Generation measurements, server observations, cleanup and errors, bound to the exact saved receipt. |
| B4 | `evaluation.json` | Imported native HHEM and UniEval results, actual per-worker readiness, request identities, reference hash, machine readings and independent shutdown observations, bound to that receipt. |
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
answer and reference hashes, both native response request identities and the
generation phase's receipt hash. Only UniEval receives the reference, unchanged.
Failed, stale, absent or
incomplete generation cannot start a scorer. There is no regeneration,
supplied-answer fallback or zero score for work not run.

A completed score survives a later measurement, shutdown or report error.
Original API/process errors and cleanup failures remain separate. Combined
completion requires completed generation, complete HHEM and all four UniEval
dimensions, collected hardware,
actual CPU/RAM observations, an uninterrupted explicit profile close and clean
confirmed shutdown. Any completed evaluator score with a required failure is partial.
Without a completed score, the workflow is failed. A genuine computed zero is retained. Failed or
oversized UniEval dimensions remain null with their native errors; completed
dimensions and the other evaluator's result survive. Error HTTP responses are
validated and read, not discarded.

Phase shutdown distinguishes `api_stopped`, the shared FastAPI application's
exit, from HHEM's `worker_exit_confirmed` and the independent
`unieval_worker_exit_confirmed`. Neither worker flag stands for the other.
Generation sets all three evaluator shutdown fields to null because neither
the application nor its workers started. Its report contains only the native
model and host server outcomes, with no invented evaluator startup time or
exit. Completion requires the native model and host collector to stop; failed
generation cleanup cannot start evaluation.

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
`native_logging` and `native_log_directory` in the workflow settings control
the native lifecycle log independently of evaluator logging. Its configured
directory is retained with the workflow diagnostics, not an evaluator-labelled
artifact. Common safe lifecycle fields and the strict record writer are shared
mechanisms; native logs declare only their own model and log components.
Preparation publishes the validated output and native-log directories through
the platform's step-output file before asset work. Uploads use those values,
including on preparation failure; changing either directory needs no workflow
source edit. No artifact lookup runs when preparation has not published a path.

An unopenable or unwritable mirror warns and records that the log is unavailable.
It does not cancel useful model work. Actual worker, API or cleanup failures
still fail the task. There is no log-volume quota, rotation framework or custom
retention period. Hard runner termination cannot promise a final upload.

Machine-helper failures emit brief body-free caller diagnostics to stderr and,
once startup identity is validated, a private failure packet with a safe cause
code and any observed HTTP status. Python validates the owned identity before
retaining that code in phase errors and reports. Fast child exit does not erase
an already received failure packet. Original work and cleanup causes remain
separate; raw exception text and invalid configuration values are not emitted.
After observing child exit, the owner drains its control reader within the
existing forced-stop bound before falling back to a generic exit error. Cleanup
also retains a startup cause recovered later, even when readiness was never
reached, alongside the actual cleanup cause.
No Hono log or server outcome is invented when validation stops the helper
before its supervisor starts.

Only the declared generation result and escaped report contain the generated
summary. The report re-reads the bounded event for source and independent
reference disclosures. All three are literal text, not interpreted HTML. If their escaped
Markdown exceeds the platform's one-MiB step-summary limit, report publication
fails explicitly while retaining the complete report artifact.
Validated HTTP results and actual exits establish success, not terminal-log
matching.

The report leads with actual work and failures before the four named scores,
their plain meanings, actual consistency mode, source spans, sentence and
comparison counts, model identities and hardware evidence. The
[native UniEval reference](unieval-api.md) owns score meanings and limitations.
There is no overall grade or publication rule. Each failure names its service and any observed HTTP status;
cleanup errors also name the generation or evaluation phase that owned them.
Beside server-log availability it directs failed or cancelled runs to
`Artifacts -> summary-eval-tests-server-logs`, using the matching filename in
the server table.

## Design rationale

Separate preparation, generation, evaluation and reporting keep model memory
lifetimes visible. One saved answer allows real service restarts without
changing what an evaluator sees. Capturing the independent reference before
generation prevents a generated-answer fallback without forbidding coincidental
text equality. Independent native results retain useful work when a sibling
fails. Named run-local configuration copies reuse
the current model and machine readers without editing shared defaults or
adding another server configuration authority.

A named instruction file makes the task independently editable without mixing
its title/summary answer with the generator API's different product. Resolving
it before request construction preserves fresh calls and independently supplied
references while keeping orchestration controls in the workflow.

The workflow adds no Python model binding, collector dependency or root
workspace. The shared FastAPI/Hono applications, frozen dependencies, native
asset tools and request/final-answer readers do the actual work.
The evaluation application is not a generation proxy: the workflow already
owns the native model, so a second forwarding process would add a readiness
and shutdown dependency without doing another task.

The pinned native decoder refuses unanchored regular-expression patterns.
Generation therefore derives string-length constraints from its answer model;
the same model's final-text validator still refuses whitespace-only or invalid
UTF-8 answers without changing accepted text.

## See also

- [Run and inspect the workflow](../how-to/run-hhem-evaluation-api.md)
- [Shared Python API](summary-evaluator-api.md)
- [Serve pipeline APIs](serve-pipeline-apis.md)
- [Model-file selection](../concepts/config/model-file.md)
- [Native HHEM operation](hhem-evaluation-api.md)
- [Native UniEval operation](unieval-api.md)
