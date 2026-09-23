# What drawing costs, and what has been retired for it

**Last Updated**: 2026-09-23

Three renderers and one whole stage have been deleted from this pipeline, each
on a measurement rather than a preference. This page keeps those measurements so
nobody takes them again, and it keeps the live line that would retire the last
renderer too: the console table an operator reads chart economics off, and the
pre-committed criterion that would switch chart drawing off. Who decides a
picture today is [visuals.md](visuals.md); where a drawing becomes pixels now is
[where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md).

## The stage stopped itself before the job did

**This section is history.** The separate stage, its job and its clock retired on 2026-09-13, and a
picture is now decided inside the shard that read the article. It is kept because the defect it
records is a property of any long job that hands its only copy of its output to an upload step.

The stage's wall-clock was `items with an OK summary x per-item cost`, and neither factor was
bounded. The first was set by how well the summarizer did, up to `run.safety_ceiling_per_run`
(200). The second was set by whichever host the runner gave us: measured mean **20.7 s on a fast
host and 40.3 s on a slow one**, over six runs and 703 items on 2026-08-24/25. A 145-item day
therefore needed anywhere from 50 to 97 minutes against a 50-minute job.

What happened when it went over is the part that made the defect invisible. A job cancelled at its
timeout **skips any step without an explicit condition**, and the `visuals` artifact upload was one
of those. So the run threw away every decision the hour had bought - on 2026-08-25 that was 88
decided items and 9 rendered charts - and `assemble` published 145 items with zero visuals and no
error anywhere on the page. The day cannot recover: `build_day` keeps an already-published item,
so the four later runs of that day re-decide the same items at full price and their answers are
discarded.

Three things changed, and each one addresses a different link in that chain:

| Change | What it stops |
| --- | --- |
| `stage_visual_planner` stops at `run.visual_planner_budget_minutes` (40) | The job is never cancelled, so it always reaches its upload step. |
| The `visuals` upload runs on `always` | Even a job cancelled for some other reason hands over what it made. |
| `visuals.enabled_kinds` drops `diagram` | 46.9% of the day stops reaching the model at all, so far more items fit inside the same budget. |
| The planner skips what the day already published | Runs 2 to 5 stop re-deciding run 1's items for an answer the assembler discards. |

