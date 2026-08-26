# Visual routing and rendering

**Last Updated**: 2026-08-26

How an item gets a chart, a diagram, or - most of the time - nothing at all.

The rule this subsystem serves is in [`../../concepts/digest.md`](../../concepts/digest.md): a
visual must carry a fact the sentence beside it does not. A picture that decorates is worse than
no picture, because the product is trust and an invented axis label costs it permanently.

## The stage runs on its own model, in its own pass

Routing is a separate CLI stage from `work`, not a step inside it:

```
idhazh work  --date <D>    # the 8B summarizes
idhazh route --date <D>    # the 4B routes and renders
idhazh assemble --date <D> # the day payload picks up whatever routed
```

One llama-server serves one set of weights, and classification is the easy task, so the router
runs on Qwen3-4B while the summarizer keeps the 8B. Splitting the stage also means **a run that
never starts a router still publishes.** Every item simply carries no picture, which is already
the common and correct answer.

## The model never writes a number

This is the whole safety design, and it is structural rather than instructed.

1. The extractor pulls every quantity out of the article text with a regex, and gives each one an
   index and a unit.
2. The model is shown that indexed menu and asked to choose bars **by index**.
3. The spec is built here in Python from the chosen indices.

A chart value that is not in the article is therefore unreachable, not merely unlikely. The Row #8
oracle - "every value in a rendered chart is present in the source article" - is a property of the
shape rather than a hope about the prompt, and the test asserts it directly.

## What the extractor drops, and why

| Dropped | Reason |
| --- | --- |
| A bare four-digit integer in 1900-2100 with no unit | It is a year. A year is a label, not a bar height. Dropping it costs nothing, because a label is a free string the model can still write. |
| A number preceded by a hyphen after a word character | `COVID-19`, `GPT-4`, `Qwen3-4B`. Identifiers, not quantities. |
| A magnitude of a bare `m` or `k` | `15 m` is fifteen metres or fifteen million. The model never writes a number, but the extractor does, and a guess here is a one-million-fold error on a published bar. The spelled-out words and the unambiguous `bn`/`mn`/`tn` are kept. |
| Anything at or below 2 with no unit | A list marker. `2 percent` keeps its unit and survives. |
| A repeat of the same value **in the same unit** | One figure quoted in a lead and a body paragraph is one fact. Twelve percent and twelve people are two. |

The menu is capped at `visuals.max_facts` (default 16). A long indexed list is lost-in-the-middle
for a small model choosing an integer.

## The model is not asked a question already answered

A published bar is `facts[i]` for some `i`. Every bar in a chart shares one unit, one quantity may
fill only one bar, and a chart needs at least `visuals.min_chart_points` of them. So the widest
chart an article can carry is the size of the largest unit group in its own numbers. Below that
threshold the answer is `none` whatever the model replies.

`reachable_kinds()` computes that before the request is built. When no enabled kind survives it,
the router writes a `Route` with `kind: none`, `asked_the_model: false`, and a rationale that says
the model never ran. The run manifest counts those separately as `items_prefiltered`.

Three properties of how it is written, and each one is load-bearing:

- **It is a predicate over every enabled kind, not a chart special case.** A diagram's steps come
  from prose, so nothing about a diagram is decidable in advance and it is always reachable while
  enabled. With `diagram` in `visuals.enabled_kinds` **no item is ever skipped** - measured at 145
  of 145 asked on 2026-08-25. That is why the arm now ships off (below): the gate cannot fire
  underneath it, and turning it back on stays a config edit somebody makes on purpose.
- **It reads the facts only - never the article's words.** A predicate that branched on fetched
  prose would let a stranger's page steer our control flow, which is Rule #11 with no prompt in
  sight. There is no keyword rescue for the diagram arm for the same reason.
- **The empty string is a unit group.** `numeric_facts` writes `""` when nothing after the number
  reads as a unit, and `same_unit_bars` already groups on it. Excluding it here would gate items
  that publish today.

With the arm off, measured on the 145 items of run `32804437110` with no model and no network:
**68 items (46.9%) never reach the model**, and 77 do. The histogram of widest unit group per
article is in [`../../reference/measurements.md`](../../reference/measurements.md).

The denominator moves when this is on: the same charts sit over a smaller routed set, so a chart
rate quoted against `items_routed` alone climbs without a single extra chart existing. Quote it
against `items_routed + items_prefiltered`, or state which one you meant.

## The stage stops itself before the job does

