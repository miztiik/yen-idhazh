# Discovering native feed-health inputs

**Last Updated**: 2026-10-23

How does the TypeScript planner find existing health observations without
scanning directories or copying rows into another state file?

## One history, named inputs

Health observations stay in `state/raw/feed-health/` and
`state/compact/feed-health/`. Readers retain original native rows, versions
and writer identities. There is no separate current-history snapshot.

`resolveHealthInventory` reads the existing `PublicationInventory`
document, `frontend/public/publication.json`, and native `CompactIndex`
documents. The Python plan stage records exact health file paths in that
publication inventory after the native ledger writer returns. Those entries
name files, not copies of health records. The small TypeScript publication
projections are checked against the Python declarations in the existing
contract binding test.

Inputs are the existing publication inventory and three health compact
indexes. The result contains native file names and ordinary named-day reader
inputs. No file glob, directory enumeration, new index,
inventory write, receipt write or publisher change is part of discovery.

## Native selection and precedence

For each day, the yearly index wins over the monthly index, which wins over
the daily index. Raw files are selected only when none of those indexes
serves the day. An `empty` or `lost` entry also serves its period and must
not fall through to leftover raw files. The publication inventory can retain
raw names after compaction has removed their files. Those names are not
fetched when a compact index already serves their dates.
An old raw name behind an empty compact period is not proof that its raw
directory still exists. It receives an unconfirmed-day notice rather than
inventing another recorded health day. Same-listener current health receipts
remain the existing caller's responsibility, not another discovery store.

Python's health-day selection is more specific than "days with a row".
`ledger_files.held_days` includes raw-folder dates and nonempty daily entries.
A nonempty monthly or yearly entry contributes every calendar day it covers,
including dates with no health rows. `load_health` takes the newest requested
number from that union, then reads the rows of those dates. TypeScript
reproduces this selection; it does not replace it with a count of row-bearing
dates. The lifecycle reader needs 31 selected dates, or the configured
reliability window when that is wider. A gap in raw dates does not become a
new empty day.

## Completeness remains explicit

A publication entry proves that a named file was recorded. It does not prove
that every writer of that day registered its files. Missing inventory,
missing compact indexes, lost days and expired years produce named notices. Discovery
therefore retains `inventory_complete: false`; an empty result is not proof
that a feed has no older observations. A future-dated observation is an
input error, not a reason to invent or shorten recorded history.

## Design rationale

Maintainer ruling (2026-10-23): permanent retirement
authority for the TypeScript planner is the existing source registry,
`config/sources.json`, through `status: retired` and `retired_on`. It is not
the native retirement ledger. Retirement-file discovery, scanning, another
index or row store, and a new publication-inventory purpose are withdrawn.
This does not delete or rewrite historical Python ledger files.

Keep discovery and recorded facts separate. Compact indexes decide which
tier serves a date, so a stale raw file already served by compaction is not
read twice. Health discovery remains bounded by its existing named inputs.
Changing the health-day counting policy requires a separate maintainer decision;
input discovery must not silently change what the existing reader selects.

## See also

- [Feed harvesting](feed-harvesting.md) - source-registry lifecycle before requests.
- [Planner runner](feed-plan-runner.md) - API composition and named evidence.
- [Ledger compaction](../publishing/ledger-compaction.md) - native index and tier rules.
- [Publication](../publishing/committing.md) - exact writes and fresh-main recovery.
