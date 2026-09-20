# What the truncation cap costs

**Last Updated**: 2026-09-20
The truncation cap removes words from an article before the model ever reads
them, and nothing about a published summary says it happened. The console says
it in four places across three routes, and this page is what each of them is
for.

**This is one question of the console rather than one route.**
[console.md](console.md) is the index - the two questions every panel names, the
five routes and the strip, the standing band and the one window that governs
every page.

The truncation cap is the one setting on this project that silently removes
words a reader might have got. Five figures answer five different questions
about it, and each one is on the surface that already owns its grain.

| Figure | Where | Grain | Read from |
| --- | --- | --- | --- |
| `Article read only in part` | the model table | one day | `state/scores.csv` |
| `Read only in part, as a percent` | the model table | one day | `state/scores.csv` |
| `Time to write one`, second figure | the model table | one day | `state/item-health/` |
| `Too long to send` | the model table | one day | `state/item-health/` |
| `n read only in part` | the run square's own label | one run | `state/item-health/` |
| `Sources cut short most often` | its own range plot | one source, the open window | `state/item-health/` |
**The run grain is a clause on a label and never a published figure.** Measured
2026-08-29 over the 19 committed runs, the count is 1 to 12 articles of 160 to
200 - 0.6 to 7.5 percent - and that swing is which articles the feeds carried
that hour. Drawn as a number beside the others it would read as the cap moving
when nothing about the cap moved. A run square is where run-level facts already
live, so it goes there and stops.

**The day grain divides by the rows its own flag answers for.**
`truncation_flagged` changed meaning at `CUT_FLAG_MEANS_A_CUT_FROM`, so a day
holding rows from both sides of that stamp has two populations in one column.
The count already excluded the older rows; the share divides by the same subset,
because a share whose numerator and denominator answer different questions is
not a share. Both are null - a dash, never a zero - on a day made only of older
rows.

**The source section is a range plot, and the cap is a rule across it.** It was
five columns of numbers, and the one number every column had to be read against
- where the cut falls - appeared nowhere in the section. One row per source now,
on a log word-length axis, with the shortest, middle and longest article that
source published drawn as a track, and a dashed rule at the cut point across
every row. The part of a track right of the rule is where the cap bites, and the
distance is the text the machine never read. The axis is a log one because the
lengths span more than two decades: a 400-word note and a 9,000-word feature sit
on the same plot, and a linear axis puts every short source on the left edge.

**One rule per cut point, not one rule.** `caps` is one entry per distinct
post-cap length among the window's cut articles, oldest first - the same rule
the compression plot reads its own lines by, so two drawings of one fact
cannot disagree. A thirty-day window over the committed ledger holds two of
them, 1,923 words and 3,846, because the cap moved on 29 August. Past the widest
of them an article lost text whichever cut was in force, so the emphasised span
starts there and says the strong thing; the narrower rule is drawn with its own
dates, so the move is visible rather than averaged away.

**Every margin on this plot is measured, and the label column moves rather than
the plot.** Fixed margins are rejected: a 168px gutter for the source names, a
34px row pitch, and a 130px threshold past which a cap label flips to read right
to left do not fit every frame. Measured 2026-09-01 on the built console, the
gutter was 12 percent of a 1,342px frame at 1440 and **52 percent of a 324px one
at 390** - so on a phone the names took more of the chart than the plot did, and
the six tracks drew inside 91px of it.

- **`labelGutter` sizes the name column from the widest name's own advance**,
 and returns null where that would take more than `MAX_GUTTER_SHARE` of the
 frame. Null is the cue to put the names above their tracks instead. A source
 id is the ledger's own spelling of a name and there is no shorter true form of
 it, so the gutter moves and the word does not - nothing is abbreviated at any
 width.
- **`rowPitch` grows a row with the plot, between a floor and a ceiling**, the
 way `cellFor` grows a run-strip cell. The floor is `ROW_PITCH_MIN`: two lines
 of type and a 10px bar leave a 34px row with no air at all between one source
 and the next. The ceiling is where six rows stop reading as one set.
- **The cap label's flip is decided by the label's own advance.** `cut at 3,846
 words (from 25 Aug)` needs 186px at `font-size="10"`; the constant it replaced
 was 130. Nothing was clipped by it on the committed tree, and a constant that
 is 56px under the string it guards is the same defect waiting for one more
 word.
- **The right-most decade label is Row #1's rule, not a second one.**
 `tickAnchor` anchors the end labels inwards, so `10,000` needs no room outside
 the plot and the 12px right margin is the track's own round cap. The
 `10,00` clip measured on 2026-08-31 was fixed there;
 [../../../frontend/tests/console-voices-cuts.spec.ts](../../../frontend/tests/console-voices-cuts.spec.ts)
 asserts it stays fixed rather than fixing it again.
- **`thinLabels` drops the axis labels that will not fit, and keeps both ends.**
 A label survives only where its left edge clears the last kept label's right
 edge by `AXIS_LABEL_GAP_PX`; a dropped label leaves its mark, so nothing about
 the data goes with it. Measured 2026-09-01 at 390 on the built console: a
 doubling axis running to 1,024 seconds carries twelve edge labels across the
 274px of plot the phone leaves, which is 24.9px an edge against the 28.3px
 `512` and `1,024` need side by side. Drawn every edge, the two ends of the
 axis are crowded; thinned, seven of the twelve survive and none is.
 It lives in `frame.ts` rather than inside the chart because a ledger is not
 obliged to span twelve doublings and the committed canary does not - its
 slowest check is under a second, so the drawn page cannot put the rule under
 load, and an axis the data never stresses is a null result rather than a pass.
 [../../../frontend/tests/console-model-panels.spec.ts](../../../frontend/tests/console-model-panels.spec.ts)
 drives it directly at the plot width the page reports.