The stage's wall-clock is `items with an OK summary x per-item cost`, and neither factor was
bounded. The first is set by how well the summarizer did, up to `run.safety_ceiling_per_run`
(200). The second is set by whichever host the runner gave us: measured mean **20.7 s on a fast
host and 40.3 s on a slow one**, over six runs and 703 items on 2026-08-24/25. A 145-item day
therefore needs anywhere from 50 to 97 minutes against a 50-minute job.

What happened when it went over is the part that made the defect invisible. A job cancelled at its
timeout **skips any step without an explicit condition**, and the `routes` artifact upload was one
of those. So the run threw away every decision the hour had bought - on 2026-08-25 that was 88
routed items and 9 rendered charts - and `assemble` published 145 items with zero visuals and no
error anywhere on the page. The day cannot recover: `build_day` keeps an already-published item,
so the four later runs of that day re-route the same items at full price and their answers are
discarded.

Three things changed, and each one addresses a different link in that chain:

| Change | What it stops |
| --- | --- |
| `stage_route` stops at `run.route_budget_minutes` (40) | The job is never cancelled, so it always reaches its upload step. |
| The `routes` upload runs on `always()` | Even a job cancelled for some other reason hands over what it made. |
| `visuals.enabled_kinds` drops `diagram` | 46.9% of the day stops reaching the model at all, so far more items fit inside the same budget. |
| The router skips what the day already published | Runs 2 to 5 stop re-deciding run 1's items for an answer the assembler discards. |

**The router visits the best story first.** The plan is vertical-major, so stopping part-way down
it would cost whole verticals their pictures while the weakest story in the first vertical kept
one. `routable_items` sorts by `rank_score` before the loop, which is the rule
`_within_ceiling` already follows for the safety ceiling: drop the weakest stories across every
vertical, never a suffix.

**The router skips an item the day's committed digest already carries.** `build_day` keeps an
already-published item and discards the new run's copy, because the reading order is part of what a
shared link shows. So a later run's decision for one of those items is computed, written, read back
and thrown away. A day runs five times: without the skip, run 2 spends its whole budget re-deciding
run 1's items at 20 to 40 measured seconds each, and the items it actually introduced queue behind
them. This is the resumability invariant the rest of the pipeline already holds - a re-run costs
only the unfinished items - applied to the one stage that did not. It reads the committed
`digest.json` the same way the asset counter reads the committed directory, so it needs no handshake
with the assembler.

The corollary is worth stating plainly: **an item published without a visual can never gain one.**
That is a property of `build_day`, not of the router, and it is why a run cancelled at the bound
cost its day permanently rather than for one run. Changing it means letting a later run mutate a
published item, which is a decision about the day payload rather than about the router.

**An item the stage never reached writes no payload.** That is the same fact `items_routed` already
reports - "items the router reached" - and it is what an item looks like today when the router
never starts. A budget stop is the stage stopping, not a decision about an item, so it does not
borrow `asked_the_model` and does not move `items_prefiltered`, which counts one specific cause.
The run log names the count and the mean that produced it.

The job's `timeout-minutes` is 50 against a 40-minute stage budget. It is the backstop, not the
budget, and the 10 minutes between them are the fixed cost the stage clock never sees - checkout,
weights, install, model start. Both numbers came down together on 2026-08-25, because a job bound
20 minutes above the stage bound is 20 minutes in which a stuck stage burns runner wall-clock past
its own limit. Raising either one is the move Rule #2 forbids.

**The chart arm has a kill line, registered before the data was read.** Authority: Jony,
2026-08-25. Over 14 consecutive days with the chart-only gate on, retire the arm if the median day
publishes a chart on fewer than 5% of published items, or spends more than 6 router minutes per
published chart. Either limb trips it. A day stopped at the budget still counts. Measured
2026-08-25 on `ubuntu-latest` (4 vCPU, 16 GB): 6.2% and 4.4 minutes - inside the line on both
limbs, which is why the arm ships. Writing the line down first is what stops the number being
argued after it is seen.

`charts_drafted` on the run manifest is what makes that reading possible. It counts the items whose
routing reply asked for a chart, whatever the decision became, so the gap between it and the day's
published charts is exactly what the two controls below rejected. Without it a model that stops
asking for charts and checks that start refusing them are the same number.

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
| Router minutes | `route_ms` summed over the runs that recorded one, in minutes. |
| Minutes per chart | Router minutes divided by charts published. |

