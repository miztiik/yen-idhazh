# Running the isolated feed planner

**Last Updated**: 2026-10-25

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

[Separate fetch and parse requests](feed-operator-api.md) expose those real
stages with durable identity-checked receipts and request replay. `/plan`
also accepts an optional `Idempotency-Key` header; the linked page defines
restart, conflict and retention behavior.

Table A

| Id | Control | Meaning |
| --- | --- | --- |
| A1 | `freshness_hours` | Optional positive finite number. Replaces each effective vertical age cutoff, not its ranking half-life. |
| A2 | `article_limit` | Optional positive integer. Replaces the configured run cap; omission uses the configured 100 articles. A configured null means no extra cap. |
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

The [native health-history reader](planner-feed-history.md) supplies rest,
source reliability and daily published evidence. Permanent retirement comes
from the existing source registry, not another ledger. Inventory and time-order
uncertainty remain explicit; none of this evidence changes portfolio scoring or
quotas.

The loader reads only named files in service settings: planning, taxonomy,
sources, extraction and ledger registrations. Output goes below the configured
state root. Paths crossing a process boundary remain relative and
POSIX-separated. The four API controls never choose a file path or fetch URL.
The effective article cap is resolved before harvesting, and its actual
configuration fingerprint is carried by candidates and selections.
The article limit controls final selection only; it never limits feed entries
or page requests. [Known expired entries](feed-harvesting.md#design-rationale)
stop before page download using the same captured clock and freshness override.

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
the lookback. Its current value is 90, meaning 90 preceding UTC days plus the
current day, with both bounds included, as in
[existing freshness rules](freshness.md).

Published history uses its native `PublishedRow` stamp,
`2026-09-12T18:40`, not the planner package version. Its bounded reader checks
the file digest and projects the fields it uses, so compatible older rows keep
working without being rewritten or assigned a new stamp.

The reader folds the actual rows from named history inputs and keeps the
earliest recorded first sight for each URL. First-sight candidates come from
valid feed links after blocked-marker filtering and before article-page fetch.
An absent URL gets a new existing-format SeenRow at the captured run clock and
identity even if later rejected as published, settled, stale, or unable to
fetch, and even if another required day is missing or lost. Blocked-marker
links do not get a sighting. The native writer must persist it before
screening; skipped or failed writes fail the run. Missing days remain missing
in the per-day report; they are not relabelled empty and do not support an
absence claim. `absence_proof` is available only when every required day has
usable evidence. Unreadable named files and corrupt evidence still fail the
run. Undated candidates without settled or current first-sight evidence retain
unknown timing and no invented recency bonus.

Owner ruling (kumarsnaveen, 2026-10-22): match the Python first-sight behavior
without inventing older evidence. A missing day cannot prevent recording that
an eligible URL was actually observed now, but it must stay visible as missing
and must not be described as proof that the URL was absent from the full
window. Keep the existing configured lookback, earliest-known timestamp, and
durable write-before-screening behavior.

One Hono app serializes planning requests and retains only its actual durable
seen-file receipts as additional per-day observations, even if a later stage
fails. Receipt paths are relative to the configured output root, where the
files were written; they are not rebuilt relative to the checkout. It validates
receipts, rejects a backwards run clock and prunes receipts outside the
configured window. A fresh process needs refreshed caller-provided inventories;
this is not a repository scan or cross-process locking mechanism.
After successful stage composition, that listener remembers which named day inputs it
accepted. As UTC advances, it omits unchanged accepted inputs older than the
new window without changing the authored inventory. New or changed invalid
inputs still fail, as do out-of-window inputs in a direct run. Newly required
days stay missing until the caller supplies their evidence; planning continues
with available observations and can record current first sight without claiming
full-window absence.
These first-sight writes remain durable if subsequent required audit recording
refuses their timing. The assessment contract retains actual first-sight timing.
Invalid audit evidence can still refuse a run after stage persistence.
The listener keeps the actual receipt; a retry cannot reset first sight
to bypass that refusal.
The returned evidence and API/CLI `first_sight` summary identify the window,
per-day status, own receipts, created count and limited absence proof.

The runner emits live JSONL progress before and after history reads, each
feed, each article, each stage and required audit recording. It does not wait
for a whole harvest batch before reporting its activity. The live envelope uses
the existing pipeline logger's `timestamp`, `level`, `message`, `eventId`,
`eventType`, `correlationId` and `durationMs` fields.
UUIDv5 event identities and one UUIDv4 run correlation follow
[the shared identity contract](../contracts/identity.md).
Typed `FeedIngestEvent` evidence is included under `audit` in its live log;
the workflow also appends the exact record to its audit JSONL file immediately.
Elapsed and operation durations are measured in milliseconds. Live
`durationMs` is null without an explicit operation measurement, never the gap
since another event. Audit stage elapsed time is exposed as `stepElapsedMs`.
The [failure diagnostic contract](feed-failure-diagnostics.md) defines the
shared feed/article evidence, operation clocks and attributable warnings.
Full article text is not put in decision logs.
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
`assessment_diversity_recorded_audit_pending`; `audited_complete` stays false when no complete publication observation is supplied.
This result does not certify publication, rolling history or a full audit.
The workflow separately requires full-audit test evidence as well as live
planning proof; it never calls the live plan published.
`main(args, {inputs, runtime, output})` returns the same summary to an awaited
caller; only the standalone process sets its exit code. A base stage result
without recorder proof remains `planning_complete: false` with its original
pending status, never a fabricated completion.
Invalid requests exit with code 1; disabled HTTP requests return 503.
Persistence errors fail rather than returning a complete-looking result.
Already durable immutable files may remain after a later failure.
The public `loadPlanInputs` result also exposes actual `seen`, `assessments`
and `diversity` ledger registrations for downstream native writes.
Its `registrations.source_runs` exposes the `feed-runs` registration
from the named ledger config. Loading requires exactly one such ledger, active
under `feed-ingest-plan`, with `raw-and-compact` grain and the registered
`["feed-ingest-plan", "feed-runs"]` prefix. Invalid registration fails loading;
exposing it does not write a source record or change audit-pending status.

The recorder preflights the whole attempt before any audit write. It preserves
first-sight timing, signed negative publication ages and every configured
positive `top_k`. Missing or invalid native input files still fail explicitly.
The API returns an error with HTTP 500, and the standalone CLI exits with code 1
without printing a summary. Required native write or readback failures also
throw; earlier durable files may remain but no completion is reported.
Source-run persistence or native completion verification failures also prevent
any successful summary. No flag or success-shaped fallback bypasses the
required recorder or its exact-attempt selector.

New source receipts contain deterministic logical membership proof that
survives daily, monthly and yearly compaction. Old raw-only receipts still need
their original files; migration cannot fabricate lost proof.
See [audit recording](feed-ingest-audit.md#compaction-safe-attempt-proof).
Older harvested content can retain its
original date and policy in a dispatch while selection keeps its later decision
date and effective policy. The shared article, source, URL and label identities
remain required. A publication observation is written under its actual UTC
observation day while the source row keeps its original run date and ID.

## Optional publication observation

An embedding operator can install `runtime.observe_publication(plan, metrics)`.
After required planning recording, `recordFeedPlan` awaits this callback for a
`PublicationRecorderInput`, checks run, correlation and attempt, and invokes the
real publication recorder. API and awaited CLI share this path; request fields
and standalone CLI controls do not add paths or publication claims.
Without the callback, health reports full completion unavailable and planning
still returns its proven pending result. With it, health reports capability,
not completion of any particular run.

Only complete publication, closed history and measured metric evidence can
produce summary `status: audit_complete`, `audited_complete: true` and
`audit.status: complete`. The summary retains the real observer result under
`publication`. Missing evidence remains pending with its reasons.
The criteria and independent native verifier are owned by
[audit recording](feed-ingest-audit.md#full-audit-completion).
Installing a callback does not enable the committed default-off service or
invoke production publishing.

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
Entry tests also prove native readback of first-sight timing, signed ages,
arbitrary positive concentration counts and later source observations, plus no
successful output on a required source write failure.

## Design rationale

One shared typed request prevents API and CLI drift. One captured clock and
override keep each live stage's day and policy truthful. Real native readback
before dispatch makes written selections, not an in-memory substitute, the
partitioner's input. An explicit incomplete result prevents durable dispatches
from masquerading as a fully audited plan while the audit contract is unsettled.

## See also

- [Harvesting](feed-harvesting.md)
- [Native health inputs](feed-history-inputs.md)
- [Screening](feed-screening.md)
- [Curation](feed-curation.md)
- [Partitioning](feed-partitioning.md)
- [Local gates](../../how-to/run-the-gates.md)
