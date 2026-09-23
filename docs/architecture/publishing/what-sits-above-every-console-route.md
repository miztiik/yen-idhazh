# What sits above every console route

**Last Updated**: 2026-09-23

Two surfaces stand on all five console routes: the tab strip, and the standing
band under it. The window control is the third and it has its own page
([which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md)),
because which surfaces follow it is a question asked far more often than how it
is drawn.

The order down the page is title, strip, band, window control, content. Chrome
above content is the one ordering a reader never has to learn, and the band's
worst fact links into the strip - which on a phone would otherwise sit 337px
BELOW it, where a reader has already scrolled past. The control comes last of the
three because a control read before any fact asks the operator to configure a
page he has been told nothing about, and because it governs everything under it
and nothing over it.

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
128px, so two fit the 288px content box of a 320px phone and five fit one row of
a desktop. The per-tab description is hidden by default and shown from `1024px`,
the breakpoint three other components already use.

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
clears 360px and still stacks five deep at 320px, which is the same defect one
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
work jobs filed a row in `state/host-fingerprint/`. Taking both off the host rows
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

The band's three facts: yesterday's verdict as a sentence with one square per run
of that day, the one worst thing and what it costs, and site size against the 1
GB limit with the articles the headroom buys. The pipeline derives it once and
publishes it as `console/band.json`; the console fetches it once in
[../../../frontend/src/routes/console/+layout.ts](../../../frontend/src/routes/console/+layout.ts)
and draws it once in
[../../../frontend/src/routes/console/+layout.svelte](../../../frontend/src/routes/console/+layout.svelte),
above all five route panels, so they cannot disagree about which route is worst.
A browser-build derivation was rejected; see
[console-payloads.md](console-payloads.md).

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

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the third shared surface.
- [console-site-size.md](console-site-size.md) - the site-size fact at full length.
- [console-payloads.md](console-payloads.md) - why the band is derived once in the pipeline and never in a browser.
- [../sources/health.md](../sources/health.md) - the quarantine rule the worst-thing sentence mirrors.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is allowed to read.
