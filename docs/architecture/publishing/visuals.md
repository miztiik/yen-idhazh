# Visual planning and rendering

**Last Updated**: 2026-11-18

How an item gets a numeric chart or - most of the time - nothing at
all: which pass decides, which gate refuses, and what every refusal is called.
The rule this subsystem serves is in
[the visual rule](../../concepts/digest.md#the-visual-rule): a supported comparison
or relationship must become quicker to grasp than prose alone. Facts already
in the summary are not disqualified, but decoration earns no space and every
source-evidence and qualification check still applies.

This page holds the decision path end to end, and the drawing of it. Each step
along that path is written up on a page of its own, and the table below routes.

## Where each step is written up

Six pages, one question each. Arrive at the one holding your question and stop.

| Page | The question it answers |
| --- | --- |
| this one | Which pass decides a visual, which gate refuses, and what every `none` is called |
| [what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md) | How a chart answer becomes a plan, the eleven checks it must clear, and the ladder a refused plan may step down |
| [where-every-drawn-figure-came-from.md](where-every-drawn-figure-came-from.md) | This number is on a bar - is it the article's own characters, or arithmetic over them, and what chain proves it |
| [where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md) | Who renders the chart, what its compiler publishes, and what a reader receives |
| [one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md) | What the file is called, and what happens when two overlapping runs write it |
| [what-drawing-costs-and-what-has-been-retired-for-it.md](what-drawing-costs-and-what-has-been-retired-for-it.md) | What drawing has cost, what has already been retired for costing too much, and where the line is read from |

## One model, one pass, inside `work`

There is no separate visual stage and no second model:

```
idhazh work --date <D> # one call an item: the summary and the answer about a chart
idhazh assemble --date <D> # the day payload picks up whatever was drawn
```

The same model writes the summary and decides whether a chart would help, which
form to use, and which readings fill its roles. `work` resolves the answer
against the article and compiles chart data while it still holds the text.

The shared system turn joins the separately configured
`write_digest_summary` and `plan_visual` files; the later `continue_summary`
turn reads its own file from the same selected config root. Their paths and
rendering rules belong to [the prompt page](../summarize/prompt.md).

The request shows [independent source readings](../summarize/prompt.md#the-model-is-shown-independent-source-readings)
after the article. Its grammar admits `none` and the operator-enabled numeric
forms the renderer supports. The capability list does not recommend a form for
an article. The
[compiler capability table](where-a-drawing-becomes-pixels.md#declared-types-are-not-delivery-promises)
names the abandoned forms retained only for historical reading.

**It was two stages on two models until 2026-09-13.** `idhazh visuals` ran a Qwen3-4B after the
summarizer had finished, decided a picture from the summary, and rendered it in a job of its own.
Plan 11 row #6 deleted that stage, the job, the model and the flag that switched between the two
paths, in one commit (maintainer ruling 2026-09-13: move forward, no rollback). The reason the pass
moved is that a second pass decides from a **summary of** the article rather than from the
article, and both payloads validate - so nothing would say it had happened. What that stage cost
while it ran is in
[what-drawing-costs-and-what-has-been-retired-for-it.md](what-drawing-costs-and-what-has-been-retired-for-it.md).

Two things follow from `work` being the job that draws. It is sharded four ways, so four runners
render a quarter of the day each instead of one runner rendering all of it against a budget; and
the file a shard writes stays on its runner, which is thrown away. What reaches `assemble` is the
decision inside `items-<n>`, and a rendered decision carries the chart's bytes in `spec` - the
same string the shard wrote to its file. `assemble` positively selects chart
decisions and writes their files before recording the day, without replacing
a file already present. Retired visual kinds produce no view or asset; their
historical outcome metadata remains unchanged. Until 2026-10-04 each shard also uploaded its whole
day directory as `shard-visuals-<n>` and `assemble` merged the four into its own. In run
`37212772816` two of them carried a newer `digest.json` than the other two, and the merged file
could not be read. No job hands a file under `frontend/public/` to another job now.

**The flag is the first of two commits** (plan 11 rows #5b and #6). The second deletes the flag,
the small model, this stage and its job together. Until then the flag off leaves the pipeline
exactly where it was.

**Numeric charts cross the actual worker and assembly boundary in tests.**
`test_assemble_publishes_a_chart_from_its_decision_alone` runs
the production call against a local boundary reply. Real extraction and anchoring finalize
the evidence; the actual request must show the readings and admit their
references. Only named serialized article, summary, decision and item-health
outputs, plus their input fingerprint, cross into a fresh publisher tree.
Neither the worker's public directory nor its captures cross.

Ordinary `stage_assemble` must recreate the named asset from those outputs.
The test checks its exact worker bytes, the digest reference and the
publication inventory, then feeds those published bytes to the actual
TypeScript reader guard. A legitimate declining boundary answer separately
keeps its summary publishable, records `model_declined` and publishes no visual.
Removing the numeric assembly writer or rejecting the compiler's payload in the
reader breaks this coverage.

The existing reader journey uses compiler-produced numeric canaries with a
plain item beside them. It checks served asset bytes, then exercises missing
and empty numeric responses without losing the story, followed by recovery on
reload. Navigation/reload retains the numeric observer lifecycle regression
coverage. These are deterministic transport and rendering
checks, not evidence that the current model generates useful plans.

`tests/fixtures/pages/wind.html` supplies four comparable readings.
`summarize-and-plan/wind-summary-and-plan.json` cites those readings and copies
their country labels. An extractor or reference change that moves or drops a
reading turns the test red rather than quietly turning the picture off.

**Generation and normal publication require separate observations.** Retain
the actual call for named warranted numeric chart examples and a
legitimate no-visual example, using the committed model and production path.
Record the code revision, model identity, source inputs and runner conditions
beside the captured requests, replies, decisions and resulting named assets.
Recorded or authored replies, an old capture, a forced type and a successful
summary cannot establish present-day generation. A warranted example that
still declines or malforms remains an unresolved defect, not a restored
capability.

After producer delivery, inspect a normal scheduled Content refresh run's
actual source revision, decisions, assets, digest, inventory and served day.
The [Pipeline tests workflow](../../reference/github-actions.md#pipeline-tests)
can show production execution but publishes no reader-facing day. Do not
repeatedly dispatch a production writer to turn this observation into a merge
gate.

## The model never writes a number

This is the whole safety design, and it is structural rather than instructed.

1. Code cuts quantity and date spans, then anchors the mentions the text-analysis
   service returned against the same article text.
2. The model chooses a form and cites numeric readings, dates and short label
   phrases as needed. Its chart prose contains no digits.
3. Code checks the references, re-slices labels, and builds and validates the
   plan before compiling the chart. Any derived value
   is arithmetic over source-backed elements through the closed, provenance-
   carrying rules in [where every drawn figure came from](where-every-drawn-figure-came-from.md).

A model-authored value is therefore unreachable, not merely unlikely. A chart
may show a derived value that is not literal source text only when code computes
it from those elements and preserves its provenance. The source-or-derived
boundary is a property of the shape, not a hope about the prompt.

What the extractor refuses to turn into an element in the first place, and what the four functions are
that may reach a number the article did not write, are in
[where-every-drawn-figure-came-from.md](where-every-drawn-figure-came-from.md).

## The gate suppresses the question and never skips the call

The chart question is left off only when no numeric form is enabled and
supported, fewer than two quantities were found, or the data references do not
fit beside the article. The request keeps the same model, response budget and
cached prefix; only the trailing data and the grammar's `visual` field go
away. Compatibility and the configured mark count are checked after the model
chooses a chart, not used to screen articles for comparability.

## Every `none` says which gate refused it

`none` is the majority outcome by design - two items in three - so a `none` with no cause makes the
largest number an operator reads the one that explains nothing, and no gate can be retired, tuned or
shown to work. `VisualDecision.none_reason` is a typed enum rather than a sentence in `rationale`,
because a console counts members and cannot count prose.

| Member | The route it names |
| --- | --- |
| `not_reachable` | No chart data references were sent. The call still wrote the summary. Between 2026-11-18 and this change, the gate checked for a table of names and figures. Earlier rows meant no choice over the elements could have validated. |
| `model_declined` | The model was asked and answered `none`. The ordinary answer, and the one the design wants to stay common. |
| `validation_failed` | A plan was drafted, the validator refused it, and the ladder reached no depth that validates. |
| `output_budget_cut` | The reply ran out of output budget after the summary closed, so the plan was never written. The item publishes; the picture is what was lost. |
| `window_exhausted` | The prompt filled the context window, so the plan was cut before it was written. |

**One member per gate, never one per call site.** The gate that leaves the question about a
chart off the request records `not_reachable` wherever it fires, because
what an operator acts on is the gate rather than the line of code. And **which** check refused is
`ValidatorCheck`'s to say: one fact with two homes is a fact that can disagree with itself.

`validation_failed` means a plan was drafted and this build refused it. Its
`rationale` distinguishes invalid evidence, an unsupported compiler, an
unselected request, an answer about a chart that breaks one of its own rules and
a replacement that cleared no measured floor. The
summary remains publishable. `rejection_reason` records the first
`ValidatorCheck` that rejected the original request, and remains on the
decision if a replacement is later selected or refused. It stays null when
the original request passed validation. A shape, configuration or compiler
refusal does not create a rejection, but does not erase one already recorded
for the original request.

An invalid plan keeps its first native field and rule in the bounded,
sanitized `rationale` and the item-health `failed_field` and `failed_rule`
cells. The [plan's cross-field rules](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md#the-plan-a-compiler-draws-from-and-the-four-things-it-may-not-carry)
supply those details directly; recording never parses an English message.
An answer that breaks one of [its own rules](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md#a-chart-answer-becomes-a-plan-in-code)
is recorded the same way, as `visual.focus` and `visual_choice_focus_required` for an answer
with no row.
Rejected values, unknown input keys and article text are not diagnostics.
A successful item-health row keeps `detail` null: its visual refusal does not
make the summary a failure.

The final `VisualDecision` records the original `planned_type` and the
successfully written `rendered_type` separately. `downgrade_depth` is zero
without a selected replacement and positive after one is selected, even if its
later write fails. `deepest_downgrade_depth` records the deepest rung reached
even when no replacement is selected; it is the attempt depth used by
`VisualAttemptRow`, and is distinct from the selected depth above.
`gate_floor_applied` is true if a numeric mark-count floor excluded a
replacement candidate, false if numeric floors were compared but excluded
none, and null if no numeric floor was compared. `marks` counts delivered
marks, not the flat mark pool. Without successful delivery, the delivered type
and mark count are null. Untyped requests and older unmeasured outcomes leave
the new evidence fields null; never infer an old request from its final drawing.
Only a valid native plan establishes the requested type. A contradictory
decline or malformed JSON cannot establish it, even if its raw bytes name a
type.

The worker projects the requested type, delivered type, selected depth, marks
and identity into its sealed item record before either completion path. The
full decision remains in the item's visual-decision payload, including the
first rejection and deepest rung needed to record an attempt without parsing
`rationale`. The record stage writes the item-health row through
`state/raw/item-health/`; its compactor later writes the corresponding
`state/compact/item-health/` files.

The shard's `visual_outcomes` report counts requested types and computes
`wasted_decode_rate`: measured typed requests not delivered in their requested
form divided by all measured typed requests. Both a different delivered type
and no delivered type count. Thus a safe replacement still records demand for
the missing requested form, not a quality failure in the replacement. The
result is a fraction, not a token-weighted cost; no measured request gives
null, not zero. Declines, suppressed or unparseable requests and historical
unknown outcomes do not enter its denominator. The stored item rows preserve
the inputs, not a second copy of the derived rate.

**Five members, because five routes have writers.** No chart question, model decline,
drafted-plan refusal, output-budget cut and context-window cut each have a
producer. A proposed gate without a writer gets no member. The oracle holds the
enum to that: every route is driven from its own fixture and the set collected
must equal the enum exactly.

The retired single-call planner writes null. Its causes are sentences in
`rationale`, and several - no summary to illustrate, a reply that lost its
shape, a kind with no renderer - are not gates at all. A payload written before the field existed writes null for the same reason, and
that is the honest reading: nothing committed says which gate refused it.

## The whole flow, drawn, so nobody has to infer it again

**This is the current path from article text through extraction and visual
planning to the reader.** The
[extraction page](../extraction/elements.md) defines how source-backed elements
are found, labelled and anchored. **A box carries a name and the one assertion
an arrow cannot carry**, and every field list lives in the table below, keyed by
node id.

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontSize":"15px","fontFamily":"ui-monospace, SFMono-Regular, Menlo, Consolas, monospace","background":"#ffffff","mainBkg":"#ffffff","edgeLabelBackground":"#ffffff","labelBackground":"#ffffff","textColor":"#0b1020","titleColor":"#0b1020","nodeTextColor":"#0b1020","secondaryTextColor":"#0b1020","tertiaryTextColor":"#0b1020","lineColor":"#6e7781","primaryColor":"#eef2ff","primaryBorderColor":"#4c6ef5","primaryTextColor":"#0b1020","clusterBkg":"#f8f9fb","clusterBorder":"#c3c8d0"}}}%%
flowchart TD

  subgraph BE["BUILD TIME - the pipeline, in CI.  NOTHING IS DRAWN HERE."]
    direction TB
    ART["<b>ARTICLE</b><br/>sanitized text; every span indexes these bytes"]
    CP["<b>CANDIDATE PASS</b> - code<br/>finds every quantity the number pattern matches<br/>mints element_id, span_start, span_end"]
    TA["<b>TEXT ANALYSIS</b> - local service, not the language model<br/>labels organisations, people and places<br/>its reply is data: a label and two offsets"]
    ANC["<b>ANCHORING</b> - code<br/>one rule per shape<br/>what will not anchor is dropped"]
    TE[("<b>TRUSTED ELEMENTS</b><br/>byte-exact, cut from the article")]
    TB["<b>SOURCE DATA REFERENCES</b> - code<br/>independent readings in a fenced block"]
    C2["<b>SUMMARIZE-AND-PLAN CALL</b> - model<br/>summary, then chart choice with type and role citations or none<br/>no schema field accepts a value, a unit or an offset"]
    VP["<b>VISUAL PLAN</b> - code resolves citations against source<br/>type + role -&gt; element_ids<br/>no geometry or literal value"]
    VV{"<b>VALIDATOR</b> - deterministic, no model<br/>is this type drawable from these elements?"}
    DL["<b>DOWNGRADE LADDER</b><br/>depth 1, depth 2, then refuse"]
    VC["<b>CHART COMPILER</b> - code<br/>plan + elements =&gt; VisualData<br/>every number traced to an element or a derived value"]
    ART --> CP --> TE
    ART --> TA --> ANC --> TE
    TE --> TB --> C2 --> VP --> VV
    VV -->|"chart plan"| VC
    VV -->|"not drawable"| DL
    DL -->|"re-enters the SAME validator"| VV
  end

  subgraph PUB["PUBLISHED - committed files, sharded by day"]
    direction TB
    DJ[("<b>digest.json</b> - the day's TEXT<br/>carries a POINTER to the visual, never its data<br/><b>never deleted</b>")]
    VJ[("<b>&lt;item_id&gt;.json</b> - chart<br/>VisualData + renderer_version<br/><b>pruned on its own clock</b>")]
  end

  subgraph FE["READ TIME - the reader's browser.  EVERY VISUAL RENDERS HERE."]
    direction TB
    PG["<b>THE PAGE</b><br/>reads digest.json and renders the text<br/>the text never waits on a drawing"]
    ROUTE{"<b>CHART KIND?</b><br/>chart, or absent/null historical kind"}
    FJ["<b>CHART FETCH</b><br/>when the story comes near"]
    SC{"<b>CHART SHAPE CHECK</b><br/>does this fit VisualData?"}
    D3["<b>d3 DRAWS</b> the SVG into the document<br/>at the width the screen actually has"]
    DEG(["<b>DEGRADE</b> - the story is simply shorter<br/>no broken glyph, no grey box, no skeleton"])
    PG --> ROUTE
    ROUTE -->|"chart or missing kind"| FJ --> SC
    SC -->|"fits"| D3
    SC -->|"refused"| DEG
    ROUTE -->|"retired kind"| DEG
  end

  VC -->|"the pointer"| DJ
  VC -->|"the data"| VJ
  DJ --> PG
  VJ --> FJ

  subgraph KEY["KEY"]
    direction LR
    K1["code"]
    K2["model"]
    K3{"a gate that can refuse"}
    K4[("persisted")]
    K5(["a refusal"])
  end

  classDef code fill:#eef2ff,stroke:#4c6ef5,stroke-width:2px,color:#0b1020;
  classDef model fill:#fff4e6,stroke:#f08c00,stroke-width:2px,color:#0b1020;
  classDef gate fill:#f3f0ff,stroke:#7048e8,stroke-width:2px,color:#0b1020;
  classDef ledger fill:#e6fcf5,stroke:#0ca678,stroke-width:2px,color:#0b1020;
  classDef none fill:#fff5f5,stroke:#e03131,stroke-width:1.5px,color:#0b1020;
  classDef plain fill:#f8f9fa,stroke:#adb5bd,stroke-width:1px,color:#0b1020;

  class ART,PG,ROUTE,FJ plain;
  class CP,TA,ANC,TB,VP,DL,VC,D3,K1 code;
  class C2,K2 model;
  class VV,SC,K3 gate;
  class TE,DJ,VJ,K4 ledger;
  class DEG,K5 none;
```

**What the boxes do not carry.**

| Node | What it holds |
|---|---|
| `CP` | Code extracts quantities and dates, with the characters and offsets recording their source. |
| `TA` | A local process the run starts, asked once per article before the model reads it. The pipeline reads a label and two offsets of each mention and nothing else; the words it returns are compared with the characters those offsets cut from `Article.text`, and a mention whose words differ is dropped. No word it returns reaches a prompt, path, URL or command |
| `TB` | [Independent quantity and date references](../summarize/prompt.md#the-model-is-shown-independent-source-readings), with brief source excerpts. |
| `C2` | Decides from the article and cites the readings and label text for the chosen form; cannot author a measured value. |
| `VP` | Resolves source references into the existing typed plan; no geometry, literal value, authored labels or alt text. |
| `VV` | Ten checks: elements exist; semantically compatible; units convertible; roles valid for the type; enough data; no duplicate in a role; no invented values; numerals matched; plan version current; stacked parts equal a separate declared whole |
| `VC` | The chart compiler: the one place chart numbers come into being, each arithmetic result resolved over Tier 1 elements through the closed four-function allow-list - `count`, `sum`, `share_of_declared_whole`, `convert` |
| `DJ` | The day's text, and for each item a pointer: the visual's `kind`, its `state`, and where its file is. **No visual data, ever** |
| `VJ` | A chart as `VisualData`: `item_id`, `type`, `renderer_version`, the flat `marks` pool with provenance, and the encoding that assigns marks to channels |
| `ROUTE` | Only `chart` or absent/null historical kinds draw. Retired kinds become no visual, including in cached-day ingestion |
| `SC` | The numeric reader validates its payload and refuses rather than guesses; a refusal costs the story its visual and nothing else |

**Three things this drawing rules out, and a plan-doc may not relax any of them.**

**The model names the form and cites the readings; it never writes a drawn number.**
Every value is cut from source by code or derived from it by the allow-list.

**Nothing is drawn at build time.** There is no SVG on disk, no headless browser, and no Node in the pipeline. `BE` ends at data.

**The text never waits on a visual.** `digest.json` is a complete page on its own. The visual file is a separate fetch, and a reader who never scrolls to a chart never pays for that file.

## Design rationale

Type selection is active; safe replacement remains a separate, inactive policy. Their
configuration, production evidence and refusal rules are defined on the
[plan validation page](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md).
The existing item ledger carries terminal measurements so requested forms
remain visible through both replacement and refusal. A failed file write is
not delivery, and a useful replacement is still an unmet original request.

**Why attempt evidence stays separate from delivery.** Selected depth says
which replacement was chosen; deepest depth and first rejection explain the
search even when it ends in refusal. An attempt writer can read these typed
facts from `VisualDecision` instead of parsing `rationale`. A search may
compare several numeric floors, so nullable boolean evidence records whether
any floor excluded a candidate without presenting one floor as representative.

**Why citations instead of a drawing spec.** A model-written drawing spec can
contain a hallucinated axis value. References limit numeric values to readings
code cut from the article. Removing the name-and-figure table gate lets the
model compare two readings for one subject or choose non-categorical roles
without opening up a new way to write a value.

**Why `none_reason` lives on the decision and not on the plan.** Three of its five members fire when
no plan object exists at all - the gate leaves the question about a chart off the request, and the budget cut and
the window cut both lose the plan's bytes - so a field on `VisualPlan` would be unwritable on exactly
the routes it is for. `VisualDecision` exists for every item either way, and `asked_the_model` and
`drafted_chart` are the same kind of fact in the same payload. Authority: Fowler, 2026-09-11.

**Why a cut reply needs two members and not one.** `output_budget_cut` and `window_exhausted` arrive
as the same event: `--no-context-shift` means a decode that reaches the end of the context window
stops there, on an ordinary HTTP 200, with the same `finish_reason` of `length` a decode that spent
its whole output budget returns. One member for both would have made the largest thing an operator
can act on unreadable, because the fix for one is not the fix for the other - a budget cut is the
reply shape's own arithmetic, and a window cut is `--ctx-size` on the summarize entry against
`extract.truncation_cap_tokens`. Separating them costs one comparison at the one call site that
writes either, over numbers already in hand: the server counted the prompt, and the summarize-and-plan call's budget is
the model file's response limit. Plan 11 row #3f, 2026-09-13;
[`../summarize/prompt.md`](../summarize/prompt.md) carries the sizing behind it.

**This page became the decision path and an index on 2026-09-23, and five pages came off it.** It
answered at least six questions at about 31,700 tokens, which made it the heaviest page the routing
table could send an agent to once the config and frontend pages were cut. The stem keeps the
question somebody arrives with - how does an item get a chart or nothing - and the drawing of that
chain; each child keeps one of the others. The cost is real and is the usual one: a ruling whose
page nobody can guess now costs a table lookup, where before it cost a long scroll
([../../reference/documentation-structure.md](../../reference/documentation-structure.md)). One
correction travelled with the split: the flow drawing's node table said the validator holds eight
checks and it holds eleven - `plan_version_current`, `stacked_bar_exhaustive` and `pie_exhaustive` were added after the drawing was made.
Authority: Fowler.

### Diagrams deferred

`flow` is abandoned and excluded from active requests; retaining its historical
name does not defer a delivery. The other diagram families and their supporting
work remain deferred, not delivered: sequence and contrast word lists, the
`comparative` and `processual` reporting classes, force layout, `hierarchy`,
`state`, `mindmap`, and the expanded whole-day check. The summarize-and-plan
call chooses from the configured active visual types, and code validates its
choice.

The intended reader benefit is a diagram that explains a process or relationship
better than the summary alone. No reader-facing diagram has yet demonstrated
that benefit, so its supporting classification and layout work is deferred too.
Keep the current three reporting classes; other visual work does not wait for
diagram delivery.

If diagrams return to scope, first use source-backed examples to establish that
reader benefit. Every arrow must have supporting article evidence; paragraph
order alone supports no connection, and a matching text span does not prove
direction or causality. These are requirements for future work, not claims that
diagram validation or rendering exists today.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Ask the model for a Vega-Lite spec directly | A fabricated axis value becomes reachable, and verifying it afterwards means parsing an arbitrary spec to work out which numbers are data. |
| Skip the summarize-and-plan call entirely when the gate refuses | The summarize-and-plan call is the call that writes the summary, so skipping it costs the item the thing a reader came for. The gate leaves the answer about a chart off the request and never skips the call. |
| Suppress the answer about a chart with a smaller budget and leave the grammar whole | The decoder starts the answer and meets the cap part-way through, which spends the decode the gate exists to save and hands back a cut reply. The grammar is the control; a budget is a request. |
| Leave the question about a chart in the trailing ask when the grammar cannot hold it | Constrained decoding renormalises onto the allowed tokens, so a title, a caption and a reason with nowhere to go end up in the summary a reader reads. |
| A `none_reason` member for each of the six gates the design record names | Four of the six have no code behind them, so four members would be words nobody can produce, nobody can retire and nobody can tell from a bug. Each arrives with the row that builds its gate. |
| Put `none_reason` on `VisualPlan` as a third code-stamped field | Two of its four routes fire when no plan object exists at all, so the field would be unwritable on exactly the cases it is for. |
| A `skip_unreachable` config flag | A knob whose `false` setting means "ask about a chart on a request that has no table to ask it about". Nobody would set it. Whether a table is built is derived from `visuals.enabled_kinds`, `visuals.enabled_types`, `min_chart_points` and `max_chart_points`, which are already config. |
| A second, smaller model to triage items first | Two calls where the point was zero. |
| Discard the whole chart when one bar disagrees on units | Observed live: the model picked three correct year-on-year megawatt bars and appended the sector headcount. Three good bars thrown away to reject one bad one. |
| Plan on the 8B | Classification is the easy task. The big model belongs on summarization, and a second set of weights would not fit the pass anyway. |

## See also

- [what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md) - the shape and the eleven checks.
- [where-every-drawn-figure-came-from.md](where-every-drawn-figure-came-from.md) - where every number on an axis came from.
- [where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md) - who draws the chart, and what the compiler publishes.
- [one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md) - the file's name, and the race it ended.
- [what-drawing-costs-and-what-has-been-retired-for-it.md](what-drawing-costs-and-what-has-been-retired-for-it.md) - what drawing has cost, and what was retired for it.
- [`../../concepts/digest.md`](../../concepts/digest.md) - the visual rule this serves.
- [`../contracts/schemas.md`](../contracts/schemas.md) - where a persisted shape lives, and what binds the frontend's copy of one.
- [../../reference/github-actions.md](../../reference/github-actions.md) - workflow triggers and publication rules.
- [`../sources/trust-boundary.md`](../sources/trust-boundary.md) - why article text is data.
- [`../contracts/determinism.md`](../contracts/determinism.md) - why decoding is pinned in one place.
- [`../../reference/benchmarks/articles-that-state-a-whole.md`](../../reference/benchmarks/articles-that-state-a-whole.md) - how often an article declares a whole its parts add up to, which is what decides whether `pie` may be drawn at all.
- [`../../concepts/evaluation.md`](../../concepts/evaluation.md) - how a stage gets measured.
