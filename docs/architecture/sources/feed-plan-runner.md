# Running the isolated feed planner

**Last Updated**: 2026-10-21

How does an operator request one feed plan through the same API and CLI?
This tool runs during development or a build. The static site never depends
on its HTTP listener. Production digest planning and workers are unchanged.

## Entry points and controls

From `services/feed-ingest-plan`, run `bun src/index.ts --serve` for the operator
API or `bun src/index.ts --cli` for an awaited one-shot run. Both use the
authored `config/feed-ingest-plan-service.json`. Its default-off `enabled`
flag names its removal condition beside the declaration: required audit
writes and complete-attempt verification must be integrated and approved.
Disabled requests fail before harvesting.

The listener defaults to loopback `127.0.0.1`, port `8787`, a 30-second idle
timeout and a 16384-byte request limit. These are validated service settings,
not production platform limits. Keep the listener local unless the operator
provides a protected development environment; this tool adds no authentication.
The request-size limit also applies to a chunked body.

`GET /api/2026-10-20/health` reports listener availability, planner enablement
and whether audited completion is available. It does not start a run.
`POST /api/2026-10-20/plan` accepts only these controls:

Table A

| Id | Control | Meaning |
| --- | --- | --- |
| A1 | `freshness_hours` | Optional positive finite number. Replaces each effective vertical age cutoff, not its ranking half-life. |
| A2 | `article_limit` | Optional positive integer. Replaces the configured run cap; omission uses that cap. A configured null means no extra cap. |
| A3 | `shards` | Optional positive integer within configured partition bounds. Omission uses the configured default. Strategy `none` requires omission or one and resolves to one worker. |
| A4 | `partition_strategy` | Optional `bin-pack`, `round-robin` or `none`; omission uses the configured strategy. |

API numbers must be JSON numbers, not strings or null. The CLI uses the same
field names with hyphens, for example
`--cli --freshness-hours 18 --article-limit 20 --shards 2`.
Omitted or blank CLI controls use configuration. Invalid supplied numbers,
fractions for integer controls, unknown fields and repeated CLI controls
fail by field name. There is no date argument.

## Real composition and identity

`src/index.ts` and HTTP routes only route requests. `runFeedPlan` validates
controls and writer context before any fetch, then composes real harvesting,
screening, curation, native selection readback, partitioning and persistence.
It uses Row #10's public selection reader and partitioner, not a second
implementation. The native reader verifies the actual written selection
files against the current curation and original harvested content.
The API and awaited CLI then pass that real stage result to
`recordPlanningMetrics`. Its existing recorder verifies named stage files and
writes and reads back actual assessment and diversity ledgers. It never runs
as an optional reporter.

The run captures one UTC instant. Harvesting, screening and curation use
that same instant and the same freshness override, so live runs do not cross
midnight or disagree on policy between stages. Original fetched records are
not rewritten to fit a later decision. The run ID combines the captured UTC
day with a numeric random UUID; tests and coordinated callers can supply
the numeric run identity explicitly. Independent requests at the same instant
therefore do not share a run ID. The configured attempt and checkout commit
identify the writer. Writer shard zero is provenance, not worker assignment.

The loader reads only named files in service settings: planning, taxonomy,
sources, extraction and ledger registrations. Output goes below the configured
state root. Paths crossing a process boundary remain relative and
POSIX-separated. The four API controls never choose a file path or fetch URL.
The effective article cap is resolved before harvesting, and its actual
configuration fingerprint is carried by candidates and selections.

Publisher, parent-domain, operational and primary-document evidence is
explicit and nullable. Nothing derives a masthead from a feed title, a story
cluster from a feed category, or a quality verdict from article length or
byline. Without a supplied work estimate, extracted word count is the measured
work proxy, in words, not a time estimate. Curation receives the actual
configured source snapshots. The returned harvest outcomes include inactive,
failed and empty sources.
Retired sources may retain an unregistered historical vertical or kind. They
still produce `SOURCE_INACTIVE` without a fetch or a source-policy lookup.
Their event envelope carries the explicit global run-context policy, including
any request override, not a claim that a historical source policy was applied.
Active and draft source references are still validated before harvesting.

## First sight and audit boundary

