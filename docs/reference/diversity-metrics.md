# Feed planning diversity readings

**Last Updated**: 2026-10-21

Which population and denominator does each available feed planning reading use?

## Identity and measurement basis

The source list is the retained configuration snapshot for this run, not today's
edited source file. Only its active sources enter the active-source denominator.
Source kind comes from each recorded source snapshot, not a later classification.
The declared source snapshot always requires a kind; an absent label is not
silently assigned a current label.

Before selection, each distinct `candidate_id` is one source-candidate instance.
The same article can appear through several carriers. A repeated occurrence of
one candidate record is refused, not counted again. These instance distributions
are necessary to measure source diversity before and after duplicate removal.
They are not unique selected-article or publication distributions.

Selected distributions use the globally unique selected article rows and their
primary sources. Other carriers never receive additional selected credit.
The recorded item count identifies the population size; source count is the
active-source snapshot size, including active sources with no items.

## Available per-run readings

- Active-source coverage divides distinct active sources with eligible instances
  by all active sources in the snapshot.
- Selection coverage divides distinct selected primary sources by distinct
  eligible sources.
- Effective source count is the exponential of the entropy of source shares.
  A uniform distribution across four sources reads four sources; a nonempty
  monopoly reads one source. An empty population reads zero sources.
- Top-source concentration sorts selected primary-source counts and divides the
  sum of the configured largest counts by the total selected articles. Supported
  persisted counts are 1, 5 and 10. Each ratio retains its integer numerator and
  denominator; ratios are never averaged.
- Selected-source Gini measures inequality over every active source, including
  sources with zero selected articles. It is the sum of all ordered pairwise
  absolute count differences divided by twice the source count and total item
  count. This is explicitly a selected reading, never a published reading.
- Source-kind distribution records both count and share for eligible instances
  and selected articles. Known snapshot kinds with no items retain zero counts.
  A zero-population share is unavailable, not a zero ratio.
- Stage readings retain the effective source count after the measured step.
  Lost diversity records the count before, the count after, and before minus
  after. A negative difference means diversity increased, not an invalid sample.

The input stage uses harvested instances. Freshness compares harvested instances
with those not rejected by the actual freshness rule, including candidates with
unknown timing that the policy accepts. It does not rename paywall, category or
substance losses as age losses. Deduplication compares actual screened eligible
instances with carrier representatives. Normalization compares those
representatives with the actual source-allowance survivors. Selection compares
those survivors with the selected unique articles. Each comparison uses its own
actual input; separate screening losses do not become duplicate losses.

## Missing evidence

Every proposed row validates against the existing `DiversityMetricRowSchema`.
Counts must be nonnegative safe integers; a ratio numerator cannot exceed its
denominator. Empty ratio denominators produce a null value with
`empty_denominator`. No result is NaN or infinity.

Publication and lead effective-source readings, published Gini and published
concentration stay unavailable with `missing_publication`. Historical overlaps
and novel-source contribution stay unavailable with `incomplete_history`;
event repetition stays unavailable with `missing_event_evidence`. Each
history-dependent row names its configured window. Unknown item counts and
history coverage remain null rather than fabricated zero observations.

No publication or lead membership exists at planning time, so no before/after
publication-stage loss is fabricated. The existing loss-row validator requires
real before and after values even for an unavailable row. The recorder reports
that unavailable measurement in its returned `unavailable` explanation instead
of writing a false row. Rolling metrics likewise remain explicitly unavailable
in the recorder result until a complete historical membership window is supplied.

## Publication and history observations

The publication observer reads only named published-ledger Parquet files and the
named day's digest. Published URL and item identities must agree with that digest.
The digest's run reference identifies the introducing run. Where an old digest
does not name a run, a matching settled successful terminal item-health record
may identify it. An ordinal alone never assigns an old item to the latest run.
Retry copies count once. Missing source kind remains unknown, not today's kind.
The digest's completion can be after midnight without changing its publication day.

History reads exactly the configured rolling days plus the larger of that window
and its configured overlap windows. The default seven-day measurement and
seven-day reference require fourteen named UTC days. A known-empty day
contributes zero articles. Missing and lost days reduce reported coverage and
make affected readings unavailable. Today's day remains partial until its UTC
end; an explicitly named earlier end can measure a completed window.

Source overlap unions all measured source sets and their corresponding prior-day
reference sets before calculating intersection and union. Novel-source shares
deduplicate article identities and use history before each publication day.
Neither calculation averages daily ratios or treats another run on the same
day as another historical novelty event.

Event readings use existing recorded pair decisions, never within-run cluster
numbers as global event identifiers. Every needed pair must carry sorted URL
keys, their recomputed pair identity, agreeing usable YES or NO verdicts, and
compatible complete recorded scorer and judge stamps. Missing, incompatible
or unclear decisions make the reading unavailable. The existing same-outlet
rule and unchanged ASCII headline-figure veto constrain positive decisions.
Every member of an event group must match every other member; pair chains alone
cannot merge events. Group names exist only inside this bounded calculation.
No matching policy, model call or new stored event identity is introduced.

## See also

- [../architecture/sources/feed-ingest-audit.md](../architecture/sources/feed-ingest-audit.md) -
  preflight refusal, durable files and the incomplete-attempt boundary.
- [../../packages/common-contracts/src/schemas/diversity.schema.ts](../../packages/common-contracts/src/schemas/diversity.schema.ts) -
  existing persisted fields and metric vocabulary.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - validation commands.
