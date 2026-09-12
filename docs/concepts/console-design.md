# Console Design

**Last Updated**: 2026-09-10

How a figure on the operator console is worded, coloured, ranked and drawn. It is
the operator half of [design-system.md](design-system.md), which keeps the
vocabulary the whole site resolves - the tokens, the colour ramps, the motion set
and the sufficiency gate. This page adds no token and defines no colour; it says
what the console may do with them.

Three pages meet here and do not overlap.
[../architecture/publishing/frontend.md](../architecture/publishing/frontend.md)
says what each panel is and where its data comes from.
[../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md)
says at what grain a figure was measured. This page says how it is allowed to
read on screen. The bounds are Jony's and Susan's
([../../.github/agents/jony.agent.md](../../.github/agents/jony.agent.md),
[../../.github/agents/susan.agent.md](../../.github/agents/susan.agent.md)).

The console is read by the developer and the operator, not by a digest reader.
That sets who it is for; it does not relax how it is written. `CLAUDE.md` section
0b binds every string in this repo.

## A console figure says what it counts, in words

The console is read by the developer and the operator, not by a digest reader.
That sets who it is for; it does not relax how it is written. `CLAUDE.md`
section 0b binds every string in this repo, so a figure on this page is labelled
in words a person can act on and never in the name of the column behind it.

Five rules hold for every number the console prints:

- **A count of that day's items, not a score.** No value between zero and one
 reaches the screen, and no cell prints a decimal. A share prints as whole
 percent.
- **No ledger column name on screen.** `hhem`, `hedge_dropped` and
 `truncation_flagged` are how the file spells it. The page spells what it
 means.
- **A dash where the ledger holds no answer.** Null and zero are different
 facts, and a zero that was really an absence is the one number nobody checks.
- **`<1` where a real measurement rounds away.** A `0` there would say the work
 was free.
- **The item count sits beside every quality figure.** A share over four
 articles is not a measurement, and a column that hides its denominator
 invites a trend that is not there.

### The empty state is the panel, not a replacement for it

A panel that vanishes when it has nothing teaches the operator that the
measurement does not exist. The heading and the explanatory sentence stay; only
the figure changes. Jony, 2026-08-30.

This is the normal case rather than the exception. Measured 2026-08-31 on the
committed tree: `job_seconds` and `cpu_model` are empty on **24 of 54** counter
rows, the three host cells on **34 of 54**, and the counters ledger starts five
days after the score ledger - so five days inside a thirty-day window have
scores and no server figures at all. A console that only designed the loaded
state would be mostly undesigned.

Five states have fixed wording, written by the owner on 2026-08-30 and held in
[../../frontend/src/lib/console/recording.ts](../../frontend/src/lib/console/recording.ts):
measurement off, sampled below 1.0, counters but no scores, scores but no
counters, and recording started mid-window. Only the dates and counts inside
them are computed, and every one is derived from the ledger that is missing - **a
date that is not true is worse than no date**. None is apologetic, none is
styled as an error, and none is a banner across the page: three panels can be in
three different states on one day.

Two of them are worth reading twice. **A sampled figure is never scaled up** -
multiplying a quarter-sample by four publishes an estimate as a measurement,
which Guardrail #10 forbids. And **no string names a config key as if it were a
word**: it is `Measurement is off`, never `runtime_counters_scrape is false`,
because a term from a subsystem is not a term for a user (section 0b).

### A figure in currency prints its rate, its source and the word for what it is

There is exactly one money figure on this site: the counterfactual cost on
`/console/machine/`. CLAUDE.md Guardrail #10 forbids the rest, and carries the
owner's carve-out for that one on conditions this section holds:

- **Never a currency symbol.** `0.48 USD`, never `$0.48`. A symbol in front of a
 number is the shape a bill takes, and this is not a bill - nothing bills us,
 because Actions minutes are free on a public repository.
- **The rate is printed, in full, beside the figure.** Both halves of it: a
 provider prices prompt tokens and written tokens apart, and one blended rate
 would understate a run that wrote a lot.
- **Where the rate came from is printed too** - `Using your rate` or `Using the
 configured rate`. A money figure whose basis is invisible is the exact thing
 Guardrail #10 exists to prevent.
- **The word for what it is sits in the panel, not in a tooltip**: what the run
 would have cost somewhere else, never an amount owed.
- **Digits are grouped by hand, never by `toLocaleString`.** The server draws
 the page and two builds have to agree; a locale-dependent separator moves the
 prerendered document and the byte gate reads it as a regression.

The label set for `What the model did`, with the sentence each one carries:

