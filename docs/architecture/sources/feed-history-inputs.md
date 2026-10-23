# Discovering native feed history

**Last Updated**: 2026-10-23

How does the TypeScript planner find the same health and retirement files
that Python reads, without copying their rows into another state file?

## One history, named inputs

The recorded history stays in `state/raw/feed-health/`,
`state/raw/feed-retirements/` and their `state/compact/` counterparts.
Both readers use the original native rows, versions and writer identities.
There is no separate current-history snapshot.

`resolveFeedInventory` reads the existing `PublicationInventory` document,
`frontend/public/publication.json`, and the three existing `CompactIndex`
documents for each ledger. The Python plan stage records exact health file
paths in that publication inventory after the native ledger writer returns.
The TypeScript reader uses its `root: state` entries as file names, not as
copies of health or retirement records. The small TypeScript publication
projections are checked against the Python declarations in the existing
contract binding test.

A caller may also supply exact native `PublicationReceipt` documents and
their expected execution identities. Receipt paths must be relative native
UUID file paths. Conflicting hashes or another invocation's identity refuse
discovery. `verifyFeedReceiptWrites` then checks the actual whole-file hashes,
native Parquet schema, content digest, UTC partition and executed identities
against the same captured bytes before those files can be used. The receipt's
whole-file hash is not the row-content hash in the Parquet footer.

Inputs are one named publication inventory, six named compact indexes and
the caller's exact receipt list. No directory or Git history walk discovers
additional days. The result contains exact native file names and ordinary
named-day reader inputs; it writes no inventory, receipt or history file.

## Native selection and precedence

For each day, the yearly index wins over the monthly index, which wins over
the daily index. Raw files are selected only when none of those indexes
serves the day. An `empty` or `lost` entry also serves its period and must
not fall through to leftover raw files. The publication inventory can retain
raw names after compaction has removed their files. Those names are not
fetched when a compact index already serves their dates.
An old raw name behind an empty compact period is not proof that its raw
directory still exists. It receives an unconfirmed-day notice rather than
inventing another recorded health day. An exact current receipt can establish
that a raw date still exists; compact precedence still decides its rows.

Python's health-day selection is more specific than "days with a row".
`ledger_files.held_days` includes raw-folder dates and nonempty daily entries.
A nonempty monthly or yearly entry contributes every calendar day it covers,
including dates with no health rows. `load_health` takes the newest requested
number from that union, then reads the rows of those dates. TypeScript
reproduces this selection; it does not replace it with a count of row-bearing
dates. The lifecycle reader needs 31 selected dates, or the configured
reliability window when that is wider. A gap in raw dates does not become a
new empty day.

Retirement discovery has no date cutoff. Every retained indexed period and
every named unabsorbed raw retirement file remains eligible. The reader does
not change native retention: if the gardener has expired a period, discovery
cannot restore its rows or describe them as still present.

## Completeness remains explicit

A publication entry proves that a named file was recorded. It does not prove
that every writer of that day registered its files, and an exact receipt
proves only that invocation's writes. Missing inventory, missing compact
indexes and expired years produce named notices. Discovery therefore returns
`inventory_complete: false`; an empty result is not proof that no endpoint
was ever retired.

The shared native retirement writer does not currently register its returned
file paths in the publication inventory. Both plan-time HTTP 410 decisions
and assemble-time low-yield decisions use that writer. Completing discovery
needs a source that proves which retained raw retirement files exist.
Whether the publication inventory should list those paths, and how their
publication retry would preserve them, remains an owner decision. This
read-only consumer adds no registration and treats neither an empty file
list nor that proposal as retirement-absence proof.

## Design rationale

Keep discovery and recorded facts separate. Existing file inventories can
name the original rows without creating another authoritative version of
their history. Compact indexes decide which tier serves a date, so stale raw
names do not require a broad scan or a guessed calendar window.
Changing the health-day counting policy requires a separate owner decision;
input discovery must not silently change what the existing reader selects.

## See also

- [Feed harvesting](feed-harvesting.md) - lifecycle decisions before requests.
- [Planner runner](feed-plan-runner.md) - API composition and named evidence.
- [Ledger compaction](../publishing/ledger-compaction.md) - native index and tier rules.
- [Publication](../publishing/committing.md) - exact writes and fresh-main recovery.
