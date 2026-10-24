# Feed planning audit recording

**Last Updated**: 2026-10-24

Which observations can the isolated feed planner record without claiming that
an incomplete attempt is complete?

## Recording boundary

`services/feed-ingest-plan/src/metrics/metrics-recorder.ts` exports
`recordPlanningMetrics(result, inputs, registrations)`. Its inputs are the
actual `FeedPlanResult`, the `PlanInputs` used by that run, and the registered
`article-assessments`, `diversity` and `source-runs` destinations. The runner owns integration
and exposes planning completion separately from full audit completion.
When the third argument is omitted, it uses `inputs.registrations`.

The recorder first checks every configured concentration count and every
harvested candidate's exact screening timing, including rejected candidates.
Rejected screening records do not retain their timing. The recorder therefore
uses the same pure freshness calculation with the original candidate, the
exact first-sight evidence consumed by screening, the captured UTC instant,
the same future-time tolerance, and the resolved freshness override.
It compares this result with retained timing wherever the stage retained it.

Assessments store the measured timing basis and timestamp. `first_seen` remains
distinct from publication and fetch time, and a future publication within the
configured tolerance keeps its signed negative age. Ranking may floor that age
at zero for the recency bonus; the audit evidence does not. Unknown timing
remains unknown and carries no timestamp or age. Concentration rows store each
configured positive `top_k`; if `k` exceeds the available sources, the reading
uses all of them.

