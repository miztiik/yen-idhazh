# Which history and source authority the TypeScript planner uses

**Last Updated**: 2026-10-24

The TypeScript planner reads native feed-health files for temporary rest and
measured reliability. Permanent retirement comes only from the existing source
configuration, `config/sources.json`, which a person curates. A source-run audit
record is not feed-health history.

## Permanent retirement is curated configuration

`feeds` supplies the current configured feed and audit population. Only its
active entries may be fetched. Draft entries and entries marked retired are
inactive and produce no DNS or feed request.

`retired` is validated separately: each entry must have `status: retired` and
`retired_on`. Its IDs must not conflict with the feed list. Historical retired
metadata does not require an active desk or source-kind lookup. The list is
retained in the effective input fingerprint and reconstruction, but is never
appended to live feeds, salience votes or feed-outcome measurements. An archived
list of sources does not create that many new observed feed reads.

TypeScript does not read, discover, register, write or retain receipts for
`feed-retirements`. It does not mutate source configuration. HTTP 410 is an
actual failed feed read and can contribute to temporary rest; it never creates
another permanent retirement store. Existing historical files and legacy Python
retirement capabilities are not removed by this TypeScript policy.

## Native health inputs

`inputs.feed_health_days` names UTC days, native compact indexes, and either raw
files or a raw index. The native reader validates schemas, file identities,
byte counts and canonical row digests. Yearly files take precedence over
monthly, daily and raw files. Shared file caches avoid opening one compact file
again for each represented day.

Health uses the newest 31 native represented days. Reliability uses
`collect.reliability_window_days`. Native `ledger_files.held_days` includes a raw
day holding files or a nonempty daily cover; a nonempty compact month or year
represents all its calendar days, including selected days that return no rows.
The selector does not replace this rule with a trailing calendar cutoff or a
filter keeping only row-bearing days.

The health input resolver uses the existing publication inventory's health
paths, the three native compact indexes and exact checked producer receipts.
Compacted precedence is resolved before staging, so absorbed raw paths in an
older inventory are not fetched as current raw evidence. No directory probe,
new date index, parallel history file or retirement input is needed.

Missing evidence remains unavailable. Current observations never turn a
missing earlier day into a known empty day. Named observations are not a claim
that every possible external producer has been inventoried.

## Recorded time and uncertain order

[Recorded instants](../contracts/recorded-instants.md) owns the field-specific
precision and uncertainty rule for native `checked_at` and keyed-request
`created_at`. It also owns preservation through raw, daily, monthly and yearly
storage. Neither file creation time nor a run identifier proves observation
chronology.

Duplicate feed/run accounts retain the native preference for a productive read.
Where accounts agree on productivity, only a definitely later saved check can
replace the held account by time. Packing does not add timing evidence.

Temporary rest uses `collect.availability_strikes_before_rest` for both the
failure threshold and rested-run count, matching the existing rule;
`collect.availability_rest_runs` remains unread. A productive read clears the
failure streak. Robots results and skips do not add failures. Only a result
proved for every admitted order is applied.

When tied or overlapping times leave the rest action unproven, the event records
an unknown lifecycle and unavailable counters rather than choosing a last row.
The feed is not automatically rested from that uncertain history; ordinary
source-status and robots checks still apply before it is fetched. Known
configured retirement is honored regardless of uncertain health order.

## Durable observations in one listener

One listener retains its own exact health-file receipts across requests,
including writes completed before a later stage fails. Paths resolve under the
actual configured output root, not the checkout. Readback validates relative
paths, escaping links, registered native paths, ledger/day/file identity and
content. Retention is bounded by the configured represented-day count.

There is no scan and no separately persisted listener history authority.
Receipts remain observations, not proof that unavailable external history was
empty. A process restart needs the existing native input inventory or exact
caller-supplied receipts.

## Measured reliability and its selection consumer

The current persisted feed read joins reliability after the health write.
Events carry the actual productive count, evidence-bearing attempts, fraction,
represented-day bounds, requested cover and native floor factor. Rest and
permission refusals stay outside that denominator. No evidence-bearing read
means unavailable reliability, not invented success.

The native floor factor feeds the separately recorded
[source-reliability penalty](feed-curation.md). It is not multiplied into
article quality. Source-run summaries receive the same measured fraction,
attempts and window even when a source supplies no eligible article.

Daily publication evidence reads only the captured UTC day's successful native
item-health rows and counts each URL once. Failed attempts do not count.
Unavailable coverage exposes an observed lower bound, not known zero.
Both item-health projections independently pin native support at
`2026-10-20`; planner or event stamps cannot silently widen it.
Current-attempt `SourceRunRecord.published_count` remains null until an actual
publication observer supplies its result.

The versioned feed event carries these facts. Native health receipts join the
exact verified workflow output files; no retirement output is created.

## Design rationale

Owner ruling, kumarsnaveen_microsoft, 2026-10-23: permanent TypeScript retirement
is the existing source registry's retired list and status, not another raw or
compact retirement ledger. This replaces the earlier draft dynamic-retirement
assumption. It authorizes no source-configuration mutation, new state file,
glob exception, publication-inventory purpose or publisher change.

Owner approval, kumarsnaveen_microsoft, 2026-10-23, "Bug 1 - A1": evolve the
existing check/request clock fields and their readers without adding a column
or using packaging as observation order. The narrow Python time-capture and
reader changes follow the [recorded-instant contract](../contracts/recorded-instants.md).

The selection consumer follows the separate
[2026-10-24 A1 approval](feed-curation.md#design-rationale). This history reader
adds no score weight, daily source ceiling or retirement authority.

## See also

- [Planning policies](feed-ingest-policies.md) - the isolated selection switch.
- [Recorded instants](../contracts/recorded-instants.md) - observation time and uncertainty.