`readSeenEvidence` uses the existing screening `SeenRow` declaration and its
independent recorded wire version `2026-08-31`. Named `seen_files` supply actual
observations, never absence proof. Observations for the same URL key retain
the earliest actual first-sight instant and run across days and retries.
Future first-sight instants and unreadable named observation files fail.

For new first sight, `inputs.seen_days` names each UTC day and its native
`readLedgerDay` inputs: `indexes` with optional `yearly`, `monthly`, `daily`
relative paths, and either `raw_index` or an explicit complete `raw_files`
list. An explicit empty `raw_files` list means a known empty day; an omitted
day or inventory does not. Dates must be distinct, ascending and inside the
configured window. `collect.seen_window_days` in `config/idhazh.json` supplies
the lookback: the current UTC day plus 90 preceding days means 91 required
days at the current setting, with both bounds included, as in
[existing freshness rules](freshness.md).

Every required day must resolve to actual rows or known empty, with no lost,
missing, expired or set-aside evidence. Only then can an absent URL key get a
new existing-format SeenRow at the captured run clock and identity. The native
writer must persist it before screening; skipped or failed writes fail the
run. Missing history preserves known observations but cannot create new first
sight. Undated candidates without settled evidence retain unknown timing and
no invented recency bonus. This proves absence within the configured retention
window, never global absence.

One Hono app serializes planning requests and retains only its actual durable
seen-file receipts as additional per-day observations, even if a later stage
fails. It validates receipts, rejects a backwards run clock and prunes receipts
outside the configured window. A fresh process needs refreshed caller-provided
inventories; this is not a repository scan or cross-process locking mechanism.
After successful stage composition, that listener remembers which named day inputs it
accepted. As UTC advances, it omits unchanged accepted inputs older than the
new window without changing the authored inventory. New or changed invalid
inputs still fail, as do out-of-window inputs in a direct run. Newly required
days stay missing until the caller supplies their evidence; planning continues
with available observations but cannot create new first sight without the
complete window.
These first-sight writes remain durable if subsequent required audit recording
refuses their timing. The current assessment contract cannot retain first-sight
timing, so an API or CLI run that consumes it fails explicitly after stage
persistence, before either audit ledger is written. The listener still keeps
the actual receipt; a retry cannot reset first sight to bypass that refusal.
The returned evidence and API/CLI `first_sight` summary identify the window,
per-day status, own receipts, created count and limited absence proof.

The runner emits existing typed `FeedIngestEvent` envelopes as JSONL on
stderr. Event IDs follow run, attempt and sequence; elapsed and step durations
are measured in milliseconds. Full article text is not put in decision logs.
Feed outcomes, actual harvest/screening/curation decisions, marginal choices
from curation's trace and stage counts retain their existing typed contracts.
The early-stage mapper never fills an unavailable publisher or timing cell.
If extraction reported success but a rejected record retained no word count,
that assessment cannot claim the schema's counted success; the exact
observation remains available in transient harvest evidence.
Harvest counts include feed refusals and article decisions as distinct input
units, and its source count retains the separate configured-feed denominator.
The returned transient evidence also includes complete harvest observations,
screening timing, source normalization, blocked/relaxed selection steps,
file identities and worker assignments. It is the audit recorder's input,
not a recomputed explanation of the final portfolio.

`runFeedPlan` returns the base `FeedPlanResult`, with
`dispatches_persisted_audit_pending`, never audited completion. This base is
also the recorder's input, so its type does not depend on its own audit output.
The API and awaited CLI require `recordPlanningMetrics` to finish before
returning a summary. Their `RecordedFeedPlanResult` adds `metrics`, containing
actual assessment, diversity and source-run files, validated completion
receipts, source records, measured evidence and remaining unavailable reasons.
After checking all five required ledger receipts, the recorder writes existing
`SourceRunRecord` rows and reads the new raw files through
`readPlanningHistory` and `selectCompleteAttempt`. Only the exact current run,
attempt and correlation identity can supply `planning_completion`.
`summarizePlan` retains the recorder result under `metrics` and exposes its
actual `source_records` and `planning_completion` at the top level. `files`
keeps the original stage files and adds the actual `source_runs` write result.