| Label | The line under it |
| --- | --- |
| Summaries today | - |
| Marked "not sure" | How many of today's summaries we told you not to trust. |
| Numbers not in the article | The summary had a figure. The article did not. |
| "Maybe" told as fact | The article said it might have happened. The summary said it did. |
| Article read only in part | The article was too long, so the machine read the start and stopped. |
| Read only in part, as a percent | The same articles, against the day's own count, so a busy day and a quiet one compare. |
| Copied, not rewritten | How much of a normal summary is lifted word for word. |
| Time to write one | How long the machine takes on one article. The second figure is the articles it read only the start of. |
| Model minutes | - |
| Too long to send | The article and the instructions together did not fit, so the machine was never asked. |
| Failed | - |

Two of those carry a rule the others do not. **The share divides by the rows
its own flag answers for**, never by the day: `truncation_flagged` changed
meaning on 2026-08-28, so a day holding rows from both sides of that stamp would
otherwise report a fact about the migration wearing a percent sign. And **`Time
to write one` carries a second figure only where the day cut something** - a
dash under every other day would be a column of absences pretending to be a
split.

**`Too long to send` is expected to read zero, and that is the point of it.** At
a truncation cap of 2,500 tokens no prompt could reach the window the machine
read with, so the count was zero by arithmetic rather than by luck. It is on the
page so that the day the cap moves, the number that says the move went too far
is already being printed. The cap has moved twice since - to 5,000 on 2026-08-29
and to 10,000 on 2026-09-09 - and the count is still zero by arithmetic, but the
arithmetic is tighter: the longest prompt the cap can produce is about 14,100
tokens of a 16,384 window, where it was about 4,200 of 8,192
([../reference/measurements.md](../reference/measurements.md)). This counter is
now the one that would catch the next move going too far, rather than a
formality.

### A section keeps the sentence that decides and loses the sentence that narrates

Twelve rows rewrote this page on 2026-08-30, each writing its own headings,
intros, readouts and empty states. Twelve hands write twelve voices, so one pass
reads the whole page at the end and settles it against `CLAUDE.md` section 0b.

- **A sentence that names a threshold, a denominator, a cost or an empty-state
 reason is kept.** Several of the console's decision rules are written nowhere
 else. Owner, 2026-08-30.
- **A sentence that says what the chart is, or argues for the shape it took, is
 cut.** The heading already names the subject, and the case against a rejected
 chart type belongs in the code comment that rejected it. Owner, 2026-08-30.
- **Prose cut from the page goes into the chart's accessible description**, so a
 screen-reader user is never left with less than a sighted one. Jony.

Three habits are what that pass caught, and they are the ones to check in any
new section. **One name for one span**: the page carried four phrasings for one
window and wrote the same instruction two ways. **One name for one control**:
`Failure rate against volume` stopped being three panels and the list under it
still named a component that no longer existed - a name taken from a component
outlives the component. **A number says what it is out of, on the same line**:
`prompt reused 51%` did not, and it is a share of prompt tokens, so it reads
`prompt tokens reused` now. That last is the one clause of section 0b a reviewer
can check mechanically, which is why it catches what the others miss.

**Say it once per screen.** Two sections both explained that they follow the
window rather than a pan, and a third printed a date span the heading above it
had already printed. A fact stated twice on one screen reads as two facts.

### Eleven measures are eleven cards, and the rows are one control away

The eleven above shipped as eleven columns of one table until 2026-08-30, and
that shape could not answer the question an operator brings to it. **Did it get
worse is a vertical scan**, and in a wide table every column beside the one being
scanned is a different quantity - a count, a percent, a second, a minute. At a
thirty-day window it was 330 numbers under eleven header paragraphs.

So the section leads with eleven cards on one `auto-fit minmax(220px, 1fr)`
grid, and each carries the same six things: **the label verbatim** - the copy is
protected and `frontend/tests/console-model.spec.ts` compares the rendered
labels byte for byte against the page's own `COLUMNS` and against the table
above, so a paraphrase fails the build rather than a review; **the newest day's
figure**, with which day printed once above the grid rather than eleven times;
**a line over the window**, drawn as markup by `Sparkline`, because eleven
engine-backed sparklines would be eleven chart instances on a page that renders
complete without one; **the change across that line**, painted from the
measure's own declared polarity; **what it is out of**, for the six quality
figures, because a card has no row to put the denominator one column away; and
**its sentence**, moved out of the header into the body where there is room.

**A day the model changed draws a dashed rule across every line**, from the same
rows the daily table draws its dividers from. Whether a swap moved anything is
the question the table could not answer at all. The rule carries a date and an
id and nothing else - an arrow or a delta across it would claim the swap caused
whatever the line then did, and no committed figure says that.

**No card is tinted.** `Copied, not rewritten` reads about 12 percent and nobody
has agreed what a bad number would be, so a tint there would invent a threshold
and publish it. The health ramp is lent to a threshold somebody agreed to, and
to nothing else.

