# Which console panel answers what

**Last Updated**: 2026-09-20
The operator's surface: which panel is on which route, the question each one
answers, and the ruling behind its shape. `/console/` tells the owner what
happened to the pipeline, where the digest tells a reader what happened in the
world.

**A rule about how any figure may read is not here.** This page says what a
named panel is; [../../concepts/console-design.md](../../concepts/console-design.md)
says how a figure on it may be worded, ranked, tinted and drawn. That is the
same axis run in both directions, and it is what keeps the console pages from
becoming that many opinions.

| Page | Owns |
| --- | --- |
| this page | the inventory: which panel, on which route, answering what, plus the chrome every route shares |
| [console-machine.md](console-machine.md) | the Hardware route: what machine the run drew, and whether the day's rate means anything because of it |
| [console-truncation.md](console-truncation.md) | what the truncation cap costs, and the four places across three routes that say it |
| [console-site-size.md](console-site-size.md) | whether the published site outgrows the 1 GB Pages cap, drawn as a rate rather than a level |
| [console-charts.md](console-charts.md) | the machinery every chart shares: the frame, the readout, the marks |
| [../../concepts/console-design.md](../../concepts/console-design.md) | the presentation rule: wording, colour, ranking, empty states |
| [console-payloads.md](console-payloads.md) | the wire: what a browser may fetch, and the trust boundary |
| [telemetry-series.md](telemetry-series.md) | the grain: what a figure was measured over |

**Each child is a question a person arrives holding, not a chapter.** Somebody
asking "what box did this run get" is not reading the panel inventory; somebody
asking "how close is the site to the cap" is not either; and the truncation cap
is said in four places across three routes, so it belongs to no single one of
them. What stays here is what you need to place any panel at all: the two
questions, the routes, the band and the window.

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
| `/console/machine/` `The two clocks, compared` | is it working - can the day's rates be trusted at all, and it is the first panel on the route |
| the rest of `/console/machine/` | what is broken on the box |

The band is not a route. It stands on all five, which is why it is the surface that can verdict five.

**Every route carries its own verdict panel, and it goes first.** That is the
rule in the row above applied rather than a second rule: a verdict that only
exists on the band tells an operator the pipeline is unwell and leaves him to
work out which of thirteen readings to distrust. A panel declares which of the
two questions it answers in its own markup, as `data-panel-question`, so the
markup is what to read when a heading and a panel disagree.

**On Pipelines "first" means first PANEL, under the glance cards.** The cards
are a verdict too - they are this route's `is it working` over the open window -
and they carry the route's first chart. Measured 2026-09-20 on the canary build,
Intel Core i7-1265U: drawing `Run health` above them put that chart at 1,179px
at 1440 CSS px and 1,704px at 390, against the 800 and 1,200 lines
`frontend/tests/console-band.spec.ts` holds - so a reader on a phone would have
scrolled a screen and a half before seeing a shape. Both verdict surfaces sit
above every panel they verdict either way, so the order costs the rule nothing.

How a panel obeying this is allowed to draw is [../../concepts/console-design.md](../../concepts/console-design.md), whose thirteen chart rules carry it as the last and widest of them. Susan, 2026-09-17.

`/evals/` remains a published entry point for old bookmarks. It carries a
prerendered meta refresh, a canonical link and a plain link to `/console/`.
GitHub Pages cannot serve a SvelteKit server redirect, so the redirect must be
static HTML. A reader with JavaScript disabled still receives a page and can use
the link.

## The console is five routes, and the strip is real anchors

Since 2026-08-30 the operator surface is prerendered routes drawn as a tab
strip. It was three; it took a fourth and a fifth on 2026-09-12:

| Path | Label | What it answers |
| --- | --- | --- |
| `/console/` | **Pipelines** | Did the runs work, and what each stage cost. |
| `/console/model/` | **Summaries** | What the model wrote, how long it took, and what it got wrong. |
| `/console/machine/` | **Hardware** | The hardware the model ran on, and how much it varied between runs. |
| `/console/judgement/` | **Judgement** | What the model made of each article, and where we disagreed. |
| `/console/voices/` | **Voices** | Who supplied the day, and how far each feed is discounted. |

Pipelines answers two questions: did the runs work, and what each stage cost.
The feed and source panels belong to Voices, so Pipelines does not describe
which feeds broke. The description is written in two places -
[console_band.py](../../../backend/idhazh/telemetry/publish/console_band.py) for
the published band and
[band.ts](../../../frontend/src/lib/console/band.ts) for the fallback - and both
must agree, because the strip a reader sees is whichever one answered.

`/console/` keeps its path. It is the one an operator types and the one every
existing bookmark points at, so moving it to `/console/pipelines/` would have
cost a redirect and bought a symmetry nobody asked for.

**A label is not an address.** `Summaries` is the label because every panel on
that route is about a published summary - its length, its cost, how long it took,
what the checker doubted - and none is about the model as an artefact.
`Hardware` is the plainest word for a processor, a memory, a clock and a context
window; `Runner` was refused because it is a term the build system uses on
itself rather than a term for a reader (`CLAUDE.md` section 0b), and `Model` was
refused for the middle route because it would put that word on the page about
the box rather than the page about the output. The route ids stay `pipelines` /
`model` / `machine`, and every `href` is unchanged. There are no per-route page
ceilings to move: `page_weight.ceilings_bytes` names only `/404` and `/evals/`,
because a route whose weight grows every time the pipeline publishes cannot be
held to a byte count somebody wrote down once.
[../../../frontend/tests/console-title.spec.ts](../../../frontend/tests/console-title.spec.ts)
asserts both halves in one file. Authority: owner, 2026-08-31.

**The fourth and fifth labels were chosen on 2026-09-11 and both routes opened
empty on 2026-09-12.** `Judgement` is singular: the other three name a place and
this one names an act, so `Judgements` would be a count of things and the tab is
not a list (Susan). `Voices` is the owner's word over Susan's `Sources` - her
case was that `Voices` appears nowhere else in this repository while `source_id`,
`config/sources.json` and `source-health.json` all do, and the owner overruled it
(`CLAUDE.md` section 0). Both routes opened carrying a heading and a named
absence and drawing no panel: a tab in a strip whose page does not exist is a
strip that lies, and the pages that fill them are specified by rows #12 and #13
of the placement plan and row #15 of the classification plan.

**Voices filled on 2026-09-14 and Judgement took its first panel on 2026-09-17.**
Row #13 was a split rather than an addition: four panels moved onto Voices off
Pipelines and Pipelines kept none of them.

