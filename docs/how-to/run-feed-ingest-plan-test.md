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

The CPU/RAM checkbox defaults off. When selected, it profiles the whole live
planner process and also runs the existing independent controlled host proof.
These are separate measurements in one Resources section, not per-article
profiles. The listener and planner share one Bun process; no second server
PID is required. An optional instrument failure is explicit and does not
change planning completion or block its metadata commit.

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
The selected JSON handoff, response, health, measured staging time, commit
result, effective settings, resources, report and real process logs are each
one unarchived artifact. Filenames include the run number and attempt, so
retries do not replace earlier evidence. The upload action uses each filename
as its artifact name; its `name` input does not name an unarchived upload.

The runtime log retains the real planner/listener stdout and stderr; the
commit log retains the real metadata-commit output. A pipeline failure keeps
its nonzero exit status through `tee`. Neither log is a second server or a
copy of article text.

When the metadata commit is not confirmed, a separate artifact named
`uncommitted-metadata-recovery-<run>-<attempt>` contains only the exact
validated current-run metadata files and their receipt list. This small
recovery archive can contain multiple UTC-day files. It never includes the
whole temporary root, private SQLite store or parsed/rejected populations.
It is not a successful commit. Invalid evidence fails preparation while
already copied individual evidence remains available for upload.

The Actions Markdown report reads the actual body-free response and health
result after the optional instruments finish. It writes the actual job
summary and five grouped public notices: Resources, This run's feed work,
Closed-day request spend, Grouped exclusions, and Policy used. Full per-feed
details stay in the public summary rather than one notice per feed or article.
Effective settings include workflow overrides, not just committed defaults.
Missing policy evidence stays unavailable; defaults are not substituted.
Reporting is controlled by `workflow_reporting.enabled`; it cannot change
ledger bytes or establish completion.

`MISSING_REQUIRED_FIELDS` is an article rejection: its offered URL or identity
was missing or invalid, or extraction produced no usable title. A grouped
count does not identify the exact missing field and does not mean a feed
configuration field is absent. The protocol reason code is unchanged.

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

Basic host facts use the existing collector without the copy benchmark and
respect the global host, fingerprint, frequency and placement switches.
The checkbox permits the existing whole-task profiler around the real HTTP
planner call; global host telemetry and memory switches remain authoritative.
CPU samples, process RAM and machine RAM are not per-article costs.

The independent proof uses the sample, pinned-process profile, copy and cache
tools. Its rows are labelled as controlled work, not live planner measurements
or a planner speed gain. Missing or disabled observations retain their reasons,
never zero substitutes. RAM is displayed in decimal GB with two-decimal free
and available percentages. Free RAM and available RAM are different quantities;
the lowest observed available RAM is a sample, not an assured whole-run minimum.
See [host measurements](../reference/host-metrics.md#whole-task-typescript-samples)
for units and controls. No host benchmark determines planning completion.

## See also

- [Runner](../architecture/sources/feed-plan-runner.md)
- [Operator APIs](../architecture/sources/feed-operator-api.md)
- [Ledger reference](../reference/feed-planner-ledgers.md)
- [Gate commands](run-the-gates.md)
