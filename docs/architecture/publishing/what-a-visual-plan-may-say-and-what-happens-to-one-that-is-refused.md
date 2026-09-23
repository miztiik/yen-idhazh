# What a visual plan may say, and what happens to one that is refused

**Last Updated**: 2026-09-23

The shape the model decodes into, the four things it may not carry, the nine
deterministic checks a plan has to clear, and the ladder a refused plan may step
down before it becomes no picture at all. Nothing here calls a model: every
check is code over the article's own element table. Where the figures on the
finished chart came from is
[where-every-drawn-figure-came-from.md](where-every-drawn-figure-came-from.md);
who decides a picture at all is [visuals.md](visuals.md).

## The plan a compiler draws from, and the four things it may not carry

`VisualPlan` in [`backend/idhazh/contracts/visual.py`](../../../backend/idhazh/contracts/visual.py)
is the shape a planner decodes into and the only thing a compiler is allowed to read. It carries
element references and closed vocabularies: a decision, a purpose, a type, one channel per encoding
role, the elements it draws from, which of them name the marks and which one lands first, one
sentence of reasoning, a title, a caption, a confidence and the vocabulary date-stamp it
was planned against. It lands ahead of its producers, so nothing writes one yet (Guardrail #3).

What it may not carry is as much of the contract as what it holds.

| Prohibition | What refuses it |
| --- | --- |
| **No geometry** | Geometry is a number, and the schema admits exactly one number. A payload naming a pixel names a key the model does not declare, and an undeclared key does not load. |
| **No literal values** | Same guard. Every drawn figure is reached by citing an element, so a number pushed into a reference field fails that field's own grammar. |
| **No authored text where a reader reads a fact** | `labels` and `annotations` are element ids, not strings. Code cuts every character a reader sees off a chart; the model points at which characters. |
| **No `alt_text`** | The field is not declared, it is named in `FORBIDDEN_FIELDS`, and the module refuses to import if one is added back. |

**The geometry ban is what keeps the compiler swappable.** A plan that names a pixel is a plan bound
to one renderer, and the renderer is a choice this project has already changed once. Nothing in the
plan says how wide, how tall, what colour or what font; a compiler decides all four and a second
compiler may decide them differently over the same plan.

**Alt text is the compiler's, and the reason is worth keeping.** Assembled from element values the
compiler already holds, it is correct by construction. Written by the model it would be one prose
channel restating the chart's own data, and no validator can read prose to check it - so it would be
the last unguarded channel in a design whose whole claim is that a stranger's page cannot reach a
drawn figure.

**Three prose channels remain, and the shape only bounds them.** `title`, `caption` and `why` are
length-capped here. Whether a numeral inside one is matched by a cited element is the validator's
check, not the shape's - it needs the article's element table, which the plan deliberately does not
carry.

**`confidence` decodes after `type`, and that ordering is the field's licence to exist.** Field order
is decode order. Second in the list a confidence conditions every field after it, and the model reads
its own hedge back as evidence. Last but one it records what the model thought and gates nothing.

**Every array has a `maxItems` and every decoded string a `maxLength`, so the worst-case reply length
is arithmetic.** At the bounds the contract declares, the longest plan the decoder can produce is
**3,767 characters** - and a token spans at least one character, so that is also a ceiling of 3,767
tokens. The two committed fixtures measure 838 characters for a four-bar plan citing eight elements
and 368 for one that declines, between a fifth and a tenth of the ceiling. The derivation is field
by field in the module docstring, it is recomputed from the generated schema, and the module refuses
to import if a bound moves without the ceiling moving with it.

The ceiling is loose by construction and the arithmetic says where: `encodings` is 51 percent of it
and `element_ids` a further 22 percent, because the schema can bound each channel at eight elements
and cannot say that no type fills more than four channels. That last sentence is a validator rule,
and a validator runs after the tokens are already spent.

## Every encoding role is a key, and an unused one is empty

`encodings` is one object with a field per role, and the schema requires all nine. A `bar` fills
`category` and `quantity` and emits `"bins": []`, `"size": []` and five more empty arrays beside
them.

**Presence is what the shape guarantees; what may be empty is the validator's.** Left optional, a
role is a role the model can simply not mention - and a plan that names `bar` and omits `quantity`
reads as a complete answer rather than as a failure. That is "a confident chart with no bars in it",
which happened twice on the first live run. Required, the same reply is a decode failure at the key.
Which roles a given type may leave empty needs that type's own rule set, and a JSON Schema cannot say
"at most four roles for a `bar`", so the per-type ruling belongs to the validator and this shape only
guarantees the validator has something to rule on.

The roles are fields rather than a map because a schema can require the keys of an object it
declares and cannot require the keys of a map. An eighteen-branch union, one per type, would have
reached the same place and was refused: the decoder would have to pick a branch before it has picked
a type.

**There is no `label` role, and `labels` is why.** `labels` is the one naming channel - the elements
whose own characters name the marks and the axes, capped at eight marks and two axes. A `label` role
would ask the model the same question a second time inside `encodings`, and a model that answers it
twice can answer it two ways with nothing to settle which. So naming stays one field and `encodings`
answers a different question: which elements are drawn, and by which channel. `event_label` is not
the exception it looks like - a timeline's `time` channel places a dot and nothing else, so the event
text is the mark rather than a name for one.

**What that costs, measured.** An empty role is `"<name>":[]` and a comma. The nine role names cost
114 characters on a plan that declines and the seven a `bar` leaves empty cost 87. Tokenized with the
Qwen3 vocabulary (`Qwen3-8B-Q4_K_M.gguf` through `llama-tokenize`, 2026-09-09) that is 28 tokens and
23 tokens, about 3.1 tokens an empty role.

| At | Declining plan, 9 empty | Eight-bar plan, 7 empty | Over 80 items |
| --- | --- | --- | --- |
| 6.01 tok/s, the configured summarizer, `ubuntu-latest`, 2026-08-23 | 4.7 s | 3.8 s | 5.1 to 6.2 min |

Eighty is `run.safety_ceiling_per_run` and is the most items a run plans for, so the run figure is an
upper bound - an item the reachability gate refuses never reaches the summarize-and-plan call's plan half at all.
`digest.yml` fires five scheduled runs a day, so the day's ceiling is 400 plans: 26 to 31 minutes of
runner wall-clock, spread over four shards rather than paid serially. The worst-case reply ceiling
did not move: it already counted every declared key, because a grammar-constrained decoder emits
them all.

## The validator refuses, and each check refuses on its own

`backend/idhazh/visual_validator.py` reads one plan and one article's element table and returns the
checks that did not hold. An empty answer means the plan may be drawn. Nine checks, all of them
deterministic code over committed data - **no check calls a model, and a test reads the module's own
imports so none can start to** (`CLAUDE.md` section 0a). It reads the same test against
`visual_vocabulary.py`, or moving a table out of the validator would move it out from under the
guard.

It is a sibling module rather than part of the planner. A validator is not a contract, so it may
import both `contracts/visual.py` and `contracts/element.py`, which a contract may not
([`../contracts/schemas.md`](../contracts/schemas.md)); and the planner it would otherwise sit inside
is the module being replaced.

| Check | What must hold | What it catches |
| --- | --- | --- |
| `element_exists` | Every id in `element_ids` is in the article's table. | A plan drawing an element the article never had. |
| `semantically_compatible` | Each element's kind fits the channel it fills. | A quote drawn as a bar height; a number used as an axis tick's name. |
| `units_convertible` | Within one measured channel, every unit is convertible or identical. | Three megawatt bars and a headcount on one axis. |
| `roles_valid_for_type` | The filled roles are the ones the type declares. | A `bar` carrying `bins`; a `bar` with an empty `quantity`. |
| `enough_data` | The marks sit between `visuals.min_chart_points` and `visuals.max_chart_points` - and a histogram, whose marks are its bins, cites a value for every bin. | Two bars, which is a sentence rather than a comparison; three values asked to fill five bars. |
| `no_duplicate_in_role` | No element fills one channel twice. | One number drawn three times under three names. |
| `no_invented_values` | Every figure reads out of the characters its element names. | A table cell that disagrees with its own excerpt. |
| `numerals_matched` | Every numeral in `title`, `caption` and `why` is one a cited element states. | A caption that converted a figure, or reached one from nowhere. |
| `plan_version_current` | The plan met the vocabulary this build holds. | Contract drift, found rather than drawn. |

**Each check returns at most one refusal, carrying its own stable name.** That is a design
constraint rather than a testing preference. A validator that answers with one string cannot say
which rule fired, so no rule can ever be retired, tuned or trusted. It also decides the order:
`element_exists` resolves first and every later check reads resolved elements only, or one absent
element would trip four rules at once and the report would name the wrong cause.

`backend/tests/test_visual_validator.py` holds **one fixture per check, each tripping only its own**,
asserted as `[rejection.check for rejection in rejections] == [check]` rather than as a membership -
a membership passes while three other rules are firing. Each check was also neutered in turn against
its own fixture, and all nine left the plan accepted, so every one of them is the sole cause of the
refusal it is credited with.

### Where the vocabulary lives, and why none of it is in `config/`

`visuals.min_chart_points`, `visuals.max_chart_points` and `visuals.histogram_bins` are knobs and
are read from `config/` (Guardrail #6). The tables are not knobs, and since 2026-09-09 they are not the
validator's either: `backend/idhazh/visual_vocabulary.py` holds which roles a type may fill, which
kinds may fill a channel, which channels are drawn on a measured axis, which units measure the same
thing, and the two date-stamps over those tables.

**Two stages read them, which is why they have a module of their own.** The validator asks whether a
plan holds to the vocabulary; the resolver asks what a plan that already holds to it displays. Until
the split, `derived_values.py` imported five names out of `visual_validator.py` - and that reads as
a later stage borrowing an earlier stage's constant, when what it really was is a shared vocabulary
with no home, sitting in whichever consumer happened to be written first. Facts about the visual
language now sit below both stages, and `derived_values.py` no longer imports the validator at all.

It is not a contract and does not sit under `contracts/`: it holds no persisted shape, it generates
no schema, and it imports `idhazh.elements`, which a contract may not (`CLAUDE.md` section 4). The
move changed no behaviour and moved neither stamp - **a date-stamp that changes because a file moved
is a date-stamp that lies**, which is the same argument that keeps both of them out of `config/`.

- **Which roles a type may fill** is a relation between `VisualType` and `EncodingRole`, two closed
 vocabularies that are both Python enums in `contracts/visual.py`. A JSON file cannot reference
 either, so a copy there is a second spelling that drifts. "A bar has no bins" is also what a bar
 *is* rather than something an operator should be able to edit: a config edit that let a bar draw
 bins would publish a plan no compiler has a template for.
- **Which units measure the same thing** is arithmetic. A kilotonne is a thousand tonnes whatever
 anybody configures. `MAGNITUDE` in `idhazh.elements` is the precedent - a magnitude word's
 multiplier lives in code beside the pattern that reads it.

Eleven of the eighteen declarable types have a role rule: the grammar-of-graphics forms, where the
channels follow from the role names and anybody would write the same table. The other seven -
`table`, `flow`, `comparison`, `callout`, `quotecard`, `whowhat`, `keyfacts` - are **named as having
no rule yet**, and a plan naming one is refused by name. Naming them is the point: a type in neither
set would be waved through by both per-type checks and drawn with nothing having ruled on it.
Refusing them is also correct rather than a stopgap - declarable is not renderable, `enabled_kinds`
is `["chart"]`, and a downgrade ladder re-enters this same validator with a nearer neighbour.

`PLAN_VOCABULARY_VERSION` is the date-stamp of the role table, and it is not the plan contract's
`version`, which says when the *shape* last moved. `plan_version_current` compares the two
date-stamps rather than matching them, because the two directions are different faults: a plan
behind the vocabulary is re-planned, and a plan ahead of it came from a build this one cannot read.
It earns its place beside `roles_valid_for_type`, which already refuses a plan the current table
disallows - this one is for the plan the table still allows *by accident*, where a role's meaning
moved rather than its legality.

### Units are convertible or identical, not merely equal strings

Comparing unit strings for equality is cheaper and it is wrong in the direction that matters. It
refuses `4,200 tonnes` beside `4.2 kt`, which is the pair a reader most needs joined, and it accepts
`tonnes` beside `t` only by accident of spelling. So two units are commensurable when they are the
same string, **or** when one table names both under one dimension - power, energy, mass, length or
duration.

That table is a closed allow-list and its omissions are the safety. A unit is read off a stranger's
page (Guardrail #11), so a unit the table does not name is compared by identity and is never assumed
compatible with anything. `m` is out because it is metres or millions, and a guess there is a
one-million-fold error on a published bar - the same reason `MAGNITUDE` omits it. `ton` is out
because short, long and metric tons are three different masses. Currency symbols are out because
joining two of them needs an exchange rate, which is a number no article wrote.

**What is not settled here is the conversion itself.** A channel mixing commensurable units passes
this check and is not drawable until something converts it, because drawing 4,200 beside 4.2 on one
axis is worse than refusing both. This check answers whether a conversion is *possible*; what it
produces, and the provenance chain that records it, are in
[where-every-drawn-figure-came-from.md](where-every-drawn-figure-came-from.md#convert-is-a-derived-value-formatting-is-not).

## The ladder steps down, and four rules stop it becoming a new picture

A downgrade is **the same claim re-rendered in a weaker form**. It is never permission to go and
find something else to draw, and four invariance rules are what make that a property rather than an
intention.

| # | Rule | How it is held |
| --- | --- | --- |
| 1 | The element set does not change | The candidate is built by relabelling the type and emptying the channels the target does not declare. `element_ids`, `labels` and `annotations` come through untouched. |
| 2 | The purpose survives | The plan's own `purpose` is never written, **and** every edge in the allow-list names the purposes it preserves. |
| 3 | The floor escalates | Each depth reads a higher percentile of the depth-0 published mark counts for the type being stepped down to. |
| 4 | It re-validates | The candidate re-enters the **same** validator, and a depth that fails falls to the next depth rather than publishing. |

**Emptying a channel is not dropping an element**, and that difference is the whole of rule 1. What
a `bubble` loses on the way to a `scatter` is the size *channel*; the elements that filled it stay
declared, stay checked by `no_invented_values`, and are simply not drawn. Read the other way - as
"an element may not leave `element_ids`" - the rule would ban every edge the source document lists.

**Rule 2 needs the edges to carry purposes, because comparing each step's endpoints cannot make a
chain safe.** `pie` to `stacked_bar` keeps a composition and `stacked_bar` to `bar` does not, so a
ladder that only asked "does this plan still say `composition`?" would walk a composition into a
comparison in two moves and record both as legal. Naming the purposes an edge preserves asks every
step about the one purpose the plan started with.

### The static allow-list, and the four edges it refuses

`DOWNGRADE_EDGES` is a static table with its own date-stamp. Without one the ladder can walk a
comparison into a timeline and record it as a legal edge; the cross-family ban is what "purpose
survives" implies and never states.

| From | To | Preserves | What the step gives up |
| --- | --- | --- | --- |
| `bubble` | `scatter` | `relationship` | The size channel. The two measured axes the relationship is stay. |
| `pie` | `stacked_bar` | `composition` | The circle. Parts of a declared whole, stacked in one bar. |
| `stacked_bar` | `bar` | `comparison` | The series split, which is what a stacked bar is refused for when its parts are not exhaustive. |
| `comparison` | `bar` | `comparison` | Nothing a reader sees - `comparison` has no role rule yet, so this is the "nearest built neighbour" `UNRULED_TYPES` promises. |
| `whowhat` | `bar` | `comparison` | The grid. A one-attribute comparison grid drawn as the comparison it is. |

**An edge that cannot change an outcome is not on the list.** A target whose required channels equal
the source's rescues nothing - a plan refused as a `line` is refused identically as an `area` - so
that pair is absent rather than listed and never fired. A test holds the whole table to that.

Four refusals are worth naming, because each is a judgement rather than a derivation:

- **`line` to `bar`** is in the source document with the condition "if the time axis is safely
  categorical". Nothing in this build can decide that, and a condition nobody can evaluate is a
  condition nobody should encode.
- **`slope` to `bar`** destroys the before-and-after pairing the slope exists to show, so it is not
  an edge at all.
- **`flow`** is the diagram family, whose only fallback is `none` - never sideways into a chart.
- **Any chart to `table` at depth 2** is in the source document, and `table` has no role rule, so
  the validator refuses it by name. A target that cannot pass rescues nothing.

### The floor, what it is a percentile of, and what an empty corpus means

`visuals.downgrade_floor_percentiles` is the ladder as one list: how many rungs it has and how high
each one is. Entry *n* is the percentile a downgrade at depth *n+1* must reach, so **the length is
the deepest permitted downgrade and the depth after it refuses** - `[50, 75]` is the design's own
ladder, the median at the first step down and the 75th percentile at the second, refuse at the
third. An empty list is the ladder switched off, which is one knob doing two jobs on purpose: a
separate on-off flag can disagree with the rungs beside it, and zero rungs is already an unambiguous
no. It ships empty, because the flag stays off until the whole two-call path works. The rungs must
rise, and `VisualsConfig` refuses a list that does not - a floor that falls with depth is a ladder
that gets easier the further down it goes.

**The floor is on the mark count**, which is the quantity the validator's own `enough_data` already
counts, over elements code extracted. The population is the depth-0 published mark counts for the
target type: including downgrades makes a loop where downgrades score lower, drag the floor down and
admit more downgrades, so the bar would loosen exactly as quality fell. It is nearest-rank, so an
integer population gives an integer floor and nothing is interpolated into a mark count no published
visual ever drew.

**A floor that cannot be computed is not cleared.** Waiving it on an empty population would make
depth 1 publish on the validator alone, which is depth 1 quietly becoming the default path. The
consequence is stated rather than hidden: `state/visuals/` does not exist yet, so today the
population is always empty, every depth refuses, and **the ladder behaves exactly as if it were
off**. What ships now is the mechanism, its edges and three of its four invariants under test; the
floor case becomes live when the ledger does.

**A downgrade with no annotation fails**, at every depth and not only at depth 2. The source
document states it both ways - a table that puts it at depth 2 and a rule that puts it at depth 1
with the reason "this is what prevents depth 1 from quietly becoming the default path" - and the
rule is the one with a reason attached. It is also the weaker of the two claims in this codebase
already: the programme requires an annotated mark on **every** visual, not only a downgraded one.

**What the percentile cannot do, said next to it.** A mark count is bounded to the
`min_chart_points`-to-`max_chart_points` window, 3 to 8 today, so a percentile over it is a
low-resolution instrument and two adjacent rungs can land on one integer - at which point the ladder
stops escalating. That is visible rather than silent, because each depth records the floor it
applied, and the answer is to move the percentiles rather than the mechanism.

**The kill criterion is pre-committed here, before any data is read.** If downgraded visuals are
kept materially less often than depth-0 ones, the ladder is manufacturing exactly the pointless
visuals it was gated against: the flag goes off and **the ladder is deleted, not tuned**. The
instrument is `visual_keep_rate` at depth 1 or more against depth 0, and it needs the keep-rate panel
and the ledger behind it, so the criterion cannot fire until both exist. Writing the line down first
is what stops the number being argued after it is seen.

## Design rationale

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

**Why the floor is a mark count and never `confidence`.** The ladder needs a number that rises with
depth, and the only per-plan number in the contract is `confidence` - which the shape itself says is
"recorded, and it gates nothing". Three reasons, and the cheapest one comes first: gating on it
breaks the shape's own written guarantee. It is also the one free number the model writes, so
prohibition 2 - "the worst a prompt injection can do is pick the wrong bars; it cannot draw the
wrong number" - would stop being true of publish decisions (Guardrail #11). And a model may not select
what publishes (`CLAUDE.md` section 0a). The mark count is code's own count over code's own
elements, and it is the quantity `enough_data` already rules on. Authority: Andre and Fowler, ruled
independently and agreeing, 2026-09-11.

**What the mark count cannot see, said rather than implied.** It is a floor, not a quality score. It
cannot tell whether the marks differ from each other, whether the labels are legible, or whether
anybody would choose to look - which is Susan's standing warning about this whole subsystem: every
binding gate here is integrity or cost, and a plain grey bar chart passes all of them.

**Why the edge table has a date-stamp of its own.** `PLAN_VOCABULARY_VERSION` is what
`plan_version_current` compares a plan against, so moving it re-plans every item carrying an older
one - a model call apiece. Adding a downgrade edge must not cost that, and `UNIT_TABLE_VERSION` set
the precedent for the same reason.

**Why the ladder ships inert rather than waiting for its ledger.** With no depth-0 population every
floor is uncomputable and every depth refuses, so today the ladder answers exactly as it would with
the flag off. That is deliberate: the edges, the invariants and the refusals are under test now, at
no reader-visible cost, and the one case that needs a corpus is the one case that waits. The
alternative - hold the whole mechanism back until `state/visuals/` lands - would put the edge table
and the invariance rules into the same commit as the ledger, where a review has to hold both.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A model checks the plan | A judge that shares the failure modes of the thing judged is not a measurement (`CLAUDE.md` section 0a). Every check the plan needs is a comparison against the article's own element table, which is committed data - so the model buys nothing and costs the only guarantee the subsystem sells. |
| Return one refusal string from the validator | Cheaper to write and it makes every rule unfalsifiable at once. Nothing can then say which check fired, so no check can be retired, tuned or shown to work - and a fixture that trips three rules proves none of them. |
| Compare unit strings for equality in the validator | Cheaper, and wrong in the direction that matters: it refuses `4,200 tonnes` beside `4.2 kt`, which is the pair a reader most needs joined, while accepting `tonnes` beside `t` only by accident of spelling. |
| Put the per-type role table in `config/` | It is a relation between two Python enums, and a JSON file can reference neither - so the copy there would be a second spelling that drifts from both. It is also not a knob: a config edit that let a `bar` draw `bins` would publish a plan no compiler has a template for. |
| An eighteen-branch union, one per type, instead of one encodings object | The decoder would have to pick a branch before it has picked a type. |
| A `label` encoding role beside the `labels` field | It asks the model the same question twice inside one reply, and a model that answers it twice can answer it two ways with nothing to settle which. |
| `confidence` as the ladder's escalating floor | The contract says it gates nothing, it is the one free number the model writes, and a model may not select what publishes (`CLAUDE.md` section 0a). Gating it would also destroy it as a diagnostic. |
| Waive the floor when no depth-0 visuals have been published | Depth 1 would publish on the validator alone, which is depth 1 quietly becoming the default path - the failure the escalating floor exists to prevent. |
| A separate on-off flag beside the ladder's rungs | Two knobs that can disagree about one thing. Zero rungs is already an unambiguous no, and the rung count is already the maximum depth. |
| A `line` to `bar` downgrade edge | The source document allows it "if the time axis is safely categorical", and nothing in this build can decide that. A condition nobody can evaluate is a condition nobody should encode. |
| Any chart to `table` at depth 2 | `table` has no role rule, so the validator refuses it by name. A target that cannot pass rescues nothing, and listing it would be a rung nobody can stand on. |
| Let the ladder move an element from one channel to another | It re-encodes the claim - the same date now means "a name on the axis" rather than "a point in time" - so the purpose survives in the field and not in the drawing. |
| Let a downgrade skip re-validation | Then a downgrade can publish the thing the original plan was refused for. |
| A repair retry instead of a ladder | A retry must perturb the input, and there is no rejection reason to feed back: the ladder was chosen over a repair retry precisely so that no validator failure ever re-calls the model. |

## See also

- [visuals.md](visuals.md) - who decides a picture at all, and where the pass runs.
- [where-every-drawn-figure-came-from.md](where-every-drawn-figure-came-from.md) - what the checks above are protecting: every figure's origin.
- [where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md) - what a plan that clears these checks is compiled into.
- [../contracts/schemas.md](../contracts/schemas.md) - `VisualPlan`, and where a persisted shape lives.
- [../extraction/elements.md](../extraction/elements.md) - the element table every check reads against.
- [../sources/trust-boundary.md](../sources/trust-boundary.md) - why article text is data and never instruction.
