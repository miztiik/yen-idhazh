# Who supplied the day, and which feeds failed

**Last Updated**: 2026-09-23

`/console/voices/` answers who supplied the day and how far each feed is
discounted. Three panels: the census of every source we may ask, the list of
every feed that failed, and what the truncation cap cost each source - that last
one has its own page, [console-truncation.md](console-truncation.md), because the
cap is said in four places across three routes.

Which panel sits on which route is [console.md](console.md); how any figure is
allowed to read is
[../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md).
Which of these surfaces follow the window control, and which do not, is
[which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md).

## Four facts about every source we may ask

Its heading on the page is `Sources we may ask, and what they yield`; "four
facts" is what the panel does rather than what it is called, and the phrase is
load-bearing because it is the argument against combining them into a score.

**One row per state, per fact, over the addresses a curator has left active.**
Permission, reading, retirement and the publishing record, and no cell combines
two of them. It is drawn from `frontend/public/source-health.json`, which the run
writes once a day, and the page renders that decision rather than making a second
one ([../sources/health.md](../sources/health.md)).

- **A table of states, not a chart.** Four categorical facts over 144 addresses,
 most of them in one state, is a tally - and a tally is a table. Every state is
 drawn whether or not it is empty, because a census that hides its empty states
 is a sample. The oracle asserts the drawn counts sum to the census, so a state
 that stopped being drawn cannot pass as a state nothing is in.
- **Every state says what it withholds while it holds.** `denied` withholds that
 source until a later run reads its rules, `unreachable` means the address is
 not asked at all, a rest withholds it until the probe, and a retirement
 withholds that address until its configured URL changes. A count with no cost
 beside it is a number nobody can weigh.
- **Then the sources held back, loudest state first.** Retirement and a refusal
 come before a rest, because a rest lifts itself and neither of those does.
 Capped at `console.source_rows`, with the tail in one sentence, exactly as the
 failure list is.
- **The curated title is not unique, so the row carries the id too.** Two feeds
 in this repository are both titled `Anthropic`, and the thing an operator edits
 is one configured address. The title alone drew two identical rows.
- **The publishing record is counts and never a rate while the record is short.**
 `collect.source_yield_min_complete_days` is 30 and the ledger is nine complete
 days deep, so the sentence prints what was offered, what was published and what
 a source lost, and says in the same breath that this is too short to read as a
 rate.
- **It does not follow the window control.** Permission, reading and retirement
 are read over the whole record, and the publishing record has a fixed span of
 its own. It declares no `data-windowed` surface for that reason, and its own
 spec asserts the span instead. On Voices that sentence matters more than it did
 on Pipelines: it sits beside two panels that DO follow the control, so the
 paragraph saying it ignores one is the only thing separating them.
- **Its population is smaller than the failure list's, and it says so.** The
 census counts the addresses a run may ask; the list below reads the whole
 ledger, tombstoned feeds included. Measured 2026-09-03, the 24 tombstoned
 sources in the item ledger were offered 560 addresses over the window and
 published none, so the smaller population loses no publication and stops the
 denominator counting sources nobody may ask.

**Nothing fetches it, so nothing stages it.** `frontend/public/source-health.json`
is read at build time by `sourceHealthView` in
`frontend/src/lib/server/payload.ts` and never by a browser, so it is not copied
into `frontend/static/` and `frontend/scripts/copy-visuals.mjs` is untouched. Its
path is derived from `DIGEST_ROOT` the way `INDEX_ROOT` is, so a canary build
reads the canary's own census.

**A missing or malformed view is a named absence, not a blank page.** The reader
is the same guard `loadDay` uses - `null`, a list, and an object with no source
list all parse cleanly and all three would reach the page as a section rendering
nothing - and a view that cannot be read costs one section and logs one line.

## Every feed that failed at least once, nearest to a rest first

Capped at `console.feed_rows` with the remainder in one sentence. **A feed with a
clean record is not in that list**: the operator came here to find what is
broken, and a list naming all 182 sources hides the 26 that are. The clean ones
are named behind a disclosure, with no bars and no order - a name is a fact, a
row in the broken list is a call to act.

The cap is applied on the server, because this list is inlined into the
prerendered document and the rows it drops cost the page nothing; the list
publishes `data-feeds-drawn` and `data-feeds-hidden` so an oracle can check that
the cap counted what it dropped. The failing rule matches `FeedHealthRow.failing`
in the contract exactly - a `200` that parsed to no entries counts as a failure,
a `robots.txt` refusal does not
([../sources/health.md](../sources/health.md)).

**The count beside a feed is its run of failures, not its lifetime total.** The
pipeline rests a feed on failures in a row ending at the newest read, so that is
the number the page prints. A source that failed twelve times in July and
answered this morning is healthy, and a lifetime total printed beside a rest
marker is a number the pipeline never used to rest anything. The rule is restated
on the read side in `frontend/src/lib/feed-health.ts`, which runs the same loop
`discover.streak` runs, so a test can drive it with rows it made up. Both read
the same evidence as well: `feedResults` settles the ledger to one row per feed
per run before any panel counts it, by the same rule `discover.settled` uses, so
a run a second attempt wrote down twice is one run on the page and one run in the
pipeline.

**Ranking follows the same fact:** nearest to a rest first, then by how much has
gone wrong in total, because a feed four failures into a five-failure rule is one
run from being dropped and a feed with more failures spread over a month is not.

**Each feed carries a target bar and a strip of days.** The bar's track is
`collect.availability_strikes_before_rest`, its fill is the run of failures, and
its marker sits on the threshold - the same `TargetBar` the truncation cap and
the minutes-per-visual rule draw with. The strip is one square a day over the
page's window, oldest to newest, on a single date axis every row shares, so
"broken since Tuesday" and "flaky all month" cannot draw the same picture. It
shrinks to fit its row rather than scrolling, because twenty scroll regions in
one column is not a list.

**Every square carries its whole day's tally as a sentence.** Colour is one
signal and never the only one, and the two outcomes that are not a verdict - a
polite refusal and a day nobody asked - take no verdict colour at all. The
squares that do are painted from the **fill ramp**, the same three tokens the run
strip uses, so the console holds one health ramp rather than two: a square this
small is a solid, and the band ramp is weighted to be read as type. `Last result`
stays free text, because it is the only human-readable cause on the page and is
never traded for a glyph.

**A ranked "ten most reliable feeds" is refused.** Every key it could rank on
ties: a feed is read once a run, so one that never failed has answered on every
run it was asked. A top ten of a hundred-and-fifty-way tie is charting a
constant.

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [console-truncation.md](console-truncation.md) - the third Voices panel: what the cap cost each source.
- [../sources/health.md](../sources/health.md) - the feed ledger these panels render, and the quarantine rule they mirror.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - why two of these read the whole record.
- [../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md) - how these panels are allowed to draw.
- [what-sits-above-every-console-route.md](what-sits-above-every-console-route.md) - the two Voices worst-state fragments on the tab strip.
