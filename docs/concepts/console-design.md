# Console Design

**Last Updated**: 2026-10-07

How a figure on the operator console is worded, coloured, ranked and drawn. This
page rules the words and the states; four pages under it rule the drawing. It is
the operator half of [design-system.md](design-system.md), which keeps the
vocabulary the whole site resolves - the tokens, the colour ramps, the motion set
and the sufficiency gate. This page adds no token and defines no colour; it says
what the console may do with them.

| Page | The question it answers |
| --- | --- |
| this page | What may a number on the console claim, and in what words? |
| [console-design/the-rules-every-console-chart-obeys.md](console-design/the-rules-every-console-chart-obeys.md) | What holds for every chart here - the domain, the stacking order, the legend, the readout strip, the ranked list, the date axis? |
| [console-design/the-mark-shapes-a-panel-may-reach-for.md](console-design/the-mark-shapes-a-panel-may-reach-for.md) | Which shape does this reading want, and what can that shape not say? |
| [console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md](console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) | How is the machine a run drew reported, and why is no rate pooled across two of them? |
| [console-design/what-the-quality-and-source-panels-draw.md](console-design/what-the-quality-and-source-panels-draw.md) | How are the model's own figures and the sources' health drawn? |
| [console-design/how-a-console-chart-gets-its-data.md](console-design/how-a-console-chart-gets-its-data.md) | Where do a panel's bytes come from, and what may it never do to get them? |
| [console-design/how-the-data-explorer-shares-the-window.md](console-design/how-the-data-explorer-shares-the-window.md) | How do the Data explorer's regions share the window, and what holds still while you use them? |

Three other pages meet here and do not overlap.
[../architecture/publishing/console.md](../architecture/publishing/console.md)
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

**A fixed benchmark figure never appears on the console.** It was taken on
another machine against another workload, so a gap between it and a run reads as
a regression nobody measured. Those numbers stay in
[../reference/pipeline-cost.md](../reference/pipeline-cost.md).

## The empty state is the panel, not a replacement for it

A panel that vanishes when it has nothing teaches the operator that the
measurement does not exist. The heading and the explanatory sentence stay; only
the figure changes.

This is the normal case rather than the exception. Measured 2026-08-31 on the
committed tree: `job_seconds` and `cpu_model` are empty on **24 of 54** counter
rows, the three host cells on **34 of 54**, and the counters ledger starts five
days after the eval ledger - so five days inside a thirty-day window have
scores and no server figures at all. A console that only designed the loaded
state would be mostly undesigned.

Seven states have fixed wording, held in
[../../frontend/src/lib/console/recording.ts](../../frontend/src/lib/console/recording.ts):
measurement off, sampled below 1.0, days the machine was timed and nothing
scored the summaries, days the server's own counters were not written down,
recording started mid-window, a day that published and lost what it
measured, and a chart that cannot show a setup change because the score record
did not read. Only the dates and counts inside them are computed, and every one
is derived from the ledger that is missing - **a date that is not true is worse
than no date**. None is apologetic, none is styled as an error, and none is a
banner across the page: three panels can be in three different states on one
day. On Hardware and Summaries the first six sit after the record notes and
before the first section, in one order - off, sampled, started, then the days
one instrument covered alone - so a page whose sections have nothing to draw
still says what the recording was doing; Jony chose the place on 2026-10-07.
The seventh sits on the two charts it is about. Susan chose the words of the
first five on 2026-08-30. On 2026-10-07 Reader and Jony chose new words for the
measurement-off line and for the two lines about days one instrument covered
alone, and Reader for the started line. Later that day Reader and Jony chose the
words that open the started line and the words of the seventh, and Jony its
place.

**A panel keeps its own line for a nothing the route's note also states.** It
says it in the note's words and never points at the note. On Hardware the
platform-mix panel says `The machine record is not packed yet.` when that record
has no packed day, which the route's note says too: the note sits several panels
above, and is not always on the page when the box is empty. Jony chose to keep
the panel's own line, and Reader chose its words, on 2026-10-07.