The two gaps are the point. Reached against asked is the reachability gate above, running before any
request. Drafted against published is the two post-model controls. A single funnel of bars would
make the last stage the shortest and hardest to read, and the last stage is where the decision sits -
so it is a table.

**A number that does not exist prints a dash, never a zero.** A day whose route job never ran
reached zero items, which is a measurement and prints as `0`. It spent no measured minutes, which is
not the same as spending none - `route_ms` is null on that manifest, and `0.0` there would read as a
router that was free. A day with no published chart has no per-chart cost, so that cell is a dash
too rather than an infinity or a zero.

**Zero reached and a day older than the counts read the same, on purpose.** `items_routed`,
`items_prefiltered` and `charts_drafted` all default to zero on a manifest written before they
existed, so a day from before 2026-08-24 prints zero reached beside the charts it really published.
That is the honest reading: nothing committed says what its router did. It also means a day before
the counts existed cannot enter the kill line's fourteen-day window, which is correct - the window
starts when the chart-only gate went on, and the gate and the counts landed together.

**No rate is stored.** `Minutes per chart` is two committed numbers divided at read time. A
persisted rate is a third fact that can disagree with the two it came from, and the console's whole
claim is that every figure on it was written down when the run happened.

**Charts published is counted from the payload, not from the manifest.** The manifest records what
the router decided; the payload records what a reader can see. A chart whose render failed, and a
diagram, are both visuals and neither is a published chart - counting visuals instead would put the
diagram arm's output on the chart arm's bill.

## Two controls that run after the model has answered

**Bars must measure the same thing.** The largest group of chosen bars that share a unit is kept
and the rest are dropped. This never invents a bar and never mixes units; it only ever removes. If
what remains is below `visuals.min_chart_points`, the item routes to nothing.

**One quantity may fill one bar.** A draft that names the same `fact_index` twice routes to
nothing. Without this the model can name index 3 three times, `same_unit_bars` groups all three
under one unit, the width check passes, and a chart of one number under three invented labels
publishes - every value true and the comparison fabricated. It is also what makes the reachability
predicate above exact rather than approximate.

**A caption written about dropped bars is discarded.** If any bar was removed, the model's caption
described a chart that no longer exists.

## Rendering runs without a browser

| Kind | Persisted spec | Renderer |
| --- | --- | --- |
| `chart` | Vega-Lite JSON | `vl-convert`, the Vega toolchain compiled as a Rust extension |
| `diagram` | Mermaid source | ours, about a hundred lines of SVG layout |
| `image` | - | **descoped 2026-08-23 on measurement.** Unreachable: `visuals.enabled_kinds` does not name it. |

**Why there is no image renderer.** Measured on `ubuntu-latest` (4 vCPU, 16 GB),
2026-08-23, run `32654562728`: `Tongyi-MAI/Z-Image-Turbo` at bfloat16 loads in
159.2 s at 9.2 GB resident, then spends **527 s per denoising step** at 512x512.
Nine steps is about **79 minutes for one image** - longer than the whole `route`
job's 60-minute bound, and about 196 hours for a 149-item day against a 6-hour
job limit. The job was cancelled at step 7 of 9 and never reached 768px or a byte
count. The plan's second candidate, `alpha-vllm/Anima-2.9B`, answers 401
Repository Not Found: it does not exist. Reducing steps does not rescue it -
three steps is still 26 minutes, and one step is noise. Rule #2 says the budget
is the platform, so the feature goes rather than the budget. The `image` member
stays in the enum because a payload must be able to say it; the config gate is
what makes it unreachable.

Both write SVG into `frontend/public/digest/<YYYY>/<MM>/<DD>/<vertical>-<NN>.svg`, beside the
payload that references them. A render failure records why and the item publishes without a
picture. No failure path raises.

**The number continues across a day's runs.** A day runs several times, and a per-process counter
that restarts at 1 makes the second run overwrite the first run's file while the digest still
references both items. That happened on 2026-08-24: 32 declared visuals over 18 files, fourteen
paths claimed twice, and `india-01.svg` shared by a stock-market story and a defence-stocks story -
so one of them showed a chart of the other's numbers under alt text describing figures that were
not in the picture. The router now seeds each vertical's counter from the highest `<vertical>-<NN>`
already on disk for that day.

