# Console Payloads

**Last Updated**: 2026-10-07
The operator console reads ten datasets. Nine of them are projected out of
`state/`, so each one crosses from a ledger into the site and each crossing
needs a contract (Guardrail #11). This page is the list. The machine-readable copy is
`backend/idhazh/contracts/console_payloads.py`, and it is the one a build reads.

Every one of them has a producer now. **Nothing reads them yet** - the console
still derives the same numbers at build time, and the row of the
shell-and-fetch migration that made the console fetch them is where it
stops. The producer landing first is deliberate: a consumer written
against a payload nobody has written is a consumer written against a guess.

## The eleven

Every path below is under `frontend/public/`. Every shape is a contract under `backend/idhazh/contracts/`.

| Dataset | Reader it replaces | Published to | Schema |
| --- | --- | --- | --- |
| Verdict band | `console-shell.ts` `consoleShell` | `console/band.json` | `console-band` |
| Telemetry rows | `payload.ts` `telemetryRows` | `telemetry/<YYYY-MM>.csv` | `public-telemetry` |
| Item health | `ledger-rows.ts` `itemHealthRows` | `telemetry/<YYYY-MM>.csv` | `public-telemetry` |
| Run manifests | `payload.ts` `loadManifests` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Published items | `payload.ts` `publishedItems` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Published charts | `payload.ts` `publishedCharts` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Day metrics | `payload.ts` `dayMetrics` | `day-metrics/<YYYY-MM>.json` | `day-metrics` |
| Machine counters | `machine-counters.ts` `loadMachineCounters` | `machine/<YYYY-MM>.csv` | `machine-shard-row` |
| Run timeline | `run-timeline.ts` `loadRunTimeline` | `run-timeline/<YYYY-MM>.csv` | `run-timeline-row` |
| Source health | `payload.ts` `sourceHealthView` | `source-health.json` | `source-health-view` |

**Two datasets left this table on 2026-09-16.** `scores/<YYYY-MM>.csv` and
`feed-health/<YYYY-MM>.csv` were published for fourteen months each and no route
ever fetched either - the console read both ledgers under `state/` at build time
and always did. Today `evalRows` reads the eval ledger's packed files and
`feedResults` the feed record's. The
published trees, their two projections and their two schemas are gone; the
ledgers stay. What that removes from this page is the twelfth dataset and the
twelfth reader, not a source the console needs.

**`source-health.json` is the one entry in that table nothing fetches**, and
that has not changed since the panels reading it moved to `/console/voices/` on
2026-09-14. `sourceHealthView` opens it at build time from a path derived off
`DIGEST_ROOT`; it is not in `copy-visuals.mjs`'s `CONSOLE_SERIES`, so it is never
staged into `frontend/static/` and never reaches the build. A
`page_weight.payload_ceilings_bytes` key naming it would therefore match nothing
and fail the bundle gate.

**Eleven datasets, eight schemas.** Three console reads answer off the run-day row
and two off the telemetry shard. That is not a shortcut: `loadManifests`,
`publishedItems` and `publishedCharts` share a key, a window and a producer, and
two of them open a day payload of hundreds of kilobytes to take one integer out
of it. `itemHealthRows` reads the census the telemetry shard already projects,
so a second projection of it would be two schemas for one row.

### The run timeline is a second cut of the census, and that is the point

`run-timeline/<YYYY-MM>.csv` is projected from the item-health ledger, which the
telemetry shard beside it also projects. It is not the two-schemas-for-one-row
case the paragraph above refuses: the telemetry shard is the census narrowed for
a browser and keyed by item, and this is the census **re-filed against a clock**
and keyed by run. Six of its durations are the census's own numbers under the
census's own names, and the two that are not - `start_offset_ms` and
`residual_ms` - are arithmetic no ledger holds. One account of each measurement,
filed twice, with the census as the source
([`run-timeline.md`](run-timeline.md)).

It keeps two months where every other series keeps fourteen, and
`observability.public_run_timeline_keep_months` is the knob. No window preset
reaches it - the panel draws one run and names it - so a third month would
publish the widest row this project writes to answer a question nobody can ask.
That is also why it is the one published series absent from
`ObservabilityConfig.full_grain_months`, which exists to stop a console window
outliving the shard it selects.

### A thirteenth shape is declared, and it is written now

`run-timeline-row` is the run timeline: one row an item, placed on the run's own
clock. It landed ahead of its producer on purpose, so the writers produce what
the chart reads rather than a shape the chart has to migrate, and it sat in the
table above's place as a declared shape with no writer until 2026-09-16.
`run_timeline.py` is that writer and the row above is the dataset.

What it holds and why it holds it is
[`run-timeline.md`](run-timeline.md). Two things about it belong here: it is
**published whole**, because nothing on it identifies a page, and it has no
`state/` counterpart, because the row is derivable from one month of the census
and a committed ledger would be a third copy of numbers git already holds.

## What may not cross

A projection cuts named cells out of a wider ledger row, and the list of what it
cuts is the trust boundary. It is checked at **import**, so a forbidden field on
a model stops the process rather than reaching the published tree.

| Shape | Refuses | Why |
| --- | --- | --- |
| `public-telemetry` | `canonical_url`, `url_key`, `detail` | Two identify the page rather than the measurement; `detail` is diagnostic free text that can quote a fetched body |

**An empty list is a real answer, and it is stated rather than left blank.** Six
shapes forbid nothing. `public-run-day` and `console-band` are not projections
of a ledger row at all - one is a reduction of two documents to counts, the
other a set of sentences the pipeline composed about its own run - so the
refusal is structural: a fetched string has no field to arrive in. `day-metrics`,
`machine-shard-row` and `source-health-view` are published
whole, because every cell on each is a count or a duration of our own work.

**One shape refuses anything, where three used to.** `public-eval` refused
`url_key`, `source_url` and `title`, and `public-feed-health` refused
`endpoint_key`; both went on 2026-09-16 with the trees they shaped. The cells
they guarded are on `EvalRow` and `FeedHealthRow` under `state/`. The scores
ledger now reaches the site whole, for the browser's query door, so `url_key`,
`source_url` and `title` do reach a browser there - as cells a panel reads as
data, out of a repository that was public all along
([how-the-query-door-answers-a-panel.md](how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door)).

## Data explorer route

The Data explorer route fetches the ledger registry at `config/ledgers.json`, then uses the query door to fetch only the indexes and data files its chosen ledgers and days require. Its two panels are `data-explorer-ask` and `data-explorer-rows`; the chart panel is later work.

## Retention

## The producers

Six modules under `backend/idhazh/telemetry/publish/`, one dataset each. None
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
| `console_band.py` | `console/band.json` | the run-day shards it wrote, the feed-health days over the widest window through `ledger.load_health`, the newest day's item-health rows and its day-metrics record, the host-fingerprint days over the widest window - all three ledgers through `ledger.load_days` - and the newest day's `run.json` |
| `run_days.py` | `run-days/<YYYY-MM>.json` | one month of committed `run.json` and `digest.json` |
| `day_metrics.py` `publish_public` | `day-metrics/<YYYY-MM>.json` | one month of `state/day-metrics/<YYYY>/<MM>/` |
| `machine.py` | `machine/<YYYY-MM>.csv` | one month of the item-health and host-fingerprint ledgers, through `ledger.load_days` |
| `run_timeline.py` | `run-timeline/<YYYY-MM>.csv` | one month of the item-health ledger, through `ledger.load_days` |

`scores.py` and `feed_health.py` were two more rows of that table until
2026-09-16. They folded a month of `state/scores/` and `state/feed-health/` into
`frontend/public/`, nothing ever fetched either file, and a mirror nobody reads
drifts from its ledger unwatched - so both modules went and `PROJECTIONS` is two
rows shorter.

`public_telemetry.py` is the seventh and it predates this page. It keeps its own
path helper because the gardener's `telemetry-aggregate` task finds a shard to
delete by the same `<month>.csv` name the helper writes, and two spellings of it
would delete a month nobody published and leave the published one behind.

`source_health.py` is the eighth. It writes `source-health.json`, the one entry
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

### The band is a reduction of the payloads beside it

`console-shell.ts` derives the band at build time from six committed ledgers and
inlines it into three prerendered documents. `console_band.py` is the
same derivation, ported sentence for sentence, and row 10 deletes the
TypeScript one. Two things about where it reads from:

- **The runs, the site size and the article counts come from the run-day shards
 this run just wrote**, not from the day payloads. Re-reducing five months of
 day payloads is the walk those shards exist to remove, and reading them makes
 the band and the console arithmetically identical rather than merely intended
 to be.
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

### The allow-list has one copy

`REFRESH_PATHS` on the `Commit the day` step names what a rebuild owns after a
lost push race, and it is read from
[`backend/idhazh/path_classes.py`](../../../backend/idhazh/path_classes.py) by the step that
prints it and by the workflow tests. It was a space-split string in the workflow
with a hand-written mirror in `backend/tests/workflows/`, asserted equal by exact
list order; two lists that can drift is one list too many, and a payload absent
from either builds locally and never reaches the site. The staged path list on
the same step still moves with a new payload root.

**Every new payload root ships with a committed file.**
`backend/utilities/commit_and_push.py` stages every path a job owns in one
`git add`, so a path that does not exist fails that call, stops the whole commit
step, and takes every sibling ledger staged beside it.
`test_every_path_the_day_stages_exists_in_a_fresh_checkout` asks the working
tree for each one.

### What checks them

`idhazh check-publication` reads every payload back through the shape that wrote it,
for the months the run touched - and for every month on disk when it is asked
for the whole tree, which is the sweep `ci.yml` takes on a change that can move
a contract. Data hygiene belongs there and not in pytest (`CLAUDE.md`
section 13): it is the producer's own gate on what it just wrote, running where
the payload is.

## Retention

The retained monthly copies have a configured age. A payload a run appends to with no age is
a directory that grows for ever (Guardrail #12). Every one of them has an age
that ends. Three are knobs under `observability` in `config/idhazh.json`, each
with a **non-null** default:

`public_run_days_keep_months`, `public_day_metrics_keep_months`,
`public_machine_keep_months`.

The telemetry copy is the `public-copy` series of
`config/gardener/telemetry-aggregate.json`, because the gardener task that folds
the ledger it copies is the thing that deletes it.

`ObservabilityConfig.refuse_windows_shorter_than` checks those settings against
the widest configured console read, and the gardener loader checks the
`public-copy` series. **A shard deleted while a window preset can
still reach it blanks that panel silently**, because a month with no file reads
exactly like a month with no runs.

The telemetry copy projects a state ledger and is held **equal** to the ledger
it projects: the `public-copy` series to the `full-grain` series of the same
declaration. Any other pair leaves either a published month nothing can check
against its source, or a source month the console has no copy of to draw. The
other copies have no state ledger of their own: `run-days` reduces the committed day
payloads, `day-metrics` has no age on the state side, and
`machine` is where the month boundary is first drawn at all.

**`public_scores_keep_months` and `public_feed_health_keep_months` were two more
until 2026-09-16.** They are refused by name now rather than ignored, because a
config file still spelling one is an operator believing a number nothing reads.
There is no successor to send them to: the `compact-summary-quality-evals` and `compact-feed-health`
declarations under `config/gardener/` govern the `state/` ledgers, which are
still there and keep their own ages.

## What the console actually fetches, and what it still carries

Row 10 landed on 2026-09-09 and it did not move all of them. It moved the two
that were bytes and the one the chain needed, and it left the rest inlined on
purpose.

| What | Where it comes from now | Why |
| --- | --- | --- |
| The band, the strip and the three carries | `console/band.json`, fetched by `console/+layout.ts` | The derivation had a second home in `frontend/src/lib/server/console-shell.ts`, over the ledger under `state/`. Two derivations of one verdict is two verdicts |
| The months list | the same payload | A page cannot ask for a month until it knows which months exist. On its own it would be a fifth serial hop before the first row (Carmack, 2026-09-08) |
| Telemetry rows | `telemetry/<YYYY-MM>.csv`, fetched on mount and on every widen | 3,414,043 of the document's 3,880,361 bytes, for panels most visits never scroll to |
| The other 28 payload keys | still inlined in the document | Together 97 KB. A fetch each breaks the four-hop cold-load ceiling for a twentieth of what one key cost |

**Measured 2026-09-09**, a developer machine / / node 24, one build
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

Every fact on the payload but one is fixed: a set of sentences and counts about
one day. The one term that moves with the archive is the months list, at one
`YYYY-MM` string a month, and a list of dates with a shared prefix is what gzip
is best at. Modelled on the committed payload the same day, re-serialised
compact, which is why the no-months row reads under the committed 777:

| months | gzip -5 | of the guardrail |
| ---: | ---: | ---: |
| 0 | 719 | 36.0 percent |
| 2 (today) | 726 | 36.3 percent |
| 14 (the retention bound) | 758 | 37.9 percent |
| 24 (two years) | 780 | 39.0 percent |

**The list cannot pass 14, and that is retention rather than a hope.** `months`
is the union of the published month shards, and each series drops a shard once
it is past its own window: the publishers trim theirs to
`observability.public_*_keep_months`, and the gardener's `telemetry-aggregate`
task trims the telemetry copy to its `public-copy` series. Every one of those is
14. So the whole growable part of this payload is the 32 bytes between
the first row and the third, and the served payload at its bound is about 809 -
40.5 percent of the guardrail, which needs no window of its own.

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

**Five charts on `/console/` are drawn in the browser** - the per-article cost,
the failure mix, the item time split, the flow diagram and the extraction yield.
There were four when this was measured: the run donut was the fourth, and it has
since been replaced by the run-yield panel, which is server-drawn inline SVG
rather than a browser chart. The four were 143 KB of finished SVG, which is what
stood between the document and the bar after the rows left; the figure has not
been re-measured because nothing turns on it. Each keeps its numbers in words
beside it: a readout strip under the four with a column per day, and for the
flow a stepped list below the page's stacking breakpoint and the day-by-day
table above it. What an empty box says until a chart draws, and after a download
that failed, is
[console-charts.md](console-charts.md#an-empty-chart-box-says-which-nothing-it-holds).

**The band's months list is the union across all five fetched series**, not the
run-day months alone. The field promised "every month a payload shard exists
for" and delivered one series' worth. They can differ: each series is pruned by
its own `observability.public_*_keep_months`, and the canary projects telemetry
over a wider span than its run-days. Measured on the canary the day it was
found, run-days held `2026-08` where the union holds `2026-07`, `2026-08` and
`2026-09` - two months of the page that would never have filled. Five
directory listings and no file opened, each directory bounded by its own knob,
so it costs the same on any size of archive (Guardrail #12).

**The canary writes these payloads too, and it has to write them late.**
`build_canary_day.py --console-payloads-only` runs the same four producers
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
published side incomplete. `TELEMETRY_ROOT` names `frontend/public/telemetry/`,
not a state directory.

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
itself.** Two jobs write a census row for every item - a work shard as the item
settles, and assemble over the whole day afterwards - and a panel that read both
would count every item of that day twice. A list keyed by item id draws one
story twice, which is how this surfaced: `MemoryBoard.svelte` threw on a repeated
key. The packing settles each day under the ledger's own key and preference in
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
writes its machine before its heaviest step and its clock after its last item,
and neither half repeats a cell of the other, so keeping one of two rows would
lose the other half. The clock step reads its own probe row back and files the
whole row again as a later write of the same work unit, and the union keeps the
later file ([../contracts/persistence.md](../contracts/persistence.md#the-two-identifiers)).
`machineRecord` in `frontend/src/lib/server/host-fingerprint.ts` reads the packed
days once, and the Hardware route hands the same rows to the fingerprints and to
`machine-counters.ts`, so a job's own clock sits beside its machine with no merge
in the frontend.

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
- [../../concepts/partitions.md](../../concepts/partitions.md) - what
 closes a month, and what a late arrival does to a closed one.
- [../../../CLAUDE.md](../../../CLAUDE.md) Guardrail #12 - every read must have
 a fixed-size input.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #11 for the trust boundary,
 Guardrail #12 for the ages, section 11 for the stamps.
