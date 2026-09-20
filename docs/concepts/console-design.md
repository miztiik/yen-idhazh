# Console Design

**Last Updated**: 2026-09-20
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

Six states have fixed wording, five written by the owner on 2026-08-30 and one
by Susan on 2026-09-17, all held in
[../../frontend/src/lib/console/recording.ts](../../frontend/src/lib/console/recording.ts):
measurement off, sampled below 1.0, counters but no scores, scores but no
counters, recording started mid-window, and a day that published and lost what
it measured. Only the dates and counts inside them are computed, and every one
is derived from the ledger that is missing - **a date that is not true is worse
than no date**. None is apologetic, none is styled as an error, and none is a
banner across the page: three panels can be in three different states on one
day.

### A record that had not begun, a quiet day, and a record that was destroyed

They are three states and they send an operator to three different places, so
they may not share a sentence. Susan, 2026-09-17.

On 2026-09-16 a merge collision destroyed 303 machine rows. The day had
published articles; the record's own day file survived with its header and
nothing else. Hardware printed the sentence a day before the record shipped
gets - the flags and the cache **start on the day the machine record ran** - so
the one day the console existed to report read as the one day nothing had
happened yet.

**The derivation is one join and it carries no judgement.** The digest for that
date carries articles, so a run worked; the record opened a day file and kept no
row, so what it measured is gone. A day with no file at all is the first state,
not this one. A day whose file is empty and that published nothing is the
second.

**A day proved lost is never counted as a day before the recording started.**
Counted in that gap it would date the instrument's own start to the day AFTER
the loss and hand that date back as the reason for it.

**The states are named in `data-` attributes, not only in the sentences.** A
page whose state can be read only off its prose can be checked only by looking
for a sentence, and an assertion that a sentence is absent passes as happily
when somebody renamed it as when the defect was fixed. `data-machine-record`
carries one of `recorded`, `off`, `lost` and `none` on every build.

Two of them are worth reading twice. **A sampled figure is never scaled up** -
multiplying a quarter-sample by four publishes an estimate as a measurement,
which Guardrail #10 forbids. And **no string names a config key as if it were a
word**: it is `Measurement is off`, never `host_fingerprint is false`,
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
- **Once the figure has a shape, the word rides the shape.** The value axis
 reads `Counterfactual cost, USD`, and the running shape reads `Counterfactual
 cost so far, USD`; the chart's own description says it again for a reader who
 cannot see the marks. A currency code alone on an axis is the shape a bill
 takes just as surely as a symbol is, and an axis title is the label a reader
 meets before any of the numbers - so it is the one place the word cannot be
 missed. The four figures above the chart keep the sentence they already
 carried. The chart does not inherit it by being near it.
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
is already being printed. The cap has moved three times since and the count is
still zero by arithmetic: the longest single-call prompt the committed cap can
produce sizes at 25,156 tokens, which is 38 percent of the 65,536 window
([../reference/pipeline-cost.md](../reference/pipeline-cost.md)). **What that
window is held open for is the two-call pair, which the counter does not read**
- it sizes at 54,887 tokens
([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)). So
this counter would catch the next move of the cap going too far for the path it
watches, and the pair has an assertion of its own.

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

## A machine is a colour and a name, and no rate is pooled across two of them
The Hardware route draws three panels about the machine a job drew: **Reading
against writing, machine by machine**, **The machines this run drew**, and **What
the platform has been giving us**. One measurement shapes all three.

Measured 2026-09-17 over the committed shard records - 380 rows, 95 runs, 19
dates - **86 of the 90 runs that name a processor drew more than one kind of
processor**. Kinds per run: one on 4 runs, two on 39, three on 43, four on 4.
Inside a single run the read rate between the fastest and the slowest machine
runs 1.00x to 6.08x, median 2.32x, and 45 of the 86 exceed 2x. Run
`2026-09-12-34689544296` read at 59.71 tokens a second on one shard's machine and
9.83 on another's.

So the rules below are not a preference about charts. A figure pooled across the
machines of one run is wrong on 95.6 percent of runs, and it was the most
quotable number on the route.

- **The machine is the unit, and the pooled figure is deleted rather than kept
 for comparison.** Each group prints its own read rate, write rate and
 multiple, from its own shards, sum over sum. One headline survives and it is
 the write-cost multiple of **the machine that read the most tokens in that
 run**, named on the line.
- **Shards that recorded no machine are their own group and are never merged
 into a named one.** 24 of the 380 committed rows have no processor name, and
 folding them into a machine attributes somebody else's seconds to it.
- **The one case where pooling is allowed carries its own sentence.** Where no
 shard of a run named a machine at all, the single group IS the pooled split,
 and the panel says so: a run that drew more than one machine - 86 of the last
 90 did - would have had two machines averaged into it.
- **A run that drew one machine says so too.** That is a good state, 4 of 90,
 and the panel reads as one rather than as a panel with a missing spread.
- **Colour is assigned ascending by key, and the key is the machine's digest
 where one was recorded and its model-name string where none was.** Arbitrary
 on purpose: by speed or by draw count the ramp would encode an ordering it
 does not mean, and by order of first appearance a machine would change colour
 when the operator changed the span - which is the control the colour exists to
 survive. The ramp is assigned once for the page, over every machine any panel
 can show at any preset, so the assignment is fixed for a build.
- **`--chart-8`, the grey, is reserved for "Machine not recorded" and is given
 to no machine.** An absence is not a machine and must not take a machine's
 hue. Rejected: hashing a machine to a stop, which collides about 60 percent of
 the time over six kinds in seven stops - and a collision is a lie the page
 cannot see.
- **`console.machine_colour_stops` bounds the ramp, and the overflow is named in
 words.** Seven machines take seven stops; an eighth folds the tail into one
 row that lists its members. Never two machines in one colour without the page
 saying so.
- **The name is on the row, always.** Colour here encodes a fact, so it is
 semantic and may never be the only carrier of it. That is also why the split
 is rows rather than a scatter: a scatter cannot carry a name per mark.
