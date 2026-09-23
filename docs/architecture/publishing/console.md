# Which console panel answers what

**Last Updated**: 2026-09-23

The operator's surface: which panel is on which route, and which of the two
questions it answers. `/console/` tells the owner what happened to the pipeline,
where the digest tells a reader what happened in the world.

**A rule about how any figure may read is not here.** This page says which panel
is where; [../../concepts/console-design.md](../../concepts/console-design.md)
says how a figure on it may be worded, ranked, tinted and drawn. That is the same
axis run in both directions, and it is what keeps the console pages from becoming
that many opinions.

| Page | Owns |
| --- | --- |
| this page | the inventory: the two questions, the five routes, and which panel sits on which |
| [what-sits-above-every-console-route.md](what-sits-above-every-console-route.md) | the chrome on all five routes: the tab strip and the standing band |
| [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) | the window control, and every surface that does not simply follow it |
| [what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md) | Pipelines: run health, what failed, where a run's time went, what one item cost the model, extraction |
| [how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md](how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md) | Pipelines: the drawing flow, the retirement rule it is judged against, and the daily tables |
| [why-a-summary-was-doubted-and-what-the-checker-measures.md](why-a-summary-was-doubted-and-what-the-checker-measures.md) | Summaries: the five doubt reasons, and every instrument the checker writes |
| [who-supplied-the-day-and-which-feeds-failed.md](who-supplied-the-day-and-which-feeds-failed.md) | Voices: the source census, and the feeds that failed |
| [console-machine.md](console-machine.md) | Hardware: what machine the run drew, and whether the day's rate means anything because of it |
| [console-truncation.md](console-truncation.md) | what the truncation cap costs, and the four places across three routes that say it |
| [console-site-size.md](console-site-size.md) | whether the published site outgrows the 1 GB Pages cap, drawn as a rate rather than a level |
| [console-charts.md](console-charts.md) | the machinery every chart shares: the frame, the readout, the marks |
| [console-payloads.md](console-payloads.md) | the wire: what a browser may fetch, and the trust boundary |
| [telemetry-series.md](telemetry-series.md) | the grain: what a figure was measured over |
| [../../concepts/console-design.md](../../concepts/console-design.md) | the presentation rule: wording, colour, ranking, empty states |

**Each child is a question a person arrives holding, not a chapter.** Somebody
asking "what box did this run get" is not reading the panel inventory; somebody
asking "how close is the site to the cap" is not either; and the truncation cap
is said in four places across three routes, so it belongs to no single one of
them. What stays here is what you need to place any panel at all: the two
questions and the five routes.

It is instrumentation: it takes no ornament and spends no reader attention, and
what it owes instead is legibility - a figure readable at a glance, a table that
fits the screen it is on, and a page that can be scanned in one pass
([../../concepts/vision.md](../../concepts/vision.md)).

## The console answers two questions, and every panel names which

**Is it working** and **what is broken** are two questions rather than one, and a panel that asks the first in its title while drawing the second is the commonest defect this surface has. A verdict panel takes the central value or the count and covers every subsystem. A break panel takes the extreme and the individual that owns it, and covers every candidate inside one subsystem. **A verdict panel sits above the panels it verdicts**, or the operator reads ten readings before he reaches the line that tells him whether to trust them.

| Surface | Which question it answers |
| --- | --- |
| the standing band | is it working - one verdict across all five routes, at a size that does not grow with the pipeline |
| `/console/` "At a glance" | is it working - for this route alone, and over the open window where the band's figures are whole-record |
| `/console/` `Run health` | is it working - in the run, and it is the first panel on the route |
| the rest of `/console/` | what is broken in the run |
| `/console/model/`, `/console/judgement/`, `/console/voices/` | what is broken in the writing, the labelling and the supply |
| `/console/machine/` `Whether the speed numbers can be trusted` | is it working - can the day's rates be trusted at all, and it is the first panel on the route |
| the rest of `/console/machine/` | what is broken on the box |

The band is not a route. It stands on all five, which is why it is the surface that can verdict five.

**Every route carries its own verdict panel, and it goes first.** That is the
rule in the row above applied rather than a second rule: a verdict that only
exists on the band tells an operator the pipeline is unwell and leaves him to
work out which of thirteen readings to distrust. A panel declares which of the
two questions it answers in its own markup, as `data-panel-question`, so the
markup is what to read when a heading and a panel disagree.

