# What the caps cost

**Last Updated**: 2026-09-20
Two caps, and what the console says each one is costing. The truncation cap
removes words from an article before the model ever reads them. The 1 GB Pages
cap ends the published site when the bytes reach it. Both are silent until
somebody draws them, which is what these panels are for.

**These are two questions of the console rather than one route.** The cap is said
in four places across three routes; the size is one section on Pipelines.
[console.md](console.md) is the index - the two questions every panel names, the
five routes and the strip, the standing band and the one window that governs
every page.
## What the cap costs, and the four places the console says it

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

## The site's size is a rate, and the level beside it says which tree

The console asks one size question: is the site going to outgrow the 1 GB Pages
cap. Two levels with no date are rejected: a waterfall of megabytes added per
day and a table of the running total do not say when.

**The waterfall drew the item ceiling and called it site growth.** Measured
2026-08-30 over the ten committed manifests, a day's gain ran 0.04 MB to 2.82 MB
while the day published 4 articles or 731. Divided by the articles, the same ten
days sit between 2,478 and 4,541 bytes. The first series moves when the feeds
have a busy morning; the second moves when somebody changes what a payload
carries, which is the only thing anybody can act on. So the chart is
`What one more article costs`, in bytes of payload tree per published article,
and it follows the page's window.

**A day outside one standard deviation of the window's median is marked, and the
rule is the whole of the marking.** The band is taken about the median rather
than about the mean: the line drawn on the chart is the median, and a band whose
centre and whose width came from two different statistics is asymmetric about
its own centre for no reason a reader can see. One published day in the window
reports no spread at all rather than a spread of zero, which would call that day
perfectly typical of itself. The values are published as text beside the chart -
that is what a chart owes anybody who cannot see it, and it is also the only way
the flags can be checked: `frontend/tests/console-site-size.spec.ts` recomputes
the band from exactly those numbers and fails if the marks disagree.

**The panel says what it is for.** Its note must do more than describe its own
axes - bytes gained, over articles published - because a reader would meet a
chart of four-digit numbers with nothing to hold them against. It is not a chart
of data growth across days; it is the marginal cost of one more article, and it
is on the page to answer how long the project can keep publishing under the 1 GB
Pages cap. The note opens with that question and the panel closes with the
answer.

**The horizon is two measured rates over one set of days.** `publishingHorizon`
divides the headroom by the window's median cost, which gives articles, and then
by the median articles a published day taken over the same days that cost came
from - so the sentence and the chart above it cannot be read off two different
windows. Neither rate is a config knob. The band next door prints the same
headroom in articles and stops there, for the reason two sections down: articles
need no daily rate at all, and the one number that used to stand in for a rate
bounded a run rather than a day. The years figure lives here because this is
where the spread and the flagged days are drawn, and the spread is the only
thing that says whether a rate is stable enough to extrapolate from. Null
wherever either rate is missing: a tree that never grew over an article it
published has no horizon, and a window whose days published nothing has no daily
rate.

**The sentence carries the caveat it cannot derive.** The cap is measured on the
built site and this rate is measured on the committed payload tree behind it, so
the room is the most we have and never the least - the two trees were 14.63
times apart on 2026-08-30 and the multiple is not stable. A figure that printed
a date without that clause would be optimistic by a multiple nobody can see.

**The chart measures its container.** A literal `760` seed is rejected because
every other chart on the page reads `console.chart_width`; the drawn width
already tracks, because `Chart.svelte` owns it from mount onward through a
`ResizeObserver`. Measured 2026-09-01 at 1440, 768 and 390, the SVG is its
host's width to within a pixel at all three.

**The window bounds what is drawn and never what is differenced.** A day's cost
is its own bytes minus the previous manifest's, so the oldest day on screen
still reads against the day before it. Differenced against zero it would report
the whole tree as one day's work, and the window would invent an outlier every
time it moved.

