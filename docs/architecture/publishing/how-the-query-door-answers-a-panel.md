# How the query door answers a panel

**Last Updated**: 2026-09-30

The query door is the one module a console panel calls to read a committed
ledger: `slice()` for rows and `ledgerReach()` for how far a ledger reaches, both
in `frontend/src/lib/data/ledger.ts`, in a reader's browser.
A page built at build time calls its twin, `sliceFromDisk()` in
`frontend/src/lib/server/ledger-disk.ts`, over the same files on disk. Both run
one reader, so a build-time page and a browser panel asking for the same span get
the same rows. Why a panel reads through one module at all is rule 4 of
[how-a-console-chart-gets-its-data.md](../../concepts/console-design/how-a-console-chart-gets-its-data.md).
This page is what the door does.

## What a panel asks for, and the four answers

A panel names a ledger, the columns it draws, a closed range of UTC days and, if
it wants, a filter:

```ts
const result = await slice('host-fingerprint', {
	columns: ['date', 'job', 'shard', 'cores'],
	from: '2026-09-01',
	to: '2026-09-30',
	where: [{ column: 'job', op: '=', value: 'work' }]
});
```

The ledger is one of a closed set, so a panel names a ledger and never a path. A
filter is a column, an operator and a value; the value is bound as a query
parameter, so no text a panel passes can become SQL (Guardrail #11). The door
refuses a request by name, before it fetches anything, when it names no columns,
names a column that is not lower case, digits and `_`, gives a day that is not a
real UTC day, puts `from` after `to`, or filters on an empty `in` list. Those are
the caller's defects, found the first time the panel runs.

Everything else comes back as one of four answers, so a panel draws the right one
of four nothings without inspecting an error:

| # | Answer | When |
| --- | --- | --- |
| 1 | `ok`, with the rows | At least one row matched. The rows are what the files hold, sorted by the requested columns left to right; the door never merges two rows, because the compaction already wrote one row per record |
| 2 | `quiet` | Every day asked for is covered and nothing matched, or the whole span lies after the newest day compacted. A filter that matches nothing is `quiet`, never an empty `ok` |
| 3 | `missing` | The ledger has no `daily.json`, so it is not published |
| 4 | `unreachable`, at a day | The first day the door could not answer, and the console says why: a day no index names, a named file that did not arrive whole, an index this build will not act on, or an engine that could not run the query |

`ok` and `quiet` carry `through`, the newest day `daily.json` names - `null`
before the first compaction - so a panel can say how far its data reaches. A day
after `through` has not been compacted yet, so it is clamped away rather than
drawn as a zero.

## Which files a span reads

The ledger carries its own indexes, because a browser cannot list a directory:
`state/compact/<ledger>/index/daily.json`, `index/monthly.json` and, for a
ledger whose compaction packs years, `index/yearly.json`, written by the
gardener's compaction task and declared as `CompactIndex` in
`backend/idhazh/contracts/ledger_index.py`.

1. **`daily.json` first; `monthly.json` only when the span starts before the
   oldest day `daily.json` names; and `yearly.json` only when it starts before the
   oldest day those two name.** A span of 30 days or less reads one index.
2. **For each day, the coarsest period that holds it**: the year file when
   `yearly.json` names that year, else the month file when `monthly.json` names
   that month, otherwise the day file. A day is read through exactly one file, so
   a day two indexes name is read from the coarser - reading it twice would double
   every number drawn from it.
3. **A day no index names, at or before `through`, is a hole**, and the answer
   is `unreachable` at the first one. Drawing the days around it would be an
   undercount nobody could see.
4. **An entry with `rows: 0` is never fetched.** A span of quiet days loads no
   engine at all.
5. **A file whose decoded length differs from its entry's `bytes` is refused**, and
   so is one that does not arrive. The decoded length, never `Content-Length`,
   because Pages compresses what it serves.
6. **A day in a packed year costs the whole year file.** The door fetches every
   file whole, so drawing one month from a year fetches all twelve. The year file
   is written one row group a month, which would let a reader that fetches by
   byte range take one month's part, and this door does not. So the gardener
   keeps a published ledger's month files at least `console.max_window_days` plus
   `compact_after_days` after their year ends, and no read the console can widen
   to reaches a year file; a span panned further back than that does.

An index is asked for with `cache: 'no-store'`, so a page's one read of it gets
what the site holds now rather than a copy an HTTP cache kept, and the page then
keeps it (next section). A data file is asked for with `?v=<rows>-<bytes>` from
its entry: a compact file is written once, so the browser may keep it for as long
as that version names it.

## What a page keeps

A page keeps what the door read for it, so nothing crosses the network or enters
the engine twice. The keeper is `frontend/src/lib/data/page-keeper.ts`.

- **Each index is read once a page and kept.** Every slice and every reach on the
  page acts on the same `daily.json`, `monthly.json` and `yearly.json`. Two asks
  at the same moment share one fetch. A 404 is kept, because it is an answer; a
  fetch that threw is not, so the next ask tries again.
- **Each data file enters the engine once, and the page keeps its name, never its
  bytes.** A file is known by its path and the version its entry names. A
  browser's engine takes the buffer it is handed and leaves the page's copy empty,
  so bytes kept on the page would read as an empty file the second time. A file
  of the wrong length is neither registered nor kept, and a file that is not there
  is kept as absent.
- **The engine starts only when every file a slice needs has arrived whole**, so
  a slice that cannot be answered never loads it.

`ledger.ts` makes one keeper when a panel first asks and keeps it until the page
is reloaded. `sliceFromDisk()` makes a fresh one for each call, so it reads the
indexes as the disk holds them then, and drops every file it registered when the
call ends: a build reads many ledgers in one process, and a development server
reads `state/` again as it changes.

**What an open tab shows after a deploy: the data it opened with.** A day
compacted after the page opened appears only after a reload. A day file the
deploy re-packed or removed, and that the page had not read yet, answers
`unreachable`, and the console says why - it arrived at a length its kept entry
does not give, or it is not there. A reload fixes both.

**Why the index is kept rather than read again.** A console route anchors its
span on a first and a newest day fixed for the page, and a panel that read a
newer index than its neighbour would draw a different span beside it. Reading the
index again before every slice would also put one more round trip in front of
each one, where a cold load allows four serial round trips in all
(`frontend/tests/console-cold-load.spec.ts`).

## How far a ledger reaches

`ledgerReach(ledger)` answers the oldest and the newest day a ledger holds, so a
route can anchor its span on the data rather than on the clock:

| # | Answer | When |
| --- | --- | --- |
| 1 | `ok`, with `first` and `through` | `through` is the newest day `daily.json` names, the same day a slice returns. `first` is the oldest day any index names, a month counting from its first day and a year from its 1 January |
| 2 | `quiet` | `daily.json` names no day yet |
| 3 | `missing` | There is no `daily.json`, so the ledger is not published |
| 4 | `unreachable` | `daily.json` is one this build will not act on, or could not be read. It carries no day, because the reach asks for none; the console says why |

It reads all three indexes at the same time through the page's keeper, so a slice
asked after it reads none again, and it starts no engine. A `monthly.json` or
`yearly.json` this build will not act on leaves the days the other indexes name,
and the console says why. A packed year counts from its 1 January even when the
ledger's first rows came later in it. The logic is
`frontend/src/lib/data/ledger-reach.ts`, which reads each index with the slice's
own reader, so the two never disagree about what an index says.

## Where each file is asked for

The address is composed in `frontend/src/lib/data/slice-reader.ts` and nowhere
else, from the closed ledger name, the period and a `covers` the index guard has
already checked:

- `<prefix>/state/compact/<ledger>/index/<period>.json`
- `<prefix>/state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet`
- `<prefix>/state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet`
- `<prefix>/state/compact/<ledger>/yearly/<YYYY>.parquet`

`<prefix>` is `visuals.asset_base_url` in `config/idhazh.json`, or SvelteKit's own
repository prefix when that knob is empty, which is the shipped default. It comes
from the build, never from a payload, so no fetched text can move where the door
asks. On disk the same paths sit under the state root handed to `sliceFromDisk()`.

## The index copy, and the stamp it reads

`frontend/src/lib/data/compact-index.ts` is the frontend's hand copy of
`CompactEntry` and `CompactIndex`, with the stamp this build reads.
`backend/tests/contracts/test_frontend_index_shapes.py` holds it in step
([../contracts/schemas.md](../contracts/schemas.md)).

**An index stamped at this build's stamp or older is read; a newer one is
refused.** A refusal is `unreachable` from the first day asked, with both stamps
in the console, and no data file is fetched. The gardener rewrites an index at its
own wake rather than in the commit that moves the shape, so a build that demanded
its own stamp exactly would blank every panel from a shape change until the next
wake. The guard checks the fields the door acts on - the ledger, the period, and
each entry's `covers`, `rows` and `bytes`, ascending and none twice - and ignores
any other field an older index carries.

## The engine

`frontend/src/lib/data/engine.ts` is the only module in `frontend/` that imports
the query engine, `@duckdb/duckdb-wasm`, taken at a caret range like every other
dependency. Nothing pins it: the door's oracle runs against whatever version is
installed, so an upgrade that breaks a query or the add-on below turns that test
red on the pull request that raised the version (owner ruling, 2026-09-28).
`frontend/tests/chart-vocabulary.spec.ts` holds that to one importer, holds every
panel to `ledger.ts`, and holds `sliceFromDisk()` to the modules under
`frontend/src/lib/server/`.

**Every file the engine holds is named `door/<n>.parquet`**, and the engine mints
the name from a counter, never from an index, a `covers` value or a caller, so no
fetched text can name a file. So every file the door registers sits under one
directory, which an engine that admits a single directory can still read.

**One build ships to the browser**: the single-threaded one that needs WebAssembly
exception handling. The threaded build needs response headers a static host cannot
send. A browser without the feature gets `unreachable`. Count the emitted engine
assets in deployed size even though they load lazily
([../../reference/site-weight.md](../../reference/site-weight.md#optional-assets)).

**None of it is first-load.** `ledger.ts` reaches the engine only through a
dynamic `import()`, and the engine reaches its package, its wasm and its worker
the same way. `frontend/scripts/bundle-gate.mjs` holds that: it follows every
static import from each page's own module, and fails when a file on that path
carries the package's name or the name of its wasm or its worker. It names the
file, not the page.

Checked 2026-09-28 against a build with three deliberate edits, reverted
afterwards: a static import of the package into the archive page; the same, plus
a static `?url` import of the wasm, into the evals page; and a `slice()` call from
the front page. That build broke in its prerender (next paragraph), so the gate
read the browser output the break leaves whole. It failed on two files - the chunk
holding the package, and a one-line chunk holding the wasm's address - and neither
is on the front page's static path. Neither is a page's own module either, so the
gate as it stood before this change, which read only those, would have passed the
same build.

**A static import of the package breaks the build before the gate runs.** In the
prerender the package resolves to its Node build, which mistakes the prerender's
worker thread for its own and throws `TypeError: Cannot destructure property 'mod'
of 'R.workerData' as it is undefined` from `duckdb-node.cjs`. The message names
neither the page nor the rule, so this paragraph is where a search for it lands.

**The worker starts from a `blob:` bootstrap** that imports the same-origin worker
file by absolute URL. A worker started from a same-origin URL takes its policy from
its own response headers, and Pages sends none, so it would run with no
`connect-src` at all; a `blob:` worker inherits the page's policy. Measured
2026-09-28 on the built archive page in Chromium: a `blob:` worker's fetch to a
third-party host was refused under `connect-src`, and its fetch to the site's own
origin answered 200.

**At build time** the engine's Node half loads the package's blocking Node build
and reads its wasm from the installed package. The build's name is held in a
variable the browser bundler cannot follow, so the Node half's own few lines ride
in the browser's engine chunk - 2,287 bytes with both halves - and none of the
Node build does.

## Where the parquet reader comes from

**The engine downloads it, the way DuckDB-Wasm does on any site.** The engine
links only DuckDB's core functions, so the first query over parquet makes it fetch
the parquet add-on - `<repository>/v<DuckDB version>/wasm_eh/parquet.duckdb_extension.wasm`,
3,218,307 bytes for DuckDB 1.5.4 and 522,051 with brotli - and it checks the
add-on's signature before loading it. `<repository>` is
`ledger.engine_extension_repository` in `config/idhazh.json`, DuckDB's own host by
default. `engine.ts` tells the engine that address with `SET
custom_extension_repository`, and the page's `connect-src` admits its origin
through `engineOrigins()` in `frontend/asset-base.js`, so one edit moves both.
Owner ruling, 2026-09-28: this is normal DuckDB-Wasm behaviour, and the site
allows it.

Measured 2026-09-28 with a throwaway page that starts the engine the way
`engine.ts` does and reads the fixture's month file, once under the site's shipped
policy and once with the add-on's origin added:

| # | Browser | Shipped policy | With the add-on's origin |
| --- | --- | --- | --- |
| 1 | Chromium 151 | Refused: the add-on request failed `csp` | 3 rows x 35 columns |
| 2 | Edge 154 | Refused the same way | 3 rows x 35 columns |

Firefox was not run: the test tool's own Firefox build was not installed. Told
another address, the engine asked for
`<that address>/v1.5.4/wasm_eh/parquet.duckdb_extension.wasm`, so a mirror serves
that layout. Pointed at a file on disk instead of an address, the Node half waits
for ever rather than failing, so a mirror is an `https://` address, never a path.

**In Node** the engine downloads the add-on over HTTPS the first time and keeps it
under the user's home directory, in `.duckdb/extensions/<host>/v1.5.4/wasm_eh/`, so
later runs read it from disk; the first read took 1.3 seconds on a developer
machine. So the door's oracle in `frontend/tests/ledger-door.spec.ts` reaches the
network once on a fresh machine - a CI runner, every run. That is the one
exception to "no test touches the network", taken by the owner on 2026-09-28. A
host that is down or has moved fails those tests and any build-time read, which is
where somebody wants to learn it.

## Design rationale

**The door is split so a Node test can load its logic.** The states, the index
guard, the address, the page keeper and the query sit in modules that import
nothing tied to one environment and take a byte source and an engine as
arguments. `ledger.ts` binds the published site, which needs `$app/paths`;
`ledger-disk.ts` binds the disk under `$lib/server/`, where SvelteKit refuses a
browser import. So `frontend/tests/ledger-door.spec.ts` drives the real reader
over recorded responses and over the disk, with no browser, and no network but
the engine's own first download of its add-on. The engine it drives takes each
buffer the way a browser's engine does, leaving the caller's copy empty, because
the Node engine copies instead and would hide a door that handed one buffer over
twice.

**A page keeps names, not bytes.** Keeping each file's bytes and handing them to
the engine again for every slice is the smaller change, and it fails only in a
browser: the browser's engine takes a registered buffer and leaves the page's copy
empty, so the second slice would hand it an empty file, while the Node engine
copies and every Node test would pass. Weighed and refused on 2026-09-29.

**No retry after a deploy.** A kept index that names a file the deploy re-packed
or removed answers `unreachable` rather than reading the indexes again and
retrying once. The retry is about twenty lines, and it would move a page's first
and newest day under panels already drawn. It is the move if an open tab is ever
seen answering `unreachable` after a deploy; nothing has shown one yet. Ruled on
2026-09-29.

**The add-on comes from DuckDB's host, not ours.** It is what every site running
this engine does, and it keeps 3.2 MB off the site and a download step out of the
build. What it costs is one more origin in `connect-src`, and the engine's
signature check is what makes that origin safe to admit. Serving a copy from this
site, checked against a digest in `config/`, with the native engine for the Node
half, was the alternative weighed on 2026-09-28; the owner ruled for the normal
design.

**Files are read by column name.** A day written before a column existed reads
that column as null. A column no file in the span holds reads as null in every
row, which is the same answer, and the console names the column, because a name
nobody wrote would otherwise look exactly like a reading nobody took.

**Rows are sorted by every requested column.** The same files then give the same
rows in the same order whichever engine read them and however it split the work.

**An integer comes back as a `number`, or not at all.** The engine hands a 64-bit
integer back as a `BigInt`; one outside the range a `number` holds exactly is
refused by name, and the slice is `unreachable`, because a rounded count is a
wrong count nobody can see.

## See also

- [../../concepts/console-design/how-a-console-chart-gets-its-data.md](../../concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules a panel's data obeys.
- [../contracts/schemas.md](../contracts/schemas.md) - the hand copy of the index shapes and the test that binds it.
- [../../reference/site-weight.md](../../reference/site-weight.md#optional-assets) - deployed size, lazy downloads and cache assumptions.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the bundle gate that keeps the engine off the first load.
