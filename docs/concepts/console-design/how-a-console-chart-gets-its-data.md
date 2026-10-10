# How a console chart gets its data

**Last Updated**: 2026-10-10

Seven rules about where a panel's bytes come from, and what a panel may never do to
get them. **They are settled by what the formats do, not by a benchmark**, and none
of them waits on a measurement (rule 7).

What a drawing may do is
[the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md).
Which shape a reading wants is
[the-mark-shapes-a-panel-may-reach-for.md](the-mark-shapes-a-panel-may-reach-for.md).
What must be true of telemetry when this workstream is done is
[../telemetry-intent.md](../telemetry-intent.md); these seven are how a panel meets
its N2, N3 and N5 without each panel deciding for itself.

**Each rule carries its reason, and the reason is the load-bearing part**
([`CLAUDE.md`](../../../CLAUDE.md) section 1). A rule whose reason has stopped
holding is a rule to change.

## The seven

### 1. The system is designed for every panel, never for one

The console draws dozens of charts across five routes and it will draw more. A
scale, a colour ramp, an axis or a reader written for one panel is a second system
that the next panel either copies by accident or forks on purpose, and a console
with two of anything is a console where a reader cannot tell which one is lying.

**So the deliverable of any charting work is the shared style and the shared
reader. The panel is the proof, never the product.** A change that ships one good
panel and no house style has bought one panel and left the next fifteen exactly
where they were.

This is the rule that decides scope arguments. "Just this panel for now" is only
allowed where the shared parts are written first and the panel is the thing that
exercises them.

### 2. The browser asks for what it draws, never for what exists

A panel names the columns it needs and the days it covers, and receives those. It
does not fetch a collection and throw most of it away.

**This holds for every collection, without exception and without a list.** Every tree
under `state/`, every panel, every route, and every collection added after this sentence
was written. It is a rule about how the reader is allowed to ask, not a rule about
any one dataset, so it needs no per-collection carve-out and gets none. A small collection is
not an excuse to fetch it whole: the collection that is small today is the one that grew
while nobody was watching it, and a reader written to slice stays correct through
that where a reader written to download does not.

The reason is the shape of the ledgers rather than any reading taken off them. A
collection grows every day; a panel draws a fixed number of marks. Downloading the collection
to compute the panel means the download grows with the archive while the drawing
does not, which is [`CLAUDE.md`](../../../CLAUDE.md) Guardrail #12 pointed at a
reader instead of a runner. **That argument does not depend on which collection it is** -
it is true of the largest and the smallest on the same grounds.

### 3. The engine ships once; the data ships on every view

A query engine is one file, fetched once and held in the browser cache. A collection is
fetched every time a panel draws it, by every reader, forever.

**That asymmetry, not the size of either, is why a query engine earns its bytes.**
An engine that turns any collection into a few kilobytes of answer costs its own size
once and saves the difference on every view after the first, across every panel on
every route. The saving is counted over the whole console rather than over the
panel that happens to arrive first - a reader picked for the smallest collection is a
reader the first large collection replaces, which is rule 1.

### 4. One module owns the reader

Every panel reaches its bytes through one module, and no panel imports a parser,
opens a socket or builds a URL itself.

The reason is the same one that gives the pipeline a single persistence door: an
engine stops being replaceable the moment a second module imports it, and a reader
that lives in fifteen panels is fifteen places to change when the collection's layout
moves. It also makes the swap in rule 3 a decision somebody can take later rather
than a rewrite they have to justify.

That module is the query door, and what it does with a request - the four answers,
which files a span reads, the stamp it reads and the one engine build - is
[../../architecture/publishing/how-the-query-door-answers-a-panel.md](../../architecture/publishing/how-the-query-door-answers-a-panel.md).

### 5. A columnar format is read by column

Parquet exists so that a reader can take three columns out of seventy and never see
the rest. A console query that selects everything has paid for a columnar format and
then read every column anyway.

So a panel's query names its columns and its date range explicitly. `SELECT *` is a
defect on this surface, not a shortcut.

Each eligible panel declares one `PanelQuery` under `frontend/src/lib/console/queries/`.
Its ledger, columns, structured predicates and span are independent of the drawing.
The native score ledger is `summary-quality-evals`; the older `scores` name and
word-count spellings are not new columns.

`queries/window.ts` owns the console's slice call and holds only the current
promise for a query's range. A changed window replaces that ask. The query door
still owns fetched files, index validation and the signed engine add-on.
An unavailable reach names no invented day and starts no slice.

### 6. A panel degrades; it never white-screens

A missing file, an empty file and a file whose day has been pruned are all normal.
The panel says what is not there, in a reader's words, and the rest of the route
draws.

This is [`CLAUDE.md`](../../../CLAUDE.md) section 12's fifth check applied per
panel rather than per page, and it matters more once a panel fetches its own bytes:
a build-time read fails the build, where a view-time read fails in front of a
person.

Ledger panels name their settled nothing inside the reserved frame:
`Nothing recorded.`, `Not published yet.`, or `Did not arrive.` Waiting has no
answer, number or fabricated bar. Only a failed read takes warning colour.
The route has one reserved standing and one delayed shimmer; retry asks only
for the failed record, not already usable siblings. Existing month-based
callers retain their treatment until their route migration removes it.

The standing says `Fetching the record.` while delayed reads are pending.
Size and timing studies are suspended by owner direction; the UI prints no
guessed engine-download figure and no absent reading holds the functionality.

The standing's state tally is pure. It imports no query engine, and completing
one answer does not restart the route's wait while another is pending. Ledger
frames share that one shimmer without drawing placeholder bars. With reduced
motion they keep a still frame.

The packed canary replays the machine producer's two actual writes. Each job
uses its own run, attempt, job, shard and `telemetry.silicon` producer. The clock
writer reads its saved probe and files one complete row; the ledger keeps that
later file, not a union of partial rows. Sixteen raw records become fifteen
jobs, with the probe fields and completion clocks retained and siblings intact.

### 7. None of these is gated on a measurement

Each of the six above follows from what the formats and the cache do, not from a
reading taken on one machine on one day. **A benchmark cannot make rule 1 more true
and cannot make rule 2 less true**, and asking for one before the work starts buys
a number that changes nothing and a week that changes nothing either.

Measurement is still owed where a number decides what gets built next
([`CLAUDE.md`](../../../CLAUDE.md) Guardrail #10). It is not owed for a structural
choice that has one correct side.

## Design rationale

**The engine question was settled twice, and the second answer is the one that
holds.** The first pass picked the small plain parser on the grounds that one panel
reading one small collection does not need SQL, and it was right about that panel and
wrong about the console. Rule 1 is why: designing the reader around the smallest
panel guarantees a second reader arrives with the first large one. Owner ruling,
2026-09-24.

## See also

- [../console-design.md](../console-design.md) - what a figure may say in words.
- [the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md) - what a drawing may do.
- [../telemetry-intent.md](../telemetry-intent.md) - what must be true of telemetry when the workstream is done.
- [../../../CLAUDE.md](../../../CLAUDE.md) Guardrail #12 - every read must have a fixed-size input.
- [../../architecture/publishing/console-payloads.md](../../architecture/publishing/console-payloads.md) - what the console reads today and where each payload comes from.