**Seeding from disk answers one run at a time, and two runs of a day overlap.** A run takes about
three hours and the day is refreshed five times, so a second run is routing while the first is still
summarizing. Neither checkout can see what the other has not pushed yet, so both read the same
highest ordinal and both write `energy-03.svg` for different items with different bytes. The router
never finds out. The push does: run `32869125768` finished eight workers and a router, then lost the
whole day at the commit step on `CONFLICT (add/add)` over four asset paths, because git cannot
rebase two adds of one path. Every summary in the day expired with the `items-*` artifacts.

**The tip's chart never moves; this run's does.** Before each rebase attempt the commit step lists
the asset paths the tip already publishes and hands them to
[`backend/utilities/renumber_racing_assets.py`](../../../backend/utilities/renumber_racing_assets.py).
Any local file standing on one of those paths is moved to the next free `<vertical>-<NN>` for the
day - free against both sides at once, not one past the highest of whichever side was read - and the
route payload that names it moves with it. The rebuild then re-reads the routes, so the `digest.json`
that lands names a file that is really in the tree. A published address is one a reader may already
hold, which is why the side that has never been published is always the side that gives way.

Measured 2026-08-22 (Windows 11, 8 vCPU, `vl-convert-python` 1.9.0.post1): a Vega-Lite render takes
2568 ms for the first call in a process and 49 ms warm, and produces about 7 KB of SVG. The cold
cost is engine boot, paid once per run rather than once per item.

## Design rationale

**Why the model picks an index instead of writing a spec.** The obvious design is to ask the model
for a Vega-Lite object. It is also the design where a hallucinated axis value is one sampling
accident away, and where the only defence is checking the output against the article afterwards -
a check that has to parse an arbitrary spec and decide which of its numbers are data. Indices
invert that: the model's entire numeric vocabulary is `0..len(facts)-1`, a bound check is two
lines, and the property holds for specs nobody has thought of yet.

**Why our own SVG for diagrams rather than Mermaid's own renderer.** `mermaid-cli` drives a
headless Chromium. That is roughly 300 MB of install and seconds per render, on a runner with a
6 h budget, to draw a chain of labelled boxes for perhaps one item in ten. The Mermaid source is
still what gets persisted, so the record is portable and anyone can re-render it with the real
toolchain. What we decline to do is ship a browser to lay out six rectangles.

**Why every field of the model's reply is required, including the empty ones.** A field with a
default is absent from the schema's `required` list, and a constrained decoder emits exactly what
`required` forces. On the first live run the model returned a confident `kind` of `chart` with no
bars in it, twice, because `points` was optional. Required-and-empty is the honest shape.

**Why `reason` is decoded before `kind`.** Pydantic emits properties in declaration order and
llama.cpp builds its grammar in that order, so **field order is decode order**. With `kind` first
the model committed to an answer and then filled `reason` by copying the prompt's own rules back -
observed live, verbatim. With `reason` first, one plain sentence about the item grounds the choice
that follows.

**Why the prompt states no base rate.** The first prompt said "Almost always it does not", "the
right answer roughly two times in three", and "When in doubt, choose none". At `temperature=0`
there is no sampling to recover from a shifted argmax, so a stated prior becomes a deterministic
flip rather than a nudge. The rewrite keeps `none` as the common answer by making it the terminal
branch of an ordered test, which reaches the same place without leaning on the logits.

**Why the feed floor of one prompt rule became two code controls.** "Do not chart a year" and "do
not chart quantities that measure different things" were requests. A request is negotiable by a
4B reading an article that mentions years. Both are now enforced - the first in the extractor, the
second after the model answers - and the prompt is shorter for it.

**Why the router skips a call rather than running faster.** Measured 2026-08-24 on `ubuntu-latest`
(run `32742672105`): 47 s of fixed cost, a 3155 s stage, 149 items at a mean of 21.0 s each, and 15
charts out of 149. Nine calls in ten produced nothing. Removing a call whose outcome is decided is
not an optimisation of the model; it is deleting work that could not have mattered. Everything else
on the table either hid the cost or raised the budget.

**Why a skipped item still writes a payload.** Silence is what turns a skip into a quiet descope.
`asked_the_model: false` plus a rationale naming the reason means a later reader of the payload does
not have to infer why an item has no picture, and `items_prefiltered` keeps the day's chart rate
from climbing on arithmetic alone.

**The gate is proved by exhaustion, not by sampling.** `test_the_gate_never_rejects_a_chart_the_model_path_would_publish`
enumerates every distinct index subset a draft could name over a fact list the gate calls
unreachable, and asserts `to_route` lands on `none` for all of them. One survivor would mean the
gate drops a chart a reader would have seen. That test is what makes "provable" a true word here,
and it only became true once one quantity was limited to one bar.