For a proven representable current run, `planning_complete` is true and
`status` is `planning_complete_audit_pending`. The API returns HTTP 200 and the
standalone CLI exits with code 0: the requested planning work succeeded.
`planning_completion` names its verified date, run, attempt, correlation,
source count and five ledger commitments. The recorder's narrower
`metrics.status` and `audit.status` remain
`assessment_diversity_recorded_audit_pending`; `audited_complete` stays false.
This result does not certify publication, rolling history or a full audit.
The workflow's separate full-audit gate can still exit with code 2.
`main(args, {inputs, runtime, output})` returns the same summary to an awaited
caller; only the standalone process sets its exit code. A base stage result
without recorder proof remains `planning_complete: false` with its original
pending status, never a fabricated completion.
Invalid requests exit with code 1; disabled HTTP requests return 503.
Persistence errors fail rather than returning a complete-looking result.
Already durable immutable files may remain after a later failure.
The public `loadPlanInputs` result also exposes actual `seen`, `assessments`
and `diversity` ledger registrations for downstream native writes.
Its `registrations.source_runs` exposes the existing `source-runs` registration
from the named ledger config. Loading requires exactly one such ledger, active
under `feed-ingest-plan`, with `raw-and-compact` grain and the registered
`["feed-ingest-plan", "source-runs"]` prefix. Invalid registration fails loading;
exposing it does not write a source record or change audit-pending status.

The recorder preflights the whole attempt before any audit write. First-sight
timing, signed negative publication ages and unsupported `top_k` concentration
counts fail explicitly, as do missing or invalid native input files. No
observation is skipped or rewritten to fit the persisted assessment contract.
The API returns an error with HTTP 500, and the standalone CLI exits with
code 1 without printing a summary. Required native write or readback failures
also throw; earlier durable files may remain but no completion is reported.
Source-run persistence or native completion verification failures also prevent
any successful summary. No flag or success-shaped fallback bypasses the
required recorder or its exact-attempt selector.

Known integration limits remain explicit. Packed files cannot prove the
original completion-file ordered hashes after raw deletion with the current
contract. Assessment payloads cannot preserve a first-sight clock or signed
future age, although transient timing retains both. Audit top-count settings
allow values the persisted metric vocabulary cannot represent. Independently
harvested older content with a later freshness override or decision day still
meets the documented dispatch date/policy conflict; the live runner avoids
that mismatch by consistent inputs, never mutation. These require approved
contract decisions, not fabricated evidence.

## Dependencies and verification

Hono provides API routing and bounded request-body handling. Hono 4.13.13
occupies 1294526 installed package-file bytes on Windows x64 with Bun 1.3.13.
This is not compressed download size, process memory or runner time.
It adds no published browser bytes. Bun pins it and the existing runtime
dependencies in the service lockfile. Arrow and Parquet reuse the adopted
native writer/reader dependencies; no Python source, packages or execution
are required by the runner.

Use `bun run check` and the named `test/plan-cli.test.ts`,
`test/plan-api.test.ts` and `test/plan-engine.test.ts` with Bun. Tests replay
the existing bounded harvest recordings, compose actual stages and write/read
actual Parquet. Recorded replay refuses an unrecorded request.
This checks storage compatibility against recorded contracts, not execution
of the Python reader, live feed availability or hosted-runner throughput.
The small recorded article fixture is shorter than the default article
threshold. Its harness uses a validated 100-word article threshold, retaining
the original recorded HTML and real extractor. It does not replace extraction
or change the shipped 180-word setting.
The real API/awaited-CLI parity test reads assessment, diversity and source
output through the native reader, compares actual hashes and rows, and runs
the real history reader and attempt selector against every named output file.
Entry tests also prove whole-audit refusal for unsupported timing or counts
and no successful output on a required source write failure.

## Design rationale

One shared typed request prevents API and CLI drift. One captured clock and
override keep each live stage's day and policy truthful. Real native readback
before dispatch makes written selections, not an in-memory substitute, the
partitioner's input. An explicit incomplete result prevents durable dispatches
from masquerading as a fully audited plan while the audit contract is unsettled.

## See also

- [Harvesting](feed-harvesting.md)
- [Screening](feed-screening.md)
- [Curation](feed-curation.md)
- [Partitioning](feed-partitioning.md)
- [Local gates](../../how-to/run-the-gates.md)