Two of them are worth reading twice. **A sampled figure is never scaled up** -
multiplying a quarter-sample by four publishes an estimate as a measurement,
which Guardrail #10 forbids. And **no string names a config key as if it were a
word**: it is `Measurement is off`, never `host_fingerprint is false`, because a
term from a subsystem is not a term for a user (section 0b).

**The measurement-off line names only a day the open window shows.** It is
worded once for each window the control offers. A window that holds a recorded
day names the newest one. A window that holds none says so, and names the
narrowest offered window that reaches back to the last recorded day, or says
that no window here does. It says nothing has been recorded at all only of a
record whose index names no row, in every window. Where the page has not read
what would make a claim true - a record not packed or not loaded, a window that
holds no packed day - it says only that measurement is off and how to turn it on.

**On Hardware, a run has the server's figures only where a shard reported one
of the two cells the server itself wrote** - the prompt tokens it read and the
seconds it spent reading them. A run is formed from the machine record or the
article record, so a run of article rows alone, or of a machine record that
holds the probe and the clocks and neither cell, has none. The page's first line
counts every run in the window, then how many of them have the server's
figures: `127 runs in these 30 days, 75 of them with figures from the model
server itself.` The started line, the line about days the server's counters
were not written down and the measurement-off line read the same runs. Nothing
samples those counters - the sampling rate is the scorer's, and only the
machine record's own switch turns them off - so Hardware prints no sampled line
about them. Reader chose the first line's words, and Jony agreed, on 2026-10-07;
Fowler ruled which runs count.