**The diagram arm is off, on the measurement it was waiting for.** The doc used to say "the arm
stays enabled until one run separates the three explanations - no exemplar in the prompt,
`min_diagram_steps` blocking short answers, or news items genuinely not being flowcharts." That run
landed. `32804437110` logs the draft kind beside the final kind: **17 chart drafts, 71 `none`
drafts, and 0 diagram drafts in 88 items.** The model is not asking for diagrams and our checks are
not rejecting them, so the first explanation is the live one - and the second and third cannot be
told apart without a prompt change nobody has a reason to make. Across 703 routed items on
2026-08-24/25 the arm produced nothing at all. Meanwhile it was the reason the reachability gate
above could never fire, which cost 46.9% of every day at 20.7 to 40.3 s an item.

So the arm is switched off in `visuals.enabled_kinds`, and the contract default follows, because a
fresh clone should not pay for it either (Rule #6: the sane default is the measured one). Nothing
else changes: the `diagram` enum member, the Mermaid writer, the SVG layout and their tests all
stay, and `TestToRoute` keeps both arms on so the rejection paths and the injection canaries still
hold. Turning it back on is one word in `config/idhazh.json`. The prompt still describes diagrams;
it was left alone on purpose, because editing it changes the decode grammar and would invalidate
the 21 s and 40 s figures this whole page rests on. A draft that asks for one now folds to `none`
with a rationale naming the switch.

**This is a pause, not a descope, and the condition to reopen it is written down.** Authority:
Jony, 2026-08-25. Two things reopen the arm together, never separately: a prompt carrying a diagram
exemplar that, measured offline against fixture articles, drafts diagrams at a rate surviving the
post-model checks - AND a hand-read sample showing those drafts carry an order the summary does not
already state. The first alone only proves a model will say "diagram" when asked to. The experiment
runs against fixtures, off the daily path, because on the daily path its bill is paid by readers:
every day it runs, the gate cannot fire and the router spends the hour before publishing nothing.

**A day with no visuals says nothing to the reader.** Authority: Jony, 2026-08-25. "No picture" is
the normal answer for an item, so a day where the router died reads exactly like a day where
nothing earned one, and both are honest. A line about our own missing machinery is the one thing on
the page a reader can neither verify nor act on. `items_failed` stays, because a missing story is
something the reader actually lost. The router's failure belongs where an operator looks: the run
manifest's `items_routed` and `route_ms`, and the console.

**Why a colliding chart is renumbered rather than merged, refreshed or picked between.** The three
cheaper-looking answers all publish a wrong picture instead of failing, which is worse than losing a
day because nobody finds out. Adding the day's directory to `REFRESH_PATHS` makes the rebuild's
hand-back delete every chart this run added that the tip lacks, while the regenerated `digest.json`
still names them - `assemble` copies the path from the route payload and cannot render anything - so
the day publishes with broken images. It also overwrites the colliding file with the tip's bytes,
which is the 2026-08-24 defect above, restored: one story's picture under another story's alt text.
Resolving the add/add by a stated side has the same two outcomes and no third one; `-X theirs` gives
our item the tip's picture, `-X ours` overwrites an asset a reader may already hold. Renumbering is
the only option where both runs' charts survive and every path in the published day resolves.

**Why the move happens in the shell's retry loop and not inside `assemble`.** The rebase is what
fails, and it runs before `REGENERATE_COMMAND` does, so a fix that runs after it never gets to run
at all. The naming rule itself stays in `backend/idhazh/render/write.py`, which owns it: the shell
lists paths and pipes them, and a small argv wrapper under `backend/utilities/` does the arithmetic
and rewrites the JSON. Bash never learns what `<vertical>-<NN>` means (Rule #3).

**Why the budget became a stop rather than a louder warning.** `run.route_budget_minutes` already
existed and already logged when the stage went over. It fired after the fact, into a log nobody
reads until a reader notices a day with no pictures - and by then the run had already been
cancelled and had already binned its artifact. A warning that only ever describes a loss is not a
control. The same field now stops the loop, which is the smallest change that makes the job fit its
bound by design instead of by which host it drew (Rule #2).

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A funnel of bars for the four chart counts on the console | The stages fall by an order of magnitude - 88 reached, 47 asked, 17 drafted, 9 published on 2026-08-25 - so the bar the decision rests on is the one a reader can barely see. A table gives every stage the same weight. |
| A model filter or a model legend on the console Charts table | A filter over two values hides half the data and saves nobody any work. When a second model has run enough days to compare, the ledger it is read from has to be truthful first. |
| Ask the model for a Vega-Lite spec directly | A fabricated axis value becomes reachable, and verifying it afterwards means parsing an arbitrary spec to work out which numbers are data. |
| Raise `route`'s `timeout-minutes` | The budget is the platform, not a preference (Rule #2). It also fixes nothing: the per-item cost doubles between runner hosts, so any bound is a coin toss until the work inside it is bounded. |
| Shard the `route` job across a matrix | Still the strongest remaining lever, and still blocked on the same thing. Asset filenames come from a per-vertical counter seeded by reading the day's directory, so four shards would each read the same highest ordinal and two would write `energy-01.svg` - the exact collision fixed on 2026-08-24, reintroduced fourfold. The 2026-08-25 renumbering does not unblock it: that runs once, at the commit step, against paths the tip already publishes, and four shards collide inside one run when their artifacts unpack over each other - long before any commit, and silently. Sharding needs the published asset path to come from the item's own identity first, and that is a published-payload change. Take the budget stop now, measure again, shard if a day still cannot finish. |
| Name the asset from the item's own identity, `<vertical>-<url_key prefix>.svg` | The full fix. It removes the counter, so no two runs and no two shards can ever choose one path, and it is what sharding is waiting for. It is also a published-payload change to a shape [`layout.md`](layout.md) states deliberately - no hash appears in any path, filename or URL - so it is CLAUDE.md section 6 Level 5 and belongs to the owner, not to a defect fix. Escalated 2026-08-25, not shipped. |
| Add the day's directory to `REFRESH_PATHS` | The hand-back deletes what the tip lacks and restores what it has, so this run's own charts are deleted while the rebuilt `digest.json` still names them, and the colliding one comes back with the other story's bytes. A broken image and a wrong image, published, instead of a job that failed loudly. |
| Resolve the add/add with `-X ours` or `-X theirs` | `theirs` puts the tip's picture under our alt text; `ours` overwrites an address a reader may already hold. Neither side of a coin flip is a correct answer to "whose chart is this". |
| Cap the number of items the router may consider | A count has to be set for the worst host, so a fast host would route 88 items and then idle for half an hour. The clock is the thing that runs out, so bound the clock. |
| A `skip_unreachable` config flag | A knob whose `false` setting means "spend 21 measured seconds proving a theorem you already proved". Nobody would set it. The predicate is derived from `min_chart_points` and `enabled_kinds`, which are already config. |
| Give a budget-stopped item a `Route` saying so | It would land in `items_prefiltered`, which counts one specific cause, and it would freeze a `none` into the published day that a later run can never lift. Not writing a payload is what an unreached item already looks like. |
| A keyword pre-filter to rescue the diagram arm | Fetched words would steer our control flow. Rule #11 in spirit, with no prompt involved. |
| A second, smaller model to triage items first | Two calls where the point was zero. |
| Diffusion for charts | Produces a beautiful picture of a chart with hallucinated axis labels. |
| A charting library in the renderer | `vl-convert` takes a spec to PNG or SVG with no browser and no runtime JavaScript. |
| `mermaid-cli` for diagrams | A headless Chromium to lay out a linear chain of boxes. |
| PNG or WebP for charts and diagrams | A bar chart is a dozen paths. The vector is smaller than any raster of it, stays sharp on a phone, and costs the retention budget less. Raster stays the right answer for a photographic image. |
| Discard the whole chart when one bar disagrees on units | Observed live: the model picked three correct year-on-year megawatt bars and appended the sector headcount. Three good bars thrown away to reject one bad one. |
| Route on the 8B | Classification is the easy task. The big model belongs on summarization, and a second set of weights would not fit the pass anyway. |
| Keep `image` out of the enum until it is built | A payload must be able to say `image`, and the four-way vocabulary is a contract. The gate belongs in config, so switching it on is an edit rather than a schema change. |

## See also

- [`../../concepts/digest.md`](../../concepts/digest.md) - the visual rule this serves.
- [`../../reference/github-actions.md`](../../reference/github-actions.md) - the commit loop that renumbers a raced chart.
- [`../sources/trust-boundary.md`](../sources/trust-boundary.md) - why article text is data.
- [`../contracts/determinism.md`](../contracts/determinism.md) - why decoding is pinned in one place.
- [`../../concepts/evaluation.md`](../../concepts/evaluation.md) - how a stage gets measured.
