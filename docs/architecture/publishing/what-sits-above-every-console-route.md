# What sits above every console route

**Last Updated**: 2026-10-06

Three surfaces stand on a full console route: the strip - the route tabs and the
days control on one row - the sentence under it that says how complete the
record is, and the standing band. A route may instead ask for workbench chrome:
the compact route strip only, with the page's own toolbar holding the days and
Run controls. A route whose panels sit under named headings adds a row of jump
links. Which surfaces follow the days control has its own page
([which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md)),
because that is asked far more often than how the control is drawn.

The order down the page is title, strip, completeness sentence, band, the
sentence about the span, the jump links, content. Chrome above content is the one
ordering a reader never has to learn, and the band's worst fact names a tab in
the strip - which on a phone would otherwise sit 337px BELOW it, where a reader
has already scrolled past. `console-band.spec.ts` holds the order.

The Data explorer is the exception. Its `+page.ts` returns `chrome:
"workbench"`, read from `console.explorer_chrome`, and the layout resolves that
through `frontend/src/lib/console/chrome.ts`. Workbench chrome keeps `#console-top`
as a screen-reader heading and draws only the compact, non-sticky strip. It does
not draw the completeness sentence, band, no-script note, span sentence, jump
links or route carry line. The route must then draw its own span and Run controls
inside its workbench. Workbench chrome also gives the route the whole window:
`app.css` lifts the console's width cap and leaves out the site footer for it,
the section steps out of the frame's gutter while the header keeps it, and from
1024 px the frame is the window's height, so the route's workbench fills what the
header and the strip leave
([how the Data explorer shares the window](../../concepts/console-design/how-the-data-explorer-shares-the-window.md)).
No other route changes.

Which panel sits on which route is [console.md](console.md); how any figure is
allowed to read is
[../../concepts/console-design.md](../../concepts/console-design.md).

## The strip is real anchors, not tabs

**Routes, not tabs, and the JavaScript-disabled gate is why.** A tab strip that
switches with script shows one panel set and no way to reach the others when the
script does not run, and every panel it hides still ships inside the one
document. Real anchors pass both, and each route can be weighed on its own. Tabs
keyed on a query string cannot prerender at all; tabs keyed on a hash stop
find-in-page at the hidden panels.

The strip's description is written in two places -
[console_band.py](../../../backend/idhazh/telemetry/publish/console_band.py) for
the published band and
[band.ts](../../../frontend/src/lib/console/band.ts) for the fallback - and both
must agree, because the strip a reader sees is whichever one answered.

**The strip has to fit, and the basis is what moved to make it.** `.tab-slot` at
`flex: 1 1 14rem` - 224px at a 16px root - puts one tab on a row of a 360px
phone, so five tabs stand five deep directly above the band. It is `8rem` now,
128px, so two fit the 288px content box of a 320px phone. From `1024px`, the
breakpoint three other components already use, the tabs are one row: each is as
wide as the longer of its label and its worst state, and the per-tab description
is shown under both.

Measured 2026-10-02 off the real built page in headless Chromium on Windows,
900px tall, with `window.innerWidth` read inside the page and equal to the asked
width at every row. The strip is the tabs and the days control together, at the
top of the page. It is the same height on Pipelines and Hardware at every width,
because no tile carries a price any more:

| Width | Tab rows | First tab | Strip | Description |
| ---: | ---: | ---: | ---: | --- |
| 320 | 3 | 140px | 315px | hidden |
| 360 | 3 | 160px | 291px | hidden |
| 390 | 3 | 175px | 323px | hidden |
| 414 | 3 | 186px | 267px | hidden |
| 480 | 2 | 142px | 238px | hidden |
| 640 | 2 | 141px | 206px | hidden |
| 768 | 2 | 353px | 206px | hidden |
| 900 | 1 | 161px | 154px | hidden |
| 1024 | 1 | 148px | 152px | shown |
| 1280 | 1 | 185px | 120px | shown |
| 1440 | 1 | 218px | 104px | shown |

Stuck, the strip is 70px at every width measured from 1024 to 1920. On
2026-09-27 the Pipelines strip was 348px at 390, because its tiles kept room for
a price; the shorter control took 81px off it there and 16px off every route at
1440.

