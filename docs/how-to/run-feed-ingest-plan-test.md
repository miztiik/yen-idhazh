# Run the isolated feed planner checks

**Last Updated**: 2026-10-24

How do you check the TypeScript planner without changing daily publication?
Use `.github/workflows/feed-ingest-plan-test.yml`. It starts only by manual
dispatch and commits genuine completed planner and host Parquet files to main.
This is a Git data commit, not site publication. The production digest workflow
is unchanged.

## Current readiness

**Full completion is available when all required evidence is supplied.**
The runner's service flag remains
off in `config/feed-ingest-plan-service.json`. Its removal condition requires
the actual audit writes and complete-attempt verification to be integrated
and approved. The workflow explicitly enables only its isolated invocation;
it does not change the committed default or approve production use.

The workflow starts the actual HTTP listener, verifies its health through
loopback HTTP and posts the validated request to its planning route. It does
not substitute a CLI call or an in-process router call. The listener is stopped
in `finally`; CLI capability remains available outside this acceptance run.
The server runs the stages and records article assessments,
diversity measurements and source completion records. A verified current raw
attempt can report `planning_complete: true` separately from
`audited_complete: false`. The workflow calls that route once, not a
separate planning recorder. It reads the returned source records and all five
required ledger file sets through the original completion selector before
exposing per-run planning completion.

The last workflow step requires independently verified live planning,
separate live feed and selected HTML article fetch/parse/replay, and a labelled
`generated_fixture` full-audit result. That fixture
runs the real observer against generated publication and complete named history,
then independently reads its actual native output. Either missing proof exits
with code 2. Live planning alone cannot pass; test publication is never labelled
as publication of the live plan.
A disabled runner, missing input,
invalid request or damaged file also fails; none becomes a successful empty
plan. Green adapter tests do not certify hosted execution or audit completion.

The recorder preserves first-seen timing, signed article ages and every
positive configured concentration count. Invalid or missing evidence still
fails before measurement writes. New logical receipts survive actual daily,
monthly and yearly compaction. Old receipts without logical proof still need
their original raw files and remain unverifiable if those files are gone.
See [partition evidence](../architecture/sources/feed-partitioning.md).

## Manual controls

The workflow exposes three text boxes, one strategy dropdown and one
whole-machine RAM checkbox. Planning values pass through the actual CLI parser
and shared request validator; the checkbox passes through a strict boolean
parser into the isolated task profiler. None becomes shell code.

### Table A - Run controls

| Id | Control | Meaning |
| --- | --- | --- |
| A1 | `freshness_hours` | Positive finite maximum article age; prefilled with 24 hours. Overrides this run's age cutoff, not the ranking half-life. |
| A2 | `article_limit` | Optional positive integer; prefilled with 100 articles. Clear it to use configuration. |
| A3 | `shards` | Optional positive worker count; prefilled with 4 workers. Clear it to use configuration. |
| A4 | `partition_strategy` | Dropdown with `bin-pack` (default), `round-robin` and `none`. |
| A5 | `profile_machine_memory` | Boolean checkbox, default false. Collect whole-machine RAM during actual document fetch/parse work. CPU and PID RAM stay enabled for that proof; the separate standalone RAM HTTP sample and copy OFF/ON proof remain independent. |

The repository's `config/feed-ingest-plan.json` owns the first four defaults;
`config/host-probes.json` owns the machine-RAM default. GitHub requires literal
form defaults, so the existing workflow test binds them to their configuration
and the strategy choices to the request validator. Update form defaults when
changing their configured values.

There is no date or reporting input. One captured UTC clock supplies the run
date and the runner. For `none`, clear the prefilled `shards` value or set it
to `1`. It uses one worker and refuses a larger explicit count before
fetching. The committed planning configuration owns reporting and all other
controls.

## Local offline checks

Use the installed Bun environment and declared package dependencies. From the
repository root:

```text
bun test ./.github/scripts/tests/feed-ingest-plan-report.test.ts ./.github/scripts/tests/feed-ingest-plan-outputs.test.ts ./.github/scripts/tests/feed-ingest-plan-workflow.test.ts --timeout 30000
bun run .github/scripts/feed-ingest-plan-verification.ts
```

The test command allows the embedded strict TypeScript compiler up to 30
seconds per test; this is not a planner speed requirement. One invocation
checks the adapters, tests and actual inline program together, without a
second adapter compilation. The workflow also runs strict package checks.
The existing main CI gates job runs these exact three selectors and the
native verifier after its package checks. A normal planner-suite pass alone
cannot replace that adapter and workflow preflight.
Use the [shared selector](run-the-gates.md) with `--list` to inspect broader
coverage. Do not execute a selection that adds Python for these isolated
checks. Repository-wide CI remains separate and authoritative at merge.

The cross-package native verifier lives with the workflow adapters at
`.github/scripts/feed-ingest-plan-verification.ts`, not in the shared contracts
package. The contracts package must check and test after only its own frozen
dependency installation, before any writer or service dependency exists.

The native verifier writes current and unchanged legacy dispatch fixtures through the
public ledger writer, then uses the real Parquet/WASM and Arrow reader. It
checks native list and struct columns, envelope and row identities, row
validation, ordered content digests, and recorded candidate, URL and UUID
values. It also compares the existing canonical-byte compatibility vector,
including Unicode, lists, nulls and floating-point values.
Physical ledger reads preserve the stored layout and digest before any declared
row migration. Current planner events use the current UUID contract only;
reporting validates it without a TypeScript legacy event branch.
The fixed `legacy-seen-day.parquet` fixture retains actual Python-written
pre-generic-task storage. Its original envelope controls which identity columns
exist and whether `job` is nullable. The native reader verifies its original
digest before filling the absent optional task fields. This is separate from
row-schema migration; a newer row declaration cannot add columns to old bytes.
The `legacy_row_count` and `legacy_seen_row_count` output values count fixed
compatibility fixture rows; they do not trigger a repository-wide scan.

Actual planner integration tests replay recorded HTTP and DNS responses
through harvesting, screening, curation and partitioning. They read the
generated dispatch files, distinguish missing files from explicit empty
results, and invoke the actual CLI to record assessment and diversity files.
Native readback verifies both ledgers; their file identities, row counts and
content digests must match the returned receipts. Missing files or mismatched
receipts fail verification. The actual CLI's complete source files are independently read and proved.

The full-file reporting check uses one actual result. It reads every stage,
measurement and source file before and after disabled and enabled reporting,
and requires identical bytes and digests after each call. Independent runs
cannot have identical source-file digests: source records retain measured
fetch/parse durations and commitments to newly generated file identities.
Those values are verified unchanged, never removed or normalized to pass.
The same applies to newly recorded per-article diagnostic timings: independent
runs need not have equal commitments. Reporting must preserve each run's own
bytes, selected identities and recorded proof.

One generated publication fixture writes native published rows from the actual
CLI's selected dispatch identities, plus a matching digest and settled health
evidence. The real publication observer reads those files and the actual
producer's source completion files, then writes independently verified native
diversity and source-observation files. This fixture proves the observer
boundary. A second complete fixture includes every configured history day,
explicit known-empty days and recorded event evidence. It must compute full
completion and pass `verifyPublicationMetrics` after actual observer readback.
API and CLI tests also require pending results when planning, publication,
events or closed history are missing, and complete measured empty portfolios.
This is test evidence, never production publication.
No isolated test makes a
network request or starts Python. These checks do not claim that the Python
reader ran, that live feeds are reachable, or that a hosted job meets a speed
target.

### Separate live fetch and parse

After verifying the actual plan, the workflow chooses one active source that
the current plan successfully fetched and parsed. It resolves that source ID
back to the committed source configuration. No entry link, page canonical tag
or other fetched text selects a destination.

