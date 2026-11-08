# Run the isolated feed planner checks

**Last Updated**: 2026-11-06

How do you check the TypeScript planner without changing daily publication?
Use offline cases for validation. The manual workflow performs real feed work
and data commits, so it is not a repeatable test gate.
This page is project-specific because it names this planner's native formats
and isolated workflow.

## Current readiness

The service flag in `config/feed-ingest-plan-service.json` defaults off.
The manual workflow enables only its own invocation; it does not approve
production use or change committed defaults. Production digest workers,
the Python pipeline and global health data are unchanged.

The workflow calls `services/feed-ingest-plan/scripts/run-feed-ingest-plan.ts`.
Its preparation and HTTP client are separate modules. Execution supervises the
shared pipeline API server in a separate child process within one workflow
step. Its planning group includes the actual fingerprint and measurement
handlers on the same socket. The address comes only from
[`config/hono-server.json`](../reference/serve-pipeline-apis.md#listener-authority).
Validated private startup data preserves local input settings, invocation-only
enablement, temporary output, run/attempt/revision identity and UTC clocks.
Readiness must match that exact child and invocation, not merely an available
port. The client posts to `/plan` once. The request captures its actual health
report and releases its live collection before replying. The client does not
continue with another summary or release request. The supervisor closes and
reaps the child in `finally`.
It verifies the returned
five-format native output and selected artifact before exposing commit paths.
Completed planning is not proof of summarization or publication.
The HTTP body, direct CLI output and saved `response.json` share one model.
Selected keys are `selected_article_ids` and `assignments[].article_id`.
Use the [native response option](../architecture/sources/feed-plan-runner.md#entry-points-and-controls)
to include readable assignment URLs; the default is false and no ledger
column changes. This is a native config, HTTP or CLI control, not another
workflow dispatch input.
Required `health` records the successful summary, an explicit report failure,
or null only when no completed report input exists. Report or cleanup failure
fails the request without changing completed planning facts or their saved row.
The client saves and verifies a structured HTTP 500 result as well as a
successful result. Both CLIs exit unsuccessfully for any request failure.

## Manual controls

The dispatch form takes article limit, worker count, partition strategy and
one optional `global_age_ceiling_hours` override. It accepts a single positive
finite number of hours, such as `24` or `36`. Blank uses
`curate_articles.global_age_ceiling_hours` from configuration, currently
36 hours. Zero, negative, non-finite, malformed and comma-list values fail
before collection; retired age-array controls are not aliases.
Values are environment data, never interpolated shell code. The run resolves
its own config before article fetch, screening, selection and reporting;
concurrent requests cannot replace each other's ceiling. The applied
policy report shows the one effective ceiling and its configuration or run
override origin. The ceiling applies only to known age, with equality
admitted. Unknown age stays eligible with zero recency and explicit missing
timing evidence; it is not assumed to be new.
For `none`, clear the worker count or set it to one.

`dump_raw_document_contents` is a dropdown with the strings `false` and `true`;
its default is `false`, not a checked or unchecked boolean input. The adapter
accepts exactly those strings, converts the choice to a native boolean, and
passes it through the invocation's validated settings in the private startup
pipe. It is not an HTTP control. The authored service setting also defaults
to false. When enabled, only failed downloaded inputs may enter the
[separate raw-document artifact](../architecture/sources/feed-operator-api.md#failure-only-raw-document-artifact).

`partition.enabled` in `config/feed-ingest-plan.json` defaults to true. Worker
counts default to four, with configured bounds of one through twenty. When
partitioning is disabled, selection still runs but worker assignment is
bypassed. Worker controls cannot change winners or fill missing article slots.
The [selection rules](../architecture/sources/feed-curation.md) explain the
global unique-URL capacity, cached scores and soft diversity adjustments.

The workflow does not profile live planner CPU or RAM. After exact-child HTTP
readiness, it records the configured host fingerprint through that same
listener, then calls the planner. The host write retains its native identity
and is committed with the planner ledgers.

Each enabled manual run also writes the separate
[article-entity diagnostic](../architecture/sources/planner-run-diagnostics.md#recognized-article-names).
Its authored `diagnostics.named_entities` limits bound output, not input text.
There is no extra dispatch switch. Names never enter job progress logs or
committed ledgers.

## Local offline checks

Inspect `npm run test:changed -- --list` from `frontend/`. For service-only
changes, use the installed declared packages rather than a full Python group:

```text
bun run --cwd packages/common-contracts check
bun run --cwd packages/ledger-file-writer check
bun run --cwd services/serve-pipeline-apis check
bun run --cwd services/serve-pipeline-apis test
bun run --cwd services/feed-ingest-plan check
bun run --cwd services/feed-ingest-plan test
```

Planner contracts are owned and tested in TypeScript; do not compare them with
retired Python planner models. A change to a Python-owned shape copied into
TypeScript still runs the native binding test:

```text
python -m pytest backend/tests/contracts/test_native_typescript_bindings.py
```

The service suite includes the existing workflow/report cases. Its case
timeout bounds test execution; it is not a planner speed
target. CI runs these offline checks. The manual workflow does not repeat them:
it calls the live Plan API and commits its real output. An unselected local
module cannot satisfy a missing dependency. The local suite does not run a
fixture-only compatibility entry point.

The process-boundary cases run the real supervisor and child lifecycle with
recorded RSS/HTML at the external transport boundary. They prove child identity,
output and in-memory batch preservation, occupied-port refusal, early exit,
readiness expiry, identity mismatch, partial-file recovery, cancellation and
supervisor disappearance without a surviving listener. These are offline checks,
not a live workflow.

Recorded RSS/HTML and transport facts drive the actual listener, worker
extractor, complete public offer flow and CLI. Generated native files prove
metadata/artifact agreement, original UTC work dates, incomplete history,
distinct attempts and explicit empty or partial outcomes. No test contacts
an external feed, starts a live workflow or requires local Python.
Recorded transports capture each invocation before fixture lookup. Their
traces must contain only feed/article targets and actual retries or redirects.
Missing fixture responses cannot conceal an automatic extra request.

For resource-address changes, combine `article-url-cleanup.test.ts`,
`harvest.test.ts` and `harvest-safety.test.ts` with the affected caller cases.
The named URL vectors check both article and feed-document hashes, exact
query-bearing dispatches, checked redirects, private-target refusals and
serialized length bounds. The recorder matches the complete URL; it never
falls back to a query-free response. Keep Python normalization outside this
native check and do not claim cross-language parity.

The generated bare-origin case executes the actual commit CLI, checks the
new remote metadata without raw-day indexes, replays it safely and verifies that
the checkout did not change. Helper-only coverage cannot certify this entry.
`safe-persist-http.test.ts` checks real loopback delivery and exact remote bytes.
The finalization cases also run the actual finalizer CLI through the same
application restarted with its delivery group and require its
`safe_persist_http_completed` CloudEvent.
They retain report and metadata recovery checks after delivery failure.
Independent writer and contract tests own native digest, identifier and
historical ledger coverage. The workflow does not add a synthetic receipt.

## Offline recording in CI

The existing CI workflow has a default-off `capture_planner_recordings`
dispatch input. It checks out the selected revision and runs the existing
real API recorder against recorded RSS and HTML. It does not read live feeds,
commit data or change parser or test deadlines.

```text
gh workflow run ci.yml --ref <branch> -f capture_planner_recordings=true
gh run download <run-id> --name planner-current-recordings --dir <temporary-directory>
```

The `planner-current-recordings` artifact is uploaded only after the recorder
succeeds. It contains eight files for
`tests/fixtures/feed-ingest-plan/entry-points/`: `response.json`, `health.json`,
`selected-articles.json` and the `discovered-articles`, `selected-articles`,
`rejected-articles`, `feed-health-state` and `plan-runs` `.rows.json` files.
It also contains `report-events.json`, the same request's validated progress
events. This current fixture is captured, not rebuilt by changing an earlier
event's version or inventing its timings.
Local capture also refreshes
`tests/fixtures/contracts/fetched-document/refused.json` from an actual failed
fetch made by the same offline recorder over recorded transport. It records
current generic document identities, not copied article fields.
This additional fixture is not included in the CI recording artifact; capture
it locally with the same recorder when its contract changes.
The capture switch is unset when the recorder step exits, including on failure.
Review and commit only these generated current recordings, then run ordinary
candidate CI without capture. Existing replay, CLI and full-suite gates remain
unchanged; a recording run is not their replacement.

## Saved output and failures

`services/feed-ingest-plan/scripts/` owns workflow execution, local input loading,
native verification, metadata commits, artifact preparation and
reporting. `services/host-probes/scripts/` owns optional controlled host tools.
`workflow_reporting.score_decimal_places` controls displayed selected scores,
with a default of three decimal places. Saved metadata and selected-text
artifacts keep exact scores; rounding never affects winner comparisons.

Every TypeScript API used by this workflow follows the
[native event standard and support matrix](../architecture/contracts/identity.md#native-api-support).
Handlers create their own events before supervision, and the mirror retains
their original source, occurrence and operation. Native HTTP results, private
readiness/stdout, full task profiles and saved delivery receipts keep their
existing protocols; event envelopes do not replace them.

Workflow YAML calls those modules directly. `.github/scripts/` retains only
the independent `ai-pipeline.ts` experiment and `serve-evaluator.py`; neither
is required for the native feed APIs. Recorded compatibility drivers live in
the service's test directory only when they cover an independently maintained
reader or writer. The runtime verifier checks actual planner files during real
execution; it has no fixture-only entry point.

The commit manifest permits exact current raw Parquet paths for the five
planner siblings and the host fingerprint. The committer validates bytes and
appends all completed files in one request through a private temporary Git
staging index against fresh main. It creates no planner raw-day JSON list.
A normal push retry preserves another writer's immutable additions. It does
not rewrite the checkout, rebase or force-push. Git receives ordinary ledger
files at their registered paths, never an archive.

Initial checkout obtains code, required registered raw/compact inputs and the
existing publication inventory at one ref. History uses the
[bounded day membership contract](../reference/feed-planner-ledgers.md#raw-day-membership):
exact local UTC-day directories identify Parquet siblings. No later fetch,
Git file catalog, sparse expansion or saved input copy is used.
Startup and finalization validate the supplied `GITHUB_SHA`; they do not query
`HEAD`. The safe-persist child receives that identity through its existing
private startup pipe, never through public planning or delivery controls.

Finalization keeps delivery, reporting and artifact preparation separate:

1. `Commit ledgers` restarts the same supervised application with only its
   [safe-persist routes](../architecture/sources/feed-operator-api.md#safe-persist-http-delivery)
   and sends one request for all verified completed ledgers. The existing
   adapter and Git engine perform delivery. The task closes and reaps that
   child. `Write run report and annotations` then calls the Markdown API in
   its own visible task; preparation remains independent.
   A delivery or report failure does not stop the remaining preparation;
   the task still fails after preserving its useful output.
2. `Prepare artifacts and list upload files as JSONL` uses the existing structured publisher
   to name each actual file relative to the ZIP root, then its total count.
   It reads only this run's prepared `artifacts` directory, follows the
   upload's ordinary file matching and excludes hidden files and directories.
   The inventory is beside the upload in the job log; it does not change the
   third-party action's file-count message or add a file to the archive.
   Its `artifact-upload` completion means enumeration, not upload success.
3. `Upload run artifacts` uploads that prepared directory as one archive named
   `collect-and-select-articles-<run>-<attempt>`, including after finalization
   failure. It contains `<run>-<attempt>-selected-articles.json` for the next
   summarization caller, plus the delivery result, body-free response and Markdown report
   when available.
   The summarization caller downloads this named artifact and reads its selected
   JSON file, not a ledger. The [summary API](../reference/summary-generator-api.md)
   receives prepared text; artifact acquisition stays outside HTTP.
   Article bodies never enter the Git request.
4. `Upload failed document metadata` runs only when the dropdown is `true` and a
   diagnostic file exists. Preparation first hands the closed
   `raw-document-contents-<UTC-day>-<numeric-run-id>-<attempt>.jsonl` to the hash-free artifact-directory destination,
   with only that exact target permitted. The separate archive is named
   `raw-document-contents-<run>-<attempt>`. Zero failed documents means no file
   and no debug upload. Failed collection still prepares and uploads available
   diagnostics; no successful raw input, extracted-text substitute or new
   retention policy is added.
5. `Upload article entities` uploads the closed private JSONL file as
   `article-entities-<run>-<attempt>` whenever it was written, including after
   later planner failure. Its one file is
   `article-entities-<UTC-day>-<numeric-run-id>-<attempt>.jsonl`. Each article
   record distinguishes empty name sets, incomplete analysis and omitted
   names. No file means no upload, not a successful empty result.
6. `Upload server failure logs` retains available
   `hono-server_<group>_<yyyy_mm_dd>_<run>_<attempt>.log` files after failure or
   cancellation. The date is the UTC run-start day. Native lifecycle evidence
   is retained in the normal artifact even when the planner never replied.
   Saved legacy evidence keeps its original unqualified filename; reading and
   copying it does not rewrite the old observations.
   There is no retention override.
7. `Finish and clean up` checks collection, finalization and the normal upload's
   returned artifact identity, plus diagnostic uploads when applicable.
   It rechecks the saved result and exact Git
   delivery receipt before removing only the temporary run directory.
   An earlier collection failure still fails the job after completed
   diagnostics have landed. Failed finalization, missing confirmation or a
   failed upload leaves temporary files untouched. A recovery artifact does
   not turn a failed commit into success.
   Cancellation deliberately skips delivery confirmation and retains output:
   no Git delivery receipt is expected when that delivery was skipped. The job
   remains cancelled or failed because collection did not finish, without a
   second missing-file cleanup error.

When the metadata commit is not confirmed, the same artifact also contains
`uncommitted-metadata-<run>-<attempt>/`: only the exact validated current-run
metadata files and `current-run-files.json`. It can contain multiple UTC-day
files. No whole temporary root or private parsed/rejected
population is uploaded. Raw diagnostics and recognized names never enter this normal archive or
the metadata Git request. Invalid evidence fails preparation while independently
verified files remain recoverable. Cancellation skips new Git delivery while
still attempting the report and recovery upload.

Readiness, graceful drain and forced-exit waits are finite settings under
`supervision` in `config/hono-server.json`; the
[runner](../architecture/sources/feed-plan-runner.md#entry-points-and-controls)
defines their defaults and failure behavior. Termination cancels the real HTTP
client, then closes the child pipe. Pipe closure also triggers child cleanup
when the supervisor disappears. Only the exact spawned child can be forcibly
killed. The server is never detached or kept alive across workflow steps.

The Markdown report reads the body-free response, its embedded successful
`health` report, verified selected metadata, captured effective settings and
host fingerprint. A missing or failed separate `health.json` write cannot
remove that report, exclusion diagnostics or earlier paused-feed evidence.
Null and failed report outcomes stay explicit rather than becoming empty
successful reports. A report or release failure is shown separately from
completed planning. Only Run
outcome and Needs attention are visible. Per-feed article results, Request
counts and coverage, Why articles were not selected, Selected article evidence,
Effective settings and Execution measurements use closed-by-default folds.
The API servers fold reads actual startup and shutdown outcomes and log
filenames, not terminal log matches. A failed file mirror is shown as
unavailable without changing the API outcome.
Routine notices do not repeat the tables;
actionable run and progress warnings remain. The report cannot establish
publication and stays separate from the delivery receipt.
The workflow writes the summary into the existing downloadable Markdown
artifact, with per-feed exclusion diagnostics appended only to that artifact.
The same report explains the original execution error and bounded related
causes without copying exception text or raw stacks. The body-free
`<run>-<attempt>-response.json` remains in the normal archive for the same
evidence in structured form.
Reporting is controlled by `workflow_reporting.enabled`; it cannot change
ledger bytes or establish completion.
The exported Markdown renderer and its separation from production digest
presentation are documented in the [operator API reference](../architecture/sources/feed-operator-api.md#markdown-rendering-api).
Run outcome shows status, selected articles against the captured maximum,
technical admission, distinct feeds checked, paused feeds and elapsed time in
useful units. Unknown technical totals keep the known subtotal visible, with
the unavailable feed count stated beside it. All-unknown is unavailable;
known-empty is zero. This is original technical admission, not a later
screening population. The [ledger reference](../reference/feed-planner-ledgers.md#c-feed-health-state)
owns the counter meanings.
Per-feed results combine this run's UTC day rows. One unknown constituent
makes that feed's exact total unavailable. Sort by selected articles
descending, technical admission descending, then feed name; unknown sort
last within each count. Request counts and repeated failure descriptions do
not appear in this table.

Needs attention separates current recorded failures, paused coverage and
missing evidence. A paused feed is not a new request failure. Historical
causes remain unavailable when report inputs do not contain them. Current
feed HTTP status is shown only for an identified HTTP check tied to its saved
failure code. The report reader verifies the exact rejected-article files named
in this run's response before showing article HTTP, fetch and pacing evidence.
It counts each terminal execution/candidate once; retries are not extra
articles. An unavailable target status remains unavailable.
Detailed article rows replace the covered aggregate failure counts. Remaining
aggregate counts keep their unknown status explicit.

For paused feeds, the reader uses the initially staged health files within the
run's recorded history bounds. It shows a validated earlier check only when its
feed, endpoint and check instant match the saved availability update. Earlier
checks are labelled separately from This run. No matching check means the
historical cause stays unavailable; a current failure followed by a pause does
not claim that no check occurred in this run. Missing native article files
preserve aggregate evidence and add an attention item; invalid native bytes
fail report creation. No network query, log parsing, API change or ledger write
is involved. No response code or deeper cause is inferred. An eligible UTC
deadline is not a scheduled request. Proven empty evidence states no recorded
problems without an empty failure table.

Effective settings use one control per row with its effective value and
source, including workflow overrides. Missing captured policy does not
substitute committed defaults. The fold links to this guide at the workflow
commit when that context is available. The article limit is a maximum, not a
promise. Switches remain booleans. The authority coefficient multiplies
configured feed weight only; [curation](../architecture/sources/feed-curation.md#fixed-score-preparation)
defines its contribution separately from measured substance and reliability.
The report distinguishes the raw technical word minimum from retained-word
score evidence, including measured zero, and accounts for terminal losses
without presenting retired source allocations or exposure controls.
Execution measurements hold the machine fingerprint, run identity, attempt
and operation durations. Concurrent durations can overlap; their sum is not
elapsed planning time.

Request counts have one canonical fold. Its count table separates This run
from the historical closed-day window, with each request category's
completeness retained. Partial totals contain only recorded requests; missing
counts are not estimates and zero is known zero. Coverage rows show UTC
bounds, recorded days, complete days and records with missing counts.
Identical descriptions share rows, with exceptional feeds listed separately.
Known-empty complete days need not contain records. Missing files do not
establish a missing-record count. Input gaps and unattributable days remain
explicit. Each period sorts by article requests, feed requests, then name;
unknown values sort last. The request table does not repeat reliability.
The closing staging note describes input transfer, not complete historical
day coverage. Missing-day lists apply only to the historical window.

Selection exclusions group routine article decisions by stage and
plain-English reason, with affected feed counts. They are not a subtractable
funnel. Current fetch and extraction failures appear only in Needs attention;
retry events are not added as separate excluded articles. Per-feed protocol
reasons remain in the artifact diagnostics.

`MISSING_REQUIRED_FIELDS` is an article rejection: its offered URL or identity
was missing or invalid, or extraction produced no usable title. A grouped
count does not identify the exact missing field and does not mean a feed
configuration field is absent. The protocol reason code is unchanged.
An unsafe target is `FETCH_FAILED`, not a missing-field count; its valid
address and hash remain in refusal evidence without a source request.
The [resource address rule](../architecture/contracts/identity.md#typescript-resource-addresses)
preserves article and feed-document queries and removes fragments.

## CI and hosted verification

The repository's test-only `ci.yml` remains authoritative for native typing,
field/default/vocabulary bindings, full-suite and real gardener packing.
Its site and browser jobs install Bun and the frozen shared-contract/writer
packages for the current native planner fixtures. Cost is those existing
test dependencies on each clean job; no new package or browser bundle bytes.
Config bindings ignore JSON object order and union-branch order. Fields,
bounds, types, nullability, defaults and vocabularies must still match.
Do not dispatch `feed-ingest-plan-test.yml` to obtain those checks: it does
live work and commits data. A conflicting PR must first merge current main
normally, then receive CI on its exact resolved head.

A later authorized live run can verify feed availability and actual hosted
operation timings. Offline fixtures and local checks make no production
throughput claim.

## Host fingerprint

The workflow uses the existing fingerprint settings and records one host row in
the native ledger. It does not collect a live planner CPU or RAM profile, run
the separate controlled host-probe proof or add a memory-profile dispatch
option. The host row is validated and committed with the planner files through
the shared safe-delivery API. If that commit is not confirmed, the exact files
remain available in the recovery artifact.

## Design rationale

The manual workflow proves that the real Plan API can fetch, parse, select,
write body-free ledger rows and hand selected text to the next stage. Named
history reads day-level ledger data from the initial input directory, not only the
immediately previous workflow run; its data families and windows are in the
[bounded day membership contract](../reference/feed-planner-ledgers.md#raw-day-membership).
The sparse checkout supplies runnable source, configuration and the required
saved ledger namespaces together. This acquires more saved data up front, but
adds no input store or independent revision proof. Adapter checks remain in
CI; repeating them here does not exercise a live API. The selected text upload
and ledger commit stay separate because the summarizer needs article bodies
while the ledger does not. CPU and RAM profiling does not prove API correctness,
so this workflow keeps the host fingerprint but does not profile the planner.
The closing tasks group orchestration rather than merge API responsibilities.
Safe Git delivery and Markdown rendering remain separate functions. One
standard artifact upload carries selected text, run evidence and any recovery
files, so consolidation adds no upload dependency. Cleanup follows confirmed
delivery instead of discarding the only recoverable copy.
The report-only native evidence reader keeps file verification separate from
Markdown layout. It reuses the existing Parquet and bounded health readers,
so exact response evidence needs no new state store or API control.

## See also

- [Runner](../architecture/sources/feed-plan-runner.md)
- [Operator APIs](../architecture/sources/feed-operator-api.md)
- [Ledger reference](../reference/feed-planner-ledgers.md)
- [Gate commands](run-the-gates.md)