**What the sixth tab does to the strip**, measured after Data explorer became live. It adds a row of tabs only from 731 to
871px, where five tabs fit one row and six do not, so Data explorer stands alone on a
second row. Below 435px six tabs stand two to a row in the same three rows five
did, and from 435 to 730px in the same two - **but the strip still grows**, by
56px at 390, because Voices then shares its row with Data explorer and its worst state
wraps inside the narrower tab. From 1024px the row scrolls, and every route opens
with its own tab whole. The old flag is gone, so this is now the normal strip on every console route.

**What moving the days control onto the strip cost a phone, and what it gave
back.** Before, the control stood under the band. Measured the same way off the
build this change started from; `Panels start` is where the last line above the
first panel ends:

| Width | Band starts, before | Band starts, Pipelines | Band starts, Hardware | Panels start, before | Panels start, Pipelines | Panels start, Hardware |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 390 | 383px | 575px | 493px | 912px | 923px | 923px |
| 768 | 279px | 364px | 359px | 647px | 616px | 669px |
| 1440 | 282px | 330px | 330px | 515px | 487px | 520px |

So on a phone the band starts 192px lower on Pipelines and 110px lower on
Hardware, while the first panel starts 11px lower on both: the band moved, and
what sits under it barely did. Hardware's panels include its new `On this page`
row.

**Two numbers were taken from the first sweep, on 2026-09-12, rather than from
the rule.** `9rem` cleared 360px and still stacked five deep at 320px, which is
the same defect one screen narrower, so the basis went to `8rem`. And the
description at the narrower `48rem` breakpoint made the strip 168px at 800px
against 86px at 768px - so widening the window made the chrome taller, which is a
discontinuity a reader notices and cannot explain. That is still why the
description waits for `1024px`.

The description is not lost below the breakpoint: it is still the anchor's
`title` and the page it opens prints it in full, so what a hidden line costs is
the one-line summary a reader gets before choosing - which is why every label is
one word.
[../../../frontend/tests/console-nav.spec.ts](../../../frontend/tests/console-nav.spec.ts)
measures the tab boxes off the built page at 1440, 768, 360 and 320, prints the
width the page really had beside every figure, and fails on a row too many or on
any two boxes that overlap.

**The strip never takes the health ramp.** The one thing that differs between
routes is a 3px rule under the active label, from the categorical ramp. Green,
amber and red on a label would say a route is failing, and a route is a noun. The
same spec reads the computed style of every tab and fails on any of the six
verdict tokens.

**Identity is otherwise identical across the five** - type scale, space scale,
radius, elevation, frame width, both ramps. The shapes they share live in
[../../../frontend/src/styles/app.css](../../../frontend/src/styles/app.css)
rather than in three scoped `<style>` blocks, because three copies are three
identities that happen to agree today.

## From the wide breakpoint up the strip sticks, and it is one row

A long route - Hardware is four groups and fifteen panels - put the days control
and every other route a screen or more behind a reader nine panels down. **From
`frame.breakpoints_px[1]` up (1024px, inclusive) the strip sticks to the top of
the screen**, so the span and the other routes stay in reach. Below that width it
scrolls away with the title, because there the tabs stand on up to three rows and
a stuck strip that tall would cover a phone.

**Where it sticks it is one row, at any count of tabs.** Each tab stands its
worst state on a line under its label, keeps the width the longer of the two
needs, and shares whatever the row has left; when the row runs out, the tab list
scrolls sideways inside the strip and the days control stays pinned at the
trailing end. The strip never wraps to a second row and no label is shortened.
Every tab fills the row's height, a tab with no worst state included, so the rule
under the active route sits on one line whichever route it is. Adding a route is an entry in the route list in
[band.ts](../../../frontend/src/lib/console/band.ts) and a page, never a layout
change, and `console-shell.spec.ts` holds the row with one tab more than the
console has, and again with as many more as it takes to make the list scroll.

**The days control is on the strip at every width.** It is five short tiles,
`1D 7D 14D 30D 90D` - one per `console.window_presets` value - at the 2.75rem
touch floor both ways and 4px apart, so 236 by 44 CSS px at every width, with
nothing beside them. The `D` is the unit: each tile hides it from a screen
reader and says the whole word instead, so `14D` is heard as `14 days`, and the
group's name, `Days shown`, is a legend only a screen reader hears. Below the
breakpoint the control takes its own row under the tabs, at the start of it,
and does not stick. The sentence about what the span is showing stays under the
band, above the panels it describes - on the strip it would make two rows - and
**it carries the price**: on a route whose window fetches month files it names
each wider preset that would fetch more, `Every windowed section below is showing
14 days. 30D would fetch 1 more month, 90D 3 more.` It keeps room for its longest
form - three lines of `--leading-xs` below `frame.breakpoints_px[0]` and two from
it - so a price that lands or clears moves nothing below it.