**Judgement's first panel is `Stories the day merged`, and it draws no model
verdict.** One column a day is the stories that day folded behind another
because the grouping pass read them as the same story; the dot on the column is
the biggest group that day, counting the one that was kept. Both are counts of
stories, so they share one axis. It reads `same_story_as` off the published day
and nothing else - the scores and the vectors that decided the grouping are
dropped from the published payload, so a page that re-derived them would be a
second opinion about a decision already taken. The route's `load`
([../../../frontend/src/routes/console/judgement/+page.server.ts](../../../frontend/src/routes/console/judgement/+page.server.ts))
works out the widest window preset before it opens the first day file, so the
read is bounded by a knob in `config/` rather than by how much the archive has
accumulated (Guardrail #12). The arithmetic sits in
[../../../frontend/src/lib/console/merge-line.ts](../../../frontend/src/lib/console/merge-line.ts)
so a test can drive it from a written-down array instead of a day off the
archive.

**The panel did not close Judgement's named absence, and the two now sit one
above the other.** They answer different questions: the panel counts what a day
folded, and the absence is about the desk and the lenses the model chose, which
it still does not record. So the route draws a figure AND still says in plain
words what is missing - an absence that disappears the first time any panel
lands on the route would take the promise with it.

There is no rate line on the panel. A day publishes a few hundred stories and
folds a handful, so the share runs at a few percent: on a 0 to 100 axis that is
a flat line two pixels off the floor, and on an axis fitted to it the noise
becomes drama. The share is in type under the chart with the denominator it is a
share of, and a real measurement that rounds away prints `<1` rather than `0`.

**Every panel title on the five routes is a noun phrase**, and that rule is
mechanical so it can be checked: no trailing question mark, and no opening
auxiliary verb. `Did the runs finish?` became `Runs that finished`, `Do the two
clocks agree` became `The two clocks, compared`, `Is the tail growing` became
`How the tail moved`, and `Did the model change move anything` became `What the
model change moved`. `What one more article costs` was already the form and is
the model for it. A question title asks the reader to hold it while he reads the
panel; a noun phrase names what is in front of him. `What`, `Which` and `How`
stay legal openings, because they head a free relative rather than a question.
Authority: Editor, 2026-08-31.

`Model` and `Machine` shared a first letter, which was the recorded cost of the
old name set; `Summaries` and `Hardware` do not, so that cost is paid off.
`What the model did` survives verbatim as the h2 on the Summaries route - it is
protected copy, and [../../../frontend/tests/console-model.spec.ts](../../../frontend/tests/console-model.spec.ts)
holds all eleven of its labels byte for byte.

**Routes, not tabs, and the JavaScript-disabled gate is why.** A tab strip that
switches with script shows one panel set and no way to reach the others when the
script does not run, and every panel it hides still ships inside the one
document. Real anchors pass both, and each route can be weighed on its own. Tabs
keyed on a query string cannot prerender at all; tabs keyed on a hash stop
find-in-page at the hidden panels. Nothing about a fourth or a fifth route
changes that argument.

**The strip has to fit, and the basis is what moved to make it.** `.tab-slot`
was `flex: 1 1 14rem` - 224px at a 16px root - which put one tab on a row of a
360px phone, so five tabs would have stood five deep directly above the band. It
is `8rem` now, 128px, so two fit the 288px content box of a 320px phone and five
fit one row of a desktop. The per-tab description is hidden by default and shown
from `1024px`, the breakpoint three other components already use.

Measured 2026-09-12 off the built page in headless Chromium, `window.innerWidth`
read inside the page beside every figure:

| Width | Rows | Tab | Strip | Description |
| ---: | ---: | ---: | ---: | --- |
| 320 | 3 | 140px | 215px | hidden |
| 360 | 3 | 160px | 199px | hidden |
| 414 | 3 | 186px | 199px | hidden |
| 480 | 2 | 142px | 162px | hidden |
| 640 | 2 | 141px | 138px | hidden |
| 768 | 1 | 135px | 86px | hidden |
| 900 | 1 | 161px | 86px | hidden |
| 1024 | 1 | 186px | 136px | shown |
| 1440 | 1 | 269px | 80px | shown |

**Two numbers were taken from that sweep rather than from the rule.** `9rem`
cleared 360px and still stacked five deep at 320px, which is the same defect one
screen narrower, so the basis went to `8rem`. And the description at the narrower
`48rem` breakpoint made the strip 168px at 800px against 86px at 768px - so
widening the window made the chrome taller, which is a discontinuity a reader
notices and cannot explain. At 1024px each tab is 186px and the line costs 50px
once, then falls back as the tabs widen.

The description is not lost below the breakpoint: it is still the anchor's
`title` and the page it opens prints it in full, so what a hidden line costs is
the one-line summary a reader gets before choosing - which is why every label is
one word.
[../../../frontend/tests/console-nav.spec.ts](../../../frontend/tests/console-nav.spec.ts)
measures the tab boxes off the built page at 1440, 360 and 320, prints the width
the page really had beside every figure, and fails on a row too many or on any
two boxes that overlap.

**Every label carries its own worst state**, computed at build time from the
committed ledger - `Machine - 4 shards read 4.31x apart`, not `Machine`.
Without it a route is where a metric goes to die: nobody opens a page to find
out whether it was worth opening. Machine's candidates are a run the machine
record refused, a shard that committed no row, and the newest run's read spread.
The spread is reported at the lowest rank on purpose: nobody has agreed how far
apart two shards of one run may read before it is a problem, so ranking it any
higher would publish a threshold this project has not taken.

**The shard that committed no row is counted against a number from another
file.** The denominator is `shards` on the day's `run.json` - what the plan
asked the matrix for, recorded before any work job existed. The numerator is how
many work jobs filed a row in `state/host-fingerprint/`. Taking both off the
host rows would make them equal by construction: `N shards reported nothing`
could never be anything but zero, and the guard that refuses a run with more
shards than the plan sized would read `len(kept) > len(kept)`. A number that
cannot disagree with its neighbour is not a check (`CLAUDE.md` Guardrail #10).
The read spread is read the same way - off `server_prompt_tokens` and
`server_prompt_seconds`, which are llama-server's own counters and not
arithmetic over the item ledger.

**An editorial fault caps at `WORTH_A_LOOK`, and there is one exception.** The
band prints the one worst thing across every route, so a loud rule on Judgement
or Voices would take the band away from a failed run - and then a skewed day and
a failed run print the same sentence, which is the band's whole job undone. A
skewed day still published; a failed run did not. `console_band.editorial`
is where the cap is applied, because the band is derived once and read
everywhere. Authority: Carmack, 2026-09-11.

**The exception is a gate that has stopped reading, and it is two-sided.** A
gating kind whose decline rate sits at either end ranks `BROKEN`: at the floor it
declines nothing, so it is stamping every article it is shown, and at the ceiling
it declines everything, which is the same instrument dead from the other side.
Either way every other figure on the route is fiction, including the figures a
reader would use to decide the day was fine. The rule is two-sided because the
failure is two-sided: a floor-only rule would let a classifier that had stopped
answering print a reassuring tab. The two bounds
are arguments and not literals (Guardrail #6); row #12 of the placement plan moves
them to `console.decline_rate_floor` and `console.decline_rate_ceiling`. The
fraction itself is null until the classifier lands, so the rule fires on nothing
today and costs nothing to carry.

**Voices has two worst-state candidates and they are ranked.** A feed sitting at
`collect.reliability_floor` is `WORTH_A_LOOK`: it is the one state where the
ranker is actively discounting a feed as far as the multiplier goes, and until
this route no page said so. A live source that has decided fewer than
`collect.source_yield_alarm_min_decisions` addresses is `WORTH_KNOWING`, because
every quality figure about it prints a dash and a dash is invisible at a glance -
ranked lower on purpose, since too little evidence is not the same as bad
evidence and ranking it higher would publish a judgement the record cannot carry.
The fragment carries its denominator - `68 of 151 sources too thin to judge`, not
`68` - for the same reason every quality figure on this console sits beside its
item count: a bare count is a number with no scale. A third candidate, the count
of feeds that answered nothing in the window, was named in the row and dropped on
measurement: a feed that answered nothing scores zero, which clamps to the floor,
so it is a strict subset of the at-floor set and could never have reached the
label. That count becomes a figure row #13 draws. Authority: Susan, 2026-09-12.

**The strip never takes the health ramp.** The one thing that differs between
routes is a 3px rule under the active label, from the categorical ramp. Green,
amber and red on a label would say a route is failing, and a route is a noun.
[../../../frontend/tests/console-nav.spec.ts](../../../frontend/tests/console-nav.spec.ts)
reads the computed style of every tab and fails on any of the six verdict
tokens.

**Identity is otherwise identical across the five** - type scale, space scale,
radius, elevation, frame width, both ramps. The shapes they share live in
[../../../frontend/src/styles/app.css](../../../frontend/src/styles/app.css)
rather than in three scoped `<style>` blocks, because three copies are three
identities that happen to agree today.

## The standing band carries three things, and the strip is above it

The order down the page is title, strip, band, window control, content. Chrome
above content is the one ordering a reader never has to learn, and the band's
worst fact links into the strip - which on a phone used to sit 337px BELOW it,
where a reader had already scrolled past. The control comes last of the three
because a control read before any fact asks the operator to configure a page he
has been told nothing about, and because it governs everything under it and
nothing over it. Authority: Susan, 2026-08-31.

The band's three facts: yesterday's verdict as a sentence with one square per
run of that day, the one worst thing and what it costs, and site size against
the 1 GB limit with the articles the headroom buys. The pipeline derives it once
and publishes it as `console/band.json`; the console fetches it once in
[../../../frontend/src/routes/console/+layout.ts](../../../frontend/src/routes/console/+layout.ts)
and draws it once in
[../../../frontend/src/routes/console/+layout.svelte](../../../frontend/src/routes/console/+layout.svelte),
above all five route panels, so they cannot disagree about which route is
worst. A browser-build derivation was rejected; see
[console-payloads.md](console-payloads.md).

**The band was 340px on a desktop and 586px on a phone - 69 percent of an 844px
viewport - measured 2026-09-01 at bf37eeef.** Three changes pay for that: the
control moved out, the site-size fact dropped from about sixty words to one
line, and the page subtitle went from every route. The subtitle repeated
what the active tab's own description says 150px lower and cost 25px on every
route.

**The site-size fact is one line: the level, the limit and the articles the
headroom buys.** The rate it divides by, the days it was measured over and the
clause about which tree the cap measures live on `What one more article costs`,
which already owns the rate, its n and its spread - a band that repeated them
spent sixty of its hundred words on a caveat, and `idhazh site-weight` and
`committed payload tree` are not reader strings anywhere now.

**The worst-thing fact says what the state costs, and the strip keeps the short
form.** `15 feeds resting` on a label becomes `15 feeds are resting, so nothing
they carry reaches the digest. Each is asked again after 5 runs.` in the band.
The retry count comes from `availability_strikes_before_rest` and never from a
literal.
Repeating the strip's short form in the band was rejected: it would put the
same words 337px apart on a phone. Nothing in the sentence invents a task:
quarantine is self-terminating, so what it asks is that the operator knows the
digest is short of sources until the retry ([../sources/health.md](../sources/health.md)).

**A resting feed no longer outranks a failed run on a tie.** Both rank BROKEN
and the sort is stable, so listing the feeds first handed every tie to the state
that clears itself after five skips. The run candidates are pushed first.

**Free swap is a candidate on Hardware, and it is silent on a box with no swap.**
It is a precursor rather than a diagnosis: once the machine pages, read rate
collapses and a shard walks towards its time bound. The band names it and the
Hardware route is where an operator sees which shard. `os_swap_free_bytes` at
zero reads as "this box has no swap" and "swap is fully consumed" equally, so
the candidate is built from the pair and says nothing where `os_swap_total_bytes`
is zero or unrecorded. **Any swap used at all is the trigger, and the band
reports it as a fact rather than a verdict** - how far in is too far is a
threshold nobody here has measured, and a severity built on one would publish a
number this project has not taken. Authority: Susan, 2026-09-17.

**One line can appear under the three facts, and it is not a fourth.** A run that
folded segments an earlier run left behind says so, in the past tense: `This run
merged 303 rows that had been waiting 2 days. The Hardware page now reaches 17
September.` A member of the band stands on every route every day; this line is
absent on every run that found nothing waiting, which is every normal run - so it
does not compete with the three for the first viewport. Present tense on a page
that was just brought current would be a false sentence, and a false sentence is
what the Hardware route's own day-with-no-rows fix exists to delete. **What the
line cannot cover:** a run that never finishes writes no band at all, so nothing
appears however far behind the record falls. The band's `generated_at` is what
covers that. Where the three numbers come from, and why they are not a listing:
[console-payloads.md](console-payloads.md).

**The verdict fact draws one small square per run of the newest day**, on the
same `--fill-*` ramp and the same shape as `Run health` 800px below, capped at
twelve then `+N`. It says what the sentence cannot: whether one run ate all 34
failures or all five limped. It is hand-written markup, so it is on the page
before any script runs, and every square names its verdict in words.

None of the three is **windowed**, and that is the difference between the band
and the per-article cost panel on Pipelines. The band stands on every route, so
a figure that moved when a control on one route moved would read as three
different sites. The runway is taken over every published day on record.

The window control sits **below** the band, in a container of its own. Inside it
it was a control in a panel it does not govern - the band is deliberately not
windowed - and it cost 125px of the first viewport on a desktop and 195px on a
phone for four tiles and a sentence. Its
tiles and its status line share one row now where the column is wide enough for
both. Each route hands its own control the same props: Pipelines prices the
month files a wider window would fetch, and Summaries and Hardware fetch nothing
and price nothing. All three read the same `idhazh:console-window` key, so a
span picked on Pipelines is the span Hardware opens on and the other way round -
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts)
drives it both ways in one browser session, because a route that writes the key
and never reads it passes a one-way check.

**Machine joined the window on 2026-08-31, and until then it was the one route
without a control.** It printed a sentence naming the fixed span instead, on the
argument that a control which answers a click by changing nothing is worse than
an absent one. What that cost is the question the console exists for: an
operator who narrowed Pipelines to 7 days to look at a bad afternoon lost the
span the moment he asked what the machine had been doing, and two charts on two
spans cannot be compared. The route is also the one whose numbers move most
between runs, so it is the one where "over how long" matters most.
Authority: owner, 2026-08-31; Fowler concurs.

**Every span the control offers is answered on the server, one small object per
preset.** The browser holds no ledger - a token total, a cache share and a
recording note all read rows this page never receives - so it cannot
re-aggregate a window the way the Pipelines viewport can. Four small objects is
the price, and it is bounded: the widest preset is the widest anything on the
route can reach, so a run older than 90 days is carried at no span at all and
the page does not grow with the ledger. That is the same rule Model's per-preset
distributions follow, and the alternative was inlining every counter row so the
browser could re-bin it. Authority: Carmack, 2026-08-31.

**A panel about one run does not follow the window.** The shard board, the
reading-against-writing split, the clock check and the latency curves read the
newest run or the newest day the ledger holds, at every preset. A window is a
span and a snapshot is not something a span can narrow - a board that emptied at
7 days would say the run had stopped existing. The page states this once, above
the snapshots, and names the run they are about. Authority: Jony, 2026-08-31.

Eight surfaces on Hardware declare `data-windowed`, and each one prints the day
count in its own words: the run count at the top, the prompt cache, context
headroom, what the platform has been giving us, the server panel's three spans,
the latency plots, what a run reads against what it writes and the cost panel.
The refused-run list follows the window without declaring it, because a clean
span renders nothing at all and a surface that comes and goes cannot report a
day count.

## Four facts about every source we may ask

**On `/console/voices/`**, with the failure list, the clean-read count and the
truncation-cap cost. Its heading on the page is `Sources we may
ask, and what they yield`; "four facts" is what the panel does rather than what
it is called, and the phrase is load-bearing here because it is the argument
against combining them into a score.

Above the failure list sits the census the list needs: **one row per state, per fact, over the addresses a curator has left active**. Permission, reading, retirement and the publishing record, and no cell combines two of them. It is drawn from `frontend/public/source-health.json`, which the run writes once a day, and the page renders that decision rather than making a second one ([../sources/health.md](../sources/health.md)).

- **A table of states, not a chart.** Four categorical facts over 144 addresses, most of them in one state, is a tally - and a tally is a table. Every state is drawn whether or not it is empty, because a census that hides its empty states is a sample. The oracle asserts the drawn counts sum to the census, so a state that stopped being drawn cannot pass as a state nothing is in.
- **Every state says what it withholds while it holds.** `denied` withholds that source until a later run reads its rules, `unreachable` means the address is not asked at all, a rest withholds it until the probe, and a retirement withholds that address until its configured URL changes. A count with no cost beside it is a number nobody can weigh.
- **Then the sources held back, loudest state first.** Retirement and a refusal come before a rest, because a rest lifts itself and neither of those does. Capped at `console.source_rows`, with the tail in one sentence, exactly as the failure list is.
- **The curated title is not unique, so the row carries the id too.** Two feeds in this repository are both titled `Anthropic`, and the thing an operator edits is one configured address. The title alone drew two identical rows.
- **The publishing record is counts and never a rate while the record is short.** `collect.source_yield_min_complete_days` is 30 and the ledger is nine complete days deep, so the sentence prints what was offered, what was published and what a source lost, and says in the same breath that this is too short to read as a rate.
- **It does not follow the window control.** Permission, reading and retirement are read over the whole record, and the publishing record has a fixed span of its own. It declares no `data-windowed` surface for that reason, and its own spec asserts the span instead. On Voices that sentence matters more than it did on Pipelines: it arrived beside two panels that DO follow the control, so the paragraph saying it ignores one is the only thing separating them.
- **Its population is smaller than the failure list's, and it says so.** The census counts the addresses a run may ask; the list below reads the whole ledger, tombstoned feeds included. Measured 2026-09-03, the 24 tombstoned sources in the item ledger were offered 560 addresses over the window and published none, so the smaller population loses no publication and stops the denominator counting sources nobody may ask.

**Nothing fetches it, so nothing stages it.** `frontend/public/source-health.json` is read at build time by `sourceHealthView` in `frontend/src/lib/server/payload.ts` and never by a browser, so it is not copied into `frontend/static/` and `frontend/scripts/copy-visuals.mjs` is untouched. Its path is derived from `DIGEST_ROOT` the way `INDEX_ROOT` is, so a canary build reads the canary's own census.

**A missing or malformed view is a named absence, not a blank page.** The reader is the same guard `loadDay` uses - `null`, a list, and an object with no source list all parse cleanly and all three would reach the page as a section rendering nothing - and a view that cannot be read costs one section and logs one line.

Then comes **every feed that failed at least once, nearest to a rest first**, capped at `console.feed_rows` with the remainder in one sentence. A feed with a clean record is not in that list: the operator came here to find what is broken, and a list naming all 182 sources hides the 26 that are. The cap is applied on the server, because this list is inlined into the prerendered document and the rows it drops cost the page nothing; the list publishes `data-feeds-drawn` and `data-feeds-hidden` so an oracle can check that the cap counted what it dropped. The failing rule matches `FeedHealthRow.failing` in the contract exactly - a `200` that parsed to no entries counts as a failure, a `robots.txt` refusal does not ([../sources/health.md](../sources/health.md)).

**The count beside a feed is its run of failures, not its lifetime total.** The
pipeline rests a feed on failures in a row ending at the newest read, so that is
the number the page prints. A source that failed twelve times in July and
answered this morning is healthy, and a lifetime total printed beside a rest
marker is a number the pipeline never used to rest anything. The rule is
restated on the read side in `frontend/src/lib/feed-health.ts`, which runs the
same loop `discover.streak` runs, so a test can drive it with rows it made up.
Both read the same evidence as well: `feedResults` settles the ledger to one
row per feed per run before any panel counts it, by the same rule
`discover.settled` uses, so a run a second attempt wrote down twice is one run
on the page and one run in the pipeline ([../sources/health.md](../sources/health.md)).
Ranking follows the same fact: nearest to a rest first, then by how much has
gone wrong in total, because a feed four failures into a five-failure rule is
one run from being dropped and a feed with more failures spread over a month is
not.

**Each feed carries a target bar and a strip of days.** The bar's track is
`collect.availability_strikes_before_rest`, its fill is the run of failures, and
its marker sits on the threshold - the same `TargetBar` the truncation cap and
the minutes-per-visual rule draw with. The strip is one square a day over the page's
window, oldest to newest, on a single date axis every row shares, so "broken
since Tuesday" and "flaky all month" cannot draw the same picture. It shrinks to
fit its row rather than scrolling, because twenty scroll regions in one column
is not a list. Every square carries its whole day's tally as a sentence: colour
is one signal and never the only one, and the two outcomes that are not a
verdict - a polite refusal and a day nobody asked - take no verdict colour at
all. The squares that do are painted from the **fill ramp**, the same three
tokens the run strip above uses, so the console holds one health ramp rather
than two: a square this small is a solid, and the band ramp is weighted to be
read as type.
`Last result` stays free text, because it is the only human-readable cause on
the page and is never traded for a glyph.

**The console reads committed records in two ways.** The run strip, feed list and
timing medians still read the ledgers at build time. The item-health viewport
fetches the browser-safe monthly projection under `telemetry/<YYYY-MM>.csv`.
Nothing under `state/` is ever served - the browser reads only the narrow
projection that drops `canonical_url`, `url_key` and `detail`
([telemetry-series.md](telemetry-series.md)).

Stage timing medians read from `state/item-health/<YYYY>/<MM>/<DD>.csv`, not from
`state/scores.csv`. The item-health ledger has one row per planned item, so it
can answer "is it getting slower" even when the scorer did not run. The score
ledger still owns faithfulness and scorer time for the scored subset.

**The timing chart draws three stages, and `score_ms` is not one of them.** A
fourth `score_ms` line is rejected. The chart is titled `Time per item, by
stage`, so every line on it is something an item waits on - and the scorer reads
a summary the model has already finished, so nothing waits on it. A fourth line
there would read as a fourth constraint on the run. It is on the Summaries route now,
under `What one summary cost`, beside the cost of writing the summary it checks,
and it prints its middle and its slowest one in twenty over the summaries it
timed. An empty cell is one fewer item timed, never a zero; a zero is the value
the column defaulted to before it was written, and it is counted as untimed for
the same reason. Authority: owner, 2026-08-31.

The viewport is a 30-day default window, not a retention policy. The window size
and where today sits are `console.default_window_days` and
`console.today_anchor`. Arrow keys pan, and `+` / `-` step the window to the
next preset, from a labelled focusable control with a visible focus ring; the
buttons beside it pan with a pointer. **Every console chart is drawn on the
server before any script runs** - most as hand-written SVG, the rest prerendered
by the engine and swapped for a live chart on mount - so the page is complete
with no script and stays complete if none arrives. If a telemetry month is
absent or cannot be parsed, that month is a gap in the charts. It is not
interpolated, and it never white-screens the console.

## One window governs the page

The window belongs to the page, not to the viewport, and one control at the top
of the console sets it. It is a set of radio buttons carrying
`console.window_presets` - five spans, all five on the page at once, so the cost
of the wide one is readable without opening a menu. A slider was rejected for
the same reason: every span is a different number of month files to fetch, and
the spans between these five cannot be told apart once drawn. The narrowest is
one day, added 2026-09-06 as the cheapest read the console can do.

Three rules keep the control honest and all three are in the contract, so a bad
config fails the build rather than the page:

- `default_window_days` is a member of `window_presets`, or the page opens on a
 window with every button unchecked.
- The presets are ascending and distinct.
- Every preset sits between `min_window_days` and `max_window_days`.

A window of N days is exactly N days, even when the ledger holds fewer. It used
to shrink to fit the rows it found, which was invisible while nothing on the
page named the span and a lie the moment a control does - a page reading 90 days
while the charts draw 2 cannot be trusted about anything else. Empty calendar
space is the honest answer to "there is nothing there".

**Widening fetches, and the control prices it first.** A preset that reaches
into months not already in hand carries a `+2 months` label, and picking it
re-uses the same month-fetch path a pan uses rather than reloading the page, so
rows already paid for stay. The control shows a busy state while the files are
in the air. Narrowing costs nothing.

**The choice is kept in `localStorage` and read on mount, never during
prerender.** First paint is therefore always the window the server drew, so the
prerendered document and the control cannot disagree while the page hydrates.

Three surfaces on the console do not simply follow the span, and each says so on the page. The first two are on Voices and the third on Pipelines:

| Surface | Route | What it does | Why |
| --- | --- | --- | --- |
| `Feeds that failed` | Voices | The count and its marker read every run on record; the strip of days beside them follows the span | A windowed recount would disagree with the resting the pipeline actually performed. Two numbers for one decision is the defect the run strip already avoids. The strip answers a different question - when it broke - and that one is only readable over a span. |
| `Sources we may ask, and what they yield` | Voices | Permission, reading and retirement read every run on record; the publishing record reads `collect.source_yield_min_complete_days` complete days | It renders the run's own decisions, and the run rests on the whole count. The publishing record has a fixed span because that span is also its readability bar - one question, one number. |
| `What the ranking makes of each feed` | Voices | Reads the factor the run applied, over the span the run reduced it on | The run reduced it over `collect.reliability_window_days` when it happened. Redrawing it over seven days would print a number no run ever applied. |
| `Site size` | every route | Absolute number always; the delta and the runway are windowed | The size is a level and the operator wants today's whatever span he is reading. The delta and the runway are rates, and a rate has to say what it is over. |
| `Minutes per visual` | Pipelines | Prints `The rule reads 14 days. Widen the window to see it.` under 14 days | The retirement rule is stated over 14 days. A median of the wrong span is the same figure with a different meaning and nothing on the page to say which one is being read. |

**Known defect: two of those readers walk the whole score ledger and will lose
history when a day is deleted.** `pipelineChanges`, which draws the model-change
markers on `/console/` and `/console/machine/`, and `scoredDays` with
`modelByDate` on `/console/model/`, all read every committed score row rather
than the window. That is deliberate - a change marker has to sit on the day it
happened, whatever span is being read - but `idhazh prune-state` archives a score
month past `observability.scores_full_grain_months` and deletes that month's day
files, and the archive carries cohort totals rather than dated rows. So from the
first live deletion those three lose the dates in the deleted month. **No number
a reader sees moves; a date list silently shortens.** Reported 2026-09-02 and
left as it is, because deletion is still in dry run. Before that switch is
thrown, either teach the readers to union the archive's cohort dates or say on
the page how far back the marker list reaches.

`Sources cut short most often` used to hard-code seven days. It follows the
control now, and the section prints its own denominator, which at seven days
runs as low as six articles. Its rows are aggregated once per preset at build
time - four sets of ten costs less than one fetch, and it keeps the section
working with no script at all. It follows the window's *length* rather than
where a pan leaves it, and the section says so: the days it reads always end on
the newest day the ledger holds.

`Visuals published` used to draw a smoothed line over a fixed fourteen days,
under a control reading thirty. It is one bar a day over the control's own
window now, and the count above the bars is that same window summed, so a
reader adding up the columns gets the number the card printed. Bars rather than
a line, because a count per day is a discrete quantity and a line between two
days claims a value for the hours in between that nobody counted. The strip is
markup rather than an engine drawing: it is complete before any script runs,
and it follows the control with one drawing instead of a server-drawn seed and
a client redraw that can disagree about the span. A window that published
nothing prints the count and no strip at all, because thirty bars of zero is an
empty plot area and a card is still a card without one.

**`Articles published` sits beside it, and it is the denominator.** A strip that
prints how many visuals were drawn without saying what they were drawn for is
rejected: a reader could not tell a busy day from a well-illustrated one - 185
visuals is most of a quiet fortnight and a rounding error on one heavy day. The
two cards read left to right as the fraction they are, articles first, and each
carries its own total for the window on screen.

**One function draws both strips, and each is drawn against its own busiest
day.** `publishedSkyline` takes the measure as an argument, so the two cannot
drift in the one property that makes the pair readable: both are one bar a day,
over the same window, at the same pitch, with the same left edges.
[frontend/tests/console-published.spec.ts](../../../frontend/tests/console-published.spec.ts)
asserts the two strips report the same `data-published-days`, which is the whole
of "they are on one window". Each strip normalises to its own peak rather than
to the larger series: articles run two orders of magnitude above visuals on the
committed ledger, so a shared scale would draw every visual bar as a hairline
and the smaller card would stop saying which of its own days were heavy.

**One chart with both series was refused.** Two axes invite a comparison of
slopes that means nothing, and one axis flattens the smaller series to nothing.
Authority: Jony, plan row #10.

The card is labelled `Visuals published`. It counts visuals in state
`rendered`, the section above it is `Visuals drawn for articles` and the table
column is `Visuals published`, so calling the card `Charts published` would name
a drawn thing with the wrong word. Its label is also a test selector, so the
selector must move with the reader-facing string.

**The prerendered seed carries that same window, and no more.** The server used
to concatenate every committed month and inline all of it, so the console
document grew for as long as the pipeline ran - a reader downloaded four months
to look at thirty days, and would have downloaded a year by next summer. It now
reads `console.default_window_days` back from the newest day on record, which is
the window the viewport opens on, so the two cannot disagree.

Measured 2026-08-26 on one Windows dev machine, against four months of real row
volume - the committed August shard (2,000 rows, 171 KB) plus three copies of it
shifted back a month each, 8,000 rows in all:

| | Raw HTML | Gzipped | Rows from the three older months |
| --- | --- | --- | --- |
| Before | 3,461,576 | 600,925 | 6,000 |
| After | 2,252,783 | 490,912 | 0 |

That is 18% off the gzipped document and 35% off the raw one, and the saving
grows with every month committed. One build per case; a prerender is
deterministic, and a control pair that the window could not affect differed by
7 gzipped bytes, which is the noise floor here.

**On the corpus committed today it changes nothing**, because that corpus is
two days long and a corpus shorter than the window is already inside it. The
defect was one of growth, and it was measured before it arrived rather than
after.

Two consequences worth stating, because both are the reason this is safe:

- **Nothing became unreachable.** The monthly shards are untouched. Panning back
 fetches `telemetry/<YYYY-MM>.csv` exactly as it always did, so the dropped
 days are one arrow key away rather than gone. That fetch path already existed
 and was dead code: with every month in the seed, there was never a month left
 to fetch.
- **The cutoff is anchored on the newest committed day, never on the build
 clock.** Anchored on today, a corpus that stopped last month would seed an
 empty console - the page would go blank precisely when the pipeline broke,
 which is when an operator needs it.

The read is bounded too. A window is a count of days, so it straddles a month
boundary and reads two shards at worst; every older shard is skipped unopened,
however many the repository has accumulated.

## Why a summary was doubted, and the one ledger that can answer it

The Summaries route draws the five reasons a summary failed to reach the top
band, one column a day, over the window the page shares. The measure cards above
it say how often the checker stopped; this says which check failed.

**It reads the committed day payloads, not `state/scores/`.** `band_reason` is
decided by `verdict` and written onto the published item by
`assemble.build_day`. The score ledger's 35 columns carry the inputs a reason is
decided from - `hhem`, `coverage`, `unsupported_numbers`, `hedge_dropped` - and
the band, and no reason column at all. So the route walks `DIGEST_ROOT` the way
`publishedItems` already does for the Pipelines route, and what ships is one
count per reason per day rather than the payloads. Re-deriving the reason from
the ledger's inputs was refused: it puts a second copy of `verdict` in a second
language, and the day the two disagree the console is wrong about the item a
reader was shown ([../../concepts/evaluation.md](../../concepts/evaluation.md)).

**The five are drawn apart and never added into one doubt count.** A single
number says how often the checker stopped and never says which fault to go and
fix. Each item carries at most one reason, so the five add up with nothing
counted twice - which is what makes the stack legal and what the oracle checks.

**Stacked, with a switch to lines.** The same array draws both with only `type`
and `stack` moving, which is the condition
[../../concepts/design-system.md](../../concepts/design-system.md) sets for that
control. Picking `Lines` reaches the live chart, not only the prerendered one. A
chart carries an explicit lifetime now - it hydrates, draws when a reader comes
within a screen of it, takes a changed option through `update`, and is
destroyed once - and a small `$effect` in
[../../../frontend/src/lib/charts/Chart.svelte](../../../frontend/src/lib/charts/Chart.svelte)
hands the live chart each new option, so a control that moves the shape or the
window is followed without a rebuild.

**A reason with no items draws nothing, so the panel names it in a sentence.**
`not_scored` has never fired: it needs a missing faithfulness score, and the
scorer has run on every production item. A series that is zero everywhere is
dropped by `stacked`, so without the sentence a reader cannot tell a fault that
never happened from one nobody looked for.

**The column total is the day's reason count, never its doubtful count**, and
the difference is printed. 369 doubtful summaries carry no reason, all of them on
the three days published before the field existed. A panel that folded them into
a band would draw a fault the checker never named; one that dropped them silently
would make three days look clean.

**It does not declare `data-windowed`.** The exact list of surfaces that do is an
oracle in
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts),
and that oracle is stronger for being exact. The panel honours the same control
and proves it in its own spec, by driving the control to each preset and reading
the control's own attribute back against the panel's.

**The panel cost 5,557 gzipped bytes on `/console/model/`**, measured 2026-09-05
over five builds against `origin/main`'s own source on the same tree. It is
recorded so nobody prices a panel like this at nothing; the route's ceiling is
not derived from it and never was.

## Every instrument the checker writes, and the panel that owes it a number

The Summaries route draws three more panels: the faithfulness score, the lead
coverage, and a table of the six instruments nothing acts on. What matters more
than any of the three is the map they ship with.

**The artefact is `DRAWN_BY`, not the charts.**
[../../../frontend/src/lib/console/eval-instruments.ts](../../../frontend/src/lib/console/eval-instruments.ts)
assigns every measured column of `state/scores/` to exactly one panel, and
`NOT_A_MEASUREMENT` says of every remaining column why it is not one - fifteen
identity and provenance columns, each with a sentence. Between them the two must
name every property of
[../../../schemas/eval-row.schema.json](../../../schemas/eval-row.schema.json),
once, and name nothing else.
[../../../frontend/tests/console-model-instruments.spec.ts](../../../frontend/tests/console-model-instruments.spec.ts)
compares the two sets in the ninety-second gate. So a column added to `EvalRow`
next month fails a test rather than going undrawn, which is what happened here:
`hhem` and `coverage` were scored on every summary from the first published day
and read by nothing on the site for two weeks.

**The scope said two panels and the survey said six columns more.** Row 4 of
[../../../TODO/20260905-03-console-backfill-plan.md](../../../TODO/20260905-03-console-backfill-plan.md)
named faithfulness and lead coverage and stated the goal as *every* existing
instrument reaching the console. Counted 2026-09-06, ten of the ledger's twenty
measured columns had no reader anywhere in `frontend/src`. The two named ones got
their own panels; the other eight went to the third. Drawing two and calling the
goal met would have left the map failing its own test on the day it was written.

**`hhem_full` and `hhem_delta` are a sentence, not a second chart.** The checker
scores each summary twice, once against the text the machine was given and once
against the whole article, so a summary that only looks faithful because the
article was cut cannot pass. Measured 2026-09-06 over 6,966 rows the two readings
differ on **7 of them**, because production hands the same string to both - the
finding recorded in [../../concepts/evaluation.md](../../concepts/evaluation.md).
A chart of a number that is flat on 99.9 percent of rows teaches an operator to
stop looking; a sentence saying how often it parts, and by how much, is the same
fact at the size it is worth.

**Nothing sets a bar, and that is decision 2 of the row.** No threshold line, no
red, no band tint, no polarity - and the spec fails the build if a tinted element
appears inside either score panel. The committed window is fifteen days and the
summarizer is about to change twice, so a threshold taken off it would be a guess
wearing a measurement's clothes. The one number that *is* a bar - the configured
lead-coverage share - is printed as a count of summaries under it and never drawn
as a line to fail against, because it caps a summary at "fairly sure" and has
never on its own marked one "not sure".

**Two lines on faithfulness, one on lead coverage.** Measured 2026-09-06 over the
fifteen committed days, the middle summary's faithfulness sat between 88 and 95
percent while the lower quarter swung from 73 to 94 - so the level and the tail
are two different facts and both are drawn. Lead coverage does the opposite: the
middle summary sat between 57 and 64 percent every single day, so a line of it
beside a moving one would read as the important one. What moves there is the
share of a day that fell under the floor, and that is what is drawn; the level is
in the readout strip and the headline.

**Lines, and no shape switch on either.** One percentile added to another is not
a quantity, and neither is one day's share added to the next day's. The condition
[../../concepts/design-system.md](../../concepts/design-system.md) sets for
carrying that control is that both shapes read the same array honestly. Bars
here would not.

**A day is that day's middle summary, and the recorded table says so.** A median
over the whole window needs every summary's reading, and carrying 6,966 of them
into the page to print four figures is not a trade worth making. The table prints
the quietest day, the middle day and the loudest day, each by its own middle
summary, and names that in the panel rather than leaving a reader to assume a
window median.

**The two densities are drawn per thousand words, not per word.** Per word they
are 0.011 and 0.004 - two numbers a reader cannot tell apart, neither of which
reads as a quantity of anything. Per thousand words they are 11.0 and 4.0
markers, which is a count of phrases in about four pages.

**Neither new panel declares `data-windowed`**, for the reason the doubt-reason
panel does not, and each proves it honours the control in its own spec.

**The faithfulness plot fails a sufficiency check on purpose.** Its axis runs
from zero to a hundred, so the fifteen committed days sit in the top fifth of
the plot and four fifths of it is empty - which is
[../../concepts/design-system.md](../../concepts/design-system.md)'s first check,
does it use the space it is on, answered no. Cropping the axis to the data would
fill the plot and would also turn a four-point drift into a cliff. This panel
exists because a band could not show a four-point move; a plot that shows a
four-point move as a collapse is the same failure with the sign flipped. The
empty four fifths is what tells an operator the movement is small, and that is
worth more than the space. Recorded here rather than waved through, per
`CLAUDE.md` section 9.

**The three panels cost 5,930 gzipped bytes on `/console/model/`**, measured
2026-09-06 over five builds against `origin/main`'s own source on the same tree.
The other two console routes moved 2 B and 4 B, inside the build noise floor, so
the change reaches one route. The live ceilings use one convention, `gzip -5`,
and the live numbers are in
[../../reference/site-weight.md](../../reference/site-weight.md#the-page-guardrails-and-what-each-route-weighs-2026-09-10)
and what to do when one fires is in
[../../how-to/run-the-gates.md](../../how-to/run-the-gates.md).

## Where a run's time went is one panel on Pipelines, at two grains

| Panel | Grain | The sentence it is for |
| --- | --- | --- |
| Where the run's time went, on the run's own clock | one bar an item, or one bar a shard | Whether the run queued or worked in parallel, and where in it the time actually went. |

**It answers "is it working".** It takes the run's central shape - what it took
end to end, what its items cost added up, and how many ran at once - and it
covers every item of the run rather than picking the worst one out. The grain
switch changes the row and never the question.

**It sits low on Pipelines, and `Run health` is the route's first panel.** A
window is a span and this panel is one run, so an operator reaches it after a
windowed panel has told him which run to open it on - and the panel that
verdicts the route goes first, which is the thirteenth chart rule applied
([../../concepts/console-design.md](../../concepts/console-design.md)).
Pipelines takes one untitled group in `console.panel_groups`: what it needed was
an order, not headings, and it already carries four section headings of its own.
Authority: Row #27, 2026-09-20.

**Two panels became one on 2026-09-20, and the grain is why.** Hardware drew a
shard's clock from `state/span-rollup/` beside an item timeline from
`frontend/public/run-timeline/`. Two folds over two ledgers can name different
runs as the newest, and on the committed data they routinely did - the rollup and
the published mirror start on different days. The merged panel folds both grains
from one set of rows in one builder call, so a step's seconds are the same
seconds whichever row a reader is on. A shard's bar runs from its first item's
start to its last item's end, which is the stretch it held a worker for, and its
steps are that shard's items added up.

**The shard panel is deleted rather than shrunk, because thickness was never the
defect.** Measured 2026-09-17 over 23 shard rows of
`state/span-rollup/2026-09.csv`, the four sub-steps of a shard's clock together
drew **0.026 px of a 760 px track** and the residual drew **0.039 px**. A browser
paints neither, so the panel published a legend teaching a reader that four
categories were zero when they were only unmeasurable at that scale. No bar
thickness fixes a band that narrow. Authority: Susan, 2026-09-17.

**Every figure it carried survives, printed.** The four sub-steps sit under the
bars as figures, each beside the step it runs inside - `tag read` is the tagging
step inside taking the article out, not a step beside it, and a reader who takes
it for one adds it twice. The overhead outside every item is printed with them,
and the run's item time plus that overhead is still the shards' whole clock.
Nothing visible was lost, because none of it was ever visible.

**Hollow is unclaimed, hatched is overclaimed, and both carry a legend key.** The
owner could not name the hatched notch on sight, which is the test: a texture
nobody can read is a texture that says nothing. Neither is tinted - nobody has
agreed how much overhead is too much.

The readers are
[../../../frontend/src/lib/server/run-timeline.ts](../../../frontend/src/lib/server/run-timeline.ts)
and
[../../../frontend/src/lib/server/span-rollup.ts](../../../frontend/src/lib/server/span-rollup.ts);
the producer of the published mirror is
[../../../backend/idhazh/telemetry/publish/run_timeline.py](../../../backend/idhazh/telemetry/publish/run_timeline.py),
its shape is [run-timeline.md](run-timeline.md) and every drawing rule is
[../../concepts/console-design.md](../../concepts/console-design.md).
[../../../frontend/tests/console-pipeline-timeline.spec.ts](../../../frontend/tests/console-pipeline-timeline.spec.ts)
holds the shard grain against the item grain per shard and per step, and fails on
a declared column that is empty across every canary row.
[../../../frontend/tests/console-substeps.spec.ts](../../../frontend/tests/console-substeps.spec.ts)
re-derives each printed figure straight from the committed rollup cells, proves
the sub-pixel rule on a built fixture in both directions, and reaches the empty
state through a rollup truncated to its header. The fixture rollup the canary
draws is written in
[../../../frontend/scripts/build-canary.mjs](../../../frontend/scripts/build-canary.mjs).

**It is a snapshot, so the window control does not reach it.** A bar's position
is measured from its own run's start and a span cannot narrow one run, so the
panel names the run it drew. It reads one published directory bounded to two
months and one `state/` ledger bounded to the archive window, and with either
gone the view is empty by construction and the route still renders whole.

**Pipelines now depends on `$lib/charts/machine` for its `seconds` formatter, and
on `STATE_ROOT`.** Both arrived with this panel. The second is the one worth
knowing: a build with `STATE_ROOT` unset draws the named empty state for the
sub-steps, which is correct rather than broken.

## What one item cost the model is two clocks, drawn apart

`What one item cost the model` is a section of the Pipelines route with two
distributions and seven printed figures. It answers what a run total cannot: how
long the model spent on **one** article, split into the part it spent reading and
the part it spent writing.

The Hardware route already pools both quantities per run and per shard, out of
the model server's own counters. That is a different measurement of a different
thing, and it cannot say that one item in nine got nothing from the prompt
cache. This section reads the published projection, per item, and follows the
window control.

### Reading and writing are two charts, and pooling them is refused

Measured 2026-09-05 over the 6,104 items of the committed projection that carry
both clocks: a prompt token costs about **101 milliseconds** to read and a
written token about **183** to write, so a written token costs **1.8 times** a
read one. The two also move for different reasons - the article's length moves
the first and the summary's length moves the second - so an operator acts on
them separately. One `model seconds` chart would hide which of the two moved.
Carmack, plan 03 Row #2 rejected alternative 1.

The panel prints both rates and the ratio, and then says the thing the ratio is
for: cutting a hundred tokens from the summary saves more time than cutting a
hundred from the article. The sentence is derived from the measured ratio rather
than written down, so it flips if the ratio ever does.

Both are drawn as **doubling bins**, by the same `distribution` the Summaries
route's two clocks use. It moved to
[frontend/src/lib/charts/series.ts](../../../frontend/src/lib/charts/series.ts)
on 2026-09-05 so a route outside `$lib/server/` could reach it - four panels now
share one binning and one pair of rules, rather than four that can drift apart.

The axis is a doubling and not a linear one, and the ledger says why. Measured
2026-09-05, reading one prompt runs from **1.4 seconds to 692**, which is nine
doublings; on a linear axis every bar but one is a hairline against the left
edge. Writing is the opposite shape and is drawn the same way on purpose:
**4,456 of 6,104** items land in one bin, 32 to 64 seconds, and drawing it
linearly would suggest a spread the measurement does not have. `fetch_ms`, whose
worst is 43,627 ms against a middle of 567, is not in this section at all - it is
a stage clock and `Time per item, by stage` above already draws it per day.

### The prompt cache is a share, and the share is printed rather than drawn

The panel prints **absolute prompt tokens** - the ones the model read against the
ones it did not - and the share beside them as whole percent. Four more figures
sit under those three: the middle prompt, the middle summary, the middle item's
own share, and how many items were read whole with nothing held over.

**A two-segment track is refused, and the track is gone.** One flat bar on no
time axis, under a note telling the reader not to read its direction: a figure a
panel disowns is a figure to remove. **What the
reader loses, named:** the picture of the split, which is now three printed
counts instead. What the split was ever worth was the counts it was built from,
and the track carried no fact they do not. Susan, 2026-09-17.

**The deleted track and the Hardware route's `Prompt cache` panel were one
subject at the two questions.** This panel carried the level - how much of the
window's prompt the model already held - and `Prompt cache` carries the
direction, one column a day. With the level deleted the Hardware panel is the
whole answer rather than half of one, so the gap a later reader sees here is a
subject already covered and not a figure to rebuild.

**A falling share here does not mean the cache got worse, and the panel still
says so.** Measured 2026-09-05 over the same 6,104 items, `cached_tokens` is
nearly a constant: the middle item kept **922** tokens and the widest kept
**941**, while `input_tokens` runs from a middle of 1,688 to a worst of 7,093. So
the share moves almost entirely because the denominator moves. Drawn as a line
over time it would fall on a week of long articles and read as a cache
regression, which is the one wrong thing an operator could act on. That sentence
is the reason a figure is missing, which is the kind of sentence this console
keeps.

**The plan's own illustrative range did not survive the measurement.** Plan 03
Row #2 decision 1 quotes `0.72 to 0.90`. Measured over the committed projection
the per-item share has a middle of **0.518**, a 5th percentile of **0.000** and a
95th of **0.820** - and **667 of 6,104** items reused nothing at all. The
decision itself stands: the share is drawn, and it is named in words beside it.

**From 2026-09-12 these four figures are about the FIRST model call, not about
the item.** An item read by two calls always reuses something, because the second
call replays the first call's prompt and is answered for it - so "read whole with
nothing held over" taken off the item total would count nothing for ever, a live
figure becoming a constant with no code change. Where the projection publishes a
split, the four read `label_*`; where it does not, they read the totals as they
always did, and `perCall` says how many rows of the window were which. Every rate
on this section still pools the totals, which is correct: a sum over both calls is
what the item cost
([the split](../summarize/throughput.md#each-call-is-charged-on-its-own-and-the-item-is-their-sum)).

### Every denominator is its own, because three of them differ

An item that failed before the model saw it has no clock and no token count; one
that failed before the fetch has no stage clock either. Measured 2026-09-05 over
the committed projection: **8,300** rows in all, **6,873** with a stage clock and
**6,104** with the model's own two. One "items" figure would be wrong for at
least one column of this section whichever row set it counted, so each figure
carries the count it answers for and the lead states the widest one.

An empty cell stays empty. A mean that treats an absent instrument as a zero
turns every fetch failure into a fetch that was infinitely fast, and zero reuse
is a real answer that has to stay counted - which is why `readWhole` is a count
and not an exclusion.

### It follows the window's length, not a pan

The reduction is taken on the server, once per entry in
`console.window_presets`, and the browser picks the open one - the same
arrangement `Sources cut short most often` and the Summaries route's
distributions use.

**That is a measured choice, not a preference.** The prerendered seed carries the
eight columns as nulls, because seeded with their real values they cost
`/console/` **176,753 gzipped bytes** - 198,624 to 375,377, and 98,182 over the
recorded ceiling (measured 2026-09-05, recorded in
[telemetry-series.md](telemetry-series.md)). The two alternatives the seed note
offered were to seed the columns this section draws, or to drop the seeded months
from `loadedMonths` and let a runtime fetch fill them. Both were refused: the
first buys the ceiling problem the seed note was written to avoid, and the second
puts a 244 KB fetch behind the first click of a control and leaves the section
blank until it lands. Reducing on the server costs the page about a hundred
numbers a preset and draws complete before any script runs.

What it costs is stated on the page: panning does not move these days, and they
always end on the newest day the ledger holds. The section says so in the same
words `Sources cut short most often` does, because one rule stated two ways reads
as two rules.

Authority: Carmack (Engine & Runtime) on the two clocks and the axis, Fowler
(Architecture) on one binning shared by four panels, Reader on the sentence
beside the share; plan 03 Row #2, 2026-09-05.

## Extraction answers both questions, and labels which half is which

`Extraction` is a Pipelines panel in two halves, and it is the console's worked
example of a panel that serves *is it working* and *what is broken* at once
rather than choosing.

The **verdict half** is four cards: articles the reading found enough figures of
one kind in, the share of published chartable articles that went out with no
chart, the share of articles whose every fact still cuts its own characters, and
the facts kept over the window. Four levels, covering the whole reading. They
carry `data-extraction-question="is it working"`.

The **break half** is one chart, `Whether the yield is falling`, carrying
`data-extraction-question="what is broken"`. Two of the cards' own lines tell the
operator to read the direction rather than the level, so the panel plots one
point a day: articles the reading found enough figures in, against published
articles carrying a chart. That pair
is the discrimination the panel exists for - the planner stopping and the
extractor stopping look identical in the published chart count alone, and they
have different fixes ([../../concepts/evaluation.md](../../concepts/evaluation.md)).

**Both series count articles, so they share one value domain**, and the panel
prints the ratio it measured. Measured 2026-09-17 over the nine committed day
records that carry an extraction block: `chartable` peaks at 225 and
`chartable_charted` at 20, which is **11.3 times** and inside the 20 a shared
axis holds. The domain is taken from the days drawn rather than fixed - there is
no ceiling here to measure distance from, so a fixed maximum would only waste the
plot on a quiet day.

**A window with one measured day draws that day as a point, not an empty plot**,
and says in words that a single day has a level and no direction. A window with
no measured day draws no axis at all and says so: an axis over nothing is a claim
the data does not support.

Authority: Susan, 2026-09-17. The four rules this panel is built to - a panel
names which of the two questions it serves, a title that asks a trend question
draws a time axis, two series share one axis under twenty times with the ratio
printed, and a value domain is fixed only where a ceiling is the comparison -
are in
[../../concepts/console-design.md](../../concepts/console-design.md#thirteen-rules-hold-for-every-chart-on-this-console).

## The chart drawing is a flow, and every drop leaves it as a named branch

`Visuals drawn for articles` opens with one diagram of where items go between the
work stage reaching one and a visual reaching a page. It is drawn left to
right, the direction the page reads and the order the pipeline runs its stages
in, and it totals the whole open window rather than one day - a single day's four
numbers are already legible in the table under it, and "where do items go" is a
question about the window.

**A funnel is rejected because it cannot answer the question this page asks.** A
funnel draws a monotonic sequence as a taper, so it says how much is left at
each step and nothing about where the rest went. The
three drops here have three different causes and three different fixes: an item
can be answered without the model being asked at all, the model can be asked and
draw nothing, and a drafted chart can fail the checks that run after it. A taper
shows all three as one slope. Every loss now leaves the flow as its own branch,
labelled `Answered without a visual`, `The model drew nothing` and `Did not
survive the checks`, and the branch is as wide as the number of items in it.

**The widths conserve, and that is asserted rather than assumed.** What leaves a
stage is what arrived at it: the branch that carries on plus the branch that was
lost. `frontend/tests/charts.spec.ts` recomputes the four stage totals from the
fixture and checks every node against them, so a layout that drew a plausible
shape from the wrong numbers fails. A flow whose widths do not conserve is
drawing a picture, not the data.

**A branch of zero is not drawn.** A stage that lost nothing has no loss to
show, and a zero-width branch with a label beside it reads as a loss too small
to see rather than as no loss at all.

**A window that gains items prints a sentence instead of a diagram.** The four
counts are not guaranteed to fall: a chart published inside the window can have
been drafted before the window opened, and the committed ledger holds exactly
that - 2026-08-25 recorded 23 drafted and 27 published. Over a whole window the
totals came back monotonic (2,121 reached, 1,425 asked, 144 drafted, 124
published on 2026-08-30), but a narrower window need not, and the drop would be
negative. The diagram steps aside and says which stage gained, because a
negative branch cannot be drawn and a clamped one would be a lie about the
count. The table below it still holds the numbers. Zero reached is the other
empty state and keeps its own sentence, so the two nothings are never one blank
panel.

**Colour is the categorical ramp, and a loss keeps the hue of the stage it
left.** Every fill comes from `PALETTE` through the sentinel bridge, so both
themes resolve with no JavaScript at all; a loss branch is the same hue at 0.28
opacity against the flow's 0.55. A second hue would say a loss is a different
kind of thing, and it is the same items going a different way. Both opacities
are low because a label to the right of a node sits over the links leaving it,
which is unavoidable in a flow this shape - the label has to stay readable
across them.

**Every label sits outside its node, on two lines, carrying the count and the
share of everything reached.** The narrowest node on the committed ledger is
under three pixels tall, so a label inside it would be unreadable - the defect
the funnel already had to fix once. Three measurements set the geometry, all
taken in the browser on 2026-08-30:

- **Two lines, not one.** `Answered without a chart 696 (33%)` ran 280px into
 a 246px column pitch and printed over the next stage's label. Split, the
 widest line is the name alone.
- **The right margin is 170 pixels, not a share of the width.** A label does not
 shrink with the frame, so a percentage leaves too little on a narrow screen -
 the first case reserved 30 percent and still clipped `Did not survive the
 checks`, which measures 151px at 12px type.
- **The node gap is 34 pixels, against the engine's default of 14.** `Published`
 and `Did not survive the checks` are 13.8px and 2.2px tall over the committed
 ledger, so at 14px their two-line labels shared nine pixels of one line. A
 two-line label is 31px and the gap has to carry it.

`depth` is set on every node rather than inferred, because an inferred layout
justifies dead ends to the far edge - it would draw the first stage's loss
beside the last stage's.

**The Sankey layout cost 5,672 gzipped bytes of lazy chart chunk**, measured
2026-08-30 by registering `SankeyChart` in place of `FunnelChart` - the whole of
the difference, with both cases byte-identical on every build. That left **2,439
bytes under the 200,000-byte line** the chart vocabulary is held to, which is
1.2 percent: **the next chart type registered crosses it**, and the answer then
is to measure what the current set costs before adding to it. The option builder
grew 616 bytes of first-load JavaScript; the engine is still a lazy chunk
nothing preloads.

**The recorded chunk size was already wrong before this landed, and by more than
this change costs.** `docs/concepts/design-system.md` carried 153,204 B from
2026-08-29, when only the funnel, the tooltip and the SVG renderer were
registered. The six figures added since brought bar, line, pie, grid, legend and
mark-line with them and nobody re-measured, so the record sat 38,685 B - 25
percent - under the truth. The number is corrected there in this commit, and the
lesson is the one `core.ts` already states: the registration list is a file
somebody has to edit, and re-measuring it is the reason it is. (The legend came
back out on 2026-08-31, when the readout strip became every chart's key: 5,532 B
gzipped, re-measured in the same commit.)

Authority: the shape, Jony, 2026-08-30; the chunk, Carmack, 2026-08-30.

## The chart drawing is judged against its own rule, and the daily rows come second

`Visuals drawn for articles` is the only console section carrying a written
decision rule in its own prose: over a stated span chart drawing is retired if the
median day spends more than a set number of minutes per published visual, or
puts a visual on fewer than a set share of the items it published. A paragraph
with the rule but none of the three numbers is rejected. Seven columns of daily
counts cannot ask the operator to take a fourteen-day median of a ratio, twice,
against two limits that are nowhere on the screen.

The section leads with the two figures the rule names. Each is a `TargetBar` -
the track at the threshold's own scale, the fill at the window median, a rule
drawn at the threshold - with a `Sparkline` under it, because `4.2 and falling`
and `4.2 and rising` are different pictures and a single number is neither. One
sentence above them states both figures and which side of its threshold each
fell on.

**The sentence and the two bars are one computation.** `chartRule` in
[frontend/src/lib/charts/glance.ts](../../../frontend/src/lib/charts/glance.ts)
returns the medians, both bars' geometry, both trends and the sentence together,
and the browser suite asserts the printed sentence is byte-identical to the one
the module builds. A verdict written in the template could say `inside` while
the bar beside it drew a fill past its marker, and nothing on the page would
look wrong.

**All three numbers are config.** `console.chart_rule_days`,
`console.chart_minutes_target` and `console.chart_coverage_pct` live in
`config/appearance.json`, bounded by `ConsoleConfig`. Hard-coded TypeScript constants are rejected because they would make the one
section that states a threshold the one section an operator could not move a
threshold on (Guardrail #6).
The contract also refuses a preset list whose widest span cannot reach
`chart_rule_days`: a rule no preset can show would print the
widen-the-window notice at every setting of the control, which reads as a broken
surface rather than as a narrow window.

**Coverage divides by what the day published, and a day that published nothing
has no share at all.** The denominator is the item count on the day's own
`digest.json`, read in the same pass that counts its charts, so no new telemetry
column was published to answer this. A quiet day returns null rather than zero
percent: zero would say chart drawing ran and reached nobody, and nineteen quiet days
would drag the median of a healthy fortnight onto the floor. This is the
null-is-not-zero rule the timing medians already follow
([../../concepts/design-system.md](../../concepts/design-system.md)).

**Neither bar takes the health ramp.** These are limits somebody chose, not a
verdict on the machine, so `TargetBar` draws them in its `policy` tone. The
marker carries the fact. Tinting a policy threshold green would invent a health
judgement nobody agreed to, which is the same mistake as a chart borrowing the
band tokens.

**Below the rule's own span the section prints the notice and no number.** The
window control governs the medians, and under `chart_rule_days` the section
says `The rule reads 14 days. Widen the window to see it.` and draws no bar. It
is the same sentence and the same reason as the glance card next to it: a median
of the wrong span is the same figure with a different meaning, and nothing on
the page would say which one is being read. The section carries
`data-windowed="chart-drawing"` and states its span in words at every setting, so
the window oracle in `frontend/tests/console-window.spec.ts` holds it to the
control like every other windowed surface.

**The seven daily columns are behind a native `<details>`, not a button.** The
console is complete before any script runs and stays complete if none does, so a
button plus a conditional block would leave the rows permanently unreachable
with JavaScript off - the rows would be gone rather than on demand. A disclosure
is keyboard-reachable for free and says which state it is in without a second
label. `Reached`, `Asked the model`, `Visuals drafted` and raw `Minutes spent`
moved down with the table: the flow diagram above already draws the first three
as branches, and the minutes on their own are the numerator of the ratio rather
than a decision. Nothing was deleted, and the table gained the `Items published`
column that coverage divides by, so the share and its denominator sit on one
row.

**The section cost 1,915 gzipped bytes of first-load JavaScript on `/console/`**,
measured 2026-08-30 over four builds spanning 6 B, against six untouched routes
that moved -4 to -12 B - so the delta is the change and not the toolchain. **No
chart type was registered**, so the lazy engine chunk did not move at all.

Authority: the two bars and the verdict, Susan, 2026-08-30; the disclosure
element, Jony, 2026-08-30.

### Both daily tables follow the window, and shut they are not cards

The Pipelines table and the Summaries table are the two `<details>` on the
console that hold a row per day. Both follow the control above them, because two
answers to one question on one page is exactly what a shared control was built
to remove.

Both are windowed now, and both take one name, byte-identical at the same
preset: **Show these figures day by day, over these N days.** `Show the daily
figures` was refused because "figures" names nothing on a page that is nothing
but figures. The day count is on the line that opens the table, so an operator
knows what he is opening before he opens it.

**Neither table is deleted, and the Pipelines one was the closer call.** Most of
what it holds is already drawn above it - the flow covers reached, asked,
drafted and published, and two target bars with their sparklines cover the
minutes and the coverage. Only `Items published` is uncharted. It stays as the
per-DAY reading of a window-level picture: it is the only place a printed rate
can be checked against the two counts it was divided from, and the only way to
attribute a window aggregate to a day. Authority: Susan, 2026-08-31.

**On Pipelines it ends `[data-windowed="chart-drawing"]` rather than hanging below
it.** It answers the section above it, and a table that has to be found is a
table nobody reads. On Summaries the placement was already right, so only the
chrome, the name and the span changed.

**Shut, a disclosure drops its border, its background, its shadow and its
padding.** Closed it is one line of link text, and a bordered, shadowed, rounded
card around it gave a footnote the visual weight of a section - which is what
made it read as something hanging off the bottom of the page rather than as the
last line of the section above. Open it takes the frame back, because then it
holds a table. The rule is `.console-disclosure:not([open])` in
[../../../frontend/src/styles/app.css](../../../frontend/src/styles/app.css), and
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts)
reads the computed values either side - an eye cannot check a box-shadow.
Authority: Susan, 2026-08-31.

The Summaries table declares `data-windowed="daily-figures"`, so the window
oracle holds it to the control like every other windowed surface. The Pipelines
one declares nothing of its own: it sits inside `chart-drawing`, which already
declares the span and prints it in words.

## Rejected alternatives

The operator's surface. The reader's own table is on
[frontend.md](frontend.md) - a reader row and a console row share nothing but a
heading.

| Option | Why rejected | Authority |
| --- | --- | --- |
| A console LISTING every feed, healthy ones included | Naming all 182 sources hides the 26 that are broken. The clean ones are named behind a disclosure since 2026-09-01, with no bars and no order - a name is a fact, a row in the broken list is a call to act. | owner, Susan |
| A ranked "ten most reliable feeds" | Every key it could rank on ties: a feed is read once a run, so one that never failed has answered on every run it was asked. A top ten of a hundred-and-fifty-way tie is charting a constant. | Susan |
| A newest-first run strip | Every other time series on the page reads left to right in time. One that read right to left made the newest day's position depend on how much history existed. | Jony |
| An empty square for a scheduled run that wrote no manifest | It claims evidence the payload does not carry. Missed runs need a persisted schedule or attempt contract before they can be drawn. | Fowler |
| A date under every column of the run strip | At 16px a track and 10px a label the dates overlap from about the fourth day, and an axis that cannot be read is decoration. | Jony |
| Scroll buttons, a zoom control or a chart library for the strip | A native scroll region already pans with the arrow keys, costs no bytes and needs no focus management of its own. | Jony |
| Re-centring the strip on the newest run after data or layout changes | The operator scrolled there on purpose. A view that snaps back cannot be read. | Jony |
| A second threshold for the red square | CI already reads a success floor to decide whether to open an issue. Two numbers answering one question drift, and then a red square and an open issue disagree. | owner |
| Counting skipped items against a run's health | An already-published article is skipped by design. Counting it would paint a healthy day amber for doing its job. | owner |
| Dropping a column from the shard board on a phone | An instrument that answers five questions on a phone and six on a desktop is two instruments. A horizontal scroll was refused with it: it hides the job clock, the column an operator opens the page for. | Jony, Susan |
| Memory and processor as four bars on the board | Four bars a row is eighty bars across a run of twenty shards, and the reader still has to pair them by eye. A median filled with the maximum notched is the same two facts on one track, and the distance between them IS the spread. | Susan |
| A piecewise 0/10/50/100 value axis on the board | Equal pixel steps for unequal value steps misreports by construction. What the reader loses: at a 6x spread the low bars compress, and that compression is the true picture of a 6x spread. | Susan |
| Summing peak memory across shards | Shards are separate jobs on separate hosts. The sum reads about 53 GB on a runner that has 16. | Carmack |
| Reading stage timings from `state/scores.csv` | The score ledger did not carry those columns, and it only covers scored items. Timings belong on the item-health census. | Fowler |
| Serving `state/item-health/` directly | It carries `canonical_url`, `url_key` and untrusted `detail`. The browser gets only the published telemetry projection. | Fowler, Guardrail #11 |
| A failure bar scaled to the window's own maximum | With one day in view the bar normalises to itself, so a 12% failure rate and a 90% one both fill the panel. | Jony |
| A failure rate carried only by an SVG `<title>` | A tooltip does not fire on touch and does not survive the screenshot an operator pastes into an issue. | Jony |
| Suppressing the failure chart for a window holding one day | It was right when the panel drew one bar per stage: a chart of a single value is a rectangle. The column carries the volume now, so one day is one column and still says how much work there was. Only a window holding nothing at all draws no chart. | Jony |
| Keeping three failure panels and adding sparklines | It leaves the split, which is the defect rather than the content. | Jony |
| A single headline failure rate for the whole pipeline | It hides which stage failed, and which stage failed is the actionable half. | Susan |
| Rendering every failed row in the window | 800 rows measured 7824px and pushed the compression chart to document y=9105. The rows are on demand. | Jony |
| A virtual-scrolling failure table | A dependency and a scroll-position bug for something a cap and a button already solve. | Jony |
| A stage glyph beside the stage name | The icon set is one generated module that reaches every route, so three stage marks would move six reader routes that cannot show this section at all. An icon that needs a caption is a label wearing a costume, and the stage name is already in the cell. | Jony |
| A per-day stacked bar list for stage timings | Thirty days is about 150 rows and no trend, and the trend is the only question the section is asked. | Jony |
| Clamping a zero stage timing into the bottom decade | It draws a plunge to the floor of the plot, which says the stage got a thousand times faster on a day it was merely quick. | Jony |
| A caret beside the line for a zero stage timing | A second shape for a fact the open dot already carries, and one more thing to learn before the chart can be read. | Jony |
| A dashed bridge across a stage-timing gap | A slope between two days that share no measurement is a number nobody took. | Jony |
| A fifth sub-millisecond decade on the stage-timing axis | It moves every mark on a 30-day chart to hold ten rows from one day. The axis is not the defect. | Jony |
| A linear/log toggle on the stage-timing axis | A toggle is an admission that we could not decide which axis is correct. | Jony |
| A density-binned scatter, or reducing the mark opacity | Both keep the two-axis reading the band split removes, and the second makes a paler blob. | Jony |
| `uplot` on the compression scatter | It drew a second, smaller chart beneath a complete SVG, and the pan and zoom it was bought for live in the viewport control, not in the plot. | Jony, Guardrail #8 |
| Fading the per-point band lines instead of collapsing them | The wash is a node count, not an alpha value. One fact drawn 1166 times is still drawn 1166 times at any opacity, and the fact has one value per configured band. | Jony, Carmack |
| A drawing library for the console charts - `echarts`, `@observablehq/plot`, `chart.js`, a component library | 336 KB gz on canvas, 128 KB gz and a DOM shim to prerender, 67 KB gz on canvas, and a component set is worst of all where every chart is bespoke. All of them own the element and the theme; the console needed the arithmetic. The console exception has three named conditions, and it still binds a reader route. | Jony, Carmack |
| `d3-scale` from a CDN | The HTTP cache is partitioned per site, so the shared-cache argument is dead, and the repo's `script-src` allows `self` only. | Carmack |
| Fixing the units by hand instead of taking the dependency | `.nice` and `ticks` are exactly the part hand-rolling gets wrong, and an axis labelled 0, 37, 74 is an axis nobody reads a value off. | Jony |
| A `console.chart_width` default per chart shape | One knob names the width the reading column leaves; a chart sharing a row divides it. Four knobs would be four ways to disagree about one column. | Jony |
| Putting the page ceilings anywhere but `config/` | A ceiling is a limit a person chose and raises on purpose, which is the definition of a knob (Guardrail #6). | Carmack, Guardrail #2 |
| A `run.success_floor_pct` reference line on a stage failure panel | That floor is a published rate over attempted items; a stage panel is a different denominator. A wrong reference line is worse than none. | Jony |
| A separate chart for where the cut falls | It is a line. A chart that says what a line says has not earned its place. | Jony |
| A cap line read from `extract.truncation_cap_tokens` | A thirty-day window can hold two settings, so the knob is a claim about a config file rather than about the plot. It also draws a line when nothing in view was cut, and the data-derived line cannot. | Jony |
| `--band-low` for the cap line | A red vertical says the cap is a failure. The cap is a setting. | Jony |
| A second shaded region for the cut | The band zone already means "target summary length". Two shadings meaning two things on one plot is one too many. | Jony |
| An SVG `<title>` as the chart tooltip | It does not fire on touch, carries a delay nobody chose, cannot be styled, is not keyboard-reachable, and does not survive a screenshot pasted into an issue. It stays as the accessible name. | Jony |
| A readout pinned to the pointer | A readout under a thumb is a readout nobody reads. | Jony |
| A tab stop on every data point | The committed ledger draws 2,541 of them. A 2,541-stop tab order is a trap, not access. | Jony |
| A readout on the run-health strip | It has no per-day point to land on. | Jony |
| A readout on `FailurePanels` - reversed 2026-08-31 | It was refused because the chart prints every stage's rate and its denominator in type under the plot. It prints them for the window, not for a day, and the day is the column the strip prints. | Susan |
| A readout on `StageTimings` - reversed 2026-08-30 | It was refused because the chart "already prints its headline in type", and the headline it printed was the newest day. The chart had no per-day label and no mark, so the other twenty-nine days could not be read at all. | Susan, over Jony's 2026-08-25 ruling |
| A floating readout box over a plot | Measured 2026-08-29 at 88 to 121px over a 220px plot: 40 to 55 percent of the chart it explains. A strip below the plot cannot occlude at any width. | Jony |
| Re-sorting the readout rows to the hovered day | The rows are the legend. A legend that re-orders under the eye as the pointer moves cannot be read, and the colour swatch already matches the line. | Jony |
| Labelling only the first and last day of a date axis | That is what it did. It is what makes a spike unattributable to a date. | owner, 2026-08-30 |
| A charting library for the readout | There is none on this surface and this adds none. One action beside `observeWidth`. | Jony, Guardrail #8 |
| One chart carrying both the visuals strip and the articles strip | Two axes invite a comparison of slopes that means nothing, and one axis flattens the smaller series to nothing. | Jony |
| Seeding the per-item cost columns with real values | It cost `/console/` 176,753 gzipped bytes and put it 98,182 over its ceiling. Dropping the seeded months instead puts a 244 KB fetch behind the first click and leaves the section blank until it lands. | Carmack |

## See also

- [frontend.md](frontend.md) - the reader's published surface, and the routes this one sits beside.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is allowed to read.
- [console-charts.md](console-charts.md) - what a chart has to conform to: the coordinate frame, the readout, and how a missing number is marked.
- [console-payloads.md](console-payloads.md) - what the console fetches, and what it may never be served.
- [telemetry-series.md](telemetry-series.md) - the published projection and the grain of every figure.
- [../sources/health.md](../sources/health.md) - the feed ledger these panels render, and the quarantine rule they mirror.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the page ceilings and what to do when one fires.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - the instrument log behind every number here.
