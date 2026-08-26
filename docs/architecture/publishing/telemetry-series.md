# Telemetry Series

**Last Updated**: 2026-08-26

The console's interactive charts read a published projection of item health. They
never read `state/item-health/` directly.

## Published shards

`backend/idhazh/publish_telemetry.py` reads
`state/item-health/<YYYY-MM>.csv` and writes
`frontend/public/telemetry/<YYYY-MM>.csv`. The browser fetches these monthly
shards on demand as the operator pans the viewport.

The published columns are exactly:

`date, run_id, item_id, vertical, source_id, stage, outcome, code, source_words, summary_words`

These source-ledger columns never cross to the browser:

- `canonical_url`
- `url_key`
- `detail`

This is a trust-boundary rule, not a size trick. `detail` is diagnostic free
text, and the URL fields are not needed to draw failure rates or compression.

## What the model did - read at build time, never published

The console's `What the model did` section is not drawn from the published
shards. It is computed while the site is built, out of two private ledgers:

- `state/scores.csv` - one row per scored item.
- `state/item-health/<YYYY-MM>.csv` - one row per planned item per run.

Neither file is served and neither crosses to a browser. What reaches the page
is a count of that day's items, never a row and never a score. The derivation is
[frontend/src/lib/server/model-work.ts](../../../frontend/src/lib/server/model-work.ts),
which sits under `$lib/server/` so SvelteKit refuses to bundle it for a browser.
The wording of the labels is settled in
[../../concepts/design-system.md](../../concepts/design-system.md); this table
says only where each figure comes from.

| On screen | Counts | Read from |
| --- | --- | --- |
| Summaries today | rows the score ledger holds for the day | `scores.csv` |
| Marked "not sure" | rows in the lowest confidence band | `band` |
| Numbers not in the article | rows asserting a figure the article never gave | `unsupported_numbers` |
| "Maybe" told as fact | rows that turned the article's hedge into an assertion | `hedge_dropped` |
| Article read only in part | rows the scorer flagged as cut short | `truncation_flagged` |
| Copied, not rewritten | median of the larger of the two copying measures | `extractiveness`, `verbatim_run` |
| Time to write one | median milliseconds the model spent on one article | `summarize_ms` |
| Model minutes | every millisecond the model spent that day | `summarize_ms` |
| Failed | rows whose run ended in a failure | `outcome` |

`hhem` still decides the band and it never prints. A faithfulness score is a
value between zero and one, and no lever moves it - so it earns no column, and
its consequence, the band, gets one instead.

Two copying measures are read and one figure is printed: the larger of the two
per item, then the median over the day. They miss opposite things. A summary can
score low on scattered four-word overlap and still lift a whole paragraph, so
taking the larger cannot under-report copying, which is the only direction that
matters.

## Degrade rules for the model section

A day earns a row by having summaries - score rows, or a runtime that timed the
summarize stage. Everything else prints as absence rather than as zero:

- **No summaries that day**: no row at all, and a gap in the throughput candle.
  A row of zeroes reads as a day that went badly rather than one with nothing
  in it.
- **The scorer did not run**: the quality cells print `-` while the speed cells
  still print. The runtime measured the time; nothing measured the quality.
- **No health row for a scored day**: the speed cells and the failure count
  print `-`. Nothing wrote a millisecond down, so no millisecond is claimed.
- **A measurement that rounds away**: `<1`, never `0`. Zero would say the model
  ran for nothing.
- **The model changed**: one divider row carrying the date and the new id, and
  the candle drops its percent-shift sentence across that boundary. Two models
  over two article sets is two measurements, not a trend.

## Degrade rules

A missing or unparsable month draws a gap. The page stays alive and logs a
browser-console warning. It does not invent zeroes, because zero failed items and
no data are different facts.

The default page is also prerendered as SVG from the same projection. If
JavaScript never runs, the console still shows the current window and honest
empty states.

## See also

- [frontend.md](frontend.md) - the console view that consumes these shards.
- [../sources/item-health.md](../sources/item-health.md) - the private item-grain ledger.
- [../../concepts/design-system.md](../../concepts/design-system.md) - how a console figure is worded and printed.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - ledgers as records, logs as evidence.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #1 and Rule #11.
