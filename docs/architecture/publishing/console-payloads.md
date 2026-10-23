# Console Payloads

**Last Updated**: 2026-10-23
The operator console reads native records as well as the remaining public
projections. Each crossing into the site needs a contract (Guardrail #11).
This page lists the public projections. The machine-readable copy is
`backend/idhazh/contracts/console_payloads.py`, and it is the one a build reads.

Every entry has a producer. The band is fetched first; the route rows own
the migration of their other readers onto native records.

## The remaining published projections

Every path below is under `frontend/public/`. Every shape is a contract under `backend/idhazh/contracts/`.

| Dataset | Reader it replaces | Published to | Schema |
| --- | --- | --- | --- |
| Verdict band | `console-shell.ts` `consoleShell` | `console/band.json` | `console-band` |
| Source health | `payload.ts` `sourceHealthView` | `source-health.json` | `source-health-view` |

**Two datasets left this table on 2026-09-16.** `scores/<YYYY-MM>.csv` and
`feed-health/<YYYY-MM>.csv` were published for fourteen months each and no route
ever fetched either - the console read both ledgers under `state/` at build time
and always did. Today `evalRows` reads the eval ledger's packed files and
`feedResults` the feed record's. The
published trees, their two projections and their two schemas are gone; the
ledgers stay. Removing a projection does not remove a source the console needs.

**`source-health.json` is the one entry in that table nothing fetches**, and
that has not changed since the panels reading it moved to `/console/voices/` on
2026-09-14. `sourceHealthView` opens it at build time from a path derived off
`DIGEST_ROOT`; it is not in `stage-publication.mjs`'s `CONSOLE_SERIES`, so it is never
staged into `frontend/static/` and never reaches the build. A
`page_weight.payload_ceilings_bytes` key naming it would therefore match nothing
and fail the bundle gate.

**Two remaining public shapes.** The band and source-health view have producers.
Pipelines reads item-health through the native query door. Its run clock is
derived from those rows in the browser, with no monthly public copy.

### The timeline is derived from native rows

[`run-timeline.md`](run-timeline.md) declares its clock arithmetic and missing
data rules. The query reads native item-health cells; no public timeline
contract, producer or retention knob remains. Native retention is unchanged.

## What may not cross

A projection cuts named cells out of a wider ledger row, and the list of what it
cuts is the trust boundary. It is checked at **import**, so a forbidden field on
a model stops the process rather than reaching the published tree.

**An empty list is a real answer.** `console-band` is a set of sentences and
named movement dates the pipeline composed about its own run: fetched text has
no field to arrive in. Source-health and the native run timeline describe
our own work, so they have no redaction projection.

**One shape refuses anything, where three used to.** `public-eval` refused
`url_key`, `source_url` and `title`, and `public-feed-health` refused
`endpoint_key`; both went on 2026-09-16 with the trees they shaped. The cells
they guarded are on `EvalRow` and `FeedHealthRow` under `state/`. The scores
ledger now reaches the site whole, for the browser's query door, so `url_key`,
`source_url` and `title` do reach a browser there - as cells a panel reads as
data, out of a repository that was public all along
([how-the-query-door-answers-a-panel.md](how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door)).

## Data explorer route

The Data explorer reads ledger files rather than another pipeline projection.
[What the Data explorer keeps and shares](data-explorer-state.md) owns its
registry refresh, browser questions, shared addresses and answer copies.

## The producers

Each dataset has its own module under `backend/idhazh/telemetry/publish/`. None
of them spells a path, a write rule or a prune of its own: `series.py` owns
those and every producer obeys the same three rules from the same place.

`stages.assemble.stage_assemble` calls none of them directly. It calls
`dispatch.publish_all`, and `dispatch.PROJECTIONS` is the one place the order is
written down - the tuple the dispatcher walks, so a projection listed there runs
exactly once and one that is not listed never runs. The dispatcher holds routing
and nothing else: it names each unit and hands over the roots, the month and the
day the run is publishing, and every projection's body stays in its own module
(CLAUDE.md section 1a).

| Producer | Writes | Reads |
| --- | --- | --- |
| `console_band.py` | `console/band.json` | native run manifests and state day-metrics over the widest window; native feed-health, item-health and host-fingerprint through the ledger door; native summary-quality-evals for checker movement |
| `day_metrics.py` | `state/day-metrics/<YYYY>/<MM>/<DD>.json` | the publication's day and manifest, with that day's native rows |

The band finds its newest manifest over the bounded named-month cover,
including the whole month of the plan being assembled. A delayed older plan
therefore cannot replace a newer published day in that month. Its subsequent
window and predecessor reads are anchored on the newest day found, not the
plan's date or the current clock. Discovery does not enter the following month.

Each native manifest keeps its `chart_evidence` without recomputing
or pooling it. Missing historical evidence stays null. The exact counts,
denominator and weighted rates are defined once in
[Where every drawn figure came from](where-every-drawn-figure-came-from.md#the-two-rates-and-why-both).
`RunManifest.read` validates the native JSON; the frontend's existing
`loadManifests` reader exposes the same evidence as
`chartEvidence`. Neither path needs a new chart or an extra source read.

`scores.py` and `feed_health.py` were two more rows of that table until
2026-09-16. They folded a month of `state/scores/` and `state/feed-health/` into
`frontend/public/`, nothing ever fetched either file, and a mirror nobody reads
drifts from its ledger unwatched - so both modules went and `PROJECTIONS` is two
rows shorter.

The retired public telemetry and timeline helpers are gone. The gardener
keeps native full grain and aggregate summaries, with no public-copy series.

`source_health.py` writes `source-health.json`, the one entry
in the table above that nothing fetches, and it sits here rather than beside the
digest because a feed's reliability is an observation about the run and not a
product surface.
### The three rules

**Only caller-named months are read.** The run knows which month it appended
to, so the daily caller names that one and every other month is skipped without
being read (Guardrail #12). A missing published file is rebuilt only when its
month is named; a fresh clone or historical repair must name the months to
publish.

**Only on a byte difference.** A re-derived month whose bytes match what is on
disk is not rewritten. Content, never a timestamp: a rebuild can carry identical
bytes and a new mtime, and a fresh checkout can carry a new mtime and identical
bytes, so a timestamp answers wrongly in both directions.

**Nothing outlives its knob**, and the named month list has to agree about the
boundary. A month below `oldest_month_kept` is not named - otherwise the next
run would write a month the console window can no longer reach. The oracle for
this row caught exactly that: six months of a twenty-month fixture were
rewritten and re-deleted on the second pass.

### The band reads native records

`console-shell.ts` derives the band at build time from six committed ledgers and
inlines it into three prerendered documents. `console_band.py` is the
same derivation, ported sentence for sentence, and row 10 deletes the
TypeScript one. Two things about where it reads from:

- **The runs and site size come from native `run.json`; published-item counts
 come from native `state/day-metrics`.** The band never opens `digest.json`.
 Public machine, run-days and day-metrics mirrors, their producers and knobs
 are retired. Native raw/compact state and the state day-metrics writer stay.
  `digest_assemble` materializes the larger of the configured discovery cover
  and two spans of native manifests and state day-metrics. Regeneration writes
  its own plan-date manifest before the band runs, so that date is the anchor
  and two spans include the farthest permitted predecessor. It no longer
  derives publication input windows from the deleted public-copy knobs.
- **The feed trouble comes from the feed-health ledger through `discover.settled`,
 `discover.streak` and `discover.resting`** - the reducers the pipeline itself
 rested a feed by. A page running its own copy is how a console starts
 contradicting the run that produced it.
- **`compaction_lag_days` and `rows_uncompacted` are handed in at 0 and have
 been since 2026-09-23.** Every writer files its own rows under the day those
 rows name, so a run that died three days ago left them in that day rather than
 in a ledger a later run had to drain. There is no backlog for either reading to
 count. They stay on the payload because a reader of an older day still finds
 them there, and a field removed is a contract break for a page nobody
 re-publishes.

**The band drew a line from those two readings until 2026-09-23, and it no
longer does.** A reading that cannot move is a line that says the same thing
every day, and an operator learns to read past it. **What the reader gives up**
is a "nothing is waiting to be folded" reassurance they could not have acted on.
A later change that can make the readings move again gets its line back with no
schema break, because the fields are still there.

The window is `max(console.window_presets)`, which is the furthest back any
panel on any route can draw, and it is **anchored on the newest day found rather
than on today**: a clock anchor answers with nothing at all for a corpus that
stopped publishing three months ago.

### The refresh paths have one declaration

`REFRESH_PATHS` on the `Commit the day` step names what a rebuild owns after a
lost push race, and it is read from
[`backend/idhazh/path_classes.py`](../../../backend/idhazh/path_classes.py) by the step that
prints it and by the workflow tests. It was a space-split string in the workflow
with a hand-written mirror in `backend/tests/workflows/`, asserted equal by exact
list order; two lists that can drift is one list too many, and a payload absent
from either builds locally and never reaches the site. The staged path list on
the same step still moves with a new payload root.

**Seed payloads support the first site build, not directory staging.**
`backend/utilities/publish_to_repo.py` indexes exact confirmed files, so a
declared output root need not exist in a fresh checkout. ASSEMBLE rebuilds the
complete derived set before publishing; failure publishes no partial set.
See [committing.md](committing.md) for the independent output declarations.

### What checks them

`idhazh check-publication` reads every payload back through the shape that wrote it,
for the months the run touched - and for every month on disk when it is asked
for the whole tree, which is the sweep `ci.yml` takes on a change that can move
a contract. Data hygiene belongs there and not in pytest (`CLAUDE.md`
section 13): it is the producer's own gate on what it just wrote, running where
the payload is.

### Recorded settings and checker movement

`settings_moved` and `checker_moved` are nullable records on the real
`ConsoleBand`; historic absent keys validate as `None`. The browser treats an
absent or malformed kind as unknown independently of the other.

The anchor is the newest native manifest day. For the widest configured window
W, each rule reads [T-(W-1), T], then walks backward at most W days to its own
nearest recorded predecessor. Settings compare each nonempty named input to
its newest earlier day holding that name. Multiple runs retain all values that
day; a revert is a change, but a later use of either value from a mixed day is
not. Historic joined flags are normalized by `PipelineInputs` first.

Checker movement reads `summary-quality-evals` through `day_metrics.read_score_rows`.
Whole `scorer_version` strings detect checker movement. Removing `metrics-`,
`bands=` and `lead=` segments identifies whether the scorer itself moved.
Only names, dates and the scorer-moved boolean reach the band, never hash values.
Both languages assert the same authored five-on-one-day expected fixture.

`settingsRules` returns Row2's real `ModelRule`; settings and checker events
remain independent, including two readouts on one date. The existing boundary
adapter chooses one settings-priority boundary. Score-only notes describe the
faithfulness scorer, not every checker change; a window wholly before coverage
makes no no-change claim.

## Retention

The three public mirror retention knobs are retired with their projections.
The native ledgers retain their own compaction declarations.

The gardener loader still checks native read floors. The `telemetry-aggregate`
declaration keeps its `full-grain` and `aggregate` windows and writes native
item-health summaries. It owns no public tree and deletes no public copy.

**`public_scores_keep_months` and `public_feed_health_keep_months` were two more
until 2026-09-16.** They are refused by name now rather than ignored, because a
config file still spelling one is an operator believing a number nothing reads.
There is no successor to send them to: the `compact-summary-quality-evals` and `compact-feed-health`
declarations under `config/gardener/` govern the `state/` ledgers, which are
still there and keep their own ages.

## What the console actually fetches, and what it still carries

The shell fetch migration began on 2026-09-09. Pipelines now reads native
query answers rather than either of the retired public month projections.

| What | Where it comes from now | Why |
| --- | --- | --- |
| The band, the strip and the three carries | `console/band.json`, fetched by `console/+layout.ts` | The derivation had a second home in `frontend/src/lib/server/console-shell.ts`, over the ledger under `state/`. Two derivations of one verdict is two verdicts |
| Pipelines measurements and run clock | declared native ledger queries and compact indexes | One source of recorded facts; no public telemetry or run-timeline copy |
| Reachable dates | the ledger indexes | The band no longer carries `months` |
| Remaining prerendered route inputs | each route's existing loader | Their movement belongs to that route, not the projection retirement |

**Historical shell migration, measured 2026-09-09**, a developer machine / / node 24, one build
per case on the real digest, `stat` on the built file:

| file | before | after |
| --- | ---: | ---: |
| `build/console/index.html` | 3,880,361 B | 302,681 B |

That is 92.2 percent off, and 106,919 bytes under the 400 KB the plan asked
for. It is an uncompressed measure and it does not replace the gzip
`page_weight` ceiling.

**The band's load is universal, not server-only, and the routes stay
prerendered.** At build time SvelteKit resolves the fetch against the staged
payload, so the band is real markup in all three documents and an operator on a
dead connection reads the verdict; in a browser the same code runs again on a
move between routes. `export const prerender = true` moved from
`+layout.server.ts` to `+layout.ts` and did not change.

**Which means the band costs a cold load no round trip at all, and that was
checked in a browser rather than reasoned from the code.** Measured 2026-09-10
on a developer machine / Chromium via Playwright against the real
build: a cold `/console/` makes 47 requests over 737,467 bytes, of which the
payloads are two telemetry shards and 303,306 bytes, and `console/band.json` is
not among them. **The chain is three round trips against the four-hop ceiling:
the document, then one shard, then the next.** `loadVisibleMonths` awaits each
month in turn, so a month is a hop and the single hop of headroom is one more
month, not one more file.

### The band is drawn once, in `console/+layout.svelte`

The title, the strip, the sentence that dates the record and the band are the
console shell, and they live in one component beside the load that fetches them.
The strip carries the days control: the shell draws it and the route holds it,
handing its window up through `window-slot.ts`. Each route renders its panels
inside the shell. Three routes each drawing their own band is three copies of
one verdict, and the day two of them disagreed about which route is worst there
would be no way to say which was right.

The order down the page is title, strip, completeness sentence, band, the
sentence about the span, the jump links, content. `console-band.spec.ts` holds
it, and
[what-sits-above-every-console-route.md](what-sits-above-every-console-route.md)
owns it. The shell holds the operator surface and each route's panels sit one
element inside it, so `[data-surface="operator"]` still means the whole page.
Which tab is lit is read off the route rather than passed in by each page.

### How big the band is, and what makes it grow

The guardrail is **2,000 bytes over the wire**, and it lives in
`page_weight.payload_ceilings_bytes` in `config/idhazh.json` and nowhere else.
`bundle-gate.mjs` applies it to the built payload, and nothing else restates it.
Measured 2026-09-10, node 24.12.0,
on the committed payload: **777 gzipped bytes from 1,799 raw - 38.9 percent of
the guardrail.**

**The band no longer carries a months list.** Native ledger indexes own
reachable dates. A copying before-validator drops only `months` from older
committed bands; every other unknown key remains an error. Settings and checker
changes are still bounded by the widest window, with one equal-length
predecessor search for each kind. The figures above describe the older shape,
before the movement fields and the retirement.
The owner suspended size studies on 2026-10-10; this change keeps the existing
ceiling rather than deriving a new value from a measurement.

**The band carried two numbers for two days, and the fix was to delete one.**
`console-band.spec.ts` asserted `8 * 1024` of its own from 2026-09-08, sized for
a months list that could grow without limit. Row 18 then gave `bundle-gate.mjs` a
per-payload pass and named `console/band.json` at 2,000 in
`page_weight.payload_ceilings_bytes` on 2026-09-09. Nothing went red, which is
the whole hazard: the spec's own century model produced 3,247 bytes, a case that
passed the number the spec asserted and failed the number the gate applied, and
the two disagreed fourfold with no test able to say so. On 2026-09-10 the spec's
constant was deleted and the spec now reads the config key (Guardrail #6), and its
century model was replaced by the retention bound above, because a century of
months was never reachable. The gate's number did not move: at 2.47 times the
bounded payload it was already a guardrail under the ruling of that day
([../../reference/site-weight.md](../../reference/site-weight.md#page-and-payload-guardrails)).
On 2026-10-03 the spec's two size checks were deleted as well. Both read the
payload each pipeline run rewrites, so a run alone could turn them red, and
both answers already have a home: the bundle gate measures the built file
against the key, and `backend/tests/test_console_payloads_producer.py` holds
each series to its own retention setting.

### The band is the second payload, not the first, and the reason is not ours

Row 11's oracle asked for the band to be the first request the console issues
after the document and the entry bundle. It is not, and the measurement says
why. Two entries behave differently:

- **A cold document carries the band already.** The route is prerendered and the
 load is universal, so SvelteKit resolves the fetch at build time and writes the
 answer into the HTML. Nothing is requested. Measured 2026-09-09 on the canary
 build: the payload requests on a cold `/console/` are the document, then
 `telemetry/2026-07.csv` and `telemetry/2026-08.csv`, and no `band.json` at all.
- **A move into the console from another page fetches it, second.** Measured the
 same day: `console/__data.json`, `console/band.json`, `telemetry/2026-07.csv`,
 `telemetry/2026-08.csv`.

`console/__data.json` is SvelteKit's own file for the route, holding what the
three `+page.server.ts` loads return. The client router **awaits** it before it
runs a single universal load
(`@sveltejs/kit/src/runtime/client/client.js`, `server_data = await load_data(...)`
ahead of the branch loaders), so the band's fetch does not start until that file
has fully arrived. It is 31,354 bytes, 6,520 gzipped, against the band's 1,904
and 779. The verdict is therefore a second round trip on that entry, not the
first, which is short of what row 11 decision 2 promised.

**Nothing in row 11 can move it.** The file exists because the console routes
have server loads; it goes when they go, which is the rest of the
shell-and-fetch migration.
So the oracle asserts what is true and pins the gap rather than hiding it: the
band is ahead of every payload the page draws a panel from, and the only request
allowed in front of it is that one named file. Anything else of ours in front
turns the test red, and so does one more request of any kind. When the server
loads go the band becomes index 0 and both lines still hold.

**Published-ledger charts on `/console/` derive and draw native answers in the
browser.** Failure mix counts recorded rows; the item time split uses one
complete clock cohort; reading and writing cost keep independent rate pairs.
Their declared questions, native helpers and readouts own those meanings, not
an engine option builder. Private build-time inputs keep the boundary named in
[console.md](console.md#rendering-direction). What an empty box says until a
chart draws, and after a download that failed, is
[console-charts.md](console-charts.md#an-empty-chart-box-says-which-nothing-it-holds).

**The band's months list names telemetry only.** The native ledgers have their
own indexes; retired public mirrors do not contribute months. The read names
the configured months and opens no telemetry row file.

**The canary writes these payloads too, and it has to write them late.**
`build_canary_day.py --console-payloads-only` runs the remaining native-backed producers
`idhazh publish` runs, called from `frontend/scripts/build-canary.mjs` straight
after it projects the telemetry. Earlier than that and the item-health rows, the
counters, the span rollup and the telemetry do not exist yet. Before this the
canary served no band at all, and every console route in the browser suite drew
the named absence while the suite reported a page that works.

## Design rationale

**The inventory is a page and a module, not a paragraph inside the producer.**
Before this, the list of what the console needs existed nowhere: the producer,
the consumer and the retention step would each have worked it out again, and
three independent derivations of one list is three chances to miss the same
entry. Naming it first is what makes a missing dataset fail at import instead of
at review. Fowler, 2026-09-08, during the shell-and-fetch migration.

**Derive the inventory from actual readers.** A missing reader leaves the
published side incomplete. Native console reads name their ledger and its
compact indexes, not a retired public root.

**Publish a shape whole when no field needs projection.** A second model with
the same fields would duplicate validation and create another place to drift.

**A dataset's entry names its producer and its reader function, never its
route.** Row #13 moved four panels from `/console/` to `/console/voices/` on
2026-09-14 and not one row of the table above changed: `feedResults`,
`itemHealthRows`, `sourceHealthView` and `shardDays` are called from a different
`+page.server.ts` and read the same files by the same rule. That is the table
working rather than the table being lucky. A route column would have gone stale
on a change that moved no data, and it would have had to be maintained by
whoever moved a panel rather than by whoever moved a payload.

**A console reader takes one row per key from the packing, and settles nothing
itself.** A work shard and assemble can both file a census row for the same item.
Counting both would count the item twice. The packing settles each day under
the ledger's own key and preference in
`backend/idhazh/ledger/keys.py` before it writes the day's file, so
`itemHealthRows`, `evalRows` and `feedHealthRows` in `frontend/src/lib/server/ledger-rows.ts` read
days that already hold one row per item per run, one per scored measurement, or
one per feed per run. Those readers hold no key and no rule: a second settle
there would be a second rule for one question. `feedResults` still passes the
feed rows through `settled` from `frontend/src/lib/feed-health.ts`, the same rule
`discover.settled` runs, so on a packed day it keeps every row.

**The rows stop at the newest packed day, though every window ends on the
newest published day.** A day is packed once a whole day has passed since it
ended, so the day a run is still publishing - the only day a repeated row ever
reached a panel - is never read; it is the newest day of every window, and every
panel built on a packed record draws it with nothing in it.
Measured 2026-09-23 over the committed ledgers, before they moved: thirteen
folded census days held 0 repeated keys between them and the unfolded day held
240 repeats over 240 items, and the eval ledger's unfolded day held 441 rows over
237 keys. **Each route says where its panels stop**, in one plain line under its
introduction, when a record is not packed yet, did not load, or stops two or
more days before the newest published day (`recordNotes` in
`frontend/src/lib/console/recording.ts`). A record that did not load because a
packed file or a packed day is missing says which, because each has its own fix
([the four faults](how-the-query-door-answers-a-panel.md#when-a-file-is-missing)).
A record whose packed rows stop before the open window says the day, month or
year they are from, as its index names it, and that the page cannot tell a
quiet stretch from a fault. It names the narrowest window the control offers
that reaches back to them, and only when one does, because an instruction that
does not work costs a click. A record whose route already prints its
"Measurement is off" line gets no second explanation: that line is worded for
the open window too, so it says the window holds nothing recorded and names the
window that reaches back to the last recorded day, without naming a day the
window does not show. A record packed as far as
the day before the newest published day, which is normal running, gets the
quietest line, last: that day is not shown yet, and that is normal. Each route
writes its notes once for each window the control offers, and the page picks the
open one.
A record read whole can still be short, and says so in a plain line too: a day
its packing recorded lost has no record, and a file it set aside unread holds
rows no panel draws, so that line names the folder a person reads them in. A
recording note never counts a lost day as a day before the recording started:
the instrument ran that day, so the day dates its start. It dates a start only
where the route's read reaches back to the oldest named day of each record the
instrument draws on, the read's `first` beside `lastRows`, and prints it only in
a window that shows that day, so an instrument that ran before the read is never
said to start in it, and no day before the read is opened to learn it.

**Packing settles rows per day, not over the whole requested window.** This
scope preserves historical rows; it does not define measurement identity.
The [observation key](../../concepts/evaluation.md#the-ledger) has no date, so
the same measurement filed on two days is kept under each, and a window that
spans both shows it once per day.

**A key with no preference keeps the first row it saw.** That is what the
backend does with a key `ledger.preference_for` has no rule for, and the ledger
bears out the reason: all 204 repeated keys of the publishing day agreed cell
for cell. Only `ITEM_HEALTH_KEY` carries a rule, because its two writers
genuinely differ - assemble cannot name the job that ran the item.

**A job's two halves in the machine record are one row once packed.** A job
writes its machine before its heaviest step and its clock after its last item.
The clock step reads its own probe row back and files the whole row again as a
later write of the same work unit. Packing keeps that later file
([../contracts/persistence.md](../contracts/persistence.md#the-two-identifiers)).
The Hardware route asks the native questions in
`frontend/src/lib/console/queries/machine.ts`. Helpers in
`frontend/src/lib/console/machine/records.ts` pass the selected host and item
cells, with the exact `run-shards` counts, to
`frontend/src/lib/console/machine/counters.ts`.
The four-cell join keeps a job's own clock beside its machine. These Hardware
helpers do not merge the two writes or read private manifests.

**Row 10 measured before it moved anything, and the measurement changed the
order of the work.** The plan read the 32 inline SVGs as "139 KB of 3,726 KB, so
this is not where the bytes are". That is true of the total and wrong about the
margin: dropping the telemetry rows alone leaves 466,318 bytes, which is still
over the 400 KB bar, and the drawn charts are the only 143 KB left to take. The
plan's own ordering would have landed a change that missed its oracle by 56 KB
and looked finished. The same measurement is why 28 payload keys were left
inlined - 97 KB spread over four more serial hops buys nothing and breaks
decision 2's cold-load ceiling. Measured 2026-09-09.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| One payload per console read, twelve files | Three of the reads answer off one day and two off one census. Splitting them costs three fetches to answer one question and puts the same integer in two files |
| Leave the nine `state/` reads prerendered and fetch only telemetry | That makes the window control decorative on every panel but one, and it is a special case where the plan says there are none |
| Fetch all twelve datasets in row 10 | The remaining 28 payload keys are 97 KB between them. Four more serial hops for a twentieth of what one key cost, and past the four-hop cold-load ceiling (Carmack, 2026-09-08) |
| Keep the band a server load and read `band.json` from disk at build time | It would meet the oracle - the band is 1,392 bytes - and leave the console a page only a finished build can produce. The point of the payload is that a shell can ask for it |
| Fork a telemetry schema for `itemHealthRows` | Two schemas for one row, and the committed shards validate against the existing one |
| Skip the forbidden-cell lists on browser payloads | The lists are the trust boundary. A projection spelled as strings gains a cell by a one-word edit unless its shape refuses it |

## See also

- [telemetry-series.md](telemetry-series.md) - the one projection that already
 existed, and how its shards are frozen.
- [../../concepts/partitions.md](../../concepts/partitions.md) - what
 closes a month, and what a late arrival does to a closed one.
- [../../../CLAUDE.md](../../../CLAUDE.md) Guardrail #12 - every read must have
 a fixed-size input.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #11 for the trust boundary,
 Guardrail #12 for the ages, section 11 for the stamps.
