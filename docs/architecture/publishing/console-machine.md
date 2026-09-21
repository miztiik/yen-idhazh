# What the Hardware route draws

**Last Updated**: 2026-09-21
`/console/machine/` answers a question no other route can ask: what machine did
the run actually get, and does the day's rate mean anything because of it.

**This is one route of the console.** [console.md](console.md) is the index - the
two questions every panel names, the five routes and the strip, the standing band
and the one window that governs every page. How any figure here is allowed to
read is [../../concepts/console-design.md](../../concepts/console-design.md), and
the machinery every chart shares is [console-charts.md](console-charts.md).
The headings, their order and which panels sit under each are
`console.panel_groups.machine` in
[`config/appearance.json`](../../../config/appearance.json), so the table below
describes that file rather than repeating a count that a config edit moves.
Every panel reads `state/item-health/`, `state/host-fingerprint/` or both -
the two instruments this route puts beside each other - and the machine panels
and the split take the processor and the flags off the machine record as well.
Both ledgers are read at build time under `$lib/server/` and nothing on the
route is fetched: neither adds a telemetry column and no reader sees a cell of
either.

| Group | Panel | Grain | The sentence it is for |
| --- | --- | --- | --- |
| What the machine was doing | Whether the speed numbers can be trusted | one bar a shard | Whether the day's rates can be trusted at all. |
| What the machine was doing | How much of the processor went to somebody else | one tile a day, and one a shard of the newest run | Whether the work was slow because another tenant on the same box took a share of the processor. |
| What the machine was doing | Whether the machine took the model's memory back | one tile a day | Whether the model waited on the disk for weight pages the kernel had reclaimed. |
| What the machine was doing | Which machines this run was given | one card a machine | What machine this is, what it can do against the others this run drew, what clock and uptime it had when we got it, and whether its record survived the day. |
| What the machine was doing | Whether some machines do the same work slower | one group a machine | What a written token costs against a read one, on the machine that paid it. |
| What the machine was doing | What kinds of machine we keep being given | one group a day, one bar a machine kind | What kinds of machine we keep being handed, and whether that is changing. |
| Where the time went | Which parts of the last run took longest | one row a shard | Was the day slow because of the work or because of the machine. |
| Where the time went | Whether the slowest articles are getting slower | one plot a percentile, one mark a run | Whether the slow end of a run is moving, and how wide the gap is today. |
| How close we are to the limits | How close an article came to using up the machine's memory | one mark an item of the newest run | How little the kernel had left at one article's worst moment, whether it gave the memory back, and how long the queue was. |
| How close we are to the limits | What is holding the machine's memory | one bar for the tightest moment of each day | What the memory is going to, and which of those parts a reader may add together. |
| How close we are to the limits | How close the longest text came to the model's limit | one mark a run | Whether raising the truncation cap is even possible. |
| What the model spends | What one article costs the machine | three figures over the span, each a range across the articles that recorded it | What a change to the prompt, the model or how many articles a day runs will cost before the run that pays for it. |
| What the model spends | How much text the model has to read again each time | one column a day | Whether a bigger cache would save wall clock. |
| What the model spends | How much of a run is reading and how much is writing | one group a run, in either unit | Which half of the model call the run actually spent itself on. |
| What the model spends | What this would have cost somewhere else | four figures over the whole span, and one column a day or one running line | Whether the runner time was a good trade, and whether the trade is getting worse. |

**Each heading names a decision an operator takes, and they run in the order he
takes them.** Until 2026-09-20 the three headings were `The newest run`, `The
open window` and `The machines` - which sort by time grain, a fact about the
instrument rather than a question anybody arrives with. An operator who wants to
know whether a slow morning was his work or the box had to scan the whole column
to find where that question lived. Four headings now: what the machine was
doing, where the time went, how close we are to the limits, and what the model
spends. Each group's answer decides whether the next is worth reading - triage,
then locate, then project, then tune. The order and the membership live in
`console.panel_groups` in `config/appearance.json`, so a re-grouping is a config
edit rather than a markup move; the route's own `load` refuses a list that names
a panel it does not draw, or leaves one out, so a typo fails the build rather
than dropping a panel off the page in silence. A titled group steps its panels'
titles to an `h3` under its own `h2`, which is what makes the grouping a
document outline and not a row of dividers. Authority: Susan, rulings A and B of
Row #9 of the honest-machine-telemetry plan, 2026-09-20.

