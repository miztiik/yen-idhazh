# What the quality and source panels draw

**Last Updated**: 2026-09-23

The panels that report what the model wrote and how the sources behaved: the
eleven measures on `/console/model/`, the two distributions under them, the
model-swap comparison, and the two panels on `/console/voices/` that watch a
source counting down or losing articles to the truncation cap.

The chart rules these obey are
[the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md).
What each panel is and where its data comes from is
[../../architecture/publishing/console.md](../../architecture/publishing/console.md).

**Quality is a table, never a line.** A line invites a trend across days whose
articles have nothing in common. The one thing on these routes that draws a
spread is the compression chart, because a spread is a property of a day's
article mix and a single number cannot carry it.

## Eleven measures are eleven cards, and the rows are one control away

Eleven columns of one table cannot answer the question an operator brings to it.
**Did it get worse is a vertical scan**, and in a wide table every column beside
the one being scanned is a different quantity - a count, a percent, a second, a
minute. At a thirty-day window that is 330 numbers under eleven header
paragraphs.

So the section leads with eleven cards on one `auto-fit minmax(220px, 1fr)`
grid, and each carries the same six things: **the label verbatim** - the copy is
protected and `frontend/tests/console-model.spec.ts` compares the rendered
labels byte for byte against the page's own `COLUMNS`, so a paraphrase fails the
build rather than a review; **the newest day's figure**, with which day printed
once above the grid rather than eleven times; **a line over the window**, drawn
as markup by `Sparkline`, because eleven engine-backed sparklines would be eleven
chart instances on a page that renders complete without one; **the change across
that line**, painted from the measure's own declared polarity; **what it is out
of**, for the six quality figures, because a card has no row to put the
denominator one column away; and **its sentence**, in the body where there is
room.

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

Two of those carry a rule the others do not. **The share divides by the rows its
own flag answers for**, never by the day: `truncation_flagged` changed meaning on
2026-08-28, so a day holding rows from both sides of that stamp would otherwise
report a fact about the migration wearing a percent sign. And **`Time to write
one` carries a second figure only where the day cut something** - a dash under
every other day would be a column of absences pretending to be a split.

**`Too long to send` is expected to read zero, and that is the point of it.** At
the committed truncation cap no prompt can reach the window the machine reads
with, so the count is zero by arithmetic rather than by luck. It is on the page
so that the day the cap moves, the number that says the move went too far is
already being printed. The longest single-call prompt the committed cap can
produce sizes at 40,622 tokens, 50 percent of the 81,920 window
([../../reference/pipeline-cost.md](../../reference/pipeline-cost.md)). **What
that window is held open for is the two-call pair, which this counter does not
read** - it sizes at 71,239 tokens
([../../architecture/summarize/prompt.md](../../architecture/summarize/prompt.md)),
and the pair has an assertion of its own.

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
either way and the section works with no script at all. The rows follow the
window control above them and the line that opens them names the span, because a
table that ignored the preset above it was two windows on one page. Shut, it
drops its border, background and shadow: closed it holds one line of link text,
and a card around a footnote is what made it read as something hanging off the
bottom of the page.

## A distribution answers what a median refuses to

`What one summary cost` is a log-binned histogram of the time to write one
summary, with a cumulative curve on a second axis and a rule at the median and
at the 95th, each printing its own value.

A median answers "how long does one take" and refuses "how bad does it get".
Measured 2026-08-31 over the 3,500 timed summaries in `state/item-health/`, those
are different questions by a factor of 2.5: the median is **122 s** and the 95th
is **300 s**, with a slowest of 702 s. The second figure is the one that decides
whether a shard fits `run.shard_timeout_minutes`, and no single number on the
page was carrying it.

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

**`score_ms` lives under the same heading, as two figures and no chart.** The
scorer reads a summary the model has already finished, so it is not a fourth
thing the run is held up by and must not be drawn as a fourth line on a
stage-timing chart. Measured 2026-08-31 over the 3,534 timed rows of
`state/scores.csv`, the middle is **2,463 ms** and the slowest one in twenty is
**14,491 ms** - printed as 2 s and 14 s, because the console prints no decimal.
Ten committed rows carry the zero the column defaulted to before it was written,
and they are counted as untimed rather than as instant.

## Compression is three marks a run, and the band prints its bounds

`How long the summaries came out` draws one column per run: the shortest summary
it wrote, the middle one and the longest.

**A mark per summary cannot be drawn, and the block is the reason.** Thousands of
marks in one colour render their dense middle as a solid area, so the only marks
anybody acts on - a summary of three words, or one at twice the length that was
asked for - are the ones the block hides. Three marks a run keep both ends and
lose the block.

**Per run and never per day.** A day holds up to five runs, and a run is one
model reading one set of articles under one set of settings, so it is the
smallest thing on this page that a change can be attributed to.

**The band's bounds print as numbers beside the chart.** A shaded region nobody
can read a bound off is a decoration, and this one is a setting somebody chose.
The band drawn behind each column is what that run's own articles were asked
for, read through each article's own length rather than off `summarize.bands`
directly - an article's length picks its band, so a run of short pieces is asked
for less than a run of long ones.

## A swap comparison carries direction in the arrow, and a verdict only where the measure has one

`What the model change moved` is seven paired dot rows. Each measure is drawn
against its own value on the older model, so no change is 100 percent on every
row - the only axis a median in seconds, a length in words and a count in a
hundred summaries can share.

