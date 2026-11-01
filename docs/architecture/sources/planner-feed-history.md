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

Service settings name bounded UTC days and optional complete raw-file lists.
Before the first fetch, the planner resolves represented health days from the
site publisher's `frontend/public/publication.json` and the gardener's existing
compact-period indexes. It reads only the named periods needed by the configured
lookback, within `health_period_limit`. These files choose represented dates;
native planner membership uses the exact local UTC-day directories and compact
Parquet paths, not raw-day indexes or Git history.
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
The request report uses closed calendar days instead. Its additional files are
loaded into the same execution input before fetching, but its totals are
calculated only when a response needs them. Missing report-only evidence never
prevents feed or article work.

Native represented membership is not limited to row-bearing dates. A daily
compact entry contributes its date only when it has rows. A nonempty month
or year contributes every calendar day in its declared cover, including
covered days with no feed row. January 31 can therefore be in the window
when January's only saved read was on January 1. This does not invent a
logical feed check or pad days outside named evidence. Known-empty daily
entries remain outside lifecycle/reliability membership.

One execution loads and validates health, discovery, publication exclusions,
settled failures and genuine publisher linkage before its first source request.
It retains those records in its live document state. Directory membership and
native file reads are shared within that capture. Later stages use the retained
records; edits, additions and removals on disk cannot change their decisions.
Current sightings and completed work remain separate from the saved baseline.
Another execution loads its own input, including any newly available files.

Workflow preparation finishes its existing bounded raw/compact acquisition
before starting the listener. Application startup and history computation invoke
no Git. The supplied input directory is the file authority; readers do not prove
an arbitrary commit or reject a regular file because it is untracked. The current
UTC day and the next day are captured for supported boundary adjustments. A run
applies actual current work at selection and finish without reopening history.
The age clock remains separate from this feedback clock.
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

The [raw-day membership contract](../../reference/feed-planner-ledgers.md#raw-day-membership)
defines empty membership and missing references. A live capture retains its
missing-file diagnostics; adding a file later cannot heal the running execution.

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

Each live article capture settles its first known source outcome in memory.
Parsing consumes its held raw body; later selection uses the completed live
metadata rather than reopening a document or a request journal. A genuinely new
capture is separate work. Whole-plan work uses the same technical outcome rule.
Settlement uses its actual UTC day, independently of selection time.

A process restart starts a new execution. There is no journal, replay or saved
input set. Finalized-health ownership and write deduplication remain
process-local; retrying after a restart has no exactly-once output guarantee.

Only active configured feeds may fetch. The separate retired-source list
does not add live reads. A changed endpoint key cannot inherit the former
URL's reliability, rest or request spend.

Catalog retirement remains a curated source setting. The planner can also
save a proven retirement decision in its existing health ledger when both
configured recovery gates hold. It does not create another retirement store
or modify the separate Python retirement machinery.

Publication exclusions and publisher exposure use genuine external published
and item-health evidence. Selected articles are not publication evidence.
The required selected-metadata linkage is captured alongside those records,
before fetching. Unknown publisher identities and missing linkage stay explicit.

## Design rationale

Retaining validated records gives every stage the same input without copying
files or adding another saved catalog. Other runs can publish later without
changing that input. Actual completed work updates its own calculations once.
Rolling-window changes use only known entering and leaving contributions;
unsupported changes stay incomplete and do not relabel an old measurement's
dates. Live work pins its capture. Capacity expiry removes that execution's
retained batch references with its input, so an old reference fails explicitly
rather than reopening historical files.

Request reporting is independent of planning decisions. A damaged report-only
day must not prevent a feed fetch, a document parse or current-run request
accounting. Selection and explicit summaries calculate from the captured
request fields and actual current work, without new historical reads.

## See also

- [Ledger reference](../../reference/feed-planner-ledgers.md)
- [Feedback recording](../contracts/feed-ingest-feedback.md)
- [Curation](feed-curation.md)
- [Operator APIs](feed-operator-api.md)
