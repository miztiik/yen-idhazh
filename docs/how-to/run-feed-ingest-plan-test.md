# Run the isolated feed planner checks

**Last Updated**: 2026-10-22

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

The last workflow step requires both independently verified live planning
completion and a labelled `generated_fixture` full-audit result. That fixture
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

The workflow exposes four strings. The actual CLI parser converts them into
the shared request validator; strings never become shell code.

### Table A - Run controls

| Id | Control | Meaning |
| --- | --- | --- |
| A1 | `freshness_hours` | Positive finite maximum article age; default 24 hours. Overrides this run's age cutoff, not the ranking half-life. |
| A2 | `article_limit` | Optional positive integer; blank uses the configured 100-article selection limit. |
| A3 | `shards` | Optional positive worker count; blank uses configuration. |
| A4 | `partition_strategy` | `bin-pack`, `round-robin` or `none`; blank uses configuration. |

There is no date or reporting input. One captured UTC clock supplies the run
date and the runner. Strategy `none` resolves to one worker and refuses an
explicit larger count before fetching. The committed planning configuration
owns reporting and all other controls.

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
The configured six-second fetch deadline still applies to each request.
The selected article limit is not a fetch limit: all configured feeds and
their offered entries remain in scope before curation chooses the portfolio.

Main repository CI separately extends the existing contract-tier case
`backend/tests/ledger/test_feed_ingest_ledgers.py::test_zero_completion_evidence_survives_without_erasing_an_earlier_complete_attempt`.
It runs the real Bun producer, actual gardener daily/monthly/yearly jobs, then
the independent Bun selector. Subprocesses have fixed timeouts and missing Bun
fails rather than skips. This case is not part of the Python-free isolated
workflow. [Gate commands](run-the-gates.md) own its installation and test cost.

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

After both the genuine planning check and the separate generated full-audit
gate pass, the workflow invokes the existing host collector and commits only
the explicit current-run file list plus its returned host file list. The
generated full-audit directory is never included. The main commit contains:
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
with the resolved requested limit. Feed failures are separate. Per-reason
counts name their denominators; feed decisions use every configured source,
including inactive sources that were not fetched. Fetch failures separately
use attempted feeds. Unknown feed entry counts remain unknown.
Recorded progress supplies completed operation outcomes and paired elapsed
intervals for history, planning, audit and HTTP. Event gaps are not summed as
operation time. Intervals overlap and must not be added. The host row supplies
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

## See also

- [Planner execution](../architecture/sources/feed-plan-runner.md)
- [Partition evidence](../architecture/sources/feed-partitioning.md)
- [Ledger persistence](../architecture/contracts/persistence.md)
- [Local gates](run-the-gates.md)
