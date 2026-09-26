# Plan 52 - Fifty panels move to the query door and six projections go

**Last Updated**: 2026-09-26
**Status**: **PLACEHOLDER. Not execution-ready and not startable.** It holds the
scope two earlier plans handed forward, so that work has an address instead of a
phrase. Nothing here is a row yet. **A worker must not pick this up.**

## What this file is for

Plans 50 and 51 both stop at a boundary and both call what lies past it "the
route plan". That phrase named no file, so a reader who went looking found
nothing - or worse, found `20260905-02-retire-the-route-name-plan.md`, which is
about something else entirely. This page is that file. Everything those two
plans defer arrives here, and they now link to it by name.

**This is a holding page, not a plan.** It has no Status Reckoner with rows in
it, no acceptance gates and no oracles, because none have been written. Turning
it into a plan is a `prepare-plan` pass over the material below, and that pass
has not happened.

## The intent this plan will serve

**A console panel should ask the question it wants answered, against the data
`state/` already holds, at the moment a reader looks at it.** Today most panels
cannot. A panel reads a file the build wrote in advance - a projection - so the
question it can ask was fixed by whoever wrote the projection, months earlier
and for a different reason. Nine of the redraws and seven of the new panels in
plan 51's section 2.10 exist only because that restriction goes.

The second half of the intent is subtraction. **A projection that outlives its
last reader is a file that can disagree with `state/`**, and one of them already
does: `frontend/public/machine/<YYYY-MM>.csv` joins `host-fingerprint` to
aggregated `item-health` rows, so it carries values neither collection holds
alone and either can move underneath it. Six such directories go, about 4.1 MB
leaves the published site, and each one leaves in the same pull request that
moves its last reader.

## What is already settled, so this plan does not re-argue it

| What | Where it was settled | What that means here |
| --- | --- | --- |
| The chart vocabulary - nine types, and a tenth is an escalation | Plan 51 section 2.6 | A row picks a type from that list. Minting a tenth is an escalation, not a row decision |
| The readout strip - one module, every chart, hover a keyboard can reach | Plan 51 section 2.7 | Every panel this plan moves uses it. No panel ships its own tooltip |
| The ten sufficiency gates, each decidable | Plan 51 section 2.8 | A panel passes them or the row says in one line why not |
| The screenshot gate and the panel capture group | Plan 51 section 2.9 | A moved panel joins the capture group in the row that moves it |
| **Every panel, and what each becomes** | **Plan 51 section 2.10** | Fifty-one panels, each ruled KEEP, REDRAW, REPLACE, DELETE or NEW by Susan on 2026-09-26, with the columns each queries and the chart it becomes. **That table is this plan's contract.** Panel 6b is delivered by plan 51's row 7 and is the one entry this plan does not own |
| The query door, and that the browser needs no collection list | Plan 51 section 2.2 | Rows here call the door. They do not extend it |
| Where a collection lives on disk, and how a period is addressed | Plan 50 sections 2 and 5.4 | A row reads through the published collection, never by building a path |

**Plan 51's rows 4 to 7 exist to make this plan cheap, not to be it.** By the
time this plan starts, the vocabulary, the strip, the gates and one worked
panel end to end are all in the tree.

## The shape this plan is expected to take

One row per console route. Each row moves that route's panels to the query
door, and **each row's scope line ends with the projection under
`frontend/public/` it deletes**.

| Route | Projection it deletes | Note |
| --- | --- | --- |
| `/console/machine` | `machine` | Panel 6b is already moved by plan 51 row 7; this row moves the rest of the route |
| the model route | `telemetry` | - |
| the last route out | `day-metrics`, `run-days`, `run-timeline`, `span-rollup` | Four at once, because they share their last readers |

`console/band.json` **stays**. It is the freshness header every route fetches
first, not a projection.

**A route is not done while the projection it fed survives.**

### What it is expected to cost, so nobody discovers it mid-flight

About **seventeen pull requests in total**, of which plan 51's rows 4 to 7 are
four. The redraws batch by the chart type each becomes - about four pull
requests, so one builder is edited once - and the new panels batch by which
`UNREAD_CELLS` group they read, so each batch moves one group of names into
`COLUMN_READERS` as one reviewable diff.

## What this plan inherits and must close

| # | Inherited from | What it is |
| --- | --- | --- |
| 1 | Plan 51 section 0, Hard scope - out | **Three of the five routes draw no panel id today.** The gates and the captures reach 26 panels on two routes until a row here wraps the other three. A row must do that before those routes can be judged |
| 2 | Plan 51, `echarts` | `echarts@^5.6.0` and sixteen importers stay installed while two grammars coexist. **The last row here uninstalls it**, and that deletion is the signal the plan is finished |
| 3 | Plan 50 row titled *The three stores the console's routes read become parquet* | `backend/utilities/migrate_to_parquet.py` carries "delete when every `state/item-health`, `state/scores` and `state/host-fingerprint` CSV is gone from `main`". **The first row here names it in its scope line** |
| 4 | Plan 50 row titled *`span-rollup` becomes parquet* | `migrate_span_rollup.py` carries the same shape of condition for `state/span-rollup`. Same treatment |
| 5 | Plan 51, telemetry-intent N7 and N8 | Neither gets its stone until the projections go. This plan is where they are answered |

## Open questions this plan starts from, rather than discovers

Both were found while writing plan 50, verified as out of its scope, and
recorded here so the first row of this plan begins with them already asked.

- **Is `scores` named for what it measures?** It is keyed per item, per run and
  per attempt. If what it scores is the feed rather than the item, the
  collection and its columns are misnamed, and no migration fixes that - a
  rename has to happen before or instead of the move.
- **Does `span-rollup` belong inside `item-health`?** The grains differ: per run
  and per stage against per item, so merging would repeat a span row once per
  item. **Measured 2026-09-25: two collections in one file save 24 bytes against
  two separate files.** There is no size argument for merging any pair of these,
  so if they merge it is a modelling decision and this plan has to make it.

## What must be true before this becomes a plan

1. Plan 50 has merged, so the query door and the four migrated collections exist.
2. Plan 51 rows 4 to 7 have merged, so the vocabulary, the strip, the gates and
   one worked panel exist.
3. A `prepare-plan` pass turns section 2.10 of plan 51 into rows, with the
   parallel group, the acceptance gates, the oracles and the decisions each row
   needs. **Until that pass runs, this page is a note and not a plan.**

## See also

- [`20260924-50-idhazh-gardener-plan.md`](20260924-50-idhazh-gardener-plan.md) - the collections, the door and the schedule this plan reads through.
- [`20260924-51-console-fetches-and-draws-its-own-data-plan.md`](20260924-51-console-fetches-and-draws-its-own-data-plan.md) - the vocabulary, the strip, the gates and the fifty-one panel verdicts that are this plan's contract.
- [`../docs/concepts/console-design.md`](../docs/concepts/console-design.md) - what the console is for.
- [`../docs/concepts/telemetry-intent.md`](../docs/concepts/telemetry-intent.md) - N7 and N8, which this plan answers.