**The daily table stays, below, behind a `Show these figures day by day`
control.** Nothing is deleted: after a card moves, the rows are what say which
day. It is a native disclosure, so the rows are in the prerendered document
either way and the section works with no script at all. Since 2026-08-31 the
rows follow the window control above them and the line that opens them names the
span, because a table that ignored the preset above it was two windows on one
page. Shut, it drops its border, background and shadow: closed it holds one line
of link text, and a card around a footnote is what made it read as something
hanging off the bottom of the page.

### A distribution answers what a median refuses to

`What one summary cost` is a log-binned histogram of the time to write one
summary, with a cumulative curve on a second axis and a rule at the median and
at the 95th, each printing its own value.

A median answers "how long does one take" and refuses "how bad does it get".
Measured 2026-08-31 over the 3,500 timed summaries in `state/item-health/`, this
box, those are different questions by a factor of 2.5: the median is **122 s**
and the 95th is **300 s**, with a slowest of 702 s. The second figure is the one
that decides whether a shard fits `run.shard_timeout_minutes`, and no single
number on the page was carrying it.

- **The bars double.** Writing times run from 0.3 s to 702 s, and on a linear
 axis every bar but one is a hairline against the left edge. Each bar is one
 doubling of the clock, so a bar is the same width wherever it sits. The lowest
 bar has no lower edge worth a label and carries the console's own `<1`.
- **The two rules are taken over the values, never off a bar.** A percentile read
 out of a bin is a guess at where inside a doubling it fell, and these are the
 two figures somebody quotes.
- **Leading and trailing empty bars are dropped; a gap in the middle stays.** An
 empty span between two occupied bars is the distribution saying nothing landed
 there, which over the committed ledger is real and visible: one summary
 finished in 0.3 s and the next fastest took 16 s.

**`score_ms` lives under the same heading, as two figures and no chart.** It was
a fourth line on `Time per item, by stage` until 2026-08-31, where it read as a
fourth thing the run is held up by. It is not: the scorer reads a summary the
model has already finished. Measured 2026-08-31 over the 3,534 timed rows of
`state/scores.csv`, this box, the middle is **2,463 ms** and the slowest one in
twenty is **14,491 ms** - printed as 2 s and 14 s, because the console prints no
decimal. Ten committed rows carry the zero the column defaulted to before it was
written, and they are counted as untimed rather than as instant. Owner,
2026-08-31.

### Compression is three marks a run, and the band prints its bounds

`How long the summaries came out` draws one column per run: the shortest summary
it wrote, the middle one and the longest.

**It was a mark per summary until 2026-08-31, and the block was the defect.**
Thousands of marks in one colour render their dense middle as a solid area, so
the only marks anybody acts on - a summary of three words, or one at twice the
length that was asked for - are the ones the block hides. Three marks a run keep
both ends and lose the block. Owner, 2026-08-30.

**Per run and never per day.** A day holds up to five runs, and a run is one
model reading one set of articles under one set of settings, so it is the
smallest thing on this page that a change can be attributed to.

**The band's bounds print as numbers beside the chart.** A shaded region nobody
can read a bound off is a decoration, and this one is a setting somebody chose.
The band drawn behind each column is what that run's own articles were asked
for, read through each article's own length rather than off `summarize.bands`
directly - an article's length picks its band, so a run of short pieces is asked
for less than a run of long ones. Susan, 2026-08-30.

### A swap comparison carries direction in the arrow, and a verdict only where the measure has one

`What the model change moved` is seven paired dot rows. Each measure is drawn
against its own value on the older model, so no change is 100 percent on every
row - the only axis a median in seconds, a length in words and a count in a
hundred summaries can share.

- **The arrowhead carries the direction; the hue carries the verdict where there
 is one.** Until 2026-08-31 every row was drawn in one categorical colour,
 because a red-for-worse ramp needed somebody to agree which way is worse for
 each of the seven. Five now say so themselves, through the polarity declared
 on the measure rather than chosen by the chart; the two with no agreed
 direction stay grey and name themselves under the plot. A hue here is never a
 guess.
- **The axis is symmetric about no change**, so a fifth off and a fifth on draw
 the same track length. An axis running 78 to 120 would draw one as the bigger
 move.
- **Both absolute values print on the row label**, because a ratio with no
 magnitude behind it can be a rounding error wearing a percentage.
- **Both article counts print above the chart, and the panel refuses to draw at
 all where either side holds fewer than `console.min_attempts_for_rate`
 summaries.** Two models over two article sets is two measurements, not a
 trend. Andre, 2026-08-30.

Measured 2026-08-31 off the built page, across the one swap the ledger holds -
`qwen3-8b-q4-k-m` on 2,228 summaries to 26 August, `qwen3-5-9b-q4-k-m` on 1,529
since 27 August:

