# Run the isolated feed planner checks

**Last Updated**: 2026-10-26

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

The workflow starts the real loopback listener, reads listener health, posts
to `/plan` and stops the listener in `finally`. It verifies the returned
four-format native output and selected artifact before exposing commit paths.
Completed planning is not proof of summarization or publication.

## Manual controls

The dispatch form takes freshness, article limit, worker count and partition
strategy through the real CLI request validator. Values are environment data,
never interpolated shell code. Blank optional values use configuration.
For `none`, clear the worker count or set it to one.

The independent host-tools checkbox defaults off. It runs the existing
separate host proof, not a measurement of the live article selection.
Its failure is explicit but does not gate planner output or commit. No
hardware proof or benchmark is required to finish planning.

## Local offline checks

Inspect `npm run test:changed -- --list` from `frontend/`, but do not execute a
Python-bearing local group for this work. Use the installed declared packages:

```text
bun run --cwd packages/common-contracts check
bun run --cwd packages/ledger-file-writer check
bun run --cwd services/feed-ingest-plan check
bun run --cwd services/feed-ingest-plan test
bun test ./.github/scripts/tests/feed-ingest-plan-report.test.ts ./.github/scripts/tests/feed-ingest-plan-outputs.test.ts ./.github/scripts/tests/feed-ingest-plan-workflow.test.ts --timeout 30000
bun run .github/scripts/feed-ingest-plan-verification.ts
```

The existing case timeout bounds test execution; it is not a planner speed
target. The workflow case compiles mandatory adapters and tests from its exact
named sparse inputs; independent host tools retain their own checks. An
unselected local module cannot satisfy a missing dependency. A second
fixed-input copy runs the native verifier with no backend directory.

Recorded RSS/HTML and transport facts drive the actual listener, worker
extractor, complete public offer flow and CLI. Generated native files prove
metadata/artifact agreement, original UTC work dates, incomplete history,
distinct attempts and explicit empty or partial outcomes. No test contacts
an external feed, starts a live workflow or requires local Python.

The generated bare-origin case executes the actual commit CLI, checks the
new remote metadata and raw-day indexes, replays it safely and verifies that
the checkout did not change. Helper-only coverage cannot certify this entry.
Other-family UUID, canonical-byte and legacy native-file vectors remain
separate compatibility checks.

## Saved output and failures

The commit manifest permits exact current raw Parquet paths for the four
planner siblings only. The committer validates bytes, appends them through a
temporary Git index and rebuilds the affected raw-day indexes from the
current main commit. A normal push retry preserves another writer's changes.
It does not rewrite the checkout, rebase or force-push.

Partial completed files are retained and can be committed even when the
planning step fails. Selected text is uploaded separately for the summarizer.
Body-free evidence uploads name response, health, measured staging time,
commit result and current planner metadata. They never upload the whole
temporary root, private SQLite store or parsed/rejected populations.

The Actions Markdown report reads the actual body-free response and health
result. It labels units, UTC clocks, incomplete coverage and unknown values.
Reporting cannot change ledger bytes or establish completion.

## CI and hosted verification

The repository's test-only `ci.yml` remains authoritative for native typing,
field/default/vocabulary bindings, full-suite and real gardener packing.
Its site and browser jobs install Bun and the frozen shared-contract/writer
packages for the current native planner fixtures. Cost is those existing
test dependencies on each clean job; no new package or browser bundle bytes.
Do not dispatch `feed-ingest-plan-test.yml` to obtain those checks: it does
live work and commits data. A conflicting PR must first merge current main
normally, then receive CI on its exact resolved head.

A later authorized live run can verify feed availability and actual hosted
operation timings. Offline fixtures and local checks make no production
throughput claim.

## Resource proof

The optional host proof uses the independent sample, pinned-process profile,
copy and cache tools. Its evidence describes those controlled operations,
not article-attributed cost or a planner speed gain. It never determines
planning completion. The host APIs and their default-off controls remain
available independently of this workflow.

## See also

- [Runner](../architecture/sources/feed-plan-runner.md)
- [Operator APIs](../architecture/sources/feed-operator-api.md)
- [Ledger reference](../reference/feed-planner-ledgers.md)
- [Gate commands](run-the-gates.md)
