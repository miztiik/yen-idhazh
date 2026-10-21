# Feed planning audit recording

**Last Updated**: 2026-10-21

Which observations can the isolated feed planner record without claiming that
an incomplete attempt is complete?

## Recording boundary

`services/feed-ingest-plan/src/metrics/metrics-recorder.ts` exports
`recordPlanningMetrics(result, inputs, registrations)`. Its inputs are the
actual `FeedPlanResult`, the `PlanInputs` used by that run, and the registered
`article-assessments` and `diversity` destinations. The runner owns integration;
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
counts stay null. These summaries have no completion phase or completion file
evidence and are not written to `source-runs`.

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

The result has status `assessment_diversity_recorded_audit_pending` and
`audited_complete: false`. Each receipt is an existing
`LedgerCompletionEvidence`: ledger name, row count, and file IDs, content
digests and file row counts. A zero-row assessment write returns an explicit
zero count and empty file list. No empty file is invented. A skipped write,
failed write or failed readback throws. Files already written before a later
failure remain incomplete-attempt artifacts; they do not establish completion.

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

## Design rationale

The existing source-run contract has only complete planning and publication
observations. Writing a pending observation under either name would change its
meaning. The recorder therefore delivers real assessment and diversity storage
without writing source completion or emitting a completion event.

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