**The grain moved off the heading and onto the panel.** A group used to carry
it: everything under `The open window` followed the span control and everything
under `The newest run` held still, and the route spent a paragraph above the
panels explaining which was which. A decision group mixes the two on purpose -
`What the machine was doing` holds a snapshot of one run beside a count over the
open span - so the carrier has to move. Every panel's subtitle ends by naming
its own grain, and `frontend/tests/console-frame.spec.ts` holds it there. What
is left of the old paragraph is the one fact no panel can state for itself:
which run the newest one currently is.

**A title states the question the panel answers, and a subtitle says why the
answer changes what you do.** Neither prints the words question or answer, and a
title borrows no word from how the thing is built - no column name, no subsystem
term, no vendor. `Prompt cache` and `Context headroom` were the two worst: both
named a mechanism and neither said what a reader would learn. The mechanical
half of the rule - no trailing question mark, no opening auxiliary verb, no
column name or vendor - is asserted in
`frontend/tests/console-title.spec.ts`; what it cannot check is whether a title
is *plain*, and Reader ruled all thirteen of the current ones on 2026-09-20.
Authority: owner for the title-and-subtitle split, CLAUDE.md section 0b for the
vocabulary, Reader for the wording.

**The verdict panel goes first**, so `Whether the speed numbers can be trusted`
opens the route rather than sitting seventh. It is the panel that says whether
the other twelve can be believed, and an operator who reads it last has read
twelve readings he had no reason to trust yet.

**A run is not a machine, and three of those panels exist because the route said
otherwise for weeks.** Measured 2026-09-17 over the committed counters ledger -
380 rows, 95 runs, 19 dates - **86 of the 90 runs that name a processor drew
more than one kind of processor**: one kind on 4 runs, two on 39, three on 43
and four on 4. Inside one run the read rate between the fastest and the slowest
machine runs 1.00x to 6.08x, median 2.32x, and 45 of the 86 exceed 2x. The worst,
run `2026-09-12-34689544296`, read at 59.71 tokens a second on one shard's
machine and 9.83 on another's. Until that date the split panel summed four
counters across every shard of a run and printed one pooled rate in bold, so the
figure an operator was most likely to quote was a number about neither machine
on 95.6 percent of runs. What replaced it is one group a machine and one
headline, attributed to the machine that read the most tokens.

**The shard is the unit, and that is the whole point of the route.** Measured on
the committed ledger on 2026-08-31, the fastest shard of run `2026-08-30-5` read
its prompts at 41.98 prompt tokens a second and the slowest at 9.73 - the same
run, the same day, **4.31x apart** - and the two slow shards took 62 and 78
percent longer to finish. A per-run average reports neither end of that, and it
is the average every throughput figure this project had quoted until this page.

**Reading and writing are never one bar, anywhere.** Read speed varies more than
4x inside a run on this ledger and write speed barely moves, so a single "model
seconds" figure averages two different machines together.

