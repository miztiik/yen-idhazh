# Run the isolated feed planner checks

**Last Updated**: 2026-10-28

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
Validated private startup data preserves staged history, invocation-only
enablement, temporary output, run/attempt/revision identity and UTC clocks.
Readiness must match that exact child and invocation, not merely an available
port. The client posts to `/plan` and reads the batch health summary while the
same child remains alive. The supervisor closes and reaps it in `finally`.
It verifies the returned
five-format native output and selected artifact before exposing commit paths.
Completed planning is not proof of summarization or publication.

## Manual controls

The dispatch form takes freshness, article limit, worker count and partition
strategy through the real CLI request validator. Values are environment data,
never interpolated shell code. Blank optional values use configuration.
For `none`, clear the worker count or set it to one.

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
Independent writer and contract tests own native digest, identifier and
historical ledger coverage. The workflow does not add a synthetic receipt.

## Saved output and failures

`services/feed-ingest-plan/scripts/` owns workflow execution, bounded history
staging, native verification, metadata commits, artifact preparation and
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

History staging uses the [bounded day membership contract](../reference/feed-planner-ledgers.md#raw-day-membership).
Named Git days, not saved raw-day JSON lists, identify all Parquet siblings.

Four tasks follow `Collect and select articles with a supervised server`:

1. `Commit ledgers and write report` calls the safe-delivery API once for all
   verified completed ledgers, then calls the Markdown API and prepares the
   upload directory. A commit or report failure does not stop the remaining
   preparation; the task still fails after preserving its useful output.
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
4. `Finish and clean up` checks collection, finalization and the upload's
   returned artifact identity. It rechecks the saved result and exact Git
   delivery receipt before removing only the temporary run directory.
   An earlier collection failure still fails the job after completed
   diagnostics have landed. Failed finalization, missing confirmation or a
   failed upload leaves temporary files untouched. A recovery artifact does
   not turn a failed commit into success.

When the metadata commit is not confirmed, the same artifact also contains
`uncommitted-metadata-<run>-<attempt>/`: only the exact validated current-run
metadata files and `current-run-files.json`. It can contain multiple UTC-day
files. No whole temporary root, private SQLite store or parsed/rejected
population is uploaded. Invalid evidence fails preparation while independently
verified files remain recoverable. Cancellation skips new Git delivery while
still attempting the report and recovery upload.

Readiness, graceful drain and forced-exit waits are finite settings under
`supervision` in `config/feed-ingest-plan-service.json`; the
[runner](../architecture/sources/feed-plan-runner.md#entry-points-and-controls)
defines their defaults and failure behavior. Termination cancels the real HTTP
client, then closes the child pipe. Pipe closure also triggers child cleanup
when the supervisor disappears. Only the exact spawned child can be forcibly
killed. The server is never detached or kept alive across workflow steps.

The Markdown report reads the body-free response, health result, effective
settings and host fingerprint. It places the host fingerprint before the
run facts, writes the report before upload and writes the same Markdown to
the job summary. The report stays separate from the delivery receipt.
It emits five grouped notices: Host fingerprint, Feed work, Request counts,
Grouped exclusions and Applied policy. Full per-feed details stay in the
summary rather than one notice per feed or article. Effective settings include
workflow overrides, not just committed defaults. Missing policy evidence is
reported as not recorded; defaults are not substituted.
Reporting is controlled by `workflow_reporting.enabled`; it cannot change
ledger bytes or establish completion.
The exported Markdown renderer and its separation from production digest
presentation are documented in the [operator API reference](../architecture/sources/feed-operator-api.md#markdown-rendering-api).
The applied-policy table follows run facts. Its article limit is a maximum,
not a promised article count. Per-feed article results are collapsed and sort
by chosen articles, admitted articles, then feed name. The collapsed request
section contains a coverage table and request-count table. Coverage separates
expected closed UTC days, complete day files, days with recorded counts and
feeds with complete counters. The request rows sort by article requests,
feed requests, then feed name; unknown counts sort last. This does not change
saved source order or other views.

Each request category is added independently. A partial value carries an
ASCII `*`; only recorded counts are added, never estimates. The coverage table
and notes show the UTC period, recorded counter days, complete-day counts and
records with unknown counters. Missing or incomplete day files, unattributable
records and staged-input gaps are stated separately. "Not recorded" means no
usable counter is present, not zero requests. A complete known-empty period
reports zero. The request notice adds only known totals and marks partial
totals too; it never calls them complete. Grouped exclusions are collapsed and
sort by count descending, then reason code. Exact coverage fields are defined in the
[ledger reference](../reference/feed-planner-ledgers.md#design-rationale).

`MISSING_REQUIRED_FIELDS` is an article rejection: its offered URL or identity
was missing or invalid, or extraction produced no usable title. A grouped
count does not identify the exact missing field and does not mean a feed
configuration field is absent. The protocol reason code is unchanged.
An unsafe cleaned target is `FETCH_FAILED`, not a missing-field count.
The [article cleanup policy](../architecture/sources/feed-harvesting.md#inputs-and-identity)
removes all article query parameters even when `tidy_urls` is false. Feed
parameters remain intact. Sparse workflow preparation stages the bounded
[saved-address history](../architecture/sources/article-identity-history.md);
incomplete recovery is logged rather than treated as complete deduplication.

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
history reads day-level ledger data from the current commit, not only the
immediately previous workflow run; its data families and windows are in the
[bounded day membership contract](../reference/feed-planner-ledgers.md#raw-day-membership).
The sparse checkout still supplies runnable source and configuration while
keeping the growing state tree out of the worktree. Adapter checks remain in
CI; repeating them here does not exercise a live API. The selected text upload
and ledger commit stay separate because the summarizer needs article bodies
while the ledger does not. CPU and RAM profiling does not prove API correctness,
so this workflow keeps the host fingerprint but does not profile the planner.
The closing tasks group orchestration rather than merge API responsibilities.
Safe Git delivery and Markdown rendering remain separate functions. One
standard artifact upload carries selected text, run evidence and any recovery
files, so consolidation adds no upload dependency. Cleanup follows confirmed
delivery instead of discarding the only recoverable copy.

## See also

- [Runner](../architecture/sources/feed-plan-runner.md)
- [Operator APIs](../architecture/sources/feed-operator-api.md)
- [Ledger reference](../reference/feed-planner-ledgers.md)
- [Gate commands](run-the-gates.md)