**The started line names only a start the open window shows, and only a true
one.** It opens on what started - `Server figures started on 20 Sep 2026.`,
`The machine record started on 17 Sep 2026.` - so two started lines with two
dates on one page read as two instruments, never as one fact with two answers.
It is worked out once for each window the control offers, from the whole
read. The instrument's first day is the first day it ran in what the route read -
a day it recorded, or a day whose record was lost - and that is its true first
day only when the read reaches back to the oldest named day of every record it
draws on (the server's counters live in the machine record alone). A
record whose indexes name a day before the read may hold a day the instrument
ran before anything the read holds, so the instrument gets no started line, and
no day before the read is opened to learn it. The line prints in each window
that shows the instrument's first day, names it, and counts the days of the
window before it that had a run. An instrument whose rows begin after its record
did - the machine identity in the machine record - is named on its own first
day. Once a record's first month is packed into one file, its indexes know the
month and not the day, so when the widest window starts inside that month, after
its 1st, no window prints a started line: no line rather than a false date.

**The line about days one instrument covered alone names only days the other
could have answered, and each day once.** On both routes the article record is
the instrument that answered: on Summaries the scorer's figures are missing, on
Hardware the server's own counters. The line is worked out once for each window
the control offers. A day the missing record holds or recorded lost is a day it
answered, and a lost day has a record note of its own. A day after that record's
newest packed day is not packed yet, and a record that did not read answers
nothing, so neither gets the line. The started line speaks for the days before
the instrument began, and while measurement is off the off line speaks for the
days after the newest one recorded, so this line names only the gaps between.
It names the days and never counts them - `There are no quality figures for
1 Oct and 3 Oct 2026.` - and where every day on screen is one of them it uses
the window's own words, `these 7 days` or `this one day`. Hardware's line claims
no score: it says only where its speed figures came from. While the sampled line
prints, this line does not: below a rate of 1.0 most days have no row of the
sampled instrument on purpose, and naming them would call the sample a gap.

**A chart that cannot show a setup change says so, and never that nothing
changed.** On Hardware two charts mark the days the pipeline that writes the
summaries changed. A day's marker comes from the run record, which names what
each run ran, and for the days before it did, from the score record's rows,
which carry no digest after that. So when the score record has not been packed
yet or did not load, a chart loses a marker only on a day the window shows that
had a run, that no run record names, and that comes before the run record first
named what ran: a later day that published nothing has no marker with the read
or without it. Those two charts then say, after the sentence about the dashed
rule,
which days, why - in the record notes' own words for each fault - and that the
chart shows every change on the other days: `This chart cannot show whether the
setup changed on 8 Sep to 12 Sep 2026, because the score record has not been
packed yet. That is a step not yet run. This chart shows every change on the
other days.` Where the chart drew no rule, the line replaces `Nothing changed
about how the summaries are written inside these 30 days.`, which would claim
days the page cannot see. Reader chose the words, and Jony the place, on
2026-10-07.

## A record that had not begun, a quiet day, and a record that was destroyed

They are three states and they send an operator to three different places, so
they may not share a sentence. A day with no file at all is the first. A day
whose file is empty and that published nothing is the second. A day that
published articles while its record kept no row is the third: **what it measured
is gone**, and that is a different errand from an instrument that had not started
yet.

**The derivation is one join and it carries no judgement.** The digest for that
date carries articles, so a run worked; the record opened a day file and kept no
row, so what it measured is gone. Hardware printed for a day before the record
shipped gets the sentence that the flags and the cache **start on the day the
machine record ran** - without the third state, the one day the console existed
to report reads as the one day nothing had happened yet.

**A day proved lost is never counted as a day before the recording started.**
Counted in that gap it would date the instrument's own start to the day AFTER
the loss and hand that date back as the reason for it.

**The states are named in `data-` attributes, not only in the sentences.** A
page whose state can be read only off its prose can be checked only by looking
for a sentence, and an assertion that a sentence is absent passes as happily
when somebody renamed it as when the defect was fixed. `data-machine-record`
carries one of `recorded`, `off`, `lost` and `none` on every build.

## A figure in currency prints its rate, its source and the word for what it is

There is exactly one money figure on this site: the counterfactual cost on
`/console/machine/`. CLAUDE.md Guardrail #10 forbids the rest, and carries the
owner's carve-out for that one, 2026-08-30, on conditions this section holds:

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

## Data explorer prints the engine answer as written

The Data explorer page is the exception to the console rule that translates ledger columns into prose. Its table prints column names, decimals, nulls and dates exactly as the engine returned them, because the operator writes the question and types those names back into the next one. Cells still render as text, never as links, images or HTML.

**The page reads a column's type one way.** One function, `classifyType()` in `frontend/src/lib/console/explorer/type-family.ts`, puts the type name the engine prints into one family: a whole number, a decimal, a date, a timestamp, a time, an interval, true/false, text, bytes, a list or a struct, or other. A timestamp is any precision, `timestamp_s`, `timestamp_ms` and `timestamp_ns` included, with or without a time zone. Text includes `uuid` and `enum`, and bytes is a `blob`. A list or a struct is that whatever it holds, because `timestamp[]` is a list rather than a time, and a name no rule knows, such as `bit`, is other. The engine prints an alias by its own name, `INT` as `INTEGER`, so no alias is listed. The table prints and sorts a cell by its column's family, the chart chooses its shape from the answer's families ([the mark shapes](console-design/the-mark-shapes-a-panel-may-reach-for.md#when-nobody-wrote-the-panel-the-columns-choose-the-shape)), and the type label takes its family's colour (below).

A whole number groups its digits from five digits up, so `2026` stays `2026`, and one longer than fifteen digits prints its exact digits. A decimal prints at most three places, and a non-zero one under 0.001 in e-notation. A date prints as the engine prints it, `2026-10-02`, with every digit of a year past 9999 and ` (BC)` after a year before 1, and a timestamp as `2026-10-02 08:24:32`, with milliseconds only when they are not zero. True/false prints `true` or `false`, a blob prints its size as `{n} bytes`, and a list or a struct prints its JSON text in the data font. Anything else prints the engine's text, and a NULL prints `null`. Numbers stand right-aligned. The first press on a column's name sorts a number or a day high to low and anything else A to Z, with NULLs last both ways. In a number column `inf` sorts above every number and `-inf` below every number, and `nan` and `-nan` name no number, so they sort with the NULLs. A day sorts by the UTC instant that its text names, to the nanosecond, whatever the browser's time zone is. A timestamp with no zone is UTC, and a timestamp with a zone moves to UTC by the offset that it prints. Text that names no instant, such as `infinity`, sorts with the NULLs. Only a number column draws in-cell bars, so text that holds digits draws none.

## The Data explorer colours a type by its family, and marks a chosen ledger

Every column type the page prints, in the column rail and under each header of the answer table, is in the data font at `--text-xs` and in the colour of its family. Text and numbers wear `--type-text` and `--type-number`, which are the editor's string and number colours, so one kind of value has one colour everywhere on the page. Dates, timestamps, times and intervals wear `--type-time`, and true/false wears `--type-truth`. A list, a struct, a blob and a type no rule knows stay in the tertiary text colour. Whole numbers and decimals share a colour, as `42` and `3.14` do in the editor. The type is always printed in words, so the colour is a second signal and the page has no legend. The family comes from `classifyType()` (above), and `typeColour()` in `frontend/src/lib/console/explorer/type-colour.ts` maps it to a token: the label is painted with exactly that token, and a list of times takes the tertiary colour, because it is a list. In the answer header only the type word takes the colour; the note about the bars after it stays tertiary.

The column rail prints each ledger's name once, as a heading that stays at the top of the list while that ledger's rows scroll, and each row prints only the column's own name. The full `ledger.column` name stays in the row's text for a screen reader and in its `title` for a hover. Rows are ordinary block flow with a 24 px minimum height: a long name or a long type wraps, the row grows, and nothing is cut short. A type that does not fit beside its name moves to its own line at the end of the row.

A chosen ledger's row in the ledger rail has the `--tint-accent` ground, a 3 px `--color-accent` edge at its start, its name at weight 600 and its second line in the secondary text colour. Every row carries the edge, transparent until chosen, so choosing a ledger moves nothing. A ledger that is not on this site is one text colour step quieter, never dimmed with opacity.

## An axis title and a column header take one form

`Article length, words`. **Sentence case, a comma, the unit in lower case, and
no full stop.**

- **The quantity, then the unit.** `Summary length, words` - never `Summary
 length (words)` and never `words`. A bracket reads as a footnote, and a label
 a reader meets before any of the numbers is not a footnote.
- **An axis title may not be a ledger column name.** `source words` is how the
 file spells `source_words_before_cap` and `source_words`. A term from a subsystem is
 not a term for a user (`CLAUDE.md` section 0b), and this is the rule two
 bullets above - no ledger column name on screen - applied to the label rather
 than to the cell.
- **It says what the heading says.** A chart that calls one quantity `Article
 length` in its heading and `source words` on its axis, on one screen, makes a
 reader work out that they are the same thing before they can read the chart.
- **A label that needs no unit is just the noun.** `Runs`, `Failed`, `Cut
 short`. The comma form is for a quantity whose number means nothing without
 the unit, and adding one where none is needed is noise.

Where each figure is read from is in
[../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md).

## A window's days take one of two names, and one day never needs a second

Every windowed sentence takes its day words from one helper,
`frontend/src/lib/console/span-words.ts`, so the 1-day window never prints
`1 days` and one edit moves every sentence. Reader chose the words on
2026-10-07.

- **The days on screen:** `these 7 days`, and `this one day` at one day. A
 sentence or a row label that opens on them is capitalised: `These 7 days`,
 `This one day`.
- **A bare count:** `7 days`, and `1 day` at one day - the days control's own
 words. A count over the window takes it and drops `these`: `on 5 of 7 days`,
 `on 1 of 1 day`.
- **No `the last 7 days`.** Every console window ends on the newest published
 day, which is not always today, so `the last` claims more than the page knows.
- **At one day, a sentence must not need a second day.** No range - one day is
 one date, never `2026-10-06 to 2026-10-06`. No order across days, no waiting for
 a later day, and no worst, middle, median, quietest or loudest day. Such a
 sentence is written whole for one day, in the same tense: `No day in these 7
 days published a summary` is `This one day did not publish a summary`, and
 `one tile a day, over these 7 days` is `one tile for this one day`.
- **The rule holds for a sentence that prints no day count.** A chart's label at
 one day says what it draws for that day - `one point for this one day`,
 `Stories folded into another in this one day` - a legend names one date, and a
 line that waits for a second day is not printed. The strip under a chart heads
 its one column alone and names no keys
 ([console-design/the-rules-every-console-chart-obeys.md](console-design/the-rules-every-console-chart-obeys.md#a-chart-with-a-shared-column-prints-every-series-together-in-a-fixed-strip)).
 Words that say `this one day` name the window, so they print only at the 1-day
 window. Reader ruled the words on 2026-10-07.

A sentence that counts something other than the window's days - runs, a rule's
own span, the days a record read - keeps its own count.

## A section keeps the sentence that decides and loses the sentence that narrates

Every panel writes its own heading, intro, readout and empty state, and many
hands write many voices. One pass reads the whole surface and settles it against
`CLAUDE.md` section 0b.

- **A sentence that names a threshold, a denominator, a cost or an empty-state
 reason is kept.** Several of the console's decision rules are written nowhere
 else.
- **A sentence that says what the chart is, or argues for the shape it took, is
 cut.** The heading already names the subject, and the case against a rejected
 chart type belongs in the rejected-alternatives table on the page that rules
 it.
- **Prose cut from the page goes into the chart's accessible description**, so a
 screen-reader user is never left with less than a sighted one.

Three habits are what that pass catches, and they are the ones to check in any
new section.

- **One name for one span.** Four phrasings for one window, and the same
 instruction written two ways, is what a page reads like when nobody has done
 this pass. The two names a window's days may take are in the section above.
- **One name for one control.** A name taken from a component outlives the
 component: `Failure rate against volume` went on naming a component that no
 longer existed.
- **A number says what it is out of, on the same line.** `prompt reused 51%` is
 a share of prompt tokens, so it reads `prompt tokens reused`. That is the one
 clause of section 0b a reviewer can check mechanically, which is why it
 catches what the others miss.

**Say it once per screen.** A fact stated twice on one screen reads as two
facts - two sections both explaining that they follow the window rather than a
pan, or a date span printed under the heading that already printed it.

## Design rationale

**Two names for a window's days, not one.** One name everywhere was the fewest
words to keep, and it breaks a count: `on 1 of this one day`. The bare count is
the days control's own words, so the second name adds no new kind of words to the
page. A name per sentence was what the console had before, and at the 1-day
window it printed `these 1 days`, `over the last 1 days` and `the 1 days ending
there` from templates of their own on every route. Reader ruled the words on
2026-10-07.

**A line about days one instrument covered alone names its days, and Hardware's
claims no score.** A count was the shorter line, and beside the started line it
reads as a second set of days: `on 2 of 90 days` under `3 days had a run but no
quality figures`. A name says where to look. Hardware could learn which days
were scored from the score record it already reads for its change markers, but
it draws no quality figure, so the claim would buy one clause at the price of
that record's read states, its lost days and a second sentence for a day with
neither. The line says where the speed figures came from, which is what the page
draws. Reader and Jony chose the words and Fowler ruled the score claim out, on
2026-10-07. Hardware's line names a day where no run had the server's own
counters, not where no run was formed: a run of article rows alone has none, and
counted as one that had them it hid the very day the line exists to name. Fowler
ruled that the same day.

**Hardware's first line keeps every run as its count.** Every panel below draws
from all the runs the page read, so the first number is all of them, and the
claim about the server's own counters is the second number, in the same sentence
as the count it is out of. A first line that counted only the runs with those
counters would not say how many runs the panels under it drew. Fowler ruled the
two numbers, and Reader and Jony chose the words, on 2026-10-07.

**A lost change marker is said on the chart that lost it.** Hardware uses the
score record for nothing but the change markers on two charts, which sit in two
groups far below the page's first line, so a note at the top would explain a
gap the reader cannot yet see. Each chart says it where the rule would be. Jony
chose the place on 2026-10-07.

**One classification of a column's type.** The table, the chart and the colours
each read type names with lists of their own, and they disagreed about the same
column: the chart drew no date chart for a `timestamp_ns` and counted a list of
decimals as a number, and the table printed a `hugeint` as text. One function now
decides, and each reader keeps only what it does with a family, so a type the
engine adds is taught to the page once.

**A colour per type family.** The operator writes the next question from the
column rail, and one ledger can list more than a hundred columns. A colour per
family finds the
numbers or the times without reading every type. Text and numbers reuse the
editor's two colours, so the page has one colour for one kind of value. Time and
true/false needed hues of their own: the other palette colours sit too close to
the accent, which is the console's link colour, and the confidence hues carry a
verdict that a type does not. Only four hues fit clear of both, so a list, a
struct and an unknown type stay tertiary; the brackets in `varchar[]` already
mark a list. Every type colour reads at least 4.5:1 on the surface in both
themes, the level normal text needs, and `frontend/tests/tokens.spec.ts`
recomputes it.

**No fixed row height in the column rail.** The rail is a scroll box of fixed
height. While its rows were a grid inside that box, each row stayed at its 24 px
minimum and never grew to its content, because a grid only shares out free
space and a full scroll box has none. A name that wrapped then printed over the
rows below it. Block flow sizes each row to its content.

**One heading per ledger instead of a prefix on every row.** In the 224 px rail
a name gets about 13 characters of the data font a line, and every item-health
column starts with the 12-character `item-health.`. Printed on every row, the
prefix filled each row's first line with the same text; cut with an ellipsis,
the name would lose the end that tells two columns apart. The heading says the
ledger once, and wrapping keeps every character on screen.

**The chosen ledger.** Before this, a chosen ledger differed from the others only
by its checkbox. `--tint-accent` is already the console's chosen ground - a
picked choice tile and a selected ranked row use it - and a 3 px edge, reserved
on every item and coloured on the chosen one, is how the console's route tabs
mark the open tab. `--color-mark` was not used:
it means a word your filter matched, and this rail has a filter. On every tinted
ground the tertiary colour reads under 4.5:1, so a chosen row's second line
steps up to secondary.

**No opacity on an unpublished ledger.** Opacity 0.72 put the second line of an
unpublished ledger at 3.08:1 in dark and 2.90:1 in light, under the 4.5:1 that
normal text needs. One text colour step keeps the row quieter and readable.

## See also

- [design-system.md](design-system.md) - the tokens, ramps, motion set and sufficiency gate this page draws on.
- [console-design/the-rules-every-console-chart-obeys.md](console-design/the-rules-every-console-chart-obeys.md) - the thirteen rules, the ranked list, the date axis and the readout strip.
- [console-design/the-mark-shapes-a-panel-may-reach-for.md](console-design/the-mark-shapes-a-panel-may-reach-for.md) - the named shapes and what each cannot say.
- [console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md](console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) - the Hardware route and the run timeline.
- [console-design/what-the-quality-and-source-panels-draw.md](console-design/what-the-quality-and-source-panels-draw.md) - the model's own figures and the sources' health.
- [console-design/how-a-console-chart-gets-its-data.md](console-design/how-a-console-chart-gets-its-data.md) - the seven rules about a panel's bytes: design for every panel, ask for what you draw, one reader.
- [../architecture/publishing/console.md](../architecture/publishing/console.md) - what each console panel is, and where its data comes from.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - the published projection and the grain of every figure.
- [config/appearance.md](config/appearance.md) - the knobs these rules read.
- [../reference/pipeline-cost.md](../reference/pipeline-cost.md) - the instrument log the console never quotes from.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0b (voice) and Guardrail #10 (every number carries its conditions).
