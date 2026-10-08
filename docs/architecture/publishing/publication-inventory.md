# Publication Inventory

**Last Updated**: 2026-10-08

How does a static build find source days and files without walking the archive?

## Named inventory

The backend writes `frontend/public/publication.json`, beside `digest/`.
`PublicationInventory` in `backend/idhazh/contracts/publication_inventory.py`
declares its shape. `version` and `changelog` follow the shared contract.
`dates` holds unique UTC dates as `YYYY-MM-DD`, newest first.
Each date must have its `digest/<YYYY>/<MM>/<DD>/digest.json` entry.
`entries` holds one record per file: `root`, `path`, `bytes` and `items`.
`root` is `public` or `state`; entries sort by root, then path.
Paths are relative to the root each entry names. Entries are the only file
list; readers select the root and then filter paths by prefix.
Only a public dated digest counts items. Other
entries record zero items.
`total_bytes` and `total_items` hold the sums across public entries only. The
inventory excludes itself so its changing size cannot change its own total.

`backend/idhazh/publication.py` reads this one named file. It never lists
an archive or infers history from the current day. Assemble records the day,
its run manifest and visuals after writing them. A visual filename comes from
the validated day and item identity, not fetched prose or a supplied path.
The telemetry dispatcher records the month files after its projections finish.
The inventory includes search JSON and binary shards, telemetry CSV,
run-day JSON, day-metrics JSON, machine CSV and run-timeline CSV when present.
It also names the source-health view and console band.

Every writer that changes a published file must refresh its inventory entry
and commit `publication.json` with that file. Vector backfill records each
repaired day through `record_day` after writing it. It rebuilds each touched
month's search index, then refreshes its entries through `record_month`.

Each update checks only the caller's named files. An absent named file removes
its entry. Other entries remain untouched. The named inventory itself grows
with its entries; no other historical input is opened. Writes use the existing
atomic writer, so a reader sees the previous complete file or the next one.
An OS-held file lock serializes the complete read, update and replacement
across plan, assemble and telemetry processes. It lives beside the public root,
outside the served tree. Acquisition failure stops the write; no timeout path
runs unlocked. A dead process releases its OS lock. The lock file remains so
waiters always refer to the same file.
The existing gate lock is not suitable here: it can run unlocked and skips CI,
which is safe for scheduling tests but can lose inventory entries.
The writer reads each named file's byte count from its metadata. The day writer
supplies its item count from the day already in memory. Replacing an entry
subtracts the old counts and adds the new ones. It does not read older digests
to recount them. Validation checks the stored totals against the named entries.

## Explicit initialization

A missing inventory stops a backend writer; it never starts a newest-day-only
inventory. The frontend instead selects zero entries when the file is absent,
contains only whitespace, or declares zero entries. It warns once per process
and never discovers replacement files. Malformed non-empty inventories and
unsafe paths still fail.
Prepare a named JSON seed using the same contract and all existing days and
files that must remain browseable. Then run:

```text
python -m utilities.publication_inventory --public-root frontend/public --seed named-inventory.json
```

The command reads the seed and checks its named files. It refuses missing
files and refuses to replace an existing inventory. It does not walk or
backfill an archive. Set `PYTHONPATH=backend` when running from a source checkout.
`--empty` is only for an explicitly new fixture tree.
An inventory written before entry counts existed is upgraded explicitly:

```text
python -m utilities.publication_inventory --public-root frontend/public --upgrade
```

This migration reads only the old manifest's named files. It measures each
file's bytes and reads each named digest to count its items. Missing files fail
the migration without replacing the old inventory.
For an archive with no inventory, supply a named UTF-8 path list instead:

```text
python -m utilities.publication_inventory --public-root frontend/public --paths public-files.txt
```

The list has one public-root-relative POSIX file path per line. A one-time
operator migration can prepare it from an explicit Git file list. The utility
does not run Git or discover paths. It measures only the supplied names and
reads each supplied digest to obtain its UTC day and item count. The operator
must include every existing day and public series that must remain browseable.
Missing files, unsafe paths and a digest stored under the wrong UTC day fail
without writing an inventory. The frontend discovers each public series
by selecting public entries and filtering their paths by prefix.
The canary build inventories one generated run directory through
`frontend/scripts/canary-inventory.mjs`, then initializes the same validated
contract. It never enumerates committed data. Only drawings referenced by that
run's named digests enter the inventory; stale drawings do not. The build copies
its generated telemetry into the public root before measuring those files.
The canary day keeps its eight named article inputs. Its site build uses the
smaller initial item count in `config/canary.json` only when `CANARY_BUILD=1`;
production keeps its normal initial count. The first and fourth items carry
rendered charts. The fourth item sorts last by time and loads after the fixture's
initial shell.
This tests lazy content without opening a larger real published day.

The plan stage registers its raw feed-health CSV files under the `state` root
after its ledger write. It derives only its own filenames from its UTC days
and writer identity. The canary registers its fixed feed-health files through
the same helper. A frontend consumer selects state entries with the `feed-health/`
prefix; it does not list the state tree. Other ledger indexes remain separate.
The merge-line stage also registers its own dated CSV file:
`content-similarity-judge/fitted-thresholds/<YYYY>/<MM>/<DD>.csv`. The
holdout-score stage registers the raw door file it wrote under
`raw/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>/`.
The canary writes and registers these same named series before the site build.

Initial migration can supply a second explicit list:

```text
python -m utilities.publication_inventory --public-root frontend/public --paths public-files.txt --state-root state --state-paths state-files.txt
```

State input names and entry paths are relative to the state root.
State entries never contribute to the published
byte or item total.

## Design rationale

Owner exception, kumarsnaveen_microsoft, 2026-10-03: a missing or empty frontend
inventory degrades to an empty page selection with one warning, rather than
stopping the build. The backend must still refuse a missing inventory so an
update cannot silently lose older names.

Plan, assemble and vector backfill stage the named inventory with their output.
Assemble also declares it in the derived refresh paths. A rejected push restores
origin's inventory before regeneration, so the day and month writers update
current entries without replacing another writer's names.
Separate checkouts
never resolve an inventory conflict with Git text merging. The commit retry
takes origin's inventory and upserts only this run's named changes before it
continues the existing rebase. It re-stats those files and refreshes their counts
and public totals, preserving every other writer's entries. The existing retry
attempt limit still applies. The OS-held lock protects one checkout; the Git
retry protects independent checkouts.

Assembly reads source digest bytes and file counts from public entries with
the `digest/` prefix. It registers the current day before reading those totals,
then registers the new run manifest after writing it. Published-day readers
derive their paths from `dates`, oldest first. A missing named day stays in that
list so the publication gate reports it. Unlisted files are not discovered.
These are source measurements, not deployed bytes. The Pages cap uses the
[fresh build inventory](build-inventory.md).

The day writer already knows the day and item identities. Recording those
names avoids making each build rediscover every historical directory.
An explicit seed keeps old published days visible without allowing an implicit
archive scan. This page stays whole because the producer and its initialization
answer the same question: how a build obtains the named inventory.

## See also

- [layout.md](layout.md) - the public paths and reader addresses.
- [build-inventory.md](build-inventory.md) - deployed bytes and published item counts.
- [../contracts/schemas.md](../contracts/schemas.md) - persisted contracts and stamps.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - local checks.
