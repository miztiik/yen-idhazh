# Where every drawn figure came from

**Last Updated**: 2026-09-23

Every number a reader reads off an axis has exactly one of two origins, and this
page is the whole of that promise: it is characters the article itself wrote, or
it is arithmetic code performed over those characters through a closed list of
four functions, carrying a chain back to every one of them. There is no third
way. What a plan may say, and what refuses one, is
[what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md);
who decides a picture at all is [visuals.md](visuals.md).

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

Whether two units may be joined at all is the validator's `units_convertible` check, in
[what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md#units-are-convertible-or-identical-not-merely-equal-strings).

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
stated once. The three bounds are all `config/` knobs and none is a number chosen in code (Guardrail #6);
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

## Three stamps, and none of them is a config key

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

## The two rates, and why both

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

## The two provenance invariants, ruled

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

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A fifth derived function | The list's shortness is the guarantee. `contracts/derived.py` raises at import if one appears, so adding one is an owner decision taken in the open rather than a widening that arrives as a diff. |
| `visuals.unit_table_version` as a config key | A stamp an operator can edit without editing the table it stamps is a stamp that lies, and every derived value that recorded it lies with it. |
| A tenth validator check for a histogram's bin count | It would fire on every histogram of every run for one config edit. The same fault is caught once, where the config loads, and named there. |
| Letting a derived value take another derived value as an input | A chain that nests can be complete at each hop and still name no element at the bottom, which is the one thing this contract exists to refuse. |
| Rounding a conversion that will not state exactly | A rounding decision hidden inside a mark is a figure the article did not write. It is refused instead, which fails closed on a unit table that grows. |

## See also

- [visuals.md](visuals.md) - who decides a picture at all, and where the pass runs.
- [what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md) - the nine checks a plan meets before any figure is resolved.
- [where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md) - what the compiler does with the figures this page resolves.
- [../extraction/elements.md](../extraction/elements.md) - the element table every Tier 1 figure is cut from.
- [../contracts/schemas.md](../contracts/schemas.md) - `DisplayedValue` and the persisted shapes around it.
- [../../reference/benchmarks/articles-that-state-a-whole.md](../../reference/benchmarks/articles-that-state-a-whole.md) - how often an article declares a whole its parts add up to.