| Measure | Before | After | Against the old model | Better | Painted |
| --- | --- | --- | --- | --- | --- |
| Time to write one | 120 s | 123 s | 103% | lower | bad |
| Summary length | 100 words | 78 words | 78% | no agreed direction | neutral |
| Copied, not rewritten | 9% | 11% | 120% | no agreed direction | neutral |
| Marked "not sure" | 17 in 100 | 14 in 100 | 86% | lower | good |
| Numbers not in the article | 5 in 100 | 3 in 100 | 64% | lower | good |
| "Maybe" told as fact | 12 in 100 | 14 in 100 | 117% | lower | bad |
| Outside the length we asked for | 29 in 100 | 11 in 100 | 38% | lower | good |

It is a difference and not yet a cause, which is what the two article counts are
there to say.

### An axis title and a column header take one form

`Article length, words`. **Sentence case, a comma, the unit in lower case, and
no full stop.** `Sources cut short most often` shipped `Longest article, words`
first, and the compression chart's two axes followed it on 2026-08-29. That
column became a range plot on 2026-08-30 and its axis carries the same form.
Three labels naming a quantity and its unit the same way is a form, so it is
written down here rather than copied a fourth time by eye.

- **The quantity, then the unit.** `Summary length, words` - never `Summary
 length (words)` and never `words`. A bracket reads as a footnote, and a label
 a reader meets before any of the numbers is not a footnote.
- **An axis title may not be a ledger column name.** `source words` is how the
 file spells `source_word_count` and `source_words`. A term from a subsystem is
 not a term for a user (`CLAUDE.md` section 0b), and this is the rule two
 bullets above - no ledger column name on screen - applied to the label rather
 than to the cell.
- **It says what the heading says.** Until 2026-08-29 the compression chart
 called one quantity `Article length` in its heading and `source words` on its
 axis, on one screen. Two names for one thing makes a reader work out that they
 are the same thing before they can read the chart.
- **A label that needs no unit is just the noun.** `Runs`, `Failed`, `Cut
 short`. The comma form is for a quantity whose number means nothing without
 the unit, and adding one where none is needed is noise.

Where each figure is read from is in
[../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md).

### A date axis is thinned by measurement, and a dropped date keeps its mark

One helper: `dayTicks` in
[../../frontend/src/lib/charts/frame.ts](../../frontend/src/lib/charts/frame.ts).
Every hand-written date axis on the console calls it. There were four rules
before 2026-08-31 and three of them thinned by a count.

**A count cannot hold at two widths.** `chart.tick_density` picks the columns
that carry a tick mark, and then the labels are measured against the room the
plot actually has and dropped in whole steps until no two touch. So the knob is a
**ceiling and never a target**: it can take a label away and it can no longer
force one on. Measured 2026-08-31 on the built console at 390px, before this
rule, four axes drew their dates 13.6, 7.4, 26.1 and 1.9px on top of each other.

The width comes from the string rather than from the element, because the axis is
decided on the server where there is no text engine to ask. `LABEL_ADVANCE_EM`
is 0.58, ten percent over the widest character measured at `font-size="10"` in
Chromium on 2026-08-31 - `20 Aug 2026` is 55.83px over 11 characters. It is
deliberately over: an estimate under the truth lets two labels touch, and an
estimate over it only drops one label the axis could have carried.

**A dropped label keeps its tick mark.** A reader counting columns needs the grid
even where the date is gone, so the marks come from the ceiling and only the
dates thin.

**The end labels anchor inwards.** The first and last tick sit ON the plot edges,
so a centred label there hangs half its width outside the frame and an `svg` cuts
what hangs. Measured 2026-08-31 at 1440, one axis drew `10,000` 3.2px past its
own `svg` and read `10,00`. `tickAnchor` is the rule and it binds a value axis as
well as a date one.

Two console axes are drawn by the engine, and the engine owns where its labels go
- `hideOverlap` is its own measured rule. What they take from here is the date
grammar: `2026-08-25` is how the ledger spells a day and it is not how a page says
one.

The oracle is geometric and reads the page rather than the rule. At 1440, 768 and
390 it collects the box of every element carrying `data-day-axis` and asserts
that no two on one axis overlap and that none is drawn outside the `svg` that
would clip it -
[../../frontend/tests/console-axis.spec.ts](../../frontend/tests/console-axis.spec.ts).

## Ranked by magnitude, in one shape

The operator asks the same question of most of this page: which one is worst.
Five of the console's six tables answered a different one. They sorted by date,
so the source that cost the digest the most articles sat wherever it happened to
fall, and the feed one run away from being rested sorted below a feed that has
failed harmlessly for a month.

`RankedList`, `TargetBar` and `Sparkline` in
[../../frontend/src/lib/components/](../../frontend/src/lib/components/) are the
shape that answers it. Their arithmetic is in
[../../frontend/src/lib/charts/rank.ts](../../frontend/src/lib/charts/rank.ts),
`targetbar.ts` and `sparkline.ts`, not in the markup, so the number a list prints
and the bar it draws come from one place.

