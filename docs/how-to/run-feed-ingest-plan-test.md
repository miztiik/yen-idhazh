# Run the isolated feed planner checks

**Last Updated**: 2026-11-01

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
real loopback server in a separate child process within one workflow step.
Validated private startup data preserves local input settings, invocation-only
enablement, temporary output, run/attempt/revision identity and UTC clocks.
Readiness must match that exact child and invocation, not merely an available
port. The client posts to `/plan` and reads the batch health summary while the
same child remains alive. The supervisor closes and reaps it in `finally`.
It verifies the returned
five-format native output and selected artifact before exposing commit paths.
Completed planning is not proof of summarization or publication.

## Manual controls

The dispatch form takes article limit, worker count, partition strategy and
three independent article-age overrides. Their labels are:

- `Institutional sources - article age windows (hours)`
- `Trade press - article age windows (hours)`
- `Community sources - article age windows (hours)`

Each age input accepts a strictly increasing comma-separated list of positive
hours, such as `24,36,48`. Blank optional values use configuration. Duplicate,
decreasing, zero, negative and malformed age lists fail before collection.
Values are environment data, never interpolated shell code. The run resolves
its own config before article fetch, screening, selection and reporting;
concurrent requests cannot replace each other's age windows. The applied
policy report shows each effective age list and its origin.
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
bypassed. Source-based bucket shares and buffers remain 60/10, 30/5 and 10/5
percent; age controls do not turn source authority into an article verdict.

The workflow does not profile live planner CPU or RAM. It still records the
configured host fingerprint and commits it with the planner ledgers.

## Local offline checks

Inspect `npm run test:changed -- --list` from `frontend/`. For service-only
changes, use the installed declared packages rather than a full Python group:

```text
bun run --cwd packages/common-contracts check
bun run --cwd packages/ledger-file-writer check
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

The generated bare-origin case executes the actual commit CLI, checks the
new remote metadata without raw-day indexes, replays it safely and verifies that
the checkout did not change. Helper-only coverage cannot certify this entry.
`safe-persist-http.test.ts` checks real loopback delivery and exact remote bytes.
The finalization cases also run the actual finalizer CLI through its separate
delivery child and require the `safe_persist_http_completed` log event.
They retain report and metadata recovery checks after delivery failure.
Independent writer and contract tests own native digest, identifier and
historical ledger coverage. The workflow does not add a synthetic receipt.

## Saved output and failures

`services/feed-ingest-plan/scripts/` owns workflow execution, local input loading,
native verification, metadata commits, artifact preparation and
reporting. `services/host-probes/scripts/` owns optional controlled host tools.
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

Five tasks follow `Collect and select articles with a supervised server`:

1. `Commit ledgers and write report` starts its own supervised
   [safe-persist HTTP child](../architecture/sources/feed-operator-api.md#safe-persist-http-delivery)
   and sends one request for all verified completed ledgers. The existing
   adapter and Git engine perform delivery. The task closes and reaps that
   child, then calls the Markdown API and prepares the upload directory.
   A delivery or report failure does not stop the remaining preparation;
   the task still fails after preserving its useful output.
2. `List actual upload files as JSONL` uses the existing structured publisher
   to name each actual file relative to the ZIP root, then its total count.
   It reads only this run's prepared `artifacts` directory, follows the
   upload's ordinary file matching and excludes hidden files and directories.
   The inventory is beside the upload in the job log; it does not change the
   third-party action's file-count message or add a file to the archive.
   Its `artifact-upload` completion means enumeration, not upload success.
3. `Upload run artifacts` uploads that prepared directory as one archive named
   `collect-and-select-articles-<run>-<attempt>`, including after finalization
   failure. It contains `<run>-<attempt>-selected-articles.json` for the next
   summarizer, plus the delivery result and Markdown report when available.
   The summarizer downloads this named artifact and reads its selected JSON
   file, not a ledger. Article bodies never enter the Git request.
4. `Upload failed raw documents` runs only when the dropdown is `true` and a
   diagnostic file exists. Preparation first hands the closed
   `raw-document-contents.jsonl` to the hash-free artifact-directory destination,
   with only that exact target permitted. The separate archive is named
   `raw-document-contents-<run>-<attempt>`. Zero failed documents means no file
   and no debug upload. Failed collection still prepares and uploads available
   diagnostics; no successful raw input, extracted-text substitute or new
   retention policy is added.
5. `Finish and clean up` checks collection, finalization and the normal upload's
   returned artifact identity, plus the diagnostic upload when applicable.
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
population is uploaded. Raw diagnostics never enter this normal archive or
the metadata Git request. Invalid evidence fails preparation while independently
verified files remain recoverable. Cancellation skips new Git delivery while
still attempting the report and recovery upload.

Readiness, graceful drain and forced-exit waits are finite settings under
`supervision` in `config/feed-ingest-plan-service.json`; the
[runner](../architecture/sources/feed-plan-runner.md#entry-points-and-controls)
defines their defaults and failure behavior. Termination cancels the real HTTP
client, then closes the child pipe. Pipe closure also triggers child cleanup
when the supervisor disappears. Only the exact spawned child can be forcibly
killed. The server is never detached or kept alive across workflow steps.

The Markdown report reads the body-free response, health result, captured
effective settings and host fingerprint. Only Run outcome and Needs attention
are visible. Per-feed article results, Request counts and coverage, Why
articles were not selected, Effective settings and Execution measurements
use closed-by-default folds. Routine notices do not repeat the tables;
actionable run and progress warnings remain. The report cannot establish
publication and stays separate from the delivery receipt.
The workflow writes the summary into the existing downloadable Markdown
artifact, with per-feed exclusion diagnostics appended only to that artifact.
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
in this run's response before showing article HTTP, fetch and robots evidence.
It counts each terminal execution/candidate once; retries are not extra
articles. A robots response never substitutes for an article response.
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
promise. Shares remain fractions and switches remain booleans.
The authority coefficient is not a source-tier weight; the
[curation rules](../architecture/sources/feed-curation.md#inputs-and-independent-evidence)
define the separate feed and tier factors.
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
An unsafe cleaned target is `FETCH_FAILED`, not a missing-field count.
The [article cleanup policy](../architecture/sources/feed-harvesting.md#inputs-and-identity)
removes all article query parameters even when `tidy_urls` is false. Feed
parameters remain intact.

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
