# Console Payloads

**Last Updated**: 2026-09-10

The operator console reads twelve datasets. Nine of them come from `state/`,
which is never served, so each one crosses a trust boundary and each crossing
needs a contract (Rule #11). This page is the list. The machine-readable copy is
`backend/idhazh/contracts/console_payloads.py`, and it is the one a build reads.

Every one of them has a producer now. **Nothing reads them yet** - the console
still derives the same numbers at build time, and row 10 of
[../../../TODO/20260908-shell-and-fetch-plan.md](../../../TODO/20260908-shell-and-fetch-plan.md)
is where it stops. The producer landing first is deliberate: a consumer written
against a payload nobody has written is a consumer written against a guess.

## The twelve

Every path below is under `frontend/public/`. Every schema is under `schemas/`.

| Dataset | Reader it replaces | Published to | Schema |
| --- | --- | --- | --- |
| Verdict band | `console-shell.ts` `consoleShell` | `console/band.json` | `console-band` |
| Telemetry rows | `payload.ts` `telemetryRows` | `telemetry/<YYYY-MM>.csv` | `public-telemetry` |
| Item health | `payload.ts` `itemHealthRows`, `itemHealthForDay` | `telemetry/<YYYY-MM>.csv` | `public-telemetry` |
| Eval rows | `payload.ts` `evalRows` | `scores/<YYYY-MM>.csv` | `public-eval` |
| Feed results | `payload.ts` `feedResults` | `feed-health/<YYYY-MM>.csv` | `public-feed-health` |
| Run manifests | `payload.ts` `loadManifests` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Published items | `payload.ts` `publishedItems` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Published charts | `payload.ts` `publishedCharts` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Day metrics | `payload.ts` `dayMetrics` | `day-metrics/<YYYY-MM>.json` | `day-metrics` |
| Machine counters | `runtime-counters.ts` `loadMachineCounters` | `machine/<YYYY-MM>.csv` | `runtime-counters-row` |
| Span rollup | `span-rollup.ts` `loadSpanRollup` | `span-rollup/<YYYY-MM>.csv` | `span-rollup-row` |
| Source health | `payload.ts` `sourceHealthView` | `source-health.json` | `source-health-view` |

**Twelve datasets, nine schemas.** Three console reads answer off the run-day
row and two off the telemetry shard. That is not a shortcut: `loadManifests`,
`publishedItems` and `publishedCharts` share a key, a window and a producer, and
two of them open a day payload of hundreds of kilobytes to take one integer out
of it. `itemHealthRows` reads the census the telemetry shard already projects,
so a second projection of it would be two schemas for one row.

## What may not cross

A projection cuts named cells out of a wider ledger row, and the list of what it
cuts is the trust boundary. It is checked at **import**, so a forbidden field on
a model stops the process rather than reaching the published tree.

| Shape | Refuses | Why |
| --- | --- | --- |
| `public-telemetry` | `canonical_url`, `url_key`, `detail` | Two identify the page rather than the measurement; `detail` is diagnostic free text that can quote a fetched body |
| `public-eval` | `url_key`, `source_url`, `title` | Two are the article's address; `title` is `UntrustedLine` on `EvalRow`, so it is fetched text |
| `public-feed-health` | `endpoint_key` | It is the configured feed URL hashed, and an address hashed is still an address |

**An empty list is a real answer, and it is stated rather than left blank.** Six
shapes forbid nothing. `public-run-day` and `console-band` are not projections
of a ledger row at all - one is a reduction of two documents to counts, the
other a set of sentences the pipeline composed about its own run - so the
refusal is structural: a fetched string has no field to arrive in. `day-metrics`,
`runtime-counters-row`, `span-rollup-row` and `source-health-view` are published
whole, because every cell on each is a count or a duration of our own work.

`detail` is the one name that is refused on one shape and kept on another, and
that is deliberate. On `ItemHealthRow` it can quote article text. On
`FeedHealthRow` the same name says in terms that it is "our own one-line reason.
Never the response body", capped at 200 characters, and the console prints it
beside a failing feed - a failure a reader can see but not read is a bar with no
label.

## Retention

## The producers

Seven modules under `backend/idhazh/`, one dataset each, all called from
`cli.stage_assemble` at the publication step. None of them spells a path, a
write rule or a prune of its own: `publish_console.py` owns those and every
producer obeys the same three rules from the same place.

| Producer | Writes | Reads |
| --- | --- | --- |
| `publish_console_band.py` | `console/band.json` | the run-day shards it wrote, `state/feed-health/`, one item-health shard, one day-metrics record, the counters file |
| `publish_scores.py` | `scores/<YYYY-MM>.csv` | `state/scores/<YYYY-MM>.csv` |
| `publish_feed_health.py` | `feed-health/<YYYY-MM>.csv` | `state/feed-health/<YYYY-MM>.csv` |
| `publish_run_days.py` | `run-days/<YYYY-MM>.json` | one month of committed `run.json` and `digest.json` |
| `publish_day_metrics.py` `publish_public` | `day-metrics/<YYYY-MM>.json` | one month of `state/day-metrics/<YYYY>/<MM>/` |
| `publish_machine.py` | `machine/<YYYY-MM>.csv` | `state/runtime-counters.csv` |
| `publish_span_rollup.py` | `span-rollup/<YYYY-MM>.csv` | `state/span-rollup/<YYYY-MM>.csv` |

`publish_telemetry.py` is the eighth and it predates this page. It keeps its own
path helper because `retention.prune_telemetry` deletes a shard through the same
function that writes one, and two spellings of `<month>.csv` would delete a
month nobody published and leave the published one behind.

### The three rules

**One month per run.** The run knows which month it appended to, so the daily
caller names that one and every other month is skipped without being read
(Rule #12). A month whose published file is **missing** is read anyway, which is
what makes a fresh clone, a deleted file and a first backfill all land.

**Only on a byte difference.** A re-derived month whose bytes match what is on
disk is not rewritten. Content, never a timestamp: a rebuild can carry identical
bytes and a new mtime, and a fresh checkout can carry a new mtime and identical
bytes, so a timestamp answers wrongly in both directions.

**Nothing outlives its knob**, and the two rules above have to agree about the
boundary. A month below `oldest_month_kept` is not resurrected by the
missing-file rule - without that clause the prune deletes a month, the next run
finds it missing and writes it, and the prune deletes it again, every run, for a
month no console window can reach. The oracle for this row caught exactly that:
six months of a twenty-month fixture were rewritten and re-deleted on the second
pass.

### The band is a reduction of the payloads beside it

`console-shell.ts` derives the band at build time from six committed ledgers and
inlines it into three prerendered documents. `publish_console_band.py` is the
same derivation, ported sentence for sentence, and row 10 deletes the
TypeScript one. Two things about where it reads from:

- **The runs, the site size and the article counts come from the run-day shards
 this run just wrote**, not from the day payloads. Re-reducing five months of
 day payloads is the walk those shards exist to remove, and reading them makes
 the band and the console arithmetically identical rather than merely intended
 to be.
- **The feed trouble comes from `state/feed-health/` through `discover.settled`,
 `discover.streak` and `discover.resting`** - the reducers the pipeline itself
 rested a feed by. A page running its own copy is how a console starts
 contradicting the run that produced it.

The window is `max(console.window_presets)`, which is the furthest back any
panel on any route can draw, and it is **anchored on the newest day found rather
than on today**: a clock anchor answers with nothing at all for a corpus that
stopped publishing three months ago.

### The allow-list has two copies and they are asserted equal

`REFRESH_PATHS` on the `Commit the day` step names what a rebuild owns after a
lost push race, and `COMMIT_REFRESH_PATHS['assemble']` in
`backend/tests/test_workflows.py` mirrors it and is asserted by exact list
equality. A payload absent from either builds locally and never reaches the
site. Both moved in the commit that added the producers, and so did the staged
path list on the same step.

**Every new payload root ships with a committed file.**
`.github/scripts/commit-and-push.sh` runs `git add "$@"` under
`set -euo pipefail`, so a path that does not exist aborts the whole commit step
and takes every sibling ledger staged in the same call with it.
`test_every_path_the_day_stages_exists_in_a_fresh_checkout` asks the working
tree for each one.

### What checks them

`idhazh validate-days` reads every payload back through the shape that wrote it,
for the months the run touched - and for every month on disk when it is asked
for the whole tree, which is the sweep `ci.yml` takes on a change that can move
a contract. Data hygiene belongs there and not in pytest (`CLAUDE.md`
section 13): it is the producer's own gate on what it just wrote, running where
the payload is.

## Retention

Seven of the twelve file by month, and a payload a run appends to with no age is
a directory that grows for ever (Rule #12). Each has a knob under
`observability` in `config/idhazh.json`, and every one of them has a **non-null**
default:

`public_telemetry_keep_months`, `public_scores_keep_months`,
`public_feed_health_keep_months`, `public_run_days_keep_months`,
`public_day_metrics_keep_months`, `public_machine_keep_months`,
`public_span_rollup_keep_months`.

All seven default to **14**, and 14 is not a round number. `console.max_window_days`
is 366, a 367-day inclusive read starting on the last day of a month can touch
fourteen month shards, and `ObservabilityConfig.refuse_windows_shorter_than`
refuses any of them set below that. **A shard deleted while a window preset can
still reach it blanks that panel silently**, because a month with no file reads
exactly like a month with no runs.

Three of the seven project a state ledger, and each is held **equal** to the
ledger it projects - `public_telemetry_keep_months` to
`item_health_full_grain_months`, `public_scores_keep_months` to
`scores_full_grain_months`, `public_feed_health_keep_months` to
`feed_health_keep_months`. Any other pair leaves either a published month
nothing can check against its source, or a source month the console has no copy
of to draw. The other four have no state ledger of their own: `run-days` reduces
the committed day payloads, `day-metrics` and `span-rollup` have no age on the
state side, and `machine` is where the month boundary is first drawn at all.

## What the console actually fetches, and what it still carries

Row 10 landed on 2026-09-09 and it did not move all twelve. It moved the two
that were bytes and the one the chain needed, and it left the rest inlined on
purpose.

| What | Where it comes from now | Why |
| --- | --- | --- |
| The band, the strip and the three carries | `console/band.json`, fetched by `console/+layout.ts` | The derivation had a second home in `frontend/src/lib/server/console-shell.ts`, over the ledger under `state/`. Two derivations of one verdict is two verdicts |
| The months list | the same payload | A page cannot ask for a month until it knows which months exist. On its own it would be a fifth serial hop before the first row (Carmack, 2026-09-08) |
| Telemetry rows | `telemetry/<YYYY-MM>.csv`, fetched on mount and on every widen | 3,414,043 of the document's 3,880,361 bytes, for panels most visits never scroll to |
| The other 28 payload keys | still inlined in the document | Together 97 KB. A fetch each breaks the four-hop cold-load ceiling for a twentieth of what one key cost |

**Measured 2026-09-09**, a developer machine / / node 24, one build
per arm on the real digest, `stat` on the built file:

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

`frontend/tests/console-cold-load.spec.ts` holds both facts. It counts the
longest run of requests that each had to wait for the one before it - the
document and the page's own fetches, never the module graph, because the module
graph's depth on any given run is a fact about how fast the machine ran. Two
readings that looked equivalent are not, and the difference is written up in that
file: grouping requests into waves lets one slow download absorb a whole serial
chain beside it, and it was proved wrong by this row's own oracle, where two
round trips added ahead of the telemetry took the real chain from three to five
and left the wave count at three.

### The band is drawn once, in `console/+layout.svelte`

The title, the strip and the band are the console shell and they live in one
component beside the load that fetches them. Each route renders its control and
its panels inside it. Three routes each drawing their own band is three copies
of one verdict, and the day two of them disagreed about which route is worst
there would be no way to say which was right.

The order on the page is title, strip, band, control, content, and it did not
move: the shell holds the operator surface and each route's panels sit one
element inside it, so `[data-surface="operator"]` still means the whole page.
Which tab is lit is read off the route rather than passed in by each page.

### How big the band is, and what makes it grow

The ceiling is **8 KB over the wire**, measured as
`gzipSync(readFileSync(path), { level: 5 }).length` and asserted in
`console-band.spec.ts`. Measured 2026-09-09, node 24, on the committed payload:
**791 gzipped bytes from 2,043 raw - 9.7 percent of the ceiling.**

Every fact on the payload but one is fixed: a set of sentences and counts about
one day. The one term that moves with the archive is the months list, at one
`YYYY-MM` string a month, and a list of dates with a shared prefix is what gzip
is best at. Modelled on the committed payload the same day:

| months | raw | gzip -5 | of the ceiling |
| ---: | ---: | ---: | ---: |
| 2 (today) | 1,559 | 736 | 9.0 percent |
| 12 (a year) | 1,659 | 763 | 9.3 percent |
| 120 (a decade) | 2,739 | 994 | 12.1 percent |
| 1,200 (a century) | 13,539 | 3,247 | 39.6 percent |

A century of publishing leaves the payload at two fifths of its ceiling, so the
months list needs no window of its own.

**Since 2026-09-10 the band has a second, tighter ceiling, and it is the one that
binds.** Row 18 gave `bundle-gate.mjs` a per-payload pass and named
`console/band.json` at **2,000 bytes** in `page_weight.payload_ceilings_bytes`,
against a measured 794 at `gzip -5`
([../../reference/measurements.md](../../reference/measurements.md)). So one
payload now carries two numbers: 8 KB asserted in `console-band.spec.ts` and
2,000 applied by the gate. Nothing fails today, and the century row above sits
between them - 3,247 bytes passes the ceiling the spec asserts and would fail the
one the gate applies. **It is unreachable either way**, because
`observability.public_telemetry_keep_months` caps the months list at 14, so the
growth the 8 KB was bought for cannot arrive. Which of the two is the ceiling is
nobody's decision yet; until it is taken, read the gate's.

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
have server loads; it goes when they go, which is the rest of
[../../../TODO/20260908-shell-and-fetch-plan.md](../../../TODO/20260908-shell-and-fetch-plan.md).
So the oracle asserts what is true and pins the gap rather than hiding it: the
band is ahead of every payload the page draws a panel from, and the only request
allowed in front of it is that one named file. Anything else of ours in front
turns the test red, and so does one more request of any kind. When the server
loads go the band becomes index 0 and both lines still hold.

**Four charts on `/console/` moved to the browser** - the run donut, the
per-article cost, the failure mix and the flow diagram. They were 143 KB of
finished SVG, which is what stood between the document and the bar after the
rows left. Each keeps a text form beside it, so a reader with no script loses
the picture and none of the numbers: the cost days are a list, the flow is a
stepped list with every count and share, the mix is its strip, and the donut is
its own sentence. `Chart` takes a `pending` line for the gap before anything
draws, because a box that is simply empty says nothing about which of the two
nothings happened.

**The band's months list is the union across all seven fetched series**, not the
run-day months alone. The field promised "every month a payload shard exists
for" and delivered one series' worth. They can differ: each series is pruned by
its own `observability.public_*_keep_months`, and the canary projects telemetry
over a wider span than its run-days. Measured on the canary the day it was
found, run-days held `2026-08` where the union holds `2026-07`, `2026-08` and
`2026-09` - two months of the page that would never have filled. Seven
directory listings and no file opened, each directory bounded by its own knob,
so it costs the same on any size of archive (Rule #12).

**The canary writes these payloads too, and it has to write them late.**
`build_canary_day.py --console-payloads-only` runs the same six producers
`idhazh publish` runs, called from `frontend/scripts/build-canary.mjs` straight
after it projects the telemetry. Earlier than that and the item-health rows, the
counters, the span rollup and the telemetry do not exist yet. Before this the
canary served no band at all, and every console route in the browser suite drew
the named absence while the suite reported a page that works.

## Design rationale

**The inventory is a page and a module, not a paragraph inside the producer.**
Before this, the list of what the console needs existed nowhere: the producer,
the consumer, the retention step and the drift gate would each have worked it
out again, and four independent derivations of one list is four chances to miss
the same entry. Naming it first is what makes a missing dataset fail at import
instead of at review. Fowler, 2026-09-08, plan-doc
[../../../TODO/20260908-shell-and-fetch-plan.md](../../../TODO/20260908-shell-and-fetch-plan.md)
row 8.

**Re-deriving it from the code found two datasets the plan's own table missed.**
`dayMetrics` and `loadSpanRollup` are console reads out of `state/` and were not
on the list of ten. Row 9 would have written ten producers and left two readers
with nothing to fetch. The table also recorded `telemetryRows` as reading
`state/telemetry/`; there is no such directory, and `TELEMETRY_ROOT` points at
`frontend/public/telemetry/`.

**Three shapes are published whole rather than projected.** The row asked for
one model per dataset with no published shape, and for `day-metrics`,
`runtime-counters-row` and `span-rollup-row` that would have produced a
projection field-for-field identical to its source - two schemas for one row,
which is what rejected alternative 2 refuses for telemetry. The refusal is the
same either way and it is written down either way; what changes is whether a
committed shard has one shape to validate against or two.

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
| Publish the state contracts unchanged and skip the forbidden-cell lists | The lists are the trust boundary. `PublicTelemetryRow` exists because a projection spelled as strings gains a cell by a one-word edit and nothing refuses it |

## See also

- [telemetry-series.md](telemetry-series.md) - the one projection that already
 existed, and how its shards are frozen.
- [../../concepts/month-partitions.md](../../concepts/month-partitions.md) - what
 closes a month, and what a late arrival does to a closed one.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - the
 property behind every window on this page.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #11 for the trust boundary,
 Rule #12 for the ages, section 11 for the stamps.