- **A card carries every watched instruction-set flag, present or absent.** A
 present flag takes `--tint-accent`; an absent one takes a hairline outline at
 the same width. The machine we draw most reports none of the watched AVX-512
 entries, so a list of what a machine has cannot show the one it is missing -
 and the missing one is what decode dispatches on. **Never read** and
 **reported none of them** are different facts: the first draws no chip and
 says so.
- **The bandwidth reading and the buffer it was taken with are one sentence.** A
 buffer at or below L3 never left cache and reads several times high, so the
 sentence says `this measured cache, not memory` rather than leaving a reader
 to compare two numbers in different places.
- **L3 and the copy rate are lengths on a track every card of the panel
 shares.** Two numbers in two sentences on two cards is a subtraction the
 reader performs; two bars on one domain is a difference the eye reads. The
 reading stays in words under its own bar, so the track is the comparison and
 never the carrier of the number.
  - **Each measure has its own domain and it comes from the readings drawn.**
    No runner model publishes a ceiling for either, so there is no limit to
    measure distance from: a fixed maximum would clip the next bigger machine
    or spend the track on room nothing reaches. The domain is anchored at zero
    and niced by `linearAxis`, which makes two lengths the two readings.
  - **MiB of cache and GiB/s of copy rate share no axis.** They are two
    quantities, so neither reading can be read off the other's length. The
    twenty-to-one test does not apply between them and is never taken.
  - **A cache reading is refused rather than pooled with the memory ones**, for
    the reason the sentence above already carries: a buffer inside L3 reads
    several times a memory rate, and on one track it would draw as the fastest
    machine of the run. The card says why its rate is not drawn.
  - **Under two readings of a kind there is no bar.** A lone bar's domain is
    its own value, so it fills the track whatever it says, and a full bar reads
    as a maximum rather than as the only one. Named on the card, because a bar
    missing beside a bar drawn is the state a reader would otherwise have to
    work out. The three refusals are `absent`, `alone` and `cache`, and
    `data-machine-bar-state` carries whichever holds.
- **A count of machine kinds is a count and never a rate.** No percentage, no
 probability, no pie: what the next job will draw is precisely what the
 processor lottery refuses to quote. Under `console.fleet_min_rows` it is a
 list with a sentence and **no bar at all** - bars over a handful of placements
 read as a distribution, and a reader who has read one will act on it. **It
 ships at 160 as a declared estimate and not a measurement** - see the design
 rationale below.
- **Over that floor the count is a trend, one group a day and one bar a kind.**
 The panel's title asks what the platform has been giving us lately, and a
 ranked list answers which is biggest rather than what is changing. The
 ordering the list carried is not lost, it is the sentence above the plot.
 **Only days that recorded a placement are drawn** - a zero-height group would
 say the platform gave us nothing that day, and a day the record never reached
 says nothing at all - so the count of days missing from the window is printed
 in the same sentence.
- **Past `console.fleet_top_kinds` the rarest kinds are one bar, named in
 words.** A grouped bar is only a bar while it is wide enough to paint: at
 `console.chart_width` of 760 and the widest span the window control offers, 90
 days, a day band is 8.4 px, five bars in it draw 1.09 px each after the chart
 engine's own gaps and seven draw 0.77 px. Four kinds plus the fold row is the
 largest set that clears a pixel there. **The fold bar equals the kinds it
 folded, in the window and on every day of it**, and the page carries both
 figures so it can be held to them agreeing.
- **None of the empty states is tinted and none gets the reserved box.** The
 route is prerendered and reads `state/` at build time, so there is no fetch,
 no waiting state and no unreachable state. Every nothing here is settled at
 build time and gets words. The heading and the note always stay.

Two panels were refused, and what the reader loses is on the record.

- **Bandwidth against decode speed was refused**, so the only on-screen test of
 whether decode is really bandwidth bound is missing. What buys it back today
 is that the machine card prints that reading in words per machine and draws it
 against the other machines of the run: the fact is on the page and its spread
 across the fleet is drawn, so only the correlation with decode is absent. It
 ships when `console.fleet_min_rows` rows exist **and**
 `console.bandwidth_min_kinds` distinct kinds carry a bandwidth reading. Two
 points define a line, so a scatter of two is a claim rather than a measurement.
- **A processor detail table was refused**, so a reader cannot read a raw column
 value off the console, and twenty-seven columns is the reference page's job.
 Five of those columns were bought back: the machine card's own `<details>`
 carries the platform's size, region, zone and fault domain, plus `microcode` -
 the one cell that moves without anything else moving, and so the only
 explanation left for a speed change with no other change. Closed by default,
 so the attention cost is zero.

Authority: Susan, 2026-09-17. The bars are Susan, 2026-09-20.
The sufficiency checks pass, conditional on the twelve flag chips shipping: a
definition list of text rows with a semicolon-joined vendor string is a 2004
page, and dropping the chips fails **made this year** and would need a
`## Design rationale` entry of its own. **Two of the card's readings were
sentences and are now lengths**, which is what carries the two-second check:
`32 MiB` beside `260 MiB` on two cards is a division the reader performs, and
two bars on one track is not.

**The veto that cost the most was a title.** "The host under the newest run"
let the page carry one processor string for the whole of its life, and that
framing is why a panel summing four counters across three machines read as
correct for weeks. The reader lost the single most load-bearing fact on the
route: a run is not a machine. Renaming it is the correction, not a rename.

## A countdown is drawn as an area, never as a fraction in a chip

`Sources close to retiring themselves` is one row per source on
`/console/voices/`: the name, a target bar of the trailing share against the
alarm point, and a square a day beneath it. Susan, 2026-09-17.

It exists for one decision: **is this source recovering, or is it counting
down?** A total cannot answer that. `41%` over thirty days and `41%` on the
fourteenth day of an unbroken run are the same number and two completely
different situations, so the panel adds a time axis and reads the run length off
it.

Six rulings hold it.

- **The dwell is the area.** A 2px rule in `--fill-low` sits under exactly the
 contiguous under-the-mark squares at the newest end. A `9/14` chip with no
 marked run is the failure this replaces: it asks the operator to trust a count
 they cannot check against the picture beside it.