Expired entries can now stop before page download under
[the harvesting rule](feed-harvesting.md#design-rationale). Their harvest
assessment retains actual publication timing, age and cutoff, with extraction
`not_attempted` and null word, attribution and suitability evidence. Before
writing, the recorder recomputes that age with the captured run clock and the
same policy, checks the early terminal rejection, and refuses missing timing
or invented extraction measurements. Parsed counts still include these entries;
successful harvested counts do not.

## What is checked and written

Stage reconciliation checks the retained source snapshots, candidate identities,
ordered typed events, original run and attempt, stage outputs, and first terminal
losses. A candidate cannot be admitted and rejected at the same stage. Feed
decisions remain separate from article losses. Duplicate losses are a subset of
terminal losses, not an extra term in the input/output equation. Carrier
membership is retained separately from the unique selected primary source.
Current event revision `2026-10-24` requires UUIDv5 `event_id` and
UUIDv4 `correlation_id`, following [the identity contract](../contracts/identity.md).
Its sole declaration and validation are in the TypeScript Zod event schema;
no Python event model is required or imported. Shared ledger rows retain their
separate Python declarations.
The same run correlation is retained by every dependent row and summary.
Live progress is separate from decision evidence: it reports work immediately
and cannot establish audit completion. The workflow appends each actual audit
record before returning from its logger, not only after the run succeeds.

Every configured source receives an internal summary, including inactive,
failed, empty and zero-selection sources. Fetch and parse counts and durations
come from the actual feed outcomes. Operational success fractions retain their
recorded attempts and window; absent history stays null. Publication and lead
counts stay null. Internal summaries have no completion phase or file evidence.
Only after all five required ledgers pass native verification are complete source
records derived from them and written to `source-runs`.

Before writing, the recorder checks the reliability switch and floor against
the original configuration, matches each article's operational history to the
native source reading, and refuses conflicting supplied evidence. It replays
curation with the same screened articles, opportunity evidence and captured
clock, then compares carrier groups, source normalization, choices, score trace
and assessments. The separate reliability penalty therefore cannot be added
only to a final display or changed without changing the proved decision.

Assessments retain measured extraction, attribution, suitability checks and
the exact timing consumed by screening. No semantic evaluation is inferred from length, a byline
or source tier. Unperformed semantic verdicts stay `not_assessed` with null
values and evaluator versions. Portfolio scores come from actual stage
assessments and choice records. The returned evidence also retains the separate
base-quality measurements, penalty trace, availability, origin, allowance
witnesses and carrier groups; it does not derive a base score backwards from a
final marginal score.

Before writing, the recorder validates both complete proposed row batches,
their configuration and active registrations. It reads the named required
rejection, selection and dispatch files through the native TypeScript Parquet
reader and checks their writer identities, digests and actual rows. It writes
assessments and diversity through the shared public `persistLedger` API, then
reads each new file back through the same reader.

The result retains status `assessment_diversity_recorded_audit_pending` and
`audited_complete: false` for its existing callers. This is not a claim that a
successfully verified current raw attempt lacks completion evidence.
`planning_completion.status` is `complete` only after that exact attempt settles
through the existing completion selector. Each receipt is an existing
`LedgerCompletionEvidence`: ledger name, physical row count, file IDs, content
digests, file row counts and a logical attempt commitment.
A zero-row assessment write returns an explicit
zero count and empty file list. No empty file is invented. A skipped write,
failed write or failed readback throws. Files already written before a later
failure remain incomplete-attempt artifacts; they do not establish completion.

## Current raw source completion

The recorder verifies actual harvest, screening and curation rejection files
separately, then combines their counts and file commitments into one existing
`rejections` receipt. Together with actual assessment, diversity, selection and
dispatch receipts, these are the five required ledger commitments.

Each source record receives the configured source count, those commitments and
the existing `plan_complete` phase. The complete source batch is written last and
read back natively. The recorder then loads those exact raw files and all five
named ledger file sets through `readPlanningHistory` and
`selectCompleteAttempt`. A different attempt, mismatched identity, skipped write,
missing file or failed source write throws instead of returning completion.

The result includes `files.source_runs`, `source_records`, all five receipts and
`planning_completion`, containing the verified run, attempt, correlation, source
count and file commitments. This supplies the real producer input for the
publication observer; tests do not manufacture the completion marker.
The base `FeedPlanResult` is unchanged. API and CLI summaries expose this
specific complete attempt as planning completion, not publication completion.

Invalid timing, non-finite measurements and invalid concentration counts refuse
the whole batch before audit writes.

## Compaction-safe attempt proof

Source-run revision `2026-10-22T10:05` adds an optional `logical` commitment to
each receipt. Its protocol version is `2026-10-22`. It records the ledger-row
schema version, unique row count and SHA-256 of one canonical record set.
The original physical file receipts remain independently checked.

Each logical row must have the original ledger, decision-day partition, run,
attempt and correlation. Dispatch content may retain its earlier fetch date;
its selection still names the decision day. The business keys are the
production settlement keys in `backend/idhazh/ledger/keys.py`, held in step
by the existing cross-language contract case. Diversity identity includes
`unit`, so count and ratio readings cannot replace one another.

Identical rows under one business key count once. Different rows under that
key refuse completion and compaction; input order never chooses a winner.
Rows use the shared Python-compatible canonical row digest, including declared
integer and floating-point types. Serialized JSON key arrays sort lexically.
The commitment hashes a newline-terminated JSON header array containing
protocol version, ledger, row schema version, decision day, run, attempt and
correlation, followed by one newline-terminated `[serialized_key, row_digest]`
array per unique key. Storage file, unit and compactor identities are not
logical membership.

The selector recomputes that commitment over all verified rows of the exact
attempt. Missing, extra, changed, cross-attempt or conflicting rows cannot
complete it. Explicit zero-row sets also have a commitment. Raw, daily,
monthly and yearly files keep their separate envelope, identity, index and
ordered-content checks. The producer verifies all five writes before writing
the source completion batch last.

Older source revisions migrate with `logical: null`. They still prove
completion from original raw files. If those files are gone, compact-only old
history remains unverifiable. Migration never invents historical membership.

Rejection version `2026-10-22` permits the early harvest-stage age reason.
The reader verifies original `2026-10-20` physical bytes before changing only
the in-memory version stamp. An earlier logical receipt is recomputed with
its recorded rejection-row stamp, not today's stamp. This preserves original
evidence through packing; no old file or receipt is rewritten.

## Publication evidence reader

`readPublicationDay` in `metrics/publication-outcomes.ts` reads named native
published-ledger files and one named digest, with validated settled item-health
read projections supplied by the caller. A known-empty published day needs no
invented digest. Missing files, unassigned legacy runs and inconsistent day
membership remain explicit missing publication evidence.

`reconcilePublication` reports only articles confirmed by the published ledger.
It joins recorded URL, item, source and run identities, and takes lead membership
from the digest. Terminal health records with conflicting unsettled values are
refused. A recorded other run can exclude an unrelated missing item from a
known-zero run; a legacy item with no recorded owner cannot.

These readers alone do not seal an audit.
`completePublicationObservations` accepts only already-complete, settled source
records and actual reconciled publication evidence. It never turns the planning
recorder's pending internal source summaries into completion records.

## Durable publication observations

`recordPublicationMetrics(input)` in the same recorder accepts a named run,
correlation, UTC observation instant, the recorded configuration hash and metric
settings, a writer, ledger settings and active diversity/source-run registrations.
`publication_days` names each day's native published files, digest and validated
settled health projection. `planning_days` names its source-run files and all five
completion ledgers. Missing named days remain missing; an explicit empty raw-file
list means known-empty. Extra or repeated dates are refused before any write.

The recorder settles complete planning attempts through their original file
commitments before attribution. It reconstructs unique stage/candidate instances
from assessments, checks their terminal rejection records, selected primary
sources and per-source counts, and derives publication members from the native
published/digest join. Callers cannot replace those populations with current-item
lists. Optional `event_pairs` contains existing recorded similarity decisions.
Titles and outlet names come only from the matching named digest items, not
caller-supplied event-item projections.

The full proposed diversity batch and any source observations validate before
writes. Actual files are written through `persistLedger` and read back natively,
including writer identities, digests, row counts and ordered rows.
The result returns those files, readings, source observations, history coverage
and unavailable explanations. It computes full completion only after readback.

An original complete source attempt and a reconciled named run can produce
`publication_complete` source observations with actual publication/lead counts.
Each published URL and primary source must belong to that run's proven selected
articles; failed workers may leave a subset, but unrelated URLs, another carrier
or publications after zero selections cannot complete the observation.
The source writer attempt must equal the original proven attempt so its native
identity agrees with the source record. Both checks precede every observer write.
Existing planning commitments remain unchanged. Missing original proof without
a reproducible logical commitment cannot become new completion proof, but it does not erase
independently proven publication membership. A plan-complete record stays in
its original run-day partition even if its observation instant falls after
midnight. A later publication observation is filed under its actual UTC
observation day while `date` and `run_id` keep the original planning day and
run. The raw ledger writer's explicit `partition_date` selects that observation
partition without changing the row's original run date. The native reader
checks the partition against the record's observation phase; it never backdates
the observation.
Packed indexes reporting discarded files make publication history missing even
when the index does not name this exact day as lost.

## Full audit completion

`audit_complete` and `audited_complete: true` require all of these facts:
the exact original planning attempt is proven; its selected URL and primary
source agree with publication; observer attempt, correlation and configuration
hash agree with that attempt; every configured publication-history day is
available and closed before the observation day; every named planning-history
day is complete or explicitly empty; and the verified nonempty metric batch
has no unavailable reason except a measured empty denominator.
Missing event similarity evidence, publication, history or original proof keeps
`publication_metrics_recorded_audit_pending` and reports reasons. A measured
zero-selection attempt can complete without inventing articles or empty files.

`verifyPublicationMetrics` independently rereads the named planning, publication
and observer files and recomputes the readings and completion. It checks the
reported identity, coverage, unavailable reasons, receipts, observation-day
partition and actual native rows without rewriting files.
The runner's optional operator callback supplies these named observations;
no API request can select a path or declare its own completion.
The isolated workflow proves full completion on generated test publication,
separate from its actual live planning result. Neither invokes a production
publisher or claims that the live plan was published.

## Design rationale

The existing source-run contract has only complete planning and publication
observations. Writing a pending observation under either name would change its
meaning. The recorder therefore never converts pending internal summaries directly into
complete records. It first proves the five existing ledger commitments, then
writes and verifies source completion.

The [contract stamps](../contracts/schemas.md#what-holds-the-copy-in-step)
advance only for the payloads whose stored meaning changes. TypeScript readers
migrate named old rows through their recorded schemas; the Python source
contracts also migrate them without supplying missing timing or reliability.
Workflow verification uses these same current and legacy row contracts.
The optional report reader migrates old event envelopes and their nested
assessment fields before enforcing current event identity and policy checks.
Logical proof preserves the facts the raw-file receipt alone loses during
packing. Keeping both distinguishes record membership from physical file
integrity. Requiring complete named evidence permits truthful full audit
completion without treating generated test publication as production output.
The service stays default-off pending a separate owner approval for use.

## See also

- [../../reference/diversity-metrics.md](../../reference/diversity-metrics.md) -
  calculation inputs, denominators and unavailable readings.
- [../../../services/feed-ingest-plan/src/metrics/metrics-recorder.ts](../../../services/feed-ingest-plan/src/metrics/metrics-recorder.ts) -
  recorder implementation and exported result type.
- [../contracts/schemas.md](../contracts/schemas.md) - persisted contract rules.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - validation.
