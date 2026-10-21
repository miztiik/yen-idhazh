# Run the isolated feed planner checks

**Last Updated**: 2026-10-21

How do you check the TypeScript planner without changing daily publication?
Use `.github/workflows/feed-ingest-plan-test.yml`. It starts only by manual
dispatch, has read-only repository access, and never commits or publishes
its output. The production digest workflow is unchanged.

## Current readiness

**A complete audited run is not available.** The runner's service flag remains
off in `config/feed-ingest-plan-service.json`. Its removal condition requires
the actual audit writes and complete-attempt verification to be integrated
and approved. This workflow does not bypass that flag.

The actual CLI entrypoint runs the stages and records article assessments
and diversity measurements. It returns their real files and receipts with
`assessment_diversity_recorded_audit_pending`; the overall plan still reports
`dispatches_persisted_audit_pending` and `audited_complete: false`.
The workflow calls that entrypoint once, not a separate recorder.
The last workflow step
refuses an unaudited result with exit code 2. A disabled runner, missing input,
invalid request or damaged file also fails; none becomes a successful empty
plan. Green adapter tests do not certify hosted execution or audit completion.

Source-complete records and complete-attempt verification remain unavailable.
The recorder refuses unsupported publication timing, negative article ages
or configured concentration counts outside the current contract before
writing either measurement ledger. These failures produce no successful
summary. The packed-history reader also
cannot prove an original raw file's ordered-row commitment from aggregate
compact counts. These are explicit missing capabilities, not completed checks.
See [partition evidence](../architecture/sources/feed-partitioning.md).

## Manual controls

The workflow exposes four strings. The actual CLI parser converts them into
the shared request validator; strings never become shell code.

### Table A - Run controls

| Id | Control | Meaning |
| --- | --- | --- |
| A1 | `freshness_hours` | Positive finite maximum article age; default 24 hours. Overrides this run's age cutoff, not the ranking half-life. |
| A2 | `article_limit` | Optional positive integer; blank uses the configured selection limit. |
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

The native verifier writes the bounded recorded dispatch fixture through the
public ledger writer, then uses the real Parquet/WASM and Arrow reader. It
checks native list and struct columns, envelope and row identities, row
validation, ordered content digests, and recorded candidate, URL and UUID
values. It also compares the existing canonical-byte compatibility vector,
including Unicode, lists, nulls and floating-point values.

Actual planner integration tests replay recorded HTTP and DNS responses
through harvesting, screening, curation and partitioning. They read the
generated dispatch files, distinguish missing files from explicit empty
results, and invoke the actual CLI to record assessment and diversity files.
Native readback verifies both ledgers; their file identities, row counts and
content digests must match the returned receipts. Missing files or mismatched
receipts fail verification. Actual CLI runs with reporting off and on must
produce the same stage and measurement ledger digests. No test makes a
network request or starts Python. These checks do not claim that the Python
reader ran, that live feeds are reachable, or that a hosted job meets a speed
target.

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

The optional artifact upload preserves generated evidence without committing
it. Article text can be present in dispatch Parquet files, as declared by
their existing contract. Treat artifacts as test evidence, never publication.
No upload is proof that a plan is complete.

## Optional GitHub report

`workflow_reporting.enabled` in `config/feed-ingest-plan.json` defaults to
false. When false, the report adapter writes no annotations or summary. It
does not control the required execution outputs, ledger writes or events.

When enabled, the separate adapter validates the existing typed event array
and formats source outcomes, observed stage counts and candidate-decision
counts. It labels missing evidence and incomplete audit explicitly. It
escapes source titles for Markdown and workflow-command data for annotations.
It omits source URLs, headers, full event dumps and article text.

The adapter is not imported by core stages or the required output adapter.
Report errors remain visible in their own step but do not fail execution.
Required native verification and the final audit gate do not ignore errors.
Remove the reporting key, adapter, its tests and its workflow invocation
together when development reporting is no longer needed. The
[policy contract](../architecture/sources/feed-ingest-policies.md) owns this
flag and its default.

## See also

- [Planner execution](../architecture/sources/feed-plan-runner.md)
- [Partition evidence](../architecture/sources/feed-partitioning.md)
- [Ledger persistence](../architecture/contracts/persistence.md)
- [Local gates](run-the-gates.md)