**The `Site size` fact carries the level, a track against the cap, the window's
delta and a runway.** The runway is headroom over the per-article cost, and what
it counts is **articles**: `(cap - bytes) / bytesPerItem`. Published days are rejected because they divide by `run.safety_ceiling_per_run`
articles a day, and that knob bounds one **run**, not one day. Up to five runs a day is normal, so
the band priced a day at 160 articles while the days it measured ran a median of
334, and the printed runway was 2.09 times too long
([../../reference/site-weight.md](../../reference/site-weight.md#days-to-the-1-gb-pages-ceiling)).
Articles need no daily rate at all, which is why the fix removed the assumption
instead of correcting it. Where no published day grew the tree over an article
it published there is no rate, so the fact says there is no runway instead of
printing a figure.

**The delta is megabytes and not a percentage, and that was a measurement.** The
oldest committed manifest recorded 13,595 bytes, so a share taken from there read
`+73,933%` on 2026-08-30 - true, unreadable, and painted green by the card's
own up-is-good rule, which is the wrong verdict on a site size as well as one
nobody asked for. `Up 9.6 MB over 30 days` is the same fact in the unit the
number above it is already in.

**The card names the tree it measured, and this is the one thing it cannot fix
itself.** `site_bytes` in a run manifest is `frontend/public/digest/`, and the
Pages cap is measured on the built bundle, which also carries every prerendered
page and the on-device model. Measured 2026-08-30 on a developer machine,
node v24.12.0, one build:

| | Bytes | Files | Per published article | Runway to the 1 GB cap |
| --- | --- | --- | --- | --- |
| Committed payload tree | 10,414,335 | 170 | 2,478 to 4,541, median 3,261 | about 2,038 published days |
| Built bundle | 152,373,806 | 343 | 46,971 cumulative, 25,786 marginal | 123 published days |

The bundle is **14.63 times larger**, and it was eighteen times larger on
2026-08-27 ([the run-manifest changelog](../../../backend/idhazh/contracts/run_manifest.py)),
so the multiple itself is not stable. **The committed-tree runway above is how
that cell was derived on the day it was measured**; it counts articles since
2026-08-31, for the reason two paragraphs up.

**The band never says "the site" has room for N, because it does not know
that.** Its one line is the level, the limit and the articles the headroom buys;
every caveat it would need - the rate, the days it was measured over, its spread,
and the fact that the cap is measured on a larger tree so the room is the most we
have and never the least - is on `What one more article costs` directly below it.
`idhazh site-weight` and `committed payload tree` are not reader strings on any
surface: a build command is not something a reader can run. The gap that wording
exists to keep visible is real and measured - 312,000 articles of room in the
committed payload tree against 119 published days in a bundle 14.63 times larger
([../../how-to/run-the-gates.md](../../how-to/run-the-gates.md)).

**The deleted per-day table is not coming back.** `Runs`, `Planned` and `Failed`
are on the run strip four headings above, `Site` is the card, and `Files` -
whether the tree grew because we published more or because pages got heavier -
is what the per-article chart now answers directly.

### Design rationale

**`/console/judgement/` must use the screen it is on.** A heading, two
sentences and one bordered panel leave most of the frame empty at 1440px. The
other three sufficiency checks were inherited rather than invented - figure
separated from ground through the shared `.console-panel` border, surface and
shadow; the panel was the only block in the route's own content, so there was one
thing the eye landed on; and the route took the page title, the five-tab strip
and the standing band from the layout before it drew anything of its own.

**`Stories the day merged` is what cleared it.** The route now draws a chart the
full width of the console frame with a window control above it, so the screen
carries a figure rather than a promise.

`/console/voices/` passes the check too: row #13 moved four panels onto it, two
of which draw a chart.

**The check could not have been passed before a figure existed.** The only way
to fill the frame of a page with no data is to put something on it that is not a
measurement, on the one surface whose doctrine is that it takes no ornament and
spends no reader attention. The alternative considered was a list of the figures
each page would carry, drawn empty - refused because it is a promise the page
cannot keep: the moment a panel changes the list is a lie and nothing fails.

The alternative to shipping empty was landing the strip and both tab rows
together, which would have put three rows on `ConsoleNav.svelte` in one parallel
group - and a strip that names a page nobody can reach is worse than three tabs.
**This entry is deleted when Judgement's named absence goes**, which is the day
the model records the desk and the lenses it chose. The merge panel did not do
it: it answers a different question and the absence is still on the page.
Authority: Susan, 2026-09-12; sufficiency cleared 2026-09-17.

**The fifth tab is a split, not an addition, and Pipelines keeps none of the
four panels.** Row #13 of the placement plan. The four are the census, the
ranking weight, the failure list and what the truncation cap cost each source.
Leaving any of them behind would give two routes an answer to "which feed is
broken" and neither of them ownership of it, and the split is what pays for the
tab existing at all. Pipelines answers one question now - did the runs work -
and its route description says so in both producers. Authority: Editor, row #13
decision 2.

**The reliability factor is read from the published view and never recomputed in
the page.** `ledger.reliability` is the only self-adjusting number in this
project and it was drawn nowhere until this row. Two derivations of one ranking
factor is two verdicts, and the day they disagree neither is worth drawing - the
same lesson the standing band learned when it moved to a producer. Authority:
row #13 decision 4.

**Voices gained the window control the panels arrived with; it did not arrive
with one.** Two of the four moved panels declare a day count, and they landed on
a route whose own panel had argued against a control: the ranking weight was
reduced over `collect.reliability_window_days` when the run happened, so a
control that redrew it would print a number no run applied. The resolution is
the pattern the console already uses rather than a new one - the control governs
the surfaces that follow it, and the three that do not each say so in a
`data-window-exempt` paragraph. Unwinding the two panels' windowing was the
alternative, and it was refused: the window is what makes "which source is the
cap costing us most, lately" answerable at all, and removing it to fit the route
would have cost the reader a question to protect a sentence.

**No page ceiling and no payload ceiling were added for this route.** A
`payload_ceilings_bytes` entry is rejected because there is no instrument that
can hold it.
`payload_ceilings_bytes` keys resolve against the build directory and
`frontend/public/source-health.json` never reaches it - `copy-visuals.mjs` stages
seven named console directories and that file is in none of them - so the key
would match nothing and `bundle-gate.mjs` fails a key that matches nothing.
`page_weight.ceilings_bytes` is not a fallback: every console route left it on
2026-09-10 because those numbers move when a run publishes, and Voices inlines
feed rows, a census and four source-cut tables. Voices fetches one payload,
`console/band.json`, which the layout already fetched on every route and which
`payload_ceilings_bytes` already caps at 2,000 bytes.


article, spread 23,066 to 26,538, which is the built bundle's cumulative average
from `idhazh site-weight`. The console reads run manifests, and the same
arithmetic over those gives 2,478 to 4,541 bytes an article - a different tree,
roughly seven times smaller per article and thirteen times smaller in total.

Three options were weighed:

| # | Option | Outcome |
| --- | --- | --- |
| 1 | Print the runway from the payload tree against the cap and call it the site's | Rejected on the measurement. It reads about 2,000 published days where `site-weight` reads 123 - out by a factor of sixteen, and a fabricated date is worse than the level it replaced. |
| 2 | Add `built_site_bytes` to the run manifest | Rejected here, not on merit. It is a persisted-contract change, which is `CLAUDE.md` section 6 Level 5 and pauses work. It is the change that would make the console's runway exact, and it is recorded here so the next person does not have to rediscover it. |
| 3 | Print the runway of the tree the console has, and name that tree inside the sentence | Taken. Every clause on the card is true and checkable, the direction of the error is stated, and the instrument that measures the other tree is named. |

A fourth was considered and dropped without a table row: a measured
payload-to-site multiple held in `config/`. The two trees do not scale together
- `frontend/static/assist/` is 45,328,441 bytes and does not grow with articles
at all - so one multiplier is not just stale-prone, it is structurally wrong.
The measured multiple was 14.63 on 2026-08-30 and eighteen three days earlier,
which is the evidence.

**The track reads about one percent full, and that is the honest picture.** It
fails the "does it use the screen it is on" sufficiency check
([../../concepts/design-system.md](../../concepts/design-system.md)) in the sense
that a nearly-empty bar carries little information, and it ships anyway: the
caption prints the room left as a number beside it - `1,014 MB left of the 1 GB
Pages cap` - and the fill has a 2px minimum so a level far under its limit still
reads as a measurement rather than as an empty control. The alternative -
rescaling the track to make the bar look busy - is a chart that lies about how
much room is left.
## See also

- [console.md](console.md) - the console index: the two questions every panel names, the five routes, the standing band and the shared window.
- [../../reference/site-weight.md](../../reference/site-weight.md) - what the reader actually downloads, measured page by page.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - the producer's own figures, including what the cap bites on.
- [../summarize/prompt.md](../summarize/prompt.md) - where the truncation cap is applied, and what it is protecting.
- [retention.md](retention.md) - what is deleted as the site grows, which is the other lever on the same ceiling.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2: the 1 GB site is GitHub's, and crossing it fails the deploy.