An independent actual Hono listener receives separate POST requests to
`/api/2026-10-20/fetch` and `/api/2026-10-20/parse`. Fetch uses `kind: feed`;
parse references that exact fetch request, article identity and correlation.
The same checks then run with `kind: article`. Its operator URL comes only
from a current-run sealed dispatch, read by its exact receipt filename through
the native Parquet reader and current dispatch contract. The earlier original
completion selector verifies the actual dispatch and selection ledgers.
The proof rechecks dispatch receipt hashes, selected membership, run, completed
attempt, UTC day and correlation, then requires nonempty extracted content and an active
configured source. It does not follow a new feed link or a page canonical tag.
Both document pairs retain the actual plan's run and correlation.
The check verifies the same article, source, run and correlation, distinct
UUIDv5 observations, and the parse-to-fetch and attempt-to-fetch causes.
It counts actual outbound DNS and HTTP calls through the unchanged production
resolver and transport. Parse must make no such calls.

The listener stops and reopens with unchanged inputs and the same private
output root. Both completed request keys must return the original exact
response bytes and statuses, with no outbound calls. Changed input,
operation and configuration must each return HTTP 409 `REQUEST_CONFLICT`.
A digest over each pair's two named journal records must remain unchanged after replay
and refusals. This proves unchanged completed receipts, not exactly-once
external network work across an interrupted fetch.

`stage-api-proof.json` records
`scope: live_configured_feed_and_selected_article`, `status`, `stage`,
`git_sha`, `documents`, `reason` and `error`. Each document records `kind`,
`status`, `stage`, `git_sha`, `source_id`, `article_id`, `run_id`,
`correlation_id`, `selection`, `calls`, `pending_request`,
`journal_records_sha256`, `reason` and `error`. Article `selection` retains
the selected candidate, run and correlation plus the exact native dispatch
file identity and content digest; feed selection is null. A pending request
retains its stage, endpoint and exact request fields before HTTP work starts.
Each completed call holds its stage, endpoint,
exact request keys and identity fields in `request`, `http_status`, exact
body-free feed `response_json`, its full-response `response_sha256`,
whitelisted `response_metadata`, and measured `network: {dns, http}` counts.
HTML responses and all error responses always have `response_json: null`.
Fetch metadata retains only validated body-free receipt fields.
HTML parse metadata retains the fetch request and observation identities,
kind, typed failure, actual word count, text digest and UTF-16 string length,
paywall evidence, bounded warnings and the native quality object, including
extractor and sanitizer fingerprints. It excludes article text, title and author.
Full original and replay response bytes are compared in private memory
before completion; comparing two redacted null fields is never replay proof.
An invalid response is withheld as
`response_json: null`; its status and digest remain, and the check fails.
The digest pair is `{before_restart, after_checks}`. Proof is written before
each call and after each response; failures retain the exact failing stage.
Only completed proof exposes `stage_api_complete: true`. An absent successful
source, unavailable readable selected article, failed fetch, failed parse,
identity mismatch or changed replay fails
the job; none is silently skipped.

An unavailable article records `NO_READABLE_SELECTED_ARTICLE`; a live article
without readable admitted extraction records `HTML_EXTRACTION_UNAVAILABLE`.
This includes known null quality, a paywall or an empty body. Malformed
metadata remains a validation failure, not an unavailable reading.
Other bounded reasons distinguish an unavailable feed, invalid completion,
dispatch membership mismatch, failed checks and private cleanup failure.
The actual quality flags, short-abstract exemption and native signal precedence
remain unchanged. This check makes no worker-token or truncation claim and
does not shorten worker input.

The live proof now requires both a configured RSS/Atom feed and a genuine
selected HTML article. Existing recorded API cases exercise native selection,
redaction, response hashing and private exact-byte replay without network access.
The actual planning request stays unkeyed and is called once; this workflow
does not claim live keyed-plan replay, interrupted-request recovery, concurrent
process locking or publication of its live selections. A reviewed merge and
one coordinator-owned manual dispatch are still required for hosted evidence.