**While stuck, the tab descriptions leave.** Each is still its tab's `title`, and
they return when the strip is back in its place. Two things follow, and
[strip.ts](../../../frontend/src/lib/console/strip.ts) owns both:

- **The page does not move.** The strip gives up the descriptions' height and an
  empty box directly under it takes that height in the same frame, so nothing
  below shifts when it sticks or unsticks. A margin on the strip cannot do it: it
  collapses into the margin of the element after it, and the page moves by the
  smaller of the two - 12px on Hardware at 1440 when it was tried.
- **Anything the page scrolls to lands below the strip, not behind it.** The
  document's scroll padding is the stuck strip's height, so a jump link, a `Top`
  link and a focused control all clear it.

It sticks only once a script has run. With no script there is nothing to shorten
it or to keep a jump link clear of it, so it stays in the flow like the title.

**The band's worst route says so on its own tab**, in a word: `Worst:` before the
fragment the tab already carries, in the main text colour and never a verdict
colour, at the top of the page as well as when stuck, so nothing reflows when the
strip sticks. When the tab list scrolls, it opens with the reader's own tab
whole, and with the worst route's tab in view too wherever both fit. The worst
route is the one fact on the strip the band cannot give once the band has
scrolled away; but a page that opened with its own tab cut off would not say
which route it is, and where the two do not both fit the band under the strip
still names the worst route.

**The strip's surface is the page ground with a rule under it**, the same hairline
that edges a reading-page item: the stronger rule on the dark ground and the
plain one on the light. A raised strip with a shadow draws nothing on the dark
ground, where height reads as a lighter surface, so "raised once stuck" would be
a colour change at the moment it sticks.

## The sentence under the strip dates the record

Every window on the console ends on the newest day the site published rather than
on the reader's day, so when the pipeline stops publishing a chart gains no gap at
its right edge - it holds the last window it drew and looks as full as it did the
day before. The sentence under the strip is what tells a stopped pipeline from a
quiet one:

```
The latest run on this page finished at 18:23 UTC on Sunday 27 September. A run still going is not on this page yet.
Nothing has been recorded since 18:23 UTC on Sunday 27 September. 2 days are missing.
```

- **The instant is the band's own `generated_at`**, the moment the run that wrote
  the record finished, in UTC and printed with `UTC` beside it. The day is always
  spelled out - weekday and date, never `today` - because the page's day is the
  UTC day and a reader's own day can be a different one.
- **The prerendered page says the first sentence and claims nothing else.** It has
  no reader's clock to judge age against, so with no script the sentence dates the
  record and stops. A browser adds only the count.
