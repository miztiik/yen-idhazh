# Console Charts

**Last Updated**: 2026-10-08

**Known noncompliance:** Existing prerendered charts do not meet [Telemetry Intent](../../concepts/telemetry-intent.md) and will be migrated to browser rendering. All new designs, charts and visuals must render in the browser; none may be prerendered.

What console charts must share: sizing, interaction, loading states and honest
marks for missing measurements. These are forward requirements, not a claim that
every existing chart meets them. Panel placement belongs to [console.md](console.md);
wording, ranking and colour belong to
[console design](../../concepts/console-design.md).

## Browser rendering and data

- Use d3.js for new charts, as required by [Telemetry Intent](../../concepts/telemetry-intent.md). Do not add ECharts, server-rendered SVG fallbacks or chart data embedded in HTML.
- Fetch data at view time through the [shared data reader](../../concepts/console-design/how-a-console-chart-gets-its-data.md). Request the columns and dates needed for the view, never a whole collection to discard most of it.
- Telemetry queries use DuckDB-Wasm over the published Parquet ledgers. Panels must not build their own URLs or import their own parsers. The [query module](how-the-query-door-answers-a-panel.md) owns those details.
- Query, derive chart values and draw in the browser. Do not depend on a route's server loader or a build-time telemetry projection.
- Share scales, readouts and loading behavior across panels. Migrate existing chart machinery to these rules; do not copy its prerender assumptions into new work.

Static hosting remains unchanged: the site serves code, assets and data files.
Browser rendering does not introduce a runtime backend.

## Every chart draws through one coordinate frame, in CSS pixels

Measure the chart's real container in the browser and redraw when it changes.
Do not choose a server fallback width and later replace it during hydration.
Reserve the chart's layout while it waits, and cap every SVG at its container.
Text and strokes must keep their intended size across narrow and wide screens.

Reuse the shared coordinate rules in
[frame.ts](../../../frontend/src/lib/charts/frame.ts):

- Anchor a linear domain at zero when mark length represents value. Use a padded domain when position represents value.
- Use d3 tick calculations. Round domains outward for readable ticks unless the domain is fixed by another rule.
- Snap logarithmic domains to whole decades. A measured zero and a missing sample need separate marks, not a fabricated positive value.
- Label calendar columns through the shared day-tick calculation. Keep the first and last dates, thin intermediate labels to fit, and retain tick marks for unlabelled columns.
- Use the operator's selected time window, including its empty days. Do not shrink a chart to the dates that happen to have rows.

Keep thresholds, colours and dimensions in the shared configuration and theme
tokens. Browser rendering does not remove the [size controls](../../reference/site-weight.md):
deferred libraries still cost a download and still count toward the deployed site.

## Item-health charts

