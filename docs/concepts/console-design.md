# Console Design

**Last Updated**: 2026-09-23

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
days after the score ledger - so five days inside a thirty-day window have
scores and no server figures at all. A console that only designed the loaded
state would be mostly undesigned.

Six states have fixed wording, held in
[../../frontend/src/lib/console/recording.ts](../../frontend/src/lib/console/recording.ts):
measurement off, sampled below 1.0, counters but no scores, scores but no
counters, recording started mid-window, and a day that published and lost what
it measured. Only the dates and counts inside them are computed, and every one
is derived from the ledger that is missing - **a date that is not true is worse
than no date**. None is apologetic, none is styled as an error, and none is a
banner across the page: three panels can be in three different states on one
day.

Two of them are worth reading twice. **A sampled figure is never scaled up** -
multiplying a quarter-sample by four publishes an estimate as a measurement,
which Guardrail #10 forbids. And **no string names a config key as if it were a
word**: it is `Measurement is off`, never `host_fingerprint is false`, because a
term from a subsystem is not a term for a user (section 0b).

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

## An axis title and a column header take one form

`Article length, words`. **Sentence case, a comma, the unit in lower case, and
no full stop.**

- **The quantity, then the unit.** `Summary length, words` - never `Summary
 length (words)` and never `words`. A bracket reads as a footnote, and a label
 a reader meets before any of the numbers is not a footnote.
- **An axis title may not be a ledger column name.** `source words` is how the
 file spells `source_word_count` and `source_words`. A term from a subsystem is
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
 this pass.
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

## See also

- [design-system.md](design-system.md) - the tokens, ramps, motion set and sufficiency gate this page draws on.
- [console-design/the-rules-every-console-chart-obeys.md](console-design/the-rules-every-console-chart-obeys.md) - the thirteen rules, the ranked list, the date axis and the readout strip.
- [console-design/the-mark-shapes-a-panel-may-reach-for.md](console-design/the-mark-shapes-a-panel-may-reach-for.md) - the named shapes and what each cannot say.
- [console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md](console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) - the Hardware route and the run timeline.
- [console-design/what-the-quality-and-source-panels-draw.md](console-design/what-the-quality-and-source-panels-draw.md) - the model's own figures and the sources' health.
- [../architecture/publishing/console.md](../architecture/publishing/console.md) - what each console panel is, and where its data comes from.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - the published projection and the grain of every figure.
- [config/appearance.md](config/appearance.md) - the knobs these rules read.
- [../reference/pipeline-cost.md](../reference/pipeline-cost.md) - the instrument log the console never quotes from.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0b (voice) and Guardrail #10 (every number carries its conditions).