**The log domain still snaps to decades, and the dead space is the price.** The
plot fills its frame; the tracks do not fill the plot, and that is a different
thing. Over the committed ledger the shortest article on the board is 361 words
and the longest 6,670, inside a domain of 100 to 10,000 - so 27.9 percent of the
plot sits left of the shortest track and 8.8 percent right of the longest,
measured 2026-09-01 at 1440. Starting the domain at the shortest article would
recover it and lose the landmark: the two cut rules are the reason the chart
exists, and a floating domain gives a reader nothing to place a mark against.

**The rule is read off the rows and never off the setting.** Every cut point
comes off the `source_words` cell a run wrote after its own cap fired. Two
things break if the page reads `extract.truncation_cap_tokens` instead. The
setting is one number, so a window spanning a change draws one rule where the
rows say two - measured on this tree the file says 10,000 tokens, which is 7,692
words, and the window's cut rows sit at 1,923 and 3,846 from the two caps
before it. And a rule from the file draws even in a window where nothing was cut
at all, which a derived one cannot.
[frontend/tests/console-voices-sources.spec.ts](../../../frontend/tests/console-voices-sources.spec.ts)
holds it with a pair of calls over rows cut at two different lengths: no
constant satisfies both.

**Two columns went, and what a reader loses is named.** `Share cut` is gone: it
was dashed below `console.min_attempts_for_rate`, it was explicitly not the sort
key, and a rate ranking was already ruled wrong here. What is lost is the share
as a number - a source at 55 percent and one at 12 percent now read the same
until their two counts are compared, and both counts are on the row.
`Cut short` and `Articles` are gone as columns and are the row's own label,
`17 of 38 cut`, which keeps the count sort and puts the denominator beside the
track it describes. Authority: Susan, 2026-08-30.

**Aggregated on the server, ten rows per preset.** A window of the committed
ledger is a few thousand rows, and this page inlines whatever it is handed, so
the browser never sees the rows the plot was made from. The window ends on the
newest day the ledger holds rather than on the build clock, so rebuilding an old
tree draws what that tree said rather than an empty plot. The 10 rows are a
constant in
[frontend/src/lib/server/model-work.ts](../../../frontend/src/lib/server/model-work.ts)
and not a config knob, because a knob there is a way to make the copy lie.

**A cut is two cells of one row compared, and never a count against the cap.**
`source_words_before_cap > source_words` is the whole test
([../sources/item-health.md](../sources/item-health.md)). The alternative,
`source_words == int(truncation_cap_tokens / 1.3)`, moves the day the cap moves,
so a seven-day window spanning a cap change would mix two cut points - and it
calls an article cut when its body happens to end on the boundary. The column
is empty on every row a run wrote before 2026-08-28, and empty is not zero:
reading it as zero would call every one of those articles cut.

**Articles, not rows.** A run writes a row for every item it plans, so the same
article carries several rows - 1.12 rows per address, measured 2026-08-25. The
table counts addresses, and where two runs read the same article it keeps the
run that read the most of it, so the two lengths compared always come off one
row. The copy says "how many articles", and the count has to mean it.

**What the cut cost is recorded here, not charted.** `hhem_full - hhem` over the
articles the cap cut is what a lost tail costs in faithfulness. Measured
2026-08-29 over all 2,683 committed score rows: **22 rows are cut**, and over
those 22 the delta runs **-0.0381 to +0.1235, mean +0.0039, median 0.0000**. It
is not on the page and will not be: it is a value between zero and one, which
the console refuses ([../../concepts/design-system.md](../../concepts/design-system.md)),
and at n=22 with a median of exactly zero it is not yet a result. The words are
the part that is publishable, and the table prints them with the same n beside
them: over those 22 articles the cut removed a median of 1,009 words and at
most 6,519.

Authority: Jony, 2026-08-29, over Fowler's ordering constraint that this ships
before the cap moves - the first day at a new cap has to be measured by a
console that can already see it, or Guardrail #10 defeats the change.

**`Visuals published` counts only items whose `visual` is a `chart` in state
`rendered`**, which is what [visuals.md](visuals.md) requires so a diagram never
lands on the chart drawing's bill. Measured 2026-08-31 over the eleven committed
published days: 185 visuals, 185 of them charts, no other kind and no other
state - so the heading and the count agree today. The day a non-chart visual
publishes for real, either the count widens or the heading narrows;
`frontend/tests/console.spec.ts` holds the count to charts and says so.

**Two manifest keys spell a stage the Python no longer calls it, and that is
deliberate.** `route_ms` and `items_routed` are published in fifteen days of
`run.json`, so the wire keeps the old spelling while the Python behind them is
`decision_ms` and `items_decided`
([../contracts/schemas.md](../contracts/schemas.md)). Anybody tidying the
mismatch renames a persisted field.
## See also

- [console.md](console.md) - the console index: the two questions every panel names, the five routes, the standing band and the shared window.
- [../summarize/prompt.md](../summarize/prompt.md) - where the cap is applied, and what it is protecting.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - what the cap bites on, measured.
- [../../reference/benchmarks/how-often-the-truncation-cap-bites.md](../../reference/benchmarks/how-often-the-truncation-cap-bites.md) - the run that priced how often it fires.
- [../../concepts/summary-metrics.md](../../concepts/summary-metrics.md) - `truncation_flagged` and what one number about one summary can and cannot see.