- **The track is the full 0 to 100 percent share, and the marker is the alarm
 point on every row.** A per-row maximum, or a marker at a different x on
 different rows, makes a stack of bars unreadable while each one looks correct.
 The whole reason to stack them is that a column means one thing all the way
 down, and the strip below obeys the same rule: one shared date axis, and every
 date present on every row even where the source was silent.
- **Colour is never the only signal.** Each square carries its own sentence, and
 the row prints `Under the mark for 9 days running` and the date it completes.
- **The date comes from the newest day the ledger holds, never from a clock.** A
 console re-opened after midnight must not move a date the run decided.
- **A red countdown while nothing retires is a lie told in colour.** While
 `collect.source_quality_auto_retire` is false the panel says
 `Nothing retires on this measurement yet - this panel is watching only.`
- **A source under its evidence floors is drawn, not hidden.** It keeps its full
 strip, its bar becomes a dash reading `not judged yet`, and the row prints how
 much evidence it has against how much it needs. Hiding it would hide the shape,
 which is what an operator came for; what it has not got is a number anybody may
 act on.

The ledger's own absence keeps the heading and both lead lines, and replaces the
rows with one sentence. A panel that shrinks to nothing when its data is missing
teaches an operator to stop looking at it.

## What the cap cost, by source

`Sources cut short most often` is one row per source, ten of them, and it is the
only place on the site that names a source next to a number about that source.
It has been on `/console/voices/` since 2026-09-14, with the census, the ranking
weight and the failure list.
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
[../reference/pipeline-cost.md](../reference/pipeline-cost.md).

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

## Thirteen rules hold for every chart on this console

> **Argued once so that no panel argues them again.** Thirteen rules settled in one place beat thirteen rules settled nine times, and a reader cannot learn nine answers to one question.

Susan ruled these on 2026-09-17, after reading all 23 console panels, both timing
components, the chart library and the committed ledgers. Twelve are chart craft -
what the drawing may do. The thirteenth is the question the panel answers, and it
catches more failures than any of the other twelve. **Each rule carries its
reason, and the reason is the load-bearing part**: a rule quoted without it is a
half-quote, and a rule whose reason has stopped holding is a rule to change.