**The budget stop is not a rare event, and that is now measured.** Over the eleven committed runs
that decided anything, the stage spends its **whole** budget on ten of them and leaves items
undecided on nine, at a median of 48.9 seconds an asked item and a median of 18 items left
([`../../archive/measurements-2026-08.md`](../../archive/measurements-2026-08.md#the-route-stages-per-item-cost-over-every-run)).
So a run that hits the bound is the normal case rather than a symptom, and **a single run's figure
must not be quoted as what the stage costs** - the fastest run on record is 1.7 times faster per
item than the next, which is enough to make an ordinary run look like a regression. What would
change the picture is sharding the stage, not tuning the number.

**The planner visits the best story first.** The plan is vertical-major, so stopping part-way down
it would cost whole verticals their pictures while the weakest story in the first vertical kept
one. `plannable_items` sorts by `rank_score` before the loop, which is the rule
`_within_ceiling` already follows for the safety ceiling: drop the weakest stories across every
vertical, never a suffix.

**The planner skips an item the day's committed digest already carries.** `build_day` keeps an
already-published item and discards the new run's copy, for crash consistency between the day write
and the ledger append rather than to hold a reading order steady. So a later run's decision for one
of those items is computed, written, read back and thrown away. A day runs five times: without the
skip, run 2 spends its whole budget re-deciding run 1's items at 20 to 40 measured seconds each,
and the items it actually introduced queue behind them. This is the resumability invariant the rest
of the pipeline already holds - a re-run costs only the unfinished items - applied to the one stage
that did not. It reads the committed `digest.json` the same way the asset counter reads the
committed directory, so it needs no handshake with the assembler.

The corollary is worth stating plainly: **an item published without a visual can never gain one.**
That is a property of `build_day`, not of the planner, and it is why a run cancelled at the bound
cost its day permanently rather than for one run. Changing it means letting a later run mutate a
published item, which is a decision about the day payload rather than about the planner.

**An item the stage never reached writes no payload.** That is the same fact `items_routed` already
reports - "items the planner reached" - and it is what an item looks like today when the planner
never starts. A budget stop is the stage stopping, not a decision about an item, so it does not
borrow `asked_the_model` and does not move `items_prefiltered`, which counts one specific cause.
The run log names the count and the mean that produced it.

The job's `timeout-minutes` is 50 against a 40-minute stage budget. It is the backstop, not the
budget, and the 10 minutes between them are the fixed cost the stage clock never sees - checkout,
weights, install, model start. Both numbers came down together on 2026-08-25, because a job bound
20 minutes above the stage bound is 20 minutes in which a stuck stage burns runner wall-clock past
its own limit. Raising either one is the move Guardrail #2 forbids.

## The kill line for chart drawing, registered before the data was read

Authority: Jony,
2026-08-25. Over 14 consecutive days with the chart-only gate on, retire chart drawing if the median day
publishes a chart on fewer than 5% of published items, or spends more than 6 planner minutes per
published chart. Either limb trips it. A day stopped at the budget still counts. Measured
2026-08-25 on `ubuntu-latest` (4 vCPU, 16 GB): 6.2% and 4.4 minutes - inside the line on both
limbs, which is why it ships. Writing the line down first is what stops the number being
argued after it is seen.

`charts_drafted` on the run manifest is what makes that reading possible. It counts the items whose
planner reply asked for a chart, whatever the decision became, so the gap between it and the day's
published charts is exactly what the two post-model controls rejected. Without it a model that stops
asking for charts and checks that start refusing them are the same number.

**The summarizer swap on 2026-08-27 moved an input the window sits on.** The planner ran on its own
Qwen3-4B and that model did not change, but the user turn it read carried the summary text as well
as the article's opening and the indexed numbers - so a different summarizer wrote a different
question, and `charts_drafted` could move with no planner change at all. The 6.2% and 4.4 minutes
measured on 2026-08-25 were taken on the retired incumbent's summaries. Read the fourteen-day window
from days after the swap, and treat a step at the swap date as a changed input rather than a
verdict. The mark that would make that step visible on the console is not built
([../summarize/throughput.md](../summarize/throughput.md)).

## Where the kill line is read from

The console carries a `Charts` table, one row per published day, newest first. It is the surface the
kill line is read off, and it is for the operator: nothing about chart economics reaches the digest
page a reader sees. Seven columns:

| Column | Read from |
| --- | --- |
| Day | The published date. |
| Reached | `items_routed + items_prefiltered`, summed over the day's runs. |
| Asked the model | `items_routed`, summed over the day's runs. |
| Charts drafted | `charts_drafted`, summed over the day's runs. |
| Charts published | The day's `digest.json`: items whose `visual` is a `chart` in state `rendered`. |
| Minutes spent | `route_ms` summed over the runs that recorded one, in minutes. |
| Minutes per visual | Minutes spent divided by charts published. |

The two gaps are the point. Reached against asked is the reachability gate, running before any
request. Drafted against published is the two post-model controls. A single funnel of bars would
make the last stage the shortest and hardest to read, and the last stage is where the decision sits -
so it is a table.

**A number that does not exist prints a dash, never a zero.** A day on which nothing was decided
reached zero items, which is a measurement and prints as `0`. It spent no measured minutes, which is
not the same as spending none - `route_ms` is null on that manifest, and `0.0` there would read as a
stage that was free. A day with no published chart has no per-chart cost, so that cell is a dash
too rather than an infinity or a zero.

**Zero reached and a day older than the counts read the same, on purpose.** `items_routed`,
`items_prefiltered` and `charts_drafted` all default to zero on a manifest written before they
existed, so a day from before 2026-08-24 prints zero reached beside the charts it really published.
That is the honest reading: nothing committed says what its planner did. It also means a day before
the counts existed cannot enter the kill line's fourteen-day window, which is correct - the window
starts when the chart-only gate went on, and the gate and the counts landed together.

**No rate is stored.** `Minutes per visual` is two committed numbers divided at read time. A
persisted rate is a third fact that can disagree with the two it came from, and the console's whole
claim is that every figure on it was written down when the run happened.

**Charts published is counted from the payload, not from the manifest.** The manifest records what
the planner decided; the payload records what a reader can see. A chart whose render failed is a
visual and is not a published chart, so counting visuals instead would put a failure on chart
drawing's bill.

## What the pipeline stopped doing on 2026-09-13

**This section is the record of three renderers that were deleted, and what each cost.** None
of them runs. It is kept because a page that hides a thing we removed is as wrong as one that
describes a thing we still run, and because two of the three were removed on measurements
somebody would otherwise take again.

| Kind | Persisted | Drawn by |
| --- | --- | --- |
| `chart` | `VisualData` - marks and their channels | d3 in the reader's browser |

Chart is the only kind. `VisualKind` held four until 2026-09-05, and the other three are gone.

**Why there is no image renderer.** Measured on `ubuntu-latest` (4 vCPU, 16 GB),
2026-08-23, run `32654562728`: `Tongyi-MAI/Z-Image-Turbo` at bfloat16 loads in
159.2 s at 9.2 GB resident, then spends **527 s per denoising step** at 512x512.
Nine steps is about **79 minutes for one image** - longer than the whole `visuals`
job's 60-minute bound, and about 196 hours for a 149-item day against a 6-hour
job limit. The job was cancelled at step 7 of 9 and never reached 768px or a byte
count. The plan's second candidate, `alpha-vllm/Anima-2.9B`, answers 401
Repository Not Found: it does not exist. Reducing steps does not rescue it -
three steps is still 26 minutes, and one step is noise. Guardrail #2 says the budget
is the platform, so the feature goes rather than the budget. The `image` member
survived in the enum for two more weeks so that a payload could say it, and no
payload ever did: scanned 2026-09-05 over all 15 committed `digest.json` files,
6,425 items and 351 visuals, and every one is a chart. It was deleted on that
evidence.

**And why the diagram renderer went with it.** Diagram drawing shipped off on 2026-08-25
for the reason above - it drafted zero diagrams in 88 items and rendered zero in
703, while making the reachability gate unfireable. What was left was a round trip
with nothing at either end. The planner wrote `flowchart TD` text "so anyone can
re-render this with the real Mermaid toolchain", and nobody can: the payload lands
under gitignored `backend/var/`, travels as a one-day artifact, and the published
`DigestVisual` carries no spec at all, so the text is unreachable 24 hours after a
run. The reader lost nothing, because the reader never received Mermaid. It also
lost data on the way back - the parser matched edges and threw them away, so order
came from a sort and two different graphs drew identically. And the diagram family
is being rebuilt on a plan that carries nodes and edges natively, so serialising
that to `flowchart TD` and reading it back with a regex would end with less than it
began. Deleted 2026-09-05 on the same scan: zero committed items carry a diagram.

**The Vega-Lite renderer is the third one deleted, and this one was the reader's.**
`vl-convert` bundled the Vega toolchain as a Rust extension and turned a compiled spec into an
SVG under `frontend/public/digest/<YYYY>/<MM>/<DD>/<item_id>.svg`, beside the payload that
referenced it. Measured 2026-08-22 (8 vCPU, `vl-convert-python` 1.9.0.post1): 2,568 ms for the
first render in a process, 49 ms warm, about 7 KB of SVG - the cold cost being engine boot,
paid once per run rather than once per item. It went on 2026-09-13 with the dependency, its
mypy override, the 495 committed drawings, the canvas knobs only it read, and `render_visual`,
the one call that turned a spec into a file.

**It was also not deterministic inside one process, and that was found while scoping the row
that deleted it.** Vega's clip-path id counter was global to the process, so the first render
of a titled plan emitted `clip1` to `clip4`, the second `clip5` to `clip8`, and at `clip10` the
id gained a digit and the file gained a byte. `_drawn` ran once per item inside one shard
process, so **an asset's bytes depended on where its item sat in the render order**. Measured
2026-09-13 on the development box against
`tests/fixtures/visual-validator/plans/passes.json`: three renders of one plan in one process
gave three different byte strings, the third 6 bytes longer than the first. The committed
evidence agreed - 495 drawings carried 3,256 clip ids running from `clip1` to `clip67`, which a
per-render counter could not produce. The determinism test could not see it: its inline spec
carried no title, so it emitted no clip path at all and passed for a reason other than the
property it named. It was recorded rather than patched, because a fix inside a module being
deleted is the temporary kind `CLAUDE.md` Guardrail #5 refuses - and it was deleted with the
module rather than ported, because its false comfort was the defect. What replaced it is a
property the data can carry: compiling one plan twice gives one document.

## Design rationale

**Why our own SVG for diagrams rather than Mermaid's own renderer.** `mermaid-cli` drives a
headless Chromium. That is roughly 300 MB of install and seconds per render, on a runner with a
6 h budget, to draw a chain of labelled boxes for perhaps one item in ten. The Mermaid source is
still what gets persisted, so the record is portable and anyone can re-render it with the real
toolchain. What we decline to do is ship a browser to lay out six rectangles.

**Diagram drawing is off, on the measurement it was waiting for.** The doc used to say "diagram
drawing stays enabled until one run separates the three explanations - no exemplar in the prompt,
`min_diagram_steps` blocking short answers, or news items genuinely not being flowcharts." That run
landed. `32804437110` logs the draft kind beside the final kind: **17 chart drafts, 71 `none`
drafts, and 0 diagram drafts in 88 items.** The model is not asking for diagrams and our checks are
not rejecting them, so the first explanation is the live one - and the second and third cannot be
told apart without a prompt change nobody has a reason to make. Across 703 decided items on
2026-08-24/25 diagram drawing produced nothing at all. Meanwhile it was the reason the reachability gate
could never fire, which cost 46.9% of every day at 20.7 to 40.3 s an item.

So diagram drawing is switched off in `visuals.enabled_kinds`, and the contract default follows, because a
fresh clone should not pay for it either (Guardrail #6: the sane default is the measured one). Nothing
else changes: the `diagram` enum member, the Mermaid writer, the SVG layout and their tests all
stay, and `TestToDecision` keeps both cases on so the rejection paths and the injection canaries still
hold. Turning it back on is one word in `config/idhazh.json`. The prompt still describes diagrams;
it was left alone on purpose, because editing it changes the decode grammar and would invalidate
the 21 s and 40 s figures this whole page rests on. A draft that asks for one now folds to `none`
with a rationale naming the switch.

**This is a pause, not a descope, and the condition to reopen it is written down.** Authority:
Jony, 2026-08-25. Two things bring diagram drawing back together, never separately: a prompt carrying a diagram
exemplar that, measured offline against fixture articles, drafts diagrams at a rate surviving the
post-model checks - AND a hand-read sample showing those drafts carry an order the summary does not
already state. The first alone only proves a model will say "diagram" when asked to. The experiment
runs against fixtures, off the daily path, because on the daily path its bill is paid by readers:
every day it runs, the gate cannot fire and the planner spends the hour before publishing nothing.

**A day with no visuals says nothing to the reader.** Authority: Jony, 2026-08-25. "No picture" is
the normal answer for an item, so a day where the planner died reads exactly like a day where
nothing earned one, and both are honest. A line about our own missing machinery is the one thing on
the page a reader can neither verify nor act on. `items_failed` stays, because a missing story is
something the reader actually lost. The planner's failure belongs where an operator looks: the run
manifest's `items_routed` and `route_ms`, and the console.

**Why the budget became a stop rather than a louder warning.** `run.visual_planner_budget_minutes` already
existed and already logged when the stage went over. It fired after the fact, into a log nobody
reads until a reader notices a day with no pictures - and by then the run had already been
cancelled and had already binned its artifact. A warning that only ever describes a loss is not a
control. The same field then stopped the loop, which was the smallest change that made the job fit its
bound by design instead of by which host it drew (Guardrail #2). The knob retired with the stage on
2026-09-13.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Raise `visuals`'s `timeout-minutes` | The budget is the platform, not a preference (Guardrail #2). It also fixes nothing: the per-item cost doubles between runner hosts, so any bound is a coin toss until the work inside it is bounded. |
| Shard the `visuals` job across a matrix | **Unblocked on 2026-08-27 and still not built.** It was blocked on the asset name: a per-vertical counter seeded from the day's directory meant four shards would each read the same highest ordinal and two would write `energy-01.svg`, silently, long before any commit. Naming the asset from the item id removes that, so sharding is now an ordinary throughput change rather than a contract one - and it is the strongest lever left, because the stage spends its whole 40-minute budget on ten of the eleven runs on record. Nobody has measured what a sharded planner costs in cache restores and model loads against what it saves, and that measurement is the work. |
| Cap the number of items the planner may consider | A count has to be set for the worst host, so a fast host would decide 88 items and then idle for half an hour. The clock is the thing that runs out, so bound the clock. The same proposal moved back to the planning step was refused on 2026-08-25 for this reason and three more, including that it would delete about 436 items from a 731-item day - [../sources/freshness.md](../sources/freshness.md). |
| Give a budget-stopped item a `VisualDecision` saying so | It would land in `items_prefiltered`, which counts one specific cause, and it would freeze a `none` into the published day that a later run can never lift. Not writing a payload is what an unreached item already looks like. |
| A keyword pre-filter to rescue the diagram drawing | Fetched words would steer our control flow. Guardrail #11 in spirit, with no prompt involved. |
| Diffusion for charts | Produces a beautiful picture of a chart with hallucinated axis labels. |
| A charting library in the renderer | `vl-convert` took a spec to SVG with no browser and no runtime JavaScript. **Retired 2026-09-13**: the reader's browser draws the chart now, so there is no renderer for a library to be in. |
| `mermaid-cli` for diagrams | A headless Chromium to lay out a linear chain of boxes. |
| PNG or WebP for charts and diagrams | A bar chart is a dozen paths. The vector is smaller than any raster of it, stays sharp on a phone, and costs the retention budget less. Raster stays the right answer for a photographic image. |
| Keep `image` out of the enum until it is built | A payload must be able to say `image`, and the four-way vocabulary is a contract. The gate belongs in config, so switching it on is an edit rather than a schema change. |
| A funnel of bars for the four chart counts on the console | The stages fall by an order of magnitude - 88 reached, 47 asked, 17 drafted, 9 published on 2026-08-25 - so the bar the decision rests on is the one a reader can barely see. A table gives every stage the same weight. |
| A model filter or a model legend on the console Charts table | A filter over two values hides half the data and saves nobody any work. When a second model has run enough days to compare, the ledger it is read from has to be truthful first. |

## See also

- [visuals.md](visuals.md) - who decides a picture at all, and where the pass runs today.
- [where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md) - the drawing path that replaced all three renderers.
- [one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md) - the naming rule that unblocked sharding.
- [console.md](console.md) - the operator surface the Charts table sits on.
- [../sources/freshness.md](../sources/freshness.md) - the item cap this stage's budget was refused in favour of.
- [../../concepts/config/run-limits.md](../../concepts/config/run-limits.md) - the retired stage budget, and the job bounds that outlived it.
- [../../archive/measurements-2026-08.md](../../archive/measurements-2026-08.md) - the per-item costs every figure here rests on.
