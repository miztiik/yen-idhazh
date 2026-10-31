# Feed history used by the TypeScript planner

**Last Updated**: 2026-10-31

Which saved observations can change feed rest and measured reliability?
The isolated planner reads current-format required `feed-health-state` fields and its
planner-owned `discovered-articles` ledger. The native Python `seen` ledger
remains separate and is not the planner's discovery source.
The global Python `feed-health` ledger and public health JSON remain separate
and keep their own formats.

## Named evidence and independent windows

Discovery reads the configured `discovered_articles.lookback_days` of prior
UTC days plus today. It retains the earliest known timestamp by canonical URL;
another feed or fetch cannot renew an article's age.

Service settings name bounded UTC days, compact indexes and either raw
indexes or explicit complete raw-file lists. The workflow resolves represented
health days from existing native indexes and publication inventory. It reads
only the named periods needed by the configured lookback, within the
`health_period_limit` control.
`discovered_files` names extra existing discovered-article Parquet files by
path; it does not create another ledger. The normal history read comes from
the configured UTC-day window, and this list is empty by default.
For example:

```json
{
  "discovered_files": [
    "state/raw/feed-ingest-plan/discovered-articles/2026/10/27/<uuid>.parquet"
  ]
}
```

The exact windows, units and skip rules are
[Table L](../../reference/feed-planner-ledgers.md#l-lookback-summaries).
Lifecycle and reliability share the validated health input, not each other's
window setting. Each calculation validates only its required columns under the
[field-read contract](../../reference/feed-planner-ledgers.md#field-based-health-history).
The request report uses closed calendar days instead. Those extra calendar
reads and historical counter calculations do not run during fetch/parse setup.

Native represented membership is not limited to row-bearing dates. A daily
compact entry contributes its date only when it has rows. A nonempty month
or year contributes every calendar day in its declared cover, including
covered days with no feed row. January 31 can therefore be in the window
when January's only saved read was on January 1. This does not invent a
logical feed check or pad days outside named evidence. Known-empty daily
entries remain outside lifecycle/reliability membership.

Within a capture, index and Parquet caches prevent reopening one compact file
for each day it represents.
Discovery history is also read once per collection. Later feed parses add
only their new sightings to current-process discovery memory; they do not
reopen the named discovery days or append the entire baseline again.

The workflow fetches current remote main once and
stages raw and compact input from that same revision without changing source
code or committing data. One boundary day is retained for known rolling-window
adjustments. A run reuses its captured calculations across HTTP stages and
applies actual current work at selection and finish. The age clock remains
separate from this feedback clock.
New parsed batches retain the existing `history_rows` field as an empty list;
historical rows need not satisfy the current full-row format to cross a stage.
Selection reads current field-based evidence instead of that saved list.

## Raw and compact copies

The current planner family reads late raw rows beside the selected compact
period. Identical representations count once. Distinct attempts retain their
actual request spend. This exception does not alter other families'
compact-first precedence or generic writer identities.

Logical feed-read settlement still prefers a productive outcome and then a
definitely later recorded check. Rest and robots skips do not enter the
reliability denominator. Captured rolling fractions are never summed.
Current producers save only `reliability.success_fraction` and
`reliability.production_factor` downward to three decimal places:
21 productive reads out of 22 save `0.954`. The factor applies the configured
floor to the original fraction before truncation, so a floor of `0.5005`
can save numeric `0.5`. JSON numbers do not retain trailing zeros.
Both values come from the original integer counts; article-pass rates,
selection scores and semantic similarity retain their own precision.
No general precision setting is introduced. Current health files use `2026-10-31`. Earlier health formats remain on disk
but refuse with a diagnostic. Current-format field gaps are partial evidence,
not a migration. Compaction preserves saved values rather than rounding them again.
Uncertain time order remains uncertain under
[the recorded-instant contract](../contracts/recorded-instants.md).

## Missing and refused evidence

Missing, known-empty, lost and corrupt evidence are different states. Typed
schema, native-format, index and filesystem refusals produce short body-free
gap diagnostics and incomplete coverage. Valid sibling files remain usable.
Unexpected programming errors propagate rather than becoming an empty day.

No logical feed evidence means unknown lifecycle and unavailable reliability.
Partial history does not become perfect health. Current work does not turn
an unverified earlier day into a measured zero.
An unrelated missing or changed column cannot remove a valid feed check or
article-admission count. Required-field gaps remain specific to their
calculation and endpoint. Invalid identity cannot be attributed and makes
that calculation incomplete for all configured feeds on the affected day.

Supported saved lifecycle and reliability calculations are read directly.
Only a missing or unusable calculation invokes bounded recovery of its own
required facts. Supported nulls and zeroes are retained. A missing unrelated
column or sibling file cannot erase a supported individual deadline.
Unknown availability alone does not block an active feed.
The [lifecycle contract](feed-availability.md) owns timed rest, recovery,
empty-feed reset and proven retirement.

## Curated retirement and external outcomes

Article technical admission is a separate derived fraction: admitted original
captures divided by admitted captures plus source-attributed article refusals.
Access, extraction, required fields and the minimum word count determine this
outcome. Age, content-policy, publication and quota losses do not change it.
Incomplete represented evidence or a zero denominator means unknown.

Each staged article fetch receipt settles its first known `source_outcome`
atomically in the existing operation journal. Its saved body and response stay
immutable. The parent feed receipt names its completed article captures, so
reconstruction reads only that root and those members, never the whole journal.
Reparse and reselection reuse the original capture outcome; a genuinely new
capture is separate work. Whole-plan work uses the same technical outcome rule.
Settlement uses its actual UTC day, independently of selection time.

Source outcomes survive process restart. Finalized-health ownership and write
deduplication remain process-local; this change adds no durable finalization
snapshot or general replay framework. The maintainer directed delivery without
that extension on 2026-10-27 UTC. Retrying health recording after a process
restart does not carry an exactly-once output guarantee.

Only active configured feeds may fetch. The separate retired-source list
does not add live reads. A changed endpoint key cannot inherit the former
URL's reliability, rest or request spend.

Catalog retirement remains a curated source setting. The planner can also
save a proven retirement decision in its existing health ledger when both
configured recovery gates hold. It does not create another retirement store
or modify the separate Python retirement machinery.

Publication exclusions and publisher exposure use genuine external published
and item-health evidence. Selected articles are not publication evidence.
Unknown publisher identities and missing linkage stay explicit.

## Design rationale

File caches and saved calculations belong to one captured run input. Other
runs can publish later without changing that run's decisions. Actual completed
work updates its own calculations once. Rolling-window changes use only known
entering and leaving contributions; unsupported changes stay incomplete and
do not relabel an old measurement's dates.

Request reporting is independent of planning evidence. A damaged report-only
day must not prevent a feed fetch, a document parse or current-run request
accounting. Selection and explicit summaries load request evidence when their
response needs it; they share verified file reads with planning evidence
without making the report an execution prerequisite.

## See also

- [Ledger reference](../../reference/feed-planner-ledgers.md)
- [Feedback recording](../contracts/feed-ingest-feedback.md)
- [Curation](feed-curation.md)
- [Operator APIs](feed-operator-api.md)
