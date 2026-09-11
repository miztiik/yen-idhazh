# Visual planning and rendering

**Last Updated**: 2026-09-11

How an item gets a chart or - most of the time - nothing at all.

The rule this subsystem serves is in [`../../concepts/digest.md`](../../concepts/digest.md): a
visual must carry a fact the sentence beside it does not. A picture that decorates is worse than
no picture, because the product is trust and an invented axis label costs it permanently.

## The stage runs on its own model, in its own pass

Visual planning is a separate CLI stage from `work`, not a step inside it:

```
idhazh work --date <D> # the 8B summarizes
idhazh visuals --date <D> # the 4B plans a visual and renders it
idhazh assemble --date <D> # the day payload picks up whatever was drawn
```

One llama-server serves one set of weights, and classification is the easy task, so the planner
runs on Qwen3-4B while the summarizer keeps the 8B. Splitting the stage also means **a run that
never starts a planner still publishes.** Every item simply carries no picture, which is already
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

## The plan a compiler draws from, and the four things it may not carry

`VisualPlan` in [`backend/idhazh/contracts/visual.py`](../../../backend/idhazh/contracts/visual.py)
is the shape a planner decodes into and the only thing a compiler is allowed to read. It carries
element references and closed vocabularies: a decision, a purpose, a type, one channel per encoding
role, the elements it draws from, which of them name the marks and which one lands first, one
sentence of reasoning, a title, a caption, a confidence and the vocabulary date-stamp it
was planned against. It lands ahead of its producers, so nothing writes one yet (Rule #3).

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
Qwen3 vocabulary (`Qwen3-8B-Q4_K_M.gguf` through `llama-tokenize`, 2026-09-09; Qwen3-4B, the
configured planner, uses the same tokenizer) that is 28 tokens and 23 tokens, about 3.1 tokens an
empty role.

| At | Declining plan, 9 empty | Eight-bar plan, 7 empty | Over 80 items |
| --- | --- | --- | --- |
| 13.00 tok/s, Qwen3-4B, `ubuntu-latest`, 2026-08-22 | 2.2 s | 1.8 s | 2.4 to 2.9 min |
| 6.01 tok/s, the configured summarizer, `ubuntu-latest`, 2026-08-23 | 4.7 s | 3.8 s | 5.1 to 6.2 min |

Eighty is `run.safety_ceiling_per_run` and is the most items a run plans for, so the run figure is an
upper bound - an item the reachability predicate refuses never reaches the model at all. On the 4B it
is 6 to 7 percent of the 40-minute `run.visual_planner_budget_minutes`, and 8 to 10 percent on top of
the 21.0 s an item this stage measured on `ubuntu-latest`, 2026-08-24 over 148 items. `digest.yml`
fires five scheduled runs a day, so the day's ceiling is 400 plans: 12 to 14 minutes of runner
wall-clock on the 4B, 26 to 31 on the summarizer. The worst-case reply ceiling did not move: it
already counted every declared key, because a grammar-constrained decoder emits them all.

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
are read from `config/` (Rule #6). The tables are not knobs, and since 2026-09-09 they are not the
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
page (Rule #11), so a unit the table does not name is compared by identity and is never assumed
compatible with anything. `m` is out because it is metres or millions, and a guess there is a
one-million-fold error on a published bar - the same reason `MAGNITUDE` omits it. `ton` is out
because short, long and metric tons are three different masses. Currency symbols are out because
joining two of them needs an exchange rate, which is a number no article wrote.

**What is not settled here is the conversion itself.** A channel mixing commensurable units passes
this check and is not drawable until something converts it, because drawing 4,200 beside 4.2 on one
axis is worse than refusing both. This check answers whether a conversion is *possible*; what it
produces, and the provenance chain that records it, are the derived-value contract below.

## A number the article did not write, and the four ways code may reach one

Every figure a reader reads off an axis resolves one of two ways. It is a **Tier 1 element** - the
characters the article itself wrote, cut at a span anybody can re-slice - or it is a **derived
value**, arithmetic code performed over Tier 1 elements, carrying a chain back to every one of them.
There is no third way, and `DisplayedValue` in `backend/idhazh/contracts/derived.py` is that sentence
written as a shape: exactly one of the two, never both, never neither. A figure that resolves to
nothing does not load, so the walk over a plan proves the resolver never reaches for the exception
rather than proving nobody happened to write one.

**Four functions, and the list is closed.** Its shortness is the guarantee rather than a starting
point: the model picks the type and points at elements, and it cannot name a function, cannot supply
an operand, and has no numeric field anywhere in its schema - `contracts/visual.py` refuses to import
if it grows one. So the worst a prompt injection can do stays "pick the wrong elements". A fifth
function is an owner decision and `contracts/derived.py` raises at import if one appears, which is
why the argument for the list being short is written beside the constant rather than only here.

| Function | Reads | Produces | What its chain records beyond function, version and inputs |
| --- | --- | --- | --- |
| `count` | the elements in one bin | how many there are, unitless | the bin's floor and ceiling |
| `sum` | two or more elements stating one unit | their total, in that unit | nothing |
| `share_of_declared_whole` | the part first, then the parts that make the whole | a percentage | nothing |
| `convert` | one element | the same quantity against another unit of its dimension | the source unit and the unit table's date-stamp |

`inputs` holds Tier 1 element ids and never another derived value. A chain that nests can be
complete at each hop and still name no element at the bottom, and "every input element" is what the
rule asks for. `share_of_declared_whole` totals its whole internally for the same reason: the share
names every element it read, and there is no intermediate a later reader has to chase.

### `convert` is a derived value; formatting is not

`2000000` drawn as `2M` moves no quantity - same number, different glyphs, nothing to record.
`4200 tonnes` drawn as `4.2 kt` is a different number against a different unit, so it carries the
full chain. Where that line falls decides what needs provenance, and running the two acts together is
how a formatting rule becomes permission to state a figure the article never gave.

The line is drawn on **scale, not spelling**. `tonne` and `t` are two names for one unit, so a
channel holding both draws them unchanged and the axis label picks a spelling - that is formatting.
`kt` beside them is a thousand-fold difference, and moving it earns a chain. On the committed
`units-convert` plan, which passes all nine validator checks and was not drawable before this, that
is one converted mark out of three.

Nothing is lost, which is what makes conversion safe here. An element's Tier 1 `span_excerpt` is the
article's own characters and is never overwritten, so a reader who wants the figure the article
printed can always be given it.

**The target unit is code's choice, never the plan's.** Taking the first entry's unit would hand the
choice to the model, which orders the channel. So the target is the smallest scale present, and among
units sharing that scale the one that sorts first. Two properties fall out and both are load-bearing:
it is a fact about the channel's contents rather than about the plan's order, and converting to the
smallest present unit only ever multiplies, so no value is divided into a repeating decimal and no
rounding decision is hidden inside a mark. A ratio that will not state exactly is refused rather than
rounded - the table holds no such pair today, so that fails closed on a table that grows.

### A histogram's marks are its bins, and the check counted its inputs

Every other type draws one mark per element in the channel `TypeRules` names, so counting that
channel counts the marks. A histogram does not: its `bins` channel holds the values being
distributed, and the bars a reader counts are `visuals.histogram_bins` of them. Until 2026-09-09
`enough_data` counted the channel for every type, so a histogram was admitted or refused on a
quantity it does not draw. Nothing collided at the committed value - `histogram_bins` is 3 and
`min_chart_points` is 3 - but the two readings were wrong in opposite directions: raise
`histogram_bins` to 12 and the validator admitted every plan asking for more bars than the ceiling
allows, while three values with twelve bins read as too few marks when what it had was too many
bars.

**"Enough data" is one check, because the second question is not about a plan.** How many bars a
histogram draws is the same for every histogram in the run, so a per-plan check would answer it
identically for every item and blame the article each time. It is asked once, where the config
loads: `VisualsConfig` holds `visuals.histogram_bins` inside the same `min_chart_points` to
`max_chart_points` window every other type's mark count sits in, and a value outside it fails the
build naming the operator who set it. What is left for `enough_data` to ask of a plan is whether the
article gave enough values to fill those bars - a floor of `visuals.histogram_bins` on the cited
values, because fewer values than bins leaves a bin empty whatever their spread.

A tenth check was weighed and refused. It would have fired on every histogram of every run for one
config edit, and the reader loses nothing by its absence: the same fault is caught earlier and
stated once. The three bounds are all `config/` knobs and none is a number chosen in code (Rule #6);
no new knob was needed, because `min_chart_points` and `max_chart_points` already mean "how many
marks a chart may draw" and a histogram's bars are marks.

### Binning is versioned config, and where the edges fall is not

A histogram's bars are counts rather than figures the article wrote, so something has to say how many
bins its values fall into. `visuals.histogram_bins` says, and the model is the one thing that may not.
Where the edges fall - equal width over the range the values cover, half-open except the last bin,
which is closed so the widest value has somewhere to go - is arithmetic and lives in
`idhazh.derived_values`, stamped by `DERIVED_VALUE_VERSION`.

A bin nothing falls into refuses the drawing. Its chain would name no element, and a mark that
resolves to nothing is the one thing this contract exists to keep off a page. The item degrades and
publishes no picture, which is the honest answer when a knob asks for more bins than the channel has
spread to fill. The default is `min_chart_points` rather than a textbook rule for a sample size this
stage never sees. **What reaches that refusal is a lack of spread and nothing else**, now that
`enough_data` refuses a plan citing fewer values than bins: a count shortfall is a plan fault the
validator names, and only values that crowd into one end of their own range get this far.

### The resolver refuses with a value, because the caller degrades

`resolve_displayed_values` returns a `Resolution`: the figures it drew, or one `Refusal` naming the
check that stopped it. It is the counterpart of the validator's `Rejection` and it exists for the
same reason - a refusal that cannot say which rule fired is a rule nobody can retire, tune or show to
work.

**It returns rather than raises because the empty bin above is reachable on a plan the validator
passed.** Thirteen of the fourteen refusals restate one of the nine checks, so a caller meeting one of
those resolved a plan it never validated - this run's own arithmetic being wrong. The fourteenth,
`values_have_spread`, is the resolver's own: values crowding into one end of their own range leave a
bar empty with a figure for every bin, and no check above refuses that. The paragraph above says the
item degrades and publishes no picture, and a caller can only do that if the refusal is something it
reads off the return. A caller that has to remember a `try` is a caller who will one day not, and the
`try` it forgets takes a whole day's digest off the air to punish one story - the trade `CLAUDE.md`
section 1a already refuses.

**The two empty-bin causes carry different names, and the difference is what an operator acts on.**
`enough_values_for_bins` says the article was thin; `values_have_spread` says
`visuals.histogram_bins` is set higher than the article's figures can fill. Folded into one name,
every empty bar reads as the knob. The four functions and the helpers under them still raise
`DerivedValueError`, which now carries the same check name - reaching `convert` with two units that
do not measure the same thing is a bug rather than an article with a problem, and the boundary a
stage calls is the one place that turns the raise into a refusal.

### Three stamps, and none of them is a config key

The plan's file list proposed `visuals.unit_table_version`. It is refused. A stamp an operator can
edit without editing the table it stamps is a stamp that lies, and every derived value that recorded
it lies with it. Which units measure the same thing is arithmetic - a kilotonne is a thousand tonnes
whatever anybody configures - so the table and its date-stamp stay in code, for the second of the two
reasons the role table stays there. The first reason does not carry over: the unit table references no
Python enum, so a JSON copy of it would be readable in a way a copy of the role table is not.

| Stamp | Stamps | Recorded by | Where |
| --- | --- | --- | --- |
| `PLAN_VOCABULARY_VERSION` | which roles a type may fill | `VisualPlan.plan_version` | `visual_vocabulary.py` |
| `UNIT_TABLE_VERSION` | which units measure the same thing, and by what factor | a `convert` chain | `visual_vocabulary.py` |
| `DERIVED_VALUE_VERSION` | the four functions and the binning rule | every chain | `derived_values.py` |

**Row 3 shipped one stamp over two tables and it is split here, because the two answer different
questions to different readers.** `plan_version_current` compares a plan against
`PLAN_VOCABULARY_VERSION`, and a plan behind it is re-planned - a model call per item. Folded
together, adding a unit spelling would cost a re-plan of every in-flight plan for a reason the model
had no part in. And a reader auditing a drawn `4.2` would get a stamp that also moves when a bar
gains a legal role, which is a stamp that says less than it appears to.

### The two rates, and why both

`derived_value_rate` is the **narrowness** alarm: what share of the figures on a page code computed
rather than the article wrote. `trusted_data_ratio` is the **correctness** alarm: what share resolves
at all, against the table it claims to come from. A build can move either without moving the other,
which is why both are reported. The closed allow-list and the separate rate are the only two things
keeping this contract narrow, and skipping either loses the guarantee unnoticed.

Both are `None` over an empty set rather than zero. A rate over nothing is not zero, and a day whose
planner drew no charts reads as a perfect score under the other convention.

**Neither is wired to a surface, and that is a named seam rather than an oversight.** Nothing resolves
a plan into figures on the daily path yet, because the compiler that would is plan 12's. They ship as
functions over a resolved set with bounded tests; the run manifest is where a per-run rate belongs,
beside `charts_drafted` and `items_prefiltered`, and it gains the two columns on the day the compiler
produces resolved sets. A field nobody writes is worse than a seam somebody named.

`sum` is the one function the resolver does not reach today: no type in the vocabulary draws a total.
It is here, tested and complete, because shipping the list four short of its own definition would be
the widening this contract exists to prevent, arriving as an omission.

### The two provenance invariants, ruled

Both were declared build-failing where they were first written, and neither had been ruled against
`CLAUDE.md` section 1a's "degrade, do not fail". They are ruled here, and neither ruling changes what
a corpus build does today.

- **`derived_provenance_complete` degrades the item.** A plan whose drawn figure resolves neither to
 a Tier 1 element nor to a derived value with a complete chain is refused by the validator, the item
 publishes with no picture, and the check that refused it is recorded - because taking a whole day's
 digest off the air to punish one story is the trade section 1a already refuses.
- **`span_integrity_pass` breaks the build on its write side and degrades the item on its read
 side.** That is what `ElementTable.span_drift` already does, and it is the three-part regime the
 element table shipped with rather than one build-failing gate.

**The span invariant is the exception because it is the only one asked on both sides of a boundary,
not because span drift is graver.** A producer cut every excerpt out of the string it hashed moments
earlier, so a mismatch there is this run's own arithmetic being wrong and every article in the run
has it - failing the build says exactly what is true. Every other invariant in this area is asked
only of a payload the asker did not build, where the worst case is one item's problem and says
nothing about a sibling. Degrading is the rule; what the exception turns on is the side of the
boundary, not the invariant.

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

`reachable_kinds` computes that before the request is built. When no enabled kind survives it,
the planner writes a `VisualDecision` with `kind: none`, `asked_the_model: false`, and a rationale that says
the model never ran. The run manifest counts those separately as `items_prefiltered`.

Three properties of how it is written, and each one is load-bearing:

- **It is a predicate over every enabled kind, not a chart special case.** Chart is the only kind
 left, so the predicate answers for one today - but a kind added later declares its own
 reachability here rather than being let through by an `if` that only knows about charts. The
 diagram arm is what made that shape necessary and then proved its own cost: a diagram's steps come
 from prose, so nothing about one is decidable in advance, and with `diagram` in
 `visuals.enabled_kinds` **no item was ever skipped** - measured at 145 of 145 asked on 2026-08-25.
- **It reads the facts only - never the article's words.** A predicate that branched on fetched
 prose would let a stranger's page steer our control flow, which is Rule #11 with no prompt in
 sight. There was no keyword rescue for the diagram arm for the same reason.
- **The empty string is a unit group.** `numeric_facts` writes `""` when nothing after the number
 reads as a unit, and `same_unit_bars` already groups on it. Excluding it here would gate items
 that publish today.

With the arm off, measured on the 145 items of run `32804437110` with no model and no network:
**68 items (46.9%) never reach the model**, and 77 do. The histogram of widest unit group per
article is in [`../../reference/measurements.md`](../../reference/measurements.md).

The denominator moves when this is on: the same charts sit over a smaller decided set, so a chart
rate quoted against `items_routed` alone climbs without a single extra chart existing. Quote it
against `items_routed + items_prefiltered`, or state which one you meant. Both keys are the wire
names the run manifest froze on 2026-09-05; the Python behind them is `items_decided` and
`items_prefiltered` ([../contracts/schemas.md](../contracts/schemas.md)).

## The two-call gate suppresses the plan and never skips the call

The single-call gate above skips a request. The two-call flow cannot, because **call 2 is the call
that writes the summary** - so what the gate takes away is the plan's decode, not the request. The
grammar is what takes it: `call_two_model(plan=False)` is the summary draft alone, with no `visual`
property, so the decoder has nowhere to write a plan. A smaller budget on its own would not do it -
the decoder would start the plan and meet the cap part-way through, which spends the decode the gate
exists to save and returns a cut reply.

`reachable_types` is the predicate, and **it reads the validator's own tables** - `TYPE_RULES`,
`ROLE_KINDS`, `VALUE_ROLES` and `commensurable`, out of
[`visual_vocabulary.py`](../../../backend/idhazh/visual_vocabulary.py). A gate written from
somebody's reading of those rules drifts the first day a rule moves, silently, in the direction that
costs items their pictures. For each type with a role rule it asks three questions of the element
table alone: is every required channel fillable by some element of a kind that channel takes, does
the channel the type counts its marks in reach the floor, and - where that channel is drawn on a
measured axis - do enough of those marks measure the same thing.

Three of the nine checks cannot refuse a plan the gate admitted, so the gate does not ask them.
`element_exists` is satisfied by choosing from the table. `plan_version_current` is stamped by code.
`numerals_matched` is about prose, and a plan can always write prose with no numeral in it. One
check does the opposite and is asked early: an element whose cell disagrees with its own characters
fails `no_invented_values` wherever it is drawn, so the gate reads it with the producer's own reader
and does not count it as a mark.

**It reads no word of the article.** Every input is a kind, a unit or a figure re-read from the
span - so a page that asks to be drawn is answered with the same tuple as one that does not. That is
Rule #11 with no prompt in sight, and it is the same property the single-call gate holds.

**The gate is proved by exhaustion, not by sampling.**
`test_the_gate_admits_nothing_the_validator_would_have_passed` builds a table the gate calls
unreachable and enumerates every assignment of every subset of its elements to every required
channel of every ruled type, asserting the validator refuses all of them. One survivor would mean
the gate costs an item a picture a reader would have seen, which is the one way a cheap gate is
expensive.

| What the gate changes about call 2 | Before | Gated |
| --- | --- | --- |
| The decoder shape | `{summary, visual}` | the summary draft alone |
| The output budget | 4,694 tokens | 905 tokens |
| The trailing user turn | 2,555 characters | 961 characters |
| The system turn, the article, call 1's reply | unchanged | unchanged |

Both budgets are derived from the reply shape's own bounds by the same arithmetic rather than one
being the other minus the plan's - two ways of computing one quantity disagree the first time a
bound moves, and the one that is wrong is the one nobody reads. The saving is 3,789 tokens off the
ceiling, which is 81 percent of it; **a ceiling is not a measurement of seconds**, and the "21
measured seconds" this page used to quote was a saving for skipping a whole call, which cannot
happen. That figure is withdrawn rather than re-used.

**The prompt loses its plan half too, and that is the same rule read a second time.** A turn that
asks for a title, a caption and a reason the grammar has nowhere to put does not simply get ignored:
constrained decoding renormalises onto the tokens the grammar allows, so the text goes into the only
channel left open, which is the summary a reader reads. `summarize_and_plan_visual.txt` is now the
summary half with a `$plan` slot, and `plan_visual.txt` is what goes in it - one file substituted in
or out rather than two whole prompts, so the summary half cannot drift between the two requests. A
test asserts the two renders share it byte for byte.

**Suppressing the plan moves nothing in front of the article.** All three differences sit after the
system turn, the article and call 1's reply, so the cached prefix a gated item reuses is the prefix
an ungated one reuses, and the floor row #3 measured is the same floor for both.

## Every `none` says which gate refused it

`none` is the majority outcome by design - two items in three - so a `none` with no cause makes the
largest number an operator reads the one that explains nothing, and no gate can be retired, tuned or
shown to work. `VisualDecision.none_reason` is a typed enum rather than a sentence in `rationale`,
because a console counts members and cannot count prose.

| Member | The route it names |
| --- | --- |
| `not_reachable` | No choice over this article's elements could have survived the validator. The call still ran and still wrote the summary. |
| `model_declined` | The model was asked and answered `none`. The ordinary answer, and the one the design wants to stay common. |
| `validation_failed` | A plan was drafted, the validator refused it, and the ladder reached no depth that validates. |
| `output_budget_cut` | The reply ran out of output budget after the summary closed, so the plan was never written. The item publishes; the picture is what was lost. |

**One member per gate, never one per call site.** The reachability gate refuses in two places - the
single-call prefilter above and the two-call suppression - and both record `not_reachable`, because
what an operator acts on is the gate rather than the line of code. And **which** check refused is
`ValidatorCheck`'s to say: one fact with two homes is a fact that can disagree with itself.

**Four members, because four routes have a writer.** The design record names six gates and the
two-call flow adds a seventh. The potential class, the novelty floor, the sufficiency bar and the
per-visual byte cap are not built, so a member for each would be a word nobody can produce, nobody
can retire and nobody can tell from a bug. Each arrives as an additive member with the row that
builds its gate. The oracle holds the enum to that: every route is driven from its own fixture and
the set collected must equal the enum exactly.

The single-call planner these four replace writes null. Its causes are sentences in `rationale`, and
several of them - no summary to illustrate, a reply that lost its shape, a kind with no renderer -
are not gates at all, so typing them into this vocabulary would be work the row that retires that
planner deletes. A payload written before the field existed writes null for the same reason, and
that is the honest reading: nothing committed says which gate refused it.

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
floor arm becomes live when the ledger does.

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

## The stage stops itself before the job does

The stage's wall-clock is `items with an OK summary x per-item cost`, and neither factor was
bounded. The first is set by how well the summarizer did, up to `run.safety_ceiling_per_run`
(200). The second is set by whichever host the runner gave us: measured mean **20.7 s on a fast
host and 40.3 s on a slow one**, over six runs and 703 items on 2026-08-24/25. A 145-item day
therefore needs anywhere from 50 to 97 minutes against a 50-minute job.

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
([`../../reference/measurements.md`](../../archive/measurements-2026-08.md#the-route-stages-per-item-cost-over-every-run)).
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
already-published item and discards the new run's copy, because the reading order is part of what a
shared link shows. So a later run's decision for one of those items is computed, written, read back
and thrown away. A day runs five times: without the skip, run 2 spends its whole budget re-deciding
run 1's items at 20 to 40 measured seconds each, and the items it actually introduced queue behind
them. This is the resumability invariant the rest of the pipeline already holds - a re-run costs
only the unfinished items - applied to the one stage that did not. It reads the committed
`digest.json` the same way the asset counter reads the committed directory, so it needs no handshake
with the assembler.

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
its own limit. Raising either one is the move Rule #2 forbids.

**The chart arm has a kill line, registered before the data was read.** Authority: Jony,
2026-08-25. Over 14 consecutive days with the chart-only gate on, retire the arm if the median day
publishes a chart on fewer than 5% of published items, or spends more than 6 planner minutes per
published chart. Either limb trips it. A day stopped at the budget still counts. Measured
2026-08-25 on `ubuntu-latest` (4 vCPU, 16 GB): 6.2% and 4.4 minutes - inside the line on both
limbs, which is why the arm ships. Writing the line down first is what stops the number being
argued after it is seen.

`charts_drafted` on the run manifest is what makes that reading possible. It counts the items whose
planner reply asked for a chart, whatever the decision became, so the gap between it and the day's
published charts is exactly what the two controls below rejected. Without it a model that stops
asking for charts and checks that start refusing them are the same number.

**The summarizer swap on 2026-08-27 moved an input the window sits on.** The planner runs on its own
Qwen3-4B and that model did not change, but the user turn it reads carries the summary text as well
as the article's opening and the indexed numbers - so a different summarizer writes a different
question, and `charts_drafted` can move with no planner change at all. The 6.2% and 4.4 minutes
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

The two gaps are the point. Reached against asked is the reachability gate above, running before any
request. Drafted against published is the two post-model controls. A single funnel of bars would
make the last stage the shortest and hardest to read, and the last stage is where the decision sits -
so it is a table.

**A number that does not exist prints a dash, never a zero.** A day whose visuals job never ran
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
visual and is not a published chart, so counting visuals instead would put a failure on the chart
arm's bill.

## Two controls that run after the model has answered

**Bars must measure the same thing.** The largest group of chosen bars that share a unit is kept
and the rest are dropped. This never invents a bar and never mixes units; it only ever removes. If
what remains is below `visuals.min_chart_points`, the item is decided to nothing.

**One quantity may fill one bar.** A draft that names the same `fact_index` twice is decided to
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

Chart is the only kind. `VisualKind` held four until 2026-09-05, and the other three are gone.

**Why there is no image renderer.** Measured on `ubuntu-latest` (4 vCPU, 16 GB),
2026-08-23, run `32654562728`: `Tongyi-MAI/Z-Image-Turbo` at bfloat16 loads in
159.2 s at 9.2 GB resident, then spends **527 s per denoising step** at 512x512.
Nine steps is about **79 minutes for one image** - longer than the whole `visuals`
job's 60-minute bound, and about 196 hours for a 149-item day against a 6-hour
job limit. The job was cancelled at step 7 of 9 and never reached 768px or a byte
count. The plan's second candidate, `alpha-vllm/Anima-2.9B`, answers 401
Repository Not Found: it does not exist. Reducing steps does not rescue it -
three steps is still 26 minutes, and one step is noise. Rule #2 says the budget
is the platform, so the feature goes rather than the budget. The `image` member
survived in the enum for two more weeks so that a payload could say it, and no
payload ever did: scanned 2026-09-05 over all 15 committed `digest.json` files,
6,425 items and 351 visuals, and every one is a chart. It was deleted on that
evidence.

**And why the diagram renderer went with it.** The arm shipped off on 2026-08-25
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

The renderer writes SVG into `frontend/public/digest/<YYYY>/<MM>/<DD>/<item_id>.svg`, beside the
payload that references it. A render failure records why and the item publishes without a
picture. No failure path raises.

**The name is the item's own id, so a path is a function of the item and of nothing else.**
`energy-4821903756.svg` - the same `<vertical>-<ten digits>` a reader already lands on as an anchor
([`layout.md`](layout.md)). Two items cannot share a path, so nothing has to notice that they did.

That is the third answer to one defect, and the first two are worth keeping on the page because they
are what a counter costs. **A per-process counter** restarted at 1 in every run, so the second run of
2026-08-24 overwrote the first run's file while the digest still referenced both items: 32 declared
visuals over 18 files, fourteen paths claimed twice, and `india-01.svg` shared by a stock-market
story and a defence-stocks story - one of them showing a chart of the other's numbers under alt text
describing figures that were not in the picture. **A counter seeded from the day's directory** fixed
that and could not fix the next one: a run takes about three hours and the day is refreshed five
times, so a second run is planning while the first is still summarizing, neither checkout can see what
the other has not pushed, and both read the same highest ordinal. Both wrote `energy-03.svg` for
different items with different bytes. The planner never found out; the push did, and run
`32869125768` lost eight workers and a visuals job at `CONFLICT (add/add)` over four asset paths, because
git cannot rebase two adds of one path. Every summary in the day expired with the `items-*`
artifacts.

The common factor is that a counter has to be seeded from something a process can observe, and two
processes observed different things. **An identity cannot be read from a directory.** That is the
whole of the fix, and it is why no third seeding rule was tried.

**What is left is one story rendered twice, and it has one right answer.** Two overlapping runs can
still both plan the same item, render it, and disagree about the bytes. That path is now the same
item on both sides, never two stories under one name - so there is nothing to choose between. The
tip's copy is published and a reader may already hold that address, and `build_day` keeps the tip's
item over this run's in any case, which makes this run's file the one nothing will reference. Before
each rebase attempt the commit step lists the asset paths the tip already publishes and hands them to
[`backend/utilities/drop_raced_assets.py`](../../../backend/utilities/drop_raced_assets.py), which
deletes this run's copy of any of them. The decision payload is left naming the same path, because after
the rebase the tip's file is sitting at it.

**Neither control repairs the day it already happened on.** Both stop a run standing on a path
another run published; neither revisits a payload that already names one file twice. 2026-08-24 kept
its 32 declared visuals over 18 files until it was repaired by hand on 2026-08-27, and it is the only
committed day that ever held one - the other five are one path per item. The repair nulls the visual
on **all 28** items that claimed a shared path, not one of each pair: nothing committed says which of
the two stories a chart was drawn for, so keeping one is a guess wearing a record's clothes. The four
singly claimed files keep their items. The 14 files nobody names any more are deleted - 172,164
bytes, three quarters of that day's picture weight, dead against the 1 GB Pages cap (Rule #2). No
reader-facing string was added: no picture is the common and correct answer and the page says nothing
about it, so a repaired item reads exactly like the 699 that never had one.

**`test_every_published_picture_belongs_to_exactly_one_item` is what would have caught it.** It reads
every committed day and holds the three ways a payload and its directory disagree: no two items share
a path, every declared path is a file that is there, and every file in a day directory is named by an
item. Against the pre-repair payload the first one fires and names all fourteen paths. It is
parametrized over the days it finds, so a second test asserts that count is not zero - a scan with no
input reports the same "no problems" as a scan that finds none.

Measured 2026-08-22 (8 vCPU, `vl-convert-python` 1.9.0.post1): a Vega-Lite render takes
2568 ms for the first call in a process and 49 ms warm, and produces about 7 KB of SVG. The cold
cost is engine boot, paid once per run rather than once per item.

## Design rationale

**Why the floor is a mark count and never `confidence`.** The ladder needs a number that rises with
depth, and the only per-plan number in the contract is `confidence` - which the shape itself says is
"recorded, and it gates nothing". Three reasons, and the cheapest one comes first: gating on it
breaks the shape's own written guarantee. It is also the one free number the model writes, so
prohibition 2 - "the worst a prompt injection can do is pick the wrong bars; it cannot draw the
wrong number" - would stop being true of publish decisions (Rule #11). And a model may not select
what publishes (`CLAUDE.md` section 0a). The mark count is code's own count over code's own
elements, and it is the quantity `enough_data` already rules on. Authority: Andre and Fowler, ruled
independently and agreeing, 2026-09-11.

**What the mark count cannot see, said rather than implied.** It is a floor, not a quality score. It
cannot tell whether the marks differ from each other, whether the labels are legible, or whether
anybody would choose to look - which is Susan's standing warning about this whole subsystem: every
binding gate here is integrity or cost, and a plain grey bar chart passes all of them.

**Why `none_reason` lives on the decision and not on the plan.** Two of its four members fire when
no plan object exists at all - the gate takes the plan fields off the request, and the budget cut
loses the plan's bytes - so a field on `VisualPlan` would be unwritable on exactly the routes it is
for. `VisualDecision` exists for every item either way, and `asked_the_model` and `drafted_chart`
are the same kind of fact in the same payload. Authority: Fowler, 2026-09-11.

**Why the edge table has a date-stamp of its own.** `PLAN_VOCABULARY_VERSION` is what
`plan_version_current` compares a plan against, so moving it re-plans every item carrying an older
one - a model call apiece. Adding a downgrade edge must not cost that, and `UNIT_TABLE_VERSION` set
the precedent for the same reason.

**Why the ladder ships inert rather than waiting for its ledger.** With no depth-0 population every
floor is uncomputable and every depth refuses, so today the ladder answers exactly as it would with
the flag off. That is deliberate: the edges, the invariants and the refusals are under test now, at
no reader-visible cost, and the one arm that needs a corpus is the one arm that waits. The
alternative - hold the whole mechanism back until `state/visuals/` lands - would put the edge table
and the invariance rules into the same commit as the ledger, where a review has to hold both.

**Why the call-2 prompt lost its plan half.** A turn that asks for fields the grammar cannot hold is
not ignored: constrained decoding renormalises onto the allowed tokens, so the text goes into the
only channel still open, which is the summary a reader reads. The same rule already governs the key
points, where asking for more than the grammar admits "would lose the item for doing what it was
told". The cost is that the unsuppressed turn moved as well: 2,614 characters to 2,555, with three
plan-referencing sentences relocated into the plan block. No rule was dropped - "summary first",
"finish the summary before you start the plan" and "you never type a number into the plan" all
survive, in the half where they are true. Authority: Andre, 2026-09-11.

**Why the reachability gate reads the validator's tables rather than a copy of its rules.** The gate
is a prediction of the validator, and a prediction written from somebody's reading of the rules is
wrong the first day a rule moves - silently, and in the direction that costs items their pictures.
Asking `TYPE_RULES`, `ROLE_KINDS`, `VALUE_ROLES` and `commensurable` directly means a rule can only
move in one place.

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

**Why the planner skips a call rather than running faster.** Measured 2026-08-24 on `ubuntu-latest`
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
unreachable, and asserts `to_decision` lands on `none` for all of them. One survivor would mean the
gate drops a chart a reader would have seen. That test is what makes "provable" a true word here,
and it only became true once one quantity was limited to one bar.

**The diagram arm is off, on the measurement it was waiting for.** The doc used to say "the arm
stays enabled until one run separates the three explanations - no exemplar in the prompt,
`min_diagram_steps` blocking short answers, or news items genuinely not being flowcharts." That run
landed. `32804437110` logs the draft kind beside the final kind: **17 chart drafts, 71 `none`
drafts, and 0 diagram drafts in 88 items.** The model is not asking for diagrams and our checks are
not rejecting them, so the first explanation is the live one - and the second and third cannot be
told apart without a prompt change nobody has a reason to make. Across 703 decided items on
2026-08-24/25 the arm produced nothing at all. Meanwhile it was the reason the reachability gate
above could never fire, which cost 46.9% of every day at 20.7 to 40.3 s an item.

So the arm is switched off in `visuals.enabled_kinds`, and the contract default follows, because a
fresh clone should not pay for it either (Rule #6: the sane default is the measured one). Nothing
else changes: the `diagram` enum member, the Mermaid writer, the SVG layout and their tests all
stay, and `TestToDecision` keeps both arms on so the rejection paths and the injection canaries still
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
every day it runs, the gate cannot fire and the planner spends the hour before publishing nothing.

**A day with no visuals says nothing to the reader.** Authority: Jony, 2026-08-25. "No picture" is
the normal answer for an item, so a day where the planner died reads exactly like a day where
nothing earned one, and both are honest. A line about our own missing machinery is the one thing on
the page a reader can neither verify nor act on. `items_failed` stays, because a missing story is
something the reader actually lost. The planner's failure belongs where an operator looks: the run
manifest's `items_routed` and `route_ms`, and the console.

**Why a raced chart is dropped rather than merged, refreshed, renumbered or picked between.**
Authority: the owner, 2026-08-27. Every cheaper-looking answer publishes a wrong picture instead of
failing, which is worse than losing a day because nobody finds out. Adding the day's directory to
`REFRESH_PATHS` makes the rebuild's hand-back delete every chart this run added that the tip lacks,
while the regenerated `digest.json` still names them - `assemble` copies the path from the decision
payload and cannot render anything - so the day publishes with broken images. Resolving the add/add
by a stated side has two outcomes and no third one; `-X theirs` gives our item the tip's picture,
`-X ours` overwrites an address a reader may already hold. **Renumbering was the answer while a path
could mean two different stories**, and it is the wrong answer now: the path names one item, so
moving this run's copy to some other name would file that item's picture under a name that is not
its own, and leave two files where the day references one. Dropping is what is left, and it costs
nothing - the rebuild keeps the tip's item, so this run's copy was never going to be referenced.

**Why the drop happens in the shell's retry loop and not inside `assemble`.** The rebase is what
fails, and it runs before `REGENERATE_COMMAND` does, so a fix that runs after it never gets to run
at all. The naming rule itself stays in `backend/idhazh/render/write.py`, which owns it: the shell
lists paths and pipes them, and a small argv wrapper under `backend/utilities/` does the work.
Bash never learns what an item id means (Rule #3).

**Why the budget became a stop rather than a louder warning.** `run.visual_planner_budget_minutes` already
existed and already logged when the stage went over. It fired after the fact, into a log nobody
reads until a reader notices a day with no pictures - and by then the run had already been
cancelled and had already binned its artifact. A warning that only ever describes a loss is not a
control. The same field now stops the loop, which is the smallest change that makes the job fit its
bound by design instead of by which host it drew (Rule #2).

**Two things about the 2026-08-24 repair are not in the record above.** Authority: owner,
2026-08-27.

The first is that no other committed day needs it. 2026-08-21 published no visual at all,
2026-08-22 and 2026-08-23 published one each, and 2026-08-25 (27 visuals over 27 files) and
2026-08-26 (40 over 40) name one file per item throughout. 2026-08-24 is the only day that ever
pointed two items at one picture, so the repair is a one-day event and not the first of a series.

The second is what that test - `backend/tests/test_published_assets.py` - costs the prune, and the
cost is the guard working rather than a false alarm. The prune - `visuals_older_than` in
[`retention.py`](../../../backend/idhazh/retention.py) - deletes an old day's SVGs and leaves the
payload that names them alone, on purpose: it removes visuals, never a day. So switching the prune
on fails the second of the test's three assertions - every declared path is a file that is there -
on the first day it prunes. The prune has to learn to null the item's `visual` as it deletes the
file before it can be enabled.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Skip call 2 entirely when the gate refuses | Call 2 is the call that writes the summary, so skipping it costs the item the thing a reader came for. The gate suppresses the plan fields inside the call and never the call (O43). |
| Suppress the plan with a smaller budget and leave the grammar whole | The decoder starts the plan and meets the cap part-way through, which spends the decode the gate exists to save and hands back a cut reply. The grammar is the control; a budget is a request. |
| Derive the suppressed budget as the full one minus the plan's characters | Two ways of computing one quantity, which disagree the first time a bound moves - and the one that is wrong is the one nobody reads. Both come off the same two-half arithmetic over their own schema. |
| Leave the plan half in the call-2 prompt when the grammar cannot hold it | Constrained decoding renormalises onto the allowed tokens, so a title, a caption and a reason with nowhere to go end up in the summary a reader reads. |
| `confidence` as the ladder's escalating floor | The contract says it gates nothing, it is the one free number the model writes, and a model may not select what publishes (`CLAUDE.md` section 0a). Gating it would also destroy it as a diagnostic. |
| Waive the floor when no depth-0 visuals have been published | Depth 1 would publish on the validator alone, which is depth 1 quietly becoming the default path - the failure the escalating floor exists to prevent. |
| A separate on-off flag beside the ladder's rungs | Two knobs that can disagree about one thing. Zero rungs is already an unambiguous no, and the rung count is already the maximum depth. |
| A `none_reason` member for each of the six gates the design record names | Four of the six have no code behind them, so four members would be words nobody can produce, nobody can retire and nobody can tell from a bug. Each arrives with the row that builds its gate. |
| Put `none_reason` on `VisualPlan` as a third code-stamped field | Two of its four routes fire when no plan object exists at all, so the field would be unwritable on exactly the cases it is for. |
| A `line` to `bar` downgrade edge | The source document allows it "if the time axis is safely categorical", and nothing in this build can decide that. A condition nobody can evaluate is a condition nobody should encode. |
| Any chart to `table` at depth 2 | `table` has no role rule, so the validator refuses it by name. A target that cannot pass rescues nothing, and listing it would be a rung nobody can stand on. |
| Let the ladder move an element from one channel to another | It re-encodes the claim - the same date now means "a name on the axis" rather than "a point in time" - so the purpose survives in the field and not in the drawing. |
| Let a downgrade skip re-validation | Then a downgrade can publish the thing the original plan was refused for. |
| A repair retry instead of a ladder | A retry must perturb the input, and there is no rejection reason to feed back: the ladder was chosen over a repair retry precisely so that no validator failure ever re-calls the model. |
| A funnel of bars for the four chart counts on the console | The stages fall by an order of magnitude - 88 reached, 47 asked, 17 drafted, 9 published on 2026-08-25 - so the bar the decision rests on is the one a reader can barely see. A table gives every stage the same weight. |
| A model filter or a model legend on the console Charts table | A filter over two values hides half the data and saves nobody any work. When a second model has run enough days to compare, the ledger it is read from has to be truthful first. |
| Ask the model for a Vega-Lite spec directly | A fabricated axis value becomes reachable, and verifying it afterwards means parsing an arbitrary spec to work out which numbers are data. |
| Raise `visuals`'s `timeout-minutes` | The budget is the platform, not a preference (Rule #2). It also fixes nothing: the per-item cost doubles between runner hosts, so any bound is a coin toss until the work inside it is bounded. |
| Shard the `visuals` job across a matrix | **Unblocked on 2026-08-27 and still not built.** It was blocked on the asset name: a per-vertical counter seeded from the day's directory meant four shards would each read the same highest ordinal and two would write `energy-01.svg`, silently, long before any commit. Naming the asset from the item id removes that, so sharding is now an ordinary throughput change rather than a contract one - and it is the strongest lever left, because the stage spends its whole 40-minute budget on ten of the eleven runs on record. Nobody has measured what a sharded planner costs in cache restores and model loads against what it saves, and that measurement is the work. |
| Keep the per-vertical counter and seed it better | Every seeding rule reads something a process can observe, and the defect is that two processes observe different things. A per-process counter lost 2026-08-24; a directory-seeded counter lost run `32869125768`. There is no third thing to read. |
| Name the asset from a hash of the address, `<vertical>-<url_key prefix>.svg` | It fixes the same defect as the item id and breaks a rule the item id does not: [`layout.md`](layout.md) says no hash appears in any path, filename or URL, and `backend/tests/test_contracts.py::test_no_hash_appears_in_any_published_path` holds it. The item id is already a published address - it is the anchor a reader lands on - so it costs the reader nothing that has not already been accepted. |
| Add the day's directory to `REFRESH_PATHS` | The hand-back deletes what the tip lacks and restores what it has, so this run's own charts are deleted while the rebuilt `digest.json` still names them, and the colliding one comes back with the other story's bytes. A broken image and a wrong image, published, instead of a job that failed loudly. |
| Resolve the add/add with `-X ours` or `-X theirs` | `theirs` puts the tip's picture under our alt text; `ours` overwrites an address a reader may already hold. Neither side of a coin flip is a correct answer to "whose chart is this". |
| Leave the 2026-08-24 day as history and let retention prune it | Retention never removes it. `retention.image_months` is `-1`, which switches the prune off entirely, and the prune deletes visuals rather than days, so it would never reach a payload even switched on. "Let it age out" is not a thing that happens here; the day stays wrong until somebody edits it. |
| Keep the first claimant's chart and null only the second | The order two items sit in a payload is not evidence of which one the chart was drawn for. This repairs 14 items by guessing on the other 14, and a guess that publishes is the failure being fixed. |
| Re-render the 2026-08-24 day from its committed decisions | Not rejected - impossible. It was offered as the thorough option in a handover and could never have been taken: the `visuals` artifact carries `retention-days: 1` and nothing under `backend/var/` is committed, so that day's decisions expired on 2026-08-25, before anyone read the handover. |
| Renumber a raced chart instead of dropping it | Right while a path could mean two different stories, wrong now that it names one item. Moving this run's copy would file that item's picture under a name that is not its own, and leave two files where the day references one. |
| Cap the number of items the planner may consider | A count has to be set for the worst host, so a fast host would decide 88 items and then idle for half an hour. The clock is the thing that runs out, so bound the clock. The same proposal moved back to the planning step was refused on 2026-08-25 for this reason and three more, including that it would delete about 436 items from a 731-item day - [../sources/freshness.md](../sources/freshness.md). |
| A `skip_unreachable` config flag | A knob whose `false` setting means "spend 21 measured seconds proving a theorem you already proved". Nobody would set it. The predicate is derived from `min_chart_points` and `enabled_kinds`, which are already config. |
| Give a budget-stopped item a `VisualDecision` saying so | It would land in `items_prefiltered`, which counts one specific cause, and it would freeze a `none` into the published day that a later run can never lift. Not writing a payload is what an unreached item already looks like. |
| A keyword pre-filter to rescue the diagram arm | Fetched words would steer our control flow. Rule #11 in spirit, with no prompt involved. |
| A second, smaller model to triage items first | Two calls where the point was zero. |
| Diffusion for charts | Produces a beautiful picture of a chart with hallucinated axis labels. |
| A charting library in the renderer | `vl-convert` takes a spec to PNG or SVG with no browser and no runtime JavaScript. |
| `mermaid-cli` for diagrams | A headless Chromium to lay out a linear chain of boxes. |
| PNG or WebP for charts and diagrams | A bar chart is a dozen paths. The vector is smaller than any raster of it, stays sharp on a phone, and costs the retention budget less. Raster stays the right answer for a photographic image. |
| Discard the whole chart when one bar disagrees on units | Observed live: the model picked three correct year-on-year megawatt bars and appended the sector headcount. Three good bars thrown away to reject one bad one. |
| A model checks the plan | A judge that shares the failure modes of the thing judged is not a measurement (`CLAUDE.md` section 0a). Every check the plan needs is a comparison against the article's own element table, which is committed data - so the model buys nothing and costs the only guarantee the subsystem sells. |
| Compare unit strings for equality in the validator | Cheaper, and wrong in the direction that matters: it refuses `4,200 tonnes` beside `4.2 kt`, which is the pair a reader most needs joined, while accepting `tonnes` beside `t` only by accident of spelling. |
| Put the per-type role table in `config/` | It is a relation between two Python enums, and a JSON file can reference neither - so the copy there would be a second spelling that drifts from both. It is also not a knob: a config edit that let a `bar` draw `bins` would publish a plan no compiler has a template for. |
| Return one refusal string from the validator | Cheaper to write and it makes every rule unfalsifiable at once. Nothing can then say which check fired, so no check can be retired, tuned or shown to work - and a fixture that trips three rules proves none of them. |
| Plan on the 8B | Classification is the easy task. The big model belongs on summarization, and a second set of weights would not fit the pass anyway. |
| Keep `image` out of the enum until it is built | A payload must be able to say `image`, and the four-way vocabulary is a contract. The gate belongs in config, so switching it on is an edit rather than a schema change. |

## See also

- [`../../concepts/digest.md`](../../concepts/digest.md) - the visual rule this serves.
- [`../contracts/schemas.md`](../contracts/schemas.md) - where a persisted shape lives, and the drift gate over it.
- [`../../reference/github-actions.md`](../../reference/github-actions.md) - the commit loop that drops a raced chart.
- [`../sources/trust-boundary.md`](../sources/trust-boundary.md) - why article text is data.
- [`../contracts/determinism.md`](../contracts/determinism.md) - why decoding is pinned in one place.
- [`../../concepts/evaluation.md`](../../concepts/evaluation.md) - how a stage gets measured.