**On Pipelines "first" means first PANEL, under the glance cards.** The cards are
a verdict too - they are this route's `is it working` over the open window - and
they carry the route's first chart. Measured 2026-09-20 on the canary build,
Intel Core i7-1265U: drawing `Run health` above them put that chart at 1,179px at
1440 CSS px and 1,704px at 390, against the 800 and 1,200 lines
`frontend/tests/console-band.spec.ts` holds - so a reader on a phone would have
scrolled a screen and a half before seeing a shape. Both verdict surfaces sit
above every panel they verdict either way, so the order costs the rule nothing.

How a panel obeying this is allowed to draw is
[../../concepts/console-design/the-rules-every-console-chart-obeys.md](../../concepts/console-design/the-rules-every-console-chart-obeys.md#thirteen-rules-hold-for-every-chart-on-this-console),
which carries it as the last and widest of the thirteen.

## The console is five routes

| Path | Label | What it answers |
| --- | --- | --- |
| `/console/` | **Pipelines** | Did the runs work, and what each stage cost. |
| `/console/model/` | **Summaries** | What the model wrote, how long it took, and what it got wrong. |
| `/console/machine/` | **Hardware** | The hardware the model ran on, and how much it varied between runs. |
| `/console/judgement/` | **Judgement** | What the model made of each article, and where we disagreed. |
| `/console/voices/` | **Voices** | Who supplied the day, and how far each feed is discounted. |

Pipelines answers two questions: did the runs work, and what each stage cost. The
feed and source panels belong to Voices, so Pipelines does not describe which
feeds broke.

`/console/` keeps its path. It is the one an operator types and the one every
existing bookmark points at, so moving it to `/console/pipelines/` would cost a
redirect and buy a symmetry nobody asked for.

`/evals/` remains a published entry point for old bookmarks. It carries a
prerendered meta refresh, a canonical link and a plain link to `/console/`.
GitHub Pages cannot serve a SvelteKit server redirect, so the redirect must be
static HTML. A reader with JavaScript disabled still receives a page and can use
the link.

### A label is not an address

`Summaries` is the label because every panel on that route is about a published
summary - its length, its cost, how long it took, what the checker doubted - and
none is about the model as an artefact. `Hardware` is the plainest word for a
processor, a memory, a clock and a context window; `Runner` was refused because
it is a term the build system uses on itself rather than a term for a reader
(`CLAUDE.md` section 0b), and `Model` was refused for the middle route because it
would put that word on the page about the box rather than the page about the
output. `Model` and `Machine` shared a first letter, which was the recorded cost
of the old name set; `Summaries` and `Hardware` do not.

`Judgement` is singular: the other three name a place and this one names an act,
so `Judgements` would be a count of things and the tab is not a list. `Voices` is
the owner's word over `Sources` (`CLAUDE.md` section 0), and its cost is that
`Voices` appears nowhere else in this repository while `source_id`,
`config/sources.json` and `source-health.json` all do.

The route ids stay `pipelines` / `model` / `machine`, and every `href` is
unchanged. There are no per-route page ceilings to move:
`page_weight.ceilings_bytes` names only `/404` and `/evals/`, because a route
whose weight grows every time the pipeline publishes cannot be held to a byte
count somebody wrote down once.
[../../../frontend/tests/console-title.spec.ts](../../../frontend/tests/console-title.spec.ts)
asserts both halves in one file.

### Every panel title on the five routes is a noun phrase

That rule is mechanical so it can be checked: no trailing question mark, and no
opening auxiliary verb. `Did the runs finish?` became `Runs that finished`, `Do
the two clocks agree` became `The two clocks, compared`, `Is the tail growing`
became `How the tail moved`, and `Did the model change move anything` became
`What the model change moved`. `What one more article costs` was already the
form. A question title asks the reader to hold it while he reads the panel; a
noun phrase names what is in front of him. `What`, `Which` and `How` stay legal
openings, because they head a free relative rather than a question.

**On Hardware the rule goes further: a title states the question the panel
answers and borrows no word from how the thing is built.** The grammar above is
necessary and is not sufficient - `Prompt cache` and `Context headroom` both pass
it while naming a mechanism and saying nothing a reader would learn. Two of the
titles named above have moved again under it: `The two clocks, compared` is now
`Whether the speed numbers can be trusted` and `How the tail moved` is now
`Whether the slowest articles are getting slower`. That route's own inventory is
[console-machine.md](console-machine.md); what is here is the rule, and it binds
any route whose titles are next rewritten.

`What the model did` survives verbatim as the h2 on the Summaries route - it is
protected copy, and
[../../../frontend/tests/console-model.spec.ts](../../../frontend/tests/console-model.spec.ts)
holds all eleven of its labels byte for byte.

## Judgement draws one panel and still names what is missing

**`Stories the day merged` draws no model verdict.** One column a day is the
stories that day folded behind another because the grouping pass read them as the
same story; the dot on the column is the biggest group that day, counting the one
that was kept. Both are counts of stories, so they share one axis.

It reads `same_story_as` off the published day and nothing else - the scores and
the vectors that decided the grouping are dropped from the published payload, so
a page that re-derived them would be a second opinion about a decision already
taken. The route's `load`
([../../../frontend/src/routes/console/judgement/+page.server.ts](../../../frontend/src/routes/console/judgement/+page.server.ts))
works out the widest window preset before it opens the first day file, so the
read is bounded by a knob in `config/` rather than by how much the archive has
accumulated (Guardrail #12). The arithmetic sits in
[../../../frontend/src/lib/console/merge-line.ts](../../../frontend/src/lib/console/merge-line.ts)
so a test can drive it from a written-down array instead of a day off the
archive.

**The panel does not close Judgement's named absence, and the two sit one above
the other.** They answer different questions: the panel counts what a day folded,
and the absence is about the desk and the lenses the model chose, which it still
does not record. So the route draws a figure AND still says in plain words what
is missing - an absence that disappears the first time any panel lands on a route
would take the promise with it. **A route whose page does not exist is a strip
that lies**, which is why both new routes opened carrying a heading and a named
absence rather than waiting for a panel.

**There is no rate line on the panel.** A day publishes a few hundred stories and
folds a handful, so the share runs at a few percent: on a 0 to 100 axis that is a
flat line two pixels off the floor, and on an axis fitted to it the noise becomes
drama. The share is in type under the chart with the denominator it is a share
of, and a real measurement that rounds away prints `<1` rather than `0`.

The holdout panel beside it is drawn to
[../../concepts/console-design/the-rules-every-console-chart-obeys.md](../../concepts/console-design/the-rules-every-console-chart-obeys.md#the-holdout-margin-is-drawn-at-the-scale-of-the-margin-not-of-the-score).

## Rejected alternatives

These are the console-wide ones. A refusal about one panel is on the page that
owns that panel, and a refusal about how any chart may draw is on
[../../concepts/console-design.md](../../concepts/console-design.md).

| Option | Why rejected |
| --- | --- |
| A drawing library for the console charts - `echarts`, `@observablehq/plot`, `chart.js`, or a component library | 336 KB gz on canvas, 128 KB gz and a DOM shim to prerender, 67 KB gz on canvas, and a component set is worst of all where every chart is bespoke. All of them own the element and the theme; the console needed the arithmetic. The console exception has three named conditions, and it still binds a reader route (Guardrail #8). |
| `d3-scale` from a CDN | The HTTP cache is partitioned per site, so the shared-cache argument is dead, and the repo's `script-src` allows `self` only. |
| Hand-rolling the units instead of taking `d3-scale` | `.nice` and `ticks` are exactly the part hand-rolling gets wrong, and an axis labelled 0, 37, 74 is an axis nobody reads a value off. |
| A `console.chart_width` default per chart shape | One knob names the width the reading column leaves; a chart sharing a row divides it. Four knobs would be four ways to disagree about one column. |
| Putting the page ceilings anywhere but `config/` | A ceiling is a limit a person chose and raises on purpose, which is the definition of a knob (Guardrail #6). |

The reader's own table is on [frontend.md](frontend.md) - a reader row and a
console row share nothing but a heading.

## See also

- [what-sits-above-every-console-route.md](what-sits-above-every-console-route.md) - the tab strip and the standing band.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the window control and its exemptions.
- [frontend.md](frontend.md) - the reader's published surface, and the routes this one sits beside.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is allowed to read.
- [console-charts.md](console-charts.md) - what a chart has to conform to: the coordinate frame, the readout, and how a missing number is marked.
- [console-payloads.md](console-payloads.md) - what the console fetches, and what it may never be served.
- [telemetry-series.md](telemetry-series.md) - the published projection and the grain of every figure.
- [../sources/health.md](../sources/health.md) - the feed ledger the Voices panels render.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the page ceilings and what to do when one fires.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - the instrument log behind every number here.