- **The second sentence fires on the reader's clock**: when the record's UTC day
  trails the reader's UTC day by more than `console.completeness_grace_days` (1).
  The grace decides only when the count is said. The count is the whole UTC days
  between the record's day and today - today is still being recorded, and the
  record's own day is not missing - so it is always at least one, and `1 day is
  missing` is singular. The page looks again at the next 00:00 UTC and whenever it
  is shown again.
- **No record is a named absence**: `This page cannot say when the last run
  finished - its record did not load.`
- It is a sentence, not a badge. Quiet type in the secondary colour, and the late
  form in the main text colour rather than a warning colour: the words carry it.

The record's other two fields cannot say it stopped. `covers_through` is the day
the run assembled, the same UTC day as `generated_at` on every run, and
`compaction_lag_days` is always 0 - and a record that stopped being written is not
rewritten to say so. Only the reader's clock can see that it is old.

**It dates the last run, never the newest packed day.** A panel that draws a
packed ledger can end days before that run, and the route's own note for that
record already says how far it reaches
([recording.ts](../../../frontend/src/lib/console/recording.ts)). Dated from the
newest packed day instead, the second sentence would say nothing had been recorded
every day, while runs still land.

The words live in
[completeness.ts](../../../frontend/src/lib/console/completeness.ts), which reads
no clock of its own; the layout hands it the reader's.

## A long route carries jump links

A route whose `console.panel_groups` entry names its groups gets an `On this page`
row under the band and the sentence about the span: one link per titled group, to
that group's heading. Each titled heading carries a `Top` link back to the
console's title. A route with no groups, or one untitled group, draws no row -
Pipelines is one untitled group, because what it needed was an order rather than
headings.

They are plain named anchors, so they work with no script at every width, and a
route with several groups gets one destination per group - which a single
floating back-to-top arrow could not give, and it would have needed a script.

## Every label carries its own worst state

`Machine - 4 shards read 4.31x apart`, not `Machine`. It is computed at build
time from the committed ledger. Without it a route is where a metric goes to die:
nobody opens a page to find out whether it was worth opening.

Machine's candidates are a run the machine record refused, a shard that committed
no row, and the newest run's read spread. **The spread is reported at the lowest
rank on purpose**: nobody has agreed how far apart two shards of one run may read
before it is a problem, so ranking it any higher would publish a threshold this
project has not taken.

**The shard that committed no row is counted against a number from another
file.** The denominator is `shards` on the day's `run.json` - what the plan asked
the matrix for, recorded before any work job existed. The numerator is how many
work jobs filed a row in the host-fingerprint ledger. Taking both off the host rows
would make them equal by construction: `N shards reported nothing` could never be
anything but zero, and the guard that refuses a run with more shards than the
plan sized would read `len(kept) > len(kept)`. A number that cannot disagree with
its neighbour is not a check (`CLAUDE.md` Guardrail #10). The read spread is read
the same way - off `server_prompt_tokens` and `server_prompt_seconds`, which are
llama-server's own counters and not arithmetic over the item ledger.

**An editorial fault caps at `WORTH_A_LOOK`, and there is one exception.** The
band prints the one worst thing across every route, so a loud rule on Judgement
or Voices would take the band away from a failed run - and then a skewed day and
a failed run print the same sentence, which is the band's whole job undone. A
skewed day still published; a failed run did not. `console_band.editorial` is
where the cap is applied, because the band is derived once and read everywhere.

**The exception is a gate that has stopped reading, and it is two-sided.** A
gating kind whose decline rate sits at either end ranks `BROKEN`: at the floor it
declines nothing, so it is stamping every article it is shown, and at the ceiling
it declines everything, which is the same instrument dead from the other side.
Either way every other figure on the route is fiction, including the figures a
reader would use to decide the day was fine. The rule is two-sided because the
failure is two-sided: a floor-only rule would let a classifier that had stopped
answering print a reassuring tab. Both bounds are `console.decline_rate_floor`
and `console.decline_rate_ceiling` rather than literals (Guardrail #6). The
fraction itself is null until the classifier lands, so the rule fires on nothing
today and costs nothing to carry.

**Voices has two worst-state candidates and they are ranked.** A feed sitting at
`collect.reliability_floor` is `WORTH_A_LOOK`: it is the one state where the
ranker is actively discounting a feed as far as the multiplier goes, and no other
page says so. A live source that has decided fewer than
`collect.source_yield_alarm_min_decisions` addresses is `WORTH_KNOWING`, because
every quality figure about it prints a dash and a dash is invisible at a glance -
ranked lower on purpose, since too little evidence is not the same as bad
evidence and ranking it higher would publish a judgement the record cannot carry.
The fragment carries its denominator - `68 of 151 sources too thin to judge`, not
`68` - for the same reason every quality figure on this console sits beside its
item count: a bare count is a number with no scale.

**A count of feeds that answered nothing is not a third candidate.** A feed that
answered nothing scores zero, which clamps to the floor, so it is a strict subset
of the at-floor set and could never reach the label. It is a figure on Voices
instead.

## The standing band carries three things

The band's three facts: the latest day's verdict as a sentence with one square per
run of that day, the one worst thing and what it costs, and site size against the
1 GB limit with the articles the headroom buys. **The first fact is labelled
`Latest day`, not `Yesterday`**: the verdict is the newest day the record holds,
which is today once today's first run has finished, and a fixed name needs no
clock, so it stays true on a page read a week later. The sentence above the band
is what dates it. The pipeline derives it once and
publishes it as `console/band.json`; the console fetches it once in
[../../../frontend/src/routes/console/+layout.ts](../../../frontend/src/routes/console/+layout.ts)
and draws it once in
[../../../frontend/src/routes/console/+layout.svelte](../../../frontend/src/routes/console/+layout.svelte),
above all five route panels, so they cannot disagree about which route is worst.
A browser-build derivation was rejected; see
[console-payloads.md](console-payloads.md).

**Each run square names its verdict, and the words after the squares say every
verdict at once**, grouped - `2 runs ran clean, 1 run failed` - so a thumb and a
keyboard read what a pointer on a 10 px square would, and no square carries a
`title`. The words sit on the squares' own line, which costs the band about 6 px
where a line of its own cost 20 and put it over its 130 px line at 1440. Susan,
2026-09-28.

**The band has to stay short, and three changes are what keep it short.**
Measured 2026-09-01 at bf37eeef it ran 340px on a desktop and 586px on a phone -
69 percent of an 844px viewport. The window control moved out, the site-size fact
dropped from about sixty words to one line, and the page subtitle came off every
route: it repeated what the active tab's own description says 150px lower and
cost 25px on every route. **The control was the largest of the three** - inside
the band it cost 125px of the first viewport on a desktop and 195px on a phone,
for four tiles and a sentence, and it was a control sitting in a panel it does
not govern.

**The site-size fact is one line: the level, the limit and the articles the
headroom buys.** The rate it divides by, the days it was measured over and the
clause about which tree the cap measures live on `What one more article costs`,
which already owns the rate, its n and its spread - a band that repeated them
spent sixty of its hundred words on a caveat, and `idhazh site-weight` and
`committed payload tree` are not reader strings anywhere
([console-site-size.md](console-site-size.md)).

**The worst-thing fact says what the state costs, and the strip keeps the short
form.** `15 feeds resting` on a label becomes `15 feeds are resting, so nothing
they carry reaches the digest. Each is asked again after 5 runs.` in the band. The
retry count comes from `availability_strikes_before_rest` and never from a
literal. Repeating the strip's short form in the band was rejected: it would put
the same words 337px apart on a phone. Nothing in the sentence invents a task:
quarantine is self-terminating, so what it asks is that the operator knows the
digest is short of sources until the retry
([../sources/health.md](../sources/health.md)).

**A resting feed never outranks a failed run on a tie.** Both rank BROKEN and the
sort is stable, so listing the feeds first would hand every tie to the state that
clears itself after five skips. The run candidates are pushed first.

**Free swap is a candidate on Hardware, and it is silent on a box with no swap.**
It is a precursor rather than a diagnosis: once the machine pages, read rate
collapses and a shard walks towards its time bound. The band names it and the
Hardware route is where an operator sees which shard. `os_swap_free_bytes` at
zero reads as "this box has no swap" and "swap is fully consumed" equally, so the
candidate is built from the pair and says nothing where `os_swap_total_bytes` is
zero or unrecorded. **Any swap used at all is the trigger, and the band reports it
as a fact rather than a verdict** - how far in is too far is a threshold nobody
here has measured, and a severity built on one would publish a number this
project has not taken.

**A compaction-lag line is not drawn.** Every writer files its own day, so no run
finds a backlog: `compaction_lag_days` is always 0 and the line could never draw.
**What the reader gives up** is a "nothing is waiting to be folded" reassurance -
one that was always going to say the same thing, so it told an operator nothing
they could act on. The payload still carries the two readings, so a later change
that can make them move again has its line back without a schema break.

**The verdict fact draws one small square per run of the newest day**, on the
same `--fill-*` ramp and the same shape as `Run health` 800px below, capped at
twelve then `+N`. It says what the sentence cannot: whether one run ate all 34
failures or all five limped. It is hand-written markup, so it is on the page
before any script runs, and every square names its verdict in words.

**None of the three is windowed**, and that is the difference between the band
and the per-article cost panel on Pipelines. The band stands on every route, so a
figure that moved when a control on one route moved would read as three different
sites. The runway is taken over every published day on record.

## Design rationale

**The Data explorer may ask for workbench chrome.** It is a tool for writing and
running a ledger question, so the full console band and span sentence push the
work below the first screen without adding a fact this route judges. The route
declares the chrome as data from `console.explorer_chrome`; the layout does not
infer it from the route name. What this removes is the global verdict while the
operator is on the Data explorer; one tab press shows it on the other routes.
Since 2026-10-05 it also removes the site footer from that route, so the
workbench can reach the window's bottom edge (owner request, Jony's layout); the
wordmark leads to the home page, whose footer carries the same links.

**The days control rides the strip at every width, not only where the strip
sticks.** One control in one place keeps the keyboard order, the screen-reader
order and the reading order the same at every width, and the span a reader sets
is the one thing on the page that has to be in reach from anywhere on a long
route. Moving it under the band below the breakpoint with CSS was rejected: the
keyboard would jump from the tabs past the band to the control and back up.
Drawing two copies and hiding one per width was rejected: it is two radio groups
to hold in step, and every check that finds the control by its attribute would
find two. Putting the band above the strip was rejected: the completeness
sentence could no longer sit both under the strip and above the band. **What
it costs:** on a phone the band starts one control row lower.

**The tiles read `1D 7D 14D 30D 90D`, with no label and no price.** The `D`
says in one character what `Days shown` said in ten, and the legend still names
the group to a screen reader, so the control is 236 px wide at every width and
leaves the strip its room for a sixth tab. A forked, smaller control for one page
was rejected: two controls would be two windows a reader cannot compare. Keeping
the label and dropping only the price room was rejected: it saves the height and
not the width, and the width is what a sixth tab needs. Dropping the price
entirely was rejected: a reader would meet what a wide span costs only after
choosing it.

**The price of a wider span lives in the sentence under the band.** A price that
appeared and disappeared on a tile moved seven panels by 15 px when it landed or
cleared (measured 2026-09-09), so every tile kept a second line for it whether
or not one was due. The sentence is always drawn and keeps room for its longest
form, so the price holds still and the tiles hold one line. **What it costs:** on
a phone the price stands a band's height below the control, about 300 px, and
from `frame.breakpoints_px[1]` up, while the strip is stuck to the top of the
screen, the price is off screen - so a reader far down Pipelines sees what a
wider span fetches only after choosing it. **And below
`frame.breakpoints_px[0]` the room is three lines.** The longest form - one day
chosen and every wider preset priced, 111 characters - took three lines at 320px
and two from 360px (measured 2026-10-02, Chromium on Windows), and 640px is the
nearest width a knob names. So on the four routes that never price a span, the
panels start 16px lower from 360 to 639px than they did before the change, for a
third line only Pipelines can fill.

**The worst route is marked on its own tab rather than repeated in a pinned
line.** The tab already carries the fragment, so a pinned `Worst now:` line would
print the same words twice in one row and take about 200px from the tabs, and
hiding the other routes' fragments while stuck to make room would shorten the
labels the one-row rule protects. **What it costs:** when the tab list scrolls,
the worst tab can be scrolled out of view - the list opens with it in view
wherever the reader's own tab stays whole beside it.

**A tab's worst state stands under its label from the breakpoint up.** Side by
side, a tab is as wide as both together, and on Pipelines - whose days control
was then the widest, because its tiles carried prices - four of five tabs were
whole at every width from 1366 to 1920, the fifth 5px short at the widest.
Stacked, a tab is as wide as its longer line: all five are whole from 1366 on
Pipelines and from 1280 on Hardware, and three and four of them at 1024. **What
it costs:** one line of every tab's height - the stuck strip is 70px where one
line made it 46 to 50px - and at the narrowest one-row widths a tab or two still
needs a sideways scroll.

**`The latest run on this page finished at`, never `Complete to`, and never
`today`.** The console's subject is the pipeline's own record, and the last run
finished writing it at that instant. `Complete to` made the same instant a promise
about every chart on the page, and a chart drawn from a packed ledger can end two
days earlier; `complete` let that chart pass for current. `Today` beside a UTC time
names the wrong day for a reader far from UTC for part of every day, and a
prerendered page is read for a day or more after it was built. **What it costs:**
the glance a reader got from `today`, and a sentence six words longer.

**The layout draws the control; the route holds the window.** The strip belongs
to the shell, and the window - span, fetches, the price per preset - belongs to
the route, so the route hands it up through
[window-slot.ts](../../../frontend/src/lib/console/window-slot.ts). The shell is
written before the route's script runs, so the prerendered control holds the
configured window and no price; it is disabled then in any case. The price is
said in the sentence under the band, which keeps its room on every route from
the first paint, so no route has to declare that it prices its presets.

**A media query cannot read the knob.** The stylesheets repeat
`frame.breakpoints_px[1]` as a literal, the one duplication a media query forces,
and `console-shell.spec.ts` reads the knob and checks the strip sticks at it and
not a pixel below it - so a moved knob with an unmoved stylesheet fails there.

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the days control on the strip, and which surfaces follow it.
- [../../concepts/config/appearance.md](../../concepts/config/appearance.md) - `console.completeness_grace_days` and every other console knob.
- [console-site-size.md](console-site-size.md) - the site-size fact at full length.
- [console-payloads.md](console-payloads.md) - why the band is derived once in the pipeline and never in a browser.
- [../sources/health.md](../sources/health.md) - the quarantine rule the worst-thing sentence mirrors.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is allowed to read.