**Hardware carried both timing panels until 2026-09-20, and carries neither
now.** They merged into one panel on Pipelines - see [where a run's time
went](console.md#where-a-runs-time-went-is-one-panel-on-pipelines-at-two-grains). The move
is what makes room on a route that had fifteen flat siblings.

**The board is six columns on a desktop and one card a shard at 1280px and
under.** The column head is the only thing naming a value, so when the columns
go the names have to go into the cells - a heading that exists only on a desktop
is a value with no name on a phone. What the cards replaced was a two-column
fallback holding five children, which pushed the read rate and the job clock
into the 3rem shard column: measured 2026-09-01 at 360px on the build before the
change, `1 h 28 m` was drawn over four lines in a 20px box, one character to a
line, and `of the 150-minute timeout - 59 percent` took six lines in 41px. Every
value the desktop shows the phone shows;
[../../../frontend/tests/console-machine-data.spec.ts](../../../frontend/tests/console-machine-data.spec.ts)
compares the two sets rather than trusting the layout, and holds every string to
at least twelve characters a line. Dropping a column on a phone was refused: an
instrument that answers five questions on a phone and six on a desktop is two
instruments. So was a horizontal scroll, which hides the job clock - the column
an operator opens the page for. Authority: Jony and Susan, 2026-08-31; the
breakpoint moved from 1024px to 1280px on 2026-09-20, when the sixth column made
the two range marks under 60px of track each and a fill and a notch that close
together are one smudge rather than a span.

**The columns are the work-or-host answer, in the order an operator reads it.**
Shard and its item count, reading against writing, the two rates, the host, the
memory and processor range marks, and the job clock with the weights load under
it. They were five until 2026-09-20, and the board's own claim - a long clock at
a quarter of its neighbour's read rate is the host - could not be checked on the
board, because every host fact behind it was on one of four other panels. The
row now carries the item count, the write rate, the load against the cores the
host reported, the free swap against the swap it has, and the two range marks.
Authority: Susan, 2026-09-17, decisions 1 to 3 of Row #19.

**The card is an edge, not a fill.** Every quiet line in a row is
`--color-text-tertiary`, which reads 4.72:1 on `--color-surface` and 4.26:1 on
`--color-surface-raised`, so lifting the card would put four strings under 4.5:1
in the dark theme to buy a tint. Both bars in a row are drawn on
`--color-surface-sunken`, so a sunken card would erase them instead.

**A run whose rows cannot be made into one run is named on the page.** The
reader refuses a run where one shard index committed two different scrapes -
two workflow runs computed the same run id and a union merge concatenated both -
and the route prints the run id and the reason rather than quietly excluding it
from a count nobody can then check. Both halves of that cause are closed on the
writer's side since 2026-08-31 and the committed file was settled with them, so
today no run is refused; the guard stays because a reader of a committed ledger
cannot assume the run that wrote it was made by today's pipeline.

**The cost panel is a counterfactual and never a bill**, and it is the one place
on this site a figure in currency appears. CLAUDE.md Guardrail #10 carries the
owner's carve-out for it; the condition is that the page prints the rate it used
and says whether that rate came from `config/idhazh.json` or from the operator.
The operator's pair is kept in `localStorage` and read on mount only, so the
first paint always matches the prerendered document, and every cost figure on
the page is derived from one shared value rather than from four copies that
could drift.

## What the context panel says the reading limit costs

**Thirteen near-identical bars, each with two lines of prose, is a table
pretending to be a chart.** The panel used to draw one target bar a run, so a
question about a trend had to be answered by reading thirteen numbers in a row.
Since 2026-09-01 it is one chart: runs across the x-axis oldest first, tokens on
the y, and the reading limit as a rule. Authority: Susan, 2026-08-31.

**The limit is a rule, not a bar.** A limit is a line a series approaches. A bar
beside a bar invites a reader to compare two lengths and forget which of them is
the ceiling, and the browser oracle checks the geometry rather than the
attribute: every mark must sit at or below the rule, because no call can exceed
the limit it was given. Authority: Jony.

**The panel says what the current setting SPENDS, not only whether it could
grow.** Until 2026-09-21 it drew the longest sequence and a dotted line for the
room left over, which answered whether the truncation cap could rise - a
question nobody was asking - and stayed silent on the size of the slack. It now
draws two marks a run, because one mark cannot carry both the ordinary article
and the worst one and the decision to cut the limit turns on the worst. Under
the chart, one sentence names the share of the limit that has never been used
and how many times the limit is the article it usually reads. Authority: Susan,
plan 37 row 21. **What the reader loses: the dotted spare line**, which was the
solid line reflected in the rule and carried no second reading.

**The grain is one model call, and that correction roughly halves the figure.**
The limit bounds one call. The pipeline carries an earlier call forward into the
later prompt - measured 2026-09-21, the later prompt contains the earlier
exchange on all 1,976 committed rows that record both - so the calls added
together are a length the server never held. The panel takes the largest filled
call slot per article instead. Measured 2026-09-21 over the 1,312 committed item
rows that record both a limit and a call's own tokens, so both figures come off
one row set: the old arithmetic read 26,706 tokens at its worst and the honest
peak is 13,569, which is 41 percent of a 65,536-token limit against 21 percent.
The overstatement is 1.97x at the worst row and 1.92x at the middle one.
**Nothing here counts calls** - a slot is measured when the ledger filled it -
because the count is a config value (plan 37, the standing rule).

**Nothing has ever been cut off.** Every finish reason in the archive says the
model stopped on its own: 2,624 of 2,624 calls, measured 2026-09-21. The word
for the other outcome is `console.context_cut_off_reason`, a knob rather than a
literal, because the vocabulary belongs to llama-server. The canary carries one
cut-off reply so the state a shrinking budget reaches is drawn rather than
argued about.

**The row states the finding and does not act on it.** The limit is
`models.summarize.inference.n_ctx` and cutting it is the owner's call. The
panel's job is to make the slack impossible to miss.

**The panel is about the worst run in the span, not the newest**, which is why
it stays windowed and why every run in the span keeps a mark. Drawing only the
newest run was refused for that reason. Authority: Carmack.

**One mark a run means the x-axis columns are runs, not days**, and a day can
carry several runs. Two consequences follow. `dayTicks` still owns the thinning
and the anchoring, but a repeated day is labelled once and the tick mark stays -
two identical dates side by side read as a chart that lost its order. And the
model-change rule falls on the FIRST run of a changed day, so one change draws
one rule; without that, a day with three runs would say the pipeline changed
three times.

**Every run's own numbers stay on the page**, in a screen-reader list under the
chart. The chart is the shape of the question; the list is the table it was made
from, and nothing on this route is only in a picture.

## What one article costs, and why it is not the run total shared out

**A run total divided by the item count cannot disagree with the run total, so
it checks nothing.** It is the same number wearing a different unit: every
article of a run gets the mean by construction, a run whose slowest article cost
ten times its quickest reports neither figure, and a change that moved only the
slow end moves the printed number by a tenth of what it actually did. Every
figure on this panel is measured per article and printed as a range - lowest,
middle, highest - which is the only shape that can price a change before the run
that pays for it. Rejected alternative: Fowler, Row #12.

**Three costs, three instruments, and they are not interchangeable.**

- **Processor time** is `cpu_busy_pct` times the processors the machine record
  names, times the item's own clock. The kernel counts every logical processor
  on one `/proc/stat` line, so the share is a share of all of them and the
  multiplier is `threads`, never `cores`. On a machine running two threads a
  core - which is what every committed record describes - using `cores` halves
  every figure. `frontend/tests/console-article-cost.spec.ts` runs the same
  arithmetic both ways and refuses the answer that used the wrong one.
- **Model time** is `prefill_ms + decode_ms`, which the summarize stage sums
  over whatever calls the article made before the row is written. It is a total
  over the work the article needed, so nothing on this panel is keyed to how
  many calls an article makes.
- **Added memory** is the rise in `llama_rss_bytes` between neighbouring items
  of one shard. A step, not a level: the level says what the server is holding,
  and the question here is what one more article adds to it.

**The memory step is taken between neighbours of ONE shard, and never across
two.** A fresh shard starts a fresh model server, so the difference between the
last item of one shard and the first of the next is a restart rather than an
article. A gap in `item_index` is skipped for the same reason: whatever happened
to the item the ledger missed is not the next item's doing. Authority: Susan,
Row #12 decision 2.

**The track holds zero, because the step goes below it.** Measured 2026-09-21
over the 1,162 steps the committed ledger holds, 402 of them are falls - the
server gives memory back as often as two times in five. A track running from the
lowest reading to the highest would put the biggest fall at the left edge,
exactly where the smallest rise would sit, so the sign would be invisible. The
shared `spanTrack` runs `0..max` and cannot draw a negative low, which is why
this panel carries its own track rather than borrowing that one.

**A processor-second is unreadable without the hour it has to fit inside**, so
the panel prints what one runner-hour supplies next to the figure - the
processor count times 3,600 - and quotes it on the smallest machine the span ran
on, because that is the one a cost has to fit inside. It then says how many
articles that hour buys at the middle figure. A share of an hour was printed
first and was cut: it rounds to `0.0%` as soon as an article is cheap, which
reads as free, and it answers a question nobody asked. Measured 2026-09-21 over
the 954 committed articles that resolve to a machine record, the middle article
takes 1,861 processor-seconds against the 14,400 a runner-hour supplies on four
logical processors - 7.7 articles an hour of the whole machine. Authority:
Susan, Row #12 decision 4, under `CLAUDE.md` Guardrail #10.

**Where no machine record names a processor count, the figure is a dash and the
panel says why.** The item ledger records a share; only the machine record says
what the share is a share of. Filling that in from the runner we usually get
would publish an assumption as a measurement. Of the 1,325 committed articles
that recorded both a busy share and a clock on 2026-09-21, 371 belong to runs
the machine record never reached, so the panel prints both counts rather than
quietly dropping the difference. Authority: Susan, Row #12 decision 5.

**What the panel cannot answer, it names.** The memory step belongs to the
model's work, and nothing in the ledger says which half of it - the prompt the
server read or the reply it wrote. The measurement that would settle it is a
resident-memory reading taken at each call boundary instead of one reading when
the article ended. Authority: Susan, Row #12 decision 3.

## Two panels left the page, and what the reader lost is named

**A container holding three unrelated figures has no question to be titled
with.** `Where the machine's time went besides the model` carried a processor
share, a weight-opening time and a count of the slots a server was started with.
A title naming a subsystem was the only title that fitted, which is the defect
the four decision headings exist to remove. Two of the three figures were
already spent: the slot count read the same value on 382 of the 383 committed
rows that carry it, and the processor share was about to stop meaning what its
own description claimed the moment the sampler separated out the time the host
gave another tenant. Authority: Susan, 2026-09-20.

**The third figure and the band are a loss, and nobody has replaced them yet.**
What went with the panel is the reading of how long a shard spent opening the
weights against the window that measured it, and the same band for the processor
share. The per-shard opening time is still on the shard board, so what is gone
is the comparison with the rest of the window rather than the number. The shape
is kept whole in `frontend/src/lib/charts/span-track.ts` with its rules held in
`frontend/tests/console-host-spans.spec.ts`, because the honest version of the
processor share - the one that separates out the stolen time - needs the same
band rather than a second one. **No panel draws that band today.**

**A run can no longer be read against its own settings.** That panel was the one
place the page said what the server was started with, so an operator comparing
two runs now has nothing on the page that names the configuration either of them
ran under. The gap stands until somebody builds the replacement, and it is
written here rather than absorbed.

**The single-run distribution panel drew the newest column of the panel below
it.** `How far the slowest articles ran behind the rest` read the last entry of
the same array the five stacked plots draw, so the two could never disagree and
one of them was redundant. The trend panel's readout already prints all five
values for whichever run the pointer is on. What the curve was being eyeballed
for is one number - how far the slow end sits from the middle - and the trend
panel now prints it for the newest run drawn. **What the reader loses:** the
whole ladder of one run as a single shape. Reading it off the five plots means
reading straight down one column instead, which the shared scale was already
built for. Authority: Susan, 2026-09-20.

## The memory board leads with what the kernel had left

**The lead is `os_mem_available_min_bytes`, the least the kernel had left at one
item's worst moment.** That is the reading the panel's question is about -
whether a bigger model fits - because a resident-set mark says what a process
held and not what was still free. And it has to be taken per item: one item can
take the machine to its floor while the shard it sits in reads as a normal
shard, so a per-shard figure cannot show it. Authority: Susan, 2026-09-20.

**The model server's own high-water mark is not drawn here, and the panel says
so.** `llama_rss_peak_bytes` is `VmHWM`: the kernel prints the larger of the
current resident set and a stored mark it refreshes only when the process gives
memory back, so the figure covers the server's whole life rather than the item
and reads lower than an earlier item's whenever a page is reclaimed
([why it reads lower](../../reference/host-metrics.md#why-the-model-servers-memory-mark-reads-lower-than-it-did)).
The column is still written to the ledger and nothing on the panel is built on
it. A caveat under a mark does not stop the mark being read, so the mark is off
the page rather than footnoted. **What the reader loses:** the only recorded
process-level peak, and with it any idea of how near the server got to the
ceiling BETWEEN two item boundaries. The end-of-item reading below is what is
left, and it is a lower bound on that peak.

**The shard grain and the window grain went with it.** Both drew only
`llama_rss_peak_bytes`, so both would have been the dropped mark under another
name, and the grain switch had nothing left to switch between.

**The two end-of-item process readings are brackets labelled at most, never
tracks.** `llama_rss_bytes` and `python_rss_bytes` run to the larger of
themselves rather than to the machine's total, and they are drawn overlapping.
A resident-set figure drawn against a total reads as a budget, and that is the
exact figure this project retracted on 2026-09-09; a reader cannot add two
brackets that visibly overlap, which is the whole point of the shape. The bar
that does partition the machine is a separate panel. Authority: Susan,
correcting herself 2026-09-20.

**An item with no kernel reading is hatched and counted in a sentence, never
drawn at zero and never filled in from the dropped mark.** Re-measured
2026-09-21 over the committed `state/item-health/` tree, 378 of 13,877 rows
carry the three kernel columns and the earliest is dated 2026-09-19 - exact
counts over committed files, so no spread. **Most committed rows do not carry
them, so this is the common case rather than the edge case**, and the count is
the figure that ages rather than the property. The sentence names the date the
reading begins and the earliest date the page read, so it is bounded by the span
it drew and never claims anything about days nobody opened.

**The item mark runs floor to recovery, not floor alone.**
`os_mem_available_min_bytes` says how close the item took the machine to its
limit; `os_mem_available_bytes` says whether it got back. **A machine whose
floor falls and whose end also falls is leaking; one whose floor falls and whose
end recovers was only working hard.** That separation exists nowhere else on the
site and it costs one more field on a series this panel already builds.

**Machine load is the second series, not a second panel.** Measured on the same
80 rows, `load_1m` runs at **5.49 on 4 vCPU** - a run queue 37 percent longer
than the cores - and no panel drew it, while `cpu_busy_max` reads 99.96 percent
on the median row and carries no signal on its own. **Busy and queued are
different facts and neither implies the other**, so both are drawn, beside the
memory they explain. A panel of its own would have been an eighth writer on a
file seven rows already serialise over.

**The two brackets added are an upper bound unless one item held both.** The
server maximum and the worker maximum fall on different items on the committed
ledger, so their sum is arithmetic over two moments that never met. The panel
says which of the two it is printing.

**`os_mem_total_bytes` is the denominator and the tell.** `/proc/meminfo` is not
namespaced, so inside a container it reports the HOST rather than the job. A
total that is not about the runner's 16 GiB means every reading built on the
other five OS cells is about a different machine, and the panel says so instead
of drawing them. Where the drawn rows disagree on the total the smaller is the
denominator, because the smaller is the one that could have run out - **and a
run that drew two machine sizes is itself a finding**, so both are printed.
`MEM_TOTAL_AGREES_WITHIN_PCT` in `frontend/src/lib/charts/machine.ts` is the
width of that check and carries its reason.

**It says what it cannot separate.** Nothing samples memory inside the model
call, so which phase owns the peak - reading the prompt or writing the answer -
is unanswerable here, and the panel says so on the panel. A memory panel silent
about what it did not separate invites a reader to assume it did.

**No tint and no band.** Nobody has agreed how little headroom is too little,
and a colour would publish a threshold that does not exist. Authority: Susan.

## Three clocks address a slow shard

**The shard board says a shard is slow. These three say where the time went.**
Each row carries the seconds no named step claimed, the seconds an item waited
before a worker started it, and the seconds the shard paid opening the weights.
All three come off ledgers the site already commits; none of them reached a
screen before.

**The unclaimed figure is read, never recomputed.** It is `stage_gap_ms` off
`state/item-health/`, added over the shard's rows, and the page works out
nothing. The column is the item's own wall clock minus every step the pipeline
named, so it is the one thing that can catch a regression in a step nobody
named - and a figure the page subtracted from the step clocks itself would agree
with them by construction and could never flag the disagreement it exists to
flag. Authority: Fowler, 2026-09-21.

**It is drawn with its sign.** Below zero says the named steps claim more time
than the items took, which is two clocks disagreeing rather than a shard that
cost nothing, and taking the absolute value would throw away the finding.
A count of the rows below zero is printed beside the total, because a total can
cancel: one item at plus two seconds and one at minus two add to nothing and the
shard would read as healthy. No committed day has ever carried a negative row,
so the canary writes one on its refused item - the failure path is where a
disagreement would really come from, and a state no fixture holds is a state no
test can reach. Authority: Susan, 2026-09-21.

**The queue wait is a typical item and the worst one, and never a sum.** The
work stage fetches every item and then runs the model over them in a different
order, so each item's wait covers the queue ahead of it. Adding them counts that
queue once per item: measured 2026-09-14, a two-item shard read 2,786 seconds
against a true 2,196. `ItemRecorder.parked` already takes the wait back out of
the item's own clock for the same reason. The pair is drawn on the board's clock
scale rather than as a number of its own, so a shard that waited longer than it
computed draws a longer bar than its own model time - which is the sentence the
board could not say before, because it drew a job clock and a model clock and
nothing that explained the gap between them. Authority: Susan, 2026-09-21.

**What it cannot settle:** which step the unclaimed time belongs to. Naming it
is what the column exists to prompt, not what it can answer.

## Three cross-boundary carries, one sentence each

Each route ends its introduction with one sentence pointing at a panel another
route owns: Pipelines says what the model spent of the day it just described,
Model says how far apart the day's runs read, Machine says how many articles the
day published. No chart, no card - a signpost that looks like a figure gets read
as one. They exist because the failure mode of splitting a page is a route that
hides the panel explaining another route's numbers.

## The run strip is a time axis, and a day nothing ran is drawn

The pipeline has written a machine row per shard per run to
`state/host-fingerprint/` and an item row to `state/item-health/` for longer than
this route has existed, and no page had ever put the two together. The route
exists before its panels do, and says what is missing once at the top and once
per named panel. A route that hid itself until it had data would be a route
nobody knew to check - which is exactly how a ledger goes four days unread.

**The run strip is a time axis: one column per day of the window, oldest on the
left.** Days advance left to right the way every other time series does, so "it
broke on Tuesday and has been amber since" is a shape rather than a sentence.
Each day is a track that grows with the room the strip has, floored at 16px with
a 4px gap, and a label may never widen a track - two days apart must measure
twice one day apart, whatever the date under it says.

**A column with no square is a day nothing ran, and it is drawn.** A strip with
one column per manifest is rejected: at the default thirty-day window over the
committed ledger it drew eleven columns, measured 2026-09-01 at 1440 on node
24.12.0, **464px of a 1,326px frame - 35.0 percent**, with the other 862px empty
on the right. That reads as a chart that failed to load. The window's own
calendar draws thirty columns at 1,290px, **97.3 percent**, and the gaps in it
are the fact this panel is the only place to see: a day the schedule dropped.

**`CELL_MAX` was not what left the margin, and the plan row that ordered this
said it was.** The ceiling is 34px and the frame offers 35.4px a column at thirty
days, so the cap costs 30px of 1,326 - two percent, not sixty-five. The column
count was the whole of it. The ceiling stays at 34, which is the size a fortnight
wants; a narrower preset still cannot fill a page-wide frame at any cell size a
run square should have, and that is what the centring rule below is for.

**Within a day, runs rise from a shared baseline.** Run 1 sits on the ground and
later runs stack upward, so every column starts from the same line and a busy
day is visibly taller than a quiet one. The DOM still reads run 1 first: the
order is reversed by layout, not by markup, so a screen reader gets the day in
the order it happened.

**Only a run that wrote a manifest gets a square.** A scheduled run that never
started left no evidence, and an empty slot would claim knowledge of a schedule
the payload does not carry. Drawing missed runs needs a persisted schedule or
attempt contract first; until one exists, the strip says what happened and
nothing about what should have.

**Dates are a separate, sparse row.** One day gets one full date. Two to six
days get one compact span (`18-20 Aug 2026`). Seven or more get a full date at
each end and as many between them as `dayTicks` measures room for. The year is
printed on the first label that changes it and not again. The arithmetic lives in
[frontend/src/lib/charts/run-history.ts](../../../frontend/src/lib/charts/run-history.ts)
so it can be tested without a browser. Eleven narrow columns had room for four
labels; thirty have room for the cadence the axis was written for.

**A day is read through the shared readout strip, not through a `title`.** A
native tooltip is rejected: it needs a hover, so on a phone the run's verdict
does not exist; it takes no styling; and it prints one square where a reader
wants the day. The strip below the
plot prints every run of the hovered day, each with the swatch it is drawn in
and the word for what it did, and the arrow keys step through the days. The
`title` and the `aria-label` stay on each square, because nothing the readout
reports may be needed to read the chart
([../../concepts/design-system.md](../../concepts/design-system.md)).

**The standing key went with it.** The readout prints the swatch and the verdict
for the run it is on, so a key beside it drew the same pair a second time - and
one fact drawn twice is how two of them drift. The rule the key's red entry
carried, `failed, or under N% published`, is a rule and not a legend, so it is
in the panel's note where the rest of the reading instructions are.

**A strip that cannot fill its frame is centred in it.** Left alignment is
rejected when the window calendar is drawn: the spare room piles up on the right,
and the right of a time axis whose last column is today is where a reader looks
for the days that just happened, so the room reads as a run that has stopped.
Left alignment is only right when the strip draws only the days that carried a
run, because then the right-hand room really is "days not yet published"; with
the window's calendar drawn, the last column is today and there is nothing to the
right of it.
`centreOffset` returns zero once the strip overflows, because a scrolling strip
has no spare room to divide and an offset would push its first column out of
reach. At the default window the strip fills, so the rule is only visible at the
7- and 14-day presets.

**Centring it exposed a gap `cellFor` had been counting and the strip never
draws.** `StripMetrics.width` was `days * (cell + gap)`, which includes a gap
after the last column that is never painted. Nothing read the number until the
spare room had to be halved, and then it put one whole gap more on the right
than on the left - 8 px of 1,326 at a 34 px cell, measured 2026-09-01, which is
a quarter of a column. `denseCellFor` beside it already counted the honest way
and said why in a comment. The same width scales the readout's marks, so the
correction also moved a pointer halfway along the strip onto the column it is
actually over.

**Where an overflowing strip OPENS is a different question, and it is the one
`console.today_anchor` answers.** The two were one line of layout for a while
and they are not the same fact: the anchor is a scroll position, and the
alignment above is where the columns sit inside a frame that is wider than they
are. The strip is a native horizontal scroll region - focusable, labelled, and
pannable with the arrow keys, with no buttons and no chart dependency.
JavaScript sets the initial scroll to the newest edge once, on the first
animation frame after mount, and never again: after that the position belongs to
the operator.

**The strip is a panel, and it follows the page's window.** It draws the days
inside the span the window control holds, states that span in its own note and
in its accessible label, and carries `data-windowed="run-health"` like every
other windowed section. A window that reaches no run says so in its own sentence
rather than showing an empty grid, and that sentence is not the one an empty
ledger gets - "no run recorded a manifest in the last N days" and "no run has
recorded a manifest yet" are different facts.

Three colours, and the boundaries are read from config rather than chosen by the page:

| Colour | When |
| --- | --- |
| Green | The run completed, nothing failed, and the source list was current |
| Amber | Something is worth a look: an item failed, the run did not complete, the source list was stale, or nothing was attempted |
| Red | The run failed, or its success rate fell below `run.success_floor_pct` |

**The red threshold is the same knob CI uses to decide whether a run opens an issue.** A red square and an open issue can never disagree, because there is one number and both read it.

**The squares are painted from the fill ramp, not the confidence ramp.** A 16px
solid is not type. Measured against the panel's surface, `--band-medium` is
5.43:1 and `--band-low` 6.12:1, which is text weight, and on screen they read as
olive and brick. The
band tokens stay text colours because four other surfaces read them as type;
`--fill-high`, `--fill-medium` and `--fill-low` are the parallel set, and
[../../concepts/design-system.md](../../concepts/design-system.md) owns the band
a fill value has to land in.

**A skipped item is not a failure.** An article already published, or one a feed repeated, is skipped by design, so the rate is over what was *attempted*. Counting skips would paint a healthy day amber for doing its job.

Beneath the strip, the section leads with its own denominator: **how many feeds did not fail, out of how many the pipeline read, over how many runs** - 152 of 179 across 44 runs, measured 2026-09-03. Four broken feeds out of eight is a collapse and four out of two hundred is a Tuesday, and until this landed the page drew both identically. The clean feeds are NAMED behind a `<details>`, alphabetically, with no bars and no order, and the summary says why there is no order: a feed is read once a run, so every clean feed has the same record. Under `console.min_attempts_for_rate` runs the sentence prints the same counts and says the record is too shallow to read as reliability - two runs deep, "did not fail" means "did not fail twice". The rule is `reliability` in `frontend/src/lib/feed-health.ts`, reading the same `failing` the quarantine reads ([../sources/health.md](../sources/health.md)).

**The sentence names its span, because a bounded read cannot prove "never".**
The read behind it is `feedResults(shardMonths(widest))` - the newest five month
shards, which is what the widest window preset can reach and no further.
"Never" claims every run there has been over a read that opens a bounded set of
files, so it is a claim only a growing read could support (`CLAUDE.md` Guardrail
#12, owner decision 2026-09-08). The sentence says the feeds "did not fail a
read in these 44 runs", with the count from the record rather than a literal.
The windowed sentence is also the more useful one: a feed that broke once in
August and has answered every run since is permanently disqualified by "never
failed", and the question on the desk is whether anything is broken now.
`tests/console-window-claims.spec.ts` holds it - it reads the three built console
documents, strips scripts and every attribute but `aria-label`, and refuses a
claim in the present perfect.

**What that guard does not catch, said out loud.** It bans a grammar, not a word: "has never failed" and "has ever reached" place a claim in an unbounded past, while "runs are never pooled" and "a counterfactual, never a bill" state rules and read over no span at all. Measured on the canary build 2026-09-09, the three console documents carry **42 remaining uses of `never` or `ever`, and every one is a rule, a domain term or a statement about named items** - 24 of them are the cell `Never checked:`, which is one of the checker's five reason names. A word list would have fired on all 42. A bare past tense - "the feeds that never failed" - makes the same claim as the perfect and is not matched, because the only pattern that would catch it is a list of verbs, and that list fires on "the part the machine never read" two sections up the same page. Those strings are held by review and by the assertions in `console.spec.ts`.

**A refusal is not an ask.** A row that preserves the strike streak - a rest,
or a robots answer - never asked the feed whether it still works, so it can make
the feed neither clean nor broken. Dropping only rests is rejected: a source the
pipeline is refused by on every single run would sit in the clean count and the
page would report it as reliable delivery. Measured 2026-09-03 over the committed
ledger, **5 feeds of 184** were in that state and every one had given the digest
nothing: `anthropic-engineering`, `anthropic-research`, `axios-business`,
`cbc-world`, `cnbc-top`. They are a third count with their own disclosure, and
the predicate that decides it is `preserves` - the same one the strike rule runs
on, so an ask means one thing in both places. The section's own explanatory
paragraph says "a feed nobody has asked is in neither count".
## See also

- [console.md](console.md) - the console index: the two questions every panel names, the five routes, the standing band and the shared window.
- [console-charts.md](console-charts.md) - the frame, the readout and the marks every chart here is built from.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a figure on these panels may be worded, ranked, tinted and drawn.
- [../sources/item-health.md](../sources/item-health.md) - the ledger eleven of these panels read.
- [../../reference/host-metrics.md](../../reference/host-metrics.md) - what each machine column is, and which of them the runner refuses to answer.
