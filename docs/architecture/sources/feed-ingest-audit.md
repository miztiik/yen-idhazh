# Feed planning audit recording

**Last Updated**: 2026-10-21

Which observations can the isolated feed planner record without claiming that
an incomplete attempt is complete?

## Recording boundary

`services/feed-ingest-plan/src/metrics/metrics-recorder.ts` exports
`recordPlanningMetrics(result, inputs, registrations)`. Its inputs are the
actual `FeedPlanResult`, the `PlanInputs` used by that run, and the registered
`article-assessments`, `diversity` and `source-runs` destinations. The runner owns integration;
the recorder does not change the API or CLI's completion status.
When the third argument is omitted, it uses `inputs.registrations`.

The recorder first checks every configured concentration count and every
harvested candidate's exact screening timing, including rejected candidates.
Rejected screening records do not retain their timing. The recorder therefore
uses the same pure freshness calculation with the original candidate, the
exact first-sight evidence consumed by screening, the captured UTC instant,
the same future-time tolerance, and the resolved freshness override.
It compares this result with retained timing wherever the stage retained it.

The existing assessment contract cannot represent a `first_seen` clock or a
signed negative publication age. The diversity contract admits only top-source
counts of 1, 5 and 10. Any such unrepresentable observation or configured count
refuses the whole request before either audit ledger is written. The error names
the field, candidate where applicable, and the measurement that would be lost.
Originally unknown timing remains unknown; it is not a fetch time or proof that
the article was first seen now.

## What is checked and written

Stage reconciliation checks the retained source snapshots, candidate identities,
ordered typed events, original run and attempt, stage outputs, and first terminal
losses. A candidate cannot be admitted and rejected at the same stage. Feed
decisions remain separate from article losses. Duplicate losses are a subset of
terminal losses, not an extra term in the input/output equation. Carrier
membership is retained separately from the unique selected primary source.

Every configured source receives an internal summary, including inactive,
failed, empty and zero-selection sources. Fetch and parse counts and durations
come from the actual feed outcomes. Operational success fractions retain their
recorded attempts and window; absent history stays null. Publication and lead
counts stay null. Internal summaries have no completion phase or file evidence.
Only after all five required ledgers pass native verification are complete source
records derived from them and written to `source-runs`.

Assessments retain measured extraction, attribution, suitability checks and
representable timing. No semantic evaluation is inferred from length, a byline
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
`LedgerCompletionEvidence`: ledger name, row count, and file IDs, content
digests and file row counts. A zero-row assessment write returns an explicit
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
The base `FeedPlanResult` is unchanged. The runner and workflow owners decide
when their caller statuses can expose this specific complete attempt.

Unsupported timing or concentration values still refuse the whole batch before
audit writes. New raw-file verification does not restore original membership
after historical packing. Neither limitation cancels valid current raw proof.

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

These readers and the bounded history arithmetic do not seal an audit.
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
and unavailable explanations with `publication_metrics_recorded_audit_pending`
and `audited_complete: false`.

An original complete source attempt and a reconciled named run can produce
`publication_complete` source observations with actual publication/lead counts.
Each published URL and primary source must belong to that run's proven selected
articles; failed workers may leave a subset, but unrelated URLs, another carrier
or publications after zero selections cannot complete the observation.
The source writer attempt must equal the original proven attempt so its native
identity agrees with the source record. Both checks precede every observer write.
Existing planning file commitments remain unchanged. Missing or packed original
planning proof cannot become new completion proof, but it does not erase
independently proven publication membership. A following-day observation cannot
fit the source contract's same-day `observed_at`: its source write stays explicitly
unavailable instead of backdating. Publication metrics can still be recorded.
Packed indexes reporting discarded files make publication history missing even
when the index does not name this exact day as lost.

## Design rationale

The existing source-run contract has only complete planning and publication
observations. Writing a pending observation under either name would change its
meaning. The recorder therefore never converts pending internal summaries directly into
complete records. It first proves the five existing ledger commitments, then
writes and verifies current raw source completion. No completion event or caller
status is changed by this recorder.

Full audit completion remains open. It requires decisions on exact first-sight
and signed-age representation, the mismatch between authored top-source counts
and their persisted vocabulary, and verification of original completion evidence
after raw files have been packed. This increment neither changes those contracts
nor declares a replacement success condition.

## See also

- [../../reference/diversity-metrics.md](../../reference/diversity-metrics.md) -
  calculation inputs, denominators and unavailable readings.
- [../../../services/feed-ingest-plan/src/metrics/metrics-recorder.ts](../../../services/feed-ingest-plan/src/metrics/metrics-recorder.ts) -
  recorder implementation and exported result type.
- [../contracts/schemas.md](../contracts/schemas.md) - persisted contract rules.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - validation.