The live HTTP step appends `progress.jsonl` and `audit-events.jsonl` during work,
prints the same observations, and uploads partial evidence even on failure or
cancellation. The completed `events.json` remains the report input.
GitHub independently stops this step after ten minutes; this limit supervises
the runtime even if its own event loop stops servicing deadline timers.
The loopback planning `fetch` disables Bun's separate five-minute socket-idle
timer. Planning returns one final JSON response, so an active server can
legitimately send no response bytes while it works. The independent ten-minute
step deadline remains the supervisor; server receive limits and article fetch
deadlines are unchanged. The health request keeps its ordinary client timeout.
The configured six-second deadline still applies to each fetch attempt;
the [shared whole-operation retry budget](../architecture/sources/feed-harvesting.md#inputs-and-identity)
also bounds DNS, robots, redirects and backoff together.
The selected article limit is not a fetch limit: all configured feeds and
their offered entries remain in scope before curation chooses the portfolio.

Main repository CI separately extends the existing contract-tier case
`backend/tests/ledger/test_feed_ingest_ledgers.py::test_zero_completion_evidence_survives_without_erasing_an_earlier_complete_attempt`.
It runs the real Bun producer, actual gardener daily/monthly/yearly jobs, then
the independent Bun selector. Subprocesses have fixed timeouts and missing Bun
fails rather than skips. This case is not part of the Python-free isolated
workflow. [Gate commands](run-the-gates.md) own its installation and test cost.

## Resource proof

The isolated workflow explicitly enables the default-off whole-task CPU and
PID RAM controls only for its separate fetch/parse listener. Whole-machine task
RAM follows `profile_machine_memory`, false by default. It does not control PID
RAM, the standalone RAM HTTP proof or the copy benchmark. The independent worker
runs from each task's opening through closing observation, requesting one poll
each second. The rolling CPU window is a separate control, not a one-second
measurement cutoff. Each document's
`stage-api-proof.json` entry contains validated profiles for exactly its two
actual work calls. Their request, run and correlation identities must match.
Restart replay and conflicts must leave the profile count at two as well as
preserving the original response bytes and journal digest. No raw article
body, parser response or journal enters these profiles.

When optional reporting is enabled, completion adds task CPU and RAM to Tables
H and I in the GitHub step summary and emits concise resource notices. Table J
shows the separate RAM sample, L3 cache, derived copy buffer size, copy OFF/ON
rates and host context. CPU is host-wide, not PID-specific. Sampled RSS maxima
and machine available-memory minima are not exact task peaks. Missing evidence
is not recorded; disabled machine RAM is labelled disabled, never zero.
The report refuses malformed or foreign revision/run/attempt/correlation/request
evidence before writing these measurements. Reporting errors remain in the
existing optional step and do not become a new planner gate.

A fast live parse may have only a partial CPU window or no elapsed CPU ticks.
That is recorded, not padded with a wait or reported as a full window.
The existing offline API case also parses a bounded generated document from
the named recording, while an independent worker polls through synchronous
work. Its `recorded_parse_profile` log is recorded-work evidence, not a live
network measurement. The workflow runs these existing named cases on Linux;
Windows results do not certify Linux process RAM.

The same resource proof also starts a separate real Bun process for a
controlled CPU task. The named fixture touches 32 MiB of RAM and hashes that
buffer for at least 3.2 seconds of elapsed work. These are controlled-work
inputs, not a delay added to live fetch or parse. Actual CPU milliseconds
are measured separately and need not equal elapsed time.

The proof pins that child's PID and start ticks, then uses the real
host-probe start/stop HTTP commands. It requires multiple one-second polls,
positive CPU time for the requested external PID, matching process identities,
process and machine RAM, and actual monotonic intervals. Stop takes the closing
observation while the child is still alive; only then does the fixture owner
close its child. `resource-proof.json` retains this as `task_profile` with
scope `controlled_cpu_task`. It does not stand in for fast live document work.

After all document profiles close, the separate resource step starts the real
RAM sample HTTP listener and calls its sample route over loopback. It requires
actual CPU and machine total, free and available RAM readings, even when task
machine RAM is disabled. This is one standalone sample, not a background
machine-memory poller. After the controlled task closes, it calls the existing
host collector with copy unselected and explicitly selected for
`isolated-copy-proof`. The test records the real hardware context, L3 size if
available, derived buffer size, repeat count and median read-plus-write rate.
It allocates two buffers and measures memory-copy throughput, not L3 hit/miss
counts. Copy work never overlaps fetch/parse or controlled-task CPU measurement.

`resource-proof.json` contains only validated safe metadata in the existing
temporary evidence root. Completion requires `resource_proof_complete: true`.
Main CI also runs this same task CPU/RAM HTTP and copy proof without fetching live feeds
or publishing data, and retains the `typescript-resource-proof` artifact.
Its artifact uses the existing ignored
`test-results/host-probes/resource-proof.json` test-report path; the isolated
workflow keeps its proof in the temporary evidence root.
Neither path writes another host ledger or changes shared defaults. See
[measurement semantics and controls](../reference/host-metrics.md#whole-task-typescript-samples).
The integrated live-feed and selected-article proof still needs the
coordinator-owned manual dispatch after review.

## Inputs and isolated evidence

The initial sparse checkout names configuration, relevant service and package
directories, the adapter scripts and tests, dependency manifests and locks,
and bounded recorded fixtures. It excludes the backend.

The workflow uses the runner's `requiredSeenDays` with the same captured UTC
clock. The current `collect.seen_window_days` value is 90, so its inclusive
window names 91 days: today and the preceding 90 days. This is separate from
the metrics window, currently 14 named days. It passes actual per-day inputs
to `settings.inputs.seen_days`, preserving authored named inputs.

Each day names raw-day and yearly, monthly and daily compact indexes. The
workflow adds their actual named files, preferring yearly over monthly over
daily over raw. It also stages a compact period's named path when its index
declares no file, so a contradictory leftover file is not hidden by sparse
checkout. It does not scan a state tree. An absent index or file is not an
empty day, and staging files alone is not proof of complete history.

Only actual rows or explicit empty evidence for every required day can
establish absence within that configured window. Missing raw indexes stay
missing inputs, never `raw_files: []`. New first-sight rows use the real
runner's writer; its returned receipt paths are included in required outputs.
The runner never claims absence across all historical time.

Trial writes go below the runner's temporary `feed-ingest-plan/state`
directory. The required output adapter returns only resolved worker counts,
worker matrix entries and registered identity-derived relative paths.
It writes `GITHUB_OUTPUT` using noncolliding multiline delimiters and cannot
claim audited success without a recorder.

The always-run artifact upload preserves partial evidence and completed files
even when committing fails. Article text can be present in dispatch Parquet
files, as declared by their existing contract. No upload proves a complete plan.

The separate API journal contains full fetched bodies. Its output root is a
new `feed-stage-api-private-*` sibling below runner temporary storage, outside
the sole uploaded `feed-ingest-plan/` directory. The workflow never uploads or
commits `planner-operations.sqlite`, its WAL/SHM files, headers or raw fetched
bodies. Each operation closes its database before responding. After stopping
the listener, the check removes only its own newly created private directory,
including on failure. A cleanup failure is explicit; any retained private
directory stays outside the artifact root. The public proof contains body-free
feed responses, redacted HTML metadata and record digests, never full HTML
parse responses or the journal records themselves.

After both the genuine planning check and the separate generated full-audit
gate pass, and the separate HTTP proof completes, the workflow commits only
the explicit current-run file list plus its returned host file list. The
existing host collector still records the actual completed planning run.
The generated full-audit directory is never included. The main commit contains:
`state/raw/feed-ingest-plan/{editorial-selections,dispatches,rejections,article-assessments,source-runs,diversity}/YYYY/MM/DD/UUID.parquet`,
any returned `state/raw/seen/YYYY/MM/DD/UUID.parquet`, and
`state/raw/host-fingerprint/YYYY/MM/DD/UUID.parquet`.
Empty ledgers have no file. Read the exact returned paths, not directory scans.

`contents: write` and checkout credentials permit the normal push. The
[committing rule](../architecture/publishing/committing.md#design-rationale)
records the owner-directed Bun exception: a separate Git index builds a
candidate on fetched main without moving the checkout, index or sparse
patterns. A rejected push retries the same immutable bytes against fresh main
under `config/push-retry.json`; it does not rerun planning. A conflicting UUID
file or exhausted deadline fails visibly and leaves artifacts intact. There is
no inventory, site, deletion or production worker update.

## Optional GitHub report

`workflow_reporting.enabled` in `config/feed-ingest-plan.json` defaults to
true. When false, the report adapter writes no annotations or summary. It
does not control the required execution outputs, ledger writes or events.

When enabled, the separate adapter validates the existing typed event array
and formats source outcomes, observed stage counts and candidate-decision
counts. The live response supplies existing source-run counts for offered,
fresh, harvested, duplicate, screened eligible, normalized and selected entries,
with the resolved requested limit. Table D groups refusals by subject and stage,
with feed groups before article groups and stages in their declared order.
Rows within each group share one denominator and sort by count, largest first;
equal counts use alphabetical reason order. The subject, stage, reason and
denominator are explicit; feed and article counts are never ranked together.
Feed decisions use every configured source, including inactive sources that
were not fetched. Article refusals use observed parsed entries, not an inferred
stage-input count. Fetch failures in the yield table separately use attempted
feeds. Unknown feed entry counts remain unknown.
Recorded progress supplies completed operation outcomes and paired elapsed
intervals for history, planning, audit and HTTP. Event gaps are not summed as
operation time. Shared `HarvestDiagnosticsSchema` validates the actual operation
diagnostics. Article completion records distinguish refusals before a fetch,
measured permitted fetches, target responses and measured extractions. A
permitted fetch includes DNS, robots, retries and redirects, so it is not an
outbound HTTP request count. Fetch and extraction times are summed work across
measured operations, not elapsed wall time. Diagnostic rows retain exact HTTP
statuses, robots results, typed causes, safe error tokens and warnings, with
explicit recorded-operation denominators. Missing historical diagnostics stay
unavailable. Intervals overlap and must not be added. The host row supplies
actual hardware identity and elapsed job observation. Screened eligible does
not mean previously unpublished. Source run, attempt and correlation identities
must match the response. Host run and recorded writer attempt must also match;
mixed-run evidence is refused. It labels missing evidence and incomplete audit explicitly. It
escapes source titles for Markdown and workflow-command data for annotations.
It omits source URLs, headers, full event dumps and article text.

The adapter is not imported by core stages or the required output adapter.
Report errors remain visible in their own step but do not fail execution.
Required native verification and the final audit gate do not ignore errors.
Remove the reporting key, adapter, its tests and its workflow invocation
together when development reporting is no longer needed. The
[policy contract](../architecture/sources/feed-ingest-policies.md) owns this
flag and its default.

The reporting default changed to true at the owner's request for a readable
yield, timing and hardware summary (kumarsnaveen, 2026-10-22). The existing
configuration control and removal condition remain in place.

## Design rationale

The separate live check fetches only a source URL already committed by the
operator. A feed proves both HTTP operations without giving parsed links new
authority to select destinations. Its private sibling output root keeps raw
bodies outside the existing whole-directory artifact upload without changing
the exact native planner and host commit list.

## See also

- [Planner execution](../architecture/sources/feed-plan-runner.md)
- [Partition evidence](../architecture/sources/feed-partitioning.md)
- [Ledger persistence](../architecture/contracts/persistence.md)
- [Local gates](run-the-gates.md)