- **Ranked by magnitude, never by date.** A date sort is a log. It is the right
 shape for exactly one thing on this page - the item list behind a selected
 cause - and the wrong shape for every ranking above it.
- **The list prints its own divisor**, as a sentence: `A full bar is 38 cuts.` A
 bar scaled to a hidden maximum can be read for order and cannot be read for
 size, and nothing on the screen says which of the two the reader has.
- **Capped, with the tail in a sentence.** The sum is printed only where adding
 the hidden magnitudes means something: counts add, distances do not, and a list
 of distances says how many rows are missing and nothing else.
- **The two empty states say different things.** `Nothing has recorded an article
 length yet.` means the ledger cannot answer. `No article was cut short in these
 7 days.` means it answered no. Reading the first as the second is the same
 mistake as reading a null as a zero.
- **No row is tinted.** The order is the ranking. A word beside the name carries
 a status where a row has one, because colour is one signal and never the only
 one.
- **A threshold is a marker on the track, never a subtraction the reader
 performs.** `12 failures` means nothing until the count that rests a feed is on
 the same track. `TargetBar` draws the track at the threshold's own scale, the
 fill at the value, and a rule at the threshold. It takes the confidence ramp
 only where the threshold is a health fact - quarantine is, and a policy limit
 somebody chose is not, so tinting one would invent a verdict nobody agreed to.

The bars and the trend lines are markup, not charts. Seventy target bars in a
feed table would be seventy chart instances, and markup is also what still draws
with JavaScript off. `sparkline.ts` and `targetbar.ts` export the shape both
drawings read, so the two can never disagree about where a marker sits or what
counts as near.

A trend line takes one colour and never the trend ramp. A rising failure count
and a rising published count are the same shape, and green on the first would be
a verdict the page never measured.

## What the cap cost, by source

`Sources cut short most often` is one row per source, ten of them, and it is the
only place on the site that names a source next to a number about that source.
It exists for one decision: **whether raising the truncation cap would actually
reach a source's articles.** It is a horizontal range plot on a log word-length
axis - a track from the source's shortest article to its longest, a dot at the
middle one, and a dashed rule at each cut point across every row. Everything
right of the widest rule is where the cap bites. The geometry, the margins and
the four other places the console reports the cap are in
[../architecture/publishing/frontend.md](../architecture/publishing/frontend.md).

Eight rulings hold it, Jony's of 2026-08-29 unless a later date is given:

- **The cap is on the chart.** This is the whole defect the plot fixes. Five
 columns of numbers were unreadable because the one number every column had to
 be compared against appeared nowhere in the section. Susan, 2026-08-30.
- **The rule comes off the rows, never off `extract.truncation_cap_tokens`.** A
 window can hold rows a run wrote under an older cap, and the setting is one
 number: a thirty-day window holds cuts at 1,923 words and at 3,846, and the
 file says only 3,846. A rule from the file also draws in a window where
 nothing was cut. Fowler, 2026-08-30.
- **It sorts by count, never by rate.** Measured over the committed ledger the
 shares run 3 to 67 percent on denominators of 6 to 38 articles, so a rate sort
 puts a source with 4 cuts of 6 above one with 17 of 38 - and it is the
 seventeen that cost the digest its articles. `Share cut` was dropped as a
 column for the same reason it was never the sort key; what a reader loses is
 the share as a number, and both counts are still on the row.
- **No row is tinted.** The order is the ranking. The confidence ramp means
 good, watch and bad about a summary, and a source at 55 percent is not broken,
 it publishes long articles. The rule itself is drawn in tertiary text rather
 than the low band: a red vertical would say the cap is a fault, and the cap is
 a setting somebody chose.
- **Ten rows and no `Show more`.** The worst seven hold 69 of 153 cuts, 45
 percent; past ten the tail is sources with a single cut in a week, and a
 control that reveals rows nobody acts on does nothing.
- **The track is the whole article, cut or not.** A track over the cut articles
 alone would answer a question about the cap with a set the cap produced, and
 it would hide how short the rest of the source's articles are - which is the
 part that says whether the cap is the problem.
- **No ledger or config name reaches it.** Not `truncation_flagged`, not
 `source_words_before_cap`, not `truncation_cap_tokens`, not `Truncated`.
- **The two empty states say different things.** `Nothing has recorded an
 article length yet.` means the ledger cannot answer; `No article was cut short
 in these 7 days.` means it answered no. Reading the first as the second is the
 same mistake as reading a null as a zero.

**Nothing is abbreviated at any width.** A source id is the ledger's own
spelling of a name, so where the name cannot sit beside the plot it moves above
the track and the row takes one more line of type. Jony, 2026-09-01.