**Failure rate against volume:** show daily item counts split by the stage where
work stopped, with each stage's failure rate on a fixed 0 to 100 percent axis.
The denominator is the number that reached that stage, not the whole day.
Print counts and denominators beside rates. Below `console.min_attempts_for_rate`,
show counts only and break the rate line, as
[a share under the floor](#a-share-under-the-floor-gets-no-mark) requires.
An empty window is not a day of zeroes.

**Summary length against the length asked for:** show daily counts inside, below
and above the configured target band. Print the `summarize.bands` bounds and name
the largest misses. Use categorical colours with a word beside each swatch, not
the confidence ramp. Count and explain rows that cannot be assigned a band.
The three bins must add up to the day's eligible article count.

**Why items failed:** rank causes by stage and code, then sources by articles
lost. Show how many sources a cause affected and the denominator for each source.
Count articles, not repeated stage records. Use `console.source_rows` to bound
the displayed list and describe its tail. Keep detailed records behind a closed
disclosure. Do not colour a source as healthy or unhealthy without an agreed rule.

## A share under the floor gets no mark

Below `console.min_attempts_for_rate`, a share is not a measurement. The chart
draws no mark for it; the readout strip and the column's accessible name print
the counts instead.

- Judge each share by the count it is taken over, so one column can keep one
  rate's mark and lose another's.
- Break that share's line at the column, and never join across it. A measured
  column with no measured neighbour is a dot with no line.
- Keep the column, so a pointer, a tap or an arrow key still selects it.
- Do not stand in for the mark on the baseline: an open point there means a
  measured zero.
- When a window leaves a mark out, a caption under the panel's window sentence
  says why, in the small grey type the failure chart's own note uses, so the
  verdict stays the last thing in its paragraph. Leave it out where that
  sentence already says the whole window is too few.

The failure chart applies this to each stage. The judge's agreement chart
judges "disagreed" by every pair read twice and "could not tell" by the pairs
whose two readings agreed. Reader chose its note: `A day has no "disagreed" dot
if fewer than 5 pairs were read twice, and no "could not tell" dot if fewer than
5 pairs agreed.`, with the floor read from config, and on a chart of two or more
columns a second sentence that says the counts are in the strip above.

## Every chart with a shared column carries a pointer readout

A readout is a visible strip beside the plot, not a tooltip under the pointer.
It must work with mouse, touch and keyboard. Each drawing declares exactly one:

| Declaration | Meaning |
| --- | --- |
| `data-readout-columns` | A positive count of shared columns, with one readout strip |
| `data-readout-records` | A count of individual records, with one readout strip |
| `data-readout-none` | A written reason that ends `; agreed with Susan` |

Do not add a competing legend or a second strip for the same declaration.
Use the shared actions in [readout.ts](../../../frontend/src/lib/charts/readout.ts).

- Select a column by the nearest x position. Record charts select their own marks.
- Use one keyboard stop per chart. Arrow keys step through its layout; Home and End jump; Escape closes. Do not put every point in the tab order.
- Keep a touch selection after the finger lifts. Only a mouse leaving clears a pointer selection.
- Give marks accessible names. Do not use native SVG `<title>` tooltips; expose their facts in the readout or in a permanent chart note.
- Once data loads, open on the newest day or relevant record, not an empty strip. Keep legend order stable while the selection moves and bind colours to series rather than rank.
- Keep the strip outside the plot. Reserve space for the busiest selection so interaction does not move the marks. Do not drop facts just to make the strip shorter than the plot.

For throughput, show each series' median, middle half, extremes and item count,
plus each run's read and write rates. Read and write must be visible together.
For `ChartReadout`, the caller supplies the separator before `restingNote`.
Test the complete heading, not a substring that can hide a missing separator.

## An empty chart box says which nothing it holds

Every browser-rendered chart needs a loading state. Keep its heading and reserved
space, including when drawing is deferred until the chart approaches the viewport.

| State | Required response |
| --- | --- |
| Data or drawing code is pending | Say the chart is loading. Do not claim that it has drawn. |
| The query returned no measurements | Name the empty window and offer a wider one when appropriate. Do not draw zeroes. |
| Data or drawing code failed to load | Explain the failure and offer retry or reload. Sibling panels keep working. |
| JavaScript is off | Say `This chart needs JavaScript.` Do not promise a prerendered fallback. |

Remove loading text only after marks have actually drawn, not when a module has
downloaded. Preserve already usable content if a later request fails. Explain
where numbers can be read only when that readout or table is actually available.
Controls that cannot work without script follow the
[no-script rule](../../concepts/design-system.md#a-control-that-needs-a-script-is-not-left-on-the-page-without-one).

## Stage timings are one trend chart, and its axis is decades

Show one series per stage over the shared calendar window, oldest on the left.
Comparable values use a padded linear domain; an extent spanning more than two
decades uses a decade-rounded logarithmic domain. Label full-decade gridlines;
minor ticks stay on the axis. Do not discard a stage because a poor scale hides it.

| Measurement | Mark and explanation |
| --- | --- |
| Positive time | A filled point at the measured value |
| Nothing timed | No point and a break in the line; state the missing coverage |
| Measured zero | An open point on the baseline and a break in the logarithmic line; explain the clock's resolution rather than claiming no time was spent |
| Only some items timed | Draw the measured sample and state how many items it covers |

Carry sample counts and total counts with each derived value. Never infer absence
from a numeric zero, or convert an empty sample into zero. A one-day series still
draws a point. A stage with no samples is labelled `not timed` once in the legend.
Full coverage needs no warning.

The resting readout shows the newest day's stage values, sorted by those values.
Keep that order during pointer movement. Stage colour never changes with rank.

## The model-change rule, and the charts it means something on

A setup-change marker identifies a change in the inputs that produced a result.
Use recorded input manifests, not `model_id` or `run_id`: a prompt, runtime or
extraction setting can change without changing the model name, and a new run
does not itself mean a new setup.

Share one browser-side comparison across charts. Obtain the required records
through the shared reader, including the comparison context before the displayed
window. Do not precompute the markers in a server loader or embed them in HTML.

- Mark a day when it introduces an input set absent from the preceding recorded day. Merely dropping an input set is not a new setup. Multiple changes on one day produce one boundary.
- Prefer a named input manifest when a day also has a legacy fingerprint. Compare like record formats; a transition between formats does not itself prove the setup changed.
- Retain legacy comparisons while the supported window still needs them. Determine retirement from available records and the configured window, not a hardcoded date.
- Missing records mean unknown, not unchanged. Do not print "nothing changed" for a day whose setup was not recorded.
- These records explain results. They must not exclude rows, change scores or gate publication.

The manifest's fields are owned by
[the input contract](../../../backend/idhazh/contracts/fingerprint.py).
Reuse those recorded facts rather than copying them into new telemetry fields.

## How the rule is drawn

Draw a dashed line in `--chart-change`, labelled `setup changed`, on the leading
edge of the changed day. This is an event, not a health verdict or a target.
Do not borrow the confidence ramp or the target marker's colour. A change on the
oldest plotted day draws no separator because no earlier setup is visible.

- Draw setup changes where they help interpret a measured result, not on unrelated feed or permission outcomes.
- A chart without a date axis cannot place a day boundary. If the change matters to its result, explain it in words instead of silently omitting it.
- A boundary without a reading still gets a written explanation. Missing measurements must not hide a change that makes a comparison unsafe.
- Include the change in the readout so keyboard and touch users receive it too. Translate input field names into plain words.
- Name the changed settings when recorded. A shortened list must count the remaining settings and keep the complete list accessible. A legacy fingerprint can say that setup changed, not which field changed.

Each chart declares `data-model-rule="yes"` with its displayed span and a
`data-model-rule-line` per visible boundary, or `data-model-rule="no"` with a
written `data-model-rule-none` reason. A supported chart with no boundary says so
through `data-model-rule-empty`. The declaration distinguishes an intentional
absence from a forgotten marker.

## Verification

Use bounded fixtures with empty, missing, partial and zero measurements. Include
a mid-window setup change, missing input records and multiple changed settings.
Verify bin totals, stage denominators and marker placement independently of the
chart's own calculations. Exercise keyboard, touch, both themes, narrow containers,
failed downloads and scripts-off behavior. Existing tests must move with their
chart; they must not preserve a server-rendered picture as the required fallback.

## Design rationale

- Browser rendering follows [Telemetry Intent](../../concepts/telemetry-intent.md). Existing prerendering is work to remove, not an exception for new designs.
- Shared coordinates and readouts make charts comparable without relearning each panel.
- Counts and coverage distinguish sparse measurements from reliable rates. A missing sample is never evidence of zero work.
- A mark for a share under the floor would place a value the strip beside it calls too few to report. Leaving the mark out is the only mark that claims no height, and a line joined across that column would draw the same false value.
- A visible readout survives touch use and screenshots; a pointer tooltip does not.
- Named setup changes explain when a comparison is no longer like-for-like without changing the results themselves.

## See also

- [../../concepts/telemetry-intent.md](../../concepts/telemetry-intent.md) - browser-owned telemetry and no prerendering.
- [../../concepts/console-design/how-a-console-chart-gets-its-data.md](../../concepts/console-design/how-a-console-chart-gets-its-data.md) - shared, bounded data queries.
- [console.md](console.md) - which panel is on which route.
- [../../concepts/console-design.md](../../concepts/console-design.md) - wording, ranking and colour.
- [console-payloads.md](console-payloads.md) - the current published data and remaining migration work.
- [../../reference/site-weight.md](../../reference/site-weight.md) - size controls and deferred asset costs.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - selected tests and browser verification.
