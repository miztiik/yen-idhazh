# Console Payloads

**Last Updated**: 2026-09-09

The operator console reads twelve datasets. Nine of them come from `state/`,
which is never served, so each one crosses a trust boundary and each crossing
needs a contract (Rule #11). This page is the list. The machine-readable copy is
`backend/idhazh/contracts/console_payloads.py`, and it is the one a build reads.

## The twelve

Every path below is under `frontend/public/`. Every schema is under `schemas/`.

| Dataset | Reader it replaces | Published to | Schema |
| --- | --- | --- | --- |
| Verdict band | `console-shell.ts` `consoleShell()` | `console/band.json` | `console-band` |
| Telemetry rows | `payload.ts` `telemetryRows()` | `telemetry/<YYYY-MM>.csv` | `public-telemetry` |
| Item health | `payload.ts` `itemHealthRows()`, `itemHealthForDay()` | `telemetry/<YYYY-MM>.csv` | `public-telemetry` |
| Eval rows | `payload.ts` `evalRows()` | `scores/<YYYY-MM>.csv` | `public-eval` |
| Feed results | `payload.ts` `feedResults()` | `feed-health/<YYYY-MM>.csv` | `public-feed-health` |
| Run manifests | `payload.ts` `loadManifests()` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Published items | `payload.ts` `publishedItems()` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Published charts | `payload.ts` `publishedCharts()` | `run-days/<YYYY-MM>.json` | `public-run-day` |
| Day metrics | `payload.ts` `dayMetrics()` | `day-metrics/<YYYY-MM>.json` | `day-metrics` |
| Machine counters | `runtime-counters.ts` `loadMachineCounters()` | `machine/<YYYY-MM>.csv` | `runtime-counters-row` |
| Span rollup | `span-rollup.ts` `loadSpanRollup()` | `span-rollup/<YYYY-MM>.csv` | `span-rollup-row` |
| Source health | `payload.ts` `sourceHealthView()` | `source-health.json` | `source-health-view` |

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

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| One payload per console read, twelve files | Three of the reads answer off one day and two off one census. Splitting them costs three fetches to answer one question and puts the same integer in two files |
| Leave the nine `state/` reads prerendered and fetch only telemetry | That makes the window control decorative on every panel but one, and it is a special case where the plan says there are none |
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
