# How the query door answers a panel

**Last Updated**: 2026-09-28

The query door is the one module a console panel calls to read a committed
ledger: `slice()` in `frontend/src/lib/data/ledger.ts`, in a reader's browser.
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
| 4 | `unreachable`, at a day | The first day the door could not answer, and the console says why: a day named by neither index, a named file that did not arrive whole, an index this build will not act on, or an engine that could not run the query |

`ok` and `quiet` carry `through`, the newest day `daily.json` names - `null`
before the first compaction - so a panel can say how far its data reaches. A day
after `through` has not been compacted yet, so it is clamped away rather than
drawn as a zero.

## Which files a span reads

The ledger carries its own indexes, because a browser cannot list a directory:
`state/compact/<ledger>/index/daily.json` and `index/monthly.json`, written by the
gardener's compaction task and declared as `CompactIndex` in
`backend/idhazh/contracts/ledger_index.py`.

1. **`daily.json` first, and `monthly.json` only when the span starts before the
   oldest day `daily.json` names.** A span of 30 days or less reads one index.
2. **For each day, the coarsest period that holds it**: the month file when
   `monthly.json` names that month, otherwise the day file. A day is read through
   exactly one file, so a day both indexes name is read from the month - reading
   it twice would double every number drawn from it.
3. **A day neither index names, at or before `through`, is a hole**, and the answer
   is `unreachable` at the first one. Drawing the days around it would be an
   undercount nobody could see.
4. **An entry with `rows: 0` is never fetched.** A span of quiet days loads no
   engine at all.
5. **A file whose decoded length differs from its entry's `bytes` is refused**, and
   so is one that does not arrive. The decoded length, never `Content-Length`,
   because Pages compresses what it serves.

An index is asked for with `cache: 'no-store'`, because file selection acts on it.
A data file is asked for with `?v=<rows>-<bytes>` from its entry: a compact file is
written once, so the browser may keep it for as long as that version names it.

## Where each file is asked for

The address is composed in `frontend/src/lib/data/slice-reader.ts` and nowhere
else, from the closed ledger name, the period and a `covers` the index guard has
already checked:

- `<prefix>/state/compact/<ledger>/index/<period>.json`
- `<prefix>/state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet`
- `<prefix>/state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet`

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
the query engine, `@duckdb/duckdb-wasm`, pinned exactly at `1.33.1-dev57.0`: its
`latest` tag is a development build, so a caret would let an install move it.
`frontend/tests/chart-vocabulary.spec.ts` holds that to one importer, holds every
panel to `ledger.ts`, and holds `sliceFromDisk()` to the modules under
`frontend/src/lib/server/`.

**One build ships to the browser**: the single-threaded one that needs WebAssembly
exception handling. The threaded build needs response headers a static host cannot
send. A browser without the feature gets `unreachable`. What it adds to the site
is in [../../reference/site-weight.md](../../reference/site-weight.md).

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

**No statement may fetch code.** The engine's automatic extension install and load
are switched off in both halves, so no query can reach a third-party host.

## What does not work yet: the parquet reader

**The pinned build reads no parquet by itself.** It links only DuckDB's core
functions. `read_parquet` lives in a separate extension file,
`wasm_eh/parquet.duckdb_extension.wasm` (3,218,307 bytes for DuckDB 1.5.4), which
the engine otherwise downloads from `extensions.duckdb.org` the first time a query
needs it. Measured 2026-09-28 on a Windows developer machine, Node 24.12.0: the
newest stable release, 1.32.0 (DuckDB 1.4.3), is the same.

Two consequences. In a browser the page's `connect-src`, which names this site and
the two hosts the encoder downloads its model from, refuses that host.
In Node the blocking build loads an extension only over HTTP or from a cache it
keeps under the user's home directory, and pointed at a file on disk it waits for
ever instead of failing. So until the file is delivered from this site's own
origin, every query over parquet ends `unreachable`, with the engine's own message
in the console. How the file is delivered is an open decision, held in the active
plan-doc for the console's data under `TODO/`.

## Design rationale

**The door is split so a Node test can load its logic.** The states, the index
guard, the address and the query sit in modules that import nothing tied to one
environment and take a byte source and an engine as arguments. `ledger.ts` binds
the published site, which needs `$app/paths`; `ledger-disk.ts` binds the disk under
`$lib/server/`, where SvelteKit refuses a browser import. So
`frontend/tests/ledger-door.spec.ts` drives the real reader over recorded
responses and over the disk, with no browser and no network.

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
- [../../reference/site-weight.md](../../reference/site-weight.md) - what the engine adds to the site, and what Pages sends again after a deploy.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the bundle gate that keeps the engine off the first load.