- **A fixed value domain is allowed only where the ceiling IS the comparison, and
  then the panel prints the ceiling beside the figure.** Everywhere else the
  domain comes from the data drawn, niced by the scale library - which is what
  `linearAxis` already does. A fixed axis over adaptive data wastes the plot; an
  adaptive axis over a limit deletes the comparison. **Five things are not "the
  data drawn". Four of them widen the domain rather than replacing it; the fifth
  narrows it, and is allowed only on the condition written beside it.** Each is
  named with the shipped site that proves it, because an exception nobody can
  point at is an exception nobody can check.
  - **A limit the panel exists to measure distance from** - 16 GiB of runner
    memory, the context window - **joins the values the domain is built from**,
    so the limit is a line on the plot and a breach still draws past it. It is
    never the axis maximum, which would clip the breach at the line and hide the
    one reading the panel exists for. Shipped twice: `targetbar.ts` runs its
    track to the larger of the value and the target, and the context headroom
    panel on `/console/machine/` builds its axis from the drawn extent rather
    than from the window it is measured against.
  - **A share or a cumulative percentage runs 0 to 100**, because a curve that
    stops short of its own top reads as a curve that has not finished. Shipped in
    `TimeHistogram.svelte`, whose right-hand percent axis is always the full
    nought to a hundred and whose comment is where that reason is already
    written. `FailurePanels.svelte` fixes the same axis for a second reason worth
    keeping: a rate over a known range is compared across stages and across days,
    and scaling it to the window's own maximum drew a 12 percent rate and a 90
    percent one at the same height.
  - **A ratio against a baseline is symmetric about that baseline and carries a
    minimum width**, or a two percent change fills the plot and reads as a rout.
    Shipped as `swapScale` in `series.ts`: no change is 100 percent and that
    point is the axis centre, and `minHalf` holds the half-width at 25 percentage
    points however small the real spread turns out to be.
  - **Every plot a panel means the reader to compare shares ONE domain.** A
    per-plot domain inside one panel deletes every comparison the panel was built
    for. Shipped in the five tail plots on `/console/machine/`, which take one
    `linearAxis` over the extent of all five.
  - **A distance far smaller than the population it sits in takes a window
    around the limit instead**, and every value outside that window is counted at
    the edge with its own figure printed rather than drawn. This is the one case
    that narrows the domain, so it carries a condition: **the breach side has to
    stay inside the window**, or it is the clipped breach the first case already
    refuses. Shipped once, on the holdout panel of `/console/judgement/` - see
    [the holdout margin is drawn at the scale of the
    margin](#the-holdout-margin-is-drawn-at-the-scale-of-the-margin-not-of-the-score)
    for the two measurements that forced it. Owner, 2026-09-19.

  **The cost this rule accepts, stated rather than hidden:** an adaptive axis
  re-nices when the reader moves the window, so the same panel on two days is not
  comparable by eye. `.nice()` bounds that to whole tick steps and the readout
  strip carries the figure - a reader who wants the number reads it, a reader who
  wants the shape gets a full plot. Audited 2026-09-17 across
  `frontend/src/lib/charts/` and its callers: 24 domains, 21 adapting and 3 fixed
  with cause, so **the rule ratifies what is shipped rather than changing it.** An
  earlier wording - set the maximum to the ceiling - would have broken two of the
  three correct ones. The 1 GB Pages cap is not on this list: it is arithmetic in
  `glance.ts` and never a scale.
- **A stacked series has a fixed order, stated once.** Read at the bottom, write
  at the top, everywhere. Unclaimed and residual always last. A stack whose order
  moves between panels cannot be compared between panels, and a reader cannot
  learn it.
- **No piecewise or non-uniform value axis.** Where a spread genuinely defeats a
  linear domain, use a log scale and label it as one. Equal pixel steps standing
  for unequal value steps is a chart that misreports by construction; a log axis
  misreports nothing, it just has to say so. The owner asked for a 0/10/50/100
  axis on the shard board and it is refused. **What the reader loses by not
  having it, named:** at a 6x spread across machines the low bars compress, and
  the detail at the low end compresses with them. That compression is the true
  picture of a 6x spread and is the thing worth seeing, where the piecewise axis
  would have drawn the slowest machine and the fastest at comparable lengths.
  Measured 2026-09-17: on a linear domain of 0 to 75 tokens a second, a 12 tok/s
  bar still draws at 16 percent of the track, which is readable - so the refusal
  costs nothing the panel needed.
- **Two series share one axis when the larger is under 20x the smaller; past that
  the smaller takes its own row on a shared x.** Measure before choosing. At 20:1
  the smaller draws under 5 percent of the plot and reads as zero. The threshold
  is a measurement rather than a taste, and the panel records the ratio it
  measured beside itself.
- **A panel may carry a shape switch or a grain switch where ONE builder call
  returns every shape it offers.** Never two calls, never a second fetch. This is
  what preserves the reason behind the no-re-shaping rule below - two derivations
  that can disagree - while allowing a cumulative line and a shard-or-item grain.
  `chartFlow` is the existing precedent.
- **A switch control sits top right of its own panel, and it is radio inputs.**
  Two named states a reader can see both of beats one state and a verb. Top right
  because the control belongs to the panel rather than to the page.
- **A tooltip is never the only carrier of a fact.** Every panel carrying one also
  carries the readout strip or a printed list. The dominant reading device has no
  hover. Restated here because tooltips are arriving at nine panels at once.
- **A segment under 1 px at `console.chart_width` is not drawn as a segment.**
  Where a split's smallest band falls below that, the split becomes a printed
  figure and the bar draws whole. Measured 2026-09-17 over 23 shard-rows of
  `state/span-rollup/2026-09.csv`: the four sub-steps of a shard's clock together
  draw 0.026 px of a 760 px track and the residual draws 0.039 px, and a browser
  paints neither. **A band at 0.026 px is a legend entry with no mark**, which
  teaches a reader the category is zero when it is only unmeasurable at this
  scale.
- **A legend key for a series with no committed rows is deleted, not drawn
  empty.** The `robots check` key has stood in one legend across 23 shard-rows
  that never carried it. A key for an absent series is a claim the data does not
  support.
- **A figure with a span is drawn as a range, never written as two sentences.**
  Value, low, high, one track. Figures that each have a span, each written as
  prose, are sentences no two of which can be compared.
- **A panel whose title asks a trend question draws a time axis.** A ranked list
  answers "which is biggest", never "what is changing". The title and the shape
  have to agree, or one of them is wrong.
- **Bar thickness comes from one place and a bar is never thickened to fill
  vertical room.** Room left over goes back to the panel. A thick bar reads as
  importance; thickness is not a variable here, so it must not vary.
- **A panel serves _is it working_ or _what is broken_, and names which. A verdict
  panel sits above the panels it verdicts.** A verdict takes the central value or
  the count and covers every subsystem. A break takes the extreme and the
  individual that owns it, and covers every candidate in one subsystem. A panel
  whose title asks one question and whose shape answers the other is the
  commonest defect on this console: of the eight panels that failed review on
  2026-09-17, five failed on this rule and only three on their drawing. The
  rule's own proof is the peak-memory panel - a per-shard maximum is the verdict
  reading, and the item that took the model process to 83.1 percent of the
  runner's 16 GiB is invisible behind it. One measurement, two questions, one of
  them built. **What a scattered verdict costs the operator:** he reads ten
  Hardware panels and only then reaches the panel that tells him whether the
  instruments agree.

Authority: Susan, 2026-09-17. Which surface answers which of the two questions is
[../architecture/publishing/console.md](../architecture/publishing/console.md);
this page rules how the drawing may read.

## A typical reading and the worst one are one mark, not two bars

A **range mark** is a track with a fill and a notch. The fill runs to the median
and the notch stands at the maximum, so the distance between them is the spread
and the reader measures it with their eye rather than by subtracting two
sentences. It is the shape the tenth rule above asks for, given a name because
the shard board draws two of them on every row.

**Why it exists: four bars a row is eighty bars.** The shard board carries a
memory reading and a processor reading, each with a typical value and a worst
one. Drawn as bars that is four per row, and a run of twenty shards is eighty
bars in one panel with the reader pairing them by eye. Drawn as two range marks
it is two tracks, and the pairing is already done. Susan, 2026-09-17.

**What the reader loses, named.** A range mark says nothing about the shape
between its two ends: a shard whose items were all near the median and one that
had a single spike draw identically. That distinction belongs to a distribution
panel over items, which is a different grain and a different question - the
board is a break panel over shards, and its job is the extreme and the shard
that owns it.

Both marks obey the first rule above. The memory mark takes the runner's 16 GiB
into the domain beside the drawn values rather than as the maximum, so a shard
that went past the ceiling would still draw past the line, and the panel prints
the ceiling. The processor mark is a share, so it runs nought to a hundred.

## A mark with two named ends is not a range mark, and it says which end is which

A **range mark** has a typical end and a worst end, and the reader learns that
shape once. **A mark whose two ends are two different measurements is a
different mark**, and giving it the range mark's field names would have taught a
reader to read a floor as a median. So it carries its own names.

The shipped one is the kernel headroom mark on the memory panel of
`/console/machine/`. Its fill runs to `os_mem_available_min_bytes` - the least
memory the kernel had while the model worked on that item - and its notch stands
at `os_mem_available_bytes`, which is what the item left when it ended. **A
machine whose floor falls and whose end also falls is leaking; one whose floor
falls and whose end recovers was only working hard.** The two states draw
differently, and the floor alone draws them the same.

**What the reader loses, named.** The mark says nothing about when in the item
the floor fell, so an item that dipped once and an item that sat at the floor
throughout draw identically. That is a question for a sampled series over one
item, which is a different grain and an instrument nobody has built - and the
panel says it cannot answer it rather than leaving the reader to assume it did.

Authority: Susan, 2026-09-17.

## A reading and the window it is read against are one track

A **span track** is a band and an upright. The band runs from the lowest reading
the window holds to the highest, and the upright stands where the newest run
read. Whether that run was unusual is then one look, rather than three numbers a
reader converts and subtracts.

**Why it exists: a sentence cannot be compared with the sentence beside it.**
`What the server did outside the model call` on `/console/machine/` carries a
processor share and a weight-opening time. Each was a reading followed by its
span in prose, in a different unit from its neighbour and with its ends buried
mid-paragraph, so a reader who wanted to know which of the two was the odd one
this run had to do the conversion by hand. Two tracks make that comparison free,
and the shape is the one the memory panel's window grain already draws - so this
is one shape reused rather than a second shape learned. Susan, 2026-09-20.

**One shape, two drawings, stated rather than hidden.** The memory panel drew
this shape first, in its own markup. The maths now lives once, in
`frontend/src/lib/charts/span-track.ts`, and the host panel draws from it; the
memory panel has not been repointed. **What that costs:** two pieces of markup
that have to agree by eye, so a change to the band or the upright is a change in
two places until the memory panel becomes a caller.

**What the reader loses, named.** A span track says nothing about the shape
between its ends, and nothing about when in the window each end fell: a figure
that drifted steadily and one that jumped once and held draw identically. That
is a question for a series over runs, which is a different grain - `How the tail
moved` on the same route is the panel built for it, for a different figure.

**An absent span is said, never drawn.** Where no run in the window recorded the
figure the panel says so in words and draws nothing, because a band of no length
would report a window that read the same thing every day. Where the window has
both ends but they sit closer than one pixel at `console.chart_width`, the span
is printed and the band becomes a mark - the eighth rule above, applied to a
band rather than to a split. A run that recorded nothing keeps the band it
cannot be placed on: the window still measured something, and the missing
upright is the fact.

**A figure with no span is not given a track.** Parallel slots sits in that same
panel as one line of text, because it is a count of what a server offered and
has no low-to-high window to place a run inside. The tenth rule binds a figure
with a span; a shape reused where it does not fit is a shape a reader stops
trusting.

Authority: Susan, 2026-09-20.

## The two rates on a shard row are measured before they are drawn

Reading and writing are two series on one board, so the fourth rule above binds:
they share one domain while the larger is under 20x the smaller, and past that
writing takes its own. The board measures the ratio from the run it is drawing
and prints it, rather than choosing once and hoping. Measured 2026-09-20 over
the three newest committed runs, a shard writes at 3.39 to 5.09 tokens a second;
the read rates on the same ledger have run 9.73 to 41.98. That is about 12x at
the widest, so the two share one scale today - and the panel will say so, or say
the opposite, from whatever run it has.

The rate domain is the largest rate on the board and never a round number. A
shard reading at a quarter of its neighbour draws a quarter-length bar, which is
the reading the panel exists for.

## A comparison drawn in one unit can be confidently wrong, so it carries both

**Reading and writing are two quantities only if you count them.** Counted in
tokens they are one quantity in two directions and the fourth rule above binds;
so are they counted in seconds. What the two counts do not have to agree about
is which side is bigger, and where they disagree the unit is the whole answer.

The shipped case is `What a run reads against what it writes` on
`/console/machine/`. A run reads far more tokens than it writes, so in tokens the
read bar towers. **Reading is batched prefill and writing is sequential decode,
so a tall read bar is not a run that spent itself reading.** A panel that offers
only the count teaches that it is, fast and without a caveat, and a reader who
acts on it tunes the prompt when the clock belongs to the answer. So the panel
carries a unit switch, and the switch is the finding rather than a convenience:
which side is taller in each unit is exactly the question "where did the model
time go", answered by looking rather than by a caption.

**The switch qualifies under the fifth rule because one call returns both
units, and the row set is decided once.** An item row is admitted on its token
counts, and its `prefill_ms` and `decode_ms` are then summed over exactly those
rows. Two independent filters would let the two units cover different runs, and
a panel whose units disagree about what they measured cannot be recovered by
reading it harder. It needs no new column: both durations already reach the
frontend for the read and write rates on the shard board.

**Each unit measures its own ratio and prints it**, so the fourth rule's
threshold is taken from the data drawn rather than assumed - and where one unit
passes 20:1 the smaller series takes its own row in that unit only. **What the
reader loses, named:** a unit switch is a state to remember, and an operator who
reads the panel in tokens on Monday and in seconds on Tuesday is comparing two
pictures. The panel opens on the same unit every time and prints the unit beside
the ratio, which is the most a switch can do about that.

Authority: owner, 2026-09-17. Susan rules the unit it opens on.

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

**The rule is widened, and its reason is what the widening preserves.** Susan,
2026-09-17. The identical-array test refuses a cumulative line, because a running
total IS a re-shape - so the counterfactual-cost panel could not offer
"cumulative by day" against "per day" at all, and the only shape a cost has that
answers whether it is growing is the cumulative one. What the original test was
protecting against was never the transform. It was **two derivations that can
disagree**, where a reader who finds both has nothing on screen saying which to
believe. So the test widens to the thing that actually holds that: **one builder
call returns every shape the panel offers**, never two calls and never a second
fetch. Where the same array draws both shapes with nothing between them the
stronger form still holds, and it is still the one to prefer.

**What the widening costs.** The byte-identical assertion no longer covers every
switch. A panel whose shapes come out of one call but are not the same array owes
its own oracle comparing the two shapes' numbers, the way `console-chrome.spec.ts`
already compares the two that qualify under the stronger form.

**The counterfactual-cost panel is the first to ship under the widened form, and
this is the oracle it paid.** `costOverDays` walks the window's runs once and
returns one array of days, each carrying what reading cost, what writing cost,
and the running total to that day. The bars read the first two, the line reads
the third, and neither derives anything. `console-machine.spec.ts` asserts the
line's last point equals every bar added up, and asserts it a second time against
the window total the four figures above the chart print - so the two shapes and
the headline number are one piece of arithmetic reached three ways.
`console-machine-panels.spec.ts` then asserts in a browser that moving the switch
changes neither the day count nor that total, which is what a second derivation
would have moved.

**Reading is the bottom band and writing the top, and the panel measures whether
the split may be drawn at all.** At the committed rate, over the 25 days the
ledger held on 2026-09-20, the writing half ran between 27.4 and 45.4 percent of
its own day, and the thinnest band of all measured 2.0 percent of the tallest
column - 3.3 px of a 164 px plot, so the split draws. The rate is the operator's
to type, though, and a writing rate near zero takes that band under a pixel. The
builder measures the thinnest band against the tallest column before it picks a
shape; under a pixel the column draws whole and the split becomes the printed
figure beside it, with the measurement it was decided on printed too.

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

- **The box is exactly `console.chart_height` tall, in both the states it appears in.** [../../frontend/tests/console-reserved.spec.ts](../../frontend/tests/console-reserved.spec.ts) measures every panel's real bounding box twice in one page session - while the months are in the air and once they have landed - and fails on any panel that changed size except the one named as fetched. It reads boxes and never a CSS property, because a CSS property is not what moves under a cursor. Measured 2026-09-09 at 1280 CSS px on a developer machine: seven panels, none changed width, one changed height by 172 px. **A second case watches the chrome above the panels**, which nothing watched before: the title, the strip, the band, the window control, the carry line and the glance grid, each against its own former box. The set is cut at the first panel's own top rather than at the fold, and that correction is the second half of the same measurement. The fold-based form asked which blocks sat inside the first 900 px; the first panel begins at 894, so it was really asking how tall the runner's fonts were, and on `ubuntu-latest` the set came back empty and took `main` red. A cut made at the panel holds at any viewport and on any machine. Each block is compared on its own rather than the panel's top being compared to itself, because a top says only that the total height above it held - a block that grew by the amount its neighbour shrank would pass, and the failure would name no block. This one names it: a 24 px line injected into the chrome fails with the two blocks below it listed by name, and the box each held before and after.
- **An empty plot draws its axis frame and its tick marks and no numbers.** A tick label needs a value and there is no value, so a number printed there would be invented. Both come out of the same `frame` and the same margins the real charts use, so the frame a reader watches is the frame they get - and the box carries no tint of its own, so the axis sits on the same ground the real charts' axes do. Measured over the committed token values: `--chart-axis` reads 3.2:1 in dark and 2.58:1 in light on a panel, against 2.76:1 and 2.38:1 on a tinted box. The waiting frame is exactly as legible as the chart it stands in for, neither louder nor quieter.
- **A skeleton mark takes `--color-rule-strong`, and that was measured rather than picked.** The sunken surface reads 1.06:1 in dark and 1.13:1 in light on a panel - a block nobody can see is not a block, and in light it was gone until the sweep crossed it. Rule-strong reads 1.61:1 and 1.48:1: plainly there, and still well under the weight of a drawn mark, which is what a placeholder owes.
- **Every skeleton on the surface is on one timeline.** The sweep is switched on by a single attribute on an ancestor, so every block starts its animation in the same frame. Out of phase, a dozen sweeping boxes read as a dozen broken things rather than as one page waiting.
- **The sweep starts late.** `console.shimmer_after_ms` is how long a wait has to outlast before it is worth drawing as one, so a fetch that lands first never animates at all. **It ships at 400 as a declared estimate and not a measurement** - see the design rationale below.
- **Only a failure takes a hue.** A quiet window and a real gap are normal, and a page that tints normal things like faults teaches its operator to stop reading the tint.

**And a retry names its own subject.** `Try again` is shorter and it is what the shape asks for, but a button read out of the sentence above it then names nothing. `Try August 2026 again` is three words longer and true on its own. It re-fetches only the months that failed: a retry that re-fetched the whole window would spend an operator's connection on months already in hand, and would blank panels that are answering correctly.

Authority: Susan and Fowler, plan row #12.

## A run's time is drawn one bar an item, on a real clock

> **The shape of the run is legible before a single number is.** A wide staircase is a run that queued; a solid block is a run that worked in parallel.

The run timeline on `/console/` draws
[`run-timeline/<YYYY-MM>.csv`](../architecture/publishing/run-timeline.md). The
shape it reads was settled first and left every drawing question open; those
questions are settled here, because a drawing is not a contract.

- **A row is one item and the y axis is items, in start order.** Sorted by start
  rather than by cost, because the queue is the thing a reader cannot get
  anywhere else, and this is the only surface on the site that can say WHICH
  article was being read.
- **A shard grain sits on the same switch, out of the same fold.** Item, item
  grouped by the shard that ran it, and one bar a shard - three states of one
  control, built by one call over one set of rows. A second panel drew the shard
  grain from `state/span-rollup/` until 2026-09-20, and two folds over two
  ledgers could name different runs as the newest. A shard's bar runs from its
  first item's start to its last item's end, which is the stretch it held a
  worker for, and its steps are that shard's items added up - so the same seconds
  are drawn at either grain and the switch cannot put two answers to one question
  on the page.
- **The x axis is elapsed milliseconds from the run's start, and the wait is
  position rather than length.** An item that queued forty seconds sits forty
  seconds to the right; nothing is drawn in front of its bar. A category axis -
  one evenly spaced column an item - would hide the queue entirely, which is the
  one thing the panel exists to show. The zero is the first item's own start and
  not the manifest's: the process start covers collecting and planning, work no
  item is charged for, so a zero there would push every bar right by one constant
  and make x=0 a moment the chart never draws.
- **Eight steps, eight chart-ramp stops, fixed by position.** `--chart-1` to
  `--chart-8` against the eight steps in pipeline order is an exact fit. A step
  keeps its stop whether or not a given run timed it, so two runs drawn a day
  apart compare by eye. The ramp deliberately holds none of the confidence hues
  ([design-system.md](design-system.md)), so no step of a pipeline is ever told by
  its colour that it is the failing one.
- **Which steps appear in the legend comes from the rows, never from a list in
  the panel.** A step with a number on at least one bar is drawn; a step with none
  is named in words underneath, and the two silences are separated: `plan` and
  `publish` are timed by nothing in the pipeline at all, and any other absence is
  a gap in what THIS run wrote down. An operator acts on only one of those.
- **Hollow is unclaimed, hatched is overclaimed, and both carry a legend key.**
  Neither is tinted - nobody has agreed how much overhead is too much, so a colour
  would publish an alarm that does not exist. The keys are there because the
  owner could not name the hatched notch on sight, which is the test a mark has
  to pass: a texture nobody can read is a texture that says nothing.
- **The residual is signed, and the sign changes the drawing rather than the
  colour.** Positive, it is a hollow slice extending the bar to the item's full
  clock, and the steps plus that slice are the item's own time exactly. Negative,
  the steps have already outrun the clock - the visual plan is decoded inside the
  summary call, so it is apportioned out of it rather than timed beside it - and
  the overrun is drawn as a **hatched hollow notch laid over the last stretch of
  the bar**, starting where the item really ended. Laid over and not appended,
  because the stretch it covers is time some step has already drawn once; an
  appended notch would make the bar longer than either reading of it. Hatched and
  not tinted, so an overrun and an overhead are told apart by texture rather than
  by a hue that would rank one of them as worse.
- **A bar names its shard, in a gutter, always.** Two bars overlapping on the
  clock is correct exactly when they sit on different shards, and without the
  shard beside them a reader cannot tell an overlap from a contradiction.
- **Under 24 bars each carries its item id; above that the gutter keeps the
  shard alone.** Density is the service here: a run of four hundred items is a
  wall of thin bars on purpose, because the wall IS the answer, and four hundred
  labels would be four hundred things to read instead.
- **`console.timeline_bars` caps the drawing and never the arithmetic.** Every
  figure above the bars - the span, the work, the items at once - counts the whole
  run, and the panel says how many of how many it drew. A panel that reported the
  run it drew rather than the run that ran would be a quieter kind of wrong.
- **Three figures land before any bar**: what the run took end to end, what its
  items cost added up, and the second divided by the first. That third number is
  the one that says staircase or block - one means a queue however many shards
  were running, and four means four shards genuinely busy together.
- **The four sub-steps are printed figures and never bands.** `robots`, `tag`,
  `render_prompt` and `parse_reply` nest inside steps the bars already draw, and
  together they come to far under one pixel of the track, so they sit under the
  bars as figures with the step each runs inside. A reader who takes `tag read`
  for a step beside taking the article out adds it twice, which is why the place
  it runs is printed next to it rather than left to be guessed.

**A column the panel reads has to carry a value somewhere on the canary day, or
the panel does not ship.**
[../../frontend/tests/console-pipeline-timeline.spec.ts](../../frontend/tests/console-pipeline-timeline.spec.ts)
takes the declared list off `run-timeline.ts`, reads `backend/var/canary/`, and
fails on any column empty across every row - then checks on the page that every
step in the legend has a slice behind it and that all eight are accounted for as
drawn, unproduced or unrecorded. The same file holds the grain oracle: it reads
the two arrays off the page and holds the shard grain against the item grain,
per shard and per step. The canary is the right fixture because it is
fixed in size (`CLAUDE.md` Guardrail #12) and because it is built, so it carries
a case the archive has never produced: not one committed census row records an
item clock, so nothing but a built day can place an item on one.

**Three panels would fail that gate today** and are left for a later row. Measured
2026-09-16 over the canary's own published payloads, by counting non-empty cells
per column across every row of each file: the one `day-metrics` record the canary
holds carries `extraction` null, `throughput` null and `stage_timing` empty, so
the extraction census, the throughput figures and the stage-timing panel each
fall back to a "nothing was measured" sentence on the fixture the browser suite
runs against. Two more columns are empty on every canary row without a panel
behind them - `day-metrics.addresses_considered` and
`machine.cgroup_peak_bytes` - which is a different defect and a cheaper one. The
`run-days` and `span-rollup` payloads are clean.

Authority: Susan, 2026-09-16. The grain switch, the move to `/console/` and the
printed sub-steps: Susan, 2026-09-20.

## The holdout margin is drawn at the scale of the margin, not of the score

`The pairs a person marked apart` on `/console/judgement/` answers one question:
would tonight's merge line fold together two articles a labeller read as two
different stories? **The comparison it draws, written as a sentence: how far the
closest marked-apart pair sits from the line, against how far the line may fall
in one day.** That is a question about a distance, and the distance is **0.0007**
as of 2026-09-19 while the scores it sits between run from 0.73 to 0.99. A panel
that draws the population cannot draw the distance.

**So the axis is the line and one day's legal fall, never the band.** It runs
from two days' fall below the line to one day's fall above it - one fall cap
either side of `floor_min`, both off `config/idhazh.json`, so the window is the
same width every day and two days of this panel compare. The cap is not a score
in the config: it is `max_down_bins` slots of `bin_width`, and the contract
derives the score from them, so the panel multiplies the same two numbers.
Measured on the built page at 1440: the margin drew at **5.8 px of a 1033 px
plot** on the 0.88 to 1.00 band, and **24 px** on this one. At 5.8 px a dot 13 px
across sits on top of the rule it is measured against, so a reader cannot see
which side of the line the closest call is on - which is the whole of what the
panel is for. The test gates on the 14 px a dot needs, not on the 24, because
the reading moves whenever the fall cap does.

**It reaches two days down because the sentence counts two days.** At the
committed cap of 0.010 one day's legal fall already moves the count on the wrong
side from 1 to all 4, and the day after adds none. The axis still draws both,
because the headline names the day after and an axis stopping at one day would
print a count for a line it had not drawn.

**The zone goes down and only down.** The clamp caps both directions, but only a
fall folds a pair the line refuses today - a rise folds fewer. A corridor drawn
either side of the line would tint scores tomorrow cannot reach. The tint says:
every mark in here is a pair tomorrow could fold.

**The rule stays neutral and the panel takes the tone.** A line is a setting, so
drawing it red would report a fault every day of its life. The panel is what
changes hue - `bad` where a mark is already on the wrong side, `warn` where one
day's fall would put one there - because the fault is the reading, not the
setting.

**Both costs of the line are drawn, not one.** The pairs marked as two stories
are dots; the pairs marked as one story are a range strip on the same axis, the
shape `What the judge said about the line` already ships two of. 117 of the 196
one-story marks score below the line, and each of those is a story the reader
sees twice. Only their scores reach the document - 1.7 KB against 88 KB for the
same rows carrying their addresses and headlines, which the strip does not draw.
**They are carried at six decimal places and that is load-bearing**: the count is
a comparison against the line, two of the 196 sit between 0.93995 and 0.94, and
at four places they round onto the line and the panel prints 115.

**This panel is not a time series, and the owner's picture ships on the chart
above it.** Four marks spanning 0.0064 on a 0.12-tall axis is 10 px of a 190 px
plot, and four rules inside 10 px is one grey smear. `Where the merge line sits`
already has days on one axis and score on the other, so the same marks are a
tinted strip across that plot: the applied line walking down into the strip is
the crossing, in the picture that can show it happening. Two drawings, two
halves of one question - this one has the distance and no date, that one has the
date and no distance.

**What the reader loses.** A mark far below the line is off this scale, so it is
counted at the edge with its score printed in words rather than drawn. That is
the safe end of the axis and never the breach - a mark above the line always
falls inside the window - but it means a reader cannot see the spread of the
misses from the picture. The shut table under the panel carries every marked
pair at zero attention cost, which is where that spread is.

**This is the fifth case in [the thirteen chart
rules](#thirteen-rules-hold-for-every-chart-on-this-console), and the only one
that narrows a domain.** It is allowed here because the breach side stays inside
the window; a fixed axis that clipped the breach is what the first case already
refuses. Authority: owner, 2026-09-19, after a design review failed the panel on
all five sufficiency checks in [design-system.md](design-system.md).

## Design rationale

**The thirteen chart rules landed in one commit, before any panel was redrawn.**
The rejected alternative was to let each panel row make its own call as it came
to it. Nine rows re-arguing the axis, the stacking order and the switch produce
nine answers, and a reader who moves between two panels cannot learn nine - which
is the defect the rules exist to remove, arriving by the door that was meant to
avoid the argument. The cost of settling first is that every panel row now waits
on one doc row. It was paid once. Landing a panel in the same commit was refused
for a different reason: doctrine plus a panel cannot be reverted without
reverting the panel, and the doctrine is the half more likely to need editing.
Susan, 2026-09-17.

**`console.shimmer_after_ms` ships at 400 and 400 is a declared estimate, not a
measurement.** Guardrail #10 refuses an unmeasured number the right to justify a
design, so this one justifies nothing: nothing about the shape of the console
depends on it, and the knob decides only whether a wait short enough to be over
already gets animated on its way past. The console started fetching its months
on 2026-09-09, so no median payload arrival exists yet to derive it from. The
shell-and-fetch migration was meant to take that measurement and could not:
the number is a reader's wait, and a reader-facing timing measurement was
ruled out of that plan's scope (owner, 2026-09-08). What would settle it is
in [../reference/pipeline-cost.md](../reference/pipeline-cost.md). Taking it inside the user-interface row was refused: a
user-interface row is not a measurement harness, and a number measured on a
laptop's loopback would be the wrong number twice over. Fowler, 2026-09-08.

**`console.fleet_min_rows` ships at 160 and 160 is a declared estimate, not a
measurement.** The share behind it is measured: the rarest of six machine kinds
held 11 of 356 committed counter rows, 3.1 percent. The row count is not.
`console.min_attempts_for_rate` already sets five placements as the floor under
a rate, and five at 3.1 percent needs about 162 rows, so 160 is that arithmetic
rounded. It justifies nothing about the shape of the page: above the gate the
counts are bars, below it the same counts are a list, and both say the same
thing. What would settle it is a seventh machine kind arriving - every share
drops, the rarest gets rarer and the bar rises - so the number is re-derived
from the committed rows rather than argued with. Susan, 2026-09-17.

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

**A panel belongs to the question it answers, not to the route it was written
on.** Four panels left `/console/` for `/console/voices/` on 2026-09-14 - the
census, the ranking weight, the failure list and what the truncation cap cost
each source - and Pipelines kept none of them. Two of the four draw a chart, so
the route they left behind lost two charts and the route they arrived on gained
its first. The rule the move was decided on is the one this page already applies
to a figure: it goes where a reader would look for it. An operator asking which
feed is broken should not have to know that half the answer is filed under "did
the runs work". Leaving copies on both routes was refused for the reason a
second derivation is always refused here - two surfaces answering one question
disagree the moment one of them is edited, and nothing on either page says which
to believe. Placement plan row #13, decision 2; authority Editor.

**A window control governs the surfaces that declare they follow it, and every
surface that does not says so in type.** Voices had no control until the panels
arrived and its own panel had argued against one: the ranking weight was reduced
over `collect.reliability_window_days` when the run happened, so a control that
redrew it would print a number no run applied. Two of the four arriving panels
declare a day count, so the control came with them. What resolves the collision
is the pattern already on Pipelines rather than a new one - three paragraphs on
Voices carry `data-window-exempt` and each says in the reader's words which span
it is over. Unwinding the two panels' windowing was the alternative; it was
refused because the window is what makes "which source is the cap costing us
most, lately" answerable, and removing a question to protect a sentence is the
wrong trade.

## See also

- [design-system.md](design-system.md) - the tokens, ramps, motion set and sufficiency gate this page draws on.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - what each console panel is, and where its data comes from.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - the published projection and the grain of every figure.
- [config.md](config.md) - the knobs these rules read.
- [../reference/pipeline-cost.md](../reference/pipeline-cost.md) - the instrument log the console never quotes from.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0b (voice) and Guardrail #10 (every number carries its conditions).
