# How the query door answers a panel

**Last Updated**: 2026-10-04

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

The chart-contract check reads each call with TypeScript's parser. Columns may
be an inline literal or a named static array, including an imported declaration.
Unknown runtime expressions and `*` fail the check. Both date endpoints must be
present; shorthand fields carry the same boundary as explicit assignments.

Everything else comes back as one of four answers, so a panel draws the right one
of four nothings without inspecting an error:

| # | Answer | When |
| --- | --- | --- |
| 1 | `ok`, with the rows | At least one row matched. The rows are what the files hold, sorted by the requested columns left to right; the door never merges two rows, because the compaction already wrote one row per record |
| 2 | `quiet` | Every day asked for is covered and nothing matched, or the whole span lies after the newest day compacted. A filter that matches nothing is `quiet`, never an empty `ok` |
| 3 | `missing` | The ledger has no `daily.json`, so it is not published. Its fault is `not-packed` |
| 4 | `unreachable`, at a day | The first day the door could not answer, and the console says why. A file the ledger should hold and does not is named as one of four faults ([below](#when-a-file-is-missing)); the other causes are a span that starts before the oldest day any index names, a named file that arrived at the wrong length or could not be fetched, an index this build will not act on, and an engine that could not run the query |

`ok` and `quiet` carry `through`, the newest day `daily.json` names - `null`
before the first compaction - so a panel can say how far its data reaches. A day
after `through` has not been compacted yet, so it is clamped away rather than
drawn as a zero. `missing` and `unreachable` carry `fault`, the name of the
missing file behind them, or `null` for an `unreachable` with another cause.

## Which files a span reads

The ledger carries its own indexes, because a browser cannot list a directory:
`state/compact/<ledger>/index/daily.json`, `index/monthly.json` and
`index/yearly.json`, written together by the gardener's compaction task - an
index for a period never packed names nothing - and declared as `CompactIndex` in
`backend/idhazh/contracts/ledger_index.py`.

1. **`daily.json` first; `monthly.json` only when the span starts before the
   oldest day `daily.json` names; and `yearly.json` only when it starts before the
   oldest day those two name.** A span of 30 days or less reads one index.
2. **For each day, the coarsest period that holds it**: the year file when
   `yearly.json` names that year, else the month file when `monthly.json` names
   that month, otherwise the day file. A day is read through exactly one file, so
   a day two indexes name is read from the coarser - reading it twice would double
   every number drawn from it.
3. **A day no index names, between the oldest day any index names and
   `through`, is a hole**, and the answer is `unreachable` at the first one,
   named `day-missing`. Drawing the days around it would be an undercount nobody
   could see. A span that starts before the oldest named day is `unreachable` at
   its first day with no fault: those days were never packed, and a route clamps
   its span to the reach's `first` (below).
4. **An entry with `rows: 0` is never fetched.** A span of quiet days loads no
   engine at all.
5. **A file whose decoded length differs from its entry's `bytes` is refused**, and
   so is one that does not arrive; one the site answers is not there is
   `file-missing`. The decoded length, never `Content-Length`,
   because Pages compresses what it serves. A year file read by byte range is
   held to the same rule by the length the engine opened it at.
6. **A day in a packed year is read from its year file by byte range.** In a
   browser the engine asks the host for the year file's footer and then for the
   parts of the months the query touches, because the gardener writes a year file
   one row group a month. One month of 10 columns out of a 29.8 MB year cost
   243,046 bytes, a tenth of that month's own file
   ([the measurement](../../reference/benchmarks/what-a-month-out-of-a-year-file-costs.md)).
   Each read asks at an address no earlier read used, so a deploy between two
   reads cannot make the host send the whole file
   ([below](#how-a-year-file-is-read-by-byte-range)). A day file and a month file
   are fetched whole, and at build time every file is.

An index is asked for with `cache: 'no-store'`, so a page's one read of it gets
what the site holds now rather than a copy an HTTP cache kept, and the page then
keeps it (next section). A data file is asked for with `?v=<rows>-<bytes>` from
its entry: a compact file is written once, so the browser may keep it for as long
as that version names it. A year file read by byte range is asked for at that
address with one more part, `read`, which no earlier read used.

## What a page keeps

A page keeps what the door read for it, so nothing it fetches whole crosses the
network or enters the engine twice. A year file read by byte range is the
exception: each read asks the host for the parts it needs again. The keeper is
`frontend/src/lib/data/page-keeper.ts`.

- **Each index is read once a page and kept.** Every slice and every reach on the
  page acts on the same `daily.json`, `monthly.json` and `yearly.json`. Two asks
  at the same moment share one fetch. A 404 is kept, because it is an answer; a
  fetch that threw is not, so the next ask tries again.
- **Each data file fetched whole enters the engine once, and the page keeps its
  name, never its bytes.** A file is known by its path and the version its entry
  names. A browser's engine takes the buffer it is handed and leaves the page's
  copy empty, so bytes kept on the page would read as an empty file the second
  time. A year file read by byte range never crosses as bytes and is never kept:
  each read has the engine open it at an address of its own, and the engine drops
  it when the read ends, answered or not. A file of the wrong length is neither
  registered nor kept, and a file that is not there is kept as absent.
- **The engine starts beside the selected data fetches**, after the indexes have
  passed validation and selected non-empty files. Quiet spans, missing indexes
  and holes start no engine. A failed data fetch can overlap startup, but its
  bytes never enter the engine and its named fault is preserved. Whole-file
  downloads and year-range reads use the same startup order.
- **Each console line is printed once for the page's life.** Every panel that
  meets one missing file prints the same line, so fifteen panels on a page
  print it once.

`ledger.ts` makes one keeper when a panel first asks and keeps it until the page
is reloaded. `sliceFromDisk()` makes a fresh one for each call, so it reads the
indexes as the disk holds them then, and drops every file it registered when the
call ends: a build reads many ledgers in one process, and a development server
reads `state/` again as it changes.

**What an open tab shows after a deploy: the data it opened with.** A day
compacted after the page opened appears only after a reload. A day file the
deploy re-packed or removed, and that the page had not read yet, answers
`unreachable`, and the console says why - it arrived at a length its kept entry
does not give, or it is not there, which is `file-missing`. A reload fixes both.

**Why the index is kept rather than read again.** A console route anchors its
span on a first and a newest day fixed for the page, and a panel that read a
newer index than its neighbour would draw a different span beside it. Reading the
index again before every slice would also put one more round trip in front of
each one, where a cold load allows four serial round trips in all
(`frontend/tests/console-cold-load.spec.ts`).

The Hardware cold-load check measures the larger of two paths: document,
indexes, whole-file data and add-on; or document, indexes, core wasm and add-on.
Data and core wasm are independent after file selection. A fast local data
response ending before the wasm request starts does not prove an extra wait.
Separate real-response gates hold each branch in turn and require the other to
progress. The timing run holds nothing, counts planted pre-index waits on both
paths, and keeps the four-hop ceiling and every engine download in scope.

## How far a ledger reaches

`ledgerReach(ledger)` answers the oldest and the newest day a ledger holds, so a
route can anchor its span on the data rather than on the clock:

| # | Answer | When |
| --- | --- | --- |
| 1 | `ok`, with `first` and `through` | `through` is the newest day `daily.json` names, the same day a slice returns. `first` is the oldest day any index names, a month counting from its first day and a year from its 1 January. Its `fault` is `index-missing` when there is no `monthly.json` or no `yearly.json`, and `first` is then the oldest day the indexes that are there name |
| 2 | `quiet` | `daily.json` names no day yet |
| 3 | `missing` | There is no `daily.json`, so the ledger is not published. Its fault is `not-packed` |
| 4 | `unreachable` | `daily.json` is one this build will not act on, or could not be read. It carries no day, because the reach asks for none; the console says why |

It reads all three indexes at the same time through the page's keeper, so a slice
asked after it reads none again, and it starts no engine. A `monthly.json` or
`yearly.json` this build will not act on leaves the days the other indexes name,
and the console says why. A packed year counts from its 1 January even when the
ledger's first rows came later in it. The logic is
`frontend/src/lib/data/ledger-reach.ts`, which reads each index with the slice's
own reader, so the two never disagree about what an index says.

## When a file is missing

A packed ledger lists its own files in its three indexes, so a file it should
hold and does not is a named fault, never an empty answer. The rule, the four
names and what the gardener does about each are on the compaction's page
([ledger-compaction.md](ledger-compaction.md#the-three-indexes-and-a-file-that-is-missing)).
`LEDGER_FAULTS` in `frontend/src/lib/data/slice-shapes.ts` declares the names,
and this is what each one draws:

| # | Fault | What is missing | A slice answers | A reach answers |
| --- | --- | --- | --- | --- |
| 1 | `not-packed` | `daily.json` | `missing`, and the route's note says the record is not packed yet | `missing` |
| 2 | `index-missing` | `monthly.json` or `yearly.json`, while `daily.json` is there | A span that needs only the indexes that are there draws; one that reaches back far enough to need the missing one is `unreachable` at its first day | `ok` from the oldest day the other indexes name |
| 3 | `file-missing` | A file an index names | `unreachable` from the first day that file covers in the span | Unchanged: a reach reads no data file |
| 4 | `day-missing` | A day between the oldest and the newest packed day that no index names | `unreachable` at that day | Unchanged |

**Each fault prints one console line**, in one shape - the fault, the ledger,
the committed path, what is wrong and what fixes it:

```text
[ledger] file-missing summary-quality-evals state/compact/summary-quality-evals/daily/2026/09/12.parquet: daily.json names it; it is not there. Reload; if it stays, re-pack that day.
```

The line names no span, so every panel that meets one fault prints the same
line, and the page keeper prints it once for the page's life; a build-time call
prints it once a call. The line is `faultLine()` in
`frontend/src/lib/data/slice-reader.ts`. A route's note for a record uses the
same names: a record whose packed file or packed day is missing says which,
because each has its own fix (`recordNotes` in
`frontend/src/lib/console/recording.ts`).

**Three gaps are expected, and none of them is a fault or a request**: a day
after the newest packed day is clamped away, an entry with `rows: 0` is never
fetched, and an empty `monthly.json` or `yearly.json` names nothing. None of
them makes the door
ask the site for a file that is not there, and `frontend/tests/ledger-door.spec.ts`
counts what a byte source is asked to prove it.

## Where each file is asked for

The address is composed in `frontend/src/lib/data/slice-reader.ts` and nowhere
else, from the closed ledger name, the period and a `covers` the index guard has
already checked:

- `<prefix>/state/compact/<ledger>/index/<period>.json`
- `<prefix>/state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet`
- `<prefix>/state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet`
- `<prefix>/state/compact/<ledger>/yearly/<YYYY>/<YYYY>.parquet`

`<prefix>` is `visuals.asset_base_url` in `config/idhazh.json`, or SvelteKit's own
repository prefix when that knob is empty, which is the shipped default. It comes
from the build, never from a payload, so no fetched text can move where the door
asks. The query a data file is asked with, `?v=<rows>-<bytes>`, and the `read`
part a year file read by byte range adds, are made in
`frontend/src/lib/data/fetched-bytes.ts` from the index entry and from random
bits, never from fetched text. On disk the same paths sit under the state root
handed to `sliceFromDisk()`.

## What the site holds for the door

The site holds the ledgers `ledger.published` in `config/idhazh.json` names:
`candidate-models`, `counterfactual-scores`, `host-fingerprint`, `item-health`,
`published`, `seen` and `summary-quality-evals`. It holds nothing else of
`state/`. The build copies each ledger's three indexes, trimmed to the widest
console span, and every compact file those trimmed indexes name, to the path each
has under `state/`: `frontend/scripts/copy-visuals.mjs` stages them into
`frontend/static/state/`, which git ignores, and the bundler carries them into
the site. A published data file is byte for byte the ledger itself, so it cannot
say anything `state/` does not. The trimmed indexes are new files for the staged
site only, and they keep the same `CompactIndex` shape. The committed registry
`config/ledgers.json` is copied verbatim to the site at `config/ledgers.json`.
`frontend/scripts/published-ledgers.mjs` decides which ledger files are in that
staged tree.

- **The trimmed indexes are the list.** No directory is walked, so the gardener's
  watermark, a raw day and any file no trimmed index names stay off the site with
  no list of things to leave out. A file whose entry has `rows: 0` is copied too,
  so every entry resolves, although the door never asks for one.
- **A published ledger without all three indexes stops the build**, which names the
  ledger and the missing file. A browser asks for a ledger's indexes before
  anything else, so a 404 there would be the only sign that the ledger was
  published wrongly. The whole site waits, reading pages included, until the
  ledger is whole again or leaves `ledger.published`.
- **The cap is the widest console span, anchored on the ledger's data.** On
  2026-10-03 that span is 90 UTC days. It is counted back from the newest day
  any of the three packed indexes names: a day as itself, a month through its
  last UTC day and a year through 31 December. A period is copied whole when it
  overlaps that span, so a month or year can make the oldest reachable day older
  than 90 days, and nothing older than that overlapping period is named.
- **Raw days after the newest packed day are listed for the site only.** The
   build checks at most the same 90 UTC days after each ledger's newest packed
   day, writes one `RawDayIndex` under `state/raw/<ledger>/index/<day>.json` for
   each listed day, and copies the parquet writer files the listing names. A day
   whose raw directory also holds a non-parquet writer file is left unlisted, and
   the build log names that file.
- **A data file an index names and the tree lacks does not stop it.** The build
  copies the rest and puts a `file-missing` warning, naming the file, on the run's
  page; the door answers `unreachable` for a span that reaches that day.
- **The canary build publishes the fixture's ledgers**, because the copy reads the
  same `STATE_ROOT` the build-time readers do, and a root that is not there stops
  the build rather than publishing nothing.
- **With `visuals.asset_base_url` set, no ledger file is copied**, because the
  door asks that host. Whoever sets it puts each `state/compact/<ledger>/` tree
  there, and the bundle gate skips the ledgers' keys. The registry still ships
  from this site, because the page reads it as the site's declaration of what it
  can show.
- **`backend/tests/contracts/test_published_ledgers_cover_the_panels.py` holds the
  two sides together**: every ledger a panel names in a `slice()` or
  `ledgerReach()` call is in `ledger.published`. The door's closed set admits one
  more, `feed-health`, which a build-time reader asks through `sliceFromDisk`
  and no browser panel asks, so the site holds none of its files.
  `frontend/tests/published-ledgers.spec.ts` asks the built
  site the door's own questions: every address an index names is there, at the
  size its entry gives, and nothing else of `state/` is.

**What it weighs, and what bounds it.** Day and month indexes are bounded by each
ledger's declaration: `daily_keep_days` plus 31 day entries and the months its
window keeps, or the months awaiting yearly packing. A ledger that keeps rows
forever packs years, so the yearly index grows by one entry a year rather than by
one month forever. Each published ledger's index directory has a
`page_weight.payload_ceilings_bytes` key of 2,200 gzipped bytes, at least twice
its longest bounded day or month index. The copied registry has its own
`config/ledgers.json` key of 3,200 gzipped bytes, which is a little over twice
the 1,469 bytes measured at gzip -5 on 2026-10-02. The bundle gate weighs all
three indexes and the registry; `backend/tests/contracts/test_page_ceilings.py`
also fails when a day or month keep window grows past its bound. Size a key from
the runner's reading, because zlib-ng, which some local Python builds use, reads
the same index about 4 percent smaller. **The data files carry no ceiling, and no
gate yet weighs what one span reads.**

Measured 2026-10-03 on this shared Windows machine from a real build of the
committed `state/`, after raw-day listings were staged, the whole built site
weighed 160,958,761 bytes, or 153.5 MB, beside the 1,073,741,824-byte Pages cap.
That leaves 870.5 MB before GitHub Pages refuses the deploy. The compact ledger
files under `build/state/compact/` weighed 15,809,007 bytes, or 15.1 MB, in all:
`candidate-models` 87,319 bytes, `counterfactual-scores` 828,742 bytes,
`host-fingerprint` 357,233 bytes, `item-health` 4,349,116 bytes, `published`
947,535 bytes, `seen` 4,560,565 bytes and `summary-quality-evals` 4,678,487
bytes. The raw-day tier added these listings and writer files:
`counterfactual-scores` 2 listings and 6 files, 135,442 bytes; `host-fingerprint` 2 listings and
58 files, 721,224 bytes; `item-health` 2 listings and 30 files, 1,841,816 bytes;
`published` 1 listing and 7 files, 87,595 bytes; `seen` 2 listings and 5 files,
234,524 bytes; and `summary-quality-evals` 3 listings and 50 files, 1,433,599
bytes. That reading is not a gate; `idhazh site-weight` is the gate and the cap
is the platform limit.

## How a year file is read by byte range

In a browser the page keeper hands the engine a year file's address rather than
its bytes, a new address for each read, through `registerAddress` in
`frontend/src/lib/data/engine.ts`, and the engine drops the file when the read
ends. The engine opens the file with a 1-byte GET and a `HEAD`, then asks only for
its footer and for the parts of the row groups the query touches. Which periods
are read this way is `RANGED_PERIODS` in `frontend/src/lib/data/slice-reader.ts`.
`sliceFromDisk()` reads every file whole, because the engine's Node half reads no
host. `frontend/tests/ledger-ranges.spec.ts` drives a real browser against a host
on 127.0.0.1 that answers the way Pages does. Five facts shape the design.

- **The engine's own default reads an address whole.** DuckDB-Wasm opens with
  `forceFullHTTPReads` on, and then reads a registered address in one GET with no
  `Range`. `engine.ts` opens the database with it off. A read answered 200 rather
  than 206 also makes the engine take the whole body without a word, so the spec
  requires every GET for a year file to name a range and be answered 206.
- **Pages answers a `HEAD` that carries a `Range` with 200 and the full length.**
  The engine takes a file's length from that `HEAD`, and accepts a 200 only while
  `allowFullHTTPReads` is on, so that setting stays on. The length it opened must
  equal the entry's `bytes`, or the slice is `unreachable` and the console says
  `<path> opened at <n> bytes to be read by range, and its entry says <m>`.
- **Pages ignores the query string.** `?v=a` and `?v=b` get the same bytes and the
  same ETag, so nothing in the query reaches the host. The browser keeps what it
  fetched under the whole address, query and all, so the door gives each read of a
  year file an address of its own: the version its entry names, and a `read` part
  of 64 random bits made when the read starts, in
  `frontend/src/lib/data/fetched-bytes.ts`. A counter would not do: it restarts
  with each page, and the browser keeps what one page fetched for the next. The
  engine reads the file under a name it mints for that one read.
- **A year file is written once and never rewritten in place.** The gardener
  writes it when the year is packed and never again, so ranges read at different
  times all come from the same bytes.
- **Every Pages deploy gives every file a new ETag**, over the same bytes. Chromium
  asks for a range it does not hold, at an address where it holds others, with
  `If-Range` naming the ETag it kept, and a host that honours `If-Range` answers a
  changed ETag with 200 and the whole file. At an address no earlier read used the
  browser holds nothing, so the only ETag a read names is the one the host gave
  that same read. The spec drives both ways a deploy can fall between two reads -
  the same page reading again, and a new page opened while what the first page
  fetched is still fresh, within Pages' `max-age=600` - and requires every GET for
  the year file to be answered 206.

**Pages honours `If-Range`, measured on the live site.** A ranged GET whose
`If-Range` names the ETag Pages serves now is answered 206 with the range; one
naming an older ETag, or a date before the file's, is answered 200 with the whole
file. Every file in one deploy carries that deploy's time as its `Last-Modified`
and in its ETag, eleven seconds after the build job ended, so the build cannot pin
it, and an unchanged file still gets a new ETag. Reading each year file at an
address no earlier read used is what keeps a deploy from costing a whole file, so
a published ledger packs a year as soon as its own declaration says
([../../concepts/config/idhazh-gardener.md](../../concepts/config/idhazh-gardener.md#the-compaction-declarations-that-ship)),
and a console read may reach a year file.

**Pages compresses a range only when the request accepts compression, measured
on the live site.** It sends a `.parquet` as `application/octet-stream` and
compresses it on request like any other file. The eval ledger's day file for
2026-09-01 is 180,579 bytes, and 166,859 compressed:

| Request | Accepting gzip | Accepting `identity` only |
| --- | --- | --- |
| `HEAD`, `Range: bytes=0-` | 200, compressed, length 166,859 | 200, length 180,579 |
| GET, `Range: bytes=0-0` | 206, compressed, `bytes 0-0/166859` | 206, `bytes 0-0/180579` |
| GET, `Range: bytes=90000-90999` | 206, compressed, `bytes 90000-90999/166859` | 206, `bytes 90000-90999/180579` |

A browser always asks the second way. The Fetch standard adds
`Accept-Encoding: identity` to every request that carries a `Range`, and page
code cannot change that header, because only the browser may set it. Chromium
sent `identity` with all three against the live site and got the right-hand
column, so the engine reads a year file's own bytes and opens it at its true
length, and the spec's host compresses nothing. A request with no `Range`, such
as a day file fetched whole, does come back compressed, and the browser unpacks
it before the engine sees it.

**One case is not covered: a deploy inside one read.** A deploy that lands between
a read's first request and its last gives the file a new ETag mid-read, and the
read's next range names the ETag it began with, so Pages sends the whole file. A
read takes about 11 seconds on a slow mobile link, and a deploy came about every
85 minutes (17 deploys in the 24 hours to 2026-10-01 02:00 UTC), so about 1 read
in 500 on such a link is caught (ESTIMATE), and fewer on a fast one.

**What it costs: a page that reads one year file twice fetches it twice.** The
engine keeps nothing of a file it dropped, and the browser holds nothing at the
new address, so a second read of the same month asks for the same ranges again:
243,046 bytes in 9.0 seconds on the slow link measured, against 15.1 seconds for
that month's own file fetched whole
([the measurement](../../reference/benchmarks/what-a-month-out-of-a-year-file-costs.md)).

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

**The device keeps one content-named engine cache.** The client build reads
Vite's manifest from the engine entry through its imports, dynamic imports and
assets. It writes a private generated module for the service-worker build,
including the anonymous JavaScript chunks; a filename search for `duckdb`
would miss them. The sorted content-named paths determine the cache identity,
not the site's build date. A deploy with those same paths keeps the engine.

The service worker answers those same-origin assets from this cache first and
keeps successful complete responses after their first real request. It does not
prefetch the engine. Activation drops older engine caches, while the retirement
switch clears this cache with the other project-owned caches. Cache-storage
failure leaves the network response usable. Ledger files and the off-origin
Parquet add-on do not enter this cache. The browser test updates the real worker
while leaving engine files unchanged, with HTTP caching disabled, and requires
no repeated engine download and successful offline reads.

**None of it is first-load.** `ledger.ts` reaches the engine only through a
dynamic `import()`, and the engine reaches its package, its wasm and its worker
the same way. `frontend/scripts/bundle-gate.mjs` holds that: it follows every
static import from each page's own module, and fails when a file on that path
carries the package's name or the name of its wasm or its worker. It names the
file, not the page.

Checked 2026-09-28 against a build with deliberate static imports of the
package and its wasm, and a `slice()` call from the front page, reverted afterwards. That build broke in its prerender (next paragraph), so the gate
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

**No test downloads the add-on.** `frontend/scripts/setup-duckdb.ts` prepares
the one cache all worktrees share under the user's home directory:
`.duckdb/extensions/<host>/<runtime version>/<platform>/`. It derives the runtime
version and platform from the installed engine, not from a second version pin.
Playwright's global setup checks that file without downloading. The shared
browser context fixture answers the worker's add-on request from the same bytes.
Tests of HTTP caching use their own local add-on host, because a routed context
disables HTTP caching.

CI restores a cache named by the installed package, runtime and platform before
any frontend test or build. A miss runs the explicit setup command. The weekly
main-branch refresh downloads the current file and saves a new cache entry under
that version's prefix, so normal runs restore the newest prepared copy without
depending on the add-on host. See [the gate commands](../../how-to/run-the-gates.md#the-frontend-gates).

## Design rationale

**The door is split so a Node test can load its logic.** The states, the index
guard, the address, the page keeper and the query sit in modules that import
nothing tied to one environment and take a byte source and an engine as
arguments. `ledger.ts` binds the published site, which needs `$app/paths`;
`ledger-disk.ts` binds the disk under `$lib/server/`, where SvelteKit refuses a
browser import. So `frontend/tests/ledger-door.spec.ts` drives the real reader
over recorded responses and over the disk, with no browser or network download.
The engine it drives takes each
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

**A year file is read by byte range, and a day or month file is fetched whole.**
A year file holds twelve months, so fetching it whole to draw one month pays for
eleven nobody asked for: about twelve times the month's own file. A day file is
small. A month file read by byte range drew sooner on the slow link measured, 9.4
seconds against 15.1, but it asks for 12 round trips where its whole fetch asks
for one, and no faster link has been measured. Reading by range needs nothing the
engine does not already ship, so it adds no dependency.

**Each read of a year file has an address of its own, and pays for it.** A deploy
gives every file a new ETag, and at an address where the browser holds part of a
year file a read can be sent the whole file, about twelve times what the month's
own file costs. Keeping the year file registered for the page, to spare a second
read its bytes, would bring that back.

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

- [how-the-query-door-answers-a-written-question.md](how-the-query-door-answers-a-written-question.md) - the Records page entry point.
- [../../concepts/console-design/how-a-console-chart-gets-its-data.md](../../concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules a panel's data obeys.
- [../contracts/schemas.md](../contracts/schemas.md) - the hand copy of the index shapes and the test that binds it.
- [../../reference/benchmarks/what-a-month-out-of-a-year-file-costs.md](../../reference/benchmarks/what-a-month-out-of-a-year-file-costs.md) - what one month read by byte range out of a year file costs, read once, read again on one page, and across a deploy.
- [../../reference/site-weight.md](../../reference/site-weight.md#optional-assets) - deployed size, lazy downloads and cache assumptions.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the bundle gate that keeps the engine off the first load.