Rejected here: the cut share on the run-health strip (a 16px square has no room
for a number, and it answers "did it work" rather than "what did it read"); a
histogram of article lengths (the engineer's chart - it answers what the corpus
looks like, and this section exists to answer whether raising the cap would
reach a source); a linear length axis (the lengths span more than two decades,
and linear crushes every short source onto the left edge - Carmack, 2026-08-30);
keeping the table and printing the cap in the intro sentence (it answers "how
far past the cap" by subtraction rather than by looking - Susan, 2026-08-30);
tinting rows by share cut (a source at 55 percent is not broken, so the tint
would invent a fault); a gauge, dial, donut or progress bar (six percent on a
dial is one pixel of arc); a before-and-after of a cap change on this page (two
caps over two article sets is two measurements, not a trend); and a table
component shared with `Feeds that failed` (an abstraction for two call sites -
reversed on 2026-08-29 when the count reached four; the shape is the ranked list
above).

**Quality is a table, never a line.** A line invites a trend across days whose
articles have nothing in common. The one thing on the page that draws a spread
is the throughput candle, because a spread is a property of a day's article mix
and a single number cannot carry it.

**A fixed benchmark figure never appears on the console.** It was taken on
another machine against another workload, so a gap between it and a run reads as
a regression nobody measured. Those numbers stay in
[../reference/measurements.md](../reference/measurements.md).

## A chart with a shared column prints every series together, in a fixed strip

One contract, one implementation:
[frontend/src/lib/components/ChartReadout.svelte](../../frontend/src/lib/components/ChartReadout.svelte).
It binds every chart on the console whose marks sit on a shared column - four
series or one - and the rules are not negotiable per chart:

- **A fixed strip below the plot, never a floating box over it.** A floating
 tooltip covers the mark it explains, and one that dodges the cursor moves the
 thing being read. Measured 2026-08-30: a floating box occupied 40 to 55
 percent of the chart it explained.
- **Every series at the hovered column, at once.** Comparing four series must
 not cost four hovers. The strip is the legend as well, so the four numbers a
 reader compares are printed once rather than twice.
- **Capped at `chart.readout_max_share`** - 0.33 today. A share of the plot and
 not a pixel count, so the cap holds at every window width.
- **A vertical guide down the hovered column**, across every series.
- **Reachable by keyboard.** Left and Right step, Home and End jump, Escape
 returns to rest. **A tooltip is never the only place a value appears**: a
 tooltip needs a hover, and a hover is not a thing a thumb can do.
- **It opens on a resting column and is never blank.** The prerendered document
 carries that column's numbers in words, so a reader with no script still gets
 one column read out to him, and the panel never changes size as it fills.

An engine-drawn chart takes the same strip through
[Chart.svelte](../../frontend/src/lib/charts/Chart.svelte). The action goes on
the wrapping element and never on the SVG, because the engine swaps that SVG out
on hydration; the column centres come from `bandShares`, which recomputes them
from the measured width because the engine keeps its grid insets in pixels.

## A chart with no column to hover says so, and no chart draws a key twice

The strip **is** the legend. It prints each series in the colour that series is
drawn in, at the column the reader is on, so a standing key beside it would draw
the same pair a second time - and one fact drawn twice is how two of them drift.
No chart on the console draws a key any more: the engine's `legend` component is
not even registered in
[core.ts](../../frontend/src/lib/charts/core.ts), and the three markup keys that
survived under charts that already had a strip are gone.

A chart with no shared column gets no strip - a ranked list, one target bar, a
flow, two shares of one total. A strip there would print the row the cursor is
already on. **That is a decision, so it is written down where the chart is**:
such a chart carries `data-readout-none` with the reason in words, and a chart
with a column carries `data-readout-columns` with the count.

The pair exists because of what the absence looks like otherwise. A chart
somebody decided needs no hover and a chart where the readout was forgotten are
the same chart on screen.
[console-readout.spec.ts](../../frontend/tests/console-readout.spec.ts)
enumerates every chart on the three console routes, fails on one that declares
neither, fails on a declared column with no strip, and fails on a swatch drawn
inside a chart that has one. It also holds the reason to five words, because
`none` passes an attribute check and tells a reader nothing.

## A stacked chart offers lines only where no data is re-shaped

Stacked says what the mix is and how big the total got. Lines say what one
series did on its own, which a stack hides the moment one band halves while its
neighbour doubles. Both questions are worth answering, so the chart offers both
shapes - **but only where the same array draws both with nothing between them**.

The test is mechanical and is the acceptance rule, not a preference: hand the
engine the identical `data` list in both shapes and change only `type` and
`stack`. The presence of a transform is the definition of "not cheap", and a
chart that needs its data massaged to fit the second shape gets no switch at
all. Owner, 2026-08-30. Two charts qualify today - `What is failing, by stage`
and `Prompt cache`, both callers of `stacked` - and
`console-chrome.spec.ts` fails the build if their two shapes ever draw different
numbers.

One control per panel, never one per series and never a preference that follows
the reader across the site. A Sankey is not a line and a histogram is not a
stacked bar; forcing the control everywhere would mean massaging data to fit it.

## A chart says how much of its window it measured, once, above the plot

`Time per item, by stage` carried one footnote per series, and the three said one
window-level fact three times in near-identical words. A fourth stage would have
made it four. **The count was the defect, not the length**, so shortening each
note would have fixed nothing. One sentence now, and five rules hold it. Susan,
2026-08-31.

- **Once per chart, whatever the series count.** The fact is about the window,
 not about a line.
- **Above the plot, not below it.** A reader meets a broken line before he meets
 the sentence that explains it.
- **The denominator is the day's own item count**, never the sum of the stages'
 totals: one item waits on all three, so summing counts it three times. Where
 the stages reached different amounts of the same days the numerator prints as
 a range, because picking one stage would be arbitrary.
- **Nothing at all where the window was measured in full.** A sentence that only
 ever says "all of it" is noise, and `SPARSE_COVERAGE` is the line it has to
 fall under - see
 [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md).
- **The open-dot legend is a second sentence in the same paragraph**, printed
 once and only where an open dot is drawn.

Not in the hover strip: `ChartReadout` is one contract capped at
`chart.readout_max_share` and it prints one column's values, so a window-level
sentence there would be a second thing that strip means. The oracle asserts
exactly one `[data-timing-coverage]` and holds its two numbers to an independent
reading of the canary ledger. **The series count appears in no assertion** -
that is what proves the sentence stopped scaling with the series
([../../frontend/tests/console-timings.spec.ts](../../frontend/tests/console-timings.spec.ts)).

## A console panel reserves its room, and names which nothing it is holding

> **A reserved box with no failure state lies, and a failure state with no reserved box shifts the layout.** They are one decision and they shipped as one row.

The console held its telemetry inside its own document until 2026-09-09. Every row it draws arrives by fetch now, which split one "nothing" into four - and three of them used to draw the same unmarked gap, so **a quiet pipeline and a broken fetch were the same picture.** That is the exact pair this page exists to tell apart.

| State | What happened | What is on screen | What the operator does |
| --- | --- | --- | --- |
| Waiting | the month files are in the air | the axis frame, its ticks, and marks that shimmer | wait |
| Quiet | every month arrived and held nothing | the panels' own empty sentences, plus one line naming the preset that reaches a month with rows in it | widen the window |
| Missing | the pipeline never wrote those months | the panels' own empty sentences, plus one line naming the months in words | nothing - it is real |
| Unreachable | a month was asked for and did not come back | the reserved shape, and one warn-tinted line naming the month, what is drawn instead, and a retry that names its own subject | press it |

**The box appears where a panel's own words would be false, and nowhere else.** That is the whole rule, and the first shape of this row got it wrong: it put the box in front of every non-ready state. Seven specs went red and each was right. A panel with rows on the way that printed "nothing is on record" would be wrong for the next second, and one whose month did not arrive would be wrong outright - those are the two the box takes. An empty window and a real gap are the other way round: the band chart already says "No summaries in this window" and the failure list already says what it found, and three precise sentences beat one general one. **What no panel can say for itself is which of the three settled nothings it is holding**, so that is said once, above the panels and beside the control that governs the window. The box carries no words at all for the same reason: a dozen panels each repeating one page-level fact is a dozen announcements of one thing.

Five rules hold under that table.

- **The box is exactly `console.chart_height` tall, in both the states it appears in.** [../../frontend/tests/console-reserved.spec.ts](../../frontend/tests/console-reserved.spec.ts) measures every panel's real bounding box twice in one page session - while the months are in the air and once they have landed - and fails on any panel that changed size except the one named as fetched. It reads boxes and never a CSS property, because a CSS property is not what moves under a cursor. Measured 2026-09-09 at 1280 CSS px on a developer machine: seven panels, none changed width, one changed height by 172 px. **A second arm watches the chrome above the panels**, which nothing watched before: the title, the strip, the band, the window control, the carry line and the glance grid, each against its own former box. The set is cut at the first panel's own top rather than at the fold, and that correction is the second half of the same measurement. The fold-based form asked which blocks sat inside the first 900 px; the first panel begins at 894, so it was really asking how tall the runner's fonts were, and on `ubuntu-latest` the set came back empty and took `main` red. A cut made at the panel holds at any viewport and on any machine. Each block is compared on its own rather than the panel's top being compared to itself, because a top says only that the total height above it held - a block that grew by the amount its neighbour shrank would pass, and the failure would name no block. This one names it: a 24 px line injected into the chrome fails with the two blocks below it listed by name, and the box each held before and after.
- **An empty plot draws its axis frame and its tick marks and no numbers.** A tick label needs a value and there is no value, so a number printed there would be invented. Both come out of the same `frame` and the same margins the real charts use, so the frame a reader watches is the frame they get - and the box carries no tint of its own, so the axis sits on the same ground the real charts' axes do. Measured over the committed token values: `--chart-axis` reads 3.2:1 in dark and 2.58:1 in light on a panel, against 2.76:1 and 2.38:1 on a tinted box. The waiting frame is exactly as legible as the chart it stands in for, neither louder nor quieter.
- **A skeleton mark takes `--color-rule-strong`, and that was measured rather than picked.** The sunken surface reads 1.06:1 in dark and 1.13:1 in light on a panel - a block nobody can see is not a block, and in light it was gone until the sweep crossed it. Rule-strong reads 1.61:1 and 1.48:1: plainly there, and still well under the weight of a drawn mark, which is what a placeholder owes.
- **Every skeleton on the surface is on one timeline.** The sweep is switched on by a single attribute on an ancestor, so every block starts its animation in the same frame. Out of phase, a dozen sweeping boxes read as a dozen broken things rather than as one page waiting.
- **The sweep starts late.** `console.shimmer_after_ms` is how long a wait has to outlast before it is worth drawing as one, so a fetch that lands first never animates at all. **It ships at 400 as a declared estimate and not a measurement** - see the design rationale below.
- **Only a failure takes a hue.** A quiet window and a real gap are normal, and a page that tints normal things like faults teaches its operator to stop reading the tint.

**And a retry names its own subject.** `Try again` is shorter and it is what the shape asks for, but a button read out of the sentence above it then names nothing. `Try August 2026 again` is three words longer and true on its own. It re-fetches only the months that failed: a retry that re-fetched the whole window would spend an operator's connection on months already in hand, and would blank panels that are answering correctly.

Authority: Susan and Fowler, plan row #12.

## Design rationale

**`console.shimmer_after_ms` ships at 400 and 400 is a declared estimate, not a
measurement.** Guardrail #10 refuses an unmeasured number the right to justify a
design, so this one justifies nothing: nothing about the shape of the console
depends on it, and the knob decides only whether a wait short enough to be over
already gets animated on its way past. The console started fetching its months
on 2026-09-09, so no median payload arrival exists yet to derive it from. The
shell-and-fetch migration was meant to take that measurement and could not:
the number is a reader's wait, and a reader-facing timing measurement was
ruled out of that plan's scope (owner, 2026-09-08). What would settle it is
in [../reference/measurements.md](../reference/measurements.md). Taking it inside the user-interface row was refused: a
user-interface row is not a measurement harness, and a number measured on a
laptop's loopback would be the wrong number twice over. Fowler, 2026-09-08.

**Every skeleton is switched on by one attribute on an ancestor, and that is what
makes them one timeline.** The rejected alternative was the obvious one: give
each block its own timer. Each block is then correct on its own and the page is
wrong - twelve sweeps at twelve offsets read as twelve separate broken things
rather than as one page waiting. Hanging the switch on the ancestor buys a
property a test can state in one line: every animation reports the same
`startTime`.

**The refusal of a shared table component was reversed on 2026-08-29, and the
reason it was right at the time is the reason it is wrong now.** It was refused
as "an abstraction for two call sites", which is a good rule. Counted again on
2026-08-30 once every section had landed, the three components draw **nine times
across five sections**, and two of those sections did not exist when the refusal
was written. What the refusal protected against was a generic `Table`, and that
is still refused: the console's problem was never table markup, it was that a
table is the wrong shape for "which one is worst", and a generic table would make
the wrong shape cheaper to produce. What landed instead is a shape with an
opinion - one order, one divisor, one tail sentence, two empty states. Fowler on
the reversal, Susan on the shape, 2026-08-29.

**The geometry was pulled out of the two chart helpers rather than copied.**
`sparkline.ts` and `targetbar.ts` already owned the rules and each also built a
chart option. A second copy for the markup bars would drift, and the drift shows
as a marker in one panel and a verdict in another disagreeing about the same
number with nothing on screen looking wrong. The rejected alternative was having
the markup call the chart builder and throw the option away; it makes a component
that draws no chart import a chart builder, which the next reader has to work
out.

## See also

- [design-system.md](design-system.md) - the tokens, ramps, motion set and sufficiency gate this page draws on.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - what each console panel is, and where its data comes from.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - the published projection and the grain of every figure.
- [config.md](config.md) - the knobs these rules read.
- [../reference/measurements.md](../reference/measurements.md) - the instrument log the console never quotes from.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0b (voice) and Guardrail #10 (every number carries its conditions).
