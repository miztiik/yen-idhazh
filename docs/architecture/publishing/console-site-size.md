# Whether the site outgrows the 1 GB cap

**Last Updated**: 2026-09-20
GitHub Pages refuses a deploy over 1 GB, so the published site has an ending and
the only useful question is when. A level cannot answer it and a rate can, which
is what this section of Pipelines draws.

**This is one question of the console rather than one route.**
[console.md](console.md) is the index - the two questions every panel names, the
five routes and the strip, the standing band and the one window that governs
every page.

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

## Design rationale

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
- [retention.md](retention.md) - what is deleted as the site grows, which is the other lever on the same ceiling.
- [layout.md](layout.md) - the published-size arithmetic behind the rate.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2: the 1 GB site is GitHub's, and crossing it fails the deploy.
