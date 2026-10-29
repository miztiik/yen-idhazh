# Feed history used by the TypeScript planner

**Last Updated**: 2026-10-29

Which saved observations can change feed rest and measured reliability?
The isolated planner reads its current `feed-health-state` format and its
planner-owned `discovered-articles` ledger. The native Python `seen` ledger
remains separate and is not the planner's discovery source.
The global Python `feed-health` ledger and public health JSON are unchanged.

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
window setting. The request report uses closed calendar days instead.

Native represented membership is not limited to row-bearing dates. A daily
compact entry contributes its date only when it has rows. A nonempty month
or year contributes every calendar day in its declared cover, including
covered days with no feed row. January 31 can therefore be in the window
when January's only saved read was on January 1. This does not invent a
logical feed check or pad days outside named evidence. Known-empty daily
entries remain outside lifecycle/reliability membership.

Within a capture, index and Parquet caches prevent reopening one compact file
for each day it represents. A new selection capture reads current named
evidence and finalized in-memory facts, rather than reusing a saved parsed
batch's old health. The age clock remains separate from this feedback clock.

## Raw and compact copies

The current planner family reads late raw rows beside the selected compact
period. Identical representations count once. Distinct attempts retain their
actual request spend. This exception does not alter other families'
compact-first precedence or generic writer identities.

Logical feed-read settlement still prefers a productive outcome and then a
definitely later recorded check. Rest and robots skips do not enter the
reliability denominator. Captured rolling fractions are never summed.
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

Permanent retirement remains a curated source setting. HTTP 410 can
contribute to temporary rest but creates no second permanent-retirement
store. The planner does not modify the global Python retirement machinery.

Publication exclusions and publisher exposure use genuine external published
and item-health evidence. Selected articles are not publication evidence.
Unknown publisher identities and missing linkage stay explicit.

## Design rationale

File caches are bounded to one capture. Reusing them across selection instants
would hide a late old-date file or a UTC window change. The pre-fetch capture
governs rest; a later selection capture includes finished work and newly
finalized evidence. Both costs belong in the run's measured health-summary
time, without a persistent cache or benchmark gate.

## See also

- [Ledger reference](../../reference/feed-planner-ledgers.md)
- [Saved article keys](article-identity-history.md)
- [Feedback recording](../contracts/feed-ingest-feedback.md)
- [Curation](feed-curation.md)
- [Operator APIs](feed-operator-api.md)