- **The arrowhead carries the direction; the hue carries the verdict where there
 is one.** A red-for-worse ramp needs somebody to agree which way is worse for
 each of the seven. Five say so themselves, through the polarity declared on the
 measure rather than chosen by the chart; the two with no agreed direction stay
 grey and name themselves under the plot. A hue here is never a guess.
- **The axis is symmetric about no change**, so a fifth off and a fifth on draw
 the same track length. An axis running 78 to 120 would draw one as the bigger
 move.
- **Both absolute values print on the row label**, because a ratio with no
 magnitude behind it can be a rounding error wearing a percentage.
- **Both article counts print above the chart, and the panel refuses to draw at
 all where either side holds fewer than `console.min_attempts_for_rate`
 summaries.** Two models over two article sets is two measurements, not a
 trend.

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

## A countdown is drawn as an area, never as a fraction in a chip

`Sources close to retiring themselves` is one row per source on
`/console/voices/`: the name, a target bar of the trailing share against the
alarm point, and a square a day beneath it.

It exists for one decision: **is this source recovering, or is it counting
down?** A total cannot answer that. `41%` over thirty days and `41%` on the
fourteenth day of an unbroken run are the same number and two completely
different situations, so the panel adds a time axis and reads the run length off
it.

- **The dwell is the area.** A 2px rule in `--fill-low` sits under exactly the
 contiguous under-the-mark squares at the newest end. A `9/14` chip with no
 marked run asks the operator to trust a count they cannot check against the
 picture beside it.
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

## What the truncation cap cost, by source

`Sources cut short most often` is one row per source, ten of them, and it is the
only place on the site that names a source next to a number about that source.
It exists for one decision: **whether raising the truncation cap would actually
reach a source's articles.** It is a horizontal range plot on a log word-length
axis - a track from the source's shortest article to its longest, a dot at the
middle one, and a dashed rule at each cut point across every row. Everything
right of the widest rule is where the cap bites. The geometry, the margins and
the four other places the console reports the cap are in
[../../architecture/publishing/console-truncation.md](../../architecture/publishing/console-truncation.md).

- **The cap is on the chart.** This is the whole defect the plot fixes. Five
 columns of numbers were unreadable because the one number every column had to
 be compared against appeared nowhere in the section.
- **The rule comes off the rows, never off `extract.truncation_cap_tokens`.** A
 window can hold rows a run wrote under an older cap, and the setting is one
 number: a thirty-day window holds cuts at 1,923 words and at 3,846, and the
 file says only 3,846. A rule from the file also draws in a window where
 nothing was cut.
- **It sorts by count, never by rate.** Measured over the committed ledger the
 shares run 3 to 67 percent on denominators of 6 to 38 articles, so a rate sort
 puts a source with 4 cuts of 6 above one with 17 of 38 - and it is the
 seventeen that cost the digest its articles. `Share cut` is not a column for
 the same reason it is not the sort key; what a reader loses is the share as a
 number, and both counts are still on the row.
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
the track and the row takes one more line of type.

## Design rationale

**A panel belongs to the question it answers, not to the route it was written
on.** Four panels left `/console/` for `/console/voices/` - the census, the
ranking weight, the failure list and what the truncation cap cost each source -
and Pipelines kept none of them. Two of the four draw a chart, so the route they
left behind lost two charts and the route they arrived on gained its first. The
rule the move was decided on is the one this page already applies to a figure: it
goes where a reader would look for it. An operator asking which feed is broken
should not have to know that half the answer is filed under "did the runs work".
Leaving copies on both routes was refused for the reason a second derivation is
always refused here - two surfaces answering one question disagree the moment one
of them is edited, and nothing on either page says which to believe.

**A window control governs the surfaces that declare they follow it, and every
surface that does not says so in type.** Voices had no control until those panels
arrived and its own panel had argued against one: the ranking weight is reduced
over `collect.reliability_window_days` when the run happened, so a control that
redrew it would print a number no run applied. Two of the four arriving panels
declare a day count, so the control came with them. Three paragraphs on Voices
carry `data-window-exempt` and each says in the reader's words which span it is
over. Unwinding the two panels' windowing was the alternative; it was refused
because the window is what makes "which source is the cap costing us most,
lately" answerable, and removing a question to protect a sentence is the wrong
trade.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| The cut share on the run-health strip | A 16px square has no room for a number, and it answers "did it work" rather than "what did it read". |
| A histogram of article lengths | It answers what the corpus looks like. The panel exists to answer whether raising the cap would reach a source. |
| A linear length axis on the cut-short plot | The lengths span more than two decades, and linear crushes every short source onto the left edge. |
| Keeping the table and printing the cap in the intro sentence | It answers "how far past the cap" by subtraction rather than by looking. |
| A gauge, dial, donut or progress bar | Six percent on a dial is one pixel of arc. |
| A before-and-after of a cap change | Two caps over two article sets is two measurements, not a trend. |

## See also

- [../console-design.md](../console-design.md) - what a figure may say, and in what words.
- [the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md) - the thirteen rules these panels obey.
- [the-mark-shapes-a-panel-may-reach-for.md](the-mark-shapes-a-panel-may-reach-for.md) - the named shapes and the panel-level switches.
- [../../architecture/publishing/console.md](../../architecture/publishing/console.md) - what each panel is, and where its data comes from.
- [../../architecture/publishing/telemetry-series.md](../../architecture/publishing/telemetry-series.md) - the grain every figure was measured at.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - the instrument log the console never quotes from.
